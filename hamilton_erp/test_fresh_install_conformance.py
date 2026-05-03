"""Fresh-install conformance tests for Hamilton ERP.

These tests pin the post-install DB state that ``setup/install.py``'s
``after_install`` hook plus the ``patches/v0_1`` data patches are
expected to produce on every fresh ``bench install-app``.

The motivation is the recurring "fresh-install gap" failure mode that
bit feat/v91-cart-sales-invoice (PR #51) five times in a row during CI:
Warehouse Type "Transit", Stock Entry Type "Material Receipt",
Fiscal Year, Mode of Payment "Cash", Price List "Standard Selling".
Each one was a record ERPNext's setup-wizard normally seeds but
Hamilton's unattended install path skipped, blowing up CI test setup
for downstream modules until added to ``_ensure_erpnext_prereqs``.

This test module asserts the *current* main's install contract. When
follow-up PRs add new seeds (e.g. PR #51's Mode of Payment / Price
List), this module must extend in the same PR — making the
fresh-install contract grow with the codebase rather than erode in
silence.

Run via:
    bench --site hamilton-unit-test.localhost run-tests \\
      --app hamilton_erp --module hamilton_erp.test_fresh_install_conformance

These tests are READ-ONLY against the test site's already-installed
state. They do NOT re-run ``after_install``. Instead, they verify the
current DB state matches what install.py + patches.txt would produce.
A test failure means either:
  (a) the test site has drifted from a fresh install (run
      ``bench --site SITE migrate`` to re-apply patches), OR
  (b) the install path has regressed — install.py or seed_hamilton_env.py
      stopped seeding the record this test asserts. Investigate which
      file changed and why.
"""
from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp.patches.v0_1.seed_hamilton_env import (
	HAMILTON_RETAIL_ITEM_GROUP,
	HAMILTON_RETAIL_ITEMS,
)

# ---------------------------------------------------------------------------
# ERPNext root records (created by setup/install.py:_ensure_erpnext_prereqs)
# ---------------------------------------------------------------------------


class TestERPNextPrerequisites(IntegrationTestCase):
	"""Pin the ERPNext root records that ``_ensure_erpnext_prereqs`` creates.

	These are records ERPNext's setup-wizard normally creates as a side
	effect of company creation. Hamilton's unattended install path never
	runs the wizard, so install.py must create them explicitly.
	"""

	def test_customer_group_all_customer_groups_exists(self):
		"""Customer Group root 'All Customer Groups' must exist (parent of all)."""
		self.assertTrue(
			frappe.db.exists("Customer Group", "All Customer Groups"),
			"Customer Group 'All Customer Groups' missing — _ensure_erpnext_prereqs regression",
		)

	def test_customer_group_individual_exists(self):
		"""Customer Group 'Individual' must exist for Walk-in Customer's group."""
		self.assertTrue(
			frappe.db.exists("Customer Group", "Individual"),
			"Customer Group 'Individual' missing — Walk-in seed cannot link",
		)

	def test_territory_all_territories_exists(self):
		"""Territory root 'All Territories' must exist (parent of all)."""
		self.assertTrue(
			frappe.db.exists("Territory", "All Territories"),
			"Territory 'All Territories' missing — _ensure_erpnext_prereqs regression",
		)

	def test_territory_default_exists(self):
		"""Territory 'Default' must exist for Walk-in Customer's territory."""
		self.assertTrue(
			frappe.db.exists("Territory", "Default"),
			"Territory 'Default' missing — Walk-in seed cannot link",
		)

	def test_item_group_all_item_groups_exists(self):
		"""Item Group root 'All Item Groups' must exist (parent of retail group)."""
		self.assertTrue(
			frappe.db.exists("Item Group", "All Item Groups"),
			"Item Group 'All Item Groups' missing — Drink/Food seed cannot link",
		)

	def test_uom_nos_exists(self):
		"""UOM 'Nos' must exist as default stock_uom for retail Items."""
		self.assertTrue(
			frappe.db.exists("UOM", "Nos"),
			"UOM 'Nos' missing — retail Item seeding will fail",
		)


# ---------------------------------------------------------------------------
# Hamilton-specific seed (created by patches/v0_1/seed_hamilton_env.py)
# ---------------------------------------------------------------------------


class TestHamiltonSeedData(IntegrationTestCase):
	"""Pin the Hamilton-specific seed records produced by seed_hamilton_env."""

	def test_walkin_customer_exists(self):
		"""Walk-in Customer must exist for anonymous-session start_session calls."""
		self.assertTrue(
			frappe.db.exists("Customer", "Walk-in"),
			"Walk-in Customer missing — DEC-055 §1 violation",
		)

	def test_walkin_customer_has_customer_group_set(self):
		"""Walk-in Customer must have a non-empty customer_group (any value).

		seed_hamilton_env._ensure_walkin_customer picks the first non-group
		Customer Group as a fallback if 'Individual' isn't found, so the exact
		value can vary across installs/tests. Pin only that the field is set —
		not the specific value, since other tests may legitimately link
		Walk-in to a different group during their setUp.
		"""
		group = frappe.db.get_value("Customer", "Walk-in", "customer_group")
		self.assertTrue(
			group,
			"Walk-in Customer has empty customer_group — seed regression",
		)
		self.assertTrue(
			frappe.db.exists("Customer Group", group),
			f"Walk-in Customer's customer_group={group!r} doesn't exist as a "
			"Customer Group — referential integrity broken",
		)

	def test_hamilton_settings_singleton_exists(self):
		"""Hamilton Settings singleton must exist."""
		settings = frappe.get_single("Hamilton Settings")
		self.assertIsNotNone(settings, "Hamilton Settings singleton not loadable")

	def test_hamilton_settings_float_amount_default(self):
		"""Hamilton Settings.float_amount should default to 300 per seed."""
		amount = frappe.db.get_single_value("Hamilton Settings", "float_amount")
		self.assertEqual(
			int(amount or 0), 300,
			f"Hamilton Settings.float_amount={amount}, expected 300 (seed default)",
		)

	def test_hamilton_settings_default_stay_duration_minutes(self):
		"""Hamilton Settings.default_stay_duration_minutes should default to 360 per seed."""
		minutes = frappe.db.get_single_value(
			"Hamilton Settings", "default_stay_duration_minutes"
		)
		self.assertEqual(
			int(minutes or 0), 360,
			f"Hamilton Settings.default_stay_duration_minutes={minutes}, expected 360",
		)

	def test_hamilton_settings_grace_minutes(self):
		"""Hamilton Settings.grace_minutes should default to 15 per seed."""
		minutes = frappe.db.get_single_value("Hamilton Settings", "grace_minutes")
		self.assertEqual(
			int(minutes or 0), 15,
			f"Hamilton Settings.grace_minutes={minutes}, expected 15",
		)

	def test_hamilton_settings_assignment_timeout_minutes(self):
		"""Hamilton Settings.assignment_timeout_minutes should default to 15 per seed."""
		minutes = frappe.db.get_single_value(
			"Hamilton Settings", "assignment_timeout_minutes"
		)
		self.assertEqual(
			int(minutes or 0), 15,
			f"Hamilton Settings.assignment_timeout_minutes={minutes}, expected 15",
		)

	def test_venue_assets_R001_through_R026_present(self):
		"""All 26 room asset_codes R001..R026 are present (verifies seed_hamilton_env plan loop)."""
		for i in range(1, 27):
			code = f"R{i:03d}"
			self.assertTrue(
				frappe.db.exists("Venue Asset", {"asset_code": code}),
				f"Venue Asset asset_code={code} missing — seed_hamilton_env plan loop regressed",
			)

	def test_venue_assets_L001_through_L033_present(self):
		"""All 33 locker asset_codes L001..L033 are present."""
		for i in range(1, 34):
			code = f"L{i:03d}"
			self.assertTrue(
				frappe.db.exists("Venue Asset", {"asset_code": code}),
				f"Venue Asset asset_code={code} missing — seed_hamilton_env plan loop regressed",
			)


# ---------------------------------------------------------------------------
# V9.1 retail catalogue (created by seed_hamilton_env._ensure_retail_items)
# ---------------------------------------------------------------------------


class TestHamiltonRetailCatalogue(IntegrationTestCase):
	"""Pin the V9.1 retail catalogue: 1 Item Group + 4 Items."""

	def test_drink_food_item_group_exists(self):
		"""Item Group 'Drink/Food' must exist as the retail-catalogue parent."""
		self.assertTrue(
			frappe.db.exists("Item Group", HAMILTON_RETAIL_ITEM_GROUP),
			f"Item Group {HAMILTON_RETAIL_ITEM_GROUP!r} missing — _ensure_retail_items regression",
		)

	def test_drink_food_parents_into_all_item_groups(self):
		"""Item Group 'Drink/Food' must parent into 'All Item Groups'."""
		parent = frappe.db.get_value(
			"Item Group", HAMILTON_RETAIL_ITEM_GROUP, "parent_item_group"
		)
		self.assertEqual(
			parent, "All Item Groups",
			f"Item Group {HAMILTON_RETAIL_ITEM_GROUP!r} parents into {parent!r}, "
			"expected 'All Item Groups'",
		)

	def test_all_four_retail_items_seeded(self):
		"""All 4 V9.1 retail Items must exist with correct codes."""
		for spec in HAMILTON_RETAIL_ITEMS:
			self.assertTrue(
				frappe.db.exists("Item", spec["item_code"]),
				f"Item {spec['item_code']!r} ({spec['item_name']}) missing — "
				"_ensure_retail_items regression",
			)

	def test_retail_items_use_drink_food_group(self):
		"""All 4 retail Items must belong to the Drink/Food Item Group."""
		for spec in HAMILTON_RETAIL_ITEMS:
			group = frappe.db.get_value("Item", spec["item_code"], "item_group")
			self.assertEqual(
				group, HAMILTON_RETAIL_ITEM_GROUP,
				f"Item {spec['item_code']!r} item_group={group!r}, "
				f"expected {HAMILTON_RETAIL_ITEM_GROUP!r}",
			)

	def test_retail_items_use_nos_uom(self):
		"""All 4 retail Items must use stock_uom='Nos'."""
		for spec in HAMILTON_RETAIL_ITEMS:
			uom = frappe.db.get_value("Item", spec["item_code"], "stock_uom")
			self.assertEqual(
				uom, "Nos",
				f"Item {spec['item_code']!r} stock_uom={uom!r}, expected 'Nos'",
			)

	def test_retail_items_have_seed_rates(self):
		"""All 4 retail Items must have standard_rate matching the seed table."""
		for spec in HAMILTON_RETAIL_ITEMS:
			rate = frappe.db.get_value("Item", spec["item_code"], "standard_rate")
			self.assertEqual(
				float(rate or 0), float(spec["rate"]),
				f"Item {spec['item_code']!r} standard_rate={rate}, "
				f"expected {spec['rate']}",
			)


# ---------------------------------------------------------------------------
# Hamilton roles (created by setup/install.py:_create_roles)
# ---------------------------------------------------------------------------


class TestHamiltonRoles(IntegrationTestCase):
	"""Pin the 3 Hamilton-specific roles + Administrator's Operator assignment."""

	def test_hamilton_operator_role_exists(self):
		"""Hamilton Operator role must exist with desk_access=1."""
		self.assertTrue(
			frappe.db.exists("Role", "Hamilton Operator"),
			"Role 'Hamilton Operator' missing — _create_roles regression",
		)
		desk_access = frappe.db.get_value("Role", "Hamilton Operator", "desk_access")
		self.assertEqual(
			int(desk_access or 0), 1,
			"Hamilton Operator role lacks desk_access=1 — operators cannot reach Asset Board",
		)

	def test_hamilton_manager_role_exists(self):
		"""Hamilton Manager role must exist."""
		self.assertTrue(
			frappe.db.exists("Role", "Hamilton Manager"),
			"Role 'Hamilton Manager' missing — _create_roles regression",
		)

	def test_hamilton_admin_role_exists(self):
		"""Hamilton Admin role must exist."""
		self.assertTrue(
			frappe.db.exists("Role", "Hamilton Admin"),
			"Role 'Hamilton Admin' missing — _create_roles regression",
		)

	def test_administrator_has_hamilton_operator_role(self):
		"""Administrator must have Hamilton Operator role granted (Asset Board access)."""
		admin = frappe.get_doc("User", "Administrator")
		operator_roles = [r for r in admin.roles if r.role == "Hamilton Operator"]
		self.assertEqual(
			len(operator_roles), 1,
			"Administrator missing 'Hamilton Operator' role — _create_roles regression. "
			"Without this, Asset Board page is 403 for Administrator and "
			"test_environment_health.test_administrator_has_hamilton_operator_role "
			"will also fail.",
		)


# ---------------------------------------------------------------------------
# Permission scrubs (Custom DocPerm changes from _block_pos_closing_for_operator)
# ---------------------------------------------------------------------------


class TestPermissionScrubs(IntegrationTestCase):
	"""Pin the targeted permission removals install.py performs."""

	def test_hamilton_operator_blocked_from_pos_closing_entry(self):
		"""Hamilton Operator must NOT have a Custom DocPerm row on POS Closing Entry.

		DEC-005 (blind cash control): operators use Cash Drop, never POS
		Closing Entry, because the latter shows expected cash totals.
		install.py:_block_pos_closing_for_operator scrubs any Custom DocPerm
		row that pairs Hamilton Operator with POS Closing Entry.
		"""
		exists = frappe.db.exists(
			"Custom DocPerm",
			{"parent": "POS Closing Entry", "role": "Hamilton Operator"},
		)
		self.assertFalse(
			exists,
			"Hamilton Operator has a Custom DocPerm on POS Closing Entry — "
			"DEC-005 blind-cash invariant violated. _block_pos_closing_for_operator "
			"either regressed or was bypassed by a fixture export.",
		)


# ---------------------------------------------------------------------------
# System Settings hardening — audit trail (per-DocType track_changes on v16)
# ---------------------------------------------------------------------------


class TestSystemSettingsHardening(IntegrationTestCase):
	"""Pin the System Settings invariants install.py is responsible for.

	History: a previous test_audit_trail_enabled_if_field_present asserted
	`System Settings.enable_audit_trail == 1` (v15-era audit gate). That
	field does not exist on Frappe v16, so the test self-skipped 100% of
	the time. Removed 2026-05-03 alongside the corresponding install hook
	(LL-038). The v16 audit mechanism is per-DocType `track_changes`,
	pinned by `test_track_changes_enabled_on_all_auditable_hamilton_doctypes`
	below — the only thing this class needs.
	"""

	def test_track_changes_enabled_on_all_auditable_hamilton_doctypes(self):
		"""T1-6: every Hamilton-owned operational DocType has `track_changes: 1`.

		The Frappe v16 audit mechanism is per-DocType `track_changes: 1`
		(which writes to `tabVersion`). This test pins it: every
		Hamilton-owned operational DocType must declare `track_changes: 1`
		on its meta. The exception is Asset Status Log itself, which IS
		the audit log — tracking changes on the audit log is circular and
		intentionally off (`track_changes: 0`).

		If this test fails: someone added a new Hamilton DocType without
		`track_changes: 1`, OR removed `track_changes` from an existing
		one. The audit-trail invariant is broken; investigate before merging.

		History: T1-6 in `docs/inbox/2026-05-04_audit_synthesis_decisions.md`
		originally called for asserting `System Settings.enable_audit_trail
		== 1`. Investigation revealed that field does not exist on Frappe
		v16.14.0; per-DocType `track_changes` is the v16 mechanism. The
		corresponding install hook `_ensure_audit_trail_enabled` was
		removed 2026-05-03 (LL-038).
		"""
		# Per-DocType track_changes coverage is the v16 audit mechanism.
		# Asset Status Log is the audit log itself — tracking changes on it
		# would be circular and is intentionally off.
		AUDITABLE_DOCTYPES = [
			"Cash Drop",
			"Cash Reconciliation",
			"Comp Admission Log",
			"Hamilton Board Correction",
			"Hamilton Settings",
			"Shift Record",
			"Venue Asset",
			"Venue Session",
		]
		EXPECTED_TRACK_CHANGES_OFF = {"Asset Status Log"}

		missing = []
		for doctype in AUDITABLE_DOCTYPES:
			meta = frappe.get_meta(doctype)
			if not meta.track_changes:
				missing.append(doctype)
		self.assertEqual(
			missing, [],
			f"Hamilton DocTypes missing track_changes=1: {missing}. "
			"This breaks the v16 audit-trail invariant — every change to these "
			"DocTypes should land in tabVersion. See "
			"docs/inbox/2026-05-04_audit_synthesis_decisions.md T1-6.",
		)

		# Sanity: Asset Status Log MUST stay track_changes=0 (it IS the audit log).
		for doctype in EXPECTED_TRACK_CHANGES_OFF:
			meta = frappe.get_meta(doctype)
			self.assertFalse(
				meta.track_changes,
				f"{doctype} has track_changes=1, but it IS the audit log. "
				"Tracking changes on the audit log is circular. "
				"Set track_changes: 0 in {doctype}.json.",
			)

	def test_setup_complete_healed(self):
		"""Installed Application rows for frappe + erpnext must show is_setup_complete=1.

		_ensure_no_setup_wizard_loop heals any 0 row to 1 on every install/migrate.
		If this test fails, the Desk lands on the setup-wizard redirect loop —
		exactly the failure test_environment_health.test_bench_serves_login_not_wizard
		also catches at the HTTP level.
		"""
		for app_name in ("frappe", "erpnext"):
			row = frappe.db.get_value(
				"Installed Application",
				{"app_name": app_name},
				"is_setup_complete",
			)
			self.assertEqual(
				int(row or 0), 1,
				f"Installed Application[{app_name}].is_setup_complete=0 — "
				"_ensure_no_setup_wizard_loop regression. Setup-wizard redirect "
				"loop will activate on next bench restart.",
			)
