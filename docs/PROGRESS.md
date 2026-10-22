# Progress

## Status board

- **Current phase:** 1 — Data import
- **Live / working:** `uv run starcoach serve` starts the app; `/health` answers. No data yet.
- **Last change:** Change 4

### What we need from the user

| Item | Needed by phase | Status |
|---|---|---|
| The four steps and pain points from the challenge video (D5 is a guess) | 5 | asked |
| LLM provider, base URL and key (D4) | 5 (app works without it) | asked |
| Deploy host: VPS, Iranian PaaS, or none (D7) | 3 | asked |
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
