"""Tests for the DEC-098 receipt-printing pipeline.

Pins the contracts that matter operationally:

  1. Test-mode escape hatch: ``frappe.in_test`` short-circuits the
     dispatch so the test suite does not depend on a physical printer.
  2. GST/HST validation: blank ``gst_hst_registration_number`` blocks
     the receipt render (and therefore the sale).
  3. Printer dispatch failure bubbles out of ``print_cash_receipt``
     so the surrounding Frappe transaction rolls back.
  4. Reprint endpoint role gate: Operator forbidden, Manager allowed.
  5. End-to-end "no receipt = no sale": when the printer dispatch
     raises inside ``submit_retail_sale``, the SI submit is reversed
     by the request-level rollback.

Test-mode behaviour:
  ``frappe.in_test`` is True inside ``IntegrationTestCase``. Most tests
  rely on the natural short-circuit; the failure-path tests (#2, #3, #5)
  set ``frappe.flags.in_test = False`` for the duration of the test so
  the real code path executes and the failure surfaces. The flag is
  restored in ``tearDown`` to keep test-suite isolation intact.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp.api import HAMILTON_POS_PROFILE, submit_retail_sale
from hamilton_erp.printing import (
	_render_receipt,
	print_cash_receipt,
	reprint_cash_receipt,
)
from hamilton_erp.setup.install import HAMILTON_WAREHOUSE_BASE


def _hamilton_company() -> str | None:
	pinned = frappe.conf.get("hamilton_company")
	if pinned and frappe.db.exists("Company", pinned):
		return pinned
	for candidate in ("Club Hamilton", "Hamilton", "Hamilton Club"):
		if frappe.db.exists("Company", candidate):
			return candidate
	matches = frappe.get_all(
		"Company",
		filters={"company_name": ["like", "%Hamilton%"]},
		fields=["name"],
		limit=1,
	)
	return matches[0]["name"] if matches else None


class TestPrintCashReceiptInTestMode(IntegrationTestCase):
	"""Pin the dev escape hatch — frappe.in_test → no-op (DEC-098)."""

	def test_print_cash_receipt_in_test_mode_is_no_op(self):
		"""When frappe.in_test=True, print_cash_receipt returns a logged
		no-op without touching the network or the print format. The SI
		argument is intentionally a non-existent docname — the short-
		circuit must fire BEFORE any DB / render lookup.
		"""
		# IntegrationTestCase sets frappe.flags.in_test=True automatically;
		# assert that explicitly so this test pins the precondition.
		self.assertTrue(getattr(frappe, "in_test", False),
			"frappe.in_test must be True inside IntegrationTestCase.")
		result = print_cash_receipt("SI-NONEXISTENT-FOR-NO-OP-TEST")
		self.assertEqual(result, {"status": "skipped", "reason": "test_mode"})


class TestPrintCashReceiptValidation(IntegrationTestCase):
	"""GST/HST validation + dispatch failure bubble-up (DEC-098)."""

	def setUp(self):
		super().setUp()
		# Most tests in this class need the real (non-test-mode) code
		# path to run. Save and restore the flag so subsequent tests in
		# the suite are not affected.
		self._saved_in_test = frappe.flags.in_test
		frappe.flags.in_test = False
		# Snapshot Hamilton Settings so we can restore in tearDown.
		settings = frappe.get_single("Hamilton Settings")
		self._saved = {
			"receipt_printer_enabled": settings.receipt_printer_enabled,
			"receipt_printer_ip": settings.receipt_printer_ip,
			"gst_hst_registration_number": settings.gst_hst_registration_number,
		}

	def tearDown(self):
		frappe.flags.in_test = self._saved_in_test
		settings = frappe.get_single("Hamilton Settings")
		for k, v in self._saved.items():
			settings.set(k, v)
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("Hamilton Settings", "Hamilton Settings")
		super().tearDown()

	def _set_settings(self, **kwargs) -> None:
		settings = frappe.get_single("Hamilton Settings")
		for k, v in kwargs.items():
			settings.set(k, v)
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("Hamilton Settings", "Hamilton Settings")

	def test_print_cash_receipt_blocks_on_blank_gst_hst(self):
		"""Blank gst_hst_registration_number → ValidationError (DEC-097)."""
		self._set_settings(
			receipt_printer_enabled=1,
			receipt_printer_ip="10.0.0.99",
			gst_hst_registration_number="",
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			# _render_receipt is the validation site; calling it directly
			# isolates the assertion from network / dispatch concerns.
			_render_receipt("SI-DOES-NOT-MATTER-FOR-VALIDATION")
		self.assertIn("GST/HST", str(ctx.exception))

	def test_print_cash_receipt_queues_on_printer_dispatch_failure(self):
		"""Per DEC-098 Option B (revised 2026-05-04): dispatch failure
		does NOT throw and does NOT roll back the sale. Instead,
		``print_cash_receipt`` catches the exception, logs an Error Log
		entry titled ``Receipt Print Retry Queue`` (the Phase-1 queue),
		and returns ``{"status": "queued_for_retry", ...}`` so the caller
		(``submit_retail_sale``) commits the sale normally.

		This was originally written as ``test_..._blocks_on_dispatch_failure``
		to assert the opposite contract; the DEC-098 amendment overruled
		that policy because the front desk cannot defer a paying customer
		mid-checkout while waiting for a printer to come back online.
		"""
		self._set_settings(
			receipt_printer_enabled=1,
			receipt_printer_ip="10.0.0.99",
			gst_hst_registration_number="105204077RT0001",
		)
		with patch("hamilton_erp.printing._render_receipt", return_value="RECEIPT"):
			with patch(
				"hamilton_erp.printing._dispatch_to_printer",
				side_effect=frappe.ValidationError("Receipt printer dispatch failed: simulated"),
			):
				with patch("hamilton_erp.printing.frappe.log_error") as log_mock:
					result = print_cash_receipt("SI-DISPATCH-FAILURE-TEST")
		self.assertEqual(result["status"], "queued_for_retry")
		self.assertIn("dispatch failed", result["reason"])
		# Pin the retry-queue Error Log title so the Phase-2 worker can
		# query for it.
		log_mock.assert_called_once()
		_, kwargs = log_mock.call_args
		self.assertEqual(kwargs["title"], "Receipt Print Retry Queue")
		self.assertIn("SI-DISPATCH-FAILURE-TEST", kwargs["message"])


class TestReprintEndpointRoleGate(IntegrationTestCase):
	"""Reprint is Manager / Admin only (DEC-098 role policy)."""

	def setUp(self):
		super().setUp()
		self._saved_user = frappe.session.user
		# Make sure the test users exist with the right roles. Hamilton
		# Operator must NOT have Hamilton Manager or Hamilton Admin.
		self._operator = self._ensure_user(
			"hamilton-op-reprint-test@example.com", ["Hamilton Operator"]
		)
		self._manager = self._ensure_user(
			"hamilton-mgr-reprint-test@example.com", ["Hamilton Manager"]
		)

	def tearDown(self):
		frappe.set_user(self._saved_user)
		super().tearDown()

	def _ensure_user(self, email: str, roles: list[str]) -> str:
		if not frappe.db.exists("User", email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"enabled": 1,
				"user_type": "System User",
			})
			user.flags.ignore_permissions = True
			user.insert(ignore_permissions=True)
		# Re-fetch and ensure required roles are attached.
		user = frappe.get_doc("User", email)
		current_roles = {r.role for r in user.roles}
		for role in roles:
			if role not in current_roles:
				user.append("roles", {"role": role})
		user.flags.ignore_permissions = True
		user.save(ignore_permissions=True)
		return email

	def test_reprint_endpoint_role_gate(self):
		"""Operator → PermissionError; Manager → succeeds (no-op in test mode)."""
		# Operator path — permission denied.
		frappe.set_user(self._operator)
		with self.assertRaises(frappe.PermissionError):
			reprint_cash_receipt(sales_invoice="ANY-SI-FOR-PERM-CHECK")

		# Manager path — sales_invoice param validation runs after the
		# role check. Use a known-bad name to avoid creating a fixture
		# Sales Invoice; the test asserts that the call gets PAST the
		# role check (a different error class than PermissionError).
		frappe.set_user(self._manager)
		with self.assertRaises(frappe.ValidationError) as ctx:
			reprint_cash_receipt(sales_invoice="SI-DOES-NOT-EXIST-XYZ")
		self.assertNotIsInstance(ctx.exception, frappe.PermissionError)
		self.assertIn("does not exist", str(ctx.exception))


class TestSubmitRetailSaleRollsBackOnPrintFailure(IntegrationTestCase):
	"""End-to-end: print failure inside submit_retail_sale must roll
	back the SI submit (no receipt = no sale, DEC-098)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _hamilton_company()
		if not cls.company:
			return
		cls.abbr = frappe.db.get_value("Company", cls.company, "abbr")
		cls.warehouse = f"{HAMILTON_WAREHOUSE_BASE} - {cls.abbr}"

	def setUp(self):
		super().setUp()
		if not _hamilton_company():
			self.skipTest("Hamilton company not seeded.")
		self._saved_in_test = frappe.flags.in_test
		# Seed stock for the test SKU.
		if not frappe.db.exists("Item", "WAT-500"):
			self.skipTest("WAT-500 not seeded.")
		se = frappe.new_doc("Stock Entry")
		se.update({
			"company": self.company,
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
		})
		se.append("items", {
			"item_code": "WAT-500",
			"qty": 5,
			"t_warehouse": self.warehouse,
			"basic_rate": 1.00,
		})
		se.insert(ignore_permissions=True)
		se.submit()

	def tearDown(self):
		frappe.flags.in_test = self._saved_in_test
		super().tearDown()

	def test_submit_retail_sale_completes_when_print_queued_for_retry(self):
		"""Per DEC-098 Option B (revised 2026-05-04): a printer dispatch
		failure is soft — ``print_cash_receipt`` returns
		``{"status": "queued_for_retry"}`` instead of throwing — so
		``submit_retail_sale`` MUST commit the sale normally.

		Originally written as ``..._rolls_back_on_print_failure`` to assert
		that the throw propagates and Frappe's request-level rollback
		reverses the SI submit. The DEC-098 amendment overruled that
		policy: cash sales must always complete at the front desk; the
		receipt obligation is satisfied async via the retry queue or
		manually via reprint.
		"""
		# Disable the test-mode short-circuit so the real path runs.
		frappe.flags.in_test = False

		queued_status = {
			"status": "queued_for_retry",
			"reason": "simulated dispatch failure",
			"ip": "10.0.0.99",
		}
		with patch(
			"hamilton_erp.printing.print_cash_receipt",
			return_value=queued_status,
		):
			result = submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
				cash_received=10.00,
			)
		# Sale completed — submit_retail_sale returns the SI envelope.
		self.assertEqual(result.get("status"), "ok")
		self.assertTrue(result.get("invoice"))
		# Defensive sanity: the patched submit_retail_sale was reached
		# (POS Profile + Walk-in customer prerequisites are met).
		self.assertTrue(frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE))
