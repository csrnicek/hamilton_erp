import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today


class TestCashReconciliation(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_shift(self, operator: str = "Administrator", status: str = "Open") -> object:
		# T1-4 (this PR): Cash Drop now validates that shift_record is set,
		# that the linked Shift Record is Open, and that its operator
		# matches the drop's. Mirror of the helper in test_cash_drop.py
		# so reconciliation tests can build a valid drop fixture.
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

	def _make_drop(self, declared: float = 100.0) -> object:
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

	def test_t1_5_first_reconciliation_submission_succeeds(self):
		"""T1-5 (per docs/inbox/2026-05-04_audit_synthesis_decisions.md):
		the FIRST submitted reconciliation for a Cash Drop succeeds.

		Sanity case for the duplicate guard — guard must not block
		legitimate first submissions.
		"""
		drop = self._make_drop(200.0)
		recon = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				"actual_count": 200.0,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)
		recon.submit()
		self.assertEqual(recon.docstatus, 1)

	def test_t1_5_second_reconciliation_for_same_drop_is_rejected(self):
		"""T1-5: A second submitted reconciliation pointing at the same
		Cash Drop must be rejected at before_submit.

		Without this guard, two managers race-submitting reconciliations
		for the same drop both succeed and overwrite the Cash Drop's
		``reconciliation`` link to whichever submitted second; the first
		reconciliation row orphans and the audit trail loses a record.
		"""
		drop = self._make_drop(200.0)

		# Manager A submits first — succeeds.
		recon_a = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				"actual_count": 200.0,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)
		recon_a.submit()

		# Manager B inserts a draft for the same drop (insert is allowed —
		# drafts can be created freely; the guard fires at before_submit).
		recon_b = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				"actual_count": 195.0,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)

		# Manager B's submit must fail with the T1-5 guard message.
		with self.assertRaises(frappe.ValidationError) as ctx:
			recon_b.submit()
		# The error message names the existing reconciliation, so the
		# manager has a breadcrumb to investigate.
		self.assertIn(recon_a.name, str(ctx.exception))
		self.assertIn("already been reconciled", str(ctx.exception).lower())
