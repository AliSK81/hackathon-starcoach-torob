# Phase 0 — The project runs

## Goal
- One command starts the app. No keys needed.

## Choices
- Package `starcoach` (Python 3.12, managed by `uv`). Deps: `fastapi`, `uvicorn`. Dev: `pytest`, `httpx`.
- CLI: `starcoach <subcommand>` with `argparse` (no extra library).
- Config: read from environment, with a tiny `.env` loader (no `python-dotenv`).
- Logs: append-only JSONL in `logs/`.
- Frontend: static files in `starcoach/web/`, served by FastAPI.

## Checklist
- [x] `pyproject.toml`, `.python-version`, `.env.example`, `.gitignore`
- [x] `starcoach serve` starts the server; `/health` returns `{"status":"ok"}`
- [x] Placeholder RTL page at `/`
- [x] JSONL event log (`starcoach.logs`)
- [x] One offline test passes (`uv run pytest`)
- [x] README: setup, commands, tests
