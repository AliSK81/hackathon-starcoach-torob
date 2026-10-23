"""The AI layer that runs next to the rule-based path (never in front of it).

Every function here is called by an async endpoint after the rule-based answer is already on screen.
The LLM only ever chooses among candidates the DB returned, or writes words about facts the DB gave it;
every id, number and name it returns is checked against that input before it is shown (R28, R20).
"""

import json
import re
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager

from starcoach import api
from starcoach import guide as guide_mod
from starcoach.filters import Filters
from starcoach.llm import LLMError, chat
from starcoach.textnorm import normalize

MAX_PARALLEL_LLM = 6
GATE_WAIT_S = 6.0  # a busy gate fails fast, so waiting AI requests can never hold every worker thread
_gate = threading.BoundedSemaphore(MAX_PARALLEL_LLM)


@contextmanager
def llm_gate():
    """At most MAX_PARALLEL_LLM calls at once; raises LLMError when none frees up in time (callers keep the rule path)."""
    if not _gate.acquire(timeout=GATE_WAIT_S):
        raise LLMError("llm busy")
    try:
        yield
    finally:
        _gate.release()
PRICE_WORDS = ("تومان", "تومن", "ریال")
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class Memo:
    """A small thread-safe LRU with a time limit, so a repeated question costs no second LLM call."""

    def __init__(self, size: int = 512, ttl_s: float = 3600.0):
        self.size, self.ttl_s = size, ttl_s
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            hit = self._items.get(key)
            if hit is None:
                return None
            if time.time() - hit[0] > self.ttl_s:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return hit[1]

    def put(self, key, value) -> None:
        with self._lock:
            self._items[key] = (time.time(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)


# ---------- plumbing ----------
def digits_in(text: str) -> set[str]:
    """Digit runs in `text`, with Persian digits and thousands separators folded away."""
    folded = re.sub(r"(?<=\d)[,٬،](?=\d)", "", (text or "").translate(_FA_DIGITS))
    return set(re.findall(r"\d+", folded))


def parse_json_object(text: str) -> dict | None:
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def ask_json(settings, system: str, user: str, purpose: str, max_tokens: int = 500,
             timeout: float = 20.0, chat_fn=chat) -> dict | None:
    """One LLM call that must answer with a JSON object. None on any failure (the caller keeps the rule path)."""
    if not settings or not settings.llm_enabled:
        return None
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        with llm_gate():
            msg = chat_fn(settings, messages, max_tokens=max_tokens, purpose=purpose, timeout=timeout)
    except LLMError:
        return None
    return parse_json_object(msg.get("content") or "")


def clean_text(value, source: str = "", maxlen: int = 160, minlen: int = 3) -> str | None:
    """Text from the LLM that is safe to show: short, no price claims, no number that is not in `source`."""
    if not isinstance(value, str):
        return None
    text = re.sub(r"[*_`#]+", "", value).strip()
    if not (minlen <= len(text) <= maxlen) or any(w in text for w in PRICE_WORDS):
        return None
    if digits_in(text) - digits_in(source) or has_mixed_script(text):
        return None
    return text


def _filters_key(f: Filters) -> tuple:
    return (f.min_price, f.max_price, f.area, f.passage, f.lat, f.lon, f.radius_m, f.at.strftime("%Y%m%d%H"),
            f.open_only, f.installments, f.torobpay, f.in_person_pay, f.fast_delivery, f.warranty, f.sort)


_LETTER_RUN = re.compile(r"[A-Za-z؀-ۿ‌]+")


def has_mixed_script(text: str) -> bool:
    """A run of letters with both Persian and Latin ones is a model slip («استabilizer»), not real text.
    «ال‌جی-LG» is fine: the hyphen ends the Persian run before the Latin one starts."""
    return any(re.search(r"[A-Za-z]", w) and re.search(r"[؀-ۿ]", w) for w in _LETTER_RUN.findall(text))


def _list_clean(values, source: str, limit: int, maxlen: int = 140) -> list[str]:
    out = []
    for v in values if isinstance(values, list) else []:
        t = clean_text(v, source, maxlen)
        if t:
            out.append(t)
        if len(out) >= limit:
            break
    return out


# ---------- AI search: understand, widen, re-rank ----------
PLAN_SYSTEM = (
    "You help a Persian-speaking shopper search the catalog of Tehran's physical shops. You get the search text and "
    "the titles a plain keyword search already found. Answer ONLY with JSON: "
    '{"interpretation": "<one short Persian sentence: what the shopper is really after>", '
    '"queries": [<up to 4 short Persian (or Latin brand/model) product phrases that could find relevant products the '
    "keyword search missed: synonyms, the product TYPE behind a described need, popular models, spelling variants>], "
    '"clarify": null or {"question": "<short Persian question>", "options": [{"label": "<2-4 Persian words>", '
    '"query": "<search phrase if chosen>"}]}} '
    "When the text describes a NEED or PROBLEM instead of a product, `interpretation` says the need and `queries` names the "
    "product TYPES a shop would list to solve it (e.g. «پشت موبایلم همیشه گرم میشه» → «فن خنک کننده موبایل»; «میخوام توی ماشین "
    "موبایلم رو ببینم» → «هولدر موبایل ماشین»); the item they already own is NOT the product. "
    "Always give clarify (2-4 options, the most common kinds) when the text is only a broad category such as «کابل» or "
    "«شارژر», or is truly ambiguous; otherwise null. "
    "Never mention prices, shops or stock."
)
RANK_SYSTEM = (
    "You pick which numbered catalog products best fit a Persian-speaking shopper's request. Answer ONLY with JSON: "
    '{"picks": [{"n": <candidate number>, "why": "<at most 16 Persian words: the feature that makes it fit THIS request, '
    'or a trade-off to know; do not repeat the title>"}]} '
    "Best first, at most 6, spread across different kinds/brands when the request is broad. Only candidates that really fit "
    "(fewer is fine, empty if none). If the request describes a problem with something the shopper already owns, never pick "
    "that item itself, only products that solve the problem. "
    "Use only the information given; never mention prices, shops or stock; never invent specs; "
    "say nothing about brand reputation or quality beyond what the title or specs state."
)
SEARCH_LIMIT = 30
EXPANSION_TAKE = 6
_search_memo = Memo(size=512, ttl_s=1800)


def _clarify(raw, source: str = "") -> dict | None:
    if not isinstance(raw, dict):
        return None
    question = clean_text(raw.get("question"), source, 100)
    options = []
    for o in raw.get("options") or []:
        if isinstance(o, dict):
            label, query = clean_text(o.get("label"), source, 40, 2), clean_text(o.get("query"), source, 80, 2)
            if label and query:
                options.append({"label": label, "query": query})
    return {"question": question, "options": options[:4]} if question and len(options) >= 2 else None


def search_assist(conn, q: str, f: Filters, settings, chat_fn=chat) -> dict:
    """What the LLM adds to a search: a reading of the request, wider candidates, and a ranked short list with reasons.

    Candidates come from the normal search under the same filters, so every pick is a real product with a real
    seller under the user's conditions. The LLM only chooses among them."""
    started = time.time()
    if not settings or not settings.llm_enabled:
        return {"ok": False, "reason": "llm_unavailable"}
    key = (normalize(q), _filters_key(f))
    cached = _search_memo.get(key)
    if cached:
        return cached | {"cached": True}
    base = api.search(conn, q, limit=20, f=f, _relaxing=True)
    titles = "\n".join(f"- {it['title']} [{it['category']}]" for it in base["items"][:8]) or "(nothing found)"
    plan = ask_json(settings, PLAN_SYSTEM, f"Search text: {q}\nKeyword search ({base['mode']}) found:\n{titles}",
                    "search_plan", max_tokens=350, chat_fn=chat_fn)
    if plan is None:
        return {"ok": False, "reason": "llm_failed"}
    src = f"{q} {titles}"
    interpretation = clean_text(plan.get("interpretation"), src, 200)
    queries = [t for t in _list_clean(plan.get("queries"), src, 4, 80) if not has_mixed_script(t)]
    candidates: dict[str, dict] = {}
    for it in base["items"]:
        candidates[it["product_id"]] = {**it, "origin": "keyword"}
    for pq in queries:
        extra = api.search(conn, pq, limit=EXPANSION_TAKE, f=f, _relaxing=True)
        for it in extra["items"][:EXPANSION_TAKE]:
            candidates.setdefault(it["product_id"], {**it, "origin": pq})
        if len(candidates) >= SEARCH_LIMIT:
            break
    pool = list(candidates.values())[:SEARCH_LIMIT]
    picks: list[dict] = []
    if pool:
        lines = "\n".join(f"{i}. {c['title']} | دسته: {c['category']} | {c['n_shops']} فروشنده" for i, c in enumerate(pool, 1))
        ranked = ask_json(settings, RANK_SYSTEM, f"Shopper request: {q}\nCandidates:\n{lines}", "search_rank",
                          max_tokens=450, chat_fn=chat_fn)
        seen = set()
        for p in (ranked or {}).get("picks") or []:
            n = p.get("n") if isinstance(p, dict) else None
            if not isinstance(n, int) or not 1 <= n <= len(pool) or n in seen:
                continue
            seen.add(n)
            c = pool[n - 1]
            why = clean_text(p.get("why"), f"{c['title']} {q}", 160)
            picks.append({k: v for k, v in c.items() if k != "origin"} | {
                "ai_reason": why, "ai_new": c["origin"] != "keyword", "ai_query": None if c["origin"] == "keyword" else c["origin"]})
            if len(picks) >= 6:
                break
    result = {"ok": True, "interpretation": interpretation, "queries": queries, "clarify": _clarify(plan.get("clarify"), src),
              "picks": picks, "candidates": len(pool), "new_count": sum(1 for p in picks if p["ai_new"]),
              "ms": round((time.time() - started) * 1000)}
    _search_memo.put(key, result)
    return result


# ---------- why this seller ----------
PICK_SYSTEM = (
    "You explain to a Persian-speaking shopper, in plain words, why one shop was picked among the sellers of a product "
    "they will visit in person. Use only the facts given. Answer ONLY with JSON: "
    '{"summary": "<at most 2 short Persian sentences>", "ask": [<at most 2 concrete short Persian questions to ask this '
    "seller before going>]} "
    "Write no digits and no prices. Never say the item is in stock: prices are only what the seller recorded. "
    "Say nothing about the shop's reputation, trustworthiness or quality: only the given facts (open time, place, payment, warranty, price position)."
)
_pick_memo = Memo(size=512, ttl_s=1800)


def explain_pick(conn, product_id: str, f: Filters, settings, chat_fn=chat) -> dict | None:
    p = api.product(conn, product_id, f)
    if not p or not p["pick"]:
        return None
    entry = next((e for e in p["sellers"] if e["shop"]["shop_id"] == p["pick"]["shop_id"]), None)
    if entry is None:
        return None
    key = (product_id, entry["shop"]["shop_id"], _filters_key(f))
    if cached := _pick_memo.get(key):
        return cached
    shop, best = entry["shop"], entry["offers"][0]
    facts = {
        "product": p["title"], "category": p["category"],
        "specs": [f"{s.get('key')}: {s.get('value')}" for s in p["specs"][:8] if s.get("key")],
        "sellers_total": p["sellers_total"], "sellers_matching_user_conditions": len(p["sellers"]),
        "picked_shop": {"open_at_visit": shop["open_now"], "hours": shop["hours_status"], "where": shop["location_short"],
                        "distance_m": entry.get("distance_m"), "installment_providers": [x["provider"] for x in shop.get("payment", []) if x["installments"]],
                        "warranty": best["warranty_kind"]},
        "data_reasons": p["pick"]["why"],
    }
    out = ask_json(settings, PICK_SYSTEM, json.dumps(facts, ensure_ascii=False), "pick_summary", max_tokens=300, chat_fn=chat_fn)
    if not out:
        return None
    summary = clean_text(out.get("summary"), "", 260)
    if not summary or digits_in(summary):
        return None
    result = {"shop_id": entry["shop"]["shop_id"], "summary": summary,
              "ask": [a for a in _list_clean(out.get("ask"), "", 2, 100) if not digits_in(a)]}
    _pick_memo.put(key, result)
    return result


# ---------- guided choice in the user's own words ----------
ANSWERS_SYSTEM = (
    "A Persian-speaking shopper does not know which model to buy. Map what they wrote to the guide questions. "
    'Answer ONLY with JSON: {"answers": {"<question id>": "<an option value copied exactly>"}, '
    '"reply": "<one short Persian sentence: what you understood about their need>"} '
    "Answer every question the text gives any hint about (e.g. «ارزان» or «بودجه کم» = the lowest budget band, «بی‌سیم» = the wireless option); "
    "leave out only the questions the text says nothing about."
)
WHY_SYSTEM = (
    "You tell a Persian-speaking shopper why each shortlisted model fits what they said they need. Answer ONLY with JSON: "
    '{"items": [{"n": <number>, "why": "<at most 18 Persian words, tied to the shopper\'s need and to the given specs>"}]} '
    "Use only the specs given; never mention prices, shops or stock; never invent specs."
)
_guide_memo = Memo(size=256, ttl_s=1800)


def guide_answers(conn, q: str, text: str, category: str | None, f: Filters, settings, chat_fn=chat) -> dict | None:
    g = api.guide(conn, q, {}, f, category)
    if not g.get("questions"):
        return None
    key = ("ans", g["category"], normalize(text))
    if cached := _guide_memo.get(key):
        return cached
    lines = []
    for question in g["questions"]:
        opts = "; ".join(f"{o['value']} = {o['label']}" for o in question["options"])
        lines.append(f"{question['id']} — {question['text']} options: {opts}")
    out = ask_json(settings, ANSWERS_SYSTEM, f"Category: {g['category']}\nQuestions:\n" + "\n".join(lines) + f"\nShopper wrote: {text}",
                   "guide_answers", max_tokens=300, chat_fn=chat_fn)
    if out is None:
        return None
    valid = {question["id"]: {o["value"] for o in question["options"]} for question in g["questions"]}
    answers = {k: v for k, v in (out.get("answers") or {}).items() if isinstance(v, str) and v in valid.get(k, set())}
    result = {"category": g["category"], "answers": answers, "reply": clean_text(out.get("reply"), text, 200)}
    _guide_memo.put(key, result)
    return result


def guide_why(conn, q: str, text: str, answers: dict, category: str | None, f: Filters, settings, chat_fn=chat) -> dict | None:
    g = api.guide(conn, q, answers, f, category)
    sugg = g.get("suggestions") or []
    if not sugg:
        return None
    key = ("why", g["category"], tuple(sorted(answers.items())), tuple(s["product_id"] for s in sugg), normalize(text))
    if cached := _guide_memo.get(key):
        return cached
    said = []
    for question in g.get("questions", []):
        if (v := answers.get(question["id"])) is not None:
            label = next((o["label"] for o in question["options"] if o["value"] == v), v)
            said.append(f"{question['text']} {label}")
    blocks, sources = [], {}
    for i, s in enumerate(sugg, 1):
        row = conn.execute("SELECT specs FROM products WHERE product_id = ?", (s["product_id"],)).fetchone()
        specs = [f"{x.get('key')}: {x.get('value')}" for x in json.loads(row["specs"] or "[]")[:10] if x.get("key")] if row else []
        sources[i] = s["title"] + " " + " ".join(specs)
        blocks.append(f"{i}. {s['title']} ({s['why']})\n   " + "; ".join(specs))
    out = ask_json(settings, WHY_SYSTEM, f"Shopper said: {text or '-'}\nAnswers: {'; '.join(said) or '-'}\nModels:\n" + "\n".join(blocks),
                   "guide_why", max_tokens=450, chat_fn=chat_fn)
    if out is None:
        return None
    whys = {}
    for it in out.get("items") or []:
        n = it.get("n") if isinstance(it, dict) else None
        if isinstance(n, int) and n in sources and (t := clean_text(it.get("why"), sources[n] + " " + text, 180)):
            whys[sugg[n - 1]["product_id"]] = t
    result = {"why": whys}
    _guide_memo.put(key, result)
    return result


# ---------- alternatives: which substitute, and why ----------
ALT_SYSTEM = (
    "A shopper's shop is closed or out of stock. Rank the substitute products and say, in Persian, how each differs from "
    "the original in terms of use. Answer ONLY with JSON: "
    '{"items": [{"n": <number>, "why": "<at most 18 Persian words: the real difference and who it suits>"}], '
    '"advice": "<one short Persian sentence: what to do next>"} '
    "Best first. Use only the specs given; never mention prices; never say anything is in stock."
)
_alt_memo = Memo(size=256, ttl_s=900)


def explain_alternatives(conn, product_id: str, subs: list[dict], settings, chat_fn=chat) -> dict | None:
    if not subs:
        return None
    key = (product_id, tuple(s["product_id"] for s in subs))
    if cached := _alt_memo.get(key):
        return cached

    def specs_of(pid: str) -> list[str]:
        row = conn.execute("SELECT title, specs FROM products WHERE product_id = ?", (pid,)).fetchone()
        return [row["title"]] + [f"{x.get('key')}: {x.get('value')}" for x in json.loads(row["specs"] or "[]")[:8] if x.get("key")] if row else []

    orig = specs_of(product_id)
    sources = {i: " ".join(specs_of(s["product_id"])) for i, s in enumerate(subs, 1)}
    lines = [f"{i}. " + "; ".join(specs_of(s["product_id"])) for i, s in enumerate(subs, 1)]
    out = ask_json(settings, ALT_SYSTEM, "Original: " + "; ".join(orig) + "\nSubstitutes:\n" + "\n".join(lines), "alternatives_why",
                   max_tokens=450, chat_fn=chat_fn)
    if out is None:
        return None
    order, whys = [], {}
    for it in out.get("items") or []:
        n = it.get("n") if isinstance(it, dict) else None
        if isinstance(n, int) and n in sources and subs[n - 1]["product_id"] not in whys:
            whys[subs[n - 1]["product_id"]] = clean_text(it.get("why"), sources[n] + " " + " ".join(orig), 180)
            order.append(subs[n - 1]["product_id"])
    result = {"order": order, "why": whys, "advice": clean_text(out.get("advice"), "", 200)}
    _alt_memo.put(key, result)
    return result


# ---------- finding the shop inside the passage ----------
DIRECTIONS_SYSTEM = (
    "You help a shopper find one shop inside a shopping passage. From the address text and the neighbouring units, write "
    'in Persian how to find it: floor, unit, what is next to it. Answer ONLY with JSON: {"text": "<at most 2 short sentences>"} '
    "Use only the given facts; never invent a landmark, floor or number."
)
_dir_memo = Memo(size=512, ttl_s=3600)


def directions(conn, shop_id: str, settings, chat_fn=chat) -> dict | None:
    from starcoach import visit

    w = visit.in_passage(conn, shop_id)
    if w is None or not (w["address"] or w["passage"]):
        return None
    if cached := _dir_memo.get(shop_id):
        return cached
    facts = {"address": w["address"], "passage": w["passage"], "kind": w["passage_kind"], "floor": w["floor_label"],
             "unit": w["unit"], "plaque": None if w.get("plaque_is_building") else w["plaque"],
             "neighbours": [f"{n['name']} ({n['unit']})" for n in w["neighbours"][:4]]}
    source = json.dumps(facts, ensure_ascii=False)
    out = ask_json(settings, DIRECTIONS_SYSTEM, source, "directions", max_tokens=250, chat_fn=chat_fn)
    text = clean_text((out or {}).get("text"), source, 300)
    result = {"text": text} if text else None
    if result:
        _dir_memo.put(shop_id, result)
    return result


# ---------- the AI's own shortlist for a described need ----------
PICKS_SYSTEM = (
    "A Persian-speaking shopper described what they need. Choose the 3 best models from the numbered candidates for THAT need, "
    "using their specs, and spread the choices (e.g. best fit, best value, a step-up). Answer ONLY with JSON: "
    '{"picks": [{"n": <candidate number>, "why": "<at most 20 Persian words: which spec makes it fit the need, and a trade-off>"}]} '
    "Use only the given specs; never mention prices, shops or stock; never invent specs."
)
GUIDE_POOL = 14


def guide_picks(conn, q: str, text: str, answers: dict, category: str | None, f: Filters, settings, chat_fn=chat) -> dict | None:
    if not text.strip():
        return None
    g = api.guide(conn, q, {}, f, category)
    if not g.get("category"):
        return None
    key = ("picks", g["category"], tuple(sorted(answers.items())), normalize(text), _filters_key(f))
    if cached := _guide_memo.get(key):
        return cached
    pool = guide_mod.apply_answers(guide_mod.category_products(conn, g["category"]), answers)
    if f.active and pool:
        stats = api._seller_stats(conn, [p["product_id"] for p in pool], f)
        pool = [p for p in pool if stats[p["product_id"]]["match"]]
    pool = sorted(pool, key=lambda p: -p["n_shops"])[:GUIDE_POOL]
    if not pool:
        return None
    sources, lines = {}, []
    for i, p in enumerate(pool, 1):
        specs = [f"{k}: {v}" for k, v in list(p["specs"].items())[:10]]
        sources[i] = p["title"] + " " + " ".join(specs)
        lines.append(f"{i}. {p['title']} | " + "; ".join(specs))
    out = ask_json(settings, PICKS_SYSTEM, f"Shopper's need: {text}\nCandidates:\n" + "\n".join(lines), "guide_picks",
                   max_tokens=450, chat_fn=chat_fn)
    if out is None:
        return None
    picks, seen = [], set()
    for it in out.get("picks") or []:
        n = it.get("n") if isinstance(it, dict) else None
        if not isinstance(n, int) or n not in sources or n in seen:
            continue
        seen.add(n)
        card = api.product_card(conn, pool[n - 1]["product_id"], f)
        if card:
            picks.append(card | {"ai_reason": clean_text(it.get("why"), sources[n] + " " + text, 200)})
        if len(picks) >= 3:
            break
    result = {"picks": picks}
    _guide_memo.put(key, result)
    return result
