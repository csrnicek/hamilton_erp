# Audit Log Coverage Audit — 2026-05-02

**Scope:** Hamilton's audit-trail surface. Two audit mechanisms are in play: (a) `Asset Status Log` and `Comp Admission Log` — Hamilton-owned DocTypes that explicitly record state-change events, and (b) Frappe's `track_changes: 1` per-DocType flag, which writes a `Version` doc capturing field-level deltas. Verify coverage, append-only enforcement, who can edit/delete log rows, and whether silent-failure paths leak un-audited state changes.

**Mindset:** an audit log is only as good as its weakest tamper-window. Hunt: writes that bypass the log helpers, roles that can delete log entries, failed-action paths that produce no audit, and retention gaps.

**Method:** enumerated every Hamilton-owned DocType's `track_changes` setting and `permissions` array; identified all callers of `_make_asset_status_log`; checked `lifecycle.py` for state-change paths that don't pass through the log writer; grepped for `frappe.db.set_value`, `frappe.db.sql ... UPDATE`, and direct `.save()` on Venue Asset.

**Severity counts:** **0 BLOCKER · 3 HIGH · 4 MEDIUM · 1 LOW.**

---

## HIGH

### H1 — Hamilton Admin has DELETE on Asset Status Log; the audit-trail-of-record can be erased by the role most likely to want to

**Files:** `hamilton_erp/hamilton_erp/doctype/asset_status_log/asset_status_log.json` (perm grid); `docs/permissions_matrix.md:18–20`.

```
| Asset Status Log | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |
                                                ^ delete
```

**Failure scenario.** Hamilton Admin (Chris, today; potentially other admins later if the role is granted) makes an operational mistake at 2am — accidental OOS that takes a popular locker offline at peak. They want it to go away. The lifecycle helpers don't expose a "delete log row" path, but Admin has DocType-level delete on Asset Status Log. They open the row in the Frappe Desk and click Delete. The row is gone. The audit trail no longer reflects the incident.

PIPEDA Principle 8 (openness) and Principle 9 (individual access) implicitly require that audit records exist when a customer asks "what happened with my session" — a deleted log can't answer.

**Why it's allowed.** The matrix (line 20) explicitly grants `delete` to Hamilton Admin on Asset Status Log. This is consistent with the "Admin = full perms" pattern but at odds with the audit trail's append-only intent.

**Concrete tamper window.** Even if Admin honors the convention and never deletes, their session is a target. Anyone who compromises an Admin account can erase the record of their own activity. Defense-in-depth says the role with the most reason to want to tamper should not have the means.

**Recommended fix.** Drop `delete` from Hamilton Admin's row on Asset Status Log. If a true log-row deletion is needed (regulatory takedown, etc.), require System Manager (Chris-only). Add a regression test in `test_security_audit.py` that asserts no Hamilton-prefixed role has `delete` on Asset Status Log.

### H2 — Hamilton Admin has DELETE on Comp Admission Log; same tamper-window class as H1

**Files:** `hamilton_erp/hamilton_erp/doctype/comp_admission_log/comp_admission_log.json` (perm grid).

Same pattern as H1: Hamilton Admin has rwcd on Comp Admission Log, the audit log for free-admission events. The matrix at line 24 confirms.

**Failure scenario.** A series of comp admissions look suspicious in a manager review (e.g., the same operator comping the same VIP every Friday for three months). Operator escalates to Admin. Admin "cleans up" by deleting the suspicious log rows. Forensic trail is broken.

**Why it's allowed.** Same as H1: convention says Admin gets full perms.

**Recommended fix.** Same as H1: drop `delete` from Hamilton Admin's row on Comp Admission Log. System Manager only.

### H3 — Failed status transitions and rejected mutations produce zero audit rows; silent failures invisible to forensic review

**Files:** `hamilton_erp/lifecycle.py:107–273` (lock-acquisition raises before any log write); `hamilton_erp/locks.py:80–91` (LockContentionError raised pre-yield).

**Failure scenario.** Operator A is trying to vacate locker L029. Operator B is concurrently trying to set it OOS. The asset lock serializes them; one succeeds and the other gets `LockContentionError`. Operator B retries. Lock contention again. They retry 4 times. From the user's perspective: they see the error 4 times. From the audit log's perspective: **nothing**. Asset Status Log only records *successful* state changes; failed acquisitions raise before the log writer is reached.

Forensic question: "Were there a lot of contention errors at peak last Friday?" Answer: nobody knows, because failed attempts aren't logged.

**Why it's allowed.** The lifecycle helper writes Asset Status Log only after `_set_asset_status` succeeds. Failed-attempt logging would require either an event-log doctype (separate from Asset Status Log, which is a state-change record) or warning-level entries via `frappe.logger().warning` — there's already a TTL-expiry warning at `locks.py:121–124` but no per-contention log.

**Recommended fix.** Two options, decide based on operational telemetry needs:

1. **Application-log path:** add `frappe.logger().info` or `warning` for every `LockContentionError` raised, including asset_name + caller_user. Cheap, doesn't bloat Asset Status Log, queryable via standard log tooling.
2. **Operational metric:** create an `Asset Lock Event Log` DocType that records every acquire-attempt (successful + contended). Heavier, but enables Manager-side dashboards. Probably overkill for Phase 1.

The application-log path is the recommended Phase 1 fix; the metric DocType is a Phase 2 candidate.

---

## MEDIUM

### M1 — `_make_asset_status_log` returns `None` in test mode; the only mechanism that catches "we forgot to log" regressions is opt-in to test setUp/tearDown

**File:** `hamilton_erp/lifecycle.py:85–87`. **CROSS-REF Audit 2 M3** — same finding from a different angle.

In production, every state change writes a log row. In CI, the writer short-circuits. A future PR could remove or rename the `_make_asset_status_log` call and CI would still go green (because the call's absence and the call's no-op test-mode behavior look identical). This audit-trail invariant has no automated guard.

**Recommended fix.** See Audit 2 M3. Either remove the test-mode skip (preferred) or add a CI gate that runs the lifecycle suite with `frappe.in_test = False`.

### M2 — `_set_vacated_timestamp` and `_set_cleaned_timestamp` write to Venue Asset without producing audit-log rows of their own

**Files:** `hamilton_erp/lifecycle.py:368–401` (the timestamp helpers).

These helpers update `last_vacated_at` and `last_cleaned_at` on the Venue Asset row. They are called *inside* the lock body, after the parent state change has been logged via `_make_asset_status_log`. The state change ("Occupied → Dirty" or "Dirty → Available") is in the log; the *timestamp write* itself is a side effect of that state change and is captured in the Frappe Version row (track_changes=1 on Venue Asset). So the data IS audited, just by a different mechanism.

**Failure scenario.** A maintenance script or future custom hook calls `_set_cleaned_timestamp` directly without the surrounding state change. The asset's `last_cleaned_at` updates without an Asset Status Log row. The Frappe Version still records the field change, but anyone querying Asset Status Log for cleaning history won't see it.

**Why it's allowed.** The timestamp helpers are scoped as private helpers of the lifecycle module; the assumption is they're only called from within state transitions that already wrote logs. The convention isn't enforced — it's documented in the docstring.

**Recommended fix.** Either (a) make the timestamp helpers private-by-convention with a leading-underscore + `# Internal: only call from within logged state transitions` comment that's currently missing, or (b) have them write a small "field-update" Asset Status Log row tagged as a field-level change rather than a status transition. Probably (a) — the Frappe Version mechanism already covers the field change.

### M3 — No retention or purge policy for audit logs; PIPEDA Principle 5 cannot be enforced for audit data either

**CROSS-REF Audit 5 H4** — same gap, different surface.

Asset Status Log, Comp Admission Log, Frappe Version rows all accumulate forever. PIPEDA's retention principle applies to audit data when the audit data contains PII (e.g., a Comp Admission Log row's `operator` Link can be traced to a User record with PII). Hamilton has no automated purge.

**Recommended fix.** Same as Audit 5 H4 — Phase 2 scheduler job that walks audit-log DocTypes and purges/anonymizes per a retention policy that needs to be written. The policy will need to balance PIPEDA's "limit retention" with operational forensics needs (Hamilton wants 6 months of forensics; PIPEDA wants minimum-necessary).

### M4 — Frappe Version rows from track_changes also accumulate without retention

**Files:** every Hamilton-owned DocType with `track_changes: 1` (verified all 8 except Asset Status Log itself).

Frappe's `Version` doc captures field-level diffs. With `track_changes: 1`, every save creates one. At Hamilton's projected volume (hundreds of asset state changes per day across 59 assets, plus shift / drop / reconciliation churn), Version table grows by ~5,000 rows/day. After a year: ~1.8M Version rows.

**Failure scenario.** Production performance degradation as `tabVersion` grows. Frappe's "View History" widget on doc forms gets slow. Audit queries get slow. Backups get larger.

**Why it's allowed.** Frappe doesn't ship a default Version-table purge job. Each app is responsible for its own retention.

**Recommended fix.** Phase 2: include Version-table purge in the same retention scheduler as M3. Probably a 1-year window that aligns with PIPEDA discussions plus a backup-retention overlap. Document the decision in `decisions_log.md`.

---

## LOW

### L1 — Cash Reconciliation cancel/amend uses Frappe native `docstatus` logging only; no Hamilton-specific cancel-audit format

**File:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.json` (`is_submittable: 1`); Frappe core handles cancel via docstatus.

Cancel events on Cash Reconciliation are captured by Frappe's standard cancel mechanism: docstatus 1→2 transition, `modified`, `modified_by` updated. There's no Hamilton-specific "this reconciliation was cancelled because…" audit log. Adequate for the current scale; flagging in case Hamilton wants richer cancel-cause forensics later (e.g., "cancelled because manager realized typo" vs "cancelled because dispute opened").

**Recommended fix.** If/when this becomes operationally important, add a `cancellation_reason` Text field on Cash Reconciliation and require it to be set before cancel via a `before_cancel` hook. Phase 2 candidate.

---

## Categories with no findings

- **`Asset Status Log` is read-only for non-Admin roles.** Hamilton Operator and Hamilton Manager have only `read`. They cannot tamper with their own audit trail. Verified at lines 18–19 of `permissions_matrix.md` and the JSON.
- **`track_changes: 1` coverage on operational DocTypes.** All Hamilton-owned DocTypes except Asset Status Log itself have `track_changes: 1`. Asset Status Log correctly has `track_changes: 0` (it IS the audit trail; tracking changes-to-the-trail is a meta-log Hamilton doesn't need at Phase 1 scale).
- **Comp Admission Log writer audit.** Comp Admission Log IS the audit trail for comp events. It writes itself. No need for a meta-log.
- **Submit/cancel/amend on submittable DocTypes.** Cash Reconciliation is the only submittable Hamilton DocType in Phase 1. Frappe's native docstatus mechanism captures the lifecycle transitions. Adequate.
- **Operator-of-record on every audit row.** Asset Status Log, Comp Admission Log, Cash Drop, Cash Reconciliation, Shift Record all have `operator` (or equivalent) Link fields. The audit trail can identify who took action. (See Audit 3 H2 for the auto-set / validation gap on this field.)
- **Doc-event hooks for cross-DocType audit triggers.** `hooks.py` doc_events list is small and explicit; no hidden side-effect chains that could write audit rows out-of-band.

---

## Cross-references

- **Audit 2 M3** — `_make_asset_status_log` test-mode skip. Same finding, this audit's M1.
- **Audit 5 H4** — no retention/purge code. Same root cause, this audit's M3 and M4.
- **Audit 3 H2** — operator field auto-set / validation. The audit log identifies operator via that field; if the field can be falsified, the audit identifies the wrong person.

---

## What I did NOT audit

- **Frappe core's audit mechanisms** — `Activity Log`, `Communication`, `Comment`, etc. Out of scope for the Hamilton-side audit.
- **Backup integrity / restore-time audit.** Runbook 8 (backup/restore drill) covers this from a different angle.
- **Per-field permlevel masking on audit logs.** Comp Admission Log's `comp_value` is the only masked field on a log DocType (Audit 5 confirmed). Asset Status Log has no field-level masking; whether `reason` should be masked from Operator is a follow-up.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
