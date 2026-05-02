import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today


class TestCashDrop(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def _make_shift(
		self, operator: str = "Administrator", status: str = "Open"
	) -> object:
		"""Create a Shift Record fixture in the requested status.

		Required after T1-4 (per docs/inbox/2026-05-04_audit_synthesis_decisions.md).
		Cash Drop now validates that shift_record is set, that the linked
		Shift Record is Open, and that its operator matches the drop's.
		"""
		return frappe.get_doc(
			{
				"doctype": "Shift Record",
				"operator": operator,
				"shift_date": today(),
				"status": status,
				"shift_start": now_datetime(),
				"float_expected": 300,
			}
		).insert(ignore_permissions=True)

	def _make_drop(
		self,
		amount: float = 100.0,
		operator: str = "Administrator",
		shift_record: str | None = None,
	) -> object:
		"""Create a Cash Drop with a valid Shift Record link.

		If ``shift_record`` is not provided, builds an Open shift for the
		given operator and links the drop to it.
		"""
		if shift_record is None:
			shift_record = self._make_shift(operator=operator).name
		return frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": operator,
				"shift_record": shift_record,
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": amount,
				"timestamp": now_datetime(),
			}
		).insert(ignore_permissions=True)

	def test_insert_cash_drop(self):
		drop = self._make_drop(150.0)
		self.assertEqual(drop.declared_amount, 150.0)
		self.assertFalse(drop.reconciled)

	def test_negative_amount_raises(self):
		doc = frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Administrator",
				"shift_record": self._make_shift().name,
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": -10.0,
				"timestamp": now_datetime(),
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	# ------------------------------------------------------------------
	# T1-4 — shift validation + declared-amount sanity bound
	# ------------------------------------------------------------------

	def test_t1_4_requires_shift_record(self):
		"""T1-4: shift_record is required.

		Operator opening Cash Drop in Desk without first opening a shift
		gets caught here; the audit trail no longer accepts unlinked drops.
		"""
		doc = frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Administrator",
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": 50.0,
				"timestamp": now_datetime(),
			}
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		self.assertIn("shift record", str(ctx.exception).lower())

	def test_t1_4_rejects_closed_shift(self):
		"""T1-4: linked Shift Record must be Open."""
		closed_shift = self._make_shift(status="Closed")
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._make_drop(amount=50.0, shift_record=closed_shift.name)
		self.assertIn("closed", str(ctx.exception).lower())

	def test_t1_4_rejects_mismatched_operator(self):
		"""T1-4: drop operator must match the shift's operator.

		Builds a shift owned by Administrator, then tries to drop into it
		as a different operator. Frappe's "Guest" is the simplest stand-in
		for a non-Administrator operator that always exists.
		"""
		shift = self._make_shift(operator="Administrator")
		# Construct the drop manually so we can set operator to Guest
		# while pointing at a shift owned by Administrator.
		doc = frappe.get_doc(
			{
				"doctype": "Cash Drop",
				"operator": "Guest",
				"shift_record": shift.name,
				"shift_date": today(),
				"shift_identifier": "Evening",
				"drop_type": "Mid-Shift",
				"drop_number": 1,
				"declared_amount": 50.0,
				"timestamp": now_datetime(),
			}
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		msg = str(ctx.exception).lower()
		self.assertTrue(
			"operator" in msg and "shift" in msg,
			f"Expected operator/shift mismatch error; got: {msg!r}",
		)

	def test_t1_4_rejects_above_5000_sanity_cap(self):
		"""T1-4: declared_amount above $5000 is rejected as a typo guard."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._make_drop(amount=24500.00)
		self.assertIn("sanity cap", str(ctx.exception).lower())

	def test_t1_4_accepts_at_or_below_5000(self):
		"""T1-4: $5000 exactly and below is fine."""
		drop = self._make_drop(amount=5000.00)
		self.assertEqual(float(drop.declared_amount), 5000.00)

	# ------------------------------------------------------------------
	# T0-4 — immutability after first save / after reconciliation
	# ------------------------------------------------------------------

	def test_t0_4_declared_amount_immutable_after_first_save(self):
		"""T0-4: editing declared_amount after first save is rejected.

		Restores the blind-cash anti-tamper invariant — operator can't drop
		$200 then quietly edit to $180.
		"""
		drop = self._make_drop(amount=200.0)
		drop.declared_amount = 180.0
		with self.assertRaises(frappe.ValidationError) as ctx:
			drop.save(ignore_permissions=True)
		self.assertIn("declared_amount", str(ctx.exception))

	def test_t0_4_operator_immutable_after_first_save(self):
		"""T0-4: editing operator after first save is rejected.

		The operator field anchors the audit trail. Re-attributing a drop
		to another operator after the fact would bury operator A's record
		under operator B's identity.
		"""
		drop = self._make_drop(amount=200.0)
		drop.operator = "Guest"
		with self.assertRaises(frappe.ValidationError) as ctx:
			drop.save(ignore_permissions=True)
		self.assertIn("operator", str(ctx.exception))

	def test_t0_4_admin_correction_flag_unblocks_edits(self):
		"""T0-4: the admin-correction escape hatch (DEC-066) lets a
		legitimate correction land.

		Hamilton Admin's correction endpoint sets the
		``frappe.flags.allow_cash_drop_correction`` flag, then saves the
		drop with the new value. The carve-out lets the save through.
		"""
		drop = self._make_drop(amount=200.0)
		drop.declared_amount = 195.0
		try:
			frappe.flags.allow_cash_drop_correction = True
			drop.save(ignore_permissions=True)
		finally:
			frappe.flags.allow_cash_drop_correction = False
		drop.reload()
		self.assertEqual(float(drop.declared_amount), 195.0)


class TestCashDropTipPullSchema(IntegrationTestCase):
	"""Task 34 / DEC-065 — tip pull schema fields on Cash Drop.

	Phase 1 BLOCKER: schema must exist so the FIRST tip-pull event at Hamilton
	doesn't contaminate blind-cash reconciliation as phantom theft. Full
	operator UX (rounding, 'take exactly $X' instruction) ships in Phase 2.
	See docs/design/tip_pull_phase2.md for the Phase 2 design intent.
	"""

	def tearDown(self):
		frappe.db.rollback()

	def _make_drop(self, **overrides):
		base = {
			"doctype": "Cash Drop",
			"operator": "Administrator",
			"shift_date": today(),
			"shift_identifier": "Evening",
			"drop_type": "Mid-Shift",
			"drop_number": 1,
			"declared_amount": 100.0,
			"timestamp": now_datetime(),
		}
		base.update(overrides)
		return frappe.get_doc(base).insert(ignore_permissions=True)

	def test_tip_pull_amount_defaults_to_zero(self):
		drop = self._make_drop()
		self.assertEqual(drop.tip_pull_amount, 0)

	def test_tip_pull_currency_defaults_to_cad_when_anvil_currency_unset(self):
		drop = self._make_drop()
		self.assertEqual(drop.tip_pull_currency, "CAD")

	def test_tip_settled_via_processor_amount_defaults_to_zero(self):
		drop = self._make_drop()
		self.assertEqual(drop.tip_settled_via_processor_amount, 0)

	def test_tip_pull_amount_writable(self):
		drop = self._make_drop(tip_pull_amount=12.70)
		self.assertEqual(drop.tip_pull_amount, 12.70)

	def test_tip_pull_difference_calculated_from_pull_minus_processor(self):
		"""Phase 1 stays at processor=0, so difference = tip_pull_amount.
		Phase 2 will populate tip_settled_via_processor_amount via the
		settlement-pairing job; the calculation hook is wired now.
		"""
		drop = self._make_drop(tip_pull_amount=12.70, tip_settled_via_processor_amount=12.67)
		self.assertAlmostEqual(drop.tip_pull_difference, 0.03, places=2)

	def test_tip_pull_difference_zero_when_both_fields_zero(self):
		drop = self._make_drop()
		self.assertEqual(drop.tip_pull_difference, 0)

	def test_negative_tip_pull_amount_allowed(self):
		"""Negative values are legal (e.g. operator returned cash to till
		after a mis-pull). Submit succeeds; warning fires only past the
		-$50 threshold.
		"""
		drop = self._make_drop(tip_pull_amount=-5.00)
		self.assertEqual(drop.tip_pull_amount, -5.00)

	def test_large_negative_tip_pull_does_not_block_submit(self):
		"""Past the -$50 warning threshold: msgprint fires (operator-facing
		warning) but the submit still succeeds. This catches typos like
		-200 instead of -2.00 without forcing a hard error path."""
		drop = self._make_drop(tip_pull_amount=-200.00)
		self.assertEqual(drop.tip_pull_amount, -200.00)

	def test_tip_pull_currency_inherits_from_anvil_currency_conf(self):
		"""Multi-venue: when frappe.conf.anvil_currency is set (e.g. USD for
		Philadelphia/DC/Dallas), tip_pull_currency picks it up at insert.
		Avoids a schema migration when US venues roll out (DEC-064 + DEC-065)."""
		original = frappe.conf.get("anvil_currency")
		try:
			frappe.conf["anvil_currency"] = "USD"
			drop = self._make_drop()
			self.assertEqual(drop.tip_pull_currency, "USD")
		finally:
			if original is None:
				frappe.conf.pop("anvil_currency", None)
			else:
				frappe.conf["anvil_currency"] = original
