"""The shopping agent: a bounded tool-calling loop over the same read model the web app uses (R1-R9, R26-R29).

The LLM decides what to look up and how to talk; the DB decides every fact. So:
- it sees short refs (P1, S2, O3), never raw ids, and a ref it was not given resolves to nothing;
- every card it shows is built from the DB by the server, from the refs it names;
- numbers in its text must match numbers the tools returned, or that sentence is dropped (R20);
- contacting sellers is the simulated channel (phones are fake, D6) and is always marked as such.
"""

import difflib
import json
import re
import time
from collections.abc import Iterator

from starcoach import api, contact, hubs, review, visit
from starcoach.ai import has_mixed_script, llm_gate
from starcoach.config import Settings
from starcoach.filters import Filters, parse_filters
from starcoach.hours import now_tehran
from starcoach.intent import Gazetteer
from starcoach.llm import LLMError, chat, validate
from starcoach.logs import log_event

MAX_ROUNDS = 6
MAX_HISTORY = 10
MAX_TEXT = 600
CALL_TIMEOUT_S = 30.0
TOTAL_BUDGET_S = 75.0
STEP_LABELS = {
    "search_products": "دارم کالا را جست‌وجو می‌کنم…", "get_product": "فروشنده‌های این کالا را بررسی می‌کنم…",
    "compare_products": "کالاها را مقایسه می‌کنم…", "guide_questions": "سؤال‌های انتخاب مدل را از روی داده می‌سازم…",
    "set_filters": "شرایط شما را اعمال می‌کنم…", "find_alternatives": "جایگزین‌ها را پیدا می‌کنم…",
    "where_in_passage": "محل دقیق فروشگاه را پیدا می‌کنم…", "find_hubs": "بورس این کالا را در تهران پیدا می‌کنم…",
    "contact_sellers": "از فروشنده‌ها می‌پرسم…", "plan_visit": "مسیر بازدید را می‌چینم…",
    "product_review": "بررسی کالا را برمی‌دارم…", "get_shop": "اطلاعات فروشگاه را می‌خوانم…",
}
CLEARABLE = {  # what "clear" means: the raw filter params to drop, and the web app's ctx fields to reset
    "budget": (["max_price", "min_price"], ["max_price", "min_price"]),
    "place": (["area", "passage", "lat", "lon", "radius_m"], ["place", "radius_m"]),
    "time": (["at"], ["day", "hour"]),
    "open": (["open"], ["open"]), "installments": (["installments"], ["installments"]),
    "torobpay": (["torobpay"], ["torobpay"]), "in_person_pay": (["in_person_pay"], ["in_person_pay"]),
    "fast": (["fast"], ["fast"]), "warranty": (["warranty"], ["warranty"]),
}
_gazetteers: dict = {}


def _gazetteer(conn) -> Gazetteer:
    key = next((r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"), "main")
    if key not in _gazetteers:
        _gazetteers[key] = Gazetteer.from_db(conn)
    return _gazetteers[key]


# ---------- tool definitions ----------
def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required or []}}}


_REFS = {"type": "array", "items": {"type": "string"}}
TOOLS = [
    _tool("search_products", "Search the catalog of products sold in Tehran's physical shops, under the user's current "
          "filters. Returns product refs (P1…). Use short Persian product words, e.g. 'هندزفری بلوتوث'. Call again with other "
          "words if nothing fits.", {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 8}}, ["query"]),
    _tool("get_product", "A product's specs and its sellers (shop refs S…, offer refs O…) with recorded price, price age, "
          "open/closed at the visit time, distance, payment and the assistant's pick.", {"product": {"type": "string"}}, ["product"]),
    _tool("compare_products", "Compare 2-3 products side by side (sellers, cheapest recorded price, nearest, differing specs).",
          {"products": _REFS}, ["products"]),
    _tool("guide_questions", "For a shopper who does not know which model: data-derived questions (budget, brand, key specs) "
          "for the category of `query`, the options with counts, and up to 3 suggested models for the given answers.",
          {"query": {"type": "string"}, "answers": {"type": "object", "description": "question id -> option value, from an earlier call"}}, ["query"]),
    _tool("set_filters", "Apply the shopper's conditions to the app (the chips under the search box). Only what they said or "
          "clearly implied. Also use `clear` to remove conditions.", {
              "max_price_toman": {"type": "integer"}, "min_price_toman": {"type": "integer"},
              "area": {"type": "string", "description": "Tehran neighbourhood"}, "passage": {"type": "string", "description": "shopping passage name"},
              "visit_day": {"type": "string", "enum": ["today", "tomorrow", "sat", "sun", "mon", "tue", "wed", "thu", "fri"]},
              "visit_hour": {"type": "integer", "minimum": 0, "maximum": 23},
              "conditions": {"type": "array", "items": {"type": "string", "enum": ["installments", "torobpay", "in_person_pay", "fast", "warranty", "open"]}},
              "sort": {"type": "string", "enum": ["price", "distance"]},
              "clear": {"type": "array", "items": {"type": "string", "enum": [*CLEARABLE, "all"]}}}),
    _tool("find_alternatives", "When a shop is closed, does not answer or lacks the item: other open sellers of the same product "
          "(same passage first) and similar products.", {"product": {"type": "string"}, "shop": {"type": "string"},
                                                          "reason": {"type": "string", "enum": ["closed", "no_answer", "out_of_stock"]}}, ["product"]),
    _tool("where_in_passage", "Floor, unit and neighbouring shops that locate a shop inside its passage.", {"shop": {"type": "string"}}, ["shop"]),
    _tool("find_hubs", "Where in Tehran this kind of product is sold (its بورس): passages from the dataset first, then a cited list.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("contact_sellers", "Ask up to 3 sellers (by offer ref) the shopper's questions and report their answers. This channel is "
          "SIMULATED in this demo; say so. Questions: in_stock, price_now, hours_today, warranty, installments, hold.",
          {"offers": _REFS, "questions": {"type": "array", "items": {"type": "string", "enum": list(contact.QUESTIONS)}}}, ["offers"]),
    _tool("plan_visit", "Order several shops into one walk with arrival times and open-on-arrival checks.", {"shops": _REFS}, ["shops"]),
    _tool("product_review", "Market signals for a product (seller count, price spread, freshness, warranty) as honest review notes.",
          {"product": {"type": "string"}}, ["product"]),
    _tool("get_shop", "A shop's location, hours status, payment options and online pages.", {"shop": {"type": "string"}}, ["shop"]),
    _tool("respond", "Finish the turn. `reply` is shown to the shopper; `show` lists cards to attach (refs you were given); "
          "`suggestions` are 2-4 short follow-up taps.", {
              "reply": {"type": "string"},
              "show": {"type": "array", "items": {"type": "object", "properties": {
                  "type": {"type": "string", "enum": ["product", "seller", "compare", "hubs", "alternatives", "guide", "plan"]},
                  "ref": {"type": "string", "description": "product ref for product/alternatives, shop ref for seller"},
                  "product": {"type": "string", "description": "product ref a seller card belongs to"},
                  "refs": _REFS, "query": {"type": "string"}, "note": {"type": "string", "description": "<= 14 words why this card"}},
                  "required": ["type"]}},
              "suggestions": {"type": "array", "items": {"type": "string"}}}, ["reply"]),
]

SYSTEM = """You are StarCoach, a Persian shopping agent for buying in person in Tehran's shops, passages and bazaars. \
You help the shopper through the whole path: work out what to buy (even when they do not know the model), find shops that really \
list it, compare them by price, distance and opening hours, ask the shops, and say where to go.

How you work
- Facts come only from tools. Never invent products, prices, shops, hours or stock. Refs (P1, S2, O3) come only from tool results.
- Prices are what the seller recorded in Torob, never confirmed stock or today's price. Say «قیمت ثبت‌شده». Only after \
contact_sellers can you report an answer, and call it a simulated demo reply («پاسخ نمایشی»).
- A shop whose activity category matches is not a shop that has the item. Offer only shops from get_product / find_alternatives.
- Dataset first: when the dataset search has products for the request, show them as cards before anything from your own \
knowledge; hubs are extra. If search finds nothing, call find_hubs and tell the shopper where to go. Anything from your own knowledge \
must be labelled «از دانش عمومی؛ قبل از رفتن بررسی کنید».
- If the shopper does not know the model: call guide_questions, ask at most two short questions (offer the options as \
suggestions), then recommend up to 3 models and say why each fits their need, using only the specs you were given.
- When the shopper states a budget, area, passage, time or payment condition, your FIRST tool call must be set_filters \
(installment-only is a hard filter; «فردا عصر» is a visit time). The current conditions are listed below; respect them.
- Ask at most ONE question per turn, and never ask what they already told you. Even while asking, attach up to 3 suggested \
models from guide_questions as product cards, so every turn gives them something to tap.
- For «where can I buy / where is it sold», attach a hubs card (type hubs) when find_hubs returned dataset hubs or a cited list.
- If a shop is closed, silent or out of stock, immediately offer find_alternatives.
- Never write refs (P1, S2, O3) in `reply` or `suggestions`: use the product or shop name. Refs are only for tool arguments and `show`.
- Look things up before answering; chain tools when needed (search → get_product → contact_sellers). Finish every turn by calling respond.

Style: Persian, warm, short (at most 4 sentences), mobile-friendly, no markdown. Put the products and sellers you recommend in \
`show`, so the shopper sees real cards; do not repeat their details in the reply."""


def context_block(sess: "Session") -> str:
    now = now_tehran()
    f = sess.f
    parts = []
    if f.max_price or f.min_price:
        parts.append(f"budget {f.min_price or 0}-{f.max_price or 'any'} toman")
    if f.area or f.passage:
        parts.append(f"place {f.passage or f.area}")
    elif f.lat is not None:
        parts.append("near the shopper's location")
    for name, on in (("installments only", f.installments), ("TorobPay", f.torobpay), ("in-person payment", f.in_person_pay),
                     ("fast delivery", f.fast_delivery), ("warranty", f.warranty), ("open at visit time", f.open_only)):
        if on:
            parts.append(name)
    known = [f"{ref}: {sess.titles[ref]}" for ref in list(sess.titles)[-12:]]
    return (f"Now (Tehran): {now:%A %Y-%m-%d %H:%M}. Visit time: {f.at:%Y-%m-%d %H:%M}.\n"
            f"Current conditions: {', '.join(parts) or 'none'}.\nRefs already known: {'; '.join(known) or 'none'}.")


# ---------- the session: refs, filters, tools ----------
class Session:
    def __init__(self, conn, settings: Settings, filters: dict | None, state: dict | None):
        self.conn, self.settings = conn, settings
        self.raw: dict = {k: str(v) for k, v in (filters or {}).items() if v not in (None, "", False)}
        self.f: Filters = parse_filters(self.raw)
        self.refs: dict[str, str] = {}
        self.titles: dict[str, str] = {}
        state = state if isinstance(state, dict) else {}
        for ref, entry in list((state.get("refs") or {}).items())[-40:]:
            if re.fullmatch(r"[PSO]\d{1,4}", ref) and isinstance(entry, dict) and isinstance(entry.get("id"), str):
                self.refs[ref], self.titles[ref] = entry["id"], str(entry.get("title") or "")[:120]
        self.next_n = {k: 1 + max([int(r[1:]) for r in self.refs if r[0] == k] or [0]) for k in "PSO"}
        self.numbers: set[float] = {float(v) for v in (self.f.min_price, self.f.max_price) if v}
        self.patch: dict = {}
        self.clear: set[str] = set()
        self.contacts: list[dict] = []
        self.last_found: list[str] = []
        self.used: list[str] = []

    # refs
    def ref(self, kind: str, ident: str, title: str | None = None) -> str:
        for r, i in self.refs.items():
            if r[0] == kind and i == ident:
                if title:
                    self.titles[r] = title
                return r
        r = f"{kind}{self.next_n[kind]}"
        self.next_n[kind] += 1
        self.refs[r] = ident
        self.titles[r] = title or ""
        return r

    def resolve(self, ref, kind: str) -> str | None:
        if isinstance(ref, str) and ref in self.refs and ref[0] == kind:
            return self.refs[ref]
        return None

    def state(self) -> dict:
        return {"refs": {r: {"id": i, "title": self.titles.get(r, "")} for r, i in list(self.refs.items())[-40:]}}

    def note_numbers(self, obj) -> None:
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            self.numbers.add(float(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                self.note_numbers(v)
        elif isinstance(obj, list):
            for v in obj:
                self.note_numbers(v)

    def stock_confirmed(self) -> bool:
        """True only when a seller said «in stock» through the contact channel in this turn."""
        return any(c["in_stock"] is True for c in self.contacts)

    def restate_filters(self) -> None:
        self.f = parse_filters(self.raw)

    # ----- tools -----
    def t_search_products(self, query: str = "", limit: int = 6, **_) -> dict:
        r = api.search(self.conn, query, limit=min(max(int(limit or 6), 1), 8), f=self.f)
        items = []
        for it in r["items"]:
            ref = self.ref("P", it["product_id"], it["title"])
            items.append({"ref": ref, "title": it["title"], "brand": it["brand"], "category": it["category"], "sellers": it["n_shops"],
                          "sellers_matching_conditions": it["match_shops"] if r["filters_active"] else None,
                          "cheapest_recorded_price": it["match_min_price"] if r["filters_active"] else it["min_price"],
                          "sellers_open_at_visit": it["open_shops"]})
        self.last_found = [self.refs[i["ref"]] for i in items]
        out = {"query": query, "match": r["mode"], "corrected": r["corrected"], "conditions_active": r["filters_active"], "items": items}
        if r["relax"]:
            out["no_or_few_results_because_of"] = [x["label"] for x in r["relax"]]
        if not items:
            out["note"] = "no product matched; try other words, or find_hubs"
        return out

    def t_get_product(self, product: str = "", **_) -> dict:
        pid = self.resolve(product, "P")
        p = api.product(self.conn, pid, self.f) if pid else None
        if p is None:
            return {"error": "unknown product ref"}
        sellers = []
        for e in p["sellers"][:6]:
            shop, best = e["shop"], e["offers"][0]
            sellers.append({
                "shop": self.ref("S", shop["shop_id"], shop["name"]), "offer": self.ref("O", best["offer_id"], shop["name"]),
                "name": shop["name"], "recorded_price": best["price"], "price_status": best["price_status"],
                "price_last_changed": (e["last_change"] or "")[:10] or None, "open_at_visit": shop["open_now"],
                "hours": shop["hours_status"], "distance_m": e.get("distance_m"), "where": shop["location_short"], "area": shop["area"],
                "installment_providers": [x["provider"] for x in shop["payment"] if x["installments"]], "warranty": best["warranty_kind"]})
        pick = None
        if p["pick"]:
            pick = {"shop": self.ref("S", p["pick"]["shop_id"]), "why": p["pick"]["why"]}
        out = {"product": product, "title": p["title"], "brand": p["brand"], "category": p["category"],
               "specs": [f"{s.get('key')}: {s.get('value')}" for s in p["specs"][:12] if s.get("key")],
               "sellers_total": p["sellers_total"], "sellers_matching_conditions": len(p["sellers"]),
               "sellers": sellers, "assistant_pick": pick, "median_recorded_price": p["median_price"]}
        if not p["sellers"] and p["relax"]:
            out["no_sellers_because_of"] = [{"condition": x["label"], "sellers_if_removed": x["sellers"]} for x in p["relax"]]
        return out

    def t_compare_products(self, products: list | None = None, **_) -> dict:
        ids = [i for r in products or [] if (i := self.resolve(r, "P"))]
        if len(ids) < 2:
            return {"error": "give 2-3 known product refs"}
        c = api.compare(self.conn, ids, self.f)
        cols = [{"product": self.ref("P", x["product_id"], x["title"]), "title": x["title"], "sellers_matching": x["sellers_match"],
                 "cheapest_recorded_price": x["min_price"], "cheapest_shop": x["cheapest_shop"], "nearest_m": x["nearest_m"],
                 "installment_sellers": x["installment_sellers"], "warranty_sellers": x["warranty_sellers"]} for x in c["products"]]
        diffs = [{"spec": r["key"], "values": r["values"]} for r in c["spec_rows"] if not r["same"]][:10]
        return {"products": cols, "differing_specs": diffs}

    def t_guide_questions(self, query: str = "", answers: dict | None = None, **_) -> dict:
        answers = {k: v for k, v in (answers or {}).items() if isinstance(k, str) and isinstance(v, str)}
        g = api.guide(self.conn, query, answers, self.f)
        if not g.get("category"):
            return {"error": "no category found for this text; search_products with other words"}
        sugg = [{"product": self.ref("P", s["product_id"], s["title"]), "title": s["title"], "sellers_matching": s["sellers_match"],
                 "median_recorded_price": s["median_price"], "why": s["why"]} for s in g["suggestions"]]
        return {"category": g["category"], "models_in_category": g["products"], "models_matching_answers": g["matching"],
                "questions": [{"id": q["id"], "text": q["text"], "options": [{"value": o["value"], "label": o["label"], "models": o["count"]} for o in q["options"]]}
                              for q in g["questions"][:4]],
                "answers_so_far": answers, "suggestions": sugg}

    def t_set_filters(self, **args) -> dict:
        clears = args.pop("clear", None) or []
        if "all" in clears:
            clears = list(CLEARABLE)
        for name in clears:
            raw_keys, ctx_keys = CLEARABLE.get(name, ([], []))
            for k in raw_keys:
                self.raw.pop(k, None)
            self.clear.update(ctx_keys)
            for k in ctx_keys:
                self.patch.pop(k, None)
        sort = args.pop("sort", None)
        out, dropped = validate({**args, "product": ""}, _gazetteer(self.conn), now_tehran())
        self.apply_filters(out["filters"], out["cheap"], sort)
        return {"applied": dict(out["filters"]), "cleared": clears, "ignored_invalid": dropped}

    def apply_filters(self, new: dict, cheap: bool = False, sort: str | None = None) -> None:
        """Make validated filters (API param names) the session's conditions and queue the matching UI patch."""
        patch = api.ctx_patch(self.conn, {"filters": new, "cheap": cheap})
        if sort == "distance":
            patch["sort"] = "distance"
            self.raw["sort"] = "distance"
        if "place" in patch:
            for k in ("area", "passage", "lat", "lon"):
                self.raw.pop(k, None)
            pl = patch["place"]
            self.raw["area" if pl["kind"] == "area" else "passage"] = pl["name"]
            if pl.get("lat") is not None:
                self.raw["lat"], self.raw["lon"] = str(pl["lat"]), str(pl["lon"])
        for k, v in new.items():
            if k not in ("area", "passage"):
                self.raw[k] = str(v)
        self.clear -= set(patch)
        self.patch.update(patch)
        self.restate_filters()

    def t_find_alternatives(self, product: str = "", shop: str = "", reason: str = "closed", **_) -> dict:
        pid, sid = self.resolve(product, "P"), self.resolve(shop, "S")
        if not pid:
            return {"error": "unknown product ref"}
        a = visit.alternatives(self.conn, pid, sid, self.f.at, reason if reason in ("closed", "no_answer", "out_of_stock") else "closed")
        sellers = [{"shop": self.ref("S", s["shop_id"], s["name"]), "name": s["name"], "where": s["where"], "recorded_price": s["price"],
                    "open_at_visit": s["open_now"], "hours": s["hours_status"], "distance_m": s["distance_m"], "why": s["why"]} for s in a["sellers"]]
        subs = [{"product": self.ref("P", s["product_id"], s["title"]), "title": s["title"], "open_sellers": s["open_shops"],
                 "nearest_m": s["nearest_m"], "why": s["why"]} for s in a["substitutes"]]
        shops = [{"shop": self.ref("S", s["shop_id"], s["name"]), "name": s["name"], "where": s["where"]} for s in a.get("category_shops", [])[:3]]
        out = {"other_open_sellers": sellers, "similar_products": subs, "sellers_total": a["sellers_total"]}
        if shops:
            out["same_category_shops_not_listing_this_item"] = {"shops": shops, "warning": "they did NOT list this product; stock unknown"}
        return out

    def t_where_in_passage(self, shop: str = "", **_) -> dict:
        sid = self.resolve(shop, "S")
        w = visit.in_passage(self.conn, sid) if sid else None
        if w is None:
            return {"error": "unknown shop ref"}
        return {"passage": w["passage"], "kind": w["passage_kind"], "floor": w["floor_label"], "unit": w["unit"], "address": w["address"],
                "neighbours": [{"name": n["name"], "unit": n["unit"], "sells": n["category"]} for n in w["neighbours"][:4]]}

    def t_find_hubs(self, query: str = "", **_) -> dict:
        top = api.search(self.conn, query, limit=10, f=Filters(at=self.f.at))["items"] if query else []
        category = api.focus_category(top) or (top[0]["category"] if top else None)
        h = hubs.hubs(self.conn, category, query, self.f.at, None)
        out = {"category": category, "dataset_hubs": [{"name": x["name"], "kind": x["kind"], "shops_listing_it": x["shops"], "open_now": x["open"]} for x in h["data_hubs"]]}
        if h["known"]:
            out["cited_list"] = {"label": h["known"]["label"], "places": h["known"]["places"], "source": h["known"]["source"]}
        if not h["data_hubs"] and not h["known"]:
            out["note"] = "no data; you may name well-known Tehran hubs from your own knowledge but label them as unverified"
        return out

    def t_contact_sellers(self, offers: list | None = None, questions: list | None = None, **_) -> dict:
        qs = [q for q in (questions or []) if q in contact.QUESTIONS] or contact.DEFAULT_QUESTIONS
        visit_at = parse_filters({"at": self.raw["at"]}).at if "at" in self.raw else None
        results = []
        for ref in (offers or [])[:3]:
            oid = self.resolve(ref, "O")
            res = contact.contact(self.conn, oid, qs, visit_at) if oid else None
            if res is None:
                continue
            reply, facts = res["reply"], res["reply"]["facts"]
            row = {"offer": ref, "shop": self.ref("S", res["shop_id"], res["shop_name"]), "name": res["shop_name"], "status": reply["status"],
                   "in_stock": facts.get("in_stock"), "price_now": facts.get("price_now"), "price_changed": facts.get("price_changed"),
                   "recorded_price": res["recorded_price"], "hold_until": facts.get("hold_until"), "closes_at": facts.get("closes_at"),
                   "reply": reply["text"]}
            results.append(row)
            self.contacts.append({**row, "shop_id": res["shop_id"], "offer_id": res["offer_id"], "product_id": res["product_id"]})
            log_event(self.settings.log_dir, "contacts", "agent_contact", offer_id=res["offer_id"], shop_id=res["shop_id"],
                      questions=qs, status=reply["status"], facts=facts, simulated=True)
        if not results:
            return {"error": "no valid offer refs"}
        return {"simulated": True, "note": contact.SIMULATED_NOTE, "results": results,
                "advice": "if nobody confirmed stock, call find_alternatives" if not any(r["in_stock"] for r in results) else None}

    def t_plan_visit(self, shops: list | None = None, **_) -> dict:
        ids = [i for r in shops or [] if (i := self.resolve(r, "S"))]
        start = (self.f.lat, self.f.lon) if self.f.lat is not None and self.f.lon is not None else None
        p = visit.plan(self.conn, ids, self.f.at, start)
        return {"stops": [{"shop": self.ref("S", s["shop_id"], s["name"]), "name": s["name"], "arrive": s["arrive"], "walk_m": s["walk_m"],
                           "where": s["where"], "open_on_arrival": s["open_on_arrival"]} for s in p["stops"]],
                "total_walk_m": p["total_walk_m"], "warnings": [w["text"] for w in p["warnings"]]}

    def t_product_review(self, product: str = "", **_) -> dict:
        pid = self.resolve(product, "P")
        sig = review.signals(self.conn, pid) if pid else None
        if sig is None:
            return {"error": "unknown product ref"}
        return {"sellers": sig["sellers"], "with_warranty": sig["with_warranty"], "price_spread_ratio": sig["spread"], "notes": [n["text"] for n in sig["notes"]]}

    def t_get_shop(self, shop: str = "", **_) -> dict:
        sid = self.resolve(shop, "S")
        s = api.shop(self.conn, sid, self.f.at, limit=0) if sid else None
        if s is None:
            return {"error": "unknown shop ref"}
        return {"name": s["name"], "name_is_real": s["name_is_real"], "where": s["location_short"], "area": s["area"], "hours": s["hours_status"],
                "payment": [{"provider": p["provider"], "installments": p["installments"], "channel": p["channel_text"]} for p in s["payment"]],
                "instagram": s["instagram"], "website": s["website"], "activity_categories": s["categories"][:8], "products_listed": s["n_offers"]}

    def run_tool(self, name: str, args: dict) -> dict:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        try:
            out = fn(**args)
        except TypeError as e:
            out = {"error": f"bad arguments: {e}"}
        self.note_numbers(out)
        return out


# ---------- cards the server builds from the refs the model named ----------
def hydrate(sess: Session, show: list) -> list[dict]:
    blocks: list[dict] = []
    for s in (show or [])[:8]:
        if not isinstance(s, dict):
            continue
        kind, note = s.get("type"), s.get("note") if isinstance(s.get("note"), str) else None
        note = note.strip()[:140] if note and not any(w in note for w in ("تومان", "تومن", "ریال")) else None
        if note and (claims_stock(note) and not sess.stock_confirmed() or has_mixed_script(note)):
            note = None  # a card note never says «in stock» unless a seller said so
        if kind == "product" and (pid := sess.resolve(s.get("ref"), "P")):
            if card := api.product_card(sess.conn, pid, sess.f):
                blocks.append({"type": "product", "item": card, "note": note})
        elif kind == "seller" and (sid := sess.resolve(s.get("ref"), "S")) and (pid := sess.resolve(s.get("product"), "P")):
            p = api.product(sess.conn, pid, sess.f)
            entry = next((e for e in p["sellers"] if e["shop"]["shop_id"] == sid), None) if p else None
            if entry is None and p:  # the shop is outside the user's conditions: still show it, unfiltered
                p = api.product(sess.conn, pid, Filters(at=sess.f.at))
                entry = next((e for e in p["sellers"] if e["shop"]["shop_id"] == sid), None) if p else None
            if entry:
                blocks.append({"type": "seller", "entry": entry, "product_id": pid, "product_title": p["title"], "note": note})
        elif kind == "compare":
            ids = [i for r in s.get("refs") or [] if (i := sess.resolve(r, "P"))][:3]
            if len(ids) >= 2:
                blocks.append({"type": "compare", "products": [{"id": i, "title": sess.titles.get(next(r for r, v in sess.refs.items() if v == i), "")} for i in ids],
                               "table": api.compare(sess.conn, ids, sess.f)})
        elif kind == "hubs" and isinstance(s.get("query"), str):
            blocks.append({"type": "hubs", "q": s["query"][:100]})
        elif kind == "alternatives" and (pid := sess.resolve(s.get("ref"), "P")):
            blocks.append({"type": "alternatives", "product_id": pid, "shop_id": sess.resolve(s.get("shop"), "S") or ""})
        elif kind == "guide" and isinstance(s.get("query"), str):
            blocks.append({"type": "guide", "q": s["query"][:100]})
        elif kind == "plan":
            blocks.append({"type": "plan"})
    return blocks


# ---------- text safety ----------
_AMOUNT = re.compile(r"(\d[\d.,٬٫]*)\s*(میلیارد|میلیون|هزار)?\s*(تومان|تومن|ریال)?")
_SENTENCE_END = re.compile(r"(?<=[.!؟?])\s+|\n+")  # a "." inside «2.5» ends nothing
_MULT = {"میلیارد": 1e9, "میلیون": 1e6, "هزار": 1e3, None: 1.0}
PRICE_TOLERANCE = 0.06
SPEC_UNIT = re.compile(r"\s*(?:میلی|مگا|گیگ|ترا|وات|آمپر|ولت|دور|متر|سانت|اینچ|پیکسل|عدد|mah|gb|mhz)", re.I)


def ground_numbers(text: str, known: set[float]) -> tuple[str, bool]:
    """Drop every sentence that states a price-sized amount no tool returned (and no budget the shopper set)."""
    sentences = _SENTENCE_END.split(text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٫", "0123456789.")))
    keep, clean = [], True
    originals = _SENTENCE_END.split(text)
    for orig, folded in zip(originals, sentences, strict=False):
        ok = True
        for m in _AMOUNT.finditer(folded):
            if not (m.group(2) or m.group(3)) or SPEC_UNIT.match(folded[m.end():]):
                continue  # a bare number or a spec («۱۰ هزار میلی‌آمپر») is not a price claim
            try:
                value = float(m.group(1).rstrip(".,٬٫").replace(",", "").replace("٬", "")) * _MULT[m.group(2)]
            except ValueError:
                continue
            if value >= 10_000 and not any(abs(value - k) <= PRICE_TOLERANCE * k for k in known if k):
                ok = False
        if ok:
            keep.append(orig)
        else:
            clean = False
    return " ".join(x for x in keep if x).strip(), clean


def _plain(text: str) -> str:
    return re.sub(r"[*_`#]+", "", text or "").strip()


# «موجود است/دارد» is a claim; «ناموجود», «موجودی» and «موجود نیست/ندارد» are not
_STOCK_CLAIM = re.compile(r"(?<!نا)موجود(?!ی)(?!\s*(?:نیست|نیستند|نبود|نمی|ندار|نداشت))")
_TRANSLIT = dict(zip("abcdefghijklmnopqrstuvwxyz", "ابکدهفگهیجکلمنوپقرستوووکیز", strict=True))


def claims_stock(text: str) -> bool:
    return bool(_STOCK_CLAIM.search(text))


def drop_stock_claims(text: str) -> tuple[str, bool]:
    """Remove sentences that say an item IS in stock. Stock is only known from a seller's answer (R15, R20)."""
    kept = [s for s in _SENTENCE_END.split(text) if not claims_stock(s)]
    return " ".join(kept).strip(), len(kept) == len([s for s in _SENTENCE_END.split(text) if s])


def contact_summary(results: list[dict]) -> str:
    """What the simulated sellers said, in the server's own words (counts only; the details are in the card)."""
    yes = sum(1 for r in results if r["in_stock"] is True)
    no = sum(1 for r in results if r["in_stock"] is False)
    silent = sum(1 for r in results if r["status"] == "no_answer")
    parts = [f"{n} فروشنده {what}" for n, what in ((yes, "موجودی را تأیید کرد"), (no, "گفت ندارد"), (silent, "جواب نداد")) if n]
    return f"از {len(results)} فروشنده پرسیدم (پاسخ نمایشی): " + "، ".join(parts) + "."


def fix_mixed_script(text: str, titles: dict[str, str]) -> str:
    """The model sometimes writes «رaman» for «رامان». Spell the Latin letters phonetically, then prefer a known name."""
    vocab = {w for t in titles.values() for w in re.findall(r"[؀-ۿ]+", t)}

    def one(m: re.Match) -> str:
        word = m.group(0)
        if not (re.search(r"[A-Za-z]", word) and re.search(r"[؀-ۿ]", word)):
            return word
        spelled = "".join(_TRANSLIT.get(ch.lower(), ch) for ch in word)
        close = difflib.get_close_matches(spelled, vocab, n=1, cutoff=0.7)
        return close[0] if close else spelled

    return re.sub(r"[A-Za-z؀-ۿ‌]+", one, text)


_REF_IN_TEXT = re.compile(r"(?<![A-Za-z0-9])[PSO]\d{1,4}(?![A-Za-z0-9])")


def deref(text: str, titles: dict[str, str]) -> str:
    """Refs are for the model only: show the title (or nothing) wherever one leaks into text."""
    def one(m: re.Match) -> str:
        title = titles.get(m.group(0), "")
        return f"«{title[:40]}»" if title else ""
    return re.sub(r"\s{2,}", " ", _REF_IN_TEXT.sub(one, text)).strip()


# ---------- the loop ----------
def _assistant_turn(message: dict) -> dict:
    turn = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("tool_calls"):
        turn["tool_calls"] = message["tool_calls"]
    return turn


def _fallback(sess: Session, text: str, why: str) -> dict:
    """No LLM (or it failed): the rule path answers, so the chat still works and says so."""
    parsed = api.ask(sess.conn, text, _gazetteer(sess.conn), settings=None)
    sess.patch.update(parsed["ctx_patch"])
    result = api.search(sess.conn, parsed["query"] or text, limit=3, f=parse_filters({**sess.raw, **{k: str(v) for k, v in parsed["filters"].items()}}))
    for it in result["items"]:
        sess.ref("P", it["product_id"], it["title"])
    show = [{"type": "product", "ref": next(r for r, i in sess.refs.items() if i == it["product_id"])} for it in result["items"]]
    reply = ("دستیار هوشمند الان در دسترس نیست؛ با جست‌وجوی ساده این‌ها را پیدا کردم." if result["items"]
             else "دستیار هوشمند الان در دسترس نیست و با جست‌وجوی ساده هم چیزی پیدا نشد؛ نام دیگری امتحان کنید.")
    return {"reply": reply, "show": show, "suggestions": [], "degraded": why}


def run_agent(conn, settings: Settings, text: str, history: list | None = None, filters: dict | None = None,
              state: dict | None = None, chat_fn=chat) -> Iterator[dict]:
    """Yields {"event": "step", ...} while it works, then one {"event": "final", ...}."""
    started = time.time()
    text = (text or "").strip()[:MAX_TEXT]
    sess = Session(conn, settings, filters, state)
    degraded = None
    final: dict | None = None
    # rules first (D12): budget, place, time and payment words are read exactly by the rule parser, so apply them before the LLM
    rules = api.ask(conn, text, _gazetteer(conn), settings=None)
    if rules["filters"]:
        sess.apply_filters(rules["filters"], rules["cheap"])
        yield {"event": "step", "tool": "rules", "label": "شرایط شما را از جمله‌تان برداشتم…"}
    if not settings.llm_enabled:
        final, degraded = _fallback(sess, text, "no_llm"), "no_llm"
    else:
        applied = f"\nAlready applied from the shopper's message by the rule parser: {', '.join(u['label'] for u in rules['understood'])}." if rules["understood"] else ""
        # dataset first (R28): search the shopper's own words before the model decides anything, so a product the dataset has
        # can never be skipped in favour of general knowledge
        pre = ""
        if rules["query"]:
            yield {"event": "step", "tool": "search_products", "label": STEP_LABELS["search_products"]}
            found = sess.run_tool("search_products", {"query": rules["query"], "limit": 5})
            if found.get("items"):
                sess.used.append("search_products")
                pre = (f"\nDataset search already done for the shopper's words «{rules['query']}» (use these refs; search again only with "
                       f"other words): {json.dumps(found, ensure_ascii=False)}")
        messages = [{"role": "system", "content": SYSTEM + "\n\n" + context_block(sess) + applied + pre}]
        for h in (history or [])[-MAX_HISTORY:]:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("text"), str):
                messages.append({"role": h["role"], "content": h["text"][:MAX_TEXT]})
        messages.append({"role": "user", "content": text})
        for round_no in range(MAX_ROUNDS):
            last = round_no == MAX_ROUNDS - 1 or time.time() - started > TOTAL_BUDGET_S
            tools = [t for t in TOOLS if t["function"]["name"] == "respond"] if last else TOOLS
            try:
                with llm_gate():
                    msg = chat_fn(settings, messages, tools=tools, tool_choice="required" if last else "auto", max_tokens=900,
                                  purpose="agent", timeout=CALL_TIMEOUT_S)
            except LLMError as e:
                degraded = f"llm_error: {str(e)[:120]}"
                break
            calls = msg.get("tool_calls") or []
            if not calls:
                final = {"reply": _plain(msg.get("content") or ""), "show": [], "suggestions": []}
                break
            messages.append(_assistant_turn(msg))
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    args = args if isinstance(args, dict) else {}
                except ValueError:
                    args = {}
                if name == "respond":
                    final = {"reply": _plain(str(args.get("reply") or "")), "show": args.get("show") or [],
                             "suggestions": [s.strip()[:60] for s in (args.get("suggestions") or []) if isinstance(s, str) and s.strip()][:4]}
                    break
                sess.used.append(name)
                yield {"event": "step", "tool": name, "label": STEP_LABELS.get(name, "…")}
                result = sess.run_tool(name, args)
                messages.append({"role": "tool", "tool_call_id": call.get("id") or name, "content": json.dumps(result, ensure_ascii=False)[:6000]})
            if final:
                break
        if final is None or not final["reply"]:
            if sess.last_found:  # the LLM found products but could not wrap up: show what it found
                final = final or {"reply": "", "show": [], "suggestions": []}
                final["reply"] = final["reply"] or "نتایج را پیدا کردم، اما دستیار نتوانست جمع‌بندی کند؛ کالاهای پیدا‌شده این‌هاست."
                final["show"] = final["show"] or [{"type": "product", "ref": next(r for r, i in sess.refs.items() if i == pid and r[0] == "P")} for pid in sess.last_found[:3]]
            else:  # nothing usable from the LLM at all: the rule path answers
                final = _fallback(sess, text, degraded or "empty")
                degraded = degraded or "empty"
    final["suggestions"] = [x for x in (deref(t, sess.titles) for t in final["suggestions"]) if x]
    reply = fix_mixed_script(deref(final["reply"], sess.titles), sess.titles)
    reply, grounded = ground_numbers(reply, sess.numbers)
    if not sess.stock_confirmed():
        reply, honest = drop_stock_claims(reply)
        grounded = grounded and honest
        if not honest and sess.contacts:  # the sentence that summed up the answers was cut: the server says it itself
            reply = f"{reply} {contact_summary(sess.contacts)}".strip()
    if not reply:
        reply = "نتیجه را در کارت‌های زیر ببینید؛ قیمت‌ها قیمت ثبت‌شده‌ی فروشنده‌اند، نه قیمت تأییدشده." if final["show"] else "چیزی پیدا نکردم؛ دقیق‌تر بگویید چه می‌خواهید."
    blocks = hydrate(sess, final["show"])
    if sess.contacts:
        blocks.insert(0, {"type": "contacts", "results": sess.contacts, "note": contact.SIMULATED_NOTE})
    out = {"event": "final", "reply": reply, "blocks": blocks, "suggestions": final["suggestions"], "ctx_patch": sess.patch,
           "ctx_clear": sorted(sess.clear), "state": sess.state(), "tools": sess.used, "grounded": grounded, "degraded": degraded,
           "ms": round((time.time() - started) * 1000)}
    yield out


def log_turn(settings: Settings, text: str, out: dict) -> None:
    log_event(settings.log_dir, "agent", "agent_turn", text=text[:200], tools=out["tools"], blocks=[b["type"] for b in out["blocks"]],
              grounded=out["grounded"], degraded=out["degraded"], ms=out["ms"])
