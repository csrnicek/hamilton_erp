// Cash Drop form client script
// The Cash Drop screen (Phase 3) is a full custom page.
// This form view is for manager review only — operators use the custom page.

frappe.ui.form.on("Cash Drop", {
	refresh(frm) {
		if (!frm.doc.reconciled) {
			frm.set_intro(__("This drop has not yet been reconciled."), "orange");
		} else {
			frm.set_intro(__("Reconciled."), "green");
		}
	},
});
