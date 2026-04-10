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
