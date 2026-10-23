# Torob In-Store Shopping Assistant — Challenge Requirements

Sources:
- **[Text]** the written challenge text (the original content of this file).
- **[Q&A]** organizers' answers in the hackathon group (§9).
- **[Video]** the challenge announcement video by the StarCoach / Torob product owner (transcript provided by the user, 2026-10-23; transcription typos fixed).

The video and the text together define the task. Where they overlap, both are cited.

---

## 1. Goal

Build an **intelligent, agent-based assistant for in-person shopping** in Tehran's small and large stores, passages (پاساژ) and shopping centers. [Text, Video]

- It guides the user along the whole in-person purchase path. [Video]
- It must have a very good user experience and UI/UX. [Text, Video]
- Teams may add their own extra features on top of the required flow. [Text, Video]

## 2. The required four-step flow [Video]

| Step | What the assistant must do |
|---|---|
| **1. Find the right product** | Help the user work out *what* product they want, even when they don't know the model yet (example: "I want sneakers but don't know which model suits me"). Ask about the user's needs and preferences, compare products and prices, and finally suggest suitable products and models. |
| **2. Find stores that have it, nearby** | Find the stores that carry the chosen product. Using the user's location, suggest nearby areas and nearby stores. |
| **3. Compare the stores** | Compare the candidate stores by **price**, **distance** (near or far), and **working hours**. |
| **4. Contact the stores** | Help the user get in touch with the stores, e.g. ask about working hours. Many stores do not update their prices or stock, so the agent itself should be able to **contact stores, ask questions and get answers**, and then give the user accurate, up-to-date information. |

## 3. Pain points the product must address [Video]

1. **The user doesn't know the right model yet.** The assistant must help them choose a suitable model (step 1).
2. **Recorded prices are stale.** The price recorded for a store may be old. Teams may use services like Google's "Let Google Call" (an AI that calls stores) to contact stores and present an updated price and stock.
3. **No answer, or the store is closed.** Sometimes the seller doesn't reply, or the user arrives and the store is closed. The agent must be smart and **quickly suggest equivalent or alternative stores**.
4. **Finding the shop inside a passage.** People often find the passage but can't find the exact shop in it. Using the shop's textual information (e.g. from Google or the address text), suggest a **more precise location of the shop inside the passage** (floor, unit, landmarks).
5. **Installment-only shoppers.** A very important case: when the user only wants options with **installment (credit) purchase**, the assistant must apply a **filter that shows only stores offering credit purchase services**.

## 4. Dataset (must be used) [Text, Video]

The downloadable Torob dataset covers in-person stores in Tehran, a large list of their products, and other information. Some fields exist for only part of the records.

### 4.1 Store and business information
- Store ID, business name and type, activity category, introductory description.
- Store images, where present.
- Torob presence history and registered licenses, where present.

### 4.2 Location, working hours and contact
- Short text address, geographic coordinates, and location description (e.g. passage name, floor, unit) wherever recorded in the address.
- Weekly working-hours schedule, for stores that registered it.
- Registered contact channels: phone and messengers such as WhatsApp and Bale. Which contact fields are publishable is decided in the final version.

### 4.3 Product information (BaseProduct) — about the product itself
- Product ID, Persian and English title, brand, category.
- Technical specifications and product description, where present.
- Product images, where present.

### 4.4 Product in store (ProductInStore) — a store's details about a product it carries
- The link between each product and its sellers, for viewing a store's products or comparing the sellers of a product.
- Seller-registered title and description, price and price unit; warranty, provider and duration wherever recorded.
- Time of the last recorded price change.
- A store that has a specific product is different from a business whose activity category alone is known. **The activity category alone does not mean the product is in stock.**

### 4.5 Purchase conditions and store capabilities
- In-store TorobPay acceptance and installment-purchase services declared by the seller, with the type of information made clear.
- Kalabarg (voucher) support and express delivery, wherever recorded.

### 4.6 Dataset notes
- `offers`: which store offered which product, at what price, and when the price was last updated (data is from the last week).
- `products` and `shops` are self-explanatory.
- In `shops`, most store names (6,364 of 6,476) are fake. All store phone numbers are fake. Other information, such as location, is real.
- The 112 stores with real names are those whose Instagram page or website is given (22 Instagram, 90 website), so teams working with Instagram have consistent data.
- All stores are in Tehran, but they are 10% of Tehran's Torob stores, selectively drawn from certain areas.
- Each store's products are capped at 300. In total, 331,506 offers cover 225,903 unique products.

## 5. Product design requirements [Text]

### 5.1 UX
- Not every flow has to go through chat. Cards, filters and buttons help the user move on without asking again.
- Search and comparison results are shown clearly. The user understands **why** a product or store was suggested and **what the next step** is.
- The user can easily change **area, budget and purchase conditions** and see the result.
- A high-quality, easy, comfortable experience and a suitable UI/UX are very important. [Video]

### 5.2 Information transparency
- Recorded price, price-change time and confirmed availability are never mixed up.
- Unknown information is shown clearly as unknown.

### 5.3 Language and platform
- Persian first, right-to-left, mobile use.

### 5.4 Technical priorities
- Good product and UX come first in this hackathon. Scalable service engineering is secondary.

## 6. Deploy [Text, Video]
- The product must be deployed (published and running on a server). This is part of the judging.
- Teams can use **Liara** (لیارا), another sponsor, as the deploy infrastructure. [Video]

## 7. Deliverables [Text]

### Demo video (mandatory)
- A demo video is mandatory. Without it, the entry is removed from judging.
- About 5 minutes. It demonstrates and explains the project's performance.
- Video quality affects the overall score.
- Show the output, not the source code. Performance, impact, output and demonstrable items matter. Present the work completely — this is very important.
- A silent video of the output only is acceptable if speaking is not possible, but it scores fewer points. No special editing is needed.

## 8. Judging criteria (300 points) [Text]

The ranking and scores are based entirely on these criteria; read them closely. [Video]

| Criterion | Points | What is judged |
|---|---|---|
| Product | 75 | Does the solution really solve in-store shopping and cover the requested items: product search, comparing options, finding a seller in the desired area, follow-up, and so on. |
| UX and user experience | 75 | Can the user work with the agent easily and without hassle; is the UI/UX appropriate — simple, smooth, user-friendly. |
| Intelligence | 50 | Can the assistant complete the purchase process more fully through seller follow-up, substitution, and attention to visit conditions (time, location, user needs, etc.). |
| Deploy | 40 | Quality and stability of the deploy process (publishing and running on a server) and final execution in the operational environment. |
| Technical implementation | 40 | Code structure, appropriate tools and technologies, performance, scalability. |
| Dataset | 20 | Product and store information are used correctly and shown transparently and understandably. |
| **Total** | **300** | |

## 9. Organizer clarifications [Q&A]

Source: organizers' answers in the hackathon group, 2026-10-21 … 2026-10-23 (pasted by the user; typos fixed).

1. **The goal is an *in-person* shopping assistant.** A few shops have a website or Instagram in the dataset; they can be used to test special scenarios.
2. **Both halves matter:** choosing the product (model) *and* choosing the store for an in-person visit. A user normally needs both to finish a purchase.
3. **When the user can't find the product,** the agent should know which shopping centre or area sells what, even using knowledge beyond the dataset (a good model may know where each item's «بورس» (trade hub) is in Tehran). It should advise going to that hub and send the user a **location widget**.
4. **Seller contact may be simulated (mock).** Voice call, SMS or WhatsApp is the team's choice; a polished one helps. What matters is that it is **efficient and easy for both seller and buyer**, ideally without bothering the seller (like "Let Google Call"). It is a plus, not the main criterion.
5. **Sources outside the dataset are welcome,** but **if something relevant is in the dataset and is not suggested, that counts as a fault.**
6. **There is no reviews dataset.** Showing users a good review of products is important; creative ideas are welcome.
7. **All products must be covered (baseline).** Extra, category-specific components (e.g. for clothing) that improve the experience earn points. Clothing is only an example.
8. Questions go to the group, not private messages (process note, no product requirement).

## 10. Requirement checklist

Each line is one checkable requirement. `docs/ROADMAP.md` maps each ID to a phase.

| ID | Requirement | Source |
|---|---|---|
| R1 | Help the user choose a product/model when they don't know it: ask needs, compare products and prices, suggest models | Video step 1, pain 1 |
| R2 | Find stores that carry the chosen product (an offer exists, not just a category match) | Video step 2; Text 4.4 |
| R3 | Use the user's location to suggest nearby areas and stores | Video step 2 |
| R4 | Compare stores by price, distance and working hours | Video step 3 |
| R5 | Help the user contact stores (e.g. ask about hours) | Video step 4 |
| R6 | The agent contacts stores itself to confirm current price and stock, then reports back | Video step 4, pain 2 |
| R7 | When a seller doesn't answer or a store is closed, quickly suggest equivalent/alternative stores | Video pain 3; Intelligence |
| R8 | Give a precise in-passage location for a shop (floor, unit, landmarks) | Video pain 4; Text 4.2 |
| R9 | Filter to stores offering installment / credit purchase | Video pain 5; Text 4.5 |
| R10 | Use the Torob dataset (shops, products, offers) correctly | Text 4; Dataset |
| R11 | Show store info: name/type, category, description, images, history, licenses where present | Text 4.1 |
| R12 | Show address, coordinates, passage/floor/unit, weekly hours, contact channels | Text 4.2 |
| R13 | Show product info: titles, brand, category, specs, description, images | Text 4.3 |
| R14 | Show a product's sellers and a store's products; seller title, price, unit, warranty, last price change | Text 4.4 |
| R15 | Never present an activity category as "in stock" | Text 4.4 |
| R16 | Show TorobPay, installments, Kalabarg, express delivery, with the information type made clear | Text 4.5 |
| R17 | Cards, filters and buttons — not only chat | Text 5.1 |
| R18 | Clear results; explain why each item is suggested and what the next step is | Text 5.1 |
| R19 | Easy change of area, budget and purchase conditions, with visible results | Text 5.1 |
| R20 | Keep recorded price, price-change time and confirmed availability separate | Text 5.2 |
| R21 | Show unknown information clearly | Text 5.2 |
| R22 | Persian, RTL, mobile-first | Text 5.3 |
| R23 | Deployed and stable on a server (Liara suggested) | Text 6; Video |
| R24 | Good code structure, tools, performance | Text 8 |
| R25 | Demo-ready product for a ~5-minute demo video showing the full flow | Text 7 |
| R26 | Know which shopping centre / area sells what (Tehran «بورس»), suggest going there when the product isn't found, with a location widget | Q&A 3 |
| R27 | Seller contact that is easy for both sides (mock allowed): the seller answers with minimal effort; the buyer gets the answer in the app | Q&A 4 |
| R28 | Dataset first: never skip a relevant dataset result; outside knowledge is extra and labeled | Q&A 5 |
| R29 | A useful product review for the user, honestly sourced (no reviews dataset) | Q&A 6 |
| R30 | All categories covered; category-specific components where they help (e.g. clothing) | Q&A 7 |
| R31 | Use the website / Instagram of the shops that have them for special scenarios | Q&A 1 |
