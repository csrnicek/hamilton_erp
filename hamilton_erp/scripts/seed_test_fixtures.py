"""One-off dev-only seed helpers for local test harness bootstrap.

These exist because ERPNext's global test records reference a `_Test Customer`
that has no installer seed path on a fresh site. They are NOT loaded by
Phase 1 code and are not part of any install hook.
"""

import frappe


def _find_non_group_customer_group() -> str:
    """Return the name of a non-group Customer Group (for linking test customers)."""
    rows = frappe.get_all(
        "Customer Group",
        filters={"is_group": 0},
        fields=["name"],
        limit=1,
    )
    if not rows:
        raise RuntimeError("No non-group Customer Group found on this site")
    return rows[0]["name"]


def seed_test_customer():
    """Create the `_Test Customer` record ERPNext test fixtures depend on."""
    name = "_Test Customer"
    if frappe.db.exists("Customer", name):
        print(f"{name} already exists")
        return

    customer_group = _find_non_group_customer_group()
    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Individual",
            "customer_group": customer_group,
            "territory": "All Territories",
        }
    )
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.commit()
    print(f"Created {doc.name} (group={customer_group})")
