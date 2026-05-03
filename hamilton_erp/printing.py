"""Receipt printing for the Epson TM-T20III thermal printer.

Hardware contract — DEC-098.

Pipeline:
  ``submit_retail_sale`` (api.py) → ``print_cash_receipt`` (orchestrator) →
  ``_render_receipt`` (Jinja → string) → ``_dispatch_to_printer`` (TCP socket
  → ESC/POS bytes → printer).

Blocking rule (DEC-098, mirrors R-012's cash-drop label rule):
  No receipt = no completed sale. If dispatch fails for any reason
  (network timeout, paper out, blank GST/HST registration number,
  Hamilton Settings missing) the orchestrator throws ``ValidationError``
  which bubbles out of ``submit_retail_sale``. The Frappe request-level
  rollback then reverses the SI submit, so the operator never sees
  "sale done" without a paper receipt.

Dev escape hatches (the only place the blocking rule is bypassed):
  1. ``frappe.in_test`` is True — short-circuits to a logged no-op so the
     test suite does not depend on a physical printer.
  2. ``Hamilton Settings.receipt_printer_enabled = 0`` — manual operator
     override, lets dev work proceed when the printer is offline. Both
     escape hatches log a clear marker so the absence of a print is
     auditable.

Print-format selection by NAME (not via ``pos_profile.print_format``):
  Frappe v16 issue #53857 — POS Profile's print-format filter UI omits
  Sales Invoice formats, only shows POS Invoice formats. Hamilton's
  retail flow uses Sales Invoice (is_pos=1). We therefore pass the
  print-format name explicitly to ``frappe.get_print``; we do NOT rely
  on the POS Profile field. When ERPNext fixes #53857 the workaround
  remains correct, just becomes redundant.

References:
  - DEC-098 (this file's authoritative decision record)
  - DEC-097 (GST/HST registration number — printed on every receipt)
  - R-012 (cash-drop label print rule — same blocking pattern)
  - docs/inbox.md "Receipt printing — Epson TM-T20III" (CRA receipt content)
"""

from __future__ import annotations

import socket

import frappe
from frappe import _

# The print-format name is referenced by string here (not via the POS
# Profile) per the Frappe v16 #53857 workaround. Keep this constant in
# sync with the print-format JSON's `"name"` field.
HAMILTON_RECEIPT_PRINT_FORMAT = "Hamilton Cash Receipt"

# TCP timeout for the Epson dispatch. Receipt printing is on the
# critical path of the sale completion, so a slow / unreachable printer
# must surface as an error in human time, not block the operator for
# 30+ seconds. 5 s is generous for a LAN-attached thermal printer.
PRINTER_TIMEOUT_SECONDS = 5

# ESC/POS control bytes. python-escpos can construct these for us, but
# since the receipt format is intentionally simple (header + lines +
# total + cut), we send the rendered text plus the cut command directly
# to keep the dependency surface minimal in the dispatch path.
ESCPOS_INIT = b"\x1b@"  # ESC @ — initialise printer
ESCPOS_CUT = b"\x1dV\x42\x00"  # GS V B — partial cut with feed


def _get_printer_config() -> tuple[str | None, bool]:
	"""Return ``(ip, enabled)`` from Hamilton Settings.

	Returns ``(None, False)`` if Hamilton Settings is missing entirely
	(brand-new site, pre-migrate, etc.) so the orchestrator can treat
	"no settings" the same as "printer disabled" for the dev-escape-
	hatch decision.
	"""
	if not frappe.db.exists("DocType", "Hamilton Settings"):
		return (None, False)
	try:
		settings = frappe.get_cached_doc("Hamilton Settings")
	except frappe.DoesNotExistError:
		return (None, False)
	ip = (settings.get("receipt_printer_ip") or "").strip() or None
	enabled = bool(settings.get("receipt_printer_enabled"))
	return (ip, enabled)


def _render_receipt(sales_invoice_name: str) -> str:
	"""Render the ``Hamilton Cash Receipt`` print format for an SI.

	Validates the GST/HST registration number is non-empty BEFORE
	rendering (per DEC-097) — a blank value blocks the sale rather than
	silently printing a CRA-non-compliant receipt.

	Loads the print format by NAME, NOT via the POS Profile (Frappe v16
	issue #53857).
	"""
	settings = frappe.get_cached_doc("Hamilton Settings")
	gst_hst_number = (settings.get("gst_hst_registration_number") or "").strip()
	if not gst_hst_number:
		frappe.throw(_(
			"GST/HST Registration Number is blank in Hamilton Settings. "
			"CRA-compliant receipts require this value (DEC-097). "
			"Open Hamilton Settings → Receipts and paste in the registration number "
			"before completing a cash sale."
		))

	# Pass print_format explicitly — see DEC-098 / Frappe issue #53857.
	rendered = frappe.get_print(
		doctype="Sales Invoice",
		name=sales_invoice_name,
		print_format=HAMILTON_RECEIPT_PRINT_FORMAT,
	)
	return rendered


def _dispatch_to_printer(rendered_content: str, ip: str) -> None:
	"""Send ``rendered_content`` to the Epson at ``ip`` via raw TCP socket.

	Throws ``frappe.ValidationError`` on any IO error so the caller
	(``print_cash_receipt``) can fail the sale cleanly. Errors are
	intentionally NOT caught here — the surrounding transaction must
	roll back when this fails (DEC-098 blocking rule).
	"""
	if not ip:
		frappe.throw(_(
			"Receipt Printer IP is blank in Hamilton Settings. "
			"Set the Epson TM-T20III IP under Hamilton Settings → Receipts."
		))

	# python-escpos provides a higher-level abstraction (escpos.printer.Network)
	# but for Hamilton's simple receipt the raw socket dispatch is more
	# transparent and fails cleanly with normal socket exceptions, which
	# integrate well with the Frappe ValidationError flow. The dependency
	# is still declared in pyproject.toml because the operator-facing
	# operations playbook references it for diagnostic / re-print tooling.
	payload = ESCPOS_INIT + rendered_content.encode("cp437", errors="replace") + b"\n\n\n" + ESCPOS_CUT

	sock = None
	try:
		sock = socket.create_connection((ip, 9100), timeout=PRINTER_TIMEOUT_SECONDS)
		sock.sendall(payload)
	except (socket.timeout, OSError) as exc:
		frappe.throw(_(
			"Receipt printer dispatch failed: could not reach Epson TM-T20III at {0} ({1}). "
			"Check power, network cable / WiFi, paper, and that the printer is online. "
			"The sale has been rolled back; retry once the printer is reachable."
		).format(ip, exc))
	finally:
		if sock is not None:
			try:
				sock.close()
			except OSError:
				# Best-effort close. We've already sent the payload (or
				# raised); a close error here should not mask the real
				# outcome above.
				pass


def print_cash_receipt(sales_invoice_name: str) -> dict:
	"""Orchestrate render + dispatch for a Sales Invoice.

	Returns a small status dict for logging / test assertions:
	  - ``{"status": "skipped", "reason": "test_mode"}`` when ``frappe.in_test``
	  - ``{"status": "skipped", "reason": "disabled"}`` when the Hamilton
	    Settings flag is unchecked (or Settings is missing entirely)
	  - ``{"status": "printed", "ip": "<ip>"}`` on a successful dispatch

	Throws ``frappe.ValidationError`` (via the underlying helpers) on
	any failure outside the two short-circuit conditions. Callers that
	hold a transaction open MUST let the throw bubble — a caught throw
	would leave a submitted SI without a receipt, violating DEC-098.
	"""
	# Test-mode escape hatch. We log via frappe.logger so the absence of
	# a print is auditable in test logs without polluting the regular
	# Error Log. Tests assert on the return value rather than the log.
	if getattr(frappe, "in_test", False):
		frappe.logger("hamilton_erp.printing").info(
			f"print_cash_receipt: skipped (frappe.in_test=True) for {sales_invoice_name}"
		)
		return {"status": "skipped", "reason": "test_mode"}

	ip, enabled = _get_printer_config()
	if not enabled:
		frappe.logger("hamilton_erp.printing").info(
			f"print_cash_receipt: skipped (receipt_printer_enabled=0) for {sales_invoice_name}"
		)
		return {"status": "skipped", "reason": "disabled"}

	rendered = _render_receipt(sales_invoice_name)
	_dispatch_to_printer(rendered, ip)
	return {"status": "printed", "ip": ip}


# ---------------------------------------------------------------------------
# Reprint endpoint
# ---------------------------------------------------------------------------
# Manager / Admin-gated; calls the same orchestrator. Operator role is
# DELIBERATELY excluded (DEC-098 reprint role policy) — the cart's
# automatic print is the operator's only print path; reprints are a
# manager-supervised operation to keep the receipt-as-control-token
# discipline intact (one paper receipt per sale, multiple operator-
# initiated reprints would muddy the asset-board hook discipline).

REPRINT_ALLOWED_ROLES = {"Hamilton Manager", "Hamilton Admin", "System Manager"}


def _check_reprint_permission() -> None:
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (user_roles & REPRINT_ALLOWED_ROLES):
		frappe.throw(
			_("Reprint Receipt requires Hamilton Manager or Hamilton Admin. "
			  "Required role: one of {0}").format(", ".join(sorted(REPRINT_ALLOWED_ROLES))),
			frappe.PermissionError,
		)


@frappe.whitelist(methods=["POST"])
@frappe.rate_limit(limit=60, seconds=60)
def reprint_cash_receipt(sales_invoice: str) -> dict:
	"""Re-render and re-dispatch the cash receipt for an existing SI.

	Manager / Admin / System Manager only — see ``REPRINT_ALLOWED_ROLES``
	and DEC-098. Uses the same orchestrator as the post-submit print
	path, so the dev escape hatches and the GST/HST validation behave
	identically on reprint.
	"""
	_check_reprint_permission()
	if not sales_invoice:
		frappe.throw(_("sales_invoice is required"))
	if not frappe.db.exists("Sales Invoice", sales_invoice):
		frappe.throw(_("Sales Invoice {0} does not exist").format(sales_invoice))
	return print_cash_receipt(sales_invoice)
