"""Walk every StarCoach hash route and primary control at phone width (and one desktop check)."""

from __future__ import annotations

import re
from urllib.parse import quote

import pytest

pytest.importorskip("playwright")

PERSIAN_DIGIT = re.compile(r"[۰-۹]")


def test_rtl_and_home(ui):
    page = ui["goto"]("#/")
    assert page.locator("html").get_attribute("dir") == "rtl"
    assert page.locator("html").get_attribute("lang") == "fa"
    page.wait_for_selector("#view h1")
    assert "تهران" in page.locator("#view").inner_text()
    page.locator("[data-ask]").first.click()
    page.wait_for_url(re.compile(r"#/search"))
    page.wait_for_selector(".product-card, .empty-state")
    ui["assert_clean"]()


def test_search_results_and_persian_price(ui):
    cat = ui["catalog"]
    page = ui["goto"](f"#/search?q={quote(cat['q'])}")
    page.wait_for_selector(".product-card")
    text = page.locator("#view").inner_text()
    assert PERSIAN_DIGIT.search(text), "expected Persian digits in search results"
    assert "تومان" in text
    ui["assert_clean"]()


def test_search_empty_query_returns_home(ui):
    page = ui["goto"]("#/search?q=")
    page.wait_for_selector("#view h1")
    assert "دستیار خرید حضوری" in page.locator("#view").inner_text()
    ui["assert_clean"]()


def test_search_no_hits(ui):
    page = ui["goto"]("#/search?q=" + quote("xyzzyqqqnotaproduct999"))
    page.wait_for_selector(".empty-state")
    assert "پیدا نشد" in page.locator(".empty-state").inner_text()
    ui["assert_clean"]()


def test_bad_ids_show_error_card(ui):
    page = ui["goto"]("#/p/nope")
    page.wait_for_selector(".empty-state")
    assert "مشکلی پیش آمد" in page.locator(".empty-state").inner_text()
    page = ui["goto"]("#/s/nope")
    page.wait_for_selector(".empty-state")
    assert "مشکلی پیش آمد" in page.locator(".empty-state").inner_text()
    ui["assert_clean"]()


def test_product_and_shop_pages(ui):
    cat = ui["catalog"]
    page = ui["goto"](f"#/p/{quote(cat['product_id'], safe='')}")
    page.wait_for_selector("article.card, .pick")
    assert "فروشنده‌ها" in page.locator("#view").inner_text() or page.locator("article.card").count() > 0
    page = ui["goto"](f"#/s/{quote(cat['shop_id'], safe='')}")
    page.wait_for_selector(".facts")
    assert page.locator("table.hours, .facts").count() > 0
    ui["assert_clean"]()


def test_compare_tray_and_limit(ui):
    cat = ui["catalog"]
    page = ui["goto"](f"#/search?q={quote(cat['q'])}")
    page.wait_for_selector("[data-compare]")
    cards = page.locator("[data-compare]")
    n = min(3, cards.count())
    assert n >= 1
    for i in range(n):
        before = page.url
        cards.nth(i).click()
        page.wait_for_timeout(100)
        # compare must not navigate away from search
        assert "#/search" in page.url or before == page.url or "#/p/" not in page.url
    page.wait_for_selector("#tray:not([hidden])")
    page.locator("#tray a[href='#/compare']").click()
    page.wait_for_url(re.compile(r"#/compare"))
    page.wait_for_selector(".cmp-table, .empty-state")
    ui["assert_clean"]()


def test_filter_sheet_apply_updates_ctx(ui):
    page = ui["goto"]("#/")
    page.locator("[data-open-sheet]").first.click()
    page.wait_for_selector("#sheet[open]")
    ui["assert_no_overflow"]()
    # pick a budget radio if present
    budget = page.locator('#sheet input[name="budget"]:not([value=""])').first
    if budget.count():
        budget.check(force=True)
    page.locator("#sheetApply").click()
    page.wait_for_function("() => !document.getElementById('sheet').open")
    chips = page.locator("#ctxbar").inner_text()
    assert "میلیون" in chips or "هزار" in chips or "بودجه" in chips or "تومان" in chips
    ui["assert_clean"]()


def test_guide_page(ui):
    page = ui["goto"]("#/guide?q=" + quote("هندزفری"))
    page.wait_for_selector("#view")
    page.wait_for_timeout(500)
    text = page.locator("#view").inner_text()
    assert "راهنما" in text or "دسته‌ای پیدا نشد" in text or "سؤال" in text
    ui["assert_clean"]()


def test_plan_add_and_remove(ui):
    cat = ui["catalog"]
    page = ui["goto"](f"#/p/{quote(cat['product_id'], safe='')}")
    page.wait_for_selector("[data-plan-add]")
    page.locator("[data-plan-add]").first.click()
    page.wait_for_timeout(200)
    page = ui["goto"]("#/plan")
    page.wait_for_selector("#view")
    assert "خالی است" not in page.locator("#view").inner_text() or page.locator("[data-plan-remove]").count() > 0
    if page.locator("[data-plan-remove]").count():
        page.locator("[data-plan-remove]").first.click()
        page.wait_for_timeout(200)
        page.wait_for_selector(".empty-state, [data-plan-remove]")
    ui["assert_clean"]()


def test_passage_page(ui):
    cat = ui["catalog"]
    page = ui["goto"](f"#/passage/{quote(cat['passage'])}")
    page.wait_for_selector("#view")
    page.wait_for_timeout(400)
    text = page.locator("#view").inner_text()
    assert cat["passage"] in text or "پاساژ" in text or "فروشگاه" in text or "پیدا" in text
    ui["assert_clean"]()


def test_seller_inbox_and_contact_sheet(ui):
    cat = ui["catalog"]
    page = ui["goto"](f"#/seller/{quote(cat['shop_id'], safe='')}")
    page.wait_for_selector("#view h1")
    assert "فروشنده" in page.locator("#view").inner_text()
    # open contact from product
    page = ui["goto"](f"#/p/{quote(cat['product_id'], safe='')}")
    page.wait_for_selector("[data-contact]")
    page.locator("[data-contact]").first.click()
    page.wait_for_selector("#sheet[open]")
    ui["assert_no_overflow"]()
    page.locator("#contactClose").click()
    page.wait_for_function("() => !document.getElementById('sheet').open")
    ui["assert_clean"]()


def test_agent_panel_open_send_close(ui):
    page = ui["goto"]("#/")
    # ai-ready is set when /health reports ai:true (always); wait for fab or open button
    page.wait_for_function("() => document.body.classList.contains('ai-ready')")
    opener = page.locator("[data-agent-open], #aiFab").first
    opener.click()
    page.wait_for_selector("#aiPanel:not([hidden])")
    page.fill("#aiInput", "سلام تست")
    page.locator("#aiForm button[type=submit]").click()
    # without LLM the agent still responds (degraded) or shows an error bubble — must not throw
    page.wait_for_timeout(3000)
    page.locator("#aiClose").click()
    page.wait_for_function("() => document.getElementById('aiPanel').hidden === true")
    ui["assert_clean"]()


def test_desktop_viewport_no_overflow(ui):
    page = ui["page"]
    page.set_viewport_size({"width": 1280, "height": 800})
    cat = ui["catalog"]
    for path in (
        "#/",
        f"#/search?q={quote(cat['q'])}",
        f"#/p/{quote(cat['product_id'], safe='')}",
        f"#/s/{quote(cat['shop_id'], safe='')}",
        f"#/passage/{quote(cat['passage'])}",
        "#/plan",
        "#/compare",
    ):
        ui["goto"](path)
        page.wait_for_timeout(300)
        ui["assert_no_overflow"]()
    ui["assert_clean"]()
