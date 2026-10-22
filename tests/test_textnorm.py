from starcoach.textnorm import normalize, to_ascii_digits, tokens


def test_arabic_letters_and_digits_fold():
    assert normalize("كابل افشان ۱ متری ۱۶×۵") == "کابل افشان 1 متری 16 x 5"
    assert normalize("آیفون ١٣ ۱۲۸GB") == "ایفون 13 128 gb"
    assert normalize("ایفون") == normalize("آیفون")


def test_zwnj_diacritics_presentation_forms():
    assert normalize("گوشی‌های سامسونگ") == "گوشی های سامسونگ"
    assert normalize("مُدِل جديد") == "مدل جدید"
    assert normalize("ﻻمپ") == "لامپ"


def test_latin_case_and_alnum_split():
    assert normalize("iPhone 13 Pro‌Max") == "iphone 13 pro max"
    assert normalize("Galaxy A54") == "galaxy a 54"


def test_empty_and_none():
    assert normalize(None) == ""
    assert normalize("") == ""


def test_tokens_and_digits():
    assert tokens("گوشی‌های مدل سامسونگ", drop_stopwords=True) == ["گوشی", "سامسونگ"]
    assert to_ascii_digits("۰۲۱۲۶۴۶۷۱۸۰") == "02126467180"
