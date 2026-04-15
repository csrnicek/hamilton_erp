"""Hamilton ERP — Tests for bulk clean catastrophic exception handling

Verifies that _mark_all_clean() in api.py correctly captures per-asset
failures in the `failed` list and still reports successfully cleaned
assets. Identified in the "Known Test Gaps" section of testing_guide.md.

Run via:
  bench --site hamilton-unit-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_bulk_clean
"""
from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp.api import _mark_all_clean
from hamilton_erp.lifecycle import start_session_for_asset, vacate_session


OPERATOR = "Administrator"


def _ensure_walkin():
	if frappe.db.exists("Customer", "Walk-in"):
		return
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": "Walk-in",
		"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
		"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
	}).insert(ignore_permissions=True)


def _make_dirty_asset(name):
	"""Create an asset and run it through Occupied -> Dirty so it's eligible for bulk clean."""
	_ensure_walkin()
	asset = frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"BC-{name[:5].upper()}-{frappe.generate_hash(length=4).upper()}",
		"asset_name": name,
		"asset_category": "Room",
		"asset_tier": "Single Standard",
		"status": "Available",
		"display_order": 9900,
	}).insert(ignore_permissions=True)
	start_session_for_asset(asset.name, operator=OPERATOR)
	vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")
	return asset


class TestBulkCleanExceptionHandling(IntegrationTestCase):
	"""Verify _mark_all_clean captures per-asset errors and reports successes."""

	def test_db_error_captured_in_failed_list(self):
		"""When mark_asset_clean raises OperationalError, it appears in the failed list."""
		asset_a = _make_dirty_asset("Bulk Err A")
		asset_b = _make_dirty_asset("Bulk Err B")

		original_clean = None

		def mock_clean_raises_on_b(asset_name, operator=None, bulk_reason=None):
			"""Raise OperationalError only for asset_b, let asset_a succeed."""
			if asset_name == asset_b.name:
				raise Exception("Simulated DB OperationalError: connection lost")
			return original_clean(asset_name, operator=operator, bulk_reason=bulk_reason)

		# Patch mark_asset_clean inside the api module where _mark_all_clean imports it
		import hamilton_erp.lifecycle as lifecycle_mod
		original_clean = lifecycle_mod.mark_asset_clean

		with patch("hamilton_erp.lifecycle.mark_asset_clean", side_effect=mock_clean_raises_on_b):
			result = _mark_all_clean(category="Room")

		# asset_b's error should be in the failed list
		failed_codes = [f["code"] for f in result["failed"]]
		self.assertIn(asset_b.asset_code, failed_codes,
			"asset_b's error should appear in the failed list")

		# The error message should be captured
		failed_entry = next(f for f in result["failed"] if f["code"] == asset_b.asset_code)
		self.assertIn("connection lost", failed_entry["error"],
			"Error message should be captured in the failed entry")

	def test_successful_assets_reported_before_failure(self):
		"""Assets cleaned before a failure still appear in the succeeded list."""
		asset_a = _make_dirty_asset("Bulk Succ A")
		asset_b = _make_dirty_asset("Bulk Succ B")

		# Determine alphabetical order (lock ordering is by name asc)
		sorted_assets = sorted([asset_a, asset_b], key=lambda a: a.name)
		first_asset = sorted_assets[0]
		second_asset = sorted_assets[1]

		original_clean = None

		def mock_clean_raises_on_second(asset_name, operator=None, bulk_reason=None):
			"""Let the first asset succeed, raise on the second."""
			if asset_name == second_asset.name:
				raise Exception("Simulated catastrophic failure")
			return original_clean(asset_name, operator=operator, bulk_reason=bulk_reason)

		import hamilton_erp.lifecycle as lifecycle_mod
		original_clean = lifecycle_mod.mark_asset_clean

		with patch("hamilton_erp.lifecycle.mark_asset_clean", side_effect=mock_clean_raises_on_second):
			result = _mark_all_clean(category="Room")

		# First asset should be in succeeded
		self.assertIn(first_asset.asset_code, result["succeeded"],
			"First asset (cleaned before failure) should be in succeeded list")

		# Second asset should be in failed
		failed_codes = [f["code"] for f in result["failed"]]
		self.assertIn(second_asset.asset_code, failed_codes,
			"Second asset (which raised) should be in failed list")

		# Both lists should have exactly 1 entry each (for our test assets)
		# Note: other dirty Room assets may exist from dev state, so check >= 1
		self.assertGreaterEqual(len(result["succeeded"]), 1,
			"At least one asset should have succeeded")
		self.assertGreaterEqual(len(result["failed"]), 1,
			"At least one asset should have failed")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# Teardown
# ===========================================================================


def tearDownModule():
	"""Restore dev state wiped by this module's tests."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
