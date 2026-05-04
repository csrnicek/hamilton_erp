import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# Variance tolerance defaults: 2% of the larger amount, with a $1.00 minimum
# floor. A flat $0.05 tolerance is too strict for real cash handling — a
# single mis-counted bill would flag a $500 drop as non-Clean. Both values
# are now configurable per venue via Hamilton Settings (F3.5 / DEC-068);
# the constants below are used only as fallbacks when Settings is missing
# or when either field is blank.
_VARIANCE_TOLERANCE_PCT_DEFAULT = 0.02
_VARIANCE_TOLERANCE_MIN_DEFAULT = 1.00


def _get_variance_tolerance() -> tuple[float, float]:
	"""Read the variance tolerance from Hamilton Settings.

	Returns (percent_as_fraction, minimum_dollars). The percent stored in
	Settings is a Percent field (e.g. 2.0 means 2%); we convert to a
	fraction (0.02) so callers don't need to know the storage shape.

	Falls back to the module-level defaults when Settings is missing or
	either field is blank — keeps the fresh-install / migrate-pending path
	working, and stays robust to operator-cleared values.
	"""
	try:
		settings = frappe.get_cached_doc("Hamilton Settings", "Hamilton Settings")
	except frappe.DoesNotExistError:
		return _VARIANCE_TOLERANCE_PCT_DEFAULT, _VARIANCE_TOLERANCE_MIN_DEFAULT
	pct_raw = settings.get("cash_variance_tolerance_percent")
	min_raw = settings.get("cash_variance_tolerance_minimum")
	pct = (flt(pct_raw) / 100.0) if pct_raw else _VARIANCE_TOLERANCE_PCT_DEFAULT
	minimum = flt(min_raw) if min_raw else _VARIANCE_TOLERANCE_MIN_DEFAULT
	return pct, minimum


def _within_tolerance(a: float, b: float) -> bool:
	"""Return True if |a - b| is within the configured percentage tolerance."""
	pct, minimum = _get_variance_tolerance()
	diff = abs(a - b)
	threshold = max(abs(a), abs(b)) * pct
	return diff <= max(threshold, minimum)


class CashReconciliation(Document):
	def validate(self):
		self._set_timestamp()

	def before_submit(self):
		"""Populate revealed fields and calculate variance flag on submission.

		The three-way comparison is only revealed after the manager submits
		their blind count — never before.  See build spec §7.7 and
		coding_standards.md §8.3.
		"""
		if self.actual_count is None:
			frappe.throw(_("Please enter the cash count before submitting."))
		self._validate_no_duplicate_reconciliation()
		self._populate_operator_declared()
		self._calculate_system_expected()
		self._set_variance_flag()

	def _validate_no_duplicate_reconciliation(self):
		"""T1-5 per docs/inbox/2026-05-04_audit_synthesis_decisions.md:
		every Cash Drop reconciles AT MOST once.

		Two managers opening the same Cash Drop and racing to submit
		reconciliations would otherwise both succeed (no DB constraint,
		no app-level guard) — and ``_mark_drop_reconciled`` would
		overwrite the Cash Drop's ``reconciliation`` link to whichever
		submitted second. Manager A's reconciliation row would orphan;
		auditors querying "show me the reconciliation for DROP-X" would
		see only Manager B's. The audit trail loses a record.

		This guard rejects the second submission with a clear error
		pointing at the existing reconciliation. Same-row resubmission
		(e.g. an amend flow) is allowed via the ``name != self.name``
		filter.
		"""
		if not self.cash_drop:
			return
		existing = frappe.db.exists(
			"Cash Reconciliation",
			{
				"cash_drop": self.cash_drop,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(_(
				"This Cash Drop has already been reconciled by "
				"{0}. A drop reconciles at most once."
			).format(existing))

	def on_submit(self):
		"""Mark the linked Cash Drop as reconciled after successful submission.

		Runs after docstatus = 1 is committed, so the reconciliation link
		is only written when the Cash Reconciliation is fully submitted.
		Previously this was in before_submit, which risked marking the drop
		reconciled even if submission failed and rolled back.
		"""
		self._mark_drop_reconciled()

	def on_cancel(self):
		# Reset Cash Drop.reconciled when this reconciliation is cancelled.
		# Without this the drop stays reconciled=1 forever, and T0-4's
		# _validate_immutable_after_reconciliation then freezes every
		# field on the drop with no way to recover.
		# Only resets when the drop's current reconciliation link still
		# points at this row — don't clobber a newer reconciliation.
		if not self.cash_drop:
			return
		current_link = frappe.db.get_value(
			"Cash Drop", self.cash_drop, "reconciliation"
		)
		if current_link == self.name:
			frappe.db.set_value(
				"Cash Drop",
				self.cash_drop,
				{"reconciled": 0, "reconciliation": None},
				update_modified=False,
			)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _set_timestamp(self):
		if not self.timestamp:
			self.timestamp = now_datetime()

	def _populate_operator_declared(self):
		"""Copy the declared amount from the linked Cash Drop."""
		declared = frappe.db.get_value("Cash Drop", self.cash_drop, "declared_amount")
		self.operator_declared = flt(declared)

	def _calculate_system_expected(self):
		"""Calculate system_expected from POS transactions.

		Phase 3 implementation.  The full calculation will be:
		    system_expected = sum_of_cash_sales
		                    - sum_of_cash_refunds  (Phase 2 — Task 31)
		                    - tip_pull_amount      (Phase 1 schema, hook below)

		The tip-pull subtraction is wired NOW (Task 34, DEC-065) so that when
		Phase 3 lands the real sum_of_cash_sales calculation, tip-pull handling
		is automatic — no separate Phase 3 follow-up needed for tip handling.
		Today, sum_of_cash_sales is the placeholder 0; the subtraction is
		mathematically -tip_pull_amount (0 - 0 - tip_pull) but the WIRING is in
		place. R-011 in docs/risk_register.md tracks this placeholder state.
		"""
		# Placeholder — Phase 3 wires up the real sum_of_cash_sales calculation.
		# The field is set to 0 here so the schema is valid, not left null.
		sum_of_cash_sales = flt(0)
		sum_of_cash_refunds = flt(0)  # Phase 2 — Task 31

		# Tip-pull subtraction hook (Task 34 / DEC-065 — wired in Phase 1 schema).
		# Reads tip_pull_amount from the linked Cash Drop. Stays at 0 until an
		# operator records an actual tip pull. When Phase 3 lands the real
		# sum_of_cash_sales, this subtraction makes recon correct automatically.
		tip_pull_amount = flt(0)
		if self.cash_drop:
			tip_pull_amount = flt(
				frappe.db.get_value("Cash Drop", self.cash_drop, "tip_pull_amount") or 0
			)

		self.system_expected = sum_of_cash_sales - sum_of_cash_refunds - tip_pull_amount

	def _set_variance_flag(self):
		"""T0-2 Path B / DEC-069: classification short-circuited until Phase 3.

		The original three-way variance rule (Clean / Possible Theft or Error
		/ Operator Mis-declared) depends on `system_expected` being a real
		number computed from POS Sales Invoice cash payment lines for the
		shift period. `_calculate_system_expected` is a Phase 3 placeholder
		that hardcodes 0, so the classifier ran every reconciliation against
		`system = 0` and produced a false-positive variance flag on EVERY
		drop with non-zero cash. R-011 in `docs/risk_register.md`.

		Until Phase 3 ships the real calculation, the flag is set to
		`"Pending Phase 3"` regardless of inputs and the three-way rule is
		not invoked. Managers reconcile cash physically per the manual
		procedure in `docs/HAMILTON_LAUNCH_PLAYBOOK.md` #3 +
		`docs/RUNBOOK.md` §7.2 (manager counts envelope, matches
		declared_amount on the printed label, signs paper).

		NEW-1 bundled: `variance_amount` is still computed (so the manager
		sees a meaningful number, not $0.00) — it's just `actual_count -
		system_expected`, which until Phase 3 equals `actual_count - 0 =
		actual_count`. After Phase 3, the same line continues to work
		against the real system_expected.
		"""
		self.variance_amount = flt(self.actual_count) - flt(self.system_expected)
		self.variance_flag = "Pending Phase 3"

	def _mark_drop_reconciled(self):
		"""Update the linked Cash Drop as reconciled.

		T3-1: use the Document API instead of frappe.db.set_value. The
		bypass-the-controller pattern was acceptable when CashDrop had
		no validate body that needed to fire post-reconciliation, but
		track_changes is enabled on Cash Drop and a direct DB write
		skips the audit-trail capture. Going through .save() restores
		the audit trail, fires any future doc_events, and re-runs
		validate (currently a no-op for the reconciled / reconciliation
		fields, but cheap insurance against a future controller change
		that adds a guard the direct write would silently bypass).
		"""
		drop = frappe.get_doc("Cash Drop", self.cash_drop)
		drop.reconciled = 1
		drop.reconciliation = self.name
		drop.save(ignore_permissions=True)
