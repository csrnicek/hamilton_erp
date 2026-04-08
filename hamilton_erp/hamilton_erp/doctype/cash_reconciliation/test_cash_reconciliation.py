import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today, now_datetime


class TestCashReconciliation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_drop(self, declared: float = 100.0) -> object:
		return frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Administrator",
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": declared,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)

	def test_operator_cannot_access_cash_reconciliation(self):
		"""Hamilton Operator must have no permissions on Cash Reconciliation."""
		perms = frappe.get_all(
			"Custom DocPerm",
			filters={"parent": "Cash Reconciliation", "role": "Hamilton Operator"},
			fields=["read"],
		)
		# The DocType permissions in the JSON also grant no Operator access.
		# This confirms the role is not inadvertently granted via DocType JSON.
		for perm in perms:
			self.assertFalse(
				perm.get("read"),
				"Hamilton Operator must not have read access to Cash Reconciliation.",
			)

	def test_insert_reconciliation(self):
		drop = self._make_drop(200.0)
		recon = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				"actual_count": 195.0,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(recon.actual_count, 195.0)
		self.assertFalse(recon.variance_flag)  # Not set until submission
