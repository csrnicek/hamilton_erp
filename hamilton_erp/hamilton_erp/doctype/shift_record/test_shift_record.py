import unittest
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today, now_datetime, add_to_date


@unittest.skip("Phase 0 stub doctype — out of scope per CLAUDE.md")
class TestShiftRecord(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_record(self, float_expected: float = 200.0, float_actual: float = 200.0) -> object:
		return frappe.get_doc(
			{
				"doctype": "Shift Record",
				"operator": "Administrator",
				"shift_date": today(),
				"shift_start": now_datetime(),
				"status": "Open",
				"float_expected": float_expected,
				"float_actual": float_actual,
			}
		).insert(ignore_permissions=True)

	def test_insert_shift_record(self):
		record = self._make_record()
		self.assertEqual(record.status, "Open")

	def test_float_variance_calculated(self):
		record = self._make_record(float_expected=200.0, float_actual=195.0)
		self.assertAlmostEqual(record.float_variance, -5.0)

	def test_shift_end_before_start_raises(self):
		doc = frappe.get_doc(
			{
				"doctype": "Shift Record",
				"operator": "Administrator",
				"shift_date": today(),
				"shift_start": now_datetime(),
				"shift_end": add_to_date(now_datetime(), hours=-1),
				"status": "Open",
				"float_expected": 200.0,
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)
