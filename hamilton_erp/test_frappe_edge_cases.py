"""Hamilton ERP — Frappe v16 & ERPNext Hard Edge Case Tests
Source: Direct analysis of frappe/frappe and frappe/erpnext v16 test suites:
  - frappe/tests/test_document.py
  - frappe/tests/test_document_locks.py
  - frappe/tests/test_naming.py
  - frappe/tests/test_sequence.py
  - frappe/tests/test_permissions.py
  - erpnext/accounts/doctype/pos_invoice/test_pos_invoice.py

Categories:
  Q — Frappe v16 Document Lifecycle Edge Cases
  R — Naming and Sequence Edge Cases
  S — Permission and Security Edge Cases
  T — ERPNext POS Patterns Applied to Hamilton
  U — Realtime and Background Job Edge Cases
"""
from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from hamilton_erp.lifecycle import (
	mark_asset_clean,
	start_session_for_asset,
	vacate_session,
)

OPERATOR = "Administrator"


def _ensure_walkin():
	if frappe.db.exists("Customer", "Walk-in"):
		return
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": "Walk-in",
		"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
		"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
	}).insert(ignore_permissions=True)


def _make_asset(name, category="Room", tier="Single Standard", status="Available"):
	_ensure_walkin()
	return frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"QR-{name[:5].upper()}-{uuid.uuid4().hex[:4].upper()}",
		"asset_name": name,
		"asset_category": category,
		"asset_tier": tier if category == "Room" else "Locker",
		"status": status,
		"display_order": 999,
	}).insert(ignore_permissions=True)


# ===========================================================================
# Category Q — Frappe v16 Document Lifecycle Edge Cases
# ===========================================================================

class TestFrappeDocumentLifecycle(IntegrationTestCase):
	"""Category Q — edge cases from frappe/tests/test_document.py"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("QR Document Lifecycle Room")

	def tearDown(self):
		frappe.db.rollback()

	def test_has_value_changed_detects_status_change(self):
		"""Q1b — has_value_changed() works correctly for status field.

		Source: test_document.py::test_value_changed
		"""
		self.asset.load_doc_before_save()
		self.assertFalse(self.asset.has_value_changed("status"))
		self.asset.status = "Out of Service"
		self.asset.reason = "Test"
		self.asset.load_doc_before_save()
		self.asset.update_modified()
		self.assertTrue(self.asset.has_value_changed("status"))

	def test_doc_set_none_on_link_field(self):
		"""Q — setting a Link field to None clears it correctly.

		Source: test_document.py::test_set
		"""
		session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.current_session, session_name)
		# After vacate, current_session should be None (not empty string)
		vacate_session(self.asset.name, operator=OPERATOR, vacate_method="Key Return")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNone(asset.current_session)

	def test_realtime_notify_fires_on_status_change(self):
		"""U1 — publish_status_change fires exactly once per lifecycle call.

		Source: test_document.py::test_realtime_notify using Mock()
		"""
		with patch("hamilton_erp.realtime.publish_status_change") as mock_publish:
			start_session_for_asset(self.asset.name, operator=OPERATOR)
			mock_publish.assert_called_once()
			args = mock_publish.call_args
			self.assertEqual(args[0][0], self.asset.name)

	def test_realtime_not_called_when_operation_fails(self):
		"""U2 — publish_status_change is NOT called if the lifecycle operation fails.

		Source: coding_standards.md §13 — publish outside the lock,
		only after successful state change.
		"""
		with patch("hamilton_erp.realtime.publish_status_change") as mock_publish:
			# Try to vacate an Available asset — must fail, no realtime
			with self.assertRaises(frappe.ValidationError):
				vacate_session(self.asset.name, operator=OPERATOR,
				               vacate_method="Key Return")
			mock_publish.assert_not_called()


# ===========================================================================
# Category Q2 — Document Locks (Frappe UI Locks)
# ===========================================================================

class TestFrappeDocumentLocks(IntegrationTestCase):
	"""Category Q — from frappe/tests/test_document_locks.py"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("QR Doc Locks Room")

	def tearDown(self):
		# Ensure lock is released even if test fails
		try:
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			if asset.is_locked:
				asset.unlock()
		except Exception:
			pass
		frappe.db.rollback()

	def test_lifecycle_bypasses_frappe_ui_lock(self):
		"""Q5c — UI lock blocks lifecycle writes — this is known behavior, documented here.

		The name of this test is a misnomer kept for git-history continuity:
		the lifecycle does NOT actually bypass Frappe's UI-level document lock.
		`ignore_permissions=True` skips role-based permission checks but is
		a separate mechanism from `Document.check_if_locked()`, which is
		called inside `doc.save()` regardless of the permissions flag.

		Practical consequence: if an operator calls `asset.lock()` from the
		Desk form (or any code path sets `_locked=1` on the asset), any
		subsequent lifecycle write (start_session_for_asset, vacate_session,
		etc.) will raise `frappe.DocumentLockedError` until the lock is
		released. In practice this should never happen because:
		  1. The Desk form for Venue Asset never calls `.lock()` on status
		     changes — only the lifecycle functions mutate status.
		  2. Lifecycle writes go through the three-layer asset_status_lock
		     (Redis + FOR UPDATE + version), which is the load-bearing
		     serialization primitive; the UI lock is a separate, weaker
		     mechanism intended for multi-operator form editing.

		To genuinely bypass UI locks, the lifecycle would have to switch
		from `doc.save(ignore_permissions=True)` to `frappe.db.set_value(...)`,
		which skips the Document framework entirely. That's a Phase 2
		design decision with implications for version-bump logic, validate
		hooks, and the realtime publish chain — not in scope for Phase 1.
		"""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		asset.lock()
		try:
			# UI lock blocks the lifecycle save — assert the known behavior.
			with self.assertRaises(frappe.DocumentLockedError):
				start_session_for_asset(self.asset.name, operator=OPERATOR)
			# Sanity check: the asset should still be Available because the
			# lifecycle save was blocked before any status mutation committed.
			result = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(result.status, "Available")
		finally:
			try:
				frappe.get_doc("Venue Asset", self.asset.name).unlock()
			except Exception:
				pass


# ===========================================================================
# Category R — Naming and Sequence Edge Cases
# ===========================================================================

class TestNamingAndSequence(IntegrationTestCase):
	"""Category R — from frappe/tests/test_naming.py, test_sequence.py"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("QR Naming Room")

	def tearDown(self):
		frappe.db.rollback()

	@unittest.skip("Task 9 — session_number not yet wired into _create_session")
	def test_session_number_unique_across_rapid_creation(self):
		"""R2 — 10 sequential sessions get unique session numbers.

		Source: test_naming.py::test_hash_collision
		"""
		numbers = []
		for _ in range(10):
			session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
			session = frappe.get_doc("Venue Session", session_name)
			numbers.append(session.session_number)
			vacate_session(self.asset.name, operator=OPERATOR, vacate_method="Key Return")
			mark_asset_clean(self.asset.name, operator=OPERATOR)
		self.assertEqual(len(numbers), len(set(numbers)), "Duplicate session numbers found")

	@unittest.skip("Task 9 — session_number not yet wired into _create_session")
	def test_session_number_not_reused_after_cycle(self):
		"""R3 — counter always increments, never recycles.

		Source: test_naming.py::test_naming_for_cancelled_and_amended_doc
		"""
		s1 = start_session_for_asset(self.asset.name, operator=OPERATOR)
		vacate_session(self.asset.name, operator=OPERATOR, vacate_method="Key Return")
		mark_asset_clean(self.asset.name, operator=OPERATOR)
		s2 = start_session_for_asset(self.asset.name, operator=OPERATOR)
		sess1 = frappe.get_doc("Venue Session", s1)
		sess2 = frappe.get_doc("Venue Session", s2)
		# sess2 number must be strictly greater than sess1
		n1 = int(sess1.session_number.rsplit("---", 1)[-1])
		n2 = int(sess2.session_number.rsplit("---", 1)[-1])
		self.assertGreater(n2, n1)


# ===========================================================================
# Category S — Permission and Security Edge Cases
# ===========================================================================

class TestPermissionsAndSecurity(IntegrationTestCase):
	"""Category S — from frappe/tests/test_permissions.py and test_document.py"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("QR Permissions Room")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_guest_cannot_insert_venue_asset(self):
		"""S2 — Guest user cannot insert Venue Asset.

		Source: test_document.py::test_permission
		"""
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({
				"doctype": "Venue Asset",
				"asset_code": f"GUEST-{uuid.uuid4().hex[:4].upper()}",
				"asset_name": "Guest Insert Attempt",
				"asset_category": "Room",
				"asset_tier": "Single Standard",
				"status": "Available",
				"display_order": 999,
			}).insert()

	def test_non_negative_version_field(self):
		"""S — version field should never be negative.

		Source: test_document.py::test_non_negative_check pattern
		"""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertGreaterEqual(asset.version or 0, 0)

	def test_link_validation_on_current_session(self):
		"""S — current_session must link to an existing Venue Session.

		Source: test_document.py::test_link_validation
		Setting current_session to a non-existent value raises LinkValidationError.
		"""
		self.asset.current_session = "VS-NONEXISTENT-FAKE-9999"
		with self.assertRaises((frappe.LinkValidationError, frappe.ValidationError)):
			self.asset.save(ignore_permissions=True)


# ===========================================================================
# Category T — ERPNext POS Patterns Applied to Hamilton
# ===========================================================================

class TestPOSPatterns(IntegrationTestCase):
	"""Category T — from erpnext/test_pos_invoice.py patterns applied to Hamilton"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("QR POS Pattern Room")

	def tearDown(self):
		frappe.db.rollback()

	def test_session_start_timestamp_is_set_on_insert(self):
		"""T4 — session_start is set when session is created.

		Source: test_pos_invoice.py::test_timestamp_change pattern
		"""
		before = now_datetime()
		session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
		session = frappe.get_doc("Venue Session", session_name)
		self.assertIsNotNone(session.session_start)
		self.assertGreaterEqual(session.session_start, before)

	def test_session_end_timestamp_set_on_vacate(self):
		"""T4b — session_end is set when session is closed.

		Source: test_pos_invoice.py::test_timestamp_change pattern
		"""
		session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
		before_vacate = now_datetime()
		vacate_session(self.asset.name, operator=OPERATOR, vacate_method="Key Return")
		session = frappe.get_doc("Venue Session", session_name)
		self.assertIsNotNone(session.session_end)
		self.assertGreaterEqual(session.session_end, before_vacate)

	def test_vacate_method_stored_on_session(self):
		"""T — vacate_method is persisted on the session for audit.

		Source: test_pos_invoice.py::test_pos_returns_with_repayment pattern
		Mirrors: "method used to close" must be recorded.
		"""
		session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
		vacate_session(self.asset.name, operator=OPERATOR,
		               vacate_method="Discovery on Rounds")
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.vacate_method, "Discovery on Rounds")

# ===========================================================================
# Category U — Realtime and Background Job Edge Cases
# ===========================================================================

class TestRealtimeEdgeCases(IntegrationTestCase):
	"""Category U — realtime publish patterns"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		self.asset = _make_asset("QR Realtime Room")

	def tearDown(self):
		frappe.db.rollback()

	def test_publish_called_once_per_start_session(self):
		"""U1 — publish_status_change called exactly once on start_session.

		Source: test_document.py::test_realtime_notify using Mock()
		"""
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			start_session_for_asset(self.asset.name, operator=OPERATOR)
			self.assertEqual(mock_pub.call_count, 1)

	def test_publish_called_once_per_vacate(self):
		"""U1b — publish_status_change called exactly once on vacate."""
		start_session_for_asset(self.asset.name, operator=OPERATOR)
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			vacate_session(self.asset.name, operator=OPERATOR,
			               vacate_method="Key Return")
			self.assertEqual(mock_pub.call_count, 1)

	def test_publish_called_once_per_mark_clean(self):
		"""U1c — publish_status_change called exactly once on mark_clean."""
		start_session_for_asset(self.asset.name, operator=OPERATOR)
		vacate_session(self.asset.name, operator=OPERATOR, vacate_method="Key Return")
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			mark_asset_clean(self.asset.name, operator=OPERATOR)
			self.assertEqual(mock_pub.call_count, 1)

	def test_publish_not_called_on_failed_operation(self):
		"""U2 — publish NOT called when lifecycle operation fails.

		Source: coding_standards.md §13 — realtime only fires on success.
		"""
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			with self.assertRaises(frappe.ValidationError):
				# Vacate on Available asset — must fail
				vacate_session(self.asset.name, operator=OPERATOR,
				               vacate_method="Key Return")
			mock_pub.assert_not_called()

# ===========================================================================
# Audit 2026-04-11 — Group I: VenueSession controller gaps
# ===========================================================================


class TestVenueSessionControllerAudit(IntegrationTestCase):
	"""Covers the VenueSession validate/before_insert hooks that the
	existing suite exercises indirectly. Indirect coverage breaks the
	moment someone changes lifecycle.py without touching the controller.
	"""

	def setUp(self):
		self.asset = _make_asset("VSess Controller Asset")

	def tearDown(self):
		frappe.db.rollback()

	def test_I1_session_end_before_start_rejected(self):
		"""venue_session._validate_session_end: session_end < session_start
		must raise. Covers an untested branch.
		"""
		from datetime import timedelta
		start = now_datetime()
		end = start - timedelta(minutes=1)
		doc = frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": self.asset.name,
			"operator_checkin": "Administrator",
			"customer": "Walk-in",
			"session_start": start,
			"session_end": end,
			"status": "Completed",
			"assignment_status": "Assigned",
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		self.assertIn("Check-out", str(ctx.exception))

	def test_I2_identity_method_defaults_to_not_applicable(self):
		"""VenueSession._set_defaults assigns identity_method='not_applicable'
		when omitted. Club Hamilton never collects ID, so this default
		is load-bearing — a change would regress DEC-055.
		"""
		sn = start_session_for_asset(self.asset.name, operator=OPERATOR)
		s = frappe.get_doc("Venue Session", sn)
		self.assertEqual(s.identity_method, "not_applicable")

	def test_I3_before_insert_preserves_explicit_session_number(self):
		"""If a caller sets session_number explicitly, before_insert
		leaves it alone. Covers the `if not self.session_number` guard
		in venue_session.py:28.
		"""
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		explicit = f"{prefix}---9998"
		doc = frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": self.asset.name,
			"operator_checkin": "Administrator",
			"customer": "Walk-in",
			"session_number": explicit,
			"session_start": now_datetime(),
			"status": "Active",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)
		self.assertEqual(doc.session_number, explicit)

	def test_I4_before_insert_autogenerates_when_omitted(self):
		"""Complementary branch: session_number omitted → before_insert
		fills it in via _next_session_number. A callable that sidesteps
		the lifecycle._create_session path still gets a valid number.
		"""
		doc = frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": self.asset.name,
			"operator_checkin": "Administrator",
			"customer": "Walk-in",
			"session_start": now_datetime(),
			"status": "Active",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)
		self.assertIsNotNone(doc.session_number)
		self.assertRegex(doc.session_number, r"^\d+-\d+-\d+---\d{4}$")


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
