# Merchant Processor Comparison — ERPNext v16 + iPad

**Status:** Draft — initial research deliverable from inbox queue 2026-05-01.
**Purpose:** Rank merchant processors by ease of integration with ERPNext / Frappe v16 for in-person card-present payments on iPad.
**Multi-venue scope:** Hamilton (CAD), Philadelphia / DC / Dallas (USD).

⚠️ **Pricing, fees, and TOS terms change frequently.** Every number in this doc must be re-verified against the processor's current website before signing a merchant agreement. Specifications are from training data; processors change rates quarterly.

---

## TL;DR — Recommendation

**Use Fiserv (existing Hamilton MID 1131224) for Hamilton.** Use Stripe Terminal as the standard for new venues (Philadelphia / DC / Dallas).

Reasoning:
1. **Fiserv at Hamilton is already running**, with standard merchant classification (per `docs/risk_register.md` R-008). Switching off it would forfeit the rate, the existing relationship, and the standard-classification protection. Don't move it without a compelling reason.
2. **Stripe Terminal at the new venues** because:
   - Native ERPNext payment-gateway integration (least Hamilton custom code)
   - Both CAD and USD supported with one API
   - Well-documented `payment_intent` flow including `merchant_transaction_id` capture
   - Adult-adjacency sensitivity at Stripe (their internal stance toward bathhouse-hospitality merchants — Hamilton itself is standard-classified per DEC-062) is real but manageable; see "Adult-adjacency policy by processor" section
3. **Helcim, Moneris, Square considered and ranked below.** Each has a real downside that puts it behind the recommendation.

---

## Comparison table

⚠️ Verify everything in this table against current vendor pages.

| Processor | CA support | US support | ERPNext native | Adapter effort | Card-present (iPad) | Adult-classification policy | Termination notice | In-person fee est. | Notes |
|---|---|---|---|---|---|---|---|---|---|
| **Fiserv (Clover, First Data merger)** | ✅ Yes | ✅ Yes | Partial (Clover branch) | Medium — depends on terminal API | ✅ Pole-mount terminal | Standard-classified (per Hamilton's existing MID) — much better than high-risk | 30-day standard | ~2.5-3.0% + flat fee | Hamilton's existing MID 1131224. Standard classification means lower risk profile than high-risk processors. |
| **Stripe Terminal** | ✅ Yes | ✅ Yes | ✅ Native (`stripe-payments` ERPNext app) | Low — well-documented `PaymentIntent` flow | ✅ BBPOS WisePOS E (~\$300) or Stripe S700 (~\$700) | Restrictive but not zero — adult-hospitality vs adult-content matters | Algorithmic, can be zero-day for adult content; longer for hospitality | ~2.7% + \$0.05 (US), 2.7% + \$0.30 (CA) | The fastest-to-integrate option. Native ERPNext integration. |
| **Helcim** | ✅ Yes (CA-flagship) | ⚠️ Partner-only | ❌ Custom adapter required | High — custom integration | ✅ Helcim Card Reader (~\$200) | Adult-friendly in Canada (declared on TOS) | 30-day standard | ~1.9% + interchange (interchange-plus model) | Best Canadian rates for high-volume merchants. USD support is via partner relationships, adds rollout complexity. |
| **Moneris** | ✅ Yes (CA-flagship) | ❌ No | ❌ Custom adapter required | Very high — Moneris APIs are baroque | ✅ Moneris Core terminal | Standard for hospitality; depends on the Moneris division | 30-day standard | ~2.4-2.8% | Canadian banking-system flagship. Strong for CA-only operators. **Skip for multi-venue.** |
| **Square** | ✅ Yes | ✅ Yes | ✅ Native (`square` ERPNext app) | Low | ✅ Square Terminal (~\$300) | Restrictive on adult; faster to terminate than Stripe in some categories | Algorithmic, often <30 days | ~2.6% + \$0.10 in-person | Easy integration, but adult-classification sensitivity is real. **Skip for adult-classified businesses.** |
| **Adyen** | ✅ Yes | ✅ Yes | ❌ Custom adapter | Very high — enterprise-grade | ✅ Adyen terminal | Adult-friendly with negotiated terms | Negotiated | Custom (interchange-plus, typically <2.0% for high-volume) | Enterprise platform; minimum volume requirements typically exclude single-venue Hamilton scale. **Worth re-evaluating at multi-venue Phase 3+ scale.** |

---

## Adult-adjacency policy by processor (this matters)

**Hamilton is not formally adult-classified** — Fiserv MID 1131224 is standard-classified, and DEC-062 (locked 2026-05-01) records that ANVIL Corp venues operate as standard commercial businesses. But individual processors apply their OWN risk models when underwriting bathhouse-hospitality businesses, and those models can differ from Hamilton's actual classification: a processor may flag the venue as adult-adjacent inside their internal categorization regardless of what the MID says. The table below describes each processor's *internal stance toward bathhouse-hospitality merchants*, not a claim about Hamilton's classification.

The wrong choice means surprise account termination during a Saturday-night peak, exactly the scenario `docs/lessons_learned.md` would have to absorb if it happened. DEC-064 (primary + backup processor per venue) is the structural defense.

| Processor | Hamilton-style classification | Notes |
|---|---|---|
| Fiserv | Standard (Hamilton's existing MID is standard, not high-risk) | This is the protective state. Don't lose it by changing processors casually. |
| Stripe Terminal | Restricted but accepted | Stripe's TOS draws the line at "adult content" (porn, sex work) vs "adult-classified hospitality" (bars, bathhouses). Hamilton falls on the hospitality side. Real-world Stripe accounts at gay bathhouses exist; the policy is enforced unevenly. **Not zero-risk.** |
| Helcim | Adult-friendly in Canada | Helcim has explicit "we accept adult businesses" language in their materials. Canadian-flagship for adult merchants. |
| Moneris | Depends on division | Moneris has a separate high-risk division. Standard division may decline; high-risk division accepts but at higher rates. |
| Square | Often declined | Square's terms explicitly exclude many adult-adjacent business types. Termination has happened to Hamilton-style businesses with little warning. Avoid. |
| Adyen | Adult-friendly with negotiated terms | Enterprise tier; negotiation matters. |

**This is the load-bearing decision factor.** Rate differences between processors are 0.2-0.5% — survivable. An account termination is catastrophic.

---

## ERPNext / Frappe v16 integration assessment

### Native (least custom code)

- **Stripe** — `payments` app (Frappe ecosystem) supports Stripe Connect + Stripe Terminal. `payment_intent` flow with webhooks for state updates. Hamilton's `submit_retail_sale` endpoint would call into the Stripe SDK directly; the response includes `payment_intent.id` which becomes Hamilton's `merchant_transaction_id`. Mature, well-tested integration.
- **Square** — `payments` app also covers Square. Same integration shape as Stripe but with Square's APIs. Works but adult-classification is the dealbreaker.

### Partial / partner-only

- **Fiserv** — depends on which Fiserv API. The Clover Connect API is well-documented (post First Data merger). Direct integration with the Fiserv MID-level API requires a partner relationship.
- **Authorize.net** — historical First Data product line. Simpler API but card-present (Hamilton's use case) requires a paired terminal — most current-era integrations route through the Clover Connect path.

### Custom adapter required

- **Helcim** — REST API is documented but no native ERPNext integration. Hamilton would need a custom `Hamilton Helcim Adapter` controller. Estimated effort: 2-3 days for in-person card-present flow + reconciliation.
- **Moneris** — APIs are notoriously complex (Vault, Credit Card, Direct Post, Hosted Payments — multiple overlapping options). Skip for multi-venue.
- **Adyen** — enterprise SDK; integration effort matches the enterprise tier.

### Card-present specifics

The above mostly covers card-not-present (e-commerce). For Hamilton's Phase 2, card-present (the customer is physically at the counter, terminal reads chip / tap) needs:

- A physical terminal that talks to the iPad (Bluetooth, USB-C, or LAN)
- Terminal SDK that integrates with ERPNext's payment flow
- Compliance with EMV / PCI standards (the terminal handles this; Hamilton inherits compliance via the processor)

**Stripe Terminal** is the strongest card-present story because Stripe sells the terminal hardware (BBPOS WisePOS E, Stripe S700) and the SDK directly supports the iPad use case via the Stripe Terminal SDK for iOS / JavaScript. **Fiserv** card-present integration depends on which Clover terminal model and which API path — see next section.

---

## Fiserv / Clover terminal hardware — iPad integration paths

Hamilton's existing Fiserv MID 1131224 routes through the Clover product line (post First Data merger). The Clover terminals fall into two integration patterns for an iPad-based POS:

- **Cloud-routed (Clover Connect API):** iPad app sends a transaction request via REST → Clover Connect dispatches to the paired terminal → terminal completes locally → result returns via webhook. The iPad and terminal don't talk directly. Works over any network they both reach. The standard semi-integrated pattern for ERPNext-style apps.
- **Direct Bluetooth pair (Clover Go SDK):** iPad app uses the Clover SDK for iOS to pair a small reader directly. Lighter integration, but Bluetooth pairing has known reliability issues and the reader is feature-limited (no display, no PIN entry without prompts on the iPad screen).

Below: ranked by iPad-integration quality at Hamilton's expected volume / use case (counter check-in, single payment per transaction, occasional retail SKU sale).

⚠️ **Pricing, lease terms, and SDK availability MUST be verified against current Fiserv / Clover quotes before commitment.** Specs below are from training data; the hardware market moves quarterly.

### Tier 1 — Best fit for Hamilton

#### Clover Flex (model C401U or successor)

- **Form factor:** Handheld, ~7-inch touchscreen, EMV chip + magstripe + tap (NFC/Apple Pay/Google Pay), built-in receipt printer, cellular optional.
- **iPad integration:** **Clover Connect API** (cloud-routed REST). iPad submits transaction; Flex displays prompts, reads card, returns result via webhook. Hamilton's submit_retail_sale endpoint becomes the iPad's launching point.
- **Hardware estimate (verify):** ~$500-700 per unit purchased; ~$50-80 / month leased through Fiserv (lease bundles maintenance + replacement). Volume / multi-venue lease terms negotiable.
- **Availability:** Widely stocked through Fiserv direct, Clover-authorized resellers, and partner ISOs. No supply-chain issues reported in training data.
- **Pros:** Most popular semi-integrated terminal in the Clover line. Mature SDK. Mobile (handheld) so the customer doesn't have to reach across the counter — operator brings the device to the customer for tap/dip. Tip prompts, receipt print, signature capture all on-device.
- **Cons:** Per-unit cost. The iPad isn't strictly necessary at Hamilton's volume — you could run the Clover Flex standalone — but the iPad gives the unified asset-board + cart experience the rest of Hamilton's flow expects.

**Recommended for Hamilton's primary check-in station + DC's 3 stations.**

#### Clover Mini (model C500 or successor)

- **Form factor:** Countertop terminal with 8-inch screen, customer-facing display, EMV/tap, built-in receipt printer.
- **iPad integration:** Same Clover Connect API as Flex. Cloud-routed.
- **Hardware estimate (verify):** ~$700-900 purchased; ~$60-100 / month leased.
- **Availability:** Widely stocked.
- **Pros:** Customer-facing display gives clearer "tap here" affordance than handheld. Stable counter mount removes drop risk.
- **Cons:** Customer must reach across counter (slower than handheld for line-up scenarios). More expensive than Flex.

**Backup recommendation if Flex is unavailable or if a venue's layout favors counter-mount over handheld.**

### Tier 2 — Lighter integration

#### Clover Go (Bluetooth card reader)

- **Form factor:** Small (~3-inch) Bluetooth reader, EMV/tap only, no screen, no built-in printer.
- **iPad integration:** **Clover SDK for iOS** — direct Bluetooth pair. iPad app drives the entire UX (prompts, tip selection, receipt routing). Reader just reads the card.
- **Hardware estimate (verify):** ~$50-100 purchased; usually no lease (it's a accessory tier).
- **Availability:** Widely stocked. Often bundled into Fiserv/Clover starter kits.
- **Pros:** Cheapest entry point. Custom iPad UX gives full design control over the payment flow.
- **Cons:** Bluetooth pairing reliability is a recurring complaint in community forums. No PIN pad → PIN-required transactions (Canadian Interac chip) may not be supported in all configurations. No customer-facing display.

**Useful as a low-cost backup or for retail-side counter where the operator/customer have shared sightline. Probably not the front-desk primary.**

### Tier 3 — Possible but not recommended

#### PAX A920 / A77 via Clover Connect

- **Form factor:** Android-based handheld (PAX A920) or countertop (A77). EMV/tap/printer.
- **iPad integration:** PAX hardware can be routed through Fiserv's Clover Connect gateway, but the SDK / docs are PAX-side, not Clover-side. Two SDKs to manage: PAX for the terminal, Clover Connect for the gateway hop.
- **Hardware estimate (verify):** ~$400-600 purchased.
- **Availability:** Through PAX-authorized resellers; bundled with Fiserv MIDs in some channels but not the default path.
- **Pros:** Hardware is robust, used widely in non-Clover ISO channels.
- **Cons:** Two-SDK integration complexity; PAX is not Fiserv's first-party hardware. Documentation is harder to find than Clover-native models. Recommend only if the Clover Flex is unavailable and PAX is what the local Fiserv ISO offers.

#### First Data FD150 / FD130 (legacy)

- **Form factor:** Older countertop EMV terminals, dial-up / Ethernet only.
- **iPad integration:** None native. Would require a custom gateway middleware.
- **Status:** **Skip.** Older First Data hardware predates the Clover-iPad integration story. If Hamilton's existing physical terminal IS one of these, it should be replaced — not extended — when the iPad cart goes live.

---

### Lease vs. buy

| Path | Pros | Cons |
|---|---|---|
| **Lease through Fiserv** (~$50-100/mo per Flex/Mini) | Maintenance + replacement included; no upfront capital; easy to swap models if needs change; lease cost is opex not capex (cleaner accounting) | Total cost over 3-4 years exceeds purchase price; locked into Fiserv as the primary processor for the lease term |
| **Buy outright** (~$500-900 per unit) | Lower lifetime cost if held 3+ years; no processor-lock; resale value if migrating away | Upfront capital; you handle replacement when terminal fails or model is EOL'd |

**Recommendation for Hamilton:** **lease the first 1-2 units** to validate the iPad integration end-to-end (test SDK, test merchant settlement, test refund/void flow) before committing to bulk purchase. After 6 months of clean operation, decide buy-vs-continue-lease for the multi-venue rollout. Leasing covers the early-iteration risk window.

### Where to buy / lease (verify before contacting)

- **Fiserv direct sales** — best for existing MID holders. Hamilton's MID 1131224 should already have a sales contact at Fiserv.
- **Clover-authorized resellers** (Banking ISOs, Heartland, Worldpay's Clover line, Square partners) — competitive pricing, varied bundle deals.
- **Costco for Business / Sam's Club** — sometimes carry Clover Flex / Mini in standard retail channels at flat pricing. Worth checking for a quick reference price even if not the eventual purchase channel.

### Open questions for Chris before ordering

1. Does Hamilton's existing Fiserv MID currently have a physical terminal already? If yes, what model — Clover or older First Data?
2. Lease vs. buy preference for Hamilton's first station? My recommendation is lease the first 1-2 units; happy to defer to your call.
3. Any objection to Clover Flex as the primary recommendation, or do you want me to research alternatives first (Stripe Terminal as researched earlier, Helcim Smart Terminal, etc.)?

---

## Per-venue recommendation

| Venue | Currency | Recommendation | Rationale |
|---|---|---|---|
| Hamilton | CAD | Fiserv (existing MID) — keep; consider Helcim as backup | Existing standard-classified relationship is protective; don't churn it. Helcim as secondary in case Fiserv ever escalates. |
| Philadelphia | USD | Stripe Terminal | Fast-to-integrate for new launch. Adult-classification risk is non-zero but manageable via clean chargeback history (R-009). |
| DC | USD | Stripe Terminal | Same as Philly. DC's 3-station setup needs a processor whose terminal SDK handles concurrent sessions cleanly — Stripe Terminal does. |
| Dallas | USD | Stripe Terminal | Same. |

**One processor relationship per currency, two relationships total** keeps operational complexity manageable. Hamilton's CAD volume + the three USD venues' combined volume should each clear minimum-volume tiers for negotiated rates within ~6 months of launch.

---

## Failover / redundancy plan

Per `docs/risk_register.md` R-008, the risk profile of single-acquirer failure is medium for Hamilton (standard MID + 30-day notice + tier-1 acquirer) and would be high for the new venues until they establish chargeback history.

**Recommended redundancy posture:**

1. **Hamilton:** Fiserv primary, Helcim shadow (open the account, leave dormant; ready to activate within 2 weeks if Fiserv classifies aside).
2. **New venues:** Stripe Terminal primary, dual-merchant capability built into the merchant adapter from day 1 (per inbox 2026-04-30 Phase 2 hardware backlog "Merchant abstraction").

The merchant abstraction work in `docs/inbox.md` 2026-04-30 already specs the per-venue config for 1-or-N merchants with named adapters. The implementation lands as part of Phase 2 hardware integration.

---

## Cost estimate

⚠️ All rates verify against current processor sites. Estimates assume modest in-person volume.

### Hamilton (CAD, ~$10K / month gross volume estimate)

- Fiserv at standard classification: ~2.7% × $10K = ~$270 / month in fees
- Helcim shadow: minimal monthly fee (typically $0-15 setup-only)
- **Estimated monthly: $285 / month**

### New venue (USD, ~$15K / month gross volume estimate, single station)

- Stripe Terminal: ~2.7% × $15K + ~$0.05 × ~250 transactions = ~$418 / month in fees
- BBPOS WisePOS E one-time: $300
- **Estimated monthly: $418 / month + $300 one-time per venue**

### DC three-station

- Same Stripe relationship; volume increases proportionally
- Three terminals × $300 = $900 hardware
- ~$1,200 / month in fees at 3× single-venue volume estimate
- **Estimated monthly: ~$1,200 / month + $900 one-time**

### Total annual (rough)

- Hamilton: ~$3,400 / year
- Philadelphia: ~$5,000 / year
- DC: ~$14,400 / year
- Dallas: ~$5,000 / year
- **Annual processing fees across all 4 venues: ~$28,000.**

Volume-tier negotiations after 6 months of trading history typically cut these rates by 0.2-0.5%, saving ~$5,000-10,000 / year at full rollout.

---

## Decision sequence

1. **Now (this PR is the analysis):** Lock the recommendation: Fiserv at Hamilton, Stripe Terminal at new venues.
2. **Pre-launch each new venue:** Open the Stripe Terminal merchant account 60 days before opening; allows underwriting + first-payment testing with dummy charges.
3. **Phase 2 implementation (Hamilton first):** Build the Fiserv card-present integration into Hamilton's `submit_retail_sale` flow. Test with the existing Fiserv terminal model.
4. **Phase 2 implementation (new venues):** Build the Stripe Terminal integration. Modular adapter pattern means swapping between Fiserv and Stripe is a config change at a future date if needed.
5. **Phase 3+ re-evaluation:** When multi-venue volume crosses ~$50K/month, re-evaluate Adyen for negotiated interchange-plus rates.

---

## Open questions for Chris

1. **Existing Fiserv MID setup:** Is there a Fiserv pole-mount / counter terminal already physically at Hamilton, or just the MID without hardware?
2. **Stripe Terminal vs Stripe Standard:** Is Hamilton's check-in flow (the cart Confirm) intended as card-present (terminal) or card-not-present (manual key-in)? Card-present is the recommendation; this question confirms.
3. **Adult-classification appetite:** Is the existing Hamilton Fiserv MID actively classified as Adult Hospitality, or is it general retail? This affects Stripe's likelihood of accepting the new venues.
4. **Helcim shadow account:** Open it now (no monthly cost, ready to activate in case of Fiserv escalation), or wait?
5. **Multi-venue processor: same provider or split?** The recommendation above splits Fiserv (Hamilton) from Stripe (US venues). Alternative: move Hamilton to Stripe too for simplicity, accepting the small classification risk. **Defer this decision to Chris** — both paths are valid.

---

## References

- `docs/risk_register.md` R-008 — Single-acquirer SPOF (downgraded for Hamilton's standard classification)
- `docs/risk_register.md` R-009 — MATCH list 1% chargeback threshold (latent until card payments ship)
- `docs/inbox.md` 2026-04-30 Phase 2 hardware backlog — original "Merchant abstraction" spec including per-venue config
- `docs/design/pos_hardware_spec.md` — companion deliverable; references this doc
- `docs/research/erpnext_hardware_field_reports.md` — companion deliverable; will surface community reports on processor integration pain
- `CLAUDE.md` — Hamilton accounting conventions, Frappe v16 hard rules
- Stripe Terminal docs: https://stripe.com/docs/terminal
- Fiserv (Clover Connect) developer docs: https://docs.clover.com
- Helcim API docs: https://devdocs.helcim.com
