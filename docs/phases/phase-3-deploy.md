# Phase 3 — Docker and first deploy

## Goal
- The same image runs locally and on a server, with the DB on a mounted disk.
- One command proves a running instance works: `starcoach smoke --url <base>`.

## Choices
- `python:3.12-slim`, installed with pip from `pyproject.toml`. Base image and PyPI index are build args, so an Iranian mirror can be used (F24).
- The DB is not inside the image. It lives on a volume at `/data/starcoach.db` (research 06 §2). If the CSVs are on the volume and the DB is missing, the container builds it at start.
- Non-root user, Docker `HEALTHCHECK` on `/health`, `restart: unless-stopped`.
- `/ready` returns 503 until the DB is present; `/health` is always 200.
- Host: the user's choice (asked). Default plan: Liara (sponsor, F23) with a disk at `/data`.

## Checklist
- [x] `/ready` endpoint
- [x] `starcoach smoke --url` checks health, search, product, shop, with timings, and logs to `logs/smoke.jsonl`
- [x] `Dockerfile`, `.dockerignore`, `docker-compose.yml`
- [x] `docker compose up` locally + smoke test passes
- [x] `starcoach pack-db` makes a compressed DB file with a SHA256 for upload
- [ ] Deploy on the user's host + smoke test (blocked on the host answer)
