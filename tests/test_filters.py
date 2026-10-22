from datetime import datetime

from starcoach.filters import distance_m, offer_matches, parse_filters, shop_matches
from starcoach.hours import TEHRAN

SHOP = {"area": "شیخ هادی", "passage": "علاءالدین", "lat": 35.6950, "lon": 51.4113, "fast_delivery": None}
PAY = [{"provider": "ترب‌پی", "channel": "in_person"}]


def test_parse_ignores_bad_values():
    f = parse_filters({"max_price": "abc", "open": "1", "sort": "weird", "at": "2026-10-24T11:00"})
    assert f.max_price is None and f.open_only and f.sort == "price"
    assert f.at == datetime(2026, 10, 24, 11, tzinfo=TEHRAN)


def test_shop_and_offer_matching():
    f = parse_filters({"area": "شیخ هادی", "torobpay": "1", "in_person_pay": "1"})
    assert shop_matches(f, SHOP, PAY, None)
    assert not shop_matches(parse_filters({"fast": "1"}), SHOP, PAY, None)  # unknown never matches
    assert not shop_matches(parse_filters({"open": "1"}), SHOP, PAY, None)  # no hours -> not "open"
    budget = parse_filters({"max_price": "1000000"})
    assert offer_matches(budget, {"price_status": "ok", "price": 900000, "warranty_kind": None})
    assert not offer_matches(budget, {"price_status": "call", "price": None, "warranty_kind": None})


def test_distance_alaeddin_charsou():
    assert 50 < distance_m(35.6950, 51.4113, 35.6948, 51.4123) < 150
