import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, time_diff_in_seconds

# Transitions involving Out of Service (to or from) require a mandatory reason.
_OOS_STATE = "Out of Service"


class AssetStatusLog(Document):
	def validate(self):
		self._set_timestamp()
		self._require_reason_for_oos_transitions()
		self._track_oos_duration()

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

	def _track_oos_duration(self):
		"""Track OOS duration for maintenance reporting (Task 25 item 24).

		When asset enters OOS: set oos_start_time
		When asset leaves OOS: set oos_end_time and calculate oos_duration_minutes

		Duration calculation requires finding the most recent "entered OOS" log entry
		for this asset to get the start time.
		"""
		# Entering OOS: record start time
		if self.new_status == _OOS_STATE:
			self.oos_start_time = self.timestamp or now_datetime()

		# Leaving OOS: record end time and calculate duration
		if self.previous_status == _OOS_STATE and self.new_status != _OOS_STATE:
			self.oos_end_time = self.timestamp or now_datetime()

			# Find the most recent OOS entry for this asset
			if self.venue_asset:
				last_oos_entry = frappe.db.get_value(
					"Asset Status Log",
					filters={
						"venue_asset": self.venue_asset,
						"new_status": _OOS_STATE,
						"oos_start_time": ["is", "set"]
					},
					fieldname=["name", "oos_start_time"],
					order_by="timestamp desc",
					as_dict=True
				)

				if last_oos_entry and isinstance(last_oos_entry, dict):
					oos_start = last_oos_entry.get("oos_start_time")
					if oos_start:
						# Calculate duration in minutes
						duration_seconds = time_diff_in_seconds(self.oos_end_time, oos_start)
						self.oos_duration_minutes = int(duration_seconds / 60)
