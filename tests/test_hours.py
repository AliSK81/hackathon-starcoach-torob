from datetime import datetime, timezone

from starcoach.hours import TEHRAN, clean_hours, is_open_at, status_text, week_table


def shift(a, b):
    return {"start_time": a, "end_time": b}


PAD = shift("00:00:00", "00:00:00")
RAW = {
    "sat": {"status": "declared", "shifts": [shift("09:00:00", "19:00:00"), PAD]},
    "sun": {"status": "declared", "shifts": [shift("09:00:00", "13:00:00"), shift("14:30:00", "20:00:00")]},
    "mon": {"status": "declared", "shifts": [shift("00:00:00", "23:59:00"), PAD]},
    "tue": {"status": "unsupported", "shifts": [shift("08:00:00", "08:00:00")]},
    "wed": {"status": "declared", "shifts": [shift("21:00:00", "21:15:00"), PAD]},
    "thu": {"status": "declared", "shifts": [shift("10:00:00", "14:00:00"), shift("10:00:00", "14:00:00")]},
    "fri": {"status": "closed", "shifts": [PAD, PAD]},
}
H = clean_hours(RAW)

# 2026-10-24 is a Saturday.
SAT = lambda h, m=0: datetime(2026, 10, 24, h, m, tzinfo=TEHRAN)  # noqa: E731


def test_clean_drops_padding_and_noise():
    assert H["sat"] == {"status": "open", "shifts": [[540, 1140]]}
    assert H["mon"]["shifts"] == [[0, 1440]]  # 23:59 means until midnight
    assert H["tue"]["status"] == "unknown"
    assert H["wed"]["status"] == "unknown"  # a 15-minute shift is noise
    assert H["thu"]["shifts"] == [[600, 840]]  # duplicate shift removed
    assert H["fri"]["status"] == "closed"
    assert clean_hours({}) is None
    assert clean_hours(None) is None


def test_is_open_three_values():
    assert is_open_at(H, SAT(10)) is True
    assert is_open_at(H, SAT(8, 59)) is False
    assert is_open_at(H, SAT(19)) is False
    assert is_open_at(H, datetime(2026, 10, 30, 12, tzinfo=TEHRAN)) is False  # Friday
    assert is_open_at(H, datetime(2026, 10, 27, 12, tzinfo=TEHRAN)) is None  # Tuesday unknown
    assert is_open_at(H, datetime(2026, 10, 25, 13, 30, tzinfo=TEHRAN)) is False  # Sunday lunch break
    assert is_open_at(None, SAT(10)) is None


def test_utc_input_is_converted():
    # 06:30 UTC = 10:00 Tehran
    assert is_open_at(H, datetime(2026, 10, 24, 6, 30, tzinfo=timezone.utc)) is True


def test_status_text():
    assert status_text(H, SAT(18)) == {"open": True, "text": "باز است · تا 19:00", "closes_in_min": 60}
    assert status_text(H, SAT(20))["text"] == "بسته · باز می‌شود فردا 09:00"
    assert status_text(H, SAT(7))["text"] == "بسته · باز می‌شود امروز 09:00"
    assert status_text(None, SAT(7))["open"] is None


def test_week_table_order():
    rows = week_table(H)
    assert [r["day"] for r in rows][:2] == ["شنبه", "یکشنبه"]
    assert rows[-1]["text"] == "تعطیل"
