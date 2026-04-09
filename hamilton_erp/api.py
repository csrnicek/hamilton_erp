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
		order_by="asset_category asc, display_order asc, name asc",
	)
	return {"assets": assets}


@frappe.whitelist(methods=["POST"])
def assign_asset_to_session(sales_invoice: str, asset_name: str) -> dict:
	"""Assign a Venue Asset after POS payment is confirmed.

	Creates a Venue Session, links it to the Sales Invoice and the asset,
	and transitions the asset to Occupied.  Phase 2 implementation.
	"""
	frappe.has_permission("Venue Asset", "write", throw=True)
	# Phase 2 not yet built. This endpoint must not be exposed in any UI until Phase 2 ships.
	frappe.throw(_("This feature is not yet available. Please contact your manager."))
