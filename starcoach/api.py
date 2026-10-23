"""Read model for the web app: plain dicts built only from DB values.

Labels that explain what a value means (for transparency) are built here, so every client shows
the same wording.
"""

import json
import sqlite3
from datetime import datetime

from starcoach.address import floor_label
from starcoach.filters import (
    INSTALLMENT_PROVIDERS,
    RELAXABLE,
    Filters,
    active_names,
    offer_matches,
    pick_seller,
    seller_reasons,
    shop_distance,
    shop_matches,
    without,
)
from starcoach.hours import is_open_at, now_tehran, status_text, week_table
from starcoach.search import search_products
from starcoach.textnorm import tokens
from starcoach.variants import parse_variant
from starcoach.variants import summarize as summarize_variants

CHANNEL_FA = {"in_person": "پرداخت حضوری در فروشگاه", "unknown": "نحوه پرداخت اعلام نشده"}
PRICE_STATUS_FA = {
    "ok": None,
    "suspicious": "قیمت با بقیه فروشنده‌ها خیلی فرق دارد؛ قبل از رفتن بپرسید",
    "call": "قیمت ثبت نشده؛ استعلام تلفنی",
    "invalid": "قیمت ثبت‌شده نامعتبر است",
}


OFFER_RANK = {"ok": 0, "suspicious": 1, "call": 2, "invalid": 3}


def _loads(value: str | None, default):
    return json.loads(value) if value else default


def shop_summary(row: sqlite3.Row, at: datetime) -> dict:
    hours = _loads(row["hours"], None)
    status = status_text(hours, at)
    location_parts = [
        f"{row['passage_kind']} {row['passage']}" if row["passage"] else None,
        floor_label(row["floor"]),
        f"واحد {row['unit']}" if row["unit"] else None,
        f"پلاک {row['plaque']}" if row["plaque"] and not row["unit"] else None,
    ]
    return {
        "shop_id": row["shop_id"],
        "name": row["name"],
        "name_is_real": bool(row["name_is_real"]),
        "area": row["area"],
        "passage": row["passage"],
        "floor": row["floor"],
        "location_short": "، ".join(p for p in location_parts if p) or None,
        "lat": row["lat"],
        "lon": row["lon"],
        "open_now": is_open_at(hours, at),
        "hours_status": status["text"],
        "instagram": row["instagram"],  # R31: the 112 real-named shops have Instagram or a website
        "website": row["website"],
    }


def payment_info(payment_json: str | None) -> list[dict]:
    out = []
    for p in _loads(payment_json, []):
        out.append({
            "provider": p["provider"],
            "channel": p["channel"],
            "channel_text": CHANNEL_FA.get(p["channel"], "نامشخص"),
            "installments": p["provider"] in INSTALLMENT_PROVIDERS,
        })
    return out


def offer_view(row: sqlite3.Row) -> dict:
    return {
        **parse_variant(row["seller_title"]),
        "shop_id": row["shop_id"],
        "offer_id": row["offer_id"],
        "seller_title": row["seller_title"],
        "description": row["description"],
        "price": row["price"],
        "price_raw": row["price_raw"],
        "price_status": row["price_status"],
        "price_note": PRICE_STATUS_FA[row["price_status"]],
        "price_changed_at": row["price_changed_at"],
        "warranty_kind": row["warranty_kind"],
        "warranty_text": row["warranty_text"],
    }


def _seller_stats(conn: sqlite3.Connection, product_ids: list[str], f: Filters) -> dict[str, dict]:
    """Per product: sellers matching `f`, the lowest matching normal price, and sellers open at the visit time."""
    stats: dict[str, dict] = {pid: {"match": set(), "open": set(), "min_price": None} for pid in product_ids}
    if not product_ids:
        return stats
    shop_cache: dict[str, tuple[bool, bool | None]] = {}
    for chunk in range(0, len(product_ids), 500):
        ids = product_ids[chunk:chunk + 500]
        rows = conn.execute(
            f"""SELECT o.product_id, o.price, o.price_status, o.warranty_kind,
                       s.shop_id, s.area, s.passage, s.lat, s.lon, s.fast_delivery, s.payment, s.hours
                FROM offers o JOIN shops s ON s.shop_id = o.shop_id
                WHERE o.product_id IN ({",".join("?" * len(ids))})""",
            ids,
        )
        for r in rows:
            cached = shop_cache.get(r["shop_id"])
            if cached is None:
                hours = _loads(r["hours"], None)
                cached = shop_cache[r["shop_id"]] = (
                    shop_matches(f, r, payment_info(r["payment"]), hours), is_open_at(hours, f.at))
            shop_ok, open_now = cached
            if not shop_ok or not offer_matches(f, r):
                continue
            st = stats[r["product_id"]]
            st["match"].add(r["shop_id"])
            if open_now:
                st["open"].add(r["shop_id"])
            if r["price_status"] == "ok" and (st["min_price"] is None or r["price"] < st["min_price"]):
                st["min_price"] = r["price"]
    return stats


FOCUS_TOP = 10
FOCUS_SHARE = 0.6


def product_card(conn: sqlite3.Connection, product_id: str, f: Filters) -> dict | None:
    """One product as a search-result card under the user's filters (the same shape search() items have)."""
    row = conn.execute(
        "SELECT product_id, title, brand, category, images, n_shops, min_price, median_price FROM products WHERE product_id = ?",
        (product_id,)).fetchone()
    if row is None:
        return None
    st = _seller_stats(conn, [product_id], f)[product_id]
    images = json.loads(row["images"] or "[]")
    return {"product_id": row["product_id"], "title": row["title"], "brand": row["brand"], "category": row["category"],
            "image": images[0] if images else None, "n_shops": row["n_shops"], "min_price": row["min_price"],
            "median_price": row["median_price"], "match_shops": len(st["match"]), "match_min_price": st["min_price"],
            "open_shops": len(st["open"])}


def focus_category(items: list[dict]) -> str | None:
    """The category the top results agree on (e.g. «گوشی سامسونگ» -> گوشی موبایل), if they clearly do."""
    top = [it["category"] for it in items[:FOCUS_TOP] if it.get("category")]
    if len(top) < 3:
        return None
    best = max(set(top), key=top.count)
    return best if top.count(best) / len(top) >= FOCUS_SHARE else None


RELAX_BELOW = 3  # with fewer results than this, suggest which filter to drop


def search(conn: sqlite3.Connection, q: str, limit: int = 20, f: Filters | None = None,
           all_categories: bool = False, _relaxing: bool = False) -> dict:
    """Ranked products. With active filters, only products with at least one matching seller are kept,
    and only in the category the unfiltered top results agree on (so filters don't surface accessories)."""
    f = f or Filters()
    result = search_products(conn, q, limit=400 if f.active else limit)
    candidates = result["items"]
    focus = None if all_categories or not f.active else focus_category(candidates)
    stats = _seller_stats(conn, [it["product_id"] for it in candidates], f)
    items = []
    for it in candidates:
        st = stats[it["product_id"]]
        if f.active and not st["match"]:
            continue
        if focus and it["category"] != focus:
            continue
        items.append({
            "product_id": it["product_id"],
            "title": it["title"],
            "brand": it["brand"],
            "category": it["category"],
            "image": it["images"][0] if it["images"] else None,
            "n_shops": it["n_shops"],
            "min_price": it["min_price"],
            "median_price": it["median_price"],
            "match_shops": len(st["match"]),
            "match_min_price": st["min_price"],
            "open_shops": len(st["open"]),
        })
        if len(items) >= limit:
            break
    relax = []
    if f.active and len(items) < RELAX_BELOW and not _relaxing:
        for name in active_names(f):
            alt = search(conn, q, limit=limit, f=without(f, name), all_categories=all_categories, _relaxing=True)
            if len(alt["items"]) > len(items):
                relax.append({"filter": name, "label": RELAXABLE[name], "products": len(alt["items"])})
        relax.sort(key=lambda r: -r["products"])
    return {"query": q, "words": result["words"], "mode": result["mode"], "total": result.get("total", 0),
            "filters_active": f.active, "focus_category": focus, "relax": relax, "items": items,
            "corrected": result.get("corrected", {})}


PRICE_UNIT_SPREAD = 3.0  # max/min normal price above this usually means different units (metre vs coil)


def _price_spread(conn: sqlite3.Connection, product_id: str) -> float | None:
    """Ratio of the highest to the lowest normal price across shops (per-shop minimum)."""
    rows = [r[0] for r in conn.execute(
        "SELECT MIN(price) FROM offers WHERE product_id = ? AND price_status = 'ok' GROUP BY shop_id", (product_id,))]
    if len(rows) < 2 or min(rows) <= 0:
        return None
    return round(max(rows) / min(rows), 2)


def _english_name(p: sqlite3.Row) -> str | None:
    """No English title field in the data (F19); use `model` or a Latin «نام محصول» spec when present."""
    # `model` is sometimes a junk slug («authentic-base-10189»); trust it only if it shares a word with the title
    if p["model"] and set(tokens(p["model"])) & set(tokens(p["title"])):
        return p["model"]
    for s in _loads(p["specs"], []):
        if s.get("key") == "نام محصول" and s.get("value") and s["value"].isascii():
            return s["value"]
    return None


def _age_days(later: str | None, earlier: str | None) -> float | None:
    if not later or not earlier:
        return None
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds() / 86400


def product(conn: sqlite3.Connection, product_id: str, f: Filters | None = None,
            _relaxing: bool = False) -> dict | None:
    """A product with its sellers, filtered and sorted by `f`, each seller with data-only reasons."""
    f = f or Filters()
    p = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if p is None:
        return None
    snapshot = conn.execute("SELECT value FROM meta WHERE key = 'snapshot'").fetchone()
    snapshot = snapshot[0] if snapshot else None
    rows = conn.execute(
        "SELECT o.*, s.* FROM offers o JOIN shops s ON s.shop_id = o.shop_id WHERE o.product_id = ?",
        (product_id,),
    ).fetchall()
    by_shop: dict[str, dict] = {}
    for r in rows:
        entry = by_shop.get(r["shop_id"])
        if entry is None:
            payment = payment_info(r["payment"])
            entry = by_shop[r["shop_id"]] = {
                "shop": shop_summary(r, f.at) | {"payment": payment, "fast_delivery": r["fast_delivery"]},
                "offers": [],
                "shop_ok": shop_matches(f, r, payment, _loads(r["hours"], None)),
                "distance_m": shop_distance(f, r["lat"], r["lon"]),
            }
        offer = offer_view(r)
        if offer_matches(f, offer):
            entry["offers"].append(offer)
    total = len(by_shop)
    sellers = []
    for entry in by_shop.values():
        if not entry.pop("shop_ok") or not entry["offers"]:
            continue
        # normal prices first, then far-off ("suspicious") ones, then no price
        entry["offers"].sort(key=lambda o: (OFFER_RANK[o["price_status"]], o["price"] or 0))
        best = entry["offers"][0]
        entry["best_price"] = best["price"]
        entry["best_status"] = best["price_status"]
        entry["last_change"] = max((o["price_changed_at"] or "" for o in entry["offers"]), default=None) or None
        if entry["distance_m"] is not None:
            entry["distance_m"] = round(entry["distance_m"])
        sellers.append(entry)
    by_price = lambda e: (OFFER_RANK[e["best_status"]], e["best_price"] or 0)  # noqa: E731
    if f.sort == "distance" and f.lat is not None:
        sellers.sort(key=lambda e: (e["distance_m"] is None, e["distance_m"] or 0, by_price(e)))
    else:
        sellers.sort(key=by_price)
    ok_prices = [e["best_price"] for e in sellers if e["best_status"] == "ok"]
    cheapest_shown = min(ok_prices) if ok_prices else None
    cheapest = p["min_price"]  # over all sellers, normal prices only
    for entry in sellers:
        entry["reasons"] = seller_reasons(entry, cheapest, f, _age_days(snapshot, entry["last_change"]),
                                          cheapest_shown)
    pick = pick_seller(sellers, lambda e: _age_days(snapshot, e["last_change"]))
    relax = []
    if not sellers and f.active and not _relaxing:
        # Which single filter, if removed, brings sellers back? (a quick alternative instead of a dead end)
        for name in active_names(f):
            alt = product(conn, product_id, without(f, name), _relaxing=True)
            if alt["sellers"]:
                relax.append({"filter": name, "label": RELAXABLE[name], "sellers": len(alt["sellers"])})
        relax.sort(key=lambda r: -r["sellers"])
    return {
        "product_id": p["product_id"],
        "title": p["title"],
        "title_redacted": bool(p["title_redacted"]),
        "brand": p["brand"],
        "category": p["category"],
        "model": p["model"],
        "images": _loads(p["images"], []),
        "specs": _loads(p["specs"], []),
        "n_shops": p["n_shops"],
        "min_price": p["min_price"],
        "median_price": p["median_price"],
        "price_spread": _price_spread(conn, product_id),
        "english_name": _english_name(p),
        "filters_active": f.active,
        "sellers_total": total,
        "sellers_hidden": total - len(sellers),
        "relax": relax,
        "pick": pick,
        "variants": summarize_variants([o for e in sellers for o in e["offers"]]),
        "sellers": sellers,
    }


def shop(conn: sqlite3.Connection, shop_id: str, at: datetime | None = None, limit: int = 100) -> dict | None:
    at = at or now_tehran()
    s = conn.execute("SELECT * FROM shops WHERE shop_id = ?", (shop_id,)).fetchone()
    if s is None:
        return None
    hours = _loads(s["hours"], None)
    products = conn.execute(
        """SELECT p.product_id, p.title, p.category, p.images, MIN(o.price) AS price, COUNT(*) AS variants,
                  MAX(o.price_changed_at) AS last_change
           FROM offers o JOIN products p ON p.product_id = o.product_id
           WHERE o.shop_id = ? AND p.title_redacted = 0
           GROUP BY p.product_id ORDER BY p.n_shops DESC LIMIT ?""",
        (shop_id, limit),
    ).fetchall()
    return {
        **shop_summary(s, at),
        "address": s["address"],
        "unit": s["unit"],
        "plaque": s["plaque"],
        "passage_kind": s["passage_kind"],
        "phone": s["phone"],
        "instagram": s["instagram"],
        "website": s["website"],
        "hours_week": week_table(hours),
        "fast_delivery": s["fast_delivery"],
        "payment": payment_info(s["payment"]),
        "categories": _loads(s["categories"], []),
        "n_offers": s["n_offers"],
        "products": [
            {
                "product_id": r["product_id"],
                "title": r["title"],
                "category": r["category"],
                "image": (_loads(r["images"], []) or [None])[0],
                "price": r["price"],
                "variants": r["variants"],
                "last_change": r["last_change"],
            }
            for r in products
        ],
    }


COMPARE_MAX = 3
COMPARE_SPECS = 30


def compare(conn: sqlite3.Connection, product_ids: list[str], f: Filters | None = None) -> dict:
    """2-3 products side by side: price and sellers under the user's filters, plus aligned specs."""
    f = f or Filters()
    cols = []
    for pid in product_ids[:COMPARE_MAX]:
        p = product(conn, pid, f)
        if p is None:
            continue
        sellers = p["sellers"]
        priced = [e for e in sellers if e["best_status"] == "ok"]
        cheapest = min(priced, key=lambda e: e["best_price"]) if priced else None
        nearest = min((e for e in sellers if e["distance_m"] is not None), key=lambda e: e["distance_m"], default=None)
        changes = [e["last_change"] for e in sellers if e["last_change"]]
        cols.append({
            "product_id": p["product_id"],
            "title": p["title"],
            "brand": p["brand"],
            "category": p["category"],
            "image": (p["images"] or [None])[0],
            "sellers_total": p["sellers_total"],
            "sellers_match": len(sellers),
            "open_match": sum(1 for e in sellers if e["shop"]["open_now"] is True),
            "min_price": cheapest["best_price"] if cheapest else None,
            "median_price": p["median_price"],
            "cheapest_shop": cheapest["shop"]["name"] if cheapest else None,
            "nearest_m": nearest["distance_m"] if nearest else None,
            "installment_sellers": sum(1 for e in sellers if any(x["installments"] for x in e["shop"]["payment"])),
            "warranty_sellers": sum(1 for e in sellers if e["offers"][0]["warranty_kind"] == "yes"),
            "last_change": max(changes) if changes else None,
            "specs": {s["key"]: s["value"] for s in p["specs"] if s.get("key")},
        })
    # spec rows: keys present in at least 2 products (or all keys when there is one), first-seen order
    keys: list[str] = []
    for c in cols:
        for k in c["specs"]:
            if k not in keys:
                keys.append(k)
    need = 2 if len(cols) > 1 else 1
    rows = []
    for k in keys:
        values = [c["specs"].get(k) for c in cols]
        if sum(v is not None for v in values) >= need:
            rows.append({"key": k, "values": values, "same": len({v for v in values}) == 1})
        if len(rows) >= COMPARE_SPECS:
            break
    for c in cols:
        c.pop("specs")
    return {"products": cols, "spec_rows": rows, "filters_active": f.active}


def category_median(conn: sqlite3.Connection, category: str) -> float | None:
    rows = [r[0] for r in conn.execute(
        "SELECT median_price FROM products WHERE category = ? AND median_price IS NOT NULL", (category,))]
    if not rows:
        return None
    rows.sort()
    return float(rows[len(rows) // 2])


def place_center(conn: sqlite3.Connection, kind: str, name: str) -> tuple[float, float] | None:
    col = "area" if kind == "area" else "passage"
    r = conn.execute(f"SELECT AVG(lat), AVG(lon) FROM shops WHERE {col} = ? AND lat IS NOT NULL", (name,)).fetchone()
    return (round(r[0], 6), round(r[1], 6)) if r and r[0] is not None else None


def ask(conn: sqlite3.Connection, text: str, gazetteer, now: datetime | None = None, settings=None,
        use_llm: bool = False) -> dict:
    """A Persian sentence -> product words + a patch for the user's filter context + what was understood.

    Rules always run. With use_llm (and a configured LLM) the LLM fills gaps and names the product when the
    request was a free description (starcoach.llm.merge)."""
    from starcoach.intent import DEFAULT_MEDIAN, parse_request
    from starcoach.llm import DESCRIPTION_WORDS, refine_request

    now = now or now_tehran()
    parsed = parse_request(text, gazetteer, now=now)
    first = search_products(conn, parsed["query"], limit=1) if parsed["query"] else {"mode": "none"}
    struggled = len(parsed["query"].split()) > DESCRIPTION_WORDS or first["mode"] != "and"
    llm_ready = bool(settings and settings.llm_enabled)
    if use_llm and llm_ready:
        parsed = refine_request(text, parsed, settings, gazetteer, now=now)
    category = None
    if parsed["query"]:
        top = search_products(conn, parsed["query"], limit=5)["items"]
        if top:
            category = top[0]["category"]
    if parsed["ambiguous"] and category:
        # bare «تومن»: thousand or million? pick what fits this category's prices (research 03 §3.1)
        median = category_median(conn, category) or DEFAULT_MEDIAN
        parsed = parse_request(text, gazetteer, now=now, median=median)
    parsed = _drop_implausible_budget(conn, parsed, category)
    parsed.setdefault("source", "rules")
    return {"text": text, "category": category, **parsed, "ctx_patch": ctx_patch(conn, parsed),
            "rules_struggled": struggled, "llm_available": llm_ready}


IMPLAUSIBLE_BUDGET_SHARE = 1 / 20  # a "budget" this far below the category median is a spec, not a price


def _drop_implausible_budget(conn: sqlite3.Connection, parsed: dict, category: str | None) -> dict:
    """«پاوربانک ۱۰ هزار» means 10,000 mAh, not a 10,000-Toman budget: give the number back to the query."""
    f = parsed.get("filters", {})
    price = f.get("max_price") or f.get("min_price")
    median = category_median(conn, category) if category else None
    if not price or not median or price >= median * IMPLAUSIBLE_BUDGET_SHARE:
        return parsed
    budget = next((u for u in parsed.get("understood", []) if u["key"] == "budget"), None)
    number = str(price) if price % 1000 == 0 else None
    filters = {k: v for k, v in f.items() if k not in ("max_price", "min_price")}
    query = f"{parsed['query']} {number}".strip() if number and budget and "هزار" in budget["text"] else parsed["query"]
    return {**parsed, "filters": filters, "query": query, "ambiguous": {},
            "understood": [u for u in parsed.get("understood", []) if u["key"] != "budget"]}


def ctx_patch(conn: sqlite3.Connection, parsed: dict) -> dict:
    """Translate parsed filters into the web app's context fields (the same ones the chips edit)."""
    f = parsed["filters"]
    patch: dict = {}
    if "max_price" in f:
        patch["max_price"] = f["max_price"]
    if "min_price" in f:
        patch["min_price"] = f["min_price"]
    for kind in ("passage", "area"):
        if kind in f:
            center = place_center(conn, kind, f[kind])
            patch["place"] = {"kind": kind, "name": f[kind], "lat": center[0] if center else None,
                              "lon": center[1] if center else None}
    if "at" in f:
        when = datetime.fromisoformat(f["at"])
        patch["day"] = (when.weekday() + 2) % 7  # Iranian week, Saturday = 0
        patch["hour"] = when.hour
    for key in ("open", "installments", "torobpay", "in_person_pay", "fast", "warranty"):
        if f.get(key):
            patch[key] = True
    if parsed.get("cheap"):
        patch["sort"] = "price"
    return patch


def guide(conn: sqlite3.Connection, q: str, answers: dict[str, str], f: Filters | None = None,
          category: str | None = None) -> dict:
    """R1: help choose a model in the category the query points to."""
    from starcoach import guide as guide_mod

    if not category:
        top = search_products(conn, q, limit=20)["items"]
        category = focus_category(top) or (top[0]["category"] if top else None)
    if not category:
        return {"category": None, "questions": [], "suggestions": [], "matching": 0, "products": 0}
    return guide_mod.guide(conn, category, answers, f, seller_stats=_seller_stats)


def areas(conn: sqlite3.Connection, passages: int = 40) -> dict:
    """Neighbourhoods and the busiest passages, with shop counts and a center point (for "near" and maps)."""
    def rows(col: str, limit: int):
        return [
            {"name": r[0], "shops": r[1], "lat": round(r[2], 6), "lon": round(r[3], 6)}
            for r in conn.execute(
                f"""SELECT {col}, COUNT(*), AVG(lat), AVG(lon) FROM shops
                    WHERE {col} IS NOT NULL AND n_offers > 0 AND lat IS NOT NULL
                    GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT ?""",
                (limit,),
            )
        ]
    return {"areas": rows("area", 100), "passages": rows("passage", passages)}


def meta(conn: sqlite3.Connection) -> dict:
    return {k: v for k, v in conn.execute("SELECT key, value FROM meta") if k in ("snapshot", "built_at")}
