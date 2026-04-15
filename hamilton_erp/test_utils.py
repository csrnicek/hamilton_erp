"""Hamilton ERP — Tests for utils.py (get_current_shift_record, get_next_drop_number)

Covers the two completely untested utility functions identified in the
"Known Test Gaps" section of docs/testing_guide.md.

Run via:
  bench --site hamilton-unit-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_utils
"""
from __future__ import annotations

import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime, today

from hamilton_erp.utils import get_current_shift_record, get_next_drop_number


OPERATOR = "Administrator"


def _make_shift(status="Open", operator=OPERATOR):
	"""Create a Shift Record with a unique name."""
	return frappe.get_doc({
		"doctype": "Shift Record",
		"operator": operator,
		"shift_date": today(),
		"status": status,
		"shift_start": now_datetime(),
		"float_expected": 300,
	}).insert(ignore_permissions=True)


def _make_cash_drop(shift_record_name, drop_number=1):
	"""Create a Cash Drop linked to a Shift Record."""
	return frappe.get_doc({
		"doctype": "Cash Drop",
		"operator": OPERATOR,
		"shift_record": shift_record_name,
		"shift_date": today(),
		"shift_identifier": f"TEST-{uuid.uuid4().hex[:6].upper()}",
		"drop_type": "Mid-Shift",
		"drop_number": drop_number,
		"timestamp": now_datetime(),
		"declared_amount": 100,
	}).insert(ignore_permissions=True)


# ===========================================================================
# get_current_shift_record()
# ===========================================================================


class TestGetCurrentShiftRecord(IntegrationTestCase):
	"""Test get_current_shift_record() returns the correct shift or None."""

	def test_returns_none_when_no_open_shift(self):
		"""Returns None when the operator has no Open shift."""
		result = get_current_shift_record(OPERATOR)
		self.assertIsNone(result,
			"Should return None when no Open shift exists")

	def test_returns_shift_name_when_one_open(self):
		"""Returns the shift name when exactly one Open shift exists."""
		shift = _make_shift(status="Open")
		result = get_current_shift_record(OPERATOR)
		self.assertEqual(result, shift.name,
			"Should return the name of the Open shift")

	def test_returns_none_for_closed_shift(self):
		"""Returns None when the only shift is Closed."""
		_make_shift(status="Closed")
		result = get_current_shift_record(OPERATOR)
		self.assertIsNone(result,
			"Should return None when only a Closed shift exists")

	def test_returns_most_recent_when_multiple_open(self):
		"""Returns the most recent Open shift when multiple exist."""
		older = _make_shift(status="Open")
		# Ensure the second shift has a later shift_start
		import time
		time.sleep(0.01)
		newer = _make_shift(status="Open")
		result = get_current_shift_record(OPERATOR)
		self.assertEqual(result, newer.name,
			"Should return the most recent Open shift by shift_start desc")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# get_next_drop_number()
# ===========================================================================


class TestGetNextDropNumber(IntegrationTestCase):
	"""Test get_next_drop_number() returns the correct sequential number."""

	def test_returns_1_for_first_drop(self):
		"""Returns 1 when no Cash Drops exist for the shift."""
		shift = _make_shift()
		result = get_next_drop_number(shift.name)
		self.assertEqual(result, 1,
			"First drop on a fresh shift should be 1")

	def test_increments_for_subsequent_drops(self):
		"""Returns count+1 for subsequent drops."""
		shift = _make_shift()
		_make_cash_drop(shift.name, drop_number=1)
		result = get_next_drop_number(shift.name)
		self.assertEqual(result, 2,
			"After one drop, next should be 2")

		_make_cash_drop(shift.name, drop_number=2)
		result = get_next_drop_number(shift.name)
		self.assertEqual(result, 3,
			"After two drops, next should be 3")

	def test_throws_on_empty_string(self):
		"""Raises ValidationError when shift_record is an empty string."""
		with self.assertRaises(frappe.ValidationError):
			get_next_drop_number("")

	def test_throws_on_none(self):
		"""Raises ValidationError when shift_record is None."""
		with self.assertRaises(frappe.ValidationError):
			get_next_drop_number(None)

	def test_throws_on_falsy_value(self):
		"""Raises ValidationError when shift_record is 0 or False."""
		with self.assertRaises(frappe.ValidationError):
			get_next_drop_number(0)

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# Teardown
# ===========================================================================


def tearDownModule():
	"""Restore dev state wiped by this module's tests."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
