"""Shared utility functions for the Hamilton ERP app."""

import frappe
from frappe import _
from frappe.utils import now_datetime


def get_current_shift_record(operator: str) -> str | None:
	"""Return the name of the active (Open) Shift Record for an operator, or None."""
	record = frappe.db.get_value(
		"Shift Record",
		{"operator": operator, "status": "Open"},
		"name",
		order_by="shift_start desc",
	)
	return record or None


def get_next_drop_number(shift_record: str) -> int:
	"""Return the next sequential cash drop number for a given shift."""
	count = frappe.db.count("Cash Drop", {"shift_record": shift_record})
	return (count or 0) + 1


def create_asset_status_log(
	venue_asset: str,
	previous_status: str,
	new_status: str,
	operator: str,
	reason: str = "",
) -> None:
	"""Create an Asset Status Log entry for every asset state change.

	This is the audit trail for the asset board — every transition must be
	recorded regardless of how it was triggered.
	"""
	frappe.get_doc(
		{
			"doctype": "Asset Status Log",
			"venue_asset": venue_asset,
			"previous_status": previous_status,
			"new_status": new_status,
			"reason": reason,
			"operator": operator,
			"timestamp": now_datetime(),
		}
	).insert(ignore_permissions=True)
