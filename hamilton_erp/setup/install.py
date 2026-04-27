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
	"""
	_ensure_erpnext_prereqs()
	_seed_hamilton_data()
	_create_roles()
	_set_role_permissions()
	frappe.db.commit()


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
	for app_name in ("frappe", "erpnext"):
		current = frappe.db.get_value(
			"Installed Application",
			{"app_name": app_name},
			"is_setup_complete",
		)
		if current != 1:
			frappe.db.set_value(
				"Installed Application",
				{"app_name": app_name},
				"is_setup_complete",
				1,
			)

	# Sync System Settings.setup_complete so anything reading it
	# (error log UI, some older Frappe helpers) also sees True.
	frappe.db.set_single_value(
		"System Settings", "setup_complete", frappe.is_setup_complete()
	)

	# Fresh ERPNext leaves DefaultValue desktop:home_page='setup-wizard' set,
	# which redirects the desk to setup-wizard on every load — the 2026-04-11
	# asset-board flash-loop incident. Pinned by
	# test_regression_desktop_home_page_not_setup_wizard. Idempotent: db.delete
	# is a no-op if the row is absent.
	frappe.db.delete("DefaultValue", {
		"parent": "__default",
		"defkey": "desktop:home_page",
		"defvalue": "setup-wizard",
	})

	frappe.db.commit()
	frappe.clear_cache(doctype="Installed Application")
	frappe.clear_cache(doctype="System Settings")


def _create_roles():
	"""Create Hamilton-specific roles if they do not already exist."""
	for role_name in ("Hamilton Operator", "Hamilton Manager", "Hamilton Admin"):
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
				}
			).insert(ignore_permissions=True)


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
