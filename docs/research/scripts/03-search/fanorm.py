"""Small hand-written Persian normalizer for search (index side AND query side)."""
import re, unicodedata

_MAP = {
    # Arabic -> Persian letters
    "ي": "ی",  # ي -> ی
    "ى": "ی",  # ى -> ی
    "ئ": "ی",  # ئ -> ی
    "ك": "ک",  # ك -> ک
    "ة": "ه",  # ة -> ه
    "ۀ": "ه",  # ۀ -> ه
    "ہ": "ه",  # ہ -> ه
    "ە": "ه",  # ە -> ه
    "ؤ": "و",  # ؤ -> و
    "أ": "ا",  # أ -> ا
    "إ": "ا",  # إ -> ا
    "ٱ": "ا",  # ٱ -> ا
    "آ": "ا",  # آ -> ا   (search-only folding: آیفون == ایفون)
    "ء": "",        # ء  drop
    "ـ": "",        # ـ tatweel drop
    # invisible / spacing chars
    "‌": " ",       # ZWNJ -> space (گوشی‌ها -> گوشی ها)
    "‍": "",        # ZWJ
    "‎": "", "‏": "", "‪": "", "‫": "", "‬": "",
    "‭": "", "‮": "", "﻿": "", "­": "",
    " ": " ", " ": " ", " ": " ",
    # punctuation variants
    "،": ",", "؛": ";", "؟": "?", "٫": ".", "٬": ",",
    "×": " x ",     # × -> x  (۱۶×۵ -> 16 x 5)
    "–": "-", "—": "-",
}
# Persian ۰-۹ and Arabic-Indic ٠-٩ -> ASCII
for i in range(10):
    _MAP[chr(0x06F0 + i)] = str(i)
    _MAP[chr(0x0660 + i)] = str(i)
# Arabic harakat / tanwin / shadda / sukun / superscript alef / hamza marks
for cp in list(range(0x064B, 0x0660)) + [0x0670]:
    _MAP[chr(cp)] = ""
_TABLE = str.maketrans(_MAP)

_DIGIT_LETTER = re.compile(r"(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)")
_SPACES = re.compile(r"\s+")


def normalize(text: str, split_alnum: bool = True) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)  # Arabic presentation forms (FB50-FEFF), fullwidth
    text = text.translate(_TABLE).lower()
    if split_alnum:  # 128gb -> 128 gb, A54 -> a 54 (helps 'آیفون ۱۳ ۱۲۸' vs '128GB')
        text = _DIGIT_LETTER.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


if __name__ == "__main__":
    import sys
    for s in ["كابل افشان ۱ متری ۱۶×۵", "گوشی‌های سامسونگ", "آیفون ١٣ ۱۲۸GB",
              "مُدِل جديد", "ﻻمپ", "iPhone 13 Pro‌Max"]:
        print(repr(s), "->", repr(normalize(s)))
