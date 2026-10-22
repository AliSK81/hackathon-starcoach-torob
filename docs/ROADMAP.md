# Roadmap

## Goal
- A Persian, mobile-first assistant for in-store shopping in Tehran stores and passages.
- It covers the full trip: state the need → find and compare products → pick a seller and plan the visit → follow up with the seller (D5).
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
| 0 | The project runs | not started | [phase-0](phases/phase-0-runs.md) |
| 1 | Data import | not started | — |
| 2 | Thin end-to-end: search → product → sellers → store | not started | — |
| 3 | Docker and first deploy | not started | — |
| 4 | Filters, area and comparison | not started | — |
| 5 | Assistant: understand the need | not started | — |
| 6 | Visit plan, substitution and seller follow-up | not started | — |
| 7 | Evaluation and reviewer doc | not started | — |
| 8 | Release: audit, final deploy, tag | not started | — |

## Requirement → phase

| Requirement or score item (`docs/requirements.md`) | Phase |
|---|---|
| Dataset must be used (shops, products, offers) | 1, 2 |
| Store info: ID, name, category, description; images, history, licenses where present | 1, 2 (show what exists; mark missing fields) |
| Location: address, coordinates, passage / floor / unit | 1, 2, 4 |
| Weekly working hours | 1, 4, 6 |
| Contact channels (phone, messengers) | 2, 6 |
| Product: ID, titles, brand, category, specs, images | 1, 2 |
| Product in store: sellers per product, store's products, seller title, price, warranty, last price change | 1, 2, 4 |
| Category alone ≠ product in stock | 2, 4 |
| Purchase conditions: TorobPay, installments, Kalabarg, express delivery, info type made clear | 1, 4 |
| UX: cards, filters, buttons, not only chat | 2, 4, 5 |
| UX: clear search and comparison; why suggested; next step | 2, 4, 5 |
| UX: change area, budget, purchase conditions and see the result | 4 |
| Transparency: price vs price-change time vs confirmed availability kept apart | 2, 6 |
| Transparency: unknown info shown clearly | 2 |
| Persian, RTL, mobile | 0, 2 |
| Product score 75: search, compare, seller in area, follow-up | 2, 4, 6 |
| UX score 75 | 2, 4, 5 |
| Intelligence score 50: follow-up, substitution, visit conditions | 5, 6 |
| Deploy score 40 | 3, 8 |
| Technical score 40: structure, tools, performance | 0, 1, 7 |
| Dataset score 20: correct and transparent use | 1, 2, 7 |
| Demo video deliverable: the app must be demo-ready, with a scenario in the reviewer doc | 7, 8 |

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
- **Done when:** `docker compose up` runs the app with the DB; a smoke test passes against the container; it runs on the chosen host if the user has given one.
- **Not yet:** no CI polish, no custom domain.

### Phase 4 — Filters, area and comparison
- **Why:** the user must change area, budget and purchase terms and see the result.
- **Done when:** filters for area, budget, open now / at a time, TorobPay, installments, fast delivery and warranty work and change results; sellers sort by price or distance; a compare view shows 2–3 products side by side; each result says why it was suggested.
- **Not yet:** no free-text assistant.

### Phase 5 — Assistant: understand the need
- **Why:** intelligence score; fewer steps for the user.
- **Done when:** a Persian sentence becomes filters (product, brand, budget, area, time, payment) with a rule-based parser; an optional LLM improves it when a key is set; answers are cards built from DB data only; an offline eval set measures parser accuracy against a baseline.
- **Not yet:** no follow-up flows.

### Phase 6 — Visit plan, substitution and seller follow-up
- **Why:** intelligence score: follow-up, substitution, visit conditions.
- **Done when:** the user can save items to a visit plan; the plan orders stores by location and opening hours and warns about closed stores; alternatives are offered when a product is over budget, far, or the store is closed; a follow-up drafts a message to the seller and tracks its status (simulated replies, labeled).
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
