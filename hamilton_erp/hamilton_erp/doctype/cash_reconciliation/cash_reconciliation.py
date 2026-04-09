import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# Variance tolerance: 2% of the larger amount, with a $1.00 minimum floor.
# A flat $0.05 tolerance is too strict for real cash handling — a single
# mis-counted bill would flag a $500 drop as non-Clean.
_VARIANCE_TOLERANCE_PCT = 0.02
_VARIANCE_TOLERANCE_MIN = 1.00


def _within_tolerance(a: float, b: float) -> bool:
	"""Return True if |a - b| is within the configured percentage tolerance."""
	diff = abs(a - b)
	threshold = max(abs(a), abs(b)) * _VARIANCE_TOLERANCE_PCT
	return diff <= max(threshold, _VARIANCE_TOLERANCE_MIN)


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
		self._populate_operator_declared()
		self._calculate_system_expected()
		self._set_variance_flag()

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
			# None agree — operator declared wrong amount and cash is missing
			self.variance_flag = "Operator Mis-declared"

	def _mark_drop_reconciled(self):
		"""Update the linked Cash Drop as reconciled."""
		frappe.db.set_value(
			"Cash Drop",
			self.cash_drop,
			{"reconciled": 1, "reconciliation": self.name},
		)
