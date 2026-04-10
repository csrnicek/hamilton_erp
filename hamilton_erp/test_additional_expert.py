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
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from hamilton_erp import lifecycle
from hamilton_erp.lifecycle import (
	VALID_TRANSITIONS,
	mark_asset_clean,
	start_session_for_asset,
	vacate_session,
)
from hamilton_erp.locks import LockContentionError, asset_status_lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_asset(name: str, category: str = "Room", tier: str = "Single Standard",
                status: str = "Available") -> object:
	"""Insert a test Venue Asset. Cleaned up in tearDown via rollback."""
	doc = frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"TEST-{name[:8].upper()}",
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

	def test_available_to_available_is_invalid(self):
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Available", "Available")

	def test_occupied_to_available_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Occupied")
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Occupied", "Available")

	def test_occupied_to_occupied_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Occupied")
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Occupied", "Occupied")

	def test_dirty_to_occupied_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Dirty")
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Dirty", "Occupied")

	def test_dirty_to_dirty_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Dirty")
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Dirty", "Dirty")

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

	def test_oos_to_oos_is_invalid(self):
		frappe.db.set_value("Venue Asset", self.asset.name, {
			"status": "Out of Service", "reason": "maintenance"})
		with self.assertRaises(frappe.ValidationError):
			self._attempt_transition("Out of Service", "Out of Service")

	def test_all_valid_transitions_covered_by_valid_map(self):
		"""Verify the 7 valid edges in VALID_TRANSITIONS map are complete."""
		valid_count = sum(len(v) for v in VALID_TRANSITIONS.values())
		self.assertEqual(valid_count, 7,
			"VALID_TRANSITIONS must have exactly 7 valid edges. "
			"If you added a state, update this test.")


# ---------------------------------------------------------------------------
# Category B: Entry/Exit Action Verification
# Source: FSM testing best practices — entry/exit actions are first-class
# ---------------------------------------------------------------------------

class TestEntryExitActions(IntegrationTestCase):
	"""Verify timestamps and fields are set correctly on every transition."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Entry Exit Room")
		self.operator = frappe.session.user

	def test_last_status_change_set_on_transition(self):
		"""hamilton_last_status_change is populated after any status change."""
		before = now_datetime()
		start_session_for_asset(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNotNone(asset.hamilton_last_status_change)
		self.assertGreaterEqual(asset.hamilton_last_status_change, before)

	def test_last_vacated_at_set_on_vacate(self):
		"""last_vacated_at is populated after vacate_session."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		before = now_datetime()
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNotNone(asset.last_vacated_at)
		self.assertGreaterEqual(asset.last_vacated_at, before)

	def test_last_cleaned_at_set_on_mark_clean(self):
		"""last_cleaned_at is populated after mark_asset_clean."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		before = now_datetime()
		mark_asset_clean(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNotNone(asset.last_cleaned_at)
		self.assertGreaterEqual(asset.last_cleaned_at, before)

	def test_version_increments_on_each_transition(self):
		"""version field increments by 1 on every status change."""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		v0 = asset.version or 0

		start_session_for_asset(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.version, v0 + 1)

		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Discovery on Rounds")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.version, v0 + 2)

		mark_asset_clean(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.version, v0 + 3)

	def test_current_session_cleared_on_vacate(self):
		"""asset.current_session is None after vacate (session link cleared)."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNotNone(asset.current_session)

		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNone(asset.current_session)

	def test_current_session_cleared_on_mark_clean(self):
		"""asset.current_session remains None after mark_clean."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		mark_asset_clean(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNone(asset.current_session)


# ---------------------------------------------------------------------------
# Category C: Lock Failure and Release Guarantees
# Source: Martin Kleppmann + redis.io distributed locking docs
# ---------------------------------------------------------------------------

class TestLockFailureAndRelease(IntegrationTestCase):
	"""Tests for lock robustness under failure conditions."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Lock Failure Room")

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
		"""
		import redis
		mock_instance = MagicMock()
		mock_instance.set.side_effect = redis.ConnectionError("Redis down")
		mock_cache.return_value = mock_instance

		with self.assertRaises(LockContentionError) as ctx:
			with asset_status_lock(self.asset.name, "test"):
				pass

		self.assertIn("temporarily unavailable", str(ctx.exception))

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

	def test_start_session_creates_exactly_one_venue_session(self):
		"""start_session creates exactly ONE Venue Session, not zero, not two."""
		before_count = frappe.db.count("Venue Session",
		                               {"venue_asset": self.asset.name})
		start_session_for_asset(self.asset.name, operator=self.operator)
		after_count = frappe.db.count("Venue Session",
		                              {"venue_asset": self.asset.name})
		self.assertEqual(after_count - before_count, 1)

	def test_session_has_correct_operator(self):
		"""Session.operator_checkin matches the operator who started it."""
		session_name = start_session_for_asset(
			self.asset.name, operator=self.operator)
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.operator_checkin, self.operator)

	def test_session_has_correct_asset(self):
		"""Session.venue_asset matches the asset it was started for."""
		session_name = start_session_for_asset(
			self.asset.name, operator=self.operator)
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.venue_asset, self.asset.name)

	def test_vacated_session_is_completed(self):
		"""After vacate, the Venue Session status is Completed.

		Mirrors ERPNext test_cancel_pos_opening_entry_without_invoices.
		"""
		session_name = start_session_for_asset(
			self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.status, "Completed")

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

	def test_same_asset_can_be_reoccupied_after_full_cycle(self):
		"""After complete Available→Occupied→Dirty→Available cycle, asset can be reoccupied.

		Mirrors ERPNext cancel-then-reopen pattern.
		"""
		start_session_for_asset(self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		mark_asset_clean(self.asset.name, operator=self.operator)

		# Must be able to start another session
		session2 = start_session_for_asset(
			self.asset.name, operator=self.operator)
		self.assertIsNotNone(session2)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Occupied")


# ---------------------------------------------------------------------------
# Category E: Bulk Clean
# Source: DEC-054 bulk clean requirements
# ---------------------------------------------------------------------------

class TestBulkClean(IntegrationTestCase):
	"""Tests for mark_all_clean (Tasks 14-15 — mark as FUTURE until implemented)."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.operator = frappe.session.user

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
# Category F: Double-Operation Protection (Concurrency)
# Source: ERPNext multiple-POS-opening-entry tests
# ---------------------------------------------------------------------------

class TestDoubleOperationProtection(IntegrationTestCase):
	"""Tests that rapid double-operations on the same asset fail cleanly.

	These test the application-level guarantees, not just the lock mechanics.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Double Op Room")
		self.operator = frappe.session.user

	def test_double_vacate_second_raises_clean_error(self):
		"""Vacating an already-Dirty asset raises ValidationError, not crash.

		Mirrors ERPNext test_multiple_pos_opening_entries_for_same_pos_profile.
		"""
		start_session_for_asset(self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")

		# Second vacate — asset is now Dirty, not Occupied
		with self.assertRaises(frappe.ValidationError) as ctx:
			vacate_session(self.asset.name, operator=self.operator,
			               vacate_method="Key Return")
		self.assertIn("Dirty", str(ctx.exception) + "Occupied")

	def test_double_start_session_second_raises_clean_error(self):
		"""Starting a session on an already-Occupied asset raises ValidationError."""
		start_session_for_asset(self.asset.name, operator=self.operator)

		with self.assertRaises(frappe.ValidationError):
			start_session_for_asset(self.asset.name, operator=self.operator)

	def test_double_mark_clean_second_raises_clean_error(self):
		"""Marking an already-Available asset clean raises ValidationError."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		mark_asset_clean(self.asset.name, operator=self.operator)

		# Second mark_clean — asset is already Available
		with self.assertRaises(frappe.ValidationError):
			mark_asset_clean(self.asset.name, operator=self.operator)


# ---------------------------------------------------------------------------
# Category G: Data State Assertions
# Source: Frappe test_db.py pattern — always re-fetch from DB, never trust cache
# ---------------------------------------------------------------------------

class TestDataStateAfterOperations(IntegrationTestCase):
	"""Assert exact DB state after each lifecycle operation.

	Uses frappe.get_doc() re-fetch (not in-memory doc) per Frappe test_db.py best practices.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Data State Room")
		self.operator = frappe.session.user

	def test_after_start_session_asset_state_is_fully_correct(self):
		"""After start_session: status=Occupied, current_session set, version=1."""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		initial_version = asset.version or 0

		session_name = start_session_for_asset(
			self.asset.name, operator=self.operator)

		# Re-fetch from DB — never trust in-memory doc
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Occupied")
		self.assertEqual(asset.current_session, session_name)
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_after_vacate_asset_state_is_fully_correct(self):
		"""After vacate: status=Dirty, current_session=None, last_vacated_at set."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		version_before_vacate = asset.version

		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Discovery on Rounds")

		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Dirty")
		self.assertIsNone(asset.current_session)
		self.assertEqual(asset.version, version_before_vacate + 1)
		self.assertIsNotNone(asset.last_vacated_at)

	def test_after_mark_clean_asset_state_is_fully_correct(self):
		"""After mark_clean: status=Available, current_session=None, last_cleaned_at set."""
		start_session_for_asset(self.asset.name, operator=self.operator)
		vacate_session(self.asset.name, operator=self.operator,
		               vacate_method="Key Return")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		version_before_clean = asset.version

		mark_asset_clean(self.asset.name, operator=self.operator)

		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")
		self.assertIsNone(asset.current_session)
		self.assertEqual(asset.version, version_before_clean + 1)
		self.assertIsNotNone(asset.last_cleaned_at)


# ---------------------------------------------------------------------------
# Category H: Guard Condition Boundaries
# Source: FSM testing best practices — guard boundaries must be tested
# ---------------------------------------------------------------------------

class TestGuardConditionBoundaries(IntegrationTestCase):
	"""Test boundary conditions on guard predicates."""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("Test Guard Boundary Room")

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

	def test_new_asset_as_occupied_is_rejected(self):
		"""New asset cannot be inserted directly as Occupied."""
		with self.assertRaises(frappe.ValidationError):
			_make_asset("Test New Occupied Room", status="Occupied")

	def test_new_asset_as_dirty_is_rejected(self):
		"""New asset cannot be inserted directly as Dirty."""
		with self.assertRaises(frappe.ValidationError):
			_make_asset("Test New Dirty Room", status="Dirty")

	def test_new_asset_as_oos_is_rejected(self):
		"""New asset cannot be inserted directly as Out of Service (no reason)."""
		with self.assertRaises(frappe.ValidationError):
			_make_asset("Test New OOS Room", status="Out of Service")

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
