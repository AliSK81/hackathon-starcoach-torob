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
| `uv run starcoach search "<query>"` | Searches products from the command line |
| `uv run starcoach eval-intents --split test` | Scores the Persian request parser on labeled requests against a no-parsing baseline (`--with-llm` adds the LLM) |
| `uv run starcoach serve` | Runs the web app and API on http://127.0.0.1:8000 |
| `uv run starcoach results` | Regenerates the offline result files in `results/` from the DB |
| `uv run starcoach ai-demo` | Runs the AI layer live (needs the LLM in `.env`) and writes `results/ai-demo.txt`: keyword vs AI search, agent tool trails, timings |
| `uv run starcoach smoke --url <base>` | Checks a running instance: health, ready, search, product, shop, web |
| `uv run starcoach pack-db` | Writes `data/starcoach.db.gz` and prints its SHA256, for upload to a server |

## Run with Docker

The image does not contain the DB. It uses the `./data` folder as a volume.

```bash
uv run starcoach build-db
docker compose up -d --build
uv run starcoach smoke --url http://127.0.0.1:8000
```

On a server with an empty volume, set `DB_URL` (a link to `starcoach.db.gz` from `pack-db`)
and `DB_SHA256`. The container downloads and checks the DB at start. If the CSVs are on the
volume instead, it builds the DB. `/ready` answers 503 until the DB is there.

In Iran, Docker Hub and PyPI may be blocked. Build with mirrors:

```bash
BASE_IMAGE=docker-mirror.liara.ir/library/python:3.12-slim PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple docker compose build
```

## Lint

```bash
uvx ruff@0.8.4 check starcoach tests
```

## Tests

All tests run offline. They use a small real sample of the dataset in `tests/fixtures/mini/`
(made by `tests/fixtures/make_mini.py`).

```bash
uv run pytest
```

## Docs

- `docs/REVIEW.md` — **reviewer guide**: what it does, requirement → evidence, architecture, results, limits, demo script
- `docs/requirements.md` — the challenge text
- `docs/ROADMAP.md` — phases and what each one delivers
- `docs/PROGRESS.md` — what shipped, with proof
- `docs/DECISIONS.md` — decisions and checked facts
- `docs/research/` — background research
