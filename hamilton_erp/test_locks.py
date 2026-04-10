"""Tests for hamilton_erp.locks — the three-layer lock helper."""
import threading
import time
import uuid

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp.locks import asset_status_lock, LockContentionError

# Note: This test module lives at the package root (not inside a doctype
# folder), so `cls.doctype` is None and Frappe skips test-record generation
# entirely. IGNORE_TEST_RECORD_DEPENDENCIES is only honored inside doctype
# folders (Frappe raises NotImplementedError otherwise), so we don't set it.


class TestAssetStatusLock(IntegrationTestCase):
	def setUp(self):
		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc(
			{
				"doctype": "Venue Asset",
				"asset_code": f"LOCK-TEST-{suffix.upper()}",
				"asset_name": f"Lock Test {suffix}",
				"asset_category": "Room",
				"asset_tier": "Single Standard",
				"status": "Available",
				"display_order": 9001,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_lock_yields_row_dict(self):
		"""Happy path — lock yields full row fields from the DB under FOR UPDATE."""
		with asset_status_lock(self.asset.name, "test") as row:
			self.assertEqual(row["name"], self.asset.name)
			self.assertEqual(row["status"], "Available")
			self.assertEqual(row["asset_category"], "Room")
			self.assertEqual(row["asset_tier"], "Single Standard")
			self.assertIn("asset_code", row)
			self.assertIn("current_session", row)
			self.assertIn("version", row)

	def test_second_acquisition_raises(self):
		"""Holding the lock blocks a second acquisition in a separate thread.

		Threads don't inherit Frappe's request-local context, so each worker
		calls ``frappe.connect(site=...)`` to get its own DB + cache binding
		(Gap 5 in the Phase 1 plan).
		"""
		site = frappe.local.site
		asset_name = self.asset.name
		# Commit the fixture so the worker threads (fresh connections) can
		# see it under FOR UPDATE — setUp's insert is otherwise uncommitted.
		frappe.db.commit()
		acquired = threading.Event()
		contention_seen = {"value": False}
		holder_error = {"value": None}

		def holder():
			try:
				frappe.init(site=site)
				frappe.connect()
				try:
					with asset_status_lock(asset_name, "assign"):
						acquired.set()
						time.sleep(0.5)
				finally:
					frappe.destroy()
			except Exception as e:  # pragma: no cover — surfaced via assertion
				holder_error["value"] = e
				acquired.set()

		def contender():
			acquired.wait(timeout=2)
			frappe.init(site=site)
			frappe.connect()
			try:
				with asset_status_lock(asset_name, "assign"):
					pass
			except LockContentionError:
				contention_seen["value"] = True
			finally:
				frappe.destroy()

		t1 = threading.Thread(target=holder)
		t2 = threading.Thread(target=contender)
		try:
			t1.start()
			t2.start()
			t1.join()
			t2.join()
		finally:
			# Clean up the fixture row we committed above so tearDown's rollback
			# doesn't leak it — delete via a fresh SQL statement then commit.
			frappe.db.sql("DELETE FROM `tabVenue Asset` WHERE name = %s", asset_name)
			frappe.db.commit()
		self.assertIsNone(holder_error["value"])
		self.assertTrue(contention_seen["value"])

	def test_different_operations_on_same_asset_are_serialized(self):
		"""Lock key is asset-only — ALL ops on one asset serialize against each other.

		Previously (pre-ChatGPT-review 2026-04-10) the key included the operation
		label, which let an "assign" and a "vacate" concurrently mutate the same
		asset. The key is now asset-only, so a second acquisition from any caller
		must raise LockContentionError regardless of the operation string.
		"""
		with asset_status_lock(self.asset.name, "assign"):
			with self.assertRaises(LockContentionError):
				with asset_status_lock(self.asset.name, "oos"):
					pass  # pragma: no cover — must not reach here
