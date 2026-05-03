import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# Variance tolerance defaults: 2% of the larger amount, with a $1.00 minimum
# floor. A flat $0.05 tolerance is too strict for real cash handling — a
# single mis-counted bill would flag a $500 drop as non-Clean. Both values
# are now configurable per venue via Hamilton Settings (F3.5 / DEC-068);
# the constants below are used only as fallbacks when Settings is missing
# or when either field is blank.
_VARIANCE_TOLERANCE_PCT_DEFAULT = 0.02
_VARIANCE_TOLERANCE_MIN_DEFAULT = 1.00


def _get_variance_tolerance() -> tuple[float, float]:
	"""Read the variance tolerance from Hamilton Settings.

	Returns (percent_as_fraction, minimum_dollars). The percent stored in
	Settings is a Percent field (e.g. 2.0 means 2%); we convert to a
	fraction (0.02) so callers don't need to know the storage shape.

	Falls back to the module-level defaults when Settings is missing or
	either field is blank — keeps the fresh-install / migrate-pending path
	working, and stays robust to operator-cleared values.
	"""
	try:
		settings = frappe.get_cached_doc("Hamilton Settings", "Hamilton Settings")
	except frappe.DoesNotExistError:
		return _VARIANCE_TOLERANCE_PCT_DEFAULT, _VARIANCE_TOLERANCE_MIN_DEFAULT
	pct_raw = settings.get("cash_variance_tolerance_percent")
	min_raw = settings.get("cash_variance_tolerance_minimum")
	pct = (flt(pct_raw) / 100.0) if pct_raw else _VARIANCE_TOLERANCE_PCT_DEFAULT
	minimum = flt(min_raw) if min_raw else _VARIANCE_TOLERANCE_MIN_DEFAULT
	return pct, minimum


def _within_tolerance(a: float, b: float) -> bool:
	"""Return True if |a - b| is within the configured percentage tolerance."""
	pct, minimum = _get_variance_tolerance()
	diff = abs(a - b)
	threshold = max(abs(a), abs(b)) * pct
	return diff <= max(threshold, minimum)


class CashReconciliation(Document):
	def validate(self):
		self._set_timestamp()

	def before_submit(self):
		"""Populate revealed fields and calculate variance flag on submission.

		The three-way comparison is only revealed after the manager submits
		their blind count — never before.  See build spec §7.7 and
		coding_standards.md §8.3.
		"""
		if self.actual_count is None:
			frappe.throw(_("Please enter the cash count before submitting."))
		self._validate_no_duplicate_reconciliation()
		self._populate_operator_declared()
		self._calculate_system_expected()
		self._set_variance_flag()

	def _validate_no_duplicate_reconciliation(self):
		"""T1-5 per docs/inbox/2026-05-04_audit_synthesis_decisions.md:
		every Cash Drop reconciles AT MOST once.

		Two managers opening the same Cash Drop and racing to submit
		reconciliations would otherwise both succeed (no DB constraint,
		no app-level guard) — and ``_mark_drop_reconciled`` would
		overwrite the Cash Drop's ``reconciliation`` link to whichever
		submitted second. Manager A's reconciliation row would orphan;
		auditors querying "show me the reconciliation for DROP-X" would
		see only Manager B's. The audit trail loses a record.

		This guard rejects the second submission with a clear error
		pointing at the existing reconciliation. Same-row resubmission
		(e.g. an amend flow) is allowed via the ``name != self.name``
		filter.
		"""
		if not self.cash_drop:
			return
		existing = frappe.db.exists(
			"Cash Reconciliation",
			{
				"cash_drop": self.cash_drop,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(_(
				"This Cash Drop has already been reconciled by "
				"{0}. A drop reconciles at most once."
			).format(existing))

	def on_submit(self):
		"""Mark the linked Cash Drop as reconciled after successful submission.

		Runs after docstatus = 1 is committed, so the reconciliation link
		is only written when the Cash Reconciliation is fully submitted.
		Previously this was in before_submit, which risked marking the drop
		reconciled even if submission failed and rolled back.
		"""
		self._mark_drop_reconciled()

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _set_timestamp(self):
		if not self.timestamp:
			self.timestamp = now_datetime()

	def _populate_operator_declared(self):
		"""Copy the declared amount from the linked Cash Drop."""
		declared = frappe.db.get_value("Cash Drop", self.cash_drop, "declared_amount")
		self.operator_declared = flt(declared)

	def _calculate_system_expected(self):
		"""Calculate system_expected from POS transactions.

		Phase 3 implementation.  The system expected total is the sum of
		all cash payment entries against Sales Invoices submitted during the
		shift period covered by this cash drop.
		"""
		# Placeholder — Phase 3 wires up the real calculation.
		# The field is set to 0 here so the schema is valid, not left null.
		self.system_expected = flt(0)

	def _set_variance_flag(self):
		"""Apply the three-way variance rule per build spec §7.7.

		Three-way comparison:
		  manager = what the manager physically counted (ground truth)
		  operator = what the operator declared when dropping the envelope
		  system = what the POS recorded as cash transactions

		  Clean:                  all three agree within tolerance
		  Possible Theft/Error:   manager ≈ operator but system differs
		                          (cash matches declaration but POS expected different)
		  Also Possible T/E:      system ≈ operator but manager found less
		                          (POS and operator agree, but cash is physically missing)
		  Operator Mis-declared:  manager ≈ system but operator declared wrong amount
		                          (physical count matches POS, operator was inaccurate)
		"""
		operator = flt(self.operator_declared)
		manager = flt(self.actual_count)
		system = flt(self.system_expected)

		manager_matches_operator = _within_tolerance(manager, operator)
		manager_matches_system = _within_tolerance(manager, system)
		system_matches_operator = _within_tolerance(system, operator)

		if manager_matches_operator and manager_matches_system:
			# All three agree — normal outcome
			self.variance_flag = "Clean"
		elif manager_matches_operator and not manager_matches_system:
			# Manager and operator agree what was in the envelope, but POS
			# expected a different amount — unrecorded transaction or theft
			self.variance_flag = "Possible Theft or Error"
		elif not manager_matches_operator and manager_matches_system:
			# Manager count matches POS expectation, but operator declared
			# a different amount — operator mis-declared
			self.variance_flag = "Operator Mis-declared"
		elif system_matches_operator:
			# POS and operator agree, but manager physically found less cash —
			# money is missing from the envelope after it was dropped
			self.variance_flag = "Possible Theft or Error"
		else:
			# F3.8 / DEC-068: when none of the three values agree, the
			# fault is genuinely ambiguous — could be operator misdeclaration,
			# theft, POS error, or any combination. The previous label
			# "Operator Mis-declared" pre-judged the operator as the bad
			# actor; "Multi-source Variance" describes the data shape
			# (multiple sources disagree) without naming a cause. The
			# specific-attribution case (manager+system agree, operator
			# differs) is unchanged above and still labels "Operator
			# Mis-declared" because that case IS specifically operator
			# misdeclaration.
			self.variance_flag = "Multi-source Variance"

	def _mark_drop_reconciled(self):
		"""Update the linked Cash Drop as reconciled.

		T3-1: use the Document API instead of frappe.db.set_value. The
		bypass-the-controller pattern was acceptable when CashDrop had
		no validate body that needed to fire post-reconciliation, but
		track_changes is enabled on Cash Drop and a direct DB write
		skips the audit-trail capture. Going through .save() restores
		the audit trail, fires any future doc_events, and re-runs
		validate (currently a no-op for the reconciled / reconciliation
		fields, but cheap insurance against a future controller change
		that adds a guard the direct write would silently bypass).
		"""
		drop = frappe.get_doc("Cash Drop", self.cash_drop)
		drop.reconciled = 1
		drop.reconciliation = self.name
		drop.save(ignore_permissions=True)
