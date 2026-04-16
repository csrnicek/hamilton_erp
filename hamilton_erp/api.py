import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Sales Invoice doc_event hook (wired in hooks.py)
# Phase 2 completes this implementation. Phase 0 stub only.
# ---------------------------------------------------------------------------


def on_sales_invoice_submit(doc, method):
	"""After POS Sales Invoice is submitted, check for admission items.

	`doc` is a HamiltonSalesInvoice instance (registered via extend_doctype_class
	in hooks.py), so the Hamilton-specific helper methods are available directly.

	If the cart contains an admission item, the custom asset-assignment flow is
	triggered via a realtime event so the operator can select a room or locker.
	Retail-only sales pass through untouched.

	NOTE: Do not call frappe.db.commit() here — v16 prohibits commits inside
	doc_events hooks (coding_standards.md §2.8).

	Realtime payload contract:
	  event:    "show_asset_assignment"
	  payload:  {"invoice": str, "category": "Room"|"Locker", "is_comp": bool}
	"""
	if not doc.has_admission_item():
		return

	# Trigger the asset-assignment overlay on the operator's terminal.
	# after_commit=True ensures the client receives the event only after
	# the Sales Invoice transaction has committed to the database.
	frappe.publish_realtime(
		"show_asset_assignment",
		{
			"invoice": doc.name,
			"category": doc.get_admission_category() or "Room",
			"is_comp": doc.has_comp_admission(),
		},
		user=frappe.session.user,
		after_commit=True,
	)


# ---------------------------------------------------------------------------
# Asset board API (Phase 1)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_asset_board_data() -> dict:
	"""Initial Asset Board load. Single batched query shape — no N+1.

	Returns:
		{
			"assets": [ {name, asset_code, asset_name, asset_category,
			             asset_tier, status, current_session,
			             expected_stay_duration, display_order,
			             last_vacated_at, last_cleaned_at,
			             hamilton_last_status_change, version,
			             session_start (only for Occupied)}, ... ],
			"settings": {grace_minutes, default_stay_duration_minutes, ...},
		}

	Enrichment is deliberately batched: after pulling the asset list, we
	collect every `current_session` for Occupied rows and fetch their
	`session_start` values in a single `frappe.get_all(..., "name in ...)`
	call. A naive loop over `get_value` would be 1 + N round trips; this
	path is guaranteed to be 2 queries regardless of occupancy. The
	`test_get_asset_board_data_under_one_second` perf baseline in
	`test_api_phase1.py` guards against future N+1 regressions.
	"""
	frappe.has_permission("Venue Asset", "read", throw=True)

	assets = frappe.get_all(
		"Venue Asset",
		fields=[
			"name", "asset_code", "asset_name", "asset_category", "asset_tier",
			"status", "current_session", "expected_stay_duration", "display_order",
			"last_vacated_at", "last_cleaned_at", "hamilton_last_status_change",
			"version",
		],
		filters={"is_active": 1},
		order_by="display_order asc",
		limit=500,
	)

	# Batched session_start lookup — one query for all occupied tiles
	occupied_session_ids = [
		a["current_session"] for a in assets
		if a["status"] == "Occupied" and a.get("current_session")
	]
	session_starts: dict[str, object] = {}
	if occupied_session_ids:
		rows = frappe.get_all(
			"Venue Session",
			fields=["name", "session_start"],
			filters={"name": ["in", occupied_session_ids]},
		)
		session_starts = {r["name"]: r["session_start"] for r in rows}
	for a in assets:
		a["session_start"] = session_starts.get(a.get("current_session"))

	return {"assets": assets, "settings": _get_hamilton_settings()}


def _get_hamilton_settings() -> dict:
	"""Return the subset of Hamilton Settings the Asset Board needs.

	Uses `frappe.get_cached_doc` so repeated calls within the same request
	are free. Falls back to sensible defaults per field so the Asset Board
	still renders on a freshly-installed site where Hamilton Settings may
	not yet have been filled in.
	"""
	s = frappe.get_cached_doc("Hamilton Settings")
	return {
		"grace_minutes": s.get("grace_minutes") or 15,
		"default_stay_duration_minutes": s.get("default_stay_duration_minutes") or 360,
		"assignment_timeout_minutes": s.get("assignment_timeout_minutes") or 15,
	}


@frappe.whitelist(methods=["POST"])
def assign_asset_to_session(sales_invoice: str, asset_name: str) -> dict:
	"""Assign a Venue Asset after POS payment is confirmed.

	Creates a Venue Session, links it to the Sales Invoice and the asset,
	and transitions the asset to Occupied.  Phase 2 implementation.
	"""
	frappe.has_permission("Venue Asset", "write", throw=True)
	# Phase 2 not yet built. This endpoint must not be exposed in any UI until Phase 2 ships.
	frappe.throw(_("This feature is not yet available. Please contact your manager."))


# ---------------------------------------------------------------------------
# Bulk cleaning (Phase 1, DEC-054)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def mark_all_clean_rooms() -> dict:
	"""Bulk-transition every Dirty room to Available.

	Used by the Asset Board's "Mark All Rooms Clean" bulk action after a
	rush hour reset. Per-asset errors are captured and returned, not raised,
	so one stuck row can't block a cleanup of 20 others.
	"""
	frappe.has_permission("Venue Asset", "write", throw=True)
	return _mark_all_clean(category="Room")


@frappe.whitelist(methods=["POST"])
def mark_all_clean_lockers() -> dict:
	"""Bulk-transition every Dirty locker to Available. See rooms variant."""
	frappe.has_permission("Venue Asset", "write", throw=True)
	return _mark_all_clean(category="Locker")


def _mark_all_clean(category: str) -> dict:
	"""Loop over all Dirty assets of the given category, cleaning each one.

	Sorted by `name` to establish a deterministic lock ordering across the
	loop (coding_standards.md §13.4) — concurrent invocations of the two
	bulk endpoints take locks in the same order every time, so they cannot
	deadlock against each other.

	Per-asset failures are recorded in the `failed` list and reported to
	the caller; the loop does not abort. A single `hamilton_asset_board_refresh`
	realtime event is fired once the loop completes so the Asset Board
	pulls the canonical state in one request instead of re-rendering each
	tile individually (DEC-054).
	"""
	from hamilton_erp.lifecycle import mark_asset_clean
	from hamilton_erp.realtime import publish_board_refresh

	dirty = frappe.get_all(
		"Venue Asset",
		filters={"status": "Dirty", "asset_category": category, "is_active": 1},
		fields=["name", "asset_code", "asset_name"],
		order_by="name asc",
	)
	succeeded: list[str] = []
	failed: list[dict] = []
	reason = f"Bulk Mark Clean — {category} reset"
	for asset in dirty:
		try:
			mark_asset_clean(
				asset["name"],
				operator=frappe.session.user,
				bulk_reason=reason,
			)
			succeeded.append(asset["asset_code"])
		except Exception as e:
			failed.append({"code": asset["asset_code"], "error": str(e)})
	publish_board_refresh("bulk_clean", len(succeeded))
	return {"succeeded": succeeded, "failed": failed}


# ---------------------------------------------------------------------------
# Single-asset actions (Phase 1 — called by Asset Board popover)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def start_walk_in_session(asset_name: str) -> dict:
	"""Assign a walk-in session to an Available asset. Available → Occupied."""
	frappe.has_permission("Venue Asset", "write", throw=True)
	from hamilton_erp.lifecycle import start_session_for_asset

	session_name = start_session_for_asset(asset_name, operator=frappe.session.user)
	return {"session": session_name}


@frappe.whitelist(methods=["POST"])
def vacate_asset(asset_name: str, vacate_method: str) -> dict:
	"""Vacate an Occupied asset. Occupied → Dirty."""
	frappe.has_permission("Venue Asset", "write", throw=True)
	from hamilton_erp.lifecycle import vacate_session

	vacate_session(asset_name, operator=frappe.session.user, vacate_method=vacate_method)
	return {"status": "ok"}


@frappe.whitelist(methods=["POST"])
def clean_asset(asset_name: str) -> dict:
	"""Mark a single Dirty asset as clean. Dirty → Available."""
	frappe.has_permission("Venue Asset", "write", throw=True)
	from hamilton_erp.lifecycle import mark_asset_clean

	mark_asset_clean(asset_name, operator=frappe.session.user)
	return {"status": "ok"}


@frappe.whitelist(methods=["POST"])
def set_asset_oos(asset_name: str, reason: str) -> dict:
	"""Set an asset Out of Service. Reason is mandatory."""
	frappe.has_permission("Venue Asset", "write", throw=True)
	from hamilton_erp.lifecycle import set_asset_out_of_service

	set_asset_out_of_service(asset_name, operator=frappe.session.user, reason=reason)
	return {"status": "ok"}


@frappe.whitelist(methods=["POST"])
def return_asset_from_oos(asset_name: str, reason: str) -> dict:
	"""Return an Out of Service asset to Available. Reason is mandatory."""
	frappe.has_permission("Venue Asset", "write", throw=True)
	from hamilton_erp.lifecycle import return_asset_to_service

	return_asset_to_service(asset_name, operator=frappe.session.user, reason=reason)
	return {"status": "ok"}
