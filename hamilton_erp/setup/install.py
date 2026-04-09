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
	"""Grant Hamilton Operator read/write/create on operational DocTypes.

	Asset Status Log is intentionally read-only for operators — logs are
	created exclusively by the API (ignore_permissions=True) to maintain
	audit integrity.  Operators must not be able to create or edit log
	entries directly from the Frappe desk.
	"""
	operator_rw_doctypes = [
		"Venue Asset",
		"Venue Session",
		"Cash Drop",
		"Shift Record",
		"Comp Admission Log",
	]
	for dt in operator_rw_doctypes:
		_ensure_role_permission(dt, "Hamilton Operator", read=1, write=1, create=1)

	# Read-only: operators can view audit logs but cannot create or modify them
	_ensure_role_permission("Asset Status Log", "Hamilton Operator", read=1)


def _grant_manager_permissions():
	"""Grant Hamilton Manager full access to all custom DocTypes.

	Cash Reconciliation requires submit=1 because the blind-reveal logic
	lives in before_submit / on_submit.  Without this permission managers
	cannot submit the document.
	"""
	standard_manager_doctypes = [
		"Venue Asset",
		"Venue Session",
		"Cash Drop",
		"Asset Status Log",
		"Shift Record",
		"Comp Admission Log",
	]
	for dt in standard_manager_doctypes:
		_ensure_role_permission(dt, "Hamilton Manager", read=1, write=1, create=1, delete=1)

	# Submittable DocTypes need submit permission — on_submit hooks only fire after submission.
	# Venue Session: on_submit finalizes the session and moves the asset to Dirty (Phase 2).
	# Cash Reconciliation: on_submit marks the drop reconciled; before_submit reveals blind count.
	for dt in ("Venue Session", "Cash Reconciliation"):
		_ensure_role_permission(
			dt, "Hamilton Manager",
			read=1, write=1, create=1, delete=1, submit=1
		)


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
	submit: int = 0,
):
	"""Upsert a role permission row for a DocType — idempotent and self-correcting.

	If a row already exists with the wrong permissions (e.g., from a previous
	broken install), this updates it rather than silently skipping.
	"""
	existing_name = frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role})
	if existing_name:
		frappe.db.set_value(
			"Custom DocPerm",
			existing_name,
			{"read": read, "write": write, "create": create, "delete": delete, "submit": submit},
		)
		return

	frappe.get_doc(
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
			"submit": submit,
		}
	).insert(ignore_permissions=True)
