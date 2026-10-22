# Progress

## Status board

- **Current phase:** 3 — Docker and first deploy
- **Live / working:** `starcoach build-db` builds the full DB (48 s, 382 MB); `starcoach search` answers Persian queries in ~10 ms; `serve` runs the mobile web app: search → product sellers → shop page.
- **Last change:** Change 9

### What we need from the user

| Item | Needed by phase | Status |
|---|---|---|
| The four steps and pain points from the challenge video (D5 is a guess) | 5 | asked |
| LLM provider, base URL and key (D4) | 5 (app works without it) | asked |
| Deploy host: VPS, Iranian PaaS (Liara is a sponsor, F23), or none (D7); and whether judges test from inside Iran | 3 | asked — Docker image ready, waiting |
| OK on stack (D2), data out of git (D3), simulated seller replies (D6) | 1 | asked |
| Public download URL for the dataset, if any | 3 | asked |

## How to work on the next change

1. Read the status board and the roadmap table. Find the current phase.
2. If the phase has no plan, write `docs/phases/phase-<N>-<name>.md`: the goal, the choices, and a checklist. Keep it short. Mark the phase `planned`.
3. Pick the next change: the smallest step that leaves the project working and moves it toward a requirement. Check DECISIONS.md first. Don't ask again what is decided there.
4. Read only the research this change needs. Check facts against the real system. Write new facts in DECISIONS.md before code depends on them.
5. Build it. Add offline tests. Run something real that proves it works: the real command, the real API, the real data.
6. Write a PROGRESS entry. Update the status board, the roadmap table, the phase checklist, and the README if a command changed.
7. Commit. Then go straight to step 1.

## Entry template

```
### Change N — <what shipped, in one line> — <date>
Phase: <N, step M>
How to see it: <the exact command>
Proof it works: <what you ran, and what happened, with numbers>

Research: <what you checked, or "none". Say if old research was wrong.>
Questions: <question -> answer, or "none">
Decisions: <IDs, or "none">

Shipped:
- ...

Not done yet:
- <honest gaps>

Next change idea:
- <a suggestion only>
```

## Entries

### Change 1 — The project runs with one command — 2026-10-22
Phase: 0, steps 1–6
How to see it: `uv sync && uv run starcoach serve`, then open http://127.0.0.1:8000/health
Proof it works: `uv run pytest` → 2 passed. Started `starcoach serve --port 8765`; `curl /health` → `{"status":"ok","version":"0.1.0","db":false,"llm":false}`; `/` returns the RTL page; `logs/runs.jsonl` got one `serve` event.

Research: 01, 03, 04, 05 written (02 and 06 still running). Local SQLite in the uv Python 3.12 is 3.47.1 (FTS5 trigram needs ≥3.34, so fine).
Questions: the 7 questions on flow, LLM, deploy, stack, data, follow-up, push → no reply yet; working on the recommended answers (D2–D7).
Decisions: D2, D3, D4, D7

Shipped:
- `pyproject.toml` (fastapi, uvicorn; dev: pytest, httpx), `.python-version` 3.12
- `starcoach` CLI with `serve`; FastAPI app with `/health` and a placeholder RTL page
- `.env` loader with no extra library; `.env.example` lists every setting
- Append-only JSONL log with secret redaction (`starcoach/logs.py`)
- README in UTF-8 (the old one was UTF-16)

Not done yet:
- No data, no search, no UI

Next change idea:
- `starcoach build-db`: CSV → SQLite with normalized text and FTS5

### Change 2 — Persian normalizer for search keys — 2026-10-22
Phase: 1, step 1
How to see it: `uv run pytest tests/test_textnorm.py`
Proof it works: 5 new tests pass (7 total). Normalized all 225,903 product titles in 2.8 s; 90,089 titles change under folding (Arabic letters, digits, ZWNJ, آ).

Research: 03 §1.4 character map, used as is. Checked on the real titles.
Questions: none
Decisions: F13–F21 added from research 01 and 03.

Shipped:
- `starcoach/textnorm.py`: `normalize`, `tokens`, `to_ascii_digits`, query stopwords
- Phase 1 plan: `docs/phases/phase-1-data.md`

Not done yet:
- Not used by any index yet

Next change idea:
- `build-db` with clean price status and warranty

### Change 3 — `build-db` and `stats`: CSVs become one clean SQLite DB — 2026-10-22
Phase: 1, steps 2 and 6
How to see it: `uv run starcoach build-db && uv run starcoach stats`
Proof it works: full build in 49.5 s, DB 352.9 MB. `stats`: shops 6,476, products 225,903, offers 331,506 (= F1); shops with offers 3,792 (= F13); real-named shops 112 (= requirements); products with ≥ 2 shops 35,254 (research said ~35k); price status ok 312,868 / suspicious 2,698 / call 15,729 / invalid 211 (F15 predicted 211 ≥ 1e10). Snapshot 2026-10-13T00:02:35Z (= F14). 12 tests pass offline.

Research: 01 §1, §5, §8 used. Suspicious count is 2,698, not research's 2,223: we compare each offer (not each shop minimum) to the per-shop-minimum median. Kept; it only adds a badge.
Questions: none
Decisions: F15 cutoffs used as is.

Shipped:
- `starcoach/db.py` schema; `starcoach/build.py` with price status, warranty kind (yes / none / unknown), payment list, product min and median price, shop offer counts, `meta.snapshot`
- Atomic build (temp file + rename); bad rows go to `logs/build.jsonl` and are skipped
- `tests/fixtures/mini/`: 383 real offers of the research demo products plus edge cases (1 Toman, null, garbage price, redacted title)

Not done yet:
- Address and hours are stored raw; not parsed yet
- No search index
- DB is large (353 MB), mostly specs JSON; check size before deploy

Next change idea:
- Address parser (passage, floor, unit, plaque)

### Change 4 — Shop addresses parsed into passage, floor, unit and plaque — 2026-10-22
Phase: 1, step 3
How to see it: `uv run starcoach build-db && uv run starcoach stats` (fields `shops_with_passage`, `shops_with_floor`, …)
Proof it works: on all 6,476 shops: passage 4,056 (62.6%), floor 4,227 (65.3%), unit or plaque 5,881 (90.8%); 563 distinct passages. Top: علاءالدین 312, بوشهری 177, چارسو 171, علاءالدین 2 127. Floors range −4…14; the typo floor 111 is dropped. 22 tests pass.

Research: 01 §2 parser reused. It was wrong on 2 cases («طبقه بالای همکف», «طبقه منفی (زیرزمین)»); both fixed and tested.
Questions: none
Decisions: none

Shipped:
- `starcoach/address.py`: `parse_address`, `canonical_passage` (9 Alaeddin spellings → علاءالدین; چهارسو → چارسو; …), `floor_label`
- New shop columns: passage, passage_kind, floor, unit, plaque; index on passage

Not done yet:
- ~10% of messy addresses stay unparsed; the raw address is always shown

Next change idea:
- Hours parser with open / closed / unknown

### Change 5 — Opening hours: cleaned, with open / closed / unknown answers — 2026-10-22
Phase: 1, step 4
How to see it: `uv run pytest tests/test_hours.py`; hours are stored cleaned in `shops.hours`
Proof it works: of 3,792 shops with offers, 3,011 have hours (= research 01 §4). Open counts on the real DB: Sat 11:00 → open 2,846 / closed 162 / unknown 784; Sat 21:30 → open 122; Thu 16:00 → open 1,535 / closed 1,472; Fri 12:00 → open 592 / closed 2,367. This matches the Iranian week. 27 tests pass.

Research: 01 §4 rules used. One bug found while testing: a 00:00–23:59 shift was dropped as "too short" by the modulo rule; fixed and tested.
Questions: none
Decisions: fixed UTC+03:30 offset instead of a tz database (F17), so no `tzdata` dependency on Windows.

Shipped:
- `starcoach/hours.py`: `clean_hours`, `is_open_at` (True / False / None), `status_text` («باز است · تا 19:00», «بسته · باز می‌شود فردا 09:00»), `week_table` in Iranian week order
- `shops.hours` holds cleaned JSON; `stats` shows `shops_with_hours`

Not done yet:
- Official holidays are not in the data; not handled

Next change idea:
- FTS5 index and `starcoach search`

### Change 6 — Phase 1 done: Persian product search with aliases and re-ranking — 2026-10-22
Phase: 1, steps 5 and 7
How to see it: `uv run starcoach search "گوشی سامسونگ"`
Proof it works: 225,052 products indexed (851 redacted titles left out). 12 demo queries in `results/search-demo-queries.txt`: all 12 have a sensible top 3 (e.g. «آیفون ۱۳ ۱۲۸» → 4 iPhone 13 128 GB phones; «جی بی ال» → JBL speaker; «شیامی ردمی» → Redmi phones, not batteries). Mean query time 10.3 ms over 50 runs. Build 48.4 s, DB 382 MB (`results/build-db.json`). 32 tests pass.

Research: 03 §2 confirmed: AND + prefix, fallback to OR, aliases needed. Two things the research did not cover and that failed on real queries:
- multi-word Persian aliases (جی بی ال) matched unrelated LED titles → now collapsed to `jbl` in the query;
- the head-word boost also boosted brand-first titles («Redmi 4A - باتری») → now only product-type head words that also name the category get the boost, and accessory categories get a penalty unless asked.
Questions: none
Decisions: D8 (below)

Shipped:
- `starcoach/search.py`: contentless FTS5 (title, alias, brand, category; bm25 4/2/2/1), alias expansion at index time, alias collapse at query time, Python re-rank (head boost, accessory penalty, log popularity)
- `starcoach/data/aliases.json`: 376 alias groups (hand groups + mined brands filtered)
- `starcoach search` CLI; `products.head`

Not done yet:
- No typo correction (سامسنگ → 0 hits)
- Seller titles are not indexed
- Prices in queries («زیر ۲۰ میلیون») not parsed yet (Phase 5)

Next change idea:
- Phase 2 plan; JSON API for search, product and shop

### Change 7 — JSON API: search, product with sellers, shop with products — 2026-10-22
Phase: 2, step 1
How to see it: `uv run starcoach serve`, then `/api/search?q=شارژر اپل`, `/api/products/<id>`, `/api/shops/<id>`, `/api/meta`
Proof it works: on the full DB, «شارژر اپل ۲۰ وات» → product with 59 sellers, cheapest first; first seller «پاساژ علاءالدین، طبقه منفی 2، پلاک 138», «باز است · تا 20:00». Timings: search 3 ms, product 4 ms, shop 2 ms. 35 tests pass (search → product → shop flow, 404s, 503 when the DB is missing, call-for-price offers have no price and a note).

Research: none new.
Questions: none
Decisions: TorobPay is shown as its own payment type, not as installments, until research 02 says what it is.

Shipped:
- `starcoach/api.py`: read model with transparency labels (price note per price status, payment channel text, hours status)
- Routes in `starcoach/app.py`; one read-only connection per request
- Phase 2 plan

Not done yet:
- No UI on top of the API yet

Next change idea:
- Search page and product cards in the web app

### Change 8 — Phase 2 done: mobile RTL web app for search → sellers → shop — 2026-10-22
Phase: 2, steps 2–6
How to see it: `uv run starcoach serve`, open http://127.0.0.1:8000 on a phone-width window, search «شارژر اپل ۲۰ وات»
Proof it works: checked in the browser at 375 × 812:
- search shows 41 cards with image, category, seller count and «از ۱٫۳ میلیون تومان»;
- the product page lists 59 seller cards with open status, passage/floor/unit, recorded price, «آخرین تغییر قیمت: ۹ ماه پیش — شاید قدیمی باشد», warranty, TorobPay chip, Neshan link;
- the shop page shows the parsed location, «ساعت کاری ثبت نشده؛ قبل از رفتن تماس بگیرید», payment with channel, Kalabarg «اطلاعاتی در داده نیست», phone marked «شماره نمایشی».
35 tests pass.

Research: 02 (TorobPay is 4-installment BNPL → F22, now counted as installments), 05 (Intl fa-IR, Neshan links). Research index `docs/research/00-index.md` written.
Questions: none new
Decisions: F22, F23, F24

Shipped:
- `starcoach/web/`: `index.html`, `app.css`, `app.js` (hash router, all values escaped, Persian number/Toman/relative-time formatting)
- Product sellers order: normal prices first, then «suspicious», then no price. Bug found in the browser: a mismatched 480k adapter offer was first.
- `canonical_passage` splits glued numbers («علاالدین3» → «علاءالدین 3»). Bug found in the browser.
- `.claude/launch.json` for the preview server

Not done yet:
- No filters (area, budget, open now, payment) — Phase 4
- System font only (Vazirmatn not self-hosted)
- No map view, only links

Next change idea:
- Dockerfile + compose, then deploy (Phase 3)

### Change 9 — Docker image, smoke-test command, packed DB download — 2026-10-22
Phase: 3, steps 1–5
How to see it: `uv run starcoach build-db && docker compose up -d --build && uv run starcoach smoke --url http://127.0.0.1:8000`
Proof it works:
- `docker compose up` → container `healthy`; `starcoach smoke --url http://127.0.0.1:8010` → 6/6 OK (health 82 ms, ready 15, search 34, product 36 (59 sellers), shop 91, web 27), SMOKE PASSED.
- Empty volume + `DB_URL` pointing at `starcoach.db.gz` (served locally) + `DB_SHA256` → entrypoint downloaded, checked and unpacked the DB; container healthy; smoke passed.
- `pack-db`: 382 MB → 97.9 MB gzip, sha256 `0fdcc8d8…f1318`.
- The smoke test also caught a stale server (old build had no `/ready` → FAIL), so it does its job.
35 tests pass.

Research: 06 (DB as a file on a volume, health + ready, mirrors for Iran) used. Not yet checked against a real Iranian host.
Questions: deploy host → still waiting (asked once).
Decisions: none new

Shipped:
- `Dockerfile` (python:3.12-slim, non-root, healthcheck on `/ready`, base image and PyPI index as build args), `docker-entrypoint.sh`, `docker-compose.yml`, `.dockerignore`
- `/ready` (503 until the DB exists)
- `starcoach smoke --url` (stdlib only; logs to `logs/smoke.jsonl`), `starcoach pack-db`

Not done yet:
- Not deployed on a public server (blocked on the host answer)
- The DB file still needs a download location the server can reach

Next change idea:
- Phase 4 filters while waiting for the host
