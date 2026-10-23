"""LLM client for any OpenAI-compatible gateway (D10), and the request-refining step.

Rules always answer first; the LLM only refines. Every value it returns is checked against the DB's own
lists before use. Every call is logged to logs/llm_calls.jsonl (never the key).
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

from starcoach.config import Settings
from starcoach.hours import TEHRAN, now_tehran
from starcoach.intent import CONDITION_FA, Gazetteer
from starcoach.logs import log_event
from starcoach.textnorm import normalize

TIMEOUT_S = 12.0
CONDITIONS = list(CONDITION_FA)  # installments, torobpay, in_person_pay, fast, warranty, open
DAYS_EN = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
PRICE_MIN, PRICE_MAX = 1_000, 10_000_000_000


class LLMError(Exception):
    pass


def chat(settings: Settings, messages: list[dict], tools: list[dict] | None = None, tool_choice=None,
         max_tokens: int = 400, purpose: str = "chat", timeout: float = TIMEOUT_S) -> dict:
    """One chat-completions call. Returns the first choice's message. Raises LLMError on any failure."""
    if not settings.llm_enabled:
        raise LLMError("llm not configured")
    body: dict = {"model": settings.llm_model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2,
                  "chat_template_kwargs": {"enable_thinking": False}}  # F27: thinking costs 6+ s
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"
    req = urllib.request.Request(
        settings.llm_base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
    )
    started = time.time()
    record = {"purpose": purpose, "model": settings.llm_model}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf-8"))
        message = out["choices"][0]["message"]
        record.update(ok=True, ms=round((time.time() - started) * 1000), usage=out.get("usage"),
                      tool_calls=len(message.get("tool_calls") or []))
        return message
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        record.update(ok=False, ms=round((time.time() - started) * 1000), error=f"HTTP {e.code}: {detail}")
        raise LLMError(record["error"]) from e
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
        record.update(ok=False, ms=round((time.time() - started) * 1000), error=repr(e))
        raise LLMError(record["error"]) from e
    finally:
        log_event(settings.log_dir, "llm_calls", "llm_call", **record)


def _filters_tool(g: Gazetteer) -> dict:
    return {"type": "function", "function": {
        "name": "set_filters",
        "description": "Fill the shopping filters from the user's Persian request. Only fill what the user said or clearly implied.",
        "parameters": {"type": "object", "properties": {
            "product": {"type": "string", "description": "Short Persian product words to search, e.g. 'هندزفری بلوتوث' or 'گوشی سامسونگ A17'. Name the product type even if the user only described a need."},
            "max_price_toman": {"type": "integer", "description": "Budget ceiling in Toman. 'میلیون' = 1,000,000; colloquial bare 'تومن' usually means thousand for small items and million for phones/laptops."},
            "min_price_toman": {"type": "integer"},
            "area": {"type": "string", "enum": sorted(set(g.areas.values())), "description": "Tehran neighbourhood, if said or implied by a street (جمهوری→شیخ هادی, لاله زار→فردوسی)."},
            "passage": {"type": "string", "description": "Shopping passage name if the user named one, e.g. 'علاءالدین'."},
            "visit_day": {"type": "string", "enum": ["today", "tomorrow"] + DAYS_EN},
            "visit_hour": {"type": "integer", "minimum": 0, "maximum": 23},
            "conditions": {"type": "array", "items": {"type": "string", "enum": CONDITIONS},
                           "description": "installments = buy in installments/credit; torobpay; in_person_pay; fast = fast delivery; warranty = original/with warranty; open = must be open at visit time."},
            "cheap": {"type": "boolean", "description": "User wants the cheapest / budget option."},
            "intent": {"type": "string", "enum": ["search", "compare", "choose"],
                       "description": "choose = user doesn't know which model and wants help choosing."},
        }, "required": ["product", "intent"]},
    }}


SYSTEM = (
    "You turn a Persian in-store shopping request in Tehran into filters by calling set_filters exactly once. "
    "Never invent prices, shops or hours. Leave out anything the user did not say or clearly imply. "
    "A rule-based parser already read the request; its reading is given as a hint and may be incomplete or wrong.\n"
    "`product` is the item the user wants to BUY, named as a shop would list it — not an item they already own "
    "and not the activity. Examples (not from any test):\n"
    "- «برای یخچالم یه چیزی میخوام که نوسان برق اذیتش نکنه» → product «محافظ برق یخچال»\n"
    "- «گوشیم بیرون زود خالی میشه» → product «پاوربانک»\n"
    "- «برای سفر میخوام عکس بگیرم، با گوشی راضی نیستم» → product «دوربین عکاسی»\n"
    "- «تلویزیون رو میخوام به دیوار وصل کنم» → product «پایه دیواری تلویزیون»"
)


def _visit_at(day: str | None, hour: int | None, now: datetime) -> str | None:
    if not day and hour is None:
        return None
    base = now.astimezone(TEHRAN)
    if day == "tomorrow":
        base += timedelta(days=1)
    elif day in DAYS_EN:
        today = (base.weekday() + 2) % 7
        base += timedelta(days=(DAYS_EN.index(day) - today) % 7)
    h = hour if hour is not None else 11
    return base.replace(hour=h, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")


def _match_passage(name: str | None, g: Gazetteer) -> str | None:
    if not name:
        return None
    key = normalize(name)
    for k in (key, key.replace("پاساژ ", "").strip()):
        if k in g.passages:
            return g.passages[k]
    hits = [v for k, v in g.passages.items() if key in k or k in key]
    return hits[0] if len(hits) == 1 else None


def validate(args: dict, g: Gazetteer, now: datetime) -> tuple[dict, list[str]]:
    """Keep only values we can check. Returns (fields, dropped-reasons)."""
    dropped = []
    out: dict = {"filters": {}}
    product = (args.get("product") or "").strip()
    out["query"] = normalize(product, split_alnum=False) if product else ""
    for key, field_name in (("max_price_toman", "max_price"), ("min_price_toman", "min_price")):
        v = args.get(key)
        if isinstance(v, (int, float)) and PRICE_MIN <= v <= PRICE_MAX:
            out["filters"][field_name] = int(v)
        elif v is not None:
            dropped.append(f"{key}={v}")
    area = args.get("area")
    if area:
        if area in g.areas.values():
            out["filters"]["area"] = area
        else:
            dropped.append(f"area={area}")
    passage = _match_passage(args.get("passage"), g)
    if passage:
        out["filters"]["passage"] = passage
        out["filters"].pop("area", None)
    elif args.get("passage"):
        dropped.append(f"passage={args.get('passage')}")
    hour = args.get("visit_hour")
    hour = hour if isinstance(hour, int) and 0 <= hour <= 23 else None
    at = _visit_at(args.get("visit_day"), hour, now)
    if at:
        out["filters"]["at"] = at
    for c in args.get("conditions") or []:
        if c in CONDITIONS:
            out["filters"][c] = "1"
        else:
            dropped.append(f"condition={c}")
    out["cheap"] = bool(args.get("cheap"))
    out["intent"] = args.get("intent") if args.get("intent") in ("search", "compare", "choose") else "search"
    return out, dropped


def _understood(filters: dict, cheap: bool) -> list[dict]:
    items = []
    if "max_price" in filters or "min_price" in filters:
        lo, hi = filters.get("min_price"), filters.get("max_price")
        text = f"{lo:,} تا {hi:,}" if lo and hi else (f"تا {hi:,}" if hi else f"از {lo:,}")
        items.append({"key": "budget", "label": "بودجه", "text": text + " تومان"})
    for key in CONDITIONS:
        if filters.get(key):
            items.append({"key": key, "label": CONDITION_FA[key], "text": CONDITION_FA[key]})
    if filters.get("at"):
        items.append({"key": "at", "label": "زمان بازدید", "text": filters["at"].replace("T", " ")})
    for kind in ("passage", "area"):
        if filters.get(kind):
            items.append({"key": kind, "label": filters[kind], "text": filters[kind]})
    if cheap:
        items.append({"key": "cheap", "label": "ارزان‌ترین", "text": "ارزان"})
    return items


def refine_request(text: str, rules: dict, settings: Settings, g: Gazetteer | None = None,
                   now: datetime | None = None) -> dict:
    """Ask the LLM to read the request; on any failure return the rules result unchanged (marked)."""
    now = now or now_tehran()
    if g is None:
        from starcoach.db import connect

        g = Gazetteer.from_db(connect(settings.db_path, readonly=True))
    hint = {"query": rules.get("query"), "filters": rules.get("filters"), "intent": rules.get("intent")}
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Now (Tehran): {now.astimezone(TEHRAN):%A %Y-%m-%d %H:%M}\n"
                                    f"Rule parser hint: {json.dumps(hint, ensure_ascii=False)}\n"
                                    f"Request: {text}"},
    ]
    tool = _filters_tool(g)
    try:
        # F28: a forced {"type":"function",...} choice makes this gateway fill only required fields; "required" fills all
        msg = chat(settings, messages, tools=[tool], tool_choice="required", purpose="refine_request")
        calls = msg.get("tool_calls") or []
        if not calls:
            raise LLMError("no tool call")
        args = json.loads(calls[0]["function"]["arguments"] or "{}")
    except (LLMError, ValueError, KeyError) as e:
        return {**rules, "source": "rules", "llm_error": str(e)[:200]}
    fields, dropped = validate(args, g, now)
    return merge(rules, fields, dropped, settings)


DESCRIPTION_WORDS = 4  # a rules query longer than this is usually a described need, not product words


def _query_finds(query: str, settings: Settings) -> bool:
    from starcoach.db import connect
    from starcoach.search import search_products

    if not query:
        return False
    conn = connect(settings.db_path, readonly=True)
    try:
        return search_products(conn, query, limit=1)["mode"] == "and"
    finally:
        conn.close()


def merge(rules: dict, llm: dict, dropped: list[str], settings: Settings) -> dict:
    """Rules win on every slot they found (measured more accurate, Change 20); the LLM fills the gaps and
    names the product when the rules' query is a long description or finds nothing."""
    rule_f = rules.get("filters", {})
    rules_query = rules.get("query", "")
    rules_struggled = len(rules_query.split()) > DESCRIPTION_WORDS or not _query_finds(rules_query, settings)
    use_llm_query = bool(llm["query"]) and rules_struggled
    # On plain requests the rules are exact and the LLM adds slots nobody asked for (Change 20),
    # so the LLM fills gaps only when the request was a free description.
    filters = dict(llm["filters"]) if rules_struggled else {}
    if "area" in rule_f or "passage" in rule_f:
        filters.pop("area", None)
        filters.pop("passage", None)
    if "max_price" in rule_f or "min_price" in rule_f:
        filters.pop("max_price", None)
        filters.pop("min_price", None)
    filters.update(rule_f)
    query = llm["query"] if use_llm_query else rules_query
    cheap = bool(rules.get("cheap") or (llm["cheap"] and rules_struggled))
    intent = rules.get("intent") if rules.get("intent", "search") != "search" else llm["intent"]
    added = sorted(set(filters) - set(rule_f)) + (["query"] if use_llm_query else [])
    return {
        **rules,
        "query": query,
        "filters": filters,
        "understood": _understood(filters, cheap),
        "cheap": cheap,
        "intent": intent,
        "ambiguous": rules.get("ambiguous", {}) if "max_price" in rule_f or "min_price" in rule_f else {},
        "source": "rules+llm",
        "llm_added": added,
        "llm_dropped": dropped,
    }
