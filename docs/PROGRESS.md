# Progress

## Status board

- **Current phase:** 7 — Evaluation and reviewer doc (3's public deploy parked, D11)
- **Live / working:** `starcoach build-db` builds the full DB (48 s, 382 MB); `starcoach search` answers Persian queries in ~10 ms; `serve` runs the mobile web app: search → product sellers → shop page, with filters (area / near me, budget, visit time, installments, TorobPay, …), reasons, relax buttons and a 3-product compare.
- **Last change:** Change 27

### What we need from the user

| Item | Needed by phase | Status |
|---|---|---|
| The four steps and pain points from the challenge video | 5 | answered 2026-10-23 → D9, `docs/requirements.md` §2–3 |
| LLM provider, base URL and key (D4) | 5 (app works without it) | answered 2026-10-23: set in `.env` → D10, F25–F27 |
| Deploy host: VPS, Iranian PaaS (Liara is a sponsor, F23), or none (D7); and whether judges test from inside Iran | 8 | parked by the user (D11); Docker image ready |
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

### Change 10 — Filter model and data-only reasons (not wired to the API yet) — 2026-10-22
Phase: 4, step 1 (partial)
How to see it: `uv run pytest tests/test_filters.py`
Proof it works: 3 new tests pass (38 total): bad params are ignored; unknown hours / unknown fast delivery never count as a match; a budget never matches a «call for price» offer; Alaeddin→Charsou distance is ~90 m.

Research: 01 §8 (payment), 02 §9 (passage coordinates).
Questions: none
Decisions: none

Shipped:
- `starcoach/filters.py`: `Filters`, `parse_filters`, `shop_matches`, `offer_matches`, `distance_m`, `seller_reasons`
- Phase 4 plan

Not done yet:
- `api.product` and `api.search` do not use the filters yet; no UI for them
- `api.py` still has its own copy of `INSTALLMENT_PROVIDERS` (move to `filters.py` when wiring)

Next change idea:
- Wire `Filters` into `api.product` (filter, sort by price/distance, reasons), then into search, then the context bar UI

### Change 11 — Requirements rewritten with the challenge video; R1–R25 mapped to phases — 2026-10-23
Phase: docs (all phases)
How to see it: `docs/requirements.md` (§2 four-step flow, §3 pain points, §9 checklist R1–R25); `docs/ROADMAP.md` "Requirement → phase"
Proof it works: every ID R1–R25 has a phase in the roadmap table; the old guess D5 is replaced by D9.

Research: the video confirms research 02's hypothesis of the flow; it adds two things research did not have: the agent itself should contact stores (like "Let Google Call") and an installment-only filter is called "very important".
Questions: the four steps from the video → answered by the user (transcript).
Decisions: D9 (replaces D5)

Shipped:
- `docs/requirements.md` in English, organized: goal, four-step flow, pain points, dataset, design rules, deploy, deliverables, judging, numbered checklist. Transcript typos fixed (e.g. «قطی» → installment, «للت گوگل کار» → "Let Google Call", «آلانتی» → alternative).
- Roadmap: requirement table by R-ID; Phase 3, 4, 5, 6 "Done when" now name R6–R9, R1 and Liara

Not done yet:
- Nothing new built in this change

Next change idea:
- Wire `Filters` into the product API with the installment-only filter (R9) and distance (R3, R4)

### Change 12 — Product sellers filter by installments, distance, open, budget; reasons and "relax" hints — 2026-10-23
Phase: 4, step 1 (R3, R4, R9, R18, R19; start of R7)
How to see it: `/api/products/<id>?installments=1`, `?lat=35.6950&lon=51.4113&sort=distance`, `?open=1&at=2026-10-24T11:00&radius_m=500`
Proof it works: `results/filters-demo.txt` (full DB, visit time Sat 11:00):
- 20W charger: installments only → 11 of 59 sellers, all with a BNPL provider; near Alaeddin by distance → nearest first («کنار شما (کمتر از ۵۰ متر)»); open + installments + 500 m → 7 sellers.
- S25 FE: installments only → 2 of 34 (تارا/ازکی‌وام, اسنپ‌پی); open + installments + 500 m → 0, and the API answers: drop «فقط اقساطی» → 25 sellers, drop «فقط باز» → 1.
- Every call ≤ 3 ms. 43 tests pass (installments-only, distance order and radius, budget never matches unknown prices, relax hint, cheapest reason under filters).

Research: 02 §9 Alaeddin coordinates used as the test point.
Questions: none
Decisions: none

Shipped:
- `api.product(conn, id, Filters)`: shop filters (area, passage, radius, open at visit time, installments, TorobPay, in-person pay, fast delivery) + offer filters (budget on normal prices only, warranty); sort by price or distance; `sellers_total`, `sellers_hidden`
- Reasons per seller, from data only: cheapest overall vs «ارزان‌ترین با شرایط شما», near-cheapest, open/closed at visit time, distance, installment providers, warranty, price fresh in the data's last week / unchanged > 3 months
- `relax`: when filters leave 0 sellers, which single filter to drop and how many sellers come back
- Found in the real run and fixed: «۰ متر از شما» for shops in the same building; "cheapest" claimed among filtered sellers only

Not done yet:
- Search results don't use the filters yet
- No UI for filters yet

Next change idea:
- Filters on search results (cards show matching sellers), then the context bar UI

### Change 13 — LLM gateway checked live: chat, tool calls, latency — 2026-10-23
Phase: 5 prep (R1, R6 depend on it)
How to see it: the facts F25–F27 in `docs/DECISIONS.md`
Proof it works: live calls to the gateway in `.env` (key never printed; `.env` is git-ignored): plain chat HTTP 200; tool call parsed budget and query correctly in 2.6 s; thinking off → 0.9 s.

Research: 04 assumed AvalAI/Liara; the user chose a different OpenAI-compatible gateway, so 04's client design (one OpenAI-compatible client, tools, Pydantic check, rules fallback) still holds. New: this model "thinks" by default, which costs 6+ s; turning it off is required for mobile.
Questions: LLM provider → answered by the user (`.env`).
Decisions: D10, F25, F26, F27

Shipped:
- Facts and decision only; no code

Not done yet:
- No LLM client in the app yet (Phase 5)

Next change idea:
- Filters on search results, then the context bar UI; then Phase 5 with this LLM

### Change 14 — Search results respect the filters; cards know matching and open sellers — 2026-10-23
Phase: 4, step 2 (R9, R19)
How to see it: `/api/search?q=گوشی سامسونگ&max_price=60000000&open=1&at=2026-10-24T11:00`
Proof it works (full DB): «گوشی سامسونگ» → S25 FE 34/34 sellers, 18 open now; with installments only → S25 FE 2/34, A17 1/26, A57 2/25; under 60M + open Sat 11:00 → A17 13/26, A07 20/28. «هندزفری بلوتوث» under 3M in شیخ هادی → Soundcore R50i 1/17 at 2.19M. 12–24 ms per search. 44 tests pass.

Research: none new.
Questions: none
Decisions: none

Shipped:
- `api.search(..., f)`: with active filters it scans the top 400 ranked products and keeps those with a matching seller; each item has `match_shops`, `match_min_price`, `open_shops`
- `/api/search` takes the same filter params as the product API

Not done yet:
- No UI for filters; no areas list

Next change idea:
- `/api/areas`, then the context bar and filter sheet in the web app

### Change 15 — Filter UI: context bar + bottom sheet; reasons and "relax" buttons on screen — 2026-10-23
Phase: 4, steps 3–4 (R3, R9, R17, R18, R19; start of R7)
How to see it: `uv run starcoach serve`, open the app, tap a chip under the search box (📍 / 💰 / 🕒 / 💳)
Proof it works (browser, 375 × 812, full DB):
- sheet: area or passage (28 areas, 40 passages with shop counts) or "near me", radius, budget presets, visit day + hour, 6 conditions, sort by price or distance;
- «گوشی سامسونگ» + installments only + ≤ 200M + Saturday 11 → chips update; cards read «۱ از ۳۴ فروشنده با شرایط شما · از ۱۹۷٫۹ میلیون»;
- S25 FE in علاءالدین + open + installments → «هیچ‌کدام از ۳۴ فروشنده…» with a button «بدون فقط اقساطی: ۶ فروشنده»; one tap → 6 sellers, nearest first, each with reasons («ارزان‌ترین با شرایط شما»، «در زمان بازدید باز است»، «کنار شما (کمتر از ۵۰ متر)»).
`/api/areas`: Alaeddin center from data 35.6950, 51.4116 (research 02: 35.6950, 51.4113). 45 tests pass.

Research: 05 §4 (context bar of chips + filter sheet with sticky apply) followed.
Questions: none
Decisions: none

Shipped:
- `/api/areas` (neighbourhoods + top passages with shop counts and centers)
- `app.js`: context state in `localStorage`, chips bar, `<dialog>` sheet, filter params on search and product calls, matching/open counts on cards, reasons chips, relax buttons, "near me" via browser location
- Found in the browser and fixed: product header showed «۰ فروشنده» under filters; the freshness reason contradicted «۱۵ روز پیش» (now «از تازه‌ترین قیمت‌های داده (هفته‌ی آخر)»)

Not done yet:
- Compare view
- "near me" needs HTTPS on the deployed site (browser rule)

Next change idea:
- Compare 2–3 products side by side

### Change 16 — Phase 4 done: compare 2–3 products side by side — 2026-10-23
Phase: 4, steps 5–6 (R4, R17, R18)
How to see it: tap «+ مقایسه» on 2–3 product cards, then «مقایسه» in the bottom tray (`#/compare`); API `/api/compare?ids=a,b,c&<filters>`
Proof it works:
- API on the full DB (point = Alaeddin): Anker R50i / QCY T13x / Anker K20i → sellers 23 / 28 / 1, lowest 4.08M / 2.19M / 3.03M, nearest 9 m / 19 m / 161 m, installment sellers 9 / 8 / 0, warranty sellers 14 / 16 / 0; 11 aligned spec rows.
- Browser 375 px with the area set to علاءالدین: three «+ مقایسه» taps → tray «۳ کالا برای مقایسه»; compare page shows the table with sticky labels, best value per row in green, «فقط تفاوت‌ها» toggle.
- The same title can be two products in the data (research 01 §7); compare shows them side by side (4.1M vs 2.2M), which helps.
46 tests pass.

Research: 05 §4 (2–3 items on mobile, "differences only") followed.
Questions: deploy → parked by the user (D11).
Decisions: D11

Shipped:
- `api.compare` + `/api/compare`: per product under the user's filters (matching sellers, lowest normal price, open, nearest, installment and warranty sellers, freshest change) + spec rows shared by ≥ 2 products
- UI: compare buttons on cards and product page, bottom tray, compare page

Not done yet:
- Phase 5: free-text assistant (rules + LLM), guided model choice (R1)

Next change idea:
- Persian rule parser: sentence → query words + budget + area + time + conditions

### Change 17 — Persian request parser (no LLM) with a labeled eval and a baseline — 2026-10-23
Phase: 5, steps 1–2 (R1 prep, R9, R19)
How to see it: `uv run starcoach eval-intents --split test`
Proof it works: 45 labeled requests in `tests/data/intents.jsonl` (30 dev, 15 held-out test), fixed "now" = Thu 2026-10-22 12:00 Tehran.

| split | parser | exact match | slot accuracy |
|---|---|---|---|
| dev | baseline (raw text, no filters) | 0.10 | 0.469 |
| dev | rules, before fixes | 0.90 | 0.896 |
| dev | rules, after fixes | 1.00 | 1.00 |
| test (held out, run once after tuning) | baseline | 0.067 | 0.429 |
| test | rules | 1.00 | 1.00 |

Reports: `results/intent-eval-dev.json`, `results/intent-eval-test.json`. 50 tests pass.
Caveat (honest): the same author wrote the cases and the parser, and the test split is small (15). Expect lower accuracy on real users' messages; the LLM step and harder cases come next.

Research: 03 §3.2 price parser reused. Two failures found on dev that research did not cover:
- «هدفون بی سیم تا ۳ میلیون» → "30 to 3 million": «سی» (30) inside «سیم», and «م» glued as "million". Fixed with word boundaries.
- «نزدیک لاله زار», «کنار جمهوری» matched same-named passages; people mean the street area. Landmarks now win unless «پاساژ …» is said.
Questions: none
Decisions: none

Shipped:
- `starcoach/intent.py`: budget (ranges, words, colloquial «تومن» resolved by median and flagged), conditions (installments, TorobPay, in-person pay, fast delivery, warranty, open), visit time (امروز/فردا/weekday + part of day / «ساعت ۵» → 17:00), place (DB gazetteer of areas and passages + street landmarks), intent (search / compare / choose), product words
- `starcoach/evaluate.py` + `starcoach eval-intents` (per-slot scores, extra filters count as errors)

Not done yet:
- Not exposed in the API/UI yet; no LLM step yet

Next change idea:
- `/api/ask` and an assistant box that shows the "understood" chips

### Change 18 — Type a sentence, get filters you can see and undo; filtered search stays on topic — 2026-10-23
Phase: 5, step 3 (R17, R18, R19; R9)
How to see it: type «گوشی سامسونگ زیر ۲۰۰ میلیون قسطی تو علاءالدین» in the search box (or tap an example on the home page); API `/api/ask?text=…`
Proof it works (browser 375 px, full DB):
- the sentence becomes chips «📍 علاءالدین», «💰 تا ۲۰۰ میلیون تومان», and a banner «از جمله‌ی شما فهمیدم — کالا: «گوشی سامسونگ»» with removable items (بودجه، فقط اقساطی، علاءالدین);
- results stay in «گوشی موبایل» (before this fix, phone cases and screen protectors filled the filtered list); 1 phone matches all conditions, and the page offers «بدون پاساژ: ۲۰ کالا», «بدون فقط اقساطی: ۲۰ کالا»;
- bare «تومن» is resolved by the category: «گوشی سامسونگ تا ۲۰۰ تومن» → 200 million; «شارژر اپل تا ۸۰۰ تومن» → 800 thousand; the banner offers the other reading.
54 tests pass.

Research: 03 §3.1 (resolve «تومن» by the category median) implemented. 04 §3.1 (chips edit the same filters with no LLM) followed.
Questions: none
Decisions: none

Shipped:
- `api.ask` + `/api/ask` (rules; logged to `logs/ask.jsonl`): product words, filters, understood items, category, ambiguity, and a `ctx_patch` for the web app
- Search: `focus_category` (the category the top 10 unfiltered results agree on, ≥ 60%), `all_cats=1` to show all; `relax` hints when fewer than 3 products match
- Web app: the search box sends sentences to the assistant; "understood" banner with ✕ per item and a "did you mean thousand/million" button; home page examples are full sentences

Not done yet:
- LLM refine step; guided model choice («کمکم کن مدل مناسب را انتخاب کنم» links to `#/guide`, not built yet)

Next change idea:
- Guided model choice (R1), then the LLM step

### Change 19 — Guided model choice: questions from the category's own data, 3 suggested models (R1) — 2026-10-23
Phase: 5, step 5 (R1, R18)
How to see it: type «نمیدونم چه مدلی هندزفری بخرم» → «کمکم کن مدل مناسب را انتخاب کنم»; or `#/guide?q=کتونی`; API `/api/guide?q=…&a.budget=…&a.brand=…`
Proof it works (`results/guide-demo.txt`, full DB, 0.15–0.5 s per call):
- «کتونی» (the video's own example) → «کتانی و کفش اسپرت», 850 models: budget (تا ۳٫۸ / ۳٫۸–۱۰ / بیش از ۱۰ میلیون), brand (نایکی 153, نیو بالانس 16, …), «برای چه کسی؟» (مردانه 182, زنانه 96);
- «گوشی» → budget, brand, internal memory (256 / 128 / 512 GB); «ساعت مچی» → for whom, water resistance, strap, movement; «لپ تاپ» → storage, screen size, CPU series;
- answers narrow it: phone + 9–120M + Samsung → 59 models → A07 64GB (28 sellers, «بیشترین فروشنده»), A07 128GB, A17; «مقایسه‌ی این ۳ مدل» opens compare.
- Each option shows how many models match it, given the other answers.
Browser 375 px checked. 55 tests pass.

Research: 04 §4.3 (substitution/choice without an LLM from category + price band + specs) followed.
Questions: none
Decisions: none

Shipped:
- `starcoach/guide.py`: budget bands from price terciles, top brands by seller count, "for whom" from titles, spec questions (user-facing keys first, value units folded, multi-valued and count keys skipped), shortlist of 3 with different strengths (most sellers, cheapest, most complete specs), respecting the user's filters
- `/api/guide`; guide page; «مدلش را نمی‌دانید؟» link on every search page
- Bugs found and fixed: «باس رم»/«رادیو»/colour questions; values «5600MHz» vs «5600 مگاهرتز» split; a broken regex back-reference (``) merged all memory sizes; long reason chips overflowed at 375 px; browsers kept a stale `app.css` → assets now carry a content hash (`?v=`) and `index.html` is `no-cache`

Not done yet:
- LLM step (better wording of questions, "why" sentences, messy requests)

Next change idea:
- LLM client + refine step with logging and fallback

### Change 20 — Phase 5 done: the LLM refines free descriptions, measured against rules and a baseline — 2026-10-23
Phase: 5, step 4 (R1, R17; Intelligence)
How to see it: type «برای کولر گازی خونه یه چیزی میخوام که برق رفت و اومد خراب نشه، نزدیک لاله زار» → «⏳ دستیار هوشمند…» → «✨ با کمک دستیار هوشمند خوانده شد (نام کالا از توضیح شما)»; `uv run starcoach eval-intents --split hard --with-llm`
Proof it works:

| split | baseline | rules | LLM replacing rules | rules + LLM (merged) |
|---|---|---|---|---|
| dev (30) | 0.469 | 1.00 | — | 0.984 |
| test (15, held out) | 0.429 | 1.00 | — | 1.00 |
| hard (10 free descriptions) | 0.28 | 0.72 | 0.423 | 0.769 |

(slot accuracy; `results/intent-eval-{dev,test,hard}.json`). LLM calls take 0.8–1.8 s; each is logged in `logs/llm_calls.jsonl` (no key). 56 tests pass, all offline (the test client now blanks the `.env` LLM settings; one test had been calling the live LLM).
Honest notes:
- The "hard" split was written before the LLM step; two rule bugs it exposed were then fixed (bare «شب» read as a visit time; «علاءالدین ۲،» lost its number because of the comma), so rules' 0.72 on hard is after that fix (0.615 before).
- The one dev "regression" with the LLM is a label artifact: «پاوربانک 20000 میلی امپر» finds 180 products vs 10 for the labeled «20 هزار».
- Still failing on hard: «پول زیادی ندارم», «زیاد گرون نباشه» are not read as "cheap"; «حدود ده میلیونه» budget missed.

Research: 04 §3 (LLM amends filters, never writes prices; code checks every value) followed. New facts F28, F29.
Questions: none
Decisions: D12

Shipped:
- `starcoach/llm.py`: stdlib OpenAI-compatible client (thinking off, 12 s timeout, JSONL log), `set_filters` tool (areas as enum), validation against DB lists, `merge` (rules win; LLM fills gaps and names the product only for free descriptions), prompt examples that are not eval cases
- `/api/ask?llm=1`; `eval-intents --with-llm`, `--split hard`
- UI: rules answer at once; for free descriptions the LLM runs in the background and the banner shows ⏳ / ✨ / "not available"
- Rules: punctuation counts as a word end; part-of-day words need a day or hour

Not done yet:
- "cheap" phrasings like «پول زیادی ندارم»; «۲۰ هزار میلی آمپر» → 20000 folding for search

Next change idea:
- Phase 6 plan: visit plan, alternatives when a store is closed or doesn't answer, simulated seller contact

### Change 21 — Lint pass: ruff config; code and tests clean — 2026-10-23
Phase: rule 12 (clean as you go)
How to see it: `uvx ruff@0.8.4 check starcoach tests`
Proof it works: "All checks passed!" (E, F, W, B, I; B008 and E501 ignored with reasons in `pyproject.toml`); 56 tests pass.
Shipped: `[tool.ruff]` in `pyproject.toml`; one import order fix; README "Lint" section.

### Change 22 — Phase 6 backend: alternatives, simulated seller contact, visit plan, in-passage location — 2026-10-23
Phase: 6, steps 1–5 backend (R4, R5, R6, R7, R8)
How to see it: `/api/alternatives?product_id=…&shop_id=…`, `POST /api/contact`, `/api/plan?shops=a,b,c&at=…`, `/api/shops/<id>/where`; `results/visit-demo.txt`
Proof it works (full DB, S25 FE in علاءالدین, Sat 11:00):
- the agent asks the 3 cheapest of 8 sellers: «بله، موجود داریم. قیمت همان است…»; «…قیمت امروز ۱۸۳٬۱۳۰٬۰۰۰ تومان است…»; replies carry facts (in_stock, price_now, closes_at, hold_until) and are marked simulated;
- if the first seller doesn't answer: 30 open alternatives, same passage first, each with floor/unit, price, hours (< 1 ms);
- 4-stop plan from the Alaeddin entrance: 205 m walk, 11:00 → 11:42, ordered by floor inside the building; a warning for the stop with no hours; the same plan on Friday flags closed stops.
61 tests pass (determinism of replies, dedupe by request id, closed alternatives excluded, plan order and warnings, passage neighbours).
Found in the real run and fixed: "hold until 11:00" when asked at 11:00; no neighbours when the address has no floor.

Research: 04 §3.2 tools (`find_substitutes`, `plan_visit`, `draft_seller_message`) implemented server-side, deterministic.
Questions: none
Decisions: D6 applied (simulated replies, labeled)

Shipped:
- `starcoach/visit.py`: `alternatives` (+ `substitutes` in the same category and price band), `in_passage`, `plan`
- `starcoach/contact.py`: message draft from chosen questions; deterministic simulated reply grounded in price freshness, hours, warranty and payment data
- API routes; `logs/contacts.jsonl`

Not done yet:
- No UI for contact, alternatives, plan, or "where" yet

Next change idea:
- UI: «از فروشنده بپرس» sheet on seller cards, status chips, alternatives on failure, plan page

### Change 23 — Seller contact in the app: ask one seller, or let the agent ask the top 3; alternatives on failure — 2026-10-23
Phase: 6, steps 1–3 UI (R5, R6, R7, R20)
How to see it: open a product (e.g. S25 FE with the area set to علاءالدین) → «🤖 از ۳ فروشنده‌ی اول بپرس», or «از فروشنده بپرس» on any seller card
Proof it works (browser 375 px, full DB, real time Fri 14:00, visit Sat 11:00):
- agent: «رامیرا ماهورا: موجودی تأیید شد · قیمت امروز ۱۸۲٫۲ میلیون تومان (تغییر کرده)», «ویان وییلا: پاسخی نداد», «فرین مهریس: موجودی تأیید شد» → «۲ از ۳ فروشنده موجودی را تأیید کردند. ارزان‌ترینِ تأییدشده: «رامیرا ماهورا» با ۱۸۲٬۱۷۰٬۰۰۰ تومان — مجتمع تجاری علاءالدین، پلاک 19»;
- single contact: question chips → message bubble → «پاسخی نیامد. فروشگاه الان طبق ساعت اعلام‌شده بسته است.» (marked «پاسخ نمایشی») → «پاسخی نداد» → 30 open alternatives for the visit time, same passage first;
- seller cards keep the confirmed status as its own chip («موجودی تأیید شد (۱۴:۰۰)…»), apart from the recorded price and its date (R20).
61 tests pass.
Found in the browser and fixed: long status chips overflowed at 375 px (chips now wrap, except the scrolling bar); «نگه می‌دارد تا 11:00» for a next-day visit now names the day.

Research: 05 §4 ("Let Google Call"-style follow-up) followed, simulated per D6.
Questions: none
Decisions: none

Shipped:
- `app.js`: contact sheet with question chips and chat bubbles, `sendContact` (request id per send), contact state in `localStorage`, `askTopSellers`, alternatives box (other sellers + substitutes), «جایگزین‌ها» on closed / failed sellers
- `contact.py`: hold time names the day when it is not today

Not done yet:
- Visit plan page; "where in the passage" on the shop page

Next change idea:
- Plan page and in-passage location

### Change 24 — Phase 6 done: visit plan page and "where in the passage" — 2026-10-23
Phase: 6, steps 4–6 (R4, R8, R7)
How to see it: «+ برنامه‌ی بازدید» on seller cards (or after «🤖 از ۳ فروشنده‌ی اول بپرس») → «🗺 برنامه‌ی بازدید» at the top; «کجای پاساژ؟» on plan stops and shop pages
Proof it works (browser 375 px, start علاءالدین, Saturday 11:00):
- plan: 3 stops, 102 m on foot, 11:00 → 11:31; a warning «ساعت کاری «مهردیس پاکآرا» ثبت نشده؛ قبل از رفتن بپرسید»; closed stops get a «جایگزین» button; Neshan links from the previous stop;
- where: «پاساژ علاءالدین، همکف، واحد 77 — 55 shops on this floor; nearby units 79, 75, 80»; a shop whose only number is «پلاک 19» (shared by many shops in the building) now says it is the building number and to ask for the unit, instead of listing five «پلاک 19» neighbours.
61 tests pass.

Research: 01 §2 (floor/unit parse) and 02 §3 (finding the unit in a multi-floor passage) applied.
Questions: none
Decisions: none

Shipped:
- `app.js`: plan state in `localStorage`, plan buttons, plan page (timeline, warnings, alternatives, contact, route, remove), «کجای پاساژ؟» on shop page and stops
- `visit.in_passage`: building plaque detection; no neighbours without a reference unit

Not done yet:
- Phase 7: reviewer doc, results summary, demo scenario

Next change idea:
- Reviewer doc (`docs/REVIEW.md`): architecture, logic, choices, how to run and check, results with numbers, demo script

### Change 25 — Reviewer guide and a one-command results refresh — 2026-10-23
Phase: 7 (R10, R24, R25)
How to see it: `docs/REVIEW.md`; `uv run starcoach results`
Proof it works: `starcoach results` rewrote 6 files in 2.0 s (`stats.json`, `search-demo-queries.txt`, `intent-eval-rules.json`, `guide-demo.txt`, `filters-demo.txt`, `visit-demo.txt`); its summary repeats the eval table (test: baseline 0.429 → rules 1.0). Live check of the demo-script claims: «برای کولر گازی خونه … خراب نشه» → «محافظ برق کولر گازی» (rules+LLM), top result «محافظ برق ارتدار کولر گازی خیام»; «تو مترو آهنگ گوش بدم، سیم نداشته باشه» → «هندزفری بلوتوث». 62 tests pass; ruff clean.

Research: none new.
Questions: none
Decisions: none

Shipped:
- `starcoach/results.py` + `starcoach results`
- `docs/REVIEW.md`: run and check, the four steps → screens, R1–R25 → evidence, architecture and modules, logic and reasons, results with numbers, honest limits, a 5-minute demo script
- README: links the reviewer guide; new command listed

Not done yet:
- Phase 8 (release audit, tag); public deploy parked (D11)
- Known gaps: typo correction; "cheap" phrasings like «پول زیادی ندارم»

Next change idea:
- Release audit against `docs/requirements.md`, then tag; then improve the weakest score item

### Change 26 — Release fixes found by the audit: missing files in git; fields the data lacks are now named — 2026-10-23
Phase: 8, step 1 (R10, R11, R12, R13, R14, R21, R24)
How to see it: fresh clone → `uv sync && uv run pytest`; product page notices; shop page «شرایط خرید» list
Proof it works:
- **Bug:** `.gitignore` had `data/`, which also ignored `starcoach/data/aliases.json` and `tests/data/intents.jsonl`. A fresh clone failed 32 tests and search would crash. Now only `/data/` is ignored. Fresh clone of `origin/main`: 62 → 63 tests pass; `build-db` gives the same counts (6,476 / 225,903 / 331,506, 49.6 s); `serve` + `smoke` passed; Docker image built from the fresh clone → healthy, smoke 6/6 OK.
- Shop page now names what the data doesn't have: messengers («ثبت نشده؛ فقط تلفن»), Torob history and licences, store image and introduction (R11, R12).
- Product page: «نام انگلیسی/مدل» from `model` (only when it shares a word with the title: 257 of the first 300 models kept; junk like «authentic-base-10189» dropped) or a Latin «نام محصول» spec (R13); when normal prices differ by more than 3× across shops, a notice says the sale unit or original/copy may differ and that the unit is not in the data (R14). Apple 20W charger: 6.8×.
63 tests pass; ruff clean.

Research: 01 §5 (no price-unit field; per-metre vs coil) and §8 (missing fields table) applied.
Questions: none
Decisions: none
