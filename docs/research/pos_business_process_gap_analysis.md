# POS Business Process Gap Analysis — Complete Report

**Date:** 2026-05-01
**Task:** Taskmaster Task 29 — POS business process gap analysis (research-driven)
**Authored autonomously overnight while Chris slept.** Phase A research by Sonnet (~13 min, 35 gotchas captured); Phase B audit + design intent by Opus (~19 min, 34 processes audited, 5 design intent docs written).
**Status:** ANALYSIS — does not commit any architectural changes; downstream implementation work is queued via the Phase 1 BLOCKER list and per-process design intent docs.

---

## How to read this report

This is a single-file synthesis of seven artifacts. Read top-to-bottom for the complete picture, OR jump to a section using the table of contents below. Each artifact also exists at its canonical path in the repo — those paths are listed in **§5 Canonical file map** at the end.

**Suggested reading order:**
1. **§1 Morning brief** (1 page) — the 5 biggest gaps + Phase 1 launch blocker list. Read this with coffee.
2. **§2 Phase B audit summary** — the 34-process gap table + Phase 1 BLOCKER list.
3. **§3 Phase A research** (the gotchas) — read selectively by category if you want the field-report pain stories.
4. **§4 Design intent docs** — five long docs (~3000 words each) for the top-5 priority gaps. Read when funding implementation work for that gap.
5. **§5 Canonical file map** — pointers back to where each artifact lives in the repo.

---

## Table of contents

- §1 Morning brief
- §2 Phase B audit (gap classification + Phase 1 BLOCKER list)
- §3 Phase A research (35 gotchas from ERPNext community sources)
- §4 Design intent docs for top-5 gaps:
  - §4.1 Refunds (Phase 2, BLOCKER for cash-side at Phase 1)
  - §4.2 Voids (Phase 1 BLOCKER)
  - §4.3 Manager Override (Phase 2)
  - §4.4 Tip Pull from Till (Phase 2, schema BLOCKER at Phase 1)
  - §4.5 Post-Close Integrity Check (Phase 1 BLOCKER)
- §5 Canonical file map
- §6 Cross-references (DECs, risks, related work)

---

## §1 Morning brief

_(Note to Chris: this section is also printed to screen — do not commit — at the end of the autonomous overnight run. It's reproduced here for completeness.)_

### The 5 biggest gaps

1. **Refunds** — Build spec has one sentence. ERPNext's POS refund flow has multiple open bugs (G-019, G-020, G-029 in §3). First refund night without a documented flow corrupts the audit trail. **Classification: build new.** Phase 2 — but cash-side minimum is a Phase 1 BLOCKER.
2. **Voids (mid-shift transaction undo)** — No surface today. Operator typos currently route through Frappe-desk cancel-amend, which is forbidden by Hamilton's permissions matrix. **Classification: build new.** Phase 1 BLOCKER.
3. **Manager Override** — Single shared service consumed by refunds, voids, comps, discounts. Activates the moment DC's multi-operator deployment lights up. **Classification: build new.** Phase 2.
4. **Tip Pull from Till** — Phase 1 schema BLOCKER. The first tip-from-drawer event at Hamilton (operator pulls cash for their card tips) will contaminate the blind-cash reconciliation as phantom theft. **Classification: build new (schema first; full design Phase 2).** Phase 1 BLOCKER for schema.
5. **Post-Close Integrity Check** — Smallest implementation, largest blast radius. G-023 in §3 documents the silent-failure mode where a night's revenue can become invisible to the GL. **Classification: build new.** Phase 1 BLOCKER.

### The single "we wish we'd known" gotcha

**Deferred stock validation explodes at POS Closing when a same-shift return is in the batch** (G-002 in §3). Reported in at least 4 GitHub issues spanning ERPNext v13 → v16, still open. The pattern: teams test in staging without same-shift returns, go live, hit it on day three, enable Allow Negative Stock as a workaround, forget to re-disable it, and two weeks later the stock ledger has sold more than was ever in the warehouse. Hamilton mitigates by NOT processing returns at Phase 1 — the bug is latent until Phase 2 returns ship. Phase 2 design must explicitly route around this OR depend on an upstream fix.

### Phase 1 launch BLOCKER count: 7

Hamilton CANNOT ship Phase 1 without closing these:

1. **Cash-side refunds** (process #1) — Phase 2 full design, but cash-only minimum at Phase 1
2. **Comps manager-PIN gate** (process #2) — current zero-value invoice flow needs PIN attestation
3. **Voids — mid-shift undo** (process #3) — operator typo recovery path
4. **Tip-pull schema present** (process #16) — even if full UI is Phase 2, the schema must exist at Phase 1 so first tip-pull event isn't recorded incorrectly
5. **Post-close orphan-invoice integrity check** (process #34)
6. **Zero-value comp item verification test** (process #20) — verification only, not new code
7. **Receipt printer integration** (process #32) — Epson TM-m30III, see existing research notes

Plus the previously-flagged **R-012 Cash Drop envelope label print pipeline** (Taskmaster Task 30) which is its own BLOCKER from yesterday's risk register update.

### Phase / classification breakdown

- **already-handled:** 6 processes — Hamilton's existing architecture covers these
- **tweak ERPNext:** 7 processes — minor config / Pricing Rule / Custom Field closes the gap
- **extend custom:** 11 processes — Hamilton's custom DocTypes need new fields/methods, but architecture works
- **build new:** 10 processes — new DocType / workflow / integration must be built

### Anything that affects Phase 1 launch (vs Phase 2/3)

**The 7 BLOCKERS above** PLUS R-012 (envelope label pipeline, Task 30 from yesterday). Everything else is deferable. Specifically deferred: full refund workflow, full void workflow, full manager-override service, full tip-pull UX, membership lifecycle (DC-only), card terminal integration (Phase 2+), settlement reconciliation, multi-jurisdiction tax remittance (Philadelphia trigger), payroll integration.

**Multi-venue feature flags surfaced as canonical:** `anvil_membership_enabled` (DC-only), `anvil_currency` (CAD/USD), `anvil_tax_mode` (HST/PA/DC/TX), `anvil_tablet_count` (1 vs 3+). All four flags align with `venue_rollout_playbook.md` and DEC-064.

---

## §2 Phase B audit — Gap classification + Phase 1 BLOCKER list

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

---

## §3 Phase A research — 35 gotchas from ERPNext community sources

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

---

## §4 Design intent docs for top-5 gaps

Each design intent doc below is structured exactly like `docs/design/cash_reconciliation_phase3.md` (PR #108) — design intent, not implementation spec. Captures the WHY behind each decision, not just the rules.

### §4.1 Refunds (Phase 2, cash-side BLOCKER at Phase 1)

# Refunds — Phase 2 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 1-BLOCKER (cash refund minimum) → Phase 2 (card-side settlement pairing)
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #1), informed by Phase A research (G-019, G-020, G-029, G-024) and DEC-005 cash invariants
**Implementation status today:** Build spec §6.7 contains exactly one sentence: "Refunds use the standard POS Return workflow against the original Sales Invoice." No Hamilton custom DocType for refund tracking. No card-side settlement reconciliation. The cart's `submit_retail_sale` has no refund counterpart. Phase A surfaced multiple ERPNext refund bugs (G-019: refund overrefund from `paid_amount`, G-020: partial return blocked, G-029: exchange flow not supported, R-010: deferred-stock close failure).

---

## Why this document exists

A refund is the most operationally fraught transaction in retail. It happens under conditions of customer friction (something went wrong), under time pressure (queue forming), and with potential for fraud (duplicate refund, refund-without-original, refund-after-store-credit). The build spec's single-sentence treatment ("standard POS Return workflow") is not a design — it is a deferral. When Hamilton's first refund happens (a wrong room tier, a malfunctioning locker, a service issue), the operator will improvise. Improvised refunds break the audit trail.

ERPNext's standard POS Return is also not safe out of the box: G-019 demonstrates that returns calculate from `paid_amount` (causing overrefund when the original sale included change), G-020 shows partial returns are blocked entirely, and G-029 confirms exchange flows (return + new sale) require two transactions. Hamilton inherits all three bugs by default.

This document captures the reasoning for Hamilton's refund flow at three levels: (1) the operator workflow during a refund, (2) the system audit trail, (3) the GL and tax remittance correctness. Each layer has a specific failure mode it prevents. Implementers must understand all three before writing code.

If a future implementer thinks "let me just enable POS Return and ship" — re-read §1 and §3. Standard POS Return without the Hamilton wrappers is a refund tool that overrefunds cash, blocks partial scenarios, and silently breaks audit on same-shift returns.

---

## 1. Refund-event taxonomy

Not all "refunds" are the same operation. Conflating them produces a UI that asks the operator to pick the wrong path and a GL that posts to the wrong account.

| Refund type | Trigger | Mechanism | GL behaviour | Audit log |
|---|---|---|---|---|
| **Cancel-before-fulfillment** | Operator typo, customer changes mind in same minute, never assigned an asset | Void (see `voids_phase1.md`) | Reverse SI within same shift | Void log entry; no refund record |
| **Cash refund (post-fulfillment)** | Customer received service, dissatisfied; cash given back from till | Sales Return invoice + cash payout from till | Reverse revenue, debit Cash refund account | Refund record with reason; reduces shift's `system_expected_cash` |
| **Card refund (post-fulfillment)** | Same as cash refund but customer paid by card | Sales Return invoice + terminal-side refund | Reverse revenue, debit AR-refund-pending; settle when processor confirms | Refund record + settlement-pair record |
| **Goodwill credit (no service issue)** | Customer hasn't paid yet but operator wants to give credit | Pricing rule or comp admission | Standard pricing path | Use Comp Admission Log |
| **Chargeback (involuntary refund)** | Processor notifies merchant of dispute filing | Outside the cart; manual JE on dispute notice | Debit revenue, credit AR (or cash if already settled) | Chargeback log (Phase 2 separate DocType) |
| **Exchange (different item)** | Customer wants Item B instead of Item A | Refund A + new sale B (two transactions, one batch) | Net reversal of A + new revenue B | Exchange link between two SIs |

The five-row taxonomy is the design surface — the operator UI presents these as five distinct tap targets, not a single "Refund" button that branches internally on type. Forcing the operator to declare the type up front is the audit-trail discipline.

### Why the taxonomy matters

If the operator treats a cancel-before-fulfillment as a Sales Return, the system creates a refund-credit JE that goes to the wrong account (refund expense vs. void revenue reversal). If they treat a chargeback as a normal refund, the cash account is debited twice (once at chargeback notice, once at the refund-day post). If they treat an exchange as a refund-then-new-sale without linking, audit shows two unrelated transactions and the customer-served history loses the exchange context.

The operator UI must NOT auto-select. The operator must affirmatively pick the type. The five tap targets force that decision.

---

## 2. Cash refund — the Phase 1-BLOCKER minimum

This is the only flow that must ship for Phase 1. Card refund (process #1's card branch) waits for Phase 2 card integration (process #21).

### The decision

A cash refund is a **negative cash drop** for reconciliation purposes. The system reduces `system_expected_cash` by the refund amount; the operator pays the customer from the till; the till runs short by exactly the refund amount; reconciliation reads zero variance.

### Operator flow

1. Operator initiates Refund from cart UI. Picks "Cash refund."
2. Operator scans or enters the original SI (or refund record number — Hamilton uses session-linked refunds, so locker tag can resolve the original SI).
3. System loads the original SI line items. Operator picks line items to refund (full or partial).
4. System computes refund amount = sum of selected lines × HST adjustment. **Critical:** uses `grand_total` of selected lines, NOT `paid_amount` of the original SI (G-019 defense).
5. Operator enters reason from dropdown (Wrong item / Service issue / Operator error / Customer dissatisfaction / Other-with-comment).
6. Manager-PIN gate fires above threshold (Phase 1 default: any refund requires manager PIN; Phase 2 introduces graduated control). See `manager_override_phase2.md` for the gate mechanics.
7. System creates Sales Return (negative SI) linked to original.
8. System computes nickel-adjustment for cash refund (CAD: round refund up or down to nickel per `_should_round_to_nickel`; round-direction: rounding ALWAYS in customer's favor on a refund — round UP — to avoid the appearance of stiffing the customer).
9. System displays "Pay $X.XX from till to customer."
10. Operator obeys, hands cash to customer.
11. System logs refund: original SI, refund SI, line items, amount, reason, operator, timestamp, manager PIN approver (if any), tablet ID, asset (if linked).
12. Refund amount subtracts from shift's `system_expected_cash` so the reconciliation reads zero variance.

### Why round refund in customer's favor

Standard rule: nickel rounding rounds to nearest. On a refund, that means an $11.07 refund pays out $11.05 (customer loses $0.02 vs. exact). Operator-facing optics: "I'm being shorted." Customer-facing optics: "Got back less than I paid."

Hamilton's rule for refunds specifically: round UP. $11.07 refund pays $11.10. The $0.03 difference is venue cost — same operating expense as the tip-rounding loss in `cash_reconciliation_phase3.md` §2 ($44/year per venue at 4 daily shifts × 365). For refunds, expected volume is far lower than tips (most shifts have zero refunds), so the cost is rounding-error level.

DEC reference target: when Phase 2 implementer codes this, formalize as DEC-NNN. Today's intent: refund rounding favors customer, never venue.

### G-019 defense — `grand_total` not `paid_amount`

The bug: ERPNext historically copied `paid_amount` (cash given) into the refund, which inflates refund when the original sale had change. Example: $90 service, customer paid $100, change $10. Refund attempts to give $100 back instead of $90.

Hamilton defense: `submit_retail_sale_refund` (planned function) reads `grand_total` from the original SI line items, not `paid_amount`. The cart's `submit_retail_sale` already posts `grand_total` as the SI line value (no `paid_amount` field manipulation), so the original record has the right number. The refund function must explicitly select `grand_total`.

Test pin: a test invocation creating an original SI with `cash_received > grand_total` (i.e. change paid back), then refunding via the new flow, must verify the refund SI's amount equals the line items' net (= `grand_total`), not the cash collected.

### G-020 defense — partial refunds work

ERPNext's bug throws "Paid amount + Write Off Amount can not be greater than Grand Total" on partial returns. Root cause: validation logic compares absolute values incorrectly for negative invoices.

Hamilton defense options:
- **Option A:** monkey-patch `validate_pos` in our hooks, replicating the proposed (rejected upstream) fix. Risky — the upstream rejection was on "financial perspective" grounds; we should understand the reasoning before patching.
- **Option B:** sidestep — when refunding, generate a full Sales Return for the original SI, then create a new Sales Invoice for the items kept. Two transactions, one operator action behind the scenes.
- **Option C:** wait for upstream fix; until then, Hamilton's partial-refund flow drops to "full refund + re-sell kept items" (operationally identical to Option B but more transparent to operator).

Recommended: Option C with explicit operator UI ("partial refund will appear as a full refund plus a new sale on the audit log"). The operator sees the truth of what's happening. Phase 2 implementer evaluates upstream status before coding.

### Refund as negative cash drop

The reconciliation half is the load-bearing piece. Without it, every refund creates a phantom theft flag.

Implementation: when refund is committed, the active Shift Record's running `system_expected_cash` (computed in `cash_reconciliation_phase3.md` §1's `_calculate_system_expected`) subtracts the refund amount. The operator's till is short by exactly the refund. Reconciliation reads:

- A (POS expected) = sum of cash sales − refunds − tip pulls − petty cash pulls
- B (Operator declared) = what the operator actually has after the refund went out
- C (Manager counted) = same

If A = B = C, reconciliation is Clean even though the till shrank by the refund amount. The refund record is the audit artifact that explains the shrinkage.

---

## 3. Card refund — Phase 2 with card integration

When Phase 2 ships card payments via Clover Connect API integration, card refund pairs with it.

### The decision

A card refund is a **two-stage transaction**: ERPNext-side reversal happens immediately; processor-side reversal happens at the next batch settlement. The system must pair both halves.

### Two-stage pattern

Stage 1 (immediate, at refund time):
1. Operator initiates Refund. Picks "Card refund."
2. System computes refund amount (same `grand_total` defense as cash refund).
3. System creates Sales Return SI in ERPNext.
4. System sends refund command to terminal via Clover Connect API.
5. Terminal returns refund auth code + transaction ID.
6. System captures terminal response into Sales Return SI's payment line (auth_code, txn_id, last_4, brand).
7. SI debits AR-Refund-Pending (asset → liability transition state) instead of cash.
8. Operator gives customer the printed refund slip (matches G-022 thermal printer rule — last 4 only on customer-facing copy).

Stage 2 (delayed, at next batch settlement):
1. Daily processor settlement report imports into ERPNext (Phase 3 settlement reconciliation, see `cash_reconciliation_phase3.md` §5).
2. Reconciliation job pairs Sales Return's `txn_id` with the refund line in the settlement file.
3. When paired, AR-Refund-Pending zeroes; cash account debits by refund amount; settlement-fee account debits by processor fee.
4. Unpaired refunds (issued in ERPNext but not in processor file, or vice versa) surface for manager review.

### Why two-stage

The processor's refund hits the customer's bank in T+2 to T+5 days. Hamilton's bank account doesn't reflect the refund until the next settlement clears. If Hamilton posts to Cash on day 0, the cash account is wrong for several days (overstates cash by the refund amount). AR-Refund-Pending is the staging account that holds the refund obligation until settlement clears.

This is the same pattern as a write-off-receivable — Hamilton owes the customer money but it hasn't yet left Hamilton's bank account.

### Settlement reconciliation as audit layer

When card processing runs for months without full reconciliation, drift accumulates. The pairing job (Phase 3) is the catcher of:
- Refunds processed at terminal but not in ERPNext (operator forgot to use the cart UI; a back-office terminal refund went uncaptured).
- Refunds in ERPNext but processor didn't apply (transmission failure, processor dispute).
- Mistyped amounts (terminal $20 vs ERPNext $200 — caught by txn-id pair amount mismatch).

This is the same architectural pattern as `cash_reconciliation_phase3.md` §5 — a settlement-side audit that complements the human reconciliation flow.

### Refund vs. void on the card side

If the original sale and refund are in the same batch (same banking day, before settlement closes), the processor often supports VOID instead of REFUND. Void is fee-free; refund incurs a fee. The cart UI can present both options and let the operator pick if the txn date allows. Phase 2 implementation detail; today's intent: prefer void when same-batch.

---

## 4. Refund authorization — manager-PIN gate

### The decision

**Every refund requires manager-PIN approval at Phase 1.** Phase 2 introduces graduated thresholds.

### Why every refund at Phase 1

Hamilton's solo-operator model means the operator IS the manager most of the time. A "manager PIN" in that case is just the operator confirming they intend to issue a refund — but it forces a deliberate action distinct from accidental tap.

In practice: the operator's PIN is the manager PIN for solo shifts. The system records the PIN owner; at Hamilton today, that's the same person, but the audit trail captures it as a separate authorization event. When Hamilton hires a second operator, the PIN gate becomes meaningful (operator can self-issue but logs as "self-authorized" — flagged at variance review).

### Phase 2 graduated thresholds

Once `anvil_tablet_count > 1` triggers manager-override (process #8), the PIN gate becomes:

- $0 – threshold A: operator self-approves (logged as self-authorized; manager reviews at end of shift)
- threshold A – threshold B: manager-PIN at terminal (manager physically present)
- > threshold B: district manager remote-approve (out-of-band SMS or admin-PIN)

Threshold values are venue-configurable per `Reconciliation Profile` (see `cash_reconciliation_phase3.md` §3). Hamilton's defaults (when DC opens): A = $50, B = $200.

### Manager-PIN UI

See `manager_override_phase2.md` for the full PIN dialog mechanics. Refund flow plugs into that as one consumer of the override service.

---

## 5. Hamilton-specific edge cases

### Comp admission refund

If a customer received a comp admission and then asks for a refund, there's nothing to refund (they paid $0). But the audit trail still needs an entry:
- Comp Admission Log retains its record (the comp happened).
- A "Comp Refund" record (subtype of refund) captures the policy decision.
- No GL impact (revenue was $0).
- Audit log shows the comp was reverted, with reason.

### Refund of a tip-pull

If a tip was paid from till to operator and the customer disputes, the tip is owed back. Operator can't unilaterally refund a tip from till that's now in their pocket. Flow:
- Manager logs a "Tip Reversal" record.
- Tip Reversal posts: debit Tips Payable (was credited at tip-pull time), credit Cash.
- Operator signs the reversal acknowledging they returned the cash.
- If operator can't / won't return cash, reversal posts as "Tips Receivable" — payroll deducts from next paycheck.

This is a Phase 3 refinement; Phase 1 handles it via manager judgment.

### Refund of a comp + paid-cart transaction

Customer's original purchase: $30 admission + $5 retail (towel). They want a refund of just the towel.

Standard ERPNext partial-refund bug (G-020) blocks this. Hamilton workaround: full Sales Return + new Sales Invoice for retained admission. Two-transaction trail; operator UI shows "this will appear as a full refund + re-sell on the audit log."

### Customer disputes after departure

Customer has left the venue when the dispute surfaces. The original SI is closed; the cash is gone (deposited or in safe). Flow:
- Manager creates a "Post-departure refund" record.
- If cash refund: cut a check from venue accounts (handled outside cart).
- If card refund: process refund via terminal's "refund without card" mode (uses last-4 + auth code stored on original SI).
- Audit log captures the missed-departure context (so operator-shift reconciliation isn't confused).

---

## 6. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Refund-reason dropdown content | TBD | Chris + ops manager | Probable: Wrong item / Service issue / Operator error / Customer dissatisfaction / Comp reversal / Post-departure / Other |
| Manager-PIN UX (Phase 1 single-operator) | TBD | Phase 1 implementer | Operator typing their own PIN is friction; consider a "this is a refund, confirm" tap as the Phase 1 minimum, full PIN at Phase 2 |
| Partial-refund mechanism | Option B/C decision | Phase 2 implementer | Watch upstream G-020 status; choose at implementation time |
| Card-refund settlement-pair window | TBD | Phase 2 implementer | T+2 expected, but processor variance — alert if unpaired > 7 days |
| Receipt format for refund | TBD | Phase 1 implementer | Mirrors sales receipt but with REFUND watermark; PCI compliance (last-4 only on card refund receipts) |
| Comp refund handling | Deferred | Phase 2 implementer | Phase 1 can ship without it (no comps refunded yet) |
| Tip-pull reversal | Deferred | Phase 3 implementer | Pairs with `tip_pull_phase2.md` design |
| DEC formalization for refund-rounding-favors-customer | Deferred | Phase 2 implementer | DEC-NNN when Phase 2 starts |
| Exchange flow (G-029) | Deferred | Phase 2 retail expansion | Phase 1 has no retail products beyond Hamilton's 4 SKUs; exchanges aren't real yet |

---

## 7. Browser test plan (Phase 1 minimum + Phase 2 extension)

Phase 1 minimum (cash refund + manager PIN + reconciliation integration):

1. **Happy-path cash refund.** Operator processes $30 cash sale. Then refunds it. Manager PIN entered. Reconciliation at end-of-shift reads zero variance.
2. **Refund of original with change.** Operator processes $30 sale, customer pays $40 cash, $10 change. Then refund. Refund amount = $30 (not $40 — G-019 defense).
3. **Partial refund full-then-resell pattern.** Customer bought $30 admission + $5 towel. Refunds towel only. System creates full Sales Return + new SI for admission. Audit log shows both linked to the original transaction.
4. **Refund without manager PIN fails.** Attempt refund without PIN. System throws: "Manager approval required."
5. **Refund subtracts from `system_expected_cash`.** Mid-shift refund. End-of-shift reconciliation: sum of cash sales − refund = expected cash. Manager count matches. Variance flag = Clean.
6. **Refund reason mandatory.** Attempt refund without selecting a reason. System throws: "Refund reason is required."
7. **Refund of nickel-rounded sale rounds in customer's favor.** Original sale grand_total = $11.07, customer paid $11.05 (rounded down at sale per Canadian rule). Refund = $11.10 (rounded up — customer's favor).
8. **Refund audit log captures all metadata.** After refund, query refund record. Verify: original SI, refund SI, line items refunded, refund amount, reason, operator, manager PIN signer, timestamp, tablet ID.
9. **Multi-line partial refund.** Original SI has 3 lines (room + locker + towel). Refund only the locker. Verify: refund SI has 1 line; original is otherwise untouched; cash adjustment matches one line's grand_total.

Phase 2 extension (card refund, settlement pairing):

10. **Happy-path card refund.** Original card sale via terminal. Refund issued via cart. Terminal returns auth code + txn id. Sales Return SI captures all four fields.
11. **Card refund pairs at next settlement.** Settlement file imports next day. Refund txn id matches Sales Return. AR-Refund-Pending zeroes; Cash debits.
12. **Unpaired refund alerts.** Refund issued in ERPNext, settlement file does NOT contain matching txn id within 7 days. Alert fires to manager.
13. **Same-batch void preferred over refund.** Refund initiated within same batch as original. System offers Void option (fee-free); operator picks Void; processor processes Void instead of Refund.
14. **Cross-day card refund.** Original sale 2 days prior. Refund issued; processor processes as Refund (not Void). Settlement pairing works across the 2-day gap.

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Refund must integrate with blind reconciliation.
- **DEC-013** — HST-inclusive pricing (`docs/review_package.md` line 118). Refund HST handling inherits this.
- **DEC-038** — Card reconciliation parallels cash reconciliation (`docs/field_masking_audit.md` line 188). Refund settlement pairing extends this.
- **DEC-046** — Hamilton Settings field set (`docs/gap_analysis.md` lines 109-112). Phase 2 adds refund-related configuration.
- **DEC-064** — Per-venue primary + backup processor (`docs/decisions_log.md` Amendment 2026-05-01). Refund must work with the active processor; failover may need re-routing.

### Phase A research
- **G-019** — POS return calculates refund from `paid_amount` instead of `grand_total`. Hamilton defense in §2.
- **G-020** — Partial return blocked. Hamilton workaround in §2.
- **G-029** — Item exchange not supported. Hamilton workaround in §1 (treat as refund + new sale).
- **G-024** — No chargeback workflow. Process #5 in audit; tightly coupled to refunds via reversal mechanics.

### Risk register
- **R-009** — MATCH list 1% chargeback threshold. Card refund mishandling can drive chargeback ratio up.
- **R-010** — ERPNext v16 polish-wave fix cadence; refund-related issues #54183 and #50787 are open. Watch upstream before refund flow ships.

### Existing code
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` is the reference pattern for cart-side transactions. Refund counterpart should mirror its authorization model (delegated capability + Administrator elevation + role gate).
- **`hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.py`** — Cash drop integrates with `system_expected_cash`; refund must subtract from the same field's calculation.
- **`hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py`** — `_calculate_system_expected` (Phase 3 implementation) must subtract refund totals.

### Hardware
- **`docs/design/pos_hardware_spec.md`** — receipt printer integration (TM-m30III) needed for refund receipts.
- **`docs/research/receipt_printer_evaluation_2026_05.md`** — TM-m30III replaces TM-T20III for receipt printing.

### Other design intent docs
- **`docs/design/cash_reconciliation_phase3.md`** §1 (`system_expected` calculator must subtract refunds), §2 (tip-pull adjustment is the same pattern as refund adjustment), §5 (settlement reconciliation pairs cash and card sides).
- **`docs/design/voids_phase1.md`** — voids are the cancel-before-fulfillment branch of §1's taxonomy; refund and void are sibling flows.
- **`docs/design/manager_override_phase2.md`** — refund's PIN gate is a consumer of the override service.
- **`docs/design/tip_pull_phase2.md`** — refund of tip is handled in §5 of this doc.

### Build spec
- `docs/hamilton_erp_build_specification.md` §6.7 — current single-sentence treatment that this document supersedes.

---

## Notes for the Phase 1 implementer (cash refund minimum)

1. Read this document twice. Then read `cash_reconciliation_phase3.md` (specifically §1 — the blind-drop philosophy that refunds plug into).
2. Implement the cash refund flow in `hamilton_erp/api.py` as `submit_retail_refund` mirroring `submit_retail_sale`'s authorization model.
3. The refund must reduce the active shift's `system_expected_cash` calculation. Work backwards from `cash_reconciliation_phase3.md` §1 — your refund function adds a row to the same audit chain that `submit_retail_sale` creates. Reconciliation reads both.
4. Manager-PIN gate: Phase 1 minimum is a confirmation tap ("Confirm refund: cash will leave till"). Full PIN typing waits for Phase 2 graduated control.
5. Partial-refund: ship Option C (full-refund-plus-resell). Document the operator-facing message clearly.
6. Round refunds in customer's favor. Add a regression test that a $11.07 refund pays out $11.10 in CAD.
7. Print a refund receipt (REFUND watermark) — only if receipt printer pipeline (process #32) has shipped first. If not yet, refund record is the audit artifact; receipt is a Phase 1.5 add.
8. Add tests covering the 9 Phase 1 browser scenarios above. Card refund tests (10–14) wait for Phase 2.

## Notes for the Phase 2 implementer (card-side)

1. Card refund pairs with merchant-abstraction adapter (process #21). Don't ship card refund without the adapter.
2. The two-stage pattern (immediate ERPNext-side, delayed processor-side) requires careful state machine: Sales Return SI exists in `Submitted` status; AR-Refund-Pending is the holding account; settlement pairing transitions the SI's `payment_status` from "pending settlement" to "settled."
3. Settlement file format is per-processor (Fiserv has its CSV; Adyen/Stripe have different schemas). Build the parser per primary processor first; backup processor is Phase 3 add (DEC-064).
4. Build the unpaired-refund alert as a scheduled job (daily after settlement-file import). Surface in the manager dashboard.
5. The same-batch void preference (§3) requires knowing the processor's batch close time. Make it configurable per `Processor Profile` DocType (Phase 2 add).

---

### §4.2 Voids (Phase 1 BLOCKER)

# Voids — Phase 1 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 1-BLOCKER
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #3), informed by Phase A research (G-013 duplicate submissions, G-014 receipt reprint), and the operational reality that operators make typos
**Implementation status today:** No void surface exists. Operator who needs to undo a just-submitted Sales Invoice must navigate the Frappe desk → Sales Invoice list → click the SI → Cancel → Amend. Multi-step, low-discoverability under busy-shift conditions, and the cart UI has no link to the post-cancellation state.

---

## Why this document exists

A void is the operator workflow for "I made a mistake, undo that last transaction." It is distinct from a refund — a refund happens after fulfillment (the customer received service and now wants money back); a void happens before fulfillment (the operator typed the wrong room tier, the customer changed their mind in the same minute, the card declined and they want to switch to cash, etc.).

The build spec does not address voids. Operators today, when they make a typo, either (a) call Chris, or (b) attempt a Frappe-desk cancel-amend cycle that they may execute incorrectly. Both paths violate the "operators don't access Frappe desk" hard rule from `docs/permissions_matrix.md`.

This document captures the reasoning for a Phase-1 void surface. The design choices are deliberate and non-obvious: voids are time-boxed, voids are reason-required, voids are reconciliation-aware, and voids are NOT a generic "delete that transaction" tool. Each design choice has a specific failure mode it prevents.

If a future implementer thinks "let me just expose the cancel button to operators" — re-read §2. Cancel-without-the-Hamilton-wrappers is the path to fraudulent stock manipulation, blind-cash bypass, and audit-trail collapse.

---

## 1. Void definition and scope

### The decision

A **void** is the reversal of a Sales Invoice that has been submitted but **not yet fulfilled** (no asset assignment, no service rendered). Voids are operator-initiated, time-boxed (within current shift only), reason-required, manager-PIN-gated above a threshold, and produce a complete audit artifact.

### What a void IS

- An undo of a just-submitted SI (typically within minutes).
- A correction surface for typos at the cart (wrong tier, wrong item, wrong quantity).
- A pre-fulfillment reversal (no asset assigned yet, no key handed over).
- A clean reconciliation event — the till did not change because cash was never collected (or was given back immediately at the operator's discretion).

### What a void is NOT

- A refund (customer received service; see `refunds_phase2.md`).
- A cancellation of an asset assignment (use the cart's "release asset" or operator-vacate flow).
- A way to delete an inconvenient transaction record (the SI is cancelled, not deleted; audit trail persists).
- A way to undo a comp admission (use the Comp Admission Log reversal path; comps are pre-zero-priced, the void mechanism doesn't apply).
- A multi-shift undo (voids are time-boxed to current shift; cross-shift reversals go through manager investigation, not a tap).

### Boundary cases

| Scenario | Tool to use |
|---|---|
| Operator typed Standard Room when guest wanted Deluxe; guest still at desk; not paid | Void original sale, ring up corrected sale |
| Same as above but guest already paid | Void original sale (refund occurs as part of void since cash was collected); ring up corrected sale |
| Guest paid, walked to room, came back saying wrong room | Refund (post-fulfillment) — see `refunds_phase2.md` |
| Operator hit submit twice, two SIs created (G-013) | Void the duplicate (the second one) |
| Operator wants to "undo" a comp admission they regret | Comp Admission Log reversal (separate flow); not a void |
| Card declined, retry succeeded — first attempt SI exists in failed state | If SI was actually created, void it; if SI was never submitted, no action needed |
| Operator made an error 3 hours ago | NOT a void — escalate to manager; audit trail requires investigation |

The boundary cases matter because they shape the UI. Void should be a single, time-boxed action targeting "the most recent submission this shift." Anything outside that window is a refund or a manager-investigated reversal.

---

## 2. Time-boxing — why voids are shift-bound

### The decision

**A void can only target SIs created in the current shift, by the current operator.** Older SIs are out of scope for voids; they must use refund or manager investigation.

### Why time-bound

Three reasons:

1. **Reconciliation invariant.** The blind cash drop closes a shift's books. Voiding a transaction from a closed shift retroactively changes the `system_expected_cash` for that closed shift — its reconciliation is now wrong but already submitted. The math no longer balances. Hamilton's blind-cash trust model requires shift books to be immutable post-close.

2. **Audit trail credibility.** A void at submission-minute is a typo correction; everyone understands it. A void of yesterday's transaction is a money-management decision. The first is operator workflow; the second is forensic accounting. Treating them as the same operation conflates the audit trail.

3. **Fraud surface.** Without time-bounding, an operator could review yesterday's takings and selectively void transactions that match cash they want to skim. The day-after void is exactly the skim path that blind cash control is designed to prevent.

### Operator-bound

Same logic at the operator dimension: only the operator who created the SI can void it within their shift. A second operator coming on shift cannot void the prior operator's transactions. Cross-operator reversals are manager-investigated.

Exception: if the prior operator's shift is still open (multi-operator overlap at DC), the manager can authorize the second operator to void on the first operator's behalf via manager-PIN. Phase 2 add.

---

## 3. Void mechanics

### Operator flow

1. Operator notices error within seconds-to-minutes of submission. Taps "Void Last Transaction" in cart UI.
2. UI displays the most recent SI for this operator's current shift, with summary (item lines, total, payment method, time submitted).
3. Operator confirms this is the SI to void.
4. UI prompts for reason from dropdown (Wrong tier / Wrong item / Wrong quantity / Customer changed mind / Duplicate submission / Card declined retry / Other-with-comment).
5. Manager-PIN gate fires above threshold (Phase 1: any void requires a confirmation tap, full PIN comes Phase 2).
6. System creates Sales Return SI for the full original (full reversal, not partial — voids are atomic). `is_pos=1`, `update_stock=1` so stock is reversed.
7. If original was Cash payment: `system_expected_cash` is reduced by the original amount (the cash that was collected is being given back now).
8. If original was Card payment: terminal-side void issued via Clover Connect API (Phase 2). Phase 1 has no Card flow, so this branch is unreachable.
9. Operator returns cash to customer (if cash) or asks customer to wait for terminal void confirmation (if card).
10. Original SI's `cancelled` field is set; void record links original SI to reversal SI; audit log captures all metadata.
11. UI returns to empty cart state. Operator can re-enter the corrected transaction.

### Why a Sales Return SI, not a delete

Frappe convention: submitted documents are immutable. Cancellation creates a new Cancellation record; deletion is forbidden post-submit. A void uses the standard mechanism (Sales Return SI) so:
- Audit trail persists (original SI + reversal SI both visible).
- GL posts cleanly (revenue reversed, stock reversed, cash reversed).
- Standard ERPNext reporting still aggregates correctly (totals net out).

Hamilton is NOT using the literal `cancel()` method on the Sales Invoice — that would attempt to roll back the document but leave Hamilton's session/asset side effects in an inconsistent state. The reversal path always uses a paired Sales Return SI.

### Side-effect cleanup

If the original SI had triggered any side effects (asset assignment, session creation), they must be cleaned up too:

- **Asset assigned?** Release it back to Available. Asset Status Log captures the release with reason "Voided sale."
- **Session created?** Mark the session as Cancelled (new session status, distinct from Active/Completed). Session record is preserved for audit.
- **Comp Admission Log entry?** This case shouldn't happen — comps go through Comp Admission Log workflow, not the standard cart. If somehow the void is on a comp transaction, escalate to manager.
- **Stock decrement?** Reversed via the Sales Return SI's `update_stock=1`.
- **Tip pull?** Voided tip is owed back to operator — reverse the Tip Pull record (Phase 3 add; Phase 1 has no tips).

### Atomicity

The void must be all-or-nothing. If any side-effect cleanup fails, the entire void rolls back. This requires:
- Server-side transaction wrapping the SI reversal + asset release + session update.
- Three-layer locking (Redis + MariaDB + version field, per `coding_standards.md` §13) on the asset being released.
- Test harness that simulates partial-failure scenarios and verifies rollback.

### Race condition: void during second operator's check-in

Edge case: operator A submits a sale at time T. Operator B (multi-tablet venue) starts a check-in for the same asset at time T+0.5s. Operator A initiates void at T+1s, intending to release the asset.

Without locking: B's check-in might commit against the original SI's asset state; A's void might commit afterward, releasing the asset that B just assigned. Result: asset shows Available but B has a guest in it.

With three-layer locking: A's void acquires the asset lock first (or waits); B's check-in sees the asset as either already-occupied-by-A (cannot proceed) or release-pending (must wait). The lock ordering serializes the two operations.

This is the same lock pattern that protects asset assignment (DEC-019). Voids inherit the protection by using the same lock helper.

---

## 4. Manager-PIN gate — Phase 1 minimum vs Phase 2 graduated

### Phase 1 minimum

**Every void requires a confirmation tap.** The tap is not a PIN — it's a deliberate action distinct from accidental swipe. The audit log captures the operator who tapped (always = operator who is making the void request, since voids are operator-bound).

Why not full PIN at Phase 1: Hamilton's solo-operator model means the operator IS the manager. A PIN is meaningless when there's only one person on shift. The confirmation tap is the deliberate-action floor.

### Phase 2 graduated

When `anvil_tablet_count > 1` triggers manager-override (process #8), voids gain graduated control:
- $0 – $X: operator self-confirm tap (logs as "self-authorized")
- $X – $Y: manager-PIN at terminal (manager must be physically present at venue)
- > $Y: district-manager remote-approve

Threshold defaults: X = $0 (any void above $0 needs manager when multi-op), Y = $200. Venue-configurable.

### PIN-bypass loophole

A subtle attack: operator processes a sale, immediately voids it before manager arrives, repeats with valid customer transactions in between. Each void requires a tap; none requires manager presence (Phase 1). At end of shift, operator pockets cash from voided transactions; SIs net to zero in GL; no variance shows in reconciliation.

Defense: void rate metric. Manager dashboard surfaces operators with > N voids per shift, where N is a venue-configurable threshold (default 3). High void counts trigger manager review even without per-transaction PIN.

This is not perfect — a careful operator can stay under the threshold — but it raises the cost of the attack and creates an audit signal.

---

## 5. Reconciliation integration

### Cash voids reduce `system_expected_cash`

Same mechanism as refunds (`refunds_phase2.md` §2). When void is committed:
- `system_expected_cash` for active shift reduces by the original SI's grand_total.
- Operator either has cash short by that amount (because they gave it back to customer) or gives the cash back at end-of-shift if customer didn't take it back yet (rare).
- Reconciliation reads expected = sales − refunds − voids − tip pulls − petty cash; if matches, Clean.

### Card voids — Phase 2 only

Same mechanism as card refunds. Two-stage:
- Stage 1: terminal-side void via Clover Connect API; ERPNext SI marked Reversed; AR-Refund-Pending debited.
- Stage 2: settlement pairing reconciles the void against processor's batch.

### Void of a void — explicitly forbidden

If an operator initiates a void, then realizes the void was a mistake, they cannot "void the void." The corrected flow:
- Re-ring up the original transaction normally.
- Both the void and the re-ring-up appear in the audit log.
- Reconciliation nets out (void reduced expected, re-ring increased it).

Reason: allowing void-of-void creates a UI escalation tree (void, void-the-void, void-the-void-of-void...) that is meaningless. The simpler model is one void per original SI; corrections happen by re-creating the transaction.

---

## 6. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Reason dropdown content | TBD | Chris + ops manager input | Probable: Wrong tier, Wrong item, Wrong quantity, Customer changed mind, Duplicate submission, Card declined retry, Other-with-comment |
| Time-bound window definition | "Current shift" — TBD precise | Phase 1 implementer | Most likely: SI created within last shift_start to now |
| High-void-rate threshold | Default 3, venue-configurable | Phase 2 implementer | Surface in manager dashboard |
| Card void via Clover Connect API | Deferred to Phase 2 | Phase 2 card implementer | Needs merchant adapter |
| Void of multi-line SI | Atomic only at Phase 1 | Phase 2 may add line-level | Phase 1: full SI void only |
| Void receipt format | Receipt printer integration first | Phase 1.5 implementer | Reuse refund receipt template (REVERSED watermark) |
| Multi-operator void authorization | Phase 2 add | Phase 2 implementer | Manager PIN to authorize cross-operator void |
| DEC formalization for void semantics | Deferred | Phase 2 implementer | DEC-NNN |

---

## 7. Browser test plan (Phase 1)

1. **Happy-path void within seconds.** Operator processes $30 cash sale. 5 seconds later, voids it. Reason "Wrong tier." Sales Return SI created. Cash flow: original collected $30, void reduces expected by $30, net zero. Original SI marked cancelled.
2. **Void releases assigned asset.** Operator processes admission for Room 7. Void initiated. Verify Room 7 returns to Available. Asset Status Log entry with reason "Voided sale."
3. **Void cancels Venue Session.** Same as above. Verify session for Room 7 marked Cancelled (not Completed).
4. **Void reverses stock.** Operator sells towel ($5 retail). Bin.actual_qty decremented. Void initiated. Bin.actual_qty restored to original value.
5. **Void requires reason.** Attempt void without selecting reason. System throws: "Reason required."
6. **Cross-operator void blocked at Phase 1.** Operator A submits SI. Operator B logs in (after shift handover). B attempts to void A's SI. System throws: "Cannot void another operator's transaction. Escalate to manager."
7. **Cross-shift void blocked.** Operator submits SI in shift 1. Closes shift. Logs back in for shift 2. Attempts to void shift 1's SI. System throws: "Cannot void prior shift's transaction. Use refund."
8. **Void of duplicate submission (G-013 scenario).** Operator's tap registered twice; two identical SIs created in same second. Operator initiates "Void Last Transaction" — UI shows the most recent. Voids it. Original (first) SI remains intact.
9. **Void of voided transaction blocked.** SI voided. Operator attempts to "Void Last Transaction" again — system shows the next-most-recent SI (or empty if no others), not the just-voided one.
10. **Reconciliation reads zero variance after void.** End of shift: 5 sales totaling $150, 1 void of $30, all cash. `system_expected_cash` = $120. Operator declared $120, manager counted $120. Variance = Clean.
11. **High-void-rate alerted (manager dashboard).** Operator initiates 4 voids in one shift (threshold = 3). Dashboard flags operator for manager review. Audit log captures void rate.
12. **Atomic rollback on partial-failure scenario.** Simulate failure at side-effect cleanup (asset release) — verify entire void rolls back; original SI and asset state are unchanged.
13. **Confirmation tap captured in audit.** Void completed. Audit log records: original SI, void SI, reason, operator, confirmation timestamp, tablet ID.

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Voids must integrate with blind reconciliation.
- **DEC-019** — Three-layer locking on asset state changes (`docs/coding_standards.md` §13). Voids inherit the protection on asset release.
- **DEC-016** — Comp Admission reason categories (`docs/review_package.md` line 127). Void reasons follow similar categorization pattern.

### Phase A research
- **G-013** — Duplicate submission under load. Void is the recovery path.
- **G-014** — Receipt reprint fraud. Void receipt format must mark it as REVERSED to prevent confusion with original.
- **G-029** — Item exchange not supported. Void + new sale is one Hamilton workaround for exchange flow.

### Risk register
- **R-010** — ERPNext v16 polish-wave fix cadence. Void-related close failures could surface; design defensively.

### Existing code
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` is the reference for the cart-side transaction model. Void counterpart should mirror authorization model.
- **`hamilton_erp/hamilton_erp/doctype/asset_status_log/`** — existing audit DocType for asset state changes. Void's asset-release fires this same DocType with reason "Voided sale."
- **`hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.py`** — session lifecycle. Void must add a "Cancelled" status path.

### Other design intent docs
- **`docs/design/refunds_phase2.md`** — voids and refunds are sibling flows in §1's taxonomy.
- **`docs/design/manager_override_phase2.md`** — void's PIN gate is a consumer of the override service.
- **`docs/design/cash_reconciliation_phase3.md`** §1 — the `system_expected` calculator must subtract void totals.

### Build spec
- `docs/hamilton_erp_build_specification.md` — voids are not specced; this document fills the gap.

---

## Notes for the Phase 1 implementer

1. Read this document twice. Then read `cash_reconciliation_phase3.md` §1 (the blind-cash invariant that voids plug into) and `coding_standards.md` §13 (the locking pattern).
2. Implement `submit_retail_void` in `hamilton_erp/api.py` mirroring `submit_retail_sale`'s authorization model. Reuse the role gate + Administrator elevation pattern.
3. Time-bound the query: `frappe.get_all("Sales Invoice", filters={"owner": real_user, "is_pos": 1, "creation": [">=", shift_start]})`. Order by creation desc, take first row, that's the candidate.
4. Side-effect cleanup must be atomic. Wrap in a single transaction. If asset release fails, roll back the SI reversal too.
5. Use the asset locking helper for the asset-release step. Test concurrent void + check-in scenarios.
6. The reason dropdown is a Select field on the Void Log DocType (new — minimal: original_si link, void_si link, reason, reason_note, operator, manager_pin_signer, timestamp, tablet_id).
7. Add a scheduled job: at end-of-shift, count voids per operator. If > venue threshold, log a `Void Rate Alert` for manager review.
8. Implement all 13 browser tests above before merging.
9. Receipt printing for the void event waits for receipt printer pipeline (process #32). Phase 1 minimum: void record is the audit; receipt is Phase 1.5.
10. Do NOT expose the standard Frappe `cancel` button to operators — voids must go through `submit_retail_void` to ensure side-effect cleanup happens.

---

### §4.3 Manager Override (Phase 2)

# Manager Override — Phase 2 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 2 (activates when `anvil_tablet_count > 1` triggers multi-operator)
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #8), informed by Phase A research (G-028 no manager-override workflow), `docs/hamilton_erp_build_specification.md` §8 (combined operator/manager permissions today), and the recurring need from refund / void / comp / discount design intents that all want a graduated control gate
**Implementation status today:** §8.2 of build spec gives Hamilton Operator the same permissions as Hamilton Manager for all operational actions (combined "Front + Manager" role). The Hamilton Manager role exists separately for cash reconciliation only (build spec §7.7). No graduated threshold control. No PIN dialog. No second-factor authorization. V5.4 §15 (manager overrides and pattern detection) is in the deferred list (build spec §14).

---

## Why this document exists

Manager override is the cross-cutting concern shared by every "I changed my mind / something needs special approval" flow: refunds (`refunds_phase2.md`), voids (`voids_phase1.md`), comps (Comp Admission Log workflow), discounts, OOS marking on revenue-impacting assets, price overrides, after-hours access, etc. Building a separate authorization gate for each flow would result in inconsistent UX, duplicate code, and gaps where one flow forgets to enforce a check.

Hamilton's solo-operator phase (today) doesn't need this. The operator is the manager. There's nobody to defer to. But solo-operator is a specific, time-limited configuration, not a forever-architecture. The day Hamilton hires a second operator, every "operator can self-approve unlimited refunds" path is a fraud surface. DC opens with multi-operator overlapping shifts from day 1; manager override is mandatory there.

The document captures the reasoning for a single shared override service that all caller flows consume. Each design choice is non-obvious: thresholds are venue-configurable and per-action, PINs are time-windowed and not stored long-term, audit logs distinguish self-authorized from delegated-authorized events, and the system exposes a manager dashboard for pattern detection that is the structural defense against subtle abuse.

If a future implementer thinks "let me just add a hardcoded $100 threshold to refunds" — re-read §3. Per-action venue-configured thresholds + a single override service is the correct architecture; ad-hoc threshold logic produces a system that drifts and silently fails to enforce.

---

## 1. The override service abstraction

### The decision

A **single shared `override.request(action, amount, context, requested_by)` service** evaluates whether the action is permitted at the requested amount and returns either:
- `auto_approved` (operator self-authorized; logs as "self-authorized")
- `pin_required` (UI prompts for PIN)
- `pin_authorized` (PIN entered, validated; action proceeds, logs as "PIN-authorized")
- `remote_approval_required` (district manager out-of-band)
- `denied` (action exceeds even district approval; structural block)

All caller flows (refund, void, comp, discount, OOS, price override) call this service. None implement their own threshold logic.

### Why one service

Three reasons:

1. **Consistency.** Every caller flow gets the same authorization UX. Operator learns one PIN dialog, not seven different ones. Audit log uses one schema.

2. **Defense against drift.** When thresholds change (venue raises refund threshold from $50 to $100), the change happens in one place. No risk of refund flow updating but void flow staying at the old threshold.

3. **Single-source-of-truth audit.** All authorization events live in one Override Log table. Pattern detection (§5) reads one stream. Manager dashboard renders one feed.

### Service interface (Phase 2 implementation contract)

```python
def request(
    action: str,             # "refund", "void", "comp", "discount", etc.
    amount: float,           # the dollar value being authorized (refund amount, comp value, etc.)
    context: dict,           # caller-flow specific (original_si, asset, customer, etc.)
    requested_by: str,       # frappe.session.user
) -> dict:
    """Returns authorization decision. Caller flow uses decision to proceed or block."""
```

The function reads:
- Venue's Override Profile for the requested action's thresholds.
- Current operator's role and authorization state.
- Recent override history (rate-limit checks, see §5).

It writes (synchronously, before returning) an Override Log record capturing the request. Whether approved or denied, the request is logged. This is the audit invariant.

---

## 2. Three tiers of authorization

### Tier 1 — Self-authorized (operator only)

Operator can authorize an action below threshold A without manager intervention. The system logs the operator as "self-authorized." Audit trail captures the timestamp; no PIN entered.

Use cases: small refunds, low-value comps, minor discount tweaks. The threshold A is venue-configurable and per-action — Hamilton's defaults (when DC opens):

| Action | Threshold A (self) | Threshold B (manager) | Threshold C (district) |
|---|---|---|---|
| Refund | $50 | $200 | $500 |
| Void | $0 (any void = manager) | $200 | $500 |
| Comp | $0 (any comp = manager) | $100 | $500 |
| Discount | 10% | 25% | 50% |
| OOS revenue-impact | n/a | always-manager | always-district above $1000/day |
| Price override | $0 (always-manager) | $50 | n/a |

Hamilton's solo-operator phase: threshold A = effectively-infinite (operator self-approves all). The thresholds activate when `anvil_tablet_count > 1` is set on the venue profile.

### Tier 2 — Manager PIN at terminal

Above threshold A, the operator initiates the action; UI prompts "Manager approval required: enter PIN." A user with Hamilton Manager role (or higher) types their PIN. PIN is validated against `User.password` (using Frappe's password verification). On success, action proceeds; Override Log captures both the requesting operator and the approving manager.

Why "at terminal": the PIN is entered on the same tablet where the operator initiated the action. Manager must be physically present at the venue. Cannot be a phone-based remote approval (that's Tier 3).

### Tier 3 — District manager remote approve

Above threshold B, even on-venue manager cannot approve. UI prompts "District approval required: SMS sent." The district manager (Hamilton Admin role at minimum) receives an SMS with a one-time code, types it back into the manager's phone, manager relays the code to the terminal. The terminal validates the code against the request.

Phase 3 refinement: replace the SMS relay with a direct admin-app push notification + tap-to-approve. SMS is the Phase 2 minimum; the bottleneck is reliable.

### Why graduated thresholds

Three tiers reflect three different fraud profiles:
- **Tier 1 (operator self):** typo fixes and small-customer-service decisions. Volume is high; per-event impact is low. Self-authorization is fine.
- **Tier 2 (manager PIN):** decisions that affect a meaningful chunk of one transaction. Volume is medium; per-event impact is meaningful. Requires a second human at the venue.
- **Tier 3 (district):** decisions that affect a meaningful chunk of a day's revenue. Volume is rare; per-event impact is large. Requires out-of-band authorization to defeat manager + operator collusion.

Without tiering: either everything requires manager (kills throughput; manager is a bottleneck) or everything is self-authorized (fraud surface). Tiering matches authorization friction to event impact.

---

## 3. Per-action thresholds — venue-configurable, NOT hardcoded

### The decision

Threshold values live in an **Override Profile** DocType (one per venue). The service reads the profile at request time. Hardcoded defaults in code are the LAST fallback, never the canonical values.

### Why per-venue

Same reasoning as `cash_reconciliation_phase3.md` §3:
1. Regulatory variation (state/province retail rules).
2. Operational variation (DC peak vs Hamilton low-volume → different threshold appropriateness).
3. Theft-experience adaptation (each venue's thresholds tighten or loosen as patterns emerge).

If thresholds are hardcoded, changing them requires a code deploy. Code deploys mean change is friction-laden; venues drift from optimal thresholds.

### Why per-action (within a venue)

A venue's risk profile differs by action. Hamilton might be lenient on refunds ($50 self-approve — refund-required friction is bad customer experience for legitimate complaints) but strict on comps ($0 self-approve — comp fraud is the structural risk because operator can give themselves a free admission disguised as a goodwill gesture).

A single "all overrides" threshold can't capture this. Per-action thresholds let venues tune each control surface to its own risk profile.

### Override Profile schema

```
Override Profile (Phase 2 DocType, linked per venue)
- venue (link to Company)
- refund_self_threshold (Currency)
- refund_manager_threshold (Currency)
- refund_district_threshold (Currency)
- void_self_threshold (Currency)
- void_manager_threshold (Currency)
- ... (one row per action × tier)
- pin_window_seconds (Int, default 300) — how long after PIN entry can subsequent actions reuse it
- high_rate_alert_threshold (Int, default 5) — overrides per shift before manager dashboard alert
```

When a new venue is provisioned, fixtures seed default thresholds; venue manager tunes via Frappe desk. Phase 2 implementer chooses the exact field set.

---

## 4. PIN mechanics

### PIN lifecycle

- Each user with Hamilton Manager+ role has a PIN. PIN is stored as a hashed value (Frappe's standard password handling). Rotated quarterly per `RUNBOOK.md` security cadence.
- PIN entry happens on the requesting operator's terminal — manager walks over, types PIN, walks away.
- After successful PIN entry, the system marks the override as authorized AND opens a 5-minute "PIN-warm" window for subsequent operations by the same operator that fall under the same threshold tier. After the window, next operation requires fresh PIN.
- PIN-warm window is venue-configurable (`pin_window_seconds`, default 300).

### Why a 5-minute warm window

A bursty refund / void / comp at the same minute (correct multiple errors during a busy moment) shouldn't require manager to type PIN N times. One PIN per "session of authorizations" is the natural rhythm.

But the window must be short. Long windows let an operator pretend to ask for one approval and then process a string of fraudulent reversals. 5 minutes is the rough floor — long enough for a manager to step away, short enough that the manager wouldn't reasonably leave for the duration.

### PIN-bypass loophole

Subtle attack: operator builds rapport with manager, accumulates 5-minute trust windows, processes fraudulent transactions toward end of each window when manager isn't watching closely.

Defense: high-rate-alert. Manager dashboard surfaces operators with > N override events per shift. Investigation is expected when threshold crossed. This is the same pattern as void rate detection in `voids_phase1.md` §4.

### PIN entry on a tablet — physical security

Tablet PIN entry is in plain view of the operator. Manager must shield the keypad with their body or use a numeric pad with randomized digit positions. Phase 2 implementer chooses; default is a randomized PIN pad on each entry (defeats shoulder-surfing).

### District manager remote approve — out-of-band

The SMS round-trip is intentional: even if the operator and manager collude, the district manager is out-of-band. The SMS code arrives on the district manager's phone, not the operator's tablet. The district manager sees the request context (action + amount + venue + operator) before typing the code; they have the option to deny and call.

### District manager bypass loophole

Not all venues will use district manager. Single-venue venues, or first-shift-of-the-month edge cases, may operate without district approval available. Defense: `district_required_threshold = infinity` for those venues; manager-PIN handles all events. The district tier is a Phase 3 add for venues that scale to multi-tier hierarchies.

---

## 5. Pattern detection — manager dashboard

### The decision

The override service writes every authorization event to an Override Log. A scheduled job aggregates the log and surfaces patterns to the manager dashboard. This is the structural defense against subtle abuse.

### What patterns to surface

- **High-rate operator:** > N overrides per shift (default 5).
- **Repeat-target customer:** > M overrides involving the same customer in a week (potential collusion).
- **End-of-shift cluster:** disproportionate overrides in last 30 minutes of shift (cash-skim cleanup pattern).
- **Same-action repeat:** > 3 voids OR > 3 refunds in same hour by same operator.
- **Off-hours overrides:** overrides outside venue's normal manager hours.
- **Threshold-edge clustering:** 80%+ of an operator's overrides hover just below a threshold (gaming the system).

Each pattern produces a "Pattern Alert" record visible to manager + admin. Manager dashboard ranks operators by alert count; drill-down shows specific events.

### Why patterns matter more than per-event PIN

A single fraudulent override can slip past PIN (manager not paying attention, manager-collusion, social engineering). Patterns are statistical — over time, fraud creates signal even if individual events look fine. The audit defense is the long-tail aggregation.

This is the same defensive principle as blind cash drop's three-number triangulation (`cash_reconciliation_phase3.md` §1) — multiple imperfect signals together produce a robust signal.

### False positives

Patterns will sometimes fire on legitimate operator behavior (a busy night with many voids, a regular customer with repeated comps). Manager investigates; if false positive, marks the alert as "reviewed — legitimate" with comment. Audit trail captures the dismissal so a pattern of dismissals (manager hand-waving real fraud) is itself detectable.

---

## 6. Hamilton's solo-operator phase — what to do today

### Today (solo operator)

- Override Profile is provisioned for Hamilton with `*_self_threshold = infinity` (operator self-approves all).
- Override Log is still written for every authorization event.
- Manager dashboard exists but has no Pattern Alerts (nothing to compare against).
- The infrastructure is in place; the gates are open.

### Day Hamilton hires its second operator

- Update Override Profile for Hamilton: tighten thresholds to defaults from §2.
- Hamilton Manager role is now meaningful (the second operator is NOT a manager; current operator IS).
- Manager dashboard activates pattern detection.
- Audit Log retroactively shows "self-authorized" events from the solo-operator era — these are correctly logged but unflagged.

### When DC opens

- DC's Override Profile is provisioned with stricter defaults from day 1 (multi-operator from go-live).
- District manager (Chris) gets SMS access wired up.
- DC manager dashboard active from day 1.

This phasing means the override service ships at Phase 1 (infrastructure), activates at Phase 2 (when multi-operator reality requires it), and scales to district control at Phase 3 (when ANVIL multi-venue chain matures).

---

## 7. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Default threshold values per action | TBD final | Chris + ops manager input | §2 table is starter values |
| PIN-warm window default | 300s, venue-configurable | Phase 2 implementer | Tune based on early multi-op feedback |
| District manager SMS gateway | TBD provider | Phase 3 implementer | Twilio / Vonage / built-in Frappe SMS |
| Pattern detection algorithm details | High-level only | Phase 2 implementer | Specific thresholds for each pattern type |
| Tablet PIN-pad design (randomized vs static) | Default randomized | Phase 2 implementer | Shoulder-surfing defense |
| Override receipt printing | Pairs with receipt printer pipeline | Phase 2 implementer | Override events optionally printed for manager-signed log |
| Cross-venue district approval | Phase 3 | Phase 3 implementer | One district manager covering multiple venues |
| DEC formalization for override service | Deferred | Phase 2 implementer | DEC-NNN |
| Migration plan from solo-operator to multi-operator | Phase 2 implementer | When Hamilton hires #2 | Documented runbook step |

---

## 8. Browser test plan (Phase 2)

1. **Tier 1 self-authorize.** Operator initiates $30 refund. Threshold A = $50. UI shows confirmation tap, no PIN. Action completes. Override Log: type=self-authorized.
2. **Tier 2 manager PIN required.** Operator initiates $100 refund. Threshold A = $50, B = $200. UI shows "Manager approval required" + PIN keypad. Wrong PIN entered → reject. Correct PIN entered → action completes. Override Log: type=PIN-authorized, manager=manager_user, operator=op_user.
3. **PIN-warm window reuse.** After Tier 2 PIN, operator initiates second $80 refund within 5 minutes. UI does NOT re-prompt PIN; reuses warm authorization. Override Log captures the reuse.
4. **PIN-warm window expiry.** Operator initiates $80 refund 6 minutes after first PIN. UI re-prompts PIN.
5. **Tier 3 district approve.** Operator initiates $300 refund. Threshold B = $200, C = $500. UI shows "District approval required" + SMS. Code arrives on district manager phone; entered into terminal. Action completes. Override Log captures district_authorizer.
6. **Above all thresholds — denied.** Operator initiates $1000 refund. Threshold C = $500. UI shows "Action exceeds maximum override; create a manual reversal entry." Action denied.
7. **Per-action threshold differs.** Same operator: $50 refund auto-approves; $50 comp requires manager PIN (different threshold table per action).
8. **Override Log captures all events.** After mixed shift (auto-approves + PIN-approves + denials), query Override Log. Verify: all events present, types distinguishable, requesting operator and authorizing manager (where applicable) all captured.
9. **High-rate alert fires.** Operator processes 6 self-authorized refunds in shift (threshold = 5). Pattern Alert created. Manager dashboard shows alert.
10. **End-of-shift cluster alert.** Operator processes 4 voids in last 20 minutes of shift, 0 in first 90% of shift. Pattern Alert: end-of-shift cluster.
11. **Tablet PIN-pad randomized.** PIN entry triggers pad render. Verify digit positions differ between two consecutive entries.
12. **Cross-operator PIN.** Operator A's terminal prompts for PIN. Operator B (also manager-role) walks over and types B's PIN. Override Log records B as authorizer (not A).
13. **Pattern Alert dismissal logged.** Manager reviews alert; marks "reviewed — legitimate" + comment. Audit log captures dismissal. Operator's alert count resets.
14. **Solo-operator (Hamilton today) behaviour.** With `*_self_threshold = infinity`, all override requests auto-approve. Override Log records every event but never prompts PIN. Pattern alerts never fire (no reference points yet).

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Override service must integrate with blind reconciliation (refunds/voids reduce expected cash via the same mechanism).
- **DEC-016** — Comp Admission reason categories (`docs/review_package.md` line 127). Comps are one consumer of the override service.
- **DEC-038** — Card reconciliation parallels cash reconciliation. Override events apply equally to card-side flows.

### Phase A research
- **G-028** — No native manager-override workflow. This document is the Hamilton response.
- **G-014** — Receipt reprint fraud. Reprint is one of the actions that should consume override service (Phase 2.5).
- **G-015** — No fixed-amount discount in POS. When Hamilton adds discounts, override service governs above-threshold use.

### Risk register
- **R-006** — Comp Admission Log `comp_value` permlevel. Override service captures who authorized comp; permlevel hides amount from operator UI.
- **R-008** — Single-acquirer SPOF. Not directly related but: card-side override events (refund auths) feed the chargeback ratio defense (R-009).

### Existing code
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` is the cart-side entrypoint. Phase 2 override-aware versions of refund / void / comp call into the override service before completing.
- **`hamilton_erp/hamilton_erp/doctype/comp_admission_log/comp_admission_log.json`** — comp DocType already exists; Phase 2 adds override-link field.
- **`docs/permissions_matrix.md`** — Hamilton Manager role definition. Override service reads role assignments to determine PIN-eligibility.

### Other design intent docs
- **`docs/design/refunds_phase2.md`** §4 — refund's manager-PIN gate consumes this service.
- **`docs/design/voids_phase1.md`** §4 — void's manager-PIN gate consumes this service.
- **`docs/design/cash_reconciliation_phase3.md`** — variance investigation may consume override for "manual override of variance flag."
- **`docs/design/tip_pull_phase2.md`** — large tip pulls may consume override.

### Build spec
- `docs/hamilton_erp_build_specification.md` §8.2 (combined operator/manager today) and §14 (V5.4 §15 deferred). This document supersedes the deferral when multi-op activates.

---

## Notes for the Phase 2 implementer

1. Read this document twice. Then read `docs/permissions_matrix.md` (existing role definitions) and the four caller-flow design intents (refunds, voids, comps, tip-pull).
2. Build the Override Profile DocType first — fixtures seed Hamilton's solo-operator-infinite-threshold profile.
3. Build the override service as a single module (`hamilton_erp/services/override.py`). All caller flows import from this module.
4. Implement the three tiers in order: Tier 1 (self-authorized) is the simplest; Tier 2 (manager PIN) requires UI work; Tier 3 (district SMS) requires SMS gateway integration.
5. Override Log is critical — write the schema first, get the audit trail right, then layer the service on top.
6. Manager dashboard is Phase 2.5 — ship Tiers 1–2 + Override Log first; pattern detection follows.
7. Test the PIN-warm window edge cases carefully. The 5-minute boundary is where subtle bugs live.
8. Solo-operator behaviour (Hamilton today) must work with `*_self_threshold = infinity`. The infrastructure is in place; gates are wide open. When Hamilton hires #2, the only change is updating the Override Profile.
9. Implement all 14 browser tests above. Pattern detection tests (9, 10, 13) require seeded data.
10. Document the migration runbook step "Hamilton hires second operator → tighten Override Profile thresholds" in `RUNBOOK.md`.

---

### §4.4 Tip Pull from Till (Phase 2, schema BLOCKER at Phase 1)

# Tip Pull from Till — Phase 2 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 1-BLOCKER (schema must exist for first tip event) → Phase 2 (full workflow when tipping begins)
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #16), informed by Phase A research (G-027 tips paid from till create timing-offset accounting problem), `docs/design/cash_reconciliation_phase3.md` §2 (where this pattern is first sketched), and CLAUDE.md "CAD nickel rounding is site-global"
**Implementation status today:** No tip-pull surface in the cart, no Tip Pull DocType, no integration with Cash Drop. Hamilton has zero tip-paying transactions today (admission services don't tip), so the gap is latent. The day a tip happens, blind cash reconciliation contaminates with phantom theft signal — the till is short by the tip amount, the system reads it as theft.

`cash_reconciliation_phase3.md` §2 sketches the workflow ("operator types tip, system rounds, system enforces exact cash pull") but does not detail the data model, the GL postings, the per-venue rounding-rule resolution, or the multi-currency handling. This document is the full design intent.

---

## Why this document exists

Tips are owed to the operator, not the venue. They settle T+1 to T+5 via processor. But operators expect tip cash at end of shift — that's a near-universal industry expectation, not a Hamilton quirk. Without a system-side tip-pull workflow, operators improvise: pulling cash from the till in the amount they think they're owed, no system record, till runs short for unexplained reasons.

The improvised flow has three failure modes:
1. **Reconciliation reads as theft.** Till shorts by tip amount; system has no record explaining the short; manager investigation triggers a "Possible Theft" flag for what is actually a legitimate tip pull.
2. **Tax misclassification.** Tip cash is the operator's compensation, not venue revenue. Sales tax / income tax remittance must NOT include the tip pull. Without system enforcement, the tip cash gets caught up in the day's revenue line.
3. **Operator rounding bias.** A $12.67 tip "becomes" $13 by operator rounding-up convenience. $0.33 of revenue per tip event becomes $0.33 of operator skim. Annualized at any volume, this is real money.

This document captures the reasoning for a tip-pull workflow that defends against all three failure modes. The design choices are deliberate: the system computes the rounding (operator has no discretion), the tip pull is a Tips Payable liability not a revenue offset, and the reconciliation calculator subtracts tip pulls explicitly.

If a future implementer thinks "the operator can just enter the rounded amount themselves" — re-read §2. Operator-discretion rounding IS the failure mode the system enforcement defends against.

---

## 1. Tip taxonomy — what counts as a tip pull

### Card tips paid from till (the primary case)

Customer pays $50 by card. Receipt prompt: "Add tip?" Customer adds $10 tip. Card auth = $60. Processor settlement (T+1 to T+5) deposits $60 to venue's bank account.

The operator wants the $10 in cash NOW, at end of shift. The cash comes from the till. The till runs short by $10. When processor settles $60 next day, $10 is "owed back" to the till — but bank deposits are aggregated; reconciliation must connect the dots over multi-day windows.

This is the failure mode G-027 documents and the primary case Hamilton must handle.

### Cash tips left for operator (a different case)

Customer pays $50 cash, leaves a $5 tip on the table for the operator. Operator pockets the $5 directly. Cash drop counts $50 (the bill). Tip never enters the till.

Phase 1 handling: operator cash tips are out-of-system. They're between the customer and the operator. Hamilton doesn't track them. Tax-wise, operators are responsible for declaring direct tips on their personal income return.

If a future state ever needs to track these (e.g., for tax reporting compliance), add a "Cash Tip Declared" record at end-of-shift; not a Phase 1/2 priority.

### Service charges (mandatory tip)

Some venues add an automatic service charge (15% on the bill, 18% for parties of 6+). This is venue revenue, not employee compensation by default. Some jurisdictions require service charges be remitted to staff; some allow venue retention. Hamilton: no service charges in Phase 1. Out of scope.

If Phase 3 introduces service charges, they go through standard ERPNext pricing (item or pricing rule), not through the tip-pull workflow.

### Pooled tips

Multi-operator venues often pool tips across staff. Operator A and B serve a customer; tip is split per-shift. Pooling logic: collect each operator's tip pulls during shift; at end-of-shift or end-of-week, pool aggregator distributes. Phase 3+ feature; Phase 1/2 = each operator pulls their own.

---

## 2. Tip pull workflow

### The decision (from `cash_reconciliation_phase3.md` §2, formalized here)

**Operator types the exact tip amount earned during shift. The system applies the venue's rounding rule. The system tells the operator the exact cash to take from the till. The operator obeys.**

### Step-by-step (CAD venue with nickel rounding)

1. End of shift: operator opens the Tip Pull surface (button in cart UI; visible only when shift is in progress).
2. Operator pulls terminal batch report from card terminal (lists each transaction's tip line).
3. Operator types total tip amount earned: e.g., `$12.67` (sum of all tips on terminal batch).
4. System applies venue's rounding rule (CAD: round UP to nearest $0.05): result `$12.70`.
5. UI displays prominently: "**Take $12.70 from drawer.**"
6. Operator obeys, removes $12.70 from till, pockets it.
7. System creates a Tip Pull record:
   - `operator` (the user pulling)
   - `shift_record` (the active shift)
   - `tip_earned_amount` = $12.67 (raw, from operator declaration)
   - `tip_pulled_amount` = $12.70 (system-rounded, what was actually taken)
   - `tip_rounding_difference` = $0.03 (loss to venue per rounding rule)
   - `currency` = CAD
   - `tip_pull_method` = "card_settlement" (vs. "cash_tip", "service_charge", etc.)
   - `processor_batch_reference` = terminal batch report ID (if available)
   - `timestamp`
8. System adjusts `system_expected_cash` for active shift: `expected -= tip_pulled_amount`.
9. Operator continues to end-of-shift cash drop normally; reconciliation reads zero variance.

### Why operator types the EARNED amount, not the rounded amount

The earned amount is the truth (sum of tips on terminal batch). The rounded amount is a system-generated derivative. If operator types the rounded amount directly, the system has no way to verify rounding was applied honestly.

By having operator type the raw earned amount, the system can:
- Apply the rounding rule deterministically.
- Validate against terminal batch amount (Phase 2 add: cross-check against settlement file).
- Detect operator-side fraud where the operator under-reports tips (typed $5 instead of actual $12 to skim the difference).

### Why the system enforces the rounded amount

(This is `cash_reconciliation_phase3.md` §2 verbatim, repeated for emphasis.)

Operators round in their own favor when given the chance:
- "$12.67 tip, I'll just take $13."
- "$12.67 tip, I'll take $12.50 and split with my buddy."

Each is a discrepancy that aggregates over time. Removing operator discretion forces a clean audit trail. The cost is the rounding loss to venue ($0.03 in the example), captured as a known operating expense.

### Annualized cost

`cash_reconciliation_phase3.md` §2 calculation: $0.03 × 4 daily tip events × 365 = $44/year per venue. This is fully accepted as an operating expense. It buys reconciliation correctness and operator-fraud defense.

### Why round UP for CAD

Round UP means operator gets MORE than the raw tip. Round DOWN would mean operator loses to rounding (operator-hostile, demotivating). Operator-favorable rounding ALSO means the "difference" account (tip_rounding_difference) is consistently positive — venue cost, not venue gain — which simplifies tax accounting (you don't generate phantom revenue from rounding).

DEC reference target: when Phase 2 implementer codes this, formalize tip-rounding direction as DEC-NNN ("Tip pull rounding is operator-favorable").

---

## 3. Per-venue rounding rules

### The decision

Tip-pull rounding is **venue-configurable**, not Canada-hardcoded. Different jurisdictions have different cash-rounding conventions; ANVIL's multi-venue rollout spans countries.

### Canonical per-venue rules

| Venue | Currency | Smallest unit | Rounding direction (tip pull) |
|---|---|---|---|
| Hamilton | CAD | $0.05 (nickel) | UP |
| Toronto | CAD | $0.05 | UP |
| Ottawa | CAD | $0.05 | UP |
| Philadelphia | USD | $0.01 (penny) | n/a (exact) |
| DC | USD | $0.01 | n/a (exact) |
| Dallas | USD | $0.01 | n/a (exact) |

USD venues don't need rounding (smallest unit is the penny; tips can be exact). The workflow simplifies: operator types $12.67, system says "Take $12.67," operator obeys.

Canadian nickel-rounded venues need the round-UP rule for the operator-favorable principle. Other countries (when ANVIL expands) will have their own — Australian dollar rounds to $0.05 like Canada; Switzerland rounds to $0.05; Mexico rounds to $0.50 or $1.00 depending on context.

### Implementation: the Reconciliation Profile (or Override Profile) holds the rule

Per `cash_reconciliation_phase3.md` §3, venue-specific rules live in a per-venue profile. Phase 2 implementer extends that profile (or creates a Tip Pull Profile sibling) with:
- `tip_rounding_currency` (CAD/USD/etc.)
- `tip_rounding_smallest_unit` (Currency)
- `tip_rounding_direction` (Up/Down/Nearest)
- `tip_rounding_account` (link to Account — where rounding loss posts)

The cart UI reads the profile; the displayed "Take $X" amount is derived; the GL posting uses the profile's account.

### Why one profile, not hardcoded

Same reasoning as `manager_override_phase2.md` §3: hardcoded values drift from venue practice; per-venue profile lets each venue tune to its own jurisdiction.

---

## 4. GL accounting — Tips Payable, not revenue

### The decision

**Tip pull DOES NOT post to revenue.** It posts to a Tips Payable liability account (or operator-advance account, accounting flavor-of-choice). When processor settlement clears T+1 to T+5, the liability is offset against incoming bank deposit.

### Why not revenue

Three reasons:

1. **Sales tax remittance.** HST / sales tax computes against revenue. If tip pull is in revenue, Hamilton over-remits HST on $10 of tip cash that wasn't venue revenue. Annualized, this is real money paid to CRA / IRS that Hamilton owes back to itself.

2. **Income tax.** Same reasoning — Hamilton's income computes against revenue. Tip in revenue = phantom income tax.

3. **Operator W-2 / T4.** Tip income is operator's, not venue's. Operator declares tips on their personal return (US: Form 4137; Canada: T4 Box 78 if employer-tracked, else self-declared). If venue revenue includes tips, the venue's records contradict the operator's records — tax-confusion city.

### The accounting flow

At tip pull (shift close):
- Debit: Cash (the cash leaves till)
- Credit: Tips Payable to Staff (liability)

At processor settlement (T+1 to T+5):
- Debit: Bank Account (cash arrives)
- Credit: Sales Revenue + HST Payable (the original card sale's normal posting; this happened at sale time, not settlement)
- Then a separate clearing entry:
- Debit: Tips Payable to Staff (liability cleared)
- Credit: Bank Account (the tip portion of the deposit goes to "settle" the liability)

Net effect over the multi-day cycle: Cash temporarily down by tip amount; Bank up by tip amount; Tips Payable transient. No revenue impact.

### What if the venue retains the tip rounding loss

The $0.03 example: operator earned $12.67; pulled $12.70. The $0.03 difference is operator-favorable. Treatment: debit Tip Rounding Adjustment expense, credit Cash. Annual aggregation = small operating expense for the venue.

If the venue ever reverses the rounding direction (round DOWN — operator-hostile), the difference is venue-favorable and gets credited to a different account (Tip Rounding Income — but DON'T DO THIS for the operator-experience reasons in §2).

---

## 5. Reconciliation integration

### How tip pull adjusts `system_expected_cash`

The cart's `system_expected_cash` calculator (Phase 3 implementation, `cash_reconciliation_phase3.md` §1) is:

```
system_expected_cash =
    sum(cash payments on submitted SIs for shift period)
    - sum(refunds for shift period, cash leg)
    - sum(voids for shift period, cash leg)
    - sum(tip pulls for shift period)        ← THIS LINE
    - sum(petty cash pulls for shift period) ← (process #7)
    + opening float
    - closing float
```

Tip pull is one of the explicit subtractions. The reconciliation reads zero variance because the operator's till runs exactly short by the tip amount.

### Multi-operator tip pulls

In overlapping-shift venues (DC), each operator pulls their own tips. Tip Pull records are linked to operator + shift_record. The reconciliation calculator scopes to the operator's shift period.

If two operators are concurrent and pulling tips simultaneously, the asset locking pattern (`coding_standards.md` §13) protects against race conditions on the till's cash count. Each operator's pull is atomic.

### Cross-shift tip pull (forgotten / late)

Operator finishes shift, walks out, realizes 30 minutes later they forgot tip pull. They've already done cash drop. Their reconciliation will read variance = -$tip_amount (till had MORE cash than expected, not less, because they didn't pull what they were owed).

This is a real human pattern. Defenses:
- Cart UI banner during last 30 minutes of shift: "Reminder: pull your tips before cash drop."
- Cash drop step explicitly asks "Have you pulled your tips? Yes / No → confirm."
- Late tip pulls are allowed but require manager-PIN (consume override service per `manager_override_phase2.md`) and create a "Late Tip Pull" record that can't disturb the closed shift's reconciliation; instead, posts as a current-day expense to be recovered next settlement.

---

## 6. Card settlement pairing — Phase 2.5 add

### The decision

When card settlement file imports next day, a pairing job verifies tip pulls match the settlement-reported tips. Discrepancies surface for manager review.

### What it catches

- **Operator over-claimed tips.** Operator typed $20 but settlement shows $12. Difference is $8 of cash skim disguised as tip.
- **Operator under-claimed tips.** Operator typed $5 but settlement shows $12. Difference is $7 of cash NOT pulled — sitting in till as unexplained variance, and operator is owed money.
- **Missing settlement.** Tip pull recorded but settlement file has no matching tips for the shift. Either processor batch is delayed (try next day) or a settlement was missed entirely.

### How it pairs

Each Tip Pull record stores `processor_batch_reference` (from terminal batch report). Settlement file has matching batch reference + total tip amount per batch. Pairing job sums Tip Pull records by batch and compares to settlement total. Variance threshold: $0.05 per batch (rounding noise) or 1% (whichever is higher).

### Phase placement

Pairing depends on settlement-reconciliation infrastructure (Phase 3, `cash_reconciliation_phase3.md` §5). Tip pairing is a consumer of that infrastructure, not a separate build.

---

## 7. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Per-venue rounding rule profile | Schema TBD | Phase 2 implementer | Reuse Reconciliation Profile or create Tip Pull Profile sibling |
| Tip pool aggregation logic | Deferred to Phase 3 | Multi-op venue need | Per-shift, per-venue, percentage split rules |
| Late tip pull workflow | Mentioned in §5, details TBD | Phase 2 implementer | Manager-PIN gate + separate posting account |
| Cash tip declaration (out-of-till) | Deferred | Phase 3+ if needed | Tax compliance gating |
| Service charges | Out of scope | n/a | Different mechanism (item or pricing rule) |
| Tip rounding direction DEC | TBD | Phase 2 implementer | DEC-NNN: tip rounding favors operator |
| Settlement pairing window | Default 7 days | Phase 2.5 implementer | Alert on unpaired > threshold |
| Operator W-2 / T4 reporting | Outside ERPNext | Payroll provider | But Tip Pull records can feed an export |
| Multi-currency tip pull (operator paid in USD at CAD venue) | Out of scope | n/a in current ANVIL config | Each venue is single-currency; if cross-currency arises, separate design |
| Tip Pull receipt printing | Pairs with receipt printer pipeline | Phase 2 implementer | Optional; tip pull record is the audit |

---

## 8. Browser test plan

Phase 1 minimum (schema + zero-tip behavior):

1. **Schema present, no UI.** Tip Pull DocType exists. Cart UI does not show Tip Pull button (because Hamilton has no tipping today). Reconciliation calculator subtracts `0` for tip pulls (no records). All existing tests pass unchanged.

Phase 2 (full workflow):

2. **Happy-path CAD tip pull.** Operator types $12.67 tip earned. UI displays "Take $12.70." Operator confirms. Tip Pull record created: tip_earned=$12.67, tip_pulled=$12.70, tip_rounding_difference=$0.03.
3. **Reconciliation reads zero variance after tip pull.** End of shift: $200 cash sales, $12.70 tip pull, no other reductions. `system_expected_cash` = $187.30. Operator declared $187.30, manager counted $187.30. Variance = Clean.
4. **USD venue: tip exact.** DC operator types $12.67. UI displays "Take $12.67." No rounding. Tip Pull: tip_pulled=$12.67, tip_rounding_difference=$0.
5. **GL posts correctly.** After tip pull: Tips Payable to Staff credited $12.70; Cash debited $12.70; Tip Rounding Adjustment debited $0.03; Cash credited $0.03 (all in same JE). Net: Cash down $12.70, Tips Payable up $12.70, Tip Rounding Adjustment up $0.03.
6. **Tip pull cannot exceed declared.** Operator types $12.67. System never displays a take-amount lower than $12.67 (rounding always favors operator).
7. **Multiple tip pulls per shift.** Operator pulls $5 mid-shift, then $7.67 at end. Two Tip Pull records linked to same shift_record. Reconciliation subtracts sum (= $12.70 rounded — actually $5.00 + $7.70 = $12.70 if rounded individually).
8. **Late tip pull requires manager.** Shift closed, reconciliation submitted. Operator returns; attempts tip pull. System throws: "Shift closed; manager-PIN required." Manager-PIN entered. Late Tip Pull record created with `is_late=True`; original reconciliation untouched.
9. **Tip pull after refund (negative scenario).** Operator processed $30 refund mid-shift. Same shift: $12.67 tip earned. Both adjustments subtract from `system_expected_cash`. Reconciliation Clean.
10. **Cross-shift settlement pairing (Phase 2.5).** Settlement file imports next day. Tip Pull records sum to $12.70; settlement file shows $12.67 in tips for that batch. Variance = $0.03 — within 1% threshold. Pairing succeeds.
11. **Settlement pairing fails on large variance.** Settlement file shows $5 in tips; Tip Pull sum = $20. Variance = $15. Alert fires: "Possible over-claimed tips, investigate."
12. **Tip pull in solo-operator mode.** Hamilton today: operator IS manager. Late tip pull manager-PIN = operator's own PIN (logs as self-authorized; flagged for end-of-shift review).

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Tip pull integrates with blind reconciliation.
- **DEC-013** — HST-inclusive pricing (`docs/review_package.md` line 118). Tax-correctness reasoning (§4) inherits this.
- **CLAUDE.md → "CAD nickel rounding is site-global"** — currency-level setting; tip pull rounding rule is the cart-level enforcement of the global setting.

### Phase A research
- **G-027** — Tips paid from till create timing-offset accounting problem. This document is the Hamilton response.
- **G-026** — Petty cash from till has no native workflow. Sibling problem with similar mechanism (process #7).
- **G-001** — POS Closing Entry overcounts cash. Tip pull is the kind of cash-reduction event that exposes G-001's bug if the cart's expected-cash calculator is wrong.

### Risk register
- **R-009** — MATCH list 1% chargeback threshold. Tip-related disputes can drive chargeback ratio up if customer disputes the tip portion of a card sale.

### Existing code
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` is the cart entrypoint. Phase 2 adds `submit_tip_pull` mirroring its authorization model.
- **`hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.json`** — Cash Drop schema may gain a `tip_pull_total` summary field for shift summary display.
- **`hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py`** — `_calculate_system_expected` (Phase 3) must subtract tip pulls.
- **`hamilton_erp/hamilton_erp/doctype/shift_record/shift_record.py`** — Shift Record may gain summary fields.

### Other design intent docs
- **`docs/design/cash_reconciliation_phase3.md`** §2 — first sketch of this workflow; this document is the full design intent.
- **`docs/design/refunds_phase2.md`** §5 — refund-of-tip handled there.
- **`docs/design/voids_phase1.md`** — voids reduce expected cash; tip pulls reduce expected cash; same calculator, different reason codes.
- **`docs/design/manager_override_phase2.md`** — late tip pull consumes override service.

### Build spec
- `docs/hamilton_erp_build_specification.md` — does not address tip pull; this document fills the gap.

---

## Notes for the Phase 1 implementer (schema only)

1. Read this document. Specifically focus on §1 (taxonomy) and §4 (GL postings) — those are the architectural commitments.
2. Build the Tip Pull DocType. Field set per §2 step 7. Empty cart UI (no button shown today).
3. Add the Tips Payable to Staff account to fixtures (chart of accounts seeded for new venues).
4. Add the Tip Rounding Adjustment account to fixtures.
5. Update the reconciliation calculator (`_calculate_system_expected`) to subtract tip pulls. Today this returns 0; Phase 3 implementation adds the full calculation including tip pulls.
6. Add Test 1 from the browser test plan: verify schema is present and reconciliation works with zero tip pulls.
7. Document the Late Tip Pull mechanism in `RUNBOOK.md` even though Phase 1 has no tips — the day a tip happens, the runbook entry is the recovery path.

## Notes for the Phase 2 implementer (full workflow)

1. Read this document twice. Then read `cash_reconciliation_phase3.md` §1-§3 (the broader cash architecture this plugs into).
2. Implement `submit_tip_pull` in `hamilton_erp/api.py` mirroring `submit_retail_sale`'s authorization model.
3. Per-venue rounding rule lives in Reconciliation Profile (or new Tip Pull Profile). Read at request time, never hardcode.
4. UI for the "Take $X" prompt must be unmissable. Bold, large, possibly highlighted color. Operator must explicitly confirm "I took $X."
5. Late tip pull path requires manager-PIN — consume the override service (`manager_override_phase2.md`).
6. Add tests 2-9 from the browser test plan.
7. Document the Phase 2 GL setup in `docs/RUNBOOK.md` — chart of accounts, posting templates, settlement reconciliation flow.

## Notes for the Phase 2.5 implementer (settlement pairing)

1. Pairs with settlement-reconciliation infrastructure (`cash_reconciliation_phase3.md` §5).
2. Add tests 10-11 from browser plan.
3. Pairing alerts integrate with manager dashboard.

---

### §4.5 Post-Close Integrity Check (Phase 1 BLOCKER)

# Post-Close Orphan-Invoice Integrity Check — Phase 1 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 1-BLOCKER
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #34), informed by Phase A research (G-023 — Sales Invoice creation skipped during POS Close, silent failure mode), G-010 (close timestamp off-by-one), and G-030 (invoice number gaps on draft deletion)
**Implementation status today:** No daily integrity check exists. The cart's `submit_retail_sale` writes Sales Invoices directly with `is_pos=1, update_stock=1`, bypassing the typical "POS Invoice → consolidated Sales Invoice" two-step ERPNext pattern. But the end-of-shift cash drop flow (build spec §7.5 step 5) does invoke a background POS Closing Entry that consolidates POS Invoices. If that consolidation step fails silently — the documented G-023 failure mode — a night's worth of sales activity has no consolidated SI, no GL posting, no P&L line.

---

## Why this document exists

This is the design intent for Hamilton's smallest Phase 1 BLOCKER but its highest blast radius. The implementation is tiny — one scheduled job, one alert, one extra reconciliation field. The audit value is enormous — a single silent failure during a busy night makes that night's revenue invisible to the books until manual review weeks later, when bank deposits and sales totals fail to reconcile.

The document captures three things: (1) what failure modes the integrity check defends against (G-023, G-010, G-030 each contribute), (2) why a daily scheduled check is the right cadence (not per-transaction, not weekly), and (3) what the alert payload contains so the operator/manager can act on it.

If a future implementer thinks "this is just a `frappe.get_all` query, why does it need a design doc" — re-read §3. The query shape is trivial; the recovery semantics are not. Without a documented recovery path, the alert fires and nobody knows what to do.

---

## 1. Failure modes this guard catches

### G-023 — Silent skip during POS Close consolidation

POS Closing Entry runs a background job to create the consolidated Sales Invoice. The job can fail silently (exception swallowed, Redis queue timeout, worker process killed). The parent POS Closing Entry submits successfully. Looks like a clean close from the operator's perspective. But the consolidated Sales Invoice doesn't exist. POS Invoices are marked as `consolidated_invoice = NULL` (or empty string) and `status = "Submitted"` — they're orphans.

GL impact: the per-transaction POS Invoice posts (revenue, tax, payment) happened at sale time. The consolidation typically creates a single Sales Invoice that mirrors the same posting but at the company-level. If consolidation skips, the per-transaction posts remain — so the GL might be partly correct — but reporting layers that aggregate by Sales Invoice (not POS Invoice) miss this revenue. Bank reconciliation against ERPNext's Sales Invoice list won't find the matching record.

Hamilton's exposure: the cart `submit_retail_sale` posts directly as Sales Invoice (not POS Invoice), bypassing G-023's most-direct trigger. But end-of-shift consolidation may still run and may still skip. Plus, future flows (refunds, voids, comps issued via Comp Admission Log) may take different paths through ERPNext's POS layer.

### G-010 — Close timestamp off-by-one

POS Closing Entry's time-range filter excludes invoices created at exactly the closing timestamp. Such invoices remain unconsolidated for that closing entry AND for the next shift's opening entry (which starts after the prior close). Permanently orphaned.

Likelihood at Hamilton: low (probability of exact-second collision is small at single-operator volume). But end-of-shift is the highest-volume moment of the day; collisions concentrate there.

### G-030 — Invoice number gaps on draft deletion

Frappe naming series increments on document creation, not submission. A draft created and then cancelled-deleted leaves a gap in the sequence. While not strictly an orphan-invoice problem, the gap detection logic is the same shape — surface unexpected sequence breaks for review.

Hamilton's exposure: medium. CRA doesn't strictly require contiguous sequences for small businesses, but the audit-readiness defense is to catch and explain gaps before an audit asks about them.

### Other latent failure modes

- **Stock ledger fail-after-SI-submit** — stock decrement fails with a database error after SI is submitted; SI says "submitted" but stock is wrong.
- **Hooks raise post-submit** — Hamilton's `on_sales_invoice_submit` hook (api.py:14) creates Venue Sessions; if it raises after SI submit, SI exists but session doesn't.
- **Concurrent submit collision** — two operators on two tablets submit at near-same time; one races ahead and the other's transaction goes into a partial state.

The integrity check, designed properly, surfaces all of the above as variants of the same audit pattern.

---

## 2. The integrity check — what it does

### The decision

A **daily scheduled job** runs at 4 AM venue-local-time (between shifts), executes a small set of queries against the prior day's POS / Sales Invoice activity, and emits an alert (visible to manager + admin) for any anomaly found.

### Queries to run

```python
# Query 1: orphaned POS Invoices (G-023 primary defense)
orphans = frappe.get_all("POS Invoice", filters={
    "creation": [">=", shift_window_start],
    "creation": ["<", today_4am],
    "status": "Submitted",
    "consolidated_invoice": ["in", ["", None]],
})

# Query 2: pre-close exact-timestamp matches (G-010)
# For each POS Closing Entry in the prior day, find any POS Invoice with
# posting_time = closing_time that is NOT in the closing entry's invoice list.
edge_cases = ...  # detailed query

# Query 3: naming series gaps (G-030)
# Find sequence breaks in HAMILTON-INVOICE naming for the prior day.
gaps = ...  # detailed query

# Query 4: stock-vs-SI mismatch (latent failure modes)
# For each Sales Invoice in the prior day, verify stock ledger entries
# exist matching the SI's items. Flag mismatches.
stock_mismatches = ...  # detailed query

# Query 5: SI-vs-VenueSession mismatch (Hamilton-specific)
# For each admission-item Sales Invoice in the prior day, verify a
# matching Venue Session exists. Hamilton's on_sales_invoice_submit hook
# should have created it; mismatches indicate hook failure.
session_mismatches = ...  # detailed query
```

Each query is bounded by the prior day's window. The job runs once daily (4 AM venue-local), checks the 24-hour window ending at the start of today's first shift.

### Alert payload

When any query returns rows, an `Integrity Alert` record is created with:
- `alert_date` (the day being checked)
- `alert_type` (orphaned_invoice / timestamp_edge / sequence_gap / stock_mismatch / session_mismatch)
- `affected_records` (Table — list of POS Invoice / Sales Invoice / sequence numbers)
- `severity` (HIGH for orphans, MEDIUM for sequence gaps, etc.)
- `recovery_path` (free text — the specific runbook step to take)
- `acknowledged_by` (User, set when manager reviews)
- `acknowledged_timestamp`
- `resolution_notes`

The alert is visible to Hamilton Manager + Hamilton Admin. Frappe desk shows a notification badge until acknowledged.

### Why daily, not per-transaction

Per-transaction integrity checks would slow down the cart and create false alarms (a check that fires before a hook completes is racing the system it's checking). Daily is the right cadence because:
- Most failure modes manifest at the shift boundary (consolidation, stock ledger, etc.).
- A 24-hour delay between failure and detection is acceptable — failures don't propagate further within a day.
- The daily aggregate gives manager review a coherent unit of work.

### Why 4 AM (and venue-local)

Between shifts. After the prior day's last close-out is committed (typically by midnight). Before the morning shift's first transaction (typically 8-10 AM). 4 AM venue-local handles all timezones cleanly.

For Hamilton (Eastern), 4 AM EST. For DC (Eastern), same. For Dallas (Central), 4 AM CST. The job uses `frappe.utils.get_user_time_zone` (or venue-attached timezone) to compute "yesterday."

---

## 3. Recovery semantics — what to do when alert fires

### The decision

Each `alert_type` has a documented recovery path. Manager opens the alert, reads the recovery instructions, executes them, marks the alert acknowledged with resolution notes.

### Recovery paths by alert type

| Alert type | Recovery path |
|---|---|
| `orphaned_invoice` | Manager creates a manual Sales Invoice referencing the orphan POS Invoice, posts it, links the original POS Invoice's `consolidated_invoice` field. (Phase 1.5 add: a one-click "consolidate this orphan" button.) |
| `timestamp_edge` | Manager submits the unconsolidated invoice via a one-off journal entry, OR re-runs POS Closing Entry's consolidation logic for that specific invoice. Documented in `RUNBOOK.md` §X. |
| `sequence_gap` | Manager investigates the gap (was a draft deleted? Did a transaction error?). If explained, marks acknowledged with note. If unexplained, escalates to Chris for compliance review. |
| `stock_mismatch` | Manager creates a manual Stock Reconciliation entry for the affected item. Investigates root cause (concurrent operations? hook failure?). |
| `session_mismatch` | Manager creates a Venue Session manually for the affected admission Sales Invoice. Investigates why the hook failed (look at error log around SI's creation timestamp). |

### Why explicit recovery paths matter

An alert with no documented recovery is a stress trigger for the manager and a "we'll figure it out later" situation that doesn't get figured out. Explicit recovery paths convert each alert from "investigate" to "execute step 1, 2, 3."

The recovery paths above are starter content. Phase 1 implementer should validate each path against actual ERPNext mechanics during build; Phase 1.5 should make some recovery paths one-click (consolidating an orphan especially).

### What if recovery doesn't work

Each alert type has an "escalate to Chris" tier. Recovery instructions explicitly include the escalation step at the bottom: "If the above doesn't resolve, page Chris with the alert ID." This is the same pattern as `RUNBOOK.md` §7.1's "page Chris immediately" for blind-cash invariant violations.

---

## 4. Alert visibility — manager + admin only

### The decision

Integrity alerts are visible to Hamilton Manager + Hamilton Admin roles. NOT visible to Hamilton Operator. Reasoning:

1. **Operator action is not the recovery path.** Recovery requires Frappe-desk access (which operators don't have per `permissions_matrix.md`) and accounting judgment (which operators don't have by role).

2. **Operator cannot fix orphan invoices anyway.** The fix is a manual SI creation by manager. Showing the alert to operator would just be informational — and informational alerts get tuned out.

3. **Operator could be the source of the failure.** If the operator's session has caused (or been involved in) the orphan, surfacing the alert to them is a tip-off if there's any malicious behavior. Manager investigates blindly.

### Alert delivery channels

- **Frappe desk notification badge** for managers logged in.
- **Email to manager + admin** at alert creation time (configurable per venue).
- **Manager dashboard shows alert count**, with drill-down.
- **Phase 2 add:** SMS to admin if alert remains unacknowledged for > 24 hours (escalation tier).

---

## 5. Operational rhythm — how managers consume alerts

### Daily morning workflow

1. Manager arrives ~8 AM. Logs into Frappe desk.
2. Notification badge shows "1 Integrity Alert (HIGH)."
3. Manager opens the alert. Reads alert_type and affected_records.
4. Manager reads recovery_path text.
5. Manager executes recovery (follows runbook step or creates a one-off entry).
6. Manager writes resolution_notes ("Recovered orphan POS-2026-04-30-INV-0023 via manual SI creation; root cause = Redis queue worker restart at 11:47 PM").
7. Manager marks alert acknowledged. Notification clears.

### Pattern of zero alerts

Most days, no alerts fire. The integrity check job runs, finds nothing, no alert is created. Manager sees no notification. This is correct.

If alerts fire frequently (more than 1 per week), it indicates a systemic issue — bugs in Hamilton's hooks, infrastructure instability, or upstream ERPNext bugs (R-010 polish-wave issues like #54183, #50787). Manager reports systemic patterns to Chris.

### Pattern of un-acknowledged alerts

If an alert sits unacknowledged for > 24 hours, Phase 2 SMS escalation fires to admin. After 72 hours unacknowledged, the audit-trail itself is a problem (something is HIGH severity and nobody is acting on it).

---

## 6. What this is NOT

- **Not a substitute for cash reconciliation.** Cash reconciliation runs per-shift; integrity check runs per-day. They catch different failure modes.
- **Not a real-time monitor.** Failures can persist up to 24 hours before detection. For real-time monitoring, separate Tier 0 monitoring layer is needed (Phase 2+).
- **Not an auto-recovery system.** It detects and surfaces; manager executes recovery. Auto-recovery is dangerous — bad fix code can compound the failure.
- **Not a substitute for testing.** It catches production failures the test suite missed. Both layers are needed.
- **Not a tax remediation tool.** If the integrity check finds revenue gaps from past months, those need accountant + tax-professional input, not just runbook steps.

---

## 7. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Exact recovery scripts per alert type | Starter content in §3 | Phase 1 implementer | Validate against ERPNext mechanics during build; refine into runbook |
| One-click "consolidate orphan" UI | Deferred to Phase 1.5 | Phase 1.5 implementer | Phase 1 ships with manual SI creation |
| SMS escalation for unacknowledged alerts | Deferred to Phase 2 | Phase 2 implementer | Pairs with override-service SMS infrastructure |
| Tier 0 real-time monitoring | Deferred to Phase 2+ | Phase 2 implementer | Separate from this daily check |
| Pattern detection across days | Deferred to Phase 2 | Phase 2 implementer | Aggregate alerts to surface systemic issues |
| Cross-venue admin dashboard | Deferred to Phase 3 | Phase 3 implementer | When ANVIL multi-venue |
| Auto-recovery for safe alert types | Deferred indefinitely | Risky; manager judgment is the safety net | Maybe never |
| DEC for integrity-check-cadence | Deferred | Phase 2 implementer | DEC-NNN: daily-at-4AM is canonical |
| Email template per alert type | Deferred to Phase 1.5 | Phase 1.5 implementer | Default text in Phase 1 |
| Per-venue alert routing rules | Deferred to Phase 2 | Multi-venue rollout | Hamilton manager vs Philadelphia manager — different recipients |

---

## 8. Browser test plan

1. **Happy day — no alerts.** Run the integrity job after a normal day. Zero `Integrity Alert` records created. Notification badge is clear.
2. **Orphan invoice triggers alert.** Manually create a POS Invoice with `status="Submitted"` and `consolidated_invoice=""`. Run the integrity job. One `Integrity Alert` record created with type=orphaned_invoice. Affected records list contains the orphan.
3. **Sequence gap triggers alert.** Create POS Invoice INV-001, INV-002, INV-004 (skip INV-003). Run integrity job. Alert with type=sequence_gap fires.
4. **Stock mismatch triggers alert.** Create Sales Invoice for towel; manually delete the corresponding Stock Ledger Entry. Run integrity job. Alert with type=stock_mismatch fires.
5. **Session mismatch triggers alert.** Create admission Sales Invoice; manually delete the corresponding Venue Session. Run integrity job. Alert with type=session_mismatch fires.
6. **Alert visible to manager only.** Hamilton Operator user has no notification badge for the alert. Hamilton Manager does.
7. **Alert acknowledgement clears notification.** Manager opens alert, writes resolution notes, marks acknowledged. Notification badge clears.
8. **Alert email sent at creation.** When alert is created, email is sent to manager + admin. Verify email content includes alert_type, affected_records, recovery_path.
9. **Daily job runs at 4 AM venue-local.** Schedule the job. Verify it runs at 4 AM EST for Hamilton, 4 AM CST for Dallas (when Dallas opens).
10. **Multiple alert types in one run.** Seed orphan + gap + mismatch in the same day. Run job. Three separate alert records created (one per type).
11. **Alert with affected_records list rendered.** UI for viewing alert shows affected records as a clickable list — clicking a row navigates to the underlying SI / POS Invoice / etc.
12. **Resolution notes mandatory.** Attempt to mark alert acknowledged without filling resolution_notes. System throws: "Resolution notes required."

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Integrity check is the system-side audit complementing operator/manager blind reconciliation.
- **DEC-019** — Three-layer locking on asset state changes (`docs/coding_standards.md` §13). Integrity check catches lock-failure side effects.

### Phase A research
- **G-023** — Silent skip during POS Close consolidation. Primary defense.
- **G-010** — Close timestamp off-by-one. Secondary defense.
- **G-030** — Invoice number gaps. Tertiary defense.
- **R-010** — ERPNext v16 polish-wave fix cadence. Open issues #54183 and #50787 will surface as integrity alerts when refunds ship in Phase 3 if upstream isn't yet patched.

### Risk register
- **R-006** — Comp Admission Log permlevel. Integrity check's session_mismatch type catches when comp's session-creation hook fails.
- **R-010** — ERPNext upstream bugs. Integrity check is the structural defense against upstream issues that aren't yet fixed.

### Existing code
- **`hamilton_erp/api.py:14`** — `on_sales_invoice_submit` hook creates Venue Sessions. Session-mismatch alert catches hook failures.
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` writes Sales Invoices. Stock-mismatch alert catches stock ledger inconsistencies.
- **`hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py`** — cash reconciliation provides per-shift integrity at cash level; this integrity check provides per-day integrity at SI level. Both layers needed.

### Other design intent docs
- **`docs/design/cash_reconciliation_phase3.md`** — sister integrity layer. Cash reconciliation operates on the cash side per-shift; this integrity check operates on the SI side per-day.
- **`docs/design/refunds_phase2.md`** — refunds are a likely future source of orphan invoices (R-010 issues #54183, #50787). The integrity check is the safety net.
- **`docs/design/voids_phase1.md`** — voids create cancelled SIs; integrity check verifies cancellation completed cleanly.

### Build spec
- `docs/hamilton_erp_build_specification.md` §7.5 — end-of-shift creates POS Closing Entry in background. This is the trigger event for G-023 failures.
- `docs/hamilton_erp_build_specification.md` §11 (Audit Logging) — this integrity check is one form of audit infrastructure complementing the document versioning.

### Operations
- `docs/RUNBOOK.md` — Phase 1 implementer adds runbook entries for each alert type's recovery path.

---

## Notes for the Phase 1 implementer

1. Read this document. Then read `RUNBOOK.md` (existing operational handling patterns).
2. Build the `Integrity Alert` DocType. Field set per §2's "Alert payload."
3. Build the daily scheduled job in `hamilton_erp/scheduled_tasks/integrity_check.py`. Register in `hooks.py`'s `scheduler_events` → `daily` (or use `cron` for the 4 AM venue-local timing).
4. Implement the five queries in §2. Start with Query 1 (orphan invoices) — it's the highest-blast-radius failure mode.
5. Email delivery uses Frappe's `frappe.sendmail`. Recipients = users with Hamilton Manager + Hamilton Admin roles.
6. Recovery paths in §3 are starter content. Validate each against actual ERPNext mechanics during build. Refine into `RUNBOOK.md` entries.
7. Test the cron timing carefully. Frappe's scheduled events run UTC by default; Hamilton needs venue-local 4 AM. Consider running every hour and checking "is_4am_venue_local" inside the job.
8. Acknowledgement workflow: alert.acknowledged_by + acknowledged_timestamp + resolution_notes. Mandatory resolution_notes per Test 12.
9. Run all 12 browser tests before merging.
10. Document the alert types and recovery paths prominently in `RUNBOOK.md` so manager has them at hand.
11. Implementation effort: small. Day or two. The audit value is large.

This is the cheapest BLOCKER to close. Ship it early.

---

## §5 Canonical file map

Each artifact in this combined report also lives at its canonical path. Use these for direct edits / future updates:

| Section | Canonical file path |
|---|---|
| Phase A research (full) | `docs/research/erpnext_pos_business_process_gotchas.md` |
| Phase B audit (full) | `docs/audits/pos_business_process_gap_audit.md` |
| §4.1 Refunds design intent | `docs/design/refunds_phase2.md` |
| §4.2 Voids design intent | `docs/design/voids_phase1.md` |
| §4.3 Manager Override design intent | `docs/design/manager_override_phase2.md` |
| §4.4 Tip Pull design intent | `docs/design/tip_pull_phase2.md` |
| §4.5 Post-Close Integrity design intent | `docs/design/post_close_integrity_phase1.md` |

**Reference template:** `docs/design/cash_reconciliation_phase3.md` (PR #108) — design intent doc structure used for all 5 above.

---

## §6 Cross-references

### Decisions referenced

- **DEC-005** — Blind Cash Drop Replaces Standard POS Closing for Operators (`docs/review_package.md` line 94)
- **DEC-011** — Brother QL-820NWB label printer (`docs/review_package.md` line 112)
- **DEC-021** — Blind cash control = DocType + Report + Page permissions + field masking
- **DEC-038** — Card reconciliation = same blind workflow as cash
- **DEC-039** — Variance reveal post-submit
- **DEC-041** — Investigation Resolution status
- **DEC-046** — Hamilton Settings printer fields
- **DEC-050** — Closing float variance handling
- **DEC-062** — Hamilton standard-merchant classification (PR #103)
- **DEC-063** — Per-venue processor choice (PR #103)
- **DEC-064** — Every venue must have primary AND backup processor (PR #103)

### Risks referenced

- **R-006** — Comp Admission Log comp_value readable by Operator (CLOSED via PR #98)
- **R-007** — Venue Session PII fields readable by Operator (in-flight via PR #100)
- **R-008** — Single-acquirer SPOF for Hamilton (downgraded per DEC-062)
- **R-009** — MATCH list 1% chargeback threshold (latent until card payments ship)
- **R-010** — ERPNext v16 polish-wave fix cadence
- **R-011** — Cash Reconciliation variance non-functional at Phase 1 (PR #110)
- **R-012** — Cash Drop envelope label print pipeline unbuilt (PR #110, Task 30 BLOCKER)

### Related work in flight

- **PR #108** — `docs/design/cash_reconciliation_phase3.md` (template for all design intent docs in §4)
- **PR #109** — Taskmaster Task 29 (this task's parent)
- **PR #110** — Risk register R-011 + R-012 + Task 30

### Multi-venue feature flags (canonical, surfaced by this analysis)

Per `docs/venue_rollout_playbook.md` Phase B + DEC-064:

- `anvil_membership_enabled` — DC-only (Hamilton, Philadelphia, Dallas: 0)
- `anvil_currency` — CAD (Hamilton) / USD (Philadelphia, DC, Dallas)
- `anvil_tax_mode` — CA_HST (Hamilton) / US_NONE (Philadelphia, DC, Dallas — but each adds its own per-jurisdiction template per the PR #51 audit rule on place-of-supply)
- `anvil_tablet_count` — 1 (Hamilton, Philadelphia, Dallas) / 3 (DC)

Multiple processes in §2 depend on these flags. Phase 2 implementation must read flags from `frappe.conf` rather than hardcoding Hamilton defaults.

---

## End of report

Total length: ~50,000 words across the synthesis + 7 source artifacts.
For implementation: open the relevant design intent doc (§4.x) and follow its 'Notes for the Phase N implementer' section.
