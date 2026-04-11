"""Venue Asset controller — schema validation and whitelisted method stubs for Phase 0."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from hamilton_erp.lifecycle import VALID_TRANSITIONS


class VenueAsset(Document):

	def validate(self):
		self._validate_status_transition()
		self._validate_tier_matches_category()
		self._validate_reason_for_oos()

	def before_save(self):
		if self.has_value_changed("status"):
			self.hamilton_last_status_change = now_datetime()

	# ------------------------------------------------------------------
	# Validation helpers
	# ------------------------------------------------------------------

	def _validate_status_transition(self):
		"""Enforce valid state transitions per build spec §5.1.

		Valid transitions:
		  Available      → Occupied, Out of Service
		  Occupied       → Dirty, Out of Service
		  Dirty          → Available, Out of Service
		  Out of Service → Available
		"""
		if not self.has_value_changed("status"):
			return
		old_doc = self.get_doc_before_save()
		if not old_doc:
			# New record — must start as Available (ChatGPT review 2026-04-10).
			# Without this guard an operator could insert a row directly as
			# "Occupied" or "Dirty", bypassing the lifecycle state machine.
			if self.status != "Available":
				frappe.throw(_("New assets must start as Available."))
			return

		old_status = old_doc.status
		if self.status not in VALID_TRANSITIONS.get(old_status, ()):
			frappe.throw(
				_("Cannot transition {0} from {1} to {2}.").format(
					self.asset_name, old_status, self.status
				)
			)

	def _validate_tier_matches_category(self):
		"""Lockers must have tier Locker. Rooms must have a room tier."""
		room_tiers = {"Single Standard", "Deluxe Single", "Glory Hole", "Double Deluxe"}
		if self.asset_category == "Locker" and self.asset_tier != "Locker":
			frappe.throw(_("Lockers must have tier 'Locker'."))
		if self.asset_category == "Room" and self.asset_tier not in room_tiers:
			frappe.throw(
				_("Rooms must have a room tier: Single Standard, Deluxe Single, "
				  "Glory Hole, or Double Deluxe.")
			)

	def _validate_reason_for_oos(self):
		"""Out of Service requires a non-whitespace reason."""
		# ChatGPT review 2026-04-10: strip() so " " / "\t" / "\n" don't pass as a reason.
		if self.status == "Out of Service" and not (self.reason or "").strip():
			frappe.throw(_("Please provide a reason for marking this asset Out of Service."))

	# ------------------------------------------------------------------
	# Whitelisted methods — Phase 1 real bodies (delegate to lifecycle.py)
	# ------------------------------------------------------------------

	@frappe.whitelist(methods=["POST"])
	def assign_to_session(self):
		"""Assign a walk-in session to this asset. Available → Occupied."""
		frappe.has_permission("Venue Asset", "write", throw=True)
		from hamilton_erp.lifecycle import start_session_for_asset
		return {"session": start_session_for_asset(self.name, operator=frappe.session.user)}

	@frappe.whitelist(methods=["POST"])
	def mark_vacant(self, vacate_method: str):
		"""Close the current session and move to Dirty."""
		frappe.has_permission("Venue Asset", "write", throw=True)
		from hamilton_erp.lifecycle import vacate_session
		vacate_session(self.name, operator=frappe.session.user,
		               vacate_method=vacate_method)

	@frappe.whitelist(methods=["POST"])
	def mark_clean(self):
		"""Dirty → Available."""
		frappe.has_permission("Venue Asset", "write", throw=True)
		from hamilton_erp.lifecycle import mark_asset_clean
		mark_asset_clean(self.name, operator=frappe.session.user)

	@frappe.whitelist(methods=["POST"])
	def set_out_of_service(self, reason: str):
		"""Any state (except OOS) → Out of Service."""
		frappe.has_permission("Venue Asset", "write", throw=True)
		from hamilton_erp.lifecycle import set_asset_out_of_service
		set_asset_out_of_service(self.name, operator=frappe.session.user, reason=reason)

	@frappe.whitelist(methods=["POST"])
	def return_to_service(self, reason: str):
		"""Out of Service → Available."""
		frappe.has_permission("Venue Asset", "write", throw=True)
		from hamilton_erp.lifecycle import return_asset_to_service
		return_asset_to_service(self.name, operator=frappe.session.user, reason=reason)
