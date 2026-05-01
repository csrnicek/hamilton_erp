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
