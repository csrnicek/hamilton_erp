"""V9.1 Phase 2 follow-up — seed Hamilton accounting prereqs on existing sites.

Newly-installed sites get `_ensure_hamilton_accounting` + `_ensure_pos_profile`
via the after_install hook (see hamilton_erp/setup/install.py). This patch
runs the same idempotent seeds on existing sites the first time they
`bench migrate` after this code lands.

Idempotent: every step uses ``frappe.db.exists()`` guards. Safe to re-run
on partial state (e.g. if a previous patch run was interrupted).
"""
import frappe


def execute():
	from hamilton_erp.setup.install import (
		_ensure_hamilton_accounting,
		_ensure_pos_profile,
	)
	# Refresh retail Item Defaults too — the original seed_hamilton_env patch
	# already executed on existing sites before this PR shipped, so its updated
	# `_ensure_retail_item_defaults` body never ran. Re-running it now wires
	# the Item Defaults rows for the 4 retail items.
	from hamilton_erp.patches.v0_1.seed_hamilton_env import _ensure_retail_item_defaults

	_ensure_hamilton_accounting()
	_ensure_pos_profile()
	_ensure_retail_item_defaults()
	frappe.db.commit()
