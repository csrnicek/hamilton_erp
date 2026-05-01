"""Hamilton Price List + POS Profile selling_price_list backfill.

The PR #51 install fixes added Hamilton-specific Price List "Hamilton
Standard Selling" and wired it into ``_ensure_pos_profile``. Existing
sites that already ran the install path before this patch shipped have:

  - No "Hamilton Standard Selling" Price List
  - POS Profile "Hamilton Front Desk" with ``selling_price_list = NULL``
    (or pointing at "Standard Selling" if they were on the prior bad fix)

This patch backfills both. Idempotent.
"""
import frappe


def execute():
	from hamilton_erp.setup.install import (
		HAMILTON_POS_PROFILE_NAME,
		HAMILTON_PRICE_LIST_NAME,
		_ensure_erpnext_prereqs,
	)

	# Re-run prereqs to create the Price List on existing sites.
	_ensure_erpnext_prereqs()

	# Backfill the POS Profile's selling_price_list if it's null or
	# pointing at the now-removed "Standard Selling" placeholder.
	if frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE_NAME):
		current = frappe.db.get_value(
			"POS Profile", HAMILTON_POS_PROFILE_NAME, "selling_price_list"
		)
		if not current or current == "Standard Selling":
			if frappe.db.exists("Price List", HAMILTON_PRICE_LIST_NAME):
				frappe.db.set_value(
					"POS Profile",
					HAMILTON_POS_PROFILE_NAME,
					"selling_price_list",
					HAMILTON_PRICE_LIST_NAME,
				)
				frappe.logger().info(
					f"hamilton_erp: backfilled POS Profile.selling_price_list "
					f"= {HAMILTON_PRICE_LIST_NAME!r} (was {current!r})"
				)
	frappe.db.commit()
