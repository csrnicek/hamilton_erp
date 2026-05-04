"""DEC-100 — backend tests for the restock_item endpoint.

The endpoint inserts a Material Receipt Stock Entry (mirroring the seed
pattern) and is role-gated to Hamilton Manager / Hamilton Admin / System
Manager. These tests cover the role gate, the validation guards, and the
happy-path Bin increment.
"""
import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import api


class TestRestockItemRoleGate(IntegrationTestCase):
	"""The endpoint must reject Hamilton Operator role; Manager+ passes."""

	def test_operator_only_user_is_rejected(self):
		"""A user with only Hamilton Operator role gets PermissionError."""
		# Build a temp user with Operator role only. We don't actually
		# call the endpoint as that user — that requires an HTTP round
		# trip — instead we verify the role-classifier returns False
		# for an operator-only user, which is the gate the endpoint
		# uses.
		original_user = frappe.session.user
		try:
			# Create a throwaway user if not present.
			email = "operator-only-test@example.com"
			if not frappe.db.exists("User", email):
				user = frappe.get_doc({
					"doctype": "User",
					"email": email,
					"first_name": "Operator",
					"send_welcome_email": 0,
				})
				user.insert(ignore_permissions=True)
			# Reset roles to Hamilton Operator only.
			frappe.db.sql(
				"DELETE FROM `tabHas Role` WHERE parent = %s",
				(email,),
			)
			frappe.db.commit()
			user = frappe.get_doc("User", email)
			user.append("roles", {"role": "Hamilton Operator"})
			user.save(ignore_permissions=True)
			frappe.db.commit()
			# Switch session.
			frappe.set_user(email)
			self.assertFalse(api._is_manager_or_admin_user())
			with self.assertRaises(frappe.PermissionError):
				api.restock_item("WAT-500", 5)
		finally:
			frappe.set_user(original_user)


class TestRestockItemValidation(IntegrationTestCase):
	"""Guard the input validation surface — runs as Administrator (Manager+)."""

	def test_qty_must_be_positive(self):
		with self.assertRaises(frappe.ValidationError):
			api.restock_item("WAT-500", 0)
		with self.assertRaises(frappe.ValidationError):
			api.restock_item("WAT-500", -3)

	def test_unknown_item_throws(self):
		with self.assertRaises(frappe.ValidationError):
			api.restock_item("DOES-NOT-EXIST-9999", 5)

	def test_missing_item_code_throws(self):
		with self.assertRaises(frappe.ValidationError):
			api.restock_item("", 5)


class TestRestockItemHappyPath(IntegrationTestCase):
	"""End-to-end: Manager+ restocks an existing item → Bin increases."""

	def setUp(self):
		# Skip if the WAT-500 retail item isn't present (fresh-install
		# without retail seed). Fail loudly on partial seed instead of
		# silently no-oping.
		if not frappe.db.exists("Item", "WAT-500"):
			self.skipTest("WAT-500 not seeded on this test site.")

	def _bin_qty(self, item_code: str) -> float:
		warehouse = frappe.db.get_single_value(
			"Stock Settings", "default_warehouse"
		)
		row = frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": warehouse},
			"actual_qty",
		)
		return float(row or 0)

	def test_restock_increments_bin(self):
		before = self._bin_qty("WAT-500")
		result = api.restock_item("WAT-500", 7)
		self.assertEqual(result["status"], "ok")
		self.assertIn("stock_entry", result)
		after = self._bin_qty("WAT-500")
		self.assertAlmostEqual(after - before, 7.0, places=4)


def tearDownModule():
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
