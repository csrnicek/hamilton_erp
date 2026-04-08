// Comp Admission Log — read-only audit trail form
// Created programmatically during the comp admission flow (Phase 2).

frappe.ui.form.on("Comp Admission Log", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.disable_save();
		}
	},
});
