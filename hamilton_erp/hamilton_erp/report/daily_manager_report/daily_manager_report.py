"""Daily Manager Report — Operational Summary for Venue Managers

Shows daily metrics across:
- Session volume and revenue
- Asset utilization
- Cash drops
- Exceptions (comps, OOS events)

Designed for Hamilton Manager+ role as a daily operational dashboard.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	"""Main report entry point.

	Returns:
		tuple: (columns, data, message, chart, report_summary)
	"""
	if not filters:
		filters = {}

	validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)

	return columns, data, None, chart, summary


def validate_filters(filters):
	"""Ensure required filters are present."""
	if not filters.get("from_date"):
		frappe.throw(_("From Date is required"))
	if not filters.get("to_date"):
		frappe.throw(_("To Date is required"))

	# Ensure from_date <= to_date
	if getdate(filters["from_date"]) > getdate(filters["to_date"]):
		frappe.throw(_("From Date cannot be after To Date"))


def get_columns():
	"""Define report columns."""
	return [
		{
			"fieldname": "date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"fieldname": "total_sessions",
			"label": _("Sessions"),
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"fieldname": "revenue",
			"label": _("Revenue"),
			"fieldtype": "Currency",
			"options": "CAD",
			"width": 120,
		},
		{
			"fieldname": "asset_utilization",
			"label": _("Utilization %"),
			"fieldtype": "Percent",
			"width": 100,
		},
		{
			"fieldname": "cash_drops",
			"label": _("Cash Drops"),
			"fieldtype": "Currency",
			"options": "CAD",
			"width": 120,
		},
		{
			"fieldname": "comp_count",
			"label": _("Comps"),
			"fieldtype": "Int",
			"width": 70,
		},
		{
			"fieldname": "oos_events",
			"label": _("OOS Events"),
			"fieldtype": "Int",
			"width": 90,
		},
	]


def get_data(filters):
	"""Fetch and aggregate daily operational data.

	Data sources:
	- Venue Session: session counts
	- Sales Invoice: revenue (submitted POS invoices)
	- Cash Drop: cash drop totals
	- Asset Status Log: OOS events
	- Comp Admission Log: comp counts
	"""
	from_date = filters["from_date"]
	to_date = filters["to_date"]

	# Generate date range
	dates = frappe.db.sql("""
		SELECT DISTINCT DATE(session_start) as date
		FROM `tabVenue Session`
		WHERE DATE(session_start) BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY date
	""", {"from_date": from_date, "to_date": to_date}, as_dict=True)

	data = []

	for row in dates:
		date = row["date"]

		# Session count for the day
		session_count = frappe.db.count("Venue Session", {
			"session_start": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]]
		})

		# Revenue: sum of submitted POS invoices for the day
		revenue_result = frappe.db.sql("""
			SELECT COALESCE(SUM(grand_total), 0) as revenue
			FROM `tabSales Invoice`
			WHERE docstatus = 1
			  AND is_pos = 1
			  AND DATE(posting_date) = %(date)s
		""", {"date": date}, as_dict=True)
		revenue = revenue_result[0]["revenue"] if revenue_result else 0

		# Asset utilization: (occupied asset-hours / available asset-hours) * 100
		# Simplified: count distinct assets used vs total active assets
		assets_used = frappe.db.count("Venue Session", {
			"session_start": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]]
		}, distinct="venue_asset")

		total_assets = frappe.db.count("Venue Asset", {"is_active": 1})
		utilization = (assets_used / total_assets * 100) if total_assets > 0 else 0

		# Cash drops for the day
		cash_drops_result = frappe.db.sql("""
			SELECT COALESCE(SUM(cash_amount), 0) as cash_drops
			FROM `tabCash Drop`
			WHERE docstatus = 1
			  AND DATE(drop_time) = %(date)s
		""", {"date": date}, as_dict=True)
		cash_drops = cash_drops_result[0]["cash_drops"] if cash_drops_result else 0

		# Comp count for the day
		comp_count = frappe.db.count("Comp Admission Log", {
			"comp_date": date
		})

		# OOS events: count Asset Status Log entries where new_status = "Out of Service"
		oos_events = frappe.db.count("Asset Status Log", {
			"log_date": date,
			"new_status": "Out of Service"
		})

		data.append({
			"date": date,
			"total_sessions": session_count,
			"revenue": revenue,
			"asset_utilization": utilization,
			"cash_drops": cash_drops,
			"comp_count": comp_count,
			"oos_events": oos_events,
		})

	return data


def get_chart(data):
	"""Generate revenue trend chart."""
	if not data:
		return None

	labels = [str(row["date"]) for row in data]
	revenue_values = [row["revenue"] for row in data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Revenue"),
					"values": revenue_values
				}
			]
		},
		"type": "line",
		"colors": ["#7cd6fd"],
		"height": 250,
	}


def get_summary(data):
	"""Generate report summary cards."""
	if not data:
		return []

	total_sessions = sum(row["total_sessions"] for row in data)
	total_revenue = sum(row["revenue"] for row in data)
	avg_utilization = sum(row["asset_utilization"] for row in data) / len(data) if data else 0
	total_comps = sum(row["comp_count"] for row in data)
	total_oos = sum(row["oos_events"] for row in data)

	return [
		{
			"value": total_sessions,
			"label": _("Total Sessions"),
			"datatype": "Int",
			"indicator": "Blue"
		},
		{
			"value": total_revenue,
			"label": _("Total Revenue"),
			"datatype": "Currency",
			"currency": "CAD",
			"indicator": "Green"
		},
		{
			"value": avg_utilization,
			"label": _("Avg Utilization"),
			"datatype": "Percent",
			"indicator": "Grey"
		},
		{
			"value": total_comps,
			"label": _("Total Comps"),
			"datatype": "Int",
			"indicator": "Orange"
		},
		{
			"value": total_oos,
			"label": _("OOS Events"),
			"datatype": "Int",
			"indicator": "Red" if total_oos > 0 else "Grey"
		},
	]
