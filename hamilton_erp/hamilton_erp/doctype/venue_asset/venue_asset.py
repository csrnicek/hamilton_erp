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
		room_tiers = {"Single Standard", "Deluxe Single", "GH Room", "Double Deluxe"}
		if self.asset_category == "Locker" and self.asset_tier != "Locker":
			frappe.throw(_("Lockers must have tier 'Locker'."))
		if self.asset_category == "Room" and self.asset_tier not in room_tiers:
			frappe.throw(
				_("Rooms must have a room tier: Single Standard, Deluxe Single, "
				  "GH Room, or Double Deluxe.")
			)

	def _validate_reason_for_oos(self):
		"""Out of Service requires a non-whitespace reason."""
		# ChatGPT review 2026-04-10: strip() so " " / "\t" / "\n" don't pass as a reason.
		if self.status == "Out of Service" and not (self.reason or "").strip():
			frappe.throw(_("Please provide a reason for marking this asset Out of Service."))

	# Whitelisted DocType methods removed 2026-04-29 (cleanup PR following
	# AI bloat audit on PR #34). They were 1-line delegators to lifecycle.*
	# never called from the JS (asset_board.js calls top-level
	# `hamilton_erp.api.*` whitelisted methods directly). The two tests
	# that exercised them were also removed in the same PR. If a future
	# integration ever wants `frappe.client.run_doc_method`-style access,
	# add it back as a thin wrapper alongside its caller, not here
	# pre-emptively.
