"""The AI layer, offline: a scripted LLM stands in for the gateway, so these check what the code does with its answers."""

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from starcoach import agent, ai
from starcoach.app import create_app
from starcoach.config import get_settings
from starcoach.db import connect
from starcoach.filters import Filters


def llm_settings(db):
    return replace(get_settings(), db_path=db, llm_base_url="http://llm.invalid", llm_api_key="k", llm_model="m")


def json_reply(obj):
    return lambda *a, **k: {"content": json.dumps(obj, ensure_ascii=False)}


class Script:
    """A fake chat(): answers come from a list, one per call, and every call is recorded."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, settings, messages, tools=None, tool_choice=None, max_tokens=0, purpose="", timeout=0):
        self.calls.append({"purpose": purpose, "messages": messages, "tools": [t["function"]["name"] for t in tools or []]})
        return self.answers.pop(0)


def tool_call(name, **args):
    return {"content": None, "tool_calls": [{"id": f"c{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}


# ---------- text safety ----------
def test_clean_text_blocks_price_claims_and_ungrounded_numbers():
    assert ai.clean_text("مناسب ورزش است") == "مناسب ورزش است"
    assert ai.clean_text("فقط ۲ میلیون تومان است") is None
    assert ai.clean_text("ظرفیت ۲۰۰۰۰ دارد", source="پاوربانک 20000 میلی آمپر") == "ظرفیت ۲۰۰۰۰ دارد"
    assert ai.clean_text("ظرفیت ۳۰۰۰۰ دارد", source="پاوربانک 20000 میلی آمپر") is None
    assert ai.clean_text("x") is None


def test_ground_numbers_drops_only_unbacked_prices():
    known = {2_500_000.0}
    text = "قیمت ثبت‌شده ۲٫۵ میلیون تومان است. قیمت دیگر ۹ میلیون تومان است. ۱۰ هزار میلی‌آمپر ظرفیت دارد."
    kept, clean = agent.ground_numbers(text.replace("٫", "."), known)
    assert "۹ میلیون" not in kept and "۱۰ هزار میلی‌آمپر" in kept and "۲.۵ میلیون" in kept
    assert clean is False
    assert agent.ground_numbers("سلام. دو فروشنده دارد.", known) == ("سلام. دو فروشنده دارد.", True)


def test_refs_never_reach_the_user():
    assert agent.deref("P1 را با S2 ببین", {"P1": "شارژر اپل"}) == "«شارژر اپل» را با ببین"


# ---------- AI search ----------
def test_search_assist_only_shows_real_candidates_and_caches(mini_db):
    conn = connect(mini_db, readonly=True)
    settings = llm_settings(mini_db)
    plan = {"interpretation": "شارژر اپل", "queries": ["شارژر اپل", "کابل شارژ"], "clarify": {
        "question": "کدام؟", "options": [{"label": "شارژر", "query": "شارژر اپل"}, {"label": "کابل", "query": "کابل شارژ"}]}}
    rank = {"picks": [{"n": 1, "why": "نزدیک‌ترین به درخواست"}, {"n": 999, "why": "ساختگی"}, {"n": 1, "why": "تکراری"}]}
    chat = Script(json_reply(plan)(), json_reply(rank)())
    out = ai.search_assist(conn, "شارژر اپل ۲۰ وات", Filters(), settings, chat_fn=chat)
    assert out["ok"] and out["interpretation"] == "شارژر اپل"
    assert len(out["picks"]) == 1 and out["picks"][0]["ai_reason"] and out["picks"][0]["product_id"].startswith("product_")
    assert out["clarify"]["options"][0]["query"] == "شارژر اپل"
    assert [c["purpose"] for c in chat.calls] == ["search_plan", "search_rank"]
    again = ai.search_assist(conn, "شارژر اپل ۲۰ وات", Filters(), settings, chat_fn=Script())  # would raise if it called the LLM
    assert again["cached"] and again["picks"] == out["picks"]


def test_search_assist_without_llm_or_on_failure(mini_db):
    conn = connect(mini_db, readonly=True)
    no_llm = replace(get_settings(), db_path=mini_db, llm_base_url="", llm_api_key="", llm_model="")
    assert ai.search_assist(conn, "شارژر", Filters(), no_llm)["ok"] is False

    def broken(*a, **k):
        raise ai.LLMError("down")
    assert ai.search_assist(conn, "هدفون ورزشی", Filters(), llm_settings(mini_db), chat_fn=broken) == {"ok": False, "reason": "llm_failed"}


def test_guide_answers_keep_only_real_options(mini_db):
    conn = connect(mini_db, readonly=True)
    g = ai.api.guide(conn, "هدفون", {}, Filters(), None)
    if not g["questions"]:
        pytest.skip("mini dataset has too few models for guide questions")
    q = g["questions"][0]
    good = q["options"][0]["value"]
    chat = Script(json_reply({"answers": {q["id"]: good, "nope": "x", "brand": "ساختگی"}, "reply": "فهمیدم"})())
    out = ai.guide_answers(conn, "هدفون", "یک متن", None, Filters(), llm_settings(mini_db), chat_fn=chat)
    assert out["answers"] == {q["id"]: good}


def test_pick_summary_is_rejected_when_it_states_numbers(mini_db):
    conn = connect(mini_db, readonly=True)
    pid = conn.execute("SELECT product_id FROM products WHERE n_shops >= 3 AND title_redacted = 0 LIMIT 1").fetchone()[0]
    settings = llm_settings(mini_db)
    bad = ai.explain_pick(conn, pid, Filters(), settings, chat_fn=Script(json_reply({"summary": "فقط ۳ میلیون است", "ask": []})()))
    assert bad is None
    ok = ai.explain_pick(conn, pid, Filters(at=Filters().at.replace(minute=1)), settings,
                         chat_fn=Script(json_reply({"summary": "نزدیک و باز است.", "ask": ["گارانتی دارد؟"]})()))
    assert ok and ok["summary"] == "نزدیک و باز است." and ok["ask"] == ["گارانتی دارد؟"]


# ---------- the agent ----------
def run(db, text, script, filters=None, state=None, history=None):
    conn = connect(db, readonly=True)
    events = list(agent.run_agent(conn, llm_settings(db), text, history, filters, state, chat_fn=script))
    assert events[-1]["event"] == "final"
    return events[:-1], events[-1]


def test_agent_searches_then_answers_with_cards_built_from_the_db(mini_db):
    script = Script(
        tool_call("search_products", query="شارژر اپل ۲۰ وات"),
        tool_call("respond", reply="این را پیدا کردم؛ P1 خوب است.", show=[
            {"type": "product", "ref": "P1", "note": "پرفروش"}, {"type": "product", "ref": "P99"}, {"type": "seller", "ref": "S5", "product": "P1"}],
            suggestions=["برای P1 از فروشنده بپرس"]),
    )
    steps, final = run(mini_db, "شارژر اپل می‌خوام", script)
    assert [s["tool"] for s in steps] == ["search_products", "search_products"]  # the server's dataset pre-search, then the model's
    assert [b["type"] for b in final["blocks"]] == ["product"]  # the invented P99 and S5 resolve to nothing
    card = final["blocks"][0]["item"]
    assert card["title"] and card["product_id"].startswith("product_") and final["blocks"][0]["note"] == "پرفروش"
    assert "P1" not in final["reply"] and card["title"][:10] in final["reply"]
    assert all("P1" not in s for s in final["suggestions"])
    assert final["state"]["refs"]["P1"]["id"] == card["product_id"]
    assert script.calls[0]["tools"][-1] == "respond"


def test_agent_applies_the_shoppers_conditions_by_rules_before_the_llm(mini_db):
    script = Script(tool_call("respond", reply="باشه."))
    steps, final = run(mini_db, "هدفون بی سیم زیر ۵ میلیون قسطی", script)
    assert steps[0]["tool"] == "rules"
    assert final["ctx_patch"]["max_price"] == 5_000_000 and final["ctx_patch"]["installments"] is True
    system = script.calls[0]["messages"][0]["content"]
    assert "installments only" in system and "5000000" in system


def test_agent_drops_a_price_the_tools_never_returned(mini_db):
    script = Script(tool_call("respond", reply="سلام. قیمتش ۹۹ میلیون تومان است."))
    _, final = run(mini_db, "سلام", script)
    assert "۹۹" not in final["reply"] and final["grounded"] is False


def test_agent_contacts_sellers_in_the_simulated_channel(mini_db):
    script = Script(
        tool_call("search_products", query="شارژر اپل ۲۰ وات"),
        tool_call("get_product", product="P1"),
        tool_call("contact_sellers", offers=["O1", "O2"], questions=["in_stock", "price_now", "bogus"]),
        tool_call("respond", reply="پرسیدم."),
    )
    steps, final = run(mini_db, "شارژر اپل ۲۰ وات؛ از دو فروشنده بپرس", script)
    assert [s["tool"] for s in steps] == ["search_products", "search_products", "get_product", "contact_sellers"]
    block = final["blocks"][0]
    assert block["type"] == "contacts" and len(block["results"]) == 2 and "نمایشی" in block["note"]
    assert all(r["offer_id"].startswith("offer_") for r in block["results"])


def test_agent_refuses_refs_it_was_not_given(mini_db):
    script = Script(tool_call("get_product", product="product_af3172caa21dd9a3e40e6349"), tool_call("respond", reply="نشد."))
    run(mini_db, "x", script)
    tool_msgs = [m for m in script.calls[1]["messages"] if m["role"] == "tool"]
    assert "unknown product ref" in tool_msgs[0]["content"]


def test_agent_keeps_refs_across_turns(mini_db):
    first = Script(tool_call("search_products", query="شارژر اپل ۲۰ وات"), tool_call("respond", reply="هست."))
    _, one = run(mini_db, "شارژر", first)
    second = Script(tool_call("get_product", product="P1"), tool_call("respond", reply="این هم فروشنده‌ها.", show=[{"type": "product", "ref": "P1"}]))
    _, two = run(mini_db, "فروشنده‌هاش؟", second, state=one["state"])
    assert two["blocks"][0]["item"]["product_id"] == one["state"]["refs"]["P1"]["id"]


def test_agent_survives_llm_failure_with_the_rule_path(mini_db):
    def broken(*a, **k):
        raise agent.LLMError("down")
    conn = connect(mini_db, readonly=True)
    events = list(agent.run_agent(conn, llm_settings(mini_db), "شارژر اپل ۲۰ وات", [], {}, None, chat_fn=broken))
    final = events[-1]
    assert final["reply"] and final["blocks"] and final["degraded"]


# ---------- endpoints ----------
@pytest.fixture()
def client(mini_db):
    return TestClient(create_app(replace(get_settings(), db_path=mini_db, llm_base_url="", llm_api_key="", llm_model="")))


def test_ai_endpoints_answer_without_a_key(client):
    assert client.get("/api/ai/search", params={"q": "شارژر"}).json()["ok"] is False
    assert client.get("/api/ai/directions/nope").json() == {"text": None}
    assert client.get("/api/ai/guide/picks", params={"q": "هدفون", "text": "ورزش"}).json() == {"picks": []}


def test_agent_endpoint_streams_steps_then_a_final_event(client):
    r = client.post("/api/agent", json={"text": "شارژر اپل ۲۰ وات زیر ۵ میلیون", "stream": True})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in r.text.split("\n\n") if line.startswith("data: ")]
    assert events[0]["event"] == "step" and events[-1]["event"] == "final"
    final = events[-1]
    assert final["degraded"] == "no_llm" and final["blocks"] and final["ctx_patch"]["max_price"] == 5_000_000
    plain = client.post("/api/agent", json={"text": "هدفون", "stream": False}).json()
    assert plain["event"] == "final" and plain["reply"]
    assert client.post("/api/agent", json={"text": ""}).status_code == 422


def test_busy_llm_gate_fails_fast_and_keeps_the_rule_path(monkeypatch, mini_db):
    import threading

    monkeypatch.setattr(ai, "_gate", threading.BoundedSemaphore(0))
    monkeypatch.setattr(ai, "GATE_WAIT_S", 0.05)
    assert ai.ask_json(llm_settings(mini_db), "s", "u", "t", chat_fn=Script()) is None  # no call is made; no thread is held
    conn = connect(mini_db, readonly=True)
    assert ai.search_assist(conn, "هدفون", Filters(), llm_settings(mini_db), chat_fn=Script())["ok"] is False


def test_model_slips_in_search_phrases_are_dropped():
    assert ai.has_mixed_script("استabilizer کولر") is True
    assert ai.has_mixed_script("محافظ برق JBL") is False


def test_stock_is_never_claimed_without_a_sellers_answer(mini_db):
    assert agent.claims_stock("این فروشنده موجود دارد") and not agent.claims_stock("ناموجود است و موجودی را بپرسید")
    assert agent.drop_stock_claims("سلام. شارژر موجود است. موجودی را بپرسید.") == ("سلام. موجودی را بپرسید.", False)
    script = Script(tool_call("search_products", query="شارژر اپل ۲۰ وات"),
                    tool_call("respond", reply="سلام. این فروشگاه شارژر موجود دارد.", show=[{"type": "product", "ref": "P1", "note": "موجود و قسطی"}]))
    _, final = run(mini_db, "شارژر", script)
    assert "موجود دارد" not in final["reply"] and final["blocks"][0]["note"] is None and final["grounded"] is False


def test_mixed_script_slips_are_repaired_from_known_names():
    titles = {"S1": "رامان دیسیلا"}
    assert agent.fix_mixed_script("از رaman پرسیدم", titles) == "از رامان پرسیدم"
    assert agent.fix_mixed_script("ال‌جی-LG خوب است", titles) == "ال‌جی-LG خوب است"
    assert ai.clean_text("محافظ رaman") is None


def test_negative_stock_phrasing_is_not_a_claim_and_a_cut_summary_is_replaced_by_the_servers():
    assert not agent.claims_stock("هیچ‌کدام موجود نیستند") and not agent.claims_stock("موجود ندارد")
    assert agent.claims_stock("موجود است") and agent.claims_stock("شارژر موجود داریم")
    rows = [{"in_stock": False, "status": "answered"}, {"in_stock": None, "status": "no_answer"}]
    assert agent.contact_summary(rows) == "از ۲ فروشنده پرسیدم (پاسخ نمایشی): ۱ فروشنده گفت ندارد، ۱ فروشنده جواب نداد.".replace("۲", "2").replace("۱", "1")


def test_dataset_is_searched_before_the_model_decides(mini_db):
    """R28: the model answers from its own knowledge only after seeing what the dataset has for the shopper's words."""
    script = Script(tool_call("respond", reply="سلام."))
    steps, _ = run(mini_db, "شارژر اپل ۲۰ وات", script)
    assert steps[0]["tool"] == "search_products"
    system = script.calls[0]["messages"][0]["content"]
    assert "Dataset search already done" in system and "P1" in system and "شارژر اپل" in system
    nothing = Script(tool_call("respond", reply="سلام."))
    run(mini_db, "زززززز", nothing)
    assert "Dataset search already done" not in nothing.calls[0]["messages"][0]["content"]
