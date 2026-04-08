import frappe
from frappe.tests import IntegrationTestCase


class TestVenueAsset(IntegrationTestCase):
	def _make_asset(self, name: str, category: str = "Room", tier: str = "Standard") -> object:
		return frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_name": name,
				"asset_category": category,
				"asset_tier": tier if category == "Room" else "",
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
		asset = self._make_asset("Test Locker L1", category="Locker", tier="")
		self.assertEqual(asset.asset_category, "Locker")

	def test_room_requires_tier(self):
		doc = frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_name": "Test Room No Tier",
				"asset_category": "Room",
				"asset_tier": "",
				"status": "Available",
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
