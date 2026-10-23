from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from starcoach import contact, visit
from starcoach.app import create_app
from starcoach.config import get_settings
from starcoach.db import connect
from starcoach.hours import TEHRAN

SAT_11 = datetime(2026, 10, 24, 11, tzinfo=TEHRAN)


@pytest.fixture()
def conn(mini_db):
    return connect(mini_db, readonly=True)


@pytest.fixture()
def client(mini_db, tmp_path):
    return TestClient(create_app(replace(get_settings(), db_path=mini_db, log_dir=tmp_path,
                                         llm_base_url="", llm_api_key="", llm_model="")))


def _busy_product(conn):
    return conn.execute("SELECT product_id FROM products ORDER BY n_shops DESC LIMIT 1").fetchone()[0]


def test_alternatives_exclude_origin_and_closed(conn):
    pid = _busy_product(conn)
    origin = conn.execute("SELECT shop_id FROM offers WHERE product_id = ? LIMIT 1", (pid,)).fetchone()[0]
    alt = visit.alternatives(conn, pid, origin, SAT_11)
    assert alt["sellers"] and all(s["shop_id"] != origin for s in alt["sellers"])
    assert all(s["open_now"] is not False for s in alt["sellers"])
    same = [s["same_passage"] for s in alt["sellers"]]
    assert same == sorted(same, reverse=True)  # same passage first


def test_contact_is_deterministic_and_marked_simulated(conn):
    offer = conn.execute("SELECT offer_id FROM offers WHERE price_status = 'ok' LIMIT 1").fetchone()[0]
    a = contact.contact(conn, offer, ["in_stock", "price_now", "hold"], SAT_11, now=SAT_11)
    b = contact.contact(conn, offer, ["in_stock", "price_now", "hold"], SAT_11, now=SAT_11)
    assert a["reply"] == b["reply"] and a["simulated"] is True and a["note"]
    assert "1)" in a["message"] and a["reply"]["status"] in ("answered", "no_answer")


def test_contact_api_dedupes_by_request_id(client, conn):
    offer = conn.execute("SELECT offer_id FROM offers LIMIT 1").fetchone()[0]
    body = {"offer_id": offer, "questions": ["in_stock"], "request_id": "r-1"}
    first = client.post("/api/contact", json=body).json()
    again = client.post("/api/contact", json=body).json()
    assert first == again
    assert client.post("/api/contact", json={"offer_id": "nope"}).status_code == 404


def test_plan_orders_stops_and_flags_closed(client, conn):
    shops = [r[0] for r in conn.execute("SELECT shop_id FROM shops WHERE n_offers > 0 AND lat IS NOT NULL LIMIT 4")]
    p = client.get("/api/plan", params={"shops": ",".join(shops), "at": "2026-10-30T12:00"}).json()  # a Friday
    assert len(p["stops"]) == 4 and p["total_walk_m"] >= 0
    assert [s["arrive"] for s in p["stops"]] == sorted(s["arrive"] for s in p["stops"])
    closed = {w["shop_id"] for w in p["warnings"] if w["kind"] == "closed"}
    assert closed == {s["shop_id"] for s in p["stops"] if s["open_on_arrival"] is False}


def test_where_lists_floor_neighbours(client, conn):
    sid = conn.execute("SELECT shop_id FROM shops WHERE passage IS NOT NULL AND floor IS NOT NULL LIMIT 1").fetchone()[0]
    w = client.get(f"/api/shops/{sid}/where").json()
    assert w["passage"] and w["floor_label"] and w["passage_shops"] >= 1


def test_passage_page_groups_shops_by_floor(client, conn):
    name = conn.execute("SELECT passage FROM shops WHERE passage IS NOT NULL GROUP BY passage ORDER BY COUNT(*) DESC").fetchone()[0]
    p = client.get(f"/api/passages/{name}").json()
    assert p["shops"] == sum(len(f["shops"]) for f in p["floors"])
    assert client.get("/api/passages/nope").status_code == 404


def test_category_shops_never_include_listed_sellers(conn):
    pid = conn.execute("SELECT product_id FROM products ORDER BY n_shops ASC LIMIT 1").fetchone()[0]
    listed = {r[0] for r in conn.execute("SELECT shop_id FROM offers WHERE product_id = ?", (pid,))}
    shops = visit.category_shops(conn, pid, None, SAT_11)
    assert all(s["shop_id"] not in listed and s["note"] for s in shops)


def test_seller_panel_round_trip_and_reuse(client, conn):
    offer, shop = conn.execute("SELECT offer_id, shop_id FROM offers WHERE price_status = 'ok' LIMIT 1").fetchone()
    body = {"offer_id": offer, "questions": ["in_stock", "price_now"], "mode": "seller", "request_id": "q1"}
    sent = client.post("/api/contact", json=body).json()
    assert sent["status"] == "waiting" and sent["reply"] is None
    assert client.post("/api/contact", json=body | {"questions": []}).json()["request"]["id"] == "q1"
    inbox = client.get(f"/api/seller/{shop}/inbox").json()
    assert [r["id"] for r in inbox["requests"]] == ["q1"]
    ans = client.post("/api/seller/reply", json={"request_id": "q1", "in_stock": True, "price_now": 123000,
                                                 "hold_until": "18:00"}).json()
    assert ans["reply"]["facts"] == {"in_stock": True, "price_now": 123000, "price_changed": True, "hold_until": "18:00"}
    assert client.get("/api/contact/q1").json()["status"] == "answered"
    again = client.post("/api/contact", json={"offer_id": offer, "mode": "seller", "request_id": "q2"}).json()
    assert again["status"] == "reused" and again["request"]["id"] == "q1"  # the seller isn't asked twice


def test_inbox_survives_restart(tmp_path):
    from starcoach.inbox import Inbox

    a = Inbox(tmp_path / "inbox.jsonl")
    a.create("r1", "o1", "s1", "p1", "t", 1000, ["in_stock"], "msg", None)
    a.answer("r1", False, None, None, None)
    a.answer("r1", True, 5, None, None)  # a second tap is ignored
    b = Inbox(tmp_path / "inbox.jsonl")
    assert b.requests["r1"]["status"] == "answered" and b.requests["r1"]["answer"]["in_stock"] is False
