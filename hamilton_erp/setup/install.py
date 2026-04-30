"""Install and migrate hooks for the Hamilton ERP app."""

import frappe
from frappe import _


def after_install():
	"""Create default roles, ERPNext prereqs, and initial seed data after install.

	Frappe v16's ``install_app()`` calls ``set_all_patches_as_completed()`` which
	marks patches.txt entries as done WITHOUT running them. So any "initial data
	seeding" (Walk-in Customer, Hamilton Settings defaults, 59 Venue Assets, ERPNext
	root records) must happen here, not in ``patches/v0_1/`` — patches only run on
	subsequent ``bench migrate`` calls, never during the initial ``bench install-app``.

	Order matters:
	  1. ``_ensure_erpnext_prereqs`` — root records (Customer Group, Territory,
	     Item Group, UOM) needed by Walk-in Customer and retail Items.
	  2. ``_ensure_hamilton_accounting`` — Company + Standard CoA + Hamilton
	     accounts (HST, 4260 Beverage, 4210 Food) + Warehouse + Cost Center +
	     Sales Taxes Template + Mode of Payment Account. Required BEFORE
	     ``_seed_hamilton_data`` so the retail Items created in
	     ``seed_hamilton_env._ensure_retail_items`` can wire Item Defaults to
	     the Hamilton accounts in the same pass.
	  3. ``_seed_hamilton_data`` — Walk-in Customer, Hamilton Settings, 59
	     Venue Assets, retail Items + Item Defaults.
	  4. ``_ensure_pos_profile`` — POS Profile "Hamilton Front Desk" depends on
	     warehouse + cost center + tax template + Mode of Payment "Cash" all
	     existing, so it runs after the accounting seed.

	``_ensure_no_setup_wizard_loop`` runs LAST so the desk lands in a usable
	state immediately after ``bench install-app`` — without depending on a
	follow-up ``bench migrate`` to fire the after_migrate hook.
	"""
	_ensure_erpnext_prereqs()
	_ensure_hamilton_accounting()
	_seed_hamilton_data()
	_ensure_pos_profile()
	_create_roles()
	_set_role_permissions()
	_ensure_audit_trail_enabled()
	_ensure_no_setup_wizard_loop()
	frappe.db.commit()


def _ensure_audit_trail_enabled():
	"""Task 25 permissions checklist item 4: enable Audit Trail.

	System Settings has an `enable_audit_trail` field in v15+ that gates
	Frappe's tamper-evident audit log of every doc change. Enabling it on
	install means every Hamilton DocType change after handoff is traceable
	without retro-fitting. Idempotent — only writes if currently 0.

	If the field doesn't exist on this Frappe build (older minor, rename,
	or stripped-down distribution), this is a no-op — checked via the
	DocType meta before any read/write so we never raise on missing fields.
	"""
	meta = frappe.get_meta("System Settings")
	if not meta.has_field("enable_audit_trail"):
		frappe.logger().info(
			"hamilton_erp: System Settings.enable_audit_trail not present; "
			"skipping audit-trail enable (Frappe version variance)."
		)
		return
	current = frappe.db.get_single_value("System Settings", "enable_audit_trail")
	if int(current or 0) == 1:
		return  # already on
	frappe.db.set_single_value("System Settings", "enable_audit_trail", 1)
	frappe.logger().info("hamilton_erp: enabled Audit Trail in System Settings")


def _ensure_no_setup_wizard_loop():
	"""Heal the setup-wizard flash-loop state on a fresh ERPNext install.

	Two things conspire to send users into a setup-wizard redirect loop on
	fresh ERPNext sites:
	  1. ``tabDefaultValue`` has ``parent='__default'``,
	     ``defkey='desktop:home_page'``, ``defvalue='setup-wizard'`` — added
	     by ERPNext's first-run defaults.
	  2. ``Installed Application.is_setup_complete=0`` — flipped to 1 only
	     when the wizard runs, which we don't run unattended.

	Heal both. Called from BOTH ``after_install`` (so fresh ``bench
	install-app`` deploys land usable without a follow-up ``bench migrate``)
	AND ``after_migrate`` (via ``ensure_setup_complete`` — so existing sites
	re-heal on every migrate too).

	Idempotent: ``frappe.db.delete`` is a no-op when no row matches;
	``frappe.db.set_value`` only fires for rows where ``is_setup_complete=0``.
	"""
	# Narrow filter — only the setup-wizard pin, not other home_page configs.
	frappe.db.delete("DefaultValue", {
		"parent": "__default",
		"defkey": "desktop:home_page",
		"defvalue": "setup-wizard",
	})

	# Heal is_setup_complete on every Installed Application row that's still 0.
	# Frappe's is_setup_complete() reads the rows for app_name in
	# ("frappe", "erpnext"); healing more rows than that is harmless and
	# forward-compatible for any future app whose install marks itself complete.
	for ia in frappe.get_all(
		"Installed Application",
		filters={"is_setup_complete": 0},
		fields=["name"],
	):
		frappe.db.set_value(
			"Installed Application", ia.name, "is_setup_complete", 1
		)


def _ensure_erpnext_prereqs():
	"""Create ERPNext root records that fresh ERPNext installs don't auto-create
	when setup-wizard hasn't been run.

	Required for hamilton_erp's ``seed_hamilton_env._ensure_walkin_customer`` to
	succeed on fresh installs. Standard ERPNext deploys complete the setup
	wizard, which creates these records as a side effect of company creation.
	Unattended deploys (CI, automated provisioning, fresh Frappe Cloud sites)
	skip the wizard, so we ensure them ourselves.

	Idempotent — uses ``frappe.db.exists()`` guards. Safe to re-run.
	"""
	if not frappe.db.exists("Customer Group", "All Customer Groups"):
		frappe.get_doc({
			"doctype": "Customer Group",
			"customer_group_name": "All Customer Groups",
			"is_group": 1,
		}).insert(ignore_permissions=True)
		frappe.logger().info("hamilton_erp: created Customer Group 'All Customer Groups' (root)")
	if not frappe.db.exists("Customer Group", "Individual"):
		frappe.get_doc({
			"doctype": "Customer Group",
			"customer_group_name": "Individual",
			"parent_customer_group": "All Customer Groups",
			"is_group": 0,
		}).insert(ignore_permissions=True)
		frappe.logger().info("hamilton_erp: created Customer Group 'Individual'")
	if not frappe.db.exists("Territory", "All Territories"):
		frappe.get_doc({
			"doctype": "Territory",
			"territory_name": "All Territories",
			"is_group": 1,
		}).insert(ignore_permissions=True)
		frappe.logger().info("hamilton_erp: created Territory 'All Territories' (root)")
	if not frappe.db.exists("Territory", "Default"):
		frappe.get_doc({
			"doctype": "Territory",
			"territory_name": "Default",
			"parent_territory": "All Territories",
			"is_group": 0,
		}).insert(ignore_permissions=True)
		frappe.logger().info("hamilton_erp: created Territory 'Default'")
	# V9.1 retail amendment — Item Group root + UOM needed by
	# `seed_hamilton_env._ensure_retail_items` for the Drink/Food child
	# group and the sample Items' stock_uom. Standard ERPNext
	# setup_complete creates these; CI's unattended install does not.
	if not frappe.db.exists("Item Group", "All Item Groups"):
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": "All Item Groups",
			"is_group": 1,
		}).insert(ignore_permissions=True)
		frappe.logger().info("hamilton_erp: created Item Group 'All Item Groups' (root)")
	if not frappe.db.exists("UOM", "Nos"):
		frappe.get_doc({
			"doctype": "UOM",
			"uom_name": "Nos",
			"must_be_whole_number": 1,
		}).insert(ignore_permissions=True)
		frappe.logger().info("hamilton_erp: created UOM 'Nos'")


def _seed_hamilton_data():
	"""Run the Hamilton-specific data seed (Walk-in Customer, Hamilton Settings
	defaults, 59 Venue Assets) defined in ``patches/v0_1/seed_hamilton_env``.

	The same seed is registered in patches.txt under ``[post_model_sync]`` for
	``bench migrate`` runs. Calling it from ``after_install`` covers fresh
	installs where patches.txt entries are auto-marked-complete by Frappe and
	never actually run. The seed is idempotent so the dual-invocation is safe.
	"""
	from hamilton_erp.patches.v0_1 import seed_hamilton_env
	seed_hamilton_env.execute()


def ensure_setup_complete():
	"""after_migrate hook — heal is_setup_complete for frappe + erpnext.

	Frappe's ``frappe.is_setup_complete()`` reads from
	``tabInstalled Application.is_setup_complete`` for rows where
	``app_name in ("frappe", "erpnext")``. On a single-admin dev site,
	``InstalledApplications.update_versions()`` (called from bench migrate)
	cannot auto-heal a 0 value because its auto-heal paths require a
	non-Administrator System User (``has_non_admin_user()``) which dev
	sites typically lack.

	This hook forces both rows to 1 on every bench migrate. It is safe
	on production because:
	  - On prod, setup completed long ago → both values are already 1,
	    so this is a no-op.
	  - Even if a prod site somehow had 0, forcing 1 is the correct
	    state (prod has a real company and real users).
	  - It only touches the two rows that gate the setup_wizard redirect;
	    it does NOT modify User, Company, or other site data.

	Registered as ``after_migrate`` in hooks.py. Idempotent.
	"""
	# Heal both the desktop:home_page='setup-wizard' DefaultValue row AND
	# every Installed Application.is_setup_complete=0. Logic lives in
	# _ensure_no_setup_wizard_loop() so after_install (fresh deploys) and
	# after_migrate (this hook) share the same code path. Idempotent.
	_ensure_no_setup_wizard_loop()

	# Sync System Settings.setup_complete so anything reading it
	# (error log UI, some older Frappe helpers) also sees True.
	frappe.db.set_single_value(
		"System Settings", "setup_complete", frappe.is_setup_complete()
	)

	frappe.db.commit()
	frappe.clear_cache(doctype="Installed Application")
	frappe.clear_cache(doctype="System Settings")


def _create_roles():
	"""Create Hamilton-specific roles and grant Administrator the Operator role.

	Administrator needs ``Hamilton Operator`` to access the Asset Board page
	and the whitelisted ``hamilton_erp.api`` endpoints. Frappe grants
	Administrator implicit "all permissions" but role-based UI checks
	(asset-board route, page permissions) test ``frappe.has_permission`` which
	is role-driven. ``test_environment_health.test_administrator_has_hamilton_operator_role``
	pins this contract; ``restore_dev_state()`` re-applies it after destructive
	tests. This installs it once at app-install time so fresh deploys (CI,
	new Frappe Cloud sites) start in the same state without manual setup.
	"""
	for role_name in ("Hamilton Operator", "Hamilton Manager", "Hamilton Admin"):
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
				}
			).insert(ignore_permissions=True)

	# Assign Hamilton Operator to Administrator. Idempotent.
	if frappe.db.exists("User", "Administrator") and frappe.db.exists("Role", "Hamilton Operator"):
		admin = frappe.get_doc("User", "Administrator")
		existing_roles = {r.role for r in admin.roles}
		if "Hamilton Operator" not in existing_roles:
			admin.append("roles", {"role": "Hamilton Operator"})
			admin.save(ignore_permissions=True)
			frappe.logger().info("hamilton_erp: assigned Hamilton Operator role to Administrator")


def _set_role_permissions():
	"""Configure role permissions on standard DocTypes.

	Custom DocType permissions are defined in their respective JSON files
	and synced automatically on bench migrate.  This function only handles
	standard DocTypes where Custom DocPerm is the correct mechanism.
	"""
	_block_pos_closing_for_operator()


def _block_pos_closing_for_operator():
	"""Remove Hamilton Operator access to the standard POS Closing Entry.

	Operators use the custom Cash Drop screen instead.  The standard POS
	Closing Entry must not be accessible to them because it shows expected
	cash totals, violating the blind cash control model (DEC-005).
	"""
	existing = frappe.db.exists(
		"Custom DocPerm",
		{"parent": "POS Closing Entry", "role": "Hamilton Operator"},
	)
	if existing:
		frappe.db.delete("Custom DocPerm", {"parent": "POS Closing Entry", "role": "Hamilton Operator"})


# ---------------------------------------------------------------------------
# Hamilton accounting seed (V9.1 Phase 2 — Sales Invoice from cart)
# ---------------------------------------------------------------------------
#
# Decisions locked 2026-04-30 from QBO mirror:
#   - HST account name:   "GST/HST Payable"
#   - Income accounts:    "4260 Beverage" (Drink SKUs), "4210 Food" (Food SKUs)
#   - Warehouse + Cost Center:  "Hamilton"
#   - POS Profile:        "Hamilton Front Desk" (operator-invisible)
#   - Tax template:       "Ontario HST 13%"
#
# The seed is idempotent — every step uses ``frappe.db.exists`` guards. Safe
# to re-run on partial state. See ``docs/decisions_log.md`` Amendment
# 2026-04-30 (b) for the full rationale.

HAMILTON_HST_ACCOUNT_BASE      = "GST/HST Payable"
HAMILTON_INCOME_ACCOUNT_BEVERAGE = "4260 Beverage"
HAMILTON_INCOME_ACCOUNT_FOOD   = "4210 Food"
HAMILTON_WAREHOUSE_BASE        = "Hamilton"
HAMILTON_COST_CENTER_BASE      = "Hamilton"
HAMILTON_TAX_TEMPLATE_BASE     = "Ontario HST 13%"
HAMILTON_POS_PROFILE_NAME      = "Hamilton Front Desk"
HAMILTON_HST_RATE              = 13.0


def _ensure_hamilton_accounting():
	"""Idempotent seed of Hamilton's company + retail accounting prereqs.

	Runs in ``after_install`` AND on every ``bench migrate`` (re-applied via
	the same patch entry). Detects an existing Hamilton-named company first
	(``frappe.conf.hamilton_company`` pin → name match → fallback create);
	then layers QBO-mirrored accounts, warehouse, cost center, tax template,
	and Mode of Payment Account on top.

	Production sites that already have a real Company set up should pin it
	via ``bench --site SITE set-config hamilton_company "Company Name"`` so
	this seed augments the existing Company rather than creating a phantom
	"Club Hamilton" alongside it.
	"""
	company = _ensure_hamilton_company()
	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		frappe.logger().warning(
			f"hamilton_erp: Company {company!r} has no abbr; skipping accounting seed"
		)
		return
	_ensure_hamilton_warehouse(company, abbr)
	_ensure_hamilton_cost_center(company, abbr)
	_ensure_hamilton_retail_accounts(company, abbr)
	_ensure_ontario_hst_template(company, abbr)
	_ensure_cash_mode_of_payment_account(company, abbr)
	_ensure_default_stock_warehouse(abbr)


def _ensure_hamilton_company() -> str:
	"""Return the Hamilton company name, creating "Club Hamilton" if missing.

	Detection order:
	  1. ``frappe.conf.hamilton_company`` — explicit per-venue pin in
	     ``site_config.json``. If set and the company exists, returned as-is.
	     If set but missing, logged and falls through.
	  2. Heuristic name match on common Hamilton-named companies.
	  3. ``frappe.defaults.get_global_default("company")`` — the system
	     default. Production sites have one; CI / fresh dev sites usually
	     don't.
	  4. Create "Club Hamilton" (abbr "CH") with Standard CoA + CAD + Canada.
	"""
	pinned = frappe.conf.get("hamilton_company")
	if pinned:
		if frappe.db.exists("Company", pinned):
			return pinned
		frappe.logger().warning(
			f"hamilton_erp: site_config.hamilton_company={pinned!r} but "
			f"no such Company exists; falling through to detection."
		)

	for candidate in ("Club Hamilton", "Hamilton", "Hamilton Club"):
		if frappe.db.exists("Company", candidate):
			return candidate

	matches = frappe.get_all(
		"Company",
		filters={"company_name": ["like", "%Hamilton%"]},
		fields=["name"],
		limit=1,
	)
	if matches:
		return matches[0]["name"]

	default_company = frappe.defaults.get_global_default("company")
	if default_company and frappe.db.exists("Company", default_company):
		# Production site with a pre-existing default — augment it rather
		# than create a sibling Club Hamilton. Operators can rename later.
		frappe.logger().info(
			f"hamilton_erp: using existing default company {default_company!r} "
			f"(no Hamilton-named company found; pin via site_config.hamilton_company "
			f"to override)"
		)
		return default_company

	# Greenfield install — create Club Hamilton with Standard CoA.
	frappe.get_doc({
		"doctype": "Company",
		"company_name": "Club Hamilton",
		"abbr": "CH",
		"default_currency": "CAD",
		"country": "Canada",
		"create_chart_of_accounts_based_on": "Standard Template",
		"chart_of_accounts": "Standard",
		"domain": "Retail",
	}).insert(ignore_permissions=True)
	frappe.logger().info("hamilton_erp: created Company 'Club Hamilton' (abbr CH)")
	return "Club Hamilton"


def _ensure_hamilton_warehouse(company: str, abbr: str):
	"""Create Warehouse "Hamilton - {abbr}" under the company root warehouse."""
	full_name = f"{HAMILTON_WAREHOUSE_BASE} - {abbr}"
	if frappe.db.exists("Warehouse", full_name):
		return
	# Find the company's root warehouse — Standard CoA creates "All Warehouses
	# - {abbr}" but variants exist; query by company + is_group=1 + parent=None.
	parent = frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 1, "parent_warehouse": ["in", ["", None]]},
		"name",
	)
	frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": HAMILTON_WAREHOUSE_BASE,
		"company": company,
		"parent_warehouse": parent,
		"is_group": 0,
	}).insert(ignore_permissions=True)
	frappe.logger().info(f"hamilton_erp: created Warehouse {full_name!r}")


def _ensure_hamilton_cost_center(company: str, abbr: str):
	"""Create Cost Center "Hamilton - {abbr}" under the company root."""
	full_name = f"{HAMILTON_COST_CENTER_BASE} - {abbr}"
	if frappe.db.exists("Cost Center", full_name):
		return
	# Company root cost center is "{company} - {abbr}" by ERPNext convention.
	parent = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 1, "parent_cost_center": ["in", ["", None]]},
		"name",
	)
	frappe.get_doc({
		"doctype": "Cost Center",
		"cost_center_name": HAMILTON_COST_CENTER_BASE,
		"company": company,
		"parent_cost_center": parent,
		"is_group": 0,
	}).insert(ignore_permissions=True)
	frappe.logger().info(f"hamilton_erp: created Cost Center {full_name!r}")


def _ensure_hamilton_retail_accounts(company: str, abbr: str):
	"""Create the QBO-mirrored Hamilton accounts: GST/HST Payable + 4260 + 4210.

	Standard CoA creates the parent groups (Indirect Income, Duties and Taxes)
	when the Company is inserted; we layer Hamilton-specific leaves on top.
	"""
	# Income accounts under Indirect Income (or fallback to first Income group).
	income_parent = _find_account_parent(company, root_type="Income",
		preferred_names=("Indirect Income", "Sales", "Income"))
	if income_parent:
		for base in (HAMILTON_INCOME_ACCOUNT_BEVERAGE, HAMILTON_INCOME_ACCOUNT_FOOD):
			full_name = f"{base} - {abbr}"
			if frappe.db.exists("Account", full_name):
				continue
			frappe.get_doc({
				"doctype": "Account",
				"account_name": base,
				"parent_account": income_parent,
				"company": company,
				"account_type": "Income Account",
				"root_type": "Income",
				"is_group": 0,
			}).insert(ignore_permissions=True)
			frappe.logger().info(f"hamilton_erp: created Account {full_name!r}")
	else:
		frappe.logger().warning(
			f"hamilton_erp: no Income parent group found for {company!r}; "
			f"income accounts not seeded"
		)

	# HST account under Duties and Taxes (or fallback to a Liability group).
	tax_parent = _find_account_parent(company, root_type="Liability",
		preferred_names=("Duties and Taxes", "Tax", "Current Liabilities"))
	if tax_parent:
		full_name = f"{HAMILTON_HST_ACCOUNT_BASE} - {abbr}"
		if not frappe.db.exists("Account", full_name):
			frappe.get_doc({
				"doctype": "Account",
				"account_name": HAMILTON_HST_ACCOUNT_BASE,
				"parent_account": tax_parent,
				"company": company,
				"account_type": "Tax",
				"root_type": "Liability",
				"is_group": 0,
				"tax_rate": HAMILTON_HST_RATE,
			}).insert(ignore_permissions=True)
			frappe.logger().info(f"hamilton_erp: created Account {full_name!r}")
	else:
		frappe.logger().warning(
			f"hamilton_erp: no Liability parent group found for {company!r}; "
			f"GST/HST Payable not seeded"
		)


def _find_account_parent(company: str, root_type: str, preferred_names: tuple) -> str | None:
	"""Find a suitable parent group account by root_type, preferring named matches."""
	candidates = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 1, "root_type": root_type},
		fields=["name"],
		order_by="lft asc",
	)
	if not candidates:
		return None
	# Prefer names that contain one of the preferred substrings (in order).
	for prefer in preferred_names:
		for c in candidates:
			if prefer in c["name"]:
				return c["name"]
	# No preferred match — return the first (deepest by lft asc) group.
	return candidates[0]["name"]


def _ensure_ontario_hst_template(company: str, abbr: str):
	"""Create Sales Taxes and Charges Template "Ontario HST 13% - {abbr}"."""
	full_name = f"{HAMILTON_TAX_TEMPLATE_BASE} - {abbr}"
	if frappe.db.exists("Sales Taxes and Charges Template", full_name):
		return
	hst_account = f"{HAMILTON_HST_ACCOUNT_BASE} - {abbr}"
	if not frappe.db.exists("Account", hst_account):
		frappe.logger().warning(
			f"hamilton_erp: HST account {hst_account!r} missing — "
			f"Ontario HST 13% template not seeded"
		)
		return
	cost_center = f"{HAMILTON_COST_CENTER_BASE} - {abbr}"
	frappe.get_doc({
		"doctype": "Sales Taxes and Charges Template",
		"title": HAMILTON_TAX_TEMPLATE_BASE,
		"company": company,
		"taxes": [{
			"charge_type": "On Net Total",
			"account_head": hst_account,
			"description": "HST",
			"rate": HAMILTON_HST_RATE,
			"included_in_print_rate": 0,
			"cost_center": cost_center if frappe.db.exists("Cost Center", cost_center) else None,
		}],
	}).insert(ignore_permissions=True)
	frappe.logger().info(f"hamilton_erp: created Sales Taxes Template {full_name!r}")


def _ensure_cash_mode_of_payment_account(company: str, abbr: str):
	"""Append a Mode of Payment Account row for Cash on this company.

	Mode of Payment "Cash" is created by Standard ERPNext install. The
	per-company account row is needed so POS Sales Invoice payments find a
	default account when ``mode_of_payment="Cash"``.
	"""
	if not frappe.db.exists("Mode of Payment", "Cash"):
		# ERPNext should have created this; if not, no-op rather than fail.
		frappe.logger().warning(
			"hamilton_erp: Mode of Payment 'Cash' missing — skipping account row"
		)
		return
	cash_account = f"Cash - {abbr}"
	if not frappe.db.exists("Account", cash_account):
		# Standard CoA creates "Cash - {abbr}" under "Cash In Hand"; if it's
		# absent, log and skip rather than crash the install.
		frappe.logger().warning(
			f"hamilton_erp: Account {cash_account!r} missing — "
			f"skipping Mode of Payment Account for Cash"
		)
		return
	mop = frappe.get_doc("Mode of Payment", "Cash")
	existing = next(
		(a for a in mop.accounts if a.company == company), None,
	)
	if existing:
		if existing.default_account != cash_account:
			existing.default_account = cash_account
			mop.save(ignore_permissions=True)
		return
	mop.append("accounts", {
		"company": company,
		"default_account": cash_account,
	})
	mop.save(ignore_permissions=True)
	frappe.logger().info(
		f"hamilton_erp: added Mode of Payment Account Cash → {cash_account!r}"
	)


def _ensure_default_stock_warehouse(abbr: str):
	"""Set Stock Settings.default_warehouse = Hamilton - {abbr} if unset."""
	full_name = f"{HAMILTON_WAREHOUSE_BASE} - {abbr}"
	if not frappe.db.exists("Warehouse", full_name):
		return
	current = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if current and current != full_name:
		# Operator already configured one — don't overwrite.
		return
	if current == full_name:
		return
	frappe.db.set_single_value("Stock Settings", "default_warehouse", full_name)
	frappe.logger().info(
		f"hamilton_erp: set Stock Settings.default_warehouse = {full_name!r}"
	)


def _ensure_pos_profile():
	"""Create POS Profile "Hamilton Front Desk" — operator-invisible.

	This is the POS profile the cart Confirm flow uses to derive defaults
	(warehouse, cost center, tax template, payment methods). It's not
	exposed in the operator UI; the asset board calls submit_retail_sale
	which references it by name.
	"""
	if frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE_NAME):
		return
	pinned = frappe.conf.get("hamilton_company")
	company = pinned if pinned and frappe.db.exists("Company", pinned) else None
	if not company:
		# Re-run the same detection used by the accounting seed.
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
		frappe.logger().warning(
			"hamilton_erp: no Hamilton company found — POS Profile not seeded"
		)
		return
	abbr = frappe.db.get_value("Company", company, "abbr")
	warehouse = f"{HAMILTON_WAREHOUSE_BASE} - {abbr}"
	cost_center = f"{HAMILTON_COST_CENTER_BASE} - {abbr}"
	tax_template = f"{HAMILTON_TAX_TEMPLATE_BASE} - {abbr}"
	# All three must exist for the POS Profile to validate; bail if any
	# are missing (logged so the operator can re-run after fixing).
	for required, doctype in (
		(warehouse, "Warehouse"),
		(cost_center, "Cost Center"),
	):
		if not frappe.db.exists(doctype, required):
			frappe.logger().warning(
				f"hamilton_erp: {doctype} {required!r} missing — POS Profile not seeded"
			)
			return
	if not frappe.db.exists("Mode of Payment", "Cash"):
		frappe.logger().warning(
			"hamilton_erp: Mode of Payment 'Cash' missing — POS Profile not seeded"
		)
		return
	profile = {
		"doctype": "POS Profile",
		"name": HAMILTON_POS_PROFILE_NAME,
		"company": company,
		"warehouse": warehouse,
		"cost_center": cost_center,
		"currency": frappe.db.get_value("Company", company, "default_currency") or "CAD",
		"update_stock": 1,
		"ignore_pricing_rule": 1,
		"payments": [{
			"mode_of_payment": "Cash",
			"default": 1,
		}],
	}
	if frappe.db.exists("Sales Taxes and Charges Template", tax_template):
		profile["taxes_and_charges"] = tax_template
	frappe.get_doc(profile).insert(ignore_permissions=True)
	frappe.logger().info(
		f"hamilton_erp: created POS Profile {HAMILTON_POS_PROFILE_NAME!r}"
	)
