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
				_("Cannot transition Venue Asset {0} from {1} to {2}.").format(
					self.asset_name, old_status, self.status
				)
			)

	def _validate_tier_for_room(self):
		"""Rooms must have a tier; lockers must not."""
		if self.asset_category == "Room" and not self.asset_tier:
			frappe.throw(_("Asset Tier is required for Room assets."))

	@staticmethod
	def _valid_transitions() -> dict:
		return {
			"Available": ["Occupied", "Out of Service"],
			"Occupied": ["Dirty", "Out of Service"],
			"Dirty": ["Available", "Out of Service"],
			"Out of Service": ["Available"],
		}
