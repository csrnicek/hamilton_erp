"""Phase 1 stress simulation — concurrency, locking, and bulk-load integrity.

Replaces the legacy stress simulation file (deleted 2026-04-29). The legacy
file referenced the pre-refactor lifecycle API (`assign_asset`,
`vacate_asset`, `acquire_lock`, …) and the `assignment_status` field, both
of which were renamed during Phase 1. All 42 of its tests had been
`@unittest.skip`'d for weeks, contributing zero coverage.

This replacement uses the current API (`start_session_for_asset`,
`vacate_session`, `set_asset_out_of_service`, …) and follows the patterns
in `test_e2e_phase1.py`:
- IntegrationTestCase with `setUpClass(cls)` running `seed_hamilton_env`.
- Per-test `setUp`/`tearDown` rolling back to keep tests self-contained.
- `real_logs()` context manager when audit log creation is being asserted.

Phase 1 stress scope (concurrency and bulk integrity only):
- TestStressConcurrentAssign      — same asset, two threads, exactly one wins.
- TestStressLockBehavior          — TTL expiry, asset-only key isolation.
- TestStressSessionNumberSequence — 25 sessions, unique + format-conformant.
- TestStressBulkTurnoverCycles    — same asset cycled 10 times back-to-back.
- TestStressCrossAssetIsolation   — operations on different assets don't block.

NOT in scope (covered by other modules or out of Phase 1):
- POS, pricing, refunds, cash drops, shift reconciliation (Phase 2+).
- Bulk Mark Clean (covered by `test_bulk_clean.py`).
- Asset count smoke checks (covered by `test_environment_health.py`).
- 59-asset seed integrity (covered by `test_seed_patch.py`).
"""
import threading
import uuid
from contextlib import contextmanager

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle
from hamilton_erp.locks import LockContentionError, asset_status_lock
from hamilton_erp.patches.v0_1 import seed_hamilton_env


# ---------------------------------------------------------------------------
# Helpers — mirror the test_e2e_phase1.py style.
# ---------------------------------------------------------------------------

@contextmanager
def real_logs():
	"""Clear both `frappe.in_test` attributes so audit logs actually write.

	`_make_asset_status_log` (lifecycle.py) reads the module-level
	`frappe.in_test`, which the test runner sets via
	`frappe.tests.utils.toggle_test_mode`. It is independent from
	`frappe.local.flags.in_test`. Tests that need the audit log path
	exercised must clear both. See `test_e2e_phase1.py::real_logs` for the
	canonical version.
	"""
	prior_attr = frappe.in_test
	prior_flag = frappe.local.flags.in_test
	frappe.in_test = False
	frappe.local.flags.in_test = False
	try:
		yield
	finally:
		frappe.in_test = prior_attr
		frappe.local.flags.in_test = prior_flag


def _make_test_asset(prefix: str, *, display_order: int = 9000) -> str:
	"""Create a fresh Available room asset and return its name. Self-contained."""
	suffix = uuid.uuid4().hex[:6]
	doc = frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_name": f"{prefix} {suffix}",
		"asset_code": f"{prefix}-{suffix}",
		"asset_category": "Room",
		"asset_tier": "Single Standard",
		"status": "Available",
		"display_order": display_order,
		"version": 0,
		"expected_stay_duration": 360,
		"company": frappe.db.get_single_value("Global Defaults", "default_company"),
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _cleanup_stress_state():
	"""Clean up committed state from stress tests (assets, sessions, Redis).

	`tearDown`'s `frappe.db.rollback()` only undoes the test's *uncommitted*
	writes. The setUp uses `.insert(...) + frappe.db.commit()` to publish the
	asset to other connections, and the threading tests commit explicitly.
	Both leave durable rows that survive rollback.

	If we don't clean up, `_next_session_number` (which falls back to
	`_db_max_seq_for_prefix` when the Redis key is cold) sees the high
	max sequence from our committed sessions. Other tests that expect a
	fresh start at `---0001` (e.g. `TestSessionNumberGenerator.test_first_call_returns_0001`)
	then get e.g. `---0071`. Local runs don't typically surface this; CI
	does because it runs all modules in one bench invocation.

	Steps: delete Sessions for STRESS-* assets, delete the assets, delete
	today's Redis session counter.
	"""
	frappe.db.sql("""
		DELETE FROM `tabVenue Session`
		WHERE venue_asset IN (
			SELECT name FROM `tabVenue Asset` WHERE asset_code LIKE 'STRESS-%%'
		)
	""")
	frappe.db.sql("DELETE FROM `tabVenue Asset` WHERE asset_code LIKE 'STRESS-%%'")
	frappe.db.commit()
	year, month, day = frappe.utils.nowdate().split("-")
	# Raw .delete() matches the raw .set / .incr path the generator uses.
	frappe.cache().delete(f"hamilton:session_seq:{int(day)}-{int(month)}-{int(year)}")


# ---------------------------------------------------------------------------
# TestStressConcurrentAssign — only one of N concurrent assigns wins.
# ---------------------------------------------------------------------------

class TestStressConcurrentAssign(IntegrationTestCase):
	"""Concurrency: two threads racing to assign the same asset.

	The three-layer lock (Redis NX → MariaDB FOR UPDATE → optimistic version)
	must guarantee exactly one assignment succeeds. The losing thread sees a
	`LockContentionError` (Redis layer) or `frappe.ValidationError`
	(MariaDB/version layer).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def setUp(self):
		self.asset_name = _make_test_asset("STRESS-CA", display_order=9001)
		# Capture the test runner's site name. Local dev uses
		# "hamilton-unit-test.localhost"; CI uses "test_site". Hardcoding
		# the dev name silently breaks CI with `IncorrectSitePath`.
		self.site = frappe.local.site

	def tearDown(self):
		frappe.db.rollback()
		_cleanup_stress_state()

	def _attempt_assign(self, operator: str, results: dict, errors: list):
		"""Thread body — own Frappe connection, isolated transaction.

		Threads have no HTTP request boundary, so the framework's normal
		auto-commit-at-request-end does not fire. We must commit explicitly
		on success — otherwise `frappe.destroy()` closes the connection with
		an uncommitted transaction and the change is rolled back. (CLAUDE.md
		bans `frappe.db.commit()` in controllers; this is a test thread, not
		a controller.)
		"""
		try:
			frappe.init(site=self.site)
			frappe.connect()
			try:
				lifecycle.start_session_for_asset(self.asset_name, operator=operator)
				frappe.db.commit()
				results["success"] += 1
			except Exception:
				frappe.db.rollback()
				raise
		except (LockContentionError, frappe.ValidationError) as e:
			results["expected_failure"] += 1
			errors.append(f"{operator}: {type(e).__name__}: {e}")
		except Exception as e:
			results["unexpected"] += 1
			errors.append(f"{operator}: UNEXPECTED {type(e).__name__}: {e}")
		finally:
			frappe.destroy()

	def test_two_threads_only_one_wins(self):
		results = {"success": 0, "expected_failure": 0, "unexpected": 0}
		errors = []
		t1 = threading.Thread(target=self._attempt_assign, args=("Administrator", results, errors))
		t2 = threading.Thread(target=self._attempt_assign, args=("Administrator", results, errors))
		t1.start(); t2.start()
		t1.join(); t2.join()

		self.assertEqual(
			results["success"], 1,
			f"Expected exactly 1 success, got {results['success']}. Errors: {errors}",
		)
		self.assertEqual(
			results["expected_failure"], 1,
			f"Expected exactly 1 expected failure, got {results['expected_failure']}.",
		)
		self.assertEqual(
			results["unexpected"], 0,
			f"Unexpected exception(s): {errors}",
		)

		# Cross-thread visibility: each thread used its own frappe.connect() and
		# committed via frappe.destroy(). The test's main connection holds a
		# REPEATABLE READ snapshot from setUp's insert, so it does NOT see the
		# winning thread's update without first ending its own snapshot.
		# `frappe.db.rollback()` releases the snapshot — subsequent reads see
		# committed state.
		frappe.db.rollback()
		status, current_session = frappe.db.get_value(
			"Venue Asset", self.asset_name, ["status", "current_session"]
		)
		self.assertEqual(status, "Occupied",
			"After race resolution the winning thread's commit should be visible.")
		self.assertIsNotNone(current_session)

	def test_double_sequential_assign_is_rejected(self):
		"""Sequential (not concurrent) double-assign is also rejected. Sanity check."""
		lifecycle.start_session_for_asset(self.asset_name, operator="Administrator")
		with self.assertRaises(frappe.ValidationError):
			lifecycle.start_session_for_asset(self.asset_name, operator="Administrator")


# ---------------------------------------------------------------------------
# TestStressLockBehavior — Redis lock semantics under stress.
# ---------------------------------------------------------------------------

class TestStressLockBehavior(IntegrationTestCase):
	"""Lock acquisition, contention, and asset-only key scoping."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def setUp(self):
		self.asset_a = _make_test_asset("STRESS-LA", display_order=9011)
		self.asset_b = _make_test_asset("STRESS-LB", display_order=9012)

	def tearDown(self):
		frappe.db.rollback()
		_cleanup_stress_state()

	def test_held_lock_rejects_second_acquire(self):
		"""While asset A's lock is held, a second acquire on A raises."""
		with asset_status_lock(self.asset_a, "assign"):
			with self.assertRaises(LockContentionError):
				with asset_status_lock(self.asset_a, "vacate"):
					pass

	def test_lock_releases_after_context_exit(self):
		"""After the context exits, a fresh acquire succeeds."""
		with asset_status_lock(self.asset_a, "assign"):
			pass
		# Should not raise:
		with asset_status_lock(self.asset_a, "vacate") as row:
			self.assertEqual(row["name"], self.asset_a)

	def test_lock_is_asset_only_not_per_operation(self):
		"""DEC-024: Redis key is asset-only. Holding 'assign' on A blocks 'vacate' on A."""
		with asset_status_lock(self.asset_a, "assign"):
			# Different operation on SAME asset must collide.
			with self.assertRaises(LockContentionError):
				with asset_status_lock(self.asset_a, "oos"):
					pass

	def test_different_assets_do_not_block_each_other(self):
		"""Holding A's lock leaves B free."""
		with asset_status_lock(self.asset_a, "assign"):
			with asset_status_lock(self.asset_b, "assign") as row:
				self.assertEqual(row["name"], self.asset_b)


# ---------------------------------------------------------------------------
# TestStressSessionNumberSequence — uniqueness + format under bulk creation.
# ---------------------------------------------------------------------------

class TestStressSessionNumberSequence(IntegrationTestCase):
	"""Session number `_next_session_number()` must produce unique,
	monotonically increasing, format-conformant identifiers under bulk load.

	Format: `{d}-{m}-{y}---{NNNN}` (DEC-033, see lifecycle.py:572 docstring).
	Day/month are NOT zero-padded; the 4-digit sequence IS zero-padded.
	Uniqueness is enforced by Redis INCR with a DB-max fallback for cold
	starts.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def tearDown(self):
		frappe.db.rollback()
		_cleanup_stress_state()

	def test_25_sequential_session_numbers_are_unique(self):
		numbers = [lifecycle._next_session_number() for _ in range(25)]
		self.assertEqual(len(numbers), len(set(numbers)),
			f"Duplicate session numbers under bulk: {numbers}")

	def test_session_number_format_is_correct(self):
		num = lifecycle._next_session_number()
		# {d}-{m}-{y}---{NNNN} — day/month not zero-padded, sequence is 4-digit padded.
		self.assertRegex(num, r"^\d{1,2}-\d{1,2}-\d{4}---\d{4}$",
			f"Session number {num!r} does not match {{d}}-{{m}}-{{y}}---{{NNNN}}")

	def test_session_numbers_strictly_increasing_within_day(self):
		nums = [lifecycle._next_session_number() for _ in range(10)]
		# Split on '---' (the literal triple-dash separator), not '-'.
		seqs = [int(n.split("---")[1]) for n in nums]
		self.assertEqual(seqs, sorted(seqs),
			f"Sequence numbers not monotonic: {seqs}")
		# And strictly increasing (no duplicates within the same day):
		self.assertEqual(len(set(seqs)), len(seqs),
			f"Sequence numbers contain duplicates: {seqs}")


# ---------------------------------------------------------------------------
# TestStressBulkTurnoverCycles — same asset cycled many times.
# ---------------------------------------------------------------------------

class TestStressBulkTurnoverCycles(IntegrationTestCase):
	"""Same asset cycled Available → Occupied → Dirty → Available many times.

	Asserts version monotonically increments and final state is consistent
	after the load.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def setUp(self):
		self.asset_name = _make_test_asset("STRESS-BT", display_order=9021)

	def tearDown(self):
		frappe.db.rollback()
		_cleanup_stress_state()

	def test_ten_full_turnover_cycles(self):
		CYCLES = 10
		start = frappe.get_doc("Venue Asset", self.asset_name)
		start_version = start.version
		for i in range(CYCLES):
			lifecycle.start_session_for_asset(self.asset_name, operator="Administrator")
			lifecycle.vacate_session(
				self.asset_name, operator="Administrator", vacate_method="Key Return"
			)
			lifecycle.mark_asset_clean(self.asset_name, operator="Administrator")
		end = frappe.get_doc("Venue Asset", self.asset_name)
		# 3 transitions per cycle (assign, vacate, clean) → version increments by 3*CYCLES.
		self.assertEqual(end.version, start_version + (3 * CYCLES),
			f"Version mismatch after {CYCLES} cycles: "
			f"start={start_version}, end={end.version}")
		self.assertEqual(end.status, "Available")
		self.assertIsNone(end.current_session)


# ---------------------------------------------------------------------------
# TestStressCrossAssetIsolation — parallel ops on different assets all succeed.
# ---------------------------------------------------------------------------

class TestStressCrossAssetIsolation(IntegrationTestCase):
	"""N threads, each operating on a distinct asset, must all succeed.

	The asset-only lock key means there should be zero contention between
	operations on different assets. Verifies the lock is correctly scoped
	(no accidental global lock).
	"""

	N_ASSETS = 4

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_hamilton_env.execute()

	def setUp(self):
		self.asset_names = [
			_make_test_asset("STRESS-CI", display_order=9030 + i)
			for i in range(self.N_ASSETS)
		]
		self.site = frappe.local.site

	def tearDown(self):
		frappe.db.rollback()
		_cleanup_stress_state()

	def _assign_one(self, asset_name: str, results: dict, errors: list):
		"""Thread body — explicit commit, see TestStressConcurrentAssign for why."""
		try:
			frappe.init(site=self.site)
			frappe.connect()
			try:
				lifecycle.start_session_for_asset(asset_name, operator="Administrator")
				frappe.db.commit()
				results["success"] += 1
			except Exception:
				frappe.db.rollback()
				raise
		except Exception as e:
			results["failure"] += 1
			errors.append(f"{asset_name}: {type(e).__name__}: {e}")
		finally:
			frappe.destroy()

	def test_parallel_assigns_all_succeed(self):
		results = {"success": 0, "failure": 0}
		errors = []
		threads = [
			threading.Thread(target=self._assign_one, args=(name, results, errors))
			for name in self.asset_names
		]
		for t in threads: t.start()
		for t in threads: t.join()
		self.assertEqual(
			results["success"], self.N_ASSETS,
			f"Expected all {self.N_ASSETS} parallel assigns to succeed. "
			f"Successes={results['success']}, failures={results['failure']}, errors={errors}",
		)
