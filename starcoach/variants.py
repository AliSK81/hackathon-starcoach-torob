"""R30: variants (colour / size) from sellers' own titles — the "name - colour / size" pattern Torob sellers use.

Used for clothing and shoes (and any product whose sellers list variants), so the buyer can pick a size and
colour and see only the sellers who listed it, at that variant's price.
"""

import re

from starcoach.textnorm import to_ascii_digits

_SIZE = re.compile(r"^(?:سایز\s*)?(?:\d{2,3}(?:[./]\d)?|[0-9]?X{0,3}[SML]|XX?L|فری ?سایز|یک|دو|سه|چهار)(?:\s*مناسب.*)?$", re.I)
MAX_LEN = 30
COLOR_WORDS = ("مشکی", "سفید", "قرمز", "آبی", "ابی", "سبز", "زرد", "نارنجی", "بنفش", "صورتی", "طوسی", "خاکستری",
               "نقره", "طلایی", "سرمه", "سورمه", "کرم", "قهوه", "عسلی", "یاسی", "زرشکی", "رزگلد", "بژ", "نوک مدادی",
               "فیروزه", "لیمویی", "شیری", "مسی", "تیتانیوم", "گرافیت", "یشمی", "کالباسی", "آجری", "نسکافه", "شکلاتی",
               "black", "white", "blue", "red", "green", "gray", "grey", "silver", "gold", "pink", "purple")


def parse_variant(seller_title: str | None) -> dict:
    """«ونس دیور - مشکی کف سفید / 44» -> {"color": "مشکی کف سفید", "size": "44"}; unknown parts are None."""
    out = {"color": None, "size": None}
    if not seller_title or " - " not in seller_title:
        return out
    tail = seller_title.rsplit(" - ", 1)[1].strip()
    parts = [p.strip() for p in tail.split("/")]
    if len(parts) == 2:
        color, size = parts
    elif len(parts) == 1:
        color, size = (None, parts[0]) if _SIZE.match(to_ascii_digits(parts[0])) else (parts[0], None)
    else:
        return out
    if (color and 0 < len(color) <= MAX_LEN and not any(ch.isdigit() for ch in to_ascii_digits(color))
            and any(w in color.lower() for w in COLOR_WORDS)):  # «اصل» or «کپی» is not a colour
        out["color"] = color
    if size and 0 < len(size) <= MAX_LEN:
        s = to_ascii_digits(size)
        if _SIZE.match(s) or s.startswith("سایز"):
            out["size"] = re.sub(r"^سایز\s*", "", s).strip()
    return out


def summarize(offers: list[dict]) -> dict:
    """Distinct colours and sizes with how many sellers listed each; empty when there is no real choice."""
    colors: dict[str, set] = {}
    sizes: dict[str, set] = {}
    for o in offers:
        if o.get("color"):
            colors.setdefault(o["color"], set()).add(o["shop_id"])
        if o.get("size"):
            sizes.setdefault(o["size"], set()).add(o["shop_id"])

    def axis(d: dict[str, set], numeric: bool) -> list[dict]:
        if len(d) < 2:
            return []
        items = [{"value": k, "sellers": len(v)} for k, v in d.items()]
        if numeric and all(re.match(r"^\d+", i["value"]) for i in items):
            items.sort(key=lambda i: float(re.match(r"^\d+(?:\.\d+)?", i["value"]).group(0)))
        else:
            items.sort(key=lambda i: -i["sellers"])
        return items[:20]

    return {"colors": axis(colors, False), "sizes": axis(sizes, True)}
