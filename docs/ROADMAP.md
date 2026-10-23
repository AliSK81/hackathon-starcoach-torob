# Roadmap

## Goal
- A Persian, mobile-first assistant for in-store shopping in Tehran stores and passages.
- It covers the four steps from the challenge video (D9): choose the product → find stores nearby → compare stores → contact stores, with fast alternatives when a store fails.
- It uses the Torob dataset correctly and shows what is known, what is old, and what is unknown.
- It runs on a public server, stable, from one command.
- It is judged on: Product 75, UX 75, Intelligence 50, Deploy 40, Technical 40, Dataset 20 (`docs/requirements.md`).

## Rules for every phase
1. **Always keep it working.** Every commit runs and can be shown. Thin version first, then improve.
2. **Small patches.** One change = one idea. Many small commits beat one big one.
3. **Don't design ahead.** Plan only the phase you are starting.
4. **Measure, don't guess.** Limits, prices, formats, rules come from the real system. Write them as `F` facts with their source.
5. **Check results, not only code.** Before a phase is `done`, look at its real output and ask: does this meet the requirement, or earn the score? If an output looks odd or always the same, find out why. Fix it before the next phase.
6. **Test honestly.** Test on data you did not tune on. Compare with a simple baseline. Keep only what holds up. Record what failed too (as `F` facts).
7. **Log everything.** Every run, decision and error goes to an append-only log (JSONL) on disk. Save results to `results/`, so anyone can check them.
8. **Survive errors.** Long-running parts log the error and go on. They never crash on one bad input. They never record the same event twice after a failure.
9. **Every capability is a command.** One CLI subcommand per capability, so each one can be run and shown alone.
10. **Blocked? Don't wait.** If a change needs something from the user, add it to "What we need from the user", ask once, and work on the next unblocked phase.
11. **Tag what ships for real.** Any version used for the real thing gets a git tag.
12. **Clean as you go.** After a few changes, run a lint pass and small refactors as their own commits. Fix bugs found in real runs at once, with a test.

## Status

| Phase | Name | Status | Plan |
|---|---|---|---|
| 0 | The project runs | done | [phase-0](phases/phase-0-runs.md) |
| 1 | Data import | done | [phase-1](phases/phase-1-data.md) |
| 2 | Thin end-to-end: search → product → sellers → store | done | [phase-2](phases/phase-2-thin-e2e.md) |
| 3 | Docker and first deploy | parked (D11): image ready, public deploy in Phase 8 | [phase-3](phases/phase-3-deploy.md) |
| 4 | Filters, area and comparison | done | [phase-4](phases/phase-4-filters.md) |
| 5 | Assistant: understand the need | done | [phase-5](phases/phase-5-assistant.md) |
| 6 | Visit plan, substitution and seller follow-up | not started | — |
| 7 | Evaluation and reviewer doc | not started | — |
| 8 | Release: audit, final deploy, tag | not started | — |

## Requirement → phase

IDs are from `docs/requirements.md` §9. Nothing is left without a phase.

| ID | Requirement (short) | Phase |
|---|---|---|
| R1 | Help choose a product/model when the user doesn't know it | 5 |
| R2 | Find stores that carry the product (offer, not just category) | 2 (done), 4 |
| R3 | Use the user's location: nearby areas and stores | 4 |
| R4 | Compare stores by price, distance, working hours | 4 |
| R5 | Help the user contact stores | 2 (links), 6 |
| R6 | Agent contacts stores to confirm price and stock, reports back | 6 |
| R7 | No answer / closed → quickly suggest alternative stores | 6 |
| R8 | Precise in-passage location (floor, unit, landmarks) | 1 (done), 2 (done), 6 |
| R9 | Installment / credit-purchase-only filter | 4 |
| R10 | Use the Torob dataset correctly | 1 (done), 7 |
| R11 | Store info, with missing fields shown as missing | 2 (done) |
| R12 | Address, coordinates, passage/floor/unit, hours, contact | 1, 2 (done) |
| R13 | Product info: titles, brand, category, specs, images | 2 (done) |
| R14 | Product sellers, store products, price, warranty, last change | 2 (done) |
| R15 | Category alone is never "in stock" | 2 (done), 4 |
| R16 | TorobPay, installments, Kalabarg, express delivery, info type clear | 2 (done), 4 |
| R17 | Cards, filters, buttons — not only chat | 2, 4, 5 |
| R18 | Why suggested + next step | 4, 5 |
| R19 | Easy change of area, budget, conditions | 4 |
| R20 | Recorded price / change time / confirmed stock kept apart | 2 (done), 6 |
| R21 | Unknown shown clearly | 2 (done) |
| R22 | Persian, RTL, mobile | 0, 2 (done) |
| R23 | Deployed and stable (Liara suggested) | 3, 8 |
| R24 | Code structure, tools, performance | 0–8, 7 |
| R25 | Demo-ready for a ~5-minute video of the full flow | 7, 8 |

Score items: Product 75 → R1–R9, R14; UX 75 → R17–R22; Intelligence 50 → R1, R6, R7, R4; Deploy 40 → R23; Technical 40 → R24; Dataset 20 → R10–R16, R20, R21.

## Phases

### Phase 0 — The project runs
- **Why:** everything else builds on a runnable skeleton.
- **Done when:** one command starts the server; `/health` answers; one offline test passes; README says how; `.env.example` exists; `data/` and `.env` are ignored.
- **Not yet:** no data import, no UI beyond a placeholder page.

### Phase 1 — Data import
- **Why:** the dataset is the core input and is scored.
- **Done when:** a CLI command builds a SQLite DB from the CSVs; bad rows are logged, not fatal; Persian text is normalized; a search index exists; a `stats` command prints counts that match F1; data-quality flags exist for bogus prices.
- **Not yet:** no ranking tricks, no embeddings.

### Phase 2 — Thin end-to-end
- **Why:** show the whole path early: search → product → sellers → store.
- **Done when:** on a phone-width screen, a Persian query returns product cards; a product page lists sellers with price, price-change age and warranty; a store page shows address, passage/floor/unit, hours, contact and map link; unknown fields say "نامشخص".
- **Not yet:** no chat, no filters beyond the query.

### Phase 3 — Docker and first deploy
- **Why:** deploy is scored on stability; deploying early finds problems early.
- **Done when:** `docker compose up` runs the app with the DB; a smoke test passes against the container; it runs on Liara (suggested by the challenge) or the user's chosen host, and the smoke test passes there.
- **Not yet:** no CI polish, no custom domain.

### Phase 4 — Filters, area and comparison
- **Why:** the user must change area, budget and purchase terms and see the result.
- **Done when:** filters for area or "near me", budget, open now / at a time, TorobPay, installments-only (R9), fast delivery and warranty work and change results; sellers sort by price or distance; a compare view shows 2–3 products side by side; each result says why it was suggested.
- **Not yet:** no free-text assistant.

### Phase 5 — Assistant: understand the need
- **Why:** intelligence score; fewer steps for the user.
- **Done when:** a Persian sentence becomes filters (product, brand, budget, area, time, payment) with a rule-based parser; a user who doesn't know the model gets a few questions and a short list of suitable models (R1); an optional LLM improves it when a key is set; answers are cards built from DB data only; an offline eval set measures parser accuracy against a baseline.
- **Not yet:** no follow-up flows.

### Phase 6 — Visit plan, substitution and seller follow-up
- **Why:** intelligence score: follow-up, substitution, visit conditions.
- **Done when:** the user can save items to a visit plan; the plan orders stores by location and opening hours and warns about closed stores; the agent "contacts" chosen stores to confirm price and stock and reports back (simulated replies, labeled, D6) (R6); when a store doesn't answer or is closed, equivalent stores are suggested at once (R7); the shop's in-passage location is shown as precisely as the data allows (R8).
- **Not yet:** no real messaging to stores.

### Phase 7 — Evaluation and reviewer doc
- **Why:** reviewers need to check claims; technical and dataset scores.
- **Done when:** `results/` holds eval outputs with numbers; the reviewer doc covers architecture, logic, choices, how to run, how to check results, real results, and a demo scenario.
- **Not yet:** —

### Phase 8 — Release
- **Why:** the submitted version must be tagged and stable.
- **Done when:** the line-by-line audit against `docs/requirements.md` passes; a fresh clone runs from the README; all tests pass offline; the deployed version is tagged.
- **Not yet:** —

## Later
- Semantic search with embeddings.
- Price history charts.
- Store photos from Instagram for the 22 stores that have it.
- Multi-store route on a map.
