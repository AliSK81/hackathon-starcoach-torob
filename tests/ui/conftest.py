"""Serve the mini DB for Playwright UI tests (offline, no LLM)."""

from __future__ import annotations

import socket
import threading
from dataclasses import replace
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from starcoach.app import create_app
from starcoach.build import build
from starcoach.config import get_settings

MINI = Path(__file__).resolve().parents[1] / "fixtures" / "mini"
SEARCH_Q = "شارژر اپل ۲۰ وات"


@pytest.fixture(scope="session")
def mini_db(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("ui-db")
    db = out / "mini.db"
    build(MINI, db, out / "logs")
    return db


@pytest.fixture(scope="session")
def app_settings(mini_db):
    return replace(get_settings(), db_path=mini_db, llm_base_url="", llm_api_key="", llm_model="")


@pytest.fixture(scope="session")
def catalog(app_settings) -> dict:
    """Resolve real product / shop / passage ids from the mini API."""
    client = TestClient(create_app(app_settings))
    search = client.get("/api/search", params={"q": SEARCH_Q}).json()
    assert search["items"], "mini DB has no search hits for the smoke query"
    product = client.get(f"/api/products/{search['items'][0]['product_id']}").json()
    assert product["sellers"], "product has no sellers"
    shop = product["sellers"][0]["shop"]
    areas = client.get("/api/areas").json()
    passage = None
    for p in areas.get("passages") or []:
        if p.get("name"):
            passage = p["name"]
            break
    if not passage and shop.get("passage"):
        passage = shop["passage"]
    assert passage, "mini DB has no passage to open"
    offer_id = product["sellers"][0]["offers"][0]["offer_id"]
    return {
        "q": SEARCH_Q,
        "product_id": product["product_id"],
        "shop_id": shop["shop_id"],
        "shop_name": shop.get("name") or "",
        "passage": passage,
        "offer_id": offer_id,
        "area": (areas.get("areas") or [{}])[0].get("name"),
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(app_settings) -> str:
    port = _free_port()
    config = uvicorn.Config(
        create_app(app_settings),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # wait until accepting
    import time
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urllib.request.urlopen(url + "/health", timeout=0.5) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.1)
    else:
        raise RuntimeError("UI test server did not become ready")
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser_context_args():
    # default phone-width; individual tests may override via page.set_viewport_size
    return {"locale": "fa-IR", "viewport": {"width": 375, "height": 812}}


@pytest.fixture(scope="session")
def browser_type_launch_args():
    # Chromium download from Google is often blocked in Iran; use installed Chrome.
    return {"channel": "chrome"}


@pytest.fixture
def ui(page, base_url, catalog):
    """Page helper: navigate, track console/page errors, assert no horizontal overflow."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

    def on_console(msg):
        if msg.type != "error":
            return
        text = msg.text or ""
        # Product image URLs from the dataset often 404 offline; those are not UI bugs.
        if "Failed to load resource" in text and "404" in text:
            return
        errors.append(f"console.error: {text}")

    page.on("console", on_console)

    def goto(hash_path: str = "#/"):
        page.goto(f"{base_url}/{hash_path}", wait_until="networkidle")
        page.wait_for_selector("#view")
        return page

    def assert_no_overflow():
        overflow = page.evaluate(
            """() => {
              const el = document.documentElement;
              return { scroll: el.scrollWidth, client: el.clientWidth, body: document.body.scrollWidth };
            }"""
        )
        assert overflow["scroll"] <= overflow["client"] + 1, f"horizontal overflow: {overflow}"

    def assert_clean():
        assert_no_overflow()
        assert not errors, "JS errors: " + "; ".join(errors)

    return {
        "page": page,
        "base_url": base_url,
        "catalog": catalog,
        "goto": goto,
        "errors": errors,
        "assert_no_overflow": assert_no_overflow,
        "assert_clean": assert_clean,
    }
