// Asset Status Log — read-only audit trail form
// Created programmatically via utils.create_asset_status_log — not manually.

frappe.ui.form.on("Asset Status Log", {
	refresh(frm) {
		frm.disable_save();
	},
});
