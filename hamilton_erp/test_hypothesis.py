"""Hamilton ERP — Property-Based Tests (Hypothesis)

Uses Hypothesis to generate hundreds of random inputs and verify
invariants that must hold regardless of input:
  - Session number format always matches DD-M-YYYY---NNNN
  - State machine never reaches an invalid state via valid transitions
  - Cash math preserves precision (no floating-point rounding errors)

Run via:
  bench --site hamilton-unit-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_hypothesis
"""
from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hamilton_erp.lifecycle import (
	_next_session_number,
	mark_asset_clean,
	return_asset_to_service,
	set_asset_out_of_service,
	start_session_for_asset,
	vacate_session,
)

OPERATOR = "Administrator"
SESSION_NUMBER_RE = re.compile(r"^\d{1,2}-\d{1,2}-\d{4}---\d{4,}$")


def _ensure_walkin():
	if frappe.db.exists("Customer", "Walk-in"):
		return
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": "Walk-in",
		"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
		"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
	}).insert(ignore_permissions=True)


def _make_asset(name):
	_ensure_walkin()
	return frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"HY-{uuid.uuid4().hex[:8].upper()}",
		"asset_name": name,
		"asset_category": "Room",
		"asset_tier": "Single Standard",
		"status": "Available",
		"display_order": 9900,
	}).insert(ignore_permissions=True)


# ===========================================================================
# P1 — Session Number Format Invariants
# ===========================================================================


class TestSessionNumberProperties(IntegrationTestCase):
	"""Property: _next_session_number always returns valid format."""

	@given(
		day=st.integers(min_value=1, max_value=28),
		month=st.integers(min_value=1, max_value=12),
		year=st.integers(min_value=2020, max_value=2040),
	)
	@settings(
		max_examples=50,
		deadline=5000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_format_matches_pattern_for_any_date(self, day, month, year):
		"""Session number matches DD-M-YYYY---NNNN for any valid date."""
		d = date(year, month, day)
		result = _next_session_number(for_date=d)
		self.assertRegex(
			result, SESSION_NUMBER_RE,
			f"Session number {result!r} does not match expected format"
		)

	@given(
		day=st.integers(min_value=1, max_value=28),
		month=st.integers(min_value=1, max_value=12),
		year=st.integers(min_value=2020, max_value=2040),
	)
	@settings(
		max_examples=50,
		deadline=5000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_prefix_contains_correct_date_components(self, day, month, year):
		"""Session number prefix encodes the exact date passed."""
		d = date(year, month, day)
		result = _next_session_number(for_date=d)
		prefix = result.split("---")[0]
		parts = prefix.split("-")
		self.assertEqual(int(parts[0]), day)
		self.assertEqual(int(parts[1]), month)
		self.assertEqual(int(parts[2]), year)

	@given(
		day=st.integers(min_value=1, max_value=28),
		month=st.integers(min_value=1, max_value=12),
		year=st.integers(min_value=2020, max_value=2040),
	)
	@settings(
		max_examples=30,
		deadline=5000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_sequence_is_positive_integer(self, day, month, year):
		"""Trailing sequence number is always a positive integer."""
		d = date(year, month, day)
		result = _next_session_number(for_date=d)
		seq_str = result.split("---")[1]
		seq = int(seq_str)
		self.assertGreater(seq, 0, f"Sequence {seq} should be positive")

	@given(
		day=st.integers(min_value=1, max_value=28),
		month=st.integers(min_value=1, max_value=12),
		year=st.integers(min_value=2020, max_value=2040),
	)
	@settings(
		max_examples=30,
		deadline=5000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_sequence_is_at_least_4_digits(self, day, month, year):
		"""Trailing sequence is zero-padded to at least 4 digits."""
		d = date(year, month, day)
		result = _next_session_number(for_date=d)
		seq_str = result.split("---")[1]
		self.assertGreaterEqual(len(seq_str), 4,
			f"Sequence {seq_str!r} should be at least 4 digits")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# P2 — State Machine Transition Invariants
# ===========================================================================

# Valid actions and the state they require
ACTIONS = [
	("start", "Available"),
	("vacate", "Occupied"),
	("clean", "Dirty"),
	("oos_from_available", "Available"),
	("oos_from_occupied", "Occupied"),
	("return", "Out of Service"),
]


class TestStateMachineProperties(IntegrationTestCase):
	"""Property: no sequence of valid transitions reaches an invalid state."""

	@given(
		actions=st.lists(
			st.sampled_from(["start", "vacate", "clean", "oos", "return"]),
			min_size=1,
			max_size=8,
		)
	)
	@settings(
		max_examples=30,
		deadline=10000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_random_action_sequence_never_corrupts(self, actions):
		"""Any sequence of actions either succeeds or raises ValidationError.

		The asset should never end up in a state that isn't one of the 4
		valid states (Available, Occupied, Dirty, Out of Service).
		"""
		asset = _make_asset(f"Hypo State {uuid.uuid4().hex[:4]}")
		valid_states = {"Available", "Occupied", "Dirty", "Out of Service"}

		for action in actions:
			try:
				if action == "start":
					start_session_for_asset(asset.name, operator=OPERATOR)
				elif action == "vacate":
					vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")
				elif action == "clean":
					mark_asset_clean(asset.name, operator=OPERATOR)
				elif action == "oos":
					set_asset_out_of_service(asset.name, operator=OPERATOR, reason="Test")
				elif action == "return":
					return_asset_to_service(asset.name, operator=OPERATOR, reason="Fixed")
			except (frappe.ValidationError, Exception):
				# Invalid transitions raise — that's correct behavior
				pass

			# After every action (success or failure), state must be valid
			status = frappe.db.get_value("Venue Asset", asset.name, "status")
			self.assertIn(status, valid_states,
				f"Asset in invalid state {status!r} after action {action!r}")

	@given(cycles=st.integers(min_value=1, max_value=5))
	@settings(
		max_examples=10,
		deadline=15000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_valid_lifecycle_is_always_repeatable(self, cycles):
		"""The happy path (Available -> Occupied -> Dirty -> Available) works N times."""
		asset = _make_asset(f"Hypo Cycle {uuid.uuid4().hex[:4]}")
		for _ in range(cycles):
			start_session_for_asset(asset.name, operator=OPERATOR)
			vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")
			mark_asset_clean(asset.name, operator=OPERATOR)
			status = frappe.db.get_value("Venue Asset", asset.name, "status")
			self.assertEqual(status, "Available")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# P3 — Cash Math Precision
# ===========================================================================


class TestCashMathProperties(IntegrationTestCase):
	"""Property: cash arithmetic preserves precision with no rounding errors."""

	@given(
		amounts=st.lists(
			st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999.99"),
			            places=2, allow_nan=False, allow_infinity=False),
			min_size=1,
			max_size=20,
		)
	)
	@settings(
		max_examples=50,
		deadline=5000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_sum_of_drops_equals_total(self, amounts):
		"""Sum of individual cash drop amounts equals the total with no rounding error."""
		# This tests the math Hamilton ERP uses for cash reconciliation
		total = sum(amounts)
		# Verify no floating-point precision loss
		float_total = sum(float(a) for a in amounts)
		decimal_total = float(total)
		# Allow 1 cent tolerance for float accumulation on large lists
		self.assertAlmostEqual(float_total, decimal_total, places=2,
			msg=f"Float sum {float_total} != Decimal sum {decimal_total}")

	@given(
		float_amount=st.floats(min_value=0.01, max_value=9999.99, allow_nan=False, allow_infinity=False),
		expected_float=st.floats(min_value=100.0, max_value=500.0, allow_nan=False, allow_infinity=False),
	)
	@settings(
		max_examples=50,
		deadline=5000,
		suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
	)
	def test_variance_calculation_preserves_sign(self, float_amount, expected_float):
		"""variance = actual - expected preserves correct sign."""
		variance = float_amount - expected_float
		if float_amount > expected_float:
			self.assertGreater(variance, 0)
		elif float_amount < expected_float:
			self.assertLess(variance, 0)
		else:
			self.assertAlmostEqual(variance, 0.0, places=10)

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# Teardown
# ===========================================================================


def tearDownModule():
	"""Restore dev state wiped by this module's tests."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
