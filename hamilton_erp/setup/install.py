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
	for role_name in ("Hamilton Operator", "Hamilton Manager"):
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
				}
			).insert(ignore_permissions=True)


def _set_role_permissions():
	"""Configure role permissions for all custom DocTypes and blocked DocTypes."""
	_grant_operator_permissions()
	_grant_manager_permissions()
	_block_pos_closing_for_operator()


def _grant_operator_permissions():
	"""Grant Hamilton Operator read/write/create on operational DocTypes."""
	operator_doctypes = [
		"Venue Asset",
		"Venue Session",
		"Cash Drop",
		"Asset Status Log",
		"Shift Record",
		"Comp Admission Log",
	]
	for dt in operator_doctypes:
		_ensure_role_permission(dt, "Hamilton Operator", read=1, write=1, create=1)


def _grant_manager_permissions():
	"""Grant Hamilton Manager full access to all custom DocTypes."""
	manager_doctypes = [
		"Venue Asset",
		"Venue Session",
		"Cash Drop",
		"Cash Reconciliation",
		"Asset Status Log",
		"Shift Record",
		"Comp Admission Log",
	]
	for dt in manager_doctypes:
		_ensure_role_permission(dt, "Hamilton Manager", read=1, write=1, create=1, delete=1)


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


def _ensure_role_permission(
	doctype: str,
	role: str,
	read: int = 0,
	write: int = 0,
	create: int = 0,
	delete: int = 0,
):
	"""Upsert a role permission row for a DocType — idempotent."""
	existing = frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role})
	if existing:
		return

	perm = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"read": read,
			"write": write,
			"create": create,
			"delete": delete,
		}
	)
	perm.insert(ignore_permissions=True)
