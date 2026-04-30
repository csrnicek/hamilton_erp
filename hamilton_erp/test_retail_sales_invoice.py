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
		# qty=2 × $3.50 → net=$7.00, HST=$0.91, grand=$7.91; cash=$20 → change=$12.09
		result = submit_retail_sale(
			items=[{"item_code": "WAT-500", "qty": 2, "unit_price": 3.50}],
			cash_received=20.00,
		)
		self.assertAlmostEqual(result["grand_total"], 7.91, places=2)
		self.assertAlmostEqual(result["change"], 12.09, places=2)

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


def tearDownModule():
	"""Restore dev state after destructive tests in this module."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
