"""Tests for the Phase 1 seed patch — seed_hamilton_env.

The seed patch runs automatically during `bench migrate` as a
post_model_sync patch. These tests verify the patch's contract:

  1. Walk-in Customer exists after execute().
  2. Hamilton Settings has the documented defaults.
  3. The 59 assets are created with the correct ordering.
  4. Re-running is a no-op (idempotent).

Because Venue Asset rows are referenced by other tables (Venue Session,
Asset Status Log) once tests have run in the same process, we cannot
always wipe and re-seed from scratch — the patch's own idempotent guard
(`if frappe.db.count("Venue Asset") > 0: return`) is what we assert on.
"""
import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp.patches.v0_1 import seed_hamilton_env


class TestSeedPatch(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_seed_creates_walkin_customer(self):
		"""Walk-in Customer exists after seed execute() — even if absent beforehand."""
		# If it already exists (e.g. created by a previous test), the
		# patch short-circuits. Either way, the post-condition is the same.
		seed_hamilton_env.execute()
		self.assertTrue(frappe.db.exists("Customer", "Walk-in"))

	def test_seed_populates_hamilton_settings(self):
		"""Hamilton Settings receives the documented defaults.

		We deliberately zero out the two most load-bearing fields first
		(float_amount, default_stay_duration_minutes) so the patch's
		'set only if falsy' branch fires and we can assert on the write.
		"""
		s = frappe.get_single("Hamilton Settings")
		s.float_amount = 0
		s.default_stay_duration_minutes = 0
		s.save(ignore_permissions=True)
		seed_hamilton_env.execute()
		s = frappe.get_single("Hamilton Settings")
		self.assertEqual(s.float_amount, 300)
		self.assertEqual(s.default_stay_duration_minutes, 360)

	def test_seed_creates_59_assets_in_correct_order(self):
		"""The 59 seeded assets exist with the correct code + display_order.

		We do NOT wipe the Venue Asset table first — other tables FK-reference
		it and a DELETE would cascade-fail. Instead, we run the idempotent
		seed patch and assert on the subset of rows whose asset_codes match
		the seed plan (R001-R026 + L001-L033). display_order on those rows
		must match the documented plan: R001=1, R011=11, ... L033=59.
		"""
		seed_hamilton_env.execute()
		assets = frappe.get_all(
			"Venue Asset",
			filters={"asset_code": ["in", [
				*[f"R{i:03d}" for i in range(1, 27)],
				*[f"L{i:03d}" for i in range(1, 34)],
			]]},
			fields=["asset_code", "asset_category", "asset_tier", "display_order"],
			order_by="display_order asc",
		)
		self.assertEqual(len(assets), 59)
		self.assertEqual(assets[0]["asset_code"], "R001")   # first Single Standard
		self.assertEqual(assets[10]["asset_code"], "R011")  # last Single Standard
		self.assertEqual(assets[11]["asset_code"], "R012")  # first Deluxe Single
		self.assertEqual(assets[20]["asset_code"], "R021")  # last Deluxe Single
		self.assertEqual(assets[21]["asset_code"], "R022")  # first Glory Hole
		self.assertEqual(assets[22]["asset_code"], "R023")  # last Glory Hole
		self.assertEqual(assets[23]["asset_code"], "R024")  # first Double Deluxe
		self.assertEqual(assets[25]["asset_code"], "R026")  # last Double Deluxe
		self.assertEqual(assets[26]["asset_code"], "L001")  # first Locker
		self.assertEqual(assets[58]["asset_code"], "L033")  # last Locker

	def test_seed_tiers_match_plan(self):
		"""Each seeded asset has the correct tier per Q6."""
		seed_hamilton_env.execute()
		tiers = {
			a["asset_code"]: a["asset_tier"]
			for a in frappe.get_all(
				"Venue Asset",
				filters={"asset_code": ["in", [
					*[f"R{i:03d}" for i in range(1, 27)],
					*[f"L{i:03d}" for i in range(1, 34)],
				]]},
				fields=["asset_code", "asset_tier"],
			)
		}
		# Single Standard: R001-R011
		for i in range(1, 12):
			self.assertEqual(tiers[f"R{i:03d}"], "Single Standard")
		# Deluxe Single: R012-R021
		for i in range(12, 22):
			self.assertEqual(tiers[f"R{i:03d}"], "Deluxe Single")
		# Glory Hole: R022-R023
		for i in range(22, 24):
			self.assertEqual(tiers[f"R{i:03d}"], "Glory Hole")
		# Double Deluxe: R024-R026
		for i in range(24, 27):
			self.assertEqual(tiers[f"R{i:03d}"], "Double Deluxe")
		# Locker: L001-L033
		for i in range(1, 34):
			self.assertEqual(tiers[f"L{i:03d}"], "Locker")

	def test_seed_is_idempotent(self):
		"""Running the seed patch twice must not duplicate any rows."""
		seed_hamilton_env.execute()
		count1 = frappe.db.count("Venue Asset")
		seed_hamilton_env.execute()
		count2 = frappe.db.count("Venue Asset")
		self.assertEqual(count1, count2)
