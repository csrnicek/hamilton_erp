import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# Transitions involving Out of Service (to or from) require a mandatory reason.
_OOS_STATE = "Out of Service"


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
			self.new_status == _OOS_STATE
			or self.previous_status == _OOS_STATE
		)
		if involves_oos and not self.reason:
			frappe.throw(
				_("Please enter a reason. A reason is required for all Out of Service changes.")
			)
