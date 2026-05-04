"""Tests for Task 25 Item 24 — OOS Duration Tracking

Verifies that Asset Status Log correctly tracks:
1. oos_start_time when asset enters Out of Service
2. oos_end_time when asset returns to service
3. oos_duration_minutes calculated from start to end
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, add_to_date


class TestOOSDurationTracking(IntegrationTestCase):
	"""Test OOS duration tracking on Asset Status Log."""

	def setUp(self):
		"""Create a test venue asset."""
		# Clean up any existing test assets
		frappe.db.delete("Asset Status Log", {"venue_asset": ["like", "%TEST-OOS%"]})
		frappe.db.delete("Venue Asset", {"asset_code": "TEST-OOS-001"})
		frappe.db.commit()

		# Create asset without explicit name - let Frappe auto-generate
		asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-OOS-001",
			"asset_name": "Test OOS Locker",
			"asset_category": "Locker",  # Lockers don't require tier validation
			"status": "Available"
		})
		asset.insert(ignore_permissions=True)
		frappe.db.commit()

		# Store the auto-generated name for tests to use
		self.test_asset_name = asset.name

	def test_oos_start_time_populated_when_entering_oos(self):
		"""When asset enters OOS, oos_start_time is set."""
		log = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"previous_status": "Available",
			"new_status": "Out of Service",
			"reason": "Plumbing issue"
		})
		log.insert(ignore_permissions=True)

		# Verify oos_start_time was set
		self.assertIsNotNone(log.oos_start_time,
			"oos_start_time should be set when asset enters OOS")

		# Should be approximately now
		time_diff = (now_datetime() - log.oos_start_time).total_seconds()
		self.assertLess(time_diff, 5,
			"oos_start_time should be set to current time")

	def test_oos_end_time_populated_when_leaving_oos(self):
		"""When asset leaves OOS, oos_end_time is set."""
		# First, create OOS entry
		oos_entry = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"previous_status": "Available",
			"new_status": "Out of Service",
			"reason": "Electrical repair"
		})
		oos_entry.insert(ignore_permissions=True)
		frappe.db.commit()

		# Now return to service
		return_entry = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"previous_status": "Out of Service",
			"new_status": "Available",
			"reason": "Repair completed"
		})
		return_entry.insert(ignore_permissions=True)

		# Verify oos_end_time was set
		self.assertIsNotNone(return_entry.oos_end_time,
			"oos_end_time should be set when asset leaves OOS")

	def test_oos_duration_calculated_correctly(self):
		"""oos_duration_minutes is calculated as end - start in minutes."""
		# Create OOS entry with timestamp 2 hours ago
		two_hours_ago = add_to_date(now_datetime(), hours=-2)
		oos_entry = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"timestamp": two_hours_ago,
			"previous_status": "Available",
			"new_status": "Out of Service",
			"reason": "HVAC maintenance"
		})
		oos_entry.insert(ignore_permissions=True)
		frappe.db.commit()

		# Return to service now
		return_entry = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"previous_status": "Out of Service",
			"new_status": "Available",
			"reason": "HVAC fixed"
		})
		return_entry.insert(ignore_permissions=True)

		# Verify duration is approximately 120 minutes (2 hours)
		self.assertIsNotNone(return_entry.oos_duration_minutes,
			"oos_duration_minutes should be calculated")
		self.assertGreaterEqual(return_entry.oos_duration_minutes, 119,
			"Duration should be at least 119 minutes (allowing 1 min variance)")
		self.assertLessEqual(return_entry.oos_duration_minutes, 121,
			"Duration should be at most 121 minutes (allowing 1 min variance)")

	def test_multiple_oos_cycles_track_correctly(self):
		"""Multiple OOS cycles for same asset track independently."""
		# First OOS cycle
		oos1 = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"timestamp": add_to_date(now_datetime(), hours=-3),
			"previous_status": "Available",
			"new_status": "Out of Service",
			"reason": "First repair"
		})
		oos1.insert(ignore_permissions=True)

		return1 = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"timestamp": add_to_date(now_datetime(), hours=-2),
			"previous_status": "Out of Service",
			"new_status": "Available",
			"reason": "First repair done"
		})
		return1.insert(ignore_permissions=True)
		frappe.db.commit()

		# Second OOS cycle (30 minutes ago to now)
		oos2 = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"timestamp": add_to_date(now_datetime(), minutes=-30),
			"previous_status": "Available",
			"new_status": "Out of Service",
			"reason": "Second repair"
		})
		oos2.insert(ignore_permissions=True)
		frappe.db.commit()

		return2 = frappe.get_doc({
			"doctype": "Asset Status Log",
			"venue_asset": self.test_asset_name,
			"operator": "Administrator",
			"previous_status": "Out of Service",
			"new_status": "Available",
			"reason": "Second repair done"
		})
		return2.insert(ignore_permissions=True)

		# Verify second cycle duration is ~30 minutes (not ~60 from first cycle)
		self.assertIsNotNone(return2.oos_duration_minutes)
		self.assertGreaterEqual(return2.oos_duration_minutes, 29)
		self.assertLessEqual(return2.oos_duration_minutes, 31)

	def tearDown(self):
		"""Clean up test data."""
		# Clean up using the dynamic asset name and asset_code
		if hasattr(self, 'test_asset_name'):
			frappe.db.delete("Asset Status Log", {"venue_asset": self.test_asset_name})
			frappe.db.delete("Venue Asset", {"name": self.test_asset_name"})
		# Also clean up by asset_code in case name wasn't stored
		frappe.db.delete("Venue Asset", {"asset_code": "TEST-OOS-001"})
		frappe.db.commit()
