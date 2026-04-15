"""Shared utility functions for the Hamilton ERP app."""

import frappe
from frappe import _


def get_current_shift_record(operator: str) -> str | None:
	"""Return the name of the active (Open) Shift Record for an operator, or None."""
	record = frappe.db.get_value(
		"Shift Record",
		{"operator": operator, "status": "Open"},
		"name",
		order_by="shift_start desc, name asc",
	)
	return record or None


def get_next_drop_number(shift_record: str) -> int:
	"""Return the next sequential cash drop number for a given shift.

	Raises if shift_record is blank — callers must ensure an active shift
	exists before creating a Cash Drop.  Passing None or '' would count
	against the null-shift bucket and produce incorrect drop numbers.
	"""
	if not shift_record:
		frappe.throw(_("Cannot create a Cash Drop: no active shift found. Please start a shift first."))
	count = frappe.db.count("Cash Drop", {"shift_record": shift_record})
	return (count or 0) + 1


