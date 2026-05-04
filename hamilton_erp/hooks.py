app_name = "hamilton_erp"
app_title = "Hamilton ERP"
app_publisher = "Chris Srnicek"
app_description = "Custom Frappe app extending ERPNext for Club Hamilton — asset board, session lifecycle, and blind cash control."
app_email = "csrnicek@yahoo.com"
app_license = "MIT"
app_version = "0.1.0"

required_apps = ["frappe", "erpnext"]

# ---------------------------------------------------------------------------
# Assets — CSS/JS bundled into the Desk app
# ---------------------------------------------------------------------------
# asset_board.css is scoped to .hamilton-asset-board / .hamilton-loading
# selectors so it does not bleed into other Frappe pages. Loaded app-wide
# (not page-specific) because the Asset Board is a Frappe Page, not a
# regular Desk view, and page-level css includes were removed in v15.

app_include_css = [
	"/assets/hamilton_erp/css/asset_board.css",
]

# Per-doctype client extensions. sales_invoice_extensions.js adds the
# DEC-098 "Reprint Receipt" button on submitted POS Sales Invoices for
# Hamilton Manager / Hamilton Admin / System Manager.
doctype_js = {
	"Sales Invoice": "public/js/sales_invoice_extensions.js",
}

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
# After migrate — heal is_setup_complete for frappe + erpnext
# ---------------------------------------------------------------------------
# Frappe's InstalledApplications.update_versions() runs on every bench
# migrate. On single-admin dev sites it cannot auto-heal a 0 value for
# is_setup_complete (requires a non-Administrator System User), so dev
# sites can silently flip into a setup_wizard redirect loop. This hook
# force-sets is_setup_complete=1 for frappe and erpnext after every
# migrate. Idempotent and safe on production — see docstring in install.py.

after_migrate = "hamilton_erp.setup.install.ensure_setup_complete"

# ---------------------------------------------------------------------------
# Extended classes — extend standard ERPNext DocType classes
# ---------------------------------------------------------------------------
# HamiltonSalesInvoice adds has_admission_item(), get_admission_category(),
# and has_comp_admission() as reusable methods on the document object.
# The doc_event hook below receives a HamiltonSalesInvoice instance as `doc`.

extend_doctype_class = {
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
# `purge_old_idempotency_records` (daily) — deletes Cash Sale Idempotency
# rows older than 24h. The DocType caches client_request_id → SI mappings
# for the T0-1 retail-sale idempotency contract; the retention window is
# operationally bounded by shift length, so 24h is generous. Wraps in
# try/except + Error Log per the Tier-1 audit requirement that scheduled
# jobs surface failures rather than silently logging "Success".
#
# `daily_orphan_check` (Task 35 — Phase 1 BLOCKER, integrity_checks.py)
# scans for submitted POS Sales Invoices in the past 24h that aren't
# linked to any POS Closing Entry. When orphans exist, emits an email
# to Hamilton Manager + Admin role-holders + writes a logger.warning.
# Wrapped in try/except per Tier-1 audit — scheduler errors must NOT
# silently terminate the job.

scheduler_events = {
	"daily": [
		"hamilton_erp.api.purge_old_idempotency_records",
		"hamilton_erp.integrity_checks.daily_orphan_check",
	],
}
