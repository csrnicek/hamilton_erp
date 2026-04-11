"""Install and migrate hooks for the Hamilton ERP app."""

import frappe
from frappe import _


def after_install():
	"""Create default roles and initial configuration after app installation."""
	_create_roles()
	_set_role_permissions()
	frappe.db.commit()


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
