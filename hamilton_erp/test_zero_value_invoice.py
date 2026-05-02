"""Regression pin: Hamilton's ERPNext v16 minor must accept submission of a
zero-grand_total Sales Invoice (the comp / 100%-discount admission flow).

**Why this test exists** — Phase 1 BLOCKER per Task 36 in
`.taskmaster/tasks/tasks.json`. ERPNext community has multiple field reports
across v13-v16 of zero-value invoices being silently rejected by various
Frappe validators (G-003 in `docs/research/erpnext_pos_business_process_gotchas.md`).
Hamilton's comp admission flow (DEC-016: comp admission with reason category)
generates zero-value Sales Invoices for staff complimentary admission, manager
comps, and promo grants. If Hamilton's pinned v16 minor has the bug:

- Comp flow fails at the till — operator can't submit
- Workaround pressure: ring $0.01 then immediately refund. Two records for one
  comp, audit trail corrupted, manager confusion at reconciliation.
- Cumulative drift in comp_value reporting

If Hamilton ever upgrades to a v16 minor that regresses this behavior, this
test catches it BEFORE Hamilton hits it at the till.

**What this test does NOT cover:**
- Permission gating on comp submission (that's Task 32 — manager PIN gate)
- Audit trail completeness for comps (covered by `test_database_advanced` and
  Comp Admission Log's existing tests)
- Phase 2 manager-override workflow

**Self-contained per CLAUDE.md test rules** — this test creates its own item
+ customer fixtures, submits, asserts, and tearDown rolls back. Does NOT
depend on Hamilton's seed data being present, so the test runs cleanly on a
fresh hamilton-unit-test.localhost site.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, today

# Test fixture identifiers — namespaced to avoid collision with seeded
# Hamilton items / customers. Each test creates them fresh in setUp and the
# tearDown frappe.db.rollback() removes them.
_TEST_ITEM_CODE = "TEST-ZERO-VALUE-COMP-ADMISSION"
_TEST_CUSTOMER = "Test Zero-Value Customer"


class TestZeroValueInvoiceSubmission(IntegrationTestCase):
	"""Verify ERPNext v16 accepts submission of zero-grand_total Sales Invoices.

	Pins Task 36 from `.taskmaster/tasks/tasks.json` — Phase 1 BLOCKER per the
	Task 29 audit (process #20 in `docs/audits/pos_business_process_gap_audit.md`).
	"""

	def tearDown(self):
		frappe.db.rollback()

	def _ensure_test_item(self) -> str:
		"""Create a $0 Hamilton-style admission item if it doesn't exist.

		Uses the `hamilton_is_admission` custom field that Hamilton's comp flow
		expects (per `hamilton_erp/overrides/sales_invoice.py:has_admission_item`).
		Item Group "All Item Groups" is used because it's a Frappe default that
		exists on every site without seed data.
		"""
		if frappe.db.exists("Item", _TEST_ITEM_CODE):
			return _TEST_ITEM_CODE
		item = frappe.new_doc("Item")
		item.update({
			"item_code": _TEST_ITEM_CODE,
			"item_name": "Test Zero-Value Comp Admission",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",  # Frappe Item.stock_uom is mandatory even for service items
			"is_stock_item": 0,  # Service item — no stock ledger impact
			"include_item_in_manufacturing": 0,
			"standard_rate": 0,
			"hamilton_is_admission": 1,
		})
		item.insert(ignore_permissions=True)
		return _TEST_ITEM_CODE

	def _ensure_test_customer(self) -> str:
		"""Create a test customer if it doesn't exist."""
		if frappe.db.exists("Customer", _TEST_CUSTOMER):
			return _TEST_CUSTOMER
		customer = frappe.new_doc("Customer")
		customer.update({
			"customer_name": _TEST_CUSTOMER,
			"customer_type": "Individual",
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
		})
		customer.insert(ignore_permissions=True)
		return _TEST_CUSTOMER

	def _build_zero_value_invoice(self) -> object:
		"""Build a Sales Invoice with grand_total=0 via a $0 admission item.

		Does NOT use Hamilton's `submit_retail_sale` API — that endpoint has
		Hamilton-specific guards (POS profile required, cart shape rules, etc.)
		that are out of scope for THIS test. We're verifying ERPNext's core
		invariant: can a Sales Invoice with grand_total=0 be submitted at all?
		That's an ERPNext v16 question, not a Hamilton-specific one.
		"""
		item_code = self._ensure_test_item()
		customer = self._ensure_test_customer()

		si = frappe.new_doc("Sales Invoice")
		si.update({
			"customer": customer,
			"posting_date": today(),
			"due_date": today(),
		})
		si.append("items", {
			"item_code": item_code,
			"qty": 1,
			"rate": 0,
		})
		return si

	def test_can_submit_zero_grand_total_sales_invoice(self):
		"""**Phase 1 BLOCKER regression pin (Task 36).**

		Submit a Sales Invoice with grand_total=0. Assert: no exception, the
		document reaches docstatus=1, and grand_total is genuinely zero.

		If THIS test fails on Hamilton's pinned ERPNext v16 minor, the comp
		admission flow is broken at the till and Hamilton CANNOT launch Phase 1
		until either (a) the upstream bug is fixed, OR (b) a robust workaround
		is documented (e.g. ring $0.01 then refund) and validated end-to-end.
		Escalate to Chris — do NOT silence this test.
		"""
		si = self._build_zero_value_invoice()
		si.insert(ignore_permissions=True)

		# Pre-submit sanity: grand_total computed to 0
		self.assertEqual(
			flt(si.grand_total),
			0,
			f"Built fixture had grand_total={si.grand_total}, expected 0. "
			f"Test setup is broken before exercising the regression pin.",
		)

		# THE pin: submit must not raise.
		# If this fails on Hamilton's pinned v16, escalate per task 36 spec.
		si.submit()

		# Post-submit sanity:
		self.assertEqual(
			si.docstatus,
			1,
			"Sales Invoice did not reach docstatus=1 after submit. "
			"ERPNext v16 has regressed the zero-value invoice path. "
			"Hamilton CANNOT launch Phase 1 until this is resolved — escalate.",
		)
		self.assertEqual(flt(si.grand_total), 0)

	def test_zero_value_invoice_with_admission_item_flag(self):
		"""Verify the `hamilton_is_admission` custom field travels through to
		the submitted Sales Invoice — Hamilton's comp flow depends on this
		field being present on the submitted SI for the `has_admission_item()`
		check in `overrides/sales_invoice.py`.
		"""
		si = self._build_zero_value_invoice()
		si.insert(ignore_permissions=True)
		si.submit()

		# Reload from DB to confirm the field round-trips through submission.
		fresh = frappe.get_doc("Sales Invoice", si.name)
		admission_items = [
			itm for itm in fresh.items if itm.get("hamilton_is_admission")
		]
		self.assertEqual(
			len(admission_items),
			1,
			"hamilton_is_admission flag did not survive Sales Invoice submission. "
			"Hamilton's comp flow's `has_admission_item()` check will return False "
			"for legitimate comps after this regression.",
		)

	def test_zero_value_invoice_status_is_paid_or_unpaid_not_overdue(self):
		"""Zero-value invoices should not appear as 'Overdue' in reports.

		ERPNext sometimes treats grand_total=0 as 'Unpaid' (status flag), which
		is correct, OR as 'Overdue' once due_date passes (incorrect for comps).
		Pin the expected behavior so a future v16 upgrade doesn't silently
		flip comps into overdue-receivable reports.
		"""
		si = self._build_zero_value_invoice()
		si.insert(ignore_permissions=True)
		si.submit()

		fresh = frappe.get_doc("Sales Invoice", si.name)
		# Acceptable: 'Paid' (auto-cleared because zero owing) or 'Unpaid'.
		# Unacceptable: 'Overdue' (would inflate AR reports with phantom owing).
		self.assertIn(
			fresh.status,
			["Paid", "Unpaid", "Submitted"],
			f"Zero-value invoice status is {fresh.status!r}; expected Paid/Unpaid/Submitted. "
			f"If 'Overdue', ERPNext is treating $0 invoices as receivables — flag for review.",
		)
