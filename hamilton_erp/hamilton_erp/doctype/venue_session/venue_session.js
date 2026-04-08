// Venue Session form client script

frappe.ui.form.on("Venue Session", {
	refresh(frm) {
		if (frm.doc.status === "Active") {
			frm.add_custom_button(__("View Asset Board"), () => {
				frappe.set_route("asset-board");
			});
		}
	},
});
