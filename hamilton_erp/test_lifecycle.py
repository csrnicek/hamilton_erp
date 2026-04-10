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
