"""Realtime publishers for the Hamilton Asset Board.

Both functions fire `frappe.publish_realtime` with `after_commit=True`
— they must only be called AFTER the lock section has exited and the
underlying transaction has committed (or is about to). Calling inside
the lock risks emitting an event for state that gets rolled back,
leaving the client's view diverged from the DB.

Per coding_standards.md §13, `lifecycle.py` treats any `publish_*` call
as I/O and routes it OUTSIDE the `asset_status_lock` context manager.
The realtime publishers here do not acquire their own locks and do not
re-validate state — they snapshot the row as it exists at publish time
and ship it to subscribed clients.

The moderate "C2" payload shape for `hamilton_asset_status_changed`
(name, status, version, current_session, last_vacated_at,
last_cleaned_at, hamilton_last_status_change, old_status) is set by
Phase 1 design §5.9 — the Asset Board consumes exactly these fields
and re-renders a single tile per event.
"""
from __future__ import annotations

from typing import Optional

import frappe


def publish_status_change(
	asset_name: str, previous_status: Optional[str] = None
) -> None:
	"""Emit `hamilton_asset_status_changed` with the moderate C2 payload.

	Reads the current row state at publish time (not a cached snapshot
	from the lifecycle caller) so the payload reflects every field the
	transaction wrote — including audit fields like
	`hamilton_last_status_change` that the caller does not explicitly
	track. Uses `frappe.db.get_value` with a field list to pull exactly
	the fields the Asset Board tile needs, no more.

	No-op when the row has been deleted between the lifecycle call and
	this publish. Raising here would surface a confusing error for a
	state change that already committed successfully; the Asset Board
	simply misses the single event and the next refresh picks up the
	canonical state. This is the correct trade-off for a publish path
	that runs after_commit.
	"""
	row = frappe.db.get_value(
		"Venue Asset",
		asset_name,
		fieldname=[
			"name",
			"status",
			"version",
			"current_session",
			"expected_stay_duration",
			"last_vacated_at",
			"last_cleaned_at",
			"hamilton_last_status_change",
		],
		as_dict=True,
	)
	if not row:
		return
	row["old_status"] = previous_status
	# Enrich Occupied tiles with session_start for the overtime ticker
	if row["status"] == "Occupied" and row.get("current_session"):
		row["session_start"] = frappe.db.get_value(
			"Venue Session", row["current_session"], "session_start"
		)
	else:
		row["session_start"] = None
	frappe.publish_realtime(
		"hamilton_asset_status_changed", row, after_commit=True
	)


def publish_board_refresh(triggered_by: str, count: int) -> None:
	"""Emit `hamilton_asset_board_refresh` for bulk operations.

	Fired by bulk paths (e.g. `mark_all_clean`) that mutate many assets
	in one call. The Asset Board responds by pulling the full list
	instead of re-rendering N individual tiles. `triggered_by` is the
	machine-readable cause string (e.g. `"bulk_clean"`) and `count` is
	the number of assets affected, so a reviewer inspecting the
	realtime stream can distinguish bulk events from individual ones
	without guessing.
	"""
	frappe.publish_realtime(
		"hamilton_asset_board_refresh",
		{"triggered_by": triggered_by, "count": count},
		after_commit=True,
	)
