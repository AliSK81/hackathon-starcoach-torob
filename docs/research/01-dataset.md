# 01 — Torob dataset deep-dive

Scope: `data/torob-dataset/{shops,products,offers}.csv`, profiled 2026-10-22 against `docs/requirements.md`.
All numbers come from Python 3 scripts now kept in `docs/research/scripts/01-dataset/`
(cited below as `scratchpad/<file>`; `load.py` reads the CSVs from `data/torob-dataset` or `$TOROB_DATA`).
Every script uses `scratchpad/load.py`, which reads the CSVs with `csv.field_size_limit(10**9)`, caches them as pickles, and treats the literal string `'null'` as missing.
Run them with `PYTHONIOENCODING=utf-8 python <script>`.

## TL;DR

| # | Finding | Evidence |
|---|---|---|
| 1 | Joins are clean: 0 orphan offers, no duplicate IDs. **2,684 of 6,476 shops (41%) have no offers**; only 3,792 shops sell anything. | `p1_joins.py` |
| 2 | The 300 cap applies to **distinct products per shop** (max = 300; 461 shops are exactly at it). Offers per shop go up to 1,346 because a (shop, product) pair can repeat as variants: 9,557 pairs, 20,315 extra rows. | `p1_joins.py`, `p11_misc.py` |
| 3 | 84% of products (190,649) have exactly one seller, so seller comparison works for about 35k products. Electronics in the Jomhouri/Alaeddin cluster has 20–60 sellers per product. | `p1b_dups.py` |
| 4 | Address parsing works: passage 62.6%, floor 65.2%, unit 35.0%, plaque 77.4%. 49% of shops say «پاساژ». | `p2_addr.py` |
| 5 | 79% of shops are within 1 km of one downtown point (Jomhouri / Lalehzar / Saadi). `location_label` is a coordinate-derived neighbourhood (mahalleh) name with 31 values, not a passage. | `p3_geo.py`, `p3b_knn.py` |
| 6 | `weekly_hours`: 2,003 shops empty. `00:00–00:00` is a padding or placeholder shift, not "24h". There are no overnight shifts. Friday is closed for 3,473 shops. | `p4_hours.py`, `p4b_hours.py` |
| 7 | Prices are in Toman, but there are junk values. 635 offers at **1 Toman** mean "call for price". 126 offers are ≥ 1e12 (max 7.3e17). 188 offers sit at about 10× the product median, probably Rial typed into the Toman field. 15,083 prices are null. | `p5_price.py`, `p5b_spread.py`, `p9c_quirks.py` |
| 8 | Snapshot = **2026-10-13 00:02 UTC**. 22.6% of prices changed in its last 7 days and 57.3% in the last 30 days. | `p6_ts.py` |
| 9 | Payment: only 266 shops list options. Providers: ترب‌پی 190, اسنپ‌پی 89, دیجی پی 61, تارا 37, ازکی‌وام 5, plus 3 shop-named oddities. **No Kalabarg anywhere.** Fast delivery is set for 1,601 shops (1,168 true). | `p8_pay.py` |
| 10 | Product images: always `image.torob.com`, 0–2 per product, HTTP 200, `CORS: *`, cached for 1 year. | `p10_img.py` |

---

## 1. Join integrity & cardinalities

`scratchpad/p1_joins.py`, `p1b_dups.py`, `p11_misc.py`

| Check | Result |
|---|---|
| Duplicate `shop_id` / `product_id` / `offer_id` | 0 / 0 / 0 |
| offers → products orphans | **0** |
| offers → shops orphans | **0** |
| Products with no offer | 0 (all 225,903 are used) |
| Shops with zero offers | **2,684** (3,792 shops have offers) |
| Duplicate (shop, product) pairs | 9,557 groups, 20,315 extra rows, largest group 105 |
| Max distinct products per shop | **300**; 461 shops have exactly 300, 548 have ≥ 250 |

The duplicate (shop, product) rows are **variants**: different colour or size in `seller_title`, often at a different price. Example: one shop has 105 «مبل تخت خوابشو مدل کاپری» offers (خردلی/165 سانت 34,947,000; نارنجی/125 سانت 26,037,000; …). Some are matching errors instead: two Schneider contactors LC1D95 and LC1D50 mapped to the same product. Only 4,202 of the groups have one identical price, and only 918 one identical seller title.
→ For UX: group by (shop, product) and show "from X Toman · N variants".

Offers per shop (all 6,476 shops):

| offers | 0 | 1 | 2–5 | 6–20 | 21–50 | 51–100 | 101–200 | 201–299 | 300 | >300 |
|---|---|---|---|---|---|---|---|---|---|---|
| shops | 2,684 | 367 | 593 | 767 | 509 | 449 | 403 | 212 | 135 | 357 |

Median 2, mean 51.2, max 1,346.

Distinct shops per product: 1 → 190,649; 2 → 19,036; 3–5 → 11,743; 6–10 → 3,523; 11–20 → 833; ≥ 21 → 119 (max 59).
The most-sold product is «شارژر اپل توان 20 وات سه پین» with 59 shops.
129,009 offers belong to products that have ≥ 2 sellers.

Shops with 0 offers mostly have only `category_names` (887 shops) or nothing at all (1,797 shops).
This is the requirement's "business whose activity category alone is known". Show these as "sells this kind of product, stock unknown", never as "has it".

## 2. Address parsing

`scratchpad/addr.py` (parser), `p2_addr.py` (rates and samples → `out_p2.txt`), `p2b_alaeddin.py`

Normalize the address before applying any regex:

- ي→ی, ك→ک
- ZWNJ → space
- Persian and Arabic-Indic digits → ASCII
- پاساز→پاساژ, «هم کف»→همکف, «زیر زمین»→زیرزمین, «طبقه ی»→طبقه

Raw keyword presence in normalized addresses (n = 6,476):

| keyword | hits | keyword | hits |
|---|---|---|---|
| پاساژ | 3,184 (49.2%) | طبقه | 4,224 (65.2%) |
| مجتمع | 467 (7.2%) | همکف | 1,041 (16.1%) |
| بازار | 186 (2.9%) | زیرهمکف | 178 (2.7%) |
| ساختمان | 362 (5.6%) | زیرزمین | 45 (0.7%) |
| سرای/سرا | 42 (0.6%) | منفی | 393 (6.1%) |
| مرکز خرید | 40 (0.6%) | واحد | 2,380 (36.8%) |
| برج | 16 (0.2%) | پلاک | 5,119 (79.0%) |
| مال | 27 (0.4%) | مغازه / غرفه / بلوک | 3 / 10 / 9 |
| تیمچه | 0 | کوچه / نبش | 1,997 / 566 |

Proposed regexes (all are in `addr.py`):

```python
KW_P = r"(?:پاساژ|مجتمع(?:\s+تجاری)?|بازار(?:چه)?|سرای|سرا|تیمچه|مرکز\s+خرید|ساختمان|برج|مال)"
RE_PASSAGE = KW_P + r"\s+(?P<name>[^،,\-\(\)]+?)(?=\s*(?:[،,\-\(\)]|طبقه|واحد|پلاک|مغازه|بلوک|$))"
#   skip a match preceded by بعد از|قبل از|روبروی|جنب|نرسیده به|کنار|پشت … (landmarks)
#   when several match, prefer پاساژ/مجتمع/سرای/مرکز خرید > بازار/مال > ساختمان/برج
RE_FLOOR = r"(?:طبقه|طبقات)\s*:?\s*(?P<val>(?:منفی|-|مثبت|\+)?\s*\d+|همکف|زیرهمکف|زیرزمین|زیرین|منفی یک|اول|دوم|سوم|…|یک|دو|سه|…)"
RE_FLOOR_ALT = r"(?<!\S)(همکف|زیرهمکف|زیرزمین)(?!\S)"     # floor word without «طبقه»
RE_UNIT = r"(?P<kw>واحد|پلاک|مغازه|غرفه)\s*:?\s*(?:شماره\s*)?(?P<val>\d+(?:[./]\d+)?\s*[A-Za-zآ-ی]?(?:\s*و\s*\d+)?)"
# floor value: همکف=0, زیرهمکف/زیرزمین/زیرین/منفی یک/-1 = -1, اول/یک/1 = 1, …
```

Hit rates after the fixes:

| field | parsed |
|---|---|
| passage / building | 4,056 (62.6%) |
| floor text | 4,224 (65.2%) |
| floor numeric value | 4,218 (65.1%) |
| unit (واحد/مغازه/غرفه) | 2,269 (35.0%) |
| plaque (پلاک) | 5,013 (77.4%) |
| unit or plaque | 5,881 (90.8%) |
| passage + floor + (unit or plaque) | 3,186 (49.2%) |

Among shops that have offers, 65% have a passage and 68% a floor (`p11_misc.py`).

Floor value distribution:

| floor | count |
|---|---|
| −4 | 2 |
| −2 | 35 |
| −1 | 573 |
| 0 | 825 |
| 1 | 1,090 |
| 2 | 709 |
| 3 | 426 |
| 4 | 248 |
| 5 | 145 |
| 6 | 87 |
| 7–14 | 85 |
| 111 | 1 (typo) |

There are 21 «طبقه» mentions the parser still misses: «طبقه منفی (زیرزمین)», «طبقهB1», «طبقه ـ1» (tatweel), «طبقه سون» (typo), «طبقه آخر», «طبقه روی همکف», «طبقه ، » (empty), «طبقه طلا و جواهر ( 2+)». Another 6 give «طبقه بالا(ی همکف)», which has no number.

Passage names need canonicalization. There are 579 distinct raw names. Alaeddin alone is spelled 9 ways across 625 addresses: علاالدین 380, علاءالدین 159, علائدین 58, علالدین 13, علادین 5, علایدین 4, علاادین 3, علاعدین 2, علاءدین 1. Map them with `علا\S{0,3}دین → علاءالدین` and also normalize the suffix numbers 1/2/3/یک/دو.
Unnumbered «علاءالدین» (277) is a separate building from «علاءالدین 2» (139), which is about 413 m away.
Other duplicate pairs to merge: چارسو/چهارسو, فراز/فراز لاله زار, تجارت جهانی/تجارت جهانی فردوسی, 110/110 فردوسی.

Top passages by shop count:

| passage | shops |
|---|---|
| علاءالدین | 277 |
| بوشهری | 177 |
| چارسو | 149 |
| علاءالدین 2 | 139 |
| اتحادیه | 100 |
| امجد | 95 |
| کیان | 75 |
| فراز | 74 |
| تجارت جهانی | 65 |
| یگانه | 65 |
| سبحان | 60 |
| ایرانیان | 59 |
| نادری | 57 |
| آلومینیوم | 57 |
| حافظ | 55 |
| صدقی نژاد | 52 |
| … | |
| موبایل ایران | 40 |
| پلاسکو | 30 |
| اپال | 34 |

### 15 sample parses (incl. failures)

| # | raw address (abridged) | parse |
|---|---|---|
| 1 | …میدان فردوسی، مجتمع تجارت جهانی فردوسی، طبقه ۵، واحد ۵۱۴ | passage=تجارت جهانی فردوسی, floor=5, unit=514 ✅ |
| 2 | خیابان جمهوری، بعد از پل حافظ، پاساژ امجد، طبقه اول، پلاك ١٠ | passage=امجد, floor=1, plaque=10 ✅ (Arabic ك and ١٠ handled) |
| 3 | سعدی جنوبی، کوچه شاهچراغی، پلاک ۴ | plaque=4 (street shop, no passage) ✅ |
| 4 | خیابان ولیعصر، نرسیده به سه راه جمهوری، کوچه رجب بیگی، پلاک 34 | plaque=34 ✅ |
| 5 | …بن بست انوشیروانی،ساختمان حمل و نقل،پلاک2،واحد2 | passage=حمل و نقل (ساختمان), unit=2, plaque=2 ✅ |
| 6 | امام خمینی، لاله زار، …، پاساژ جهان الکتریک، پلاک ۱۶ | passage=جهان الکتریک, plaque=16 ✅ |
| 7 | خیابان جمهوری اسلامی، رم، …، پلاک ۶، طبقه ۱، واحد ۱ | floor=1, unit=1, plaque=6 ✅ |
| 8 | …نبش کوچه شیده، پلاک ۱۰۷، | plaque=107 ✅ |
| 9 | خیابان جمهوری، نرسیده به پل حافظ، پاساژ توکل، طبقه -۱، پلاک ۱۰، واحد ۱۰ | passage=توکل, floor=−1, unit=10, plaque=10 ✅ |
| 10 | …کوچه تیمساری، پلاك٦ | plaque=6 ✅ |
| 11 | …پاساژ نادری، طبقه بالای همکف (اول)، واحد ۱۰ | passage=نادری, floor_raw=«طبقه بالا», **floor=None** ❌ (should be 1) |
| 12 | …پاساژ کریستال، طبقه منفی (زیرزمین)، پلاک ۵ | passage=کریستال, **floor missed** ❌ (should be −1) |
| 13 | خیابان فردوسی، کوچه باربد، پاساژ سرای لاله زار، پلاک ۱ | passage=«سرای لاله زار» ✅ |
| 14 | خیابان فردوسی، خیابان باربد، سرای لاله زار، طبقه اول، پلاک ۶۹ | passage=«لاله زار» (kw سرای) ⚠️ same building as #13 under a different name; needs canonicalization |
| 15 | خیابان حافظ، **بعد از ساختمان بورس**، …، بازار موبایل ایران، طبقه زیرین، واحد 132 | passage=موبایل ایران, floor=−1, unit=132 ✅. The landmark guard rejected «ساختمان بورس»; before that fix the parser returned «بورس». |

Recommendation: parse once offline and store `passage_canon`, `floor`, `unit`, `plaque`. Show the raw address alongside the parse. Let the LLM fall back on the ~10% of messy addresses.

## 3. Geography

`scratchpad/p3_geo.py`, `p3b_knn.py`, `p11_misc.py`

- Coordinate ranges: lat 35.6403–35.8126, lon 51.3053–51.5093. All 6,476 points are inside the Tehran bounding box and none are null.
- Precision: mostly 13–15 decimals, so these are raw pins. 294 points have only 6–7 decimals.
- Identical coordinates are rare: 6,467 distinct points, only 7 coordinates are shared, by 16 shops in total (max 4, Passage Kian).
  But shops are densely packed:
  - Nearest-neighbour distance: median 4.1 m, p10 0.9 m, p90 25 m.
  - 706 shops have another shop within 1 m; 3,644 within 5 m.
  - Rounded to 4 decimals (~11 m): 209 cells hold ≥ 5 shops, 1,775 shops in total.

  Conclusion: shops in the same building have *nearly* identical pins, not identical ones. Group buildings by parsed passage plus a ~50 m radius.
- Within one passage the pins are tight: Alaeddin median 37 m to its centroid, Boushehri 15 m, Charsou 20 m, Ettehadieh 18 m.
  Outliers exist: Alaeddin max 1,262 m, Alaeddin 2 max 2,566 m. These are mis-pins or a different building with the same name.
  «ایرانیان» has a median of 562 m, so it is two different buildings.
- Concentration around the downtown centroid (35.69335, 51.4175):

  | radius | shops |
  |---|---|
  | ≤ 500 m | 625 |
  | ≤ 1 km | 5,120 (79%) |
  | ≤ 2 km | 5,580 |
  | ≤ 5 km | 5,925 |
  | max | 13.3 km |

  This matches the requirement note "selectively drawn from certain areas".
- Distances from Alaeddin (1) to other passages, using median pins:

  | passage | distance |
  |---|---|
  | Charsou | 75 m |
  | Alaeddin 2 | 413 m |
  | Mobile Iran | 461 m |
  | Plasco | 843 m |
  | Tejarat Jahani Ferdowsi | 963 m |
  | Boushehri | 1,160 m |
  | Kian | 1,421 m |
  | Opal | 10.6 km |
  | Kourosh Mall | 10.0 km |

  Walking-route suggestions make sense inside the downtown cluster.

**`location_label`** has 31 values, plus 1 empty.

| label | shops | median m to centroid | max m |
|---|---|---|---|
| فردوسی | 3,282 | 549 | 1,079 |
| شیخ هادی | 1,587 | 245 | 812 |
| بهارستان | 616 | 216 | 847 |
| آسمان | 151 | 391 | 967 |
| باغ فیض | 107 | 261 | 633 |
| ایرانشهر | 99 | 382 | 1,107 |
| سنائی | 96 | 352 | 595 |
| سهروردی | 82 | 298 | 548 |
| تجریش | 76 | 164 | 598 |
| جنت آباد جنوبی | 68 | 252 | 834 |
| … 21 more with 1–54 shops | | | |

It is a **neighbourhood (mahalleh) name derived from coordinates**:

- Labels are spatially coherent: 98.4% of shops share the label of their nearest neighbour (6,373 / 6,476).
- Each label spans ≤ ~1 km.
- One passage can straddle two labels. Alaeddin's 283 shops split 260 «شیخ هادی» and 23 «فردوسی», which fits a polygon lookup on the pin rather than an address field.
- The label appears as text inside the address for only 1,076 shops.
- Names such as باغ فیض, جنت آباد جنوبی, کیانشهر شمالی, سازمان برنامه شمالی match Tehran municipality neighbourhood names (not verified against an official list).

Use it as the "area" filter chip («محله»). Use the parsed passage as the finer level.

## 4. Weekly hours

`scratchpad/p4_hours.py`, `p4b_hours.py`, `p4c.py`, `p4d_tz.py`

- 2,003 shops have `{}`, meaning unknown. The other 4,473 always have all 7 keys `sat…fri`.
  Among the 3,792 shops with offers, 3,011 (79%) have hours. 3,000 of them have at least one `declared` day.
- Day status counts: declared 27,270, closed 4,006, unsupported 35.
- Times are always `HH:MM:SS`.
- **Shift arrays are padded to 2 entries with `00:00:00–00:00:00`.**
  After dropping that placeholder, declared days have 1 real shift (26,803) or 2 (467).
  No declared day consists only of the placeholder.
  `closed` days have only placeholders. There are 0 closed days with real times.
- Real split shifts look like `09:00–13:00 + 14:30–20:00` (13) or `09:00–19:00 + 19:30–23:30` (25). 48 days repeat the same shift twice, so dedupe them.
- **Overnight (end < start): 0. Shifts ending at 00:00: 0.** The code should still handle wrap-around.
- "24h" is written as `00:00–23:59` (236 days) or `00:00–23:45` (27). It is never `00:00–00:00`.
- Junk durations: `00:00–00:00:01` (61 days) and 15-minute shifts like `21:00–21:15`. Treat a shift under ~30 minutes as unknown.
- `unsupported` (35 days) has start == end (e.g. `08:00–08:00`). Treat it as unknown.
- Common opening times: 09:00 (10,599), 10:00 (6,987), 09:30 (3,519). Common closing times: 18:00 (5,724), 19:00 (3,719), 20:00 (2,785).
- Weekend pattern: Friday is closed for 3,473 shops and declared for 998. Thursday is declared for 4,270 (often shorter). This matches the Iranian week.

**Time zone.** Use `Asia/Tehran`, UTC+03:30 with no DST since 21 Sep 2022.

- Wikipedia "Iran Standard Time": "On 21 September 2022, Iran abolished DST for the second time and now observes standard time year-round."
- Python tzdata 2026b agrees: 2022-07-01 → +04:30 (DST); 2022-12-01, 2023-07-01, 2026-07-01, 2026-10-22 → +03:30.

**Proposed `is_open_at`** returns three values: True, False, or None (unknown).

```python
DAY = ["mon","tue","wed","thu","fri","sat","sun"]          # index = datetime.weekday()
def real_shifts(day):
    out = []
    for s in day["shifts"]:
        a, b = s["start_time"], s["end_time"]
        if a == b: continue                                  # 00:00-00:00 padding or unsupported junk
        if (to_min(b) - to_min(a)) % 1440 < 30: continue     # 00:00-00:00:01, 15-min noise
        if b in ("23:59:00", "23:45:00"): b = "24:00:00"
        if (a, b) not in out: out.append((a, b))
    return out
def is_open_at(wh, dt):                                      # dt aware, converted to Asia/Tehran
    if not wh: return None
    t = dt.astimezone(ZoneInfo("Asia/Tehran"))
    today, yday = wh[DAY[t.weekday()]], wh[DAY[(t.weekday()-1) % 7]]
    if today["status"] == "unsupported": return None
    hm = t.strftime("%H:%M:%S")
    # previous day's overnight tail (none in the current data, kept for safety)
    if yday["status"] == "declared" and any(b < a and hm < b for a, b in real_shifts(yday)): return True
    if today["status"] == "closed": return False
    shifts = real_shifts(today)
    if not shifts: return None
    return any((a <= hm < b) if a < b else (hm >= a) for a, b in shifts)
```

The UI should also show "closes in 40 min" or "opens Saturday 09:00". Mark these hours as declared by the shop, not confirmed. Official holidays are not in the data.

## 5. Prices

`scratchpad/p5_price.py`, `p5b_spread.py`, `p9c_quirks.py`, `p12.py`

- 316,423 prices are numeric and 15,083 are null. All numeric values are integers with no decimals and none are 0.
- Distribution (Toman):

  | stat | value |
  |---|---|
  | min | 1 |
  | p1 | 3,000 |
  | p5 | 85,000 |
  | p25 | 901,000 |
  | median | 3,640,000 |
  | p75 | 14,300,000 |
  | p95 | 108,630,000 |
  | p99 | 430,000,000 |
  | p99.9 | 3.8e9 |
  | max | 7.34e17 |

- Junk tails:
  - ≤ 1: 635 offers from 16 shops. These are placeholders; one description reads «جهت دریافت قیمت تماس حاصل فرمایید».
  - ≤ 100: 740.
  - ≥ 1e10: 211. ≥ 1e12: 126, mostly generators at about 2e13, which is digit garbage.
  - ≥ 1e15: 13. Eight of these are MacBooks and Surface laptops at 3.7–7.3e17.
  - Real low prices exist: SMD resistors and diodes cost 420–840 Toman.
  - Real high prices exist: 1e9–1e10 is genuine for industrial gear (Cummins 110 kVA genset 1.34e9; Siemens CPU 416 3.4e9; a 900 kVA genset 1.65e10).
- **Recommended cutoffs:**
  - Treat `price ≤ 10` as "call for price".
  - Hide or flag `price > 1e10` as invalid.
  - Within a product with ≥ 3 sellers, flag a price outside `[median/3, 3×median]` as "suspicious". That flags 2,223 of 75,006 offers.
  - The Rial-in-Toman error is visible: 188 offers are 8–12× the product median and 73 are 1/12–1/8 of it. Example: JBL PartyBox 520 median 135.5M, max 1.22B.
- **Spread across shops** (per-shop minimum, prices in 1e3–1e10):
  - 33,090 products have ≥ 2 priced shops; 15,057 have ≥ 3 and 5,665 have ≥ 5.
  - max/min ratio: p25 1.11, median 1.36, p75 1.90, p90 3.44, p99 95.7.
  - 1,940 products have identical prices everywhere; 7,373 have ratio > 2.
  - Large ratios usually mean unit or packaging differences, not real price spread. «سیم افشان افشار نژاد 2.5» ranges from 39,000 (per metre) to 5.85M (median, a 100 m coil) to 39.2M.
  - **There is no price-unit field.** The requirement mentions a "price unit", but the dataset doesn't have one; the unit only appears inside free-text descriptions («فروش این محصول به صورت حلقه 100 متری», «قیمت بر اساس خرید کارتنی»).
- **Null price** (15,083 offers):
  - Concentrated in 157 shops, and 139 shops have *only* null prices. The top shop has 951.
  - Mostly industrial B2B categories: pumps 860, sludge pumps 598, generators 542, drives 454, CCTV 400, breakers 376.
  - 1,503 of them have a description (e.g. «حداقل سفارش ۱۰ کارتن»).
  - Interpretation: "price on inquiry" or wholesale. Show «قیمت: استعلام تلفنی».
  - 769 offers have a null timestamp, 11 of them also with a null price.
- **Is it Toman?** The column name `price_toman` and the README both say so, and values are plausible as Toman:

  | product | sellers | median price (Toman) |
  |---|---|---|
  | Galaxy A07 64GB | 27 | 44,000,000 |
  | Galaxy S25 FE 256GB | 33 | 195,000,000 |
  | MacBook Pro M5 1TB | 6 | 515,525,000 |

  Read as Rial, an S25 FE would cost 19.5M Toman, which is implausibly cheap. Individual sellers sometimes typed Rial (see the 10× cluster above).

## 6. `last_price_changed_at`

`scratchpad/p6_ts.py`

- Format: ISO-8601 with microseconds and `+00:00`, so it is UTC. 330,737 values are non-null and 769 are null.
- Oldest 2020-12-03, median 2026-09-21, **newest 2026-10-13 00:02:35 UTC**. Only 10 rows fall on 10-13, so the effective snapshot is the end of 2026-10-12. That fits "last week".
- Relative to the newest timestamp:

  | window | offers |
  |---|---|
  | 1 d | 14,446 (4.4%) |
  | 3 d | 38,870 (11.8%) |
  | **7 d** | **74,712 (22.6%)** |
  | 14 d | 143,510 (43.4%) |
  | **30 d** | **189,664 (57.3%)** |
  | 90 d | 256,396 (77.5%) |
  | 180 d | 309,482 (93.6%) |
  | **365 d** | **325,545 (98.4%)** |

- By year: 2020: 3, 2021: 13, 2022: 33, 2023: 314, 2024: 2,252, 2025: 7,525, 2026: 320,597. In 2026 the counts climb toward Sep (87,626) and Oct (128,845).
- There is a daily rhythm: Fri 2026-10-09 had 3,289 changes and Thu 10-08 had 7,008, against 12–16k on other days. That confirms the Iranian weekend.
- This is a *last price change* time, not a "last confirmed in stock" time. Show it as «آخرین تغییر قیمت: ۳ روز پیش» and never present it as availability. Prices unchanged for more than 90 days (22.5%) should carry a "may be outdated" badge.

## 7. Text quality

`scratchpad/p7_text.py`, `p7b_specs.py`, `p9c_quirks.py`

| field (n) | Arabic ي/ك | ZWNJ | Persian digits | Arabic-Indic digits | Latin digits | Persian+Latin digits mixed | Latin letters | no Persian letters |
|---|---|---|---|---|---|---|---|---|
| persian_title (225,903) | 2,878 | 9,115 | 39,686 | 223 | 159,899 | 17,405 | 132,906 | 1,866 |
| seller_title (331,506) | 3,976 | 11,502 | 37,604 | 356 | 250,300 | 15,150 | 206,365 | 3,191 |
| offer description (38,377 non-empty) | 307 | 3,363 | 9,772 | 112 | 13,081 | 1,690 | 9,402 | 228 |
| shop address (6,476) | 69 | 259 | 5,061 | 43 | 1,032 | 41 | 195 | 0 |
| spec values (first 50k products) | 540 | 15,800 | 11,391 | 30 | 147,898 | 1,001 | 87,057 | 83,050 |

- 68 titles use Arabic presentation forms (U+FB50–FEFF), e.g. «ﺳﻴﻢ ﺍﻟﺒﺮﺯ». Apply NFKC.
- Search must do the following:
  - normalize ي/ك → ی/ک
  - turn ZWNJ into a space, or ignore it
  - fold all digits to ASCII
  - lowercase Latin text
  - match Persian↔Latin brand aliases (سامسونگ↔Samsung)
- **There is no English title field.** About 59% of persian_titles already contain Latin model codes, and ~1,832 are ASCII-only (e.g. `6ES7134-4GB51-0AB0`). `model` is filled for only 4,056 products (1.8%), lowercase and spaced like «redmi note 8». A spec «نام محصول» with Latin text exists for 1,468 products.
- `seller_title` vs `persian_title` in a 20k sample:
  - 10,868 are identical after normalization; 870 more differ only as substrings.
  - Median similarity 1.00, p10 0.51.
  - Sellers add colour or size variants and marketing words, and sometimes describe a different item (e.g. a seller's «اسپیکر همراه با نور ستاره‌ای ساند تک پرودو» mapped to «اسپیکر بی سیم پرودو مدل Soundtec Star Light»).
  - Show `persian_title` as the canonical name and `seller_title` as "seller's wording".
- **Redacted titles:** 849 products are titled «عنوان حذف‌شده برای انتشار», with 1,017 offers, mostly relays and watches. 1,036 seller titles are also redacted. Hide these or fall back to category plus specs.
- 2 products have an empty `persian_title`. 4,138 titles are shared by more than one product_id (10,532 products). Example: «شارژر اپل توان 20 وات سه پین» exists as two products with 57 and 28 shops.
- `brand_name` is null for **168,269 of 225,903 (74.5%)**. It is Persian-script, e.g. سامسونگ 3,351, اپل 2,719, شیائومی 1,950, ام وی ام 1,464, داهوا 1,072. `category_name` is never null (3,428 leaf categories).
- `specs`: 144,599 products (64%) have specs, median 6 keys, max 258. Nearly all are in section «مشخصات کلی».
  Top keys: برند 41,329, رنگ 26,843, وزن 24,741, ابعاد 18,772, جنس بدنه, کشور سازنده, مدل.
- Spec coverage for some top categories:

  | category | products with specs | avg keys |
  |---|---|---|
  | گوشی موبایل | 96% | 37.1 |
  | هدفون | 88% | 15.9 |
  | اسپیکر | 85% | 14.4 |
  | ساعت مچی | 68% | 11.6 |
  | دوربین مدار بسته | 60% | 9.5 |
  | سیم و کابل | 63% | 4.3 |
  | سوکت و کانکتور | 46% | 1.8 |
  | کابلشو | 43% | 1.5 |

## 8. Payment options, fast delivery, contacts, warranty, missing fields

`scratchpad/p8_pay.py`, `p8b_warr.py`

**`payment_options`**: 266 shops have it (240 of them have offers). There are 385 entries, all with the keys `{provider_name, channel, min_price_toman, max_price_toman, category_names}`.

| provider | shops | in_person | unknown |
|---|---|---|---|
| ترب‌پی (TorobPay) | 190 | 50 | 140 |
| اسنپ‌پی (Snapp Pay) | 89 | 53 | 36 |
| دیجی پی (Digipay) | 61 | 45 | 16 |
| تارا (Tara) | 37 | 26 | 11 |
| ازکی‌وام (Azki Vam) | 5 | 0 | 5 |
| دکان ابزار / تجهیزات آشپزخانه حلما / جیتکس مارکت | 1 each | – | 1 each |

The last three look like shop names placed in the provider field, probably in-house installment plans.

- Channel values are only `in_person` (174) and `unknown` (211).
  `unknown` most likely means the shop declared the provider without saying whether it works in-store. It is dominated by ترب‌پی 140, which suggests TorobPay acceptance known from Torob's online side. Show it as «پذیرش ترب‌پی (نحوه: نامشخص)», and show «پرداخت حضوری» only for `in_person`.
- A common bundle: 16 shops list all four (Snapp, Tara, TorobPay, Digipay) in-person. That looks like one aggregator POS.
- `min/max_price_toman` is almost always null (357 entries) or 0/0 (28). Only 2 entries have values (Digipay min 400,000; Snapp min 200), with max 0, which presumably means "no max".
  Semantics: an installment purchase-amount range, where 0/null means not declared. In practice it is unusable.
- `category_names` within entries is non-empty only once (2 categories).
- The 300 offer descriptions mentioning اقساط/قسطی/ترب‌پی include other installment schemes («بالن - اسنپ پی - بازنشستگان تامین اجتماعی», «اقساطی با چک»). This is free text the LLM can surface, labelled "seller's description".

**`supports_fast_delivery`**: null 4,875, true 1,168, false 433. 1,090 true shops have offers. Delivery area, ETA, and fee are not present.

**Kalabarg**: «کالابرگ» or «کالا برگ» appears 0 times in every shops column, in offer descriptions, and in seller titles. **Not present.**

**Contacts**: every shop has exactly one `{channel: "phone", display_number}`, an 11-digit Persian-numeral string such as «۰۲۱۲۶۴۶۷۱۸۰». All of them are fake. There is no WhatsApp, Bale, or Telegram.
Instagram is set for 22 shops (`{"handle", "profile_url"}`) and website for 90. No shop has both, and these 112 are the real-named shops.

**Warranty**: 58,943 offers (17.8%) have a warranty object `{provider, period_months, description}`.

- `period_months` is null for 50,138. The rest are 18 (2,435), 12 (2,366), 24 (1,979), 6 (1,014), 36 (453), 60, 120, 48.
- Provider is null for 44,539. Otherwise: «شرکتی» 7,310, «تست و تحویل در حضور مشتری» 3,977, «بدون گارانتی» 1,625, پارس ارتباط افزار 292, …
- «بدون گارانتی» is an explicit *no warranty*. Don't render it as a warranty.

**Requirement fields missing from the data** (show these as "unknown" in the UI, never invent them):

| Requirement mentions | Dataset |
|---|---|
| Business type, introductory description | ❌ none (only `name` and `category_names`) |
| Store images | ❌ none |
| Torob presence history, registered licenses (e.g. Enamad) | ❌ none |
| Messenger contacts (WhatsApp, Bale) | ❌ phone only, and fake |
| English product title | ❌ no field (model 1.8%, Latin text inside titles) |
| Product description (BaseProduct) | ❌ only specs; description exists only per offer (11.6% non-empty) |
| Price unit | ❌ no field; implicitly Toman per listing (per metre vs per coil is ambiguous) |
| Confirmed availability / stock | ❌ none (an offer only means "listed") |
| Kalabarg support | ❌ none |
| Installment details (limits, terms) | ⚠️ provider name only; limits effectively empty |
| Fast-delivery details | ⚠️ boolean only, 25% coverage |
| Category hierarchy | ⚠️ leaf names only; shop lists also contain some parent names (e.g. «لوازم جانبی موبایل و تبلت») |

## 9. Category taxonomy & demo scenarios

`scratchpad/p9_cat.py`, `p9b_demo.py`

- There are 3,428 product leaf categories. All of them appear in shop `category_names`, which has 3,988 distinct values.
  The 560 extra values are parent or other names: لوازم جانبی موبایل و تبلت 194, لامپ و چراغ 121, کفش و صندل… .
- Shop `category_names`: median 2 per shop, max 363, empty for 1,797 shops.
- For shops with offers, the median share of offers whose category is in the shop's `category_names` is 1.00, and p25 is also 1.00. So `category_names` contains what the shop actually lists, plus the categories of 887 shops that list nothing.
- The data is heavy on electrical, CCTV, and mobile. Top categories by offers (offers / products / shops):

| category | offers | products | shops |
|---|---|---|---|
| سیم و کابل برق ساختمان | 7,837 | 5,274 | 274 |
| دوربین مدار بسته | 5,903 | 3,467 | 259 |
| ژنراتور و موتور برق | 3,496 | 1,790 | 133 |
| تاچ و ال سی دی گوشی و تبلت | 3,285 | 1,418 | 43 |
| چراغ پنلی و سقفی | 3,220 | 2,370 | 218 |
| پمپ خانگی و صنعتی | 3,093 | 1,732 | 151 |
| ساعت مچی عقربه‌ای و دیجیتالی | 2,903 | 2,510 | 37 |
| سوکت و کانکتور | 2,671 | 2,077 | 269 |
| کلید و فیوز مینیاتوری | 2,659 | 1,507 | 206 |
| هدفون، هدست و هندزفری | 2,602 | 1,339 | 251 |
| … گوشی موبایل | 2,122 | 814 | 134 |
| … اسپیکر و سیستم صوتی | 2,006 | 1,063 | 220 |

**Five demo scenarios.** In the table, *shops* counts distinct shops with a sane price between 1e3 and 1e10, using each shop's minimum. All of them have a newest price change on 2026-10-11 or 10-12.

| # | Scenario | Product (real title) | Shops | Min / median / max (Toman) | Where |
|---|---|---|---|---|---|
| 1 | "Galaxy S25 FE under 200M near Jomhouri, open now" | گوشی سامسونگ (ویتنام) S25 FE 5G \| حافظه 256 رم 8 گیگابایت | 33 | 184.0M / 195.0M / 223.7M | Alaeddin 7, Bozorgmehr 5, Mobile Iran 4; شیخ هادی 24, فردوسی 7 |
| 2 | "Original Apple 20W charger: compare and spot fakes" | شارژر اپل توان 20 وات سه پین | 57 (+28 under a duplicate product_id) | 480k / 3.5M / 13.8M (duplicate: 4.08M / 5.85M / 9.2M) | Alaeddin 14, Alaeddin 3 4, Mobile Iran 4 |
| 3 | "Home alarm: one floor of Alaeddin 2 has 18 sellers" | سیستم اعلام سرقت سایلکس مدل SG8 LITE | 48 | 13.4M / 15.475M / 25.4M | Alaeddin 2 18, Naderi 4, Yeganeh 4 |
| 4 | "Surge protector for an AC unit, Lalehzar electrical bazaar, walking route" | محافظ برق ۱۶ آمپر پارت الکتریک مناسب کولرگازی و فر | 38 | 800k / 1.1M / 6.16M | Faraz Lalehzar 6, Sobhan 5, Faraz 4; all فردوسی |
| 5 | "Budget earbuds ≤ 3M, substitute if out" | هدفون بی سیم کیو سی وای مدل T13x | 26 | 2.19M / 2.8M / 3.7M | Alaeddin 5, Charsou 3, Tejarat Jahani 3 |

Alternates:

- Substitutes for #5: Anker Soundcore R50i A3949 (28 shops, median 3.0M, max 22.95M outlier) and Soundcore K20i (20 shops, 2.57M–4.48M).
- A Rial-error transparency demo: JBL PartyBox Stage 320 (33 shops, median 94.5M, max 860M).
- CCTV: Dahua DH-HAC-HDW1200CLQP-IL-A (19 shops, 2.48M–9.78M).
- Unit-ambiguity demo: Afshar Nezhad 2.5 mm² cable (40 shops, 39k – 39.2M).

Combining #1 and #3 with Alaeddin, Alaeddin 2, and Charsou (75–413 m apart) gives a natural "multi-stop walking plan".

## 10. Images

`scratchpad/p10_img.py`, `p10b.py`

- All 349,118 URLs are on `https://image.torob.com/base/images/xx/yy/<id>.<ext>`.
- Images per product: 0 → 1,219; 1 → 100,250; 2 → 124,434. The maximum is 2, so the field looks capped.
- Extensions: jpg 271,031; webp 76,099; avif 675; png 543; jpeg 377; 337 have no extension.
- Fetch test with urllib and a browser User-Agent:

  | file | status | content type | size | headers |
  |---|---|---|---|---|
  | 3 random jpg | 200 | image/jpeg | 13.6–90 KB | `Cache-Control: public, max-age=31536000`, `Access-Control-Allow-Origin: *` |
  | 1 webp | 200 | image/webp | 11 KB | |
  | 2 extensionless | 200 | none | 21–36 KB | |

  Extensionless URLs return no `Content-Type`; browsers sniff it, but a proxy might not. All images can be hotlinked directly. Store images do not exist.

## Unverified / open questions

1. **Channel `unknown` meaning.** It is inferred to be "provider declared, in-store acceptance not stated", but this is not documented. Ask the organizers or check the challenge video.
2. **`location_label` source.** It is inferred to be a coordinate→municipality-neighbourhood lookup, but the names were not checked against an official Tehran mahalleh polygon set.
3. **Null price vs price = 1.** Both are read as "call for price"; only one description confirms it. There may be other placeholder values (e.g. 1,000 or 10,000) that weren't separated.
4. **The 10× outliers** are assumed to be Rial typed as Toman. They may also be bulk or pack prices.
5. **Duplicate (shop, product) rows** are assumed to be variants or matching errors. They may also be distinct listings that Torob merged.
6. **Snapshot date.** The newest timestamp is 2026-10-13 00:02 UTC. The exact crawl time and whether offers were filtered to "active" listings are unknown.
7. **Passage canonicalization.** Whether unnumbered «علاءالدین» always means Alaeddin 1 is not verified; 32 shops say «علاءالدین 1» explicitly. «ایرانیان», with a median of 562 m to its centroid, is at least two buildings.
8. **`weekly_hours` meaning.** Whether it reflects real current hours or a one-off registration is unknown. Ramadan and holiday changes are not represented.
9. **Images.** Only 6 URLs were fetched. Availability from the deploy server's region, and any hotlink or rate limits, are untested.
10. **Toman confirmation** rests on the column name, the README, and plausibility of phone and laptop prices. It does not come from an external price check.
11. **The challenge video** (mandatory, not watched here) may define extra semantics, e.g. exactly how TorobPay "in-store" status should be shown.
