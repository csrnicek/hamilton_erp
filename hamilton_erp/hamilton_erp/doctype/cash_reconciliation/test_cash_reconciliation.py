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
		"""Hamilton Operator must have no permissions on Cash Reconciliation.

		Two independent checks:
		1. DocType JSON has no Hamilton Operator permission row — this is the
		   base permission enforced even before install.py has run.
		2. Custom DocPerm table has no read-granting row — this confirms
		   install.py has not accidentally added operator access at runtime.

		Using both checks prevents the test from passing vacuously when the
		Custom DocPerm table is empty (e.g., on a fresh site).
		"""
		# Check 1: DocType JSON base permissions have no Operator row
		import frappe.permissions
		doctype_perms = frappe.get_meta("Cash Reconciliation").permissions
		operator_rows = [p for p in doctype_perms if p.role == "Hamilton Operator"]
		self.assertEqual(
			len(operator_rows),
			0,
			"Cash Reconciliation DocType JSON must have no Hamilton Operator permission row.",
		)

		# Check 2: Custom DocPerm table has no read-granting row for Operator
		custom_perms = frappe.get_all(
			"Custom DocPerm",
			filters={"parent": "Cash Reconciliation", "role": "Hamilton Operator"},
			fields=["read"],
			order_by="name asc",
		)
		for perm in custom_perms:
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
