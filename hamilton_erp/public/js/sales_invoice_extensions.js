// Hamilton ERP — Sales Invoice client extensions.
//
// Adds a "Reprint Receipt" button to submitted POS Sales Invoices for
// Hamilton Manager / Hamilton Admin / System Manager. Hamilton Operator
// is deliberately excluded — see DEC-098 (reprint role policy).
//
// The button calls `hamilton_erp.printing.reprint_cash_receipt`, which
// re-renders the "Hamilton Cash Receipt" print format and dispatches it
// to the Epson TM-T20III. Same dev-mode escape hatches apply (frappe.in_test
// and Hamilton Settings.receipt_printer_enabled) — the operator-facing
// behaviour is identical to the original post-submit print.

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		const reprint_roles = ["Hamilton Manager", "Hamilton Admin", "System Manager"];
		const has_reprint_role = (frappe.user_roles || []).some((r) => reprint_roles.includes(r));

		// Only show on submitted POS invoices (is_pos=1, docstatus=1) so the
		// button never appears on drafts or non-POS Sales Invoices.
		if (
			has_reprint_role
			&& frm.doc.is_pos === 1
			&& frm.doc.docstatus === 1
		) {
			frm.add_custom_button(__("Reprint Receipt"), () => {
				frappe.call({
					method: "hamilton_erp.printing.reprint_cash_receipt",
					args: { sales_invoice: frm.doc.name },
					freeze: true,
					freeze_message: __("Reprinting receipt..."),
					callback: (r) => {
						if (r.exc) return;
						const status = (r.message && r.message.status) || "unknown";
						if (status === "printed") {
							frappe.show_alert({
								message: __("Receipt sent to printer at {0}", [r.message.ip]),
								indicator: "green",
							});
						} else if (status === "skipped") {
							frappe.show_alert({
								message: __("Reprint skipped: {0}", [r.message.reason]),
								indicator: "orange",
							});
						}
					},
				});
			});
		}
	},
});
