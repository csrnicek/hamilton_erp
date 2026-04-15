import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ShiftRecord(Document):
	def validate(self):
		self._calculate_float_variance()
		self._validate_shift_end()

	def _calculate_float_variance(self):
		"""float_variance = float_actual − float_expected."""
		if self.float_actual is not None and self.float_expected is not None:
			self.float_variance = flt(self.float_actual) - flt(self.float_expected)

	def _validate_shift_end(self):
		if self.shift_end and self.shift_start and self.shift_end < self.shift_start:
			frappe.throw(_("Shift end time cannot be before shift start time."))
