# Phase 7 — Evaluation and reviewer doc

## Goal
- A reviewer can check every claim: one command regenerates the result files; the reviewer doc explains what, why and how well.

## Choices
- `starcoach results` regenerates the offline results (DB stats, search demo, request-parser eval, guide demo, filter demo, visit demo) into `results/`. LLM results need a key and are regenerated with `eval-intents --with-llm`.
- Reviewer doc: `docs/REVIEW.md` (English), with a requirement → evidence table (R1–R25), architecture, main logic, choices, how to run and check, real numbers, honest limits, and a demo script for the video.

## Checklist
- [x] `starcoach results`
- [x] `docs/REVIEW.md`
- [x] README links the reviewer doc
