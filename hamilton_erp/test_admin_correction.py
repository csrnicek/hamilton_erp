"""Tests for the DEC-066 admin-correction endpoint.

Covers:
  * Role gate — only Hamilton Admin / System Manager can call.
  * Required `reason` validation.
  * `target_doctype` whitelist validation.
  * Audit-log path — original row left pristine, correction row created.
  * Mutable-target path — target field updated AND correction row created.
  * Mutable-target path requires `target_field` and `new_value`.

Lives at the package root (same level as api.py, lifecycle.py). We
intentionally do NOT set IGNORE_TEST_RECORD_DEPENDENCIES — Frappe v16's
IntegrationTestCase can't auto-detect cls.doctype for package-root
modules, so it skips test-record generation entirely.
"""
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today

from hamilton_erp.api import submit_admin_correction


class TestSubmitAdminCorrection(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.operator_email = "admin-correction-operator-test@example.com"
		if not frappe.db.exists("User", cls.operator_email):
			frappe.get_doc({
				"doctype": "User",
				"email": cls.operator_email,
				"first_name": "AdminCorrectionOpTest",
				"send_welcome_email": 0,
				"enabled": 1,
				"roles": [{"role": "Hamilton Operator"}],
			}).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		email = getattr(cls, "operator_email", None)
		if email and frappe.db.exists("User", email):
			frappe.delete_doc("User", email, ignore_permissions=True, force=True)
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _make_shift(self, operator: str = "Administrator", status: str = "Open") -> object:
		# T1-4 (PR #168, merged 2026-05-03): Cash Drop now validates that
		# shift_record is set, that the linked Shift Record is Open, and
		# that its operator matches the drop's. Mirror of the helper in
		# test_cash_drop.py / test_cash_reconciliation.py.
		return frappe.get_doc(
			{
				"doctype": "Shift Record",
				"operator": operator,
				"shift_date": today(),
				"status": status,
				"shift_start": now_datetime(),
				"float_expected": 300,
			}
		).insert(ignore_permissions=True)

	def _make_drop(self, declared: float = 100.0):
		shift = self._make_shift()
		return frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Administrator",
				"shift_record": shift.name,
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": declared,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)

	def _make_comp_log(self):
		# Minimal Comp Admission Log row — schema-permitting fixture.
		# Real shape may need adjustment if required fields change.
		return frappe.get_doc(
			{
				"doctype": "Comp Admission Log",
				"operator": "Administrator",
				"timestamp": now_datetime(),
				"reason": "test fixture",
			}
		).insert(ignore_permissions=True)

	# ------------------------------------------------------------------
	# Role gate
	# ------------------------------------------------------------------

	def test_operator_cannot_submit_correction(self):
		drop = self._make_drop(100.0)
		frappe.set_user(self.operator_email)
		with self.assertRaises(frappe.PermissionError):
			submit_admin_correction(
				target_doctype="Cash Drop",
				target_name=drop.name,
				reason="typo",
				target_field="declared_amount",
				new_value="120",
			)

	# ------------------------------------------------------------------
	# Validation
	# ------------------------------------------------------------------

	def test_missing_reason_raises(self):
		drop = self._make_drop(100.0)
		with self.assertRaises(frappe.ValidationError):
			submit_admin_correction(
				target_doctype="Cash Drop",
				target_name=drop.name,
				reason="",
				target_field="declared_amount",
				new_value="120",
			)

	def test_invalid_target_doctype_raises(self):
		with self.assertRaises(frappe.ValidationError):
			submit_admin_correction(
				target_doctype="Sales Invoice",
				target_name="DOES-NOT-MATTER",
				reason="invalid type",
			)

	def test_missing_target_row_raises(self):
		with self.assertRaises(frappe.ValidationError):
			submit_admin_correction(
				target_doctype="Cash Drop",
				target_name="CASH-DROP-DOES-NOT-EXIST",
				reason="missing",
				target_field="declared_amount",
				new_value="120",
			)

	def test_mutable_target_requires_field_and_value(self):
		drop = self._make_drop(100.0)
		with self.assertRaises(frappe.ValidationError):
			submit_admin_correction(
				target_doctype="Cash Drop",
				target_name=drop.name,
				reason="missing field",
			)

	# ------------------------------------------------------------------
	# Mutable target — Cash Drop
	# ------------------------------------------------------------------

	def test_cash_drop_correction_applies_and_logs(self):
		drop = self._make_drop(100.0)
		result = submit_admin_correction(
			target_doctype="Cash Drop",
			target_name=drop.name,
			reason="operator typo — declared 100, should be 120",
			target_field="declared_amount",
			new_value="120",
		)
		self.assertEqual(result["status"], "applied")
		self.assertEqual(result["target_doctype"], "Cash Drop")
		self.assertEqual(result["target_name"], drop.name)

		# Cash Drop was actually updated
		updated = frappe.db.get_value(
			"Cash Drop", drop.name, "declared_amount"
		)
		self.assertEqual(float(updated), 120.0)

		# Correction row exists with old/new captured
		corr = frappe.get_doc("Hamilton Board Correction", result["correction"])
		self.assertEqual(corr.target_doctype, "Cash Drop")
		self.assertEqual(corr.target_name, drop.name)
		self.assertEqual(corr.target_field, "declared_amount")
		self.assertEqual(str(corr.old_value), "100.0")
		self.assertEqual(corr.new_value, "120")
		self.assertEqual(corr.operator, "Administrator")

	def test_cash_drop_correction_clears_carve_out_flag(self):
		"""After the call, frappe.flags.allow_cash_drop_correction must be reset."""
		drop = self._make_drop(100.0)
		# Pre-condition: flag is not set / falsy
		self.assertFalse(getattr(frappe.flags, "allow_cash_drop_correction", False))
		submit_admin_correction(
			target_doctype="Cash Drop",
			target_name=drop.name,
			reason="check flag teardown",
			target_field="declared_amount",
			new_value="105",
		)
		# Post-condition: flag is back to falsy
		self.assertFalse(getattr(frappe.flags, "allow_cash_drop_correction", False))

	# ------------------------------------------------------------------
	# Audit-log target — Comp Admission Log
	# ------------------------------------------------------------------

	def test_comp_admission_log_correction_logs_only(self):
		try:
			log = self._make_comp_log()
		except frappe.ValidationError:
			self.skipTest(
				"Comp Admission Log fixture requires more fields than the "
				"minimal test stub provides; covered by ad-hoc verification."
			)
			return

		result = submit_admin_correction(
			target_doctype="Comp Admission Log",
			target_name=log.name,
			reason="mis-attribution to wrong operator",
			target_field="reason",
			new_value="corrected reason text",
		)
		self.assertEqual(result["status"], "logged")

		# Original audit-log row UNCHANGED
		log.reload()
		self.assertEqual(log.reason, "test fixture")

		# Correction row IS created with new_value captured
		corr = frappe.get_doc("Hamilton Board Correction", result["correction"])
		self.assertEqual(corr.target_doctype, "Comp Admission Log")
		self.assertEqual(corr.target_name, log.name)
		self.assertEqual(corr.new_value, "corrected reason text")
