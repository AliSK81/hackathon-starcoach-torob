# Research index

| File | Topic | Serves |
|---|---|---|
| [01-dataset.md](01-dataset.md) | Deep profile of shops, products, offers: joins, address parsing, hours, prices, timestamps, text, payment, missing fields, demo scenarios | Dataset 20; Product 75 (transparency); Phase 1 |
| [02-challenge-context.md](02-challenge-context.md) | The StarCoach hackathon, Torob's in-store features, TorobPay, Kalabarg, Tehran shopping pain points, neighbourhoods | Product 75; Intelligence 50; the four-step flow (D5) |
| [03-persian-search.md](03-persian-search.md) | Persian normalization, SQLite FTS5, price parsing in queries, embeddings, typos, brand aliases | Product 75 (search); Technical 40 |
| [04-llm-agent.md](04-llm-agent.md) | LLM access from Iran, OpenAI-compatible client, agent tools, no-key fallback, logging, evaluation | Intelligence 50; Technical 40 |
| [05-ux-rtl-maps.md](05-ux-rtl-maps.md) | No-build frontend, Persian typography and formatting, maps and navigation links in Iran, shopping-assistant UX patterns, contact links | UX 75; Product 75 |
| [06-deploy.md](06-deploy.md) | Iranian PaaS (Liara, …), VPS, data shipping, Dockerfile, stability kit | Deploy 40 |

Scripts behind the numbers: `scripts/` (01-dataset, 03-search, `profile.py`).

## Consolidated design

1. **One clean SQLite DB built offline** from the CSVs; never guess at request time (01, 03).
2. **Search = own normalizer + FTS5 unicode61 + alias table + re-ranking**; no NLP library, no embeddings in v1 (03).
3. **Transparency is a feature:** recorded price, last price change, and "stock not confirmed" are always separate; unknown is shown as unknown with a reason (01 §5–8, 05 §4).
4. **Data gaps are real:** no store images, licences, messengers, stock, Kalabarg, or price unit (01 §8). Phones are fake. Show these as unknown.
5. **Location = passage, floor, unit** parsed from the address (≈63% / 65% / 91%) plus coordinates; most shops sit within 1 km downtown, so walking routes inside and between passages matter (01 §2–3, 02 §4).
6. **Hours are three-valued** (open / closed / unknown); Friday is mostly closed; Tehran is UTC+3:30 (01 §4).
7. **Assistant: rules first, LLM optional.** A Persian rule parser gives filters; an OpenAI-compatible LLM (via an Iranian gateway) may refine; the LLM never invents prices or hours — the UI shows DB values only (04).
8. **Frontend without a build step**, self-hosted assets, Persian `Intl` formatting, Neshan links for navigation (05).
9. **Deploy inside Iran** (Docker; Liara is a hackathon sponsor), DB shipped as a file, read-only, health checks and smoke tests (06).

## Conflicts and gaps

| Topic | Conflict / gap | How we check |
|---|---|---|
| Four-step flow | Not public anywhere (02); D5 is a guess | Ask the user (asked) |
| TorobPay | Public sources say online-only 4-installment BNPL; the data has `channel: in_person` for 50 shops (02 §5, 01 §8) | Show the channel as recorded; label `unknown` channel as "not declared" |
| Frontend library | 05 recommends Preact+htm; we chose plain JS (fewest libraries) | Revisit if the UI code gets hard to change |
| Suspicious price count | 01 says 2,223; our build flags 2,698 (different comparison base) | Recorded in Change 3; only a badge |
| Judges inside Iran? | Decides Iran-hosted vs abroad (06, 05) | Ask the user; default to Iran-hosted |
| Gateway tool calling | AvalAI/Liara document it; Metis/GapGPT unverified (04) | Live smoke test once a key exists |
