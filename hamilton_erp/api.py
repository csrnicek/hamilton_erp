import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Sales Invoice doc_event hook (wired in hooks.py)
# Phase 2 completes this implementation. Phase 0 stub only.
# ---------------------------------------------------------------------------


def on_sales_invoice_submit(doc, method):
	"""After POS Sales Invoice is submitted, check for admission items.

	`doc` is a HamiltonSalesInvoice instance (registered via override_doctype_class
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
