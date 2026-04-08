import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class VenueSession(Document):
	def validate(self):
		self._set_defaults()
		self._validate_session_end()

	def on_submit(self):
		pass  # Phase 2: finalize session, move asset to Dirty

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _set_defaults(self):
		"""Ensure forward-compat fields have correct defaults at Hamilton."""
		if not self.identity_method:
			self.identity_method = "not_applicable"
		if not self.session_start:
			self.session_start = now_datetime()

	def _validate_session_end(self):
		"""Session end must be after session start."""
		if self.session_end and self.session_start and self.session_end < self.session_start:
			frappe.throw(_("Session End cannot be earlier than Session Start."))
