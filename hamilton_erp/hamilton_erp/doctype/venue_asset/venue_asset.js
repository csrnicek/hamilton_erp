// Venue Asset form client script
// Phase 1 adds interactive status controls and board navigation.

frappe.ui.form.on("Venue Asset", {
	refresh(frm) {
		// Read-only badge for current status
		frm.set_intro(
			__("Status: {0}", [frm.doc.status]),
			frm.doc.status === "Available"
				? "blue"
				: frm.doc.status === "Occupied"
				? "red"
				: frm.doc.status === "Dirty"
				? "orange"
				: "grey"
		);
	},
});
