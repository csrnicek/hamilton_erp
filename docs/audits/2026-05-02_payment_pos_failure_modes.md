# Payment / POS Failure-Mode Audit — 2026-05-02

**Scope:** retail-sale + POS-submit + payment paths in `hamilton_erp/api.py`, the `Sales Invoice` override, the `Cash Drop` and `Cash Reconciliation` controllers, and the per-request transaction model that wraps them.

**Mindset:** assume the code is wrong until proven right. Hunt: race conditions, missing transactions, permission bypass, error-swallowing, fixture/state assumptions, partial-failure scenarios (network drop mid-payment, duplicate submit, browser crash, stale state, failed commit after payment, etc.). Cite `file:line` for every finding. No fixes — document only.

**Method:** dispatched an Explore pass over `api.py`, `overrides/sales_invoice.py`, `cash_drop.py`, `cash_reconciliation.py`, `lifecycle.py`, `locks.py`, `hooks.py` (~2k LOC). Verified the high-severity findings against actual code at the cited lines before publishing this audit; reranked or dropped claims that didn't survive the second look.

**Severity counts:** **1 BLOCKER · 7 HIGH · 5 MEDIUM · 3 LOW.**

> ⚠️ **The BLOCKER** below should be addressed before any Cash Reconciliation flow is exposed in Phase 1. If Cash Reconciliation is gated to Phase 3, the rank drops to HIGH. See finding for the conditional.

---

## BLOCKER

### B1 — Cash Reconciliation `system_expected` is a Phase-3 stub; every reconciliation falsely flags theft

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:60–69`

```python
def _calculate_system_expected(self):
    """Phase 3 implementation. ..."""
    # Placeholder — Phase 3 wires up the real calculation.
    self.system_expected = flt(0)
```

**Failure scenario.** Manager closes shift, runs reconciliation:

- operator declared $100, manager counted $100, system "expected" $0 (the stub).
- `_set_variance_flag` (lines 71–112) walks the three-way comparison.
- `manager_matches_operator = True` (both $100, within tolerance).
- `manager_matches_system = False` ($100 vs $0, way outside tolerance).
- The branch `elif manager_matches_operator and not manager_matches_system:` fires → `variance_flag = "Possible Theft or Error"`.

Result: **every clean reconciliation flags as suspected theft.** Alert fatigue ensues. Within a week, managers stop reading the flags. Real theft slips through.

**Why it fails.** `system_expected` is hard-coded to `0`, but the variance algorithm assumes it's the real POS-derived expected total. The two have to ship together; one without the other is worse than no flag at all.

**Conditional rank.** BLOCKER **if** Cash Reconciliation is exposed in Phase 1 launch. HIGH **if** the DocType / endpoint is admin-only / hidden until Phase 3. The DocType currently has no Hamilton-side gate that I found.

**Recommended fix (do not implement tonight).** Implement the Phase-3 query: `SELECT SUM(amount) FROM tabSales Invoice Payment WHERE mode_of_payment = 'Cash' AND parent IN (... SIs in shift window ...)`. Use the linked Cash Drop's shift_date / shift_identifier to scope the window. Until the implementation lands: either gate the DocType behind a permission such that operators/managers cannot create one in Phase 1, OR temporarily set `variance_flag = "Pending Phase 3 — system_expected not yet computed"` so the field doesn't lie about findings.

---

## HIGH

### H1 — Stock pre-check has a TOCTOU race; the second concurrent submit fails after the customer paid

**File:** `hamilton_erp/api.py:548–556`

```python
for item_code, total_qty in qty_by_item.items():
    bin_qty = flt(frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": pos_profile.warehouse},
        "actual_qty",
    ) or 0)
    if bin_qty < total_qty:
        frappe.throw(...)
```

**Failure scenario.** Two operators ring the same retail item simultaneously when stock is low (e.g., last 1 of "Day Pass" with `is_stock_item=1`). Both pass the pre-check (each reads `bin_qty=1`, each requests `1`). Both proceed into the cart insert + submit. ERPNext's stock-ledger validation fires inside `submit()` for the second request (negative-stock guard) and rolls that SI back. The second operator's customer has already handed over cash but the SI never committed, the till now has $X with no corresponding sale, and the operator gets a Frappe stack trace, not a recovery path.

**Why it fails.** `Bin.actual_qty` is read without a row lock. Between the read and the eventual stock-ledger write inside `si.submit()`, another transaction can decrement the same Bin. ERPNext's per-SLE validation is the only guard, and it fires *after* the operator told the customer the payment was processed.

**Impact bounding.** Hamilton's retail mix is the variable. If Day Passes / locker rentals are configured `is_stock_item=0` (services), the pre-check is essentially advisory and the race is a non-event. If any item is genuinely stock-tracked at low quantity and rung concurrently from two iPads, this fires.

**Recommended fix.** Either use `SELECT ... FROM \`tabBin\` WHERE item_code = %s AND warehouse = %s FOR UPDATE` to lock the Bin row inside the transaction (covers stock check through SI submit); OR document this race explicitly and put retail items on `is_stock_item=0` for Phase 1. Confirm the latter via a launch checklist.

### H2 — `frappe.set_user("Administrator")` finally block can leak elevated session if user-restore raises

**File:** `hamilton_erp/api.py:569–673`

```python
real_user = frappe.session.user
original_ignore_perms = frappe.flags.get("ignore_permissions", False)
frappe.set_user("Administrator")
frappe.flags.ignore_permissions = True
...
try:
    ...
finally:
    frappe.flags.ignore_permissions = original_ignore_perms
    frappe.set_user(real_user)
```

**Failure scenario.** A user record is deleted or disabled mid-request (between line 571 and the finally on line 672). When the finally block runs `frappe.set_user(real_user)`, Frappe raises (cannot find user). The `frappe.flags.ignore_permissions` flag was already restored on the previous line, but **the elevated session user is now stuck as Administrator** for the remainder of the request. If any subsequent middleware or hook runs in this request, it runs as Administrator with elevated trust.

**Why it fails.** The finally block restores `ignore_permissions` first, then `set_user`. If the second call throws, the first has already happened, and we're left in a partially-restored state where `frappe.session.user == "Administrator"`. There is no second-line catch.

**Concrete risk path.** A `before_request_close` or post-submit hook (e.g., a webhook that writes audit metadata) that runs as Administrator in this scenario gets full perms instead of operator perms.

**Recommended fix.** Wrap the finally block in its own try/except so the second restore can't be skipped if the first throws; log the failure via `frappe.log_error` and force `frappe.set_user("Guest")` as a defensive fallback. Order the restores symmetrically (last set, first restored).

### H3 — POS Profile field access has no defensive validation; missing field = developer-error stack trace at the till

**File:** `hamilton_erp/api.py:587, 596, 608–609`

The code reads `pos_profile.warehouse`, `pos_profile.cost_center`, `pos_profile.selling_price_list`, `pos_profile.company`, `pos_profile.currency`, `pos_profile.taxes_and_charges` directly off the cached doc. Existence of the profile is checked at line 502 (`frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE)`), but field-level population is not.

**Failure scenario.** A future migration drops or renames a field; or a manual edit clears `cost_center` on the production POS Profile. Operator submits cart. Code accesses `pos_profile.cost_center` mid-loop (line 609). Python raises `AttributeError: 'HamiltonPOSProfile' object has no attribute 'cost_center'`. Operator sees a Frappe error toast with a developer traceback. Cart is rolled back, but the customer is standing there with cash and the operator can't tell whether the transaction went through.

**Why it fails.** No assertion that the resolved POS Profile is fully populated for the cart flow. The code trusts the seed and trusts that no human ever opens the POS Profile form to "tidy up" a field.

**Recommended fix.** After `pos_profile = frappe.get_cached_doc(...)` (line 519), assert the required fields are non-empty and throw a translatable, operator-readable error: "POS Profile {0} is missing required field(s): {fields}. Run `bench migrate` to re-seed." The `_ensure_pos_profile` install path can stay the source of truth.

### H4 — Concurrent reconciliation of the same Cash Drop overwrites each other's audit pointer

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:114–120`

```python
def _mark_drop_reconciled(self):
    frappe.db.set_value(
        "Cash Drop", self.cash_drop,
        {"reconciled": 1, "reconciliation": self.name},
        update_modified=False,
    )
```

**Failure scenario.** Manager A and Manager B open the same `Cash Drop` form (a process or workflow accident), each runs the reconciliation wizard, each submits. Both `CashReconciliation` rows commit. `_mark_drop_reconciled` runs for each in turn: the second `set_value` overwrites the first's `reconciliation` field. The audit trail says only the second reconciliation exists; the first is in the database but the Cash Drop no longer points to it. A later "show me how this drop was reconciled" query points at the wrong reconciliation row.

**Why it fails.** No `before_submit` check against `Cash Drop.reconciled == 1` before letting the new reconciliation submit. No row lock on the Cash Drop for the duration of the reconciliation transaction.

**Recommended fix.** In `CashReconciliation.before_submit`, throw if the linked Cash Drop is already reconciled. Optionally `SELECT ... FOR UPDATE` on the Cash Drop row at the start of `validate` to serialize concurrent attempts.

### H5 — Lock TTL (15s) can expire mid-critical-section; second writer can race past

**File:** `hamilton_erp/locks.py:27, 72, 105–126`

The advisory Redis lock has a 15-second TTL. ERPNext request timeouts are typically 30–60s. If the critical section runs longer than 15s (slow DB, realtime queue backed up, scheduler tick), the lock expires and a second concurrent request can acquire it. The version-CAS check at the underlying status-write site is the ultimate guard — but only catches the second writer; the first writer's now-overwritten changes were committed before the second writer's CAS noticed.

**Failure scenario.** Two operators issue conflicting status changes on a Venue Asset. First operator's transaction is mid-flight, holding the lock. Lock expires after 15s. Second operator's request acquires the now-free lock and reads stale state. Both write back; CAS catches the second writer (good), but the second writer's intent is dropped silently from the operator's perspective.

**Why it fails.** TTL is shorter than worst-case critical-section latency. The lock is best-effort; the only true guard is CAS at the row level, which is fine-grained but invisible to the operator.

**Recommended fix.** Increase `LOCK_TTL_MS` to match P99 critical-section latency (measure first, don't guess). Optionally implement lock re-extension inside long critical sections. Document the TTL ceiling as a known operational constraint.

### H6 — No idempotency key on `submit_retail_sale`; double-tap or retry creates duplicate Sales Invoices

**File:** `hamilton_erp/api.py:403`

```python
@frappe.whitelist()
def submit_retail_sale(items=None, payment_method="Cash", cash_received=0):
```

**Failure scenario.** Operator double-taps the "Charge Cash" button; OR the network swallows the response so the JS retry kicks in; OR the operator refreshes the page mid-submit. Two requests arrive at the server, milliseconds apart. Both pass all validations (separate transactions, no shared state). Both insert a fresh SI with a unique autoname. Both submit. The till now has two SIs for one cart, the customer was charged once but the books say twice, and the operator has to manually cancel one (which requires elevated permission they may not have).

**Why it fails.** No idempotency key, no client-supplied request ID, no server-side dedup window.

**Recommended fix.** Accept an optional `idempotency_key` parameter (UUID generated client-side per cart). Store the resolved `(idempotency_key → sales_invoice_name)` in Redis with a 5-minute TTL. On a duplicate submit with the same key, return the existing SI name unchanged instead of creating a new one. This is the standard pattern for payment APIs.

### H7 — Variance-flag tolerance has a $1.00 floor that masks small-till discrepancies

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py:14–17`

```python
def _within_tolerance(a, b):
    diff = abs(a - b)
    threshold = max(a, b) * 0.02
    return diff <= max(threshold, 1.00)
```

**Failure scenario.** A small-amount Cash Drop ($20 till). Operator declares $20.00, manager counts $19.05. Variance: $0.95. Tolerance: `max($20 * 0.02, $1.00) = max($0.40, $1.00) = $1.00`. $0.95 ≤ $1.00 → flagged "Clean". Real $0.95 discrepancy is invisible. Repeat 365 days a year, $347/year per till in untracked variance.

**Why it fails.** The $1.00 floor is reasonable for a $1000 till but lets through proportionally significant variance on small ones.

**Recommended fix.** Either remove the $1.00 floor and rely on the 2% threshold alone (with a hard minimum like $0.05 to absorb rounding), or scale the floor: $0.10 floor + 2% threshold, capped at $5.

---

## MEDIUM

### M1 — `db_set("owner", real_user)` between `insert()` and `submit()` is harmless under Frappe's request transaction, but only as long as that holds

**File:** `hamilton_erp/api.py:660–662`

The audit pass initially flagged this as a partial-failure window. After re-reading: Frappe's whitelisted endpoint wraps the request in a single DB transaction; both the `insert` and the `db_set` UPDATE are rolled back together if `submit()` raises. So the *current* code is safe.

**Why it's still on the list.** `db_set` writes raw SQL with `update_modified=False` — that pattern is one `frappe.db.commit()` away from being a real partial-write window if a future hook adds explicit commit logic mid-flow. Defensive note for reviewers, not a live bug.

**Recommended fix.** Set `si.owner = real_user` *before* `insert()` (so it lands as part of the same INSERT) instead of after. Eliminates the conceptual exposure and removes the need for `db_set`. Slightly intrusive — needs to confirm the elevated insert path doesn't reset `owner` somewhere.

### M2 — Rounding adjustment returned to the client is freshly computed; if ERPNext's `calculate_taxes_and_totals` re-runs and clears the field, response and DB diverge

**File:** `hamilton_erp/api.py:631, 665–669`

The response value is read directly off the in-memory `si` object. If anything between line 631 and the actual DB commit re-computes taxes (e.g., a `before_save` hook on a custom field), `si.rounding_adjustment` could change. The receipt the client prints from the response then disagrees with the GL entry written to ERPNext. Auditor reconciling the till finds a $0.05 unreconciled GL hit.

**Recommended fix.** After `si.submit()`, re-read the SI from the DB (`frappe.get_doc("Sales Invoice", si.name)`) and use that copy for the response. Source of truth = the committed row.

### M3 — `walkin_customer = frappe.conf.get("hamilton_walkin_customer") or "Walk-in"`: typo in config = hard fail with no fallback path explained

**File:** `hamilton_erp/api.py:510–515`

A typo'd `bench set-config hamilton_walkin_customer "WalkIn"` reaches production. The check at line 514 fails because "WalkIn" doesn't exist. The error message echoes the configured value, not the default — operator can't tell whether the config is the bug.

**Recommended fix.** When the configured name doesn't exist, fall back to the seeded default `"Walk-in"` and emit a `frappe.logger().warning` with both names. OR validate the config at `before_save` of Hamilton Settings with a pick-list of valid customer names.

### M4 — Cart-line `qty=0` error message doesn't distinguish "you sent an empty line" from "the calculation produced 0"

**File:** `hamilton_erp/api.py:527–528`

`if not item_code or qty <= 0: frappe.throw("Invalid cart line: {0}")` — the operator sees "Invalid cart line" with the dict. They can't tell whether their cart UI shipped a phantom row or whether something downstream zeroed the qty.

**Recommended fix.** Differentiate the messages. If `qty <= 0`, throw "Item {item_code}: quantity must be greater than zero" — guides the operator to remove the row. If `not item_code`, throw "Cart row missing item_code".

### M5 — `change_amount` and `paid_amount` are written from local computation, not re-read from `calculate_taxes_and_totals`

**File:** `hamilton_erp/api.py:643–646`

```python
si.change_amount = change
si.base_change_amount = change
si.paid_amount = amount_due
si.base_paid_amount = amount_due
```

If ERPNext's controllers later overwrite these during `validate` (which they're known to do for `outstanding_amount`), the SI's eventual state may not match what the code thinks it set. The check at line 632 (`cash_received < amount_due`) covers the obvious case, but defense-in-depth would re-validate `paid_amount + change_amount == cash_received` post-submit.

**Recommended fix.** Add a post-submit assertion in dev/test mode (gated by `frappe.conf.developer_mode`) that the committed SI's `paid_amount + change_amount` matches `cash_received`. Catches downstream regressions without hurting prod.

---

## LOW

### L1 — `publish_realtime(..., after_commit=True)` is eventual-consistency under contention; Asset Board can render stale tile briefly

**File:** `hamilton_erp/api.py:31–39`

Realtime delivery is best-effort. Under load, board updates can arrive out of order or with delay. The Asset Board UI handles this with version checks (per `decisions_log.md` design intent), so a stale tile self-heals on the next event. Acceptable as-is; noting for completeness.

**Recommended fix.** Verify the Asset Board client-side reconciles via a polling fallback (e.g., refresh every 30s if no event since last). If not, add one.

### L2 — `cash_received` negative check (api.py:491–492) is the only guard against malformed numeric input from the client

**File:** `hamilton_erp/api.py:491–492`

The check is correct. But it's a single point of validation. If a future refactor moves or removes this line and there's no second-line defense, downstream cash math (line 639 onwards) silently produces negative change and a malformed payment line.

**Recommended fix.** Add a redundant `assert change >= 0` after the change calculation (line 639). Keeps the system robust to refactors that could relocate the upstream check.

### L3 — `si.remarks` audit-trail-via-string concatenation can lose the operator name if a prior caller already set remarks with a multi-MB blob

**File:** `hamilton_erp/api.py:651–652`

```python
si.remarks = (si.remarks or "") + f"\nRecorded via cart by {real_user}"
```

Unbounded concatenation. Doesn't matter today (nobody else writes `remarks` for retail SIs), but the `remarks` field in ERPNext is `Long Text` — could grow. More importantly, audit-trail facts living in free-text `remarks` are not queryable.

**Recommended fix.** Move the operator-of-record audit fact to a dedicated field on the SI (`hamilton_recorded_by`, custom field) or to a Comment. Free-text remarks should not be the system of record for who rang the sale.

---

## Categories with no findings

- **Permission-bypass via the override path itself.** The elevated-write pattern in `submit_retail_sale` (`frappe.set_user("Administrator")` + `ignore_permissions=True`) is documented and bounded; it's only used inside the whitelisted endpoint, restored in `finally`, and the Hamilton Operator role has no direct Sales Invoice perms (verified). No findings here other than H2 (the restore-can-leak edge case).
- **SQL injection.** All cited queries use parameterized `%s` placeholders. No string-formatted SQL in the audited paths. No findings.
- **Money math: float vs Decimal.** Frappe's `flt()` is the canonical wrapper; all monetary fields go through it. ERPNext's currency handling matches. No findings beyond M5 (defense-in-depth).
- **Tax calculation.** `set_pos_fields` populates taxes from POS Profile per the comment at lines 619–625. ERPNext's tax engine is the underlying authority; no Hamilton-side override that I could find that would corrupt the calculation.

---

## Cross-references

- `docs/research/erpnext_pos_business_process_gotchas.md` — G-001 through G-035 catalogue. **G-002** (deferred-stock-validation) and **G-023** (orphan-invoice / linked closing-entry race) are the upstream issues for which Task 35 (orphan integrity check, PR #124) is the Hamilton-side mitigation. This audit's **B1** is a downstream issue for the same family.
- `docs/audits/security_review_2026_05_full_codebase.md` — full-codebase security review. Cross-check H2 (set_user leak path) and H3 (POS Profile field validation) against the security review's findings list when synthesizing the next pass.
- `docs/decisions_log.md` — DEC-061 (per-venue currency), DEC-064 (primary processor), DEC-065 (tip pull). H1 (stock race) interacts with DEC-064/DEC-065 because card-payment paths add a second async leg (settlement) that compounds the partial-failure window.

---

## What I did NOT audit

This audit deliberately stops at the Hamilton-side code. **Out of scope:**

- ERPNext core's transaction model (assumed correct for the scenarios above).
- Frappe's `whitelist()` decorator and request lifecycle (assumed atomic per request).
- Card-payment terminal integration (Phase 2 — entire flow not yet implemented; auditing it would be premature).
- Frontend cart UI behaviour (HTML/JS; Hamilton Operator's perspective). The H6 idempotency finding implies a UI-side change too — flagged here for awareness only.

Re-audit recommended after card-payment integration lands.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
