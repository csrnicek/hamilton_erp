import json

import frappe
from frappe import _
from frappe.utils import flt


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
			             session_start (only for Occupied),
			             guest_name (only for Occupied, V9 D6/E8),
			             oos_set_by (only for OOS, V9 E11)}, ... ],
			"settings": {grace_minutes, default_stay_duration_minutes, ...},
		}

	Enrichment is deliberately batched: after pulling the asset list, we
	collect every `current_session` for Occupied rows and fetch their
	`session_start` and `full_name` values in a single batched query. For
	OOS rows we batch-query Asset Status Log for the most-recent
	OOS-transition operator, then resolve user IDs to full names in one
	more batched query. Total queries: 1 (assets) + 1 (sessions) + 1
	(status logs) + 1 (users) = 4, regardless of occupancy. A naive loop
	over `get_value` would be 1 + N round trips. The
	`test_get_asset_board_data_under_one_second` perf baseline in
	`test_api_phase1.py` guards against future N+1 regressions.

	V9 panel enrichment (Phase 1 closeout, 2026-04-29):
	- guest_name: feeds the .hamilton-guest-info panel in expanded
	  Occupied overlay. Walk-in (anonymous) sessions have full_name=None,
	  which the JS gracefully renders as elapsed-only.
	- oos_set_by: feeds the .hamilton-oos-info-meta line in expanded OOS
	  overlay ("Set by M. CHEN · 4 days ago"). Resolved from Asset Status
	  Log → User.full_name. Days-ago is computed client-side from
	  hamilton_last_status_change (already in the asset payload).
	"""
	frappe.has_permission("Venue Asset", "read", throw=True)

	assets = frappe.get_all(
		"Venue Asset",
		fields=[
			"name", "asset_code", "asset_name", "asset_category", "asset_tier",
			"status", "current_session", "expected_stay_duration", "display_order",
			"last_vacated_at", "last_cleaned_at", "hamilton_last_status_change",
			"version",
			# OOS reason — read by asset_board.js OOS expand panel and
			# Return-to-Service modal. Without this field both call sites
			# fall back to "Reason unknown" forever (user-visible bug).
			"reason",
		],
		filters={"is_active": 1},
		order_by="display_order asc",
		limit=500,
	)

	# Batched session lookup — one query for all occupied tiles.
	# Pulls session_start AND full_name (V9 guest-info panel D6/E8).
	# full_name is used for the Occupied tile's guest-info display; falls
	# back to None for Walk-in (anonymous) sessions.
	occupied_session_ids = [
		a["current_session"] for a in assets
		if a["status"] == "Occupied" and a.get("current_session")
	]
	session_data: dict[str, dict] = {}
	if occupied_session_ids:
		rows = frappe.get_all(
			"Venue Session",
			fields=["name", "session_start", "full_name"],
			filters={"name": ["in", occupied_session_ids]},
		)
		session_data = {r["name"]: r for r in rows}
	for a in assets:
		sess = session_data.get(a.get("current_session")) or {}
		a["session_start"] = sess.get("session_start")
		# V9 D6/E8: guest_name for Occupied tile guest-info panel
		a["guest_name"] = sess.get("full_name") or None

	# V9 E11: who set this asset Out of Service?
	# Batched lookup of the most-recent Asset Status Log entry where
	# new_status='Out of Service' for each currently-OOS asset. Returns
	# the operator's full name (or User docname as fallback).
	oos_asset_names = [
		a["name"] for a in assets if a["status"] == "Out of Service"
	]
	oos_operators: dict[str, str] = {}
	if oos_asset_names:
		# Fetch all OOS-transition log entries for these assets in one
		# query, then keep the most-recent per asset.
		log_rows = frappe.get_all(
			"Asset Status Log",
			fields=["venue_asset", "operator", "timestamp"],
			filters={
				"venue_asset": ["in", oos_asset_names],
				"new_status": "Out of Service",
			},
			order_by="timestamp desc",
		)
		seen: set[str] = set()
		latest_by_asset: dict[str, str] = {}
		operator_user_ids: set[str] = set()
		for r in log_rows:
			asset_name = r["venue_asset"]
			if asset_name in seen:
				continue
			seen.add(asset_name)
			latest_by_asset[asset_name] = r["operator"] or ""
			if r["operator"]:
				operator_user_ids.add(r["operator"])
		# Resolve user IDs to full names in a single query.
		user_full_names: dict[str, str] = {}
		if operator_user_ids:
			user_rows = frappe.get_all(
				"User",
				fields=["name", "full_name"],
				filters={"name": ["in", list(operator_user_ids)]},
			)
			user_full_names = {
				u["name"]: (u.get("full_name") or u["name"]) for u in user_rows
			}
		for asset_name, user_id in latest_by_asset.items():
			if user_id:
				oos_operators[asset_name] = user_full_names.get(user_id, user_id)
	for a in assets:
		# V9 E11: oos_set_by for OOS-info panel in expanded overlay
		a["oos_set_by"] = (
			oos_operators.get(a["name"])
			if a["status"] == "Out of Service" else None
		)

	# V9.1 retail amendment: enrich payload with retail Items grouped by
	# Item Group when the venue has `retail_tabs` configured in
	# site_config.json. Empty config (or no retail Items) returns empty
	# arrays — venues with no retail surface get an asset-only board with
	# no extra queries.
	retail_payload = _get_retail_payload()
	return {
		"assets": assets,
		"settings": _get_hamilton_settings(),
		"items": retail_payload["items"],
		"retail_tabs": retail_payload["retail_tabs"],
	}


def _get_retail_payload() -> dict:
	"""Return retail Items + tab list for venues that opt in via site_config.

	`site_config.json` key `retail_tabs` is a list of Item Group names. Each
	maps to a tab in the Asset Board. Items in the configured groups are
	fetched in one batched query, and stock counts come from one batched
	`Bin` query against the venue's default Warehouse.

	Total queries: 0 (when no retail config), 2 (Item + Bin) otherwise.
	No N+1.
	"""
	tabs = frappe.conf.get("retail_tabs") or []
	if not isinstance(tabs, list) or not tabs:
		return {"items": [], "retail_tabs": []}

	default_warehouse = frappe.db.get_single_value(
		"Stock Settings", "default_warehouse"
	)
	# Active Items in any of the configured groups.
	items = frappe.get_all(
		"Item",
		filters={
			"item_group": ["in", tabs],
			"disabled": 0,
		},
		fields=[
			"name", "item_code", "item_name", "item_group",
			"image", "standard_rate",
		],
		order_by="item_group asc, item_code asc",
	)
	# Stock counts via Bin (per-warehouse). Filter to the venue's default
	# warehouse — multi-warehouse selection is deferred per V9.1-D7.
	stock_by_item: dict[str, float] = {}
	if items and default_warehouse:
		bin_rows = frappe.get_all(
			"Bin",
			filters={
				"item_code": ["in", [i["item_code"] for i in items]],
				"warehouse": default_warehouse,
			},
			fields=["item_code", "actual_qty"],
		)
		stock_by_item = {b["item_code"]: b["actual_qty"] for b in bin_rows}
	for it in items:
		it["stock"] = float(stock_by_item.get(it["item_code"], 0) or 0)
	return {"items": items, "retail_tabs": tabs}


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
		"show_waitlist_tab": bool(s.get("show_waitlist_tab")),
		"show_other_tab": bool(s.get("show_other_tab")),
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


# Bulk "Mark All Clean" feature was REMOVED 2026-04-29 (DEC-054 reversed).
# Per browser-test session 2026-04-29: cleaning happens per-tile via the
# Dirty tile's expand-overlay "Mark Clean" action (the per-asset path that
# was always present). The bulk endpoint was an opt-in shortcut that
# bypassed the per-tile audit context and was never used by operators in
# live testing.


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


# ---------------------------------------------------------------------------
# Retail cart — Sales Invoice creation (V9.1 Phase 2)
# ---------------------------------------------------------------------------


HAMILTON_POS_PROFILE = "Hamilton Front Desk"


@frappe.whitelist(methods=["POST"])
def submit_retail_sale(items, cash_received) -> dict:
	"""Create + submit a POS Sales Invoice from the cart drawer.

	Called by ``_open_cash_payment_modal`` in asset_board.js when the
	operator confirms a cash payment. Creates a POS Sales Invoice with
	``is_pos=1, update_stock=1`` so submitting auto-creates the Stock
	Ledger Entry that decrements warehouse stock.

	Arguments:
	  items: list of {item_code, qty, unit_price}. JSON-encoded by
	         frappe.xcall when sent from the client; accepts list or str.
	  cash_received: numeric (Currency). Must be >= grand_total. Change
	         is computed and returned.

	Returns:
	  {sales_invoice: str, change: float, grand_total: float}

	Raises:
	  - PermissionError if caller lacks Sales Invoice create perm.
	  - ValidationError if cart empty, cash_received < grand_total, or
	    POS Profile / Walk-in customer missing.
	"""
	frappe.has_permission("Sales Invoice", "create", throw=True)

	# frappe.xcall serializes lists to JSON over the wire. Accept both.
	if isinstance(items, str):
		items = json.loads(items)
	if not items or not isinstance(items, list):
		frappe.throw(_("Cart is empty"))
	cash_received = flt(cash_received)
	if cash_received < 0:
		frappe.throw(_("Cash received cannot be negative"))

	if not frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE):
		frappe.throw(_(
			"POS Profile {0} is not configured. Run `bench migrate` to seed."
		).format(HAMILTON_POS_PROFILE))
	if not frappe.db.exists("Customer", "Walk-in"):
		frappe.throw(_(
			"Walk-in customer not seeded. Run `bench migrate` to populate."
		))

	pos_profile = frappe.get_cached_doc("POS Profile", HAMILTON_POS_PROFILE)

	si = frappe.new_doc("Sales Invoice")
	si.update({
		"company": pos_profile.company,
		"customer": "Walk-in",
		"is_pos": 1,
		"update_stock": 1,
		"pos_profile": HAMILTON_POS_PROFILE,
		"currency": pos_profile.currency,
		"selling_price_list": pos_profile.selling_price_list or "Standard Selling",
	})
	if pos_profile.taxes_and_charges:
		si.taxes_and_charges = pos_profile.taxes_and_charges

	for line in items:
		item_code = line.get("item_code")
		qty = flt(line.get("qty"))
		unit_price = flt(line.get("unit_price"))
		if not item_code or qty <= 0:
			frappe.throw(_("Invalid cart line: {0}").format(line))
		if not frappe.db.exists("Item", item_code):
			frappe.throw(_("Item {0} does not exist").format(item_code))
		si.append("items", {
			"item_code": item_code,
			"qty": qty,
			"rate": unit_price,
			"warehouse": pos_profile.warehouse,
			"cost_center": pos_profile.cost_center,
		})

	# Pull tax rows from the template before computing totals. ERPNext's
	# ``set_taxes()`` is the canonical method on AccountsController.
	if si.taxes_and_charges:
		si.set_taxes_and_charges()

	si.set_missing_values()
	si.calculate_taxes_and_totals()
	grand_total = flt(si.grand_total)

	if cash_received < grand_total:
		frappe.throw(_(
			"Cash received {0} is less than grand total {1}"
		).format(cash_received, grand_total))

	change = flt(cash_received - grand_total)
	si.append("payments", {
		"mode_of_payment": "Cash",
		"amount": grand_total,  # collected in cash, change handled separately
	})
	si.change_amount = change
	si.base_change_amount = change
	si.paid_amount = grand_total
	si.base_paid_amount = grand_total

	si.flags.ignore_permissions = True
	si.insert(ignore_permissions=True)
	si.submit()

	return {
		"sales_invoice": si.name,
		"change": change,
		"grand_total": grand_total,
	}
