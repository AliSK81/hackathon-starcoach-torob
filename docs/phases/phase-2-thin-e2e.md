# Phase 2 — Thin end-to-end

## Goal
- On a phone screen: type a Persian query → product cards → a product's sellers → a store page.
- Every value says what it is: recorded price, price-change time, and "stock not confirmed" are separate.
- Unknown values say «نامشخص» (or why), never blank.

## Choices
- JSON API in FastAPI: `/api/search`, `/api/products/{id}`, `/api/shops/{id}`. One read-only SQLite connection per request.
- Frontend: plain HTML/CSS/JS, no library and no build step (fewest libraries; research 05 suggested Preact+htm, but the views are simple enough). Hash routes: `#/search?q=`, `#/p/<id>`, `#/s/<id>`.
- System Persian fonts first (`Vazirmatn` if installed, then Tahoma). Self-hosting a font is a later change.
- Persian digits and Toman formatting with `Intl` `fa-IR` (research 05 §2).
- Navigation link: Neshan `https://nshn.ir/?lat=..&lng=..` (research 05 §3); contact `tel:` marked as a demo number (F2).

## Checklist
- [x] API: search, product with offers grouped by shop, shop with its products
- [ ] Search page with product cards
- [ ] Product page with seller list
- [ ] Shop page: address parts, hours, payment, contact, map link
- [ ] Transparency labels and «نامشخص» everywhere a value is missing
- [ ] Check at 375 px width in the browser
