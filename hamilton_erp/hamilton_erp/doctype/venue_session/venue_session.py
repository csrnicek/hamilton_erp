import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class VenueSession(Document):
	def validate(self):
		self._set_defaults()
		self._validate_session_end()

	def before_insert(self):
		"""Auto-populate session_number via the Redis INCR generator.

		Callers (e.g. lifecycle._create_session) pass everything EXCEPT
		session_number; this hook fills it in from hamilton_erp.lifecycle._next_session_number().
		If a caller explicitly sets session_number (e.g. TestSessionNumberGenerator's
		cold-fallback test that seeds a historic row directly), we leave it alone.

		API abuse footgun: session_number is read_only on the form, but a caller
		using insert(ignore_permissions=True) — or a future @frappe.whitelist
		endpoint that accepts a raw dict — could set an arbitrary session_number
		and bypass the generator. This is accepted as a known limit because
		Task 11 adds a DB uniqueness constraint on session_number, so any
		collision with a generator-produced value surfaces as DuplicateEntryError
		on insert (which _create_session's retry loop will catch per Task 11(c)).
		"""
		if not self.session_number:
			# Local import is defensive: lifecycle.py is currently import-safe
			# from this module (it only imports frappe, frappe._, typing at
			# module top), but keeping the import local guards against future
			# lifecycle.py growth that might introduce a top-level doctype
			# import and close a circular path. Cheap to keep, expensive to
			# debug if it's removed and the hazard ever materializes.
			from hamilton_erp.lifecycle import _next_session_number
			self.session_number = _next_session_number()

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
			frappe.throw(_("Check-out time cannot be before check-in time."))
