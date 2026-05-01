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
