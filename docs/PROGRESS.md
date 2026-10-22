# Progress

## Status board

- **Current phase:** 1 — Data import
- **Live / working:** `uv run starcoach serve` starts the app; `/health` answers. No data yet.
- **Last change:** Change 1

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
