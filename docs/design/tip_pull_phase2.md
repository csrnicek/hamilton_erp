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
