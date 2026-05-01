# ERPNext POS Business Process Gotchas — Field Research

**Date:** 2026-05-01
**Purpose:** Surface forgotten / under-handled business processes in real ERPNext POS deployments. Input to Phase B audit (`docs/audits/pos_business_process_gap_audit.md`) and Hamilton ERP Phase 2/3 planning.
**Scope:** ERPNext v13–v16, field reports sourced from discuss.frappe.io, github.com/frappe/erpnext, r/ERPNext, and consultant blogs.

---

## TL;DR — Top 10 Gotchas by Frequency

1. **POS Closing Entry — change amount overcounts cash** (G-001): the closing total adds full cash received without subtracting change, causing every shift to show a phantom overage.
2. **Deferred stock validation — stock errors surface only at shift close, not at sale time** (G-002): operators sell a last item, someone returns it, the POS closing entry then explodes.
3. **100% discount / comp invoices cannot be submitted** (G-003): validation blocks zero-value invoices; complimentary admissions require a custom workaround.
4. **No native card terminal integration** (G-004): ERPNext POS has no built-in physical terminal; virtually every real deployment uses standalone card machines and manual entry.
5. **POS invoice customer field not set when created via new-customer flow** (G-005): causes silent consolidation failures at close.
6. **Expired pricing rules keep applying after their valid_upto date** (G-006): promotional prices silently persist beyond the campaign window.
7. **Tax-inclusive pricing double rounding** (G-007): the net_amount is rounded, then multiplied by the tax rate — introducing a second rounding pass that misstates the tax ledger.
8. **POS offline mode data loss — invoices missing after sync** (G-008): offline transactions fail to sync and must be re-entered manually from paper receipts.
9. **No per-customer price list switching in POS** (G-009): selecting a non-default customer doesn't switch their price list; member rates don't auto-apply.
10. **POS Closing Entry skips invoice created at the exact closing timestamp** (G-010): a race condition leaves one invoice unconsolidated forever.

---

## Methodology

**Sources searched:**
- discuss.frappe.io — keyword searches for: POS closing, POS return, cash reconciliation, POS variance, split payment, partial payment, offline mode, price list, accounting dimension, coupon code, discount, void, comp, cashier, opening balance, thermal printer
- github.com/frappe/erpnext — Issues searched: POS closing, POS return, negative stock POS, write off amount, pricing rule POS, accounting dimension POS, coupon code POS, fractional amount, 100% discount
- GitHub community apps: github.com/aisenyi/stripe_terminal, github.com/esafwan/erpnext_pos_coupon, github.com/bailabs/tailpos
- Web searches covering: card terminal integration, multi-jurisdiction tax, membership/subscription billing, chargeback handling, tip payroll accounting, receipt printer setup, multi-tablet sync

**Approximate volume reviewed:** ~50 GitHub issues, ~25 Frappe forum threads, ~10 community GitHub apps surveyed.

---

## Gotchas — Full List, Ranked by Frequency

---

### G-001 — POS Closing Entry overcounts cash by including change amount in total

- **Source:** https://discuss.frappe.io/t/pos-closing-shows-incorrect-closing-amount-because-change-amount-is-not-deducted-from-cash-received/155583
- **Deployment context:** Retail/hospitality, any size, Frappe v13–v16
- **The problem:** When a customer pays $5 for a $2 item, ERPNext records the full $5 as cash received in the POS Closing Entry — without subtracting the $3 change given back. Physical cash in the drawer is $2 higher than the opening, but the POS system shows $5 higher. Every shift that has any change transactions will appear to be over.
- **Root cause:** The POS Closing Entry totals the `paid_amount` field from each invoice but ignores the `change_amount` field. The `Account for Change Amount` in POS Profile is designed to route change to a separate float account, but the closing total does not offset it.
- **Resolution (or lack):** Community suggestion is to configure "Account for Change Amount" to a separate account per Mode of Payment, but the reported behaviour that the closing totals are wrong persists in multiple versions as of late 2025. No confirmed core fix.
- **Hamilton relevance:** HIGH. Hamilton's cash flow depends on the blind count. If the system's expected total is wrong, the operator can't verify their drop against it. The `submit_retail_sale` controller should confirm it uses `grand_total` (not `paid_amount`) when calculating expected cash. Also: Hamilton already uses a dedicated Float Account — verify the closing entry subtracts change correctly.
- **Frequency in field reports:** HIGH — multiple independent threads, versions v13–v16
- **Process category:** cash / reconciliation

---

### G-002 — Stock validation fires at POS Closing, not at sale time — refund batches explode the close

- **Source:** https://github.com/frappe/erpnext/issues/50787 (open as of 2025-11-27); https://github.com/frappe/erpnext/issues/46240
- **Deployment context:** Any venue using POS with "Update Stock" enabled, any size, ERPNext v15.53+
- **The problem:** When a shift contains both a sale and a same-shift return of the same item, the following timing mismatch occurs: the sale's stock deduction is committed immediately on POS Invoice submit; the return's stock credit is only applied when POS Closing Entry runs. The closing entry's internal validation runs before the credit is applied, sees a net-negative stock balance, and throws: `"1.0 units of Item X needed in Warehouse Y to complete this transaction."` The entire shift close fails.
- **Root cause:** POS invoices write to stock ledger immediately on submit. POS return invoices (credit notes) do not write to the stock ledger until POS Closing Entry consolidation. The consolidation validation runs before the return credits are posted.
- **Resolution (or lack):** Temporary workaround: enable "Allow Negative Stock," run the close, immediately disable it. Open issue as of late 2025 — no fix merged.
- **Hamilton relevance:** HIGH. This is already tracked as R-010 in `docs/risk_register.md`. Hamilton's comp flow and any future refunds create exactly this condition. The workaround (Allow Negative Stock) is unsafe at a venue because it could mask real overruns on physical inventory. Candidate for a custom consolidation hook that pre-processes returns before validation.
- **Frequency in field reports:** HIGH — duplicated across issues #50787 and #46240, with multiple +1 comments
- **Process category:** inventory / refund / POS closing

---

### G-003 — 100% discount / complimentary admissions cannot be submitted in POS

- **Source:** https://github.com/frappe/erpnext/issues/40631; https://github.com/frappe/erpnext/issues/52002
- **Deployment context:** Any venue needing comps, free trials, staff access, or zero-price items, Frappe v14–v16
- **The problem:** Applying a 100% discount to a POS invoice item causes a validation error on submit. Two separate bugs compound this: (a) the general submit block on 100% discount items, and (b) a tax-inclusive rounding bug where the Net Total rounds to ₹0.01 while Grand Total is ₹0.00, triggering "Incorrect value: Grand Total (Company Currency) must be >= 0.0."
- **Root cause:** Validation logic does not differentiate between a fraudulent zero-value sale and a legitimate complimentary transaction. Tax-inclusive rounding compounds the problem by leaving a fractional cent mismatch.
- **Resolution (or lack):** No native resolution. Workarounds used in the field: (a) use a nominal $0.01 item price, (b) create a dedicated "comp" item with a $0 fixed price in a separate price list, (c) use a pricing rule that sets the price to $0 for the comp customer group, (d) install third-party "POS Awesome" which handles this differently.
- **Hamilton relevance:** CRITICAL. Staff access, comp admissions, and goodwill giveaways are real flows at Hamilton. The current `submit_retail_sale` must have a tested path for zero-value invoices. Verify this now — before go-live.
- **Frequency in field reports:** HIGH — reported repeatedly across v13–v16, multiple threads
- **Process category:** comp / discount / operator workflow

---

### G-004 — No native physical card terminal integration in ERPNext POS

- **Source:** https://discuss.frappe.io/t/if-you-are-using-pos-in-the-usa-how-do-you-accept-credit-card-payment/45998; https://github.com/aisenyi/stripe_terminal
- **Deployment context:** Any retail venue accepting card, any jurisdiction, any size
- **The problem:** ERPNext POS has no built-in integration with physical card terminals (Fiserv Clover, Square, Stripe Terminal, Moneris, Verifone, etc.). The default workflow is: run the card on a standalone terminal beside the computer, get the approval code, then manually enter the transaction total in ERPNext. There is no automatic "paid by card" confirmation flowing from the terminal into the POS invoice.
- **Root cause:** Frappe's payments module supports online gateways (Stripe, Razorpay, PayPal) but not the physical terminal protocol (Stripe Terminal SDK, Fiserv's Clover Connect, First Data's POSAPI). Community apps exist (github.com/aisenyi/stripe_terminal, github.com/aisenyi/pasigono) but are community-maintained and may lag behind Frappe core releases.
- **Resolution (or lack):** Most small deployments accept the manual-entry approach. For integrated card: Stripe Terminal (via community app) is the most mature option. For Fiserv/First Data, no open ERPNext integration exists as of 2026.

> "All my customers use standalone credit card machines, that plug into the wall with telephone lines." — forum user describing standard practice

- **Hamilton relevance:** HIGH. Hamilton's Phase 2 card integration (Fiserv per DEC-0XX) must be built custom. The SAQ-A model is correct — terminal handles all card data, ERPNext stores only last 4 + auth code. The existing CLAUDE.md audit rule (Issue I) already flags this. Confirm Fiserv's integration model before Phase 2 scope is finalized.
- **Frequency in field reports:** HIGH — this comes up in virtually every North American deployment discussion
- **Process category:** card payment / hardware / PCI compliance

---

### G-005 — POS invoice customer field unpopulated when customer created at POS — consolidation fails silently

- **Source:** https://github.com/frappe/erpnext/issues/29544
- **Deployment context:** Any venue that allows creating new customers during POS sessions, ERPNext v13
- **The problem:** When a cashier creates a new customer from within the POS interface during a sale, the customer name displays in the invoice's UI title, but the `customer` field on the POS Invoice document is not actually set. The invoice proceeds and shows as PAID. At POS closing, the consolidation logic cannot group or submit the invoice and it is silently skipped. The unsubmitted invoice becomes an orphan — sales revenue from that transaction is never posted to the General Ledger.
- **Root cause:** The new-customer creation flow in the POS UI updates the UI display name but does not save the customer link field to the backend document before submission. A race condition between the UI update and document save.
- **Resolution (or lack):** The reporter suggested validation before submission to detect missing customer field and auto-populate. Fixed in later versions but patterns persist in custom code.
- **Hamilton relevance:** MEDIUM. Hamilton uses a single walk-in customer (`hamilton_walkin_customer` from `frappe.conf`) so this scenario is avoided at the POS level. However, if any future flow allows custom customer creation from the POS (e.g. membership signup), this gap should be tested explicitly.
- **Frequency in field reports:** MEDIUM — reported in multiple venues, particularly those with mixed customer databases
- **Process category:** customer management / invoice consolidation

---

### G-006 — Expired pricing rules keep applying after their valid_upto date

- **Source:** https://github.com/frappe/erpnext/issues/50122 (marked "released" with PR #50667)
- **Deployment context:** Any venue using time-limited promotions, Frappe v14–v16 prior to fix
- **The problem:** A pricing rule set to expire on date X continues applying its discount to invoices created on date X+2. The `apply_pricing_rule` function in ERPNext core did not validate the `valid_upto` date against the invoice's `posting_date` when applying the rule. A 5% discount for a promo that ended last week silently continues.
- **Root cause:** The `apply_pricing_rule` function receives `posting_date` in its parameters but never checks it against the rule's validity window.
- **Resolution (or lack):** Fixed in PR #50667. The issue was marked "released," but version pinning matters — earlier v16 builds have this bug. Verify by running a test invoice dated past the promo window.
- **Hamilton relevance:** MEDIUM. Hamilton currently has 4 SKUs with flat pricing, so this is not live today. As promo pricing grows (happy hour, member rate, new-venue launches), this is a silent revenue leak risk. The first promo launch should include a day-after smoke test: confirm the discount is no longer applied.
- **Frequency in field reports:** MEDIUM — multiple affected installations
- **Process category:** pricing / promotions

---

### G-007 — Tax-inclusive pricing double rounding misstates the tax ledger

- **Source:** https://discuss.frappe.io/t/tax-inclusive-pricing-tax-amount-is-wrong-due-to-double-rounding/160161
- **Deployment context:** Any venue using tax-inclusive item prices (price shown to customer already includes tax), any jurisdiction, Frappe v14–v16
- **The problem:** When "Is this Tax included in Basic Rate?" is enabled, ERPNext: (1) rounds the intermediate `net_amount`, then (2) multiplies the rounded net_amount by the tax rate to get the tax. Multiplying an already-rounded number by the tax rate introduces a second rounding error. The grand total displayed to the customer is correct (ERPNext silently adjusts), but the tax account entry in the GL is wrong by 1 cent. Over time, HST payable is understated.
- **Root cause:** `current_tax_amount = (tax_rate / 100.0) * item.net_amount` — net_amount is pre-rounded, so the tax calculation has already lost precision.
- **Resolution (or lack):** Issue closed by Frappe as "working as expected." Reporter continued experiencing the problem. No fix in core.
- **Hamilton relevance:** HIGH. Hamilton prices items inclusive of HST (the guest sees one price). This bug affects Hamilton's HST remittance. Verify whether Hamilton's current price model uses inclusive or exclusive pricing, and whether the variance is material at Hamilton's volume. At small volumes the error is sub-cent per transaction but accumulates.
- **Frequency in field reports:** MEDIUM — known across multiple tax jurisdictions
- **Process category:** tax / accounting

---

### G-008 — Offline mode data loss — invoices fail to sync and disappear

- **Source:** https://discuss.frappe.io/t/offline-pos-syncing-issue/38370; https://github.com/frappe/erpnext/issues/29068
- **Deployment context:** Any deployment using offline POS (unreliable internet, tablet POS), Frappe v12–v14
- **The problem:** When ERPNext POS operates offline (browser-cached mode), completed transactions are stored locally. If the sync to the backend fails — due to a network timeout, a browser crash, a tab close, or a background sync conflict — the invoices disappear entirely. The only recovery path is to re-enter them manually from paper receipts.

> "Were you able to find any solution? This is a recurring issue with offline POS." — forum user, no answer received

- **Root cause:** Frappe removed the robust browser-based offline POS cache in v12, replacing it with "Event Streaming," which proved "unstable and complex in practical scenarios." Duplicate-check logic for replay was incomplete.
- **Resolution (or lack):** No reliable resolution. Third-party apps (TailPOS, github.com/bailabs/tailpos) use an offline-first architecture with two-way sync and idempotency keys, which is more reliable but requires a separate install and maintenance burden.
- **Hamilton relevance:** MEDIUM. Hamilton's venue uses wired LAN + wifi with a managed router. Offline mode is not a planned operating mode. However, if internet goes down mid-shift (Rogers outage, etc.), Hamilton has no offline fallback. Operators would have to take cash-only on paper and re-enter on restore. Document this in the operations runbook.
- **Frequency in field reports:** HIGH historically — massive thread volume in v10–v13; somewhat reduced post-v14 as offline mode was de-emphasized
- **Process category:** infrastructure / reliability

---

### G-009 — POS does not switch price list when a non-default customer is selected

- **Source:** https://discuss.frappe.io/t/does-point-of-sale-works-with-item-price-lists/119860
- **Deployment context:** Any venue with tiered pricing (member vs. walk-in, wholesale vs. retail), Frappe v13–v16
- **The problem:** In the ERPNext POS UI, each POS Profile has a single default price list. When a cashier selects a customer who belongs to a customer group with a different price list (e.g., "Member" price list), the item prices do not update. The default walk-in price remains displayed. The cashier must manually apply a discount — or knows to look the other way.

> "Only the default price list is loaded for all customers. If we pick a customer from the non-default Pricing List, the price does not get updated." — forum user shirkit

- **Root cause:** The POS page loads item prices once from the default price list on session open. It does not re-fetch prices when the customer selection changes the applicable price list.
- **Resolution (or lack):** Workarounds: (a) extensive Pricing Rules for each member rate — 3,000 items manually configured per one user's report; (b) separate POS Profiles per customer tier — works but "cash counting might be a problem"; (c) POS Awesome (v14 only) supports price list switching. No core fix in standard ERPNext.
- **Hamilton relevance:** HIGH for Phase 2/3 when DC membership launches. Walk-in price vs. member price is a fundamental billing distinction. If Hamilton sells member day passes, the POS must auto-apply the member price when the member's tag is scanned. This is a design gap that needs a custom solution or POS Awesome migration.
- **Frequency in field reports:** HIGH — recurring discussion across retail and membership venues
- **Process category:** pricing / membership

---

### G-010 — POS Closing Entry misses the invoice created at the exact closing timestamp

- **Source:** https://github.com/frappe/erpnext/issues/41514 (opened May 2024)
- **Deployment context:** Any POS deployment, particularly busy-close scenarios, ERPNext v15–v16
- **The problem:** POS Closing Entry collects all POS invoices created between the opening and closing timestamp. Invoices created at precisely the same second as the closing timestamp are excluded by the time-range filter (likely `< closing_time` rather than `<= closing_time`). Those invoices remain perpetually unconsolidated — they are never included in any future closing entry either, because the next shift's opening time is after them.
- **Root cause:** Off-by-one in the timestamp comparison: `posting_time < closing_time` instead of `posting_time <= closing_time`.
- **Resolution (or lack):** Issue opened May 2024, assigned, no PR merged as of the research date. The unconsolidated invoice must be manually submitted as a journal entry or via a custom script.
- **Hamilton relevance:** LOW in normal operation (the probability of exact-second collision is small). HIGH if Hamilton ever uses automated session-close scripts that trigger the closing entry immediately after the last transaction. Add a post-close audit step: verify `frappe.get_all('POS Invoice', filters={'status': 'Submitted', 'consolidated_invoice': ''})` returns zero after every close.
- **Frequency in field reports:** MEDIUM — several +1 reports in the thread; likely underreported because operators don't know it happened
- **Process category:** POS closing / data integrity

---

### G-011 — POS Closing Entry fails with tax charge-type reference error

- **Source:** https://github.com/frappe/erpnext/issues/41329 (closed, unclear fix); https://github.com/frappe/erpnext/issues/35857
- **Deployment context:** Any venue using compound tax rules (e.g., tax-on-tax, or "On Previous Row Amount" charge types), Frappe v14–v15
- **The problem:** When a Sales Taxes Template uses charge type "On Previous Row Amount" or "On Previous Row Total" and a reference row is set, submitting POS Closing Entry throws: `"Can refer row only if the charge type is 'On Previous Row Amount' or 'Previous Row Total.'"` This validation fires even when the reference is correctly configured, blocking shift close entirely.
- **Root cause:** The POS Closing Entry generates a consolidated Sales Invoice from the POS invoices; the re-creation of the tax template rows does not correctly carry over the row reference, so the validation fails on what is effectively a system-generated copy.
- **Resolution (or lack):** Issue closed with no linked fix. Field teams that hit this typically flatten their tax template to "Actual" or "On Net Total" charge types to avoid the compound reference.
- **Hamilton relevance:** MEDIUM. Hamilton's Ontario HST 13% template uses "On Net Total" — this specific bug would not fire. When Hamilton adds Philadelphia (PA compound tax: 6% + 8% prepared food) or DC (6% + 10% alcohol), any compound tax template with row references will be at risk. Design those templates to avoid row-reference charge types.
- **Frequency in field reports:** MEDIUM — multiple reports across v14–v15
- **Process category:** tax / POS closing

---

### G-012 — POS Closing Entry cross-posts to wrong company in multi-company setup

- **Source:** https://github.com/frappe/erpnext/issues/40866; https://github.com/frappe/erpnext/issues/33724
- **Deployment context:** Multi-company ERPNext instances (e.g., separate legal entities per venue), Frappe v13–v16
- **The problem:** In a multi-company setup, the POS Closing Entry for Company B fetches the "Change Amount Account" from Company A's defaults. When the consolidated Sales Invoice is created, it fails with: `"Account [account] does not belong to Company B."` Shift close fails entirely until an administrator manually corrects the account on the closing entry.
- **Root cause:** The code fetches the change amount account from `frappe.defaults.get_global_default("default_cash_account")` which returns Company A's account regardless of which company the POS profile belongs to.
- **Resolution (or lack):** Partially fixed in various PRs but still reported in v16 (issue #40866 is a 2024 report). The fix requires explicitly reading the company from the POS Profile and fetching that company's accounts.
- **Hamilton relevance:** HIGH for multi-venue expansion. If Hamilton sets up Philadelphia or DC as a separate legal entity (which is typical for US venue liability isolation), each venue's POS Profile must be on a separate company entity in ERPNext. This bug would fire immediately. Document in `venue_rollout_playbook.md` Phase 0: verify cross-company POS account defaults before the first close at each new venue.
- **Frequency in field reports:** HIGH among multi-company deployments; MEDIUM overall
- **Process category:** multi-entity / POS closing

---

### G-013 — POS Invoice duplicate submissions under load — same sale posted multiple times

- **Source:** https://discuss.frappe.io/t/erpnext-freezing-pos-sales-auto-submission-duplicate-sales/33556
- **Deployment context:** Retail with high transaction volume (800+ invoices/day), multiple concurrent POS users, ERPNext v9–v10
- **The problem:** Under concurrent load, ERPNext POS submits the same invoice multiple times within seconds. One user reported: `"One transaction got posted 5 times!!"`. The duplicate invoices inflate revenue figures and create stock over-deductions. Reconciliation requires manual cancellation of duplicates, which (in submitted state) requires cancel + amend cycles.
- **Root cause:** The submission trigger in the POS JavaScript fired multiple times on double-tap or slow response, and server-side idempotency was absent — there was no guard against resubmission of an already-submitted document.
- **Resolution (or lack):** Fixed in PR #12985 for online POS (v9–v10 era). Offline POS was left unresolved. Post-v14, the POS architecture changed significantly and this specific pattern was reduced, but race conditions in concurrent submission are still reported sporadically.
- **Hamilton relevance:** LOW at current single-operator scale. MEDIUM when multi-venue opens with multiple operators. Ensure Hamilton's `submit_retail_sale` whitelisted method is idempotent — if called twice with the same session_id, the second call should be a no-op, not a second invoice. Test this explicitly.
- **Frequency in field reports:** HIGH historically (v9–v10), MEDIUM in current versions
- **Process category:** data integrity / concurrency

---

### G-014 — Receipt reprinting is unlimited — no fraud control on duplicate receipts

- **Source:** https://discuss.frappe.io/t/pos-double-printing-security-flaw/34676; https://discuss.frappe.io/t/securing-erpnext-pos-no-multiple-print-no-breadcrumb-single-conclude-button/18390
- **Deployment context:** Any POS with cashier-level operators, retail/hospitality
- **The problem:** Any cashier can navigate to the invoice list via breadcrumbs, reopen any submitted invoice, and reprint the receipt. The system does not track how many times a receipt has been printed or require manager authorization for reprints. A dishonest cashier can print an extra receipt for a cash transaction and use it to remove merchandise, claim a second payment, or back-date a "return."
- **Root cause:** ERPNext's receipt print action is just a print format render — there is no print-count field or reprint authorization workflow.
- **Resolution (or lack):** Community workarounds: hide breadcrumbs via custom CSS/JS, remove Print permission from the Cashier role. No native print-count tracking or reprint-auth workflow. Third-party apps like POS Awesome offer optional single-print mode.
- **Hamilton relevance:** MEDIUM. Hamilton is single-operator most of the time, so the social-engineering risk is lower. However, for multi-operator environments and any future employee growth, adding a "print once" constraint or at minimum a reprint audit log is worth considering in Phase 2.
- **Frequency in field reports:** MEDIUM — security-focused discussion threads
- **Process category:** fraud control / access control

---

### G-015 — No fixed-amount discount in POS — percentage-only

- **Source:** https://discuss.frappe.io/t/fixed-discount-in-pos-any-workarounds/116383
- **Deployment context:** Any retail POS needing "X dollars off" promotions (common in hospitality), Frappe v14–v16
- **The problem:** ERPNext POS supports percentage discounts only. There is no way to apply a flat "$5 off this order" discount in the standard POS interface. Community confirmation from an NCP moderator: `"there's no option for a specific discount amount — this feature isn't in the Point of Sale (POS) system."`
- **Root cause:** The POS discount UI only renders a single percentage field. The underlying Sales Invoice supports `discount_amount` as a fixed value, but the POS front-end does not expose it.
- **Resolution (or lack):** Workarounds: (a) POS Awesome (overengineered for this alone, per forum users), (b) create an item called "Discount" with a negative price, (c) use a pricing rule with a "Flat Discount Amount" — but this requires the pricing rule to evaluate before the cart total is shown (see G-006).
- **Hamilton relevance:** MEDIUM. Hamilton's current pricing model is fixed-rate service tiers, so this is not an immediate gap. Future membership incentives (e.g., "$20 off your next locker upgrade") would hit this wall. Document in Phase 2 backlog.
- **Frequency in field reports:** HIGH — one of the most commonly requested POS features
- **Process category:** discount / pricing

---

### G-016 — Coupon code field has a self-referential dependency — never renders in POS v16

- **Source:** https://discuss.frappe.io/t/coupon-code-field-is-not-visible-in-v16-12-0-pos-screen-even-after-correct-setup/162190
- **Deployment context:** Any ERPNext v16.12.0 POS using coupon codes, Frappe v16
- **The problem:** The `coupon_code` field on POS Invoice has `"depends_on": "coupon_code"` — a self-referential condition that means the field only renders if it already has a value. On a new invoice, it never renders, so cashiers cannot enter coupon codes at all.
- **Root cause:** A metadata bug in the field definition — the `depends_on` value accidentally points to the field itself rather than to a valid trigger condition.
- **Resolution (or lack):** The root cause is identified in the community thread. Fix requires changing the `depends_on` expression on the `coupon_code` field in the POS Invoice DocType. No confirmed core PR merged as of the research date. Workaround: direct the cashier to the Sales Invoice form instead, which renders the field.
- **Hamilton relevance:** LOW currently (no coupon campaigns). HIGH the moment Hamilton runs a digital promo code campaign. Test before any promo launch on v16.
- **Frequency in field reports:** LOW — new in v16.12.0
- **Process category:** promotions / UI bug

---

### G-017 — Accounting dimensions missing from consolidated POS invoice — mandatory GL fields blank

- **Source:** https://github.com/frappe/erpnext/issues/36210 (closed, fix PR #36668); https://github.com/frappe/frappe/pull/46961
- **Deployment context:** Any deployment using Accounting Dimensions (e.g., cost centre, department, branch) with Mandatory for P&L enabled, Frappe v13–v15
- **The problem:** When POS invoices are merged into a consolidated Sales Invoice at shift close, the accounting dimensions configured in the POS Profile (e.g., Department = Operations) are not carried over. The consolidated invoice is missing the mandatory dimension, and GL entry submission fails with: `"Accounting Dimension [name] is required for 'Profit and Loss' account [account code]."`
- **Root cause:** The consolidation script was scrubbing/unscrubbing accounting dimension field names incorrectly — mapping the display label rather than the actual field name. The field value was dropped in translation.
- **Resolution (or lack):** Fixed in PR #36668 (v13 era) and a follow-up fix in PR #46961 (April 2025 for later versions). If Hamilton's production is on a tagged v16 release earlier than the April 2025 fix, this could still fire.
- **Hamilton relevance:** MEDIUM. Hamilton may add a venue-level accounting dimension for multi-site P&L reporting. Check whether Hamilton's production v16 tag post-dates the April 2025 fix before enabling mandatory dimensions.
- **Frequency in field reports:** MEDIUM — affects multi-department and multi-venue setups
- **Process category:** accounting / POS closing

---

### G-018 — Write-off amount and change amount are mutually dependent — interaction causes validation errors

- **Source:** https://github.com/frappe/erpnext/issues/45607; github.com/frappe/erpnext/pull/30395; github.com/frappe/erpnext/pull/44763
- **Deployment context:** Any POS with cash rounding or any POS return, Frappe v13–v16
- **The problem:** In a POS invoice, the `write_off_amount` is auto-calculated based on the `change_amount`, and `change_amount` is auto-calculated based on `write_off_amount`. They are circularly dependent. In cases where both are non-zero (cash rounding + change), the calculation loops produce incorrect values. Applying "Write off amount" and "Change amount" simultaneously on a POS Invoice with `is_pos` checked is not reliably possible.
- **Root cause:** Circular dependency in the POS invoice validation logic — each field's on-change handler recalculates the other.
- **Resolution (or lack):** Multiple PRs have attempted partial fixes (#30395, #44763). The issue recurs in new cases. The current state is fragile for any edge case involving both rounding and change.
- **Hamilton relevance:** HIGH. Hamilton's CAD nickel rounding (the $0.05 smallest fraction) means cash POS sales almost always have a write-off component (rounding to nearest nickel) AND may have a change component. This interaction is untested in Hamilton's current implementation. Add an explicit test: a cash sale of $13.04 should round to $13.05 and give $0.00 change when paid with $13.05, with a $0.01 write-off.
- **Frequency in field reports:** HIGH — multiple PRs and issues
- **Process category:** cash / rounding / accounting

---

### G-019 — POS return calculates refund from paid_amount instead of grand_total — overrefunds customer

- **Source:** https://github.com/frappe/erpnext/issues/30627 (closed)
- **Deployment context:** Any POS with cash returns, ERPNext v13.24.0
- **The problem:** When a customer returns an item and the original sale had change (customer paid more than total), the return invoice tries to refund the full `paid_amount` (what the customer actually handed over) rather than the `grand_total` (the item cost). Example: item costs R2,584, customer paid R2,600, change was R16. On return, system tries to refund R2,600 instead of R2,584.
- **Root cause:** The return invoice logic copies `paid_amount` from the original invoice rather than `grand_total`. The change amount is not subtracted.
- **Resolution (or lack):** Issue is closed, suggesting a fix was merged — but the exact version is unconfirmed. Verify in the current build by running a test return on a sale that had change.
- **Hamilton relevance:** HIGH. If Hamilton ever processes a cash refund (a rare but real scenario — wrong item, service issue), the operator should receive a specific dollar amount back, not the amount the customer originally handed over.
- **Frequency in field reports:** MEDIUM — reported across v13; may be resolved in v14+
- **Process category:** refund / cash

---

### G-020 — Partial return blocked — "Paid amount + Write Off Amount cannot be greater than Grand Total"

- **Source:** https://discuss.frappe.io/t/return-pos-invoice-with-partial-payment-paid-amount-write-off-amount-can-not-be-greater-than-grand-total/88527
- **Deployment context:** Any venue needing partial refunds, Frappe v14–v16
- **The problem:** If a customer returns some items from an order but not all, and a partial refund is appropriate, the return invoice validation throws: `"Paid amount + Write Off Amount can not be greater than Grand Total."` The validation compares amounts using the absolute value of the negative return invoice, but the logic is backwards for partial amounts. Full refunds work; partial refunds do not.
- **Root cause:** Validation logic in `validate_pos()` does not handle the partial return case. The fix (converting comparisons to absolute values for return invoices) was proposed and then rejected on "financial perspective" grounds.
- **Resolution (or lack):** Unresolved as of 2024. No confirmed fix or core workaround. Operators typically process partial returns as full returns and then create a new invoice for the kept items.
- **Hamilton relevance:** MEDIUM. Hamilton's typical transaction is atomic (one time slot, one locker). A partial refund would be unusual but not impossible (e.g., room charged but service partially delivered). If a partial refund is ever needed, it currently requires a convoluted workaround.
- **Frequency in field reports:** MEDIUM — multiple reports 2022–2024
- **Process category:** refund / POS return

---

### G-021 — No X/Z report — no native end-of-shift till snapshot or day-total reset

- **Source:** https://discuss.frappe.io/t/x-and-z-reports-end-of-day-cash-reconciliation-for-pos/4671; https://github.com/frappe/erpnext/issues/2731
- **Deployment context:** Any retail POS, especially regulated industries, any size
- **The problem:** Traditional retail POS systems provide X reports (intraday snapshots without reset) and Z reports (end-of-day close that zeroes the register and posts to accounting). ERPNext has no equivalent. One user stated: `"It seems like a very fundamental feature for a POS software, but I didn't see it in the software."` The POS Closing Entry partially covers Z-report function but does not zero the till float, produce a formatted Z-report printout, or create the bank-deposit journal entry automatically.
- **Root cause:** ERPNext's POS was designed around invoice management, not till management. The cashier workflow (opening float → sales → closing entry) maps loosely to Z-report concepts but lacks the operator-facing print format and the explicit reset mechanism.
- **Resolution (or lack):** No core X/Z report. Many deployments customize a Print Format on the POS Closing Entry to produce a Z-report-equivalent. Bank deposit must be handled as a separate Journal Entry or Payment Entry.
- **Hamilton relevance:** HIGH. Hamilton's blind cash control requires a formal end-of-night report the operator can sign and drop with the bag. This is custom work. The `submit_retail_sale` architecture should include a "generate closing summary" step that produces: opening float, total sales by type, expected cash, and bag reference. The operator signs it and drops the bag. This printout is the audit trail.
- **Frequency in field reports:** HIGH — one of the oldest recurring requests in the forum (first reported 2015, still recurring)
- **Process category:** cash / reporting / audit

---

### G-022 — Thermal receipt printer: variable-length receipts cause multi-page split and auto-cut confusion

- **Source:** https://discuss.frappe.io/t/please-share-your-experience-with-thermal-printer-on-pos-module/31855; https://discuss.frappe.io/t/thermal-printing-for-pos-receipts/4840
- **Deployment context:** Any POS using thermal receipt printers, Frappe v12–v16
- **The problem:** ERPNext POS generates receipts as PDFs. PDF rendering assumes a fixed page size. A thermal receipt printer has a variable-length paper roll. When the receipt content exceeds one "page," it prints on multiple sheets of thermal paper, with the auto-cutter activating between pages. Operators are left with two receipt strips that may or may not be understood as belonging to the same transaction. One user summarized: `"The way printing is handled in ERPNext does not allow for variable length receipts at this time."`
- **Root cause:** ERPNext's print framework uses weasyprint/wkhtmltopdf to generate PDFs with standard page sizes. Thermal printers require ESC/POS commands or RAW mode printing with variable length — a fundamentally different protocol.
- **Resolution (or lack):** Solutions: (a) design a minimalist receipt format that fits on one page (limit items per invoice), (b) use Epson's ePOS-Print JavaScript API for direct ESC/POS printing (requires configuration and network-accessible printer), (c) use a third-party print bridge (PrintNode, QZ Tray) that intercepts the PDF and renders it to ESC/POS. No core ERPNext solution.
- **Hamilton relevance:** HIGH. Hamilton spec includes an Epson TM-T20III receipt printer. Epson supports ePOS-Print API for network printing — this is the recommended path. Test the receipt format before go-live: a Hamilton receipt should fit on one continuous strip. Keep the format minimal (venue name, date/time, items, total, operator). Also note: PCI rules require last 4 only on card receipts — no full PANs.
- **Frequency in field reports:** HIGH — virtually every thermal printer deployment encounters this
- **Process category:** hardware / receipt printing

---

### G-023 — POS Closing Entry loses revenue from POS Invoices with no consolidated invoice after closing

- **Source:** https://github.com/frappe/erpnext/issues/41036 (Sales Invoice creation skipped during POS Close)
- **Deployment context:** Any POS deployment, ERPNext v15–v16
- **The problem:** Occasionally during POS Closing Entry, the job to create the consolidated Sales Invoice is silently skipped. POS invoices are marked as "consolidated" in their metadata, but no corresponding Sales Invoice exists. Revenue never hits the GL. There is no error surfaced to the operator — the closing entry reports success.
- **Root cause:** The background job that creates the consolidated Sales Invoice can fail silently (exception swallowed, or job queue timeout) while the parent POS Closing Entry still submits successfully.
- **Resolution (or lack):** Reported in 2024 on ERPNext v15–v16. No confirmed fix. Mitigation: after every shift close, query `frappe.get_all('POS Invoice', filters={'consolidated_invoice': ['is', 'not set'], 'status': 'Submitted'})` — if any rows exist, the close was incomplete.
- **Hamilton relevance:** HIGH. A silent skip means a night's revenue never hits the P&L. Hamilton should add a post-close integrity check: after every POS Closing Entry submission, verify zero orphaned POS invoices. If any exist, alert the operator and surface them for manual review.
- **Frequency in field reports:** MEDIUM — reported but hard to detect because it's silent
- **Process category:** data integrity / POS closing

---

### G-024 — No chargeback / dispute workflow — card reversals must be handled entirely outside ERPNext

- **Source:** General field research; https://discuss.frappe.io/t/expenses-and-credit-card-purchase-orderrs/24948 (tangential)
- **Deployment context:** Any venue accepting card payments, particularly in jurisdictions with consumer protection regulations (US, Canada)
- **The problem:** ERPNext has no chargeback workflow. When a payment processor notifies the merchant of a chargeback: (a) the funds are deducted from the merchant account, (b) a dispute window opens requiring response documents, (c) if the dispute is won, funds are reversed back. None of these steps — deduction, response tracking, potential reversal, processor fee — have a native ERPNext workflow. Accountants typically handle chargebacks via manual Journal Entries.
- **Root cause:** ERPNext's payments module covers online payment gateway transactions but has no concept of processor-level dispute management.
- **Resolution (or lack):** No native solution. Standard practice: (a) receive chargeback notification from processor portal, (b) create a Journal Entry in ERPNext debiting revenue / crediting accounts receivable (or cash), (c) track disputes in a spreadsheet or custom DocType, (d) if dispute won, reverse the JE.
- **Hamilton relevance:** LOW in Phase 1 (cash only). MEDIUM in Phase 2 (card integration). When Hamilton adds card payments, document the chargeback JE procedure in the operations manual. Also note: the SAQ-A integration model (terminal-only card data) reduces chargeback fraud risk but does not eliminate friendly fraud.
- **Frequency in field reports:** LOW in ERPNext threads (most hospitality operators accept this as out-of-scope), HIGH in general hospitality operator discussions
- **Process category:** card payment / accounting

---

### G-025 — Subscription / membership recurring payment gateway integration is thin — no Stripe/Authorize recurring native in POS

- **Source:** https://discuss.frappe.io/t/is-erpnext-solution-of-subscription-management-and-recurring-payment/161063; https://github.com/frappe/erpnext/issues/11239
- **Deployment context:** Any venue with membership tiers, recurring billing, or subscription services
- **The problem:** ERPNext has a Subscription module and an Auto Repeat module, but neither integrates with physical POS or with real-time payment gateway recurring billing (Stripe Subscriptions, Authorize.net ARB). The follow-up question in the forum — "Can Auto Repeat handle monthly payments with Stripe or Authorize.net?" — went unanswered. In practice, recurring membership billing is typically handled outside ERPNext (Stripe portal, manual renewal invoice) and then posted back as Payment Entries.
- **Root cause:** Frappe's payment integrations are oriented toward one-time checkout flows, not subscription billing with vault tokens, retry logic, failed payment handling, proration, and cancellation credits.
- **Resolution (or lack):** No native recurring payment via terminal. Several community apps (Razorpay subscriptions — India only, Stripe webhooks via custom code) exist but are not maintained for v16.
- **Hamilton relevance:** HIGH for DC membership launch (per `docs/venue_rollout_playbook.md`). DC memberships mean monthly billing. Hamilton needs to decide before DC launch: (a) manage all recurring billing in Stripe directly and import invoices to ERPNext, or (b) build custom recurring billing in ERPNext. Option (a) is safer and faster.
- **Frequency in field reports:** MEDIUM — active discussion in membership-oriented ERPNext communities
- **Process category:** membership / subscription

---

### G-026 — Petty cash / supplies from the till has no native workflow — requires manual Journal Entry each time

- **Source:** https://discuss.frappe.io/t/how-to-manage-petty-expenses-on-erpnext/129717; https://github.com/frappe/erpnext/issues/7582
- **Deployment context:** Any venue with small cash expenses from the till (toilet paper, printer paper, tip-out float), small/medium business
- **The problem:** ERPNext has no "Paid Out" or "Miscellaneous Expense" button in the POS interface — the kind that traditional restaurant/retail POS systems provide for taking cash from the drawer. Operators taking $8 for paper towels or $50 to tip a delivery driver must: close out of POS, navigate to Accounts → Journal Entry, create a JE against the petty cash account, and then return to POS. In practice, operators don't do this, the cash disappears from the drawer, and the reconciliation variance is unexplained.
- **Root cause:** POS interface has no "cash out" or "petty expense" transaction type.
- **Resolution (or lack):** POS Awesome adds a "Cash In/Out" movement feature. For native ERPNext, the POS Opening Entry has a "Cash In" feature but it is not designed for per-transaction expense logging.
- **Hamilton relevance:** HIGH. Hamilton's operations will include small cash disbursements (supplies, tips, float adjustments). Without a formal till-out workflow, these vanish from the reconciliation. Consider adding a custom "Cash Out" voucher type to the POS, or at minimum a daily petty cash JE template the operator can fill in 30 seconds.
- **Frequency in field reports:** HIGH among hospitality operators; lower for pure retail
- **Process category:** cash / petty cash

---

### G-027 — Tips paid from the till create a timing-offset accounting problem between POS close and payroll run

- **Source:** General field research; https://www.patriotsoftware.com/blog/payroll/tips-vs-auto-gratuities; payroll accounting guides
- **Deployment context:** Any hospitality venue where staff receive tips or service charges paid via POS cash, particularly in Canada and US
- **The problem:** When a customer pays a tip in cash via the POS, the flow is: (1) POS records total including service charge as revenue, (2) cash in till includes the tip amount, (3) at shift close, the operator pays the tip in cash to staff from the drawer, (4) the payroll run (weekly) records wage + tip-out as payroll expense. The problem: the cash leaves the till at shift close (reducing the drawer) but the corresponding payroll expense doesn't hit the GL until the payroll run. If tips are large, the cash drawer reconciliation shows a variance for the days between the cash payout and the payroll entry. Accountants call this a "tips payable" float account — but it requires deliberate setup to avoid confusion.
- **Root cause:** ERPNext's payroll and POS modules are not connected. Tips flow through cash but payroll is a separate batch process.
- **Resolution (or lack):** The correct accounting pattern: debit Cash, credit Tips Payable (liability) at POS close; debit Tips Payable, credit Cash at payroll run. ERPNext can do this with a custom Journal Entry template, but it requires deliberate configuration. Without it, the daily cash reconciliation will show variances equal to the tips paid out.
- **Hamilton relevance:** HIGH if Hamilton staff receive any cash gratuity. Even if tips are currently zero, the accounting structure should be set up before the first tip is paid. Create a "Tips Payable" liability account and a JE template for tip-out at shift close.
- **Frequency in field reports:** MEDIUM — mentioned in payroll and hospitality threads; low-frequency in ERPNext-specific discussion because most small operators ignore it and accept the variance
- **Process category:** payroll / cash / tips

---

### G-028 — No manager override / approval workflow for discounts at POS

- **Source:** https://github.com/frappe/erpnext/issues/11748 (enable/disable discount per POS Profile); https://discuss.frappe.io/t/fixed-discount-in-pos-any-workarounds/116383
- **Deployment context:** Any venue with cashier/manager role separation
- **The problem:** ERPNext has no native "require manager PIN/approval for discount above X%" workflow in POS. A cashier can apply any discount percentage (up to 100%) without any second-factor authorization. POS Profile can enable or disable discount fields globally, but there is no graduated control (e.g., cashier can discount 10%, manager required for >10%, director required for >50%). This is a standard fraud-prevention feature in enterprise POS systems.
- **Root cause:** POS discount configuration is binary: enabled or disabled at the POS Profile level.
- **Resolution (or lack):** No native solution. Workarounds: (a) disable discount entirely and use pricing rules (which apply automatically, no operator discretion), (b) use POS Awesome's extended permissions, (c) build a custom approval dialog via client-side script.
- **Hamilton relevance:** MEDIUM. With a single operator, manager approval isn't critical today. In a multi-operator multi-venue environment, uncontrolled discount capability is a significant loss-prevention gap. Design the Phase 2 POS profile configuration to disable ad-hoc discounts; all comps should go through the formal comp admission log, not a discount field.
- **Frequency in field reports:** MEDIUM — discussed by medium and larger deployments
- **Process category:** access control / fraud prevention

---

### G-029 — Item exchange (return + new item in one transaction) is not supported

- **Source:** https://github.com/frappe/erpnext/issues/7404; https://discuss.frappe.io/t/how-to-process-refunds-in-erpnext-complete-flow/19009
- **Deployment context:** Any retail venue with exchanges, Frappe v13–v16
- **The problem:** Retail's most common refund scenario — "I want to return Item A and get Item B instead" — has no single-transaction path in ERPNext POS. Return invoices can only include items from the original invoice. Adding a new item to a return invoice to create an exchange triggers: `"serial number for the new item doesn't belong to the original Sales Invoice."` The operator must process two separate transactions: a return invoice and a new sale invoice.
- **Root cause:** Return invoice validation enforces that all items must link back to the original invoice's items. This is by design (for audit trail), but it prevents exchange workflows.
- **Resolution (or lack):** Marked as a design limitation. Workaround: two transactions. POS Awesome also does not solve this natively.
- **Hamilton relevance:** LOW for Hamilton's current model (time slots and lockers are not exchangeable for different items). MEDIUM when retail products are added (towels, merchandise). For a service business, this matters when a guest is upgraded or downgraded to a different room type — which is a similar exchange pattern at the service level.
- **Frequency in field reports:** HIGH in retail; MEDIUM in hospitality
- **Process category:** refund / return

---

### G-030 — POS invoice number series creates gaps on draft deletion — audit trail compliance risk

- **Source:** https://github.com/frappe/erpnext/issues/11822; https://discuss.frappe.io/t/invoice-number-with-multiple-series-numbering/161610
- **Deployment context:** Regulated industries requiring sequential invoice numbering (Canadian CRA, provincial retail, most EU jurisdictions), any size
- **The problem:** When a POS invoice is created in draft state and then deleted (cancelled before submission), the naming series counter increments and does not reset. Invoice #1001, #1002 are submitted; draft #1003 is deleted; next invoice is #1004. Auditors (and CRA/IRS in some contexts) require contiguous invoice sequences with no unexplained gaps. A gap requires a written explanation.
- **Root cause:** Frappe's naming series is a counter that increments on document creation, not on document submission. Deletion does not decrement the counter.
- **Resolution (or lack):** Known limitation of Frappe's naming series design. Workaround: (a) configure POS to never create drafts (submit immediately on complete), (b) use a sequence number that resets daily and is supplemented by timestamp (so gaps are expected within the sequence), (c) document and explain gaps in audit log. No core fix.
- **Hamilton relevance:** MEDIUM. Canadian CRA does not currently require contiguous invoice numbering for small businesses, but the audit trail expectation is implicit. If Hamilton is ever audited, an unexplained invoice gap invites questions. Configure POS to submit directly (no draft state) and document the naming series behavior.
- **Frequency in field reports:** MEDIUM — particularly in regulated/international markets
- **Process category:** audit / compliance

---

### G-031 — ERPNext POS v16 opening entry cashier field drops silently — shift cannot start

- **Source:** https://discuss.frappe.io/t/erpnext-16-pos-opening-entry-can-not-select-cashier/159559
- **Deployment context:** ERPNext v16.0.0 specifically
- **The problem:** When creating a POS Opening Entry in ERPNext v16.0.0, selecting a user in the Cashier field causes the field to immediately clear itself, then the form throws "Cashier is required." Operators cannot start a shift. This was a regression in the initial v16.0.0 release.
- **Root cause:** Users were not pre-added to the POS Profile's "Applicable for Users" list. Additionally, a PR (#51984) changed the design so POS Opening Entry is no longer accessible directly — it must be created from within the POS interface at login.
- **Resolution (or lack):** Fixed in v16.1.0. Confirmed by user: `"The problem was with version 16.0.0. Now I installed version 16.1.0 and with this version it works ok."`
- **Hamilton relevance:** MEDIUM. Hamilton is on a specific tagged v16 release. Confirm Hamilton's build is v16.1.0 or later. Also note the architectural change: POS Opening Entry is now operator-initiated from the POS screen, not from the ERPNext desktop. Update operator documentation accordingly.
- **Frequency in field reports:** LOW — version-specific v16.0.0 only
- **Process category:** shift management / v16 migration

---

### G-032 — Multi-tablet concurrent POS: no per-asset locking — same room/locker double-booked

- **Source:** https://github.com/frappe/erpnext/issues/14721 (POS display on tablets and stock quantity); General concurrency research
- **Deployment context:** Multi-tablet venues where more than one operator can book the same resource simultaneously
- **The problem:** Standard ERPNext POS has no concept of asset/resource locking. If two tablets can both see "Room 101 = Available," both operators can simultaneously start a sale for Room 101. Both POS invoices submit. The double-booking is discovered only when both guests arrive at the same room.
- **Root cause:** ERPNext POS manages stock quantities, not discrete assets. Stock decrement on submit handles inventory, but a room or locker is a unique asset, not a fungible quantity-of-one. POS stock validation ("allow negative stock" etc.) operates at the item level, not at the serial number / asset level, so it cannot prevent two invoices for the same unique asset.
- **Resolution (or lack):** No native solution. Hamilton ERP Phase 1 specifically built a three-layer lock (Redis + MariaDB FOR UPDATE + optimistic version field) to address exactly this gap.
- **Hamilton relevance:** CRITICAL — this is the core problem Hamilton Phase 1 solved. The three-layer lock is the design answer. This gotcha validates the architectural choice. Ensure the lock documentation is preserved in `docs/decisions_log.md` for future maintenance.
- **Frequency in field reports:** MEDIUM in field reports (most single-operator POS don't hit it), HIGH in Hamilton's use case
- **Process category:** asset management / concurrency

---

### G-033 — "Allow Negative Stock" as a POS closing workaround creates lasting audit exposure

- **Source:** https://github.com/frappe/erpnext/issues/50787 (documented workaround)
- **Deployment context:** Any POS with stock-tracked items, particularly venues with physical goods
- **The problem:** The recommended workaround for the stock-validation-at-close bug (G-002) is to temporarily enable "Allow Negative Stock," run the close, then disable it. However: (a) the operator may forget to re-disable it, leaving negative stock permitted indefinitely; (b) during the window when it's enabled, other operators can process sales that create real stock-going-negative (e.g., scanning a spoiled item), which are then silently accepted; (c) the audit log shows "Allow Negative Stock was on at 11:47 PM" which can raise questions.
- **Root cause:** The workaround temporarily loosens a stock guard that should always be on.
- **Resolution (or lack):** See G-002 — no core fix yet. Hamilton's custom approach (processing stock immediately at sale time, not deferred to consolidation) avoids this entirely.
- **Hamilton relevance:** HIGH. Hamilton's architecture (immediate stock update via `submit_retail_sale`) was partly designed to avoid the deferred-stock problem. Confirm that Hamilton's stock entries are truly immediate and not deferred. If Hamilton ever hits the G-002 scenario, do NOT use Allow Negative Stock as a workaround — escalate to a developer fix.
- **Frequency in field reports:** MEDIUM
- **Process category:** inventory / operations

---

### G-034 — No native "lost and found" or "guest belongings" workflow

- **Source:** General hospitality field research; frappe.io/hospitality module survey
- **Deployment context:** Hotels, spas, wellness venues, bathhouses — any venue where guests leave belongings
- **The problem:** ERPNext has no lost-and-found module or workflow. Common requirements: log found item (description, location, date found, operator), link to a guest if identified, track storage location, manage unclaimed item disposal. None of this is in ERPNext core or the Frappe Hospitality module. Most venues manage this in a paper log or a separate spreadsheet.
- **Root cause:** Lost-and-found is outside the scope of ERP systems (it's an operations log, not a financial transaction). Frappe Hospitality focuses on reservations, restaurant tables, and room folios.
- **Resolution (or lack):** Custom DocType required. This is a relatively simple build: a DocType with found-date, description, location, linked guest (optional), status (stored / claimed / disposed), and disposal date. About 2 hours of development.
- **Hamilton relevance:** HIGH for a bathhouse. Guests leave phones, jewelry, clothes, keys regularly. Without a system, disputes about stolen or lost items become he-said-she-said. A simple lost-and-found log also serves as liability protection.
- **Frequency in field reports:** LOW in ERPNext discussions (not an ERP concern), HIGH in hospitality operator discussions
- **Process category:** operations / guest management

---

### G-035 — Multi-jurisdiction tax compliance requires per-venue setup that is not templated

- **Source:** https://github.com/frappe/erpnext/issues/8711; 4devnet.com multi-country ERPNext guide
- **Deployment context:** Multi-venue businesses spanning different tax jurisdictions (Canada/US, multi-province, multi-state)
- **The problem:** ERPNext does not have a "venue tax profile" abstraction. Each venue's tax jurisdiction (Ontario HST 13%, Pennsylvania sales tax 6%+8%, DC 6%+10%, Texas 8.25%) must be configured as a separate Sales Taxes and Charges Template, linked to the correct company entity, and tested independently. There is no migration wizard or templating tool. For a chain expanding to a new jurisdiction, the setup is fully manual and error-prone.
- **Root cause:** ERPNext's tax configuration is company-scoped, not venue-scoped within a company. Multi-jurisdiction within a single company requires custom code or separate company entities.
- **Resolution (or lack):** Standard practice: one ERPNext Company per legal entity per jurisdiction. Each company has its own chart of accounts, tax templates, and POS profiles. This means 4+ ERPNext companies for a 4-venue US+Canada chain, with inter-company consolidation required for group reporting.
- **Hamilton relevance:** CRITICAL for multi-venue expansion. This is already documented in CLAUDE.md (Audit Issue G) and `docs/decisions_log.md`. The Canadian nickel-rounding rule (CRA 2013) is a Canada-specific quirk. Philadelphia's prepared-food split rate, DC's alcohol rate, and Texas's statewide rate all need separate templates. Hamilton's `frappe.conf` per-venue tax template convention must be extended to each new venue.
- **Frequency in field reports:** HIGH for multi-jurisdiction operators
- **Process category:** tax / multi-venue

---

## Process Category Aggregates

| Category | Gotcha IDs | Count | Notes |
|---|---|---|---|
| Cash / Reconciliation | G-001, G-018, G-021, G-026, G-027 | 5 | Highest aggregate impact — affects every shift |
| POS Closing Entry bugs | G-001, G-002, G-010, G-011, G-012, G-017, G-023 | 7 | Hot spot: closing entry is the most failure-prone single step |
| Refund / Return | G-002, G-019, G-020, G-029 | 4 | Returns are systematically underbuilt in ERPNext POS |
| Comp / Discount | G-003, G-015, G-016, G-028 | 4 | Zero-value and controlled-discount flows are fragile |
| Card Payment / Hardware | G-004, G-022, G-024 | 3 | All require custom/external work; no native solutions |
| Inventory / Stock | G-002, G-033 | 2 | Deferred stock validation is the main risk |
| Pricing / Promotions | G-006, G-009 | 2 | Expired rules and price-list switching are silent bugs |
| Tax / Accounting | G-007, G-011, G-035 | 3 | Rounding and jurisdiction are both risky |
| Data Integrity / Race Conditions | G-005, G-010, G-013 | 3 | Concurrency and timing bugs are hard to detect |
| Access Control / Fraud | G-014, G-028 | 2 | No native manager-override or reprint audit |
| Membership / Subscription | G-009, G-025 | 2 | Both require significant custom work |
| Multi-venue / Multi-company | G-012, G-032, G-035 | 3 | Expansion-blocking if not planned |
| Operations (no ERP equivalent) | G-021, G-026, G-027, G-034 | 4 | X/Z reports, petty cash, tips, lost-and-found |
| Hardware / Printing | G-004, G-022 | 2 | ERPNext thermal receipt printing is non-trivial |
| Version-specific / Migration | G-031 | 1 | v16.0.0 regression — already fixed in v16.1.0 |

**Hottest spot:** POS Closing Entry (7 bugs). The closing entry is the single most failure-prone process in ERPNext POS. Every shift's close is a validation gauntlet — stock checks, accounting dimensions, tax charge types, company accounts, timestamp edge cases. Hamilton's post-close integrity check (zero orphaned POS invoices) is essential.

---

## "We Wish We'd Known" — The Single Most-Cited Gotcha Across the Corpus

The one gotcha that bit the most teams is **the deferred stock + refund timing bomb at POS close** (G-002, also compounded by G-033's workaround risk). Teams build their inventory flow, test it in a staging environment where there are no same-day returns, go live, and then on day three a cashier processes a return in the same shift as the original sale. The POS Closing Entry explodes with a cryptic stock validation error. The operator calls support, is told to enable "Allow Negative Stock," runs the close, and forgets to re-disable it. Two weeks later, the venue's stock ledger has sold more items than were ever in the warehouse. This pattern — a bug in the closing consolidation's stock timing, a risky workaround, and an easy-to-forget cleanup step — was documented in at least four separate GitHub issues and multiple forum threads, spanning ERPNext v13 through v16 (as of late 2025 still open). The reason it keeps resurfacing is structural: the POS Invoice and the POS Closing Entry are architecturally decoupled in their stock-ledger write timing, and the consolidation code does not account for same-shift returns. Any deployment with physical goods and even occasional returns will encounter this.

---

## Cited Threads / Issues (Full URL List)

### discuss.frappe.io / discuss.erpnext.com
- https://discuss.frappe.io/t/how-to-process-refunds-in-erpnext-complete-flow/19009
- https://discuss.frappe.io/t/correct-way-to-refund-a-customer-payment/33914
- https://discuss.frappe.io/t/pos-closing-shows-incorrect-closing-amount-because-change-amount-is-not-deducted-from-cash-received/155583
- https://discuss.frappe.io/t/return-pos-invoice-with-partial-payment-paid-amount-write-off-amount-can-not-be-greater-than-grand-total/88527
- https://discuss.frappe.io/t/erpnext-16-pos-opening-entry-can-not-select-cashier/159559
- https://discuss.frappe.io/t/is-erpnext-solution-of-subscription-management-and-recurring-payment/161063
- https://discuss.frappe.io/t/fixed-discount-in-pos-any-workarounds/116383
- https://discuss.frappe.io/t/x-and-z-reports-end-of-day-cash-reconciliation-for-pos/4671
- https://discuss.frappe.io/t/please-share-your-experience-with-thermal-printer-on-pos-module/31855
- https://discuss.frappe.io/t/thermal-printing-for-pos-receipts/4840
- https://discuss.frappe.io/t/if-you-are-using-pos-in-the-usa-how-do-you-accept-credit-card-payment/45998
- https://discuss.frappe.io/t/does-point-of-sale-works-with-item-price-lists/119860
- https://discuss.frappe.io/t/erpnext-slow-with-multiple-pos-users/33794
- https://discuss.frappe.io/t/offline-pos-syncing-issue/38370
- https://discuss.frappe.io/t/pos-closing-voucher-showing-wrong-difference/70937
- https://discuss.frappe.io/t/erpnext-freezing-pos-sales-auto-submission-duplicate-sales/33556
- https://discuss.frappe.io/t/securing-erpnext-pos-no-multiple-print-no-breadcrumb-single-conclude-button/18390
- https://discuss.frappe.io/t/pos-double-printing-security-flaw/34676
- https://discuss.frappe.io/t/tax-inclusive-pricing-tax-amount-is-wrong-due-to-double-rounding/160161
- https://discuss.frappe.io/t/coupon-code-field-is-not-visible-in-v16-12-0-pos-screen-even-after-correct-setup/162190
- https://discuss.frappe.io/t/how-to-manage-petty-expenses-on-erpnext/129717
- https://discuss.frappe.io/t/invoice-number-with-multiple-series-numbering/161610
- https://discuss.frappe.io/t/pos-closing-entry-multi-company/120498

### github.com/frappe/erpnext — Issues
- https://github.com/frappe/erpnext/issues/50787 — POS Closing Entry stock validation error with refunds (OPEN)
- https://github.com/frappe/erpnext/issues/46240 — POS Invoice stock validation deferred to close (CLOSED)
- https://github.com/frappe/erpnext/issues/41514 — POS Closing Entry misses invoice at exact close timestamp (OPEN)
- https://github.com/frappe/erpnext/issues/41329 — POS Closing Entry tax charge-type reference error (CLOSED)
- https://github.com/frappe/erpnext/issues/41036 — Sales Invoice creation skipped during POS Close (OPEN)
- https://github.com/frappe/erpnext/issues/40866 — POS Closing Entry multi-company wrong account (OPEN)
- https://github.com/frappe/erpnext/issues/40631 — POS 100% discount cannot submit (OPEN)
- https://github.com/frappe/erpnext/issues/36210 — POS invoice merging drops accounting dimensions (CLOSED via PR #36668)
- https://github.com/frappe/erpnext/issues/35857 — POS Closing Entry charge type reference error v14–v15
- https://github.com/frappe/erpnext/issues/34349 — Inventory shrinkage variance tracking (OPEN / Under Review)
- https://github.com/frappe/erpnext/issues/34134 — POS return totals wrong calculated
- https://github.com/frappe/erpnext/issues/33724 — Multi-company POS mode of payment fetched from default company
- https://github.com/frappe/erpnext/issues/33494 — paid_amount modified during validation on fractional grand_total
- https://github.com/frappe/erpnext/issues/30627 — POS return uses paid_amount instead of grand_total (CLOSED)
- https://github.com/frappe/erpnext/issues/29959 — Pricing rule applied even if ignore_pricing_rule checked
- https://github.com/frappe/erpnext/issues/29842 — Write off amount wrong in consolidated POS invoice
- https://github.com/frappe/erpnext/issues/29544 — POS invoice customer field not set — consolidation fails
- https://github.com/frappe/erpnext/issues/29354 — POS pricing rule discount shown after order complete only
- https://github.com/frappe/erpnext/issues/29068 — POS offline mode issues
- https://github.com/frappe/erpnext/issues/28601 — Coupon code based pricing rule not working for multiple rules
- https://github.com/frappe/erpnext/issues/12926 — POS rounding issue and unpaid invoices
- https://github.com/frappe/erpnext/issues/12810 — Do not allow over 100% discount in POS
- https://github.com/frappe/erpnext/issues/11822 — Invoice number series gap on draft deletion
- https://github.com/frappe/erpnext/issues/11748 — Enable/disable discount in POS using POS Profile
- https://github.com/frappe/erpnext/issues/7582 — POS Cash reconciliation
- https://github.com/frappe/erpnext/issues/7515 — Sales Return Invoice POS payment entry wrong
- https://github.com/frappe/erpnext/issues/7404 — Allow exchange for Sales Return
- https://github.com/frappe/erpnext/issues/6308 — Allow multiple POS profiles per user
- https://github.com/frappe/erpnext/issues/52002 — POS 100% discount + tax inclusive rounding bug (CLOSED as duplicate)
- https://github.com/frappe/erpnext/issues/51237 — POS Opening Entry (v16)
- https://github.com/frappe/erpnext/issues/50122 — Expired pricing rules still applied (RELEASED via PR #50667)
- https://github.com/frappe/erpnext/issues/45607 — Write off amount not working for Sales Invoice + POS Invoice
- https://github.com/frappe/erpnext/issues/45414 — Negative inventory submitting despite Allow Negative Stock disabled
- https://github.com/frappe/erpnext/issues/14721 — POS display on tablets and stock quantity

### github.com/frappe/erpnext — Pull Requests
- https://github.com/frappe/erpnext/pull/50667 — Fix: expired pricing rules (fix for G-006)
- https://github.com/frappe/erpnext/pull/46961 — Fix: consolidating POS invoices on accounting dimensions
- https://github.com/frappe/erpnext/pull/45899 — Fix: POS accounting dimension fieldname error
- https://github.com/frappe/erpnext/pull/44772 — Fix: POS Closing entry issue
- https://github.com/frappe/erpnext/pull/44763 — Fix: Paid + Write Off amount issue in Sales Invoice
- https://github.com/frappe/erpnext/pull/36668 — Fix: accounting dimensions in POS invoice merge
- https://github.com/frappe/erpnext/pull/30395 — Fix: write off amount wrongly calculated in POS Invoice

### Community Apps (evidence of ERPNext POS gaps)
- https://github.com/ucraft-com/POS-Awesome — Full POS replacement; existence signals native POS limitations
- https://github.com/defendicon/POS-Awesome-V15 — v15 fork
- https://github.com/aisenyi/stripe_terminal — Stripe physical terminal integration (native gap)
- https://github.com/aisenyi/pasigono — ERPNext POS hardware integrations
- https://github.com/esafwan/erpnext_pos_coupon — Coupon support for ERPNext POS (native gap)
- https://github.com/bailabs/tailpos — Offline-first POS for ERPNext (native gap)
- https://github.com/The-Commit-Company/mint — Bank reconciliation for ERPNext
