// Cash Reconciliation form client script
// Full implementation in Phase 3 (manager reconciliation screen).
// The form must NEVER be accessible to Hamilton Operator role — enforced via permissions.

frappe.ui.form.on("Cash Reconciliation", {
	refresh(frm) {
		if (!frm.doc.docstatus) {
			// Before submission, hide the reveal section so the manager
			// cannot see expected amounts before entering their blind count.
			frm.set_df_property("section_reveal", "hidden", 1);
			frm.set_df_property("operator_declared", "hidden", 1);
			frm.set_df_property("system_expected", "hidden", 1);
			frm.set_df_property("variance_flag", "hidden", 1);
		}
	},
});
