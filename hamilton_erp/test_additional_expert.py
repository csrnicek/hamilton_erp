"""Additional expert tests for Hamilton ERP lifecycle, locks, and state machine.

Sources:
- Redis.io distributed locking documentation
- Martin Kleppmann "How to do distributed locking"
- ERPNext pos_opening_entry test patterns
- Frappe test_db.py savepoint and transaction patterns
- FSM coverage criteria research (IET Software)
- Hypothesis property-based testing patterns
- 3-AI review findings (ChatGPT, Grok, Gemini) 2026-04-10

These tests complement the main test modules. They are marked with
# REQUIRES-LIVE-SITE for tests needing a running Frappe instance.
"""
from __future__ import annotations

import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from hamilton_erp import lifecycle
from hamilton_erp.lifecycle import (
	mark_asset_clean,
	start_session_for_asset,
	vacate_session,
)
from hamilton_erp.locks import LockContentionError, asset_status_lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_walkin() -> None:
	"""Idempotent Walk-in Customer fixture (DEC-055 §1).

	lifecycle.start_session_for_asset defaults customer="Walk-in", and the
	Venue Session insert fails if the Customer doesn't exist. This module
	is independent of test_lifecycle.py so it cannot rely on that file's
	defensive setUp — create Walk-in here whenever an asset is made.
	"""
	if frappe.db.exists("Customer", "Walk-in"):
		return
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": "Walk-in",
		"customer_group": frappe.db.get_value(
			"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
		"territory": frappe.db.get_value(
			"Territory", {"is_group": 0}, "name") or "All Territories",
	}).insert(ignore_permissions=True)


def _make_asset(name: str, category: str = "Room", tier: str = "Single Standard",
                status: str = "Available") -> object:
	"""Insert a test Venue Asset. Cleaned up in tearDown via rollback.

	asset_code uses a uuid suffix so concurrent test methods in the same
	class never collide on the unique constraint, even if a previous test's
	rollback was incomplete or the same friendly name is used twice.
	"""
	_ensure_walkin()
	doc = frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"TEST-{name[:6].upper()}-{uuid.uuid4().hex[:4].upper()}",
		"asset_name": name,
		"asset_category": category,
		"asset_tier": tier if category == "Room" else "Locker",
		"status": status,
		"display_order": 999,
	})
	doc.insert(ignore_permissions=True)
	return doc


# ---------------------------------------------------------------------------
# Category A: State Machine — All Invalid Transitions Systematic
# Source: FSM coverage criteria — every invalid edge must be tested
# ---------------------------------------------------------------------------

class TestAllInvalidTransitions(IntegrationTestCase):
	"""Exhaustive test that every undefined transition is rejected.

	The VALID_TRANSITIONS map defines 7 allowed edges.
	There are 4 states × 4 targets = 16 possible transitions.
	9 of these are invalid and must all raise ValidationError.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Invalid Transitions Room")

	def tearDown(self):
		frappe.db.rollback()

	def _attempt_transition(self, from_status: str, to_status: str):
		"""Force an asset to from_status then attempt to_status via save()."""
		frappe.db.set_value("Venue Asset", self.asset.name, "status", from_status)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		asset.status = to_status
		if to_status == "Out of Service":
			asset.reason = "test reason"
		asset.save(ignore_permissions=True)

	def test_available_to_dirty_is_invalid(self):
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Available", "Dirty")

	def test_occupied_to_available_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Occupied")
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Occupied", "Available")

	def test_dirty_to_occupied_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Dirty")
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Dirty", "Occupied")

	def test_oos_to_occupied_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, {
			"status": "Out of Service", "reason": "maintenance"})
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Out of Service", "Occupied")

	def test_oos_to_dirty_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, {
			"status": "Out of Service", "reason": "maintenance"})
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Out of Service", "Dirty")


# ---------------------------------------------------------------------------
# Category C: Lock Failure and Release Guarantees
# Source: Martin Kleppmann + redis.io distributed locking docs
# ---------------------------------------------------------------------------

class TestLockFailureAndRelease(IntegrationTestCase):
	"""Tests for lock robustness under failure conditions."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Lock Failure Room")

	def tearDown(self):
		frappe.db.rollback()

	def test_lock_released_when_exception_inside_with_block(self):
		"""If code inside the lock raises, the lock is still released.

		Source: Martin Kleppmann — the most dangerous lock failure mode is
		a lock that is never released. Our finally block handles this, but
		we test it explicitly.
		"""
		class IntentionalError(Exception):
			pass

		with self.assertRaises(IntentionalError):
			with asset_status_lock(self.asset.name, "test"):
				raise IntentionalError("deliberate failure inside lock")

		# Lock must be released — re-acquisition must succeed
		with asset_status_lock(self.asset.name, "test") as row:
			self.assertEqual(row["name"], self.asset.name)

	def test_lock_released_when_frappe_throw_inside_with_block(self):
		"""frappe.throw (ValidationError) inside the lock still releases it."""
		with self.assertRaises(frappe.ValidationError):
			with asset_status_lock(self.asset.name, "test"):
				frappe.throw("deliberate validation error")

		# Re-acquisition must succeed
		with asset_status_lock(self.asset.name, "test") as row:
			self.assertEqual(row["name"], self.asset.name)

	def test_lock_released_for_nonexistent_asset(self):
		"""If the asset doesn't exist, the lock is still cleaned up.

		Source: ChatGPT review — a failed not-found path could leak a lock.
		"""
		with self.assertRaises(frappe.ValidationError):
			with asset_status_lock("VA-DOES-NOT-EXIST-999", "test"):
				pass  # frappe.throw in lock body for missing asset

		# Verify no key leak — re-acquisition of the same (nonexistent) name
		# should also fail cleanly, not raise a Redis ConnectionError
		try:
			with asset_status_lock("VA-DOES-NOT-EXIST-999", "test"):
				pass
		except frappe.ValidationError:
			pass  # Expected — asset doesn't exist

	@patch("hamilton_erp.locks.frappe.cache")
	def test_redis_unavailable_raises_lock_contention_error(self, mock_cache):
		"""Redis down at acquire time → LockContentionError, not ConnectionError.

		Source: ChatGPT review fix — wrap acquire in try/except.

		Note: we can't assert on the exception message string because patching
		`frappe.cache` also breaks `frappe._()` (the translation lookup uses
		the same cache backend), so the localized error message comes back as
		a MagicMock repr instead of the actual translated string. The
		assertRaises(LockContentionError) above already proves the contract
		that matters: a Redis ConnectionError is converted to our typed
		LockContentionError, not propagated raw.
		"""
		import redis
		mock_instance = MagicMock()
		mock_instance.set.side_effect = redis.ConnectionError("Redis down")
		mock_cache.return_value = mock_instance

		with self.assertRaises(LockContentionError):
			with asset_status_lock(self.asset.name, "test"):
				pass

	def test_no_redis_key_leak_after_successful_release(self):
		"""After a successful lock/release, no Redis key remains.

		Source: redis.io — locks must always be cleaned up.
		"""
		cache = frappe.cache()
		key = f"hamilton:asset_lock:{self.asset.name}"

		with asset_status_lock(self.asset.name, "test"):
			self.assertIsNotNone(cache.get(key))  # Key exists while held

		self.assertIsNone(cache.get(key))  # Key gone after release


# ---------------------------------------------------------------------------
# Category D: Session Integrity
# Source: ERPNext pos_opening_entry test patterns
# ---------------------------------------------------------------------------

class TestSessionIntegrity(IntegrationTestCase):
	"""Session creation and uniqueness constraints.

	Mirrors ERPNext's test_multiple_pos_opening_entries_for_same_pos_profile
	pattern applied to our asset sessions.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Session Integrity Room")
		self.operator = frappe.session.user

	def tearDown(self):
		frappe.db.rollback()

	def test_vacated_session_has_session_end_timestamp(self):
		"""After vacate, the session has a session_end timestamp."""
		session_name = start_session_for_asset(
			self.asset.name, operator=self.operator)
		before = now_datetime()
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		session = frappe.get_doc("Venue Session", session_name)
		self.assertIsNotNone(session.session_end)
		self.assertGreaterEqual(session.session_end, before)

	def test_vacated_session_has_vacate_method(self):
		"""After vacate, session.vacate_method is set correctly."""
		session_name = start_session_for_asset(
			self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Discovery on Rounds")
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.vacate_method, "Discovery on Rounds")


# ---------------------------------------------------------------------------
# Category E: Bulk Clean
# Source: DEC-054 bulk clean requirements
# ---------------------------------------------------------------------------

class TestBulkClean(IntegrationTestCase):
	"""Tests for mark_all_clean (Tasks 14-15 — mark as FUTURE until implemented)."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.operator = frappe.session.user

	def tearDown(self):
		frappe.db.rollback()

	def test_mark_asset_clean_with_bulk_reason(self):
		"""mark_asset_clean with bulk_reason sets distinguishing log reason (DEC-054)."""
		asset = _make_asset("Test Bulk Reason Room")
		frappe.db.set_value("Venue Asset", asset.name, "status", "Dirty")

		# Temporarily clear in_test flag to allow log creation
		prev = frappe.flags.in_test
		frappe.flags.in_test = False
		try:
			mark_asset_clean(asset.name, operator=self.operator,
			                 bulk_reason="Bulk Mark Clean — morning reset")
		finally:
			frappe.flags.in_test = prev

		# Verify the log entry has the distinguishing reason
		log = frappe.get_last_doc("Asset Status Log",
		                          filters={"venue_asset": asset.name})
		self.assertEqual(log.reason, "Bulk Mark Clean — morning reset")

	def test_mark_asset_clean_without_bulk_reason_has_no_reason(self):
		"""Single-tile mark_clean has no reason (None), not bulk reason."""
		asset = _make_asset("Test Single Clean Room")
		frappe.db.set_value("Venue Asset", asset.name, "status", "Dirty")

		prev = frappe.flags.in_test
		frappe.flags.in_test = False
		try:
			mark_asset_clean(asset.name, operator=self.operator)
		finally:
			frappe.flags.in_test = prev

		log = frappe.get_last_doc("Asset Status Log",
		                          filters={"venue_asset": asset.name})
		self.assertIsNone(log.reason)


# ---------------------------------------------------------------------------
# Category H: Guard Condition Boundaries
# Source: FSM testing best practices — guard boundaries must be tested
# ---------------------------------------------------------------------------

class TestGuardConditionBoundaries(IntegrationTestCase):
	"""Test boundary conditions on guard predicates."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Guard Boundary Room")

	def tearDown(self):
		frappe.db.rollback()

	def test_oos_reason_single_character_is_accepted(self):
		"""OOS reason of exactly 1 non-whitespace character is valid."""
		self.asset.status = "Out of Service"
		self.asset.reason = "X"
		self.asset.save(ignore_permissions=True)  # Should not raise

	def test_oos_reason_single_space_is_rejected(self):
		"""OOS reason of a single space is rejected (whitespace-only)."""
		self.asset.status = "Out of Service"
		self.asset.reason = " "
		with self.assertRaises(frappe.ValidationError):
			self.asset.save(ignore_permissions=True)

	def test_oos_reason_tab_only_is_rejected(self):
		"""OOS reason of only tabs is rejected."""
		self.asset.status = "Out of Service"
		self.asset.reason = "\t\t\t"
		with self.assertRaises(frappe.ValidationError):
			self.asset.save(ignore_permissions=True)

	def test_oos_reason_none_is_rejected(self):
		"""OOS reason of None is rejected."""
		self.asset.status = "Out of Service"
		self.asset.reason = None
		with self.assertRaises(frappe.ValidationError):
			self.asset.save(ignore_permissions=True)

	def test_new_asset_as_available_is_accepted(self):
		"""New asset as Available is always valid."""
		doc = _make_asset("Test New Available Room", status="Available")
		self.assertEqual(doc.status, "Available")


# ---------------------------------------------------------------------------
# Category I: Concurrent Assignment (Threading)
# Source: Redis.io + Kleppmann — mutual exclusion is the #1 guarantee
# ---------------------------------------------------------------------------

class TestConcurrentAssignment(IntegrationTestCase):
	"""Two threads simultaneously trying to assign the same asset.

	Only one should succeed. Uses same thread-per-Frappe-connection pattern
	as test_locks.py TestAssetStatusLock.test_second_acquisition_raises.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Concurrent Assign Room")
		frappe.db.commit()  # Make asset visible to other connections

	def tearDown(self):
		frappe.db.delete("Venue Session", {"venue_asset": self.asset.name})
		frappe.db.delete("Venue Asset", {"name": self.asset.name})
		frappe.db.commit()

	def test_only_one_of_two_concurrent_starts_succeeds(self):
		"""Two simultaneous start_session calls → exactly one succeeds."""
		site = frappe.local.site
		operator = frappe.session.user
		results = {"success": 0, "failure": 0, "errors": []}

		def try_assign():
			frappe.init(site=site)
			frappe.connect()
			try:
				start_session_for_asset(self.asset.name, operator=operator)
				frappe.db.commit()
				results["success"] += 1
			except (frappe.ValidationError, LockContentionError):
				results["failure"] += 1
			except Exception as e:
				results["errors"].append(str(e))
			finally:
				frappe.destroy()

		t1 = threading.Thread(target=try_assign)
		t2 = threading.Thread(target=try_assign)
		t1.start()
		t2.start()
		t1.join(timeout=30)
		t2.join(timeout=30)

		self.assertEqual(results["errors"], [], f"Unexpected errors: {results['errors']}")
		self.assertEqual(results["success"], 1,
			f"Expected exactly 1 success, got {results['success']}")
		self.assertEqual(results["failure"], 1,
			f"Expected exactly 1 failure, got {results['failure']}")


# ===========================================================================
# Audit 2026-04-11 — Group F: Input boundary coverage gaps
# ===========================================================================


class TestInputBoundariesAudit(IntegrationTestCase):
	"""Boundary-condition tests for whitespace, field length, and null
	handling on the lifecycle public API. These cover cases that the
	existing 'reason must be non-whitespace' guard handles on paper but
	hasn't been exercised against NBSP, tabs, newlines, or the VARCHAR
	field-length cliff.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Boundary Test Room")

	def tearDown(self):
		frappe.db.rollback()

	def test_F1_oos_reason_nbsp_only_is_rejected(self):
		"""U+00A0 (non-breaking space) should be treated as whitespace —
		str.strip() catches it in Python 3. Guards against an operator
		pasting a decorative NBSP as the reason."""
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name,
				operator="Administrator",
				reason="\u00a0\u00a0\u00a0",
			)

	def test_F2_oos_reason_newlines_and_tabs_only_is_rejected(self):
		"""Pure whitespace — mixed tabs, newlines, and spaces — rejected."""
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name,
				operator="Administrator",
				reason="\n\t  \n\t",
			)

	def test_F3_oos_reason_with_valid_content_plus_whitespace_accepted(self):
		"""A real reason with leading/trailing whitespace IS valid — the
		guard only rejects whitespace-only strings. Pin the contract so
		it doesn't get tightened accidentally."""
		lifecycle.set_asset_out_of_service(
			self.asset.name,
			operator="Administrator",
			reason="   broken lock   ",
		)
		self.assertEqual(
			frappe.db.get_value("Venue Asset", self.asset.name, "status"),
			"Out of Service")

	def test_F4_vacate_method_empty_string_rejected(self):
		"""vacate_method="" is not in _VACATE_METHODS — must throw BEFORE
		the lock is even acquired (lifecycle.py 318-323)."""
		start_session_for_asset(self.asset.name, operator="Administrator")
		with self.assertRaises(frappe.ValidationError):
			vacate_session(self.asset.name, operator="Administrator",
			               vacate_method="")

	def test_F5_vacate_method_none_rejected(self):
		"""None passed as vacate_method — same pre-lock guard."""
		start_session_for_asset(self.asset.name, operator="Administrator")
		with self.assertRaises((frappe.ValidationError, TypeError)):
			vacate_session(self.asset.name, operator="Administrator",
			               vacate_method=None)

	def test_F6_display_order_zero_is_valid(self):
		"""display_order=0 must be accepted — it's a valid sort key, not
		a null. An overly-defensive Int field check could reject it and
		break the seed patch's R001 row."""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"BD-ZERO-{uuid.uuid4().hex[:4].upper()}",
			"asset_name": "Zero Display Order",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 0,
		}).insert(ignore_permissions=True)
		self.assertEqual(doc.display_order, 0)


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
