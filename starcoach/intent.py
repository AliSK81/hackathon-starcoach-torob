"""Rule-based Persian request parser: sentence -> product words + filters (research 03 §3.2, 04 §4.2).

No LLM. Everything it finds is reported back as "understood" items, so the user can see and undo it.
"""

import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from starcoach.address import canonical_passage
from starcoach.hours import TEHRAN, now_tehran
from starcoach.textnorm import normalize

# ---------- price ----------
_ONES = {"یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "شیش": 6, "هفت": 7, "هشت": 8, "نه": 9}
_TEENS = {"ده": 10, "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15, "پونزده": 15,
          "شانزده": 16, "شونزده": 16, "هفده": 17, "هجده": 18, "هیجده": 18, "نوزده": 19}
_TENS = {"بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90}
_HUND = {"صد": 100, "یکصد": 100, "دویست": 200, "سیصد": 300, "چهارصد": 400, "پانصد": 500, "پونصد": 500,
         "ششصد": 600, "هفتصد": 700, "هشتصد": 800, "نهصد": 900}
_WORDNUM = {**_ONES, **_TEENS, **_TENS, **_HUND, "نیم": 0.5}
_W = "|".join(sorted(_WORDNUM, key=len, reverse=True))
_NUM = rf"(?:\d+(?:[.,/]\d+)?|(?<!\S)(?:{_W})(?!\S)(?:\s+و\s+(?:{_W})(?!\S))*)"  # «سی» must not match inside «سیم»
_UNIT = (r"(?<=[\s\d])(?:میلیارد|ملیارد|میلیونی|میلیون|ملیون|میل|م|هزاری|هزار|تومان|تومن|تومنی|تومانی|ت|ریال|k|m)"
         r"(?!\w)(?!\s*(?:میلی|امپر|mah|گیگ|مگ|پیکسل|وات|دور|متر))")
_CUR = r"(?:\s*(?:تومان|تومن|تومنی|تومانی|ریال))?"
_MAX_W = r"(?:زیر|کمتر از|کم تر از|حداکثر|نهایتا|تا سقف|ارزان تر از|ارزونتر از|ارزون تر از|تا)"
_MIN_W = r"(?:بالای|بالاتر از|بیشتر از|بیش از|حداقل|گرانتر از|گرون تر از)"
_APX_W = r"(?:حدود|حدودا|در حد|تقریبا|دور و بر|در رنج)"
_CHEAP = re.compile(r"(?<!\S)(?:ارزان|ارزون|ارزونترین|ارزانترین|ارزون ترین|ارزان ترین|اقتصادی|به صرفه|مقرون به صرفه)(?!\S)")
_RANGE = re.compile(rf"(?:بین|از)?\s*(?P<a>{_NUM})\s*(?P<ua>{_UNIT})?{_CUR}\s*(?:تا|-|و(?=\s*\d))\s*(?P<b>{_NUM})\s*(?P<ub>{_UNIT}){_CUR}")
_ONE = re.compile(rf"(?P<cmp>{_MAX_W}|{_MIN_W}|{_APX_W})?\s*(?P<n>{_NUM})\s*(?P<u>{_UNIT}){_CUR}(?:\s*(?:به بالا|به پایین|به بالاتر))?")
_CMP_ONLY = re.compile(r"(?P<cmp>زیر|کمتر از|حداکثر|بالای|بیشتر از|حداقل)\s+(?P<n>\d+(?:[.]\d+)?)(?!\d)"
                       r"(?!\s*(?:گیگ|ترا|مگا|اینچ|متر|سانت|وات|ولت|میلی|gb|tb|mah|g\b))")
DEFAULT_MEDIAN = 3_640_000  # all offers (research 01 §5)


def _num(tok: str) -> float:
    tok = tok.strip()
    if re.fullmatch(r"\d+(?:[.,/]\d+)?", tok):
        if "," in tok and len(tok.split(",")[1]) == 3:
            return float(tok.replace(",", ""))
        return float(tok.replace(",", ".").replace("/", "."))
    return sum(_WORDNUM[w] for w in re.split(r"\s+و\s+", tok))


def _mult(u: str | None) -> float | None:
    if not u:
        return None
    u = u.strip()
    if u.startswith(("میلیارد", "ملیارد")):
        return 1e9
    if u.startswith(("میلیون", "ملیون", "میل")) or u in ("م", "m"):
        return 1e6
    if u.startswith("هزار") or u == "k":
        return 1e3
    if "ریال" in u:
        return 0.1
    return 0.0  # bare تومن: ambiguous


def _resolve(value: float, mult: float | None, median: float) -> tuple[float, bool]:
    if mult and mult > 0:
        return value * mult, False
    if mult == 0.0 and value >= 1000:
        return value, False  # «۵۰۰۰۰۰ تومان» literal
    cands = [value * 1e3, value * 1e6] if value < 1000 else [value]
    return min(cands, key=lambda v: abs(math.log10(v) - math.log10(median))), True


def parse_price(text: str, median: float = DEFAULT_MEDIAN) -> dict:
    """Return {min, max, cheap, ambiguous, matched, rest} on normalized text."""
    q = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    q = re.sub(r"(?<=\d)\s*(میلیون|هزار|تومان|تومن|م)(?!\w)", r" \1", q)
    out = {"min": None, "max": None, "cheap": False, "ambiguous": False, "matched": None}
    if m := _RANGE.search(q):
        ub = m.group("ub")
        ua = m.group("ua") or ub
        a, x1 = _resolve(_num(m.group("a")), _mult(ua), median)
        b, x2 = _resolve(_num(m.group("b")), _mult(ub), median)
        out.update(min=int(min(a, b)), max=int(max(a, b)), ambiguous=x1 or x2, matched=m.group(0).strip())
        q = q.replace(m.group(0), " ")
    elif m := _ONE.search(q):
        v, amb = _resolve(_num(m.group("n")), _mult(m.group("u")), median)
        cmp_, tail = m.group("cmp") or "", m.group(0)
        if re.fullmatch(_MIN_W, cmp_) or "به بالا" in tail:
            out["min"] = int(v)
        elif re.fullmatch(_APX_W, cmp_) or ((m.group("u") or "").endswith("ی") and not cmp_):
            out["min"], out["max"] = int(v * 0.8), int(v * 1.2)
        else:
            out["max"] = int(v)
        out.update(ambiguous=amb, matched=tail.strip())
        q = q.replace(tail, " ")
    elif m := _CMP_ONLY.search(q):
        v, _ = _resolve(float(m.group("n")), None, median)
        if m.group("cmp") in ("بالای", "بیشتر از", "حداقل"):
            out["min"] = int(v)
        else:
            out["max"] = int(v)
        out.update(ambiguous=True, matched=m.group(0).strip())
        q = q.replace(m.group(0), " ")
    if _CHEAP.search(q):
        out["cheap"] = True
        q = _CHEAP.sub(" ", q)
    out["rest"] = re.sub(r"\s+", " ", q).strip()
    return out


# ---------- conditions ----------
CONDITION_WORDS = [
    ("installments", r"اقساط|اقساطی|قسطی|قسط|اعتباری|خرید اعتباری|اسنپ ?پی|دیجی ?پی|تارا|ازکی ?وام|بی ?ان ?پی ?ال"),
    ("torobpay", r"ترب ?پی"),
    ("in_person_pay", r"کارتخوان|کارت ?به ?کارت حضوری|پرداخت حضوری"),
    ("fast", r"ارسال فوری|ارسال سریع|فوری بفرست|همین امروز برسه"),
    ("warranty", r"گارانتی ?دار|گارانتی|ضمانت|اصل|اورجینال|اورجینالی"),
    ("open", r"الان باز|باز باشه|باز باشد|که باز|بازه|باز است|همین الان"),
]
CONDITION_FA = {"installments": "فقط اقساطی", "torobpay": "ترب‌پی", "in_person_pay": "پرداخت حضوری",
                "fast": "ارسال فوری", "warranty": "گارانتی‌دار", "open": "فقط باز"}

# ---------- time ----------
DAY_WORDS = {"شنبه": 0, "یکشنبه": 1, "یک شنبه": 1, "دوشنبه": 2, "دو شنبه": 2, "سه شنبه": 3, "سهشنبه": 3,
             "چهارشنبه": 4, "چهار شنبه": 4, "پنجشنبه": 5, "پنج شنبه": 5, "جمعه": 6}
PART_HOURS = {"صبح": 10, "ظهر": 13, "بعدازظهر": 16, "بعد از ظهر": 16, "عصر": 17, "غروب": 18, "شب": 20}
_DAY_RE = "|".join(sorted(map(re.escape, DAY_WORDS), key=len, reverse=True))
_PART_RE = "|".join(sorted(map(re.escape, PART_HOURS), key=len, reverse=True))
_B, _E = r"(?<!\S)", r"(?!\S)"  # whole words only («شب» must not match «شبکه»)
_TIME_RE = re.compile(
    rf"(?:{_B}(?P<rel>امروز|فردا|پس ?فردا){_E})?\s*(?:{_B}(?P<day>{_DAY_RE}){_E})?\s*"
    rf"(?:{_B}(?P<part>{_PART_RE}){_E})?\s*(?:{_B}ساعت\s*(?P<h>\d{{1,2}})(?::(?P<mm>\d\d))?(?!\d))?"
)


def parse_time(text: str, now: datetime) -> tuple[datetime | None, str | None]:
    """«فردا عصر», «پنجشنبه ساعت ۵», «امروز ساعت 18» -> Tehran datetime and the matched words."""
    for m in _TIME_RE.finditer(text):
        rel, day, part, h = m.group("rel"), m.group("day"), m.group("part"), m.group("h")
        if not (rel or day or part or h):
            continue
        base = now.astimezone(TEHRAN)
        today_idx = (base.weekday() + 2) % 7  # Python Mon=0 -> Iranian Sat=0
        if rel == "فردا":
            base += timedelta(days=1)
        elif rel and rel.replace(" ", "") == "پسفردا":
            base += timedelta(days=2)
        if day:
            ahead = (DAY_WORDS[day] - today_idx) % 7
            base = now.astimezone(TEHRAN) + timedelta(days=ahead)
        hour = int(h) if h else PART_HOURS.get(part or "", None)
        if hour is None:
            hour = 11 if (rel or day) else base.hour
        if h and part in ("عصر", "بعدازظهر", "بعد از ظهر", "غروب", "شب") and hour < 12:
            hour += 12
        if h and not part and 1 <= hour <= 8:
            hour += 12  # «ساعت ۵» in shopping talk means 17:00
        minute = int(m.group("mm") or 0)
        when = base.replace(hour=min(hour, 23), minute=minute, second=0, microsecond=0)
        if when < now.astimezone(TEHRAN) - timedelta(minutes=30) and not (rel or day):
            when += timedelta(days=1)
        return when, m.group(0).strip()
    return None, None


# ---------- places ----------
NEAR_WORDS = r"(?:نزدیک|نزدیکی|حوالی|اطراف|سمت|توی|تو|در|داخل)"
LANDMARKS = {  # common names people say -> a passage or area in the data
    "جمهوری": ("area", "شیخ هادی"),
    "لاله زار": ("area", "فردوسی"),
    "لالهزار": ("area", "فردوسی"),
    "منوچهری": ("area", "فردوسی"),
    "سعدی": ("area", "فردوسی"),
    "امین حضور": ("area", "بهارستان"),
    "علا الدین": ("passage", "علاءالدین"),
}


@dataclass
class Gazetteer:
    areas: dict[str, str] = field(default_factory=dict)  # normalized -> name
    passages: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_db(cls, conn: sqlite3.Connection, min_shops: int = 3) -> "Gazetteer":
        g = cls()
        for (name,) in conn.execute("SELECT DISTINCT area FROM shops WHERE area IS NOT NULL"):
            g.areas[normalize(name)] = name
        for name, n in conn.execute(
            "SELECT passage, COUNT(*) FROM shops WHERE passage IS NOT NULL AND n_offers > 0 GROUP BY 1"
        ):
            if n >= min_shops and len(normalize(name)) >= 3 and not normalize(name).isdigit():
                g.passages[normalize(name)] = name
        return g


def find_place(text: str, g: Gazetteer) -> tuple[dict | None, str | None]:
    """Longest passage or area name in the text (passages win: they are more precise)."""
    best = None
    for kind, table in (("passage", g.passages), ("area", g.areas)):
        for key, name in table.items():
            for m in re.finditer(rf"(?<!\S)(?:(?:پاساژ|مجتمع|بازار|سرای)\s+)?{re.escape(key)}(?!\S)", text):
                if best is None or len(m.group(0)) > len(best[2]):
                    best = (kind, name, m.group(0))
    for key, (kind, name) in LANDMARKS.items():
        k = normalize(key)
        for m in re.finditer(rf"(?<!\S){re.escape(k)}(?!\S)", text):
            # a street/landmark name wins over a same-named passage unless «پاساژ …» was said
            said_passage = best is not None and best[0] == "passage" and best[2] != normalize(best[1])
            if best is None or (not said_passage and len(m.group(0)) >= len(best[2])) or len(m.group(0)) > len(best[2]):
                best = (kind, canonical_passage(name) if kind == "passage" else name, m.group(0))
    if not best:
        return None, None
    return {"kind": best[0], "name": best[1]}, best[2]


# ---------- the whole request ----------
FILLER = re.compile(
    r"(?<!\S)(?:میخوام|میخواهم|می خوام|می خواهم|میخواستم|دنبال|هستم|لطفا|یه|یک|برام|برای من|پیدا کن|پیشنهاد بده|"
    r"پیشنهاد|بده|کن|بگو|کجا|بخرم|خرید|بخرم|از کجا|مغازه|فروشگاه|فروشنده|که|باشه|باشد|داشته|داره|دارن|کدوم|چی|"
    r"خوب|خوبه|مناسب|قیمت|با|و|رو|را|هم|ام|من|برم|بریم|میرم|برای|بهم|ای|ی)(?!\S)"
)
INTENT_WORDS = [
    ("compare", r"مقایسه|فرق|تفاوت|کدوم بهتره|کدام بهتر"),
    ("choose", r"نمیدونم|نمی دونم|نمی‌دونم|کمکم کن|راهنمایی|کدوم مدل|چه مدلی|چی بخرم|مدل مناسب"),
]


def parse_request(text: str, g: Gazetteer, now: datetime | None = None, median: float = DEFAULT_MEDIAN) -> dict:
    """Return {"query", "filters": {...API params...}, "understood": [{"key", "label", "text"}], "ambiguous", "intent"}."""
    now = now or now_tehran()
    t = normalize(text, split_alnum=False)
    understood: list[dict] = []
    filters: dict = {}

    intent = "search"
    for name, pattern in INTENT_WORDS:
        if re.search(pattern, t):
            intent = name
            t = re.sub(pattern, " ", t)
            break

    price = parse_price(t, median)
    t = price["rest"]
    if price["max"] is not None:
        filters["max_price"] = price["max"]
    if price["min"] is not None:
        filters["min_price"] = price["min"]
    if price["matched"]:
        understood.append({"key": "budget", "label": "بودجه", "text": price["matched"]})
    if price["cheap"]:
        understood.append({"key": "cheap", "label": "ارزان‌ترین", "text": "ارزان"})

    for key, pattern in CONDITION_WORDS:
        if m := re.search(rf"(?<!\S)(?:{pattern})(?!\S)", t):
            filters[key] = "1"
            understood.append({"key": key, "label": CONDITION_FA[key], "text": m.group(0)})
            t = t.replace(m.group(0), " ")

    when, when_text = parse_time(t, now)
    if when:
        filters["at"] = when.strftime("%Y-%m-%dT%H:%M")
        understood.append({"key": "at", "label": "زمان بازدید", "text": when_text})
        t = t.replace(when_text, " ")

    place, place_text = find_place(t, g)
    if place:
        filters["area" if place["kind"] == "area" else "passage"] = place["name"]
        understood.append({"key": place["kind"], "label": place["name"], "text": place_text})
        t = t.replace(place_text, " ")
        t = re.sub(rf"(?<!\S){NEAR_WORDS}(?=\s|$)", " ", t)

    t = FILLER.sub(" ", t)
    t = re.sub(r"(?<!\S)(?:تومان|تومن|ریال)(?!\S)", " ", t)
    query = re.sub(r"\s+", " ", t).strip()
    return {
        "query": query,
        "filters": filters,
        "understood": understood,
        "ambiguous": {"budget_unit": price["ambiguous"]} if price["ambiguous"] else {},
        "intent": intent,
        "cheap": price["cheap"],
    }
