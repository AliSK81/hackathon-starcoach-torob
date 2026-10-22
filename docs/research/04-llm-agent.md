# 04 — LLM agent: provider access, design, fallback, evaluation

Researched 2026-10-22. Prices and model lists change often. Re-check them on the day the key is bought.
Related: `docs/DECISIONS.md` D4 (one OpenAI-compatible client, works without a key), D6 (simulated seller replies), `01-dataset.md` (fields, demo scenarios).

## TL;DR

1. **Anthropic, OpenAI and Google all exclude Iran.** Calls to their APIs from an Iranian server or an Iran-registered account are not an option. An Iranian **OpenAI-compatible gateway** (AvalAI, Liara AI, Metis, GapGPT) is the practical route. All of them resell GPT, Claude and Gemini and take payment in Toman.
2. **Keep D4.** Use one `openai` Python client configured by `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL`, and call Chat Completions with `tools`. Do **not** depend on `strict`, `response_format` or prompt caching. Anthropic's own OpenAI layer ignores all three, and gateways vary. Validate everything with Pydantic and retry once.
3. **Models, cheap and fast tier, per 1M tokens (input / output):**
   - `claude-haiku-5-5`: $0.10 / $0.50
   - `gpt-5-nano`: $0.05 / $0.40
   - `gpt-5-mini`: $0.25 / $2.00
   - `gemini-3.5-flash-lite`: $0.30 / $2.50
   - `gemini-3.8-flash`: $0.75 / $3.75 (promo price)
   - Quality step-up: `claude-sonnet-5-5` at $2 / $10.

   There is **no public Persian benchmark for these exact models**. Choose by running our own 60–100-query eval (§6).
4. **Pattern: deterministic first, LLM refines.**
   - The rule parser and SQL produce cards in under 1 s.
   - The LLM, when a key is set, does four jobs: re-parses messy queries into the **same filter schema**, ranks substitutes from DB candidates, writes a short "why", and drafts the seller message.
   - The LLM **never writes prices, hours or stock**. It references `offer_id` / `shop_id`. The UI renders the values from the DB.
5. **Without a key**, roughly 80–90% of the demo flow can be deterministic: search, filter, compare, open-now, payment, walking plan, substitutes and templated messages. This is an estimate, not a measurement.

---

## 1. Provider access from Iran

### 1.1 First-party providers

| Provider | Iran supported? | Source |
|---|---|---|
| Anthropic (API, apps, and Claude through cloud resellers) | No. Unlisted regions are unsupported. Also excluded: entities owned or controlled from unsupported regions, wherever they are located. | https://www.anthropic.com/supported-countries , https://platform.claude.com/docs/en/api/supported-regions |
| OpenAI API | No. Iran is not on the list. | https://developers.openai.com/api/docs/supported-countries |
| Google Gemini API | No. The list goes from "Iraq" to "Ireland". | https://ai.google.dev/gemini-api/docs/available-regions |
| OpenRouter | Its ToS does not name Iran. §5.7 says some model providers do not authorize users in certain regions, **and it forbids VPNs or proxies to reach those "Restricted Models"**. Breaking §5.7 can end the account. Paying from Iran is a separate obstacle. | https://openrouter.ai/terms |

**Implication:** a foreign key run through a VPN breaks the provider's terms, and the account or deployment can be cut off before the judging day. An Iranian gateway is the low-risk choice for an Iranian deploy server. If the team does have a legitimate account in a supported region with a non-Iranian server, the same client works by changing `LLM_BASE_URL`.

### 1.2 Iranian OpenAI-compatible gateways

| Gateway | Base URL | Chat Completions plus `tools` | Models | Pricing / notes |
|---|---|---|---|---|
| **AvalAI** | `https://api.avalai.ir/v1` (primary); mirror `https://api.avalapis.ir/v1` per a third-party plugin listing | **Yes, documented.** `tools`, `tool_calls`, `role:"tool"`. Strict mode and parallel calls depend on the model or route ("may fall back to best-effort"). Tool search and custom tools are Responses-API only. | Claude (opus-4-8 … haiku-4-5; pricing page also lists `claude-haiku-5-5`, `claude-sonnet-5-5`), GPT (gpt-5.5, gpt-5.6-luna/terra/sol, gpt-5-mini …), Gemini (gemini-3.5-flash, gemini-3.8-flash …) | USD list prices, charged in Toman at the platform's rate. **States a 0% markup** on these models. **Rate-limit tiers:** base tier `claude-haiku-5-5` = **1 RPM** / 10K TPM. Phone verification gives Tier 1 immediately (25 RPM / 50K TPM) plus 200,000 Toman of free credit. Also says the official Anthropic SDK can be used natively. |
| **Liara AI** | Per-project URL `https://ai.liara.ir/api/v1/<project-id>` (the key is created in the console and shown once) | **Yes, documented** ("Function calling", `tool_choice:"auto"`), through the OpenAI SDK and the Vercel AI SDK | Many providers. **Model IDs are provider-prefixed**, e.g. `openai/gpt-4o-mini`, `openai/gpt-4.1` (OpenRouter style). Only models in your plan can be used. | Pricing not on the docs pages fetched. Liara is also an Iranian PaaS, so app and LLM could share one vendor. |
| **Metis** | `https://api.metisai.ir/openai/v1` (OpenAI wrapper). There are separate wrappers per provider (Anthropic, Gemini, DeepSeek …); their URLs were not fetched. | **Unclear.** The OpenAI-wrapper page says the direct-connection mode doesn't support "Metis features such as bots or function calling". That may mean Metis's own bot functions rather than passing `tools` through. **Test before relying on it.** | OpenAI, Anthropic, Gemini, DeepSeek, GLM, Kimi … | Pricing page not fetched |
| **GapGPT** | Not verified: gapgpt.app timed out twice and search found nothing. From memory, possibly `https://api.gapgpt.app/v1`. | Unknown | Unknown | Unknown |

Sources:
- AvalAI: https://docs.avalai.ir/fa/quickstart , https://docs.avalai.ir/fa/guides/function-calling , https://docs.avalai.ir/fa/pricing , https://docs.avalai.ir/fa/rate-limits , mirror via https://wordpress.org/plugins/?p=326903
- Liara: https://docs.liara.ir/ai/about/ , https://docs.liara.ir/ai/quick-start/ , https://docs.liara.ir/ai/foundations/tools/
- Metis: https://docs.metisai.ir/ , http://docs.metisai.ir/api/wrapper/openai/

**Cautions**
- Gateways are resellers of the same restricted providers. Availability can change overnight.
- Support for some features differs per model and route. For tool calls, strict JSON and streaming, the gateway's docs say so (AvalAI) or say nothing (the others). **Run the smoke test in §2.4 against the exact base URL and model before the demo.**
- Use **one gateway and keep a second one configured** as a hot spare. Switching only changes three env vars.
- At AvalAI's base tier (1 RPM for Haiku 5.5), a multi-call agent turn would be throttled. **Verify the phone number (Tier 1) before the demo.**

## 2. Client design

### 2.1 Recommended: one OpenAI-compatible client

```python
# app/llm/client.py  (sketch)
from openai import OpenAI
client = OpenAI(base_url=env.LLM_BASE_URL, api_key=env.LLM_API_KEY,
                timeout=env.LLM_TIMEOUT_S or 12, max_retries=1)
resp = client.chat.completions.create(
    model=env.LLM_MODEL, messages=msgs, tools=TOOLS, tool_choice="auto",
    max_tokens=700, temperature=None,          # omit temperature: Claude 4.7+ rejects values < 1 via the OpenAI layer
    parallel_tool_calls=True)
```

- `LLM_ENABLED = bool(LLM_BASE_URL and LLM_API_KEY and LLM_MODEL)`. If false, use the rule path (§4) only.
- Read `resp.usage.prompt_tokens` / `completion_tokens` for logging and cost.
- **Don't send `temperature` or `top_p` by default.** Through Anthropic's OpenAI layer, Claude 4.7+ returns 400 for `temperature` < 1 or for `top_p` ≠ default. Gateways may or may not pass these through.
- **Don't force a tool call** (`tool_choice:"required"` or a named function). Claude Opus 5.5 and Sonnet 5.5 return an error for it. Use `"auto"` and steer through the prompt.
- **Don't rely on `strict: true` or `response_format`.** Anthropic's compatibility layer *ignores* both, and AvalAI says strict "may fall back to best-effort". Parse the arguments with `json.loads` and validate them with a Pydantic model. On failure, send one repair message ("arguments invalid: <error>"), then fall back to the rule result.
- Persian text in tool arguments: always `json.loads` and never string-match. Escaping differs between models.

Source for the Anthropic-layer behaviour: https://platform.claude.com/docs/en/api/openai-sdk — strict ignored, `response_format` ignored, no prompt caching, system messages hoisted, forced tool use errors on Opus/Sonnet 5.5. The layer itself is labelled "primarily intended to test and compare… not… production-ready". Gemini's equivalent is `https://generativelanguage.googleapis.com/v1beta/openai/`, with tools and structured output supported (https://ai.google.dev/gemini-api/docs/openai).

### 2.2 Native Anthropic SDK compared

| | OpenAI-compatible client | Native `anthropic` SDK |
|---|---|---|
| Works through Iranian gateways | **Yes** (their primary interface) | Only where the gateway exposes `/v1/messages`. AvalAI says it does; base URL not verified. |
| Switch providers or models | Change env only | Claude only |
| Strict tool schemas / structured outputs | Best-effort | `strict: true`, `output_config.format` guaranteed |
| Prompt caching | Provider-automatic at most | Explicit `cache_control` |
| Thinking / effort control | Mostly ignored | Full |

**Verdict:** for a hackathon demo that must run from Iran on an unknown provider, the OpenAI-compatible client wins. The native SDK's guarantees (strict schemas) are replaced by our own Pydantic validation. Optional: a ~40-line `AnthropicAdapter` behind the same interface if a native key appears. That is not worth building up front.

### 2.3 Model shortlist (cheap, fast, Persian)

| Model ID | $/1M in | $/1M out | Notes | Source |
|---|---|---|---|---|
| `claude-haiku-5-5` | 0.10 | 0.50 | Prompts ≤100K tokens. Above that: $0.50 / $2.50. Current Haiku. | claude-api skill model table (cached 2026-10-06); AvalAI pricing page lists the same |
| `claude-sonnet-5-5` | 2.00 | 10.00 | Quality step-up. Rejects forced tool use. | same |
| `claude-haiku-4-5` | 1.00 | 5.00 | Previous Haiku, widely listed on gateways | skill table |
| `gpt-5-nano` | 0.05 | 0.40 | Cheapest | https://developers.openai.com/api/docs/pricing |
| `gpt-6-luna` / `gpt-5.6-luna` | 0.10 / 0.20 | 0.50 / 1.20 | Newest small tier (the "luna" = small label is our inference) | same |
| `gpt-5-mini` | 0.25 | 2.00 | | same |
| `gpt-4.1-mini` / `gpt-4o-mini` | 0.40 / 0.15 | 1.60 / 0.60 | Older; still listed | same |
| `gemini-3.5-flash-lite` | 0.30 | 2.50 | | https://ai.google.dev/gemini-api/docs/pricing |
| `gemini-3.8-flash` (`gemini-flash-latest`) | 0.75 (1.50 from 2027-01-01) | 3.75 (7.50) | Output price includes thinking tokens | same; AvalAI pricing |

**Persian quality evidence.** It is thin and old, and none of it tests our task (slot extraction and short explanations).
- **Khayyam Challenge / PersianMMLU** (20K Persian exam MCQs, 2024): GPT-4 50%, Claude 3 Haiku 43%, GPT-3.5 36%, best open model (Aya) 34%. Students scored 77%; random is 25%. https://arxiv.org/abs/2404.06644
- **PersLitEval** (4,514 Persian-literature MCQs, 2026): Gemini 2.5 Flash 45.1% (best of six), GPT-4o 42.0%, GPT-4.1 Mini 32–35%. Claude was not tested. https://www.alphaxiv.org/abs/2605.27015
- **MELAC** (19 Persian datasets, 41 LLMs) runs a live leaderboard: https://huggingface.co/spaces/opll-org/Open-Persian-LLM-Leaderboard . Its table did not render when fetched, so the current rankings were not read.

Conclusion: frontier families all handle modern Persian. Small or older "mini" models are noticeably weaker on knowledge-heavy Persian. **Pick between `claude-haiku-5-5` and `gpt-5-mini` (or `gemini-3.8-flash`) on our own §6 eval.** Watch three things: tool-call validity, colloquial Tehran Persian (تومن، ملیون، کارتخوان), and whether replies stay in Persian.

### 2.4 Smoke test to run on any new gateway or model (≈ 1 cent)

1. Plain chat in Persian → reply in Persian.
2. One `tools` call (`search_products`) → valid `tool_calls[0].function.arguments`.
3. Send a `role:"tool"` result back → a final text that references `offer_id`.
4. `stream=True` → chunks arrive.
5. Two parallel tool calls in one turn → both returned.

Save the outcome to `logs/llm_smoke.jsonl`. Show the result on an `/admin/llm` health page or in `GET /api/health`.

## 3. Agent pattern

### 3.1 Shape: a bounded workflow, not an open-ended agent

```
user text ─► rule parser (always) ─► Filters v0 ─► SQL/FTS ─► cards v0 ──► UI (≤1 s)
                 │ LLM enabled?
                 └─► LLM turn 1: tools available, sees Filters v0 + top candidates
                       ├─ calls tools (≤3 rounds, ≤6 calls total)
                       └─ returns AssistantReply JSON (validated) ─► cards v1 + "why" + next actions
```

- The LLM **amends** a typed `Filters` object. It never writes SQL. Server code runs every query.
- Hard limits: 3 tool rounds, 12 s wall time, and `max_tokens` 700. If any limit is hit, keep the v0 cards and show «پیشنهاد هوشمند در دسترس نیست».
- UI chips (area, budget, payment, open-now) edit the `Filters` object directly with **no LLM call**. This matches the requirement "the user can easily change area, budget, and purchase conditions" (requirements.md, UX).

### 3.2 Tool schemas (OpenAI `tools` format; descriptions in English, values in Persian)

```jsonc
[
 {"type":"function","function":{"name":"search_products",
  "description":"Full-text + filter search over products that have at least one offer. Returns ≤8 products with offer_count, min/median price_toman, top shops. Use for any product need.",
  "parameters":{"type":"object","additionalProperties":false,"properties":{
    "query":{"type":"string","description":"Persian product words, normalized (e.g. 'هندزفری بلوتوث')"},
    "brand":{"type":["string","null"]},
    "category":{"type":["string","null"],"description":"Torob leaf category name if known"},
    "max_price_toman":{"type":["integer","null"]},"min_price_toman":{"type":["integer","null"]},
    "area":{"type":["string","null"],"description":"location_label (محله) or passage name"},
    "open_at":{"type":["string","null"],"description":"ISO-8601 Asia/Tehran, or 'now'"},
    "payment":{"type":["array","null"],"items":{"enum":["torobpay","snapppay","digipay","tara","installment","in_person_any"]}},
    "limit":{"type":"integer","default":8,"maximum":20}},
   "required":["query"]}}},
 {"type":"function","function":{"name":"compare_offers",
  "description":"All offers for 1–3 product_ids with price_toman, price_changed_at, warranty, shop area/passage/floor, open_at status, payment. Use before recommending a seller.",
  "parameters":{"type":"object","additionalProperties":false,"properties":{
    "product_ids":{"type":"array","items":{"type":"string"},"maxItems":3},
    "area":{"type":["string","null"]},"open_at":{"type":["string","null"]},
    "sort":{"enum":["price","distance","freshness"],"default":"price"}},
   "required":["product_ids"]}}},
 {"type":"function","function":{"name":"find_shops",
  "description":"Shops matching area / open time / payment / category, even without a specific product (category alone ≠ in stock).",
  "parameters":{"type":"object","additionalProperties":false,"properties":{
    "area":{"type":["string","null"]},"open_at":{"type":["string","null"]},
    "payment":{"type":["array","null"],"items":{"type":"string"}},
    "category":{"type":["string","null"]},"near_lat":{"type":["number","null"]},"near_lon":{"type":["number","null"]},
    "limit":{"type":"integer","default":10}},"required":[]}}},
 {"type":"function","function":{"name":"get_shop",
  "description":"Full shop card: name, address, passage/floor/unit, weekly hours, payment options, fast delivery, contact channel, offer count.",
  "parameters":{"type":"object","additionalProperties":false,"properties":{"shop_id":{"type":"string"}},"required":["shop_id"]}}},
 {"type":"function","function":{"name":"find_substitutes",
  "description":"Alternatives for a product from the same category within a price band, ranked by spec/title similarity and seller availability near the chosen area.",
  "parameters":{"type":"object","additionalProperties":false,"properties":{
    "product_id":{"type":"string"},"max_price_toman":{"type":["integer","null"]},"area":{"type":["string","null"]},"limit":{"type":"integer","default":5}},
   "required":["product_id"]}}},
 {"type":"function","function":{"name":"plan_visit",
  "description":"Order 1–6 offer stops into a walking route (nearest-neighbour on coordinates, passage grouping), check each shop is open at arrival, return ETA per stop and total walking metres.",
  "parameters":{"type":"object","additionalProperties":false,"properties":{
    "offer_ids":{"type":"array","items":{"type":"string"},"maxItems":6},
    "start_at":{"type":"string","description":"ISO-8601 Asia/Tehran"},
    "start_lat":{"type":["number","null"]},"start_lon":{"type":["number","null"]},
    "minutes_per_stop":{"type":"integer","default":10}},
   "required":["offer_ids","start_at"]}}},
 {"type":"function","function":{"name":"draft_seller_message",
  "description":"Create a Persian message draft to a seller asking to confirm stock/price/warranty/hold the item. Server fills facts from DB; you only choose questions and tone. Never sends.",
  "parameters":{"type":"object","additionalProperties":false,"properties":{
    "offer_id":{"type":"string"},
    "questions":{"type":"array","items":{"enum":["in_stock","price_still_valid","original_or_copy","warranty","hold_until","torobpay_in_store","installment"]}},
    "visit_time":{"type":["string","null"]},"tone":{"enum":["formal","friendly"],"default":"friendly"}},
   "required":["offer_id","questions"]}}}
]
```

Design notes:
- `find_substitutes` was added to the list in the brief. Substitution is one of the three named Intelligence items, and doing it server-side (category + price band + trigram/spec similarity) keeps the candidates grounded. The LLM then **chooses among them and explains why**.
- `draft_seller_message` returns `{draft_id, text, channel, phone_display}`. The server builds the text from a template plus the chosen questions, and the LLM may rephrase it. Phones are fake (F2), so "send" opens a simulated chat clearly marked «نمایشی» (D6).
- Tool results are **trimmed** to the fields shown above, ≤8 rows each. Free-text seller descriptions are cut to about 200 characters and wrapped as data.

### 3.3 Structured output: cards rendered by the UI, not free text

The final LLM message must be JSON that matches this schema (validated by Pydantic):

```jsonc
{"reply_fa": "≤2 short Persian sentences, no numbers except counts",
 "cards": [{"kind":"offer|product|shop|substitute|plan|draft", "id":"<id from a tool result>",
            "reason_codes":["cheapest_in_area","open_now","torobpay_in_person","fresh_price","has_warranty","closest","same_passage","within_budget","substitute_cheaper","substitute_more_sellers"],
            "reason_fa":"≤15 words, no prices/times"}],
 "next_actions": [{"label_fa":"...","action":"compare|plan_visit|draft_message|widen_area|raise_budget|show_substitutes","args":{}}],
 "filters": { /* the amended Filters object, echoed so the chips update */ }}
```

**Grounding rules, enforced in code rather than only in the prompt:**
1. **The ID whitelist.** Every `cards[].id` must appear in a tool result from *this* turn. Unknown IDs are dropped and logged as `hallucinated_id`.
2. **The UI renders every fact from the DB by ID:**
   - price, with the price-change date ("۳ روز پیش")
   - hours / open status
   - address and floor
   - payment
   - warranty

   The LLM supplies only `reason_codes` and an optional short `reason_fa`. This also satisfies "recorded price, price-change time and confirmed availability are not conflated" (requirements.md).
3. **The number guard.** After normalizing Persian and Arabic digits, scan `reply_fa` and `reason_fa` for digits or number words (میلیون، هزار، تومان). Strip any number that does not appear in the turn's tool results, or reject the reply and use the template text. Better still, the prompt tells the model never to write prices. `reason_codes` are rendered by templates such as «ارزان‌ترین در فردوسی (۱۸۴ میلیون، ۲ روز پیش)», with the numbers inserted from the DB.
4. **Unknown stays unknown.** If `weekly_hours` is empty, the status is «ساعت کاری ثبت نشده», never "open". Stock is always «موجودی تأیید نشده» until the simulated seller reply.
5. **Deterministic "why".** `reason_codes` can be computed without the LLM (cheapest, open now, closest, and so on). The no-key path therefore shows the same "why" chips. The LLM adds a ranking among them and one sentence of nuance.

### 3.4 Streaming and latency (mobile)

Response-time limits (Nielsen): 0.1 s feels instant, **1 s keeps flow**, 10 s is the attention limit. Past 10 s the user needs progress feedback and a way to cancel. https://www.nngroup.com/articles/response-times-3-important-limits/

Budget per user message:

| Step | Target |
|---|---|
| Rule parse + SQLite FTS + cards v0 | < 300 ms server, < 1 s on screen |
| LLM round 1 (tool choice) | 1–3 s |
| Tool execution | < 200 ms each |
| LLM round 2 (final JSON) | 1–3 s |
| Total smart answer | **3–7 s typical, 12 s hard timeout** |

- Use **SSE** (`text/event-stream`, FastAPI `StreamingResponse`):
  1. `event: cards` (v0, immediately)
  2. `event: status` («در حال مقایسه فروشنده‌ها…» while tools run)
  3. `event: cards` (v1)
  4. `event: text`
  5. `event: done`

  This is progressive enhancement and does not depend on token streaming.
- Token streaming of the final JSON is optional. Streamed tool-call deltas vary by gateway. Use non-streaming requests for the tool rounds; stream only the final `reply_fa` if the gateway supports it (smoke-test step 4).
- Keep prompts small, since Persian costs more tokens per word than English (unverified for each tokenizer):
  - system prompt ≈ 800 tokens
  - tool schemas ≈ 1,200
  - the last 6 turns only
  - trimmed tool results

## 4. Fallback without an LLM: a rule-based Persian parser

The no-key path must demo every step. The same `Filters` object feeds SQL whether the rules or the LLM filled it.

### 4.1 Normalization (before everything; also used when building the FTS index)

- Arabic to Persian letters: ي→ی, ك→ک, ة→ه. Persian and Arabic digits to ASCII. Strip diacritics and tatweel. Use ZWNJ consistently (می‌خوام / میخوام / می خوام → one form).
- Library: **hazm** (normalizer, tokenizer, lemmatizer, POS). `pip install hazm`; the README says Python 3.12+. https://github.com/roshan-research/hazm . A 30-line custom normalizer is enough if hazm's dependencies are heavy on Python 3.14 (F12). **Check `pip install hazm` on 3.14 early.**
- FTS5: the `unicode61` tokenizer splits on Unicode separators. `remove_diacritics` only affects Latin characters, so Persian normalization must happen in Python before indexing *and* before querying. A second `trigram` table catches partial and misspelled words, but queries shorter than 3 characters match nothing. https://www.sqlite.org/fts5.html

### 4.2 Intent and slot extraction

| Slot | Method | Examples |
|---|---|---|
| intent | keyword rules, by priority | compare: «مقایسه، فرق، کدوم بهتره» · plan: «مسیر، برنامه، کی برم» · follow-up: «پیام بده، بپرس، موجود داره؟» · substitute: «جایگزین، مشابه، اگه نبود» · else search |
| budget | regex over normalized digits + unit words | «زیر ۲۰۰ میلیون»→max 200,000,000 · «تا ۳ تومن» (colloquial: million Toman)→max 3,000,000 · «بین ۲ تا ۳ میلیون» · «۸۰۰ تومن»→ambiguous (thousand?): ask a chip question |
| brand | gazetteer from `products.brand` (Persian + English + common transliterations: سامسونگ/samsung, شیائومی/xiaomi, انکر/anker) | the longest match wins |
| category | gazetteer of the 3,428 leaf categories plus a small synonym map (هندزفری→هدفون، هدست و هندزفری; شارژر گوشی→…) | |
| product words | the remaining tokens after removing slot phrases and stop-words (می‌خوام، یه، دنبال، لطفا) | used as the FTS query |
| area | gazetteer: 31 `location_label` values + parsed passage names (علاءالدین، چارسو، پلاسکو، لاله‌زار…) + landmarks mapped to coordinates (جمهوری، فردوسی، تجریش، میدان امام) | «نزدیک جمهوری» → near point + radius |
| time | rules → aware datetime in `Asia/Tehran` | «الان/همین الان»→now · «امروز عصر»→today 17:00 · «فردا صبح»→tomorrow 10:00 · «پنجشنبه ساعت ۵»→next Thu 17:00 · «ظهر»→13:00 |
| payment | keyword map | ترب‌پی/ترب پی→torobpay · اسنپ‌پی→snapppay · اقساط/قسطی→installment · کارتخوان→in_person_any |
| needs | flags | «اصل/اورجینال»→prefer warranty + flag fake risk · «گارانتی»→has_warranty · «ارسال فوری»→fast_delivery |

An unknown or ambiguous slot becomes a **suggestion chip**, not a guess. For example, «۸۰۰ تومن یعنی ۸۰۰ هزار؟».

### 4.3 What can be deterministic

| Feature | Without LLM | What the LLM adds |
|---|---|---|
| Search + filters | Full (FTS + slots + chips) | Messy or long requests, implicit needs («برای کولر گازی» → 16A protector) |
| Compare offers | Full (table sorted by price/distance/freshness, outlier flags) | One-line trade-off summary |
| Pick seller by area/hours/payment | Full (`is_open_at` from 01-dataset §4, payment flags, distance) | Weighing conflicting needs |
| Substitution | Good (same category, price band, trigram/spec overlap, more sellers nearby) | Judging "is this really equivalent" from specs; explaining it |
| Visit plan | Full (nearest-neighbour walk, open-at-arrival check, passage grouping) | Natural-language plan summary |
| Seller follow-up | Template drafts with selectable questions; simulated replies | Tone and rephrasing; parsing a free-text "seller reply" into stock / price confirmed |
| "Why recommended" | `reason_codes` → template sentences | Ranking and nuance |

**Estimate:** about 80–90% of the scripted demo works with no key. The LLM's visible value is robustness to free-form Persian, substitute judgement, and natural explanation and message drafting. **Both modes should be demoed:** the same query with the key off and on, which shows that "intelligence" is real rather than scripted.

## 5. Logging, safety, cost

### 5.1 Secrets
- Keys live only in env or `.env`; `.env` is git-ignored, and `.env.example` holds placeholders. Never put a key or env dump in a prompt, tool result, error message returned to the LLM, log line or frontend response.
- Use a log formatter that redacts `Authorization`, `api_key` and `sk-…`-like strings. The OpenAI SDK's debug logging prints headers, so keep `OPENAI_LOG` unset.
- `/api/health` reports `llm: {enabled, provider_host, model}` and **never the key**.

### 5.2 JSONL call log (`logs/llm_calls.jsonl`, one line per request)
```json
{"ts":"2026-10-22T12:00:01+03:30","req_id":"…","session":"…","turn":3,"round":1,
 "host":"api.avalai.ir","model":"claude-haiku-5-5","prompt_version":"v4",
 "messages_sha":"…","tools":["search_products","compare_offers"],
 "tool_calls":[{"name":"compare_offers","args":{…},"ms":42,"rows":7}],
 "usage":{"in":2950,"out":310},"cost_usd":0.00045,"latency_ms":1830,
 "status":"ok|timeout|invalid_json|hallucinated_id|http_429","fallback_used":false}
```
- Store full messages in a separate `logs/llm_payloads.jsonl` for debugging the demo. Mask phone-number patterns from user text. The dataset's phones are fake anyway.
- These logs double as eval material: replay real queries in §6.

### 5.3 Cost control
- Per call ≈ 3K input + 300 output tokens, with 2–3 calls per turn:
  - Haiku 5.5: ≈ $0.0015 per turn, so 1,000 demo turns ≈ $1.5.
  - Sonnet 5.5: ≈ $0.03 per turn.
  - Persian tokenization may raise these figures; check `usage` in the logs.
- Guards:
  - `max_tokens` 700
  - ≤3 tool rounds
  - ≤N LLM turns per session per hour
  - a daily USD budget counter in SQLite; when exceeded, set `LLM_ENABLED=false` automatically and show the rule path
- **Cache:** SQLite table `llm_cache(key, value, created_at)`. The key is `sha256(model, prompt_version, normalized_query, filters_json, data_version)`. It is valid because the dataset is static. It makes the demo video reproducible and instant on retakes. Clear it when `prompt_version` changes.
- Provider prompt caching: OpenAI applies it automatically to long stable prefixes; it is not available through Anthropic's OpenAI layer. Keep the system prompt and tool list byte-stable anyway (no timestamps in the system prompt; put "now" in the user turn).

### 5.4 Safety and prompt-injection
- Seller titles and descriptions are untrusted text. Pass them only inside tool results as JSON strings, and tell the model they are data.
- The LLM cannot send anything. `draft_seller_message` only drafts, and sending is a user click into the simulated chat.
- Validate tool arguments: clamp `limit`, check that IDs exist, and parse `open_at` as a datetime. Reject anything else with an `is_error`-style tool message.

## 6. Evaluation

### 6.1 Dataset (`eval/queries.jsonl`, 60–100 items, written **before** tuning the parser)
```json
{"id":"q017","text":"یه هندزفری بلوتوث زیر ۳ تومن میخوام نزدیک چارسو که الان باز باشه",
 "expect":{"intent":"search","category":"هدفون، هدست و هندزفری","max_price_toman":3000000,
           "area":"چارسو","open_at":"now","brand":null,"payment":null},
 "gold_product_ids":["…"], "notes":"colloquial تومن = million"}
```
- Coverage:
  - the 5 demo scenarios from `01-dataset.md` §9
  - 10 compare, 10 substitute, 10 plan, 10 follow-up
  - 15 colloquial / misspelled / Finglish (e.g. «hedzefri samsung»)
  - 10 with conflicting or ambiguous needs
  - 5 out-of-scope («بلیط هواپیما»)
- Gold labels come from a teammate who did not write the rules. Hold out 30% as a test split that is not looked at while tuning.

### 6.2 Metrics
| Level | Metric |
|---|---|
| Parser | Per-slot precision/recall; **exact-match on the full filter object**; intent accuracy |
| Retrieval | Hit@5 for `gold_product_ids`; **constraint-violation rate** (share of returned offers breaking budget, area, open-at or payment) |
| Agent | Valid-JSON rate; tool-call validity; **hallucinated-ID rate**; **unsupported-number rate** (numbers in text not in tool results); p50/p95 latency; cost per turn |
| Explanation | 20 items rated 1–3 by a human for "is the why true per the card data" |

### 6.3 Baselines (same queries, same DB)
1. **FTS only**: the raw query into FTS5, sorted by price. No filters.
2. **Rules + FTS**: §4 parser.
3. **LLM-parsed + FTS**: the LLM fills `Filters` only (one call, no agent loop).
4. **Full agent**: tools, substitutes and explanation.

Report a small table, model × variant. It shows honestly where the LLM helps; expect the biggest gains on colloquial or implicit queries and little gain on clean ones. Put the table in the demo or README as evidence for the Intelligence and Technical criteria.

Runner: `python -m app.eval --variant rules|llm|agent --split test`, writing `eval/results/<date>_<variant>_<model>.json`. For LLM variants, pin `prompt_version` and use the cache. A full run should cost cents.

## Unverified / open questions

1. **Which provider or key the team has** is not yet known. Everything here assumes an Iranian OpenAI-compatible gateway.
2. **GapGPT**: base URL, tool support and pricing are not verified (site timed out). `api.gapgpt.app/v1` is from memory only.
3. **Metis tools passthrough**: the docs sentence about "function calling" not being supported in direct mode is ambiguous. Needs a live test. Its Anthropic and Gemini wrapper URLs were not fetched.
4. **Liara AI pricing** and the exact model-ID list were not seen. The ID format `openai/gpt-4o-mini` comes from their docs example.
5. **AvalAI rate limits for `gpt-5-mini` and `gemini-3.8-flash`** were not in the fetched excerpt (Haiku 5.5's were). Whether AvalAI's native Anthropic endpoint exists, and its URL, is unverified. Whether `stream=True` with `tools` works through each gateway is unverified.
6. **Claude model IDs and prices** (`claude-haiku-5-5` $0.10/$0.50, `claude-sonnet-5-5` $2/$10) come from the claude-api skill table (cached 2026-10-06) and match AvalAI's page. They were not checked on Anthropic's live pricing page.
7. **The "luna" OpenAI models** are listed in OpenAI's pricing table. Treating them as the small tier is an inference.
8. **No benchmark covers Persian slot extraction or tool use** for current models. Quality claims rest on old MCQ benchmarks. Our own eval (§6) is the only real evidence.
9. **Persian token inflation** per tokenizer was not measured; cost estimates may be 1.5–3× low.
10. **Gateway legal/terms status.** These are resellers of providers that exclude Iran, and their continuity is outside our control. Keep the no-LLM path demo-complete.
11. **hazm on Python 3.14** (the local version, F12) is not tested.
12. **The challenge video** (not watched) may define what "follow-up" means, e.g. a real Bale or WhatsApp hand-off. The data has phone only (F2).
