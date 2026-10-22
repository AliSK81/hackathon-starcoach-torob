"""Persian text normalization for search keys (research 03 §1.4).

The same function runs on indexed text and on queries. Raw text is kept for display.
"""

import re
import unicodedata

_MAP = {
    "ي": "ی",  # Arabic yeh -> Persian yeh
    "ى": "ی",  # alef maksura
    "ئ": "ی",  # yeh with hamza
    "ك": "ک",  # Arabic kaf -> Persian kaf
    "ة": "ه",  # teh marbuta -> heh
    "ۀ": "ه",  # heh with yeh
    "ہ": "ه",
    "ە": "ه",
    "ؤ": "و",  # waw with hamza
    "أ": "ا",  # alef forms -> alef (آیفون == ایفون)
    "إ": "ا",
    "ٱ": "ا",
    "آ": "ا",
    "ء": "",  # hamza
    "ـ": "",  # tatweel
    "‌": " ",  # ZWNJ
    "‍": "",
    "‎": "",
    "‏": "",
    "‪": "",
    "‫": "",
    "‬": "",
    "‭": "",
    "‮": "",
    "﻿": "",
    "­": "",
    " ": " ",
    " ": " ",
    " ": " ",
    "،": ",",  # Arabic comma
    "؛": ";",
    "؟": "?",
    "٫": ".",  # Arabic decimal separator
    "٬": ",",
    "×": " x ",
    "–": "-",
    "—": "-",
}
for _i in range(10):
    _MAP[chr(0x06F0 + _i)] = str(_i)  # Persian digits
    _MAP[chr(0x0660 + _i)] = str(_i)  # Arabic-Indic digits
for _cp in list(range(0x064B, 0x0660)) + [0x0670]:
    _MAP[chr(_cp)] = ""  # harakat, tanwin, shadda, sukun, superscript alef
_TABLE = str.maketrans(_MAP)

_DIGIT_LETTER = re.compile(r"(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)")
_SPACES = re.compile(r"\s+")
_TOKEN = re.compile(r"[^\W_]+")

# Query-side words that carry no product meaning.
STOPWORDS = frozenset("ها های ی مدل برای با و از به در که این یک میخوام میخواهم لطفا".split())


def normalize(text: str | None, split_alnum: bool = True) -> str:
    """Fold Persian/Arabic variants, digits and case into one search form."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).translate(_TABLE).lower()
    if split_alnum:
        text = _DIGIT_LETTER.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def to_ascii_digits(text: str | None) -> str:
    """Only convert Persian and Arabic digits to ASCII, nothing else."""
    if not text:
        return ""
    return text.translate({0x06F0 + i: str(i) for i in range(10)} | {0x0660 + i: str(i) for i in range(10)})


def tokens(text: str | None, drop_stopwords: bool = False) -> list[str]:
    """Normalized word tokens."""
    out = _TOKEN.findall(normalize(text))
    if drop_stopwords:
        out = [t for t in out if t not in STOPWORDS]
    return out
