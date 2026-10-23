# Phase 9 — Organizer clarifications (R26–R31)

## Goal
- Cover the expectations the organizers added in the group Q&A (`docs/requirements.md` §9).

## Choices
- **R26 hubs, dataset first (R28):** (1) passages/areas with the most sellers of the category in our data; (2) the Balad list of Tehran trade hubs cited in research 02 §4, labeled «دانش عمومی (بلد)»; (3) only if both are empty, the LLM's own knowledge, labeled «پیشنهاد هوش مصنوعی؛ بررسی کنید». Location widget = a mini-map drawn from our own data (SVG; no map tiles, so it works where tile servers are blocked) + Neshan / Google links. An OpenStreetMap iframe was tried first; it could not be confirmed to load in the test browser.
- **R27 two-sided contact (mock):** a seller panel page (`#/seller/<shop_id>`) lists questions from buyers with one-tap answers; the buyer's card updates when the seller answers; the automatic simulated reply stays as the fallback.
- **R29 reviews:** no reviews in the data. Show (a) data signals that act like reviews (sellers count, price spread, warranty share, price freshness) and (b) an LLM "what to check before buying" summary from the specs, labeled as AI, never as user reviews.
- **R30:** category-specific components where data supports them (e.g. clothing/shoes: size and for-whom; phones: memory/RAM chips).
- **R31:** website / Instagram links for the 112 real-named shops (already on shop pages); mark them in seller cards.

## Checklist
- [x] R26 hubs API + card on product and empty search, with map widget
- [x] R27 seller panel + buyer status update
- [ ] R29 review summary (data signals + labeled AI summary)
- [ ] R30 category components
- [ ] R31 online-presence badge
- [ ] Re-run the audit for R26–R31
