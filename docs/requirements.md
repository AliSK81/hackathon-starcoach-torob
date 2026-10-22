**System Description — Torob In-Store Shopping Assistant Challenge**

The system is an intelligent assistant for in-store shopping from small and large stores, passages, and shopping centers in Tehran. Its four-step flow is defined in the challenge video; additional features may be added at the team's discretion, and several pain points of in-store shopping are described in the video. The challenge video is mandatory viewing — not all points are in the text, and the video plus the challenge text together define the full task.

**Dataset (must be used)**
The downloadable Torob dataset covers Tehran stores and products; some fields exist for only part of the records.

*Store and business information*
- Store ID, business name and type, activity category, and introductory description.
- Store images, where present.
- Torob presence history and registered licenses, where present.

*Location, working hours, and contact*
- Short text address, geographic coordinates, and location description (e.g., passage name, floor, unit) wherever recorded in the address.
- Weekly working-hours schedule, for stores that registered it.
- Registered contact channels — phone and messengers such as WhatsApp and Bale. Which contact fields are publishable is determined in the final version.

*Product information (BaseProduct)* — complete, about the product itself
- Product ID, Persian and English title, brand, and category.
- Technical specifications and product description, where present.
- Product images, where present.

*Product in store (ProductInStore)* — a store's extra details about a specific product it carries
- The link between each product and its sellers, for viewing a store's products or comparing sellers of a product.
- Seller-registered title and description, price and price unit; warranty, provider, and duration wherever recorded.
- Time of last recorded price change.
- Distinguishes a store that has a specific product from a business whose activity category alone is known; activity category alone does not indicate a product is in stock.

*Purchase conditions and store capabilities*
- In-store TorobPay acceptance status and installment-purchase services declared by the seller, with the information type made clear.
- Kalabarg (voucher) support and express delivery, wherever recorded.

*Dataset notes*
- The `offers` table shows which store offered which product at what price and when the price was last updated (data is from last week).
- The `products` and `shops` tables are self-explanatory.
- In the `shops` table, most store names (6,364 of 6,476) are fake.
- All store phone numbers are fake.
- Other information, such as location, is real.
- The 112 stores with non-fake names are those whose Instagram page or website is given in the table (22 Instagram, 90 website); these are non-fake so participants working with their Instagram have consistent data.
- All stores are in Tehran, but they are 10% of Tehran's Torob stores and selectively drawn from certain Tehran areas.
- Each store's products are capped at 300; overall, 331,506 offers cover 225,903 unique products.

**Product Design Notes and Requirements**

*UX design*
- Not all user flows need to go through chat. Cards, filters, and buttons help the user proceed without asking again.
- Search and comparison results are shown clearly; the user understands why a product or store was suggested and what the next step is.
- The user can easily change area, budget, and purchase conditions and see the result.

*Information transparency*
- Recorded price, price-change time, and confirmed availability are not conflated.
- Unknown information is shown clearly.

*Language and platform*
- Focus on Persian, right-to-left experience, and mobile use.

*Technical priorities*
- Good product and UX are the priority in this hackathon; scalable service engineering is secondary.

**Deliverables**

*Demo video (mandatory)*
- Submitting a project demo video is mandatory.
- The video is about 5 minutes and demonstrates and explains the project's performance.
- If no demo video is submitted, the entry is removed from judging.
- Video quality affects the overall score.
- The video shows the output; no need to show source code. Performance, impact, output, and demonstrable items matter. The work is presented completely — this is very important.
- If unable to speak, a silent video of the output only is acceptable but scores fewer points; this is better than no points. No special editing is needed.

**Judging Criteria (300 points)**

*Product — 75*
Whether the solution genuinely solves the in-store shopping problem and covers the requested items: product search, comparing options, finding a seller in the desired area, follow-up, and so on.

*UX and user experience — 75*
Whether the user can work with the agent easily and without hassle, and whether the UI/UX is appropriate — how simple, smooth, and user-friendly the design is.

*Intelligence — 50*
Whether the assistant can complete the purchase process more fully through seller follow-up, substitution, and attention to visit conditions (time, location, user needs, etc.).

*Deploy — 40*
Quality and stability of the deploy process (publishing and running the project on a server) and final execution in the operational environment.

*Technical implementation — 40*
Technical level of the challenge: code structure, use of appropriate tools and technologies, performance, and scalability.

*Dataset — 20*
Whether product and store information are used correctly and displayed transparently and understandably to the user.

**Scoring Table**
| Criterion | Points |
|---|---|
| Product | 75 |
| UX and user experience | 75 |
| Intelligence | 50 |
| Deploy | 40 |
| Technical implementation | 40 |
| Dataset | 20 |
| **Total** | **300** |