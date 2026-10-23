from starcoach.db import connect
from starcoach.search import alias_tokens, collapse_aliases, query_words, search_products


def test_aliases_both_ways():
    assert "iphone" in alias_tokens(["ایفون"])
    assert "ایفون" in alias_tokens(["iphone"])
    assert collapse_aliases(["اسپیکر", "جی", "بی", "ال"]) == ["اسپیکر", "jbl"]


def test_query_words_drop_stopwords():
    assert query_words("هدفون ارزان برای من") == ["هدفون", "من"]


def test_search_finds_demo_products(mini_db):
    conn = connect(mini_db, readonly=True)
    top = search_products(conn, "شارژر اپل ۲۰ وات")["items"][0]
    assert "شارژر اپل توان 20 وات" in top["title"]
    top = search_products(conn, "گوشی سامسونگ s25 fe")["items"][0]
    assert top["category"] == "گوشی موبایل"


def test_latin_query_matches_persian_title(mini_db):
    conn = connect(mini_db, readonly=True)
    items = search_products(conn, "qcy t13x")["items"]
    assert any("کیو سی وای" in i["title"] for i in items)


def test_no_match_and_empty(mini_db):
    conn = connect(mini_db, readonly=True)
    assert search_products(conn, "")["mode"] == "none"
    assert search_products(conn, "زززز")["items"] == []


def test_typo_is_corrected_only_when_nothing_matches(mini_db):
    conn = connect(mini_db, readonly=True)
    r = search_products(conn, "گوشی سامسنگ")
    assert r["corrected"] == {"سامسنگ": "سامسونگ"} and r["items"]
    assert search_products(conn, "شارژر اپل")["corrected"] == {}


def test_variant_parsing_from_seller_titles():
    from starcoach.variants import parse_variant, summarize

    assert parse_variant("ونس دیور - مشکی کف سفید / 44") == {"color": "مشکی کف سفید", "size": "44"}
    assert parse_variant("ست کت و شلوار - عسلی / سایز ۳ مناسب ۴۴ و ۴۶") == {"color": "عسلی", "size": "3 مناسب 44 و 46"}
    assert parse_variant("شارژر اپل 20 وات") == {"color": None, "size": None}
    offers = [{"shop_id": "a", "color": "مشکی", "size": "42"}, {"shop_id": "b", "color": "سفید", "size": "41"}]
    s = summarize(offers)
    assert [x["value"] for x in s["sizes"]] == ["41", "42"] and len(s["colors"]) == 2
