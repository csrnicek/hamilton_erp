# Cash Handling Failure-Mode Audit — 2026-05-02

**Scope:** Cash Drop submission, Cash Reconciliation, the variance algorithm, and the Shift Record / operator linkage that supports them. Includes the just-merged Task 34 / PR #122 tip-pull schema (`tip_pull_currency`, `tip_pull_amount`, `tip_pull_difference`).

**Mindset:** assume the code is wrong until proven right. Hunt failure modes — operator falsification paths, audit-trail corruption, manager-override invisibility, multi-manager / multi-shift races, currency mismatches, theft-flag false negatives.

**Method:** explore-pass over `cash_drop.py`/`json`, `cash_reconciliation.py`/`json`, `shift_record.py`/`json`, `utils.py` (shift / drop helpers), and any `api.py` cash endpoints. Verified each high-severity claim at the cited lines. Cross-referenced Audit 1 (`payment_pos_failure_modes`) where overlap exists — duplicates labeled CROSS-REF below to avoid double-counting.

**Severity counts:** **0 BLOCKER · 4 HIGH · 4 MEDIUM · 2 LOW.**

> The most severe cash-handling concern (Cash Reconciliation `system_expected` Phase-3 stub causing every clean reconciliation to false-flag as theft) is already documented as **Audit 1 B1** and is the active conditional launch BLOCKER. This audit does not re-rank it; this audit catalogs the *other* gaps in the cash flow that are independent of B1.

---

## HIGH

### H1 — `variance_amount` field is declared and `read_only: 1`, but the controller never calculates it

**Files:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.json:99–104`; `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:71–112`.

```json
{
   "description": "Auto-calculated: actual_count - system_expected. ...",
   "fieldname": "variance_amount",
   "fieldtype": "Currency",
   "label": "Variance Amount",
   "read_only": 1
}
```

**Failure scenario.** Manager submits the blind count. `_set_variance_flag` fires and writes `variance_flag = "Possible Theft or Error"`. Manager opens the form post-submit and sees:

- `variance_flag` = "Possible Theft or Error" ✓
- `variance_amount` = $0.00 ❌ (the field is declared `read_only` and described as "Auto-calculated", but nothing calculates it)

The manager has no signal whether the discrepancy is $0.50 (rounding noise) or $500 (real theft). They open every flagged reconciliation just to do the subtraction by hand. Over 6 months: alert fatigue, misallocated investigation time, theft signal noise drowned out.

**Why it's allowed.** `validate()` (line 24–35) calls `_set_variance_flag()` at line 35. That method writes `variance_flag` only — it never sets `self.variance_amount`. The JSON declares the field, the description promises auto-calculation, the controller doesn't deliver.

**Recommended fix.** In `_set_variance_flag` (or a new `_set_variance_amount` called immediately before it), compute `self.variance_amount = flt(self.actual_count) - flt(self.system_expected)`. The fix is one line; the gap is purely a missed implementation step.

### H2 — Cash Drop's `operator` field has no auto-set and no check against `frappe.session.user`

**File:** `hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.py:1–18` (entire controller — no operator validation).

```python
class CashDrop(Document):
    def validate(self):
        self._set_timestamp()
        self._validate_declared_amount()
```

**Failure scenario.** Hamilton Operator role has `create` and `write` on Cash Drop (per `cash_drop.json` perms). Operator Alice creates a Cash Drop document and sets `operator = "bob_op@hamilton"` (Alice's coworker, Bob). She declares $50. The doc submits successfully. The audit trail says Bob made a $50 drop. Bob never touched the till that shift. Alice has just generated a paper trail that frames Bob.

**Why it's allowed.** No `before_insert` auto-set of `operator = frappe.session.user`. No `validate` check that `operator == frappe.session.user` (or that the elevated user is an admin). The field is `reqd: 1` but has no default and no source-of-truth binding.

**Impact bounding.** Requires the offender to know another operator's username and to write the doc via API or Frappe form. The Hamilton iPad UI presumably auto-fills `operator` to the logged-in user, so the *normal* UX path is correct — but the *raw DocType* is the audit surface, and it's open.

**Recommended fix.** Add `before_insert` hook: `if not self.operator: self.operator = frappe.session.user`. Add `validate` check: `if self.operator != frappe.session.user and "Hamilton Admin" not in frappe.get_roles(): frappe.throw(...)`. Mirror the same on Cash Reconciliation's `manager` field (see H3 / M3).

### H3 — Variance flag's two "Possible Theft or Error" branches are semantically different but produce identical output

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:97–112`

```python
if manager_matches_operator and manager_matches_system:
    self.variance_flag = "Clean"
elif manager_matches_operator and not manager_matches_system:
    # POS expected different amount — unrecorded transaction or theft
    self.variance_flag = "Possible Theft or Error"
elif not manager_matches_operator and manager_matches_system:
    # Operator mis-declared (POS and physical agree)
    self.variance_flag = "Operator Mis-declared"
elif system_matches_operator:
    # POS and operator agree, manager found less — money missing AFTER drop
    self.variance_flag = "Possible Theft or Error"
else:
    self.variance_flag = "Operator Mis-declared"
```

**Failure scenario.** Two completely different incidents land on the same flag:

- **Branch 1** (manager+operator agree, system disagrees): an unrecorded sale or POS-side bug. The till physically matches the operator's declaration, but the POS thinks more money should be there. Investigation target: the POS / unrecorded sales.
- **Branch 2** (system+operator agree, manager finds less): cash was physically removed *after* the operator dropped it. Investigation target: the path between drop and count (the safe, transit, the manager themselves).

These are root-cause-different: branch 1 = software / unrecorded transaction; branch 2 = physical theft. Manager sees the same string and starts the same investigation, missing the cause.

**Why it's allowed.** The control structure assigns the same string to both branches. The comments in the code distinguish them; the *output* doesn't.

**Recommended fix.** Distinct flag values: `"Possible Unrecorded Transaction"` for branch 1, `"Possible Cash Removed Post-Drop"` for branch 2, keep `"Possible Theft or Error"` only for the "none agree" fallthrough. The `Select` field options on `variance_flag` need to match. Update `decisions_log.md §7.7` (build spec note) so the rule list captures the distinction.

### H4 — Cash Reconciliation has no `before_submit` check against an already-reconciled drop; concurrent submissions overwrite each other's audit pointer

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:114–120`

```python
def _mark_drop_reconciled(self):
    frappe.db.set_value(
        "Cash Drop", self.cash_drop,
        {"reconciled": 1, "reconciliation": self.name},
        update_modified=False,
    )
```

**Failure scenario** (CROSS-REF Audit 1 H4 — same root cause, called out separately here for the cash-flow audit's completeness). Manager A and Manager B both open the same drop, both submit reconciliations near-simultaneously. Both `CashReconciliation` rows commit (no DB constraint, no app check). The second `_mark_drop_reconciled` runs *after* the first; it overwrites `Cash Drop.reconciliation` to point at itself. The first reconciliation is in the database but the drop no longer points at it. A "show me the reconciliation for DROP-2026.05-0001" lookup returns the second one only, missing Manager A's count entirely.

**Recommended fix.** `before_submit`: `if frappe.db.get_value("Cash Drop", self.cash_drop, "reconciled"): frappe.throw("This drop is already reconciled by reconciliation {linked_id}.")`. Optionally `SELECT ... FOR UPDATE` on the Cash Drop row at the start of `validate` to serialize. Optionally a unique constraint on `(cash_drop, docstatus=1)`.

---

## MEDIUM

### M1 — `declared_amount = 0` is accepted with no warning; "I made no sales this shift" looks identical to "I just decided to drop $0"

**File:** `hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.py:16–18`

```python
def _validate_declared_amount(self):
    if self.declared_amount is not None and self.declared_amount < 0:
        frappe.throw(_("Declared Amount cannot be negative."))
```

**Failure scenario.** Operator finishes shift, never opened the till, drops a $0 envelope. System accepts. Manager counts $0. System "expected" $0 (Audit 1 B1 stub). All three agree → `variance_flag = "Clean"`. But: was the till genuinely untouched, or did the operator pocket the cash and declare zero to dodge the variance check? Without a "this is a mid-shift, why would you declare zero?" gate, both look identical.

**Why it's allowed.** Validation rejects strictly-negative only. Zero passes.

**Recommended fix.** For `drop_type = "Mid-Shift"`, throw on `declared_amount == 0` ("Mid-shift drops must declare non-zero cash"). For `drop_type = "End-of-Shift"`, allow zero but mark the reconciliation with a "Zero declared — verify operator made no sales" flag (a third variance-flag value, or a separate boolean).

### M2 — Cash Drop does not check that the linked Shift Record is `status = "Open"`

**Files:** `hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.py:7–18`; `hamilton_erp/hamilton_erp/doctype/shift_record/shift_record.json` (status field).

**Failure scenario.** Operator's shift was closed at 11pm. At 11:30pm, somebody (admin user, automation script, the operator if they have access) creates a Cash Drop pointing at the now-closed Shift Record. The drop submits. The audit trail now contains a drop attached to a closed shift, breaking chronological invariants. Reports that join Cash Drops to Shift Record windows produce inconsistent answers.

**Why it's allowed.** The `shift_record` field on Cash Drop has no `reqd` flag and no validation. The controller doesn't load the Shift Record to check its `status`.

**Recommended fix.** In `validate`: `if self.shift_record: status = frappe.db.get_value("Shift Record", self.shift_record, "status"); if status != "Open": frappe.throw("Cannot record a Cash Drop against a {0} shift.".format(status))`.

### M3 — Cash Reconciliation's `manager` field has no auto-set and no role-check guard

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:24–50`

Mirror of H2 on the manager side. The `manager` field is `reqd: 1` but has no `before_insert` auto-set and no `validate` check that `manager == frappe.session.user` (or that the user is admin overriding for someone else). A user with write perm can submit a reconciliation "as" another manager.

**Recommended fix.** `before_insert`: auto-set `manager = frappe.session.user`. `validate`: throw if `manager != frappe.session.user` and the actor isn't an admin. Same shape as H2.

### M4 — No venue-scoping check between the manager and the operator's shift

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:24–50` (no scoping logic anywhere).

**Failure scenario.** When Hamilton becomes multi-venue (Phase 2), Manager from Venue A opens a Cash Drop from Venue B and submits a reconciliation. Cross-venue review is allowed. If permissions are venue-scoped (DEC-021 / `permissions_matrix.md`), this *should* be blocked, but the controller doesn't enforce it.

**Phase status.** Single-venue today (Hamilton only). Becomes a real risk in Phase 2 multi-venue. Documenting now so the gap is visible.

**Recommended fix.** When venue scoping is implemented (Phase 2), add a `validate` check: `if get_user_venue(self.manager) != get_drop_venue(self.cash_drop): frappe.throw("Cross-venue reconciliation requires Admin role.")`. Until Phase 2: not applicable.

---

## LOW

### L1 — `actual_count` missing negative-value validation

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:24–50`

A manager could enter `actual_count = -50` via API or doctype insert. The variance math uses `abs()` internally so the *math* is technically valid, but a negative physical count is impossible. Defensive validation should reject it; the schema's Currency type doesn't enforce sign.

**Recommended fix.** Add `if self.actual_count is not None and self.actual_count < 0: frappe.throw(...)` to `validate`. Same pattern as `_validate_declared_amount` on Cash Drop.

### L2 — Cancel/resubmit cycle on a reconciled Cash Drop leaves the `Cash Drop.reconciled` flag stale

**Files:** Across `cash_drop.py` and `cash_reconciliation.py` — no `on_cancel` hook on either.

**Failure scenario.** Manager submits Cash Reconciliation R1, which marks `Cash Drop D1.reconciled = 1` and `D1.reconciliation = "R1"`. Manager realizes R1 had a typo, cancels R1. R1.docstatus → 2 (cancelled). But D1 still has `reconciled = 1` and `reconciliation = "R1"` pointing at a cancelled doc. New reconciliation R2 cannot be created because the H4 guard (when added) would reject "already reconciled" — even though the linked reconciliation is cancelled.

**Why it's allowed.** No `on_cancel` hook on `CashReconciliation` to revert the drop's reconciled flag.

**Recommended fix.** Add `on_cancel` to `CashReconciliation`: clear `Cash Drop.reconciled = 0` and `Cash Drop.reconciliation = None` if the drop's `reconciliation` field still points at this cancelled doc. Make sure to handle the case where R2 already replaced R1's pointer (don't blank it then).

---

## Tip Pull Schema (Task 34 / DEC-065) — focused review

Following the just-merged PR #122 fixes, I checked the tip-pull fields specifically:

- **`tip_pull_currency` resolution** (PR #122 fix `f9a8836`): controller `before_insert` correctly reads `frappe.conf.anvil_currency` with `"CAD"` fallback. Caller-passed value is preserved. **No new findings.**
- **`tip_pull_difference` calculation:** computed in `_compute_tip_pull_difference` (per the controller's `validate` chain). I did not deep-audit this path — the controller-level math looks correct and tests cover the basic cases. Flagging here as a re-audit candidate after Phase 2 settlement-pairing lands.
- **Negative `tip_pull_amount` warning threshold (`-$50`):** validated on submit via `_warn_on_large_negative_tip_pull`; uses `msgprint` (warning) rather than `throw` (error). Operator-facing UX is correct. **No findings.**

---

## Categories with no findings

- **SQL injection** — All cash queries use Frappe ORM helpers (`db.get_value`, `db.set_value`) with parameterized arguments. No string-formatted SQL. No findings.
- **Currency-mismatch handling** — `tip_pull_currency` resolution is venue-aware (PR #122). No findings post-fix.
- **Tip-pull negative-amount validation** — handled correctly via `_warn_on_large_negative_tip_pull`. No findings.
- **Money math float / Decimal correctness** — all amount fields go through `flt()`. ERPNext currency framework handles rounding consistently. No findings beyond Audit 1 M5 (defense-in-depth).
- **Submit-cancel-resubmit on Cash Drop itself** — Cash Drop is a transactional doc; ERPNext's cancel mechanics are standard. The only gap (L2 above) is on the reconciliation side, not the drop itself.

---

## Cross-references

- **Audit 1 B1** (system_expected=0 stub) is the active launch BLOCKER for the cash flow. Fixing it without addressing **H1** (variance_amount calculation) here only fixes half the manager-facing display.
- **Audit 1 H4** is the same race as **H4** here. Single fix.
- **Audit 1 H7** (variance $1.00 floor) interacts with **M1** (declared zero accepted). Both small-amount cases hide real signal.
- `docs/decisions_log.md` DEC-064 (per-venue primary processor) and DEC-065 (tip-pull schema) were the impetus for the Task 34 / PR #122 work that this audit cross-checked.

---

## What I did NOT audit

- ERPNext's POS Closing Entry creation and its Cash Drop linkage — that's Audit 1's territory and the Task 35 orphan-check (PR #124, just landed) is the safety net for it.
- Phase 2 multi-venue scoping logic — flagged in M4 as a re-audit candidate.
- Tip settlement-pairing / processor reconciliation — Phase 2 work, not yet implemented.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
