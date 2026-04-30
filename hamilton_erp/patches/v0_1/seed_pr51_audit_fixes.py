"""PR #51 audit fixes — re-run helpers whose behavior changed.

The pre-merge audit on PR #51 (2026-04-30) tightened two seed helpers:

  - ``_ensure_round_off_account_linked`` now overwrites the Standard CoA
    auto-default ``round_off_cost_center = "Main - {abbr}"`` with
    ``"Hamilton - {abbr}"`` so rounding GL entries tie to the Hamilton
    cost center for venue-level reporting (Audit Issue H).

  - ``_ensure_pos_profile`` now sets ``write_off_limit = 0`` explicitly
    for forward-compat (Audit Issue F). Existing POS Profiles already
    have 0 by default; this patch is a no-op for them.

Existing sites that already ran ``seed_canadian_nickel_rounding`` need
this follow-up because patches in ``tabPatch Log`` don't re-execute.
Fresh installs pick the new behavior up via ``after_install``.

Idempotent. Safe to re-run.
"""
import frappe


def execute():
	from hamilton_erp.setup.install import (
		_ensure_hamilton_company,
		_ensure_round_off_account_linked,
	)

	company = _ensure_hamilton_company()
	abbr = frappe.db.get_value("Company", company, "abbr")
	if abbr:
		_ensure_round_off_account_linked(company, abbr)
	frappe.db.commit()
