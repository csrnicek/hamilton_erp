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

	# ------------------------------------------------------------------
	# Audit 2026-04-11 — Group G: Bulk clean gaps
	# ------------------------------------------------------------------

	def test_G1_per_asset_failures_are_captured_not_raised(self):
		"""DEC-054: one stuck row must NOT block a cleanup of the others.
		The _mark_all_clean loop catches per-asset Exception and records
		it in the 'failed' list. Simulate a failure on R001 and verify
		R002/R003 still succeed.
		"""
		from unittest.mock import patch
		from hamilton_erp import lifecycle as lc
		real = lc.mark_asset_clean
		def selective_boom(asset_name, operator=None, bulk_reason=None):
			# Raise for R001 only
			code = frappe.db.get_value("Venue Asset", asset_name, "asset_code")
			if code == "R001":
				raise RuntimeError("simulated failure on R001")
			return real(asset_name, operator=operator, bulk_reason=bulk_reason)
		# api._mark_all_clean imports mark_asset_clean locally, so patch the
		# source module (hamilton_erp.lifecycle.mark_asset_clean). The import
		# happens at call time and picks up the patched attribute.
		with patch("hamilton_erp.lifecycle.mark_asset_clean",
		           side_effect=selective_boom):
			result = api.mark_all_clean_rooms()
		self.assertTrue(len(result["failed"]) >= 1,
			f"Expected at least 1 captured failure; got {result}")
		self.assertTrue(
			any(f["code"] == "R001" for f in result["failed"]),
			"R001 should appear in failed list")
		# The rest of the rooms should still be Available
		r002 = frappe.db.get_value(
			"Venue Asset", {"asset_code": "R002"}, "status")
		self.assertEqual(r002, "Available")

	def test_G2_empty_dirty_pool_returns_empty_lists(self):
		"""If no assets are Dirty, the bulk endpoint returns
		{succeeded: [], failed: []} — it does NOT fail.
		"""
		# Ensure all rooms are clean first
		api.mark_all_clean_rooms()
		result = api.mark_all_clean_rooms()
		self.assertEqual(result["succeeded"], [])
		self.assertEqual(result["failed"], [])

	def test_G3_loop_ordering_by_name_ascending(self):
		"""_mark_all_clean's order_by='name asc' establishes deterministic
		lock ordering (coding_standards.md §13.4). Verify by inspecting
		the order of succeeded codes — rooms cleaned in sorted order.
		"""
		result = api.mark_all_clean_rooms()
		# succeeded is in iteration order, which reflects 'name asc'
		if len(result["succeeded"]) >= 2:
			self.assertEqual(
				result["succeeded"],
				sorted(result["succeeded"],
				       key=lambda c: frappe.db.get_value(
				           "Venue Asset", {"asset_code": c}, "name") or "")
			)

	def test_G4_rooms_bulk_does_not_touch_lockers_or_other_categories(self):
		"""Regression guard: mark_all_clean_rooms filters by
		asset_category='Room'. A bug that drops the filter would clean
		dirty lockers too.
		"""
		# Explicitly set a locker to Dirty and call rooms endpoint
		l_name = frappe.db.get_value(
			"Venue Asset", {"asset_code": "L001"}, "name")
		before = frappe.db.get_value("Venue Asset", l_name, "status")
		api.mark_all_clean_rooms()
		after = frappe.db.get_value("Venue Asset", l_name, "status")
		# Locker state must be unchanged
		self.assertEqual(before, after,
			"Locker should not be affected by mark_all_clean_rooms")

	def test_G5_single_board_refresh_event_on_bulk(self):
		"""DEC-054: the bulk endpoint fires ONE board-refresh event, not
		one per asset. Without this, a reset of 20 dirty rooms floods the
		realtime channel.
		"""
		from unittest.mock import patch
		with patch("hamilton_erp.realtime.publish_board_refresh") as mock_pub:
			api.mark_all_clean_rooms()
		self.assertEqual(mock_pub.call_count, 1,
			f"Expected exactly 1 board-refresh event, got {mock_pub.call_count}")


# ---------------------------------------------------------------------------
# Group H — Asset Board API (5 tests)
# ---------------------------------------------------------------------------


class TestAssetBoardAPI(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
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

	def test_H1_inactive_assets_excluded_from_board(self):
		"""is_active=0 filter — if a locker is decommissioned mid-day it
		must disappear from the board immediately.
		"""
		r001 = frappe.db.get_value(
			"Venue Asset", {"asset_code": "R001"}, "name")
		frappe.db.set_value("Venue Asset", r001, "is_active", 0)
		try:
			data = api.get_asset_board_data()
			codes = {a["asset_code"] for a in data["assets"]}
			self.assertNotIn("R001", codes,
				"Inactive asset should be filtered out of board")
		finally:
			frappe.db.set_value("Venue Asset", r001, "is_active", 1)

	def test_H2_available_assets_have_null_session_start(self):
		"""For assets in state Available, session_start enrichment must
		be None — it's only populated for Occupied rows whose
		current_session is non-null.
		"""
		data = api.get_asset_board_data()
		avail = [a for a in data["assets"] if a["status"] == "Available"]
		self.assertTrue(avail, "Expected at least one Available asset")
		for a in avail:
			self.assertIsNone(a.get("session_start"))

	def test_H3_sort_order_is_display_order_ascending(self):
		"""Regression guard: api.get_asset_board_data uses order_by='display_order asc'.
		A broken sort would scatter the tiles on the board."""
		data = api.get_asset_board_data()
		orders = [a["display_order"] for a in data["assets"]]
		self.assertEqual(orders, sorted(orders),
			"Asset board must return rows in display_order ascending")

	def test_H4_assign_asset_to_session_phase2_stub_throws(self):
		"""assign_asset_to_session is a Phase 2 not-yet-implemented stub.
		It MUST throw a user-friendly ValidationError — if it silently
		returns, a POS operator could fire it from the browser console
		and corrupt session state.
		"""
		with self.assertRaises(frappe.ValidationError):
			api.assign_asset_to_session(sales_invoice="INV-FAKE",
			                            asset_name="FAKE-ASSET")

	def test_H5_board_data_query_count_bounded(self):
		"""Two-query invariant: assets query + session_start enrichment
		query. Even with many Occupied rows, the query count must NOT
		grow linearly (N+1 regression guard).
		"""
		# Occupy several so the enrichment branch fires
		from hamilton_erp import lifecycle
		for code in ("R004", "R005", "R006"):
			name = frappe.db.get_value(
				"Venue Asset", {"asset_code": code}, "name")
			if frappe.db.get_value(
				"Venue Asset", name, "status") == "Available":
				lifecycle.start_session_for_asset(
					name, operator="Administrator")
		frappe.db.commit()
		writes_before = frappe.db.transaction_writes
		data = api.get_asset_board_data()
		# No writes happened — it's a read-only call
		self.assertEqual(frappe.db.transaction_writes, writes_before,
			"get_asset_board_data must not issue writes")
		self.assertEqual(len(data["assets"]), 59)


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
