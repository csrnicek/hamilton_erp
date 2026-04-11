"""Unit-style tests for hamilton_erp.lifecycle helper functions.

Task 3 covers only the pure helpers — transition validation.
Tasks 4–8 add integration tests against the real DB for each
whitelisted lifecycle function.

Note: this module lives at the package root (same level as api.py,
locks.py, test_locks.py). We intentionally do NOT set
IGNORE_TEST_RECORD_DEPENDENCIES — Frappe v16's IntegrationTestCase
can't auto-detect cls.doctype for package-root modules, so it skips
test-record generation entirely and there's no cascade to break.
"""
import uuid

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle


class TestLifecycleHelpers(IntegrationTestCase):
	def test_valid_transitions_map(self):
		t = lifecycle.VALID_TRANSITIONS
		self.assertIn("Occupied", t["Available"])
		self.assertIn("Dirty", t["Occupied"])
		self.assertIn("Available", t["Dirty"])
		self.assertIn("Out of Service", t["Available"])
		self.assertIn("Available", t["Out of Service"])

	def test_require_transition_passes_on_valid(self):
		row = {"name": "VA-0001", "status": "Available", "version": 0}
		lifecycle._require_transition(row, current="Available",
		                              target="Occupied", asset_name="VA-0001")

	def test_require_transition_throws_on_mismatch(self):
		row = {"name": "VA-0001", "status": "Dirty", "version": 0}
		with self.assertRaises(frappe.ValidationError):
			lifecycle._require_transition(row, current="Available",
			                              target="Occupied", asset_name="VA-0001")

	def test_require_oos_entry_throws_on_already_oos(self):
		row = {"name": "VA-0001", "status": "Out of Service", "version": 0}
		with self.assertRaises(frappe.ValidationError):
			lifecycle._require_oos_entry(row, asset_name="VA-0001")

	def test_require_oos_entry_passes_on_other_states(self):
		for status in ("Available", "Occupied", "Dirty"):
			row = {"name": "VA-0001", "status": status, "version": 0}
			lifecycle._require_oos_entry(row, asset_name="VA-0001")  # no raise

	def test_log_helper_skipped_in_test_flag(self):
		"""Grok review: Asset Status Log helper short-circuits when in_test is set."""
		prev_flag = frappe.flags.in_test
		frappe.flags.in_test = True
		try:
			result = lifecycle._make_asset_status_log(
				asset_name="VA-0001",
				previous="Available",
				new_status="Occupied",
				reason=None,
				operator="test@example.com",
				venue_session=None,
			)
			self.assertIsNone(result)
		finally:
			frappe.flags.in_test = prev_flag


class TestStartSession(IntegrationTestCase):
	def setUp(self):
		# Walk-in customer is required (DEC-055 §1). The seed patch creates it,
		# but this test runs before Task 11, so create it here as a local fixture.
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"START-TEST-{suffix.upper()}",
			"asset_name": f"Start Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9002,
			"version": 0,
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_start_session_flips_asset_to_occupied(self):
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Occupied")
		self.assertEqual(asset.current_session, session_name)
		self.assertEqual(asset.version, 1)
		# Review 2026-04-10: lock the contract Tasks 5-8 will copy — every
		# transition stamps hamilton_last_status_change.
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_start_session_creates_venue_session(self):
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)
		s = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(s.venue_asset, self.asset.name)
		self.assertEqual(s.assignment_status, "Assigned")
		self.assertEqual(s.operator_checkin, "Administrator")
		self.assertEqual(s.status, "Active")
		self.assertIsNotNone(s.session_start)

	def test_start_session_rejects_non_available(self):
		# Walk the transitions legally: Available → Occupied → Dirty,
		# because VenueAsset._validate_status_transition rejects illegal edges.
		self.asset.status = "Occupied"
		self.asset.save(ignore_permissions=True)
		self.asset.status = "Dirty"
		self.asset.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Dirty")


class TestVacateSession(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"VACATE-TEST-{suffix.upper()}",
			"asset_name": f"Vacate Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9003,
			"version": 0,
		}).insert(ignore_permissions=True)
		self.session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_vacate_moves_to_dirty(self):
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Dirty")
		self.assertIsNone(asset.current_session)
		self.assertIsNotNone(asset.last_vacated_at)
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for vacate.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_vacate_closes_session(self):
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		s = frappe.get_doc("Venue Session", self.session_name)
		self.assertEqual(s.status, "Completed")
		self.assertEqual(s.operator_vacate, "Administrator")
		self.assertEqual(s.vacate_method, "Key Return")
		self.assertIsNotNone(s.session_end)

	def test_vacate_rejects_non_occupied(self):
		# Move asset to Dirty first so it's no longer Occupied
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator", vacate_method="Key Return"
			)
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Dirty")

	def test_vacate_requires_valid_method(self):
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator", vacate_method="Nonsense"
			)

	def test_vacate_rejects_oos_asset(self):
		"""OOS → vacate must throw.

		3-AI review 2026-04-10: closes the gap where test_vacate_rejects_non_occupied
		only covers Dirty → vacate. Walk the asset Occupied → OOS via the real
		pipeline (set_asset_out_of_service auto-closes the linked session via
		Discovery on Rounds), then attempt vacate_session and assert rejection.
		"""
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Maintenance"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator", vacate_method="Key Return"
			)
		# Lock release after rejection — same invariant as the other tests.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Out of Service")


class TestMarkClean(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		# VenueAsset._validate_status_transition requires new assets to start
		# as Available, so walk the state machine Available → Occupied → Dirty.
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"CLEAN-TEST-{suffix.upper()}",
			"asset_name": f"Clean Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9004,
			"version": 0,
		}).insert(ignore_permissions=True)
		self.asset.status = "Occupied"
		self.asset.save(ignore_permissions=True)
		self.asset.status = "Dirty"
		self.asset.save(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_mark_clean_moves_dirty_to_available(self):
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")
		self.assertIsNotNone(asset.last_cleaned_at)
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for mark-clean.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_mark_clean_rejects_non_dirty(self):
		self.asset.status = "Available"
		self.asset.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Available")

	def test_mark_clean_accepts_bulk_reason(self):
		"""Bulk reason must be propagated as log_reason to _set_asset_status.

		DEC-054 §5: bulk reason is written to the Asset Status Log row's reason
		field. We mock _set_asset_status to verify the kwarg wiring at the unit
		layer without depending on Task 11's log-creation integration.
		"""
		from unittest.mock import patch
		target = "hamilton_erp.lifecycle._set_asset_status"
		with patch(target, wraps=lifecycle._set_asset_status) as spy:
			lifecycle.mark_asset_clean(
				self.asset.name, operator="Administrator",
				bulk_reason="Bulk Mark Clean — Room reset",
			)
		spy.assert_called_once()
		self.assertEqual(
			spy.call_args.kwargs["log_reason"],
			"Bulk Mark Clean — Room reset",
		)
		# Happy-path still sanity-checked so a broken _set_asset_status doesn't
		# hide behind the spy.
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")


class TestSetOutOfService(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"OOS-TEST-{suffix.upper()}",
			"asset_name": f"OOS Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9005,
			"version": 0,
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_oos_from_available(self):
		"""Happy path + assert `reason` kwarg reaches _set_asset_status as log_reason.

		The wraps= pattern (from Task 6 fix bundle) records call args while
		still invoking the real implementation, so the status/reason-field
		assertions below still fire.
		"""
		from unittest.mock import patch
		target = "hamilton_erp.lifecycle._set_asset_status"
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		with patch(target, wraps=lifecycle._set_asset_status) as spy:
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="Plumbing failure"
			)
		spy.assert_called_once()
		self.assertEqual(spy.call_args.kwargs["log_reason"], "Plumbing failure")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Out of Service")
		self.assertEqual(asset.reason, "Plumbing failure")
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for OOS entry.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_oos_from_occupied_closes_session(self):
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Emergency"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Out of Service")
		s = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(s.status, "Completed")
		self.assertEqual(s.vacate_method, "Discovery on Rounds")

	def test_oos_from_dirty(self):
		"""Dirty → OOS routes through the `else` branch (log_venue_session=None).

		Locks in the invariant that vacate_session clears current_session,
		so a Dirty asset entering OOS has no session to link in the audit log.
		Walk the asset through the real pipeline (start → vacate → oos) rather
		than raw save() so the invariant is exercised end-to-end.
		"""
		lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		# Asset is now Dirty with current_session=None (vacate_session invariant).
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Plumbing after turnover"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Out of Service")
		self.assertEqual(asset.reason, "Plumbing after turnover")
		# The load-bearing invariant: Dirty assets have no current_session, so
		# OOS-from-Dirty cannot link the audit log back to any session.
		self.assertIsNone(asset.current_session)

	def test_oos_requires_reason(self):
		# Empty string
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason=""
			)
		# Whitespace-only — covered by `not reason.strip()` branch
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="   \t\n  "
			)

	def test_oos_reject_if_already_oos(self):
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="First"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="Second"
			)
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Out of Service")


class TestReturnToService(IntegrationTestCase):
	def setUp(self):
		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"RETURN-TEST-{suffix.upper()}",
			"asset_name": f"Return Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9006,
			"version": 0,
		}).insert(ignore_permissions=True)
		# Walk to OOS via the real production pipeline (Task 7's function).
		# Raw-inserting with status="Out of Service" is blocked by the
		# "New assets must start as Available" guard in venue_asset.py.
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Initial OOS"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_return_moves_to_available(self):
		"""Happy path + assert `reason` kwarg reaches _set_asset_status as log_reason.

		Also locks in the Gemini-review requirement that OOS → Available
		clears asset.reason via the new elif branch in _set_asset_status.
		"""
		from unittest.mock import patch
		target = "hamilton_erp.lifecycle._set_asset_status"
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		with patch(target, wraps=lifecycle._set_asset_status) as spy:
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator", reason="Repair done"
			)
		spy.assert_called_once()
		self.assertEqual(spy.call_args.kwargs["log_reason"], "Repair done")
		self.assertEqual(spy.call_args.kwargs["previous"], "Out of Service")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")
		self.assertIsNotNone(asset.last_cleaned_at)
		# Gemini review 2026-04-10: OOS → Available MUST clear asset.reason.
		# The setUp seeds "Initial OOS", so any regression in the reason-
		# clearing else branch of _set_asset_status fails loudly here.
		self.assertFalse(asset.reason)
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for return-to-service.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_return_requires_reason(self):
		with self.assertRaises(frappe.ValidationError):
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator", reason="   "
			)

	def test_return_rejects_non_oos(self):
		# Walk the asset back to Available via the real pipeline so the
		# state machine guards are respected.
		lifecycle.return_asset_to_service(
			self.asset.name, operator="Administrator", reason="Pre-reject reset"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator", reason="any"
			)
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Available")
