# 05 — UX, RTL/Persian typography, maps, deep links

Scope: Persian, RTL, mobile-first web app served by FastAPI with no build step. UX (75) and Product (75) are half the score. The requirements in `docs/requirements.md` that shape the UI:
- Use cards, filters and buttons, not only chat.
- Show why an item was suggested and what the next step is.
- Make area, budget and purchase conditions easy to change.
- Show recorded price, price-change time and confirmed availability **separately**.
- Show unknowns clearly.

Research date: 2026-10-22. Facts confirmed in sources or by running code are marked as such. Everything else is listed under "Unverified" at the end.

---

## 0. Most important finding: Iran's connectivity in 2026

Iran has spent much of 2026 under international-internet shutdowns, while the domestic National Information Network (NIN) stays up:
- A shutdown began on 8 Jan 2026, and another followed the 28 Feb strikes.
- A tiered "Internet Pro" scheme was announced on 14 Apr 2026.
- Sources: [ASL19](https://asl19.org/en/blog/2026-04-07-the-myth-of-domestic-internet-in-iran), [TechSpot](https://www.techspot.com/news/112041-iran-internet-outage-passes-1000-hours-one-longest.html), [MEA TechWatch](https://meatechwatch.com/2026/04/01/irans-internet-shutdown-surpasses-750-hours-as-wartime-blackout-reshapes-regional-connectivity-risks/), [arXiv 2603.28753](https://arxiv.org/pdf/2603.28753).

What this means for us:
- **Vendor every asset**: JS, CSS, fonts and icons. Serve them from our own FastAPI `/static`. Use no CDN at runtime, including jsDelivr, unpkg, cdnjs and Google Fonts.
- **Use a domestic map provider (Neshan) as the primary map.** OSM, Google Maps and WhatsApp may be unreachable for Iranian judges or users.
- **The app must stay useful with no map at all.** Use a list sorted by distance, plus passage, floor and unit text.
- If the deploy server is outside Iran, judges inside Iran may not reach it. That is a decision for the Deploy section; flag it to the team.

On public CDNs: I found no OONI evidence that jsDelivr, unpkg or cdnjs are specifically blocked in Iran. The only related evidence is SNI blocking of `cdn.sstatic.net` in 2023 ([Tor issue 115](https://gitlab.torproject.org/tpo/anti-censorship/team/-/issues/115)). jsDelivr is blocked in China ([PsychoPy forum](https://discourse.psychopy.org/t/cdn-jsdelivr-net-has-been-blocked-in-china-is-there-any-possible-change-the-source-of-css/29212)), and some regions report it unavailable ([Bootstrap issue](https://redirect.github.com/twbs/bootstrap/issues/39145)). This is moot during a shutdown, so vendoring is the only safe choice.

---

## 1. Frontend without a build step

| Option | Size (min / gzip) | Fit for our UI |
|---|---|---|
| **Preact + htm** (`htm/preact/standalone.module.js` from htm@3.1.1) | 13.2 KB min ([jsDelivr listing](https://data.jsdelivr.com/v1/packages/npm/htm@3.1.1?structure=flat)), about 5–6 KB gzip (est.). Preact alone is about 5.0 KB gzip and htm 0.7 KB ([bundlephobia](https://bundlephobia.com/api/size?package=preact), [htm](https://bundlephobia.com/api/size?package=htm)) | Real components (ProductCard, OfferRow, FreshnessBadge, BottomSheet) and hooks. Renders JSON from FastAPI and the LLM tool outputs directly. An ES module with no build: `import {html, render, useState} from '/static/vendor/standalone.module.js'` ([Preact docs](https://preactjs.com/llms.txt)). |
| Alpine.js 3 | `cdn.min.js` 44.7 KB min ([jsDelivr listing](https://data.jsdelivr.com/v1/packages/npm/alpinejs@3.14.9?structure=flat)), about 16–19 KB gzip ([bundlephobia](https://bundlephobia.com/api/size?package=alpinejs)) | HTML-first and pairs well with Jinja. Repeated card markup across chat, list and comparison gets messy without components. Its default build uses `new Function`, which conflicts with a strict CSP. |
| htmx 2 | about 18 KB gzip ([bundlephobia](https://bundlephobia.com/api/size?package=htmx.org)) | Server-rendered partials and SSE work well. Client state for the instant filter sheet, compare tray, saved list and geolocation still needs Alpine or vanilla JS on top. |
| Vanilla JS | 0 KB | Most code to write. The template-string `innerHTML` pattern gives escaping and XSS risk with LLM text. |

**Recommendation: Preact + htm standalone, vendored**, about 6 KB gzip, with hand-written CSS (no Tailwind CDN).
- Load the map SDK (Leaflet via Neshan, about 43 KB gzip for Leaflet 1.9.4 alone, [bundlephobia](https://bundlephobia.com/api/size?package=leaflet)) **lazily**, only when the user opens the map tab.
- To vendor a file, fetch it once (from outside Iran or with a VPN) from `https://cdn.jsdelivr.net/npm/htm@3.1.1/preact/standalone.module.js` and commit it to `static/vendor/`.
- Use the native `<dialog>` element for bottom sheets and modals. It needs no library.

---

## 2. Persian typography and formatting

### Font: Vazirmatn
- License: **SIL OFL 1.1**, free to self-host and embed ([repo](https://github.com/rastikerdar/vazirmatn)). Latest release is v33.003, 22 Jun 2022 ([releases](https://github.com/rastikerdar/vazirmatn/releases)).
- woff2 sizes ([jsDelivr manifest](https://data.jsdelivr.com/v1/packages/gh/rastikerdar/vazirmatn@v33.003?structure=flat)):
  - Regular 50.7 KB and Bold 51.0 KB. These include Roboto for Latin text.
  - Variable `Vazirmatn[wght].woff2`: 111 KB for all weights.
  - **Non-Latin (NL)**: Regular 21.9 KB, Bold 22.3 KB, Variable 48 KB.
  - **FD (Farsi Digits)**: renders ASCII digits as Persian glyphs. **UI**: tighter line height for UI text.
- **Pick:** self-host `Vazirmatn-UI-NL-Regular.woff2` and `-Bold.woff2`, about 44 KB total, and fall back to `system-ui` for Latin. Use the non-NL Regular and Bold if model names render badly.
- Use `font-display: swap` and `<link rel=preload>` the Regular file.
- Prefer generating Persian digits with `Intl` over relying on the FD font. Phone numbers must stay ASCII in `tel:` hrefs, and only the font changes how digits look.

### RTL basics
- Put `<html lang="fa" dir="rtl">` on the root.
- Use **CSS logical properties** everywhere: `margin-inline-start`, `padding-inline`, `inset-inline-end`, `border-start-start-radius`, `text-align: start`. Flex and grid follow `dir` automatically.
- Mirror direction-implying icons (back and forward chevrons, "next" arrows) with `[dir=rtl] .icon-dir { transform: scaleX(-1) }`. Do not mirror the phone, check, search or map-pin icons.
- For mixed bidi text, wrap Latin model names and SKUs in `<bdi>`. Show phone numbers, prices in ASCII, and URLs with `dir="ltr"` inside RTL text. Use `unicode-bidi: plaintext` for LLM text.
- Give the Leaflet container `dir="ltr"` and set `dir="rtl"` inside the popup content. This is a safe default; test it.
- Normalize user input on both client and server:
  - Persian digits `۰-۹` and Arabic digits `٠-٩` → ASCII.
  - Arabic `ي`/`ك` → `ی`/`ک`.
  - ZWNJ (`‌`) is meaningful, so keep it.
- Budget field: `inputmode="numeric"`. Test that `<input type=range>` grows right-to-left.

### Numbers, Toman, dates: verified in Node 24 / ICU 78

| Code | Output |
|---|---|
| `new Intl.NumberFormat('fa-IR').format(12500000)` | `۱۲٬۵۰۰٬۰۰۰` (Persian digits, `٬` thousands separator) |
| `new Intl.NumberFormat('fa-IR',{notation:'compact',compactDisplay:'long',maximumFractionDigits:1}).format(12500000)` | `۱۲٫۵ میلیون` (**must** set `maximumFractionDigits:1`, otherwise it rounds to `۱۳ میلیون`) |
| same, `850000` | `۸۵۰ هزار` |
| same, `1250000000` | `۱٫۳ میلیارد` (with the default fraction digits) |
| `{style:'currency',currency:'IRR'}` | `ریال ۱۲۵٬۰۰۰٬۰۰۰` (rial only, LRM-prefixed). **Don't use it.** Append ` تومان` manually. |
| `new Intl.DateTimeFormat('fa-IR',{day:'numeric',month:'long',year:'numeric'})` | `۳۰ مهر ۱۴۰۵`. `fa-IR` defaults to the **persian** calendar, and `-u-ca-persian` is explicit and safe. |
| `{weekday:'long',day:'numeric',month:'long',timeZone:'Asia/Tehran'}` | `پنجشنبه ۳۰ مهر` |
| `{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tehran'}` | `۱۴:۰۰` |
| `new Intl.RelativeTimeFormat('fa',{numeric:'auto'}).format(-3,'day')` | `۳ روز پیش`. Also `-1,'day'` → `دیروز`, `0,'day'` → `امروز`, `-2,'hour'` → `۲ ساعت پیش` |

- Avoid `dateStyle:'full'`: ICU output is odd (`۱۴۰۵ مهر ۳۰, پنجشنبه`). Use explicit fields.
- `RelativeTimeFormat` does not choose the unit. Write a 10-line helper for that: minute → hour → day → week.
- Toman conventions:
  - Convert from the dataset's `price unit` (rial or toman) to **toman**.
  - On cards, show `۱۲٫۵ میلیون تومان`. In detail and comparison views, show the full `۱۲٬۵۰۰٬۰۰۰ تومان`.
  - Show ranges as `از ۱۱٫۸ تا ۱۳٫۲ میلیون تومان`.
- Always pass `timeZone:'Asia/Tehran'` for working-hours logic, for example `باز است تا ۲۱:۰۰`.

---

## 3. Maps in Iran

| Option | Reachable in Iran | Key / cost | Notes |
|---|---|---|---|
| **Neshan Leaflet SDK** | Yes (domestic) | Free signup at [platform.neshan.org/panel](https://platform.neshan.org/panel/login). **200,000 toman free credit for 3 months**, then pay-as-you-go ([platform](https://platform.neshan.org/)). Map-display price is not stated ([pricing](https://platform.neshan.org/pricing/)). | Drop-in Leaflet 1.9.4 ([docs](https://platform.neshan.org/docs/sdk/web/leaflet/neshan-leaflet-sdk/)). Example code: `new L.Map("map",{key:"web.xxx", maptype:"dreamy", center:[35.6997,51.3380], zoom:14})`. Maptypes include `dreamy` and `standard-night` (six styles in total). Can fall back to OSM tiles through `setMapType(url)`. Also offers MapLibre and OpenLayers SDKs, plus search, reverse-geocode, distance-matrix and **TSP** APIs, which fit a multi-store visit route ([docs index](https://platform.neshan.org/docs/)). |
| Leaflet + OSM `tile.openstreetmap.org` | Uncertain. Fastly CDN; sanctions concerns ([OSM help 2021](https://help.openstreetmap.org/questions/80467/today-map-not-loaded-without-vpn/)); a claim of ISP blocking ([OSM-talk](https://lists.openstreetmap.org/pipermail/talk/2021-November/087098.html)); likely unreachable during 2026 shutdowns | Free, best-effort, no SLA | [Policy](https://operations.osmfoundation.org/policies/tiles/): HTTPS only, valid Referer, visible "© OpenStreetMap contributors", no prefetch or offline. Fine for a dev fallback. |
| Map.ir | Yes (domestic) | Free token via registration ([pub.dev](https://pub.dev/packages/mapir_gl), [mapir-vue](https://cdn.jsdelivr.net/npm/mapir-vue@2.2.11/README.md)) | Mostly mapbox-gl / vector tiles. Leaflet support is community-only ([mapir-leaflet](https://www.npmjs.com/package/mapir-leaflet)). |
| Balad | Yes | No public web SDK found | Use it only as a deep-link target. |

**Recommendation:**
- Use the **Neshan Leaflet SDK** with a Web key in `.env`. Lazy-load it from `static.neshan.org`, which is domestic, or vendor its `index.js` and `index.css` (`https://static.neshan.org/sdk/leaflet/v1.9.4/neshan-sdk/v1.0.8/`).
- Add a config switch that falls back to plain Leaflet + OSM.
- If the map fails, show the distance list. For the demo video, the free credit is enough.

### Navigation deep links (from lat/lon)
- **Neshan**, from Neshan's official MCP server source ([deeplinks.py](https://raw.githubusercontent.com/NeshanMaps/Neshan-MCP/main/src/neshan_mcp/utils/deeplinks.py)):
  - Point (Android/web): `https://nshn.ir/?lat=35.6997&lng=51.3380`
  - Point (iOS): `neshan://?ll=35.6997,51.3380`
  - Route (Android/web): `https://nshn.ir?origin=LAT,LNG&destination=LAT,LNG&vehicle=d`. `vehicle` is `d` (car) or `m` (motorcycle). `origin` is required, so get it from `navigator.geolocation`, or use the point link if there is none.
  - Route (iOS): `neshan://?origin=..&destination=..&vehicle=d|m|w|b|p`, where w = walk, b = bike, p = transit.
  - The https link falls back to the Neshan web app when the app is not installed.
- **Google Maps** ([docs](https://developers.google.com/maps/documentation/urls/get-started)), no API key needed:
  - `https://www.google.com/maps/search/?api=1&query=35.6997%2C51.3380`
  - `https://www.google.com/maps/dir/?api=1&destination=35.6997%2C51.3380&travelmode=driving&dir_action=navigate`. `travelmode` is driving, walking, bicycling, two-wheeler or transit.
- **Balad**: `https://balad.ir/location?latitude=35.6997&longitude=51.3380&zoom=16`. **Unverified**: the URL loads Balad's site, but no official docs were found ([ArduinoMapLink says it's assumed](https://github.com/arefttt/ArduinoMapLink)).
- **Android generic**: `geo:35.6997,51.3380?q=35.6997,51.3380(نام فروشگاه)` opens an app chooser listing installed map apps (Neshan, Balad, Google). It does not work on iOS.
- UI: a single "مسیریابی" button opens a bottom sheet with Neshan (first), Balad and Google Maps. Remember the last choice in `localStorage`.

---

## 4. UX patterns for the shopping assistant

**Hybrid layout: chat drives, cards decide.**
- Each assistant turn returns text **plus** structured blocks: product cards, store and offer cards, a comparison block, and a "next step" button row.
- Quick-reply chips sit under every turn: `ارزان‌تر`, `نزدیک‌تر`, `فقط با ترب‌پی`, `اقساطی`, `مقایسه کن`, `الان باز باشد`.
- The research says to keep free text plus buttons, because removing either one hurts users ([NN/g via Lovable summary](https://lovable.dev/en/guides/how-to-build-a-chatbot-ui)), and too many buttons lowers engagement ([VentureBeat](https://venturebeat.com/business/too-many-buttons-spoil-the-bot)). Use 3–5 chips per turn.
- Amazon Rufus shows a scrollable row of suggested questions and expands from the product page with context ([Business Insider](https://businessinsider.nl/i-tried-out-amazons-new-ai-shopping-assistant-rufus-one-feature-stood-out-as-a-game-changer/), [Amazon UK](https://aboutamazon.co.uk/news/retail/amazon-rufus-launch-uk-generative-ai-shopping-assistant)).
- Perplexity puts product cards (image, price, retailer, buy or visit) inline in answers ([TechRadar](https://www.techradar.com/computing/artificial-intelligence/perplexitys-new-buy-with-pro-is-the-perfect-ai-powered-shopping-assistant-for-black-friday)).
- Google AI Mode builds comparison tables on request and has a **"Let Google Call"** feature that phones local stores to confirm stock and price ([Google blog](https://blog.google/products-and-platforms/products/shopping/agentic-checkout-holiday-ai-shopping/), [TechCrunch](https://techcrunch.com/2025/11/13/google-expands-ai-shopping-with-conversational-search-agentic-checkout-and-an-ai-that-calls-stores-for-you)). This is a direct model for our "seller follow-up" step: a pre-filled message to the store asking "موجود دارید؟"

**Persistent context bar** (sticky top, the answer to "easily change area, budget, conditions"):
- Chips: `📍 پاساژ علاءالدین ▾` `💰 تا ۱۵ میلیون ▾` `ترب‌پی ✓` `اقساط` `باز الان`.
- Tapping a chip opens a **filter bottom sheet** (`<dialog>`) with a sticky "نمایش ۲۳ نتیجه" apply button, and results re-rank instantly.
- Baymard: on mobile, use a drawer or a sticky apply button, show an applied-filters overview (28% of sites lack one), and keep filter state across navigation ([Baymard filter UI](https://baymard.com/learn/ecommerce-filter-ui), [applied filters](https://baymard.com/research-articles/how-to-design-applied-filters), [apply buttons](https://baymard.com/guidelines/1125-apply-buttons-in-mobile-filtering-interfaces)).

**Offer card: transparency block.** Each line is labeled with its own source:
```
قیمت ثبت‌شده      ۱۲٫۵ میلیون تومان
آخرین تغییر قیمت  ۶ روز پیش (۲۴ مهر)       ← grey/amber badge by age
موجودی            تأیید نشده — «بپرس»       ← button → contact sheet
```
- Availability states: `فروشنده این کالا را ثبت کرده` (in the offers table) is different from `فقط حوزه فعالیت فروشگاه مرتبط است` (category match only, never shown as "in stock") and from `تأییدشده توسط شما/فروشنده در [time]` (after follow-up).
- Freshness badge colors: < 24 h green, 1–7 d amber, > 7 d grey. The dataset is about one week old, so most offers will be amber; say so honestly.
- **Unknowns**: show the field with `نامشخص` plus an info icon and a reason, for example `ساعت کاری ثبت نشده` or `گارانتی ذکر نشده`. Never hide the field or invent a value. In comparisons, unknown cells show `—` with the same reason in a tooltip. NN/g warns that uneven data ruins comparison tables, so surface the gaps explicitly ([NN/g](https://www.nngroup.com/articles/comparison-tables/)).
- **Data-type tags** for purchase conditions: `اعلام فروشنده` (seller-declared) vs `ثبت در ترب`, as required by "the information type made clear".

**"Why this" badges**: 1–3 short reasons generated from the scoring features, not free LLM prose. Examples: `ارزان‌ترین در پاساژ`, `۳۰۰ متر از شما`, `ترب‌پی دارد`, `الان باز است`, `گارانتی ۱۸ ماهه`. Tapping one expands "چرا این پیشنهاد؟" to show the scoring.

**Comparison on mobile** ([NN/g](https://www.nngroup.com/articles/comparison-tables/)):
- 2 items fit on mobile and at most 3 with horizontal scroll.
- Use a sticky header row with product or store names.
- Add a "فقط تفاوت‌ها" toggle and collapsible rows.
- A compare tray floats at the bottom: `مقایسه (۲)`.

**Visit plan / shopping list** ("follow-up"):
- Save items and stores to a `لیست خرید` stored in localStorage and optionally on the server.
- A visit plan groups stops **by passage → floor → unit**, for example `پاساژ چارسو · طبقه ۲ · واحد ۲۱۴`.
- Order passages with Neshan TSP or distance-matrix, or with a simple nearest-neighbor fallback. Inside a passage, order stops by floor and then unit.
- Each stop shows open/closed status at the planned time, a contact button, a "رسیدم/خریدم/نداشت" check-off and **substitutes**: `اگر نداشت: ۲ فروشنده دیگر در همین پاساژ`.

**Local examples**:
- Torob shop pages carry an in-person buying note: inspect the item before paying, and pick it up in person ([Torob shop page](https://torob.com/shop/77584/%DA%86%D8%B3%D8%A8-%D8%B5%D9%81%D8%B1%DB%8C/)). Reuse this tone in our "قبل از رفتن" tips.
- Digikala and Torob patterns (seller list sorted by price, "کمترین قیمت", price-range header) are familiar to Iranian users; match them. Not researched in depth here.

---

## 5. Contact deep links

| Channel | Format | Notes |
|---|---|---|
| Phone | `tel:+982112345678` | ASCII digits, E.164 format. Show the number in a `dir="ltr"` span. **All dataset phones are fake**: label them `شماره نمایشی` in the demo. |
| WhatsApp | `https://wa.me/989121234567?text=<urlencoded>` | International format with no `+`, no leading 0 and no dashes ([Bird](https://bird.com/explained/whatsapp/what-is-a-whatsapp-click-to-chat-link.md), [Dotdigital](https://support.dotdigital.com/en/articles/11331301-click-to-chat-for-whatsapp)). `api.whatsapp.com/send?phone=` is undocumented ([Unipile](https://www.unipile.com/fr/?p=275019)). May be unreachable in Iran. |
| Bale | `https://ble.ir/<username>`. Groups: `https://ble.ir/join/<hash>` | Seen in library docs ([BaleSharp](https://www.nuget.org/packages/BaleSharp), [Balethon](https://pypi.org/project/Balethon/0.4.0)). No official docs found, and opening a chat by phone number is not supported as far as I found. |
| Eitaa | `https://eitaa.com/<username>`. Invites: `https://eitaa.com/joinchat/<hash>` | Seen on a university page ([Lorestan Univ.](https://aleshtar.lu.ac.ir/en/alashtar-higher-education/news-from-the-aleshtar-center/eitaa-information-channel/)). Unofficial. |
| SMS | `sms:+989121234567?&body=<encoded>` | The `?&body=` form works on both platforms. Android also accepts `?body=` and older iOS used `;body=`/`&body=`. Avoid `;`, which some Android versions read as part of the recipient ([West Wind](https://weblog.west-wind.com/posts/2013/Oct/09/Prefilling-an-SMS-on-Mobile-Devices-with-the-sms-Uri-Scheme), [Mobile Commons](https://faq.mobilecommons.com/hc/en-us/articles/55547216453403-Creating-QR-Code-Scan-to-Text-Links-with-the-SMS-URI-Format)). Encode with `encodeURIComponent`, not `+` for spaces. |

Pre-filled follow-up text, generated per offer:
`سلام، از طریق ترب پیدا کردم. «[نام کالا]» با قیمت حدود [قیمت] تومان موجود دارید؟ امروز تا ساعت چند باز هستید؟`
Put "پیامک" (SMS) first, because it works without international internet.

---

## 6. Accessibility, performance, PWA

- **Budget**: about 150 KB on the first load, gzip, excluding images.
  - JS: Preact+htm about 6 KB plus app code about 20–30 KB.
  - CSS: about 10 KB.
  - Fonts: 2 × 22 KB.
  - Leaflet/Neshan loads only on the map tab.
- Images:
  - `loading="lazy"`, `decoding="async"`, and explicit `width`/`height` (or `aspect-ratio`) to avoid layout shift.
  - Use a grey placeholder with a product-category icon when there is no image. Many dataset rows lack images.
  - Proxy and resize images through FastAPI with a cache if the source hosts are slow.
- Network:
  - gzip/brotli middleware, plus `Cache-Control: immutable` on hashed vendor files.
  - Skeleton cards while the LLM thinks, then stream tokens (SSE) and show a typing indicator. A typing indicator softens perceived latency, per a study summarized in [Lovable/NN/g](https://lovable.dev/en/guides/how-to-build-a-chatbot-ui).
- A11y:
  - `lang="fa"`; tap targets ≥ 44–48 px; color contrast ≥ 4.5:1.
  - Freshness and availability must not be conveyed by color alone; always show text.
  - `aria-live="polite"` on the chat log; focus trap via `<dialog>`; `prefers-reduced-motion`.
  - Real `<button>` and `<a>` elements for every chip.
- **PWA: yes, minimal.** It costs about 15 minutes and looks app-like in the demo (standalone, no URL bar, home-screen icon).
  - Chromium needs `name`/`short_name`, 192 and 512 px icons, `start_url` and `display`, over HTTPS ([MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_Installable)).
  - Chrome no longer requires a service worker with a fetch handler (since Chrome 108 mobile / 112 desktop, [Chrome blog](https://developer.chrome.com/blog/update-install-criteria?hl=en)).
  - Add `"dir":"rtl","lang":"fa"` to the manifest.
  - Optional: a tiny service worker that caches the app shell and the shopping list, so the visit plan opens offline inside a passage with bad signal. That is a real in-store pain point and a good demo moment.

---

## Unverified / open questions

1. **Iran connectivity in Oct 2026**: the newest sources are from April 2026. Is the international internet reachable for judges now? Where should we deploy (Iranian VPS vs abroad)? This decides whether Google Maps, WhatsApp and OSM links work at all.
2. **Neshan map-display pricing**: whether rendering tiles consumes the 200k toman credit, and how fast. Also check whether a domain-restricted Web key works on our deploy domain.
3. **The Neshan `nshn.ir` link** is taken from Neshan's official MCP source, not from user-facing docs. Test on Android and iOS with and without the app. Can `origin` be omitted (use current location)?
4. **The Balad URL format** (`/location?latitude=&longitude=&zoom=`) is unofficial. Test on a device.
5. **Bale and Eitaa link formats** come from third-party pages only. Can either open a chat by phone number? Probably not.
6. **SMS `?&body=` on current iOS (17/18+)**: there are conflicting old reports. Test on a device.
7. **Browser ICU differences**: Safari/iOS output for `compact` + `long` in `fa-IR` (`۱۲٫۵ میلیون`) is not tested. Keep a JS fallback formatter.
8. **Exact gzip size of `htm/preact/standalone.module.js`** is estimated from its 13.2 KB minified size. Which Preact version does htm 3.1.1 bundle (likely an old 10.x)? Confirm hooks are exported.
9. **Leaflet inside a `dir=rtl` page**: the `dir="ltr"` wrapper is a precaution, not verified as needed.
10. **Which contact fields are publishable** is still to be decided by the organizers (per requirements). Design the contact sheet to hide missing channels gracefully.
11. **Torob and Digikala app UI details** (seller list, price history) were not inspected directly. Screenshot them for design reference.
