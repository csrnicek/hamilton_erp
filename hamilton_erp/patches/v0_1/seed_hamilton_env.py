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


def _ensure_walkin_customer():
	"""Create the 'Walk-in' Customer used by every anonymous session."""
	if frappe.db.exists("Customer", "Walk-in"):
		return
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": "Walk-in",
		"customer_group": frappe.db.get_value(
			"Customer Group", {"is_group": 0}, "name"
		) or "All Customer Groups",
		"territory": frappe.db.get_value(
			"Territory", {"is_group": 0}, "name"
		) or "All Territories",
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
