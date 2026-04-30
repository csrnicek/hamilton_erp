# Hamilton ERP — Complete Testing Guide
**Updated:** 2026-04-10 after Tasks 1-8 complete

This document tells you WHAT to run, WHEN to run it, and WHY.
The goal is code as close to perfect as possible.

---

## The 4 levels of testing

### Level 1 — /run-tests (run after EVERY task)
The core test suite. Always run this. Always run the full suite including expert tests.

**Command:**
```
cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle hamilton_erp.test_locks hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset hamilton_erp.test_additional_expert
```

**What it runs:**
- test_lifecycle.py — state machine + all 5 lifecycle methods (25 tests)
- test_locks.py — three-layer lock correctness (3 tests)
- test_venue_asset.py — validator rules (17 tests)
- test_additional_expert.py — expert edge cases (52 tests)

**When:** After every single task, no exceptions.

**Expected failures in test_additional_expert:** Some tests require
Tasks 9-11 to pass. Always report the full count so we can track progress.

---

### Level 2 — /coverage (run after Tasks 9 and 11)
Shows exactly which lines of code are never executed by any test.
Any uncovered line is a potential hidden bug.

**Install (one time):**
```
pip install pytest-cov --break-system-packages
```

**Command:**
```
cd ~/frappe-bench-hamilton && source env/bin/activate && python -m coverage run -m pytest && python -m coverage report --include="*/hamilton_erp/lifecycle.py,*/hamilton_erp/locks.py" --show-missing
```

**What to look for:** Any line marked as "not covered" in lifecycle.py or locks.py.
Target: 90%+ coverage on both files before production.

**When:** After Task 9 (all lifecycle methods) and Task 11 (seed patch).

---

### Level 3 — /mutmut — Mutation Testing (run after Task 9 and before Task 25)
The hardest test of all. Deliberately introduces small bugs into the code
(changes == to !=, removes conditions, flips operators) then runs all tests.
If a bug survives all tests, your tests are weaker than you think.

**What "surviving mutant" means:** Your tests missed a real bug.
**Target:** 0 surviving mutants in lifecycle.py and locks.py.

**Install (one time):**
```
pip install mutmut --break-system-packages
```

**Command:**
```
cd ~/hamilton_erp && mutmut run --paths-to-mutate hamilton_erp/lifecycle.py,hamilton_erp/locks.py && mutmut results
```

**When:** After Task 9 (all lifecycle complete) and Task 25 (pre-production deploy).
This is slow (~20-30 minutes) — only run at major checkpoints.

**Output legend:**
- 🎉 Killed = test caught the bug (good)
- 🙁 Survived = test MISSED the bug (bad — add a test)
- ⏰ Timeout = test took too long
- 🤔 Suspicious = test was slow but passed

---

### Level 4 — /hypothesis — Property-Based Testing (run after Task 9)
Instead of writing specific test cases, Hypothesis generates hundreds of
random inputs automatically and finds edge cases you would never think of.
Especially powerful for the state machine.

**Install (one time):**
```
pip install hypothesis --break-system-packages
```

**What it does for Hamilton ERP:**
- Tries random sequences of lifecycle calls (start, vacate, clean, oos, return)
- Finds invalid transition combinations you didn't test explicitly
- Tests that the version field always increments correctly
- Tests that timestamps are always monotonically increasing

**When:** After Task 9 when all 5 lifecycle methods exist.
Requires hamilton_erp/test_hypothesis.py — will be created at Task 9 hardening.

---

## 3-AI Review Checkpoints
Run ChatGPT + Grok + Claude (new claude.ai tab) reviews at:

| Checkpoint | When | Status |
|---|---|---|
| Tasks 1-2 | After locks.py complete | ✅ Done |
| Tasks 1-8 | After all 5 lifecycle methods | ✅ Done |
| Task 9 | After session number generation | 🔜 Next |
| Task 11 | After seed patch | 🔜 |
| Task 21 | After full Asset Board UI | 🔜 |
| Task 25 | Before Frappe Cloud deploy | 🔜 |

**Review files:**
- Blind review prompt: docs/reviews/review_task9_blind.md
- Context-aware review prompt: docs/reviews/review_task9_context.md

---

## Why each tool catches different bugs

| Tool | What it catches |
|---|---|
| /run-tests | Bugs you already thought to test |
| /coverage | Code paths you forgot to test at all |
| /mutmut | Tests that pass even when the code is wrong |
| /hypothesis | Edge cases you never thought of |
| 3-AI review | Architectural issues and design flaws |

No single tool is enough. All 4 together give you near-certainty.

---

## Current test count (as of 2026-04-14)
- Full suite: **334 tests passing**, 0 failures, 7 skipped across **13 modules**
- See CLAUDE.md "Test Suite" table for the per-module breakdown

---

## Advanced Database and Performance Tests

**File:** `hamilton_erp/test_database_advanced.py`
**Tests:** 51 | **Added:** 2026-04-14

These tests target the infrastructure underneath the application logic — MariaDB indexes and query plans, Redis lock mechanics, Frappe v16 framework contracts, and fraud-detection invariants. They complement the functional tests (lifecycle, locks, edge cases) by verifying that the database, cache, and framework behave the way Hamilton ERP assumes they do.

Run with:
```
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_database_advanced
```

---

### R1 — Database Index Verification (7 tests)

Queries `INFORMATION_SCHEMA.STATISTICS` to confirm every `search_index` field declared in DocType JSON actually has a corresponding MariaDB index. Missing indexes cause full table scans on the Asset Board and session queries.

| Test | What it verifies |
|---|---|
| `test_venue_asset_status_index_exists` | `tabVenue Asset.status` has an index |
| `test_venue_session_session_number_index_exists` | `tabVenue Session.session_number` has an index |
| `test_venue_session_venue_asset_index_exists` | `tabVenue Session.venue_asset` has an index |
| `test_shift_record_operator_index_exists` | `tabShift Record.operator` has an index |
| `test_cash_drop_shift_record_index_exists` | `tabCash Drop.shift_record` has an index |
| `test_asset_status_log_venue_session_index_exists` | `tabAsset Status Log.venue_session` has an index |
| `test_venue_asset_display_order_index_exists` | `tabVenue Asset.display_order` has an index (Asset Board ORDER BY) |

**What's not yet tested:**
- Composite/covering indexes for common multi-column queries
- Index selectivity / cardinality checks

---

### R2 — Query Performance and SLA Timing (6 tests)

Uses `EXPLAIN` to inspect query plans and `time.monotonic()` to enforce timing SLAs on critical operations. These SLAs are generous (100ms board load, 200ms session creation, 50ms lock acquisition) — any breach indicates a missing index or regression.

| Test | What it verifies |
|---|---|
| `test_asset_board_query_returns_explain_plan` | EXPLAIN on the board query produces a valid plan |
| `test_asset_board_load_under_100ms` | `get_asset_board_data()` completes in <100ms |
| `test_session_creation_under_200ms` | `start_session_for_asset()` completes in <200ms |
| `test_lock_acquisition_under_50ms` | Redis + FOR UPDATE lock acquired in <50ms |
| `test_session_number_like_query_not_full_scan` | LIKE query on session_number does not produce type=ALL |
| `test_for_update_query_targets_single_row` | FOR UPDATE uses const/eq_ref/ref (primary key lookup) |

**What's not yet tested:**
- SLA timing under concurrent load (multiple simultaneous requests)
- Query performance with >1000 sessions in the table
- Slow query log integration

---

### R3 — MariaDB Edge Cases (7 tests)

Verifies MariaDB-specific behaviours that Frappe and Hamilton ERP depend on. A wrong isolation level, table-level locking, or lost microsecond precision would break the state machine or session ordering.

| Test | What it verifies |
|---|---|
| `test_transaction_isolation_is_repeatable_read` | `@@tx_isolation` = REPEATABLE-READ |
| `test_global_isolation_matches_session` | Session and global isolation levels match |
| `test_for_update_locks_row_not_table` | FOR UPDATE on asset A does not block reads on asset B |
| `test_datetime_microsecond_precision` | `session_start` column has DATETIME_PRECISION = 6 |
| `test_null_vs_empty_string_in_reason` | Fresh asset `reason` is NULL, not empty string |
| `test_unique_constraint_on_asset_code` | Duplicate `asset_code` raises exception |
| `test_session_number_unique_constraint_enforced` | Duplicate `session_number` raises exception |

**What's not yet tested:**
- Deadlock detection and automatic retry (two transactions locking rows in opposite order)
- Character set / collation edge cases (UTF-8 asset names)
- Large BLOB/TEXT field handling in Asset Status Log

---

### R4 — Redis Edge Cases (7 tests)

Tests the Redis primitives that the three-layer lock (locks.py) depends on. If `SET NX` doesn't prevent overwrites, or the Lua CAS release deletes the wrong key, the lock is broken.

| Test | What it verifies |
|---|---|
| `test_lock_ttl_matches_constant` | Lock key TTL is within tolerance of `LOCK_TTL_MS` |
| `test_incr_returns_integer` | `INCR` returns `int`, not bytes or string |
| `test_incr_at_large_values` | `INCR` at 99999 → 100000 (no overflow at our threshold) |
| `test_key_namespace_isolation` | `hamilton:` namespace keys don't collide with Frappe internals |
| `test_nx_flag_prevents_overwrite` | Second `SET NX` on existing key returns False |
| `test_lua_cas_release_correct_token` | Lua CAS release deletes only when token matches; wrong token returns 0 |
| `test_cold_start_db_fallback_returns_correct_max` | `_db_max_seq_for_prefix()` reads MariaDB correctly when Redis key is cold |

**What's not yet tested:**
- Redis connection failure / reconnection handling
- Redis memory pressure (maxmemory policy eviction)
- Key expiry race condition (lock expires during FOR UPDATE)

---

### R5 — Frappe v16 Specific Behaviour (9 tests)

Pins Frappe v16 framework contracts that Hamilton ERP relies on. If a Frappe upgrade changes `in_test`, `track_changes`, `autoname`, or role handling, these tests break before production does.

| Test | What it verifies |
|---|---|
| `test_frappe_in_test_flag_is_true` | `frappe.in_test` is True during test execution |
| `test_override_doctype_class_loads_correctly` | `HamiltonSalesInvoice` mixin has expected methods |
| `test_scheduler_job_is_importable` | `check_overtime_sessions` is importable and callable |
| `test_after_migrate_hook_is_importable` | `ensure_setup_complete` is importable and callable |
| `test_role_permissions_exist_for_venue_asset` | Venue Asset has permissions for all 3 Hamilton roles |
| `test_track_changes_enabled_on_venue_session` | Venue Session has `track_changes = 1` |
| `test_track_changes_enabled_on_shift_record` | Shift Record has `track_changes = 1` |
| `test_track_changes_enabled_on_venue_asset` | Venue Asset has `track_changes = 1` |
| `test_track_changes_enabled_on_cash_drop` | Cash Drop has `track_changes = 1` |
| `test_track_changes_enabled_on_cash_reconciliation` | Cash Reconciliation has `track_changes = 1` |
| `test_track_changes_enabled_on_comp_admission_log` | Comp Admission Log has `track_changes = 1` |
| `test_track_changes_enabled_on_hamilton_board_correction` | Hamilton Board Correction has `track_changes = 1` |
| `test_track_changes_enabled_on_hamilton_settings` | Hamilton Settings has `track_changes = 1` |
| `test_track_changes_explicitly_disabled_on_asset_status_log` | Asset Status Log has `track_changes = 0` (audit log itself — tracking is recursive) |
| `test_venue_session_autoname_is_hash` | Venue Session uses `hash` autoname (DEC-033) |
| `test_venue_asset_autoname_is_series` | Venue Asset uses `VA-.####` naming series |

**What's not yet tested:**
- `override_doctype_class` loads correctly via Frappe's `get_controller()` (not just import)
- Custom field metadata survives `bench migrate`
- Webhook / notification hook contracts

---

### R6 — Fraud Detection and Operational Integrity (5 tests)

Verifies the guards that prevent fraud, data corruption, and operational errors in the single-operator, walk-in-guest environment.

| Test | What it verifies |
|---|---|
| `test_orphan_session_detectable` | Session older than stay_duration + grace_minutes is found by overtime query |
| `test_duplicate_assignment_blocked_by_state_machine` | Second `start_session` on Occupied asset raises `ValidationError` |
| `test_bulk_clean_does_not_affect_occupied_assets` | `_mark_all_clean()` skips Occupied assets — never transitions Occupied → Available |
| `test_vacate_method_stored_correctly` | Vacate method is persisted on the Venue Session record |
| `test_oos_from_occupied_auto_closes_session` | OOS on Occupied asset closes session with "Discovery on Rounds" |

**What's not yet tested:**
- Bulk clean race condition (two operators press "Clean All" simultaneously)
- Cash drop without an active shift (should be blocked)
- Session duration manipulation (backdated session_start)

---

### R7 — Concurrency and Connection Reliability (3 tests)

Tests that the system handles repeated operations without leaking connections or corrupting state. Threading-based concurrency tests are omitted because Frappe's `IntegrationTestCase` runs inside an uncommitted transaction that is invisible to child threads.

| Test | What it verifies |
|---|---|
| `test_sequential_lock_acquisitions_on_different_assets` | 3 sequential lock/unlock cycles don't exhaust the connection pool |
| `test_full_lifecycle_is_repeatable` | Available → Occupied → Dirty → Available repeatable 3 times |
| `test_version_increments_monotonically` | Version field increments by exactly 1 on each state transition |

**What's not yet tested:**
- True multi-thread / multi-process concurrency (requires `setUpClass` + `db.commit()` pattern from `test_adversarial.py`)
- Connection pool exhaustion under sustained load
- Frappe worker restart mid-transaction

---

### R8 — Data Integrity Under Edge Conditions (7 tests)

Verifies timestamp ordering, field nullability, and cleanup after state transitions. These catch regressions where a field gets set to empty string instead of NULL, or a timestamp is missing after a transition.

| Test | What it verifies |
|---|---|
| `test_session_end_after_session_start` | `session_end > session_start` after vacate |
| `test_last_cleaned_at_updates_on_mark_clean` | `last_cleaned_at` is stamped on Dirty → Available |
| `test_last_cleaned_at_updates_on_return_from_oos` | `last_cleaned_at` is stamped on OOS → Available (DEC-031) |
| `test_last_vacated_at_updates_on_vacate` | `last_vacated_at` is stamped on Occupied → Dirty |
| `test_reason_cleared_after_return_from_oos` | `reason` is NULL (not empty string) after return from OOS |
| `test_current_session_cleared_after_vacate` | `current_session` is NULL (not empty string) after vacate |
| `test_hamilton_last_status_change_populated` | `hamilton_last_status_change` is set on every transition |

**What's not yet tested:**
- Timezone edge cases (UTC vs local time in `session_start`)
- Leap second / DST transition handling
- Field truncation on very long reason strings

---

## Known Test Gaps — Resolve Before Task 25 Handoff

These are concrete, known-missing tests that must be written before the Phase 1 handoff deploy.

### 1. API POST Permission Tests

Verify that a Guest user (unauthenticated) cannot call any of these whitelisted endpoints via the API layer:

- `start_walk_in_session`
- `vacate_asset`
- `clean_asset`
- `set_asset_oos`
- `return_asset_from_oos`

Each test should hit the endpoint through `frappe.handler.execute_cmd()` (or equivalent) with no session/role, and assert a `PermissionError` or 403. Direct Python imports bypass the permission gate entirely (see Best Practice #3 in `claude_memory.md`), so these tests must exercise the HTTP/handler layer.

### 2. Sales Invoice Override Tests

`HamiltonSalesInvoice` (in `hamilton_erp/overrides/sales_invoice.py`) defines three methods loaded via `override_doctype_class` in hooks.py:

- `has_admission_item()` — returns True if any line item matches admission criteria
- `get_admission_category()` — returns the admission category string
- `has_comp_admission()` — returns True if the admission is comped

None of these have any test coverage. Tests should create a Sales Invoice with and without admission items and verify each method's return value. These methods are the foundation of Phase 2 financial integration.

### 3. Bulk Clean Catastrophic Exception Handling

`_mark_all_clean()` in `api.py` iterates over all Dirty assets and calls `mark_asset_clean()` on each. If a catastrophic exception occurs mid-loop (e.g., DB connection failure), verify that:

- The error is raised or logged, not silently swallowed
- Assets cleaned before the failure remain clean (committed)
- The caller receives an error response, not a success with partial results

### 4. `utils.py` — Completely Untested Functions

`get_current_shift_record()` and `get_next_drop_number()` in `hamilton_erp/utils.py` have zero test coverage:

- `get_current_shift_record()` — returns the active Shift Record for the current operator. Must be tested with: no active shift, one active shift, multiple shifts (should return most recent).
- `get_next_drop_number()` — returns the next sequential drop number for a shift. Must be tested with: no prior drops (returns 1), existing drops (returns max + 1), and the empty-string guard (a known edge case where an empty string in the `drop_number` field causes `max()` to return `""` instead of an integer).

---

## Expert-Level Testing — Full Checklist

These are the 10 expert-level testing activities that go beyond unit and integration tests. Each one targets a class of failure that basic tests cannot catch. Ordered by priority.

### Before Go-Live (must complete before first real shift)

**1. Security Penetration Testing**
Raw HTTP API exploitation attempts against all whitelisted endpoints. Includes:
- SQL injection via `frappe.form_dict` parameters (asset names, session numbers, reasons)
- Privilege escalation — Guest calling operator-only endpoints, operator calling admin-only endpoints
- CSRF token bypass attempts
- Rate limiting / brute force against session creation

**2. Chaos Testing**
Deliberately break infrastructure mid-operation and verify graceful recovery:
- Kill Redis mid-shift — verify lock acquisition fails cleanly (not silent corruption)
- Network failure mid-transaction — verify MariaDB rollback leaves no half-written state
- `bench restart` mid-session — verify the session is recoverable or cleanly orphaned
- Redis flush during active operations — verify cold-start fallback in session numbering

**3. Data Migration Testing**
Seed 6 months of realistic historical data (10,000+ sessions, 500+ shifts, 2,000+ cash drops) and verify:
- All patches in `hamilton_erp/patches/` run cleanly against the historical data
- No unique constraint violations from realistic session number patterns
- Performance does not degrade with historical volume (asset board still <100ms)

### Task 25 (complete before Frappe Cloud deploy)

**4. Property-Based Testing (Hypothesis)**
Random inputs against critical functions:
- `_next_session_number()` — random dates, high sequence numbers, midnight boundaries
- Cash math — random float amounts, verify no floating-point rounding errors
- State machine — random sequences of valid transitions never reach an invalid state
- Session number format — all generated numbers match the `DD-M-YYYY---NNNN` pattern

**5. Mutation Testing (mutmut)**
Verify the test suite catches real bugs by deliberately introducing small mutations:
- Target: `lifecycle.py` and `locks.py`
- Goal: 80%+ kill ratio (80% of mutations are caught by at least one test)
- Any surviving mutant in a critical path (lock acquisition, state transition) must be killed

**6. Load Testing**
Simulate realistic concurrent usage over an extended period:
- 20 concurrent check-ins over 2 hours
- Measure response time degradation over time (should stay flat, not creep up)
- Monitor MariaDB connection pool, Redis memory, and Python worker RSS
- Verify session numbering remains unique under sustained load

**7. Slow Query Log Analysis**
Enable MariaDB slow query log, run a full shift simulation (start shift, 50 check-ins, 50 vacates, bulk clean, cash drops, close shift), then audit:
- Every query over 10ms — identify missing indexes or bad query plans
- Any full table scan on tables with >100 rows
- Any query that locks more than one row
- Enable with: `SET GLOBAL slow_query_log = 'ON'; SET GLOBAL long_query_time = 0.01;`

### Phase 2 (after go-live, before scaling)

**8. Contract Tests vs ERPNext**
Verify ERPNext internal APIs that Hamilton ERP depends on still behave correctly:
- Sales Invoice creation and submission — `HamiltonSalesInvoice` override hooks fire
- POS Closing Entry — GL entries post correctly with Hamilton admission items
- ERPNext version upgrade — run full test suite against ERPNext v16.x point releases
- `frappe.get_meta()` contracts — field types, options, and permissions haven't changed

**9. Structured Logging**
Add JSON-formatted log entries for every critical operation:
- Session creation — asset, operator, session_number, duration_ms
- Lock acquisition — asset, operation, wait_ms, success/fail
- Cash drop — shift, drop_number, declared_amount, operator
- Errors — full stack trace, request context, user
- Output to Frappe Error Log or external (Loki, CloudWatch) — decision pending

**10. Formal STRIDE Threat Model**
Document every entry point, trust boundary, and data flow with explicit mitigations:
- **S**poofing — operator identity (Frappe session auth, no anonymous access)
- **T**ampering — cash drop amounts, session timestamps (audit trail, track_changes)
- **R**epudiation — operator denies action (Asset Status Log, Version history)
- **I**nformation Disclosure — guest sees revenue data (role-based field permissions)
- **D**enial of Service — lock flooding, bulk API abuse (Redis TTL, rate limiting)
- **E**levation of Privilege — operator accessing admin endpoints (Frappe role check)
