"""V9.1 Phase 2 follow-up — Canadian penny-elimination rounding seed.

Adds the two new helpers landed 2026-04-30 (c) to the install path:
``_ensure_round_off_account_linked`` (links Round Off + cost center on
Company) and ``_ensure_cad_nickel_rounding`` (sets CAD's
``smallest_currency_fraction_value`` to 0.05).

Existing sites that already ran ``seed_hamilton_accounting`` need this
follow-up patch because patches in tabPatch Log don't re-execute. Fresh
installs pick the new helpers up via ``after_install`` directly.

Idempotent: each step uses ``frappe.db.exists()`` / current-value guards.
Safe to re-run.
"""
import frappe


def execute():
	from hamilton_erp.setup.install import (
		_ensure_cad_nickel_rounding,
		_ensure_hamilton_company,
		_ensure_round_off_account_linked,
	)

	# Resolve the Hamilton company exactly the way the install seed does so
	# this patch handles pinned-name and Club-Hamilton-default cases alike.
	company = _ensure_hamilton_company()
	abbr = frappe.db.get_value("Company", company, "abbr")
	if abbr:
		_ensure_round_off_account_linked(company, abbr)
	_ensure_cad_nickel_rounding()
	frappe.db.commit()
