# Hamilton ERP — Expert Testing Checklist
**Source:** Research from Redis.io, Martin Kleppmann (Designing Data-Intensive Applications),
FSM testing literature, and project-specific gaps identified during 3-AI reviews.
**Updated:** 2026-04-10 after Tasks 1-5

---

## Category 1: State Machine Coverage (Academic Standard)
*Source: IET Software FSM coverage criteria research + state machine testing best practices*

The academic standard for FSM test coverage requires ALL of the following:

### 1a. All-states coverage (already have this ✅)
Every state must be reached by at least one test.
- Available ✅, Occupied ✅, Dirty ✅, Out of Service ✅

### 1b. All-transitions coverage (partially have this)
Every defined transition must be exercised by at least one test.
| Transition | Test exists? |
|---|---|
| Available → Occupied | ✅ test_available_to_occupied |
| Available → Out of Service | ✅ test_available_to_oos |
| Occupied → Dirty | ✅ test_occupied_to_dirty |
| Occupied → Out of Service | ✅ test_occupied_to_oos |
| Dirty → Available | ✅ test_dirty_to_available |
| Dirty → Out of Service | ✅ test_dirty_to_oos |
| Out of Service → Available | ✅ test_oos_to_available |

**Missing:** All invalid transitions rejected (partially covered, needs systematic check)

### 1c. Invalid transition rejection (must test ALL invalid transitions)
For every state, test that every undefined transition is rejected:
- [ ] Available → Dirty (should fail)
- [ ] Available → Available (no-op, should fail or be ignored)
- [ ] Occupied → Available (must go through Dirty first)
- [ ] Occupied → Occupied (double-assign, should fail)
- [ ] Dirty → Occupied (must clean first)
- [ ] Dirty → Dirty (no-op, should fail)
- [ ] Out of Service → Occupied (must go Available first)
- [ ] Out of Service → Dirty (must go Available first)
- [ ] Out of Service → Out of Service (already OOS, should fail)

### 1d. Guard condition boundary tests
*Source: State machine testing best practices — guards that are always true/false are modeling errors*
- [ ] OOS reason = exactly 1 character (minimum valid)
- [ ] OOS reason = 500 characters (maximum, should pass)
- [ ] OOS reason = 501 characters (should this fail? Define the limit)
- [ ] Status transition with version = 0 (initial)
- [ ] Status transition with version = MAX_INT (overflow risk)

### 1e. Entry/exit action verification
*Source: Expert FSM testing — entry/exit actions are first-class behaviors, not side effects*
- [ ] After Available→Occupied: verify hamilton_last_status_change is set ✅ (partial)
- [ ] After Occupied→Dirty: verify last_vacated_at is set (MISSING)
- [ ] After Dirty→Available: verify last_cleaned_at is set (MISSING)
- [ ] After Any→OOS: verify reason is persisted on asset row (MISSING)
- [ ] After OOS→Available: verify reason is cleared (MISSING — Task 8)
- [ ] version field increments on every status change (MISSING)

---

## Category 2: Distributed Lock Correctness
*Source: Redis.io distributed locks documentation + Martin Kleppmann "How to do distributed locking"*

### 2a. Mutual exclusion (have basic version ✅)
- ✅ test_second_acquisition_raises (same asset, same operation)
- ✅ test_different_operations_on_same_asset_are_serialized (different operations)

### 2b. Failure modes (MISSING — critical)
*These are the scenarios Kleppmann identifies as most dangerous in production:*
- [ ] **Redis down at acquire time** → should get clean LockContentionError, not ConnectionError crash
- [ ] **Redis down at release time** → lock should TTL out, not mask the original exception
- [ ] **Redis restart while lock is held** → key disappears, next caller can acquire (verify this is safe)
- [ ] **Lock expires during slow DB operation** → MariaDB FOR UPDATE still serializes (verify DB layer holds)
- [ ] **Stale token attack** → Process A's expired lock cannot delete Process B's live lock (Lua CAS test)

### 2c. Lock release guarantees (MISSING)
*Source: redis-py test suite patterns*
- [ ] Exception raised INSIDE the `with` block → lock still released (finally block test)
- [ ] frappe.throw() inside the `with` block → lock still released
- [ ] Missing asset (asset_name doesn't exist) → lock released before error propagates
- [ ] DB deadlock inside the `with` block → lock released

### 2d. Idempotency and re-entrancy
- [ ] Same process tries to acquire lock it already holds → second acquire raises LockContentionError
      (this is intentional — our lock is NOT re-entrant, and a test should prove it)

### 2e. Key correctness
- [ ] Lock key format is exactly `hamilton:asset_lock:{asset_name}` (no operation suffix)
- [ ] Two different assets can be locked simultaneously without blocking each other
- [ ] Lock key is cleaned up from Redis after successful release (no key leak)
- [ ] Lock key is cleaned up from Redis after exception (no key leak)

---

## Category 3: Session Lifecycle Correctness
*Source: Project-specific gaps from 3-AI reviews*

### 3a. Session creation integrity
- [ ] start_session creates exactly ONE Venue Session (not zero, not two)
- [ ] session_number format matches DEC-033: `{d}-{m}-{y}---{NNN}` (MISSING)
- [ ] session_number is unique — two sessions on same day get different numbers (MISSING)
- [ ] session_number resets to 001 on a new day (MISSING)
- [ ] Walk-in customer default is set correctly on session
- [ ] operator field is populated on session

### 3b. Vacate integrity
- [ ] Vacate with vacate_method="Key Return" closes session correctly
- [ ] Vacate with vacate_method="Discovery on Rounds" closes session correctly  
- [ ] Vacate with invalid vacate_method raises ValidationError ✅
- [ ] Double-vacate (vacate already-Dirty asset) raises clean error ✅ (test_vacate_rejects_non_occupied)
- [ ] After vacate: asset.current_session is None (session link cleared)
- [ ] After vacate: Asset Status Log entry links to the CLOSED session (not None)
- [ ] After vacate: venue_session.status is "Closed" or equivalent

### 3c. Asset Status Log completeness
- [ ] Log entry created on every transition (not just some)
- [ ] Log previous_status matches asset's actual previous status
- [ ] Log new_status matches asset's actual new status
- [ ] Log operator is populated
- [ ] Log timestamp is recent (within 1 second of operation)
- [ ] Bulk clean log entries have distinguishing reason string (DEC-054)

---

## Category 4: Concurrency and Race Conditions
*Source: Distributed systems best practices*

### 4a. Double-booking prevention (the #1 production risk)
- [ ] Two threads simultaneously call start_session on same asset → exactly ONE succeeds
- [ ] Two threads simultaneously call vacate on same occupied asset → exactly ONE succeeds
- [ ] Two threads simultaneously call mark_clean on same dirty asset → exactly ONE succeeds

### 4b. Version field optimistic locking
- [ ] version field starts at 0 on new assets (MISSING)
- [ ] version increments by 1 on every status change (MISSING)
- [ ] Stale version check: if caller reads version=3 but DB has version=4, the CAS should fail (MISSING)

### 4c. Bulk clean concurrency
- [ ] Bulk clean on 33 lockers acquires and releases 33 locks in sorted name order (deadlock prevention)
- [ ] If one lock fails during bulk clean, remaining assets continue (no abort)
- [ ] Failed assets in bulk clean are reported at the end

---

## Category 5: Data Integrity
*Source: Project-specific requirements from DEC-019, DEC-031, DEC-033, DEC-054, DEC-055*

### 5a. Timestamp fields
- [ ] last_vacated_at is populated after vacate (MISSING)
- [ ] last_cleaned_at is populated after mark_clean (MISSING)
- [ ] hamilton_last_status_change is populated after every status change (partial ✅)
- [ ] hamilton_last_status_change is set on initial insert (MISSING)

### 5b. Referential integrity
- [ ] Asset.current_session is None when Available or Dirty (MISSING enforcement)
- [ ] Asset.current_session is set when Occupied (MISSING enforcement)
- [ ] Closing a session that doesn't exist fails cleanly (no silent corruption)

### 5c. Seed data integrity (Task 11)
- [ ] Exactly 59 assets created (R001-R026 + L001-L033)
- [ ] All assets start as Available
- [ ] Walk-in Customer record exists before any session can be created
- [ ] Hamilton Settings singleton exists with valid defaults
- [ ] No duplicate asset_codes

---

## Priority: When to add these tests

### Add during Tasks 6-9 (as each function is implemented):
- 1e (entry/exit actions — timestamps, version increment)
- 3a (session creation integrity)
- 3b (vacate integrity completeness)
- 3c (Asset Status Log completeness)

### Add during Task 11 (seed patch):
- 5c (seed data integrity)

### Add as a hardening pass after Task 9:
- 1c (all invalid transitions systematic)
- 2b (Redis failure modes)
- 2c (lock release guarantees)
- 4a (double-booking prevention threads)
- 4b (version field optimistic locking)

### Add during Task 25 (pre-deploy):
- 2e (key correctness / no key leaks)
- 5a (timestamp fields complete)
- 5b (referential integrity)

---

## How to use this checklist

When starting each task, tell Claude Code:
> "Check docs/testing_checklist.md and add any relevant tests from the checklist
> that apply to this task."

This ensures the checklist drives test additions naturally as each feature lands.


---

## Category 6: Frappe/ERPNext-Specific Edge Cases
*Source: Direct analysis of frappe/frappe and frappe/erpnext v16 test suites*

### 6a. Savepoint and transaction rollback patterns
*Source: frappe/tests/test_db.py — test_savepoints, test_savepoints_wrapper, test_pk_collision_ignoring*

Frappe uses savepoints for partial rollback within a transaction.
Our lifecycle functions must handle these correctly:

- [ ] **Savepoint rollback** — if a lifecycle function fails partway through, the partial DB writes
      are rolled back but the Redis lock is still released (our `finally` handles this, but test it)
- [ ] **PK collision** — if two sessions try to create a Venue Session with the same name simultaneously,
      the second should get `frappe.DuplicateEntryError`, not a silent corruption
      Pattern from Frappe: `with savepoint(): self.assertRaises(frappe.DuplicateEntryError, doc.insert)`
- [ ] **Transaction write counting** — `frappe.db.transaction_writes` should not grow unboundedly
      during a single lifecycle operation (guards against N+1 write patterns)
- [ ] **before_commit/after_commit callbacks** — verify that `publish_realtime` fires in
      `after_commit`, NOT before (coding_standards.md §13.3 requirement)

### 6b. POS session uniqueness patterns
*Source: ERPNext erpnext/accounts/doctype/pos_opening_entry/test_pos_opening_entry.py*

ERPNext's POS opening entry tests show exactly the pattern we need for session uniqueness.
These are direct analogs to our start_session_for_asset:

- [ ] **Same asset, same operator, attempt twice** — second call should raise ValidationError
      (mirrors `test_multiple_pos_opening_entries_for_same_pos_profile`)
- [ ] **Same asset, different operators** — second operator attempting same asset raises
      (mirrors `test_multiple_pos_opening_entry_for_same_pos_profile_by_multiple_user`)
- [ ] **Different assets, same operator** — both succeed
      (mirrors `test_multiple_pos_opening_entry_for_multiple_pos_profiles`)
- [ ] **Cancel/close then re-open** — after vacate, same asset can be reassigned
      (mirrors `test_cancel_pos_opening_entry_without_invoices` then re-create)
- [ ] **Attempt to cancel while session active** — should raise
      (mirrors `test_cancel_pos_opening_entry_with_invoice`)

### 6c. Document docstatus patterns
*Source: ERPNext POS tests — docstatus is a key Frappe integrity check*

- [ ] **Venue Session docstatus on close** — after vacate, session.docstatus should be 1 (Submitted)
      or a defined "Closed" status. An open docstatus=0 session on a Dirty asset is inconsistent.
- [ ] **Asset Status Log is immutable** — operators cannot edit log entries
      (Hamilton Operator has read=1, write=0 on Asset Status Log — test this is enforced)

### 6d. has_permission enforcement patterns
*Source: frappe/tests/test_client.py — test_http_invalid_method_access*

- [ ] **Unauthenticated API call** → returns 401/403, not 500
- [ ] **Hamilton Operator calling whitelisted method** → succeeds
- [ ] **Guest user calling whitelisted method** → returns 403
- [ ] **POST method required** — whitelisted methods use `methods=["POST"]`.
      A GET request to a POST-only endpoint must fail.
      `test_http_invalid_method_access` in Frappe tests this pattern.

### 6e. Timestamp and datetime serialization
*Source: frappe/tests/test_db.py — test_datetime_serialization, test_timestamp_change*

- [ ] **hamilton_last_status_change serializes correctly** — stores as datetime, retrieves correctly
- [ ] **last_vacated_at and last_cleaned_at store microseconds** — verify precision is not lost
- [ ] **Timestamp is set WITHIN the lock body** — not before acquire or after release
      (a timestamp set outside the lock could be out of order with the DB write)
- [ ] **test_timestamp_change analog** — if a lifecycle method is called twice in rapid succession,
      the second timestamp is always >= the first (monotonicity)

### 6f. Bulk operation patterns  
*Source: frappe/tests/test_db.py — test_bulk_insert, test_bulk_update*

Frappe's bulk operations show how to test chunk-based writes:

- [ ] **Bulk mark_clean with 0 dirty assets** — returns empty list, no errors
- [ ] **Bulk mark_clean with 1 dirty asset** — works correctly (boundary case)
- [ ] **Bulk mark_clean with all 26 rooms dirty** — completes without timeout
- [ ] **Bulk mark_clean with all 33 lockers dirty** — completes without timeout
- [ ] **Bulk mark_clean with mix of dirty and non-dirty** — only dirty ones change,
      non-dirty ones produce clean error report (not abort)
- [ ] **Bulk mark_clean transaction writes** — each asset is ONE transaction
      (no bulk-writes-in-one-transaction antipattern — would hold all DB locks simultaneously)

---

## Category 7: Frappe v16 Controller Hook Ordering
*Source: frappe/tests/test_db.py — test_transactions_disabled_during_writes, doc_events patterns*

Frappe fires controller hooks in a specific order. Our code must not violate this:

- [ ] **validate() called before before_save()** — verify hamilton_last_status_change is NOT set
      in validate(), only in before_save() (correct order)
- [ ] **before_save fires before DB write** — timestamps must be set before the row is saved
- [ ] **after_commit fires AFTER the transaction commits** — realtime publish must not fire mid-transaction
- [ ] **doc_events hook on Sales Invoice** — our `on_sales_invoice_submit` hook fires correctly
      when a Sales Invoice is submitted (Phase 2 test, mark as FUTURE)
- [ ] **Hook does not fire on cancel** — `doc_events.on_submit` should not run on docstatus=2

---

## Implementation notes for Frappe-specific tests

### Pattern: Testing with frappe.set_user()
ERPNext tests switch users to test permissions:
```python
frappe.set_user("hamilton.operator@test.com")
# attempt operation that should be allowed
frappe.set_user("Administrator")  # always restore in tearDown
```

### Pattern: savepoint for expected exceptions
When testing that an operation raises without poisoning the transaction:
```python
from frappe.utils.data import savepoint
with savepoint():
    self.assertRaises(frappe.ValidationError, lifecycle.start_session_for_asset, ...)
    raise Exception  # rollback the savepoint
```

### Pattern: asserting DB state after operation
```python
# Always re-fetch from DB, never trust the in-memory doc
asset = frappe.get_doc("Venue Asset", asset_name)
self.assertEqual(asset.status, "Occupied")
self.assertIsNotNone(asset.current_session)
self.assertEqual(asset.version, 1)
```


# Hamilton ERP — Advanced Edge Case Tests
**Source:** Jepsen distributed systems research, Martin Kleppmann "Designing Data-Intensive Applications",
MariaDB isolation level research, Redis.io distributed locking docs, production hardening patterns.
**Added:** 2026-04-10 after Tasks 1-8 3-AI review

These tests go beyond normal unit and integration testing into distributed systems hardening.
Add these to test_additional_expert.py progressively as the project matures.

---

## Category J: Jepsen-Level Distributed Systems Tests
*Source: jepsen.io — the gold standard for distributed systems correctness testing*

Jepsen tests are the hardest class of tests. They probe for anomalies that only appear
under concurrent load and partial failure. MariaDB has known Jepsen findings — we must
test that our locking layer compensates for them.

### J1. Lost Update (P4) — Confirmed MariaDB anomaly
*Source: Jepsen MariaDB Galera testing — MariaDB allows P4 (Lost Update) in default isolation*

MariaDB REPEATABLE READ can lose an update if two transactions read the same row,
then both write to it. Our FOR UPDATE lock prevents this — but we must test it.

```python
def test_concurrent_version_bump_no_lost_update(self):
    """Two threads read the same version and both try to write.
    The second must fail with version mismatch, not silently overwrite.
    This tests the optimistic version check prevents P4 (Lost Update).
    """
    # Thread 1: read version=0, set status=Occupied, write version=1
    # Thread 2: read version=0 (same read), try to set version=1 — must FAIL
    # Result: exactly one succeeds, one gets ValidationError
```

### J2. Stale Read — Confirmed MariaDB anomaly
*Source: Jepsen MariaDB — "regularly exhibits Stale Read"*

After a commit, a second connection may read stale data for a brief window.
Our `frappe.get_doc(..., for_update=True)` bypasses the document cache —
but we must verify the DB layer is not serving stale reads.

```python
def test_committed_status_visible_to_new_connection(self):
    """After start_session commits, a fresh frappe.connect() on a
    new thread must see status=Occupied, not Available (stale read).
    """
```

### J3. Write-Write Conflict Detection
*Source: Jepsen — InnoDB does not detect write-write conflicts in all cases*

Two transactions that write different fields on the same row can both succeed
in some MariaDB configurations, creating inconsistent state.
Our version field forces a conflict — but test it explicitly.

```python
def test_version_field_catches_write_write_conflict(self):
    """Simulate two transactions writing to the same asset row
    without going through the lock. The version check must catch
    the conflict on the second write.
    """
```

---

## Category K: Kleppmann-Level Lock Safety Tests
*Source: Martin Kleppmann "How to do distributed locking" — the definitive paper*

Kleppmann identifies the most dangerous failure modes for Redis-based locks.
Our three-layer design compensates for most of them — but we need tests.

### K1. The "Process Pause" scenario
*Source: Kleppmann — a GC pause or OS thread suspend can cause a process to hold
a lock past its TTL without knowing it*

```python
def test_lock_ttl_expiry_warning_is_logged(self):
    """Simulate TTL expiry by manually deleting the Redis key while
    inside the lock body. Verify the TTL-expiry warning is logged.
    Verify the Lua CAS release correctly no-ops (doesn't delete
    the new holder's key).
    """
    # Manually delete Redis key mid-lock to simulate TTL expiry
    # Assert frappe.logger().warning was called with "TTL expired"
    # Assert re-acquisition succeeds immediately after
```

### K2. The "Fencing Token" requirement
*Source: Kleppmann — without monotonically increasing fencing tokens,
a slow lock holder can corrupt state after its lock expires*

Our version field IS a fencing token — it's monotonically increasing.
But we need a test that proves it prevents the corruption scenario.

```python
def test_version_as_fencing_token_prevents_stale_write(self):
    """Simulate a slow holder: read version=3, pause, then try to write
    with expected_version=3 after the real version is already 4.
    Must raise ValidationError, not silently overwrite.
    """
    asset = make_asset("Test Fencing Token Room")
    # Fast-forward version by doing 4 real transitions
    # Then attempt _set_asset_status with expected_version=0 (stale)
    # Must raise: "Concurrent update detected"
```

### K3. Lock non-reentrancy (by design)
*Source: Kleppmann — re-entrant locks are dangerous in distributed systems*

Our lock is intentionally NOT re-entrant. If the same process tries to
acquire the lock it already holds, it must raise LockContentionError.
This prevents a class of bugs where nested calls accidentally bypass
the serialization guarantee.

```python
def test_lock_is_not_reentrant(self):
    """The same process holding the lock cannot acquire it again.
    This is intentional — re-entrant locks would allow nested
    lifecycle calls to bypass the serialization guarantee.
    """
    with asset_status_lock(asset.name, "outer"):
        with self.assertRaises(LockContentionError):
            with asset_status_lock(asset.name, "inner"):
                pass  # must not reach here
```

---

## Category L: MariaDB Isolation Level Tests
*Source: MariaDB.com isolation level violation testing blog post*

### L1. REPEATABLE READ phantom read
MariaDB defaults to REPEATABLE READ. Within a transaction, a second read
of the same row returns the SAME value even if another transaction committed
a change. Our FOR UPDATE re-read in _set_asset_status bypasses this — test it.

```python
def test_for_update_reads_latest_not_snapshot(self):
    """REPEATABLE READ would return the snapshot value. FOR UPDATE
    must return the latest committed value. Verify our re-read in
    _set_asset_status sees the current version, not the transaction-start snapshot.
    """
```

### L2. Deadlock detection and rollback
MariaDB detects deadlocks and rolls back the younger transaction.
If our lock acquisition order ever changes (e.g., bulk clean acquires
multiple row locks), we could deadlock. Test the detection path.

```python
def test_deadlock_raises_cleanly_not_hang(self):
    """Two threads acquire locks on two different assets in opposite order.
    MariaDB deadlock detection must roll back one, not hang forever.
    The rolled-back transaction must retry cleanly.
    Note: use a short lock timeout to make this test fast.
    """
```

### L3. Transaction write limit
Frappe has a MAX_WRITES_PER_TRANSACTION limit. A bulk clean of 59 assets
in a single transaction would hit this limit. Test that bulk clean uses
per-asset transactions, not one giant transaction.

```python
def test_bulk_clean_does_not_exceed_write_limit(self):
    """Bulk clean of N assets must use N separate transactions,
    not one transaction with N writes. Check frappe.db.transaction_writes
    after each asset to verify it resets between assets.
    """
```

---

## Category M: Chaos Engineering Tests
*Source: Netflix chaos engineering principles applied to our stack*

### M1. Redis restart mid-operation
```python
def test_operation_survives_redis_restart(self):
    """Simulate Redis restart (flush all keys) while an operator
    is actively using the system. The next operation must fail
    with LockContentionError (fail closed), not crash or corrupt data.
    """
    # Flush all Redis keys to simulate restart
    # Attempt lifecycle operation
    # Must either succeed (if lock acquired before flush) or
    # fail with LockContentionError (if flush happened during acquire)
    # Must NOT corrupt asset state
```

### M2. MariaDB connection loss mid-transaction
```python
def test_db_connection_loss_rolls_back_cleanly(self):
    """If the DB connection drops after _create_session but before
    _set_asset_status, the whole transaction must roll back.
    No orphaned session, no status change.
    """
```

### M3. Slow operator (> TTL duration)
```python
def test_slow_transaction_logs_ttl_warning(self):
    """If a lifecycle operation takes longer than LOCK_TTL_MS (15s),
    the TTL warning log must fire. The MariaDB FOR UPDATE must still
    prevent data corruption. This is our K1 (process pause) test
    but with a real time delay instead of manual key deletion.
    Note: use a mock to simulate the delay without actually sleeping 15s.
    """
```

---

## Category N: Security Edge Cases
*Source: OWASP, Claude 3-AI review finding on operator parameter*

### N1. Operator parameter injection
```python
def test_operator_cannot_be_spoofed_via_api(self):
    """When called via the whitelisted method, operator must be
    hardcoded to frappe.session.user — callers cannot pass a
    different email to impersonate another operator.
    (Test after Tasks 16-20 wire the whitelisted methods)
    """
```

### N2. Asset name injection
```python
def test_asset_name_sql_injection_rejected(self):
    """Asset name with SQL injection characters must be rejected
    by the DocType validator before reaching lifecycle code.
    Test: asset_name = "'; DROP TABLE tabVenue Asset; --"
    """
```

### N3. Negative version field
```python
def test_negative_version_rejected(self):
    """version field must never go negative. If someone manually
    sets version=-1 in the DB, the next lifecycle operation must
    detect the invariant violation and throw.
    """
```

---

## Category O: Data Integrity Invariant Tests
*Source: ChatGPT 3-AI review — "status ↔ current_session invariants under-enforced"*

### O1. Full invariant sweep after every operation
```python
def test_invariants_hold_after_full_lifecycle_cycle(self):
    """Run a complete cycle: Available→Occupied→Dirty→Available→OOS→Available.
    After EACH transition, assert ALL invariants:
    - Available: current_session=None, reason=None
    - Occupied: current_session is not None
    - Dirty: current_session=None
    - OOS: reason is not None and not whitespace
    - After OOS→Available: reason=None
    These invariants must NEVER be violated.
    """
```

### O2. Invariant helper _assert_row_invariants_for_status
```python
def test_assert_row_invariants_catches_corrupted_available_with_session(self):
    """A row with status=Available but current_session set should fail
    invariant check. This guards against manual SQL edits or bugs in
    future lifecycle code.
    """
    # Manually set inconsistent state via frappe.db.set_value
    # Then call the invariant checker (if implemented)
    # Must raise with a clear error message
```

### O3. Asset Status Log completeness
```python
def test_every_transition_creates_exactly_one_log_entry(self):
    """Count Asset Status Log rows before and after each transition.
    Each lifecycle call must create EXACTLY ONE log entry, not zero, not two.
    (Disable frappe.flags.in_test for this test to allow log creation)
    """
```

---

## Category P: Session Number Tests (Task 9)
*Source: DEC-033 — session number format {d}-{m}-{y}---{NNN}*

### P1. Format compliance
```python
def test_session_number_format_matches_dec033(self):
    """Session number must match: {d}-{m}-{y}---{NNN}
    Example valid: "10-4-2026---001", "10-4-2026---999"
    Example invalid: "2026-04-10---001" (wrong date format)
    """
    import re
    pattern = r"^\d{1,2}-\d{1,2}-\d{4}---\d{3}$"
    self.assertRegex(session_number, pattern)
```

### P2. Daily reset
```python
def test_session_counter_resets_at_midnight(self):
    """Session numbers reset to 001 on a new day.
    Simulate: mock date as today, create session (gets NNN),
    advance mock date to tomorrow, create another session (must get 001).
    """
```

### P3. Concurrent session number generation
```python
def test_session_numbers_unique_under_concurrent_load(self):
    """10 concurrent threads each create a session on the same asset
    sequentially (only one can succeed at a time due to lock).
    All successful sessions must have unique session numbers.
    No two sessions on the same day may share a number.
    """
```

### P4. Redis fallback
```python
def test_session_number_falls_back_to_db_when_redis_unavailable(self):
    """If Redis INCR fails, session number generation falls back to
    DB-based counter. Must still produce a valid DEC-033 format number.
    Must not crash or leave session_number empty.
    """
```

---

## When to add these tests

| Category | Add when | Priority |
|---|---|---|
| J (Jepsen) | After Task 9 (hardening pass) | Critical — data integrity |
| K (Kleppmann) | After Task 9 | Critical — lock correctness |
| L (MariaDB) | After Task 11 | High — isolation bugs |
| M (Chaos) | After Task 21 | High — production resilience |
| N (Security) | After Task 16-20 (UI wiring) | High — security |
| O (Invariants) | After Task 9 | Critical — data integrity |
| P (Session Number) | During Task 9 | Required — new feature |

---

## How to run Jepsen-style tests manually

Jepsen uses the Elle checker for cycle detection in transaction dependency graphs.
The Python equivalent approach for our stack:

1. Run 100 concurrent lifecycle operations on the same pool of assets
2. After all complete, verify:
   - Every asset is in a valid state
   - No two sessions are Active for the same asset
   - version field is monotonically increasing for each asset
   - Asset Status Log has exactly N entries (one per transition)

This is the "linearizability check" — the gold standard for distributed systems correctness.
