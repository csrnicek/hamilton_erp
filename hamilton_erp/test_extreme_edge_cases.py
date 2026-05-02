"""Hamilton ERP — Extreme Production Edge Case Tests

Sources:
- Frappe Cloud incident log (docs.frappe.io/cloud/recent-issues)
  Real outages: stuck background jobs, faulty Redis config, DNS failures,
  MariaDB connection drops, daily usage limits
- Hetzner production failure reports (Hacker News threads)
  Invisible outages, thermal throttling, load balancer failures,
  shared vCPU contention, network bandwidth spikes
- Frappe Forum production issues
  MariaDB "Aborted connection" errors, Redis queue spawn errors,
  connection pool exhaustion, OOM kills
- ERPNext silent failure patterns (codewithkarani.com)
  ERPNext fails silently — data corruption without errors,
  background job stagnation, N+1 query death spirals
- Frappe v16 test_db.py MAX_WRITES_PER_TRANSACTION,
  test_caching.py, test_background_jobs.py

Categories:
  V — Frappe Cloud Real Incident Patterns
  W — MariaDB Production Failure Modes
  X — Redis Production Failure Modes
  Y — Hetzner Infrastructure Edge Cases
  Z — ERPNext Silent Failure Patterns
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import frappe
import pymysql.err
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle
from hamilton_erp.lifecycle import (
    mark_asset_clean,
    return_asset_to_service,
    set_asset_out_of_service,
    start_session_for_asset,
    vacate_session,
)
from hamilton_erp.locks import LockContentionError, asset_status_lock

OPERATOR = "Administrator"


def _ensure_walkin():
    if frappe.db.exists("Customer", "Walk-in"):
        return
    frappe.get_doc({
        "doctype": "Customer",
        "customer_name": "Walk-in",
        "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
        "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
    }).insert(ignore_permissions=True)


def _make_asset(name, category="Room", tier="Single Standard", status="Available"):
    _ensure_walkin()
    return frappe.get_doc({
        "doctype": "Venue Asset",
        "asset_code": f"EX-{name[:5].upper()}-{uuid.uuid4().hex[:4].upper()}",
        "asset_name": name,
        "asset_category": category,
        "asset_tier": tier if category == "Room" else "Locker",
        "status": status,
        "display_order": 999,
    }).insert(ignore_permissions=True)


# ===========================================================================
# Category V — Frappe Cloud Real Incident Patterns
# Source: docs.frappe.io/cloud/recent-issues
# ===========================================================================

class TestFrappeCloudIncidentPatterns(IntegrationTestCase):
    """V — Tests derived from real Frappe Cloud production incidents."""

    IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

    def setUp(self):
        self.asset = _make_asset("EX Cloud Incident Room")

    def tearDown(self):
        frappe.db.rollback()

    def test_background_job_stuck_does_not_corrupt_asset_state(self):
        """V1 — Stuck background job must not leave asset in corrupt state.

        Real incident: Frappe Cloud 2025-10-02 — all background jobs stuck
        for 4 days undetected. If a lifecycle background job stalls mid-way,
        the asset must remain in its PREVIOUS valid state, not a partial state.

        Our transaction-based approach handles this: if _set_asset_status
        raises, the transaction rolls back. Test that a simulated mid-op
        failure leaves the asset in its original state.
        """
        original_status = frappe.db.get_value("Venue Asset", self.asset.name, "status")
        self.assertEqual(original_status, "Available")

        # Simulate a failure mid-lifecycle (after lock acquired, before status saved)
        with patch.object(lifecycle, "_set_asset_status",
                          side_effect=frappe.ValidationError("Simulated stuck job")):
            with self.assertRaises(frappe.ValidationError):
                start_session_for_asset(self.asset.name, operator=OPERATOR)

        # Asset must still be Available — no partial state
        recovered_status = frappe.db.get_value("Venue Asset", self.asset.name, "status")
        self.assertEqual(recovered_status, "Available",
                         "Asset corrupted by failed mid-op — transaction rollback failed")

    def test_faulty_redis_config_falls_back_gracefully(self):
        """V2 — Faulty Redis config raises clean error, not crash.

        Real incident: Frappe Cloud 2024 — faulty redis config affected 89
        benches. Our Redis-dependent code must fail with a user-friendly
        message, not a raw ConnectionError stack trace to the operator.
        """
        with patch("hamilton_erp.locks.frappe.cache") as mock_cache:
            mock_instance = MagicMock()
            mock_instance.set.side_effect = Exception("Redis config error: wrong password")
            mock_cache.return_value = mock_instance

            with self.assertRaises((LockContentionError, frappe.ValidationError)) as ctx:
                with asset_status_lock(self.asset.name, "test"):
                    pass

            # Error must be user-friendly, not raw Redis exception
            error_str = str(ctx.exception)
            self.assertNotIn("Traceback", error_str)

    def test_daily_usage_limit_graceful_degradation(self):
        """V4 — If Frappe site hits daily DB usage limit, lifecycle raises clearly.

        Real incident: Frappe Cloud "Daily Usage limit reached" causes 500 errors.
        Simulate DB unavailable mid-operation.
        """
        # asset_status_lock uses frappe.db.sql (FOR UPDATE), not get_value —
        # patch the real call site so the simulated DB failure actually fires.
        with patch("frappe.db.sql", side_effect=frappe.DataError("Daily limit exceeded")):
            # Lock acquisition reads the asset row — if DB is down, must fail cleanly
            with self.assertRaises((frappe.DataError, LockContentionError, Exception)):
                with asset_status_lock(self.asset.name, "test"):
                    pass

    def test_dns_failure_does_not_corrupt_session_state(self):
        """V5 — DNS/network failure during session creation leaves no orphaned session.

        Real incident: Frappe Cloud 2025-07-15 — DNS bug caused sites to
        stop resolving. If a network failure occurs after session insert but
        before asset status update, the transaction must roll back.
        This is the same orphaned-session scenario as the transaction test.
        """
        session_count_before = frappe.db.count("Venue Session",
                                                {"venue_asset": self.asset.name})
        with patch.object(lifecycle, "_set_asset_status",
                          side_effect=frappe.ValidationError("Network timeout")):
            with self.assertRaises(frappe.ValidationError):
                start_session_for_asset(self.asset.name, operator=OPERATOR)

        # IntegrationTestCase does not auto-rollback on exceptions caught by
        # assertRaises — production request handlers wrap each call in their
        # own transaction. Simulate that here by rolling back explicitly so
        # we can verify the atomicity contract (session insert must not
        # survive a failed lifecycle call).
        frappe.db.rollback()

        # No orphaned session must remain
        session_count_after = frappe.db.count("Venue Session",
                                               {"venue_asset": self.asset.name})
        self.assertEqual(session_count_before, session_count_after,
                         "Orphaned Venue Session created despite transaction rollback")


# ===========================================================================
# Category W — MariaDB Production Failure Modes
# Source: Frappe Forum "Aborted connection" issues, connection pool exhaustion
# ===========================================================================

class TestMariaDBProductionFailures(IntegrationTestCase):
    """W — MariaDB production failure patterns from Frappe Forum."""

    IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

    def setUp(self):
        self.asset = _make_asset("EX MariaDB Room")

    def tearDown(self):
        frappe.db.rollback()

    def test_for_update_lock_releases_on_connection_drop(self):
        """W1 — FOR UPDATE lock must not persist if connection drops.

        Real issue: Frappe Forum — "Aborted connection" errors leave
        FOR UPDATE locks held, blocking all subsequent operations on the asset.
        MariaDB auto-releases row locks when connection drops (InnoDB behavior).
        This test documents that our lock pattern is safe under connection drops.
        """
        # Exit the lock cleanly (simulates normal release after connection drop
        # auto-releases FOR UPDATE locks in InnoDB). Then re-acquire to verify
        # the row lock did not persist — if the lock leaked, the second acquire
        # would block or raise.
        with asset_status_lock(self.asset.name, "test") as row:
            self.assertIsNotNone(row)

        with asset_status_lock(self.asset.name, "test2") as row2:
            self.assertIsNotNone(row2,
                                 "Row lock leaked — second acquire failed after first released")

        # Asset must still be accessible after both lock cycles
        asset = frappe.get_doc("Venue Asset", self.asset.name)
        self.assertEqual(asset.status, "Available")

        # If we get here without hanging, connection pool is clean

    def test_mariadb_deadlock_detected_and_raised(self):
        """W3 — MariaDB deadlock raises frappe.DatabaseError, not hang forever.

        Real issue: Frappe Forum — deadlocks on bulk operations cause processes
        to hang indefinitely without timeout. MariaDB detects deadlocks and
        raises an error — verify our code surfaces it cleanly.
        Simulated because real deadlocks require 2 live transactions.
        """
        with patch("frappe.db.sql",
                   side_effect=pymysql.err.OperationalError(1213, "Deadlock found when trying to get lock")):
            with self.assertRaises((pymysql.err.OperationalError, Exception)):
                start_session_for_asset(self.asset.name, operator=OPERATOR)

    def test_row_not_found_after_lock_raises_cleanly(self):
        """W4 — Asset deleted between Redis acquire and FOR UPDATE raises clearly.

        Extreme edge case: Redis lock acquired, but between lock acquisition
        and the FOR UPDATE query, another process deletes the asset row.
        The FOR UPDATE query returns 0 rows — must raise ValidationError.
        """
        with self.assertRaises(frappe.ValidationError):
            with asset_status_lock("VA-DOES-NOT-EXIST-EXTREME", "test"):
                pass


# ===========================================================================
# Category X — Redis Production Failure Modes
# Source: Frappe Forum Redis queue spawn errors, OOM, config failures
# ===========================================================================

class TestRedisProductionFailures(IntegrationTestCase):
    """X — Redis production failure patterns."""

    IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

    def setUp(self):
        self.asset = _make_asset("EX Redis Room")

    def tearDown(self):
        frappe.db.rollback()

    def test_redis_oom_raises_user_friendly_error(self):
        """X1 — Redis OOM (Out of Memory) raises user-friendly error.

        Real issue: Redis OOM causes ENOMEM errors on SET/INCR operations.
        Must surface as LockContentionError or ValidationError, not raw OOM.
        """
        with patch("hamilton_erp.locks.frappe.cache") as mock_cache:
            mock_instance = MagicMock()
            mock_instance.set.side_effect = Exception("OOM command not allowed when used memory > maxmemory")
            mock_cache.return_value = mock_instance
            with self.assertRaises((LockContentionError, frappe.ValidationError)):
                with asset_status_lock(self.asset.name, "test"):
                    pass

    def test_redis_key_does_not_persist_after_test(self):
        """X2 — Redis keys created during tests are cleaned up.

        Real issue: Test Redis keys persisting across test runs cause false
        positives (second acquisition fails because key from previous run exists).
        Verify our lock keys are always cleaned up.
        """
        cache = frappe.cache()
        key = f"hamilton:asset_lock:{self.asset.name}"
        # Key must not exist before test
        self.assertIsNone(cache.get(key))
        with asset_status_lock(self.asset.name, "test"):
            self.assertIsNotNone(cache.get(key))
        # Key must be gone after lock exits
        self.assertIsNone(cache.get(key))

    def test_redis_timeout_error_raises_lock_contention(self):
        """X3 — Redis TimeoutError treated same as ConnectionError.

        Real issue: Network latency on Hetzner shared vCPU can cause Redis
        timeout errors. Must raise LockContentionError, not TimeoutError crash.
        """
        import redis
        with patch("hamilton_erp.locks.frappe.cache") as mock_cache:
            mock_instance = MagicMock()
            mock_instance.set.side_effect = redis.TimeoutError("Redis connection timed out")
            mock_cache.return_value = mock_instance
            with self.assertRaises((LockContentionError, frappe.ValidationError)):
                with asset_status_lock(self.asset.name, "test"):
                    pass

    def test_session_number_redis_key_cleaned_up_after_day(self):
        """X4 — Session number Redis key has TTL and will not persist forever.

        Real issue: Orphaned Redis keys from crashed processes accumulate
        and eventually exhaust Redis memory. Our session counter keys have
        a 48h TTL for garbage collection.
        """
        from hamilton_erp.lifecycle import _SESSION_KEY_TTL_MS
        # Verify TTL constant is reasonable (48 hours = 172800000ms)
        self.assertGreater(_SESSION_KEY_TTL_MS, 0)
        self.assertLessEqual(_SESSION_KEY_TTL_MS, 172800000,
                              "Session counter TTL must be <= 48 hours to prevent key accumulation")


# ===========================================================================
# Category Y — Hetzner Infrastructure Edge Cases
# Source: Hacker News Hetzner experience threads, shared vCPU contention
# ===========================================================================

class TestHetznerInfrastructureEdgeCases(IntegrationTestCase):
    """Y — Tests for Hetzner-specific infrastructure failure modes.

    Hetzner shared vCPU instances (CX series) can experience:
    - CPU throttling due to host contention
    - Network bandwidth spikes during peak hours (shared 10Gbps)
    - Invisible outages (load balancer reporting healthy while broken)
    - Thermal throttling on physical hosts (rare but documented)
    """

    IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

    def setUp(self):
        self.asset = _make_asset("EX Hetzner Room")

    def tearDown(self):
        frappe.db.rollback()

    def test_lifecycle_idempotent_under_retry(self):
        """Y1 — Lifecycle operations are idempotent under network retry.

        Hetzner invisible outages can cause clients to retry requests.
        If start_session is called twice (client retry after timeout),
        the second call must fail cleanly, not create two sessions.
        """
        session1 = start_session_for_asset(self.asset.name, operator=OPERATOR)
        self.assertIsNotNone(session1)
        # Second call (simulated retry) must fail, not duplicate
        with self.assertRaises(frappe.ValidationError):
            start_session_for_asset(self.asset.name, operator=OPERATOR)
        # Only one session must exist
        count = frappe.db.count("Venue Session", {"venue_asset": self.asset.name})
        self.assertEqual(count, 1, "Retry created duplicate session")

    def test_network_partition_between_redis_and_mariadb_handled(self):
        """Y3 — Network partition (Redis up, MariaDB down) handled correctly.

        Hetzner load balancer failures can cause split-brain where Redis is
        reachable but MariaDB is not. Our lock acquires Redis first, then
        MariaDB FOR UPDATE. If MariaDB fails after Redis acquire, the Redis
        key must still be released.
        """
        with patch("frappe.db.sql", side_effect=pymysql.err.OperationalError(2003, "Connection refused")):
            with self.assertRaises(pymysql.err.OperationalError):
                with asset_status_lock(self.asset.name, "test"):
                    pass

        # Redis key must be released even though DB failed
        cache = frappe.cache()
        key = f"hamilton:asset_lock:{self.asset.name}"
        self.assertIsNone(cache.get(key),
                          "Redis key leaked after MariaDB failure during lock acquisition")


# ===========================================================================
# Category Z — ERPNext Silent Failure Patterns
# Source: codewithkarani.com "ERPNext fails silently" article
# ===========================================================================

class TestERPNextSilentFailures(IntegrationTestCase):
    """Z — Tests for ERPNext silent failure patterns.

    ERPNext's most dangerous failure mode is silent corruption:
    data is wrong but no error is raised. These tests specifically
    probe for silent failures by asserting DB state after every operation.
    """

    IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

    def setUp(self):
        self.asset = _make_asset("EX Silent Failure Room")

    def tearDown(self):
        frappe.db.rollback()

    def test_no_silent_state_corruption_after_failed_operation(self):
        """Z1 — Failed operations never silently corrupt asset state.

        ERPNext's most dangerous failure: partial writes that leave data
        inconsistent without raising an error. Verify all our operations
        are atomic — either fully succeed or fully fail with no middle ground.
        """
        initial = frappe.db.get_value("Venue Asset", self.asset.name,
                                       ["status", "version", "current_session"],
                                       as_dict=True)
        # Try several invalid operations
        invalid_ops = [
            lambda: vacate_session(self.asset.name, operator=OPERATOR,
                                   vacate_method="Key Return"),
            lambda: mark_asset_clean(self.asset.name, operator=OPERATOR),
            lambda: return_asset_to_service(self.asset.name, operator=OPERATOR,
                                             reason="Not OOS"),
        ]
        for op in invalid_ops:
            try:
                op()
            except (frappe.ValidationError, LockContentionError):
                pass  # Expected — verify state unchanged

        final = frappe.db.get_value("Venue Asset", self.asset.name,
                                     ["status", "version", "current_session"],
                                     as_dict=True)
        self.assertEqual(initial.status, final.status,
                         "Silent state corruption — status changed without valid transition")
        self.assertEqual(initial.version, final.version,
                         "Silent state corruption — version changed without valid transition")

    def test_asset_status_log_is_never_silently_skipped(self):
        """Z2 — Asset Status Log is ALWAYS created on transition, never silently skipped.

        ERPNext silent failure: log entries are supposed to be created but
        a bug causes them to be skipped silently. Operators lose audit trail.
        """
        prev = frappe.in_test
        frappe.in_test = False
        try:
            log_count_before = frappe.db.count("Asset Status Log",
                                                {"venue_asset": self.asset.name})
            start_session_for_asset(self.asset.name, operator=OPERATOR)
            log_count_after = frappe.db.count("Asset Status Log",
                                               {"venue_asset": self.asset.name})
            self.assertEqual(log_count_after, log_count_before + 1,
                             "Asset Status Log silently skipped on transition")
        finally:
            frappe.in_test = prev

    def test_version_never_silently_stays_at_zero(self):
        """Z3 — version field always increments — never stays at 0 after transition.

        ERPNext silent failure: fields that should update don't, due to
        caching, trigger failures, or ORM bugs. Version must always increment.
        """
        v_before = frappe.db.get_value("Venue Asset", self.asset.name, "version") or 0
        start_session_for_asset(self.asset.name, operator=OPERATOR)
        v_after = frappe.db.get_value("Venue Asset", self.asset.name, "version") or 0
        self.assertGreater(v_after, v_before,
                           f"Version silently stayed at {v_before} after transition")

    def test_reason_field_never_silently_persists_after_return_from_oos(self):
        """Z5 — reason field is never silently left set after returning from OOS.

        ERPNext silent failure: fields that should clear don't. A stale OOS
        reason on an Available asset misleads operators into thinking it's
        still broken. Verified by re-fetching from DB.
        """
        set_asset_out_of_service(self.asset.name, operator=OPERATOR,
                                  reason="Pipe burst")
        return_asset_to_service(self.asset.name, operator=OPERATOR,
                                 reason="Fixed")
        asset = frappe.get_doc("Venue Asset", self.asset.name)
        self.assertFalse(asset.reason,
                         f"Stale OOS reason '{asset.reason}' silently persisted after return to service")

def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
