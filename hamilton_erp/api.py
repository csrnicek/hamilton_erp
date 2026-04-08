import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Sales Invoice doc_event hook (wired in hooks.py)
# Phase 2 completes this implementation. Phase 0 stub only.
# ---------------------------------------------------------------------------


def on_sales_invoice_submit(doc, method):
	"""After POS Sales Invoice is submitted, check for admission items.

	If the cart contains an admission item (hamilton_is_admission = 1) the
	custom asset-assignment flow is triggered via a realtime event so the
	operator can select a room or locker.  Retail-only sales pass through
	untouched.

	NOTE: Do not call frappe.db.commit() here — v16 prohibits commits inside
	doc_events hooks.
	"""
	has_admission = any(
		item.get("hamilton_is_admission") for item in doc.items
	)
	if not has_admission:
		return

	admission_category = _get_admission_category(doc)

	# Trigger the asset-assignment overlay on the operator's terminal.
	# after_commit=True ensures the client receives the event only after
	# the Sales Invoice transaction has committed to the database.
	frappe.publish_realtime(
		"show_asset_assignment",
		{"invoice": doc.name, "category": admission_category, "is_comp": _is_comp_admission(doc)},
		user=frappe.session.user,
		after_commit=True,
	)


def _get_admission_category(doc) -> str:
	"""Return the asset category (Room/Locker) from the first admission item."""
	for item in doc.items:
		if item.get("hamilton_is_admission"):
			return item.get("hamilton_asset_category") or "Room"
	return "Room"


def _is_comp_admission(doc) -> bool:
	"""Return True if any admission item in the invoice is a comp."""
	return any(
		item.get("hamilton_is_comp") for item in doc.items if item.get("hamilton_is_admission")
	)


# ---------------------------------------------------------------------------
# Asset board API (Phase 1)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_asset_board_data() -> dict:
	"""Return all venue assets for the asset board UI."""
	assets = frappe.get_all(
		"Venue Asset",
		fields=[
			"name",
			"asset_name",
			"asset_category",
			"asset_tier",
			"status",
			"current_session",
			"expected_stay_duration",
			"display_order",
		],
		order_by="asset_category asc, display_order asc",
	)
	return {"assets": assets}


@frappe.whitelist(methods=["POST"])
def assign_asset_to_session(sales_invoice: str, asset_name: str) -> dict:
	"""Assign a Venue Asset after POS payment is confirmed.

	Creates a Venue Session, links it to the Sales Invoice and the asset,
	and transitions the asset to Occupied.  Phase 2 implementation.
	"""
	frappe.has_permission("Venue Asset", "write", throw=True)
	# Full implementation in Phase 2.
	frappe.throw(_("Phase 2 not yet implemented"))
