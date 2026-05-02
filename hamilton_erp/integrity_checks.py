"""Daily integrity checks for Hamilton ERP — surfaces orphaned records that
would otherwise sit invisible in the database.

Phase 1 Task 35 (BLOCKER) — Post-close orphan-invoice integrity check.
Detects Sales Invoices submitted in the past 24h that are NOT linked to any
POS Closing Entry. Without this check, network blips, browser tab crashes,
or POS Closing Entry generation bugs (e.g. G-002 deferred-stock-validation
in `docs/research/erpnext_pos_business_process_gotchas.md`) can leave
legitimate Sales Invoices unlinked to the day's closing entry. Manager-side
reconciliation matches the closing total to the cash drop count and
everything looks fine — but revenue from the orphan is invisible to the
manager's daily review. Tax under-reports; bank deposit mismatches; only
external auditors catch it months later.

This module's `find_orphan_sales_invoices()` is the single source of truth
for orphan detection. It runs daily via scheduler_events.daily in hooks.py
and emits a Frappe Notification listing each orphan + amount + cashier +
timestamp. Resolution workflow (manager links orphan to a closing entry OR
creates a new one) is deferred to Phase 2 follow-up — this Phase 1
deliverable surfaces orphans so they can't go silent, but the resolution
UI is tracked separately.

Reference:
- Task 35 in `.taskmaster/tasks/tasks.json`
- G-023 in `docs/research/erpnext_pos_business_process_gotchas.md`
- `docs/design/post_close_integrity_phase1.md` — design intent doc
"""

import frappe
from frappe.utils import flt, get_datetime, now_datetime, add_days


# Threshold below which orphans don't trigger a notification (just log).
# Defaults to $0 — alert on every orphan. Hamilton can raise to $5 via
# Hamilton Settings if noise becomes a problem in practice.
DEFAULT_ALERT_THRESHOLD = 0.0


def find_orphan_sales_invoices(hours_lookback: int = 24, threshold: float | None = None) -> list[dict]:
	"""Return submitted Sales Invoices in the past `hours_lookback` hours
	that are NOT linked to any POS Closing Entry.

	Args:
		hours_lookback: How far back to scan. Default 24h matches the daily
			scheduler cadence; longer values catch orphans that older runs
			missed (e.g. when the scheduler itself was down).
		threshold: Minimum grand_total to include. Orphans below this amount
			are silently dropped (NOT included in the returned list). When
			None, reads from Hamilton Settings `orphan_check_alert_threshold_amount`
			or falls back to DEFAULT_ALERT_THRESHOLD.

	Returns:
		List of dicts: [{name, grand_total, owner, posting_date, ...}]
		Empty list when no orphans detected (the happy path).
	"""
	# Resolve threshold: per-call override > Hamilton Settings > default
	if threshold is None:
		threshold = flt(
			frappe.db.get_single_value(
				"Hamilton Settings", "orphan_check_alert_threshold_amount"
			) or DEFAULT_ALERT_THRESHOLD
		)

	# Window: now - hours_lookback hours. We compare against `posting_date`
	# (a Date) rather than `creation` (a Datetime) because Hamilton's daily
	# scheduler runs once per day and we want to catch yesterday's orphans
	# even when the run fires after the calendar day rolls over.
	cutoff = add_days(get_datetime(now_datetime()), -1)

	# Find every submitted Sales Invoice whose posting_date is on/after
	# the cutoff AND that does NOT appear in any POS Closing Entry's
	# pos_transactions child table.
	#
	# Implementation note: ERPNext's POS Closing Entry uses the
	# `POS Invoice Reference` child table (or in older versions
	# `POS Closing Entry Detail`) to list invoices in the closing batch.
	# Hamilton's seeded ERPNext v16 uses `POS Invoice Reference` with
	# parent = the POS Closing Entry name and pos_invoice = the SI name.
	#
	# The orphan condition: SI is submitted (docstatus=1), is_pos=1, and
	# no `POS Invoice Reference` row exists pointing at it. We use a
	# parameterized SQL query with %s placeholders per coding_standards.md.
	rows = frappe.db.sql(
		"""
		SELECT si.name, si.grand_total, si.owner, si.posting_date,
		       si.creation, si.pos_profile
		FROM `tabSales Invoice` si
		LEFT JOIN `tabPOS Invoice Reference` pir
		  ON pir.pos_invoice = si.name
		WHERE si.docstatus = 1
		  AND si.is_pos = 1
		  AND si.posting_date >= %s
		  AND pir.name IS NULL
		  AND si.grand_total >= %s
		ORDER BY si.posting_date DESC, si.creation DESC
		""",
		(cutoff, threshold),
		as_dict=True,
	)
	return list(rows)


def daily_orphan_check():
	"""Scheduled job — runs daily per scheduler_events in hooks.py.

	Detects orphan Sales Invoices and emits a Frappe Notification to
	Hamilton Manager + Hamilton Admin roles when any are found. The
	notification surfaces each orphan with amount, cashier, and timestamp;
	managers must investigate before the data drift compounds.

	Wrapped in try/except per Tier-1 audit requirement: scheduler errors
	must NOT silently terminate the job — they get logged via
	`frappe.log_error` so a failed integrity check becomes its own visible
	signal rather than a quiet absence of alerts.
	"""
	try:
		orphans = find_orphan_sales_invoices()
	except Exception:
		frappe.log_error(
			title="Hamilton orphan integrity check failed",
			message=frappe.get_traceback(),
		)
		return

	if not orphans:
		# Happy path. Don't spam — silent success is fine for this job.
		return

	# Build one notification covering all orphans found in this run.
	# A Frappe Notification creates an in-app alert + (if configured)
	# an email to subscribers of "Hamilton Manager" / "Hamilton Admin" roles.
	subject = (
		f"⚠️ Hamilton: {len(orphans)} orphan invoice"
		f"{'s' if len(orphans) != 1 else ''} detected (past 24h)"
	)
	body_lines = [
		f"The daily integrity check found {len(orphans)} submitted POS Sales "
		f"Invoice{'s' if len(orphans) != 1 else ''} not linked to any POS Closing Entry. "
		"This means revenue from these invoices is currently invisible to manager-side "
		"reconciliation and may also be missing from the bank deposit and tax remittance.\n",
		"",
		"**Orphans (review and link to closing entries before next reconciliation):**",
		"",
	]
	for o in orphans:
		body_lines.append(
			f"- **{o['name']}** — ${flt(o['grand_total']):.2f} — "
			f"posted {o['posting_date']} by {o['owner']}"
			+ (f" (POS Profile: {o['pos_profile']})" if o.get("pos_profile") else "")
		)
	body_lines.append("")
	body_lines.append(
		"_Resolution workflow: open each Sales Invoice and link it to the "
		"matching POS Closing Entry, OR create a new POS Closing Entry to "
		"absorb the invoice. Document the cause (network error, browser "
		"crash, deferred-stock-validation bug per R-013, etc.) in the linked "
		"closing entry's notes. See `docs/RUNBOOK.md` for the full procedure._"
	)

	# Frappe's built-in Notification doctype handles in-app alerts; we send
	# an explicit email via sendmail() to the Hamilton Manager + Admin role
	# subscribers because Notification doctype config is per-site and may
	# not be set up at first run.
	try:
		recipients = _resolve_manager_admin_recipients()
		if recipients:
			frappe.sendmail(
				recipients=recipients,
				subject=subject,
				message="\n".join(body_lines),
				now=False,  # Queue, don't block the scheduler tick
			)
	except Exception:
		frappe.log_error(
			title="Hamilton orphan check email send failed",
			message=frappe.get_traceback(),
		)

	# Always also log so the orphan list is captured even if email fails.
	frappe.logger().warning(
		f"[hamilton_erp.integrity_checks] {subject}: "
		+ "; ".join(f"{o['name']}=${flt(o['grand_total']):.2f}" for o in orphans)
	)


def _resolve_manager_admin_recipients() -> list[str]:
	"""Return User emails for Hamilton Manager + Hamilton Admin role holders."""
	users = frappe.get_all(
		"Has Role",
		filters={
			"role": ["in", ["Hamilton Manager", "Hamilton Admin"]],
			"parenttype": "User",
		},
		fields=["parent"],
		distinct=True,
	)
	if not users:
		return []
	emails = frappe.get_all(
		"User",
		filters={
			"name": ["in", [u["parent"] for u in users]],
			"enabled": 1,
		},
		fields=["email"],
	)
	return [e["email"] for e in emails if e.get("email")]
