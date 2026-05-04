"""DEC-103 — backend tests for the comp_admission endpoint.

Covers:
  - Operator-only role is rejected via PermissionError
  - Missing reason throws ValidationError
  - Happy path: occupies the asset, creates the Comp Admission Log,
    stamps comp_flag = 1 on the Venue Session
  - get_asset_board_data exposes is_comp on Occupied tiles
"""
import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import api
from hamilton_erp.patches.v0_1 import seed_hamilton_env


class TestCompAdmissionRoleGate(IntegrationTestCase):
	"""Operator-only user cannot call comp_admission."""

	def test_operator_only_user_is_rejected(self):
		original_user = frappe.session.user
		try:
			email = "operator-comp-test@example.com"
			if not frappe.db.exists("User", email):
				user = frappe.get_doc({
					"doctype": "User",
					"email": email,
					"first_name": "OperatorComp",
					"send_welcome_email": 0,
				})
				user.insert(ignore_permissions=True)
			frappe.db.sql(
				"DELETE FROM `tabHas Role` WHERE parent = %s",
				(email,),
			)
			frappe.db.commit()
			user = frappe.get_doc("User", email)
			user.append("roles", {"role": "Hamilton Operator"})
			user.save(ignore_permissions=True)
			frappe.db.commit()
			frappe.set_user(email)
			with self.assertRaises(frappe.PermissionError):
				api.comp_admission("any-asset", "test reason")
		finally:
			frappe.set_user(original_user)


class TestCompAdmissionValidation(IntegrationTestCase):
	def test_missing_reason_throws(self):
		with self.assertRaises(frappe.ValidationError):
			api.comp_admission("any-asset", "")
		with self.assertRaises(frappe.ValidationError):
			api.comp_admission("any-asset", "   ")

	def test_missing_asset_name_throws(self):
		with self.assertRaises(frappe.ValidationError):
			api.comp_admission("", "valid reason")


class TestCompAdmissionHappyPath(IntegrationTestCase):
	"""End-to-end on a seeded asset."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		seed_hamilton_env.execute()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		# Flush today's session-counter Redis key (matches test_api_phase1).
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		frappe.cache().delete(f"hamilton:session_seq:{prefix}")
		frappe.db.commit()
		super().tearDownClass()

	def _pick_available_asset(self) -> str:
		row = frappe.db.get_value(
			"Venue Asset",
			{"status": "Available", "is_active": 1},
			"name",
		)
		if not row:
			self.skipTest("No Available asset in seeded inventory.")
		return row

	def test_comp_admission_occupies_asset_and_logs(self):
		asset_name = self._pick_available_asset()
		result = api.comp_admission(asset_name, reason="VIP loyalty comp")
		self.assertEqual(result["status"], "ok")
		self.assertIn("session", result)
		self.assertIn("comp_admission_log", result)

		# Session has comp_flag = 1. Status options on Venue Session are
		# Active / Completed (no Occupied — that's the Venue Asset
		# vocabulary, not Venue Session).
		session = frappe.get_doc("Venue Session", result["session"])
		self.assertEqual(session.status, "Active")
		self.assertEqual(int(session.comp_flag or 0), 1)

		# Comp Admission Log row exists with our reason.
		log = frappe.get_doc("Comp Admission Log", result["comp_admission_log"])
		self.assertEqual(log.venue_session, result["session"])
		self.assertEqual(log.reason_category, "Manager Decision")
		self.assertEqual(log.reason_note, "VIP loyalty comp")

		# Asset board exposes is_comp = True for the comp-occupied tile.
		data = api.get_asset_board_data()
		comped = next((a for a in data["assets"] if a["name"] == asset_name), None)
		self.assertIsNotNone(comped)
		self.assertTrue(comped.get("is_comp"))


def tearDownModule():
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
