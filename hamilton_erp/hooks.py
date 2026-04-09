app_name = "hamilton_erp"
app_title = "Hamilton ERP"
app_publisher = "Chris Srnicek"
app_description = "Custom Frappe app extending ERPNext for Club Hamilton — asset board, session lifecycle, and blind cash control."
app_email = "chris@hamilton.example.com"
app_license = "MIT"
app_version = "0.1.0"

required_apps = ["frappe", "erpnext"]

# ---------------------------------------------------------------------------
# Fixtures — synced on bench migrate
# ---------------------------------------------------------------------------
# Filters limit export/import to only Hamilton fields so bench export-fixtures
# does not capture unrelated custom fields from other apps.

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "like", "%-hamilton_%"]],
	},
	{
		"dt": "Property Setter",
		"filters": [["name", "like", "%-hamilton_%"]],
	},
	{
		"dt": "Role",
		"filters": [["name", "in", ["Hamilton Operator", "Hamilton Manager", "Hamilton Admin"]]],
	},
]

# ---------------------------------------------------------------------------
# After install — seed roles and initial configuration
# ---------------------------------------------------------------------------

after_install = "hamilton_erp.setup.install.after_install"

# ---------------------------------------------------------------------------
# Override classes — extend standard ERPNext DocType classes
# ---------------------------------------------------------------------------
# HamiltonSalesInvoice adds has_admission_item(), get_admission_category(),
# and has_comp_admission() as reusable methods on the document object.
# The doc_event hook below receives a HamiltonSalesInvoice instance as `doc`.

override_doctype_class = {
	"Sales Invoice": "hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice",
}

# ---------------------------------------------------------------------------
# doc_events — hooked into standard ERPNext DocType lifecycle
# ---------------------------------------------------------------------------

doc_events = {
	"Sales Invoice": {
		"on_submit": "hamilton_erp.api.on_sales_invoice_submit",
	},
}

# ---------------------------------------------------------------------------
# Scheduler events
# ---------------------------------------------------------------------------
# Overtime detection runs every 15 minutes. The task is a no-op until
# Phase 1 implementation lands.

scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"hamilton_erp.tasks.check_overtime_sessions",
		],
	},
}
