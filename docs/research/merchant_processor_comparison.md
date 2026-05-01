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

**Stripe Terminal** is the strongest card-present story because Stripe sells the terminal hardware (BBPOS WisePOS E, Stripe S700) and the SDK directly supports the iPad use case via the Stripe Terminal SDK for iOS / JavaScript. **Fiserv** card-present integration depends on which Clover terminal model and which API path.

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
