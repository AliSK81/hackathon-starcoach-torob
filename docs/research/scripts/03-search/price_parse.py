"""Regex-based price-intent parser for casual Persian shopping queries. Output prices are in TOMAN."""
import math, re
from dataclasses import dataclass, field
from typing import Optional

from fanorm import normalize  # digits -> ASCII, ي/ك -> ی/ک, ZWNJ -> space, lower-case

_ONES = {"یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "شیش": 6, "هفت": 7, "هشت": 8, "نه": 9}
_TEENS = {"ده": 10, "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15, "پونزده": 15,
          "شانزده": 16, "شونزده": 16, "هفده": 17, "هجده": 18, "هیجده": 18, "نوزده": 19}
_TENS = {"بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50, "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90}
_HUND = {"صد": 100, "یکصد": 100, "دویست": 200, "سیصد": 300, "چهارصد": 400, "پانصد": 500, "پونصد": 500,
         "ششصد": 600, "هفتصد": 700, "هشتصد": 800, "نهصد": 900}
_WORDNUM = {**_ONES, **_TEENS, **_TENS, **_HUND, "نیم": 0.5}
_W = "|".join(sorted(_WORDNUM, key=len, reverse=True))
# a number = digits (with , or . or / as separators) or a chain of number words joined by 'و'
NUM = rf"(?:\d+(?:[.,/]\d+)?|(?:{_W})(?:\s+و\s+(?:{_W}))*)"
UNIT = r"(?:میلیارد|ملیارد|میلیونی|میلیون|ملیون|میل|م|هزاری|هزار|تومان|تومن|تومنی|تومانی|ت|ریال|k|m)(?!\w)(?!\s*(?:میلی|امپر|mah|گیگ|مگ|پیکسل|وات|دور|متر))"
# optional trailing currency after a magnitude word, e.g. 'میلیون تومان'
CUR = r"(?:\s*(?:تومان|تومن|تومنی|تومانی|ریال))?"

MAX_W = r"(?:زیر|کمتر از|کم تر از|حداکثر|نهایتا|تا سقف|ارزان تر از|ارزونتر از|ارزون تر از|تا)"
MIN_W = r"(?:بالای|بالاتر از|بیشتر از|بیش از|حداقل|گرانتر از|گرون تر از)"
APX_W = r"(?:حدود|حدودا|در حد|تقریبا|دور و بر|در رنج)"
CHEAP = re.compile(r"\b(?:ارزان|ارزون|ارزونترین|ارزانترین|ارزون ترین|ارزان ترین|اقتصادی|به صرفه|قیمت مناسب|مقرون به صرفه|زیر قیمت)\b")
PRICEY = re.compile(r"\b(?:گران|گرون|گرونترین|گرانترین|لوکس|پرچمدار|حرفه ای|بهترین)\b")


def _num(tok: str) -> float:
    tok = tok.strip()
    if re.fullmatch(r"\d+(?:[.,/]\d+)?", tok):
        if "," in tok and len(tok.split(",")[1]) == 3:  # 20,000 thousands sep
            return float(tok.replace(",", ""))
        return float(tok.replace(",", ".").replace("/", "."))  # 1/5 or 1.5 = 1.5 (Persian decimal is often '/')
    return sum(_WORDNUM[w] for w in re.split(r"\s+و\s+", tok))


def _mult(unit: Optional[str]) -> Optional[float]:
    if not unit:
        return None
    u = unit.strip()
    if u.startswith(("میلیارد", "ملیارد")): return 1e9
    if u.startswith(("میلیون", "ملیون", "میل")) or u in ("م", "m"): return 1e6
    if u in ("هزار", "k"): return 1e3
    if "ریال" in u: return 0.1
    return 0.0  # bare تومان/تومن: ambiguous colloquial magnitude, resolved later


@dataclass
class PriceIntent:
    min_toman: Optional[int] = None
    max_toman: Optional[int] = None
    sort: Optional[str] = None          # 'price_asc' | 'price_desc'
    ambiguous_unit: bool = False
    rest: str = ""                      # query text with price phrases removed
    matched: list = field(default_factory=list)


def _resolve(value: float, mult: Optional[float], unit_word: Optional[str], ref_median: float) -> tuple[float, bool]:
    """mult None  -> no unit at all; 0.0 -> bare 'تومن'. Pick the magnitude closest (log) to the category median."""
    if mult and mult > 0:
        return value * mult, False
    if mult == 0.0 and value >= 1000:      # '۵۰۰۰۰۰ تومان' literal
        return value, False
    cands = [value * 1e3, value * 1e6] if value < 1000 else [value]
    best = min(cands, key=lambda v: abs(math.log10(v) - math.log10(ref_median)))
    return best, True


RANGE = re.compile(rf"(?:بین|از)?\s*(?P<a>{NUM})\s*(?P<ua>{UNIT})?{CUR}\s*(?:تا|-|و(?=\s*\d))\s*(?P<b>{NUM})\s*(?P<ub>{UNIT}){CUR}")
ONE = re.compile(rf"(?P<cmp>{MAX_W}|{MIN_W}|{APX_W})?\s*(?P<n>{NUM})\s*(?P<u>{UNIT}){CUR}(?:\s*(?:به بالا|به پایین|به بالاتر))?")
CMP_ONLY = re.compile(rf"(?P<cmp>زیر|کمتر از|حداکثر|بالای|بیشتر از|حداقل)\s+(?P<n>\d+(?:[.]\d+)?)\b(?!\s*(?:گیگ|ترا|مگا|اینچ|متر|سانت|وات|ولت|میلی|gb|tb|mah))")


def parse_price(query: str, ref_median_toman: float = 3_640_000) -> PriceIntent:
    """ref_median_toman: median price of the detected category (default = dataset-wide offer median)."""
    q = normalize(query, split_alnum=False)
    q = re.sub(r"(?<=\d),(?=\d{3}\b)", "", q)            # 20,000,000 -> 20000000
    q = re.sub(r"(?<=\d)\s*(میلیون|هزار|تومان|تومن|م)\b", r" \1", q)
    out = PriceIntent()
    m = RANGE.search(q)
    if m:
        ub = m.group("ub"); ua = m.group("ua") or ub          # 'بین ۱۰ تا ۱۵ میلیون' -> unit shared
        a, amb1 = _resolve(_num(m.group("a")), _mult(ua), ua, ref_median_toman)
        b, amb2 = _resolve(_num(m.group("b")), _mult(ub), ub, ref_median_toman)
        out.min_toman, out.max_toman = int(min(a, b)), int(max(a, b))
        out.ambiguous_unit = amb1 or amb2
        out.matched.append(m.group(0).strip()); q = q.replace(m.group(0), " ")
    else:
        m = ONE.search(q)
        if m:
            v, amb = _resolve(_num(m.group("n")), _mult(m.group("u")), m.group("u"), ref_median_toman)
            cmp_, tail = (m.group("cmp") or ""), m.group(0)
            if re.fullmatch(MIN_W, cmp_) or "به بالا" in tail:
                out.min_toman = int(v)
            elif re.fullmatch(APX_W, cmp_) or (m.group("u") or "").endswith("ی") and not cmp_:
                out.min_toman, out.max_toman = int(v * 0.8), int(v * 1.2)   # 'حدود ۱۰ میلیون' / '۱۰ میلیونی'
            else:                                                           # زیر/تا/حداکثر or bare amount
                out.max_toman = int(v)
            out.ambiguous_unit = amb
            out.matched.append(tail.strip()); q = q.replace(tail, " ")
        else:
            m = CMP_ONLY.search(q)                                          # 'گوشی زیر 20' (no unit at all)
            if m:
                v, amb = _resolve(float(m.group("n")), None, None, ref_median_toman)
                if m.group("cmp") in ("بالای", "بیشتر از", "حداقل"): out.min_toman = int(v)
                else: out.max_toman = int(v)
                out.ambiguous_unit = True
                out.matched.append(m.group(0)); q = q.replace(m.group(0), " ")
    if CHEAP.search(q):
        out.sort = "price_asc"; q = CHEAP.sub(" ", q)
    elif PRICEY.search(q):
        out.sort = "price_desc"; q = PRICEY.sub(" ", q)
    out.rest = re.sub(r"\s+", " ", q).strip()
    return out


if __name__ == "__main__":
    PHONE, HEADSET = 70_800_000, 4_298_000   # measured category medians (offers.csv)
    tests = [("گوشی سامسونگ زیر ۲۰ میلیون", PHONE), ("گوشی سامسونگ زیر ۲۰ میلیون تومان", PHONE),
             ("هندزفری تا ۵ تومن", HEADSET), ("گوشی تا ۵۰ تومن", PHONE), ("بین ۱۰ تا ۱۵ میلیون", PHONE),
             ("لپ تاپ از ۵۰۰ هزار تا ۲ میلیون", PHONE), ("هندزفری بلوتوث ارزون", HEADSET), ("آیفون ۱۳ ۱۲۸", PHONE),
             ("گوشی زیر 20", PHONE), ("قاب گوشی زیر ۲۰۰ هزار", HEADSET), ("یخچال حدود ۴۰ میلیون", PHONE),
             ("گوشی ۱۰ میلیونی", PHONE), ("گوشی بالای ۳۰ میلیون", PHONE), ("گوشی یک و نیم میلیون", HEADSET),
             ("هدفون زیر پانصد هزار تومن", HEADSET), ("ساعت هوشمند ۲/۵ میلیون به بالا", HEADSET),
             ("مانیتور زیر ۲۷ اینچ", PHONE), ("گوشی زیر ۲۰۰۰۰۰۰۰ ریال", PHONE), ("گوشی زیر 20,000,000 تومان", PHONE),
             ("گرونترین گوشی سامسونگ", PHONE), ("پاوربانک ۲۰ هزار میلی آمپر", HEADSET)]
    for t, ref in tests:
        r = parse_price(t, ref)
        print(f"{t!r:45} -> min={r.min_toman} max={r.max_toman} sort={r.sort} amb={r.ambiguous_unit} rest={r.rest!r}")
