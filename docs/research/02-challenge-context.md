# 02 — Challenge context: Torob In-Store Shopping Assistant

Research date: 2026-10-22 (30 Mehr 1405). Every claim has a source URL. "Dataset" means our local `data/torob-dataset/shops.csv` (6,476 rows), analysed directly. That is a primary source for this project.

---

## 1. The challenge and event

**Bottom line: the four-step flow is NOT public.** No page, post or video describing it was found. The video link was not found either.

- **Event.** The challenge is almost certainly part of the **StarCoach Agentic AI Hackathon** (هکاتون Agentic AI استارکوچ), run by StarCoach (استارکوچ). StarCoach is an AI-education academy at Sharif Technology Tower, Tarasht, Tehran.
  - Event page: https://starcoach.ir/hackathon/agentic-ai
  - Organizer: https://starcoach.ir/
- **Sponsors.** Torob is listed as **main sponsor (اسپانسر اصلی)**. The other sponsors are Wallex, Liara, BoxAPI and Tapsell. Source: https://starcoach.ir/hackathon/agentic-ai
- **Challenges.** There are three: **چالش ترب**, چالش والکس and چالش لیارا. **Each is worth 300 points**, which matches the 300-point rubric in `docs/requirements.md`. The page shows only the challenge title, with no description. Source: https://starcoach.ir/hackathon/agentic-ai
- **Format.**
  - Online and three days long. Teams have 1–4 people. Each team gets a mentor.
  - Day 1: workshops (three experience-sharing sessions plus one coordination session).
  - Day 2: the competition starts.
  - "Day 4": end and final judging. The page itself contradicts the "three-day" description.
  - Registration is closed, with 267 of 300 spots taken.
  - Source: https://starcoach.ir/hackathon/agentic-ai
- **Dates.**
  - The StarCoach homepage lists the start as **Wednesday 29 Mehr**, i.e. 2026-10-21. Source: https://starcoach.ir/
  - On 2026-10-22 the event page countdown showed "2 روز و 9 ساعت" left, which suggests it ends around 24–25 Oct 2026. This end date is inferred. Source: https://starcoach.ir/hackathon/agentic-ai
- **Prizes.**
  - 1st place: 50M toman. 2nd: 30M toman. 3rd: 20M toman.
  - There is a separate 80M-toman special prize for the Wallex challenge only.
  - Source: https://starcoach.ir/hackathon/agentic-ai
- **Mentors listed.** Sara Behboudi, Mobina Attarbashian, Ali Moradi, Rouhollah Delpak, Seyed Hossein Mostafavi and Taha Hosseinpour. Source: https://starcoach.ir/hackathon/agentic-ai
- **Judging and deliverables.** The public page has no rubric. The page says only that it ends in "داوری نهایی" (final judging). The 300-point rubric exists only in our `requirements.md`.
- **Video.** No link was found. The likely channels are:
  - Aparat: https://www.aparat.com/Starcoach (fetch timed out)
  - Telegram: https://t.me/StarcoachChnl (fetch timed out)
  - Bale: https://ble.ir/Starcoach
- **Earlier StarCoach event (same format).** The Vibe-Coding hackathon ran 28–30 Mordad, with Liara as main sponsor and ZarinPal, ArvanCloud, Tapsell and Sotoon as sponsors. Source: https://starcoach.ir/hackathon/vibe-coding
  - Public team repos from it show the deliverable style: a Persian dashboard, a "suggested demo path for judges", Docker Compose and an LLM fallback.
  - https://github.com/Rouzbeh2003/ZarinPal-Challenge-Starcoach-Hackathon
  - https://github.com/aliemamidev/Liara-StarCoach-Hackathon
- **Not this event.** Quera lists a separate Torob event, "Torob Turbo", described as a 10-day LLM agentic-product hackathon. It appeared only in a search snippet; the page itself timed out. Source: https://quera.org/events/torob-0406

## 2. Torob's existing in-store–related features

### What a Torob store page shows today
Example page: الکترو سهیل, a Lalehzar-area shop. Source: https://torob.com/shop/369773/%D8%A7%D9%84%DA%A9%D8%AA%D8%B1%D9%88-%D8%B3%D9%87%DB%8C%D9%84/

- **Shown:**
  - Name, plus city and province.
  - A full text address with passage, floor and unit, e.g. "پاساژ گوهر، طبقه -۱، پلاک ۶، واحد ۶".
  - Phone numbers.
  - Torob history: "شروع همکاری با ترب", "زمان فعالیت در ترب", "وضعیت فعلی در ترب: غیرفعال از تاریخ …".
  - A performance score label (امتیاز عملکرد) and the enamad seal.
  - A **"خرید حضوری" badge** with the text "توصیه ترب خرید حضوری از این فروشگاه است".
  - Advisory policy blocks: pay after checking the goods, collect in person, and view the goods in front of the seller.
- **Not shown on that page:** working hours, map or coordinates, messengers, TorobPay, installments, Kalabarg, express delivery.
- **Implication.** Our dataset fields (`weekly_hours`, `lat`/`lon`, `payment_options`, `supports_fast_delivery`) go *beyond* the current public store page. That is room to differentiate.

### "Nearby" and in-person discovery
- The Torob app description promises "حضوری از فروشگاه‌های اطرافت" and "بررسی کالاها، خدمات و فروشگاه‌های اطراف شما در سراسر ایران". It also names the AI assistant **«از ترب بپرس»**. App version 0.18.6.2, updated 12 Mehr 1405. Source: https://cafebazaar.ir/app/ir.torob
- An unofficial Torob API wrapper exposes an `in_person` search flag and a `city` parameter, defaulting to Tehran. Source: https://pypi.org/project/torob/
- **Seller side.**
  - Physical shops can list without a website. The requirement: "فروشگاه شما باید مکان فیزیکی برای مراجعه حضوری کاربر داشته باشد". There is no commission, a listing needs only a price, and buyers call or visit. Source: https://torob.com/sell/
  - The seller app «فروشندگان حضوری ترب» edits price and stock (version 1.8, updated 1404/12/03). Source: https://myket.ir/app/o.com.torob.panel
- **Torob's safe-shopping guide** tells in-person buyers to **call first to confirm opening hours and product details**. This is a pain point Torob itself acknowledges. Source: https://torob.com/pages/safe-shopping-guide/
- **Torob‑Jo (ترب‌جو).** An Instagram-DM bot: you send a post or screenshot and get Torob links for the same or similar products. Images only, no Reels. Source: https://blog.torob.com/shopping-guide/%D8%AA%D8%B1%D8%A8%D8%AC%D9%88/

### TorobPay (ترب‌پی) and installments
- **Terms.** Four installments with no fee (no credit card, cheque or guarantor needed). 25% is paid at purchase and the rest over 3 months. The credit limit is set per user. Sources:
  - https://www.rade.ir/installment/706177-%D8%AA%D8%B1%D8%A8%D9%BE%DB%8C/
  - https://cafebazaar.ir/app/ir.torob ("خرید قسطی با ترب‌پی در ۴ قسط بدون کارمزد")
- **Public sources say online only.** Rade lists TorobPay as "غیر حضوری" (online), and a WooCommerce plugin exists for it. No public source confirms in-store TorobPay. Sources:
  - https://www.rade.ir/installment/706177-%D8%AA%D8%B1%D8%A8%D9%BE%DB%8C/
  - https://fa.wordpress.org/plugins/?p=348176
- **The dataset contradicts this.** It has `payment_options` entries with `channel: "in_person"` for TorobPay: 50 such entries, versus 140 TorobPay entries with channel `unknown`.
  - Other providers: SnappPay (53 in_person / 36 unknown), DigiPay (45 / 16), Tara (26 / 11), Azkivam (5 unknown).
  - Only 266 of 6,476 shops have any payment option.
  - Each entry also has `min_price_toman`, `max_price_toman` and `category_names`, mostly null.
  - **UX rule:** show TorobPay at the till only where `channel == in_person`. Label `unknown` as "declared by seller, channel unconfirmed". This is required by requirements.md ("with the information type made clear").
- **Competitor patterns.**
  - Basalam's **SalamPay** in-store mode: the customer scans the shop's QR or opens a link, then picks a credit plan. Source: https://basalam.com/blog/salampay-inpersooon/
  - **SnappPay** added routing (مسیریابی) to the store address in its in-person section. Source: https://digiato.com/iran-technology-news/snappay-new-features-in-person-purchases (found via search; the fetch timed out)

### Kalabarg (کالابرگ)
- **What it is.** A government electronic voucher. Credit is loaded onto the household head's bank card and can be spent only on listed **basic foodstuffs** (dairy, eggs, chicken, oil, rice, legumes, sugar and so on). It cannot be withdrawn as cash. Sources:
  - https://www.rade.ir/?p=706085
  - https://khanesarmaye.com/electronic-subsidy/ (unofficial)
- **Not for phones or appliances.** You cannot buy phones or home appliances with it. Source: https://khanesarmaye.com/electronic-subsidy/
- **Accepting stores.**
  - Chains: Ofogh Kourosh, Refah, Hyperfamily, Daily Market and others, plus Digikala and Snapp online. Source: https://www.beytoote.com/housekeeping/sundries/kalabarg-store.html
  - Many small shops are connected too. The authoritative list is in the «شما» app / shoma.sfara.ir. Sources:
    - https://www.taadolnewspaper.ir/fa/news/337488/
    - https://www.shahrekhabar.com/adv/177183037226942
- **1405 status.** Still running. Some butchers and poultry shops stopped accepting it because the government was slow to reimburse them. Sources:
  - https://fararu.com/fa/news/1010864/
  - https://www.digikala.com/mag/kalabarg-1405-increase-mordad-payout/
- **Dataset.** There is **no Kalabarg field** in `shops.csv`, and the string کالابرگ appears 0 times. The dataset's categories are mostly electronics and electrical, so Kalabarg is largely irrelevant here. Treat it as "unknown" everywhere.

### Express delivery
- `supports_fast_delivery`: true for 1,168 shops, false for 433, null for 4,875 (Dataset).
- No public Torob page describing the feature was found.

## 3. Pain points of in-store shopping in Tehran

Each pain point is listed with its evidence and what the product can do about it.

- **Wasted trips: closed shops and unknown hours**
  - Torob advises calling ahead to confirm hours. Source: https://torob.com/pages/safe-shopping-guide/
  - Passage hours vary by shop and on holidays.
    - Alaeddin: about 8–22 on weekdays and 8–16 on holidays. A commenter says not all shops open on Fridays. Source: https://www.alibaba.ir/mag/aladdin-market/
    - Balad lists Alaeddin as 9–21 daily. Source: https://balad.ir/p/%D9%BE%D8%A7%D8%B3%D8%A7%DA%98-%D8%B9%D9%84%D8%A7%D8%A1%D8%A7%D9%84%D8%AF%DB%8C%D9%86-Pn7aB7YpEmL3c5
    - Most Lalehzar shops open about 10–20. Sources: https://balad.ir/blog/?p=3104, https://balad.ir/blog/?p=2168
  - Dataset:
    - 4,473 shops have `weekly_hours`, 2,003 have empty `{}`.
    - Friday is `closed` for **3,473 of 4,473 (78%)**.
    - Only 117 shops declare a real split shift (midday break), e.g. 10–16 and 18–21.
    - Statuses are `declared`, `closed` and `unsupported`. There is also a placeholder second shift of 00:00–00:00, which must be ignored.
  - **Product fix:** an "open when I arrive" filter and a warning when the route crosses a closing time.
- **Price uncertainty and haggling**
  - The same phone was quoted at 1.65M vs 1.68M toman in neighbouring shops. Card readers have been charged more than the agreed price. Sources:
    - https://netran.net/mag/%D9%86%D9%82%D8%AF-%D9%BE%D8%A7%D8%B3%D8%A7%DA%98-%D8%B9%D9%84%D8%A7%D8%A7%D9%84%D8%AF%DB%8C%D9%86/
    - https://www.alibaba.ir/mag/aladdin-market/
  - Khabaronline: "why Alaeddin is no longer a trusted reference". Source: https://www.khabaronline.ir/news/324657/
  - **Product fix:** show the recorded price together with `last_price_changed_at` and its age. Never imply that this price is guaranteed at the counter.
- **Stock uncertainty**
  - Torob's seller app lets shops edit stock (https://myket.ir/app/o.com.torob.panel). But the requirements say category alone does not mean the product is in stock.
  - **Product fix:** a "call or WhatsApp to confirm" button and a pre-written question for the seller (follow-up). Label every result as one of: offer recorded / category only / confirmed by user.
- **Finding the unit inside a passage**
  - Alaeddin has 9 floors and about 1,100 units, with small, poor elevators. Source: https://www.alibaba.ir/mag/aladdin-market/
  - Dataset addresses include floor and unit, e.g. "پاساژ علالدین 2، طبقه 6، واحد 622".
  - **Product fix:** parse the passage, floor and unit. Group stops by passage and order them by floor.
- **Parking and traffic**
  - The central traffic zone (طرح ترافیک) runs Saturday–Wednesday, 6:30–18:00, and needs a permit. Source: https://khodro45.com/mag/traffic-zone-map/
  - Alaeddin has 2 parking floors. Source: https://www.alibaba.ir/mag/aladdin-market/
  - Shoush has very little parking. Source: https://balad.ir/blog/?p=3904
  - Metro access:
    - Alaeddin: Ferdowsi, Saadi, Imam Khomeini and Hasanabad stations. Source: https://www.alibaba.ir/mag/aladdin-market/
    - Lalehzar: Imam Khomeini and Saadi; Darvazeh Dowlat for the Manouchehri end. Sources: https://balad.ir/blog/?p=2168, https://www.hamshahrionline.ir/news/970682/
  - **Product fix:** suggest metro first and warn about the traffic-zone hours.
- **Crowding, trust and safety**
  - About 30,000 visitors a day at Alaeddin. Fire and permit issues, poor ventilation. Source: https://www.alibaba.ir/mag/aladdin-market/
  - Trust signals worth showing: years on Torob, active/inactive status and enamad. Source: https://torob.com/shop/369773/
- **Payment options**
  - Shoppers want to know before the trip whether installments or BNPL work at the till. See section 2: the `in_person` vs `unknown` channel split.
- **Out-of-town buyers**
  - Lost shop days plus travel cost make a wasted trip expensive. Source: https://irpakhsh.com/aladdin-passage-mobile-phone-accessories-wholesale/ (found via search; not fetched directly)

## 4. Neighbourhood geography (dataset `location_label`)

All counts, median coordinates, passages and categories below are computed from the Dataset. External sources are given where they confirm a mapping.

| location_label | shops | median lat, lon | main passages (from addresses) | dominant categories |
|---|---|---|---|---|
| فردوسی | 3,282 | 35.6921, 51.4225 | پاساژ بوشهری (146), **چارسو** (127), اتحادیه, امجد, فراز, نادری; Lalehzar addresses: 1,478 | building wire and cable, switches and sockets, lighting, panel lights, mobile phones |
| شیخ هادی | 1,587 | 35.6950, 51.4088 | **علاءالدین / علالدین / علاالدین ۲** (~275), یگانه, حافظ, بزرگمهر | mobile phones, mobile accessories, CCTV, headphones, TV |
| بهارستان | 616 | 35.6904, 51.4258 | پاساژ کیان (71), صدقی‌نژاد, فرهاد, الماس, سعدی قدیم | generators, pumps, sump pumps, car and motorcycle parts |
| آسمان | 151 | 35.7770, 51.3523 | مجتمع تجاری **اپال** (Opal) | mobile phones, accessories, pet food |
| باغ فیض | 107 | 35.7386, 51.3143 | **کوروش مال** (Kourosh Mall) | clothing, mobile phones, watches |
| ایرانشهر | 99 | 35.7135, 51.4214 | مجتمع کریمخان, مجتمع تجارت ایران | printer cartridges, label printers, laptops, barcode readers |
| سنائی | 96 | 35.7188, 51.4221 | مجتمع مرجان | books, cosmetics, industrial automation |
| سهروردی | 82 | 35.7212, 51.4291 | نگین آبی, مجتمع امین | machine-made carpets, cosmetics, clothing |
| تجریش | 76 | 35.8059, 51.4300 | پاساژ قائم, البرز, تندیس, بازار تجریش | mobile phones, cosmetics, jewellery |
| جنت آباد جنوبی | 68 | 35.7382, 51.3099 | پاساژ شاهین, ساحل | car services, supplements |
| امجدیه | 54 | 35.7155, 51.4282 | پاساژ مرجان, جار سنتر | women's manteaus and suits |

The Dataset also has smaller labels: آذربایجان (51; medical, Sinuhe passage), آشتیانی (37), کیانشهر شمالی, بهار, درختی (Aren mall), مطهری (Besat fruit and fish market), فلسطین, عباس آباد, ولیعصر and others.

**Mapping checks:**
- **شیخ هادی ≈ Alaeddin / Jomhouri mobile bazaar.** Balad puts Alaeddin in "محله شیخ هادی", at Hafez St × Jomhouri Eslami St. Sources:
  - https://balad.ir/p/%D9%BE%D8%A7%D8%B3%D8%A7%DA%98-%D8%B9%D9%84%D8%A7%D8%A1%D8%A7%D9%84%D8%AF%DB%8C%D9%86-Pn7aB7YpEmL3c5
  - Alaeddin 2 is also tagged `tehran-nei-sheykh-hadi`: https://balad.ir/p/%D8%A8%D8%A7%D8%B2%D8%A7%D8%B1-%D8%B9%D9%84%D8%A7%D8%A7%D9%84%D8%AF%DB%8C%D9%86-tehran-nei-sheykh-hadi_cell-phone-store-3sHs5UHEBaCZNk
- **فردوسی ≈ Lalehzar (lighting and electrical) and Charsou.**
  - Lalehzar is Tehran's first chandelier and lighting market. Source: https://balad.ir/blog/?p=3104
  - Charsou sits at the SE corner of Jomhouri Eslami × Pol-e Hafez, directly across from Alaeddin, but the Dataset tags it فردوسی. Source: https://www.kojaro.com/attraction/9018-charso-market/
  - Balad slugs Lalehzar shops as `tehran-nei-ferdowsi`. Source: https://balad.ir/p/لوستر-روژان-tehran-nei-ferdowsi_home-goods-and-accessories-store-4VwHM7IkaEodeM
- **بهارستان ≈ Amin Hozour / Saadi south (pumps, generators, appliances).** Balad describes Seh-rah Amin Hozour as an old home-appliance and electrical market along Amirkabir St. Source: https://balad.ir/blog/?p=2168
  - The Dataset has no "امین حضور" string in any address, so this mapping is inferred.
- **باغ فیض.** Wikipedia names Kourosh Mall as its landmark (35.7442, 51.3225). Source: https://en.wikipedia.org/wiki/Bagh_Feiz
- **امجدیه.** The former name of Shahid Shiroudi Stadium (35.7103, 51.4275). Source: https://en.wikipedia.org/wiki/Shahid_Shiroudi_Stadium

**Key passage coordinates:**

| Place | lat, lon | Source |
|---|---|---|
| Alaeddin passage | 35.6950, 51.4113 | Dataset median of 536 shops |
| Charsou | 35.6948, 51.4123 | Dataset median of 171 shops |
| Boushehri passage (Lalehzar) | 35.6898, 51.4229 | Dataset median of 357 shops |
| Lalehzar street shops | 35.6908, 51.4229 | Dataset median of 1,480 shops |
| Kian passage (Baharestan) | 35.6899, 51.4259 | Dataset |
| Opal | 35.7770, 51.3514 | Dataset |
| Kourosh Mall | 35.7384, 51.3139 | Dataset |
| Tajrish bazaar area | 35.8059, 51.4302 | Dataset |
| **Iran Mall** | 35.753389, 51.192417 | https://en.wikipedia.org/wiki/Iran_Mall |
| **Paytakht Computer Complex** | no coordinate source found | Address: Valiasr St above Vanak Sq., start of Mirdamad, https://www.kojaro.com/attraction/9006-مجتمع-کامپیوتر-پایتخت/ |

- **Iran Mall:** 0 shops in the Dataset.
- **Paytakht:** only 2 Dataset addresses mention پایتخت. Both are probably different businesses.
- **So Iran Mall and Paytakht are outside the dataset's sampled areas. Don't demo them.**

**Category → Tehran market (بورس)**, per Balad:
- Mobile and computer: Paytakht, Charsou, Alaeddin, Iran Mobile Bazaar (Jomhouri), Iranian Traders Center.
- Home appliances: Amin Hozour, Shoush, Gholhak.
- Lighting: Lalehzar.
- Tools: Imam Khomeini St / Hasanabad, Sheikh Hadi St, Khayyam.
- Source: https://balad.ir/blog/?p=2168

## 5. Competitors and UX inspiration

- **Google Maps product search (US, late 2024).**
  - Product search shows a carousel with in-stock status, and tapping a store gives hours, directions and contact.
  - It needs merchant inventory feeds.
  - Sources: https://keyword.wordtracker.com/blog/search-news/google-maps-now-lets-you-search-for-products-nearby, https://www.searchenginejournal.com/google-maps-launches-product-search-steps-for-retailers/532696/
  - **Pattern to copy:** a product card followed by "who has it nearby", then the store sheet (hours, route, call).
- **Google Lens in-store (Dec 2024).**
  - Snap a product in the aisle to see whether this store's price is competitive, similar items in stock nearby, and reviews.
  - Store detection uses proximity.
  - Sources: https://searchengineland.com/google-in-store-shopping-ai-powered-comparisons-448476, https://www.dacgroup.com/insights/local-search-news/google-lens-adds-additional-ai-powered-in-store-and-local-shopping-features/
  - **Pattern:** "you are at shop X; it is Y% above the cheapest seller 200 m away".
- **Amazon Rufus.**
  - Conversational product-type comparisons ("difference between X and Y").
  - Answers grounded in listings, reviews and Q&A.
  - **Clickable suggested follow-up questions and categories.**
  - Sources: https://www.aboutamazon.co.uk/news/retail/amazon-ai-shopping-tools, https://www.retail-insight-network.com/news/amazon-ai-shopping-assistant-rufus
  - **Pattern:** chips for next questions, so the user does not have to type.
- **Perplexity Shopping.**
  - Product cards with a plain-language comparison built from reviews and specs, presented as unsponsored.
  - Its CEO admitted they "don't fully understand" the ranking, which is a counter-example.
  - Sources: https://www.websitebuilderexpert.com/news/perplexity-shopping-assistant/, https://dc.fortune.com/2024/11/18/perplexity-ai-ceo-shopping-product-recommendation-search-tools/
  - **Lesson:** give an explicit "why recommended" (price rank, distance, open now, payment fit, data freshness).
- **Digikala physical stores** (Jomhouri, Saadat Abad).
  - Store landing pages show address, hours (e.g. Jomhouri 9:30–21), product testing before purchase, free advice and in-store discounts.
  - Sources: https://www.digikala.com/landing/dkstores-jomhouri/, https://www.digikala.com/landing/dkstores_general/
- **SnappPay / Basalam SalamPay.**
  - In-store BNPL: SalamPay via QR, and SnappPay added a store-finder with routing.
  - Sources: https://basalam.com/blog/salampay-inpersooon/, https://digiato.com/iran-technology-news/snappay-new-features-in-person-purchases
- **Torob's own AI products:** «از ترب بپرس» in the app and Torob‑Jo on Instagram.
  - The challenge probably expects an agent that goes *beyond* these, towards visit planning and seller follow-up.
  - Sources: https://cafebazaar.ir/app/ir.torob, https://blog.torob.com/shopping-guide/%D8%AA%D8%B1%D8%A8%D8%AC%D9%88/

---

## Unverified / open questions

- **Four-step flow: NOT found** in any public source. Recover it from the challenge video, the StarCoach Telegram channel (https://t.me/StarcoachChnl), or Aparat (https://www.aparat.com/Starcoach). Both fetches timed out.
  - Working hypothesis, NOT a source: something like (1) search or describe the need → (2) compare products and sellers → (3) pick a store and plan the visit (area, hours, route, payment) → (4) follow up with the seller.
  - The Product criterion in requirements.md lists "product search, comparing options, finding a seller in the desired area, follow-up". This is the best available proxy.
- **Exact hackathon end date and submission deadline.** Only a countdown ("2 روز و 9 ساعت" on 2026-10-22) and "Wednesday 29 Mehr" were seen.
- **The Torob challenge's own text and pain-point list** are not public. The event page shows only the title.
- **Whether TorobPay really works at the physical till.** Public sources say online only, while the dataset has an `in_person` channel. Ask the mentors, and show the channel honestly.
- **Kalabarg.** It is in requirements.md, but the dataset has no field for it. Clarify whether it will appear in the "final version" of the data.
- **Express delivery semantics.** What `supports_fast_delivery` means (same-day? courier?) is undocumented.
- **Paytakht Computer Complex coordinates.** No sourced lat/lon was found. It is outside the dataset areas in any case.
- **Charsou labelling.** Charsou sits across from Alaeddin but is labelled فردوسی (161) more often than شیخ هادی (9). Check whether `location_label` comes from a reverse-geocoder (Balad/Neshan neighbourhood polygons).
- **Amin Hozour.** No dataset address contains it. The بهارستان ≈ Amin Hozour mapping is inferred from categories (pumps, generators) and location.
- **Hours from tourism blogs** (Alaeddin 8–22 vs Balad 9–21) disagree. Trust per-shop `weekly_hours` over passage-level claims.
- **«از ترب بپرس».** Its UX and capabilities were not documented anywhere public beyond one line in the app description.
