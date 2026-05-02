import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today


class TestCashDrop(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_drop(self, amount: float = 100.0) -> object:
		return frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Administrator",
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": amount,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)

	def test_insert_cash_drop(self):
		drop = self._make_drop(150.0)
		self.assertEqual(drop.declared_amount, 150.0)
		self.assertFalse(drop.reconciled)

	def test_negative_amount_raises(self):
		doc = frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Administrator",
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": -10.0,
				"timestamp": now_datetime(),
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)
