# Phase 6 — Visit plan, alternatives and seller contact

## Goal
- When a store is closed, doesn't answer, or doesn't have the item, the user gets equivalent stores at once (R7).
- The agent "contacts" a store about stock, current price, hours, warranty, installments, holding the item, and reports back (R5, R6). Phones are fake (F2), so replies are simulated and labeled (D6).
- A visit plan orders the chosen stores into a walk, checks each is open on arrival, and warns early (R4).
- Each stop says where the shop is inside its passage: floor, unit, and neighbouring units (R8).

## Choices
- Alternatives: same product at other sellers (same passage first, then by distance), open at the visit time; then substitute products (same category, similar price, more sellers nearby).
- Contact: the message is a template from chosen questions (the LLM may rephrase it when configured). The simulated reply is deterministic per (offer, day) and built from data: fresh price → likely in stock; old price → may have changed; some sellers don't answer. Every reply is marked «پاسخ نمایشی». Confirmed stock is shown apart from the recorded price (R20).
- State of each contact lives in the browser (`localStorage`); every send and reply is also logged to `logs/contacts.jsonl` with a request id, so a retry never records twice.
- Plan: nearest-neighbour from the start point, same-passage stops kept together and ordered by floor; walking 4.5 km/h; 10 minutes per stop.

## Checklist
- [x] `/api/alternatives` (other sellers, then substitute products) + "جایگزین" on seller cards
- [x] Contact: `/api/contact` (draft + simulated reply), contact sheet in the UI, status on seller cards
- [x] No answer / out of stock / closed → alternatives shown in the same place
- [ ] Visit plan: add stops, `/api/plan`, plan page with arrival times and warnings
- [ ] In-passage location: floor, unit, neighbouring units on the same floor
- [ ] Check real output on the demo scenarios
