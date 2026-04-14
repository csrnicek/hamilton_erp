"""Phase 1 end-to-end QA test cases H10, H11, H12.

These tests exercise the full stack: lifecycle.py + venue_asset
whitelisted methods + Asset Status Log auto-create. They turn
off frappe.flags.in_test inside each test so the status log
path is exercised (the default guard is helpful for unit tests
at scale but E2E tests must verify the real log).

Task 22 adds H10 (Vacate and Turnover).
Task 23 adds H11 (Out of Service).
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


def tearDownModule():
	"""Restore dev state wiped by this module's tests."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
