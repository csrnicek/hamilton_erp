import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

# ---------------------------------------------------------------------------
# Sales Invoice doc_event hook (wired in hooks.py)
# Phase 2 completes this implementation. Phase 0 stub only.
# ---------------------------------------------------------------------------


def on_sales_invoice_submit(doc, method):
	"""After POS Sales Invoice submit: fire `show_asset_assignment` realtime
	event when the cart contains an admission item; retail-only sales pass
	through. Phase 0 stub — Phase 2 completes the assignment flow.

	`doc` is a HamiltonSalesInvoice (extend_doctype_class registration in
	hooks.py). No frappe.db.commit() — v16 doc_events forbid it
	(coding_standards.md §2.8).

	Realtime payload contract — event: "show_asset_assignment", payload:
	{"invoice": str, "category": "Room"|"Locker", "is_comp": bool}.
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
	oos_log_reasons: dict[str, str] = {}
	if oos_asset_names:
		# Fetch all OOS-transition log entries for these assets in one
		# query, then keep the most-recent per asset.
		# Also pluck `reason` from the same row — it's a durable
		# fallback when Venue Asset.reason is empty (legacy / migrated
		# rows OOS'd before the asset-row reason persistence landed,
		# or a future code path that fails to write it). The audit log
		# always carries the reason because set_asset_out_of_service
		# throws if reason is blank (lifecycle.py:433).
		log_rows = frappe.get_all(
			"Asset Status Log",
			fields=["venue_asset", "operator", "timestamp", "reason"],
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
			if r.get("reason"):
				oos_log_reasons[asset_name] = r["reason"]
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
		# Reason fallback: if Venue Asset.reason is empty for an OOS row,
		# pull the most-recent Asset Status Log entry's reason. Closes
		# the "Reason unknown" UI bug for legacy / migrated assets where
		# the asset-row reason was never persisted but the audit log
		# captured the reason at OOS-entry time.
		if a["status"] == "Out of Service" and not a.get("reason"):
			a["reason"] = oos_log_reasons.get(a["name"]) or a.get("reason")

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
		# DEC-099 — exposed so the Asset Board's Start Shift modal can
		# default the float prompt to the venue standard. Operators
		# rarely override; the single-tap default is the goal.
		"float_amount": float(s.get("float_amount") or 0),
	}


@frappe.whitelist(methods=["POST"])
def assign_asset_to_session(sales_invoice: str, asset_name: str) -> dict:
	"""Assign a Venue Asset after POS payment is confirmed.

	Creates a Venue Session, links it to the Sales Invoice and the asset,
	and transitions the asset to Occupied. **Phase 2 implementation; not
	wired in Phase 1.**

	T1-1 per docs/inbox/2026-05-04_audit_synthesis_decisions.md.
	Previously this endpoint hard-threw "feature not yet available". The
	hard-throw left a "paid but unassigned" trap: a Sales Invoice
	submitted via the standard /app/point-of-sale UI (or a manual Desk
	insert) with an admission item would fire ``on_sales_invoice_submit``
	(api.py:13-40), publish the assignment overlay event, and lead the
	operator to call this endpoint, which would crash. Customer pays;
	asset never assigned.

	Defense-in-depth response (T1-1):
	1. submit_retail_sale (above) now rejects admission items at the
	   cart-validation step. The retail cart can no longer be the source.
	2. This endpoint becomes a logged no-op rather than a hard throw.
	   The realtime event still fires (it's downstream of SI submit and
	   belongs to ERPNext core's hook chain), but calling this from the
	   overlay returns ``{"status": "phase_1_disabled", ...}`` cleanly
	   instead of stranding the operator with an exception.

	Phase 2 will replace this body with the real assignment flow.
	"""
	frappe.has_permission("Venue Asset", "write", throw=True)
	frappe.logger().warning(
		"assign_asset_to_session called in Phase 1 (no-op). "
		f"sales_invoice={sales_invoice!r} asset_name={asset_name!r} "
		"caller={caller!r}".format(caller=frappe.session.user)
	)
	return {
		"status": "phase_1_disabled",
		"message": _(
			"Asset assignment from POS payment is a Phase 2 feature. "
			"Use the walk-in Asset Board flow for assignments today."
		),
		"sales_invoice": sales_invoice,
		"asset_name": asset_name,
	}


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
# Admin correction endpoint (DEC-066)
#
# Implements the corrective surface that DEC-066 documents and PR #168
# anticipates via frappe.flags.allow_cash_drop_correction. Hamilton Admin /
# System Manager only — corrections are infrequent, high-trust, and must
# leave a tamper-resistant record.
#
# For audit-log targets (Asset Status Log, Comp Admission Log): the original
# row is left untouched. The Hamilton Board Correction row IS the correction.
# For mutable targets (Cash Drop, Venue Asset): the field is updated AND the
# correction row records the before/after.
# ---------------------------------------------------------------------------


# DocTypes whose rows are append-only (audit logs). Corrections to these
# DocTypes never mutate the original row — only a Hamilton Board Correction
# row pointing at the original is created.
_AUDIT_LOG_TARGETS = ("Asset Status Log", "Comp Admission Log")

# DocTypes whose rows accept field-level corrections (mutable targets).
# Each entry maps the target DocType to the frappe.flags.* attribute the
# target's controller respects to bypass its immutability guards.
# Cash Drop's allow_cash_drop_correction flag is honored by
# _validate_immutable_after_first_save / _validate_immutable_after_reconciliation
# in the cash_drop controller (T0-4, PR #168).
_MUTABLE_TARGETS = {
	"Cash Drop": "allow_cash_drop_correction",
	"Venue Asset": None,  # No controller-level immutability today; mutate directly.
}


def _is_admin_user() -> bool:
	"""Hamilton Admin or System Manager only.

	System Manager bypasses every Hamilton role check (Frappe convention).
	Hamilton Admin is the application-level admin role.
	"""
	roles = set(frappe.get_roles())
	return "System Manager" in roles or "Hamilton Admin" in roles


# Frappe fieldtypes that need numeric coercion before being assigned
# to a Document field. Whitelisted endpoints receive everything as
# strings on the wire; downstream validators do numeric comparisons
# (e.g. `if self.declared_amount < 0`) which TypeError on a string.
_NUMERIC_FIELDTYPES_FLOAT = {"Currency", "Float", "Percent"}
_NUMERIC_FIELDTYPES_INT = {"Int", "Check"}


def _coerce_field_value(doc, fieldname: str, value):
	"""Coerce `value` to the Python type the field expects.

	Resolves the field's Frappe fieldtype from `doc.meta` and converts:
	  * Currency / Float / Percent → frappe.utils.flt(value)
	  * Int / Check                → frappe.utils.cint(value)
	  * everything else (Data, Text, Select, Link, Datetime, …) → str(value)

	Returns the value unchanged if `value is None` so caller-supplied
	None gets stored as None (not "None"). Returns `value` as-is on an
	unknown fieldname so the caller's downstream `set` raises a clearer
	error than this helper would.
	"""
	if value is None:
		return None
	df = doc.meta.get_field(fieldname)
	if df is None:
		return value
	from frappe.utils import cint
	if df.fieldtype in _NUMERIC_FIELDTYPES_FLOAT:
		return flt(value)
	if df.fieldtype in _NUMERIC_FIELDTYPES_INT:
		return cint(value)
	# Data / Text / Select / Link / Datetime / Date / Time — keep as str.
	return str(value)


@frappe.whitelist(methods=["POST"])
def submit_admin_correction(
	target_doctype: str,
	target_name: str,
	reason: str,
	target_field: str | None = None,
	new_value: str | None = None,
) -> dict:
	"""Hamilton Admin / System Manager only — record a corrective change
	to a Hamilton-owned DocType row, with tamper-resistant audit trail.

	DEC-066 implementation. Bridges the operational gap T0-4 + T1-2 created:
	once Cash Drops are immutable after first save and audit logs cannot be
	deleted by Hamilton Admin, this is the sanctioned escape hatch for typo
	correction. Every correction lands in `tabHamilton Board Correction`
	(the DocType has track_changes=1 so the correction row itself is also
	auditable).

	Args:
		target_doctype: One of `Asset Status Log`, `Cash Drop`,
			`Comp Admission Log`, `Venue Asset`.
		target_name: The target row's `name` (primary key).
		reason: REQUIRED — free-text explanation. Logged to the correction
			row's `reason` field. Used by future auditors to understand
			intent.
		target_field: Optional. The specific field being corrected on the
			target row. Required when `new_value` is provided AND the
			target is mutable (Cash Drop / Venue Asset).
		new_value: Optional. The corrected value for `target_field`. For
			audit-log targets, this is recorded in the correction row's
			`new_value` but the audit row is NOT mutated. For mutable
			targets, the field is updated.

	Returns:
		{"status": "logged" | "applied", "correction": <correction name>,
		 "target_doctype": ..., "target_name": ...}

	Raises:
		frappe.PermissionError: caller lacks Hamilton Admin / System Manager.
		frappe.ValidationError: reason missing, target row missing,
			invalid target_doctype, or mutable-target call missing
			target_field/new_value.
	"""
	if not _is_admin_user():
		frappe.throw(_(
			"Admin corrections require Hamilton Admin or System Manager role."
		), exc=frappe.PermissionError)

	if not reason or not str(reason).strip():
		frappe.throw(_("Correction reason is required."))

	if target_doctype not in _AUDIT_LOG_TARGETS and target_doctype not in _MUTABLE_TARGETS:
		frappe.throw(_(
			"Invalid target_doctype {0}. Allowed: {1}."
		).format(
			target_doctype,
			", ".join(sorted(set(_AUDIT_LOG_TARGETS) | set(_MUTABLE_TARGETS))),
		))

	if not frappe.db.exists(target_doctype, target_name):
		frappe.throw(_(
			"{0} {1} does not exist."
		).format(target_doctype, target_name))

	# Capture the old value (if any) for the correction record.
	old_value: str | None = None
	if target_field:
		current = frappe.db.get_value(target_doctype, target_name, target_field)
		old_value = str(current) if current is not None else None

	# Audit-log path: log only, don't mutate.
	if target_doctype in _AUDIT_LOG_TARGETS:
		correction = _make_correction_row(
			target_doctype=target_doctype,
			target_name=target_name,
			target_field=target_field,
			old_value=old_value,
			new_value=str(new_value) if new_value is not None else None,
			reason=reason,
		)
		return {
			"status": "logged",
			"correction": correction.name,
			"target_doctype": target_doctype,
			"target_name": target_name,
		}

	# Mutable-target path: validate field args, mutate, log.
	if not target_field or new_value is None:
		frappe.throw(_(
			"target_field and new_value are required for corrections to {0}."
		).format(target_doctype))

	flag_attr = _MUTABLE_TARGETS[target_doctype]
	target_doc = frappe.get_doc(target_doctype, target_name)
	# Coerce new_value to the field's Python type before setting. The
	# endpoint receives new_value as a string over the wire (whitelisted
	# POST), but downstream validators expect numeric types where the field
	# is Currency / Float / Int / Check. Without this, e.g. CashDrop's
	# `_validate_declared_amount` does `self.declared_amount < 0` and hits
	# `TypeError: '<' not supported between instances of 'str' and 'int'`.
	target_doc.set(target_field, _coerce_field_value(target_doc, target_field, new_value))
	prior_flag = getattr(frappe.flags, flag_attr, False) if flag_attr else None
	try:
		if flag_attr:
			setattr(frappe.flags, flag_attr, True)
		target_doc.save(ignore_permissions=True)
	finally:
		if flag_attr:
			# Restore prior value (typically False/missing). We use setattr
			# to keep the attribute cleared rather than deleting; downstream
			# code reads via getattr(frappe.flags, "...", False) so either
			# works, but explicit reset is safer under exception paths.
			setattr(frappe.flags, flag_attr, prior_flag)

	correction = _make_correction_row(
		target_doctype=target_doctype,
		target_name=target_name,
		target_field=target_field,
		old_value=old_value,
		new_value=str(new_value),
		reason=reason,
	)
	return {
		"status": "applied",
		"correction": correction.name,
		"target_doctype": target_doctype,
		"target_name": target_name,
	}


def _make_correction_row(
	target_doctype: str,
	target_name: str,
	target_field: str | None,
	old_value: str | None,
	new_value: str | None,
	reason: str,
):
	"""Insert a Hamilton Board Correction row capturing the correction.

	Centralized so both the audit-log and mutable-target branches build
	the row identically. Operator and timestamp auto-set from the session;
	the correction row itself has track_changes=1 so any later edit to
	the row is also auditable.
	"""
	from frappe.utils import now_datetime

	doc = frappe.get_doc({
		"doctype": "Hamilton Board Correction",
		"target_doctype": target_doctype,
		"target_name": target_name,
		"target_field": target_field,
		"old_value": old_value,
		"new_value": new_value,
		"reason": reason,
		"operator": frappe.session.user,
		"timestamp": now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	return doc


# ---------------------------------------------------------------------------
# Retail cart — Sales Invoice creation (V9.1 Phase 2)
# ---------------------------------------------------------------------------


HAMILTON_POS_PROFILE = "Hamilton Front Desk"

# Roles authorized to record retail sales via the cart drawer.
#
# Hamilton Operator deliberately does NOT have direct Sales Invoice
# permissions in the role grid (DEC-005 / DEC-021 — POS Closing Entry is
# blocked from Operators because it shows expected cash totals; Sales Invoice
# direct-write would defeat the same blind-cash invariants and bypass the
# constrained cart UX). The cart wraps Sales Invoice creation in a tightly
# scoped surface (cash-only, fixed POS Profile, server-validated rates,
# server-validated stock) and the underlying writes run with
# ``ignore_permissions=True``. This is a pure delegation pattern, not
# "permission check + bypass" — the role gate at the function entry IS the
# authorization check; there is no second layer.
HAMILTON_RETAIL_SALE_ROLES = (
	"Hamilton Operator",
	"Hamilton Manager",
	"Hamilton Admin",
	"System Manager",
)

# Payment methods accepted by submit_retail_sale. V9.1 ships Cash; Card lands
# in Phase 2 next iteration (alongside the merchant-abstraction work — see
# docs/inbox.md 2026-04-30 hardware backlog). The tuple is the source of
# truth for both the entry-point validation and the rounding gate.
HAMILTON_PAYMENT_METHODS = ("Cash", "Card")


def _should_round_to_nickel(payment_method: str) -> bool:
	"""Return True if this payment method should round to the nearest 5¢.

	Per the Canadian penny-elimination rule (2013), cash transactions
	round to the nearest 5¢ and electronic transactions (debit, credit,
	cheque, e-transfer, gift card) settle to the cent. Tap-to-pay = card
	method per V9.1-D14, so it stays exact-cent too.

	Reference: Government of Canada Budget 2012 backgrounder; the precise
	rule is "totals ending in 1, 2 round down to 0; 3, 4 round up to 5;
	6, 7 round down to 5; 8, 9 round up to 10". Frappe's
	``round_based_on_smallest_currency_fraction`` produces the same
	results when ``smallest_currency_fraction_value = 0.05``.
	"""
	return payment_method == "Cash"


def _check_retail_sale_permission():
	"""Gate the retail-sale endpoint to Hamilton roles + System Manager.

	Administrator is implicitly allowed (Frappe convention — install hooks,
	bench scripts, and dev sessions all run as Administrator). Everyone else
	must hold at least one of HAMILTON_RETAIL_SALE_ROLES.
	"""
	user = frappe.session.user
	if user == "Administrator":
		return
	if not (set(frappe.get_roles(user)) & set(HAMILTON_RETAIL_SALE_ROLES)):
		frappe.throw(
			_("You do not have permission to record retail sales. "
			  "Required role: one of {0}").format(", ".join(HAMILTON_RETAIL_SALE_ROLES)),
			frappe.PermissionError,
		)


@frappe.whitelist(methods=["POST"])
def submit_retail_sale(
	items,
	cash_received,
	payment_method: str = "Cash",
	client_request_id: str | None = None,
) -> dict:
	"""Create + submit a POS Sales Invoice from the cart drawer.

	Called by ``_open_cash_payment_modal`` in asset_board.js when the
	operator confirms a cash payment. Creates a POS Sales Invoice with
	``is_pos=1, update_stock=1`` so submitting auto-creates the Stock
	Ledger Entry that decrements warehouse stock.

	Authorization model — delegated capability:
	  - Entry is gated by ``_check_retail_sale_permission``: caller must
	    hold a Hamilton role (or System Manager / Administrator).
	  - The Sales Invoice is created with ``ignore_permissions=True``
	    because Hamilton Operator does not have direct Sales Invoice
	    perms by design — direct write would bypass the constrained cart
	    UX and the blind-cash invariants. The cart IS the only legitimate
	    write surface; the role gate is the only authorization check.

	Server-side rate authority:
	  - Client-supplied ``unit_price`` is validated against
	    ``Item.standard_rate`` (within $0.01 tolerance for floating-point
	    noise). Mismatches are rejected to defeat client-side price
	    tampering. The rate written to the Sales Invoice is always the
	    server-side value, never the client's submission.

	Pre-submit stock guard:
	  - ``Bin.actual_qty`` is checked against the cart's aggregate
	    requested qty (per item) before insert. Produces clean operator
	    errors for the common "cart has more than stock" case. True
	    concurrent last-unit races (two cashiers selling the last item
	    simultaneously) still surface as raw ERPNext stock-ledger errors
	    on the second submit; Hamilton is single-operator most of the
	    time, so this gap is acceptable. A locked Bin row would be
	    over-engineering for the current operating model.

	Canadian penny-elimination rounding (2013):
	  - Cash sales round the post-tax grand_total to the nearest 5¢.
	    HST is computed first on the unrounded subtotal; the
	    rounding_adjustment posts as a separate GL entry to
	    ``Company.round_off_account`` (DEC-038 + Canadian nickel rule).
	  - Card / electronic sales settle to the exact cent
	    (``disable_rounded_total=1``). Tap-to-pay = Card per V9.1-D14.
	  - The gate is the ``payment_method`` argument; ``_should_round_to_nickel``
	    encapsulates the decision so the contract is testable in isolation.

	Arguments:
	  items: list of {item_code, qty, unit_price}. JSON-encoded by
	         frappe.xcall when sent from the client; accepts list or str.
	         ``unit_price`` must match ``Item.standard_rate``.
	  cash_received: numeric (Currency). Must be >= the rounded total
	         (which equals grand_total for Card, rounded-to-nickel for
	         Cash). Change is computed and returned.
	  payment_method: "Cash" (default) or "Card". V9.1 supports Cash;
	         Card lands in Phase 2 next iteration (merchant abstraction).
	         The parameter exists now so the rounding contract is stable.

	Returns:
	  {
	    sales_invoice: str,
	    grand_total: float,           # pre-rounding total (HST included)
	    rounded_total: float,         # what the customer pays
	    rounding_adjustment: float,   # rounded_total - grand_total
	    change: float,                # cash_received - rounded_total
	  }

	Raises:
	  - PermissionError if caller lacks any Hamilton role.
	  - ValidationError if cart empty, cash_received < amount due,
	    unknown item, rate mismatch, insufficient stock, unsupported
	    payment_method, or POS Profile / Walk-in customer missing.
	  - ValidationError ("Card payments are Phase 2 next iteration")
	    when payment_method="Card" — the gate is in place so the
	    rounding contract is stable, but the actual Card flow (merchant
	    integration) ships separately.
	"""
	_check_retail_sale_permission()

	# T0-1 idempotency fast path. Operator's network drops between server
	# commit and client response; their cart did not auto-clear so they
	# tap Confirm again. Same client_request_id (UUID generated at first
	# Confirm tap) → return the original Sales Invoice's payload without
	# creating a second SI / second cash payment line / second stock
	# decrement. The unique constraint on Cash Sale Idempotency closes the
	# narrow concurrent-retry race after this fast path.
	if client_request_id:
		# Variable named `idem_row` (not `cached*`) because the
		# test_all_redis_keys_use_hamilton_namespace lint matches any
		# variable containing "cache" or "redis" as a Redis API call —
		# this row is a MariaDB query result (Cash Sale Idempotency
		# DocType), not a Redis cache value.
		idem_row = frappe.db.get_value(
			"Cash Sale Idempotency",
			{"client_request_id": client_request_id},
			["sales_invoice", "response_payload"],
			as_dict=True,
		)
		if idem_row:
			# Return the original response payload verbatim if we stored
			# it on the original call. Reconstructing from the Sales
			# Invoice alone fails for `change` because ERPNext recomputes
			# `change_amount = paid_amount - amount_due` after submit, so
			# the SI has change_amount=0 even when the customer received
			# real change. Older records (pre-response_payload field)
			# fall back to the SI-reconstruction path.
			if idem_row.get("response_payload"):
				return json.loads(idem_row["response_payload"])
			return _build_retail_sale_response(idem_row["sales_invoice"], payment_method)

	if payment_method not in HAMILTON_PAYMENT_METHODS:
		frappe.throw(_(
			"Unsupported payment method: {0}. Supported: {1}"
		).format(payment_method, ", ".join(HAMILTON_PAYMENT_METHODS)))
	if payment_method == "Card":
		# Gate is in place (rounding will correctly disable for Card via
		# _should_round_to_nickel) but the end-to-end Card flow — merchant
		# adapter, terminal integration, merchant_transaction_id capture —
		# is Phase 2 next iteration. Throw clearly rather than create a
		# half-recorded Card invoice without the merchant linkage.
		frappe.throw(_(
			"Card payments are Phase 2 next iteration; not yet implemented. "
			"See docs/inbox.md 2026-04-30 hardware backlog."
		))

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
	# Audit Issue C: walk-in customer name is venue-configurable. Default
	# "Walk-in" matches Hamilton; Toronto / DC / Montreal can pin their own
	# label via ``bench set-config hamilton_walkin_customer "<name>"``.
	walkin_customer = frappe.conf.get("hamilton_walkin_customer") or "Walk-in"
	if not frappe.db.exists("Customer", walkin_customer):
		frappe.throw(_(
			"Walk-in customer {0} not seeded. Run `bench migrate` to populate."
		).format(walkin_customer))

	pos_profile = frappe.get_cached_doc("POS Profile", HAMILTON_POS_PROFILE)

	# Validate every cart line up front (existence, qty, server-side rate)
	# and aggregate quantities by item_code so the stock check sees the
	# true total per SKU. The JS cart guarantees one line per item, but
	# server-side aggregation is the right contract.
	qty_by_item: dict[str, float] = {}
	rate_by_item: dict[str, float] = {}
	for line in items:
		item_code = line.get("item_code")
		qty = flt(line.get("qty"))
		unit_price = flt(line.get("unit_price"))
		if not item_code or qty <= 0:
			frappe.throw(_("Invalid cart line: {0}").format(line))
		if not frappe.db.exists("Item", item_code):
			frappe.throw(_("Item {0} does not exist").format(item_code))
		# T1-1 per docs/inbox/2026-05-04_audit_synthesis_decisions.md:
		# admission items must NOT flow through the retail cart. The cart
		# UI hides admission items from the retail tabs (UI-layer guard),
		# but a curious operator opening /app/point-of-sale or a future
		# API caller could route an admission item here. Server-side
		# defense-in-depth: reject before any DB write.
		is_admission = frappe.db.get_value("Item", item_code, "hamilton_is_admission")
		if is_admission:
			frappe.throw(_(
				"Admission items cannot be sold via the retail cart. "
				"Item {0} is an admission item; use the admission flow."
			).format(item_code))
		# Server-side rate authority — fetch Item.standard_rate and reject
		# mismatches outside a $0.01 tolerance. The rate written to the
		# Sales Invoice (further down) uses ``rate_by_item``, NOT the
		# caller-supplied ``unit_price``.
		expected_rate = flt(frappe.db.get_value("Item", item_code, "standard_rate"))
		if abs(unit_price - expected_rate) > 0.01:
			frappe.throw(_(
				"Price mismatch for {0}: client sent ${1}, server price is ${2}"
			).format(item_code, f"{unit_price:.2f}", f"{expected_rate:.2f}"))
		qty_by_item[item_code] = qty_by_item.get(item_code, 0) + qty
		rate_by_item[item_code] = expected_rate

	# Pre-submit stock guard. Raw ERPNext stock-ledger errors are
	# operator-hostile (a multi-line stack trace inside a "Negative stock"
	# wrapper); this surfaces a clean, translatable message before insert.
	for item_code, total_qty in qty_by_item.items():
		bin_qty = flt(frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": pos_profile.warehouse},
			"actual_qty",
		) or 0)
		if bin_qty < total_qty:
			frappe.throw(_(
				"Insufficient stock for {0}: {1} requested, {2} available"
			).format(item_code, total_qty, bin_qty))

	# Delegated capability — see the docstring's authorization-model section.
	# Hamilton Operator does NOT have direct Sales Invoice or Customer perms,
	# so ERPNext's validation hooks (notably ``_get_party_details`` in
	# erpnext/accounts/party.py) need a permission elevation. The
	# ``frappe.flags.ignore_permissions=True`` flag alone is insufficient
	# because some ERPNext perm checks (specifically the doctype-level
	# access check inside ``has_permission``) bypass the flag. The reliable
	# pattern is to switch to Administrator for the duration of the write,
	# then restore. We override ``owner`` post-insert so the audit trail
	# still captures the real operator who recorded the sale.
	real_user = frappe.session.user
	original_ignore_perms = frappe.flags.get("ignore_permissions", False)
	frappe.set_user("Administrator")
	frappe.flags.ignore_permissions = True
	apply_rounding = _should_round_to_nickel(payment_method)
	try:
		si = frappe.new_doc("Sales Invoice")
		si.update({
			"company": pos_profile.company,
			"customer": walkin_customer,
			"is_pos": 1,
			"update_stock": 1,
			"pos_profile": HAMILTON_POS_PROFILE,
			"currency": pos_profile.currency,
			# Read the Price List from the POS Profile — seed sets this to
			# "Hamilton Standard Selling" via ``_ensure_pos_profile``. No
			# string-literal fallback to "Standard Selling" because that
			# name collides with ERPNext's own test-fixture Price List
			# (which uses INR currency and conflicts with our CAD).
			"selling_price_list": pos_profile.selling_price_list,
			# Canadian penny-elimination rule: Cash sales round the
			# post-tax total to the nearest 5¢; Card / electronic sales
			# settle to the exact cent. The Currency-level setting
			# (CAD.smallest_currency_fraction_value=0.05) is the global
			# default; this per-invoice flag is the payment-method gate
			# that overrides for non-cash payments.
			"disable_rounded_total": 0 if apply_rounding else 1,
		})
		if pos_profile.taxes_and_charges:
			si.taxes_and_charges = pos_profile.taxes_and_charges

		# One Sales Invoice line per cart entry. Rate is always the
		# server-side value from rate_by_item, never the caller-supplied
		# unit_price.
		for line in items:
			item_code = line["item_code"]
			si.append("items", {
				"item_code": item_code,
				"qty": flt(line["qty"]),
				"rate": rate_by_item[item_code],
				"warehouse": pos_profile.warehouse,
				"cost_center": pos_profile.cost_center,
			})

		# Audit Issue A: ``si.set_taxes_and_charges()`` is a no-op for
		# is_pos=1 invoices in v16 (early-exits at the `is_pos` check
		# in accounts_controller.py). The actual tax-row population
		# happens inside ``set_missing_values`` → ``set_pos_fields``,
		# which copies taxes_and_charges + the rows from the POS Profile
		# onto the SI. The previous explicit call was misleading code,
		# not broken — tests pass at 13% HST because of the POS path.
		si.set_missing_values()
		si.calculate_taxes_and_totals()
		grand_total = flt(si.grand_total)
		# When rounding is enabled, ERPNext populates rounded_total with
		# the nickel-rounded value; when disabled, rounded_total is 0 and
		# the grand_total is the amount due. ``amount_due`` is what the
		# customer actually pays — this is what cash math + payment line
		# must use, otherwise outstanding_amount drifts by the rounding
		# delta.
		amount_due = flt(si.rounded_total) if (apply_rounding and si.rounded_total) else grand_total
		rounding_adjustment = flt(si.rounding_adjustment) if apply_rounding else 0.0

		if cash_received < amount_due:
			frappe.throw(_(
				"Cash received {0} is less than amount due {1}"
			).format(cash_received, amount_due))

		change = flt(cash_received - amount_due)
		si.append("payments", {
			"mode_of_payment": payment_method,
			"amount": amount_due,  # rounded total for Cash, exact grand_total for Card
		})
		si.change_amount = change
		si.base_change_amount = change
		si.paid_amount = amount_due
		si.base_paid_amount = amount_due

		# Audit-trail note: the operator who actually made the sale is
		# captured in ``remarks`` (visible in the SI form / list) so a
		# manager reviewing a sale can identify the responsible operator
		# even though the SI's ``owner`` is the elevated user.
		if real_user and real_user != "Administrator":
			si.remarks = (si.remarks or "") + f"\nRecorded via cart by {real_user}"

		si.flags.ignore_permissions = True
		si.insert(ignore_permissions=True)
		# Override ``owner`` so the audit trail captures the actual operator,
		# not the elevated Administrator session. ``db_set`` with
		# update_modified=False keeps modified/modified_by intact at the
		# elevated user (which is fine — the modification IS being done by
		# the system on behalf of the operator).
		if real_user and real_user != "Administrator":
			si.db_set("owner", real_user, update_modified=False)
		si.submit()

		response = {
			"sales_invoice": si.name,
			"grand_total": grand_total,
			"rounded_total": amount_due,
			"rounding_adjustment": rounding_adjustment,
			"change": change,
		}

		# T0-1 idempotency record. The unique constraint on
		# `client_request_id` is the durable enforcement: two concurrent
		# requests that both passed the fast-path exists() check race here,
		# and the loser's insert raises UniqueValidationError. Throwing
		# rolls back the loser's SI submission; the operator retries with
		# the same token and the fast path returns the winner's payload.
		#
		# response_payload stashes the verbatim response so retries return
		# byte-identical values for `change`. Reconstructing change from
		# the SI alone fails because ERPNext recomputes change_amount
		# after submit (paid_amount == amount_due → change_amount = 0).
		if client_request_id:
			frappe.get_doc({
				"doctype": "Cash Sale Idempotency",
				"client_request_id": client_request_id,
				"sales_invoice": si.name,
				"response_payload": json.dumps(response),
			}).insert(ignore_permissions=True)

		return response
	finally:
		frappe.flags.ignore_permissions = original_ignore_perms
		frappe.set_user(real_user)


def _build_retail_sale_response(sales_invoice: str, payment_method: str) -> dict:
	# Reconstruct the submit_retail_sale response payload from a
	# previously-submitted Sales Invoice. Used by the T0-1 idempotency
	# fast path so a retried request returns the same shape as the original.
	si = frappe.get_doc("Sales Invoice", sales_invoice)
	apply_rounding = _should_round_to_nickel(payment_method)
	grand_total = flt(si.grand_total)
	amount_due = (
		flt(si.rounded_total)
		if (apply_rounding and si.rounded_total)
		else grand_total
	)
	rounding_adjustment = flt(si.rounding_adjustment) if apply_rounding else 0.0
	change = flt(si.change_amount)
	return {
		"sales_invoice": si.name,
		"grand_total": grand_total,
		"rounded_total": amount_due,
		"rounding_adjustment": rounding_adjustment,
		"change": change,
	}


def purge_old_idempotency_records():
	"""Daily scheduler job — delete Cash Sale Idempotency records older than 24h.

	The retention window must outlive the operational network-retry window
	(seconds to minutes) but stays short to keep the table small. 24h is
	the same window operators reconcile their shift in, so any retry that
	is still relevant to a same-shift operator falls inside it.

	Wraps in a try/except + Error Log per the Tier-1 audit requirement that
	scheduled jobs surface failures rather than silently logging "Success".
	"""
	from frappe.utils import add_to_date

	try:
		cutoff = add_to_date(now_datetime(), hours=-24)
		frappe.db.delete("Cash Sale Idempotency", {"created_at": ["<", cutoff]})
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			title="purge_old_idempotency_records failed",
			message=frappe.get_traceback(),
		)
		raise


# ---------------------------------------------------------------------------
# Shift Management (DEC-099) — operator-facing start/end shift from Asset Board
# ---------------------------------------------------------------------------
# These endpoints let any Hamilton Operator open and close their shift
# without touching Frappe Desk. Gating rule: when no Open Shift Record
# exists for `frappe.session.user`, the Asset Board renders a Start Shift
# landing screen instead of the asset grid (asset_board.js).
#
# Float prompt default — comes from Hamilton Settings.float_amount so the
# venue's standard float is one tap to confirm. Operator can override at
# the prompt for unusual openings (e.g. partial-shift handover).


def _get_open_shift_for_user(user: str | None = None) -> dict | None:
	"""Return the open Shift Record (status=Open) for `user`, or None.

	`user` defaults to `frappe.session.user`. Returns a dict with
	`name`, `shift_date`, `shift_start`, `float_expected` so the JS
	can render the operator's session header without an extra round trip.
	"""
	user = user or frappe.session.user
	rows = frappe.get_all(
		"Shift Record",
		filters={"operator": user, "status": "Open"},
		fields=["name", "shift_date", "shift_start", "float_expected"],
		order_by="shift_start desc",
		limit=1,
	)
	return rows[0] if rows else None


@frappe.whitelist(methods=["GET"])
def get_current_shift() -> dict:
	"""Return the current operator's Open Shift Record, or {} if none.

	Used by the Asset Board on load to decide between the Start Shift
	landing screen and the normal asset grid. Read permission on Shift
	Record is the gate (Hamilton Operator has it via the seeded role).
	"""
	frappe.has_permission("Shift Record", "read", throw=True)
	shift = _get_open_shift_for_user()
	return {"shift": shift or None}


@frappe.whitelist(methods=["POST"])
def start_shift(float_expected: float | str | None = None) -> dict:
	"""Open a new Shift Record for the current operator.

	Refuses if the operator already has an Open Shift Record (one open
	shift per operator at a time — closes the silent-double-open trap).

	`float_expected` is required so the operator explicitly confirms the
	cash they're starting with. The Asset Board defaults the prompt to
	`Hamilton Settings.float_amount` but operators can override.
	"""
	frappe.has_permission("Shift Record", "create", throw=True)

	existing = _get_open_shift_for_user()
	if existing:
		frappe.throw(
			_("You already have an open shift ({0}). End it before starting a new one.").format(
				existing["name"]
			)
		)

	if float_expected is None or str(float_expected).strip() == "":
		frappe.throw(_("Float expected is required to start a shift."))

	float_value = flt(float_expected)
	if float_value < 0:
		frappe.throw(_("Float expected cannot be negative."))

	now = now_datetime()
	doc = frappe.get_doc({
		"doctype": "Shift Record",
		"operator": frappe.session.user,
		"shift_date": now.date(),
		"status": "Open",
		"shift_start": now,
		"float_expected": float_value,
	})
	doc.insert()
	return {
		"shift": {
			"name": doc.name,
			"shift_date": str(doc.shift_date),
			"shift_start": str(doc.shift_start),
			"float_expected": float(doc.float_expected or 0),
		}
	}


@frappe.whitelist(methods=["POST"])
def end_shift(shift_name: str | None = None) -> dict:
	"""Close the current operator's Open Shift Record.

	The Asset Board End Shift flow runs the final cash drop FIRST and
	shows the shift summary; once the operator acknowledges, the JS
	calls this endpoint to flip the Shift Record to Closed.

	If `shift_name` is supplied it must match the operator's open shift
	(defense against a stale tab calling end_shift on a different open
	shift the same user opened in another tab). If omitted, the
	operator's currently-open shift is used.
	"""
	frappe.has_permission("Shift Record", "write", throw=True)

	shift = _get_open_shift_for_user()
	if not shift:
		frappe.throw(_("No open shift found for {0}.").format(frappe.session.user))
	if shift_name and shift_name != shift["name"]:
		frappe.throw(
			_("Open shift mismatch: requested {0}, but current open shift is {1}.").format(
				shift_name, shift["name"]
			)
		)

	doc = frappe.get_doc("Shift Record", shift["name"])
	doc.status = "Closed"
	doc.shift_end = now_datetime()
	doc.save()
	return {"shift": doc.name, "status": "Closed"}


@frappe.whitelist(methods=["GET"])
def get_shift_summary() -> dict:
	"""Compute the End-Shift summary the operator must acknowledge (DEC-102).

	Returns counts and totals for the current operator's day so the
	Asset Board can render the acknowledgement modal before closing
	the shift. Filters scoped to `frappe.session.user` and today's date.

	Shape:
	  {
	    "sessions_started_today": int,
	    "sessions_open_now": int,
	    "open_sessions": [{name, asset_code, session_start}],
	    "cash_sales_total": float,
	    "cash_drops_count": int,
	    "cash_drops_total": float,
	  }
	"""
	frappe.has_permission("Shift Record", "read", throw=True)
	user = frappe.session.user
	today = now_datetime().date()

	sessions_started = frappe.db.count(
		"Venue Session",
		filters={"operator_checkin": user, "session_start": [">=", today]},
	)
	open_sessions_rows = frappe.get_all(
		"Venue Session",
		filters={"status": "Occupied"},
		fields=["name", "venue_asset", "session_start"],
		order_by="session_start asc",
	)
	asset_codes: dict[str, str] = {}
	if open_sessions_rows:
		asset_names = [r["venue_asset"] for r in open_sessions_rows if r.get("venue_asset")]
		if asset_names:
			for row in frappe.get_all(
				"Venue Asset",
				filters={"name": ["in", asset_names]},
				fields=["name", "asset_code"],
			):
				asset_codes[row["name"]] = row["asset_code"]
	open_sessions = [
		{
			"name": r["name"],
			"asset_code": asset_codes.get(r["venue_asset"]) or r["venue_asset"],
			"session_start": str(r["session_start"]) if r.get("session_start") else None,
		}
		for r in open_sessions_rows
	]

	cash_sales_total = (
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(grand_total), 0)
			FROM `tabSales Invoice`
			WHERE is_pos = 1
			  AND posting_date = %s
			  AND owner = %s
			  AND docstatus = 1
			""",
			(today, user),
		)[0][0]
		or 0
	)

	drop_rows = frappe.get_all(
		"Cash Drop",
		filters={"operator": user, "shift_date": today},
		fields=["name", "declared_amount"],
	)
	cash_drops_total = sum(float(r.get("declared_amount") or 0) for r in drop_rows)

	return {
		"sessions_started_today": int(sessions_started or 0),
		"sessions_open_now": len(open_sessions),
		"open_sessions": open_sessions,
		"cash_sales_total": float(cash_sales_total),
		"cash_drops_count": len(drop_rows),
		"cash_drops_total": float(cash_drops_total),
	}
