from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from starcoach import api
from starcoach.app import create_app
from starcoach.config import get_settings
from starcoach.db import connect
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
    p = api.product(conn, row["product_id"], at=datetime(2026, 10, 24, 11, tzinfo=TEHRAN))
    offer = next(o for s in p["sellers"] for o in s["offers"] if o["price_status"] == "call")
    assert offer["price"] is None and offer["price_note"]
