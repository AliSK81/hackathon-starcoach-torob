from pathlib import Path

from starcoach.evaluate import EVAL_NOW, baseline_parse, run_eval
from starcoach.intent import Gazetteer, parse_price, parse_request
from starcoach.textnorm import normalize

G = Gazetteer(  # keys are normalized, as Gazetteer.from_db builds them
    areas={normalize(n): n for n in ("شیخ هادی", "فردوسی", "بهارستان")},
    passages={normalize(n): n for n in ("علاءالدین", "چارسو", "لاله زار", "جمهوری", "بوشهری")},
)
CASES = Path(__file__).parent / "data" / "intents.jsonl"


def parse(text):
    return parse_request(text, G, now=EVAL_NOW)


def test_budget_words_and_units():
    assert parse_price("زیر ۲۰ میلیون")["max"] == 20_000_000
    assert parse_price("یک و نیم میلیون")["max"] == 1_500_000
    assert parse_price("بین 10 تا 15 میلیون")["min"] == 10_000_000
    assert parse_price("پاوربانک 20 هزار میلی امپر")["max"] is None  # capacity, not a price
    assert parse_price("هدفون بی سیم تا 3 میلیون")["max"] == 3_000_000  # «سی» inside «سیم» is not 30


def test_request_slots():
    r = parse("یه گوشی سامسونگ زیر ۲۰۰ میلیون قسطی تو علاءالدین فردا عصر")
    assert r["query"] == "گوشی سامسونگ"
    assert r["filters"]["max_price"] == 200_000_000
    assert r["filters"]["installments"] == "1"
    assert r["filters"]["passage"] == "علاءالدین"
    assert r["filters"]["at"] == "2026-10-23T17:00"
    assert {u["key"] for u in r["understood"]} == {"budget", "installments", "passage", "at"}


def test_landmark_beats_same_named_passage():
    assert parse("لامپ نزدیک لاله زار")["filters"].get("area") == "فردوسی"
    assert parse("لامپ پاساژ لاله زار")["filters"].get("passage") == "لاله زار"


def test_eval_beats_baseline():
    for split in ("dev", "test"):  # the "hard" split is for the LLM; rules are not expected to pass it
        rules = run_eval(CASES, parse, split)
        base = run_eval(CASES, baseline_parse, split)
        assert rules["slot_accuracy"] >= 0.9 > base["slot_accuracy"]
