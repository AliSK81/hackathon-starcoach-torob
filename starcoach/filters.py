"""User filters (area, budget, visit time, purchase conditions) and data-only "why" reasons."""

import math
from dataclasses import dataclass, field, replace
from datetime import datetime

from starcoach.hours import TEHRAN, is_open_at, now_tehran

INSTALLMENT_PROVIDERS = {"ترب‌پی", "اسنپ‌پی", "دیجی پی", "تارا", "ازکی‌وام"}  # BNPL / credit (F22)
TOROBPAY = "ترب‌پی"
FRESH_DAYS = 30


@dataclass
class Filters:
    min_price: int | None = None
    max_price: int | None = None
    area: str | None = None  # location_label
    passage: str | None = None
    lat: float | None = None  # user's point for distance
    lon: float | None = None
    radius_m: int | None = None
    at: datetime = field(default_factory=now_tehran)  # visit time
    open_only: bool = False
    installments: bool = False
    torobpay: bool = False
    in_person_pay: bool = False
    fast_delivery: bool = False
    warranty: bool = False
    sort: str = "price"  # price | distance

    @property
    def has_shop_filters(self) -> bool:
        return bool(self.area or self.passage or self.radius_m or self.open_only or self.installments
                    or self.torobpay or self.in_person_pay or self.fast_delivery)

    @property
    def active(self) -> bool:
        return self.has_shop_filters or self.min_price is not None or self.max_price is not None or self.warranty


def _int(v: str | None) -> int | None:
    try:
        return int(float(v)) if v not in (None, "") else None
    except ValueError:
        return None


def _float(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _bool(v: str | None) -> bool:
    return v in ("1", "true", "yes", "on")


def parse_filters(params: dict) -> Filters:
    """Build Filters from query params; bad values are ignored, never fatal."""
    at = now_tehran()
    if params.get("at"):
        try:
            parsed = datetime.fromisoformat(params["at"])
            at = parsed if parsed.tzinfo else parsed.replace(tzinfo=TEHRAN)
        except ValueError:
            pass
    sort = params.get("sort") or "price"
    return Filters(
        min_price=_int(params.get("min_price")),
        max_price=_int(params.get("max_price")),
        area=params.get("area") or None,
        passage=params.get("passage") or None,
        lat=_float(params.get("lat")),
        lon=_float(params.get("lon")),
        radius_m=_int(params.get("radius_m")),
        at=at,
        open_only=_bool(params.get("open")),
        installments=_bool(params.get("installments")),
        torobpay=_bool(params.get("torobpay")),
        in_person_pay=_bool(params.get("in_person_pay")),
        fast_delivery=_bool(params.get("fast")),
        warranty=_bool(params.get("warranty")),
        sort=sort if sort in ("price", "distance") else "price",
    )


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def shop_distance(f: Filters, lat: float | None, lon: float | None) -> float | None:
    if f.lat is None or f.lon is None or lat is None or lon is None:
        return None
    return distance_m(f.lat, f.lon, lat, lon)


def shop_matches(f: Filters, shop: dict, payment: list[dict], hours: dict | None) -> bool:
    """shop: a row with area, passage, lat, lon, fast_delivery. Unknown never counts as a match."""
    if f.area and shop["area"] != f.area:
        return False
    if f.passage and shop["passage"] != f.passage:
        return False
    if f.radius_m:
        d = shop_distance(f, shop["lat"], shop["lon"])
        if d is None or d > f.radius_m:
            return False
    if f.open_only and is_open_at(hours, f.at) is not True:
        return False
    providers = {p["provider"] for p in payment}
    if f.installments and not providers & INSTALLMENT_PROVIDERS:
        return False
    if f.torobpay and TOROBPAY not in providers:
        return False
    if f.in_person_pay and not any(p["channel"] == "in_person" for p in payment):
        return False
    if f.fast_delivery and shop["fast_delivery"] != 1:
        return False
    return True


def offer_matches(f: Filters, offer: dict) -> bool:
    """Budget uses normal prices only; an unknown price never matches a budget."""
    if f.min_price is not None or f.max_price is not None:
        if offer["price_status"] != "ok" or offer["price"] is None:
            return False
        if f.min_price is not None and offer["price"] < f.min_price:
            return False
        if f.max_price is not None and offer["price"] > f.max_price:
            return False
    if f.warranty and offer["warranty_kind"] != "yes":
        return False
    return True


def seller_reasons(entry: dict, cheapest: int | None, f: Filters, snapshot_age_days: float | None,
                   cheapest_shown: int | None = None) -> list[dict]:
    """Short, data-only reasons for a seller card. kind: good | info | warn.

    `cheapest` is over all sellers; `cheapest_shown` over the sellers left after filters.
    """
    shop, best = entry["shop"], entry["offers"][0]
    out = []
    if best["price_status"] == "ok" and cheapest is not None and best["price"] == cheapest:
        out.append({"kind": "good", "text": "ارزان‌ترین قیمت ثبت‌شده"})
    elif best["price_status"] == "ok" and cheapest_shown is not None and best["price"] == cheapest_shown:
        out.append({"kind": "good", "text": "ارزان‌ترین با شرایط شما"})
    elif best["price_status"] == "ok" and cheapest:
        extra = (best["price"] - cheapest) / cheapest
        if extra <= 0.05:
            out.append({"kind": "good", "text": "نزدیک به ارزان‌ترین قیمت"})
    if shop["open_now"] is True:
        out.append({"kind": "good", "text": "در زمان بازدید باز است"})
    elif shop["open_now"] is False:
        out.append({"kind": "warn", "text": "در زمان بازدید بسته است"})
    if entry.get("distance_m") is not None:
        d = format_distance(entry["distance_m"])
        out.append({"kind": "info", "text": d if d.startswith("کنار") else f"{d} از شما"})
    providers = {p["provider"] for p in shop.get("payment", [])}
    if providers & INSTALLMENT_PROVIDERS:
        out.append({"kind": "info", "text": "خرید اقساطی: " + "، ".join(sorted(providers & INSTALLMENT_PROVIDERS))})
    if best["warranty_kind"] == "yes":
        out.append({"kind": "info", "text": "گارانتی دارد"})
    if snapshot_age_days is not None and snapshot_age_days <= 7:
        out.append({"kind": "info", "text": "از تازه‌ترین قیمت‌های داده (هفته‌ی آخر)"})
    elif snapshot_age_days is not None and snapshot_age_days > 90:
        out.append({"kind": "warn", "text": "قیمت بیش از ۳ ماه تغییر نکرده"})
    return out


# Filter fields and their Persian names, for "relax this filter" hints.
RELAXABLE = {
    "max_price": "سقف بودجه",
    "min_price": "حداقل قیمت",
    "area": "محله",
    "passage": "پاساژ",
    "radius_m": "فاصله",
    "open_only": "فقط باز",
    "installments": "فقط اقساطی",
    "torobpay": "ترب‌پی",
    "in_person_pay": "پرداخت حضوری",
    "fast_delivery": "ارسال فوری",
    "warranty": "گارانتی‌دار",
}
_OFF = {"max_price": None, "min_price": None, "area": None, "passage": None, "radius_m": None}


def without(f: Filters, name: str) -> Filters:
    return replace(f, **{name: _OFF.get(name, False)})


def active_names(f: Filters) -> list[str]:
    return [n for n in RELAXABLE if getattr(f, n) not in (None, False)]


def format_distance(m: float) -> str:
    if m < 50:
        return "کنار شما (کمتر از ۵۰ متر)"
    if m < 1000:
        return f"{int(round(m / 10.0) * 10)} متر"
    return f"{m / 1000:.1f} کیلومتر"
