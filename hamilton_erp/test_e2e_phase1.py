"""Phase 1 end-to-end QA test cases H10, H11, H12.

These tests exercise the full stack: lifecycle.py + venue_asset
whitelisted methods + Asset Status Log auto-create. They turn
off frappe.flags.in_test inside each test so the status log
path is exercised (the default guard is helpful for unit tests
at scale but E2E tests must verify the real log).

Task 22 adds H10 (Vacate and Turnover).
Task 23 adds H11 (Out of Service) — 8 tests covering OOS from all
  entry states, reason validation, return cycle, audit trail, version.
Task 24 adds H12 (Occupied Asset Rejection).
"""
import uuid
from contextlib import contextmanager

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle
from hamilton_erp.patches.v0_1 import seed_hamilton_env


@contextmanager
def real_logs():
	"""Temporarily turn off the in_test flag so Asset Status Log is written."""
	prior = frappe.flags.in_test
	frappe.flags.in_test = False
	try:
		yield
	finally:
		frappe.flags.in_test = prior


class TestH10VacateAndTurnover(IntegrationTestCase):
	"""H10: Available → Occupied → Dirty → Available with audit logs at each step."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def setUp(self):
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_name": f"H10 Asset {uuid.uuid4().hex[:6]}",
			"asset_code": f"H10-{uuid.uuid4().hex[:6]}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9100,
			"version": 0,
			"expected_stay_duration": 360,
			"company": frappe.db.get_single_value("Global Defaults", "default_company"),
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	def tearDown(self):
		frappe.db.rollback()

	def test_h10_full_turnover_cycle(self):
		"""Full lifecycle: Available → Occupied → Dirty → Available.

		Verifies:
		- Asset status at each step
		- current_session set then cleared
		- Venue Session created and completed
		- vacate_method recorded
		- last_vacated_at and last_cleaned_at timestamps
		- Exactly 3 Asset Status Log entries in correct order
		"""
		with real_logs():
			# 1. Assign — Available → Occupied
			session = lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Occupied")
			self.assertEqual(a.current_session, session)

			log1 = frappe.get_all(
				"Asset Status Log",
				filters={"venue_asset": self.asset.name, "new_status": "Occupied"},
				fields=["previous_status", "new_status"],
			)
			self.assertEqual(len(log1), 1)
			self.assertEqual(log1[0]["previous_status"], "Available")

			# 2. Vacate — Occupied → Dirty
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Dirty")
			self.assertIsNone(a.current_session)
			self.assertIsNotNone(a.last_vacated_at)

			sess = frappe.get_doc("Venue Session", session)
			self.assertEqual(sess.status, "Completed")
			self.assertEqual(sess.vacate_method, "Key Return")
			self.assertIsNotNone(sess.session_end)

			# 3. Mark Clean — Dirty → Available
			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Available")
			self.assertIsNotNone(a.last_cleaned_at)

			# Three audit log entries total (Occupied, Dirty, Available)
			all_logs = frappe.get_all(
				"Asset Status Log",
				filters={"venue_asset": self.asset.name},
				fields=["previous_status", "new_status"],
				order_by="creation asc",
			)
			self.assertEqual(len(all_logs), 3)
			self.assertEqual(
				[(l["previous_status"], l["new_status"]) for l in all_logs],
				[("Available", "Occupied"),
				 ("Occupied", "Dirty"),
				 ("Dirty", "Available")],
			)

	def test_h10_vacate_discovery_on_rounds(self):
		"""Same cycle but with 'Discovery on Rounds' vacate method."""
		with real_logs():
			session = lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Discovery on Rounds",
			)
			sess = frappe.get_doc("Venue Session", session)
			self.assertEqual(sess.vacate_method, "Discovery on Rounds")
			self.assertEqual(sess.status, "Completed")

			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Available")

	def test_h10_version_increments_through_full_cycle(self):
		"""Version field increments at each transition (3 total)."""
		with real_logs():
			lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.version, 1)

			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.version, 2)

			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.version, 3)

	def test_h10_operator_recorded_on_session(self):
		"""operator_checkin and operator_vacate are recorded on the Venue Session."""
		with real_logs():
			session = lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			sess = frappe.get_doc("Venue Session", session)
			self.assertEqual(sess.operator_checkin, "Administrator")

			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return",
			)
			sess = frappe.get_doc("Venue Session", session)
			self.assertEqual(sess.operator_vacate, "Administrator")

	def test_h10_asset_reusable_after_full_cycle(self):
		"""After a full turnover, the same asset can be occupied again."""
		with real_logs():
			# First cycle
			session1 = lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return",
			)
			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")

			# Second cycle
			session2 = lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			self.assertNotEqual(session1, session2)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Occupied")
			self.assertEqual(a.current_session, session2)


class TestH11OutOfService(IntegrationTestCase):
	"""H11: Out of Service from any state, reason required, return cycle."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def setUp(self):
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_name": f"H11 Asset {uuid.uuid4().hex[:6]}",
			"asset_code": f"H11-{uuid.uuid4().hex[:6]}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9101,
			"version": 0,
			"expected_stay_duration": 360,
			"company": frappe.db.get_single_value("Global Defaults", "default_company"),
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	def tearDown(self):
		frappe.db.rollback()

	def test_h11_oos_from_occupied_with_session_close(self):
		"""H11: OOS on an Occupied asset auto-closes the session and logs the reason."""
		with real_logs():
			session_name = lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Plumbing failure — flooding",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Out of Service")
			self.assertEqual(a.reason, "Plumbing failure — flooding")

			sess = frappe.get_doc("Venue Session", session_name)
			self.assertEqual(sess.status, "Completed")
			self.assertEqual(sess.vacate_method, "Discovery on Rounds")

			# OOS audit log carries the reason
			logs = frappe.get_all(
				"Asset Status Log",
				filters={"venue_asset": self.asset.name, "new_status": "Out of Service"},
				fields=["reason"],
			)
			self.assertEqual(len(logs), 1)
			self.assertEqual(logs[0]["reason"], "Plumbing failure — flooding")

	def test_h11_oos_from_available(self):
		"""H11: OOS from Available — no session to close."""
		with real_logs():
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Scheduled maintenance",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Out of Service")
			self.assertEqual(a.reason, "Scheduled maintenance")
			self.assertIsNone(a.current_session)

	def test_h11_oos_from_dirty(self):
		"""H11: OOS from Dirty state — another valid entry point."""
		with real_logs():
			# Get asset to Dirty: Available → Occupied → Dirty
			lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator"
			)
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Dirty")

			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Biohazard cleanup required",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Out of Service")

	def test_h11_oos_without_reason_rejected(self):
		"""H11: Blank/whitespace reason raises ValidationError."""
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="   "
			)

	def test_h11_return_to_service_cycle(self):
		"""H11: OOS → return to service → Available with last_cleaned_at set."""
		with real_logs():
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Maintenance",
			)
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator",
				reason="Repaired",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.status, "Available")
			self.assertIsNotNone(a.last_cleaned_at)
			# OOS reason is cleared when returning to service
			self.assertFalse(a.reason)

	def test_h11_return_without_reason_rejected(self):
		"""H11: Returning to service with blank reason raises ValidationError."""
		with real_logs():
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Broken lock",
			)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.return_asset_to_service(
					self.asset.name, operator="Administrator",
					reason="",
				)

	def test_h11_full_audit_trail(self):
		"""H11: Full OOS cycle produces correct audit log sequence."""
		with real_logs():
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Pipe burst",
			)
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator",
				reason="Fixed by plumber",
			)
			all_logs = frappe.get_all(
				"Asset Status Log",
				filters={"venue_asset": self.asset.name},
				fields=["previous_status", "new_status"],
				order_by="creation asc",
			)
			self.assertEqual(len(all_logs), 2)
			self.assertEqual(
				[(l["previous_status"], l["new_status"]) for l in all_logs],
				[("Available", "Out of Service"),
				 ("Out of Service", "Available")],
			)

	def test_h11_version_increments(self):
		"""H11: Version increments through OOS and return."""
		with real_logs():
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Maintenance",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.version, 1)

			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator",
				reason="Done",
			)
			a = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(a.version, 2)


def tearDownModule():
	"""Restore dev state wiped by this module's tests."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
