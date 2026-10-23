# Phase 4 — Filters, area and comparison

## Goal
- The user sets area (or "near me"), budget, visit time and purchase conditions once; every list updates.
- Every seller says why it is suggested.
- 2–3 products can be compared side by side.

## Choices
- One `Filters` object (`starcoach/filters.py`) parsed from query params, used by search and product pages.
- Budget applies to normal prices only (`ok`), never to «call» or «suspicious».
- Area = `location_label` (31 neighbourhoods) or a passage; "near me" = browser location + distance (haversine).
- Visit time: now, or a chosen day and hour; "open" uses the three-valued hours (unknown is not "open").
- Conditions: installments (any BNPL provider), TorobPay, in-person payment, fast delivery, has warranty.
- Reasons are built from data only (cheapest, open, distance, payment, warranty, fresh price).
- UI: a sticky context bar of chips that opens a filter sheet (`<dialog>`); choices are saved in `localStorage`.

## Checklist
- [x] `Filters` + seller filtering, sorting (price / distance) and reasons on the product page API
- [x] Search filtered by budget, area, open, conditions; cards show matching sellers
- [x] `/api/areas` with shop counts and centers
- [x] UI: context bar + filter sheet; results update
- [ ] Compare view for 2–3 products
- [ ] Check real output for the demo scenarios
