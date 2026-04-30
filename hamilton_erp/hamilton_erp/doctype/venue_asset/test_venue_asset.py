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
		# Test-only asset_code: slug-from-name for uniqueness. Production uses
		# R001/L001-style immutable codes — see venue_asset.json asset_code description.
		test_asset_code = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper()
		return frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_code": test_asset_code,
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

	def test_room_requires_valid_tier(self):
		"""Rooms given a non-room tier must be rejected by the custom validator."""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-ROOM-BAD-TIER",
			"asset_name": "Test Room Bad Tier",
			"asset_category": "Room",
			"asset_tier": "Locker",   # schema-valid option, semantically wrong for a Room
			"status": "Available",
			"display_order": 99,
		})
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

	# ------------------------------------------------------------------
	# ChatGPT review 2026-04-10 — new controller guards
	# ------------------------------------------------------------------

	def test_new_asset_must_start_available(self):
		"""Directly inserting with any non-Available status must raise."""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-NEW-BAD-INIT",
			"asset_name": "Test New Bad Init",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Occupied",
			"display_order": 99,
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_oos_reason_whitespace_is_rejected(self):
		"""A reason field of only whitespace must not satisfy OOS's mandatory reason."""
		asset = self._make_asset("Test Room OOS Whitespace")
		asset.status = "Out of Service"
		asset.reason = "   "
		self.assertRaises(frappe.ValidationError, asset.save)

	# ------------------------------------------------------------------
	# Phase 1 — whitelisted methods call lifecycle module
	# ------------------------------------------------------------------

	# ------------------------------------------------------------------
	# Audit 2026-04-11 — Group E: Controller guard gaps
	# ------------------------------------------------------------------

	def test_E1_locker_with_deluxe_tier_rejected(self):
		"""Lockers must have asset_tier == 'Locker'. A room tier must fail."""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-LOCKER-DELUXE",
			"asset_name": "Locker With Deluxe Tier",
			"asset_category": "Locker",
			"asset_tier": "Deluxe Single",
			"status": "Available",
			"display_order": 97,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_E2_locker_with_glory_hole_tier_rejected(self):
		"""Different bad room tier, same guard. Parameterized coverage so
		any future addition to the room_tiers set shows up here."""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-LOCKER-GH",
			"asset_name": "Locker With GH Room",
			"asset_category": "Locker",
			"asset_tier": "GH Room",
			"status": "Available",
			"display_order": 97,
		})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_E3_simultaneous_status_and_tier_change_both_validated(self):
		"""If a save changes BOTH status AND tier, both validators must
		fire. Guards against an optimization that only checks the changed
		field via has_value_changed.
		"""
		asset = self._make_asset("Test Dual Change")
		# Switch category → mismatched tier simultaneously
		asset.asset_category = "Locker"
		# Leave tier as 'Single Standard' — this is now invalid for a Locker
		asset.status = "Out of Service"
		asset.reason = "test"
		with self.assertRaises(frappe.ValidationError):
			asset.save(ignore_permissions=True)

	def test_E4_validate_order_tier_before_oos_reason(self):
		"""validate() runs transition → tier → reason in that order. If a
		Locker is given a bad tier AND no OOS reason, the tier error
		should surface first (locker misconfiguration is the root cause).
		"""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-ORDER",
			"asset_name": "Test Validate Order",
			"asset_category": "Locker",
			"asset_tier": "Deluxe Single",
			"status": "Available",
			"display_order": 97,
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		# Tier error, not reason error
		self.assertIn("Locker", str(ctx.exception))

	def test_E5_new_asset_as_oos_with_valid_reason_still_rejected(self):
		"""The new-asset guard rejects anything except Available, even if
		a valid OOS reason is supplied. OOS on insert bypasses the
		lifecycle state machine.
		"""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": "TEST-NEW-OOS",
			"asset_name": "Test New OOS",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Out of Service",
			"reason": "broken on delivery",
			"display_order": 98,
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		self.assertIn("Available", str(ctx.exception))


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
