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
	# NEW-2 per docs/inbox/2026-05-04_audit_synthesis_decisions.md: wrap the
	# publish in try/except so a transient Frappe Cloud realtime / socketio
	# hiccup cannot turn the operator's response payload into a stack trace.
	# The DB has already committed (the lifecycle caller routed us here AFTER
	# the lock + after_commit), so the right behaviour on publish failure is
	# to log + continue. The Asset Board's polling fallback heals the
	# divergence on the next refresh.
	#
	# The nested try around log_error is defensive: log_error's own post-save
	# hook calls publish_realtime (Frappe's notify_update on the new Error Log
	# row). If the realtime infra is down, that nested publish ALSO fails. In
	# that case fall back to the process logger so the asset_name lands
	# somewhere greppable in bench logs.
	try:
		frappe.publish_realtime(
			"hamilton_asset_status_changed", row, after_commit=True
		)
	except Exception:
		try:
			frappe.log_error(
				title="publish_status_change: publish_realtime failed",
				message=(
					f"asset_name={asset_name!r} previous_status={previous_status!r}\n\n"
					f"{frappe.get_traceback()}"
				),
			)
		except Exception:
			# Last-resort fallback — process logger doesn't touch the DB or
			# the realtime infra, so it works even when both are unhealthy.
			frappe.logger().warning(
				f"publish_status_change: both publish_realtime and "
				f"log_error failed for asset_name={asset_name!r} "
				f"previous_status={previous_status!r}"
			)


# publish_board_refresh was REMOVED 2026-04-29 (DEC-054 reversed). Bulk
# operations no longer exist; per-asset publish_status_change is the only
# realtime event used by Phase 1.
