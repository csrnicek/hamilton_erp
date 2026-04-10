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


# ---------------------------------------------------------------------------
# Public lifecycle functions
# ---------------------------------------------------------------------------


def start_session_for_asset(asset_name: str, *, operator: str, customer: str = "Walk-in") -> str:
	"""Available → Occupied + create Venue Session. Returns session name."""
	from hamilton_erp.locks import asset_status_lock
	from hamilton_erp.realtime import publish_status_change

	with asset_status_lock(asset_name, "assign") as row:
		_require_transition(row, current="Available", target="Occupied",
		                    asset_name=asset_name)
		# NOTE: _create_session runs BEFORE _set_asset_status. A throw from
		# _set_asset_status (e.g. hypothetical version-CAS failure) would leave
		# the Venue Session insert pending — the request-level transaction rolls
		# it back in a normal HTTP call path. Programmatic callers MUST NOT
		# wrap this in try/except; let exceptions propagate to trigger rollback.
		session_name = _create_session(asset_name, operator=operator, customer=customer)
		_set_asset_status(
			asset_name,
			new_status="Occupied",
			session=session_name,
			log_reason=None,
			operator=operator,
			previous="Available",
			expected_version=row["version"],
		)
	publish_status_change(asset_name, previous_status="Available")
	return session_name


# ---------------------------------------------------------------------------
# Private helpers (all run INSIDE the lock — zero I/O except the permitted writes)
# ---------------------------------------------------------------------------


def _create_session(asset_name: str, *, operator: str, customer: str) -> str:
	"""Insert a Venue Session row for a freshly-assigned asset. Caller holds the asset lock.

	NOTE: session_number is intentionally unset — Task 9 wires the Redis INCR
	generator. identity_method defaults to 'not_applicable' via the controller's
	_set_defaults hook.
	"""
	session = frappe.get_doc({
		"doctype": "Venue Session",
		"venue_asset": asset_name,
		"operator_checkin": operator,
		"customer": customer,
		"session_start": frappe.utils.now_datetime(),
		"status": "Active",
		"assignment_status": "Assigned",
	}).insert(ignore_permissions=True)
	return session.name


def _set_asset_status(
	asset_name: str,
	*,
	new_status: str,
	session: Optional[str],
	log_reason: Optional[str],
	operator: str,
	previous: str,
	expected_version: int,
) -> None:
	"""Write the new status, bump version, and create the audit log.

	The caller must have just read `expected_version` under FOR UPDATE inside the
	same lock, so an optimistic-lock conflict here would be a bug, not a race.
	"""
	# for_update=True bypasses frappe.local.document_cache, which could return
	# a pre-lock snapshot if an earlier get_doc in this request cached the asset.
	# Safe — we already hold the row lock via the caller's asset_status_lock.
	asset = frappe.get_doc("Venue Asset", asset_name, for_update=True)
	if asset.version != expected_version:
		frappe.throw(_("Concurrent update to {0} — please refresh and retry.")
		             .format(asset_name))
	asset.status = new_status
	asset.current_session = session
	asset.version = expected_version + 1
	asset.hamilton_last_status_change = frappe.utils.now_datetime()
	if new_status == "Out of Service":
		asset.reason = log_reason
	asset.save(ignore_permissions=True)
	_make_asset_status_log(
		asset_name=asset_name,
		previous=previous,
		new_status=new_status,
		reason=log_reason,
		operator=operator,
		venue_session=session,
	)
