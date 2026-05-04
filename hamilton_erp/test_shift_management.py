"""DEC-099 — backend contract tests for the operator-facing shift management endpoints.

Covers:
  - get_current_shift returns None when no Open shift exists
  - start_shift inserts a Shift Record with the supplied float_expected
  - start_shift refuses a second open for the same operator
  - end_shift flips the record to Closed and stamps shift_end
  - get_shift_summary returns the expected shape
  - _get_hamilton_settings includes float_amount

Lives at the package root alongside test_api_phase1.py for the same
reason — Frappe v16's IntegrationTestCase can't auto-detect cls.doctype
for package-root modules.
"""
import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import api


class TestShiftManagementEndpoints(IntegrationTestCase):
	"""Round-trip tests for the start_shift / end_shift / summary surface."""

	def setUp(self):
		# Wipe any in-flight Shift Records / Cash Drops for the current
		# user so each test starts from a clean slate.
		user = frappe.session.user
		frappe.db.sql(
			"DELETE FROM `tabCash Drop` WHERE operator = %s",
			(user,),
		)
		frappe.db.sql(
			"DELETE FROM `tabShift Record` WHERE operator = %s",
			(user,),
		)
		frappe.db.commit()

	def tearDown(self):
		user = frappe.session.user
		frappe.db.sql(
			"DELETE FROM `tabCash Drop` WHERE operator = %s",
			(user,),
		)
		frappe.db.sql(
			"DELETE FROM `tabShift Record` WHERE operator = %s",
			(user,),
		)
		frappe.db.commit()

	def test_get_current_shift_returns_none_when_no_open(self):
		"""No Open Shift Record → get_current_shift returns {"shift": None}."""
		result = api.get_current_shift()
		self.assertIsNone(result.get("shift"))

	def test_start_shift_inserts_open_record(self):
		result = api.start_shift(float_expected=200)
		self.assertIn("shift", result)
		self.assertEqual(result["shift"]["float_expected"], 200.0)

		current = api.get_current_shift()
		self.assertIsNotNone(current["shift"])
		self.assertEqual(current["shift"]["name"], result["shift"]["name"])

		doc = frappe.get_doc("Shift Record", result["shift"]["name"])
		self.assertEqual(doc.status, "Open")
		self.assertEqual(doc.operator, frappe.session.user)
		self.assertIsNotNone(doc.shift_start)

	def test_start_shift_refuses_double_open(self):
		"""Second start_shift call must throw — DEC-099 silent-double-open trap."""
		api.start_shift(float_expected=200)
		with self.assertRaises(frappe.ValidationError):
			api.start_shift(float_expected=300)

	def test_start_shift_requires_float_expected(self):
		with self.assertRaises(frappe.ValidationError):
			api.start_shift(float_expected=None)
		with self.assertRaises(frappe.ValidationError):
			api.start_shift(float_expected="")

	def test_start_shift_rejects_negative_float(self):
		with self.assertRaises(frappe.ValidationError):
			api.start_shift(float_expected=-1)

	def test_end_shift_closes_open_record(self):
		started = api.start_shift(float_expected=200)
		shift_name = started["shift"]["name"]

		result = api.end_shift(shift_name=shift_name)
		self.assertEqual(result["status"], "Closed")

		doc = frappe.get_doc("Shift Record", shift_name)
		self.assertEqual(doc.status, "Closed")
		self.assertIsNotNone(doc.shift_end)

	def test_end_shift_throws_when_no_open(self):
		with self.assertRaises(frappe.ValidationError):
			api.end_shift()

	def test_get_shift_summary_returns_expected_shape(self):
		"""Smoke test the shape — values can be zero on an empty test DB."""
		api.start_shift(float_expected=200)
		summary = api.get_shift_summary()
		for key in (
			"sessions_started_today",
			"sessions_open_now",
			"open_sessions",
			"cash_sales_total",
			"cash_drops_count",
			"cash_drops_total",
		):
			self.assertIn(key, summary, f"Missing summary key: {key}")
		self.assertIsInstance(summary["open_sessions"], list)

	def test_get_hamilton_settings_includes_float_amount(self):
		"""DEC-099 — Asset Board Start Shift modal pulls float_amount default."""
		settings = api._get_hamilton_settings()
		self.assertIn("float_amount", settings)
		self.assertIsInstance(settings["float_amount"], float)


def tearDownModule():
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
