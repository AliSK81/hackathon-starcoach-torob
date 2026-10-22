"""Parse a Tehran shop address into passage, floor, unit and plaque (research 01 §2).

The raw address is always kept for display; these fields only help search, grouping and routes.
"""

import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _norm(s: str) -> str:
    s = s.replace("ي", "ی").replace("ك", "ک").replace("‌", " ").replace("ـ", "").translate(_DIGITS)
    for a, b in (("پاساز", "پاساژ"), ("هم کف", "همکف"), ("زیر زمین", "زیرزمین"),
                 ("زیر همکف", "زیرهمکف"), ("طبقه ی ", "طبقه "), ("طبقهی", "طبقه")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


_SEP = r"[،,\-\(\)]"
_KW = r"(?:پاساژ|مجتمع(?:\s+تجاری)?|بازار(?:چه)?|سرای|سرا|تیمچه|مرکز\s+خرید|ساختمان|برج|مال)"
_RE_PASSAGE = re.compile(
    r"(?P<kw>" + _KW + r")\s+(?P<name>[^،,\-\(\)]+?)(?=\s*(?:" + _SEP + r"|طبقه|واحد|پلاک|مغازه|بلوک|$))"
)
_LANDMARK_BEFORE = re.compile(r"(بعد از|قبل از|روبروی|روبه رو|جنب|نرسیده به|بالاتر از|پایین تر از|کنار|پشت)\s*$")
_KW_PRIORITY = {"پاساژ": 0, "مجتمع تجاری": 0, "مجتمع": 0, "سرای": 0, "سرا": 0, "بازارچه": 0, "تیمچه": 0,
                "مرکز خرید": 0, "بازار": 1, "مال": 1, "برج": 2, "ساختمان": 2}

_FLOOR_WORDS = {
    "همکف": 0, "همکف تجاری": 0, "لابی": 0, "زیرین": -1, "زیرهمکف": -1, "زیرزمین": -1,
    "منفی یک": -1, "منفی دو": -2, "منفی سه": -3, "مثبت یک": 1, "بالای همکف": 1,
    "اول": 1, "یکم": 1, "دوم": 2, "سوم": 3, "چهارم": 4, "پنجم": 5, "ششم": 6, "هفتم": 7, "هشتم": 8,
    "نهم": 9, "دهم": 10, "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7, "هشت": 8,
    "نه": 9, "ده": 10, "منفی": -1,
}
_FLOOR_ALT = "|".join(sorted(map(re.escape, _FLOOR_WORDS), key=len, reverse=True))
_RE_FLOOR = re.compile(r"(?:طبقه|طبقات)\s*:?\s*(?P<val>(?:منفی|-|مثبت|\+)?\s*\d+(?!\d)|" + _FLOOR_ALT + r")")
_RE_FLOOR_BARE = re.compile(r"(?<!\S)(?P<val>همکف|زیرهمکف|زیرزمین)(?!\S)")
_RE_UNIT = re.compile(
    r"(?P<kw>واحد|پلاک|مغازه|غرفه)\s*:?\s*(?:شماره\s*)?(?P<val>[0-9]+(?:[./][0-9]+)?\s*[A-Za-zآ-ی]?(?:\s*و\s*[0-9]+)?)"
)
MAX_FLOOR = 30

# Same building, different spellings (research 01 §2).
_CANON = [
    (re.compile(r"علا\S{0,3}دین"), "علاءالدین"),
    (re.compile(r"^چهارسو"), "چارسو"),
    (re.compile(r"^(تجارت جهانی|فراز|110) (فردوسی|لاله زار)$"), r"\1"),
    (re.compile(r"\s+(یک|1)$"), ""),
    (re.compile(r"\s+دو$"), " 2"),
    (re.compile(r"\s+سه$"), " 3"),
]


def canonical_passage(name: str) -> str:
    name = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", name)  # علاالدین3 -> علاالدین 3
    name = re.sub(r"\s+", " ", name).strip()
    for pattern, repl in _CANON:
        name = pattern.sub(repl, name)
    return name.strip()


def _floor_value(v: str) -> int | None:
    v = v.strip().replace(" ", "")
    m = re.match(r"(منفی|-)?(مثبت|\+)?(\d+)$", v)
    if m:
        n = int(m.group(3))
        n = -n if m.group(1) else n
        return n if abs(n) <= MAX_FLOOR else None
    for word, value in _FLOOR_WORDS.items():
        if word.replace(" ", "") == v:
            return value
    return None


def parse_address(address: str | None) -> dict:
    """Return passage (canonical name), passage_kind, floor (int), unit, plaque. Missing parts are None."""
    out = {"passage": None, "passage_kind": None, "floor": None, "unit": None, "plaque": None}
    if not address:
        return out
    a = _norm(address)
    cands = [m for m in _RE_PASSAGE.finditer(a) if not _LANDMARK_BEFORE.search(a[: m.start()])]
    if cands:
        m = min(cands, key=lambda m: _KW_PRIORITY.get(re.sub(r"\s+", " ", m.group("kw")), 3))
        name = canonical_passage(m.group("name"))
        if name:
            out["passage"] = name
            out["passage_kind"] = re.sub(r"\s+", " ", m.group("kw"))
    m = _RE_FLOOR.search(a) or _RE_FLOOR_BARE.search(a)
    if m:
        out["floor"] = _floor_value(m.group("val"))
    for m in _RE_UNIT.finditer(a):
        value = m.group("val").strip()
        if m.group("kw") == "پلاک":
            out["plaque"] = out["plaque"] or value
        else:
            out["unit"] = out["unit"] or value
    return out


def floor_label(floor: int | None) -> str | None:
    if floor is None:
        return None
    if floor == 0:
        return "همکف"
    if floor < 0:
        return f"طبقه منفی {-floor}"
    return f"طبقه {floor}"
