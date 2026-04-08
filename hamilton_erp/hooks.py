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
		"filters": [["name", "in", ["Hamilton Operator", "Hamilton Manager"]]],
	},
]

# ---------------------------------------------------------------------------
# After install — seed roles and initial configuration
# ---------------------------------------------------------------------------

after_install = "hamilton_erp.setup.install.after_install"

# ---------------------------------------------------------------------------
# doc_events — hooked into standard ERPNext DocType lifecycle
# ---------------------------------------------------------------------------
# Phase 2 wires this up fully. Stub is declared here so hooks.py is complete
# from Phase 0 onward and the handler exists to accept the call.

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
