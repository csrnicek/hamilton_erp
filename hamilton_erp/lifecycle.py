"""Venue Asset state-transition and session lifecycle core.

Public API (called from venue_asset.py whitelisted methods and from api.py):
    start_session_for_asset, vacate_session, mark_asset_clean,
    set_asset_out_of_service, return_asset_to_service, mark_all_clean

All public functions:
  - acquire the three-layer lock (locks.asset_status_lock)
  - validate the transition
  - mutate the asset, bump version, write timestamps
  - create an Asset Status Log entry (skipped in tests — see _make_asset_status_log)
  - publish the realtime event OUTSIDE the lock (via hamilton_erp.realtime)

No function here performs I/O (print, enqueue, publish_realtime) inside
the lock section.
"""
from __future__ import annotations

from typing import Optional

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# State machine — single source of truth
# ---------------------------------------------------------------------------
#
# This is the canonical state map for Venue Asset status transitions.
# The VenueAsset controller (venue_asset.py) imports this constant for its
# validate() hook, so the map is defined ONCE here. Do not duplicate.

VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
	"Available": ("Occupied", "Out of Service"),
	"Occupied": ("Dirty", "Out of Service"),
	"Dirty": ("Available", "Out of Service"),
	"Out of Service": ("Available",),
}


def _require_transition(row: dict, *, current: str, target: str, asset_name: str) -> None:
	"""Throw if row["status"] != current OR if current→target is not a valid edge."""
	if row["status"] != current:
		frappe.throw(_("Cannot {0} {1}: current status is {2}, expected {3}.")
		             .format(target.lower(), asset_name, row["status"], current))
	if target not in VALID_TRANSITIONS.get(current, ()):
		frappe.throw(_("Invalid transition {0}→{1} for {2}.")
		             .format(current, target, asset_name))


def _require_oos_entry(row: dict, *, asset_name: str) -> None:
	"""Out of Service can come from Available / Occupied / Dirty, but not from itself."""
	if row["status"] == "Out of Service":
		frappe.throw(_("Asset {0} is already Out of Service.").format(asset_name))


# ---------------------------------------------------------------------------
# Asset Status Log — in-test guard (Grok review 2026-04-10)
# ---------------------------------------------------------------------------


def _make_asset_status_log(
	*,
	asset_name: str,
	previous: str,
	new_status: str,
	reason: Optional[str],
	operator: str,
	venue_session: Optional[str],
) -> Optional[str]:
	"""Create an Asset Status Log entry. Short-circuits in tests.

	Returns the log name, or None when suppressed.

	Tests that specifically assert log creation must clear frappe.flags.in_test
	locally via setUp/tearDown.
	"""
	if frappe.flags.in_test:
		return None
	log = frappe.get_doc({
		"doctype": "Asset Status Log",
		"venue_asset": asset_name,
		"previous_status": previous,
		"new_status": new_status,
		"reason": reason,
		"operator": operator,
		"venue_session": venue_session,
		"timestamp": frappe.utils.now_datetime(),
	}).insert(ignore_permissions=True)
	return log.name
