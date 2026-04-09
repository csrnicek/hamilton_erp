"""after_install hook — run once when the app is first installed on a site."""

import frappe
from frappe import _


def after_install():
	"""Create default roles and initial configuration after app installation."""
	_create_roles()
	_set_role_permissions()
	frappe.db.commit()


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
