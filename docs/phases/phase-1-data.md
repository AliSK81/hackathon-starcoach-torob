# Phase 1 — Data import

## Goal
- `starcoach build-db` turns the three CSVs into one SQLite DB that the app reads.
- Fields are cleaned once, at build time, so the app never guesses.

## Choices
- Own Persian normalizer, no NLP library (research 03 §1.4).
- SQLite FTS5 `unicode61` over normalized title + brand + brand aliases + category (03 §2.4). No trigram, no embeddings.
- Price status per offer: `ok`, `call` (null or ≤ 10), `invalid` (> 1e10), `suspicious` (outside median/3…3×median when ≥ 3 sellers) (F15).
- Address parsed into passage, floor, unit, plaque; raw address kept (01 §2).
- Hours cleaned: drop `00:00–00:00` padding and shifts under 30 min; status open / closed / unknown (F16).
- Bad rows are logged to `logs/build.jsonl` and skipped. The build never stops on one row.

## Checklist
- [x] Normalizer `starcoach/textnorm.py` with tests
- [x] `build-db`: shops, products, offers tables with cleaned prices and warranty
- [x] Address parser (passage, floor, unit, plaque) with tests
- [x] Hours parser and `is_open_at` (open / closed / unknown) with tests
- [x] FTS5 index and `starcoach search "<query>"`
- [x] `starcoach stats` prints counts that match F1
- [x] Check real output: 10 demo queries give sensible top results
