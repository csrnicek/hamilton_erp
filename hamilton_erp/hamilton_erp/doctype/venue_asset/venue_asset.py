"""Venue Asset controller — schema validation and whitelisted method stubs for Phase 0."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


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
			return  # New record — any initial status is valid

		old_status = old_doc.status
		valid = self._valid_transitions()
		if self.status not in valid.get(old_status, []):
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
		"""Out of Service requires a reason."""
		if self.status == "Out of Service" and not self.reason:
			frappe.throw(_("Please provide a reason for marking this asset Out of Service."))

	@staticmethod
	def _valid_transitions() -> dict:
		return {
			"Available": ["Occupied", "Out of Service"],
			"Occupied": ["Dirty", "Out of Service"],
			"Dirty": ["Available", "Out of Service"],
			"Out of Service": ["Available"],
		}

	# ------------------------------------------------------------------
	# Whitelisted methods — stubs for Phase 0, implemented in Phase 1
	# ------------------------------------------------------------------

	@frappe.whitelist(methods=["POST"])
	def assign_to_session(self, session_name: str):
		"""Assign this asset to a Venue Session. Full locking logic in Phase 1."""
		frappe.throw(_("assign_to_session is not yet implemented (Phase 1)."))

	@frappe.whitelist(methods=["POST"])
	def mark_vacant(self):
		"""Transition Occupied → Dirty when guest vacates. Full logic in Phase 1."""
		frappe.throw(_("mark_vacant is not yet implemented (Phase 1)."))

	@frappe.whitelist(methods=["POST"])
	def mark_clean(self):
		"""Transition Dirty → Available after cleaning. Full logic in Phase 1."""
		frappe.throw(_("mark_clean is not yet implemented (Phase 1)."))

	@frappe.whitelist(methods=["POST"])
	def set_out_of_service(self, reason: str):
		"""Transition any state → Out of Service. Full logic in Phase 1."""
		frappe.throw(_("set_out_of_service is not yet implemented (Phase 1)."))

	@frappe.whitelist(methods=["POST"])
	def return_to_service(self, reason: str):
		"""Transition Out of Service → Available. Full logic in Phase 1."""
		frappe.throw(_("return_to_service is not yet implemented (Phase 1)."))
