from frappe.model.document import Document
from frappe.utils import now_datetime


class CompAdmissionLog(Document):
	def validate(self):
		self._set_timestamp()

	def _set_timestamp(self):
		if not self.timestamp:
			self.timestamp = now_datetime()
