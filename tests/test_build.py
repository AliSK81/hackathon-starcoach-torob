import csv

from starcoach.build import clean_payment, clean_warranty, price_status, stats
from starcoach.db import connect

from .conftest import MINI


def _count(name):
    with open(MINI / f"{name}.csv", encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def test_counts_match_csv(mini_db):
    s = stats(mini_db)
    assert s["shops"] == _count("shops")
    assert s["products"] == _count("products")
    assert s["offers"] == _count("offers")
    assert s["shops_with_offers"] == s["shops"] - 2  # two category-only shops in the fixture


def test_price_edge_cases(mini_db):
    s = stats(mini_db)
    assert s["price_call"] >= 2  # one 1-Toman offer and one null price
    assert s["price_invalid"] >= 1
    conn = connect(mini_db, readonly=True)
    bad = conn.execute("SELECT COUNT(*) FROM offers WHERE price_status IN ('call','invalid') AND price IS NOT NULL")
    assert bad.fetchone()[0] == 0
    redacted = conn.execute("SELECT COUNT(*) FROM products WHERE title_redacted = 1").fetchone()[0]
    assert redacted >= 1


def test_product_aggregates(mini_db):
    conn = connect(mini_db, readonly=True)
    row = conn.execute(
        "SELECT n_shops, min_price, median_price FROM products WHERE title LIKE '%S25 FE 5G%' ORDER BY n_shops DESC"
    ).fetchone()
    assert row["n_shops"] >= 10
    assert row["min_price"] <= row["median_price"]


def test_price_status_rules():
    assert price_status(None) == "call"
    assert price_status(1) == "call"
    assert price_status(420) == "ok"
    assert price_status(2 * 10**13) == "invalid"


def test_warranty_and_payment_cleaning():
    assert clean_warranty('{"description":null,"period_months":null,"provider":"بدون گارانتی"}')[0] == "none"
    kind, months, text = clean_warranty('{"description":null,"period_months":18,"provider":"شرکتی"}')
    assert (kind, months) == ("yes", 18) and "شرکتی" in text
    assert clean_warranty("null") == (None, None, None)
    pay = clean_payment('[{"provider_name":"ترب‌پی","channel":"in_person"},{"provider_name":"ترب‌پی","channel":"in_person"}]')
    assert pay == [{"provider": "ترب‌پی", "channel": "in_person"}]
