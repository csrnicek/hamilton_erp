"""HST Remittance Report for CRA Filing (Form GST62)

Generates summary and detail reports matching CRA NETFILE confirmation format.
Maps ERPNext transactions to GST62 form lines for 1742279 Ont Inc.

Summary view: GST62 form lines with totals (Lines 101-113C)
Detail view: Transaction-level breakdown with running balance

GST/HST Registration: 105204077RT0001
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	"""Main entry point for report execution."""
	if not filters:
		filters = {}

	validate_filters(filters)

	if filters.get("detail_view"):
		return get_detail_report(filters)
	else:
		return get_summary_report(filters)


def validate_filters(filters):
	"""Ensure required filters are present."""
	if not filters.get("from_date"):
		frappe.throw(_("From Date is required"))
	if not filters.get("to_date"):
		frappe.throw(_("To Date is required"))
	if not filters.get("company"):
		frappe.throw(_("Company is required"))


def get_summary_report(filters):
	"""Generate CRA form summary matching QuickBooks format."""
	columns = get_summary_columns()
	data = calculate_cra_lines(filters)

	return columns, data


def get_summary_columns():
	"""Column definitions for summary view."""
	return [
		{
			"fieldname": "line_number",
			"label": _("Line"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "description",
			"label": _("Description"),
			"fieldtype": "Data",
			"width": 400
		},
		{
			"fieldname": "amount",
			"label": _("Amount"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150
		}
	]


def calculate_cra_lines(filters):
	"""Calculate all CRA form lines from ERPNext data."""
	company = filters.get("company")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")

	# Get HST account name for this company
	hst_account = get_hst_account(company)

	# Line 101: Sales and other revenue (taxable supplies)
	line_101 = get_taxable_sales_revenue(company, from_date, to_date, hst_account)

	# Line 103: GST/HST collected or collectible
	line_103 = get_hst_collected(company, from_date, to_date, hst_account)

	# Line 104: Adjustments (Sales) - manual entry field
	line_104 = 0.0  # TODO: Add custom field for manual adjustments

	# Line 105: Total GST/HST and adjustments
	line_105 = line_103 + line_104

	# Line 106: Input Tax Credits (ITCs)
	line_106 = get_input_tax_credits(company, from_date, to_date, hst_account)

	# Line 107: Adjustments (Purchases) - manual entry field
	line_107 = 0.0  # TODO: Add custom field for manual adjustments

	# Line 108: Total ITCs and adjustments
	line_108 = line_106 + line_107

	# Line 109: Net tax
	line_109 = line_105 - line_108

	# Line 110: Instalments - manual entry field
	line_110 = 0.0  # TODO: Add custom field for instalments

	# Line 111: Rebates
	line_111 = 0.0  # Not applicable for Hamilton

	# Line 112: Total other credits
	line_112 = line_110 + line_111

	# Line 113A: Balance
	line_113a = line_109 - line_112

	# Line 205: Real property
	line_205 = 0.0  # TODO: Add custom field for real property purchases

	# Line 405: Other self-assessed
	line_405 = 0.0  # Not applicable for Hamilton

	# Line 113B: Total other debits
	line_113b = line_205 + line_405

	# Line 113C: Final balance
	line_113c = line_113a + line_113b

	# Build summary rows matching GST62 form structure (exact CRA wording)
	data = [
		{"line_number": "Line 101", "description": "Sales and other revenue.", "amount": line_101},
		{"line_number": "Line 103", "description": "GST/HST collected or collectible.", "amount": line_103},
		{"line_number": "Line 104", "description": "Adjustments (Sales).", "amount": line_104},
		{"line_number": "LINE 105", "description": "Total GST/HST and adjustments for period.", "amount": line_105},
		{"line_number": "", "description": "", "amount": None},  # Blank row
		{"line_number": "Line 106", "description": "Input tax credits (ITCs).", "amount": line_106},
		{"line_number": "Line 107", "description": "Adjustments (Purchases).", "amount": line_107},
		{"line_number": "LINE 108", "description": "Total ITCs and adjustments.", "amount": line_108},
		{"line_number": "", "description": "", "amount": None},  # Blank row
		{"line_number": "LINE 109", "description": "Net Tax.", "amount": line_109},
		{"line_number": "", "description": "", "amount": None},  # Blank row
		{"line_number": "Line 110", "description": "Instalments and other annual filer payments.", "amount": line_110},
		{"line_number": "Line 111", "description": "Rebates.", "amount": line_111},
		{"line_number": "LINE 112", "description": "Total other credits.", "amount": line_112},
		{"line_number": "", "description": "", "amount": None},  # Blank row
		{"line_number": "LINE 113A", "description": "Balance.", "amount": line_113a},
		{"line_number": "", "description": "", "amount": None},  # Blank row
		{"line_number": "Line 205", "description": "GST/HST due on acquisition of taxable real property.", "amount": line_205},
		{"line_number": "Line 405", "description": "Other GST/HST to be self-assessed.", "amount": line_405},
		{"line_number": "LINE 113B", "description": "Total other debits.", "amount": line_113b},
		{"line_number": "", "description": "", "amount": None},  # Blank row
		{"line_number": "LINE 113C", "description": "Balance.", "amount": line_113c},
	]

	return data


def get_hst_account(company):
	"""Get the HST Payable account name for the company."""
	# Standard ERPNext HST account naming
	account = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["like", "%HST%"], "account_type": "Tax"},
		"name"
	)

	if not account:
		frappe.throw(_("HST Payable account not found for company {0}").format(company))

	return account


def get_taxable_sales_revenue(company, from_date, to_date, hst_account):
	"""Calculate Line 101: Sales and other revenue (net of tax)."""
	result = frappe.db.sql("""
		SELECT SUM(si.net_total)
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Taxes and Charges` stc ON stc.parent = si.name
		WHERE si.docstatus = 1
			AND si.company = %(company)s
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND stc.account_head = %(hst_account)s
	""", {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"hst_account": hst_account
	})

	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_hst_collected(company, from_date, to_date, hst_account):
	"""Calculate Line 103: GST/HST collected or collectible."""
	result = frappe.db.sql("""
		SELECT SUM(stc.base_tax_amount)
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Taxes and Charges` stc ON stc.parent = si.name
		WHERE si.docstatus = 1
			AND si.company = %(company)s
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND stc.account_head = %(hst_account)s
	""", {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"hst_account": hst_account
	})

	return flt(result[0][0]) if result and result[0][0] else 0.0


def get_input_tax_credits(company, from_date, to_date, hst_account):
	"""Calculate Line 106: Input Tax Credits (ITCs) from purchases."""
	# ITCs from Purchase Invoices
	pi_result = frappe.db.sql("""
		SELECT SUM(ptc.base_tax_amount)
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Taxes and Charges` ptc ON ptc.parent = pi.name
		WHERE pi.docstatus = 1
			AND pi.company = %(company)s
			AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND ptc.account_head = %(hst_account)s
	""", {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"hst_account": hst_account
	})

	pi_itcs = flt(pi_result[0][0]) if pi_result and pi_result[0][0] else 0.0

	# ITCs from Journal Entries (for manual HST entries like in the PDF sample)
	je_result = frappe.db.sql("""
		SELECT SUM(jea.debit - jea.credit)
		FROM `tabJournal Entry` je
		INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		WHERE je.docstatus = 1
			AND je.company = %(company)s
			AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND jea.account = %(hst_account)s
			AND jea.debit > 0
	""", {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"hst_account": hst_account
	})

	je_itcs = flt(je_result[0][0]) if je_result and je_result[0][0] else 0.0

	return pi_itcs + je_itcs


def get_detail_report(filters):
	"""Generate transaction-level detail report matching QuickBooks format."""
	columns = get_detail_columns()
	data = get_detail_transactions(filters)

	return columns, data


def get_detail_columns():
	"""Column definitions for detail view."""
	return [
		{"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "transaction_type", "label": _("Transaction Type"), "fieldtype": "Data", "width": 150},
		{"fieldname": "voucher_no", "label": _("#"), "fieldtype": "Dynamic Link", "options": "transaction_type", "width": 150},
		{"fieldname": "memo", "label": _("Memo/Description"), "fieldtype": "Data", "width": 250},
		{"fieldname": "party", "label": _("Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "tax_code", "label": _("Tax Code"), "fieldtype": "Data", "width": 120},
		{"fieldname": "tax_rate", "label": _("Tax Rate"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "net_amount", "label": _("Net Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "tax_amount", "label": _("Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "balance", "label": _("Balance"), "fieldtype": "Currency", "width": 120}
	]


def get_detail_transactions(filters):
	"""Get all HST transactions for the period with running balance."""
	company = filters.get("company")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	hst_account = get_hst_account(company)

	transactions = []

	# Get Purchase Invoice ITCs
	pi_data = frappe.db.sql("""
		SELECT
			pi.posting_date as date,
			'Purchase Invoice' as transaction_type,
			pi.name as voucher_no,
			pi.bill_no as memo,
			pi.supplier as party,
			'HST (ITC) ON' as tax_code,
			ptc.rate as tax_rate,
			ptc.base_net_amount as net_amount,
			ptc.base_tax_amount as tax_amount
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Taxes and Charges` ptc ON ptc.parent = pi.name
		WHERE pi.docstatus = 1
			AND pi.company = %(company)s
			AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND ptc.account_head = %(hst_account)s
		ORDER BY pi.posting_date, pi.name
	""", {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"hst_account": hst_account
	}, as_dict=1)

	transactions.extend(pi_data)

	# Get Journal Entry ITCs
	je_data = frappe.db.sql("""
		SELECT
			je.posting_date as date,
			'Journal Entry' as transaction_type,
			je.name as voucher_no,
			je.user_remark as memo,
			'' as party,
			'HST (ITC) ON' as tax_code,
			13.0 as tax_rate,
			jea.debit / 0.13 as net_amount,
			jea.debit as tax_amount
		FROM `tabJournal Entry` je
		INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
		WHERE je.docstatus = 1
			AND je.company = %(company)s
			AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND jea.account = %(hst_account)s
			AND jea.debit > 0
		ORDER BY je.posting_date, je.name
	""", {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"hst_account": hst_account
	}, as_dict=1)

	transactions.extend(je_data)

	# Sort by date
	transactions = sorted(transactions, key=lambda x: (x["date"], x["voucher_no"]))

	# Add running balance
	balance = 0.0
	for row in transactions:
		balance += flt(row["tax_amount"])
		row["balance"] = balance

	return transactions
