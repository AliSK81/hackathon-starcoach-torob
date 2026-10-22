"""Read model for the web app: plain dicts built only from DB values.

Labels that explain what a value means (for transparency) are built here, so every client shows
the same wording.
"""

import json
import sqlite3
from datetime import datetime

from starcoach.address import floor_label
from starcoach.hours import is_open_at, now_tehran, status_text, week_table
from starcoach.search import search_products

INSTALLMENT_PROVIDERS = {"ترب‌پی", "اسنپ‌پی", "دیجی پی", "تارا", "ازکی‌وام"}  # BNPL / credit (F22)
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


def search(conn: sqlite3.Connection, q: str, limit: int = 20) -> dict:
    result = search_products(conn, q, limit=limit)
    items = []
    for it in result["items"]:
        items.append({
            "product_id": it["product_id"],
            "title": it["title"],
            "brand": it["brand"],
            "category": it["category"],
            "image": it["images"][0] if it["images"] else None,
            "n_shops": it["n_shops"],
            "min_price": it["min_price"],
            "median_price": it["median_price"],
        })
    return {"query": q, "words": result["words"], "mode": result["mode"], "total": result.get("total", 0),
            "items": items}


def product(conn: sqlite3.Connection, product_id: str, at: datetime | None = None) -> dict | None:
    at = at or now_tehran()
    p = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if p is None:
        return None
    rows = conn.execute(
        "SELECT o.*, s.* FROM offers o JOIN shops s ON s.shop_id = o.shop_id WHERE o.product_id = ?",
        (product_id,),
    ).fetchall()
    by_shop: dict[str, dict] = {}
    for r in rows:
        entry = by_shop.get(r["shop_id"])
        if entry is None:
            entry = by_shop[r["shop_id"]] = {
                "shop": shop_summary(r, at) | {"payment": payment_info(r["payment"]),
                                                "fast_delivery": r["fast_delivery"]},
                "offers": [],
            }
        entry["offers"].append(offer_view(r))
    sellers = []
    for entry in by_shop.values():
        # normal prices first, then far-off ("suspicious") ones, then no price
        entry["offers"].sort(key=lambda o: (OFFER_RANK[o["price_status"]], o["price"] or 0))
        best = entry["offers"][0]
        entry["best_price"] = best["price"]
        entry["best_status"] = best["price_status"]
        entry["last_change"] = max((o["price_changed_at"] or "" for o in entry["offers"]), default=None) or None
        sellers.append(entry)
    sellers.sort(key=lambda e: (OFFER_RANK[e["best_status"]], e["best_price"] or 0))
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


def meta(conn: sqlite3.Connection) -> dict:
    return {k: v for k, v in conn.execute("SELECT key, value FROM meta") if k in ("snapshot", "built_at")}
