"""Phase 1 seed migration — creates 59 Venue Assets, Walk-in Customer,
and the Hamilton Settings singleton on any fresh install.

DEC-054 §1 (asset counts) + DEC-055 §1 (Walk-in) + DEC-055 §3 (settings).

Idempotent: each seed is guarded per-row (per asset_code for Venue
Assets, per-name for Walk-in Customer, per-field for Hamilton Settings),
so re-running is safe even over partial seed state.
Registered in patches.txt under [post_model_sync].
"""
import frappe


def execute():
	_ensure_walkin_customer()
	_ensure_hamilton_settings()
	_ensure_venue_assets()
	_ensure_retail_items()


# V9.1 retail amendment seed (Item Group + sample Items + initial stock).
# Idempotent — safe to re-run. See docs/design/V9.1_RETAIL_AMENDMENT.md.
HAMILTON_RETAIL_ITEM_GROUP = "Drink/Food"

# Each entry pairs the SKU with its QBO-mirrored income account (per
# Amendment 2026-04-30 (b)). Beverages → 4260 Beverage; food → 4210 Food.
HAMILTON_RETAIL_ITEMS = [
	{"item_code": "WAT-500", "item_name": "Water 500ml",       "rate": 3.50, "income_account_base": "4260 Beverage"},
	{"item_code": "GAT-500", "item_name": "Sports Drink 500ml","rate": 5.00, "income_account_base": "4260 Beverage"},
	{"item_code": "BAR-PROT","item_name": "Protein Bar",       "rate": 4.00, "income_account_base": "4210 Food"},
	{"item_code": "BAR-ENRG","item_name": "Energy Bar",        "rate": 4.50, "income_account_base": "4210 Food"},
]
HAMILTON_RETAIL_INITIAL_STOCK_QTY = 24


def _ensure_retail_items():
	"""Seed Hamilton's V9.1 retail catalogue: 1 Item Group + 4 sample Items.

	Inventory (initial stock count) is NOT seeded by this patch — Stock
	Entries are venue-specific data that belongs in the venue's own stocking
	flow, not in committed code. Hamilton's stocking is done manually via
	`bench --site … console` after first install (or via the Frappe Cloud
	Desk UI). The amendment doc lists the verification step.

	Item Defaults wiring (added 2026-04-30) maps each SKU to its income
	account, the Hamilton warehouse, and the Hamilton cost center. This
	depends on ``hamilton_erp.setup.install._ensure_hamilton_accounting``
	having run first (it does — install.py orders the seeds correctly).
	"""
	# Item Group
	if not frappe.db.exists("Item Group", HAMILTON_RETAIL_ITEM_GROUP):
		parent = frappe.db.get_value(
			"Item Group", {"is_group": 1, "name": "All Item Groups"}, "name",
		) or "All Item Groups"
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": HAMILTON_RETAIL_ITEM_GROUP,
			"parent_item_group": parent,
			"is_group": 0,
		}).insert(ignore_permissions=True)

	# Items
	for spec in HAMILTON_RETAIL_ITEMS:
		if not frappe.db.exists("Item", spec["item_code"]):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": spec["item_code"],
				"item_name": spec["item_name"],
				"item_group": HAMILTON_RETAIL_ITEM_GROUP,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"include_item_in_manufacturing": 0,
				"standard_rate": spec["rate"],
			}).insert(ignore_permissions=True)

	_ensure_retail_item_defaults()


def _ensure_retail_item_defaults():
	"""Wire Item Defaults rows for the seeded retail items.

	One row per (item, company) — sets default_warehouse, income_account,
	and selling_cost_center to Hamilton's QBO-mirrored values. Idempotent:
	updates the existing row if present, appends a new one if absent.

	Skips silently when prerequisites (Hamilton company, warehouse, cost
	center, income accounts) aren't seeded yet — the install order makes
	that case impossible in fresh installs, but on partial migrate state
	we'd rather no-op than crash.
	"""
	from hamilton_erp.setup.install import (
		HAMILTON_WAREHOUSE_BASE,
		HAMILTON_COST_CENTER_BASE,
	)

	# Detect Hamilton company using the same pin → name → default flow as
	# the install seed. We can't import the full helper (circular import on
	# fresh install), but the list of candidates is short.
	company = frappe.conf.get("hamilton_company")
	if not company or not frappe.db.exists("Company", company):
		for candidate in ("Club Hamilton", "Hamilton", "Hamilton Club"):
			if frappe.db.exists("Company", candidate):
				company = candidate
				break
	if not company:
		matches = frappe.get_all(
			"Company",
			filters={"company_name": ["like", "%Hamilton%"]},
			fields=["name"],
			limit=1,
		)
		if matches:
			company = matches[0]["name"]
	if not company:
		# No Hamilton company exists — the accounting seed didn't run.
		# Skip silently; production-pin or fresh install will populate later.
		return

	abbr = frappe.db.get_value("Company", company, "abbr")
	warehouse   = f"{HAMILTON_WAREHOUSE_BASE} - {abbr}"
	cost_center = f"{HAMILTON_COST_CENTER_BASE} - {abbr}"
	if not frappe.db.exists("Warehouse", warehouse):
		return
	if not frappe.db.exists("Cost Center", cost_center):
		return

	for spec in HAMILTON_RETAIL_ITEMS:
		if not frappe.db.exists("Item", spec["item_code"]):
			continue
		income_account = f"{spec['income_account_base']} - {abbr}"
		if not frappe.db.exists("Account", income_account):
			# Income account missing — operator will configure later.
			continue
		item = frappe.get_doc("Item", spec["item_code"])
		existing = next(
			(d for d in item.item_defaults if d.company == company), None,
		)
		target = {
			"company": company,
			"default_warehouse": warehouse,
			"income_account": income_account,
			"selling_cost_center": cost_center,
			"buying_cost_center": cost_center,
		}
		if existing:
			changed = False
			for field, value in target.items():
				if existing.get(field) != value:
					existing.set(field, value)
					changed = True
			if changed:
				item.save(ignore_permissions=True)
		else:
			item.append("item_defaults", target)
			item.save(ignore_permissions=True)


def _ensure_walkin_customer():
	"""Create the anonymous-session Customer (default name "Walk-in").

	Audit Issue C: the customer name is read from
	``frappe.conf.get("hamilton_walkin_customer")`` so a future venue
	(Toronto, DC, Montreal) can pin its own preferred label via
	``bench --site SITE set-config hamilton_walkin_customer "<name>"``.
	Default remains "Walk-in" for Hamilton and any unconfigured site.

	Audit Issue D: Customer Group and Territory are pinned to the named
	defaults that ``_ensure_erpnext_prereqs`` creates ("Individual" /
	"Default") so the customer ends up in the same group/territory across
	every install — non-deterministic ``frappe.db.get_value({"is_group": 0})``
	queries previously picked "any" non-group record, which varied by
	install order on non-greenfield sites.
	"""
	customer_name = frappe.conf.get("hamilton_walkin_customer") or "Walk-in"
	if frappe.db.exists("Customer", customer_name):
		return
	customer_group = (
		"Individual"
		if frappe.db.exists("Customer Group", "Individual")
		else "All Customer Groups"
	)
	territory = (
		"Default"
		if frappe.db.exists("Territory", "Default")
		else "All Territories"
	)
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": customer_name,
		"customer_group": customer_group,
		"territory": territory,
	}).insert(ignore_permissions=True)


def _ensure_hamilton_settings():
	"""Populate Hamilton Settings singleton with defaults if unset.

	Only writes fields that are currently falsy — operators who tuned the
	settings manually are preserved.
	"""
	settings = frappe.get_single("Hamilton Settings")
	changed = False
	defaults = {
		"float_amount": 300,
		"default_stay_duration_minutes": 360,
		"grace_minutes": 15,
		"assignment_timeout_minutes": 15,
	}
	for field, value in defaults.items():
		if not settings.get(field):
			settings.set(field, value)
			changed = True
	if changed:
		settings.save(ignore_permissions=True)


def _ensure_venue_assets():
	"""Seed the 59 physical assets (26 rooms + 33 lockers).

	Order per Q6:
	  R001-R011 Single Standard  (11)
	  R012-R021 Deluxe Single    (10)
	  R022-R023 GH Room          (2)
	  R024-R026 Double Deluxe    (3)
	  L001-L033 Lockers          (33)

	Idempotent guard (Task 11 code review, I2): per-asset `exists()` check
	inside the loop. The previous binary guard
	(`if frappe.db.count("Venue Asset") > 0: return`) was unsafe — a crash
	mid-seed would leave a permanently half-seeded DB with no recovery path
	via `bench migrate`, and any Venue Asset fixture from another test
	class would silently no-op this patch's `execute()` call. Skipping
	per asset_code makes this safe to call over partial seed state.
	"""
	company = frappe.defaults.get_global_default("company")
	if not company:
		frappe.logger().warning(
			"seed_hamilton_env: no default company set — "
			"Venue Assets will be created with company=None"
		)

	# Each row: (code_prefix, count, category, tier, name_prefix,
	#            code_start, display_start)
	plan = (
		("R", 11, "Room",   "Single Standard", "Sing STD",  1,  1),
		("R", 10, "Room",   "Deluxe Single",   "Sing DLX", 12, 12),
		("R",  2, "Room",   "GH Room",         "GH",       22, 22),
		("R",  3, "Room",   "Double Deluxe",   "Dbl DLX",  24, 24),
		("L", 33, "Locker", "Locker",          "Lckr",      1, 27),
	)
	for code_prefix, count, category, tier, name_prefix, code_start, display_start in plan:
		for i in range(count):
			asset_code = f"{code_prefix}{code_start + i:03d}"
			if frappe.db.exists("Venue Asset", {"asset_code": asset_code}):
				continue
			asset_name = f"{name_prefix} {i + 1}"
			frappe.get_doc({
				"doctype": "Venue Asset",
				"asset_code": asset_code,
				"asset_name": asset_name,
				"asset_category": category,
				"asset_tier": tier,
				"status": "Available",
				"is_active": 1,
				"expected_stay_duration": 360,
				"display_order": display_start + i,
				"company": company,
				"version": 0,
			}).insert(ignore_permissions=True)
