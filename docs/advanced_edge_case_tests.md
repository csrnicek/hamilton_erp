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
