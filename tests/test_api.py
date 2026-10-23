from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from starcoach import api
from starcoach.app import create_app
from starcoach.config import get_settings
from starcoach.db import connect
from starcoach.filters import INSTALLMENT_PROVIDERS, Filters
from starcoach.hours import TEHRAN


@pytest.fixture()
def client(mini_db):
    return TestClient(create_app(replace(get_settings(), db_path=mini_db)))


def test_search_then_product_then_shop(client):
    r = client.get("/api/search", params={"q": "شارژر اپل ۲۰ وات"})
    assert r.status_code == 200
    first = r.json()["items"][0]
    assert first["n_shops"] > 1

    p = client.get(f"/api/products/{first['product_id']}").json()
    assert len(p["sellers"]) == first["n_shops"]
    prices = [s["best_price"] for s in p["sellers"] if s["best_status"] == "ok"]
    assert prices == sorted(prices)  # cheapest normal price first
    ranks = [s["best_status"] for s in p["sellers"]]
    assert ranks == sorted(ranks, key=api.OFFER_RANK.get)  # suspicious and unknown prices after
    seller = p["sellers"][0]
    assert {"open_now", "hours_status", "location_short"} <= seller["shop"].keys()

    s = client.get(f"/api/shops/{seller['shop']['shop_id']}").json()
    assert s["address"]
    assert any(x["product_id"] == first["product_id"] for x in s["products"])


def test_not_found_and_missing_db(client, tmp_path):
    assert client.get("/api/products/nope").status_code == 404
    assert client.get("/api/shops/nope").status_code == 404
    missing = TestClient(create_app(replace(get_settings(), db_path=tmp_path / "none.db")))
    assert missing.get("/api/search", params={"q": "x"}).status_code == 503
    assert missing.get("/ready").status_code == 503
    assert missing.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_price_labels_are_separate(mini_db):
    conn = connect(mini_db, readonly=True)
    row = conn.execute("SELECT product_id FROM offers WHERE price_status = 'call' LIMIT 1").fetchone()
    p = api.product(conn, row["product_id"], Filters(at=datetime(2026, 10, 24, 11, tzinfo=TEHRAN)))
    offer = next(o for s in p["sellers"] for o in s["offers"] if o["price_status"] == "call")
    assert offer["price"] is None and offer["price_note"]


def _charger(client):
    return client.get("/api/search", params={"q": "شارژر اپل ۲۰ وات"}).json()["items"][0]["product_id"]


def test_installments_only_filter(client):
    pid = _charger(client)
    all_ = client.get(f"/api/products/{pid}").json()
    only = client.get(f"/api/products/{pid}", params={"installments": "1"}).json()
    assert 0 < len(only["sellers"]) < len(all_["sellers"])
    assert only["sellers_hidden"] == only["sellers_total"] - len(only["sellers"])
    for e in only["sellers"]:
        assert {p["provider"] for p in e["shop"]["payment"]} & INSTALLMENT_PROVIDERS
        assert any(r["text"].startswith("خرید اقساطی") for r in e["reasons"])


def test_distance_sort_and_radius(client):
    pid = _charger(client)
    near_alaeddin = {"lat": "35.6950", "lon": "51.4113", "sort": "distance"}
    p = client.get(f"/api/products/{pid}", params=near_alaeddin).json()
    dists = [e["distance_m"] for e in p["sellers"] if e["distance_m"] is not None]
    assert dists == sorted(dists) and dists
    close = client.get(f"/api/products/{pid}", params=near_alaeddin | {"radius_m": "300"}).json()
    assert all(e["distance_m"] <= 300 for e in close["sellers"])
    assert len(close["sellers"]) < len(p["sellers"])


def test_budget_excludes_unknown_prices(client):
    pid = _charger(client)
    p = client.get(f"/api/products/{pid}", params={"max_price": "100000000"}).json()
    assert p["sellers"] and all(e["best_status"] == "ok" for e in p["sellers"])
    assert p["sellers"][0]["reasons"][0]["text"] == "ارزان‌ترین قیمت ثبت‌شده"


def test_zero_results_suggest_which_filter_to_relax(client):
    pid = _charger(client)
    p = client.get(f"/api/products/{pid}", params={"max_price": "1000", "installments": "1"}).json()
    assert p["sellers"] == []
    assert p["relax"] and p["relax"][0]["filter"] == "max_price" and p["relax"][0]["sellers"] > 0


def test_cheapest_reason_respects_filters(client):
    pid = _charger(client)
    p = client.get(f"/api/products/{pid}", params={"installments": "1"}).json()
    texts = [r["text"] for r in p["sellers"][0]["reasons"]]
    overall = client.get(f"/api/products/{pid}").json()["min_price"]
    if p["sellers"][0]["best_price"] == overall:
        assert "ارزان‌ترین قیمت ثبت‌شده" in texts
    else:
        assert "ارزان‌ترین با شرایط شما" in texts


def test_search_filters_keep_only_products_with_matching_sellers(client):
    plain = client.get("/api/search", params={"q": "شارژر"}).json()["items"]
    inst = client.get("/api/search", params={"q": "شارژر", "installments": "1"}).json()["items"]
    assert inst and len(inst) <= len(plain)
    assert all(0 < i["match_shops"] <= i["n_shops"] for i in inst)
    cheap = client.get("/api/search", params={"q": "شارژر", "max_price": "2000000"}).json()["items"]
    assert all(i["match_min_price"] <= 2000000 for i in cheap)


def test_areas_have_counts_and_centers(client):
    a = client.get("/api/areas").json()
    assert a["areas"] and a["passages"]
    top = a["areas"][0]
    assert top["shops"] >= a["areas"][-1]["shops"] and 35 < top["lat"] < 36 and 51 < top["lon"] < 52


def test_compare_aligns_specs_and_prices(client):
    items = client.get("/api/search", params={"q": "شارژر اپل"}).json()["items"][:3]
    ids = ",".join(i["product_id"] for i in items)
    c = client.get("/api/compare", params={"ids": ids}).json()
    assert len(c["products"]) == len(items)
    assert all(len(r["values"]) == len(items) for r in c["spec_rows"])
    assert c["products"][0]["sellers_match"] == c["products"][0]["sellers_total"]
    f = client.get("/api/compare", params={"ids": ids, "installments": "1"}).json()
    assert all(p["sellers_match"] <= p["sellers_total"] for p in f["products"])


def test_ask_turns_a_sentence_into_a_filter_patch(client):
    r = client.get("/api/ask", params={"text": "شارژر اپل ۲۰ وات زیر ۵ میلیون قسطی فردا عصر"}).json()
    assert r["query"] == "شارژر اپل 20 وات"
    assert r["ctx_patch"]["max_price"] == 5_000_000 and r["ctx_patch"]["installments"] is True
    assert r["ctx_patch"]["hour"] == 17 and 0 <= r["ctx_patch"]["day"] <= 6
    assert {u["key"] for u in r["understood"]} >= {"budget", "installments", "at"}


def test_ask_resolves_bare_toman_by_category(client):
    phone = client.get("/api/ask", params={"text": "گوشی سامسونگ تا ۲۰۰ تومن"}).json()
    charger = client.get("/api/ask", params={"text": "شارژر اپل تا ۸۰۰ تومن"}).json()
    assert phone["filters"]["max_price"] == 200_000_000  # phones: million
    assert charger["filters"]["max_price"] == 800_000  # chargers: thousand
    assert phone["ambiguous"] and charger["ambiguous"]


def test_filtered_search_stays_in_the_category_the_query_means(client):
    r = client.get("/api/search", params={"q": "شارژر اپل", "installments": "1"}).json()
    if r["focus_category"]:
        assert all(i["category"] == r["focus_category"] for i in r["items"])
    every = client.get("/api/search", params={"q": "شارژر اپل", "installments": "1", "all_cats": "1"}).json()
    assert every["focus_category"] is None and len(every["items"]) >= len(r["items"])


def test_search_suggests_relaxing_when_results_are_few(client):
    r = client.get("/api/search", params={"q": "شارژر اپل", "max_price": "1000"}).json()
    assert r["items"] == [] and r["relax"] and r["relax"][0]["filter"] == "max_price"
