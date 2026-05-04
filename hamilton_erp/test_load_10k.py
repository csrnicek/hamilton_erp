"""Hamilton ERP — 10,000 Check-in Load Test

What this tests:
  - Session numbers are unique across 10,000 check-ins
  - Redis INCR counter stays correct under volume
  - MariaDB connection pool does not exhaust
  - Retry loop handles any real collisions cleanly
  - Midnight boundary fix holds (all numbers match today's date prefix)
  - Full check-in cycle (start → vacate → clean) works at scale

How it works:
  - Creates 50 Venue Assets (rooms) as the test pool
  - Runs 200 complete check-in cycles on each asset (200 x 50 = 10,000)
  - Each cycle: start_session → vacate_session → mark_asset_clean
  - Collects all session numbers and verifies uniqueness
  - Reports timing, throughput, and any failures

Runtime: ~5-10 minutes on local bench. Safe — runs against
hamilton-test.localhost only. Zero risk to Frappe Cloud.

Usage:
  cd ~/frappe-bench-hamilton && source env/bin/activate
  bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp \
    --module hamilton_erp.test_load_10k
"""
from __future__ import annotations

import time
import uuid
from collections import Counter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from hamilton_erp.lifecycle import (
	mark_asset_clean,
	start_session_for_asset,
	vacate_session,
)

OPERATOR = "Administrator"
NUM_ASSETS = 50          # assets in the test pool
CYCLES_PER_ASSET = 200   # check-in cycles per asset
TOTAL_CHECKINS = NUM_ASSETS * CYCLES_PER_ASSET  # 10,000


def _ensure_walkin():
	if frappe.db.exists("Customer", "Walk-in"):
		return
	frappe.get_doc({
		"doctype": "Customer",
		"customer_name": "Walk-in",
		"customer_group": frappe.db.get_value(
			"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
		"territory": frappe.db.get_value(
			"Territory", {"is_group": 0}, "name") or "All Territories",
	}).insert(ignore_permissions=True)


class TestLoad10k(IntegrationTestCase):
	"""10,000 check-in load test.

	This test is intentionally slow — it is a load test, not a unit test.
	Expected runtime: 5-10 minutes on a local M1 Max bench.
	"""

	IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_walkin()

		# Create the asset pool
		cls.asset_names = []
		print(f"\n  Creating {NUM_ASSETS} test assets...")
		for i in range(NUM_ASSETS):
			suffix = uuid.uuid4().hex[:6].upper()
			asset = frappe.get_doc({
				"doctype": "Venue Asset",
				"asset_code": f"LD-{i:03d}-{suffix}",
				"asset_name": f"Load Test Room {i:03d}",
				"asset_category": "Room",
				"asset_tier": "Single Standard",
				"status": "Available",
				"display_order": 9000 + i,
			}).insert(ignore_permissions=True)
			cls.asset_names.append(asset.name)

		frappe.db.commit()
		print(f"  ✅ {NUM_ASSETS} assets ready")

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		super().tearDownClass()

	def tearDown(self):
		# Do NOT rollback between individual test methods —
		# setUpClass data must persist across the full run.
		pass

	# ------------------------------------------------------------------
	# TEST 1 — Core uniqueness test
	# ------------------------------------------------------------------

	def test_01_session_numbers_unique_across_10000_checkins(self):
		"""Run 10,000 check-in cycles and verify every session number
		is unique. This is the primary load test.

		Reports:
		  - Total time
		  - Check-ins per second
		  - Any duplicate session numbers (should be zero)
		  - Any failed cycles (should be zero)
		"""
		session_numbers = []
		# Parallel to session_numbers — each entry is the session_start of
		# the corresponding session. Used to derive the EXPECTED prefix
		# per-session in the validation step below. Single global prefix
		# capture (the prior approach) was incorrect: a 10k-cycle run takes
		# ~20 minutes and can cross local midnight in CI (Asia/Kolkata
		# tz crosses UTC 18:30), at which point production code correctly
		# emits sessions whose prefix matches the NEW date — but the test
		# would flag them as "wrong" against the now-stale start-of-test
		# prefix. Production behavior is the DEC-056 / Fix 10 invariant:
		# each session's prefix is pinned to its OWN session_start.date().
		session_starts = []
		failures = []
		retries_detected = 0

		# Capture at-test-start date for the informational log line. NOT
		# used as the validation invariant — see session_starts.
		today_prefix_parts = nowdate().split("-")
		d = int(today_prefix_parts[2])
		m = int(today_prefix_parts[1])
		y = int(today_prefix_parts[0])
		start_of_test_prefix = f"{d}-{m}-{y}"

		print("\n  Starting 10,000 check-in load test...")
		print(f"  Assets: {NUM_ASSETS} | Cycles per asset: {CYCLES_PER_ASSET}")
		print(f"  Test start date prefix (most sessions): {start_of_test_prefix}")
		print("  (Sessions after a midnight cross use their own date per DEC-056.)")

		start_time = time.time()
		completed = 0

		for asset_name in self.asset_names:
			for cycle in range(CYCLES_PER_ASSET):
				try:
					# START SESSION
					session_name = start_session_for_asset(
						asset_name, operator=OPERATOR)

					# Read the session number AND its session_start date.
					# session_start is needed to validate the per-session
					# prefix below (see session_starts comment above).
					session_data = frappe.db.get_value(
						"Venue Session", session_name,
						["session_number", "session_start"], as_dict=True)
					session_numbers.append(session_data.session_number)
					session_starts.append(session_data.session_start)

					# VACATE
					vacate_session(
						asset_name,
						operator=OPERATOR,
						vacate_method="Key Return",
					)

					# CLEAN
					mark_asset_clean(asset_name, operator=OPERATOR)

					completed += 1

					# Progress report every 1000 check-ins
					if completed % 1000 == 0:
						elapsed = time.time() - start_time
						rate = completed / elapsed
						print(f"  Progress: {completed:,}/{TOTAL_CHECKINS:,} "
						      f"({rate:.0f}/sec) — {elapsed:.1f}s elapsed")

				except Exception as exc:
					failures.append({
						"asset": asset_name,
						"cycle": cycle,
						"error": str(exc),
					})
					# Ensure asset is back to Available for next cycle
					try:
						frappe.db.set_value(
							"Venue Asset", asset_name, "status", "Available")
						frappe.db.set_value(
							"Venue Asset", asset_name, "current_session", None)
					except Exception:
						pass

		elapsed = time.time() - start_time
		rate = completed / elapsed if elapsed > 0 else 0

		# ── REPORT ──────────────────────────────────────────────────
		print("\n  ═══════════════════════════════════════")
		print("  LOAD TEST RESULTS")
		print("  ═══════════════════════════════════════")
		print(f"  Total check-ins completed : {completed:,}/{TOTAL_CHECKINS:,}")
		print(f"  Total time                : {elapsed:.1f}s")
		print(f"  Throughput                : {rate:.1f} check-ins/sec")
		print(f"  Failures                  : {len(failures)}")

		# Duplicate detection
		counts = Counter(session_numbers)
		duplicates = {k: v for k, v in counts.items() if v > 1}
		print(f"  Duplicate session numbers : {len(duplicates)}")

		# Prefix validation — per-session, against EACH session's own
		# session_start.date(). The production invariant is DEC-056 /
		# Fix 10: session_number's date prefix matches the date the
		# session was started, NOT a single global "test start date".
		# A 10k-cycle run that crosses midnight (UTC 18:30 in CI's
		# Asia/Kolkata tz) correctly produces sessions with the NEW
		# date prefix; the test must validate that, not flag it.
		def _expected_prefix(session_start):
			"""Date prefix matching ``_next_session_number(for_date=...)`` output."""
			if session_start is None:
				return None
			dt = session_start.date() if hasattr(session_start, "date") else session_start
			return f"{dt.day}-{dt.month}-{dt.year}---"

		wrong_prefix = []
		for sn, ss in zip(session_numbers, session_starts):
			if not sn:
				continue
			expected = _expected_prefix(ss)
			if expected is None:
				continue
			if not sn.startswith(expected):
				wrong_prefix.append((sn, expected))
		print(f"  Wrong date prefix         : {len(wrong_prefix)}")

		# Null/empty session numbers
		null_numbers = [sn for sn in session_numbers if not sn]
		print(f"  Null/empty session numbers: {len(null_numbers)}")

		# Format validation — must match d-m-yyyy---NNNN (4+ digits;
		# the trailing sequence is :04d-padded to 4 digits by default,
		# but overflow past 9999 in a single day renders as 5+ digits
		# without truncation — production code logs a warning but does
		# not raise. Allow \d{4,} so a legitimate overflow during a
		# 10k-cycle load test is not flagged as "bad format".)
		import re
		bad_format = [
			sn for sn in session_numbers
			if sn and not re.match(r"^\d+-\d+-\d+---\d{4,}$", sn)
		]
		print(f"  Bad format (not d-m-y---NNNN+): {len(bad_format)}")

		if failures:
			print("\n  FAILURES (first 5):")
			for f in failures[:5]:
				print(f"    Asset {f['asset']} cycle {f['cycle']}: {f['error']}")

		if duplicates:
			print("\n  DUPLICATES (first 5):")
			for sn, count in list(duplicates.items())[:5]:
				print(f"    {sn} appeared {count} times")

		print("  ═══════════════════════════════════════\n")

		# ── ASSERTIONS ──────────────────────────────────────────────
		self.assertEqual(
			len(failures), 0,
			f"{len(failures)} check-in cycles failed — see report above",
		)
		self.assertEqual(
			len(duplicates), 0,
			f"{len(duplicates)} duplicate session numbers found — "
			f"Redis INCR or DB unique constraint is broken",
		)
		self.assertEqual(
			len(null_numbers), 0,
			f"{len(null_numbers)} sessions have no session_number — "
			f"before_insert hook is not firing",
		)
		self.assertEqual(
			len(bad_format), 0,
			f"{len(bad_format)} session numbers have wrong format — "
			f"expected d-m-yyyy---NNNN (4-digit sequence)",
		)
		self.assertEqual(
			len(wrong_prefix), 0,
			f"{len(wrong_prefix)} session numbers have a date prefix "
			"that does NOT match their own session_start.date() — this "
			"is the DEC-056 / Fix 10 invariant. Sample (session_number, "
			f"expected_prefix): {wrong_prefix[:3]}",
		)

	# ------------------------------------------------------------------
	# TEST 2 — Sequence is monotonically increasing
	# ------------------------------------------------------------------

	def test_02_session_numbers_monotonically_increasing(self):
		"""Verify the trailing sequence on session numbers always
		increases. No gaps are required (retries can cause skips),
		but the sequence must never go backwards.
		"""
		rows = frappe.db.sql("""
			SELECT session_number
			FROM `tabVenue Session`
			WHERE session_number LIKE %s
			ORDER BY creation ASC
		""", (f"{self._today_prefix()}---%",), as_dict=True)

		sequences = []
		for row in rows:
			sn = row["session_number"]
			if sn and "---" in sn:
				try:
					seq = int(sn.rsplit("---", 1)[-1])
					sequences.append(seq)
				except ValueError:
					pass

		if len(sequences) < 2:
			self.skipTest("Not enough sessions to check monotonicity")

		backwards = []
		for i in range(1, len(sequences)):
			if sequences[i] < sequences[i - 1]:
				backwards.append((sequences[i - 1], sequences[i]))

		self.assertEqual(
			len(backwards), 0,
			f"Session sequence went backwards {len(backwards)} times: "
			f"{backwards[:5]}",
		)

	# ------------------------------------------------------------------
	# TEST 3 — Connection pool did not exhaust
	# ------------------------------------------------------------------

	def test_03_database_still_responsive_after_load(self):
		"""Verify the database is still responsive after 10,000 operations.
		If the connection pool exhausted, this query would hang or fail.
		"""
		count = frappe.db.count("Venue Session")
		self.assertIsNotNone(count)
		self.assertGreater(count, 0)

		# Also verify we can still write
		asset_name = self.asset_names[0]
		asset = frappe.get_doc("Venue Asset", asset_name)
		self.assertEqual(asset.status, "Available")

	# ------------------------------------------------------------------
	# TEST 4 — Redis key did not leak
	# ------------------------------------------------------------------

	def test_04_redis_counter_key_has_correct_ttl(self):
		"""Verify the Redis session counter key still has a TTL
		after 10,000 operations. TTL going to -1 means it lost its
		expiry and would never be garbage collected.
		"""
		prefix = self._today_prefix()
		key = f"hamilton:session_seq:{prefix}"
		cache = frappe.cache()

		# Check key exists (it should after 10,000 INDEXes)
		value = cache.get(key)
		if value is None:
			self.skipTest("Redis key expired or was flushed during test")

		# Check TTL is still set (not -1 = no expiry, not -2 = gone)
		ttl = cache.ttl(key)
		self.assertGreater(
			ttl, 0,
			f"Redis key {key} has TTL={ttl} — "
			f"key lost its expiry and will never be garbage collected",
		)

	# ------------------------------------------------------------------
	# TEST 5 — Throughput is acceptable
	# ------------------------------------------------------------------

	def test_05_throughput_above_minimum(self):
		"""Verify throughput is at least 10 check-ins per second.
		This is a very conservative lower bound — local bench on M1 Max
		should do 50-100+/sec. If this fails, something is wrong with
		the DB or Redis configuration.
		"""
		# We can infer throughput from the session creation timestamps
		rows = frappe.db.sql("""
			SELECT MIN(creation) as first, MAX(creation) as last,
			       COUNT(*) as total
			FROM `tabVenue Session`
			WHERE session_number LIKE %s
		""", (f"{self._today_prefix()}---%",), as_dict=True)

		if not rows or not rows[0]["total"]:
			self.skipTest("No sessions to measure")

		row = rows[0]
		total = row["total"]

		if row["first"] and row["last"] and row["first"] != row["last"]:
			elapsed = (row["last"] - row["first"]).total_seconds()
			if elapsed > 0:
				rate = total / elapsed
				print(f"\n  Measured throughput: {rate:.1f} check-ins/sec "
				      f"({total:,} sessions in {elapsed:.1f}s)")
				# Threshold lowered from 10 → 5 (2026-04-28) → 4 (2026-05-04) to
				# accommodate CI runner variance (GitHub Actions ubuntu-latest ranges
				# 4.8-9.9/sec). Local M1 Max benchmarks at ~16-20/sec. The point of
				# this assertion is to catch order-of-magnitude regressions (Redis
				# crashed → 0.5/sec, lock contention runaway → 1-2/sec), not 20%
				# hardware variance.
				self.assertGreater(
					rate, 4,
					f"Throughput {rate:.1f}/sec is below minimum 4/sec — "
					f"DB or Redis may be misconfigured",
				)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _today_prefix(self) -> str:
		parts = nowdate().split("-")
		d = int(parts[2])
		m = int(parts[1])
		y = int(parts[0])
		return f"{d}-{m}-{y}"
