// Shift Record form client script

frappe.ui.form.on("Shift Record", {
	float_actual(frm) {
		const variance = flt(frm.doc.float_actual) - flt(frm.doc.float_expected);
		frm.set_value("float_variance", variance);
	},
});
