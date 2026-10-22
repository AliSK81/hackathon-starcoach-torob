"""Build the SQLite DB from the Torob CSVs.

Each row is cleaned once here. A bad row is logged and skipped; it never stops the build.
The DB is written to a temp file and renamed at the end, so a failed build leaves the old DB intact.
"""

import csv
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

from starcoach.db import SCHEMA, connect
from starcoach.logs import log_event
from starcoach.textnorm import to_ascii_digits

csv.field_size_limit(10**9)

REDACTED_TITLE = "عنوان حذف‌شده برای انتشار"
NO_WARRANTY = "بدون گارانتی"
PRICE_CALL_MAX = 10  # F15: 1 Toman means "call for price"
PRICE_INVALID_MIN = 10**10  # F15: above this is digit garbage
SUSPICIOUS_FACTOR = 3  # F15: outside median/3 .. 3*median, when >= 3 sellers
SUSPICIOUS_MIN_SHOPS = 3


def _json(value: str | None):
    if value is None or value in ("", "null"):
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def _null(value: str | None) -> str | None:
    return None if value in (None, "", "null") else value


def price_status(raw: int | None) -> str:
    if raw is None or raw <= PRICE_CALL_MAX:
        return "call"
    if raw > PRICE_INVALID_MIN:
        return "invalid"
    return "ok"


def clean_warranty(value: str | None) -> tuple[str | None, int | None, str | None]:
    """Return (kind, months, text). kind is 'yes', 'none' (explicitly no warranty) or None (unknown)."""
    w = _json(value)
    if not isinstance(w, dict):
        return None, None, None
    provider = (w.get("provider") or "").strip()
    months = w.get("period_months")
    desc = (w.get("description") or "").strip()
    if provider == NO_WARRANTY:
        return "none", None, NO_WARRANTY
    parts = [p for p in (provider, f"{months} ماهه" if months else "", desc) if p]
    if not parts:
        return None, None, None
    return "yes", int(months) if months else None, " · ".join(parts)


def clean_payment(value: str | None) -> list[dict]:
    out = []
    for p in _json(value) or []:
        if isinstance(p, dict) and p.get("provider_name"):
            item = {"provider": p["provider_name"].strip(), "channel": p.get("channel") or "unknown"}
            if item not in out:
                out.append(item)
    return out


def _rows(path: Path):
    with open(path, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def build(data_dir: Path, db_path: Path, log_dir: Path) -> dict:
    started = time.time()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".building")
    if tmp.exists():
        tmp.unlink()
    conn = connect(tmp)
    conn.executescript(SCHEMA)
    counts: dict[str, int] = defaultdict(int)

    def bad(table: str, row_no: int, err: Exception) -> None:
        counts[f"{table}_skipped"] += 1
        log_event(log_dir, "build", "bad_row", table=table, row=row_no, error=repr(err))

    # shops
    shops = []
    for i, r in enumerate(_rows(data_dir / "shops.csv")):
        try:
            contacts = _json(r["contacts"]) or []
            phone = next((c.get("display_number") for c in contacts if c.get("channel") == "phone"), None)
            insta = _json(r["instagram"])
            website = _null(r["website_url"])
            fast = _null(r["supports_fast_delivery"])
            hours = _json(r["weekly_hours"])
            shops.append((
                r["shop_id"], _null(r["name"]), 1 if (insta or website) else 0, _null(r["address"]),
                _null(r["location_label"]), float(r["lat"]) if _null(r["lat"]) else None,
                float(r["lon"]) if _null(r["lon"]) else None,
                json.dumps(_json(r["category_names"]) or [], ensure_ascii=False),
                to_ascii_digits(phone) if phone else None,
                insta.get("profile_url") if isinstance(insta, dict) else None, website,
                json.dumps(hours, ensure_ascii=False) if hours else None,
                None if fast is None else int(fast == "true"),
                json.dumps(clean_payment(r["payment_options"]), ensure_ascii=False),
            ))
        except Exception as e:  # noqa: BLE001 - one bad row must not stop the build
            bad("shops", i, e)
    conn.executemany("INSERT INTO shops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)", shops)
    counts["shops"] = len(shops)

    # products
    products = []
    for i, r in enumerate(_rows(data_dir / "products.csv")):
        try:
            title = (r["persian_title"] or "").strip()
            products.append((
                r["product_id"], title, 1 if (title == REDACTED_TITLE or not title) else 0,
                _null(r["brand_name"]), _null(r["category_name"]), _null(r["model"]),
                json.dumps(_json(r["image_urls"]) or [], ensure_ascii=False),
                json.dumps(_json(r["specs"]) or [], ensure_ascii=False),
            ))
        except Exception as e:  # noqa: BLE001
            bad("products", i, e)
    conn.executemany(
        "INSERT INTO products (product_id,title,title_redacted,brand,category,model,images,specs) VALUES (?,?,?,?,?,?,?,?)",
        products,
    )
    counts["products"] = len(products)
    del products

    # offers
    offers = []
    for i, r in enumerate(_rows(data_dir / "offers.csv")):
        try:
            raw = _null(r["price_toman"])
            raw_int = int(float(raw)) if raw is not None else None
            status = price_status(raw_int)
            kind, months, wtext = clean_warranty(r["warranty"])
            offers.append([
                r["offer_id"], r["product_id"], r["shop_id"], _null(r["seller_title"]), _null(r["description"]),
                raw_int, raw_int if status == "ok" else None, status, _null(r["last_price_changed_at"]),
                kind, months, wtext,
            ])
        except Exception as e:  # noqa: BLE001
            bad("offers", i, e)

    # suspicious prices: far from the product's median when enough shops price it
    by_product: dict[str, dict[str, int]] = defaultdict(dict)
    for o in offers:
        if o[7] == "ok":
            shop_min = by_product[o[1]].get(o[2])
            by_product[o[1]][o[2]] = o[6] if shop_min is None else min(shop_min, o[6])
    medians = {
        pid: statistics.median(per_shop.values())
        for pid, per_shop in by_product.items()
        if len(per_shop) >= SUSPICIOUS_MIN_SHOPS
    }
    for o in offers:
        med = medians.get(o[1])
        if o[7] == "ok" and med and not (med / SUSPICIOUS_FACTOR <= o[6] <= med * SUSPICIOUS_FACTOR):
            o[7] = "suspicious"
    conn.executemany("INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", offers)
    counts["offers"] = len(offers)
    for o in offers:
        counts[f"price_{o[7]}"] += 1
    del offers

    # aggregates
    conn.executescript("""
        UPDATE shops SET n_offers = (SELECT COUNT(*) FROM offers o WHERE o.shop_id = shops.shop_id);
        UPDATE products SET n_shops = (SELECT COUNT(DISTINCT shop_id) FROM offers o WHERE o.product_id = products.product_id);
        UPDATE products SET min_price = (SELECT MIN(price) FROM offers o
            WHERE o.product_id = products.product_id AND o.price_status = 'ok');
    """)
    prices: dict[str, list[int]] = defaultdict(list)
    for pid, price in conn.execute("SELECT product_id, price FROM offers WHERE price_status = 'ok'"):
        prices[pid].append(price)
    conn.executemany(
        "UPDATE products SET median_price = ? WHERE product_id = ?",
        [(int(statistics.median(v)), pid) for pid, v in prices.items()],
    )
    snapshot = conn.execute("SELECT MAX(price_changed_at) FROM offers").fetchone()[0]
    conn.executemany("INSERT INTO meta VALUES (?,?)", [
        ("snapshot", snapshot),
        ("built_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        ("counts", json.dumps(counts)),
    ])
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    os.replace(tmp, db_path)

    counts_out = dict(counts)
    counts_out["seconds"] = round(time.time() - started, 1)
    counts_out["db_mb"] = round(db_path.stat().st_size / 2**20, 1)
    log_event(log_dir, "build", "build_done", **counts_out)
    return counts_out


def stats(db_path: Path) -> dict:
    conn = connect(db_path, readonly=True)
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    out = {
        "shops": q("SELECT COUNT(*) FROM shops"),
        "shops_with_offers": q("SELECT COUNT(*) FROM shops WHERE n_offers > 0"),
        "shops_real_name": q("SELECT COUNT(*) FROM shops WHERE name_is_real = 1"),
        "products": q("SELECT COUNT(*) FROM products"),
        "products_multi_shop": q("SELECT COUNT(*) FROM products WHERE n_shops >= 2"),
        "products_redacted": q("SELECT COUNT(*) FROM products WHERE title_redacted = 1"),
        "offers": q("SELECT COUNT(*) FROM offers"),
        "snapshot": q("SELECT value FROM meta WHERE key = 'snapshot'"),
    }
    for status, n in conn.execute("SELECT price_status, COUNT(*) FROM offers GROUP BY 1"):
        out[f"price_{status}"] = n
    conn.close()
    return out
