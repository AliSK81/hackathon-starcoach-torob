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
    seller_reasons,
    shop_distance,
    shop_matches,
    without,
)
from starcoach.hours import is_open_at, now_tehran, status_text, week_table
from starcoach.search import search_products

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


def search(conn: sqlite3.Connection, q: str, limit: int = 20, f: Filters | None = None) -> dict:
    """Ranked products. With active filters, only products with at least one matching seller are kept."""
    f = f or Filters()
    result = search_products(conn, q, limit=400 if f.active else limit)
    candidates = result["items"]
    stats = _seller_stats(conn, [it["product_id"] for it in candidates], f)
    items = []
    for it in candidates:
        st = stats[it["product_id"]]
        if f.active and not st["match"]:
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
    return {"query": q, "words": result["words"], "mode": result["mode"], "total": result.get("total", 0),
            "filters_active": f.active, "items": items}


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
        "filters_active": f.active,
        "sellers_total": total,
        "sellers_hidden": total - len(sellers),
        "relax": relax,
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
