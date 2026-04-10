import re

import frappe
from frappe.tests import IntegrationTestCase

# Break Frappe's test-record auto-seed cascade at the hamilton_erp boundary.
# Venue Asset.company → Company pulls in ERPNext's entire test-fixture graph
# (Item Price → _Test Customer, etc.), and Venue Session links to
# Sales Invoice / Item / Customer / User which cascade the same way.
# We never touch those in these tests, so tell the generator to skip them.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]


class TestVenueAsset(IntegrationTestCase):
	def _make_asset(self, name: str, category: str = "Room", tier: str = "Single Standard") -> object:
		resolved_tier = "Locker" if category == "Locker" else tier
		asset_code = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper()
		return frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_code": asset_code,
				"asset_name": name,
				"asset_category": category,
				"asset_tier": resolved_tier,
				"status": "Available",
				"display_order": 99,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	# ------------------------------------------------------------------
	# Schema / insert
	# ------------------------------------------------------------------

	def test_insert_room_asset(self):
		asset = self._make_asset("Test Room A1")
		self.assertEqual(asset.status, "Available")
		self.assertEqual(asset.asset_category, "Room")

	def test_insert_locker_asset(self):
		asset = self._make_asset("Test Locker L1", category="Locker")
		self.assertEqual(asset.asset_category, "Locker")

	def test_room_requires_tier(self):
		doc = frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_code": "TEST-ROOM-NO-TIER",
				"asset_name": "Test Room No Tier",
				"asset_category": "Room",
				"asset_tier": "",
				"status": "Available",
				"display_order": 99,
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	# ------------------------------------------------------------------
	# Valid state transitions
	# ------------------------------------------------------------------

	def test_available_to_occupied(self):
		asset = self._make_asset("Test Room Trans1")
		asset.status = "Occupied"
		asset.save()  # must not raise

	def test_occupied_to_dirty(self):
		asset = self._make_asset("Test Room Trans2")
		asset.status = "Occupied"
		asset.save()
		asset.status = "Dirty"
		asset.save()  # must not raise

	def test_dirty_to_available(self):
		asset = self._make_asset("Test Room Trans3")
		asset.status = "Occupied"
		asset.save()
		asset.status = "Dirty"
		asset.save()
		asset.status = "Available"
		asset.save()  # must not raise

	# ------------------------------------------------------------------
	# Invalid state transitions
	# ------------------------------------------------------------------

	def test_available_to_dirty_is_invalid(self):
		asset = self._make_asset("Test Room Invalid1")
		asset.status = "Dirty"
		self.assertRaises(frappe.ValidationError, asset.save)

	def test_occupied_to_available_is_invalid(self):
		asset = self._make_asset("Test Room Invalid2")
		asset.status = "Occupied"
		asset.save()
		asset.status = "Available"
		self.assertRaises(frappe.ValidationError, asset.save)

	# ------------------------------------------------------------------
	# Out of Service transitions (model-based paths 2–5)
	# ------------------------------------------------------------------

	def test_available_to_oos(self):
		asset = self._make_asset("Test Room OOS1")
		asset.status = "Out of Service"
		asset.reason = "Maintenance"
		asset.save()  # must not raise
		self.assertEqual(asset.status, "Out of Service")

	def test_occupied_to_oos(self):
		asset = self._make_asset("Test Room OOS2")
		asset.status = "Occupied"
		asset.save()
		asset.status = "Out of Service"
		asset.reason = "Maintenance"
		asset.save()  # must not raise
		self.assertEqual(asset.status, "Out of Service")

	def test_dirty_to_oos(self):
		asset = self._make_asset("Test Room OOS3")
		asset.status = "Occupied"
		asset.save()
		asset.status = "Dirty"
		asset.save()
		asset.status = "Out of Service"
		asset.reason = "Maintenance"
		asset.save()  # must not raise

	def test_oos_to_available(self):
		asset = self._make_asset("Test Room OOS4")
		asset.status = "Out of Service"
		asset.reason = "Maintenance"
		asset.save()
		asset.status = "Available"
		asset.save()  # must not raise
		self.assertEqual(asset.status, "Available")

	def test_oos_to_occupied_is_invalid(self):
		asset = self._make_asset("Test Room OOS5")
		asset.status = "Out of Service"
		asset.reason = "Maintenance"
		asset.save()
		asset.status = "Occupied"
		self.assertRaises(frappe.ValidationError, asset.save)

	def test_oos_to_dirty_is_invalid(self):
		asset = self._make_asset("Test Room OOS6")
		asset.status = "Out of Service"
		asset.reason = "Maintenance"
		asset.save()
		asset.status = "Dirty"
		self.assertRaises(frappe.ValidationError, asset.save)

	# ------------------------------------------------------------------
	# Locker tier clearing
	# ------------------------------------------------------------------

	def test_locker_requires_locker_tier(self):
		"""Lockers must have tier 'Locker' — any other tier raises."""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-LOCKER-WRONG-TIER",
			"asset_name": "Test Locker Wrong Tier",
			"asset_category": "Locker",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 99,
		})
		self.assertRaises(frappe.ValidationError, doc.insert)
