"""Unit-style tests for hamilton_erp.lifecycle helper functions.

Task 3 covers only the pure helpers — transition validation.
Tasks 4–8 add integration tests against the real DB for each
whitelisted lifecycle function.

Note: this module lives at the package root (same level as api.py,
locks.py, test_locks.py). We intentionally do NOT set
IGNORE_TEST_RECORD_DEPENDENCIES — Frappe v16's IntegrationTestCase
can't auto-detect cls.doctype for package-root modules, so it skips
test-record generation entirely and there's no cascade to break.
"""
import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle


class TestLifecycleHelpers(IntegrationTestCase):
	def test_valid_transitions_map(self):
		t = lifecycle.VALID_TRANSITIONS
		self.assertIn("Occupied", t["Available"])
		self.assertIn("Dirty", t["Occupied"])
		self.assertIn("Available", t["Dirty"])
		self.assertIn("Out of Service", t["Available"])
		self.assertIn("Available", t["Out of Service"])

	def test_require_transition_passes_on_valid(self):
		row = {"name": "VA-0001", "status": "Available", "version": 0}
		lifecycle._require_transition(row, current="Available",
		                              target="Occupied", asset_name="VA-0001")

	def test_require_transition_throws_on_mismatch(self):
		row = {"name": "VA-0001", "status": "Dirty", "version": 0}
		with self.assertRaises(frappe.ValidationError):
			lifecycle._require_transition(row, current="Available",
			                              target="Occupied", asset_name="VA-0001")

	def test_require_oos_entry_throws_on_already_oos(self):
		row = {"name": "VA-0001", "status": "Out of Service", "version": 0}
		with self.assertRaises(frappe.ValidationError):
			lifecycle._require_oos_entry(row, asset_name="VA-0001")

	def test_require_oos_entry_passes_on_other_states(self):
		for status in ("Available", "Occupied", "Dirty"):
			row = {"name": "VA-0001", "status": status, "version": 0}
			lifecycle._require_oos_entry(row, asset_name="VA-0001")  # no raise

	def test_log_helper_skipped_in_test_flag(self):
		"""Grok review: Asset Status Log helper short-circuits when in_test is set."""
		prev_flag = frappe.flags.in_test
		frappe.flags.in_test = True
		try:
			result = lifecycle._make_asset_status_log(
				asset_name="VA-0001",
				previous="Available",
				new_status="Occupied",
				reason=None,
				operator="test@example.com",
				venue_session=None,
			)
			self.assertIsNone(result)
		finally:
			frappe.flags.in_test = prev_flag
