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

		// T0-2 Path B / DEC-069: variance classification is hard-disabled
		// until Phase 3 wires up the real `system_expected` calculation.
		// Surface this prominently on the form so a manager who opens a
		// Cash Reconciliation today knows the flag will read "Pending
		// Phase 3" regardless of inputs and that they should use the
		// manual reconciliation procedure.
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline(
			__(
				"<strong>Variance classification disabled until Phase 3.</strong> " +
				"System-expected calculation is Phase 3 work — variance flag reads " +
				"\"Pending Phase 3\" regardless of inputs. " +
				"Use the manual reconciliation procedure: manager counts the envelope, " +
				"matches the declared amount on the printed label, signs off on paper. " +
				"See HAMILTON_LAUNCH_PLAYBOOK.md #3 and RUNBOOK.md §7.2."
			),
			"orange",
		);
	},
});
