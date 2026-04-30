"""Backend tests for the V9.1 Phase 2 retail cart → Sales Invoice flow.

Tests cover:
  - The accounting seed creates Hamilton company + warehouse + cost center +
    HST account + 4260 Beverage / 4210 Food income accounts + Sales Taxes
    Template + POS Profile "Hamilton Front Desk".
  - ``submit_retail_sale`` creates a POS Sales Invoice with the expected
    shape (``is_pos=1``, ``update_stock=1``, customer=Walk-in, taxes
    applied, payment captured, change computed).
  - Stock decrement happens automatically via the Stock Ledger Entry that
    submission generates.
  - Validation rejects empty cart, insufficient cash, missing items.

Each test seeds its own stock via Stock Entry (Material Receipt) and uses
``frappe.db.rollback()`` via IntegrationTestCase's transactional wrapping
so test pollution is contained.
"""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from hamilton_erp.api import HAMILTON_POS_PROFILE, submit_retail_sale
from hamilton_erp.setup.install import (
	HAMILTON_COST_CENTER_BASE,
	HAMILTON_HST_ACCOUNT_BASE,
	HAMILTON_INCOME_ACCOUNT_BEVERAGE,
	HAMILTON_INCOME_ACCOUNT_FOOD,
	HAMILTON_TAX_TEMPLATE_BASE,
	HAMILTON_WAREHOUSE_BASE,
)


def _hamilton_company() -> str | None:
	"""Resolve the Hamilton company name using the same logic as the seed."""
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


class TestHamiltonAccountingSeed(IntegrationTestCase):
	"""Verify the install/migrate seed creates all retail accounting prereqs."""

	def test_hamilton_company_exists(self):
		"""A Hamilton-named (or pinned) company exists after install."""
		company = _hamilton_company()
		self.assertIsNotNone(company,
			"No Hamilton company found — accounting seed did not run.")

	def test_hamilton_warehouse_exists(self):
		company = _hamilton_company()
		self.assertIsNotNone(company)
		abbr = frappe.db.get_value("Company", company, "abbr")
		warehouse = f"{HAMILTON_WAREHOUSE_BASE} - {abbr}"
		self.assertTrue(
			frappe.db.exists("Warehouse", warehouse),
			f"Warehouse {warehouse!r} not seeded.",
		)

	def test_warehouse_type_transit_seeded(self):
		"""ERPNext's ``Company.create_default_warehouse`` references
		Warehouse Type "Transit" when creating the "Goods In Transit"
		warehouse on Company insert. ERPNext does NOT seed this Warehouse
		Type in its own after_install (the setup wizard creates it).
		Hamilton must seed it explicitly in ``_ensure_erpnext_prereqs`` or
		fresh-install Company creation fails with
		``LinkValidationError: Could not find Warehouse Type: Transit``.

		Pinning this contract here so any future cleanup that "removes
		seemingly unused records from _ensure_erpnext_prereqs" surfaces as
		a test failure, not a CI fresh-install crash.
		"""
		self.assertTrue(
			frappe.db.exists("Warehouse Type", "Transit"),
			"Warehouse Type 'Transit' must be seeded by "
			"_ensure_erpnext_prereqs — required by ERPNext's Company "
			"creation hook for the 'Goods In Transit' warehouse.",
		)

	def test_stock_entry_type_material_receipt_seeded(self):
		"""Stock Entry Type "Material Receipt" must exist or
		``_seed_stock`` (used by every TestSubmitRetailSale and
		TestSubmitRetailSaleHardening test) fails with
		``LinkValidationError: Could not find Stock Entry Type:
		Material Receipt``.

		ERPNext's setup wizard seeds the standard Stock Entry Types via
		``erpnext/setup/setup_wizard/operations/install_fixtures.py``, but
		Hamilton skips the wizard. Same install-time gap class as
		Warehouse Type "Transit" — fixed by explicit seeding in
		``_ensure_erpnext_prereqs``.
		"""
		self.assertTrue(
			frappe.db.exists("Stock Entry Type", "Material Receipt"),
			"Stock Entry Type 'Material Receipt' must be seeded by "
			"_ensure_erpnext_prereqs — required by ``_seed_stock`` test "
			"helpers and any future Hamilton flow that creates Stock Entry "
			"records of type Material Receipt.",
		)

	def test_hamilton_price_list_seeded(self):
		"""Price List "Hamilton Standard Selling" must exist (CAD,
		selling). Fifth in the fresh-install gap family — but with a
		Hamilton-specific name to avoid collision with ERPNext's own
		test fixtures, which insert a "Standard Selling" Price List with
		INR currency. The Hamilton-specific name lets both coexist.
		``_ensure_pos_profile`` sets ``selling_price_list = "Hamilton
		Standard Selling"`` on the POS Profile so ``submit_retail_sale``
		reads it from there directly (no string-literal fallback).
		"""
		from hamilton_erp.setup.install import HAMILTON_PRICE_LIST_NAME
		self.assertTrue(
			frappe.db.exists("Price List", HAMILTON_PRICE_LIST_NAME),
			f"Price List {HAMILTON_PRICE_LIST_NAME!r} must be seeded by "
			"_ensure_erpnext_prereqs.",
		)
		# Verify it's selling-enabled and CAD
		pl = frappe.get_doc("Price List", HAMILTON_PRICE_LIST_NAME)
		self.assertEqual(pl.currency, "CAD")
		self.assertEqual(int(pl.selling), 1)
		self.assertEqual(int(pl.enabled), 1)

	def test_pos_profile_uses_hamilton_price_list(self):
		"""POS Profile "Hamilton Front Desk" must have
		``selling_price_list = "Hamilton Standard Selling"`` so
		``submit_retail_sale`` reads from the profile and doesn't need
		the (now-removed) string-literal fallback to "Standard Selling".
		"""
		from hamilton_erp.setup.install import (
			HAMILTON_POS_PROFILE_NAME,
			HAMILTON_PRICE_LIST_NAME,
		)
		self.assertTrue(frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE_NAME))
		current = frappe.db.get_value(
			"POS Profile", HAMILTON_POS_PROFILE_NAME, "selling_price_list"
		)
		self.assertEqual(current, HAMILTON_PRICE_LIST_NAME,
			f"POS Profile selling_price_list should be "
			f"{HAMILTON_PRICE_LIST_NAME!r}, got {current!r}.")

	def test_mode_of_payment_cash_seeded(self):
		"""Mode of Payment "Cash" must exist or every downstream
		seeding helper bails silently and the POS Profile never gets
		created. ERPNext's setup wizard seeds it via
		``install_fixtures.py``; Hamilton skips the wizard. Fourth in
		the Warehouse Type "Transit" / Stock Entry Type "Material
		Receipt" / Fiscal Year / Mode of Payment "Cash" fresh-install
		gap family.
		"""
		self.assertTrue(
			frappe.db.exists("Mode of Payment", "Cash"),
			"Mode of Payment 'Cash' must be seeded by "
			"_ensure_erpnext_prereqs — required by "
			"_ensure_cash_mode_of_payment_account and _ensure_pos_profile, "
			"both of which silently bail without it (cascading to a "
			"missing POS Profile and submit_retail_sale errors).",
		)

	def test_fiscal_year_covers_today(self):
		"""A Fiscal Year covering today's date must exist or every
		transaction (Sales Invoice, Stock Entry, etc.) raises
		``FiscalYearError``. ERPNext's setup wizard creates one; Hamilton
		skips the wizard. Third in the Warehouse Type "Transit" / Stock
		Entry Type "Material Receipt" / Fiscal Year fresh-install gap
		family — fixed by explicit seeding in ``_ensure_erpnext_prereqs``.
		"""
		from datetime import date
		today_iso = date.today().strftime("%Y-%m-%d")
		covering = frappe.get_all(
			"Fiscal Year",
			filters={
				"year_start_date": ["<=", today_iso],
				"year_end_date": [">=", today_iso],
			},
			fields=["name"],
			limit=1,
		)
		self.assertTrue(
			covering,
			f"No Fiscal Year covers {today_iso}. ERPNext requires an "
			"active Fiscal Year for any transaction's posting_date. "
			"_ensure_erpnext_prereqs must seed the current calendar year.",
		)

	def test_hamilton_cost_center_exists(self):
		company = _hamilton_company()
		self.assertIsNotNone(company)
		abbr = frappe.db.get_value("Company", company, "abbr")
		cost_center = f"{HAMILTON_COST_CENTER_BASE} - {abbr}"
		self.assertTrue(
			frappe.db.exists("Cost Center", cost_center),
			f"Cost Center {cost_center!r} not seeded.",
		)

	def test_qbo_mirrored_income_accounts_exist(self):
		"""4260 Beverage and 4210 Food (QBO mirror) are seeded as income accounts."""
		company = _hamilton_company()
		self.assertIsNotNone(company)
		abbr = frappe.db.get_value("Company", company, "abbr")
		for base in (HAMILTON_INCOME_ACCOUNT_BEVERAGE, HAMILTON_INCOME_ACCOUNT_FOOD):
			full = f"{base} - {abbr}"
			self.assertTrue(
				frappe.db.exists("Account", full),
				f"Account {full!r} not seeded.",
			)
			self.assertEqual(
				frappe.db.get_value("Account", full, "root_type"), "Income",
				f"{full} should have root_type='Income'.",
			)

	def test_gst_hst_payable_exists_with_tax_type(self):
		"""GST/HST Payable is a Tax-type account with rate 13."""
		company = _hamilton_company()
		self.assertIsNotNone(company)
		abbr = frappe.db.get_value("Company", company, "abbr")
		full = f"{HAMILTON_HST_ACCOUNT_BASE} - {abbr}"
		self.assertTrue(
			frappe.db.exists("Account", full),
			f"Account {full!r} not seeded.",
		)
		acc = frappe.get_doc("Account", full)
		self.assertEqual(acc.account_type, "Tax")
		self.assertEqual(acc.root_type, "Liability")
		self.assertAlmostEqual(float(acc.tax_rate or 0), 13.0)

	def test_ontario_hst_template_exists(self):
		"""Sales Taxes and Charges Template "Ontario HST 13%" is seeded."""
		company = _hamilton_company()
		self.assertIsNotNone(company)
		abbr = frappe.db.get_value("Company", company, "abbr")
		template_name = f"{HAMILTON_TAX_TEMPLATE_BASE} - {abbr}"
		self.assertTrue(
			frappe.db.exists("Sales Taxes and Charges Template", template_name),
			f"Sales Taxes Template {template_name!r} not seeded.",
		)
		template = frappe.get_doc("Sales Taxes and Charges Template", template_name)
		self.assertEqual(len(template.taxes), 1)
		self.assertEqual(template.taxes[0].rate, 13)
		self.assertEqual(
			template.taxes[0].account_head,
			f"{HAMILTON_HST_ACCOUNT_BASE} - {abbr}",
		)

	def test_pos_profile_hamilton_front_desk_exists(self):
		"""POS Profile "Hamilton Front Desk" is seeded with warehouse + tax template."""
		self.assertTrue(
			frappe.db.exists("POS Profile", HAMILTON_POS_PROFILE),
			f"POS Profile {HAMILTON_POS_PROFILE!r} not seeded.",
		)
		profile = frappe.get_doc("POS Profile", HAMILTON_POS_PROFILE)
		self.assertEqual(profile.update_stock, 1)
		# At least one Cash payment method
		cash_payments = [p for p in profile.payments if p.mode_of_payment == "Cash"]
		self.assertEqual(len(cash_payments), 1)
		self.assertEqual(cash_payments[0].default, 1)
		# Audit Issue F: write_off_limit is reqd in v16; pin the contract
		# that it's set (even if 0) so a future ERPNext minor with a >0
		# constraint catches as a test failure, not a silent install crash.
		self.assertIsNotNone(profile.write_off_limit,
			"POS Profile.write_off_limit must be set explicitly (Audit Issue F).")

	def test_cash_mode_of_payment_account_for_hamilton_company(self):
		"""Mode of Payment 'Cash' has an account row for the Hamilton company."""
		company = _hamilton_company()
		self.assertIsNotNone(company)
		mop = frappe.get_doc("Mode of Payment", "Cash")
		hamilton_rows = [a for a in mop.accounts if a.company == company]
		self.assertEqual(
			len(hamilton_rows), 1,
			f"Mode of Payment 'Cash' has {len(hamilton_rows)} account rows for "
			f"company {company!r}; expected exactly 1.",
		)

	def test_retail_items_have_item_defaults_wired(self):
		"""All 4 retail items have Item Defaults pointing to Hamilton accounts."""
		company = _hamilton_company()
		self.assertIsNotNone(company)
		abbr = frappe.db.get_value("Company", company, "abbr")
		warehouse = f"{HAMILTON_WAREHOUSE_BASE} - {abbr}"
		expected = {
			"WAT-500":  f"{HAMILTON_INCOME_ACCOUNT_BEVERAGE} - {abbr}",
			"GAT-500":  f"{HAMILTON_INCOME_ACCOUNT_BEVERAGE} - {abbr}",
			"BAR-PROT": f"{HAMILTON_INCOME_ACCOUNT_FOOD} - {abbr}",
			"BAR-ENRG": f"{HAMILTON_INCOME_ACCOUNT_FOOD} - {abbr}",
		}
		for item_code, income in expected.items():
			if not frappe.db.exists("Item", item_code):
				self.skipTest(f"Item {item_code} not seeded — retail seed did not run.")
			item = frappe.get_doc("Item", item_code)
			rows = [d for d in item.item_defaults if d.company == company]
			self.assertEqual(
				len(rows), 1,
				f"Item {item_code} has {len(rows)} Item Default rows for "
				f"company {company!r}; expected 1.",
			)
			row = rows[0]
			self.assertEqual(row.income_account, income)
			self.assertEqual(row.default_warehouse, warehouse)


class TestSubmitRetailSale(IntegrationTestCase):
	"""End-to-end tests for the submit_retail_sale API.

	Each test:
	  1. Seeds 24 units of stock for the test SKU (Material Receipt).
	  2. Calls submit_retail_sale with a single-line cart.
	  3. Asserts on the returned Sales Invoice + stock decrement.

	Cleanup is automatic via IntegrationTestCase's transactional rollback.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _hamilton_company()
		if not cls.company:
			cls.skipTest_reason = "No Hamilton company seeded."
			return
		cls.abbr = frappe.db.get_value("Company", cls.company, "abbr")
		cls.warehouse = f"{HAMILTON_WAREHOUSE_BASE} - {cls.abbr}"

	def setUp(self):
		super().setUp()
		if not _hamilton_company():
			self.skipTest("Hamilton company not seeded.")
		# Each test seeds its own stock so the test is self-contained.
		self._seed_stock("WAT-500", 24)
		self._seed_stock("BAR-PROT", 24)

	def _seed_stock(self, item_code: str, qty: float):
		"""Add `qty` of `item_code` to the Hamilton warehouse via Material Receipt."""
		if not frappe.db.exists("Item", item_code):
			self.skipTest(f"Item {item_code} not seeded.")
		se = frappe.new_doc("Stock Entry")
		se.update({
			"company": self.company,
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
		})
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"t_warehouse": self.warehouse,
			"basic_rate": 1.00,
		})
		se.insert(ignore_permissions=True)
		se.submit()

	def _get_stock(self, item_code: str) -> float:
		row = frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": self.warehouse},
			"actual_qty",
		)
		return float(row or 0)

	def test_submit_creates_pos_sales_invoice_with_walkin_customer(self):
		stock_before = self._get_stock("WAT-500")
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=10.00,
		)
		self.assertIn("sales_invoice", result)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertEqual(si.customer, "Walk-in")
		self.assertEqual(si.is_pos, 1)
		self.assertEqual(si.update_stock, 1)
		self.assertEqual(si.pos_profile, HAMILTON_POS_PROFILE)
		self.assertEqual(si.docstatus, 1, "Sales Invoice should be submitted.")
		# Stock decrement
		stock_after = self._get_stock("WAT-500")
		self.assertAlmostEqual(stock_before - stock_after, 2.0,
			msg="Stock did not decrement by 2 on submit.")

	def test_submit_applies_hst_tax_line_at_13_percent(self):
		# qty=2 × WAT-500 ($3.50 standard_rate) → net=$7.00, HST=$0.91, grand=$7.91
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertAlmostEqual(float(si.net_total), 7.00, places=2)
		# One tax line, rate 13
		self.assertEqual(len(si.taxes), 1, "Expected exactly one tax line (HST).")
		hst = si.taxes[0]
		self.assertAlmostEqual(float(hst.rate), 13.0)
		self.assertAlmostEqual(float(hst.tax_amount), 0.91, places=2)
		self.assertAlmostEqual(float(si.grand_total), 7.91, places=2)

	def test_submit_returns_correct_change(self):
		# qty=2 × $3.50 → net=$7.00, HST=$0.91, grand=$7.91 (pre-rounding).
		# Canadian nickel rounding: $7.91 → rounded $7.90.
		# cash=$20 → change=$20.00 - $7.90 = $12.10.
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		self.assertAlmostEqual(result["grand_total"], 7.91, places=2)
		self.assertAlmostEqual(result["rounded_total"], 7.90, places=2)
		self.assertAlmostEqual(result["rounding_adjustment"], -0.01, places=2)
		self.assertAlmostEqual(result["change"], 12.10, places=2)

	def test_submit_records_cash_payment(self):
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertEqual(len(si.payments), 1)
		self.assertEqual(si.payments[0].mode_of_payment, "Cash")
		# Outstanding should be 0 (paid in full).
		self.assertAlmostEqual(float(si.outstanding_amount), 0.0, places=2)

	def test_submit_rejects_empty_cart(self):
		with self.assertRaises(frappe.ValidationError):
			submit_retail_sale(items=[], cash_received=10.00)

	def test_submit_rejects_insufficient_cash(self):
		with self.assertRaises(frappe.ValidationError):
			submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 10.00}],
				cash_received=5.00,
			)

	def test_submit_rejects_unknown_item(self):
		with self.assertRaises(frappe.ValidationError):
			submit_retail_sale(
				items=[{"item_code": "DOES-NOT-EXIST", "qty": 1, "unit_price": 1.00}],
				cash_received=10.00,
			)

	def test_submit_accepts_json_string_items(self):
		"""frappe.xcall may serialize the list as JSON over the wire."""
		import json
		result = submit_retail_sale(
			items=json.dumps([{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}]),
			cash_received=10.00,
		)
		self.assertIn("sales_invoice", result)

	def test_submit_with_multiple_lines(self):
		stock_wat_before = self._get_stock("WAT-500")
		stock_bar_before = self._get_stock("BAR-PROT")
		result = submit_retail_sale(
			items=[
				{"item_code": "WAT-500",  "qty": 2, "unit_price": 3.50},
				{"item_code": "BAR-PROT", "qty": 1, "unit_price": 4.00},
			],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertEqual(len(si.items), 2)
		# Subtotal = 7 + 4 = 11; HST = 1.43; grand_total = 12.43
		self.assertAlmostEqual(float(si.net_total), 11.00, places=2)
		self.assertAlmostEqual(float(si.grand_total), 12.43, places=2)
		# Both stock counts decrement
		self.assertAlmostEqual(stock_wat_before - self._get_stock("WAT-500"), 2.0)
		self.assertAlmostEqual(stock_bar_before - self._get_stock("BAR-PROT"), 1.0)


class TestSubmitRetailSaleHardening(IntegrationTestCase):
	"""PR #51 hardening regressions — role gate, server-side rate authority,
	and pre-submit stock guard.

	Each test pre-seeds the stock it needs in setUp via Material Receipt;
	IntegrationTestCase plus restore_dev_state() in tearDownModule keep
	state contained.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _hamilton_company()
		if not cls.company:
			return
		cls.abbr = frappe.db.get_value("Company", cls.company, "abbr")
		cls.warehouse = f"{HAMILTON_WAREHOUSE_BASE} - {cls.abbr}"

		# A user with NO Hamilton roles. Frappe auto-assigns "All" / "Guest"
		# / "System User" on insert; none of those are in the allowed set.
		cls.no_role_email = "no-hamilton-role-test@example.com"
		if not frappe.db.exists("User", cls.no_role_email):
			frappe.get_doc({
				"doctype": "User",
				"email": cls.no_role_email,
				"first_name": "NoHamilton",
				"send_welcome_email": 0,
				"enabled": 1,
			}).insert(ignore_permissions=True)

		# A user with Hamilton Operator role for the positive-path test.
		cls.operator_email = "hamilton-operator-test@example.com"
		if not frappe.db.exists("User", cls.operator_email):
			frappe.get_doc({
				"doctype": "User",
				"email": cls.operator_email,
				"first_name": "OpTest",
				"send_welcome_email": 0,
				"enabled": 1,
				"roles": [{"role": "Hamilton Operator"}],
			}).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		for email in (getattr(cls, "no_role_email", None), getattr(cls, "operator_email", None)):
			if email and frappe.db.exists("User", email):
				frappe.delete_doc("User", email, ignore_permissions=True, force=True)
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		if not _hamilton_company():
			self.skipTest("Hamilton company not seeded.")
		self._seed_stock("WAT-500", 10)

	def _seed_stock(self, item_code: str, qty: float):
		if not frappe.db.exists("Item", item_code):
			self.skipTest(f"Item {item_code} not seeded.")
		se = frappe.new_doc("Stock Entry")
		se.update({
			"company": self.company,
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
		})
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"t_warehouse": self.warehouse,
			"basic_rate": 1.00,
		})
		se.insert(ignore_permissions=True)
		se.submit()

	# ---------------------------------------------------------------
	# Issue 1 + 5: role gate (delegated capability — no Sales Invoice
	# perm required, only Hamilton role membership).
	# ---------------------------------------------------------------

	def test_role_gate_rejects_user_without_hamilton_role(self):
		"""Non-Hamilton user gets PermissionError before any DB write."""
		original_user = frappe.session.user
		try:
			frappe.set_user(self.no_role_email)
			with self.assertRaises(frappe.PermissionError):
				submit_retail_sale(
					items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
					cash_received=10.00,
				)
		finally:
			frappe.set_user(original_user)

	def test_role_gate_accepts_hamilton_operator(self):
		"""Hamilton Operator can record retail sales (delegated capability).

		Operator does NOT have direct Sales Invoice perms; the cart wraps
		the write with ignore_permissions=True after the role gate.
		"""
		original_user = frappe.session.user
		try:
			frappe.set_user(self.operator_email)
			result = submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
				cash_received=10.00,
			)
			self.assertIn("sales_invoice", result)
			self.assertTrue(frappe.db.exists("Sales Invoice", result["sales_invoice"]))
		finally:
			frappe.set_user(original_user)

	def test_role_gate_accepts_administrator(self):
		"""Administrator is implicitly allowed (Frappe convention)."""
		# Already running as Administrator in tests — pins the contract that
		# no role membership is required for Administrator specifically.
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
			cash_received=10.00,
		)
		self.assertIn("sales_invoice", result)

	# ---------------------------------------------------------------
	# Issue 2: server-side rate authority. Client-supplied unit_price
	# is validated against Item.standard_rate; mismatches are rejected.
	# ---------------------------------------------------------------

	def test_rate_mismatch_rejected_when_client_sends_lower_price(self):
		"""A compromised client trying to underpay is rejected."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 0.01}],
				cash_received=10.00,
			)
		self.assertIn("Price mismatch", str(ctx.exception))
		self.assertIn("WAT-500", str(ctx.exception))

	def test_rate_mismatch_rejected_when_client_sends_higher_price(self):
		"""Higher prices are also rejected — server is authoritative both ways."""
		with self.assertRaises(frappe.ValidationError):
			submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 999.99}],
				cash_received=2000.00,
			)

	def test_server_rate_used_on_invoice_not_client_value(self):
		"""Even when client sends correct rate, the invoice persists the
		SERVER value. Pins the contract that the server is authoritative
		regardless of client agreement."""
		expected = flt(frappe.db.get_value("Item", "WAT-500", "standard_rate"))
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
			cash_received=10.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertAlmostEqual(float(si.items[0].rate), float(expected), places=2,
			msg="Sales Invoice line rate must come from Item master, not client.")

	def test_rate_tolerance_absorbs_floating_point_noise(self):
		"""$0.01 tolerance prevents floating-point noise from false rejections."""
		# 3.50 + 0.005 should still be accepted (within $0.01).
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.505}],
			cash_received=10.00,
		)
		self.assertIn("sales_invoice", result)

	# ---------------------------------------------------------------
	# Issue 3: pre-submit stock guard. Cart qty > Bin.actual_qty is
	# rejected with a clean operator message before the Sales Invoice
	# is even inserted.
	# ---------------------------------------------------------------

	def test_insufficient_stock_rejected_before_submit(self):
		"""Aggregate cart qty > Bin.actual_qty raises a clean ValidationError."""
		# setUp seeded 10 units. Try to sell 100.
		with self.assertRaises(frappe.ValidationError) as ctx:
			submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 100, "unit_price": 3.50}],
				cash_received=500.00,
			)
		msg = str(ctx.exception)
		self.assertIn("Insufficient stock", msg)
		self.assertIn("WAT-500", msg)

	def test_stock_check_aggregates_duplicate_lines(self):
		"""Even if the cart has two lines for the same item, the stock
		check sums them — server-side aggregation contract.

		Uses qty=500 on each duplicate line (total 1000) so the test
		fires our pre-submit guard regardless of any stock accumulation
		from prior test classes in this module. The value is far above
		any realistic Hamilton inventory (single-venue, ~24-unit
		restocks per the V9.1 seed comment).
		"""
		with self.assertRaises(frappe.ValidationError) as ctx:
			submit_retail_sale(
				items=[
					{"item_code": "WAT-500", "qty": 500, "unit_price": 3.50},
					{"item_code": "WAT-500", "qty": 500, "unit_price": 3.50},
				],
				cash_received=10000.00,
			)
		self.assertIn("Insufficient stock", str(ctx.exception))

	def test_stock_check_uses_pos_profile_warehouse(self):
		"""Pin the contract that the stock check reads Bin against the POS
		Profile's warehouse, not the Stock Settings default. A future
		warehouse refactor that splits the two would silently bypass this
		check unless the test catches it."""
		# 10 units in Hamilton warehouse; request 5 — should succeed.
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 5, "unit_price": 3.50}],
			cash_received=20.00,
		)
		self.assertIn("sales_invoice", result)


class TestCanadianCashRounding(IntegrationTestCase):
	"""Canadian penny-elimination rule (2013): cash transactions round to
	the nearest 5¢; HST is computed on the unrounded subtotal first; the
	rounding_adjustment posts as a separate GL entry to the Round Off
	account; card / electronic payments settle to the cent.

	Reference: Government of Canada Budget 2012 backgrounder; Wikipedia
	"Cash rounding"; ERPNext's
	``frappe.utils.data.round_based_on_smallest_currency_fraction``.
	See docs/decisions_log.md Amendment 2026-04-30 (c).
	"""

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
		self._seed_stock("WAT-500", 100)

	def _seed_stock(self, item_code: str, qty: float):
		if not frappe.db.exists("Item", item_code):
			self.skipTest(f"Item {item_code} not seeded.")
		se = frappe.new_doc("Stock Entry")
		se.update({
			"company": self.company,
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
		})
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"t_warehouse": self.warehouse,
			"basic_rate": 1.00,
		})
		se.insert(ignore_permissions=True)
		se.submit()

	# ---------------------------------------------------------------
	# Seed verification — Currency + Round Off Account
	# ---------------------------------------------------------------

	def test_cad_currency_smallest_fraction_is_nickel(self):
		"""``Currency CAD.smallest_currency_fraction_value`` must be 0.05.

		This is what makes ERPNext's
		``round_based_on_smallest_currency_fraction`` produce nickel
		increments instead of cents. Without this, the
		``disable_rounded_total=0`` branch in submit_retail_sale would
		round to the cent (a no-op), defeating the whole point.
		"""
		value = flt(frappe.db.get_value(
			"Currency", "CAD", "smallest_currency_fraction_value"
		))
		self.assertAlmostEqual(value, 0.05, places=4,
			msg="CAD smallest_currency_fraction_value should be 0.05 "
			"(Canadian nickel rounding).")

	def test_company_round_off_account_linked(self):
		"""Company.round_off_account must be set so rounding_adjustment posts."""
		round_off = frappe.db.get_value(
			"Company", self.company, "round_off_account"
		)
		self.assertIsNotNone(round_off,
			f"Company {self.company!r} has no round_off_account; "
			"rounding_adjustment GL entry will fail to post.")
		self.assertTrue(frappe.db.exists("Account", round_off),
			f"round_off_account {round_off!r} does not exist as an Account.")

	def test_company_round_off_cost_center_linked(self):
		"""Company.round_off_cost_center must tie to the Hamilton cost
		center (not the Standard CoA auto-default "Main - {abbr}") so
		rounding GL entries are scoped for venue-level reporting.
		Audit Issue H (PR #51 review)."""
		cc = frappe.db.get_value(
			"Company", self.company, "round_off_cost_center"
		)
		expected = f"{HAMILTON_COST_CENTER_BASE} - {self.abbr}"
		self.assertEqual(cc, expected,
			f"round_off_cost_center should be {expected!r} (Hamilton-scoped); "
			f"got {cc!r}. Standard CoA default 'Main - {{abbr}}' should be "
			f"overwritten by _ensure_round_off_account_linked.")

	# ---------------------------------------------------------------
	# Payment-method gate (the rounding decision)
	# ---------------------------------------------------------------

	def test_should_round_to_nickel_helper(self):
		"""The internal gate: Cash → True, anything else → False."""
		from hamilton_erp.api import _should_round_to_nickel
		self.assertTrue(_should_round_to_nickel("Cash"),
			"Cash sales must round per Canadian penny-elimination rule.")
		self.assertFalse(_should_round_to_nickel("Card"),
			"Card sales must settle to the exact cent.")
		# Defensive: anything that isn't 'Cash' (including future methods
		# that haven't been added yet, or typos) should not round.
		self.assertFalse(_should_round_to_nickel("Bitcoin"))
		self.assertFalse(_should_round_to_nickel(""))
		self.assertFalse(_should_round_to_nickel("CASH"))  # case-sensitive

	def test_payment_method_default_is_cash(self):
		"""Omitting payment_method defaults to Cash (rounding applies)."""
		# No payment_method param → Cash → SI's disable_rounded_total=0.
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertEqual(int(si.disable_rounded_total or 0), 0,
			"Cash sale must NOT have disable_rounded_total set.")

	def test_payment_method_card_not_yet_implemented(self):
		"""payment_method='Card' is rejected as Phase 2 next iteration.

		The rounding gate (_should_round_to_nickel) correctly returns False
		for Card, but the end-to-end Card flow (merchant adapter,
		merchant_transaction_id capture, terminal integration) ships
		separately. Throwing here is the correct contract until that lands.
		"""
		with self.assertRaises(frappe.ValidationError) as ctx:
			submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
				cash_received=10.00,
				payment_method="Card",
			)
		self.assertIn("Card", str(ctx.exception))

	def test_payment_method_unknown_rejected(self):
		"""Unknown payment methods are rejected at function entry."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			submit_retail_sale(
				items=[{"item_code": "WAT-500", "qty": 1, "unit_price": 3.50}],
				cash_received=10.00,
				payment_method="Bitcoin",
			)
		self.assertIn("Unsupported payment method", str(ctx.exception))

	# ---------------------------------------------------------------
	# Rounding math — the actual nickel rounding behavior
	# ---------------------------------------------------------------

	def test_cash_sale_rounds_grand_total_to_nearest_nickel(self):
		"""net=$7.00, HST=$0.91, grand=$7.91 → rounded=$7.90 (down to nickel)."""
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertAlmostEqual(float(si.grand_total), 7.91, places=2)
		self.assertAlmostEqual(float(si.rounded_total), 7.90, places=2)
		self.assertAlmostEqual(float(si.rounding_adjustment), -0.01, places=2)

	def test_hst_computed_on_unrounded_subtotal_not_rounded_total(self):
		"""CRA rule: tax is calculated to the cent BEFORE the final cash
		rounding. The HST line on the SI must be the exact 13% × subtotal,
		never derived from the rounded total."""
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		# Subtotal $7.00 × 13% = $0.91 (exact). Anything other than $0.91
		# means rounding leaked into the tax math.
		self.assertAlmostEqual(float(si.taxes[0].tax_amount), 0.91, places=2,
			msg="HST must be 13% × $7.00 = $0.91; rounding leaked into tax.")

	def test_change_uses_rounded_total_not_grand_total(self):
		"""Cash change is cash_received - rounded_total (not - grand_total).

		For grand=$7.91, rounded=$7.90, cash=$20.00:
		  - WRONG: $20 - $7.91 = $12.09 (UX shows penny that doesn't exist)
		  - RIGHT: $20 - $7.90 = $12.10 (matches what operator gives back)
		"""
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		self.assertAlmostEqual(result["change"], 12.10, places=2,
			msg="Change must be computed against rounded_total, not grand_total.")

	def test_payment_amount_uses_rounded_total(self):
		"""SI.payments[0].amount = rounded_total (what was actually
		collected), not grand_total. Otherwise paid_amount drifts and
		outstanding_amount != 0."""
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		si = frappe.get_doc("Sales Invoice", result["sales_invoice"])
		self.assertAlmostEqual(float(si.payments[0].amount), 7.90, places=2)
		self.assertAlmostEqual(float(si.outstanding_amount), 0.0, places=2,
			msg="Outstanding must be 0; rounded_total + change = paid in full.")

	def test_rounding_adjustment_posts_to_round_off_account(self):
		"""On submit, the 1¢ rounding loss appears as a GL entry on
		Company.round_off_account (Path B accounting per the research)."""
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		round_off = frappe.db.get_value(
			"Company", self.company, "round_off_account"
		)
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={
				"voucher_no": result["sales_invoice"],
				"account": round_off,
			},
			fields=["debit", "credit"],
		)
		self.assertEqual(len(gl_entries), 1,
			f"Expected exactly 1 GL entry on Round Off account "
			f"({round_off!r}); got {len(gl_entries)}.")
		# grand=$7.91 → rounded=$7.90 → 1¢ loss → debit Round Off $0.01.
		entry = gl_entries[0]
		net = flt(entry.get("debit")) - flt(entry.get("credit"))
		self.assertAlmostEqual(net, 0.01, places=2,
			msg="Round Off entry should reflect the 0.01 cash rounding loss "
			"(debit - credit = 0.01).")

	# ---------------------------------------------------------------
	# Rounding pattern — exhaustive terminal-digit check vs CRA rule
	# ---------------------------------------------------------------

	def test_rounding_pattern_matches_cra_rule(self):
		"""Verify Frappe's algorithm matches the Government of Canada
		penny-elimination rule:
		  1, 2 → round down to 0
		  3, 4 → round up to 5
		  6, 7 → round down to 5
		  8, 9 → round up to next 0

		Tests against ``round_based_on_smallest_currency_fraction`` directly
		so the contract is verified independent of any Sales Invoice plumbing.
		"""
		from frappe.utils.data import round_based_on_smallest_currency_fraction
		cases = [
			# (input, expected, comment)
			(10.00, 10.00, "0 → 0 (no change)"),
			(10.01, 10.00, "1 → 0 (round down)"),
			(10.02, 10.00, "2 → 0 (round down)"),
			(10.03, 10.05, "3 → 5 (round up)"),
			(10.04, 10.05, "4 → 5 (round up)"),
			(10.05, 10.05, "5 → 5 (no change)"),
			(10.06, 10.05, "6 → 5 (round down)"),
			(10.07, 10.05, "7 → 5 (round down)"),
			(10.08, 10.10, "8 → 10 (round up across dime)"),
			(10.09, 10.10, "9 → 10 (round up across dime)"),
		]
		for input_val, expected, comment in cases:
			with self.subTest(input=input_val, expected=expected, rule=comment):
				actual = round_based_on_smallest_currency_fraction(
					input_val, "CAD", 2
				)
				self.assertAlmostEqual(actual, expected, places=2,
					msg=f"CRA rule violated: {input_val} should round to "
					f"{expected} ({comment}); got {actual}.")

	def test_card_path_helper_indicates_no_rounding(self):
		"""Even though Card payments throw NotImplementedError today, the
		rounding gate is already correctly OFF for Card. When Phase 2 next
		iteration removes the throw, the rounding contract is already in
		place — this test pins that contract."""
		from hamilton_erp.api import _should_round_to_nickel
		self.assertFalse(_should_round_to_nickel("Card"),
			"Card payments must not round; the gate is the contract that "
			"survives the Card-flow implementation in Phase 2 next.")


def tearDownModule():
	"""Restore dev state after destructive tests in this module."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
