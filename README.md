# StarCoach — Persian in-store shopping assistant (Torob challenge)

A mobile-first, right-to-left web app that helps people shop in person in Tehran stores and passages.
It is built on the Torob dataset (shops, products, offers).

## Setup

Needs [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 if missing).

```bash
uv sync
```

Put the Torob dataset CSVs in `data/torob-dataset/` (`shops.csv`, `products.csv`, `offers.csv`).
The `data/` folder is not in git.

Optional: copy `.env.example` to `.env` and edit it. The app needs no keys.

## Commands

| Command | What it does |
|---|---|
| `uv run starcoach build-db` | Builds `data/starcoach.db` from the CSVs (about 1 minute) |
| `uv run starcoach stats` | Prints counts from the built DB |
| `uv run starcoach serve` | Runs the web app and API on http://127.0.0.1:8000 |

## Tests

All tests run offline. They use a small real sample of the dataset in `tests/fixtures/mini/`
(made by `tests/fixtures/make_mini.py`).

```bash
uv run pytest
```

## Docs

- `docs/requirements.md` — the challenge text
- `docs/ROADMAP.md` — phases and what each one delivers
- `docs/PROGRESS.md` — what shipped, with proof
- `docs/DECISIONS.md` — decisions and checked facts
- `docs/research/` — background research
