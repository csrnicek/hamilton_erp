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

	# DEC-069: the three classifier-active tests added in DEC-068
	# (test_f38_three_way_disagree_uses_multi_source_variance_label,
	#  test_f38_specific_operator_misdeclaration_still_labeled_correctly,
	#  test_f35_tolerance_reads_from_hamilton_settings_override) were
	# removed under T0-2 Path B because _set_variance_flag now
	# short-circuits to "Pending Phase 3" regardless of inputs. Those
	# tests assumed the three-way classifier was active and would fail
	# under Path B. They will return when Phase 3 reactivates the
	# classifier with a real system_expected calculation.

	def test_t0_2_path_b_variance_flag_pending_phase_3_for_any_inputs(self):
		"""T0-2 Path B / DEC-069: until Phase 3 ships the real
		system_expected calculator, variance_flag is unconditionally
		'Pending Phase 3' regardless of the three-way input shape.

		Pinning four representative input shapes that previously produced
		each of the four classification outcomes — all must now resolve
		to 'Pending Phase 3' so a future regression that re-enables the
		classifier without also delivering the system_expected calculator
		surfaces immediately.

		variance_amount must still be populated (NEW-1 bundled into Path
		B) — the manager sees a meaningful number, not $0.00.
		"""
		# Phase 1 system_expected is hardcoded 0; the four cases below
		# previously produced (Clean / Possible Theft or Error /
		# Operator Mis-declared / Operator Mis-declared) respectively.
		cases = [
			(0.0, 0.0),     # all-zero: previously "Clean"
			(100.0, 100.0), # manager+operator agree, system=0: previously "Possible Theft or Error"
			(0.0, 100.0),   # manager+system agree (=0), operator differs: previously "Operator Mis-declared"
			(75.0, 100.0),  # all three differ: previously "Operator Mis-declared" (catch-all / Multi-source Variance under DEC-068)
		]
		for actual, declared in cases:
			drop = self._make_drop(declared)
			recon = frappe.get_doc(
				{
					"doctype": "Cash Reconciliation",
					"cash_drop": drop.name,
					"manager": "Administrator",
					"actual_count": actual,
					"timestamp": now_datetime(),
				}
			).insert(ignore_permissions=True)
			recon.submit()
			self.assertEqual(
				recon.variance_flag,
				"Pending Phase 3",
				f"variance_flag must be 'Pending Phase 3' regardless of inputs "
				f"(manager={actual}, operator={declared}, system=0); got "
				f"{recon.variance_flag!r}. T0-2 Path B contract.",
			)
			# variance_amount = actual - system_expected (= actual - 0 in Phase 1)
			self.assertAlmostEqual(
				float(recon.variance_amount),
				actual,
				places=2,
				msg=f"variance_amount must equal actual_count - system_expected "
				f"({actual} - 0 = {actual}); got {recon.variance_amount!r}. "
				f"NEW-1 bundled into T0-2 Path B.",
			)
			# Roll back inside the loop so each case starts fresh
			# without test-pollution between iterations.
			frappe.db.rollback()
	def _submit_recon(self, drop, actual: float = 100.0):
		recon = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				"actual_count": actual,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)
		recon.submit()
		return recon

	def test_on_cancel_resets_drop_reconciled_flag(self):
		"""Cancelling a reconciliation must clear Cash Drop.reconciled."""
		drop = self._make_drop(100.0)
		recon = self._submit_recon(drop, actual=100.0)
		drop.reload()
		self.assertEqual(drop.reconciled, 1)
		self.assertEqual(drop.reconciliation, recon.name)

		recon.cancel()
		drop.reload()
		self.assertEqual(drop.reconciled, 0)
		self.assertFalse(drop.reconciliation)

	def test_on_cancel_no_op_without_cash_drop(self):
		"""on_cancel guards against missing cash_drop link."""
		drop = self._make_drop(100.0)
		recon = self._submit_recon(drop, actual=100.0)
		recon.cash_drop = None
		# Direct field-level reset without re-running validate; the guard
		# is what we are testing — no exception should fire.
		recon.on_cancel()
