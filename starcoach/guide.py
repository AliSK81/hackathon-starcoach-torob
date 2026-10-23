"""Guided model choice (R1): questions built from a category's own data, then a short list of models.

No LLM needed: budget bands come from price quantiles, brand options from seller counts, and feature
questions from spec keys whose values split the category well.
"""

import json
import math
import re
import sqlite3
from collections import Counter

from starcoach.filters import Filters
from starcoach.textnorm import normalize

MIN_PRODUCTS = 6
SPEC_MIN_COVERAGE = 0.35  # a feature question needs the key on at least this share of products
SPEC_MAX_VALUES = 5
SPEC_MIN_VALUE_SHARE = 0.08
MAX_FEATURE_QUESTIONS = 3
SHORTLIST = 3
SKIP_SPEC_KEYS = {"برند", "مدل", "نام محصول", "شرکت سازنده", "کشور سازنده", "ابعاد", "وزن", "تاریخ معرفی",
                  "سازگاری", "محتویات جعبه", "اقلام همراه", "توضیحات", "سایر امکانات", "کد", "سری", "رنگ",
                  "رنگ بندی", "باس رم", "فرکانس", "سایز", "رادیو"}
# Features people choose by; asked first when the data supports them.
PREFERRED_KEYS = ["حافظه داخلی", "مقدار رم", "ظرفیت حافظه", "اندازه صفحه نمایش", "اندازه نمایشگر", "نوع اتصال",
                  "نویز کنسلینگ", "حذف نویز", "مقاومت در برابر آب", "ضد آب", "نوع موتور", "جنس بند", "جنس بدنه",
                  "سری پردازنده", "نوع پردازنده", "پردازنده", "ظرفیت باتری", "ظرفیت", "کیفیت تصویر", "رزولوشن",
                  "دید در شب", "نوع دوربین", "نوع لامپ", "توان", "نوع", "کاربرد", "جنس"]
YES_NO = {"دارد", "ندارد", "بله", "خیر", "عدم پشتیبانی", "پشتیبانی"}
UNIT_FOLDS = [  # «5600MHz» == «5600 مگاهرتز», «128GB» == «128 گیگابایت»
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:mhz|مگاهرتز)"), "mhz"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:gb|گیگابایت|گیگ)"), "gb"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:tb|ترابایت)"), "tb"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:hz|هرتز)"), "hz"),
]
AUDIENCE = [("مردانه", "مردانه"), ("زنانه", "زنانه"), ("بچگانه", "بچگانه|کودک|پسرانه|دخترانه")]
AUDIENCE_MIN_SHARE = 0.15


def _band_label(lo: int | None, hi: int | None) -> str:
    def fa(n: int) -> str:
        return f"{n / 1e6:.1f}".rstrip("0").rstrip(".") + " میلیون" if n >= 1e6 else f"{round(n / 1e3)} هزار"
    if lo is None:
        return f"تا {fa(hi)}"
    if hi is None:
        return f"بیش از {fa(lo)}"
    return f"{fa(lo)} تا {fa(hi)}"


def _round_price(v: float) -> int:
    if v <= 0:
        return 0
    mag = 10 ** max(int(math.log10(v)) - 1, 3)
    return int(round(v / mag) * mag)


def category_products(conn: sqlite3.Connection, category: str) -> list[dict]:
    rows = conn.execute(
        """SELECT product_id, title, brand, images, specs, n_shops, min_price, median_price
           FROM products WHERE category = ? AND title_redacted = 0 AND median_price IS NOT NULL""",
        (category,),
    ).fetchall()
    out = []
    for r in rows:
        specs = {}
        for s in json.loads(r["specs"] or "[]"):
            k, v = (s.get("key") or "").strip(), (s.get("value") or "").strip()
            if k and v and k not in specs:
                specs[k] = v
        out.append({**dict(r), "specs": specs, "images": json.loads(r["images"] or "[]")})
    return out


def _clean_value(v: str) -> str:
    v = re.sub(r"\s*عدد\s*$", "", v.strip())
    return re.sub(r"[\s,،]+$", "", re.sub(r"^[\s,،]+", "", v)).strip()


def _value_key(v: str) -> str:
    v = normalize(_clean_value(v))
    for pattern, unit in UNIT_FOLDS:
        v = pattern.sub(lambda m, u=unit: f"{m.group(1)} {u}", v)
    return v[:40]


def _audience(title: str) -> str | None:
    t = normalize(title)
    for value, pattern in AUDIENCE:
        if re.search(rf"(?<!\S)(?:{pattern})(?!\S)", t):
            return value
    return None


def build_questions(products: list[dict]) -> list[dict]:
    """[{id, text, options: [{value, label, count}]}]"""
    questions = []
    prices = sorted(p["median_price"] for p in products)
    q1, q2 = prices[len(prices) // 3], prices[2 * len(prices) // 3]
    b1, b2 = _round_price(q1), _round_price(q2)
    if 0 < b1 < b2:
        bands = [(None, b1), (b1, b2), (b2, None)]
        questions.append({
            "id": "budget", "text": "بودجه‌تان حدوداً چقدر است؟",
            "options": [{"value": f"{lo or ''}-{hi or ''}", "label": _band_label(lo, hi),
                         "count": sum(1 for p in products if (lo is None or p["median_price"] >= lo)
                                      and (hi is None or p["median_price"] < hi))}
                        for lo, hi in bands],
        })
    brands = Counter()
    for p in products:
        if p["brand"]:
            brands[p["brand"]] += p["n_shops"]
    top = [b for b, _ in brands.most_common(6)]
    if len(top) >= 2:
        questions.append({
            "id": "brand", "text": "برند خاصی مد نظرتان است؟",
            "options": [{"value": b, "label": b, "count": sum(1 for p in products if p["brand"] == b)} for b in top],
        })
    # who is it for? (shoes, watches, bags): from titles, when enough titles say it
    n = len(products)
    aud = Counter(a for p in products if (a := _audience(p["title"])))
    if sum(aud.values()) / n >= AUDIENCE_MIN_SHARE and len(aud) >= 2:
        questions.append({
            "id": "audience", "text": "برای چه کسی؟",
            "options": [{"value": v, "label": v, "count": c} for v, c in aud.most_common()],
        })
    # feature questions: spec keys with a few well-spread values
    key_count = Counter(k for p in products for k in p["specs"])
    candidates = []
    for key, cnt in key_count.items():
        preferred = key in PREFERRED_KEYS
        if key in SKIP_SPEC_KEYS or key.startswith("تعداد") or cnt / n < (0.15 if preferred else SPEC_MIN_COVERAGE):
            continue
        raw = [p["specs"][key] for p in products if key in p["specs"]]
        if sum(1 for v in raw if "," in v or "،" in v) / len(raw) > 0.2:
            continue  # multi-valued lists (sizes, colors) don't make clean choices
        values = Counter(_value_key(v) for v in raw)
        common = [(v, c) for v, c in values.most_common(SPEC_MAX_VALUES) if c / cnt >= SPEC_MIN_VALUE_SHARE]
        if len(common) < 2 or sum(c for _, c in common) / cnt < (0.5 if preferred else 0.7):
            continue
        if not preferred and all(_clean_value(v) in YES_NO for v, _ in common):
            continue  # yes/no on a niche feature (e.g. «رادیو») is not how people choose
        shares = [c / cnt for _, c in common]
        entropy = -sum(s * math.log(s) for s in shares)
        labels = {}
        for p in products:
            if key in p["specs"]:
                labels.setdefault(_value_key(p["specs"][key]), _clean_value(p["specs"][key]))
        score = entropy * cnt / n + (10 - PREFERRED_KEYS.index(key) / 10 if preferred else 0)
        candidates.append((score, key, [(v, labels[v], c) for v, c in common]))
    for _, key, vals in sorted(candidates, reverse=True)[:MAX_FEATURE_QUESTIONS]:
        questions.append({
            "id": f"spec:{key}", "text": f"{key}؟",
            "options": [{"value": v, "label": label, "count": c} for v, label, c in vals],
        })
    return questions


def apply_answers(products: list[dict], answers: dict[str, str]) -> list[dict]:
    out = products
    for qid, value in answers.items():
        if not value:
            continue
        if qid == "budget":
            lo, _, hi = value.partition("-")
            lo_v, hi_v = (int(lo) if lo else None), (int(hi) if hi else None)
            out = [p for p in out if (lo_v is None or p["median_price"] >= lo_v) and (hi_v is None or p["median_price"] < hi_v)]
        elif qid == "brand":
            out = [p for p in out if p["brand"] == value]
        elif qid == "audience":
            out = [p for p in out if _audience(p["title"]) == value]
        elif qid.startswith("spec:"):
            key = qid[5:]
            out = [p for p in out if key in p["specs"] and _value_key(p["specs"][key]) == value]
    return out


def shortlist(products: list[dict], match: dict[str, dict] | None = None) -> list[dict]:
    """Pick up to 3 models with different strengths: most available, cheapest, and a strong third."""
    pool = [p for p in products if not match or match.get(p["product_id"], {}).get("match")]
    if not pool:
        return []
    def sellers(p):
        return len(match[p["product_id"]]["match"]) if match else p["n_shops"]
    picks: list[tuple[dict, str]] = []
    most = max(pool, key=lambda p: (sellers(p), -p["median_price"]))
    picks.append((most, f"بیشترین فروشنده ({sellers(most)}) — راحت‌تر پیدا می‌شود و قیمت‌ها قابل مقایسه است"))
    rest = [p for p in pool if p is not most and sellers(p) >= 2] or [p for p in pool if p is not most]
    if rest:
        cheap = min(rest, key=lambda p: p["median_price"])
        picks.append((cheap, "ارزان‌ترین گزینه‌ی این گروه (بر اساس میانه‌ی قیمت فروشنده‌ها)"))
        rest = [p for p in rest if p is not cheap]
    if rest:
        spec_rich = max(rest, key=lambda p: (len(p["specs"]), sellers(p)))
        picks.append((spec_rich, "مشخصات کامل‌تر ثبت شده؛ برای مقایسه‌ی دقیق‌تر"))
    return [{
        "product_id": p["product_id"], "title": p["title"], "brand": p["brand"],
        "image": (p["images"] or [None])[0], "n_shops": p["n_shops"], "sellers_match": sellers(p),
        "median_price": p["median_price"], "min_price": p["min_price"], "why": why,
    } for p, why in picks[:SHORTLIST]]


def guide(conn: sqlite3.Connection, category: str, answers: dict[str, str], f: Filters | None = None,
          seller_stats=None) -> dict:
    products = category_products(conn, category)
    if len(products) < MIN_PRODUCTS:
        return {"category": category, "products": len(products), "questions": [], "matching": len(products),
                "suggestions": shortlist(products)}
    questions = build_questions(products)
    chosen = apply_answers(products, answers)
    match = None
    if f is not None and f.active and seller_stats is not None:
        match = seller_stats(conn, [p["product_id"] for p in chosen], f)
    # option counts reflect the other answers, so the user sees how each choice narrows it
    for q in questions:
        others = {k: v for k, v in answers.items() if k != q["id"]}
        base = apply_answers(products, others)
        for o in q["options"]:
            o["count"] = len(apply_answers(base, {q["id"]: o["value"]}))
    return {"category": category, "products": len(products), "questions": questions, "answers": answers,
            "matching": len(chosen), "suggestions": shortlist(chosen, match)}
