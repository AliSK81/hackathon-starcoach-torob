"""Cut a small, real sample of the Torob dataset for offline tests.

Run once from the repo root: `uv run python tests/fixtures/make_mini.py`.
It keeps every offer of a few demo products, a few edge-case offers, and the shops and
products those offers point to.
"""

import csv
import sys
from pathlib import Path

csv.field_size_limit(10**9)
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "torob-dataset"
OUT = Path(__file__).resolve().parent / "mini"

# Title substrings of demo products (research 01 §9).
DEMO_TITLES = [
    "S25 FE 5G | حافظه 256 رم 8",
    "شارژر اپل توان 20 وات سه پین",
    "هدفون بی سیم کیو سی وای مدل T13x",
    "Soundcore R50i",
    "سیستم اعلام سرقت سایلکس مدل SG8 LITE",
    "محافظ برق ۱۶ آمپر پارت الکتریک",
    "JBL PartyBox Stage 320",
]
MAX_PRODUCTS_PER_DEMO = 2
MAX_EXTRA_SHOP_OFFERS = 40


def read(name):
    with open(SRC / f"{name}.csv", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write(name, fields, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    pf, products = read("products")
    of, offers = read("offers")
    sf, shops = read("shops")

    offer_count = {}
    for o in offers:
        offer_count[o["product_id"]] = offer_count.get(o["product_id"], 0) + 1
    demo_ids = []
    for needle in DEMO_TITLES:
        hits = [p for p in products if needle in p["persian_title"]]
        hits.sort(key=lambda p: -offer_count.get(p["product_id"], 0))
        demo_ids += [p["product_id"] for p in hits[:MAX_PRODUCTS_PER_DEMO]]
    keep_offers = [o for o in offers if o["product_id"] in set(demo_ids)]

    # Edge cases: call-for-price, null price, garbage price, redacted title.
    redacted = {p["product_id"] for p in products if p["persian_title"] == "عنوان حذف‌شده برای انتشار"}
    edge_rules = [
        lambda o: o["price_toman"] == "1",
        lambda o: o["price_toman"] in ("", "null"),
        lambda o: o["price_toman"] not in ("", "null") and float(o["price_toman"]) > 1e12,
        lambda o: o["product_id"] in redacted,
    ]
    for rule in edge_rules:
        keep_offers.append(next(o for o in offers if rule(o)))

    # A few more offers from one busy demo shop, so shop pages have content.
    shop_ids = {o["shop_id"] for o in keep_offers}
    busy = max(shop_ids, key=lambda s: sum(1 for o in offers if o["shop_id"] == s))
    keep_offers += [o for o in offers if o["shop_id"] == busy and o not in keep_offers][:MAX_EXTRA_SHOP_OFFERS]

    product_ids = {o["product_id"] for o in keep_offers}
    shop_ids = {o["shop_id"] for o in keep_offers}
    # Plus two shops with no offers at all (category-only businesses).
    no_offer_shops = [s for s in shops if s["shop_id"] not in {o["shop_id"] for o in offers}][:2]

    write("products", pf, [p for p in products if p["product_id"] in product_ids])
    write("offers", of, keep_offers)
    write("shops", sf, [s for s in shops if s["shop_id"] in shop_ids] + no_offer_shops)
    print(f"products={len(product_ids)} offers={len(keep_offers)} shops={len(shop_ids) + len(no_offer_shops)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
