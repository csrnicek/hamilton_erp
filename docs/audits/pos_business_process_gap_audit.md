# POS Business Process Gap Audit

**Date:** 2026-05-01
**Author:** Phase B audit (Opus, autonomous overnight run), informed by Phase A research (`docs/research/erpnext_pos_business_process_gotchas.md`)
**Status:** ANALYSIS — does not commit any architectural changes; downstream design intent docs follow

---

## TL;DR

This audit covers **34 business processes** — the 17 Chris flagged plus 17 additional categories surfaced by the Phase A field-research review. Each was checked against four sources: Hamilton's build spec (`docs/hamilton_erp_build_specification.md`), Hamilton's custom DocTypes (`hamilton_erp/hamilton_erp/doctype/`), native ERPNext v16, and community apps documented in Phase A.

Results by gap classification: **already-handled = 6**, **tweak ERPNext = 7**, **extend custom = 11**, **build new = 10**. Phase 1 launch BLOCKERS: **5** (refunds + voids + comp manager-override + tip-pull cash flow + post-close orphan-invoice integrity check). Everything else can ship after the production URL flips, but five of these BLOCKERS must close before go-live or Hamilton operates without an audit-defensible cash-handling story on day 1.

The five highest-priority gaps received design intent docs (`docs/design/{process}_phase{N}.md`) — refunds, voids, manager-override, tip-pull-from-till, and post-close integrity. Each captures the *why*, not just the *what*, modeled on `docs/design/cash_reconciliation_phase3.md`. Implementation funding decisions can be made directly from those docs.

---

## Audit table

Legend:
- **Build spec:** is the process specced in `docs/hamilton_erp_build_specification.md`? (yes / partial / no)
- **Hamilton DocType:** is there a custom DocType implementing it? (yes / partial / no)
- **Native ERPNext:** does ERPNext provide it built-in? (yes / partial / no — with a note)
- **Community app:** did Phase A surface a maintained app? (yes-link / no)
- **Gap class:** already-handled / tweak / extend / build new
- **Phase:** 1-BLOCKER / 1.5 / 2 / 3 / 4+
- **Multi-venue flag:** does it depend on a planned per-venue config flag (`anvil_membership_enabled`, `anvil_tax_mode`, `anvil_currency`, `anvil_tablet_count`)?

| # | Process | Build spec? | Hamilton DocType? | Native ERPNext? | Community app? | Gap class | Phase | Multi-venue flag | One-line note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Refunds (cash & card) — settlement reconciliation pairing | partial (§6.7 names "POS Return") | no | partial — POS Return DocType, no settlement-pair logic | no | build new | **1-BLOCKER** | yes — `anvil_currency` for refund-rounding rule per venue | G-019/G-020/G-029; refund flow not specced beyond a single sentence |
| 2 | Comps & discounts (workflow + manager approval) | partial (Comp Admission Log specced; manager approval not) | partial (`comp_admission_log` exists) | no — discount field is binary | POS-Awesome (G-028) | extend custom | **1-BLOCKER** | yes — `anvil_membership_enabled` (DC member comps differ) | G-003/G-028; current flow has no manager-PIN gate above threshold |
| 3 | Voids (mid-shift transaction undo) | no | no | partial — cancel-amend cycle for submitted SI | no | build new | **1-BLOCKER** | no | No "void this last transaction" surface; operator must cancel + amend |
| 4 | End-of-shift handover between operators | partial (§7.5/7.6 cover one operator at a time) | partial (Shift Record covers single shift only) | no | no | extend custom | 1.5 | yes — `anvil_tablet_count` (overlapping shift at DC) | Hamilton single-operator today; DC needs handover overlap |
| 5 | Customer disputes / chargebacks (response packets) | no | no | no — JE-only workaround (G-024) | no | build new | 2 | no (latent until card payments live) | Latent until Phase 2 card; then mandatory before R-009 listing risk |
| 6 | Daily / weekly closeout & bank deposit | partial (§7.5 ends at "POS Closing Entry created") | partial (Cash Drop, Cash Reconciliation) | partial — POS Closing Entry, no Z-report (G-021) | no | extend custom | 1.5 | yes — `anvil_currency` (CAD/USD deposit slips) | No formal Z-report or deposit-slip generation |
| 7 | Petty cash / supply purchases from drawer | no | no | no (G-026) | no | build new | 1.5 | no | Operators currently have no clean way to log $8 paper-towel pull |
| 8 | Manager overrides (price, comp, return, refund) | no (defers to V5.4 §15) | no | no (G-028) | no | build new | 2 (Phase 2 multi-op) | yes — `anvil_tablet_count`/staff size | Solo operator today; multi-op makes it mandatory |
| 9 | Lost / found items | no | no | no (G-034) | no | build new | 1.5 | no | Bathhouse priority — phones/jewelry/keys; liability protection |
| 10 | Staff sales / employee discount | no | no | partial — Pricing Rule by Customer Group | no | tweak ERPNext | 2 | yes — `anvil_membership_enabled` cluster | Employee Customer Group + Pricing Rule covers it |
| 11 | Membership lifecycle (signup/renewal/cancel/refund) | no — Hamilton defers (§14) | no | partial — Subscription DocType; not POS-integrated (G-025) | no | build new | 2 (DC-priority) | yes — `anvil_membership_enabled` (DC ON, others OFF) | DC launch blocker; Hamilton can ignore until DC ramps |
| 12 | Inventory / receiving | partial (POS uses standard Stock) | no | yes — Purchase Receipt | no | already-handled | 1 | no | Standard ERPNext Purchase Receipt + Bin works |
| 13 | Daily safe count | no | no | no | no | build new | 1.5 | no | Safe-count separate from drop reconciliation; needed for shrinkage detection |
| 14 | Bank deposit reconciliation | no | no | partial — Bank Reconciliation tool, no auto-pairing | The-Commit-Company/mint (mentioned in Phase A) | tweak + extend | 2 | yes — `anvil_currency` per venue | Standard Bank Reconciliation is manual; mint app helps |
| 15 | Sales tax remittance — multi-jurisdiction | partial (§6.2 = Ontario HST only) | no | partial — Sales Taxes Template per company (G-035) | no | tweak ERPNext + extend | 2 (per venue rollout) | yes — `anvil_tax_mode` (HST/PA-tiered/DC-tiered/TX) | Per-venue Company entity + tax template pattern |
| 16 | Payroll integration (tips paid from till) | no | no | no — payroll separate, tip flow not specced (G-027) | no | build new | **1-BLOCKER** | yes — `anvil_currency`+`anvil_tax_mode` (rounding rule) | Tip-from-till creates phantom variance; needed for blind-cash truth |
| 17 | Promotions / pricing tiers (happy hour, member, time-of-day) | partial (§6.3 names Pricing Rules) | no | yes — Pricing Rule (with G-006 expiry bug, G-009 customer-switch bug) | POS-Awesome (G-009) | tweak ERPNext | 2 | yes — `anvil_membership_enabled` | Pricing Rule + day/time validity is native; member-rate switch is the gap |
| 18 | POS closing — change-amount overcounting | no | no (uses `submit_retail_sale` cart) | partial — bug exists (G-001) | no | already-handled | 1 | no | Hamilton's `submit_retail_sale` posts grand_total via SI, not POS Closing Entry — bypasses bug |
| 19 | Stock validation deferred to POS Closing | no | no | partial — bug exists (G-002, R-010) | no | already-handled | 1 | no | Hamilton stock decrements at SI submit (immediate, not deferred) — bypasses bug |
| 20 | 100% discount / zero-value invoices (comps) | no (assumes $0 admission item works) | partial (Comp Admission Log) | partial — bug exists (G-003) | no | tweak ERPNext | **1-BLOCKER (verify only)** | no | Hamilton uses zero-priced comp item — must verify it submits cleanly on current v16 build before go-live |
| 21 | No native card-terminal integration | yes (defers to "standalone terminal") | no | no (G-004) | aisenyi/stripe_terminal (G-004) | build new | 2 | yes — `anvil_currency` (Fiserv vs USD-side) | Phase 2 Fiserv/Clover Connect work |
| 22 | New-customer-from-POS consolidation gap | no | no (Hamilton uses single walk-in) | partial — bug exists (G-005) | no | already-handled | 1 | yes — `anvil_membership_enabled` (DC creates real customers) | Hamilton uses fixed walk-in; DC will hit it |
| 23 | Expired pricing rules continue applying | no | no | partial — bug fixed in PR #50667 (G-006); requires version pin | no | tweak ERPNext (verify version) | 1.5 | no | Verify Hamilton's tagged v16 includes PR #50667 |
| 24 | Tax-inclusive double rounding (HST) | no (uses tax-inclusive prices) | no | partial — bug closed "working as expected" (G-007) | no | tweak ERPNext (test) | 1.5 | yes — `anvil_tax_mode` | Hamilton volumes are sub-cent per txn; track HST remittance variance |
| 25 | Offline mode data loss | no (defers offline software) | no | partial — historic bug (G-008) | bailabs/tailpos (G-008) | already-handled | 1 | no | Hamilton has dual-WAN hardware; offline software deferred per §14 |
| 26 | Per-customer price-list switching at POS | no | no | partial — bug exists (G-009) | POS-Awesome | tweak + extend | 2 (DC) | yes — `anvil_membership_enabled` | Member rate auto-application at DC needs custom hook |
| 27 | POS Closing misses invoice at exact close timestamp | no | no | partial — open bug (G-010) | no | already-handled | 1 | no | Hamilton bypasses POS Closing in `submit_retail_sale` flow |
| 28 | Compound tax (PA prepared-food, DC alcohol) charge-type bug | no (Hamilton is single-rate HST) | no | partial — bug exists (G-011) | no | tweak ERPNext | 2 (PA/DC) | yes — `anvil_tax_mode` | Use "On Net Total" charge type; avoid row-references |
| 29 | Multi-company POS cross-account default fetch | no | no | partial — bug exists (G-012) | no | tweak ERPNext | 2 (per venue) | yes — `anvil_currency` | Configure each Company's defaults explicitly per `venue_rollout_playbook.md` Phase 0 |
| 30 | Receipt reprint fraud control | no | no | no (G-014) | no | extend custom | 1.5 | no | Add reprint-count + reprint-audit-log to receipt print path |
| 31 | Coupon code self-referential bug (v16.12.0) | no (no coupon campaigns) | no | partial — bug exists (G-016) | esafwan/erpnext_pos_coupon (G-016) | already-handled | 1 (no coupons today) | yes — `anvil_membership_enabled` (member-coupons) | Verify on first coupon launch; not relevant to Hamilton today |
| 32 | Receipt printer variable-length / thermal handling | partial (§7.8 names label printer; receipt printer in §12) | partial (Hamilton Settings has label printer fields only) | no — fixed-page PDF (G-022) | no | extend custom | **1-BLOCKER** | no | Receipt-printer integration design exists in research notes; not yet implementation-coded |
| 33 | Asset locking — multi-tablet double-booking | yes (§5.2) | yes (3-layer lock per DEC-019, see `coding_standards.md` §13) | no (G-032) | no | already-handled | 1 | yes — `anvil_tablet_count` | This is the architectural problem Hamilton solved |
| 34 | Post-close orphaned-invoice integrity check | no | no | no — silent failure (G-023) | no | build new | **1-BLOCKER** | no | Daily integrity scan: `frappe.get_all('POS Invoice', filters={'consolidated_invoice':['is','not set']})` |

---

## Per-process narrative

### 1. Refunds (cash & card) — settlement reconciliation pairing

- **Status today:** §6.7 of the build spec contains a single sentence ("Refunds use the standard POS Return workflow against the original Sales Invoice"). No Hamilton DocType for refund-tracking. No card-side settlement pairing. Partial returns are blocked by ERPNext core (G-020).
- **What's missing:** (a) explicit refund workflow design (single-attempt vs partial vs exchange — G-019/G-020/G-029); (b) card-side settlement reconciliation when Phase 2 card lands (R-009 chargeback ratio defense depends on it); (c) cash refund handling under nickel-rounding rule (G-019: refund must use `grand_total`, not `paid_amount`); (d) refund-reason capture and audit linkage.
- **Recommended close path:** build new — write `refunds_phase2.md` design intent (delivered alongside this audit), then Phase 2 implementation.
- **Phase placement reasoning:** Phase 1-BLOCKER for the cash-refund minimum (operator handles a wrong-room scenario tonight). Card-side settlement waits for Phase 2 card integration. Without a documented refund flow on day 1, the first refund is an ad-hoc Frappe-desk JE that breaks the audit trail.
- **Multi-venue dependency:** yes — `anvil_currency` (CAD nickel-rounding refund vs USD penny refund); `anvil_membership_enabled` (DC membership refund flow differs from anonymous walk-in).
- **Reference:** Phase A G-019, G-020, G-029, G-024; R-010 (deferred-stock bug bites refunds first); DEC-005 (blind cash ↔ refund interaction).

### 2. Comps & discounts (workflow + manager approval)

- **Status today:** Comp Admission Log DocType exists (`hamilton_erp/hamilton_erp/doctype/comp_admission_log/`), with mandatory reason categories (DEC-016) and `comp_value` masked at permlevel 1. Build spec §4.5 covers the data capture but has no manager-approval workflow. Operators self-approve all comps.
- **What's missing:** (a) manager-PIN gate above a threshold (e.g., $0–$50 = operator self-approve, $50+ = manager second-factor); (b) discount-vs-comp distinction at point of sale (a discount on a paying transaction is different from a free admission); (c) for DC, member-comp paths (member's monthly free guest token is a different audit trail than goodwill comp).
- **Recommended close path:** extend custom — Comp Admission Log gains an `approver` field + `approval_method` (auto / manager-pin / manager-override), and a Phase 2 PIN-gate UI. The DocType architecture works; the workflow doesn't.
- **Phase placement reasoning:** Phase 1-BLOCKER for the threshold check (current flow lets operator comp unlimited admissions with no second-factor — significant fraud surface). Phase 2 adds DC member-comp variant.
- **Multi-venue dependency:** yes — `anvil_membership_enabled` (DC member-comp logic); `anvil_tablet_count` (multi-operator venues need delegated approval, single-operator venues can self-approve under threshold).
- **Reference:** Phase A G-003, G-028, G-016 (comp UI bugs); R-006 (`comp_value` permlevel — already mitigated). DEC-016 (reason categories).

### 3. Voids (mid-shift transaction undo)

- **Status today:** No void surface. Operator who needs to undo a just-submitted sale must navigate to Sales Invoice list, cancel + amend — multi-step, low-discoverability, and creates a cancelled-document audit artifact.
- **What's missing:** Single-tap "void last transaction" within shift window, with reason capture and audit log entry distinct from a chargeback or refund. Void should reverse stock, reverse SI, and clean up any session/asset side effects.
- **Recommended close path:** build new — see `voids_phase1.md` design intent.
- **Phase placement reasoning:** Phase 1-BLOCKER. The first time an operator types the wrong room tier ($50 deluxe instead of $30 standard) and needs to undo it before the guest walks in, they will need this. Currently they call Chris.
- **Multi-venue dependency:** no — same flow at all venues.
- **Reference:** Not directly in Phase A (closest: G-013 duplicate-submission; G-014 receipt-reprint). DEC-005 (blind cash means void must reduce expected cash, not stay invisible).

### 4. End-of-shift handover between operators

- **Status today:** §7.5 ends with "Operator logs out." §7.6 covers "incoming operator starts shift" with float verification + board confirmation. No overlap window — current model assumes a single operator at a time.
- **What's missing:** Two-operator overlap workflow for venues with multi-operator shifts (DC peak): outgoing operator's open shift state + active drops + pending reconciliations need to be visible to / handed off cleanly to incoming operator. Includes signed handover document (or digital equivalent).
- **Recommended close path:** extend custom — Shift Record gains `prior_shift` link + `handover_signature` + `handover_notes`; UI surface for "outgoing reviews open items with incoming."
- **Phase placement reasoning:** Phase 1.5 — Hamilton solo today. Phase 2 DC ramp means this becomes mandatory before DC opens.
- **Multi-venue dependency:** yes — `anvil_tablet_count` > 1 implies overlapping shifts.
- **Reference:** Build spec §7.5/§7.6; Phase A doesn't cover handover specifically (ERPNext's POS doesn't have a concept).

### 5. Customer disputes / chargebacks

- **Status today:** No workflow. Phase 1 has zero card transactions (cart is cash-only per `submit_retail_sale` Card-throws-NotImplemented). Phase 2 ships card; chargebacks become real.
- **What's missing:** Chargeback DocType (notification capture, dispute-window timer, response-packet attachment fields, processor-fee tracking, win/lose status, GL-reversal trigger if won).
- **Recommended close path:** build new — Phase 2 alongside card integration.
- **Phase placement reasoning:** Phase 2. Latent until card payments ship. R-009 makes it a soft-blocker for Phase 2 launch — without chargeback tracking, Hamilton can't watch the 0.65% Visa monitored threshold.
- **Multi-venue dependency:** no operationally; yes for processor selection (per DEC-063 different processors = different chargeback portals).
- **Reference:** G-024; R-009 (MATCH list 1% threshold); DEC-064 (primary + backup processor — chargeback may force a backup-flip).

### 6. Daily / weekly closeout & bank deposit

- **Status today:** §7.5 stops at "POS Closing Entry created in background." No Z-report (G-021), no deposit slip, no bank-deposit JE template.
- **What's missing:** Operator-signable end-of-shift Z-report (printed from label printer or thermal); deposit-slip generator pairing envelopes from safe; weekly aggregation report for accountant.
- **Recommended close path:** extend custom — Cash Drop + Cash Reconciliation gain a "shift summary" generator that produces a printed Z-report and deposit slip.
- **Phase placement reasoning:** Phase 1.5. Operators today close shifts informally; first audit will surface this gap. Hamilton's blind-cash story needs a printed audit artifact.
- **Multi-venue dependency:** yes — `anvil_currency` (CAD vs USD deposit slip formats).
- **Reference:** G-021 (X/Z report); DEC-005 (blind cash drop); `cash_reconciliation_phase3.md` (existing design intent).

### 7. Petty cash / supply purchases from drawer

- **Status today:** Nothing. If the cleaning supplier wants $40 cash on Saturday, the operator either skips it (supplier walks) or pulls the cash and it shows up as a reconciliation variance.
- **What's missing:** "Cash Out" voucher type accessible from POS surface — captures purpose, amount, signer, optional receipt photo, GL account (e.g., "Supplies — Petty Cash"). The flow reduces `system_expected_cash` by exactly the voucher amount, just like tip-pull adjustments do.
- **Recommended close path:** build new — Cash Out Voucher DocType; small UI button in POS shell.
- **Phase placement reasoning:** Phase 1.5. Without this, every cash-from-drawer event becomes an unexplained reconciliation variance, eroding the trust model that justifies blind cash.
- **Multi-venue dependency:** no (rare per-venue variation in account mapping but architecture identical).
- **Reference:** G-026 (community-acknowledged ERPNext gap; POS-Awesome has Cash In/Out feature); DEC-005 invariant.

### 8. Manager overrides (price, comp, return, refund)

- **Status today:** Hamilton operator role combines Front + Manager permissions (build spec §8.2). No graduated control — operator can apply 100% discount, refund, void without second-factor. V5.4 §15 manager-override is in the deferred list (§14).
- **What's missing:** Threshold-gated override system (operator self-approve under X, manager PIN at X, district manager remote-approve at Y). Applies to: discounts, comps, refunds, voids, OOS marking on revenue-impacting assets.
- **Recommended close path:** build new — see `manager_override_phase2.md` design intent.
- **Phase placement reasoning:** Phase 2. Hamilton today is solo-operator; operator IS the manager. As DC opens with multi-operator overlapping shifts, manager-override becomes mandatory.
- **Multi-venue dependency:** yes — `anvil_tablet_count` triggers it; `anvil_membership_enabled` (DC member-discount overrides differ).
- **Reference:** G-028; build spec §8 (audit attribution invariant).

### 9. Lost / found items

- **Status today:** Nothing. Manual paper log if any.
- **What's missing:** Lost & Found DocType — found_date, description, location, found-by operator, status (held/claimed/disposed), claim_date, claimed_by, photo attachment, disposal_date+method. Optional link to a Venue Session (if guest known).
- **Recommended close path:** build new — relatively simple DocType, ~half a day of work.
- **Phase placement reasoning:** Phase 1.5. Bathhouse-priority. Without it, the first lost-phone dispute becomes he-said-she-said and creates liability exposure.
- **Multi-venue dependency:** no — same flow everywhere.
- **Reference:** G-034.

### 10. Staff sales / employee discount

- **Status today:** Not specced. Could be configured today via standard ERPNext (Customer Group "Employee" + Pricing Rule with employee-rate price).
- **What's missing:** Convention/setup, not code. Need to designate Customer Group + price rule + audit field on SI for "employee transaction."
- **Recommended close path:** tweak ERPNext — fixture seed adds Employee Customer Group and a default Pricing Rule (configurable per venue).
- **Phase placement reasoning:** Phase 2. Not Phase 1 because Hamilton doesn't have employee transactions today; first new-hire sale will trigger setup.
- **Multi-venue dependency:** yes — couples with `anvil_membership_enabled` cluster (employee-comp paths differ if member discounts also apply).
- **Reference:** Phase A doesn't cover specifically; G-009 (price-list switching) is the implementation-time risk.

### 11. Membership lifecycle (signup, renewal, cancel, refund)

- **Status today:** Hamilton's build spec §14 explicitly defers V5.4 §3-§4 (Identity Rules + Membership). Hamilton anonymous walk-in only.
- **What's missing:** Everything — signup capture, renewal billing (monthly/annual), cancellation, prorated refund, vault-token management, failed-payment dunning. Phase A G-025 confirms ERPNext's Subscription module is not POS-integrated.
- **Recommended close path:** build new — Phase 2 / DC priority. Hybrid approach (Phase A G-025 recommendation): manage recurring billing in Stripe Customer Portal, post Payment Entries back to ERPNext.
- **Phase placement reasoning:** Phase 2 specifically for DC. Hamilton + Philadelphia + Dallas are anonymous — they don't trigger this. DC's membership model is the architectural change.
- **Multi-venue dependency:** yes — `anvil_membership_enabled` is the canonical flag (DC=true, others=false).
- **Reference:** G-025; `venue_rollout_playbook.md` DC-priority section.

### 12. Inventory / receiving

- **Status today:** Standard ERPNext. Bin tracking is live (`submit_retail_sale` validates Bin.actual_qty pre-submit). Purchase Receipt is the receiving doctype.
- **What's missing:** Nothing for Phase 1. SKU expansion in Phase 2 may need a custom "Receiving" UI (currently uses Frappe desk Purchase Receipt form, which is power-user heavy).
- **Recommended close path:** already-handled.
- **Phase placement reasoning:** Phase 1 — already works.
- **Multi-venue dependency:** no.
- **Reference:** `submit_retail_sale` Bin check; ERPNext Purchase Receipt.

### 13. Daily safe count

- **Status today:** Nothing. Cash reconciliation is per-envelope, not per-safe.
- **What's missing:** Safe Count DocType — date, operator/manager, declared count by denomination, expected count (sum of all unreconciled envelopes + float reserves), variance, signature. Frequency configurable per venue (Hamilton daily, low-volume weekly).
- **Recommended close path:** build new — small DocType, big audit-trail value. Catches the case where envelopes are correctly reconciled but the safe is missing one.
- **Phase placement reasoning:** Phase 1.5. Without it, a stolen envelope (after reconciliation but before deposit) creates a silent shrinkage with no detection until the bank deposit clears short.
- **Multi-venue dependency:** no.
- **Reference:** Not directly in Phase A; complements G-001/G-021 (cash reporting gaps).

### 14. Bank deposit reconciliation

- **Status today:** Standard ERPNext Bank Reconciliation tool exists but is manual. The-Commit-Company/mint app (Phase A community-app list) provides automated bank-feed reconciliation.
- **What's missing:** Auto-pairing of deposit slips to bank statement entries; surface unmatched items to manager.
- **Recommended close path:** tweak + extend — install mint or wire a custom hook between Cash Reconciliation submit and a Bank Reconciliation Entry stub.
- **Phase placement reasoning:** Phase 2. Hamilton's volume in Phase 1 is low enough for manual reconciliation; Philadelphia/DC volume will overwhelm manual reconciliation.
- **Multi-venue dependency:** yes — `anvil_currency` (per-venue bank account, per-venue deposit format).
- **Reference:** Phase A community-app list (mint).

### 15. Sales tax remittance — multi-jurisdiction

- **Status today:** §6.2 = Ontario HST 13% only. Build spec hardcodes Hamilton's tax setup.
- **What's missing:** Per-venue tax-template architecture. CLAUDE.md "Hamilton accounting / multi-venue conventions" already documents the approach (per-venue Sales Taxes Template, accept template name via `frappe.conf`). Implementation is not yet executed.
- **Recommended close path:** tweak ERPNext + extend custom — fixtures for PA prepared-food split (G-011 risk: avoid row-references), DC alcohol rate, TX statewide. `frappe.conf.hamilton_tax_template_name` already partly exists; needs per-venue extension.
- **Phase placement reasoning:** Phase 2 (per-venue rollout). Implemented at each venue's Phase 0 setup.
- **Multi-venue dependency:** yes — `anvil_tax_mode` is the canonical flag (HST / PA-tiered / DC-tiered / TX).
- **Reference:** G-035; CLAUDE.md → "One Sales Taxes Template per place-of-supply jurisdiction"; DEC reference: see `decisions_log.md` Amendment 2026-04-30 (Hamilton accounting names locked).

### 16. Payroll integration — tips paid from till

- **Status today:** Nothing. Tips don't currently flow through ERPNext (Hamilton has no tip-paying transactions today). When they start, the till short matches the tip pull but the system reads it as theft.
- **What's missing:** Tip-pull workflow per `cash_reconciliation_phase3.md` §2 (operator types tip, system rounds, system enforces exact cash pull, GL posts as Tips Payable liability not revenue).
- **Recommended close path:** build new — Tip Pull DocType + Cash Drop integration; see `tip_pull_phase2.md` design intent.
- **Phase placement reasoning:** Phase 1-BLOCKER. The day a tip happens, a clean reconciliation goes to "Possible Theft." That contaminates the trust model. Better to ship Hamilton with tip-pull = $0 supported but the schema in place.
- **Multi-venue dependency:** yes — `anvil_currency` (CAD nickel-up rounding vs USD penny); `anvil_tax_mode` (some jurisdictions tax tips differently).
- **Reference:** G-027; `cash_reconciliation_phase3.md` §2; CLAUDE.md "CAD nickel rounding is site-global."

### 17. Promotions / pricing tiers (happy hour, member, time-of-day)

- **Status today:** §6.3 names Pricing Rules. Standard ERPNext Pricing Rule supports day/time validity (DEC-014 establishes Locker Special + Under 25 rules).
- **What's missing:** (a) verify version pin includes G-006 expiry-date fix (PR #50667); (b) member-rate auto-apply when DC member tag scanned (G-009 — current ERPNext doesn't switch price list on customer change); (c) day-after smoke test for new promo launches.
- **Recommended close path:** tweak ERPNext (verify version) + build custom hook for DC member-rate auto-apply.
- **Phase placement reasoning:** Phase 2 (when DC launches and member rates need to apply automatically).
- **Multi-venue dependency:** yes — `anvil_membership_enabled`.
- **Reference:** G-006, G-009; DEC-014.

### 18. POS closing — change-amount overcounting (G-001)

- **Status today:** Hamilton's `submit_retail_sale` posts a Sales Invoice directly with `is_pos=1, update_stock=1`. It does NOT use POS Closing Entry as the per-transaction posting mechanism — POS Closing Entry only consolidates at shift close. The grand_total is what flows; change_amount is calculated per transaction and not summed at close.
- **What's missing:** Verify on a test that the consolidation step (background job at end-of-shift, build spec §7.5 step 5) does not re-trigger G-001's bug. If it does, the workaround is to mirror the cart's grand_total-based pattern in the consolidation hook.
- **Recommended close path:** already-handled (likely). Verify before go-live.
- **Phase placement reasoning:** Phase 1 — needs a test invocation, not new code.
- **Reference:** G-001.

### 19. Stock validation deferred to POS Closing (G-002, R-010)

- **Status today:** Hamilton's `submit_retail_sale` writes Stock Ledger Entry on per-transaction submit (`update_stock=1`), not deferred. Same-shift refunds will hit the bug only if Hamilton routes them through POS Closing consolidation.
- **What's missing:** Phase 2/3 refund flow (process #1) must NOT batch refund-stock to POS Closing. Each refund posts immediately.
- **Recommended close path:** already-handled architecturally. Refund design intent (`refunds_phase2.md`) commits to this pattern.
- **Reference:** G-002, R-010, G-033.

### 20. 100% discount / zero-value invoices (G-003)

- **Status today:** Hamilton's comp flow uses a $0-priced "Comp Admission" item (build spec §6.1). This is the field-tested workaround for G-003.
- **What's missing:** Pre-go-live test — submit a $0 SI on the current v16 build and confirm it doesn't trip the validation bug. The bug is fragile across versions.
- **Recommended close path:** Phase 1-BLOCKER (verify only). Add a test to `test_retail_sales_invoice.py` that submits a comp-priced item and confirms success.
- **Reference:** G-003, G-052002.

### 21. No native card-terminal integration (G-004)

- **Status today:** §6.5 names "Mode of Payment: Card — no integration." `submit_retail_sale` throws NotImplemented when payment_method=Card. DEC-064 commits to primary + backup processor architecture.
- **What's missing:** Phase 2 work. `cash_reconciliation_phase3.md` §5 identifies Hamilton's terminal as Clover Flex C405 (Clover Connect API capable).
- **Recommended close path:** build new — Phase 2 merchant-abstraction adapter.
- **Reference:** G-004; DEC-062, DEC-063, DEC-064; `cash_reconciliation_phase3.md` §5.

### 22. New-customer-from-POS consolidation gap (G-005)

- **Status today:** Hamilton uses single walk-in customer (`hamilton_walkin_customer` from `frappe.conf`). G-005 cannot fire because no new-customer flow exists in Hamilton's cart.
- **What's missing:** When DC adds membership signup at the desk, this gap activates. Test before DC launches.
- **Recommended close path:** already-handled at Hamilton; defer DC-specific test.
- **Reference:** G-005.

### 23. Expired pricing rules continue applying (G-006)

- **Status today:** PR #50667 fixed it; Hamilton's tagged v16 must include the fix.
- **What's missing:** Manual verification — `bench --site SITE doctor` or version check.
- **Recommended close path:** tweak ERPNext (verify only).
- **Reference:** G-006.

### 24. Tax-inclusive double rounding (G-007)

- **Status today:** Hamilton uses HST-inclusive prices (DEC-013). G-007 silently miscounts HST by sub-cent per transaction.
- **What's missing:** Quarterly variance check at HST remittance — actual cash collected vs computed-from-grand_total HST. If material, investigate switching to tax-exclusive pricing or custom rounding.
- **Recommended close path:** tweak ERPNext + monitor.
- **Reference:** G-007; DEC-013.

### 25. Offline mode data loss (G-008)

- **Status today:** Hamilton has dual-WAN router (build spec §12, DEC-XX) and offline software is deferred (§14, V5.4 §11).
- **What's missing:** Operator runbook entry for "Rogers outage — what to do" (cash-only paper, re-enter on restore).
- **Recommended close path:** already-handled (deferred by design); document in `RUNBOOK.md`.
- **Reference:** G-008.

### 26. Per-customer price-list switching at POS (G-009)

- **Status today:** Cart uses single Price List from POS Profile (`pos_profile.selling_price_list`). No customer-driven price-list switching.
- **What's missing:** DC member-rate auto-apply. Either custom hook in cart layer (read member tag, swap price list, refresh tile prices) or migrate to POS Awesome (v15+ supports this natively).
- **Recommended close path:** tweak + extend custom — Phase 2 with DC.
- **Reference:** G-009.

### 27. POS Closing misses invoice at exact close timestamp (G-010)

- **Status today:** Hamilton's submit-direct pattern posts SI immediately. POS Closing Entry consolidation runs at end-of-shift and could in theory miss a same-second invoice.
- **What's missing:** Post-close orphan check — captured in process #34.
- **Recommended close path:** already-handled architecturally; #34 adds the integrity check.
- **Reference:** G-010.

### 28. Compound tax charge-type bug (G-011)

- **Status today:** Hamilton's HST 13% template uses "On Net Total" — single-rate, no row-references. Bug doesn't fire.
- **What's missing:** Philadelphia's PA tiered tax (6% standard + 8% prepared food), DC's tiered alcohol/restaurant rates. Each new template must avoid row-reference charge types.
- **Recommended close path:** tweak ERPNext (per-venue rollout).
- **Reference:** G-011; CLAUDE.md "One Sales Taxes Template per place-of-supply jurisdiction."

### 29. Multi-company POS cross-account default fetch (G-012)

- **Status today:** Hamilton is single-company today. Bug doesn't fire.
- **What's missing:** Each new venue → new Company entity → new POS Profile → explicit account configuration to avoid cross-company default-fetch bug.
- **Recommended close path:** tweak ERPNext (per-venue rollout); add to `venue_rollout_playbook.md` Phase 0 checklist.
- **Reference:** G-012; CLAUDE.md → DEC-064 / `venue_rollout_playbook.md`.

### 30. Receipt reprint fraud control (G-014)

- **Status today:** Standard ERPNext print = unlimited reprints, no count, no audit log.
- **What's missing:** `print_count` field on Sales Invoice; reprint audit log; manager-PIN gate above first reprint.
- **Recommended close path:** extend custom — small custom hook on print action.
- **Phase placement reasoning:** Phase 1.5. Single-operator low-risk today, but adds with multi-op.
- **Reference:** G-014.

### 31. Coupon code self-referential bug (G-016)

- **Status today:** Hamilton has zero coupon campaigns today.
- **What's missing:** Verify before first coupon campaign; fix `depends_on` field metadata if still broken in Hamilton's v16 build.
- **Recommended close path:** already-handled (no current need); verify on first campaign.
- **Reference:** G-016.

### 32. Receipt printer (Epson TM-m30III) integration (G-022)

- **Status today:** Hardware committed (TM-m30III replaces TM-T20III per `cash_reconciliation_phase3.md` cross-references). Software pipeline not built.
- **What's missing:** ePOS-Print API integration or direct ESC/POS bridge; receipt print format that fits one continuous strip (variable-length, no auto-cut multi-page split); PCI-compliant card-receipt template (last-4 only).
- **Recommended close path:** extend custom — Phase 1-BLOCKER for printed receipts on request (build spec §6.6 says "printed on a thermal receipt printer when the guest requests one").
- **Phase placement reasoning:** Phase 1-BLOCKER. Build spec promises a feature ("printed on request") that has no implementation pipeline yet.
- **Reference:** G-022; `docs/research/receipt_printer_evaluation_2026_05.md`.

### 33. Asset locking — multi-tablet double-booking (G-032)

- **Status today:** Hamilton's three-layer lock (Redis + MariaDB FOR UPDATE + optimistic version, DEC-019 / `coding_standards.md` §13) is the reference solution. This is the architectural problem Hamilton solved.
- **What's missing:** Nothing. The architecture is correct.
- **Recommended close path:** already-handled.
- **Reference:** G-032; DEC-019; `coding_standards.md` §13.

### 34. Post-close orphaned-invoice integrity check (G-023)

- **Status today:** No daily integrity check after POS Closing Entry. G-023 is a silent failure mode — `consolidated_invoice` field unset on a POS Invoice means revenue never hit GL but no error surfaced.
- **What's missing:** Daily scheduled job — see `post_close_integrity_phase1.md` design intent.
- **Recommended close path:** build new — small scheduler job + alert.
- **Phase placement reasoning:** Phase 1-BLOCKER. Without it, a single silent failure during a busy night makes that night's revenue invisible to the P&L until manual review (potentially weeks later, when the bank deposit and the SI total disagree).
- **Reference:** G-023.

---

## Top-5 highest-priority gaps

Ranked by selection criteria: (a) Phase 1 launch blocker risk, (b) frequency in Phase A field reports, (c) blast radius if missed.

1. **Refunds (cash & card)** — `refunds_phase2.md` design intent. Build-spec §6.7 has one sentence; G-019/G-020 show ERPNext's refund layer is buggy under several common scenarios; first-refund-night without a documented flow becomes an ad-hoc Frappe-desk JE that breaks audit trail.

2. **Voids (mid-shift undo)** — `voids_phase1.md` design intent. No surface today. Operator typo on payment confirmation = call Chris. Critical operator workflow with zero implementation. Field reports (G-013, G-014) show duplicate-submission and reprint bugs — voids tightly coupled to both.

3. **Manager override (price/comp/return/refund)** — `manager_override_phase2.md` design intent. Solo-operator phase masks the gap. DC opens with multi-operator overlapping shifts — gap activates immediately. G-028 confirms ERPNext has no native graduated-control system.

4. **Tip-pull-from-till (payroll integration)** — `tip_pull_phase2.md` design intent. Tips currently zero; the day a tip happens, blind-cash reconciliation contaminates with phantom theft flag. Hamilton must ship with tip_pull schema in place. G-027 documents the cross-industry pattern.

5. **Post-close orphan-invoice integrity check** — `post_close_integrity_phase1.md` design intent. G-023 is the silent-failure mode that makes a night's revenue vanish without an error. Tiny implementation (one scheduled job + alert), enormous audit value.

---

## Phase 1 launch BLOCKERS

Hamilton cannot ship Phase 1 without closing these. Cross-reference with `docs/risk_register.md` R-006, R-007, R-010.

1. **Refunds (cash side, minimum)** — process #1. Document the cash-refund flow before go-live; card refund is Phase 2 with card integration.
2. **Comps manager-PIN gate** — process #2. Without it, single operator can comp unlimited admissions with no audit defense.
3. **Voids (mid-shift undo)** — process #3. Operator typo workflow.
4. **Tip-pull schema in place** — process #16. Tip pull = $0 day 1, schema must exist so first tip doesn't break reconciliation.
5. **Post-close orphan-invoice integrity check** — process #34. Daily scheduled integrity scan.
6. **100% discount / zero-value comp item — pre-go-live verification test** — process #20. Adds a test, not new code, but verifies the comp flow works on Hamilton's specific v16 build.
7. **Receipt printer (TM-m30III) integration** — process #32. Build spec §6.6 promises printed receipts on request; pipeline not built.

5 design intent docs cover the top 5; #20 (verify-only test) and #32 (already in research) don't need separate design docs but are tracked as launch blockers in this audit.

---

## Cross-references

### DEC entries
- `docs/review_package.md` DEC-001 to DEC-016 (Hamilton early decisions)
- `docs/decisions_log.md` Amendments 2026-04-29 to 2026-05-01 (canonical mockup, retail cart, Canadian rounding, accounting names lock, DEC-062/063/064 merchant architecture)

### Risk register
- R-006 — Comp Admission Log `comp_value` permlevel (PRE-GO-LIVE BLOCKER) — affects process #2
- R-007 — Venue Session PII fields (PRE-GO-LIVE BLOCKER for Philadelphia) — affects process #11
- R-008 — Single-acquirer SPOF — affects process #5
- R-009 — MATCH list 1% threshold — affects process #1, #5
- R-010 — ERPNext v16 polish-wave fix cadence — affects process #1, #19
- R-011, R-012 — newly added today, see `risk_register.md`

### Design docs
- `docs/design/V10_CANONICAL_MOCKUP.html` — asset-board UI canon
- `docs/design/cash_reconciliation_phase3.md` — template + complementary process to #1, #6, #16
- `docs/design/V9.1_RETAIL_AMENDMENT.md` — Phase 2 retail cart spec
- `docs/design/pos_hardware_spec.md` — hardware procurement (label printer, receipt printer, tablet, scanner)

### Phase A gotchas (mapped to Phase B processes)
| Phase A gotcha | Phase B process |
|---|---|
| G-001 change-amount overcount | #18 |
| G-002 deferred stock validation | #19 |
| G-003 100% discount | #20 |
| G-004 card terminal | #21 |
| G-005 new customer field | #22 |
| G-006 expired pricing rules | #23 |
| G-007 tax-inclusive double rounding | #24 |
| G-008 offline mode | #25 |
| G-009 price list switching | #26 |
| G-010 close timestamp off-by-one | #27, #34 |
| G-011 compound tax charge-type | #28 |
| G-012 multi-company default account | #29 |
| G-013 duplicate submissions | #3 |
| G-014 receipt reprint fraud | #30 |
| G-015 fixed-amount discount | #2 |
| G-016 coupon code v16.12.0 | #31 |
| G-017 accounting dimensions | (covered by venue rollout) |
| G-018 write-off / change interaction | #1 |
| G-019 paid_amount vs grand_total refund | #1 |
| G-020 partial return blocked | #1 |
| G-021 X/Z report | #6 |
| G-022 thermal receipt printer | #32 |
| G-023 orphan invoice silent skip | #34 |
| G-024 chargeback workflow | #5 |
| G-025 subscription / membership | #11 |
| G-026 petty cash | #7 |
| G-027 tips paid from till | #16 |
| G-028 manager override | #8 |
| G-029 item exchange | #1 |
| G-030 invoice number gaps | (covered by #34 orphan check) |
| G-031 v16.0.0 cashier dropdown | (already on later v16 patch) |
| G-032 multi-tablet double booking | #33 |
| G-033 allow negative stock | #19 |
| G-034 lost & found | #9 |
| G-035 multi-jurisdiction tax | #15 |

### Multi-venue feature flags

Three flags surfaced as canonical in this audit (consistent with `venue_rollout_playbook.md` and DEC-064):

- **`anvil_membership_enabled`** — DC=true, all others=false. Affects: comps (#2), price-list switching (#26), customer creation (#22), staff sales (#10), member coupons (#31), membership lifecycle (#11).
- **`anvil_currency`** — CAD (Hamilton, Toronto, Ottawa, Montreal) / USD (Philadelphia, DC, Dallas). Affects: refunds (#1), tip rounding (#16), tax mode (#15), bank reconciliation (#14), card integration (#21).
- **`anvil_tax_mode`** — HST / PA-tiered / DC-tiered / TX. Affects: tax remittance (#15), compound tax bugs (#28), tax-inclusive rounding (#24).
- **`anvil_tablet_count`** — 1 (Hamilton today) / 3+ (DC peak). Affects: shift handover (#4), manager override (#8), asset locking (#33 — already handled).

---

## Notes for the implementer

This audit is analysis. None of these processes have been implemented as a result of this audit. The five design intent docs that follow this audit (in `docs/design/`) capture the *why* for the top 5 priorities; they are intent documents, not implementation specs. Phase 1 BLOCKER processes need implementation PRs before the production URL flips.

The audit table is intentionally readable in row order — the first 17 rows are Chris's starter list (renumbered to roll up duplicates with Phase A); rows 18-34 are Phase A surface-ups not in the original 17. Implementation funding should consider the full 34 list, not just the 17.

When in doubt about whether a gap is "tweak" vs "extend" vs "build new":
- **Tweak** = configuration change in existing ERPNext (Pricing Rule, Customer Group, Sales Taxes Template, Mode of Payment, etc.)
- **Extend custom** = Hamilton DocType already exists; add fields and/or controller logic
- **Build new** = no existing DocType; new file under `hamilton_erp/hamilton_erp/doctype/`

The line is fuzzy. Ask Chris if a row-classification matters for funding.
