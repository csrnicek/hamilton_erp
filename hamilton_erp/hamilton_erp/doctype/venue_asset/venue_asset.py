import frappe
from frappe import _
from frappe.model.document import Document


class VenueAsset(Document):
	# Phase 1 implements the full controller. Phase 0 defines the schema
	# and validation skeleton so the DocType installs and migrates cleanly.

	def validate(self):
		self._validate_status_transition()
		self._validate_tier_for_room()

	def before_save(self):
		pass  # Phase 1: calculate derived fields (e.g., overtime flag)

	def after_insert(self):
		pass  # Phase 1: publish realtime board update

	def on_update(self):
		pass  # Phase 1: publish realtime board update on every save

	# ------------------------------------------------------------------
	# Validation helpers
	# ------------------------------------------------------------------

	def _validate_status_transition(self):
		"""Enforce that only valid state transitions are applied.

		Valid transitions per build spec §5.1:
		  Available  → Occupied, Out of Service
		  Occupied   → Dirty, Out of Service
		  Dirty      → Available, Out of Service
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
				_("'{0}' is currently {1} and cannot be changed to {2} from here. "
				  "Use the asset board to update room and locker status.").format(
					self.asset_name, old_status, self.status
				)
			)

	def _validate_tier_for_room(self):
		"""Rooms must have a tier. Lockers must not — clear any accidentally set value."""
		if self.asset_category == "Room" and not self.asset_tier:
			frappe.throw(_("Please select a Room Tier (Standard or Deluxe) before saving."))
		elif self.asset_category == "Locker" and self.asset_tier:
			# Lockers are single-tier. Silently clear any accidentally set value
			# rather than throwing, as this is a configuration mistake not an
			# operational error.
			self.asset_tier = ""

	@staticmethod
	def _valid_transitions() -> dict:
		return {
			"Available": ["Occupied", "Out of Service"],
			"Occupied": ["Dirty", "Out of Service"],
			"Dirty": ["Available", "Out of Service"],
			"Out of Service": ["Available"],
		}
