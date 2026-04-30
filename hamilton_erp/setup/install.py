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

	Order matters: ``_ensure_erpnext_prereqs`` must run BEFORE ``_seed_hamilton_data``
	because ``seed_hamilton_env._ensure_walkin_customer`` looks up Customer Group
	"All Customer Groups" and Territory "All Territories".

	``_ensure_no_setup_wizard_loop`` runs LAST so the desk lands in a usable
	state immediately after ``bench install-app`` — without depending on a
	follow-up ``bench migrate`` to fire the after_migrate hook.
	"""
	_ensure_erpnext_prereqs()
	_seed_hamilton_data()
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
	without retro-fitting. Idempotent — only writes if currently 0/None.

	If the field doesn't exist on this Frappe version, this is a no-op
	(captured by the existence check), so the install path stays robust
	across minor v16 versions.
	"""
	# Field name in Frappe v15+: `enable_audit_trail` on System Settings.
	# Use frappe.db.get_single_value to avoid loading the doc unnecessarily.
	current = frappe.db.get_single_value("System Settings", "enable_audit_trail")
	if current is None:
		# Field absent on this Frappe build — older minor or rename.
		frappe.logger().info(
			"hamilton_erp: System Settings.enable_audit_trail not present; "
			"skipping audit-trail enable (Frappe version variance)."
		)
		return
	if int(current) == 1:
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
