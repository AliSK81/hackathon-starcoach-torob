# Phase 5 — Assistant: understand the need

## Goal
- A Persian sentence becomes the same filters the chips set: product words, budget, area/passage, visit time, conditions.
- The user sees what was understood, as editable chips, and gets product cards at once (no LLM wait).
- When the user doesn't know the model (R1), the assistant asks a few data-driven questions and shortlists models.
- With an LLM key, the LLM refines the parse and explains choices; it never invents prices or hours (research 04 §3.3).

## Choices
- Rules first (`starcoach/intent.py`): price parser from research 03 §3.2, area/passage gazetteer from the DB, time and payment keywords (research 04 §4.2).
- Ambiguous values (bare «تومن») are resolved by the category median and flagged, so the UI can ask.
- Eval: a fixed set of labeled Persian requests in `tests/data/intents.jsonl`, split dev / held-out test; baseline = no parsing (raw text into search). Results to `results/intent-eval.json`.
- LLM: stdlib HTTP client for any OpenAI-compatible gateway (D10); thinking off; one tool call to fill filters; Pydantic-free validation by our own code; JSONL log without keys; rules answer when the LLM fails or is slow.
- Guided choice: facets from the category's own data (price bands, top brands, spec keys with few values).

## Checklist
- [x] Rule parser: budget, area/passage, time, conditions, product words
- [x] Eval set + `starcoach eval-intents` with baseline and held-out split
- [ ] `/api/ask` + assistant box in the UI with "understood" chips
- [ ] LLM client + refine step with fallback; logged
- [ ] Guided model choice (R1)
- [ ] Check real output on the demo scenarios
