# Decisions and checked facts

Rules:
- Never edit an old entry. A new entry replaces an old one and says so ("replaces D3").
- Progress entries link to these IDs instead of repeating them.

## Decisions

| ID | Decision | Date | Who |
|---|---|---|---|
| D1 | `requirements.md` lives at `docs/requirements.md`. It is the only source of the task. | 2026-10-22 | rules |
| D2 | Stack: Python + FastAPI + SQLite (FTS5). Frontend: mobile-first Persian RTL web app with no build step, served by FastAPI. | 2026-10-22 | Claude (recommended to user, pending reply) |
| D3 | The raw dataset (273 MB) stays out of git (`data/` is ignored). A CLI command builds a SQLite DB from the CSVs. | 2026-10-22 | Claude (pending reply) |
| D4 | LLM access goes through one OpenAI-compatible client set by `.env` (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`). The app works fully without a key, using a rule-based Persian parser. | 2026-10-22 | Claude (pending reply) |
| D5 | Working guess for the four-step flow (video not available to Claude): 1) state the need, 2) find and compare products, 3) pick a seller by area, hours and purchase terms, and plan the visit, 4) follow up with the seller. | 2026-10-22 | Claude (pending reply) |
| D6 | Store phones are fake, so seller follow-up drafts real messages but simulates replies, clearly labeled as a demo. | 2026-10-22 | Claude (pending reply) |
| D7 | Deploy target: a Docker image that runs anywhere. The host is chosen when the user answers. | 2026-10-22 | Claude (pending reply) |

## Checked facts

| ID | Fact | Value | Date | Source |
|---|---|---|---|---|
| F1 | Row counts | shops 6,476; products 225,903; offers 331,506 | 2026-10-22 | `data/torob-dataset/README.txt`; `python docs/research/scripts/profile.py data/torob-dataset` |
| F2 | Store contacts | every contact is `phone` (6,476); no WhatsApp/Bale fields in the data | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F3 | `payment_options` coverage | non-empty for 266 of 6,476 shops; providers include ترب‌پی، اسنپ‌پی، دیجی‌پی، تارا، ازکی‌وام; channel is `in_person` or `unknown` | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F4 | `supports_fast_delivery` | true 1,168; false 433; null 4,875 | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F5 | `weekly_hours` | empty for 2,003 shops; day status values: declared 27,270, closed 4,006, unsupported 35 | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F6 | `location_label` | 31 distinct values; top: فردوسی 3,282, شیخ هادی 1,587, بهارستان 616 | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F7 | Product field gaps | brand null 168,269; model null 221,847; specs empty 81,304; images empty 1,219 | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F8 | Offer prices | 15,083 offers have no price; min 1, median 3,640,000, max ≈7.3e17 Toman (bogus outliers exist) | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F9 | Offer warranty | null for 272,563 offers; JSON `{provider, period_months, description}` otherwise | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F10 | Price-change dates | newest 2026-10-13; 769 null; oldest 2020-12-03 | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F11 | Sellers per product | 187,004 products have 1 offer; max 105 offers for one product | 2026-10-22 | `python docs/research/scripts/profile.py data/torob-dataset` |
| F12 | Local tooling | Python 3.14.2, SQLite 3.50.4, uv 0.5.9, Docker 29.6.2 | 2026-10-22 | `python --version`, `python -c "import sqlite3;print(sqlite3.sqlite_version)"`, `uv --version`, `docker --version` |
| F13 | Join integrity | 0 orphan offers; 0 duplicate IDs; 2,684 shops have no offers; max 300 distinct products per shop; 9,557 repeated (shop, product) pairs are variants | 2026-10-22 | `docs/research/scripts/01-dataset/p1_joins.py`, `p1b_dups.py` (research 01 §1) |
| F14 | Snapshot time | newest `last_price_changed_at` = 2026-10-13 00:02 UTC; timestamps are UTC | 2026-10-22 | `docs/research/scripts/01-dataset/p6_ts.py` (research 01 §6) |
| F15 | Price junk | 635 offers at 1 Toman ("call for price"); 211 offers ≥ 1e10; real prices go down to ~420 and up to ~1.65e10 for industrial gear; 188 offers ≈ 10× product median (Rial typed as Toman) | 2026-10-22 | `p5_price.py`, `p5b_spread.py` (research 01 §5) |
| F16 | Hours format | shifts padded with `00:00–00:00`; 24h written as `00:00–23:59`; no overnight shifts; `unsupported` days have start == end | 2026-10-22 | `p4_hours.py`, `p4b_hours.py` (research 01 §4) |
| F17 | Time zone | Asia/Tehran is UTC+03:30 all year (DST abolished 2022-09-21) | 2026-10-22 | `p4d_tz.py` with Python tzdata; Wikipedia "Iran Standard Time" |
| F18 | Kalabarg | the word کالابرگ appears 0 times in any column | 2026-10-22 | `p8_pay.py` (research 01 §8) |
| F19 | Requirement fields missing from data | store images, business type/description, presence history, licenses, messenger contacts, English title, product description, price unit, stock, Kalabarg | 2026-10-22 | research 01 §8 table |
| F20 | FTS5 unicode61 over normalized titles | build 3.2 s, 86.5 MiB, queries 0.5–6.4 ms; needs brand aliases (آیفون↔iphone) and a category boost | 2026-10-22 | `docs/research/scripts/03-search/fts_bench.py`, `fts_bench2.py` (research 03 §2) |
| F21 | Redacted titles | 849 products titled «عنوان حذف‌شده برای انتشار» | 2026-10-22 | `p7_text.py` (research 01 §7) |
