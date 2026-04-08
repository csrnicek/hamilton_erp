import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class CashDrop(Document):
	def validate(self):
		self._set_timestamp()
		self._validate_declared_amount()

	def _set_timestamp(self):
		if not self.timestamp:
			self.timestamp = now_datetime()

	def _validate_declared_amount(self):
		if self.declared_amount is not None and self.declared_amount < 0:
			frappe.throw(_("Declared Amount cannot be negative."))
