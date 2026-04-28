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

	def test_before_insert_sets_session_number(self):
		"""Task 10: VenueSession.before_insert must auto-populate session_number
		via lifecycle._next_session_number() when the caller doesn't pass one.

		Asserts not just presence but full DEC-033 format: `{d}-{m}-{y}---{NNN}`
		with day/month NOT zero-padded and the trailing sequence IS zero-padded
		to 3 digits. A naive `"---" in session.session_number` would pass for
		a value like `"---"` alone; the regex catches that regression class.
		"""
		asset = self._make_asset()
		# Insert via _make_session which does NOT pass session_number — the
		# before_insert hook should populate it from the Redis INCR generator.
		session = self._make_session(asset.name)
		self.assertTrue(
			session.session_number,
			"Expected session_number to be auto-populated by before_insert",
		)
		# DEC-033 format: one or more digits for d, m, y, then '---', then
		# exactly 4 digits for the sequence. Day/month are NOT zero-padded.
		# Task 11 (2026-04-10) widened the sequence from 3 to 4 digits.
		self.assertRegex(
			session.session_number,
			r"^\d+-\d+-\d+---\d{4}$",
			f"session_number {session.session_number!r} does not match DEC-033 format",
		)

	def test_sales_invoice_field_is_read_only(self):
		"""DEC-055 §2 — sales_invoice must be read_only on the form."""
		meta = frappe.get_meta("Venue Session")
		field = meta.get_field("sales_invoice")
		self.assertEqual(field.read_only, 1)
