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
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from hamilton_erp import lifecycle
from hamilton_erp.lifecycle import (
	VALID_TRANSITIONS,
	mark_asset_clean,
	return_asset_to_service,
	set_asset_out_of_service,
	start_session_for_asset,
	vacate_session,
)
from hamilton_erp.locks import LockContentionError, asset_status_lock

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

	def test_timestamp_mismatch_on_concurrent_save(self):
		"""Q1 — Frappe raises TimestampMismatchError on concurrent saves.

		Source: test_document.py::test_conflict_validation
		Two instances of the same asset saved concurrently — second must fail.
		This is Frappe's own conflict detection, separate from our version CAS.
		"""
		asset1 = frappe.get_doc("Venue Asset", self.asset.name)
		asset2 = frappe.get_doc("Venue Asset", self.asset.name)
		asset1.save(ignore_permissions=True)
		with self.assertRaises(frappe.TimestampMismatchError):
			asset2.save(ignore_permissions=True)

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

	def test_xss_stripped_from_oos_reason(self):
		"""Q4 — XSS in OOS reason field is stripped automatically by Frappe.

		Source: test_document.py::test_xss_filter
		"""
		xss = '<script>alert("XSS")</script>'
		self.asset.status = "Out of Service"
		self.asset.reason = f"Maintenance{xss}"
		self.asset.save(ignore_permissions=True)
		self.asset.reload()
		self.assertNotIn(xss, self.asset.reason)
		self.assertIn("Maintenance", self.asset.reason)

	def test_mandatory_field_enforced_on_insert(self):
		"""Q — mandatory fields raise MandatoryError if missing.

		Source: test_document.py::test_mandatory
		asset_code is reqd=1 — missing it must raise.
		"""
		doc = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_name": "No Code Asset",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 999,
		})
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_new_doc_with_fields_pattern(self):
		"""Q — frappe.new_doc with fields is valid Frappe v16 pattern.

		Source: test_document.py::test_new_doc_with_fields
		"""
		doc = frappe.new_doc("Venue Asset", asset_name="New Doc Pattern Room")
		self.assertEqual(doc.asset_name, "New Doc Pattern Room")
		self.assertTrue(doc.is_new())

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

	def test_frappe_ui_lock_prevents_second_lock(self):
		"""Q5 — Frappe built-in UI lock prevents double-locking.

		Source: test_document_locks.py::test_locking
		"""
		asset1 = frappe.get_doc("Venue Asset", self.asset.name)
		asset2 = frappe.get_doc("Venue Asset", self.asset.name)
		asset1.lock()
		with self.assertRaises(frappe.DocumentLockedError):
			asset2.lock()
		asset1.unlock()

	def test_frappe_ui_lock_persists_across_instances(self):
		"""Q5b — UI lock is persistent — new doc instance sees the lock.

		Source: test_document_locks.py::test_operations_on_locked_documents
		"""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		asset.lock()
		# New instance must see the lock
		fresh = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertTrue(fresh.is_locked)
		asset.unlock()
		fresh2 = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertFalse(fresh2.is_locked)

	def test_lifecycle_bypasses_frappe_ui_lock(self):
		"""Q5c — lifecycle writes use ignore_permissions=True and bypass UI lock.

		This documents the intentional behavior: an operator with the Frappe
		form open (UI lock) does not block the lifecycle from writing.
		The lifecycle lock (Redis + FOR UPDATE) is the correct serialization layer.
		"""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		asset.lock()
		try:
			# Lifecycle must succeed even with UI lock active
			start_session_for_asset(self.asset.name, operator=OPERATOR)
			result = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(result.status, "Occupied")
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

	def test_asset_code_unique_constraint_raises_duplicate_entry(self):
		"""R — duplicate asset_code raises DuplicateEntryError.

		Source: test_naming.py::test_hash_collision pattern
		"""
		code = f"UNIQUE-{uuid.uuid4().hex[:6].upper()}"
		frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": code,
			"asset_name": "First Asset With Code",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 999,
		}).insert(ignore_permissions=True)

		with self.assertRaises((frappe.DuplicateEntryError, frappe.UniqueValidationError)):
			frappe.get_doc({
				"doctype": "Venue Asset",
				"asset_code": code,
				"asset_name": "Second Asset Same Code",
				"asset_category": "Room",
				"asset_tier": "Single Standard",
				"status": "Available",
				"display_order": 999,
			}).insert(ignore_permissions=True)

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

	def test_standard_creation_field_is_set_by_framework(self):
		"""S3 — creation field is set by Frappe, not by us.

		Source: test_permissions.py::test_set_standard_fields_manually
		We cannot manually set creation/owner — Frappe controls them.
		"""
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertIsNotNone(asset.creation)
		self.assertIsNotNone(asset.owner)
		self.assertIsNotNone(asset.modified_by)

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

	def test_session_status_active_while_occupied(self):
		"""T — session status is Active while asset is Occupied.

		Source: test_pos_opening_entry.py::test_pos_opening_entry pattern
		"""
		session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.status, "Active")

	def test_session_status_completed_after_vacate(self):
		"""T — session status is Completed after vacate.

		Source: test_pos_opening_entry.py::test_cancel_pos_opening_entry pattern
		"""
		session_name = start_session_for_asset(self.asset.name, operator=OPERATOR)
		vacate_session(self.asset.name, operator=OPERATOR, vacate_method="Key Return")
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.status, "Completed")


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

	def test_publish_receives_correct_asset_name(self):
		"""U1d — publish called with the correct asset_name argument."""
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			start_session_for_asset(self.asset.name, operator=OPERATOR)
			call_args = mock_pub.call_args
			self.assertEqual(call_args[0][0], self.asset.name)

	def test_publish_receives_correct_previous_status(self):
		"""U1e — publish called with correct previous_status."""
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			start_session_for_asset(self.asset.name, operator=OPERATOR)
			call_kwargs = mock_pub.call_args[1]
			self.assertEqual(call_kwargs.get("previous_status"), "Available")
