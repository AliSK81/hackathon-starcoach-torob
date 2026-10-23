"""Seller contact (R5, R6): draft the message, then a SIMULATED seller reply (D6: phones are fake, F2).

The reply is deterministic for (offer, day) and grounded in data: a recent price change makes "in stock"
likely; an old one makes a changed price likely; some sellers don't answer. Every reply is marked simulated.
"""

import hashlib
import json
import random
import sqlite3
from datetime import datetime, timedelta

from starcoach.filters import INSTALLMENT_PROVIDERS, TOROBPAY
from starcoach.hours import DAY_FA, DAYS, hhmm, is_open_at, now_tehran

QUESTIONS = {
    "in_stock": "الان موجود دارید؟",
    "price_now": "قیمت هنوز همین است؟",
    "hours_today": "امروز تا چه ساعتی باز هستید؟",
    "warranty": "گارانتی‌اش چیست؟",
    "installments": "خرید اقساطی یا ترب‌پی دارید؟",
    "hold": "تا وقتی برسم برایم نگه می‌دارید؟",
}
DEFAULT_QUESTIONS = ["in_stock", "price_now", "hours_today"]
SIMULATED_NOTE = "پاسخ نمایشی: شماره‌های فروشگاه‌ها در داده ساختگی است و پیام واقعاً ارسال نمی‌شود."


def _toman(n: int) -> str:
    return f"{n:,} تومان".replace(",", "٬")


def _rng(offer_id: str, day: str) -> random.Random:
    seed = int(hashlib.sha256(f"{offer_id}|{day}".encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def _age_days(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    return (now - datetime.fromisoformat(iso)).total_seconds() / 86400


def load(conn: sqlite3.Connection, offer_id: str) -> tuple[sqlite3.Row, sqlite3.Row, sqlite3.Row] | None:
    o = conn.execute("SELECT * FROM offers WHERE offer_id = ?", (offer_id,)).fetchone()
    if o is None:
        return None
    s = conn.execute("SELECT * FROM shops WHERE shop_id = ?", (o["shop_id"],)).fetchone()
    p = conn.execute("SELECT * FROM products WHERE product_id = ?", (o["product_id"],)).fetchone()
    return o, s, p


def draft(o: sqlite3.Row, s: sqlite3.Row, p: sqlite3.Row, questions: list[str], visit_at: datetime | None) -> str:
    title = p["title"] if not p["title_redacted"] else (o["seller_title"] or "این کالا")
    price = f" با قیمت {_toman(o['price'])}" if o["price"] else ""
    lines = [f"سلام، وقت بخیر. در ترب دیدم «{title}» را{price} ثبت کرده‌اید."]
    for i, q in enumerate(questions, 1):
        text = QUESTIONS[q]
        if q == "hold" and visit_at:
            text = f"اگر موجود است، تا ساعت {visit_at:%H:%M} برایم نگه می‌دارید؟"
        lines.append(f"{i}) {text}")
    lines.append("ممنون.")
    return "\n".join(lines)


def simulate_reply(o: sqlite3.Row, s: sqlite3.Row, questions: list[str], now: datetime,
                   visit_at: datetime | None) -> dict:
    rng = _rng(o["offer_id"], now.strftime("%Y-%m-%d"))
    hours = json.loads(s["hours"]) if s["hours"] else None
    open_now = is_open_at(hours, now)
    no_answer_p = 0.12 + (0.15 if hours is None else 0.0) + (0.5 if open_now is False else 0.0)
    delay_s = rng.randint(2, 6)
    if rng.random() < no_answer_p:
        return {"status": "no_answer", "delay_s": delay_s,
                "text": "پاسخی نیامد." + (" فروشگاه الان طبق ساعت اعلام‌شده بسته است." if open_now is False else ""),
                "facts": {}}
    age = _age_days(o["price_changed_at"], now)
    stock_p = 0.85 if age is not None and age <= 7 else 0.7 if age is not None and age <= 30 else 0.5 if age is not None and age <= 90 else 0.3
    in_stock = rng.random() < stock_p
    facts: dict = {"in_stock": in_stock}
    parts = ["سلام، وقت شما بخیر."]
    if not in_stock:
        parts.append("متأسفانه فعلاً این کالا را نداریم.")
        if rng.random() < 0.4:
            parts.append("احتمالاً هفته‌ی بعد دوباره می‌آید.")
        return {"status": "answered", "delay_s": delay_s, "text": " ".join(parts), "facts": facts}
    parts.append("بله، موجود داریم.")
    if "price_now" in questions:
        if o["price"]:
            changed = rng.random() < (0.25 if age is not None and age <= 7 else 0.5)
            if changed:
                factor = 1 + rng.choice([0.03, 0.05, 0.08, 0.1, -0.03])
                new_price = int(round(o["price"] * factor / 10_000) * 10_000) or o["price"]
                facts.update(price_now=new_price, price_changed=True)
                parts.append(f"قیمت امروز {_toman(new_price)} است.")
            else:
                facts.update(price_now=o["price"], price_changed=False)
                parts.append("قیمت همان است که ثبت شده.")
        else:
            new_price = None
            facts.update(price_now=None, price_changed=None)
            parts.append("قیمت را حضوری می‌گوییم؛ بستگی به مدل دارد.")
    if "hours_today" in questions:
        today = hours.get(["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()]) if hours else None
        if today and today["status"] == "open":
            end = max(b for _, b in today["shifts"])
            facts["closes_at"] = hhmm(end)
            parts.append(f"امروز تا ساعت {hhmm(end)} باز هستیم.")
        elif today and today["status"] == "closed":
            parts.append("امروز تعطیل هستیم.")
            facts["closed_today"] = True
        else:
            close = rng.choice([19, 20, 21])
            facts["closes_at"] = f"{close}:00"
            parts.append(f"امروز تا حدود ساعت {close} هستیم.")
    if "warranty" in questions:
        if o["warranty_kind"] == "yes":
            parts.append(f"گارانتی: {o['warranty_text']}.")
        elif o["warranty_kind"] == "none":
            parts.append("گارانتی ندارد.")
        else:
            w = rng.choice(["۱۸ ماه گارانتی شرکتی دارد.", "تست و تحویل حضوری؛ گارانتی ندارد.", "۶ ماه گارانتی فروشگاه."])
            parts.append(w)
            facts["warranty_from_reply"] = w
    if "installments" in questions:
        providers = {p["provider"] for p in json.loads(s["payment"] or "[]")}
        inst = sorted(providers & INSTALLMENT_PROVIDERS)
        if inst:
            parts.append("خرید اقساطی با " + "، ".join(inst) + " داریم.")
        else:
            parts.append("فعلاً فقط نقدی و کارت‌خوان.")
        facts["installments"] = inst
        facts["torobpay"] = TOROBPAY in providers
    if "hold" in questions:
        hold = rng.random() < 0.7
        until_dt = max(visit_at or now, now + timedelta(hours=1))  # never "hold until now"
        until = until_dt.strftime("%H:%M")
        if until_dt.date() != now.date():
            until = f"{DAY_FA[DAYS[until_dt.weekday()]]} {until}"
        facts["hold_until"] = until if hold else None
        parts.append(f"تا ساعت {until} برایتان نگه می‌داریم؛ به اسم شما." if hold else "نگه داشتن نداریم؛ زودتر تشریف بیاورید.")
    return {"status": "answered", "delay_s": delay_s, "text": " ".join(parts), "facts": facts}


def contact(conn: sqlite3.Connection, offer_id: str, questions: list[str] | None = None,
            visit_at: datetime | None = None, now: datetime | None = None) -> dict | None:
    loaded = load(conn, offer_id)
    if loaded is None:
        return None
    o, s, p = loaded
    now = now or now_tehran()
    questions = [q for q in (questions or DEFAULT_QUESTIONS) if q in QUESTIONS] or DEFAULT_QUESTIONS
    reply = simulate_reply(o, s, questions, now, visit_at)
    return {
        "offer_id": offer_id, "shop_id": s["shop_id"], "shop_name": s["name"], "product_id": p["product_id"],
        "channel": "پیامک", "to": s["phone"], "questions": questions,
        "message": draft(o, s, p, questions, visit_at),
        "reply": reply, "simulated": True, "note": SIMULATED_NOTE,
        "recorded_price": o["price"], "recorded_at": o["price_changed_at"], "asked_at": now.isoformat(timespec="minutes"),
    }


def answer_reply(req: dict) -> dict:
    """A seller's one-tap answer as the same reply shape the buyer's app shows."""
    ans = req.get("answer") or {}
    facts: dict = {"in_stock": bool(ans.get("in_stock"))}
    parts = ["سلام، وقت شما بخیر."]
    if not ans.get("in_stock"):
        parts.append("متأسفانه فعلاً این کالا را نداریم.")
    else:
        parts.append("بله، موجود داریم.")
        recorded = req.get("recorded_price")
        price = ans.get("price_now") or recorded
        if price:
            facts.update(price_now=price, price_changed=bool(recorded and price != recorded))
            parts.append(f"قیمت امروز {_toman(price)} است." if facts["price_changed"] else "قیمت همان است که ثبت شده.")
        if ans.get("hold_until"):
            facts["hold_until"] = ans["hold_until"]
            parts.append(f"تا ساعت {ans['hold_until']} برایتان نگه می‌داریم.")
    if ans.get("note"):
        parts.append(ans["note"])
    return {"status": "answered", "text": " ".join(parts), "facts": facts, "delay_s": 0}
