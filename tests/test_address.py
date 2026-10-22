import pytest

from starcoach.address import canonical_passage, floor_label, parse_address

CASES = [
    # (address, passage, floor, unit, plaque) — real addresses from research 01 §2
    ("میدان فردوسی، مجتمع تجارت جهانی فردوسی، طبقه ۵، واحد ۵۱۴", "تجارت جهانی", 5, "514", None),
    ("خیابان جمهوری، بعد از پل حافظ، پاساژ امجد، طبقه اول، پلاك ١٠", "امجد", 1, None, "10"),
    ("سعدی جنوبی، کوچه شاهچراغی، پلاک ۴", None, None, None, "4"),
    ("خیابان جمهوری، نرسیده به پل حافظ، پاساژ توکل، طبقه -۱، پلاک ۱۰، واحد ۱۰", "توکل", -1, "10", "10"),
    ("خیابان جمهوری، نبش شیخ هادی، پاساژ علالدین 2، طبقه 6، واحد 622", "علاءالدین 2", 6, "622", None),
    ("پاساژ نادری، طبقه بالای همکف (اول)، واحد ۱۰", "نادری", 1, "10", None),
    ("پاساژ کریستال، طبقه منفی (زیرزمین)، پلاک ۵", "کریستال", -1, None, "5"),
    ("خیابان حافظ، بعد از ساختمان بورس، بازار موبایل ایران، طبقه زیرین، واحد 132", "موبایل ایران", -1, "132", None),
]


@pytest.mark.parametrize("address,passage,floor,unit,plaque", CASES)
def test_parse_real_addresses(address, passage, floor, unit, plaque):
    p = parse_address(address)
    assert (p["passage"], p["floor"], p["unit"], p["plaque"]) == (passage, floor, unit, plaque)


def test_canonical_passage_variants():
    for raw in ["علاالدین", "علاءالدین", "علائدین", "علادین"]:
        assert canonical_passage(raw) == "علاءالدین"
    assert canonical_passage("چهارسو") == "چارسو"
    assert canonical_passage("فراز لاله زار") == "فراز"


def test_empty_and_labels():
    assert parse_address(None)["passage"] is None
    assert floor_label(0) == "همکف"
    assert floor_label(-1) == "طبقه منفی 1"
    assert floor_label(None) is None
