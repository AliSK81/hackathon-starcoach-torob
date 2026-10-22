"""Weekly opening hours: clean the raw JSON and answer "is it open at this time?" (research 01 §4).

Answers are three-valued: True (open), False (closed), None (unknown). Hours are declared by
the shop, not confirmed.
"""

from datetime import datetime, timedelta, timezone

# F17: Asia/Tehran is UTC+03:30 all year since DST was abolished in 2022.
TEHRAN = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index = datetime.weekday()
DAY_FA = {"sat": "شنبه", "sun": "یکشنبه", "mon": "دوشنبه", "tue": "سه‌شنبه", "wed": "چهارشنبه",
          "thu": "پنجشنبه", "fri": "جمعه"}
WEEK_ORDER = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]  # Iranian week
MIN_SHIFT_MINUTES = 30  # shorter shifts are data noise (F16)


def _minutes(hms: str) -> int:
    h, m = hms.split(":")[:2]
    return int(h) * 60 + int(m)


def clean_hours(raw: dict | None) -> dict | None:
    """Return {day: {"status": "open"|"closed"|"unknown", "shifts": [[start_min, end_min], ...]}} or None."""
    if not raw:
        return None
    out = {}
    for day in DAYS:
        d = raw.get(day) or {}
        status = d.get("status")
        shifts = []
        for s in d.get("shifts") or []:
            try:
                a, b = _minutes(s["start_time"]), _minutes(s["end_time"])
            except (KeyError, ValueError, AttributeError):
                continue
            if a == b:  # 00:00-00:00 padding or 'unsupported' junk
                continue
            if b in (23 * 60 + 59, 23 * 60 + 45):  # how the data writes "until midnight"
                b = 24 * 60
            if (b - a if b > a else b - a + 1440) < MIN_SHIFT_MINUTES:
                continue
            if [a, b] not in shifts:
                shifts.append([a, b])
        if status == "closed":
            out[day] = {"status": "closed", "shifts": []}
        elif status == "declared" and shifts:
            out[day] = {"status": "open", "shifts": sorted(shifts)}
        else:
            out[day] = {"status": "unknown", "shifts": []}
    if all(v["status"] == "unknown" for v in out.values()):
        return None
    return out


def _to_tehran(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TEHRAN)
    return dt.astimezone(TEHRAN)


def is_open_at(hours: dict | None, dt: datetime) -> bool | None:
    if not hours:
        return None
    t = _to_tehran(dt)
    now = t.hour * 60 + t.minute
    yesterday = hours[DAYS[(t.weekday() - 1) % 7]]
    if any(b < a and now < b for a, b in yesterday["shifts"]):  # overnight tail (none in data yet)
        return True
    today = hours[DAYS[t.weekday()]]
    if today["status"] == "closed":
        return False
    if today["status"] == "unknown":
        return None
    return any((a <= now < b) if a < b else now >= a for a, b in today["shifts"])


def hhmm(minutes: int) -> str:
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


def status_text(hours: dict | None, dt: datetime) -> dict:
    """A short Persian status like «باز است · تا 19:00» or «بسته · باز می‌شود شنبه 09:00»."""
    if not hours:
        return {"open": None, "text": "ساعت کاری ثبت نشده"}
    t = _to_tehran(dt)
    now = t.hour * 60 + t.minute
    state = is_open_at(hours, t)
    today_key = DAYS[t.weekday()]
    if state is True:
        end = next(b for a, b in hours[today_key]["shifts"] if a <= now < b or b < a)
        return {"open": True, "text": f"باز است · تا {hhmm(end)}", "closes_in_min": (end - now) % 1440}
    if state is None:
        return {"open": None, "text": "ساعت کاری امروز نامشخص"}
    # closed now: find the next opening in the coming 7 days
    for offset in range(0, 8):
        day = DAYS[(t.weekday() + offset) % 7]
        info = hours[day]
        starts = [a for a, _ in info["shifts"] if offset > 0 or a > now]
        if info["status"] == "open" and starts:
            when = "امروز" if offset == 0 else ("فردا" if offset == 1 else DAY_FA[day])
            return {"open": False, "text": f"بسته · باز می‌شود {when} {hhmm(min(starts))}"}
    return {"open": False, "text": "بسته"}


def week_table(hours: dict | None) -> list[dict]:
    """Rows for display in Iranian week order."""
    if not hours:
        return []
    rows = []
    for day in WEEK_ORDER:
        info = hours[day]
        if info["status"] == "open":
            text = "، ".join(f"{hhmm(a)}–{hhmm(b)}" for a, b in info["shifts"])
        elif info["status"] == "closed":
            text = "تعطیل"
        else:
            text = "نامشخص"
        rows.append({"day": DAY_FA[day], "status": info["status"], "text": text})
    return rows


def now_tehran() -> datetime:
    return datetime.now(TEHRAN)
