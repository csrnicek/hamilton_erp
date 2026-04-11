"""Tests for the Phase 1 api.py additions.

Lives at the package root (same level as api.py, lifecycle.py). We
intentionally do NOT set IGNORE_TEST_RECORD_DEPENDENCIES — Frappe v16's
IntegrationTestCase can't auto-detect cls.doctype for package-root
modules, so it skips test-record generation entirely and there's no
cascade to break. See test_lifecycle.py for the same note.
"""
import time

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import api
from hamilton_erp.patches.v0_1 import seed_hamilton_env


class TestGetAssetBoardData(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Seed the full 59-asset inventory once for the performance test.
		# Delete Venue Sessions first because Venue Asset has a link field
		# current_session → Venue Session, and Venue Session's venue_asset
		# field FK-blocks asset deletion until sessions are gone.
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		seed_hamilton_env.execute()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Scrub session + asset rows this class committed. Without this,
		# committed Venue Sessions with today's prefix bleed into
		# TestSessionNumberGenerator in test_lifecycle and break the
		# "first call returns 0001" + DB-fallback invariants.
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		# Also flush today's Redis session counter so a subsequent
		# test_lifecycle run doesn't resume from our incremented value.
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		frappe.cache().delete(f"hamilton:session_seq:{prefix}")
		frappe.db.commit()
		super().tearDownClass()

	def test_returns_all_active_assets(self):
		data = api.get_asset_board_data()
		self.assertEqual(len(data["assets"]), 59)

	def test_returns_settings_block(self):
		data = api.get_asset_board_data()
		self.assertIn("settings", data)
		self.assertIn("grace_minutes", data["settings"])

	def test_occupied_assets_include_session_start(self):
		"""Pick one asset, occupy it via lifecycle, then check enrichment."""
		from hamilton_erp import lifecycle
		asset_name = frappe.db.get_value(
			"Venue Asset", {"asset_code": "R001"}, "name"
		)
		lifecycle.start_session_for_asset(asset_name, operator="Administrator")
		frappe.db.commit()
		data = api.get_asset_board_data()
		r001 = next(a for a in data["assets"] if a["name"] == asset_name)
		self.assertEqual(r001["status"], "Occupied")
		self.assertIn("session_start", r001)
		self.assertIsNotNone(r001["session_start"])

	def test_get_asset_board_data_under_one_second(self):
		"""Grok review — single-query perf baseline. 59 assets in < 1.0s."""
		# Occupy a handful so the enrichment branch fires
		from hamilton_erp import lifecycle
		for code in ("R002", "R003", "L001", "L002"):
			name = frappe.db.get_value(
				"Venue Asset", {"asset_code": code}, "name")
			if frappe.db.get_value(
				"Venue Asset", name, "status") == "Available":
				lifecycle.start_session_for_asset(name, operator="Administrator")
		frappe.db.commit()
		t0 = time.perf_counter()
		data = api.get_asset_board_data()
		elapsed = time.perf_counter() - t0
		self.assertEqual(len(data["assets"]), 59)
		self.assertLess(
			elapsed, 1.0,
			f"get_asset_board_data took {elapsed:.3f}s — "
			f"suspect N+1 regression",
		)


class TestBulkMarkClean(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Seed the full 59-asset inventory. Sessions cleaned up in
		# tearDownClass along with assets so we don't leak state into
		# TestSessionNumberGenerator via today's session_number prefix.
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		seed_hamilton_env.execute()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		frappe.cache().delete(f"hamilton:session_seq:{prefix}")
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		# Dirty a few rooms and a few lockers
		from hamilton_erp import lifecycle
		for code in ("R001", "R002", "R003"):
			name = frappe.db.get_value(
				"Venue Asset", {"asset_code": code}, "name")
			if frappe.db.get_value(
				"Venue Asset", name, "status") == "Available":
				lifecycle.start_session_for_asset(
					name, operator="Administrator")
				lifecycle.vacate_session(
					name, operator="Administrator",
					vacate_method="Key Return")
		for code in ("L001", "L002"):
			name = frappe.db.get_value(
				"Venue Asset", {"asset_code": code}, "name")
			if frappe.db.get_value(
				"Venue Asset", name, "status") == "Available":
				lifecycle.start_session_for_asset(
					name, operator="Administrator")
				lifecycle.vacate_session(
					name, operator="Administrator",
					vacate_method="Key Return")
		frappe.db.commit()

	def test_mark_all_clean_rooms_clears_only_rooms(self):
		result = api.mark_all_clean_rooms()
		self.assertGreaterEqual(len(result["succeeded"]), 3)
		# Verify rooms are Available, lockers still Dirty
		r001 = frappe.db.get_value(
			"Venue Asset", {"asset_code": "R001"}, "status")
		l001 = frappe.db.get_value(
			"Venue Asset", {"asset_code": "L001"}, "status")
		self.assertEqual(r001, "Available")
		self.assertEqual(l001, "Dirty")

	def test_mark_all_clean_lockers_clears_only_lockers(self):
		api.mark_all_clean_rooms()  # clean rooms first so we can isolate lockers
		result = api.mark_all_clean_lockers()
		self.assertGreaterEqual(len(result["succeeded"]), 2)
		l001 = frappe.db.get_value(
			"Venue Asset", {"asset_code": "L001"}, "status")
		self.assertEqual(l001, "Available")
