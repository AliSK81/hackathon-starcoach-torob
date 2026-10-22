"""Smoke test a running instance over HTTP: health, search, product, shop. Standard library only."""

import json
import time
import urllib.parse
import urllib.request

DEFAULT_QUERY = "شارژر اپل ۲۰ وات"


def _get(base: str, path: str, timeout: float) -> tuple[int, dict, float]:
    started = time.time()
    req = urllib.request.Request(base.rstrip("/") + path, headers={"User-Agent": "starcoach-smoke"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            body = json.loads(raw) if "json" in (r.headers.get("Content-Type") or "") else {"text": raw[:200]}
            return r.status, body, time.time() - started
    except urllib.error.HTTPError as e:
        return e.code, {}, time.time() - started


def run(base: str, query: str = DEFAULT_QUERY, timeout: float = 15.0) -> dict:
    """Return {"ok": bool, "checks": [{"name", "ok", "status", "ms", "detail"}]}. Never raises on HTTP errors."""
    checks = []

    def check(name: str, path: str, test) -> dict:
        try:
            status, body, secs = _get(base, path, timeout)
            ok, detail = test(status, body)
        except Exception as e:  # noqa: BLE001 - a smoke test reports, it does not crash
            status, body, secs, ok, detail = None, {}, 0.0, False, repr(e)
        checks.append({"name": name, "ok": ok, "status": status, "ms": round(secs * 1000), "detail": detail})
        return body

    check("health", "/health", lambda s, b: (s == 200 and b.get("status") == "ok", b))
    check("ready", "/ready", lambda s, b: (s == 200, b))
    found = check(
        "search", "/api/search?q=" + urllib.parse.quote(query),
        lambda s, b: (s == 200 and len(b.get("items", [])) > 0, f"{len(b.get('items', []))} items"),
    )
    items = found.get("items") or []
    if items:
        product = check(
            "product", "/api/products/" + items[0]["product_id"],
            lambda s, b: (s == 200 and len(b.get("sellers", [])) > 0, f"{len(b.get('sellers', []))} sellers"),
        )
        sellers = product.get("sellers") or []
        if sellers:
            check(
                "shop", "/api/shops/" + sellers[0]["shop"]["shop_id"],
                lambda s, b: (s == 200 and bool(b.get("shop_id")), b.get("hours_status")),
            )
    check("web", "/", lambda s, b: (s == 200, "index"))
    return {"base": base, "ok": all(c["ok"] for c in checks) and len(checks) >= 6, "checks": checks}
