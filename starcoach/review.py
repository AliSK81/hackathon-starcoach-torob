"""R29: a product review without a reviews dataset, honestly sourced.

1. Market signals from the Torob data (always): sellers, price spread and freshness, warranty share.
2. An optional AI summary from the specs: strengths, weaknesses, what to check in the shop. Labeled as AI,
   never as user reviews; no prices; cached in an append-only JSONL file so each product is asked once.
"""

import json
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path

AI_LABEL = "جمع‌بندی هوش مصنوعی از مشخصات و دانش عمومی؛ نظر واقعی خریداران نیست."
MAX_SPECS = 25
MAX_ITEMS = 3


def signals(conn: sqlite3.Connection, product_id: str) -> dict | None:
    p = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if p is None:
        return None
    snapshot = conn.execute("SELECT value FROM meta WHERE key = 'snapshot'").fetchone()
    snap = datetime.fromisoformat(snapshot[0]) if snapshot and snapshot[0] else None
    rows = conn.execute(
        """SELECT shop_id, MIN(CASE WHEN price_status = 'ok' THEN price END) AS price, MAX(price_changed_at) AS changed,
                  MAX(warranty_kind = 'yes') AS warranty
           FROM offers WHERE product_id = ? GROUP BY shop_id""",
        (product_id,),
    ).fetchall()
    prices = [r["price"] for r in rows if r["price"]]
    fresh = sum(1 for r in rows if snap and r["changed"] and (snap - datetime.fromisoformat(r["changed"])).days <= 7)
    out = {
        "sellers": len(rows),
        "with_warranty": sum(1 for r in rows if r["warranty"]),
        "fresh_7d": fresh,
        "median_price": int(statistics.median(prices)) if prices else None,
        "spread": round(max(prices) / min(prices), 2) if len(prices) >= 2 else None,
        "notes": [],
    }
    if out["sellers"] >= 10:
        out["notes"].append({"kind": "good", "text": f"پرفروشنده: {out['sellers']} فروشگاه این کالا را ثبت کرده‌اند؛ پیدا کردن و چانه زدن راحت‌تر است"})
    elif out["sellers"] <= 2:
        out["notes"].append({"kind": "warn", "text": "فقط ۱ یا ۲ فروشگاه این کالا را ثبت کرده‌اند؛ قبل از رفتن موجودی را بپرسید"})
    if out["spread"] and out["spread"] > 1.5:
        out["notes"].append({"kind": "warn", "text": f"قیمت‌ها تا {out['spread']:.1f} برابر فرق دارند؛ اصل/غیراصل یا واحد فروش را بپرسید"})
    elif out["spread"] and out["spread"] <= 1.15:
        out["notes"].append({"kind": "good", "text": "قیمت‌ها بین فروشنده‌ها نزدیک به هم است؛ بازار این کالا ثابت است"})
    if rows and out["fresh_7d"] / len(rows) >= 0.5:
        out["notes"].append({"kind": "good", "text": "بیشتر فروشنده‌ها قیمت را در هفته‌ی آخر داده به‌روز کرده‌اند"})
    if rows and out["with_warranty"] / len(rows) >= 0.5:
        out["notes"].append({"kind": "good", "text": f"{out['with_warranty']} از {len(rows)} فروشنده گارانتی ثبت کرده‌اند"})
    return out


class ReviewCache:
    def __init__(self, path: Path):
        self.path = path
        self.items: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    self.items[rec["product_id"]] = rec["review"]
                except (ValueError, KeyError):
                    continue

    def get(self, product_id: str) -> dict | None:
        return self.items.get(product_id)

    def put(self, product_id: str, review: dict) -> None:
        if product_id in self.items:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"product_id": product_id, "review": review}, ensure_ascii=False) + "\n")
        self.items[product_id] = review


def _clean_list(v) -> list[str]:
    if not isinstance(v, list):
        return []
    out = []
    for x in v[:MAX_ITEMS]:
        if isinstance(x, str) and 3 < len(x) < 160 and not any(w in x for w in ("تومان", "تومن", "ریال")):
            out.append(x.strip())
    return out


def ai_review(conn: sqlite3.Connection, product_id: str, settings, cache: ReviewCache) -> dict | None:
    cached = cache.get(product_id)
    if cached:
        return cached | {"cached": True}
    from starcoach.llm import LLMError, chat

    if not settings or not settings.llm_enabled:
        return None
    p = conn.execute("SELECT title, brand, category, specs FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if p is None:
        return None
    specs = [f"{s.get('key')}: {s.get('value')}" for s in json.loads(p["specs"] or "[]")[:MAX_SPECS] if s.get("key")]
    messages = [
        {"role": "system", "content": (
            "You write a short, balanced Persian product review for a shopper who will buy in a physical shop in Tehran. "
            "Use the specs and general knowledge. Never mention prices or shops; never claim to quote users. "
            "Answer only with JSON: {\"strengths\": [<=3 short items], \"weaknesses\": [<=3], "
            "\"check_in_shop\": [<=3 concrete things to check or ask in the shop before paying], \"good_for\": \"one short line\"}.")},
        {"role": "user", "content": f"کالا: {p['title']}\nبرند: {p['brand'] or 'نامشخص'}\nدسته: {p['category']}\nمشخصات:\n" + "\n".join(specs)},
    ]
    try:
        msg = chat(settings, messages, max_tokens=500, purpose="review")
        text = (msg.get("content") or "").strip()
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start:end + 1]) if start >= 0 else {}
    except (LLMError, ValueError):
        return None
    review = {
        "strengths": _clean_list(data.get("strengths")),
        "weaknesses": _clean_list(data.get("weaknesses")),
        "check_in_shop": _clean_list(data.get("check_in_shop")),
        "good_for": data.get("good_for")[:160] if isinstance(data.get("good_for"), str) else None,
        "label": AI_LABEL,
    }
    if not (review["strengths"] or review["check_in_shop"]):
        return None
    cache.put(product_id, review)
    return review
