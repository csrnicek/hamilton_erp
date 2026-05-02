# Asset Assignment Failure-Mode Audit — 2026-05-02

**Scope:** asset assignment lifecycle — `start_session_for_asset`, `vacate_session`, `mark_asset_clean`, `set_asset_out_of_service`, `return_asset_to_service` and the three-layer lock + realtime publish chain that supports them.

**Mindset:** assume the code is wrong until proven right. Hunt failure modes (race conditions, partial-failure scenarios, status-machine bypass, audit gaps), not happy paths.

**Method:** explore-pass over `lifecycle.py`, `locks.py`, `realtime.py`, `api.py` assignment endpoints, `Venue Asset` controller + `before_save` hook, `Venue Session` controller, `Asset Status Log` controller, `hooks.py` doc_events, and `decisions_log.md` Parts 4–5 (state machine + OOS workflow). Verified each high-severity claim against the actual cited lines before publishing — re-reading the lock module showed the explore agent had misread the `coding_standards.md §13.3` "zero I/O" rule as applying to the entire `with` body, when it applies only to the acquisition prologue (between `try:` at locks.py:92 and `yield rows[0]` at locks.py:107). Findings recalibrated accordingly.

**Severity counts:** **0 BLOCKER · 2 HIGH · 4 MEDIUM · 2 LOW.**

> No BLOCKER-rank findings in this audit. The lifecycle code's three-layer lock pattern (Redis advisory + MariaDB FOR UPDATE + version-CAS) is genuinely thorough; the most concerning issues here are the *post-commit* paths (realtime publish, audit log) and the perimeter (direct Frappe form edits bypassing helpers). Calibrated against the user's emergency criteria — no active data loss, no security hole, no launch BLOCKER — and the inventory is clean enough at the lifecycle core to support that judgment.

---

## HIGH

### H1 — `publish_realtime` has no error handling; Redis / socketio failure leaves the Asset Board diverged from the DB until a manual refresh

**File:** `hamilton_erp/realtime.py:72–74`

```python
frappe.publish_realtime(
    "hamilton_asset_status_changed", row, after_commit=True
)
```

**Failure scenario.** Operator vacates locker L029. The transaction commits; status flips to `Dirty` in the DB. `publish_status_change` runs `after_commit=True`. The realtime queue write fails — Redis socketio is unreachable (Frappe Cloud incident, transient outage, restart window). The call silently fails (or the after_commit queue swallows it). The Asset Board client never receives the event. From the operator's perspective, L029 is still rendered as `Occupied` until they manually refresh the page. They click `Vacate` again and get `LockContentionError: Asset L029 is being processed` (because the asset is now `Dirty`, not `Occupied`, so the API correctly rejects it — but the *error message* talks about contention, not state).

**Why it's allowed.** The function-level docstring (`realtime.py:42–46`) explicitly notes the no-op-on-deleted-row behavior is the correct trade-off for an `after_commit` publish path: raising would surface a confusing error for a state change that already committed. But the docstring does *not* anticipate the case where `frappe.publish_realtime` itself raises (queue full, Redis down, payload too large). There is no `try/except` wrap; an exception at line 72 propagates to the lifecycle caller, which is past the lock release and past the transaction commit. The exception lands in the operator's response payload as a stack trace — the DB is correct, but the operator sees an error.

**Recommended fix (do not implement tonight).** Wrap `frappe.publish_realtime` in a `try/except`, log via `frappe.log_error`, and accept the temporary divergence. The Asset Board's polling fallback (DEC-061 design intent — *L1 — Asset Board client-side reconciliation*) will heal on next refresh. Optional: enqueue a backfill job to retry the publish out-of-band.

### H2 — Direct Frappe form edits on Venue Asset bypass lifecycle helpers; reason / current_session / status-log can drift

**Files:** `hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py:19–47` (validate hook); `hamilton_erp/lifecycle.py:255–259` (reason management).

**Failure scenario.** A user with `write` permission on `Venue Asset` (Hamilton Admin role, per the perm grid) opens the form for L029 and manually changes status from `Out of Service` → `Available` to bypass a stuck lifecycle. The `validate_status_transition` hook (`venue_asset.py:25–47`) allows this transition (it's a legal state-machine edge). The form save commits. But:

- The `reason` field carries over from the OOS state (lifecycle.py only clears it on the API-driven path at lines 257–259).
- No `Asset Status Log` row is created (lifecycle helpers create those; the `before_save` hook doesn't).
- No `publish_realtime` event fires (lifecycle calls it explicitly *after* lock release).
- `current_session` is whatever it was before the manual edit (could be a stale completed-session pointer if anything's gone weird).

**Result:** the asset is `Available` in the DB, but the audit trail says it's still `Out of Service`. The Asset Board never receives a status-changed event so the tile doesn't update. The `reason` field still shows the old OOS reason.

**Why it's allowed.** The lifecycle helpers (`_set_asset_status`, `_make_asset_status_log`, `publish_status_change`) are imperative, not declarative. They live outside the DocType controller. The `before_save` hook (`venue_asset.py:19–22`) only updates `hamilton_last_status_change`; it does not write the status log, clear `reason`, or fire realtime events. So the only place that maintains the full invariant set is the lifecycle API layer.

**Impact bounding.** Hamilton Operator does not have `write` perm on Venue Asset (verified — they have row-level read via the perm grid but go through whitelisted endpoints for state changes). Hamilton Admin does. So this is a *privileged-user-causes-corruption* path, not an ops-floor risk. But that's exactly the user most likely to "just fix it manually" during an incident.

**Recommended fix.** Move the post-status-change invariants into the `before_save` / `on_update` controller methods, so any form edit that changes `status` triggers them. Specifically: clear `reason` when `status` changes away from `Out of Service`; create an `Asset Status Log` row whose `operator` is `frappe.session.user` and whose `reason = "Manual form edit by {user}"` so the audit trail captures the bypass; fire `publish_status_change` from the controller. Keep the lifecycle helpers as the canonical API path; the controller is the safety net for direct edits.

---

## MEDIUM

### M1 — Lock TTL (15s) is shorter than worst-case critical-section latency; lock can expire while the operation is still running

**File:** `hamilton_erp/locks.py:27` (LOCK_TTL_MS) and `locks.py:108–124` (TTL-expiry detection in `finally`).

The Redis lock has a 15s TTL. The MariaDB `FOR UPDATE` row lock at `locks.py:96–104` provides the second layer of serialization, so even if the Redis TTL elapses, the FOR UPDATE blocks the next caller until the transaction commits. The release-time `cache.get(key) != token` check (`locks.py:108–117`) logs a warning when this happens.

**Failure scenario.** Critical section runs >15s under load (slow DB, scheduler tick congestion, ERPNext stock validation walking a long Bin chain). The Redis lock expires. A second caller's Redis acquire succeeds. They issue their `SELECT ... FOR UPDATE`, MariaDB blocks them. First caller commits and releases the FOR UPDATE; second caller proceeds. **Data integrity is preserved** (FOR UPDATE serialized them), but the version-CAS check inside `_set_asset_status` is the only thing protecting against the second writer reading the pre-commit row state. If the second writer's read happened to land *between* the first caller's UPDATE and COMMIT (unusual under InnoDB's read-committed isolation but observable on read-uncommitted setups), they could see a half-applied state.

**Why it's allowed.** The 15s TTL is heuristic. Production-load measurements haven't been published. The `try/except` at `locks.py:117` catches Redis faults during the expiry check.

**Recommended fix.** Measure P99 critical-section latency in CI / production logs; size `LOCK_TTL_MS` to 2× P99. Optionally implement lock re-extension for long sections (acquire → start work → periodic refresh → release).

### M2 — `publish_status_change`'s session lookup is unprotected against concurrent session deletion; Occupied tile renders without the overtime ticker

**File:** `hamilton_erp/realtime.py:66–72`

```python
if row["status"] == "Occupied" and row.get("current_session"):
    row["session_start"] = frappe.db.get_value(
        "Venue Session", row["current_session"], "session_start"
    )
```

**Failure scenario.** The asset row at line 47 is read at time T. The session row at line 68 is read at time T+ε. Between those two reads, an admin deletes the session row directly via SQL or a Frappe form (rare but possible). Line 68 returns `None`. The published event has `session_start=None`. The Asset Board renders the tile as `Occupied` but the overtime ticker (`Xm late` / `Xm left`) is blank. Operator can't tell at-a-glance whether the room is overtime.

**Why it's allowed.** The two reads are not in a transaction together. The publish path runs `after_commit` and is intentionally I/O-tolerant.

**Recommended fix.** Read both rows in a single SELECT with a JOIN, or wrap the two reads inside one short read transaction. Alternatively: log a warning when `session_start` resolves to `None` for an `Occupied` asset (signal of upstream data corruption).

### M3 — `_make_asset_status_log` returns `None` in test mode; tests cannot easily assert audit-log creation, masking regressions

**File:** `hamilton_erp/lifecycle.py:85–87`

```python
if frappe.in_test:
    return None
```

**Failure scenario.** A future PR refactors `_set_asset_status` and accidentally drops the `_make_asset_status_log` call. CI runs the lifecycle test suite. Every test still passes — because `_make_asset_status_log` was returning `None` anyway in test mode, the absence of the call is invisible. The PR ships. In production, status changes commit but no `Asset Status Log` rows are written. PIPEDA / audit-trail invariants silently break. A manager doing reconciliation finds the audit trail is empty and panics; the dev team can't reproduce because tests pass.

**Why it's allowed.** The skip was added (per the docstring at `lifecycle.py:80–86`) to reduce test noise from log-row creation. Tests that assert log creation must `setUp/tearDown` toggle `frappe.in_test` themselves. This is opt-in and easy to forget.

**Impact bounding.** This is a test-fidelity issue, not a runtime bug. Production code creates the logs. But it weakens CI as a regression detector for the audit-log invariant.

**Recommended fix.** Remove the `if frappe.in_test: return None` short-circuit. Tests that don't care about log rows can ignore them; tests that need to assert non-creation can use a fixture-cleanup helper. Alternatively: keep the skip but add a CI gate that runs the suite with `frappe.in_test = False` for the `lifecycle` and `audit` test modules specifically.

### M4 — OOS-from-Occupied auto-closes the session; a concurrent `Vacate` from a stale UI raises a confusing error

**File:** `hamilton_erp/lifecycle.py:440–449` (OOS auto-close), `lifecycle.py:357–359` (vacate session-state guard).

**Failure scenario.** L029 is `Occupied` with `current_session=S1`. Operator A clicks `Set OOS`. The asset lock serializes; OOS auto-closes S1 with `vacate_method="Discovery on Rounds"`. Asset is now `Out of Service`, S1 is `Completed`.

Meanwhile, Operator B is looking at a board snapshot from before A's action (their realtime event was queued but not yet rendered). They click `Vacate` on L029. Their request hits the API, acquires the asset lock (now released by A), sees `status=Out of Service`. The vacate path checks `asset.status == "Occupied"` (it isn't), and raises a `ValidationError`. The error message is technically correct but operator-hostile: it doesn't explain that *another operator just took the locker out of service*.

**Why it's allowed.** The state-machine guard fires correctly. The error message is generic.

**Recommended fix.** When `vacate_session` rejects because status is now `Out of Service`, raise a specific error: "L029 was set Out of Service by {user} at {timestamp} — vacate is no longer needed." Surface the OOS reason if available. Same shape for the `mark_asset_clean` and `return_asset_to_service` reject paths.

---

## LOW

### L1 — `Asset Status Log` does not record `venue_session` for OOS-from-Available transitions; a session that just closed is not linked to the OOS log

**File:** `hamilton_erp/lifecycle.py:449–453`

When an asset transitions Available → Out of Service, the log row is written with `venue_session=None` (because no session is currently active). This is correct under the existing schema, but it means that an auditor reviewing "L029 was put OOS at 02:30 — why?" can't easily walk back to "the most recent session ended at 02:25 with vacate_method=Key Return" — the log row has no breadcrumb to that session.

**Recommended fix.** Optional design enhancement: when entering OOS from Available, log the most recent `Asset Status Log` entry id (or session) as a "preceding-session-context" reference. Architectural; not a bug.

### L2 — `Venue Asset.current_session` is a Frappe Link, no DB-level foreign key; orphan possible if a session is deleted out-of-band

**File:** `hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.json` (field definition).

Frappe Link fields are validated at app level (on save), not at the DB level. Direct SQL deletion of the linked Venue Session leaves `Venue Asset.current_session` pointing at a non-existent row. The realtime payload's session_start lookup (M2) returns `None`; the lifecycle vacate path's `_close_current_session` would raise `frappe.DoesNotExistError`. Real impact requires someone to delete a session row out-of-band — not impossible (data corruption recovery, manual SQL during incident response).

**Recommended fix.** Either (a) add a DB FK constraint via a one-shot migration, or (b) accept the limitation and add defensive checks in the consumers (already present for `vacate`; missing for the realtime payload).

---

## Categories with no findings

- **Status-machine bypass via the API.** All assignment endpoints route through `lifecycle.py` helpers, which delegate state validation to `validate_status_transition` in `venue_asset.py`. The state edges in `decisions_log.md §4` are honored. No findings.
- **Lock-not-acquired silent failure.** `locks.py:80–91` raises `LockContentionError` with a translatable operator-facing message when Redis SET NX fails. The MariaDB FOR UPDATE at `locks.py:96–104` then provides a second-layer block. No silent failures.
- **Permission gates on assignment endpoints.** Whitelisted endpoints in `api.py` apply role checks before delegating to lifecycle. Hamilton Operator role is granted only via these endpoints (no direct write on Venue Asset / Venue Session). No findings.
- **Lifecycle hook ordering / `before_save` write-wars.** Only `before_save` writer is `venue_asset.py:19–22` (sets `hamilton_last_status_change`). Lifecycle.py writes happen before the `save` call, not concurrently. No write-war found.
- **OOS workflow integrity (reason capture, log row, status flip atomicity).** `set_asset_out_of_service` performs the three steps inside the lock, all in one transaction. Reason validation is at line 411–419. No gap found.

---

## Cross-references

- Audit 1 (`docs/audits/2026-05-02_payment_pos_failure_modes.md`) **H5** is the same root concern as **M1** here — lock TTL ceiling. Fix once, applies to both.
- `docs/decisions_log.md §4` (state machine) and `§5` (OOS workflow) are the canonical contracts the lifecycle code implements. Both are honored.
- `docs/coding_standards.md §13.3` (zero-I/O lock prologue) is correctly applied at `locks.py:93–107`.
- The `_make_asset_status_log` test-skip pattern (M3) was introduced before the audit-log audit (this audit's sibling, in progress). Cross-check both audits for follow-up.

---

## What I did NOT audit

- The Asset Board frontend (HTML/JS) — out of scope for this server-side audit. H1's user impact assumes the board's polling fallback exists; if it doesn't, H1 escalates.
- ERPNext core's transaction model — assumed correct.
- Frappe's realtime queue internals — assumed best-effort delivery.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
