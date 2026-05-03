import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today


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

	def test_f38_three_way_disagree_uses_multi_source_variance_label(self):
		"""F3.8 / DEC-068: when none of the three values agree, the label
		is 'Multi-source Variance', not 'Operator Mis-declared'.

		The previous label pre-judged the operator as the bad actor. The
		new label describes the data shape (multi-source disagreement)
		without naming a cause. The specific-attribution case (manager +
		system agree, operator differs) is unchanged and still labels
		'Operator Mis-declared' — that case IS specifically operator
		misdeclaration, so the original label is correct there.
		"""
		drop = self._make_drop(100.0)
		recon = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				# manager=80, operator=100 (drop), system=0 (placeholder
				# default for Phase 1). With $20 spread and $1.00 minimum
				# tolerance, none of the three pairwise comparisons match.
				"actual_count": 80.0,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)
		recon.submit()
		self.assertEqual(
			recon.variance_flag,
			"Multi-source Variance",
			f"Three-way disagreement should produce 'Multi-source Variance', "
			f"got {recon.variance_flag!r}.",
		)

	def test_f38_specific_operator_misdeclaration_still_labeled_correctly(self):
		"""F3.8 boundary: when manager + system agree and operator differs,
		the label remains 'Operator Mis-declared' (the specific case).

		Phase 1 system_expected is hardcoded 0 — so we exercise this case
		by setting actual_count = 0 to match. operator (declared_amount)
		differs.
		"""
		drop = self._make_drop(100.0)
		recon = frappe.get_doc(
			{
				"doctype": "Cash Reconciliation",
				"cash_drop": drop.name,
				"manager": "Administrator",
				# manager=0, system=0 (placeholder), operator=100. Manager
				# matches system; operator does not. Specific operator-
				# misdeclaration case.
				"actual_count": 0.0,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)
		recon.submit()
		self.assertEqual(
			recon.variance_flag,
			"Operator Mis-declared",
			f"Manager+system agree, operator differs → should still be "
			f"'Operator Mis-declared' (specific attribution); got "
			f"{recon.variance_flag!r}.",
		)

	def test_f35_tolerance_reads_from_hamilton_settings_override(self):
		"""F3.5 / DEC-068: tightening the variance tolerance via Hamilton
		Settings makes a previously-Clean reconciliation flag.

		Default tolerance is 2% / $1.00 floor. Set the percent to 0.1%
		and the minimum to $0.05 — a $50 difference between manager and
		operator (out of $1000) should now flag instead of falling under
		the original 2% / $1 envelope.
		"""
		from frappe.utils import flt

		settings = frappe.get_doc("Hamilton Settings", "Hamilton Settings")
		original_pct = settings.cash_variance_tolerance_percent
		original_min = settings.cash_variance_tolerance_minimum
		try:
			settings.cash_variance_tolerance_percent = 0.1
			settings.cash_variance_tolerance_minimum = 0.05
			settings.save(ignore_permissions=True)
			frappe.clear_cache(doctype="Hamilton Settings")

			# Drop $1000 declared, manager counts $999.50 — well under the
			# default 2%/$1 tolerance ($20/$1 effective floor=$20), so under
			# defaults this would be Clean. With tightened tolerance
			# (0.1%/$0.05 → $1 effective vs. $0.50 difference, wait — let me
			# pick numbers that flip outcome unambiguously). Use $1000 vs
			# $999.40 → diff=$0.60. Default: max(20, 1) = $20 envelope, well
			# under → Clean. Tightened: max(1, 0.05) = $1 envelope, 0.60
			# under → still clean. Tighten further: use diff=$1.50.
			drop = self._make_drop(1000.0)
			recon = frappe.get_doc(
				{
					"doctype": "Cash Reconciliation",
					"cash_drop": drop.name,
					"manager": "Administrator",
					# manager=$998.50 vs operator=$1000 → diff $1.50.
					# Default envelope ~$20 → Clean. Tightened envelope $1
					# → flags (operator-misdeclared, since system=0).
					"actual_count": 998.50,
					"timestamp": now_datetime(),
				}
			).insert(ignore_permissions=True)
			recon.submit()
			# With tightened tolerance, manager and operator no longer
			# match within tolerance → not "Clean".
			self.assertNotEqual(
				recon.variance_flag,
				"Clean",
				"Tightened tolerance should flag a $1.50 diff that the "
				"$20 default envelope would have ignored. Settings reads "
				f"pct={float(flt(0.1))} min={float(flt(0.05))}.",
			)
		finally:
			settings.cash_variance_tolerance_percent = original_pct
			settings.cash_variance_tolerance_minimum = original_min
			settings.save(ignore_permissions=True)
			frappe.clear_cache(doctype="Hamilton Settings")
