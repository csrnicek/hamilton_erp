import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime


class TestVenueSession(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_asset(self) -> object:
		return frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_name": "Test Room VS1",
				"asset_category": "Room",
				"asset_tier": "Standard",
				"status": "Available",
				"display_order": 1,
			}
		).insert(ignore_permissions=True)

	def _make_session(self, asset_name: str) -> object:
		return frappe.get_doc(
			{
				"doctype": "Venue Session",
				"venue_asset": asset_name,
				"status": "Active",
				"session_start": now_datetime(),
				"operator_checkin": "Administrator",
			}
		).insert(ignore_permissions=True)

	def test_insert_session(self):
		asset = self._make_asset()
		session = self._make_session(asset.name)
		self.assertEqual(session.status, "Active")

	def test_identity_method_defaults_to_not_applicable(self):
		asset = self._make_asset()
		session = self._make_session(asset.name)
		self.assertEqual(session.identity_method, "not_applicable")

	def test_forward_compat_fields_present_and_null(self):
		"""H22 — all V5.4 forward-compatibility fields must exist."""
		asset = self._make_asset()
		session = self._make_session(asset.name)
		for field in (
			"member_id",
			"full_name",
			"date_of_birth",
			"membership_status",
			"arrears_amount",
			"arrears_sku",
			"scanner_data",
			"eligibility_snapshot",
			"block_status",
			"terminal_transaction_id",
			"payment_provider",
			"integration_status",
			"payment_gateway_reference",
		):
			self.assertIsNone(
				session.get(field),
				f"Forward-compat field '{field}' should be null at Hamilton.",
			)

	def test_session_end_before_start_raises(self):
		asset = self._make_asset()
		doc = frappe.get_doc(
			{
				"doctype": "Venue Session",
				"venue_asset": asset.name,
				"status": "Active",
				"session_start": now_datetime(),
				"session_end": add_to_date(now_datetime(), hours=-1),
				"operator_checkin": "Administrator",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)
