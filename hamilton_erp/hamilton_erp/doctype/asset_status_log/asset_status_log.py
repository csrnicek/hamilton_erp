import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# States that require a reason for audit completeness.
_REASON_REQUIRED_STATES = {"Out of Service", "Available"}


class AssetStatusLog(Document):
	def validate(self):
		self._set_timestamp()
		self._require_reason_for_oos_transitions()

	def _set_timestamp(self):
		if not self.timestamp:
			self.timestamp = now_datetime()

	def _require_reason_for_oos_transitions(self):
		"""Reason is mandatory when transitioning to or from Out of Service."""
		involves_oos = (
			self.new_status == "Out of Service"
			or self.previous_status == "Out of Service"
		)
		if involves_oos and not self.reason:
			frappe.throw(
				_("A reason is required when marking an asset Out of Service or returning it to service.")
			)
