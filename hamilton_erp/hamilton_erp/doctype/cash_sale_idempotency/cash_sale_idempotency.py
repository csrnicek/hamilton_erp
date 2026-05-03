import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CashSaleIdempotency(Document):
	def before_insert(self):
		if not self.created_at:
			self.created_at = now_datetime()
