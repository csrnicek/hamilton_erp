import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# Threshold below which a variance is treated as rounding noise, not a flag.
_VARIANCE_TOLERANCE = 0.05


class CashReconciliation(Document):
	def validate(self):
		self._set_timestamp()

	def before_submit(self):
		"""Populate revealed fields and calculate variance flag on submission.

		The three-way comparison is only revealed after the manager submits
		their blind count — never before.  See build spec §7.7 and
		coding_standards.md §8.3.
		"""
		self._populate_operator_declared()
		self._calculate_system_expected()
		self._set_variance_flag()
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
		"""Apply the three-way variance rule per build spec §7.7."""
		operator = flt(self.operator_declared)
		manager = flt(self.actual_count)
		system = flt(self.system_expected)

		manager_matches_operator = abs(manager - operator) <= _VARIANCE_TOLERANCE
		system_matches_operator = abs(system - operator) <= _VARIANCE_TOLERANCE

		if manager_matches_operator and system_matches_operator:
			self.variance_flag = "Clean"
		elif manager_matches_operator and not system_matches_operator:
			# Operator and manager agree but system expected differs →
			# possible theft or unrecorded transaction.
			self.variance_flag = "Possible Theft or Error"
		else:
			# Manager count differs from operator declaration →
			# operator mis-declared or miscounted.
			self.variance_flag = "Operator Mis-declared"

	def _mark_drop_reconciled(self):
		"""Update the linked Cash Drop as reconciled."""
		frappe.db.set_value(
			"Cash Drop",
			self.cash_drop,
			{"reconciled": 1, "reconciliation": self.name},
		)
