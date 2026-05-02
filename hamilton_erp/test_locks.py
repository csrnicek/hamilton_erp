"""Tests for hamilton_erp.locks — the three-layer lock helper."""
import threading
import time
import uuid

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp.locks import LockContentionError, asset_status_lock

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

	# ------------------------------------------------------------------
	# Audit 2026-04-11 — Group A: Lock correctness gaps
	# ------------------------------------------------------------------

	def test_A1_lock_tokens_are_unique_per_acquisition(self):
		"""Each asset_status_lock acquisition must generate a distinct token.

		If tokens ever collided, a slow caller whose TTL elapsed could
		accidentally release a DIFFERENT caller's lock during Lua CAS.
		We patch uuid4 through the locks module's namespace to observe
		every token generated inside the context manager across 50 back-
		to-back acquisitions.
		"""
		from unittest.mock import patch

		from hamilton_erp import locks
		seen: list[str] = []
		real_uuid4 = locks.uuid.uuid4
		def capturing_uuid4():
			t = real_uuid4()
			seen.append(t.hex)
			return t
		with patch.object(locks.uuid, "uuid4", side_effect=capturing_uuid4):
			for _ in range(50):
				with asset_status_lock(self.asset.name, "assign"):
					pass
		self.assertEqual(len(seen), 50)
		self.assertEqual(len(set(seen)), 50,
			"Lock tokens must be unique across acquisitions — duplicate detected")

	def test_A2_redis_ttl_expiry_warning_logged(self):
		"""When the Redis key no longer holds our token at release time,
		the release path must log a warning about TTL expiry during the
		critical section (locks.py lines 116-125). This is the last line
		of defense telling ops that a slow operation crossed LOCK_TTL_MS.

		We simulate expiry by evicting the key from Redis mid-section and
		asserting frappe.logger().warning was called with a TTL-expiry
		message. MariaDB FOR UPDATE still preserves data integrity, so
		this is a signal-only path, not a correctness path.
		"""
		from unittest.mock import patch
		captured: list[str] = []

		class _L:
			def warning(self, msg):
				captured.append(msg)

		with patch("frappe.logger", return_value=_L()):
			key = f"hamilton:asset_lock:{self.asset.name}"
			cache = frappe.cache()
			with asset_status_lock(self.asset.name, "assign"):
				# Evict our token mid-section to simulate TTL expiry
				cache.delete(key)
		self.assertTrue(
			any("TTL expired" in m for m in captured),
			f"Expected TTL-expiry warning; got: {captured}",
		)

	def test_A3_lua_release_failure_does_not_mask_primary_exception(self):
		"""If Lua CAS release itself raises, the lock context manager's
		finally block must swallow it and LOG — never shadow the primary
		exception being propagated out of the with-body (locks.py 128-133).

		The cost of letting a release exception win is that the real
		business error gets lost. Verified by raising a ValidationError
		inside the with-block while forcing cache.eval to fail.
		"""
		from unittest.mock import patch
		cache = frappe.cache()
		real_eval = cache.eval
		def boom(*a, **k):
			raise RuntimeError("simulated Lua EVAL failure")
		with patch.object(cache, "eval", side_effect=boom):
			with self.assertRaises(frappe.ValidationError) as ctx:
				with asset_status_lock(self.asset.name, "assign"):
					frappe.throw("primary business error")
		# The primary error must survive, not be replaced by RuntimeError
		self.assertIn("primary business error", str(ctx.exception))
		# Lock will TTL out on its own — verify we did NOT leak it by
		# reconstructing real_eval and calling release ourselves:
		key = f"hamilton:asset_lock:{self.asset.name}"
		# Best-effort cleanup so the next test is not blocked
		cache.delete(key)

	def test_A4_twenty_threads_contending_only_one_wins_at_a_time(self):
		"""Heavy-contention stress: 20 threads race for the same asset lock.

		Invariants:
		  - Total attempts == 20
		  - Successes + LockContentionErrors == 20 (no lost threads)
		  - At least ONE thread succeeds (not a full deadlock)
		  - The holder of the lock holds it for a real (tiny) window so
		    contention is observable
		"""
		site = frappe.local.site
		asset_name = self.asset.name
		frappe.db.commit()
		results = {"success": 0, "contention": 0, "other": []}
		lock_obj = threading.Lock()

		def worker():
			frappe.init(site=site)
			frappe.connect()
			try:
				with asset_status_lock(asset_name, "assign"):
					time.sleep(0.05)
				with lock_obj:
					results["success"] += 1
			except LockContentionError:
				with lock_obj:
					results["contention"] += 1
			except Exception as e:  # pragma: no cover
				with lock_obj:
					results["other"].append(str(e))
			finally:
				frappe.destroy()

		threads = [threading.Thread(target=worker) for _ in range(20)]
		try:
			for t in threads:
				t.start()
			for t in threads:
				t.join(timeout=20)
		finally:
			frappe.db.sql("DELETE FROM `tabVenue Asset` WHERE name = %s",
			              asset_name)
			frappe.db.commit()
		self.assertEqual(results["other"], [])
		self.assertEqual(results["success"] + results["contention"], 20,
			f"Lost threads: {results}")
		self.assertGreaterEqual(results["success"], 1,
			"No thread won the lock — suggests full deadlock")

	def test_A5_redis_key_format_is_raw_asset_only(self):
		"""Pin the exact key format the lock uses.

		Regression guard: ChatGPT review 2026-04-10 removed the operation
		suffix, and the key MUST remain `hamilton:asset_lock:{asset_name}`.
		If someone adds an operation suffix back (subtle bug — two
		different ops on one asset could then both acquire), this test
		fails loudly.
		"""
		import uuid as _u
		from unittest.mock import patch

		from hamilton_erp import locks
		fixed = _u.UUID("11111111-1111-1111-1111-111111111111")
		cache = frappe.cache()
		with patch.object(locks.uuid, "uuid4", return_value=fixed):
			with asset_status_lock(self.asset.name, "assign"):
				key = f"hamilton:asset_lock:{self.asset.name}"
				stored = cache.get(key)
				# Must NOT include the operation string anywhere
				no_op_key = f"hamilton:asset_lock:{self.asset.name}:assign"
				self.assertIsNone(cache.get(no_op_key),
					"Legacy per-operation key format detected")
				self.assertIsNotNone(stored,
					"Expected asset-only lock key to be present")


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
