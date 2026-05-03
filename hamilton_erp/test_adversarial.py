"""Adversarial test suite for Hamilton ERP Phase 1.

Simulates hostile, edge-case, and race-condition inputs against the
lifecycle state machine, locking layer, session number generator,
bulk operations, and input validation surface.

RUN ON: hamilton-unit-test.localhost ONLY
NEVER run on hamilton-test.localhost (dev browser site)

ATTACK FAMILIES:
  A — State Machine Violations     (illegal transitions, double-actions)
  B — Concurrency & Lock Attacks   (contention, lock release after failure)
  C — Session Sequence Attacks     (format, monotonicity, rollover, cold Redis)
  D — Input Validation Attacks     (None, empty, whitespace, bad kwargs)
  E — Bulk Operation Attacks       (bulk clean, skip-occupied, error isolation)
  F — Financial & Phase 2 Attacks  (all skipTest — functions don't exist yet)

Usage:
  cd ~/frappe-bench-hamilton && source env/bin/activate
  bench --site hamilton-unit-test.localhost run-tests \
      --app hamilton_erp --module hamilton_erp.test_adversarial
"""
import json
import uuid
from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle
from hamilton_erp.locks import LOCK_TTL_MS, LockContentionError, asset_status_lock

# ---------------------------------------------------------------------------
# Crash reporter — collects pass/crash per attack ID for post-run summary
# ---------------------------------------------------------------------------

_CRASH_LOG: list[dict] = []


def _log_crash(attack_id: str, message: str) -> None:
	_CRASH_LOG.append({
		"id": attack_id,
		"status": "CRASH",
		"message": str(message),
		"timestamp": datetime.now().isoformat(),
	})


def _log_pass(attack_id: str) -> None:
	_CRASH_LOG.append({
		"id": attack_id,
		"status": "PASS",
		"message": "",
		"timestamp": datetime.now().isoformat(),
	})


def _write_report() -> None:
	"""Write a JSON crash report to /tmp/hamilton_adversarial_report.json."""
	passed = sum(1 for r in _CRASH_LOG if r["status"] == "PASS")
	crashed = sum(1 for r in _CRASH_LOG if r["status"] == "CRASH")
	report = {
		"total": len(_CRASH_LOG),
		"passed": passed,
		"crashed": crashed,
		"results": _CRASH_LOG,
	}
	path = "/tmp/hamilton_adversarial_report.json"
	with open(path, "w") as f:
		json.dump(report, f, indent=2)
	print(f"\n{'=' * 60}")
	print(f"ADVERSARIAL REPORT: {passed} passed, {crashed} crashed")
	print(f"Full report: {path}")
	print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _ensure_walkin_customer() -> None:
	"""Create Walk-in customer if absent (DEC-055 §1)."""
	if not frappe.db.exists("Customer", "Walk-in"):
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "Walk-in",
			"customer_group": frappe.db.get_value(
				"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
			"territory": frappe.db.get_value(
				"Territory", {"is_group": 0}, "name") or "All Territories",
		}).insert(ignore_permissions=True)


def _make_asset(prefix: str = "ADV", category: str = "Room",
                tier: str = "Single Standard", display_order: int = 9900):
	"""Create a fresh Available Venue Asset with a unique code."""
	suffix = uuid.uuid4().hex[:6].upper()
	return frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"{prefix}-{suffix}",
		"asset_name": f"{prefix} {suffix}",
		"asset_category": category,
		"asset_tier": tier,
		"status": "Available",
		"display_order": display_order,
		"version": 0,
	}).insert(ignore_permissions=True)


def _walk_to_dirty(asset_name: str) -> None:
	"""Walk an Available asset through Available → Occupied → Dirty."""
	asset = frappe.get_doc("Venue Asset", asset_name)
	asset.status = "Occupied"
	asset.save(ignore_permissions=True)
	asset.status = "Dirty"
	asset.save(ignore_permissions=True)


def _walk_to_occupied(asset_name: str) -> str:
	"""Available → Occupied via start_session_for_asset. Returns session name."""
	return lifecycle.start_session_for_asset(asset_name, operator="Administrator")


def _walk_to_oos(asset_name: str) -> None:
	"""Available → Out of Service via set_asset_out_of_service."""
	lifecycle.set_asset_out_of_service(
		asset_name, operator="Administrator", reason="Adversarial test"
	)


# ===========================================================================
# FAMILY A — State Machine Violations
# ===========================================================================


class TestFamilyA_StateMachineViolations(IntegrationTestCase):
	"""Attacks that attempt illegal state transitions.

	Every test confirms the transition is rejected AND that the asset's
	status is unchanged after the rejected attempt.
	"""

	def setUp(self):
		_ensure_walkin_customer()
		self.asset = _make_asset(prefix="A-SM")

	def tearDown(self):
		frappe.db.rollback()

	# A01 — Assign an already-Occupied asset
	def test_a01_assign_occupied_asset(self):
		attack_id = "A01"
		try:
			_walk_to_occupied(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator"
				)
			# Verify status unchanged
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Occupied")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A02 — Assign a Dirty asset
	def test_a02_assign_dirty_asset(self):
		attack_id = "A02"
		try:
			_walk_to_dirty(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Dirty")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A03 — Assign an Out of Service asset
	def test_a03_assign_oos_asset(self):
		attack_id = "A03"
		try:
			_walk_to_oos(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Out of Service")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A04 — Vacate an Available asset (no session to close)
	def test_a04_vacate_available_asset(self):
		attack_id = "A04"
		try:
			with self.assertRaises(frappe.ValidationError):
				lifecycle.vacate_session(
					self.asset.name, operator="Administrator",
					vacate_method="Key Return"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A05 — Clean an Available asset (not dirty)
	def test_a05_clean_available_asset(self):
		attack_id = "A05"
		try:
			with self.assertRaises(frappe.ValidationError):
				lifecycle.mark_asset_clean(
					self.asset.name, operator="Administrator"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A06 — Clean an Occupied asset (must go through Dirty first)
	def test_a06_clean_occupied_asset(self):
		attack_id = "A06"
		try:
			_walk_to_occupied(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.mark_asset_clean(
					self.asset.name, operator="Administrator"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Occupied")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A07 — Double-vacate: vacate then vacate again
	def test_a07_double_vacate(self):
		attack_id = "A07"
		try:
			_walk_to_occupied(self.asset.name)
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return"
			)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.vacate_session(
					self.asset.name, operator="Administrator",
					vacate_method="Key Return"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Dirty")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A08 — Return to service from Available (not OOS)
	def test_a08_return_to_service_from_available(self):
		attack_id = "A08"
		try:
			with self.assertRaises(frappe.ValidationError):
				lifecycle.return_asset_to_service(
					self.asset.name, operator="Administrator",
					reason="Should fail"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A09 — Double OOS: set OOS then set OOS again
	def test_a09_double_oos(self):
		attack_id = "A09"
		try:
			_walk_to_oos(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.set_asset_out_of_service(
					self.asset.name, operator="Administrator",
					reason="Second OOS"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Out of Service")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# A10 — Full cycle: Available → Occupied → Dirty → Available (legal)
	# then attempt Dirty → Occupied (illegal)
	def test_a10_dirty_to_occupied_illegal(self):
		attack_id = "A10"
		try:
			_walk_to_dirty(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator"
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Dirty")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise


# ===========================================================================
# FAMILY B — Concurrency & Lock Attacks
# ===========================================================================


class TestFamilyB_ConcurrencyAndLockAttacks(IntegrationTestCase):
	"""Attacks against the three-layer locking system.

	Tests that the Redis advisory lock prevents concurrent mutations,
	that locks are released after validation failures, and that
	LockContentionError is raised (not a silent pass-through).
	"""

	def setUp(self):
		_ensure_walkin_customer()
		self.asset = _make_asset(prefix="B-LOCK")

	def tearDown(self):
		frappe.db.rollback()
		# Clean up any leftover Redis lock keys from this test's asset
		key = f"hamilton:asset_lock:{self.asset.name}"
		try:
			frappe.cache().delete(key)
		except Exception:
			pass

	# B01 — Pre-held Redis lock blocks lifecycle function
	def test_b01_pre_held_lock_blocks_lifecycle(self):
		attack_id = "B01"
		try:
			cache = frappe.cache()
			key = f"hamilton:asset_lock:{self.asset.name}"
			token = uuid.uuid4().hex
			# Manually set the Redis lock key to simulate another holder
			cache.set(key, token, nx=True, px=LOCK_TTL_MS)
			with self.assertRaises(LockContentionError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator"
				)
			# Asset must still be Available — the lifecycle never entered
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			# Clean up the manual lock
			cache.delete(key)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# B02 — Lock released after validation rejection (re-acquirable)
	def test_b02_lock_released_after_rejection(self):
		attack_id = "B02"
		try:
			_walk_to_dirty(self.asset.name)
			# Attempt illegal transition — should fail but release lock
			with self.assertRaises(frappe.ValidationError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator"
				)
			# If the lock was NOT released, this would raise LockContentionError
			with asset_status_lock(self.asset.name, "verify-release") as row:
				self.assertEqual(row["status"], "Dirty")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# B03 — Lock released after every lifecycle rejection path
	def test_b03_lock_released_after_vacate_rejection(self):
		attack_id = "B03"
		try:
			# Vacate on Available — should fail
			with self.assertRaises(frappe.ValidationError):
				lifecycle.vacate_session(
					self.asset.name, operator="Administrator",
					vacate_method="Key Return"
				)
			# Verify lock was released
			with asset_status_lock(self.asset.name, "verify-release") as row:
				self.assertEqual(row["status"], "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# B04 — Lock released after mark_clean rejection
	def test_b04_lock_released_after_clean_rejection(self):
		attack_id = "B04"
		try:
			with self.assertRaises(frappe.ValidationError):
				lifecycle.mark_asset_clean(
					self.asset.name, operator="Administrator"
				)
			with asset_status_lock(self.asset.name, "verify-release") as row:
				self.assertEqual(row["status"], "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# B05 — Lock released after OOS rejection (already OOS)
	def test_b05_lock_released_after_oos_rejection(self):
		attack_id = "B05"
		try:
			_walk_to_oos(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.set_asset_out_of_service(
					self.asset.name, operator="Administrator",
					reason="Already OOS"
				)
			with asset_status_lock(self.asset.name, "verify-release") as row:
				self.assertEqual(row["status"], "Out of Service")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# B06 — Lock on non-existent asset
	def test_b06_lock_nonexistent_asset(self):
		attack_id = "B06"
		try:
			fake_name = f"DOES-NOT-EXIST-{uuid.uuid4().hex[:6]}"
			with self.assertRaises(frappe.ValidationError):
				with asset_status_lock(fake_name, "ghost"):
					pass  # Should never reach here
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise


# ===========================================================================
# FAMILY C — Session Sequence Attacks
# ===========================================================================


class TestFamilyC_SessionSequenceAttacks(IntegrationTestCase):
	"""Attacks against the DEC-033 session number generator.

	The generator uses Redis INCR with a DB fallback on cold starts.
	Format: {d}-{m}-{y}---{NNNN} (day/month NOT zero-padded, seq IS).
	"""

	def setUp(self):
		year, month, day = frappe.utils.nowdate().split("-")
		self._prefix = f"{int(day)}-{int(month)}-{int(year)}"
		self._key = f"hamilton:session_seq:{self._prefix}"
		frappe.cache().delete(self._key)

	def tearDown(self):
		frappe.db.rollback()
		frappe.cache().delete(self._key)

	# C01 — Format matches DEC-033
	def test_c01_format_matches_dec033(self):
		attack_id = "C01"
		try:
			sn = lifecycle._next_session_number()
			prefix, seq = sn.split("---")
			parts = prefix.split("-")
			self.assertEqual(len(parts), 3, f"Prefix should be d-m-y, got {prefix}")
			self.assertEqual(len(seq), 4, f"Sequence must be 4 digits, got {seq}")
			self.assertTrue(seq.isdigit(), f"Sequence must be numeric, got {seq}")
			self.assertEqual(prefix, self._prefix)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# C02 — Monotonic increment
	def test_c02_monotonic_increment(self):
		attack_id = "C02"
		try:
			sn1 = lifecycle._next_session_number()
			sn2 = lifecycle._next_session_number()
			sn3 = lifecycle._next_session_number()
			seq1 = int(sn1.split("---")[1])
			seq2 = int(sn2.split("---")[1])
			seq3 = int(sn3.split("---")[1])
			self.assertEqual(seq2, seq1 + 1)
			self.assertEqual(seq3, seq2 + 1)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# C03 — First call of the day returns 0001
	def test_c03_first_call_returns_0001(self):
		attack_id = "C03"
		try:
			sn = lifecycle._next_session_number()
			self.assertTrue(
				sn.endswith("---0001"),
				f"Expected first call to end with ---0001, got {sn}",
			)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# C04 — DB fallback when Redis key is cold
	def test_c04_db_fallback_cold_redis(self):
		attack_id = "C04"
		try:
			suffix = uuid.uuid4().hex[:6]
			asset = _make_asset(prefix=f"C04-{suffix}")
			# Seed a session with today's prefix + sequence 0042
			frappe.get_doc({
				"doctype": "Venue Session",
				"venue_asset": asset.name,
				"session_number": f"{self._prefix}---0042",
				"status": "Active",
				"session_start": frappe.utils.now_datetime(),
				"operator_checkin": "Administrator",
			}).insert(ignore_permissions=True)
			# Ensure Redis key is cold
			frappe.cache().delete(self._key)
			sn = lifecycle._next_session_number()
			self.assertEqual(
				sn, f"{self._prefix}---0043",
				f"Cold-Redis fallback should resume at db_max+1=0043, got {sn}",
			)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# C05 — Redis failure raises user-friendly ValidationError
	def test_c05_redis_failure_raises_validation_error(self):
		attack_id = "C05"
		try:
			from unittest.mock import patch

			import redis as redis_lib

			with patch.object(
				frappe.cache(), "get",
				side_effect=redis_lib.ConnectionError("simulated outage"),
			):
				with self.assertRaises(frappe.ValidationError) as ctx:
					lifecycle._next_session_number()
			self.assertIn("temporarily unavailable", str(ctx.exception))
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# C06 — Sequence stays 4 digits even at high values
	def test_c06_high_sequence_still_4_digits(self):
		attack_id = "C06"
		try:
			# Seed Redis counter to 9998 so next call returns 9999
			cache = frappe.cache()
			cache.set(self._key, 9998, px=lifecycle._SESSION_KEY_TTL_MS)
			sn = lifecycle._next_session_number()
			seq = sn.split("---")[1]
			self.assertEqual(seq, "9999", f"Expected 9999, got {seq}")
			self.assertEqual(len(seq), 4)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise


# ===========================================================================
# FAMILY D — Input Validation Attacks
# ===========================================================================


class TestFamilyD_InputValidationAttacks(IntegrationTestCase):
	"""Attacks that pass malformed, None, or empty inputs to lifecycle
	functions. Every attack must produce a clear error, never a silent
	pass-through or data corruption.
	"""

	def setUp(self):
		_ensure_walkin_customer()
		self.asset = _make_asset(prefix="D-VAL")

	def tearDown(self):
		frappe.db.rollback()

	# D01 — Vacate with invalid vacate_method
	def test_d01_invalid_vacate_method(self):
		attack_id = "D01"
		try:
			_walk_to_occupied(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.vacate_session(
					self.asset.name, operator="Administrator",
					vacate_method="Teleportation"
				)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D02 — OOS with empty string reason
	def test_d02_oos_empty_reason(self):
		attack_id = "D02"
		try:
			with self.assertRaises(frappe.ValidationError):
				lifecycle.set_asset_out_of_service(
					self.asset.name, operator="Administrator", reason=""
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D03 — OOS with whitespace-only reason
	def test_d03_oos_whitespace_reason(self):
		attack_id = "D03"
		try:
			with self.assertRaises(frappe.ValidationError):
				lifecycle.set_asset_out_of_service(
					self.asset.name, operator="Administrator",
					reason="   \t\n  "
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D04 — Return to service with empty reason
	def test_d04_return_empty_reason(self):
		attack_id = "D04"
		try:
			_walk_to_oos(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.return_asset_to_service(
					self.asset.name, operator="Administrator", reason=""
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Out of Service")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D05 — Return to service with whitespace-only reason
	def test_d05_return_whitespace_reason(self):
		attack_id = "D05"
		try:
			_walk_to_oos(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.return_asset_to_service(
					self.asset.name, operator="Administrator",
					reason="   \t  "
				)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Out of Service")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D06 — Start session on non-existent asset
	def test_d06_start_session_nonexistent_asset(self):
		attack_id = "D06"
		try:
			fake_name = f"GHOST-ASSET-{uuid.uuid4().hex[:6]}"
			with self.assertRaises((frappe.ValidationError, LockContentionError)):
				lifecycle.start_session_for_asset(
					fake_name, operator="Administrator"
				)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D07 — Vacate with empty string vacate_method
	def test_d07_vacate_empty_method(self):
		attack_id = "D07"
		try:
			_walk_to_occupied(self.asset.name)
			with self.assertRaises(frappe.ValidationError):
				lifecycle.vacate_session(
					self.asset.name, operator="Administrator",
					vacate_method=""
				)
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D08 — OOS reason cleared when returning to Available
	def test_d08_oos_reason_cleared_on_return(self):
		attack_id = "D08"
		try:
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Broken pipe"
			)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.reason, "Broken pipe")

			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator",
				reason="Pipe repaired"
			)
			asset = frappe.get_doc("Venue Asset", self.asset.name)
			self.assertEqual(asset.status, "Available")
			self.assertFalse(asset.reason,
				"OOS reason must be cleared after returning to service")
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# D09 — Version field increments on every transition
	def test_d09_version_increments_every_transition(self):
		attack_id = "D09"
		try:
			# Available → Occupied (v0 → v1)
			_walk_to_occupied(self.asset.name)
			v1 = frappe.db.get_value("Venue Asset", self.asset.name, "version")
			self.assertEqual(v1, 1)

			# Occupied → Dirty (v1 → v2)
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator",
				vacate_method="Key Return"
			)
			v2 = frappe.db.get_value("Venue Asset", self.asset.name, "version")
			self.assertEqual(v2, 2)

			# Dirty → Available (v2 → v3)
			lifecycle.mark_asset_clean(
				self.asset.name, operator="Administrator"
			)
			v3 = frappe.db.get_value("Venue Asset", self.asset.name, "version")
			self.assertEqual(v3, 3)

			# Available → OOS (v3 → v4)
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator",
				reason="Test"
			)
			v4 = frappe.db.get_value("Venue Asset", self.asset.name, "version")
			self.assertEqual(v4, 4)

			# OOS → Available (v4 → v5)
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator",
				reason="Done"
			)
			v5 = frappe.db.get_value("Venue Asset", self.asset.name, "version")
			self.assertEqual(v5, 5)

			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise


# ===========================================================================
# FAMILY E — Lifecycle Rollback Contract (T1-7)
# ===========================================================================
#
# Per docs/inbox/2026-05-04_audit_synthesis_decisions.md T1-7. The
# lifecycle module's contract (lifecycle.py:113-127, 308-318, 430-442)
# is: when an inner function raises mid-way, the lifecycle entry-point
# MUST NOT swallow the exception. The exception must propagate to the
# caller's transaction boundary so request-level rollback cleans up
# any partial state (the Venue Session insert that happened inside the
# lock before the raising call).
#
# A future contributor that wraps a lifecycle call in `try: ... except:
# pass` would silently break this. These tests pin the contract by
# monkey-patching the inner function to raise and asserting the
# exception propagates out the lifecycle entry-point.


class TestFamilyE_LifecycleRollbackContract(IntegrationTestCase):
	"""T1-7: lifecycle entry points must propagate inner-function
	exceptions, never swallow them.

	The actual orphan-prevention is provided by the caller's
	transaction boundary (the request transaction in production, the
	IntegrationTestCase tearDown rollback in tests). What the lifecycle
	itself owes its callers is exception-propagation. Tests pin that.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	def setUp(self):
		_ensure_walkin_customer()
		self.asset = _make_asset(prefix="E-RB")

	def tearDown(self):
		frappe.db.rollback()

	# E01 — start_session propagates _set_asset_status exceptions
	def test_e01_start_session_propagates_set_asset_status_exceptions(self):
		"""start_session_for_asset MUST raise when _set_asset_status raises.

		If this test fails, a contributor has wrapped the inner call in
		try/except. That breaks the no-catch-and-continue contract at
		lifecycle.py:113-127. Partial state (Venue Session inserted, asset
		status not flipped) would commit on an HTTP request boundary that
		didn't see the exception.
		"""
		attack_id = "E01"
		try:
			original = lifecycle._set_asset_status

			def boom(*a, **kw):
				raise frappe.ValidationError("T1-7 simulated CAS failure (E01)")

			lifecycle._set_asset_status = boom
			try:
				with self.assertRaises(frappe.ValidationError):
					lifecycle.start_session_for_asset(
						self.asset.name, operator="Administrator"
					)
			finally:
				lifecycle._set_asset_status = original
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# E02 — vacate_session propagates _set_asset_status exceptions
	def test_e02_vacate_session_propagates_set_asset_status_exceptions(self):
		"""vacate_session MUST raise when _set_asset_status raises.

		Same contract as E01, applied to the vacate path
		(lifecycle.py:308-318). Inside the asset lock, _close_current_session
		runs BEFORE _set_asset_status. A swallowed exception here would
		commit a half-vacated state (session marked Completed, asset still
		Occupied).
		"""
		attack_id = "E02"
		try:
			_walk_to_occupied(self.asset.name)
			original = lifecycle._set_asset_status

			def boom(*a, **kw):
				raise frappe.ValidationError("T1-7 simulated CAS failure (E02)")

			lifecycle._set_asset_status = boom
			try:
				with self.assertRaises(frappe.ValidationError):
					lifecycle.vacate_session(
						self.asset.name,
						operator="Administrator",
						vacate_method="Key Return",
					)
			finally:
				lifecycle._set_asset_status = original
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise

	# E03 — set_asset_out_of_service propagates _set_asset_status exceptions
	def test_e03_set_oos_propagates_set_asset_status_exceptions(self):
		"""set_asset_out_of_service MUST raise when _set_asset_status raises.

		Same contract as E01/E02, applied to the OOS path
		(lifecycle.py:430-442). When previous == Occupied,
		_close_current_session runs BEFORE _set_asset_status. A swallowed
		exception here would commit a half-OOS'd state.
		"""
		attack_id = "E03"
		try:
			_walk_to_occupied(self.asset.name)
			original = lifecycle._set_asset_status

			def boom(*a, **kw):
				raise frappe.ValidationError("T1-7 simulated CAS failure (E03)")

			lifecycle._set_asset_status = boom
			try:
				with self.assertRaises(frappe.ValidationError):
					lifecycle.set_asset_out_of_service(
						self.asset.name,
						operator="Administrator",
						reason="Plumbing",
					)
			finally:
				lifecycle._set_asset_status = original
			_log_pass(attack_id)
		except Exception as e:
			_log_crash(attack_id, e)
			raise


class TestFamilyF_Phase2Financial(IntegrationTestCase):
	"""Attacks against Phase 2 financial functions.

	All tests are skipped with self.skipTest because the underlying
	functions (process_refund, validate_split_tender, comp admission
	flow, POS-linked cash drops) do not exist yet in Phase 1.
	These serve as placeholders that will be activated in Phase 2.
	"""

	def setUp(self):
		_ensure_walkin_customer()
		self.asset = _make_asset(prefix="F-FIN")

	def tearDown(self):
		frappe.db.rollback()

	# F01 — Comp admission without reason
	def test_f01_comp_without_reason(self):
		self.skipTest(
			"F01: Comp admission flow not implemented — Phase 2. "
			"hamilton_erp.lifecycle has no comp_reason parameter."
		)

	# F02 — Zero-value non-comp walk-in
	def test_f02_zero_value_walkin(self):
		self.skipTest(
			"F02: Price validation not implemented — Phase 2. "
			"start_session_for_asset has no override_price parameter."
		)

	# F03 — Refund releases asset
	def test_f03_refund_releases_asset(self):
		self.skipTest(
			"F03: process_refund not implemented — Phase 2. "
			"No refund lifecycle function exists yet."
		)

	# F04 — Double refund on same session
	def test_f04_double_refund(self):
		self.skipTest(
			"F04: process_refund not implemented — Phase 2. "
			"No refund lifecycle function exists yet."
		)

	# F05 — Split tender validation
	def test_f05_split_tender_mismatch(self):
		self.skipTest(
			"F05: validate_split_tender not implemented — Phase 2. "
			"No split tender validation function exists yet."
		)

	# F06 — Cash drop zero amount
	def test_f06_cash_drop_zero_amount(self):
		self.skipTest(
			"F06: POS-linked cash drop flow not implemented — Phase 2. "
			"hamilton_erp.cash module does not exist yet."
		)

	# F07 — HST mixed taxable/exempt items
	def test_f07_hst_mixed_items(self):
		self.skipTest(
			"F07: HST calculation not implemented — Phase 2. "
			"Tax logic lives in ERPNext POS, not hamilton_erp."
		)

	# F08 — Negative cash in split tender
	def test_f08_split_tender_negative_cash(self):
		self.skipTest(
			"F08: validate_split_tender not implemented — Phase 2. "
			"No split tender validation function exists yet."
		)


# ---------------------------------------------------------------------------
# Suite runner + crash report output
# ---------------------------------------------------------------------------

def load_tests(loader, tests, pattern):
	suite = __import__("unittest").TestSuite()
	test_classes = [
		TestFamilyA_StateMachineViolations,
		TestFamilyB_ConcurrencyAndLockAttacks,
		TestFamilyC_SessionSequenceAttacks,
		TestFamilyD_InputValidationAttacks,
		TestFamilyE_LifecycleRollbackContract,
		TestFamilyF_Phase2Financial,
	]
	for cls in test_classes:
		loaded = loader.loadTestsFromTestCase(cls)
		suite.addTests(loaded)

	# Append a finalizer test that writes the crash report
	class _WriteReport(IntegrationTestCase):
		def test_zzz_write_adversarial_report(self):
			_write_report()

	suite.addTests(loader.loadTestsFromTestCase(_WriteReport))
	return suite
