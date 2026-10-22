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
