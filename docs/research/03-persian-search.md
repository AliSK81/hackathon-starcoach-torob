# 03 — Persian product search (normalization, SQLite FTS5, price parsing, embeddings, typos)

Scope: search over 225,903 product titles (`products.csv` → `persian_title`) plus 331,506 seller titles (`offers.csv` → `seller_title`) from a Python backend on SQLite. All numbers come from my own runs on the dev box (Windows 11, 16 logical cores, Python 3.14.2, **bundled SQLite 3.50.4**) unless a URL is cited. The scripts and their outputs are copied to `docs/research/scripts/03-search/`; the code that matters is also in this doc.

## TL;DR — recommendation

1. **Write your own ~40-line normalizer (§1.4) and use no NLP library.** hazm's current release does not install on Python 3.14, and by default its normalizer converts digits *to* Persian, which is the opposite of what search needs. Parsivar is an 18 MB wheel last released in Jan 2024.
2. **Use SQLite FTS5 with `unicode61` over normalized text as the main index.** Measured: build 3.2 s, 86.5 MiB, queries 0.5–6.4 ms. Add `prefix='2 3'` and run AND queries with a prefix `*` on the last term, falling back to OR when AND returns nothing.
3. **Do not use `trigram` as the main index.** It is bigger (109.8 MiB), slower on most queries, cannot match tokens shorter than 3 characters (`13`, `LG`, `5`), and it did not fix the typo case either. Use a trigram index **only over the term vocabulary (45.7k terms)** for spelling correction, which took 0.1–2.7 ms per term.
4. **Ranking needs more than bm25.** For "گوشی سامسونگ" the raw bm25 top 3 were all accessories. A category-intent boost moves real phones to the top (§2.4).
5. **Add a brand alias table (fa↔en)** mined from `brand_name` and specs (§5.2), plus about 30 hand-checked entries. Without it, "آیفون ۱۳ ۱۲۸" gets no AND hits, because the titles spell it `iPhone`.
6. **Parse the price before searching (§3).** Prices are in **toman** (`price_toman`). Resolve the ambiguous colloquial "تومن" magnitude using the category's median price.
7. **Skip embeddings in v1.** multilingual-e5-small runs on CPU (283 titles/s with 4 threads, about 13 min for all titles, 331 MiB as fp32), but on product titles it was not clearly better than FTS + aliases and it surfaced semantically loose matches. Keep it as an optional re-ranker later.

---

## 1. Persian normalization

### 1.1 What is actually in the data (products.csv `persian_title`, 225,903 rows)

| feature | rows containing it |
|---|---|
| ASCII digits | 159,899 |
| Latin letters | 132,906 |
| Persian digits ۰-۹ | 39,686 |
| ZWNJ U+200C | 9,115 |
| Arabic yeh ي | 2,497 |
| Arabic kaf ك | 891 |
| Arabic-Indic digits ٠-٩ | 223 |
| alef maksura ى | 122 |
| harakat (fatha / tanwin / shadda) | ~84 |
| tatweel ـ | 59 |
| NBSP / RLM / hamza forms | <30 each |

Spelling variants in titles: آیفون 2,336 vs ایفون 285. iPhone 855 / iphone 148. شیائومی 2,413 vs شیامی 15, plus `Xiaomi` 381. سامسونگ 3,494 vs Samsung 619. Only 57,634 of 225,903 products (25.5%) have a non-null `brand_name`.

### 1.2 How raw FTS5 `unicode61` behaves without normalization (verified)

```text
insert: 'گوشی‌ها','مُدِل','آیفون','ايفون','۱۲۸GB','١٣','f/4.5-6.3','Samsung'
vocab : ['3','4','5','6','f','samsung','آیفون','ايفون','د','ل','م','ها','١٣','گوشی','۱۲۸gb']
```

* ZWNJ is a separator (category Cf), so `گوشی‌ها` → `گوشی` + `ها`. That is fine.
* **Harakat break words apart**: `مُدِل` → `م`,`د`,`ل`. Combining marks (Mn) are not in the default `L* N* Co` token categories, and `remove_diacritics` only applies to Latin script ([sqlite.org/fts5.html](https://www.sqlite.org/fts5.html), unicode61 section).
* `ي` and `ی` stay as different tokens, and so do `آ` and `ا`.
* `١٣` ≠ `13`, and `۱۲۸gb` stays one token.

⇒ Normalize **both** the indexed text and the query with the same function.

### 1.3 Libraries

| lib | latest (PyPI) | size | license | notes |
|---|---|---|---|---|
| **hazm** | 0.12.1 (2026-04-01) | 887 KB wheel + nltk, python-crfsuite, flashtext, huggingface-hub | MIT | **`requires_python >=3.12,<3.14`**, so it will not install on our Python 3.14 (pip falls back to 0.10.0). `Normalizer()` defaults include `persian_numbers=True` (converts Latin digits to Persian), `correct_spacing`, `seperate_mi`, `persian_style`. Useful for prose, wrong for search keys. [pypi](https://pypi.org/project/hazm), [normalizer.py](https://github.com/roshan-research/hazm/blob/master/hazm/normalizer.py) |
| **parsivar** | 0.2.3.1 (2024-01-02) | **18 MB wheel** (bundled models), dep nltk | MIT (repo LICENSE.txt; no PyPI license metadata) | Has Pinglish→Persian conversion and statistical half-space correction. Releases look inactive; 26 open issues. [github](https://github.com/ICTRC/Parsivar), [LREC'18 paper](https://aclanthology.org/L18-1179/) |
| **persian-tools** (py-persian-tools) | 0.0.11 (2023-03-19) | 35 KB | MIT | Digit conversion, number↔words, national-ID checks. Stale. [github](https://github.com/persian-tools/py-persian-tools) |
| persiantools (majiidd) | 6.2.0 (2026-08-05) | 29 KB, no deps | MIT | Jalali dates plus `characters.ar_to_fa` and `digits.fa_to_en`. Maintained, but it is overkill for 20 map entries. [github](https://github.com/majiidd/persiantools) |
| dadmatools | 2.3.6 | heavy (spacy, gensim, torch extra) | Apache-2.0 | Requires Python `<3.13`. Not relevant here. |

(The PyPI metadata above was pulled with `curl https://pypi.org/pypi/<name>/json`.)

**Verdict: a hand-written normalizer is enough** and is deterministic, needs no dependencies, and processed all 225,903 titles in **3.8 s** including CSV parsing. Our needs are character folding, not linguistic analysis.

### 1.4 The exact character map + code (tested)

| from | to | why |
|---|---|---|
| ي U+064A, ى U+0649, ئ U+0626 | ی U+06CC | Arabic yeh / alef maksura / yeh-hamza |
| ك U+0643 | ک U+06A9 | Arabic kaf |
| ة U+0629, ۀ U+06C0, ہ U+06C1, ە U+06D5 | ه U+0647 | teh marbuta / heh-yeh (کیسهٔ) |
| ؤ U+0624 | و | |
| أ U+0623, إ U+0625, ٱ U+0671, **آ U+0622** | ا | آیفون ≡ ایفون (search-only folding) |
| ء U+0621, ـ U+0640 (tatweel) | (removed) | |
| U+064B–U+065F, U+0670 (harakat, tanwin, shadda, sukun, superscript alef) | (removed) | |
| ZWNJ U+200C | space | گوشی‌ها → `گوشی ها`; اچ‌پی ≡ اچ پی |
| ZWJ U+200D, LRM/RLM U+200E/F, U+202A–E, BOM U+FEFF, soft hyphen U+00AD | (removed) | |
| NBSP U+00A0, U+202F, U+2009 | space | |
| ۰-۹ U+06F0–9, ٠-٩ U+0660–9 | 0-9 | |
| ، ؛ ؟ ٫ ٬ | , ; ? . , | |
| × U+00D7 | ` x ` | `۱۶×۵` → `16 x 5` |
| – — | - | |
| (pre-step) NFKC | | Arabic presentation forms U+FB50–FEFF (ﻻ → لا), fullwidth Latin |
| (post-step) lower() + split digit/letter boundaries | | `128GB` → `128 gb`, `A54` → `a 54` |

```python
import re, unicodedata
_MAP = {"ي":"ی","ى":"ی","ئ":"ی","ك":"ک",
        "ة":"ه","ۀ":"ه","ہ":"ه","ە":"ه","ؤ":"و",
        "أ":"ا","إ":"ا","ٱ":"ا","آ":"ا",
        "ء":"","ـ":"","‌":" ","‍":"","‎":"","‏":"",
        "‪":"","‫":"","‬":"","‭":"","‮":"","﻿":"","­":"",
        " ":" "," ":" "," ":" ","،":",","؛":";","؟":"?",
        "٫":".","٬":",","×":" x ","–":"-","—":"-"}
for i in range(10):
    _MAP[chr(0x06F0+i)] = str(i); _MAP[chr(0x0660+i)] = str(i)
for cp in list(range(0x064B, 0x0660)) + [0x0670]:
    _MAP[chr(cp)] = ""
_TABLE = str.maketrans(_MAP)
_DIGIT_LETTER = re.compile(r"(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)")

def normalize(text: str, split_alnum: bool = True) -> str:
    if not text: return ""
    text = unicodedata.normalize("NFKC", text).translate(_TABLE).lower()
    if split_alnum: text = _DIGIT_LETTER.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()
```

Test output:

```text
'كابل افشان ۱ متری ۱۶×۵' -> 'کابل افشان 1 متری 16 x 5'
'گوشی‌های سامسونگ'   -> 'گوشی های سامسونگ'
'آیفون ١٣ ۱۲۸GB'          -> 'ایفون 13 128 gb'
'مُدِل جديد'              -> 'مدل جدید'
'ﻻمپ'                     -> 'لامپ'
'iPhone 13 Pro‌Max'  -> 'iphone 13 pro max'
```

**Notes:**

* **`ها`/`های` suffix.** Because ZWNJ becomes a space, `ها` ends up as its own token. Drop `ها، های، ی` as query-side stopwords. Glued forms like `گوشیها` are rare, and the prefix `*` on the last term covers some of them. Do not stem the index: product words (`بلوتوثی`, `هندزفری`) are not prose.
* **Query-side stopwords used:** `ها های مدل برای با و ارزون ارزان قیمت خرید بهترین تا`. Price words are removed first by the price parser.
* **Store the raw title for display** and index only the normalized form.

## 2. SQLite FTS5

### 2.1 Facts

* **Version.** `python -c "import sqlite3;print(sqlite3.sqlite_version)"` prints **3.50.4** (Python 3.14.2 on Windows; python.org builds bundle their own SQLite). On a Linux VPS, Python links the **system** libsqlite3, so check the version there. FTS5 trigram needs ≥ **3.34.0** (2020-12-01, [simonw/sqlite-fts5-trigram](https://github.com/simonw/sqlite-fts5-trigram), [sqlite forum](https://sqlite.org/forum/forumpost/76b444bebe?t=c)). Trigram `remove_diacritics` needs ≥ 3.45 ([GRDB PR](https://github.com/groue/GRDB.swift/pull/1655)). `contentless_unindexed=1` appears to be 3.47.0 ([yunqa note](https://yunqa.de/delphi/news/2024-11-08_sqlite3), unverified against official release notes).
* **unicode61** tokens are Unicode categories `L* N* Co`. Everything else is a separator. `remove_diacritics` is described for Latin script only ([fts5 docs](https://www.sqlite.org/fts5.html)). With our normalizer in front of it, unicode61 works fine for Persian.
* **trigram:** "Substrings consisting of fewer than 3 unicode characters do not match any rows" in MATCH queries. The index can serve `LIKE`/`GLOB`.
* **bm25:** k1=1.2 and b=0.75 are hard-coded. Lower is better. Per-column weights go in as `bm25(t, w1, w2, …)`. Prefix queries use `"term"*`, and `prefix='2 3'` builds prefix indexes. `detail=column` / `none` shrink the index but disable phrase/NEAR queries ([fts5 docs](https://www.sqlite.org/fts5.html)).
* **Gotcha (hit during the experiment):** `bm25()` cannot be used once the query planner flattens a subquery or GROUP BY ("unable to use function bm25 in the requested context"). Use the `rank` column inside a subquery that has `ORDER BY rank LIMIT n`.

### 2.2 Experiment setup

```python
# rows: (product_id, normalize(title), normalize(brand_name), normalize(category_name), raw_title)
CREATE VIRTUAL TABLE p USING fts5(product_id UNINDEXED, title, brand, category, raw UNINDEXED, <opts>);
executemany(INSERT ...); INSERT INTO p(p) VALUES('optimize'); VACUUM;
-- unicode61 opts: tokenize='unicode61 remove_diacritics 2', prefix='2 3'
-- trigram  opts: tokenize='trigram'
-- unicode61 query: '"t1" AND "t2" AND "tlast"*' ORDER BY bm25(p,5.0,3.0,1.0) (title,brand,category), fallback to OR if 0 hits
-- trigram query : title:"t" AND ... for tokens >=3 chars, plus `title LIKE '%t%'` for tokens <3 chars
```

### 2.3 Results (`python fts_bench.py`)

| | build time | DB size |
|---|---|---|
| normalize + read CSV (225,903 rows) | 3.8 s | — |
| plain table with same columns, no index | — | 47.3 MiB |
| **FTS5 unicode61 + prefix 2,3** | **3.2 s** | **86.5 MiB** (~39 MiB index) |
| FTS5 trigram | 4.4 s | 109.8 MiB (~62 MiB index) |
| seller titles (offers.csv, 331,506), unicode61 contentless | 3.4 s (+3.3 s normalize) | 65.5 MiB |

| query (as typed) | unicode61: hits / ms / top-3 | trigram: hits / ms / top-3 |
|---|---|---|
| گوشی سامسونگ | AND 2,409 / 4.7 ms: باتری گوشی سامسونگ E250; گوشی سامسونگ گلکسی S25 اولترا; باتری گوشی سامسونگ S10 PLUS | 519 / 6.0 ms: فلت گوشی سامسونگ A31; فلت … A30S; کاور گوشی … A71 |
| آیفون ۱۳ ۱۲۸ | **AND = 0** → OR 4,876 / 4.8 ms: منبع تغذیه آیفون تصویری … 1286 (wrong: آیفون here is a video door phone); مانیتور آیفون تصویری 1286; گوشی اپل (استوک) iPhone 13 \| حافظه 128 | **0 / 0.9 ms** |
| هندزفری بلوتوث ارزون | 300 / 0.9 ms: هندزفری بلوتوثی مدل k2; … Y80; … Ultrapods Pro | 113 / 2.4 ms: same first 2; هندزفری بلوتوثی انکر |
| iphone 13 | 169 / 0.7 ms: دوربین جلو آیفون ۱۳ (iPhone 13); دوربین اصلی iphone 13; محافظ صفحه … iPhone 13 | 170 / 7.1 ms: قاب سیلیکونی … iPhone 13; قاب … iPhone 13 Pro Max; فلت شارژ آیفون iPhone 13 |
| لنز دوربین سونی | 142 / 1.3 ms: لنز دوربین سونی Tamron 80-210; … ۷۵-۳۰۰ دست دوم; … Batis 25mm | 61 / 3.5 ms: Tamron 80-210; FE 50mm f/2.5 G; FE 85mm f/1.4 GM |
| کابل افشان ۱۶×۵ | 9 / 6.4 ms: کابل افشان 5 در 16 (5x16) کرمان کابل ابهر; … هادی کابل البرز; کابل ۵×۱۶ افشان ویام | 18 / 11.4 ms: کابل ۵×۱۶ افشان ویام; کابل افشان 16x5 مغان; … کرمان کابل ابهر |
| شیامی ردمی | AND 0 → OR 123 / 0.5 ms: گلس شیامی 11 تی; … (no Redmi phones) | 0 / 0.4 ms |
| هدفون بی‌سیم | 685 / 2.3 ms: هدفون بی سیم بی دبلیو HF14; هدفون بی سیم M19; … AKZ55 | 585 / 6.8 ms: similar |
| samsung a54 | 9 / 0.7 ms: فلت مین سامسونگ Samsung Galaxy A54 …; فلت پاور …; فلت سنسور اثر انگشت … | 9 / 4.9 ms: same set |
| ساعت کاسیو | 401 / 1.2 ms: ساعت کاسیو اصل; ساعت مچی کاسیو GA; ساعت مچی کاسیو اصل | 391 / 2.4 ms: same |
| ایرپاد | 250 / 0.7 ms | 222 / 1.0 ms |
| سامسنگ (typo) | 0 | 0 |

With the alias expansion and category boost from `fts_bench2.py`:

```text
آیفون ۱۳ ۱۲۸ => ("ایفون" OR "iphone") AND ("13") AND ("128"*): 4 hits 0.8 ms
   - گوشی اپل (استوک) iPhone 13 | حافظه 128 گیگابایت           [گوشی موبایل]
   - گوشی اپل iPhone 13 (Not Active) | حافظه 128 گیگابایت      [گوشی موبایل]
   - گوشی اپل دو سیم (استوک) iPhone 13 | حافظه 128 گیگابایت    [گوشی موبایل]
شیامی ردمی => ("شیامی" OR "شیائومی" OR "xiaomi") AND ("ردمی"*): 43 hits 0.4 ms
گوشی سامسونگ + `bm25(...) - 10*(category='گوشی موبایل')`: 11.1 ms
   - گوشی سامسونگ Samsung Galaxy Z Flip 8 5G حافظه 256 و رم 12 گیگابایت
   - گوشی سامسونگ Samsung GALAXY S22 ULTRA 5G 256GB Ram 12GB (کارکرده)
   - گوشی سامسونگ گلکسی S25 اولترا
offers FTS, '"iphone" AND "13" AND "128"': 9 hits, top-500 grouped by product_id 0.8 ms
```

### 2.4 Conclusions

* **unicode61 + normalizer** is fast (all queries ≤ 6.4 ms, mostly < 2 ms), small, and handles mixed Persian/Latin/digit text well. Trigram costs about 27% more disk, ran 1.2–10× slower in this run, and silently drops 2-character terms such as `13`, `LG`, `5`, `x`, `a`. Its one advantage is substring matching (`5x16` inside `(5x16)`), and the normalizer's digit/letter split already covers most of that.
* **Ranking is the real problem, not recall.** Generic nouns such as "گوشی" also appear in thousands of accessory titles (باتری/فلت/گلس/قاب گوشی). Practical fixes, in order:
  1. Category-intent boost. Map the query head noun to the dominant category, either with a small FTS over the 3,428 `category_name`s or with a hand map (گوشی→گوشی موبایل, لپ تاپ→لپ تاپ و نوت بوک). Then rank `bm25 − boost`.
  2. A penalty for accessory head-words (قاب، گلس، فلت، باتری، کاور، محافظ) when the query does not contain them.
  3. Popularity as a tie-break: number of offers per product, joined from offers.
* **Seller titles:** a contentless FTS5 table (or one with `content=` pointing to an offers table) costs 65.5 MiB / 3.4 s. Use it as a second recall source: group hits by `product_id` and merge with the product hits. Seller titles add variants such as `iphone` vs `ایفون` for the same product.
* **Schema suggestion:** `products_fts(title, brand, brand_aliases, category, tokenize='unicode61 remove_diacritics 2', prefix='2 3')` with `content='products', content_rowid='rowid'` so text is not stored twice. Put the alias-expanded brand into the `brand_aliases` column at index time, so queries in Latin or Persian both hit without OR-expansion at query time.

## 3. Price parsing

### 3.1 Toman vs Rial

* The official unit is the rial, and **1 toman = 10 rials**. Toman is the everyday unit for prices. Written prices are often in rials, spoken ones in tomans ([Wikipedia: Iranian rial](https://en.wikipedia.org/wiki/Iranian_rial)). Redenomination: Parliament approved a 1 toman = 10,000 current rials scheme in May 2020, and on **5 Oct 2025** voted for a new rial worth 10,000 current rials (100 qirans), with both currencies circulating in parallel for 3 years. Its effective status is not confirmed (same source).
* **Our dataset is already in toman:** the column is `offers.price_toman`. Measured medians from offers.csv joined to category: گوشی موبایل p50 **70.8M** (p10 2.7M, p90 360M); هدفون، هدست و هندزفری p50 4.3M; شارژر گوشی p50 2.9M; کیف و کاور گوشی p50 530k; لپ تاپ و نوت بوک p50 306M; all offers p50 3.64M. There are garbage outliers (min 1, max 7.3e17), so clip them.
* **Colloquial "تومن".** Traditionally a bare "X تومن" in speech meant **X thousand toman** ("۵ تومن" = 5,000 toman). With inflation, people now also drop "میلیون", and in car or phone talk "۲۰ تومن" commonly means 20 million. *I found no authoritative source for this colloquial usage* (searches returned only low-quality travel pages). Treat it as ambiguous and resolve it by category: pick ×1,000 or ×1,000,000, whichever puts the value closer (log scale) to the category's median price. Set `ambiguous_unit=True` so the UI can confirm ("منظورتان ۵ میلیون تومان است؟").
* Rial input ("۲۰۰۰۰۰۰۰ ریال") is divided by 10.

### 3.2 Parser (tested; depends on `normalize` from §1.4)

```python
import math, re
from dataclasses import dataclass, field
from typing import Optional
from fanorm import normalize

_ONES = {"یک":1,"یه":1,"دو":2,"سه":3,"چهار":4,"پنج":5,"شش":6,"شیش":6,"هفت":7,"هشت":8,"نه":9}
_TEENS = {"ده":10,"یازده":11,"دوازده":12,"سیزده":13,"چهارده":14,"پانزده":15,"پونزده":15,
          "شانزده":16,"شونزده":16,"هفده":17,"هجده":18,"هیجده":18,"نوزده":19}
_TENS = {"بیست":20,"سی":30,"چهل":40,"پنجاه":50,"شصت":60,"هفتاد":70,"هشتاد":80,"نود":90}
_HUND = {"صد":100,"یکصد":100,"دویست":200,"سیصد":300,"چهارصد":400,"پانصد":500,"پونصد":500,
         "ششصد":600,"هفتصد":700,"هشتصد":800,"نهصد":900}
_WORDNUM = {**_ONES, **_TEENS, **_TENS, **_HUND, "نیم": 0.5}
_W = "|".join(sorted(_WORDNUM, key=len, reverse=True))
NUM = rf"(?:\d+(?:[.,/]\d+)?|(?:{_W})(?:\s+و\s+(?:{_W}))*)"
UNIT = (r"(?:میلیارد|ملیارد|میلیونی|میلیون|ملیون|میل|م|هزاری|هزار|تومان|تومن|تومنی|تومانی|ت|ریال|k|m)"
        r"(?!\w)(?!\s*(?:میلی|امپر|mah|گیگ|مگ|پیکسل|وات|دور|متر))")   # '۲۰ هزار میلی آمپر' is not a price
CUR = r"(?:\s*(?:تومان|تومن|تومنی|تومانی|ریال))?"
MAX_W = r"(?:زیر|کمتر از|کم تر از|حداکثر|نهایتا|تا سقف|ارزان تر از|ارزونتر از|ارزون تر از|تا)"
MIN_W = r"(?:بالای|بالاتر از|بیشتر از|بیش از|حداقل|گرانتر از|گرون تر از)"
APX_W = r"(?:حدود|حدودا|در حد|تقریبا|دور و بر|در رنج)"
CHEAP = re.compile(r"\b(?:ارزان|ارزون|ارزونترین|ارزانترین|ارزون ترین|ارزان ترین|اقتصادی|به صرفه|قیمت مناسب|مقرون به صرفه|زیر قیمت)\b")
PRICEY = re.compile(r"\b(?:گران|گرون|گرونترین|گرانترین|لوکس|پرچمدار|حرفه ای|بهترین)\b")

def _num(tok):
    tok = tok.strip()
    if re.fullmatch(r"\d+(?:[.,/]\d+)?", tok):
        if "," in tok and len(tok.split(",")[1]) == 3: return float(tok.replace(",", ""))
        return float(tok.replace(",", ".").replace("/", "."))       # ۲/۵ = 2.5 (Persian decimal slash)
    return sum(_WORDNUM[w] for w in re.split(r"\s+و\s+", tok))     # 'یک و نیم' = 1.5

def _mult(u):
    if not u: return None
    u = u.strip()
    if u.startswith(("میلیارد","ملیارد")): return 1e9
    if u.startswith(("میلیون","ملیون","میل")) or u in ("م","m"): return 1e6
    if u in ("هزار","k"): return 1e3
    if "ریال" in u: return 0.1
    return 0.0                                                      # bare تومن: ambiguous

@dataclass
class PriceIntent:
    min_toman: Optional[int] = None; max_toman: Optional[int] = None
    sort: Optional[str] = None; ambiguous_unit: bool = False
    rest: str = ""; matched: list = field(default_factory=list)

def _resolve(value, mult, unit_word, ref_median):
    if mult and mult > 0: return value * mult, False
    if mult == 0.0 and value >= 1000: return value, False          # '۵۰۰۰۰۰ تومان' literal
    cands = [value * 1e3, value * 1e6] if value < 1000 else [value]
    return min(cands, key=lambda v: abs(math.log10(v) - math.log10(ref_median))), True

RANGE = re.compile(rf"(?:بین|از)?\s*(?P<a>{NUM})\s*(?P<ua>{UNIT})?{CUR}\s*(?:تا|-|و(?=\s*\d))\s*(?P<b>{NUM})\s*(?P<ub>{UNIT}){CUR}")
ONE = re.compile(rf"(?P<cmp>{MAX_W}|{MIN_W}|{APX_W})?\s*(?P<n>{NUM})\s*(?P<u>{UNIT}){CUR}(?:\s*(?:به بالا|به پایین|به بالاتر))?")
CMP_ONLY = re.compile(r"(?P<cmp>زیر|کمتر از|حداکثر|بالای|بیشتر از|حداقل)\s+(?P<n>\d+(?:[.]\d+)?)\b"
                      r"(?!\s*(?:گیگ|ترا|مگا|اینچ|متر|سانت|وات|ولت|میلی|gb|tb|mah))")

def parse_price(query: str, ref_median_toman: float = 3_640_000) -> PriceIntent:
    """ref_median_toman = median price of the detected category (default: whole-dataset offer median)."""
    q = normalize(query, split_alnum=False)
    q = re.sub(r"(?<=\d),(?=\d{3}\b)", "", q)
    q = re.sub(r"(?<=\d)\s*(میلیون|هزار|تومان|تومن|م)\b", r" \1", q)
    out = PriceIntent()
    if m := RANGE.search(q):
        ub = m.group("ub"); ua = m.group("ua") or ub                       # unit shared: 'بین ۱۰ تا ۱۵ میلیون'
        a, x1 = _resolve(_num(m.group("a")), _mult(ua), ua, ref_median_toman)
        b, x2 = _resolve(_num(m.group("b")), _mult(ub), ub, ref_median_toman)
        out.min_toman, out.max_toman, out.ambiguous_unit = int(min(a, b)), int(max(a, b)), x1 or x2
        out.matched.append(m.group(0).strip()); q = q.replace(m.group(0), " ")
    elif m := ONE.search(q):
        v, amb = _resolve(_num(m.group("n")), _mult(m.group("u")), m.group("u"), ref_median_toman)
        cmp_, tail = (m.group("cmp") or ""), m.group(0)
        if re.fullmatch(MIN_W, cmp_) or "به بالا" in tail: out.min_toman = int(v)
        elif re.fullmatch(APX_W, cmp_) or (m.group("u") or "").endswith("ی") and not cmp_:
            out.min_toman, out.max_toman = int(v * 0.8), int(v * 1.2)        # 'حدود ۴۰ میلیون', '۱۰ میلیونی'
        else: out.max_toman = int(v)                                          # زیر / تا / حداکثر / bare
        out.ambiguous_unit = amb; out.matched.append(tail.strip()); q = q.replace(tail, " ")
    elif m := CMP_ONLY.search(q):                                             # 'گوشی زیر 20' (no unit)
        v, _ = _resolve(float(m.group("n")), None, None, ref_median_toman)
        if m.group("cmp") in ("بالای", "بیشتر از", "حداقل"): out.min_toman = int(v)
        else: out.max_toman = int(v)
        out.ambiguous_unit = True; out.matched.append(m.group(0)); q = q.replace(m.group(0), " ")
    if CHEAP.search(q): out.sort = "price_asc"; q = CHEAP.sub(" ", q)
    elif PRICEY.search(q): out.sort = "price_desc"; q = PRICEY.sub(" ", q)
    out.rest = re.sub(r"\s+", " ", q).strip()
    return out
```

Test run. The ref median is 70.8M for phone-like queries and 4.3M for headset-like ones. All 25 cases came out as intended:

```text
'گوشی سامسونگ زیر ۲۰ میلیون'        -> max=20000000                         rest='گوشی سامسونگ'
'گوشی سامسونگ زیر ۲۰ میلیون تومان'  -> max=20000000                         rest='گوشی سامسونگ'
'هندزفری تا ۵ تومن'                 -> max=5000000   amb=True               rest='هندزفری'
'گوشی تا ۵۰ تومن'                   -> max=50000000  amb=True               rest='گوشی'
'بین ۱۰ تا ۱۵ میلیون'               -> min=10000000 max=15000000            rest=''
'گوشی بین ۱۰ و ۱۵ میلیون'           -> min=10000000 max=15000000            rest='گوشی'
'لپ تاپ از ۵۰۰ هزار تا ۲ میلیون'    -> min=500000 max=2000000               rest='لپ تاپ'
'هندزفری بلوتوث ارزون'              -> sort=price_asc                       rest='هندزفری بلوتوث'
'آیفون ۱۳ ۱۲۸'                      -> (no price)                           rest='ایفون 13 128'
'گوشی زیر 20'                       -> max=20000000  amb=True               rest='گوشی'
'قاب گوشی زیر ۲۰۰ هزار'             -> max=200000                           rest='قاب گوشی'
'یخچال حدود ۴۰ میلیون'              -> min=32000000 max=48000000            rest='یخچال'
'گوشی ۱۰ میلیونی'                   -> min=8000000 max=12000000             rest='گوشی'
'گوشی بالای ۳۰ میلیون'              -> min=30000000                         rest='گوشی'
'گوشی یک و نیم میلیون'              -> max=1500000                          rest='گوشی'
'هدفون زیر پانصد هزار تومن'         -> max=500000                           rest='هدفون'
'ساعت هوشمند ۲/۵ میلیون به بالا'    -> min=2500000                          rest='ساعت هوشمند'
'مانیتور زیر ۲۷ اینچ'               -> (no price)                           rest='مانیتور زیر 27 اینچ'
'گوشی زیر ۲۰۰۰۰۰۰۰ ریال'            -> max=2000000                          rest='گوشی'
'گوشی زیر 20,000,000 تومان'         -> max=20000000                         rest='گوشی'
'گرونترین گوشی سامسونگ'             -> sort=price_desc                      rest='گوشی سامسونگ'
'پاوربانک ۲۰ هزار میلی آمپر'        -> (no price)                           rest='پاوربانک 20 هزار میلی امپر'
'دوربین ۲۰ مگاپیکسل زیر ۵ میلیون'   -> max=5000000                          rest='دوربین 20 مگاپیکسل'
'پاور بانک زیر ۸۰۰ تومن'            -> max=800000    amb=True               rest='پاور بانک'
'۲ تا هندزفری ارزون'                -> sort=price_asc                       rest='2 تا هندزفری'   (add 'تا' to stopwords)
```

Order of operations: `parse_price` (on raw query) → detect category from `rest` → re-run with that category's median if the unit was ambiguous → FTS on `rest` → filter by `MIN(price_toman)` over offers.

## 4. Semantic search (embeddings)

| model | params / dim | disk | Persian evidence (FaMTEB avg / retrieval) |
|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | 118M / 384 | ~470 MB | 46.62 / 23.08 |
| LaBSE | 471M / 768 | ~1.8 GB | 48.47 / 21.20 |
| multilingual-e5-small | 118M / 384 | 471 MB (measured, local HF cache) | not in table (expect below e5-base) |
| multilingual-e5-base | 278M / 768 | ~1.1 GB | 57.03 / 41.20 |
| multilingual-e5-large | 560M / 1024 | ~2.2 GB | 58.44 / 42.98 |
| BGE-M3 | 568M / 1024 | ~2.3 GB | 59.10 / 43.38 |
| Jina-embeddings-v3 | 570M / 1024 | — | 59.28 / 43.51 |
| OpenAI text-embedding-3-small | API / 1536 | — | not in FaMTEB. $0.02 / 1M tokens ([OpenAI](https://developers.openai.com/api/docs/models/text-embedding-3-small)) |

FaMTEB numbers: [arXiv 2502.11571](https://arxiv.org/html/2502.11571v1), Table 2 (EMNLP Findings 2025). Param and dimension figures come from the models' HF cards and are not re-verified here. The Hakim paper argues that multilingual models are sub-optimal for Persian ([arXiv 2505.08435](https://arxiv.org/pdf/2505.08435)).

**Own benchmark** (`emb_bench.py`): multilingual-e5-small, CPU, `torch.set_num_threads(4)` to imitate a 4-vCPU VPS, 30k random titles, `"passage: "` / `"query: "` prefixes.

```text
encoded 30000 titles in 105.8s = 283 titles/s; dim=384
extrapolated 225,903 titles: 13.3 min; matrix fp32 331 MiB (int8 ≈ 83 MiB)
query: ~10-15 ms incl. query encoding, brute-force cosine over 30k
'گوشی ارزون سامسونگ'      -> کلگی شارژر سامسونگ; فیلتر دوار جاروبرقی سامسونگ; شارژر اصلی سامسونگ   (bad)
'هندزفری بی سیم'          -> هندزفری بی سیم سامسونگ Buds FE; مگنت بی سیم; هندزفری با سیم ...      (mixed; با سیم = wired!)
'iphone 13'               -> دوربین اصلی iphone 13; گلس ایفون 13 پرومکس; باتری ... iPhone 13      (ok, matches FTS)
'شارژر فندکی ماشین'       -> شارژر فندکی خودرو راموکس ...; شارژر فندکی HAMR; فیش فندکی خودرو       (good: ماشین≈خودرو synonym)
'لپ تاپ برای برنامه نویسی'-> سیم تعمیری لپ‌تاپ; طراحی سایت فروش لپ تاپ; نصب درایور لپ تاپ          (bad)
'ساعت هوشمند'             -> ساعت هوشمند گرین لاین ...; ... شیائومی ...; ... هیمی ...              (good)
```

The tokenizer gives 16.2 e5 tokens per title on average (40 chars), and 28.7 cl100k tokens. A full OpenAI embedding pass is about 6.5M tokens, roughly $0.13. Cost is not the issue. The issues are network latency per query and API availability from Iran-hosted servers. Sanctions-related access is an open question.

**VPS sizing (small VPS, 2–4 vCPU / 2–4 GB RAM):** e5-small at inference needs about 0.5 GB for the model (torch adds more; ONNX via the already-installed `fastembed`/`onnxruntime` is lighter) plus 331 MiB of vectors. Precompute embeddings offline and ship the `.npy` file. Brute-force cosine over 226k×384 is roughly 10–30 ms, or use `sqlite-vec` (installed, v0.1.9). This is feasible, but it roughly doubles RAM use, and on short product titles it mostly helps synonyms (ماشین/خودرو) and hurts precision (با سیم vs بی سیم).

**Recommendation: FTS-only for v1.** Get recall from normalization, aliases and a typo corrector, and precision from category boost and price filter. If time allows, add e5-small (or e5-base) as a **re-ranker over the FTS top-200** or as a fallback when FTS returns fewer than 5 hits. Do not use it as the primary retriever.

## 5. Typos and synonyms

### 5.1 Typo correction with a trigram index over the vocabulary (`fts_bench2.py`)

* `CREATE VIRTUAL TABLE v USING fts5vocab(main, p, row)` gives 45,700 distinct non-numeric terms (read in 87 ms).
* Put them into an in-memory `fts5(term, tokenize='trigram')`. For an unknown query token, OR-query its trigrams, then score each candidate by (trigram Jaccard + difflib ratio)/2 × (1 + 0.05·log(1+df)), allowing at most ±2 length difference.

```text
correct(سامسنگ)   -> سامسونگ 0.965, سامسنوگ, سامسون   [1.3 ms]
correct(هندزفیری) -> هندزفری 0.978, هندفری, هندایی    [1.6 ms]
correct(بلوتوت)   -> بلوتوث 0.862, بلوتوثی            [2.4 ms]
correct(کاسیوو)   -> کاسیو 0.964                     [2.7 ms]
correct(یخچل)     -> یخچال 0.767                     [0.1 ms]
correct(شیامی)/(ایفن)/(هدفن) -> unchanged: each exists in the vocab (rare variants)
```

Only run correction when a token has df=0, or when the AND query returns 0 hits. Rare-but-present variants such as شیامی (15 titles) need the alias table instead of the typo corrector. One option is to auto-alias a low-df term to a high-df term at edit distance 1–2 that shares a prefix, for example شیامی/شیاومی→شیائومی. Review those by hand.

### 5.2 Brand alias table (fa ↔ Latin), mined from the dataset (`brand_alias.py`, 2.8 s)

Method: for each product with `brand_name`, collect the Latin tokens from these spec values:

* `برند` and `شرکت سازنده`,
* the first Latin word of `نام محصول`,
* the first Latin word of the title.

Then count co-occurrence per Persian brand, drop tokens that contain digits or are generic (pro, max, usb, …), and require that the first letter be phonetically plausible (ب→b/p, ک→k/c/q, …). Keep pairs with count ≥ 5 that cover ≥ 5% of the brand's products.

Result: **370 of 2,243 Persian brands** got an alias. Top of the list:

```text
سامسونگ→samsung(558/3351)  اپل→iphone(491), apple(186)  داهوا→dahua  سونی→sony  اچ پی→hp  کانن→canon
هایک ویژن→hikvision  هیوندای→hyundai  فیلیپس→philips  کاسیو→casio  بوش→bosch  انکر→anker  پاناسونیک→panasonic
چری→chery  اتونیکس→autonics  وسترن دیجیتال→western, wd  لگرند→legrand  نوکیا→nokia  مک دودو→mcdodo
لنوو→lenovo (+noise 'loq')  ایسوس→asus  باسیوس→baseus  جی بی ال→jbl  سیکو→seiko  هواوی→huawei  نایکی→nike
```

Known gaps and noise: شیائومی→xiaomi was missed (my first-letter table maps ش only to `s`; add `x`). Sub-brand and model words leak in (loq, expertbook, ultrastar). ⇒ Hand-review the top ~50 brands and add product-line aliases manually: آیفون↔iphone, گلکسی↔galaxy, ردمی↔redmi, ایرپاد↔airpods, پوکو↔poco, مک بوک↔macbook, آیپد↔ipad, پلی استیشن↔playstation/ps5. Also add a few generic synonyms that are common in queries: ماشین↔خودرو, هندزفری↔هدفون↔هدست (the category is the same), گوشی↔موبایل↔تلفن همراه, لپ تاپ↔لپتاپ↔نوت بوک, شارژر↔شارژ. The `specs` key `شرکت سازنده` itself is sparse. `برند` appears 41,329 times and is the main source.

Use: at **index time**, write the aliases of the product's brand into a `brand_aliases` FTS column. At **query time**, expand a recognized token into `("ایفون" OR "iphone")`. Expansion cost was 0.4–0.8 ms per query in the test.

## Unverified / open questions

* The colloquial meaning of a bare "X تومن" (thousand vs million) has no authoritative source. The category-median heuristic is my own design, and real users should be asked through the `ambiguous_unit` confirmation.
* The version that introduced `contentless_unindexed` (3.47.0?) was not checked against the official release notes. The VPS's system SQLite version is unknown: run `python -c "import sqlite3;print(sqlite3.sqlite_version)"` there. Ubuntu 22.04 ships 3.37.x, which is fine for trigram but not for contentless_unindexed.
* Ranking quality was judged by eye on about 12 queries. There is no labelled relevance set, and building 30–50 query→expected-product pairs would let us tune the bm25 weights and boosts.
* The ~2 ms tail latency was measured on a fast desktop. On a 2-vCPU VPS, expect 2–5× slower, which is still well under 50 ms.
* Embedding quality for e5-base, BGE-M3 and OpenAI was not measured on this data, only e5-small. FaMTEB does not cover e-commerce titles. OpenAI API reachability from the deployment location is unknown.
* hazm 0.10.0 (the version pip picks for Python 3.14) was not installed or tested, so its dependency tree on 3.14 is unknown.
* The redenomination (new rial = 10,000 old rials, voted Oct 2025) may change how users quote prices during the 3-year transition. Its current status was not verified.
* `price_toman` has extreme outliers (1 to 7.3e17), so filtering and median logic must clip them. Dataset quirks are covered in `01-dataset.md`.

## Sources

* SQLite FTS5 docs — https://www.sqlite.org/fts5.html
* Trigram tokenizer in SQLite 3.34.0 — https://github.com/simonw/sqlite-fts5-trigram ; https://sqlite.org/forum/forumpost/76b444bebe?t=c ; trigram remove_diacritics ≥3.45: https://github.com/groue/GRDB.swift/pull/1655
* contentless_unindexed in 3.47.0 (secondary) — https://yunqa.de/delphi/news/2024-11-08_sqlite3
* hazm — https://pypi.org/project/hazm ; https://github.com/roshan-research/hazm/blob/master/hazm/normalizer.py
* Parsivar — https://github.com/ICTRC/Parsivar ; https://aclanthology.org/L18-1179/
* persian-tools — https://github.com/persian-tools/py-persian-tools ; persiantools — https://github.com/majiidd/persiantools
* Iranian rial / toman / redenomination — https://en.wikipedia.org/wiki/Iranian_rial
* FaMTEB — https://arxiv.org/html/2502.11571v1 ; Hakim — https://arxiv.org/pdf/2505.08435
* OpenAI text-embedding-3-small pricing — https://developers.openai.com/api/docs/models/text-embedding-3-small
