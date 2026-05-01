# Hamilton backup processor evaluation (2026-05-01)

**Author:** Claude (research session, async — for Chris's later review)
**Status:** Recommendation. Not yet a DEC-NNN decision. Promote to `decisions_log.md` once Chris signs off.
**Companion docs:** `docs/research/merchant_processor_comparison.md` (broader Fiserv vs Stripe vs Helcim baseline), `docs/decisions_log.md` (DEC-062 standard-merchant classification, DEC-064 dual-processor mandate).

---

## TL;DR

**Recommended backup: Helcim** (Calgary, AB). It is the only candidate that combines (a) a Canadian-domiciled CAD-native processor with explicit interchange-plus pricing visible online, (b) zero monthly / PCI / cancellation fees and a $15 chargeback fee that's refunded if you win, (c) a documented Smart Terminal HTTP API that can be driven from any client (iPad-friendly via REST, no native iOS SDK required), and (d) a Calgary-based underwriting team that does high-touch review at signup rather than light-touch onboarding followed by surprise freezes. The trade-offs are real — Helcim does freeze accounts, has a 6-month reserve clause on terminations, and has surface-level "restricted business" language that could be invoked against a bathhouse — but it's the least-bad blend of price, control, and escape valve.

**Runner-up: Moneris** (Toronto, ON, RBC/BMO joint venture). Slower contract cycle, more conservative pricing, and equipment rental fees that smell like a 2010s telco bill — but Moneris is the most-Canadian-establishment processor available, settles T+1 in CAD, has a published Moneris Go API + iOS SDK, and is the processor you actually want if Hamilton's reputation deteriorates in a way that makes a fintech (Helcim, Stripe, Square) twitchy. Moneris is the "the bank backs us" option.

**Explicitly NOT recommended for the backup role: Stripe Terminal** (despite best-in-class iOS SDK) and **Square Canada** (despite zero hardware cost). Both have well-documented patterns of terminating accounts in adult-adjacent categories with little notice and 90-180 day fund holds. Hamilton already accepts that Fiserv (incumbent) is the lowest-perception-risk processor; the backup must NOT introduce a higher freeze risk than the primary. That disqualifies Stripe and Square.

**File path written to:** `/Users/chrissrnicek/hamilton_erp/docs/research/hamilton_backup_processor_evaluation.md`

---

## Context — why Hamilton needs a backup at all

Three threads converge here:

1. **DEC-062 (standard-merchant classification, 2026-04-30):** Hamilton is a hospitality / wellness venue, not a formally adult-classified business. Hamilton's MCC code, marketing, and merchant agreement all describe a men's bathhouse / gym / wellness facility — not adult entertainment. Fiserv (MID 1131224) underwrote Hamilton on those terms.

2. **The perception-driven termination scenario.** Even with a clean MCC and standard-merchant classification, processors can change their minds. A risk analyst sees the venue name, Googles it, sees adult-adjacent imagery in a third-party review, and quietly flags the merchant for "enhanced review." Two weeks later the account is closed. This is not theoretical — it has happened to massage parlors, gay bars, and wellness venues with names processors found "off-brand." See the Stripe Hacker News thread (`https://news.ycombinator.com/item?id=32854528`) and Helcim's own BBB complaints for examples of post-onboarding terminations.

3. **DEC-064 (dual-processor mandate, 2026-05-01):** Every Hamilton venue must have a primary AND backup processor. Both pre-approved. Both integration-tested. Swappable in hours via a config flag (the merchant adapter system already designed in `decisions_log.md` ~line 1672 onward). The backup account stays dormant — no live transactions — but the underwriting is done, the merchant agreement is signed, the terminal is in a drawer, and the iPad app's adapter has been smoke-tested in sandbox.

The backup is insurance. The premium is paid in: small annual fees (some processors), the time to do underwriting twice, and the cost of one extra terminal sitting in a drawer. The payout is: when the primary freezes (Friday afternoon, of course, never on a Tuesday morning when banks are open), Hamilton flips a config flag and keeps trading. Without a backup, a freeze means closing the venue until a new merchant agreement is underwritten — typically 5-15 business days during which Hamilton is collecting cash only.

The criteria for the backup are therefore different from the criteria for the primary:

- The backup does NOT have to be the cheapest. Fiserv handles 95%+ of Hamilton's volume; the backup handles 0% in normal operation.
- The backup MUST be diversified from the primary — different parent company, different underwriting bank, different risk-policy lineage. (Clover Canada is Fiserv-owned, so Clover does NOT count as a backup. Eliminated up front.)
- The backup MUST be approvable for a wellness venue without contortions or undisclosed-business-type signups. If the application requires concealing what Hamilton does, the eventual freeze is guaranteed — it's just delayed.
- The backup SHOULD have an iPad-compatible API or SDK so the existing cart drawer code can be adapted in a single sprint.

---

## Evaluation table

| Criterion | Helcim | Moneris | Stripe Terminal CA | Square Canada |
|---|---|---|---|---|
| **Card-present rate** | Interchange + 0.40% + 8¢ (Tier 1, $0–50k/mo); drops to +0.15% + 6¢ at $1M+ | 2.65% + $0.10 flat | 2.70% + $0.05 flat | 2.6% + $0.15 flat |
| **Card-not-present** | Interchange + 0.50% + 25¢ | 2.85% + $0.30 | 2.9% + $0.30 | 3.3% + $0.30 (Free plan) |
| **Manual key-in** | Interchange + ~0.50% + 25¢ | ~2.85% + $0.30 | 3.4% + $0.05 | 3.5% + $0.15 |
| **Monthly fee** | $0 | ~$5–25 (varies by plan) | $0 (Terminal) | $0 (Free), $49 (Plus), $149 (Premium) |
| **Equipment rental** | None — purchase only ($239–$429 CAD) | $19.95–$125/mo per device rental | None — purchase only ($59 WisePad / $249 WisePOS E) | None — first reader free, $59 thereafter |
| **PCI compliance fee** | $0 | Charges annual PCI fee (~$100–200/yr range typical) | $0 | $0 |
| **Statement fee** | $0 | $2/mo paper statement | $0 | $0 |
| **Chargeback fee** | $15 (refunded if you win) | $25 | $15 (Stripe) | $0 |
| **Cross-border surcharge (USD card)** | +0.45% to +1.13% | ~0.50%–0.80% (varies) | +1% intl + currency | ~1.5% non-CAD card |
| **Contract length** | Month-to-month | 3-year historical (now de-emphasized) | Month-to-month | Month-to-month |
| **Early termination fee** | $0 | $0 (replaced by $25–50/device "refurbishing fee") | $0 | $0 |
| **Reserve / hold clause** | 6-month reserve on termination | Yes, varies | Up to 90-day rolling reserve possible | Up to 180-day fund hold possible |
| **Settlement speed** | T+1 (Faster Deposits, batches ≤$25k, close by 7pm MT) | T+1 (BMO Next Day Settlement) | T+2 standard, instant 1% fee | T+1 standard, instant 1.75% fee |
| **CAD-native?** | Yes (Calgary HQ) | Yes (Toronto HQ, RBC/BMO joint venture) | Yes (CAD settlement) | Yes (CAD settlement) |
| **iPad SDK / integration** | Smart Terminal REST API (no native iOS SDK; use URLSession from Swift) | Moneris Go API + iOS SDK on GitHub | Stripe Terminal iOS SDK (iOS 15+) — best-in-class | Mobile Payments SDK (Reader SDK retired 2025-12-31) |
| **Existing Frappe/ERPNext plugin** | None public — custom adapter required | None public — custom adapter required | aisenyi/stripe_terminal (community); frappe/payments has Stripe support | None public — custom adapter required |
| **Account-freeze risk for adult-adjacent** | Medium — high-touch underwriting at signup, but 6-month reserve on terminations and AUP language allows discretionary closure | Low–Medium — conservative, asks the right questions upfront, less likely to freeze post-approval | **HIGH** — Stripe explicitly prohibits "adult services," many post-onboarding terminations | **HIGH** — Square ToS allows termination "for any reason or no reason at all" |
| **Underwriting style** | High-touch (Calgary team manually reviews) | High-touch (bank-grade KYC) | Light-touch / automated | Light-touch / automated |
| **Support** | Phone + email, business hours MT, generally well-reviewed (4.3 Trustpilot, 649 reviews) | Phone 24/7, mixed reviews — slow ticket queue | Email + chat (phone for higher tiers), 24/7, well-reviewed | Phone + chat, business hours, mixed reviews |

---

## Per-processor narrative

### Helcim (recommended)

**Fees.** Helcim's published pricing is interchange-plus, which is the only honest pricing model in card processing — every other "flat rate" provider is bundling interchange into a higher number that profits the processor on lower-cost cards. For Hamilton's Tier 1 volume ($0–50k/mo), card-present is interchange + 0.40% + 8¢. Real-world all-in cost on a typical Visa debit transaction: ~1.6% all-in. On a Visa World rewards card: ~2.2% all-in. On Amex: ~2.9% all-in. Card-not-present is interchange + 0.50% + 25¢ — Hamilton barely uses CNP today (Phase 2 Stripe Identity flow is the main candidate), so this matters less.

No monthly fee. No PCI compliance fee. No statement fee. No setup fee. No cancellation fee. Chargeback is $15 and Helcim refunds it if you win the dispute — that's a fairer chargeback model than every other processor on this list. International (USD-card-on-CAD-merchant) surcharge is +0.45% to +1.13% depending on card type, which is reasonable.

**Contract.** Month-to-month. No early termination fee. You buy the terminal outright ($239 for the basic Card Reader, $429 for the Smart Terminal — or 12 payments of $39 = $468 if financed). Equipment ownership matters for the backup role: Hamilton can buy one Smart Terminal, leave it in a drawer, and pay $0/month for the privilege of having a backup processor pre-approved. Moneris's monthly rental model would cost $20+/mo for the same drawer-bound terminal.

**Account-freeze risk.** This is where the analysis gets nuanced. Helcim has a 4.3-star Trustpilot rating across 649 reviews, which is genuinely good for a payment processor. Most reviews are from happy small-business owners with simple businesses. But: the negative reviews and BBB complaints describe a real failure mode — Helcim's underwriting team approves a merchant, the merchant starts processing, and then Helcim's risk team (separate department) reviews the first batch and either holds the funds for 6 months or terminates the account. The published "first batch review" policy at `learn.helcim.com/docs/account-review-reasons` confirms this is a known process.

For Hamilton, the relevant question is: does Helcim's risk team treat a wellness venue / men's bathhouse as a Restricted Business under their AUP? The AUP language at `legal.helcim.com/us/acceptable-use-policy/` (USA version; Canadian version similarly worded) lists prohibited and restricted categories but does not enumerate "bathhouse" specifically. "Adult-oriented services" is in the restricted list. The classification is therefore at Helcim's discretion. Helcim's Calgary underwriting team is known for being more willing to have a conversation about edge cases than Stripe or Square — they will tell you yes or no upfront, and if they say yes, the post-approval freeze risk is lower than with light-touch processors. The path to "good" is: present Hamilton during application as exactly what DEC-062 says it is — a hospitality / wellness venue with hot tubs, sauna, gym, towel service, food and beverage retail. Don't lead with the word "bathhouse" in the application. Be honest if asked. The application either gets approved or doesn't. If it doesn't, switch to Moneris.

The 6-month reserve clause on terminations is the worst case. If Helcim ever does terminate Hamilton's account, Helcim can hold all funds processed in the 6 months prior to termination as a reserve. For Hamilton's drawer-bound backup processor, the 6-month exposure is approximately zero (because nothing is processed). For the moment Hamilton flips the config flag and starts running real transactions through Helcim, the exposure ramps up at $X/day until it hits 6 months of revenue. This is a real risk if Hamilton ever has to actually USE the backup for an extended period. Mitigation: when the primary processor (Fiserv) freezes, Hamilton's playbook should be (a) flip to Helcim for immediate continuity, (b) immediately apply for a third processor (Moneris, or another Canadian bank-backed option) so Hamilton is never single-processor again, and (c) once the third processor is approved, route most volume through it and use Helcim only as the secondary.

**iPad / ERPNext integration.** Helcim does NOT publish a native iOS SDK. They publish a Smart Terminal REST API at `devdocs.helcim.com/docs/overview-of-smart-terminal-api`. To take a payment from an iPad: the iPad app makes an HTTPS POST to Helcim's API endpoint with the amount, terminal ID, and idempotency key; the API contacts the Smart Terminal over its cloud connection; the Smart Terminal prompts the customer for tap/insert/PIN; the API returns an authorization response. This is a perfectly reasonable integration model and matches Hamilton's existing `submit_retail_sale` flow architecture (server-side adapter making HTTPS calls). No frappe/payments plugin exists for Helcim; Hamilton would write a custom adapter, which the existing decisions_log already anticipates (~line 1672, "the codebase ships with adapter classes ... and `merchant_type` selects which adapter to use"). Estimated effort: 3–5 days for a functional adapter with sandbox testing, including webhook handling for the Smart Terminal's transaction-state events.

**Hardware.** The Helcim Smart Terminal is a standalone Android-based device (the same WisePOS E hardware Stripe sells, in fact, but with Helcim's app loaded). It connects to Helcim's cloud over WiFi/4G — does NOT need to be paired with the iPad over Bluetooth. This is operationally cleaner than the Stripe Terminal model, where the iPad and reader must maintain a Bluetooth pairing that drops occasionally. The Smart Terminal has its own screen, prints receipts (with an optional add-on), and supports Interac, Visa, Mastercard, Amex, Discover.

**Payout speed.** T+1 via Faster Deposits, provided the batch closes by 7:00 PM Mountain Time and the batch is ≤$25,000. Hamilton runs on Eastern Time (Hamilton, Ontario), so 7:00 PM MT = 9:00 PM ET — easy to hit. Hamilton's daily batch will not exceed $25k for years to come, so the cap is irrelevant. Faster Deposits uses Interac e-transfer rails, which means the funds arrive almost in real time once Helcim initiates them.

**Support.** Phone (Calgary office, business hours MT) and email. Trustpilot 4.3/5, 649 reviews. Generally praised for responsiveness during onboarding and ongoing operations; the negative reviews concentrate on the post-approval termination pattern. Support quality matters less for a backup processor (Hamilton won't call Helcim's support except during the application phase and integration smoke tests).

**Verdict.** Best blend of price, control, and integration friendliness for the backup role. The freeze risk is the same direction as for any non-Fiserv processor; Helcim's high-touch underwriting reduces the post-approval surprise factor relative to Stripe/Square. The interchange-plus pricing means Hamilton actually saves money on the backup vs. flat-rate processors if the backup ever has to handle real volume.

### Moneris (runner-up)

**Fees.** Flat-rate 2.65% + $0.10 card-present, 2.85% + $0.30 card-not-present. Interac at $0.10 in-person, $1.00 CNP. These rates are negotiable for higher-volume merchants — Hamilton is not currently high-volume, so the published rates are the floor. PCI compliance fees of a few hundred dollars per year are typical with Moneris (the search results confirm "Clover and Moneris may charge annual fees ranging from a few hundred to thousands of dollars for PCI compliance"). Equipment rental is $19.95–$125/mo per device. Chargeback fee $25.

The all-in cost picture: Moneris is more expensive than Helcim on every line item except possibly support quality, and even there the reviews are mixed. For Hamilton's Tier 1 volume, Moneris's flat-rate model overcharges on debit Interac (Helcim's interchange-plus passes the $0.10 Interac wholesale rate; Moneris's 2.65% + $0.10 charges 2.65% on top of that) but undercharges nothing — Helcim wins on every card type at this volume.

**Contract.** Historically 3-year with early termination fees. Per the 2026 update, Moneris has retired the early termination fee in favor of a per-device "refurbishing cost" of $25–$50 — a meaningful improvement, but the 3-year shadow remains in the standard agreement template. Negotiate to month-to-month explicitly during application.

**Account-freeze risk.** Lowest of the four candidates. Moneris is jointly owned by RBC and BMO — two of Canada's Big Six banks — and operates with bank-grade KYC and underwriting. Their risk policies are conservative, but they ASK upfront. If Moneris approves a wellness venue / bathhouse, the post-approval termination risk is meaningfully lower than with Helcim, Stripe, or Square. Moneris is also the processor most likely to be tolerant of a Canadian hospitality merchant whose business name causes Anglo-American risk teams to twitch — they're Canadian and they've seen everything. The trade-off: their underwriting may take longer (2–4 weeks vs. Helcim's 3–7 days) and they may demand more documentation. For a backup processor that Hamilton is not in a hurry to deploy, this is fine.

**iPad / ERPNext integration.** Moneris Go API + iOS SDK published on GitHub via the new Moneris Developer Portal (`api-developer.moneris.com`). The Moneris Go integration model is similar to Helcim's: the terminal is a standalone device, the iPad app calls Moneris Go API endpoints to initiate a transaction, the terminal handles the customer-facing flow, the API returns a result. They also publish a "scenario: GO Integration Method" doc that walks through the integration. Sandbox access is available before merchant signup; production access requires the merchant agreement.

No frappe/payments plugin for Moneris exists publicly. Custom adapter required, similar effort to Helcim (3–5 days).

**Hardware.** Moneris Go terminal and PAX A920 (same hardware as Square's terminal, different software stack). Rentable at $19.95/mo or purchasable. The rental model is a worse fit than Helcim's purchase-only for the drawer-bound backup use case — Hamilton would pay $20/mo × 12 = $240/year for a terminal that processes nothing.

**Payout speed.** T+1 via BMO Next Day Settlement when the merchant has a BMO banking relationship; T+1–T+2 otherwise depending on bank. CAD-native settlement. No instant payout offering at the per-transaction level (Moneris targets the bank-relationship segment, not the gig economy).

**Support.** 24/7 phone support — the only candidate that publishes 24/7 phone support — but Trustpilot and BBB reviews are mixed, with consistent complaints about slow ticket-queue resolution for billing disputes and contract cancellations. For a backup processor, the 24/7 phone support is a real asset: when Fiserv freezes Hamilton at 11pm on a Saturday, Moneris has a human on the phone.

**Verdict.** The "your bank backs us" option. More expensive in every line item, slower to onboard, but the post-approval freeze risk is the lowest of the four. Recommended as the runner-up — and arguably as a third processor down the road, once Hamilton has multi-venue volume to negotiate rates with. If Helcim declines the application, promote Moneris to backup and add a third option (Worldline / Bambora) as the next-tier fallback.

### Stripe Terminal Canada

**Fees.** 2.70% + $0.05 card-present in CAD. Interac $0.15 per transaction. CNP 2.9% + $0.30. International cards +1%. No monthly fees on the Terminal product itself (Stripe charges monthly fees for some adjacent products like Radar but not Terminal core).

**Contract.** Month-to-month. No ETF.

**Account-freeze risk.** This is the disqualifier. Stripe's published Restricted Businesses list (`stripe.com/legal/restricted-businesses`) includes "adult services, including ... sexual massages, fetish services" and "adult content and services—pornography, adult video stores, strip clubs, escort services, adult live chat." A men's bathhouse will be classified by a Stripe risk analyst as adult-adjacent the moment they Google the venue name. There are well-documented patterns of Stripe terminating accounts post-onboarding once their automated risk monitoring or a manual review flags the merchant — see the Hacker News thread, the chargeback.io and durangomerchantservices.com analyses, and the PaymentCloud guide. Stripe also has a 90-180 day fund hold provision that is invoked frequently in adult-adjacent terminations.

The argument for Stripe is "best iOS SDK, best developer experience, fastest integration." That argument is real but irrelevant to the backup role. Hamilton needs a backup that WON'T FREEZE in the worst-case scenario. Stripe is the most likely of the four candidates to freeze. Disqualified.

**iPad / ERPNext integration.** Stripe Terminal iOS SDK is the gold standard — full Swift SDK, sample code, well-documented, iOS 15+. The community-maintained `aisenyi/stripe_terminal` ERPNext plugin exists. The frappe/payments core supports Stripe for online flows. If Hamilton were starting from scratch and freeze risk weren't the dominant factor, Stripe would be the obvious primary, not even the backup. But freeze risk IS the dominant factor.

**Hardware.** BBPOS WisePad 3 ($59) and BBPOS WisePOS E ($249). Both are Canada-supported. Bluetooth pairing (WisePad 3) or cloud-connected standalone (WisePOS E).

**Payout speed.** T+2 standard for new Canadian accounts (Stripe accelerates to T+1 after a track record); first payout has a 7-business-day delay. Instant Payouts available at 1% fee.

**Support.** Email/chat for the standard tier, phone for higher tiers. 24/7 chat coverage. Generally well-reviewed by developers, less well-reviewed by merchants who need a human during a freeze incident.

**Verdict.** Best technology, worst freeze profile for Hamilton. Do NOT use as the backup. Possibly viable as the primary for a Phase 2 venue in a different category (a true wellness spa with no bathhouse association), but not for Hamilton.

### Square Canada

**Fees.** 2.6% + $0.15 card-present (Free plan, post-October-2025 pricing), 3.3% + $0.30 CNP, 3.5% + $0.15 manual key-in. The Free plan exists; Plus is $49/mo and Premium is $149/mo with reduced rates. First reader is free, subsequent are $59. No PCI fee. No chargeback fee (Square eats it under their model).

**Contract.** Month-to-month. No ETF. The flexibility is real.

**Account-freeze risk.** Same disqualifier as Stripe, possibly worse. Square's ToS explicitly says the company can terminate "for any reason or no reason at all." Adult-adjacent businesses are commonly terminated. The 180-day fund hold is the standard outcome. The Reddit / BBB / Trustpilot pattern is that Square approves nearly anyone with a phone number and SSN/SIN, then terminates 30-90 days later when their risk monitoring catches up. For a hospitality / wellness venue with the wrong perception profile, this pattern is almost certain. Disqualified for the same reason as Stripe.

**iPad / ERPNext integration.** Mobile Payments SDK (the successor to Reader SDK, which retires 2025-12-31). Available for US, Canada, Australia. Terminal API also published. iOS-friendly. No frappe/payments plugin exists; custom adapter required.

**Hardware.** First reader is free (the magstripe + chip dongle); contactless reader is $59; Square Terminal device (Android-based, standalone) is $399 CAD. Hamilton already owns iPads, so the $0–59 reader is the relevant cost.

**Payout speed.** T+1 standard for Canadian merchants. Instant Payout at 1.75% fee.

**Support.** Phone + chat, business hours mainly. Mixed reviews. The freeze-recovery experience is widely complained about.

**Verdict.** Even cheaper than Stripe on hardware, comparable on rates, better contract terms, worse freeze profile. Disqualified for Hamilton's backup role for the same reason as Stripe — both are fintech-style light-touch onboarders with well-documented post-approval termination patterns in adult-adjacent categories.

---

## Final recommendation

**Top pick: Helcim** for Hamilton's backup processor.

**Reasoning:**

1. **Cost matches the use case.** Zero monthly fees and purchase-only hardware mean the dormant backup costs Hamilton ~$0/year to maintain (one-time $429 Smart Terminal purchase amortized across years). Moneris's $20+/mo rental adds $240+/year to the dormant-backup cost. Stripe and Square are also purchase-only but disqualified on freeze risk.
2. **Underwriting style matches Hamilton's profile.** Helcim's Calgary underwriting team is willing to have a conversation about edge cases at signup. They will say yes or no based on Hamilton's actual business description (DEC-062 standard-merchant: hospitality/wellness venue) rather than an automated risk score. If they say no, Hamilton learns that fact during application and pivots to Moneris with no money lost.
3. **Integration friction is manageable.** Helcim's Smart Terminal REST API is documented and works with any HTTPS-capable client. The custom adapter for the Hamilton ERPNext app is a 3–5 day build, comparable to any other non-Stripe option. No SDK lock-in, no native-iOS-app constraint, no Bluetooth pairing reliability concerns.
4. **CAD-native, T+1 settlement, Canadian domiciled.** The cross-border processing concerns that affect Stripe (US-domiciled) and the multi-currency complications that affect Square (US-headquartered) don't apply. Helcim is Calgary; Moneris is Toronto; both are unambiguously Canadian.
5. **The 6-month reserve clause is a manageable risk.** As long as Hamilton uses Helcim only as a backup (drawer-bound until needed), the reserve exposure is approximately zero. The risk only materializes if Helcim becomes the primary for an extended period — at which point Hamilton should be applying for a third processor anyway (the lesson from any single-processor freeze is that two processors aren't enough; three is the minimum target state).

**Runner-up: Moneris.**

**Reasoning:** If Helcim declines Hamilton's application, or if Helcim's underwriting team flags the venue type as Restricted, Moneris becomes the obvious next choice. Moneris is more expensive and slower to onboard, but the post-approval freeze risk is the lowest of any candidate. Moneris is also the right longer-term answer if Hamilton expands to multi-venue and wants a single bank-backed processor relationship across all six cities. The downside is the rental fee model and the historically aggressive contract terms — both negotiable, but Hamilton should expect to spend an hour with a Moneris account manager pushing back on their default agreement.

**What would change the recommendation later:**

- **If Helcim's AUP enforcement tightens** in 2026–2027 in response to a public incident at another bathhouse / massage venue, Moneris becomes the recommendation.
- **If Stripe formally exits hostility toward wellness venues** (unlikely in the medium term — Stripe's risk model is automated and unlikely to change), Stripe's superior tech would tip the balance for Phase 2 venues.
- **If Hamilton's volume grows past Tier 2 ($50k/mo) at the venue,** the interchange-plus pricing on Helcim begins to matter more vs. Moneris's flat rate; Helcim becomes more compelling as the backup AND a candidate to take over as primary if Fiserv's pricing isn't competitive.
- **If a Frappe Cloud Marketplace plugin appears for Moneris or Helcim**, the integration cost drops to near-zero and the recommendation tilts toward whichever is plugin-supported.

---

## Action items for Chris

1. **Open the Helcim merchant application** at `https://www.helcim.com/signup/`. Use the business description: "hospitality and wellness venue offering hot tubs, sauna, gym, towel/locker service, retail food and beverage." MCC code: 7298 (Health & Beauty Spas) or 7298 / 7299 — let Helcim's underwriting select. Do NOT lead with "bathhouse" in the application form, but answer honestly if asked. Application should take 15–30 minutes; underwriting decision in 3–7 business days.

2. **If Helcim approves**: do NOT process any live transactions. Order one Smart Terminal ($429 CAD purchase, NOT financed). Set up Helcim API credentials in a Frappe site config flag (`hamilton_merchant_backup_helcim_api_key`). Build the Helcim adapter in `hamilton_erp/payments/adapters/helcim.py` mirroring the Fiserv adapter structure. Smoke-test in Helcim's sandbox.

3. **If Helcim declines or flags Hamilton as a Restricted Business under their AUP**: do NOT argue. Stop the application. Move to Moneris (apply via `https://www.moneris.com/en/contact-us` or via Hamilton's existing BMO business banking relationship for the Next Day Settlement preference). Repeat steps 1–2 with Moneris.

4. **Once a backup is approved and integration-tested**: run a $1 live test transaction through the backup processor's terminal to confirm end-to-end flow (auth → capture → settle → payout). Use a real card; reverse the charge after verification. Document the test result in `docs/runbooks/processor_swap_runbook.md` (creating that file if it does not yet exist).

5. **Document the swap procedure** in a new runbook file: `docs/runbooks/processor_swap_runbook.md`. Include: (a) the config-flag location to swap primary → backup, (b) the Frappe bench restart command, (c) the smoke-test checklist (process a $1 test, verify webhook fires, verify Sales Invoice creates, verify payout schedule), (d) the fallback procedure if the swap itself fails, (e) the playbook for applying for a third processor immediately after a primary freeze.

6. **Promote this evaluation to a DEC-NNN entry** in `docs/decisions_log.md` once Chris has signed off on the recommendation. Reference DEC-062 (standard-merchant classification) and DEC-064 (dual-processor mandate) as the upstream decisions; this DEC selects the specific backup processor.

7. **Add a calendar reminder** to re-evaluate the backup processor choice annually — in May 2027, repeat the freeze-risk and pricing review. If Helcim's AUP enforcement has changed, or if a Frappe Cloud plugin has appeared for one of these processors, the choice may shift.

---

## Sources

- [Helcim Pricing](https://www.helcim.com/pricing/)
- [Helcim Fee Disclosures Canada](https://legal.helcim.com/ca/fee-disclosures/)
- [Helcim Acceptable Use Policy USA](https://legal.helcim.com/us/acceptable-use-policy/) (Canadian version similarly worded)
- [Helcim Business Restrictions & Acceptable Use Policy](https://learn.helcim.com/docs/helcim-business-restrictions)
- [Helcim Smart Terminal API Overview](https://devdocs.helcim.com/docs/overview-of-smart-terminal-api)
- [Helcim First Batch Account Reviews](https://learn.helcim.com/docs/account-review-reasons)
- [Helcim Trustpilot Reviews](https://www.trustpilot.com/review/helcim.com)
- [Helcim BBB Complaints (Calgary)](https://www.bbb.org/ca/ab/calgary/profile/credit-card-merchant-services/helcim-0017-58538/complaints)
- [Helcim NerdWallet Review 2026](https://www.nerdwallet.com/business/software/reviews/helcim)
- [Helcim Faster Deposits Announcement](https://www.helcim.com/announcements/introducing-helcim-faster-deposits/)
- [Helcim Bank Deposit Timelines](https://learn.helcim.com/docs/bank-deposit-timelines-helcim)
- [Moneris Pricing](https://www.moneris.com/en/pricing)
- [Moneris Developer Portal](https://api-developer.moneris.com/)
- [Moneris Go Integration Guide](https://www.moneris.com/-/media/files/non_specific_guides/moneris-go-integration-guide-en.ashx)
- [Moneris Review (Merchant Cost Consulting)](https://merchantcostconsulting.com/lower-credit-card-processing-fees/moneris-review/)
- [Moneris Solutions Review (Card Payment Options)](https://www.cardpaymentoptions.com/credit-card-processors/moneris-solutions-review/)
- [How to Cancel a Moneris Merchant Account (Clearly Payments)](https://www.clearlypayments.com/blog/how-to-cancel-moneris-merchant-account/)
- [Stripe Terminal Documentation](https://docs.stripe.com/terminal)
- [Stripe Terminal Regional Considerations Canada](https://docs.stripe.com/terminal/payments/regional?integration-country=CA)
- [Stripe Terminal Pricing Q&A](https://support.stripe.com/questions/pricing-for-stripe-terminal)
- [Stripe Terminal iOS SDK](https://stripe.dev/stripe-terminal-ios/docs/index.html)
- [Stripe Prohibited and Restricted Businesses](https://stripe.com/legal/restricted-businesses)
- [Stripe Closed/Suspended Merchant Account Guide](https://www.chargeback.io/blog/stripe-closed-suspended-my-account)
- [Stripe Terminate Hacker News Discussion](https://news.ycombinator.com/item?id=32854528)
- [Stripe Instant Payouts Documentation](https://docs.stripe.com/payouts/instant-payouts)
- [Stripe Default Payout Speeds Canada](https://support.stripe.com/questions/accessing-faster-payout-speeds-in-europe-and-canada)
- [Square Canada Pricing](https://squareup.com/ca/en/pricing)
- [Square In-Person Payments APIs and SDKs](https://developer.squareup.com/ca/en/in-person-payments)
- [Square Mobile Payments SDK General Availability](https://developer.squareup.com/blog/announcing-mobile-payments-sdk-ga-and-new-terminal-api-features/)
- [Square Account Termination Guide (Corepay)](https://corepay.net/articles/what-to-do-when-square-terminates-your-merchant-account/)
- [Square Drops High-Risk Merchant (Signature Payments)](https://signaturepayments.com/when-square-drops-your-high-risk-merchant-account/)
- [Worldline (Bambora) Canada Software Profile](https://www.softwareadvice.com/online-payment/bambora-profile/)
- [frappe/payments GitHub](https://github.com/frappe/payments)
- [aisenyi/stripe_terminal ERPNext Integration](https://github.com/aisenyi/stripe_terminal)
