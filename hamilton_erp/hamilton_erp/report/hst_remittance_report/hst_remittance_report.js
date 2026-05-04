// Copyright (c) 2026, Hamilton and contributors
// For license information, please see license.txt

frappe.query_reports["HST Remittance Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("company"),
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "detail_view",
			label: __("Detail View"),
			fieldtype: "Check",
			default: 0
		}
	],
	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Bold styling for LINE rows (totals and final balance)
		if (column.fieldname === "line_number" && data.line_number && data.line_number.startsWith("LINE")) {
			value = "<span style='font-weight:bold'>" + value + "</span>";
		}

		if (column.fieldname === "description" && data.line_number && data.line_number.startsWith("LINE")) {
			value = "<span style='font-weight:bold'>" + value + "</span>";
		}

		if (column.fieldname === "amount" && data.line_number && data.line_number.startsWith("LINE")) {
			value = "<span style='font-weight:bold'>" + value + "</span>";
		}

		return value;
	}
};
