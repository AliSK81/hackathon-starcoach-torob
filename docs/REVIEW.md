# StarCoach — reviewer guide

A Persian, mobile-first assistant for in-person shopping in Tehran's stores and passages, built on the Torob dataset.
It follows the four steps of the challenge video: **choose the product → find stores near you → compare stores → contact stores**, and recovers quickly when a store is closed or doesn't answer.

- Code: `starcoach/` (Python, FastAPI, SQLite) and `starcoach/web/` (plain HTML/CSS/JS, no build step).
- Every number below comes from a command in this repo; result files are in `results/`.
- Requirements and their IDs (R1–R25): `docs/requirements.md` §9.

---

## 1. Run it and check it

```bash
uv sync
uv run starcoach build-db        # CSVs in data/torob-dataset/ -> data/starcoach.db (~50 s)
uv run starcoach serve           # http://127.0.0.1:8000 — open it at phone width
uv run pytest                    # 74 offline tests
uv run starcoach results         # regenerates results/*.txt|json from the DB (~2 s)
uv run starcoach smoke --url http://127.0.0.1:8000
```

Docker: `docker compose up -d --build` (the DB is mounted from `./data`; see README).
Optional LLM: set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env` (any OpenAI-compatible gateway). Without it, everything except the LLM refinement works.

## 2. What the user can do (the four steps)

| Step (video) | Screen / action | How it works |
|---|---|---|
| 1. Find the right product | Type a sentence («گوشی سامسونگ زیر ۲۰۰ میلیون قسطی تو علاءالدین»); or «نمیدونم چه مدلی هندزفری بخرم» → guided questions | Rule parser turns the sentence into filters shown as removable chips; free descriptions go to the LLM in the background. Guided choice asks questions built from the category's own data and shortlists 3 models; compare up to 3 side by side. |
| 2. Find stores that have it, near you | Product page: sellers with passage / floor / unit, distance, open status | Only shops with an offer for the product are listed (category alone ≠ in stock). Area, passage or "near me" + radius. |
| 3. Compare stores | «⭐ پیشنهاد دستیار» picks one seller and says why (and why not the cheapest); sellers sorted by price or distance; "why" chips; filters for budget, visit time, installments, TorobPay, in-person payment, fast delivery, warranty | All reasons come from data (cheapest, open at visit time, distance, installments, warranty, price freshness). Empty results offer one-tap "drop this filter" fixes. |
| 4. Contact stores | «از فروشنده بپرس» or «🤖 از ۳ فروشنده‌ی اول بپرس» | The agent drafts the message from chosen questions and reports replies: in stock, today's price, closing time, hold. Phones in the data are fake, so replies are **simulated and labeled**. No answer / out of stock / closed → alternatives at once. |
| + Browse a passage | type «پاساژ علاءالدین» or tap a passage name | Floor-by-floor list of shops: unit, what they sell, open at the visit time. |
| + Plan the visit | «🗺 برنامه‌ی بازدید» | Orders stops into a walk, checks each is open on arrival, warns early, and shows where the shop is inside the passage. |

## 3. Requirement → evidence

| ID | Requirement | Evidence |
|---|---|---|
| R1 | Help choose the model | `/api/guide`, guide page; `results/guide-demo.txt` (e.g. «کتونی» → 850 models → budget / brand / for whom) |
| R2 | Stores that carry the product | product page lists only shops with an offer; `api.product` |
| R3 | Use the user's location | "near me" / passage / area + radius; distance sort; `results/filters-demo.txt` |
| R4 | Compare stores by price, distance, hours | seller sort + reasons; compare page; visit plan arrival checks |
| R5 | Help contact stores | contact sheet; `tel:` link marked as demo number |
| R6 | Agent contacts stores, reports back | `POST /api/contact`, «از ۳ فروشنده‌ی اول بپرس»; `results/visit-demo.txt` |
| R7 | No answer / closed → alternatives fast | `/api/alternatives` (same passage first, open at visit time, then substitutes, then same-category shops marked stock-unknown); relax hints for empty filters |
| R8 | Precise location inside the passage | passage page (floor by floor); address parser (passage 62.6%, floor 65.3%, unit/plaque 90.8% of shops); «کجای پاساژ؟» with floor neighbours |
| R9 | Installment-only filter | `installments=1` (TorobPay, Snapp Pay, Digipay, Tara, Azki Vam); charger 11/59 sellers, S25 FE 2/34 |
| R10 | Use the dataset correctly | `starcoach stats` = 6,476 / 225,903 / 331,506 rows; joins checked (F13) |
| R11 | Store info, missing shown as missing | shop page; missing fields listed in F19 shown as «نامشخص» |
| R12 | Address, coordinates, hours, contact | shop page: parsed address, Neshan/Google links, weekly hours, phone (demo) |
| R13 | Product info | product page: image, brand, category, specs |
| R14 | Sellers per product, products per shop, price, warranty, last change | product page and shop page |
| R15 | Category alone ≠ in stock | category-only shops never appear as sellers; shop page says so |
| R16 | TorobPay, installments, Kalabarg, fast delivery, info type clear | payment list with «پرداخت حضوری» vs «نحوه پرداخت اعلام نشده»; Kalabarg «اطلاعاتی در داده نیست» |
| R17 | Not only chat | chips, sheet, cards, buttons; chat-like input is optional |
| R18 | Why suggested + next step | reason chips on every seller; buttons for contact / plan / alternatives |
| R19 | Change area, budget, conditions easily | sticky chip bar + sheet; sentence chips removable with ✕ |
| R20 | Recorded price ≠ change time ≠ confirmed stock | three separate lines/chips; «موجودی تأیید نشده» banner; confirmed only after a (simulated) reply |
| R21 | Unknown shown clearly | «نامشخص», «ساعت کاری ثبت نشده», «قیمت ثبت نشده؛ استعلام تلفنی» |
| R22 | Persian, RTL, mobile | `dir="rtl"`, `fa-IR` numbers and dates, checked at 375 × 812 |
| R23 | Deployed and stable | Docker image, `/health`, `/ready`, healthcheck, `starcoach smoke`; public deploy parked by the team (D11) |
| R24 | Code structure, tools, performance | one module per capability, one CLI command per capability, 74 tests, ruff clean; timings below |
| R25 | Demo-ready | §8 demo script |
| R26 | Which bazaar sells what + location widget | `/api/hubs`: dataset hubs first, then a cited Balad list, then the LLM (labeled); hubs card on product pages and empty searches; self-drawn mini-map |
| R27 | Seller contact easy for both sides | buyer question → seller panel (`#/seller/<id>`, one-tap answers) → buyer's chat updates; answers reused for 3 h so the seller isn't asked twice; automatic simulated reply as fallback |
| R29 | A useful, honest product review | «بررسی کالا»: market signals from the data + an AI summary (strengths, weaknesses, in-shop checklist) labeled «نظر واقعی خریداران نیست» |
| R30 | Category-specific components | colour / size chips parsed from sellers' variant titles (shoes, clothing, furniture), filtering sellers to the chosen variant and its price; guided questions use category-specific facets («برای چه کسی؟» for shoes and watches) |
| R31 | Website / Instagram shops | «فروشگاه با صفحه‌ی آنلاین» badge with Instagram / website links on seller cards and shop pages |

## 4. Architecture

```
CSV (shops, products, offers)
   │  starcoach build-db  (clean once: prices, warranty, payment, address, hours; FTS5 index)
   ▼
SQLite (read-only at runtime, 382 MB)
   │
FastAPI ── /api/search  /api/products/{id}  /api/shops/{id}  /api/compare  /api/areas
   │       /api/ask (rules [+ LLM])  /api/guide  /api/alternatives  /api/contact  /api/plan
   │       /api/ai/*  (async ✨ layer: search, pick, guide, alternatives, directions)  /api/agent (SSE)
   │       /api/shops/{id}/where  /health  /ready
   ▼
web app (index.html + ai.js + app.js + app.css, hash routes, localStorage for the user's context, compare list, plan, contacts)
```

| Module | Job |
|---|---|
| `textnorm.py` | Persian normalization (Arabic letters, digits, ZWNJ, diacritics) for search keys |
| `build.py`, `db.py` | CSV → SQLite; price status (ok / suspicious / call / invalid); warranty kind; payment; aggregates |
| `address.py` | passage (canonical), floor, unit, plaque from free-text addresses |
| `hours.py` | weekly hours cleaned; `is_open_at` → open / closed / unknown; Persian status text |
| `search.py` | FTS5 + alias table (آیفون↔iphone, جی بی ال↔jbl, …) + re-ranking |
| `filters.py` | user filters, matching, distance, data-only reasons, relax hints |
| `api.py` | read model for the app (transparency labels live here) |
| `intent.py` | rule-based request parser (budget, place, time, conditions, intent) |
| `llm.py` | OpenAI-compatible client; LLM refinement merged with rules |
| `ai.py` | async AI layer: search reading + widening + re-rank, pick summary, guide mapping and picks, alternatives, directions; caches, gate, text guards |
| `agent.py` | shopping agent: bounded tool loop over the read model, short refs, server-built cards, number and stock guards |
| `ai_demo.py` | `starcoach ai-demo`: live evidence in `results/ai-demo.txt` |
| `guide.py` | guided model choice |
| `visit.py` | alternatives, substitutes, in-passage location, visit plan |
| `contact.py` | message draft + simulated seller reply |
| `evaluate.py`, `results.py`, `smoke.py` | evaluation, result files, deploy smoke test |

## 5. Main logic and why

- **Clean once, at build time.** Junk prices are classified, not shown as real: 1 Toman = "call for price" (635 offers), > 1e10 = invalid (211), far from the product median = "suspicious" (2,698; shown with a warning and sorted after normal prices). Rial-typed-as-Toman cases are caught by the median rule.
- **Search.** A hand-written normalizer plus SQLite FTS5 (`unicode61`) beat the alternatives measured in research 03 (trigram: bigger, slower, misses 2-letter tokens; embeddings: no clear gain). Ranking fixes measured failures: product-type head word boost («گوشی سامسونگ» → phones, not batteries), accessory penalty, popularity; multi-word aliases collapsed («جی بی ال» → `jbl`).
- **Filters are one object.** Chips, the sentence parser and the LLM all produce the same filters, so the user can always see and undo them.
- **Three-valued hours.** Unknown is never treated as open; 2,003 shops have no hours.
- **Rules first, LLM second (D12).** Measured: the LLM alone drops slots; merged it helps on free descriptions (table below).
- **AI next to the rules, never in front (D14).** Every screen paints from the rules in milliseconds; the AI fills `✨` cards a few seconds later from a cache-backed, capped LLM path. Measured: normal search 11–38 ms while an AI call ran 4.2 s. No embedding model exists on the gateway (F31), so AI search widens with LLM-suggested phrases run through the same FTS search under the same filters and then re-ranks those real candidates; it surfaced 20 products the keyword list had missed on 7 queries (F32).
- **The agent can only show what the DB returned (D15).** It reasons over short refs; the server builds every card; price-sized numbers must match tool output; «in stock» is dropped unless a seller answered through the simulated channel; the simulation is labeled everywhere. The rule parser applies budget, place, time and payment before the LLM runs.
- **Simulated contact, honestly labeled (D6).** Store phones are fake (F2), so the agent cannot really message. Replies are deterministic per offer and day and grounded in data (fresh price → likely in stock, old price → likely changed), and always marked «پاسخ نمایشی».

## 6. Results (real numbers)

**Data** (`results/stats.json`, `results/build-db.json`): 6,476 shops (3,792 with offers, 112 real names), 225,903 products, 331,506 offers; price status ok 312,868 / suspicious 2,698 / call 15,729 / invalid 211. Build 48 s, DB 382 MB (97.9 MB gzip).

**Search** (`results/search-demo-queries.txt`): 12 demo queries, all with a sensible top 3; ~10 ms mean.

**Request understanding** (slot accuracy; `results/intent-eval-*.json`; 63 labeled requests):

| split | baseline (no parsing) | rules | rules + LLM |
|---|---|---|---|
| dev (30) | 0.469 | 1.00 | 0.984 |
| test (15, held out) | 0.429 | 1.00 | 1.00 |
| hard (10 free descriptions) | 0.28 | 0.88 | 0.96 |
| hard2 (8 messy requests; rules 0.80 while held out) | 0.421 | 0.90 | 0.90 |

The LLM *replacing* the rules scored 0.423 on hard (F29); that is why the LLM only fills gaps.

**Speed** (full DB, laptop): search 3–25 ms; product page 1–4 ms; compare / guide 0.15–0.5 s; LLM step 0.8–1.8 s (thinking off, F27). Docker smoke: all checks < 100 ms.

**Scenarios** (`results/filters-demo.txt`, `results/visit-demo.txt`, `results/guide-demo.txt`):
- Apple 20W charger: 59 sellers → installments only 11 → open + installments + within 500 m of Alaeddin 7.
- Galaxy S25 FE in Alaeddin, Saturday 11:00: 8 sellers; the agent asks the cheapest 3; if one doesn't answer, 30 open alternatives, same passage first; a 3-stop walk of ~100–200 m.

## 7. Honest limits

- Seller replies are simulated (phones are fake). Real contact would need a messaging channel the dataset doesn't have.
- Hours are as declared by shops; public holidays are not in the data.
- No store images, licences, stock, Kalabarg or price unit in the dataset (F19); shown as unknown.
- Labeled requests were written by the same team as the parser; the held-out test is small. The "hard" split is the most realistic and is where the numbers are lower.
- Typo correction covers words of 3+ letters missing from the index; very short typos are left alone.
- Public deployment is parked (D11); the Docker image and smoke test are ready.

## 8. Demo script (about 5 minutes)

1. **Home (15 s).** Phone-width screen; say what the app is; point at the note that prices are recorded prices and stock is not confirmed; point at «✨ گفت‌وگو با دستیار هوشمند».
2. **AI search (50 s).** Type «برای دویدن هندزفری». The normal list appears at once; a few seconds later the ✨ card shows the reading, picks with reasons and «فقط با دستیار پیدا شد» on items keyword search missed. Then «گوشیم بیرون زود خالی میشه» → power banks. Then «کابل» → the clarifying question.
3. **The agent (90 s).** Tap «✨ دستیار»: «نمیدونم چه هندزفری‌ای بخرم؛ برای ورزش، حدود ۳ میلیون» → budget chip applied, 3 cards, one question; tap «مقایسه این سه مدل». Then «شارژر اپل ۲۰ وات قسطی نزدیک علاءالدین؛ از دو فروشنده بپرس موجوده؟» → watch the steps (rules → search → sellers → ask → alternatives), the labeled-simulated answers and the alternatives.
4. **Guide in your own words (30 s).** Guide for «هندزفری» → «برای ورزش و دویدن، ضد عرق، بودجه کم» → budget mapped, 3 AI picks with a trade-off each.
5. **A sentence with filters (40 s).** Tap «گوشی سامسونگ زیر ۲۰۰ میلیون قسطی تو علاءالدین»: chips, «only phones» focus, relax buttons.
6. **Sellers (40 s).** Open a product; read «⭐ پیشنهاد دستیار» and its ✨ summary and what to ask the seller; seller cards: recorded price + age, open status, passage / floor / unit.
7. **Seller panel (25 s).** «از فروشنده بپرس» → second tab «پنل فروشنده (نمایشی)» → one tap answer → the buyer's chat updates.
8. **Plan and where in the passage (25 s).** Add stops → «🗺 برنامه‌ی بازدید»; «کجای پاساژ؟» with the ✨ directions line.
9. **Where it is sold (15 s).** Agent: «کت و شلوار مردانه کجا بخرم؟» → hubs card with map.
10. **Close (10 s).** Tests, evaluation numbers, `results/ai-demo.txt`, Docker smoke test.
