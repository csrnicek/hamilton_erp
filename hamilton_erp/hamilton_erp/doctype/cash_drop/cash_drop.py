import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# T1-4 per docs/inbox/2026-05-04_audit_synthesis_decisions.md.
# Sanity-bound on a single declared_amount to catch operator typos like
# $24,500 instead of $245.00. Above this, the form rejects with guidance
# to contact Chris for an admin override (Hamilton Board Correction path
# — DEC-066). Tuned generously so honest large drops still fit; if real
# operations regularly exceed this, raise the constant.
_DECLARED_AMOUNT_UPPER_BOUND = 5000.00

# T0-4 per docs/inbox/2026-05-04_audit_synthesis_decisions.md.
# Set of fields that are LOCKED from edit after the first save. Adding a
# new financially-meaningful field to Cash Drop later? Add it here. The
# point is the blind-cash anti-tamper invariant per DEC-005: an operator
# cannot drop $200, walk away, and then edit the record to $180 once
# they realize they're short. ``track_changes: 1`` records edits, but
# track_changes is post-hoc detection — this guard is prevention.
#
# ``reconciled``, ``reconciliation``, ``pos_closing_entry`` are already
# ``read_only: 1`` in the JSON, so they don't need to be in this set.
_IMMUTABLE_AFTER_FIRST_SAVE = (
	"declared_amount",
	"operator",
	"shift_record",
	"shift_date",
	"shift_identifier",
	"drop_type",
	"drop_number",
	"timestamp",
)

# Tip Pull negative-value warning threshold (Task 34, DEC-065).
# Operator can record a negative tip_pull_amount (e.g. returning cash to till
# after a mis-pull) but values more negative than this trigger an at-submit
# warning to catch typos like -$200 when -$2.00 was intended. The warning
# does NOT block submit — manager will see it on reconciliation.
_TIP_PULL_NEGATIVE_WARN_THRESHOLD = -50.0


class CashDrop(Document):
	def before_insert(self):
		"""Set tip_pull_currency from the venue's per-venue config.

		Multi-venue feature flag `frappe.conf.anvil_currency` is the canonical
		per-venue currency identifier (per docs/venue_rollout_playbook.md
		Phase B + DEC-064). When unset (e.g. during testing or pre-Phase-2
		venues), the JSON-default of "CAD" applies.
		"""
		if not self.tip_pull_currency:
			venue_currency = frappe.conf.get("anvil_currency")
			if venue_currency:
				self.tip_pull_currency = venue_currency

	def validate(self):
		self._set_timestamp()
		self._validate_declared_amount()
		self._validate_declared_amount_upper_bound()
		self._validate_shift_record_set()
		self._validate_shift_is_open()
		self._validate_operator_matches_shift()
		self._validate_immutable_after_first_save()
		self._validate_immutable_after_reconciliation()
		self._compute_tip_pull_difference()
		self._warn_on_large_negative_tip_pull()

	def _set_timestamp(self):
		if not self.timestamp:
			self.timestamp = now_datetime()

	def _validate_declared_amount(self):
		if self.declared_amount is not None and self.declared_amount < 0:
			frappe.throw(_("Declared Amount cannot be negative."))

	# ------------------------------------------------------------------
	# T1-4 — shift validation + declared-amount sanity bound
	# ------------------------------------------------------------------

	def _validate_declared_amount_upper_bound(self):
		"""T1-4: reject obviously-wrong declared amounts.

		Operator typo: meant $245.00, types $24500.00. The reconciliation
		manager would catch the variance, but a $24,500 drop bubbling up
		the chain wastes manager time. Hard reject here with guidance to
		use the admin-override path (DEC-066) for legitimate large drops.
		"""
		if (
			self.declared_amount is not None
			and flt(self.declared_amount) > _DECLARED_AMOUNT_UPPER_BOUND
		):
			frappe.throw(_(
				"Declared Amount {0} is above the ${1:.2f} sanity cap. "
				"If this is correct, ask Chris (Hamilton Admin) to issue "
				"a corrected drop via Hamilton Board Correction (DEC-066)."
			).format(flt(self.declared_amount), _DECLARED_AMOUNT_UPPER_BOUND))

	def _validate_shift_record_set(self):
		"""T1-4: shift_record must be set.

		Operator opens Cash Drop in Desk without first opening a Shift
		Record. Saves with ``shift_record = NULL``. End-of-shift
		reconciliation has unlinked drops — false theft flag at audit
		time. Reject here.
		"""
		if not self.shift_record:
			frappe.throw(_(
				"Shift Record is required. Open your shift via the operator "
				"flow before recording a Cash Drop."
			))

	def _validate_shift_is_open(self):
		"""T1-4: linked Shift Record must be in status 'Open'.

		An operator's shift was closed; somebody (admin user, automation,
		or the operator themselves) creates a Cash Drop pointing at the
		now-closed Shift Record. The audit trail then contains a drop
		attached to a closed shift, breaking chronological invariants.
		"""
		if not self.shift_record:
			# Caught by _validate_shift_record_set; defensive guard here.
			return
		shift_status = frappe.db.get_value(
			"Shift Record", self.shift_record, "status"
		)
		if shift_status != "Open":
			frappe.throw(_(
				"Cannot record a Cash Drop against a {0} Shift Record. "
				"Only an open shift can receive drops."
			).format(shift_status or "missing"))

	def _validate_operator_matches_shift(self):
		"""T1-4: operator on the drop must equal operator on the linked shift.

		Without this, Operator A could accidentally drop into Operator B's
		shift, skewing B's end-of-shift reconciliation. Reject early.
		"""
		if not self.shift_record or not self.operator:
			return
		shift_operator = frappe.db.get_value(
			"Shift Record", self.shift_record, "operator"
		)
		if shift_operator and shift_operator != self.operator:
			frappe.throw(_(
				"Cash Drop operator {0} does not match the Shift Record's "
				"operator {1}. The drop must be recorded against the operator "
				"who owns the shift."
			).format(self.operator, shift_operator))

	# ------------------------------------------------------------------
	# T0-4 — immutability after first save / after reconciliation
	# ------------------------------------------------------------------

	def _validate_immutable_after_first_save(self):
		"""T0-4: financial / identity fields cannot be edited after first save.

		Restores the blind-cash anti-tamper invariant per DEC-005: an
		operator cannot drop $200, walk away, then quietly edit the
		record to $180 once they realize they're short. ``track_changes:
		1`` records the edit but doesn't prevent it; this guard is
		prevention.

		Carve-outs:
		- ``self.is_new()`` — first save is fine.
		- ``frappe.flags.allow_cash_drop_correction`` — admin-correction
		  path (DEC-066). Hamilton Admin can use a controlled endpoint
		  that sets this flag; the underlying edit produces a Hamilton
		  Board Correction row capturing reason + before/after values.
		"""
		if self.is_new():
			return
		if getattr(frappe.flags, "allow_cash_drop_correction", False):
			return
		original = self.get_doc_before_save()
		if original is None:
			# Expected to be available on every non-new save; defensive
			# fall-through here so a malformed Frappe call doesn't bypass.
			return
		changed = [
			f for f in _IMMUTABLE_AFTER_FIRST_SAVE
			if self.get(f) != original.get(f)
		]
		if changed:
			frappe.throw(_(
				"Cannot edit Cash Drop fields after first save: {0}. "
				"Blind-cash invariant per DEC-005. For a legitimate "
				"correction, ask Hamilton Admin to issue a Hamilton Board "
				"Correction (DEC-066)."
			).format(", ".join(sorted(changed))))

	def _validate_immutable_after_reconciliation(self):
		"""T0-4: once reconciled, the drop is fully frozen.

		After Cash Reconciliation submits, the Cash Drop's ``reconciled``
		flag flips to 1 and ``reconciliation`` links the new
		reconciliation row. From that moment, no field on the drop is
		editable except via the controlled admin-correction path (DEC-066).

		Carve-out: same ``frappe.flags.allow_cash_drop_correction``
		escape hatch as the first-save guard.
		"""
		if self.is_new():
			return
		if getattr(frappe.flags, "allow_cash_drop_correction", False):
			return
		# Use the persisted ``reconciled`` value, not the in-memory one —
		# the in-memory copy could be a draft mutation that hasn't been
		# rejected yet. The persisted value is the source of truth.
		persisted_reconciled = frappe.db.get_value(
			"Cash Drop", self.name, "reconciled"
		)
		if not persisted_reconciled:
			return
		original = self.get_doc_before_save()
		if original is None:
			return
		changed = [
			f for f in self.meta.get("fields", [])
			if self.get(f.fieldname) != original.get(f.fieldname)
		]
		if changed:
			fieldnames = sorted(set(c.fieldname for c in changed))
			frappe.throw(_(
				"Cannot edit Cash Drop {0} after reconciliation: changes "
				"detected in {1}. Use Hamilton Board Correction (DEC-066) "
				"if a legitimate correction is needed."
			).format(self.name, ", ".join(fieldnames)))

	def _compute_tip_pull_difference(self):
		"""Calculated field: tip_pull_amount - tip_settled_via_processor_amount.

		Phase 1: tip_settled_via_processor_amount stays 0 (Phase 2 settlement-
		pairing job populates it), so the difference equals tip_pull_amount in
		Phase 1. The calculation is wired now so Phase 2 doesn't need to add it.
		"""
		self.tip_pull_difference = flt(self.tip_pull_amount or 0) - flt(
			self.tip_settled_via_processor_amount or 0
		)

	def _warn_on_large_negative_tip_pull(self):
		"""Surface a non-blocking warning when tip_pull_amount is unusually negative.

		Negative tip_pull_amount is allowed (e.g. operator returned cash to the
		till after a mis-pull) but values past _TIP_PULL_NEGATIVE_WARN_THRESHOLD
		are likely typos (e.g. -200 when -2.00 was meant) and warrant a sanity
		check. The warning is informational; submit still succeeds. Manager
		sees the value on reconciliation regardless.
		"""
		amt = flt(self.tip_pull_amount or 0)
		if amt < _TIP_PULL_NEGATIVE_WARN_THRESHOLD:
			frappe.msgprint(
				_("Tip Pull Amount is unusually negative ({0}). "
				  "If this is a typo (e.g. -200 instead of -2.00), correct it before submitting. "
				  "If intentional, manager will review on reconciliation.").format(amt),
				title=_("Confirm Tip Pull Amount"),
				indicator="orange",
				alert=True,
			)
