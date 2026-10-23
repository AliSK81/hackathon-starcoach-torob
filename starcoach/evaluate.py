"""Offline evaluation of request parsing on labeled Persian requests (tests/data/intents.jsonl).

Each labeled slot is one check. Extra filters the label did not ask for count as errors too.
"""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from starcoach.hours import TEHRAN
from starcoach.textnorm import tokens

# A fixed "now" so time answers are reproducible: Thursday 2026-10-22 12:00 Tehran.
EVAL_NOW = datetime(2026, 10, 22, 12, 0, tzinfo=TEHRAN)
DAYS = {"sat": 0, "sun": 1, "mon": 2, "tue": 3, "wed": 4, "thu": 5, "fri": 6}
CONDITION_KEYS = ("installments", "torobpay", "in_person_pay", "fast", "warranty", "open")


def expected_time(label: str) -> str:
    when, hour = label.split()
    base = EVAL_NOW
    if when == "tomorrow":
        base += timedelta(days=1)
    elif when in DAYS:
        today = (EVAL_NOW.weekday() + 2) % 7
        base += timedelta(days=(DAYS[when] - today) % 7)
    return base.replace(hour=int(hour), minute=0).strftime("%Y-%m-%dT%H:%M")


def check_case(case: dict, out: dict) -> list[dict]:
    """Return one {slot, ok, want, got} per checked slot."""
    f = out.get("filters", {})
    checks = []
    q_toks = set(tokens(out.get("query", "")))
    want_words = [w for w in case.get("query_has", [])]
    missing = [w for w in want_words if not set(tokens(w)) <= q_toks]
    checks.append({"slot": "query", "ok": not missing, "want": want_words, "got": out.get("query")})
    for key in ("max_price", "min_price"):
        want = case.get(key)
        got = f.get(key)
        got = int(got) if got is not None else None
        if want is not None or got is not None:
            checks.append({"slot": key, "ok": want == got, "want": want, "got": got})
    for key in ("area", "passage"):
        want, got = case.get(key), f.get(key)
        if want is not None or got is not None:
            checks.append({"slot": key, "ok": want == got, "want": want, "got": got})
    want_c = set(case.get("conditions", []))
    got_c = {k for k in CONDITION_KEYS if f.get(k)}
    if want_c or got_c:
        checks.append({"slot": "conditions", "ok": want_c == got_c, "want": sorted(want_c), "got": sorted(got_c)})
    want_t = expected_time(case["time"]) if case.get("time") else None
    got_t = f.get("at")
    if want_t or got_t:
        checks.append({"slot": "time", "ok": want_t == got_t, "want": want_t, "got": got_t})
    if "cheap" in case or out.get("cheap"):
        checks.append({"slot": "cheap", "ok": bool(case.get("cheap")) == bool(out.get("cheap")),
                       "want": bool(case.get("cheap")), "got": bool(out.get("cheap"))})
    if "intent" in case or out.get("intent", "search") != "search":
        want_i = case.get("intent", "search")
        checks.append({"slot": "intent", "ok": want_i == out.get("intent", "search"), "want": want_i,
                       "got": out.get("intent", "search")})
    if case.get("ambiguous"):
        checks.append({"slot": "ambiguous", "ok": bool(out.get("ambiguous")), "want": True,
                       "got": bool(out.get("ambiguous"))})
    return checks


def run_eval(path: Path, parse: Callable[[str], dict], split: str) -> dict:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = [c for c in cases if split == "all" or c["split"] == split]
    rows, slots_ok, slots_n, exact = [], 0, 0, 0
    per_slot: dict[str, list[int]] = {}
    for case in cases:
        try:
            out = parse(case["text"])
        except Exception as e:  # noqa: BLE001 - one bad case is a failed case, not a crash
            out = {"error": repr(e)}
        checks = check_case(case, out)
        ok = all(c["ok"] for c in checks)
        exact += ok
        for c in checks:
            slots_n += 1
            slots_ok += c["ok"]
            per_slot.setdefault(c["slot"], [0, 0])
            per_slot[c["slot"]][0] += c["ok"]
            per_slot[c["slot"]][1] += 1
        rows.append({"text": case["text"], "ok": ok, "failed": [c for c in checks if not c["ok"]]})
    return {
        "split": split,
        "cases": len(cases),
        "exact_match": round(exact / len(cases), 3) if cases else None,
        "slot_accuracy": round(slots_ok / slots_n, 3) if slots_n else None,
        "per_slot": {k: f"{v[0]}/{v[1]}" for k, v in sorted(per_slot.items())},
        "failures": [r for r in rows if not r["ok"]],
    }


def baseline_parse(text: str) -> dict:
    """No understanding: the raw text is the query and there are no filters."""
    return {"query": text, "filters": {}}
