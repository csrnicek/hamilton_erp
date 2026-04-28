import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime


class TestCompAdmissionLog(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_session(self) -> object:
		asset = frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_name": "Test Room CAL1",
				"asset_category": "Room",
				"asset_tier": "Single Standard",
				"status": "Available",
				"display_order": 1,
			}
		).insert(ignore_permissions=True)
		return frappe.get_doc(
			{
				"doctype": "Venue Session",
				"venue_asset": asset.name,
				"status": "Active",
				"session_start": now_datetime(),
				"operator_checkin": "Administrator",
			}
		).insert(ignore_permissions=True)

	def test_insert_comp_log(self):
		session = self._make_session()
		log = frappe.get_doc(
			{
				"doctype": "Comp Admission Log",
				"venue_session": session.name,
				"operator": "Administrator",
				"timestamp": now_datetime(),
				"reason_category": "Manager Decision",
				"reason_note": "VIP guest",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(log.reason_category, "Manager Decision")

	def test_reason_category_is_required(self):
		session = self._make_session()
		doc = frappe.get_doc(
			{
				"doctype": "Comp Admission Log",
				"venue_session": session.name,
				"operator": "Administrator",
				"timestamp": now_datetime(),
				"reason_category": "",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)
