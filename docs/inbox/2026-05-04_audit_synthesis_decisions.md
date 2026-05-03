# Audit Synthesis — Final Ship Decisions

**Date:** 2026-05-04
**Source:** Synthesis of 4 audits (Claude.ai, ChatGPT, Claude Code self-audit 2026-05-02, Claude Code verification 2026-05-03).
**Audited commit:** `19402cf677ad9562c4372c71c74a2b44bd3da862`. Verified against `4a7418d` (current `main`). Zero non-docs changes between SHAs — every file:line citation is authoritative.
**Status:** All severity calls reconciled across reviewers. This document is the locked ship list. Claude Code reads this at session start for today's work.

---

## ⛔ Decision Required Before Any Code

**Is Cash Reconciliation IN Phase 1 launch scope?**

- **YES** → Implement T0-2 **Path A** (real `system_expected` calculation). Larger fix; supervised `bench migrate` window. Higher confidence reconciliation, but also higher build cost and rollback risk if the calculation has bugs.
- **NO** → Implement T0-2 **Path B** (hard-disable + manual reconciliation procedure). Smaller fix; still requires migrate. Cash Reconciliation in Frappe becomes inert; managers reconcile cash physically with paper.

**This decision must be locked before any T0-2 work begins.** Both paths are spec'd below. If unsure, default to Path B — it ships in 2-4 hours and removes risk; Path A can land in Phase 3 properly.

---

## Verified Severity Tally

| Tier | Count | Items |
|---|---|---|
| **BLOCKER** (cannot launch) | 3 | T0-1, T0-2, T0-3 |
| **HIGH** (must close pre-launch) | 8 | T0-4, T1-1, T1-2, T1-5, T1-7, NEW-1, NEW-2, COMP-RUNTIME |
| **MEDIUM** (test-first or smaller) | 4 | T1-3, T1-4 (+$5000 bundle), T1-6, T1-CORRECT |
| **Tier 2** (pre-second-venue) | 4 | PR #100, Stack #3, Customer-link PII, PIPEDA scheduler |

**Total pre-launch PRs estimated:** 11 (3 BLOCKER + 8 HIGH). Some are bundleable in a single supervised `bench migrate` window.

---

## Ship Order (Verified by Claude Code)

The order optimizes for: decisions first → controller-only fixes (no migrate) → consolidated migrate window → hardware-coupled → idempotency. Each item is one PR with auto-merge enabled per the standard PR template.

### Phase 1 — Decision (Day 1, before any code)

| # | Item | Action |
|---|---|---|
| 0 | Cash Reconciliation Phase 1 scope | Chris locks Path A or Path B for T0-2 |

### Phase 2 — Controller-only (no `bench migrate` STOP) — can ship tonight in parallel

| # | Item | Files | Notes |
|---|---|---|---|
| 1 | **T0-4** Cash Drop immutability | `cash_drop.py` | Same file as T1-4. Bundle into one PR if convenient. |
| 2 | **T1-4 + $5000 bound** Cash Drop shift validation + upper-bound sanity | `cash_drop.py` | Bundles A1 F3.4 ($5000 cap). Same file as T0-4. |
| 3 | **T1-5** Cash Recon uniqueness per drop | `cash_reconciliation.py` | Same file as T0-2 — sequence around the migrate window. |
| 4 | **T1-1** Admission gate + assign_asset stub no-op | `api.py` | Independent file. Parallel-safe. |
| 5 | **NEW-2** publish_realtime try/except | `realtime.py` | Independent file. Parallel-safe. ~5 LOC. |
| 6 | **T1-7** Lifecycle rollback regression tests | `test_adversarial.py` | Test-only. Parallel-safe. |
| 7 | **T1-3 TEST** Hamilton Operator runtime read on Hamilton Settings | `test_security_audit.py` | Test first. If passes → close T1-3 as no-issue. If fails → fix lands as JSON perm change in Phase 3. |
| 8 | **COMP-RUNTIME** Verify `Comp Admission Log.comp_value` masking at runtime | `test_security_audit.py` | Open existing `TestCompAdmissionLogValueMasking`, confirm it runs as Hamilton Operator (not Administrator) before asserting None. |
| 9 | **T1-CORRECT (design)** Audit-log correction-without-delete pattern | `docs/decisions_log.md` | DOCS-ONLY. Design how managers fix typos in Asset Status Log / Comp Admission Log without `delete`. Pre-requisite to T1-2. |

### Phase 3 — Consolidated `bench migrate` window (supervised — STOP condition)

These all need migrate. Bundle into ONE supervised session so migrate fires once. Order doesn't matter much within the window.

| # | Item | Files | Why bundle? |
|---|---|---|---|
| 10 | **T0-2** Cash Recon `system_expected` (Path A or B per Phase 1 decision) | `cash_reconciliation.py` (+ `.json` for Path B Select options) | The big fix. Path A ships with feature flag `Hamilton Settings.cash_recon_use_real_system_expected` (default OFF) for instant rollback. |
| 11 | **NEW-1** `variance_amount` calculation | `cash_reconciliation.py` | Bundle into T0-2 PR. One-line: `self.variance_amount = flt(self.actual_count) - flt(self.system_expected)`. |
| 12 | **T1-2** Drop `delete` from Admin on audit logs | `asset_status_log.json`, `comp_admission_log.json` | Sequence after T1-CORRECT. JSON-only change. |
| 13 | **T1-6 TEST** Audit trail enablement post-install | `test_fresh_install_conformance.py` | Test-only. Asserts `frappe.db.get_single_value("System Settings", "enable_audit_trail") == 1`. |

### Phase 4 — Hardware-coupled (gated on Brother QL-820NWB physical availability)

| # | Item | Why slot here |
|---|---|---|
| 14 | **T0-3** Cash Drop envelope label print pipeline (R-012) | **HARDWARE PREREQUISITE: confirm Brother QL-820NWB is in Chris's possession and reachable from the Frappe Cloud bench network BEFORE starting.** Realistic timeline: 3-5 days. This is the launch gate if hardware isn't ready. Cannot launch without this per R-012. |

### Phase 5 — Idempotency (largest fix; requires migrate; can be bundled with Phase 3)

| # | Item | Notes |
|---|---|---|
| 15 | **T0-1** Idempotency token on `submit_retail_sale` | New DocType `Cash Sale Idempotency` + scheduler purge job + frontend UUID generation. Bundle migrate with Phase 3 if scheduling allows. **Operational mitigation until shipped:** train operators that "Sale failed" might mean "succeeded but network dropped — verify SI exists in Desk before retrying." |

---

## Item Specifications (for Claude Code)

Each item below is paste-ready as a Claude Code prompt. STOP conditions are flagged. Model recommendations included.

### T0-1 — Idempotency Token on `submit_retail_sale`

**Severity:** BLOCKER (consensus; A1 + Claude Code verification)

**Evidence (verified):**
- `hamilton_erp/api.py:402-403` — endpoint signature has no `client_request_id`.
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js:710` — `// Cart intentionally NOT cleared — operator can retry.`

**Failure mode:** Network drop after server commit but before client receives response → operator sees "Sale failed" → retries → second SI for same items → double stock decrement, double cash payment lines.

**Claude Code prompt:**
```text
Implement idempotency on hamilton_erp.api.submit_retail_sale to prevent
double-charge on network retry. T0-1 in
docs/inbox/2026-05-04_audit_synthesis_decisions.md.

Plan:
1. Create new DocType "Cash Sale Idempotency" with fields:
   - client_request_id (Data, 200 chars, unique=1, indexed)
   - sales_invoice (Link to Sales Invoice)
   - created_at (Datetime, default=now)
2. Modify submit_retail_sale to accept optional client_request_id:
   - If provided AND a Cash Sale Idempotency record exists with that key,
     return the cached SI's response payload without creating a new one.
   - After successful si.submit(), insert the idempotency record. Use
     try/except IntegrityError to handle the tight retry race.
3. Modify asset_board.js _open_cash_payment_modal: generate UUID via
   crypto.randomUUID() at Confirm tap, pass as client_request_id.
4. Scheduler job to purge idempotency records older than 24h (daily).
5. Tests:
   - test_submit_retail_sale_idempotent_same_request_id_returns_same_si
   - test_submit_retail_sale_different_request_ids_create_two_sis
   - test_submit_retail_sale_no_request_id_passthrough_unchanged_behavior
6. Update docs/decisions_log.md with new DEC entry.
7. Update docs/lessons_learned.md with the network-drop pattern.
8. Open PR with auto-merge enabled per CLAUDE.md PR template.

This task requires Opus reasoning. Type /model to switch if currently on
Sonnet.

STOP CONDITION: bench migrate required for the new DocType.
```

---

### T0-2 — Cash Reconciliation `system_expected` (Decision-Locked)

**Severity:** BLOCKER conditional. Lock Path A or Path B before code.

**Evidence (verified):** `cash_reconciliation.py:67-69` — `self.system_expected = flt(0)` placeholder.

**Path A — Implement real calculation (if Cash Recon IS in Phase 1):**

```text
T0-2 Path A — implement real Cash Reconciliation system_expected with
feature-flag rollback.

Read first:
- docs/risk_register.md R-011
- docs/design/cash_reconciliation_phase3.md if exists
- docs/decisions_log.md DEC entries on cash recon

Plan:
1. Add Hamilton Settings field: cash_recon_use_real_system_expected
   (Check, default 0).
2. Replace _calculate_system_expected body with:
   - If Hamilton Settings flag is OFF: keep placeholder (self.system_expected = 0).
   - If ON: query submitted Sales Invoices in shift window, sum cash
     payments[].amount, subtract tip pulls if applicable.
3. Define shift window: start = previous Cash Drop's timestamp (or
   shift_start if first drop); end = self.cash_drop.timestamp.
4. Bundle NEW-1: add self.variance_amount = flt(self.actual_count) -
   flt(self.system_expected) in _set_variance_flag.
5. Six tests covering full variance matrix:
   - all three agree → Clean
   - operator + manager agree, system differs → Possible Theft
   - POS + operator agree, manager short → Possible Theft (different branch)
   - manager + system agree, operator misdeclared → Operator Mis-declared
   - empty period → system_expected = 0 + flag indicates empty
   - multiple drops in shift → window correctly bounded per drop
6. Document feature flag in docs/decisions_log.md and HAMILTON_LAUNCH_PLAYBOOK.md.
7. Update R-011 to mark closed once flag is flipped on in production.
8. Open PR with auto-merge enabled.

This task requires Opus reasoning.

STOP CONDITION: bench migrate required for new Hamilton Settings field.
Bundle into the Phase 3 migrate window per the decisions doc.

ROLLBACK: If post-deploy reveals the calculation is wrong, flip flag OFF
in Frappe Desk → Hamilton Settings. variance_flag returns to placeholder
behavior; manual reconciliation takes over. No revert PR needed.
```

**Path B — Hard-disable until Phase 3 (if Cash Recon is OUT of Phase 1):**

```text
T0-2 Path B — hard-disable Cash Reconciliation variance classification
until Phase 3.

Plan:
1. Add "Pending Phase 3" to variance_flag Select options in
   cash_reconciliation.json.
2. In _set_variance_flag (cash_reconciliation.py:71), short-circuit
   immediately to self.variance_flag = "Pending Phase 3" and return.
   Skip the three-way classification entirely.
3. Bundle NEW-1: add self.variance_amount = flt(self.actual_count) -
   flt(self.system_expected). Manager still sees a number, not $0.00.
4. Add a banner on the Cash Reconciliation form via cash_reconciliation.js:
   "System expected calculation is Phase 3 work. Use manual reconciliation
   procedure in RUNBOOK_EMERGENCY.md."
5. Update HAMILTON_LAUNCH_PLAYBOOK.md and docs/RUNBOOK.md with manual
   reconciliation procedure (manager physically counts envelope, matches
   declared_amount on printed label, signs off on paper).
6. Single test: test_variance_flag_pending_phase_3_for_any_inputs.
7. Update docs/decisions_log.md with DEC-NNN documenting deferral.
8. Update R-011 to mark closed (deferred).
9. Open PR with auto-merge enabled.

This task is Sonnet-appropriate.

STOP CONDITION: bench migrate for the Select option change. Bundle into
Phase 3 migrate window.
```

---

### T0-3 — Cash Drop Envelope Label Print Pipeline (R-012)

**Severity:** BLOCKER (R-012 in repo). HARDWARE-DEPENDENT.

**Evidence (verified):** `cash_drop.py` is 19 lines; no `on_submit` hook; no Label Template DocType in tree; `Hamilton Settings.printer_label_template_name` field has no other side.

**Hardware prerequisite:**
- [ ] Brother QL-820NWB physically in Chris's possession
- [ ] Printer reachable from Frappe Cloud bench (network address tested)
- [ ] 1-day spike confirms `brother_ql` Python library OR ESC/POS approach handles 8 spec fields

**Until hardware is verified, do NOT start this task.** If hardware is not ready by launch week, T0-3 IS the launch gate and Hamilton cannot open. R-012 is unconditional.

**Claude Code prompt:**
```text
Implement Cash Drop envelope label print pipeline (T0-3 / R-012). PRE-LAUNCH
BLOCKER. Run only after Chris confirms Brother QL-820NWB is on his desk
and pingable from Frappe Cloud.

Read first:
- docs/risk_register.md R-012 (full spec)
- docs/research/label_printer_evaluation_2026_05.md (printer choice)
- docs/hamilton_erp_build_specification.md §7.4 (8 spec fields)

Plan:
1. Create Label Template DocType (template_body Long Text with
   {placeholder} syntax, printer_type Select).
2. Add Cash Drop on_submit hook:
   - Read Hamilton Settings.printer_label_template_name and printer_ip_address.
   - Render template with 8 fields: venue_name, shift_date, operator,
     shift_identifier, drop_type, drop_number, declared_amount, timestamp.
   - Dispatch via brother_ql library OR ESC/POS raster fallback.
   - On dispatch failure: frappe.throw with clear operator error,
     PREVENTING the submit. (No silent fallback to unlabeled drop.)
3. Idempotency: re-submit must not re-print.
4. Tests:
   - test_label_content_includes_all_8_fields
   - test_print_failure_blocks_cash_drop_submit
   - test_print_success_allows_submit
   - test_resubmit_does_not_double_print
5. Update docs/RUNBOOK.md and RUNBOOK_EMERGENCY.md with printer
   troubleshooting (paper out, network unreachable, printer off).
6. Update docs/decisions_log.md with DEC-NNN.
7. Update R-012 to mark closed once printer round-trip tests pass.
8. Open PR with auto-merge enabled.

This task requires Opus reasoning.

STOP CONDITION: bench migrate for the new Label Template DocType. Bundle
into Phase 3 migrate window.
```

---

### T0-4 — Cash Drop Immutability After Save / Reconciliation

**Severity:** HIGH (verified — demoted from synthesis BLOCKER per Claude Code's `track_changes` recovery argument).

**Evidence (verified):** Cash Drop schema — only `reconciled`, `reconciliation`, `pos_closing_entry` are `read_only=1`. `declared_amount` and 7 other identity fields are mutable. Hamilton Operator has `read+write+create`.

**Why HIGH not BLOCKER:** `track_changes: 1` (cash_drop.json:167) records every edit; manager can audit via Activity tab. Not silent corruption. Still must close pre-launch.

**Claude Code prompt:**
```text
Lock Cash Drop financial fields after save (T0-4). Restores blind-cash
anti-tamper invariant per DEC-005. Bundle with T1-4 (same file).

Plan:
1. Add to cash_drop.py validate():
   _validate_immutable_after_save:
     If self.is_new() is False, fetch original via get_doc_before_save().
     frappe.throw if any of these fields changed: declared_amount,
     operator, shift_record, shift_date, shift_identifier, drop_type,
     drop_number, timestamp.

   _validate_immutable_after_reconciliation:
     If self.reconciled == 1, frappe.throw on ANY field change EXCEPT
     when frappe.flags.allow_cash_drop_correction is True.

2. Add whitelisted admin-correction endpoint:
   - Requires Hamilton Admin or System Manager role
   - Accepts cash_drop name, field, new_value, reason
   - Sets frappe.flags.allow_cash_drop_correction = True
   - Creates Hamilton Board Correction row with reason
   - Saves the Cash Drop with the new value
3. Tests in test_cash_drop.py:
   - test_cash_drop_declared_amount_immutable_after_first_save
   - test_cash_drop_all_fields_immutable_after_reconciliation
   - test_cash_drop_admin_correction_path_works
   - test_cash_drop_non_admin_cannot_correct
4. Update docs/decisions_log.md with DEC-NNN.
5. Update docs/permissions_matrix.md with corrections endpoint.
6. Open PR with auto-merge enabled.

This task is Sonnet-appropriate.

NO STOP CONDITION: controller-only change.
```

---

### T1-1 — Admission Gate + `assign_asset_to_session` Stub No-Op

**Severity:** HIGH (consensus; verified).

**Claude Code prompt:**
```text
Add server-side admission-item gate to submit_retail_sale and soften
assign_asset_to_session stub to no-op. T1-1.

Plan:
1. In submit_retail_sale (api.py around line 541, after cart-line
   validation), check each item: if frappe.db.get_value("Item",
   item_code, "hamilton_is_admission") is 1, frappe.throw with clear
   error "Admission items cannot be sold via the retail cart."
2. In assign_asset_to_session (api.py:259-268), replace hard-throw with:
   frappe.logger().warning(...) and return {"status": "phase_1_disabled"}.
3. Update CLAUDE.md noting standard /app/point-of-sale UI is unsupported
   for Phase 1 Hamilton operators.
4. Tests:
   - test_submit_retail_sale_rejects_admission_items
   - test_submit_retail_sale_accepts_retail_only_items
   - test_assign_asset_to_session_returns_phase_1_disabled
5. Update docs/decisions_log.md.
6. Open PR with auto-merge enabled.

This task is Sonnet-appropriate. NO STOP CONDITION.
```

---

### T1-2 — Drop `delete` from Admin on Audit Logs (BLOCKED ON T1-CORRECT)

**Severity:** HIGH. Sequenced AFTER T1-CORRECT design lands.

**Evidence (verified):** Asset Status Log Hamilton Admin row has `'delete': 1`. Comp Admission Log Hamilton Admin row has `'delete': 1`.

**Sequencing constraint (Claude Code addition):** Before removing `delete`, design the correction-without-delete pattern (T1-CORRECT below) so managers have an operational escape hatch for typos. Otherwise this fix creates an unfixable audit log.

**Claude Code prompt (run AFTER T1-CORRECT lands):**
```text
Drop delete permission from Hamilton Admin on Asset Status Log and Comp
Admission Log. Audit logs become append-only. T1-2.

PREREQUISITE: T1-CORRECT correction-without-delete pattern must be in
docs/decisions_log.md. Verify before starting.

Plan:
1. Edit asset_status_log.json permissions: remove "delete": 1 from
   Hamilton Admin row (set 0 or omit key).
2. Same edit on comp_admission_log.json.
3. Tests in test_security_audit.py:
   - test_asset_status_log_admin_cannot_delete
   - test_comp_admission_log_admin_cannot_delete
4. Update docs/permissions_matrix.md.
5. Update docs/decisions_log.md.
6. Open PR with auto-merge enabled.

This task is Sonnet-appropriate.

STOP CONDITION: bench migrate for permission changes. Bundle into Phase 3
window.
```

---

### T1-CORRECT — Audit Log Correction-Without-Delete Pattern (DESIGN ONLY)

**Severity:** HIGH (Claude Code addition). Pre-requisite to T1-2.

**Why:** Removing `delete` from Admin without providing an operational way to fix typos creates a brittle audit system. Managers will need to amend rows for legitimate reasons (operator typo, mis-attributed action).

**Claude Code prompt:**
```text
Design correction-without-delete pattern for Asset Status Log and Comp
Admission Log. Pre-requisite to T1-2. Docs only — no code, no schema.

Plan:
1. Read existing entries on Hamilton Board Correction DocType. It exists
   for asset-board corrections; evaluate if it can extend to audit logs.
2. Decide between two patterns:
   a. Add Long Text "correction_notes" field to each audit DocType,
      append-only via controller validation. Manager adds note explaining
      the error; original row stays intact.
   b. Create separate "Audit Log Correction" DocType linking back to the
      original row. Same append-only semantics, separate doctype keeps
      audit log row pristine.
3. Document decision in docs/decisions_log.md with DEC-NNN. Pattern (a)
   is simpler; pattern (b) preserves stricter audit-log immutability.
4. Update HAMILTON_LAUNCH_PLAYBOOK.md with the manager workflow ("how do
   I correct an audit row?").
5. Update docs/permissions_matrix.md describing the correction surface.
6. Open DOCS-ONLY PR with auto-merge enabled.

This task is Sonnet-appropriate.

NO STOP CONDITION: docs only.
```

---

### T1-3 TEST — Hamilton Operator Asset Board Read (Test First)

**Severity:** MEDIUM (verified — demoted; test required, fix conditional).

**Claude Code prompt:**
```text
T1-3 verification test. The synthesis claimed Hamilton Operator hits 403
on Asset Board load. Untested. Write the test before any fix.

Plan:
1. Add to test_security_audit.py:
   test_hamilton_operator_can_load_asset_board_data
   - Create a User with ONLY "Hamilton Operator" role (no extras)
   - frappe.set_user(this user)
   - Call hamilton_erp.api.get_asset_board_data
   - Assert response contains settings.grace_minutes
2. Run the test.
   - If PASSES: T1-3 closes as no-issue. Document in inbox.md.
   - If FAILS with PermissionError: T1-3 confirmed. Open follow-up PR
     adding Hamilton Operator read on Hamilton Settings (JSON change,
     bench migrate, bundle into Phase 3 window).
3. Update docs/decisions_log.md.
4. Open PR with the test (and conditional follow-up PR with the JSON
   change if needed).

This task is Sonnet-appropriate.

NO STOP CONDITION for the test PR. STOP CONDITION (bench migrate) on the
follow-up if it fires.
```

---

### T1-4 — Cash Drop Shift Validation + $5,000 Upper Bound

**Severity:** MEDIUM (verified — demoted; bundles A1 F3.4 $5,000 cap per Claude Code recommendation).

**Claude Code prompt:**
```text
Add shift validation + declared_amount upper bound to Cash Drop. T1-4
bundled with A1 F3.4. Same file as T0-4 — coordinate with that PR.

Plan:
1. Add to cash_drop.py validate():
   - _validate_shift_record_set: shift_record required
   - _validate_shift_is_open: linked Shift Record.status == "Open"
   - _validate_operator_matches_shift: Shift Record.operator ==
     self.operator
   - _validate_declared_amount_upper_bound: reject > $5000 with
     confirmation message ("If this is correct, contact Chris to
     override.")
2. Tests:
   - test_cash_drop_requires_shift_record
   - test_cash_drop_rejects_closed_shift
   - test_cash_drop_rejects_mismatched_operator
   - test_cash_drop_rejects_amount_above_5000
   - test_cash_drop_accepts_amount_at_or_below_5000
3. Update docs/decisions_log.md.
4. Open PR with auto-merge enabled.

This task is Sonnet-appropriate.

NO STOP CONDITION.
```

---

### T1-5 — Cash Reconciliation Uniqueness Per Drop

**Severity:** HIGH (verified).

**Claude Code prompt:**
```text
Prevent multiple Cash Reconciliations for same Cash Drop. T1-5.

Plan:
1. Add to cash_reconciliation.py before_submit:
   _validate_no_duplicate_reconciliation:
     existing = frappe.db.exists("Cash Reconciliation", {
       "cash_drop": self.cash_drop,
       "docstatus": 1,
       "name": ["!=", self.name]
     })
     if existing: frappe.throw with link to existing.
2. Tests:
   - test_cash_reconciliation_rejects_duplicate_submission
   - test_cash_reconciliation_first_submission_succeeds
3. Update docs/decisions_log.md.
4. Open PR with auto-merge enabled.

This task is Sonnet-appropriate. NO STOP CONDITION.
```

---

### T1-6 TEST — Audit Trail Enablement Post-Install

**Severity:** MEDIUM (verified — demoted).

**Claude Code prompt:**
```text
Add post-install audit-trail enablement test. T1-6.

Plan:
1. Add to test_fresh_install_conformance.py:
   test_audit_trail_enabled_post_install:
     assert frappe.db.get_single_value("System Settings",
       "enable_audit_trail") == 1
2. Update docs/runbooks/launch_day_rehearsal.md to manually verify the
   System Settings flag.
3. Open PR with auto-merge enabled.

This task is Sonnet-appropriate. NO STOP CONDITION.
```

---

### T1-7 — Lifecycle Rollback Regression Tests

**Severity:** MEDIUM (verified — demoted; forward-looking defense for Phase 2).

**Claude Code prompt:**
```text
Add lifecycle rollback regression tests. T1-7. Test-only.

Plan:
1. Add to test_adversarial.py:
   - test_start_session_rollback_on_set_asset_status_failure
     (monkey-patch lifecycle._set_asset_status to raise; call
     start_session_for_asset; assert no Venue Session exists, asset state
     unchanged)
   - test_vacate_session_rollback_on_close_session_failure
   - test_set_oos_rollback_on_close_session_failure
2. Update docs/decisions_log.md and coding_standards.md noting the
   no-catch-and-continue contract for lifecycle callers.
3. Open PR with auto-merge enabled.

This task is Sonnet-appropriate. NO STOP CONDITION.
```

---

### NEW-1 — `variance_amount` Calculation (Bundle into T0-2)

**Severity:** HIGH (Claude Code addition — separate from T0-2 root).

**Evidence (verified):** `cash_reconciliation.json:99-104` declares `variance_amount` as auto-calculated. `cash_reconciliation.py` has zero assignments to `self.variance_amount`. Manager sees $0.00 in the field.

**Fix:** Bundle into T0-2 PR. Add to `_set_variance_flag` or earlier:
```
self.variance_amount = flt(self.actual_count) - flt(self.system_expected)
```

---

### NEW-2 — `publish_realtime` Try/Except Wrap

**Severity:** HIGH (Claude Code addition — synthesis missed entirely).

**Evidence (verified):** `realtime.py:72-74`:
```python
frappe.publish_realtime(
    "hamilton_asset_status_changed", row, after_commit=True
)
```
No try/except. Frappe Cloud realtime hiccups → exception → operator response payload becomes a stack trace. DB has committed; Asset Board has stale state until manual refresh.

**Claude Code prompt:**
```text
Wrap publish_realtime in try/except. NEW-2. ~5 LOC.

Plan:
1. In hamilton_erp/realtime.py around line 72, wrap the
   frappe.publish_realtime call in try/except Exception:
   - On exception: frappe.log_error with title "publish_realtime failed
     for asset status change" and continue.
   - Asset Board's polling fallback heals the divergence on next refresh.
2. Add test:
   test_publish_realtime_swallows_redis_exception (monkey-patch
   frappe.publish_realtime to raise; call publish_status_change; assert
   no exception propagates).
3. Update docs/decisions_log.md.
4. Open PR with auto-merge enabled.

This task is Sonnet-appropriate. NO STOP CONDITION.
```

---

### COMP-RUNTIME — Verify Comp Admission Log Masking at Runtime

**Severity:** HIGH (Claude Code addition — fills static-vs-runtime verification gap).

**Claude Code prompt:**
```text
Verify Comp Admission Log.comp_value masking actually fires at runtime
for Hamilton Operator. Static JSON check is insufficient.

Plan:
1. Open existing TestCompAdmissionLogValueMasking in test_security_audit.py.
2. Confirm the test:
   a. Creates a User with ONLY Hamilton Operator role
   b. Calls frappe.set_user on that User before reading comp_value
   c. Asserts comp_value returns None (or masked) for that user
   d. Then calls frappe.set_user("hamilton_manager") and asserts the
      same field returns the actual value
3. If the test runs as Administrator instead of Hamilton Operator: fix it
   to genuinely exercise the operator runtime path.
4. Add a parallel test for the Manager-can-read positive path.
5. Open PR with auto-merge enabled.

This task is Sonnet-appropriate. NO STOP CONDITION.
```

---

## Tier 2 (Pre-Second-Venue, NOT Blocking Hamilton Launch)

These items remain deferred per the synthesis. Hamilton-only launch is safe; Philadelphia / DC / Dallas rollout is not until they close.

| Item | Source | Notes |
|---|---|---|
| **PR #100** Venue Session PII masking + encryption-at-rest (R-007) | All 4 reviewers | Block any second venue. |
| **Stack #3** Cash Drop field masking (Task 25 item 7) | Already in repo queue | Schedule supervised migrate. |
| **Customer link PII inheritance** | A1 F5.6 | Multi-venue refactor work. |
| **PIPEDA retention scheduler** | A3 inbox #5 | Phase 2 work. |

---

## Operational Mitigations Until Each Fix Lands

Until T0-1 ships: Train operators that "Sale failed" toast may mean "succeeded but network dropped." Verify SI exists in Desk before retrying.

Until T0-2 ships: Manual cash reconciliation per RUNBOOK_EMERGENCY.md.

Until T0-3 ships: **Cannot launch.** Hamilton operations cannot begin. R-012.

Until T0-4 ships: Manager reviews track_changes Activity tab on every Cash Drop during reconciliation.

---

## Fresh Claude Session Briefing

When Chris starts a new Claude Code session today, the standard `/start` command auto-reads `claude_memory.md`, `inbox.md`, and design docs per `CLAUDE.md`. This decisions document is in `docs/inbox/` so it surfaces during inbox triage.

**Recommended first action in the new session:**
```text
Read docs/inbox/2026-05-04_audit_synthesis_decisions.md in full. Confirm
you understand:
1. The Cash Reconciliation Phase 1 scope decision is required from me
   before T0-2 work.
2. T0-3 is hardware-dependent (Brother QL-820NWB) — confirm hardware
   status before scheduling.
3. Phase 2 controller-only fixes (T0-4, T1-4, T1-1, T1-5, NEW-2, T1-7,
   T1-3 test, COMP-RUNTIME, T1-CORRECT) can ship in parallel without
   bench migrate.
4. Phase 3 fixes consolidate into ONE supervised bench migrate window.

Then ask me which item to start with.
```

---

## Verification Provenance

This document reconciles:
- **A1** — Claude.ai chat audit (2026-05-03, 928 lines, 30 findings)
- **A2** — ChatGPT word-by-word audit (2026-05-03, 515 lines, 29 findings)
- **A3** — Claude Code self-audit (2026-05-02, 9 PRs #150-158 docs-only, 54 findings)
- **A4** — Claude Code verification (2026-05-03, 243 lines, verdicts on every Tier 0/1 item)

**Severity calls in this document follow A4's verification** where it disagreed with the synthesis, because A4 verified against live `main` (`4a7418d`) at the file:line level. A4's calibrated downgrades (T0-4, T1-3, T1-4, T1-6, T1-7) and additions (NEW-1, NEW-2, COMP-RUNTIME, T1-CORRECT) are all reflected here.

*End of decisions. Lock-step ship list. Auto-merge per CLAUDE.md template. Reads cleanly in a fresh Claude Code session.*
