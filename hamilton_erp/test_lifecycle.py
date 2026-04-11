"""Unit-style tests for hamilton_erp.lifecycle helper functions.

Task 3 covers only the pure helpers — transition validation.
Tasks 4–8 add integration tests against the real DB for each
whitelisted lifecycle function.

Note: this module lives at the package root (same level as api.py,
locks.py, test_locks.py). We intentionally do NOT set
IGNORE_TEST_RECORD_DEPENDENCIES — Frappe v16's IntegrationTestCase
can't auto-detect cls.doctype for package-root modules, so it skips
test-record generation entirely and there's no cascade to break.
"""
import uuid

import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import lifecycle


class TestLifecycleHelpers(IntegrationTestCase):
	def test_valid_transitions_map(self):
		t = lifecycle.VALID_TRANSITIONS
		self.assertIn("Occupied", t["Available"])
		self.assertIn("Dirty", t["Occupied"])
		self.assertIn("Available", t["Dirty"])
		self.assertIn("Out of Service", t["Available"])
		self.assertIn("Available", t["Out of Service"])

	def test_require_transition_passes_on_valid(self):
		row = {"name": "VA-0001", "status": "Available", "version": 0}
		lifecycle._require_transition(row, current="Available",
		                              target="Occupied", asset_name="VA-0001")

	def test_require_transition_throws_on_mismatch(self):
		row = {"name": "VA-0001", "status": "Dirty", "version": 0}
		with self.assertRaises(frappe.ValidationError):
			lifecycle._require_transition(row, current="Available",
			                              target="Occupied", asset_name="VA-0001")

	def test_require_oos_entry_throws_on_already_oos(self):
		row = {"name": "VA-0001", "status": "Out of Service", "version": 0}
		with self.assertRaises(frappe.ValidationError):
			lifecycle._require_oos_entry(row, asset_name="VA-0001")

	def test_require_oos_entry_passes_on_other_states(self):
		for status in ("Available", "Occupied", "Dirty"):
			row = {"name": "VA-0001", "status": status, "version": 0}
			lifecycle._require_oos_entry(row, asset_name="VA-0001")  # no raise

	def test_log_helper_skipped_in_test_flag(self):
		"""Grok review: Asset Status Log helper short-circuits when in_test is set."""
		prev_flag = frappe.flags.in_test
		frappe.flags.in_test = True
		try:
			result = lifecycle._make_asset_status_log(
				asset_name="VA-0001",
				previous="Available",
				new_status="Occupied",
				reason=None,
				operator="test@example.com",
				venue_session=None,
			)
			self.assertIsNone(result)
		finally:
			frappe.flags.in_test = prev_flag


class TestStartSession(IntegrationTestCase):
	def setUp(self):
		# Walk-in customer is required (DEC-055 §1). The seed patch creates it,
		# but this test runs before Task 11, so create it here as a local fixture.
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"START-TEST-{suffix.upper()}",
			"asset_name": f"Start Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9002,
			"version": 0,
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_start_session_flips_asset_to_occupied(self):
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Occupied")
		self.assertEqual(asset.current_session, session_name)
		self.assertEqual(asset.version, 1)
		# Review 2026-04-10: lock the contract Tasks 5-8 will copy — every
		# transition stamps hamilton_last_status_change.
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_start_session_creates_venue_session(self):
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)
		s = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(s.venue_asset, self.asset.name)
		self.assertEqual(s.assignment_status, "Assigned")
		self.assertEqual(s.operator_checkin, "Administrator")
		self.assertEqual(s.status, "Active")
		self.assertIsNotNone(s.session_start)

	def test_start_session_rejects_non_available(self):
		# Walk the transitions legally: Available → Occupied → Dirty,
		# because VenueAsset._validate_status_transition rejects illegal edges.
		self.asset.status = "Occupied"
		self.asset.save(ignore_permissions=True)
		self.asset.status = "Dirty"
		self.asset.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Dirty")


class TestVacateSession(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"VACATE-TEST-{suffix.upper()}",
			"asset_name": f"Vacate Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9003,
			"version": 0,
		}).insert(ignore_permissions=True)
		self.session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_vacate_moves_to_dirty(self):
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Dirty")
		self.assertIsNone(asset.current_session)
		self.assertIsNotNone(asset.last_vacated_at)
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for vacate.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_vacate_closes_session(self):
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		s = frappe.get_doc("Venue Session", self.session_name)
		self.assertEqual(s.status, "Completed")
		self.assertEqual(s.operator_vacate, "Administrator")
		self.assertEqual(s.vacate_method, "Key Return")
		self.assertIsNotNone(s.session_end)

	def test_vacate_rejects_non_occupied(self):
		# Move asset to Dirty first so it's no longer Occupied
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator", vacate_method="Key Return"
			)
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Dirty")

	def test_vacate_requires_valid_method(self):
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator", vacate_method="Nonsense"
			)

	def test_vacate_rejects_oos_asset(self):
		"""OOS → vacate must throw.

		3-AI review 2026-04-10: closes the gap where test_vacate_rejects_non_occupied
		only covers Dirty → vacate. Walk the asset Occupied → OOS via the real
		pipeline (set_asset_out_of_service auto-closes the linked session via
		Discovery on Rounds), then attempt vacate_session and assert rejection.
		"""
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Maintenance"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(
				self.asset.name, operator="Administrator", vacate_method="Key Return"
			)
		# Lock release after rejection — same invariant as the other tests.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Out of Service")


class TestMarkClean(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		# VenueAsset._validate_status_transition requires new assets to start
		# as Available, so walk the state machine Available → Occupied → Dirty.
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"CLEAN-TEST-{suffix.upper()}",
			"asset_name": f"Clean Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9004,
			"version": 0,
		}).insert(ignore_permissions=True)
		self.asset.status = "Occupied"
		self.asset.save(ignore_permissions=True)
		self.asset.status = "Dirty"
		self.asset.save(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_mark_clean_moves_dirty_to_available(self):
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")
		self.assertIsNotNone(asset.last_cleaned_at)
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for mark-clean.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_mark_clean_rejects_non_dirty(self):
		self.asset.status = "Available"
		self.asset.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Available")

	def test_mark_clean_accepts_bulk_reason(self):
		"""Bulk reason must be propagated as log_reason to _set_asset_status.

		DEC-054 §5: bulk reason is written to the Asset Status Log row's reason
		field. We mock _set_asset_status to verify the kwarg wiring at the unit
		layer without depending on Task 11's log-creation integration.
		"""
		from unittest.mock import patch
		target = "hamilton_erp.lifecycle._set_asset_status"
		with patch(target, wraps=lifecycle._set_asset_status) as spy:
			lifecycle.mark_asset_clean(
				self.asset.name, operator="Administrator",
				bulk_reason="Bulk Mark Clean — Room reset",
			)
		spy.assert_called_once()
		self.assertEqual(
			spy.call_args.kwargs["log_reason"],
			"Bulk Mark Clean — Room reset",
		)
		# Happy-path still sanity-checked so a broken _set_asset_status doesn't
		# hide behind the spy.
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")


class TestSetOutOfService(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"OOS-TEST-{suffix.upper()}",
			"asset_name": f"OOS Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9005,
			"version": 0,
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_oos_from_available(self):
		"""Happy path + assert `reason` kwarg reaches _set_asset_status as log_reason.

		The wraps= pattern (from Task 6 fix bundle) records call args while
		still invoking the real implementation, so the status/reason-field
		assertions below still fire.
		"""
		from unittest.mock import patch
		target = "hamilton_erp.lifecycle._set_asset_status"
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		with patch(target, wraps=lifecycle._set_asset_status) as spy:
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="Plumbing failure"
			)
		spy.assert_called_once()
		self.assertEqual(spy.call_args.kwargs["log_reason"], "Plumbing failure")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Out of Service")
		self.assertEqual(asset.reason, "Plumbing failure")
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for OOS entry.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_oos_from_occupied_closes_session(self):
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator"
		)
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Emergency"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Out of Service")
		s = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(s.status, "Completed")
		self.assertEqual(s.vacate_method, "Discovery on Rounds")

	def test_oos_from_dirty(self):
		"""Dirty → OOS routes through the `else` branch (log_venue_session=None).

		Locks in the invariant that vacate_session clears current_session,
		so a Dirty asset entering OOS has no session to link in the audit log.
		Walk the asset through the real pipeline (start → vacate → oos) rather
		than raw save() so the invariant is exercised end-to-end.
		"""
		lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
		lifecycle.vacate_session(
			self.asset.name, operator="Administrator", vacate_method="Key Return"
		)
		# Asset is now Dirty with current_session=None (vacate_session invariant).
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Plumbing after turnover"
		)
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Out of Service")
		self.assertEqual(asset.reason, "Plumbing after turnover")
		# The load-bearing invariant: Dirty assets have no current_session, so
		# OOS-from-Dirty cannot link the audit log back to any session.
		self.assertIsNone(asset.current_session)

	def test_oos_requires_reason(self):
		# Empty string
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason=""
			)
		# Whitespace-only — covered by `not reason.strip()` branch
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="   \t\n  "
			)

	def test_oos_reject_if_already_oos(self):
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="First"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="Second"
			)
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Out of Service")


class TestReturnToService(IntegrationTestCase):
	def setUp(self):
		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"RETURN-TEST-{suffix.upper()}",
			"asset_name": f"Return Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9006,
			"version": 0,
		}).insert(ignore_permissions=True)
		# Walk to OOS via the real production pipeline (Task 7's function).
		# Raw-inserting with status="Out of Service" is blocked by the
		# "New assets must start as Available" guard in venue_asset.py.
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="Initial OOS"
		)

	def tearDown(self):
		frappe.db.rollback()

	def test_return_moves_to_available(self):
		"""Happy path + assert `reason` kwarg reaches _set_asset_status as log_reason.

		Also locks in the Gemini-review requirement that OOS → Available
		clears asset.reason via the new elif branch in _set_asset_status.
		"""
		from unittest.mock import patch
		target = "hamilton_erp.lifecycle._set_asset_status"
		initial_version = frappe.db.get_value("Venue Asset", self.asset.name, "version")
		with patch(target, wraps=lifecycle._set_asset_status) as spy:
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator", reason="Repair done"
			)
		spy.assert_called_once()
		self.assertEqual(spy.call_args.kwargs["log_reason"], "Repair done")
		self.assertEqual(spy.call_args.kwargs["previous"], "Out of Service")
		asset = frappe.get_doc("Venue Asset", self.asset.name)
		self.assertEqual(asset.status, "Available")
		self.assertIsNotNone(asset.last_cleaned_at)
		# Gemini review 2026-04-10: OOS → Available MUST clear asset.reason.
		# The setUp seeds "Initial OOS", so any regression in the reason-
		# clearing else branch of _set_asset_status fails loudly here.
		self.assertFalse(asset.reason)
		# 3-AI review 2026-04-10: every transition must bump version + stamp
		# hamilton_last_status_change. Lock these contracts for return-to-service.
		self.assertEqual(asset.version, initial_version + 1)
		self.assertIsNotNone(asset.hamilton_last_status_change)

	def test_return_requires_reason(self):
		with self.assertRaises(frappe.ValidationError):
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator", reason="   "
			)

	def test_return_rejects_non_oos(self):
		# Walk the asset back to Available via the real pipeline so the
		# state machine guards are respected.
		lifecycle.return_asset_to_service(
			self.asset.name, operator="Administrator", reason="Pre-reject reset"
		)
		with self.assertRaises(frappe.ValidationError):
			lifecycle.return_asset_to_service(
				self.asset.name, operator="Administrator", reason="any"
			)
		# Review 2026-04-10: the rejection path must release the Redis lock via
		# the finally-block Lua CAS. If release was skipped, acquiring the same
		# asset's lock in a fresh call would raise LockContentionError instead
		# of entering the with-block cleanly.
		from hamilton_erp.locks import asset_status_lock
		with asset_status_lock(self.asset.name, "verify-release") as row:
			self.assertEqual(row["status"], "Available")


class TestSessionNumberGenerator(IntegrationTestCase):
	"""Task 9: DEC-033 session number generator with Redis INCR + DB fallback.

	Sequence is reset by KEY NAME (the date-based prefix changes at midnight),
	not by TTL. The 48h TTL just garbage-collects stale keys. When the Redis
	key is cold, `_next_session_number` falls back to the max trailing sequence
	for today's prefix in `tabVenue Session` so a mid-day Redis flush cannot
	restart the daily sequence at 001 and collide with already-persisted rows.
	"""

	def setUp(self):
		# No Walk-in Customer fixture needed — the generator is pure (no
		# Venue Session inserts). The DB-fallback test seeds its own asset
		# + session directly. If a future change ever gives session_number
		# a default that inserts a Customer-linked row, a failing test will
		# flag it and we'll add the fixture then (YAGNI).
		# Compute today's Redis key up front so setUp/tearDown and tests all
		# target the same string. nowdate() returns "YYYY-MM-DD".
		year, month, day = frappe.utils.nowdate().split("-")
		self._prefix = f"{int(day)}-{int(month)}-{int(year)}"
		self._key = f"hamilton:session_seq:{self._prefix}"
		# Flush any leftover Redis key from prior runs or other tests run
		# earlier in the same day. Uses raw .delete() to match the raw .set()
		# / .incr() path the generator uses — wrapper methods like
		# delete_value() prefix the key via make_key() and would miss it.
		frappe.cache().delete(self._key)

	def tearDown(self):
		# Rollback DB so seeded Venue Asset / Venue Session rows evaporate,
		# AND flush the Redis key so other tests in the same day don't see
		# leftover state from this class.
		frappe.db.rollback()
		frappe.cache().delete(self._key)

	def test_first_call_returns_0001(self):
		n = lifecycle._next_session_number()
		self.assertTrue(
			n.endswith("---0001"),
			f"Expected first call to end with ---0001, got {n}",
		)

	def test_second_call_returns_0002(self):
		lifecycle._next_session_number()
		n2 = lifecycle._next_session_number()
		self.assertTrue(
			n2.endswith("---0002"),
			f"Expected second call to end with ---0002, got {n2}",
		)

	def test_format_matches_dec_033(self):
		"""DEC-033: {d}-{m}-{y}---{NNNN}. Day/month NOT zero-padded; sequence IS."""
		n = lifecycle._next_session_number()
		prefix, seq = n.split("---")
		parts = prefix.split("-")
		self.assertEqual(len(parts), 3, f"Prefix should be d-m-y, got {prefix}")
		# Sequence is always 4 digits, zero-padded (Task 11: widened from 3).
		self.assertEqual(len(seq), 4, f"Sequence should be 4 digits, got {seq}")
		self.assertTrue(seq.isdigit(), f"Sequence should be numeric, got {seq}")
		# Prefix matches today's computed prefix (guards against off-by-one
		# timezone or formatting regressions).
		self.assertEqual(prefix, self._prefix)

	def test_db_fallback_when_redis_cold(self):
		"""When the Redis key is cold but the DB already has today's rows,
		resume the sequence at db_max + 1 instead of restarting at 001.

		This is the load-bearing invariant: a mid-day Redis flush must not
		cause session_number collisions against already-persisted rows.
		"""
		suffix = uuid.uuid4().hex[:6]
		asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"SEQ-TEST-{suffix.upper()}",
			"asset_name": f"Seq Fallback {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9007,
			"version": 0,
		}).insert(ignore_permissions=True)
		# Directly seed a Venue Session with today's prefix + sequence 005.
		# Only mandatory fields per venue_session.json are populated:
		# venue_asset, status, session_start, operator_checkin.
		frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": asset.name,
			"session_number": f"{self._prefix}---0005",
			"status": "Active",
			"session_start": frappe.utils.now_datetime(),
			"operator_checkin": "Administrator",
		}).insert(ignore_permissions=True)
		# Ensure the Redis key is cold before the call — simulates the
		# post-flush scenario that motivated the fallback.
		frappe.cache().delete(self._key)
		n = lifecycle._next_session_number()
		self.assertEqual(
			n,
			f"{self._prefix}---0006",
			f"Expected cold-Redis fallback to resume at db_max+1=0006, got {n}",
		)


class TestCreateSessionRetryOnDuplicate(IntegrationTestCase):
	"""Task 11(c): _create_session retries up to 3 times on UniqueValidationError.

	The DB has a UNIQUE constraint on Venue Session.session_number. If a
	Redis hiccup or cold-start race ever produces a duplicate, the INSERT
	raises UniqueValidationError (field-level unique violation, raised by
	frappe.model.base_document.show_unique_validation_message). _create_session
	catches it and retries with a fresh session_number (rebuilt doc dict →
	before_insert re-runs → _next_session_number() re-runs → fresh Redis INCR).
	"""

	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"RETRY-{suffix.upper()}",
			"asset_name": f"Retry Test {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9099,
			"version": 0,
		}).insert(ignore_permissions=True)

		# Pre-seed a Venue Session under a far-future prefix so the retry
		# tests can force collisions without touching today's Redis key
		# (and without depending on date mocking).
		self._collide_prefix = "1-1-2099"
		self._collide_key = f"hamilton:session_seq:{self._collide_prefix}"
		self._collide_number = f"{self._collide_prefix}---0001"

		# Seed the colliding row on a throwaway asset so the UNIQUE
		# constraint fires on any subsequent insert with the same number.
		decoy_suffix = uuid.uuid4().hex[:6]
		self.decoy_asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"DECOY-{decoy_suffix.upper()}",
			"asset_name": f"Decoy {decoy_suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9100,
			"version": 0,
		}).insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": self.decoy_asset.name,
			"session_number": self._collide_number,
			"status": "Active",
			"session_start": frappe.utils.now_datetime(),
			"operator_checkin": "Administrator",
			"customer": "Walk-in",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()
		frappe.cache().delete(self._collide_key)

	def test_retry_succeeds_after_collisions(self):
		"""If the first 2 attempts collide, the 3rd attempt succeeds with a fresh number."""
		from unittest.mock import patch

		call_count = {"n": 0}

		# Patch _next_session_number to return the colliding value on the
		# first 2 calls and a unique value on the 3rd. This simulates a
		# Redis state where INCR transiently returns a stale/duplicate
		# sequence before catching up.
		unique_number = f"{self._collide_prefix}---0099"

		def fake_next(*args, **kwargs):
			# Accept **kwargs because _create_session now passes for_date=
			# (Fix 10 Part A, DEC-056). We ignore it here — the test only
			# cares about the sequence of return values.
			call_count["n"] += 1
			if call_count["n"] <= 2:
				return self._collide_number
			return unique_number

		with patch("hamilton_erp.lifecycle._next_session_number", side_effect=fake_next):
			session_name = lifecycle._create_session(
				self.asset.name, operator="Administrator", customer="Walk-in"
			)

		self.assertEqual(call_count["n"], 3)
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.session_number, unique_number)
		self.assertEqual(session.venue_asset, self.asset.name)

	def test_retry_exhausted_raises_validation_error(self):
		"""After 3 collisions in a row, _create_session raises ValidationError."""
		from unittest.mock import patch

		with patch(
			"hamilton_erp.lifecycle._next_session_number",
			return_value=self._collide_number,
		):
			with self.assertRaises(frappe.ValidationError) as ctx:
				lifecycle._create_session(
					self.asset.name, operator="Administrator", customer="Walk-in"
				)
		self.assertIn("Session number collision", str(ctx.exception))

	def test_message_log_restored_after_successful_retry(self):
		"""Task 11 3-AI review, Fix 2: successful retries must not leak stale
		"must be unique" toasts into frappe.local.message_log.

		Scenario: the first 2 inserts collide on session_number (raising
		UniqueValidationError, which appends a "must be unique" toast), then
		the 3rd succeeds. The snapshot/restore logic in _create_session MUST
		discard the failed-attempt toasts so the operator does not see a
		misleading warning alongside a successful assignment.
		"""
		from unittest.mock import patch

		# Clear any pre-existing messages so our assertion is precise.
		frappe.local.message_log = []

		unique_number = f"{self._collide_prefix}---0077"
		call_count = {"n": 0}

		def fake_next(*args, **kwargs):
			# Accept **kwargs because _create_session now passes for_date=
			# (Fix 10 Part A, DEC-056).
			call_count["n"] += 1
			if call_count["n"] <= 2:
				return self._collide_number
			return unique_number

		with patch("hamilton_erp.lifecycle._next_session_number", side_effect=fake_next):
			session_name = lifecycle._create_session(
				self.asset.name, operator="Administrator", customer="Walk-in"
			)

		# (a) Session was created successfully.
		self.assertTrue(frappe.db.exists("Venue Session", session_name))
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.session_number, unique_number)

		# (b) message_log has no residual "must be unique" toast from the
		# two failed attempts. Each entry in message_log is a dict with a
		# 'message' key; stringify defensively in case Frappe changes the
		# shape across versions.
		leaked_toasts = [
			m for m in (getattr(frappe.local, "message_log", []) or [])
			if "must be unique" in str(m).lower()
		]
		self.assertEqual(
			leaked_toasts,
			[],
			f"Expected message_log clean after retry, but found leaked "
			f"'must be unique' toasts: {leaked_toasts}",
		)


class TestCreateSessionMidnightBoundary(IntegrationTestCase):
	"""Fix 10 / DEC-056: _create_session pins session_number date to
	session_start. Retries that cross midnight MUST reuse the start_date
	instead of re-deriving it from wall-clock.

	Club Hamilton is open overnight Friday and Saturday — this is a real
	operational scenario for a 24h venue, not a theoretical race. Without
	this fix, a collision retry that straddles midnight would emit a
	session_number whose date prefix does not match session_start's date.
	"""

	def setUp(self):
		if not frappe.db.exists("Customer", "Walk-in"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "Walk-in",
				"customer_group": frappe.db.get_value(
					"Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
				"territory": frappe.db.get_value(
					"Territory", {"is_group": 0}, "name") or "All Territories",
			}).insert(ignore_permissions=True)

		suffix = uuid.uuid4().hex[:6]
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"MIDBND-{suffix.upper()}",
			"asset_name": f"Midnight Boundary {suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9300,
			"version": 0,
		}).insert(ignore_permissions=True)

		# Pre-seed a decoy Venue Session under day X's prefix so the
		# first insert attempt in _create_session will collide with it
		# on the UNIQUE (session_number) constraint. This forces the
		# real retry loop to run end-to-end — the test is NOT a pure
		# mock: Frappe's insert actually hits the DB and the UNIQUE
		# index actually fires.
		self._collide_prefix = "15-3-2099"
		self._collide_number = f"{self._collide_prefix}---0001"
		self._collide_key = f"hamilton:session_seq:{self._collide_prefix}"

		decoy_suffix = uuid.uuid4().hex[:6]
		self.decoy_asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"MIDDCY-{decoy_suffix.upper()}",
			"asset_name": f"Midnight Decoy {decoy_suffix}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9301,
			"version": 0,
		}).insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": self.decoy_asset.name,
			"session_number": self._collide_number,
			"status": "Active",
			"session_start": frappe.utils.now_datetime(),
			"operator_checkin": "Administrator",
			"customer": "Walk-in",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()
		frappe.cache().delete(self._collide_key)

	def test_midnight_boundary_session_number_matches_session_start(self):
		"""Simulate a call at 23:59 on day X that collides on the first
		insert. The retry happens after midnight (day Y wall-clock). The
		final persisted session MUST have:
		  - session_number prefix = day X (not day Y)
		  - session_start date    = day X (not day Y)
		  - _next_session_number called with for_date=day_X on BOTH attempts
		"""
		from datetime import date as date_cls, datetime as datetime_cls
		from unittest.mock import patch

		day_x_night = datetime_cls(2099, 3, 15, 23, 59, 30)
		day_y_morning = datetime_cls(2099, 3, 16, 0, 0, 45)
		day_x_date = date_cls(2099, 3, 15)

		# Fake now_datetime: first call returns day X at 23:59:30 (this
		# is the session_start capture). Any subsequent call would
		# return day Y at 00:00:45 — if the implementation re-reads
		# the wall-clock inside the retry loop (the bug), it would pick
		# up day Y here.
		now_calls = {"n": 0}

		def fake_now_datetime():
			now_calls["n"] += 1
			return day_x_night if now_calls["n"] == 1 else day_y_morning

		# Fake _next_session_number: capture the for_date parameter on
		# every call, return the colliding number the first time
		# (forcing a retry), and a unique number the second time. The
		# captured for_dates are the primary assertion: both calls MUST
		# receive day X, not day Y.
		captured_for_dates = []
		unique_number = f"{self._collide_prefix}---0077"

		def fake_next(*, for_date=None, **kwargs):
			captured_for_dates.append(for_date)
			if len(captured_for_dates) == 1:
				return self._collide_number
			return unique_number

		# Also mock the overlapping nowdate path — _next_session_number
		# only calls nowdate() when for_date is None, which should NOT
		# happen under the fix. We still patch it to day Y so a buggy
		# implementation that ignores for_date and falls back to
		# nowdate would produce visibly-wrong day Y prefixes.
		with patch("hamilton_erp.lifecycle.now_datetime", side_effect=fake_now_datetime), \
		     patch("hamilton_erp.lifecycle._next_session_number", side_effect=fake_next), \
		     patch("frappe.utils.nowdate", return_value="2099-03-16"):
			session_name = lifecycle._create_session(
				self.asset.name, operator="Administrator", customer="Walk-in"
			)

		# Assertion 1: two attempts happened — collision + successful retry.
		self.assertEqual(
			len(captured_for_dates), 2,
			f"Expected exactly 2 attempts (collision + retry), "
			f"got {len(captured_for_dates)}",
		)

		# Assertion 2: BOTH attempts passed day X's date to
		# _next_session_number. The second attempt receiving day Y
		# would mean the retry loop re-derived the date from wall-clock.
		for i, fd in enumerate(captured_for_dates, start=1):
			self.assertEqual(
				fd, day_x_date,
				f"Attempt {i}: _next_session_number received for_date={fd!r}, "
				f"expected {day_x_date!r}. Retries MUST NOT re-derive the "
				f"date from wall-clock — the midnight boundary bug is back.",
			)

		# Assertion 3: the final persisted session has day X's
		# session_number prefix AND day X's session_start.
		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.session_number, unique_number)
		self.assertTrue(
			session.session_number.startswith(f"{self._collide_prefix}---"),
			f"session_number {session.session_number!r} does not start with "
			f"day X prefix {self._collide_prefix!r} — midnight boundary bug.",
		)
		self.assertEqual(
			session.session_start.date(), day_x_date,
			f"session_start date {session.session_start.date()} != "
			f"{day_x_date} — session_start was captured after midnight.",
		)


class TestNextSessionNumberRedisFailure(IntegrationTestCase):
	"""Task 11 3-AI review, Fix 3: Redis faults must surface as a
	user-friendly ValidationError, not a bare redis.ConnectionError
	stack trace.
	"""

	def test_redis_failure_raises_validation_error(self):
		"""If cache().get raises redis.ConnectionError, _next_session_number
		catches it and raises frappe.ValidationError with 'temporarily
		unavailable' in the message."""
		import redis
		from unittest.mock import patch

		# Patch the cache's .get to raise on the very first call — this
		# simulates Redis being down when we check whether the sequence
		# key exists. The broad except in _next_session_number should
		# wrap this in a user-friendly ValidationError.
		with patch.object(
			frappe.cache(), "get",
			side_effect=redis.ConnectionError("simulated Redis outage"),
		):
			with self.assertRaises(frappe.ValidationError) as ctx:
				lifecycle._next_session_number()

		self.assertIn("temporarily unavailable", str(ctx.exception))


# ---------------------------------------------------------------------------
# Task 12 — Realtime publishers
# ---------------------------------------------------------------------------


class TestRealtimePublishers(IntegrationTestCase):
	"""Task 12: realtime.publish_status_change and publish_board_refresh.

	Both publishers must fire `frappe.publish_realtime` with
	after_commit=True — they are called OUTSIDE the lock section from
	lifecycle.py, and the event must only be observable to clients after
	the transaction that produced the state change has committed.
	Emitting before commit would leak state that could still roll back.
	"""

	def setUp(self):
		self.asset = frappe.get_doc({
			"doctype": "Venue Asset",
			"asset_code": f"RT-{uuid.uuid4().hex[:6].upper()}",
			"asset_name": f"RT Test {uuid.uuid4().hex[:6]}",
			"asset_category": "Room",
			"asset_tier": "Single Standard",
			"status": "Available",
			"display_order": 9009,
			"version": 0,
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_publish_status_change_emits_expected_payload(self):
		from unittest.mock import patch

		captured = {}

		def fake_publish(event, payload, **kwargs):
			captured["event"] = event
			captured["payload"] = payload
			captured["kwargs"] = kwargs

		from hamilton_erp import realtime
		with patch.object(frappe, "publish_realtime", side_effect=fake_publish):
			realtime.publish_status_change(self.asset.name, previous_status="Available")

		self.assertEqual(captured["event"], "hamilton_asset_status_changed")
		self.assertEqual(captured["payload"]["name"], self.asset.name)
		self.assertEqual(captured["payload"]["old_status"], "Available")
		self.assertIn("version", captured["payload"])
		self.assertIn("status", captured["payload"])
		self.assertTrue(captured["kwargs"].get("after_commit"))

	def test_publish_board_refresh_emits_expected_payload(self):
		from unittest.mock import patch

		captured = {}

		def fake_publish(event, payload, **kwargs):
			captured["event"] = event
			captured["payload"] = payload
			captured["kwargs"] = kwargs

		from hamilton_erp import realtime
		with patch.object(frappe, "publish_realtime", side_effect=fake_publish):
			realtime.publish_board_refresh("bulk_clean", 5)

		self.assertEqual(captured["event"], "hamilton_asset_board_refresh")
		self.assertEqual(captured["payload"]["triggered_by"], "bulk_clean")
		self.assertEqual(captured["payload"]["count"], 5)
		self.assertTrue(captured["kwargs"].get("after_commit"))

	def test_publish_status_change_noop_when_asset_missing(self):
		"""If the asset row does not exist (e.g. deleted between the
		lifecycle call and the after-commit publish), the publisher
		returns cleanly instead of raising. The alternative — blowing
		up on a missing row — would surface a confusing error to the
		operator for a state change that already committed successfully."""
		from unittest.mock import patch

		captured = {"called": False}

		def fake_publish(event, payload, **kwargs):
			captured["called"] = True

		from hamilton_erp import realtime
		with patch.object(frappe, "publish_realtime", side_effect=fake_publish):
			realtime.publish_status_change(
				"NonExistent-ASSET-XYZ", previous_status="Available"
			)

		self.assertFalse(
			captured["called"],
			"publish_status_change must be a no-op when the asset row "
			"cannot be read — not emit an empty/bogus event.",
		)


# ===========================================================================
# Audit 2026-04-11 — Groups B, C, D, J
# Lifecycle races, session-number edges, version CAS, realtime contracts
# ===========================================================================


def _ensure_walkin_al():
	"""Idempotent Walk-in customer for audit-added tests below."""
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


def _make_audit_asset(name: str, status: str = "Available",
                      category: str = "Room", tier: str = "Single Standard"):
	_ensure_walkin_al()
	return frappe.get_doc({
		"doctype": "Venue Asset",
		"asset_code": f"AL-{uuid.uuid4().hex[:8].upper()}",
		"asset_name": name,
		"asset_category": category,
		"asset_tier": tier if category == "Room" else "Locker",
		"status": status,
		"display_order": 950,
	}).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Group B — Lifecycle races (6 tests)
# ---------------------------------------------------------------------------


class TestLifecycleRaces(IntegrationTestCase):
	"""Cross-operation races that the lock + state machine must catch.

	The locks serialize status changes on a single asset, so most of these
	races look linear end-to-end. What we're really verifying is that the
	second call observes the first call's committed row under FOR UPDATE
	and throws the expected ValidationError instead of silently corrupting
	state.
	"""

	def setUp(self):
		self.asset = _make_audit_asset("Race Test Asset")

	def tearDown(self):
		frappe.db.rollback()

	def test_B1_concurrent_vacate_of_same_session_throws_second(self):
		"""Two vacate calls on the same Occupied asset — second must fail
		because the first closes the session and flips the asset to Dirty.
		"""
		lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
		lifecycle.vacate_session(self.asset.name, operator="Administrator",
		                         vacate_method="Key Return")
		with self.assertRaises(frappe.ValidationError):
			lifecycle.vacate_session(self.asset.name, operator="Administrator",
			                         vacate_method="Key Return")

	def test_B2_concurrent_mark_clean_throws_second(self):
		"""Dirty → Available on an already-cleaned asset must throw.

		Covers the transition-validation path inside the lock body.
		"""
		lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
		lifecycle.vacate_session(self.asset.name, operator="Administrator",
		                         vacate_method="Key Return")
		lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
		with self.assertRaises(frappe.ValidationError):
			lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")

	def test_B3_concurrent_oos_on_already_oos_throws(self):
		"""`_require_oos_entry` must reject OOS → OOS inside the lock body."""
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="broken 1")
		with self.assertRaises(frappe.ValidationError):
			lifecycle.set_asset_out_of_service(
				self.asset.name, operator="Administrator", reason="broken 2")

	def test_B4_start_session_then_oos_keeps_session_closed(self):
		"""Starting a session then immediately OOS-ing the asset must
		auto-close the session with Discovery on Rounds and leave it in
		the Completed state — not orphaned Active.
		"""
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator")
		lifecycle.set_asset_out_of_service(
			self.asset.name, operator="Administrator", reason="asset broke")
		s = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(s.status, "Completed")
		self.assertEqual(s.vacate_method, "Discovery on Rounds")

	def test_B5_close_session_wrong_asset_link_defensive_guard(self):
		"""lifecycle._close_current_session throws if the passed session
		belongs to a different asset (line 376-378). Covers the defensive
		cross-doctype invariant that protects against manual SQL edits or
		future double-close bugs.
		"""
		other_asset = _make_audit_asset("Race Other Asset")
		sess_a = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator")
		lifecycle.start_session_for_asset(
			other_asset.name, operator="Administrator")
		# Point sess_a at the WRONG asset in-memory, then call the private
		# helper directly — lock ordering is not at issue because the
		# helper itself throws before any write.
		with self.assertRaises(frappe.ValidationError) as ctx:
			lifecycle._close_current_session(
				other_asset.name,
				current_session=sess_a,
				operator="Administrator",
				vacate_method="Key Return",
			)
		self.assertIn("belongs to", str(ctx.exception))

	def test_B6_close_already_completed_session_defensive_guard(self):
		"""lifecycle._close_current_session throws if the session is
		already Completed (line 379-381). Protects against a bug that
		would otherwise double-close and overwrite session_end.
		"""
		session_name = lifecycle.start_session_for_asset(
			self.asset.name, operator="Administrator")
		lifecycle.vacate_session(self.asset.name, operator="Administrator",
		                         vacate_method="Key Return")
		# Session is now Completed. Calling the private helper again
		# must refuse.
		with self.assertRaises(frappe.ValidationError) as ctx:
			lifecycle._close_current_session(
				self.asset.name,
				current_session=session_name,
				operator="Administrator",
				vacate_method="Key Return",
			)
		self.assertIn("already", str(ctx.exception))


# ---------------------------------------------------------------------------
# Group C — Session number edges (5 tests)
# ---------------------------------------------------------------------------


class TestSessionNumberEdges(IntegrationTestCase):
	def setUp(self):
		# Flush today's session counter to isolate test state
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		frappe.cache().delete(f"hamilton:session_seq:{prefix}")

	def tearDown(self):
		frappe.db.rollback()
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		frappe.cache().delete(f"hamilton:session_seq:{prefix}")

	def test_C1_sequence_overflow_past_9999_logs_warning(self):
		"""_next_session_number logs a warning (NOT raises) once the daily
		sequence exceeds 9999. The format string still renders (Python %d
		never truncates), so correctness holds — but ops needs to hear
		about it.
		"""
		from unittest.mock import patch
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		key = f"hamilton:session_seq:{prefix}"
		cache = frappe.cache()
		# Seed at 9999 so next INCR yields 10000
		cache.set(key, 9999, px=60_000)
		warnings: list[str] = []

		class _L:
			def warning(self, msg):
				warnings.append(msg)

		with patch("frappe.logger", return_value=_L()):
			sn = lifecycle._next_session_number()
		self.assertTrue(
			any("overflow" in w for w in warnings),
			f"Expected overflow warning; got: {warnings}",
		)
		self.assertTrue(sn.endswith("10000"),
			f"Expected 10000 tail, got {sn}")

	def test_C2_unique_validation_on_non_session_number_field_reraises(self):
		"""_create_session catches UniqueValidationError ONLY if the field
		is session_number. Any other unique-field collision must propagate
		(lifecycle.py line 221). Without this, a future unique constraint
		would silently retry 3 times with the wrong field.
		"""
		from unittest.mock import patch

		class _FakeExc(frappe.UniqueValidationError):
			pass

		call_count = {"n": 0}

		def boom_on_insert(self, *a, **k):
			call_count["n"] += 1
			# Raise a unique-violation that mentions a DIFFERENT field,
			# NOT session_number. The scoping guard must let it escape.
			raise _FakeExc("some_other_field must be unique")

		with patch.object(frappe.model.document.Document, "insert", boom_on_insert):
			with self.assertRaises(frappe.UniqueValidationError):
				lifecycle._create_session(
					"FAKE-ASSET", operator="Administrator", customer="Walk-in")
		# Must NOT retry 3 times — single raise, single call
		self.assertEqual(call_count["n"], 1,
			f"Expected 1 insert attempt; got {call_count['n']} "
			f"— non-session_number unique error was retried")

	def test_C3_incr_return_value_cast_to_int(self):
		"""redis-py returns INCR as int, but _next_session_number explicitly
		casts via `int(cache.incr(key))`. If a future redis wrapper returns
		bytes/str, the format spec `{seq:04d}` would blow up. Pin the cast
		as part of the contract.
		"""
		from unittest.mock import patch
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		cache = frappe.cache()
		real_incr = cache.incr
		def str_incr(key):
			# Return a string to simulate a misbehaving redis wrapper
			return str(real_incr(key))
		# Seed so the cold-path DB query is skipped
		cache.set(f"hamilton:session_seq:{prefix}", 0, px=60_000)
		with patch.object(cache, "incr", side_effect=str_incr):
			sn = lifecycle._next_session_number()
		# Must contain a 4-digit tail, not a Python repr
		self.assertRegex(sn, r"---\d{4}$")

	def test_C4_db_max_fallback_handles_multiple_historic_rows(self):
		"""_db_max_seq_for_prefix must return the MAX trailing sequence,
		not an arbitrary row. Seed several rows with distinct tails and
		verify the helper picks the highest.
		"""
		_ensure_walkin_al()
		asset = _make_audit_asset("DB Max Seed Asset")
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		# Seed three historic rows with known tails
		for tail in ("0005", "0017", "0042"):
			frappe.get_doc({
				"doctype": "Venue Session",
				"venue_asset": asset.name,
				"operator_checkin": "Administrator",
				"customer": "Walk-in",
				"session_number": f"{prefix}---{tail}",
				"session_start": frappe.utils.now_datetime(),
				"status": "Active",
				"assignment_status": "Assigned",
			}).insert(ignore_permissions=True)
		self.assertEqual(lifecycle._db_max_seq_for_prefix(prefix), 42)

	def test_C5_cold_start_uses_db_max_not_zero(self):
		"""When Redis has no key for today's prefix, _next_session_number
		must seed from `_db_max_seq_for_prefix` + 1, not from 1. Otherwise
		a mid-day Redis flush would restart the sequence and collide with
		persisted rows.
		"""
		_ensure_walkin_al()
		asset = _make_audit_asset("Cold Start Asset")
		year, month, day = frappe.utils.nowdate().split("-")
		prefix = f"{int(day)}-{int(month)}-{int(year)}"
		# Seed a historic row at tail 0100 and flush redis
		frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": asset.name,
			"operator_checkin": "Administrator",
			"customer": "Walk-in",
			"session_number": f"{prefix}---0100",
			"session_start": frappe.utils.now_datetime(),
			"status": "Active",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)
		frappe.cache().delete(f"hamilton:session_seq:{prefix}")
		sn = lifecycle._next_session_number()
		# Must yield 0101, not 0001
		self.assertTrue(sn.endswith("0101"),
			f"Cold-start fallback failed: got {sn}, expected …0101")


# ---------------------------------------------------------------------------
# Group D — Version CAS (3 tests)
# ---------------------------------------------------------------------------


class TestVersionCAS(IntegrationTestCase):
	"""_set_asset_status reads version UNDER the lock via get_doc(..., for_update=True)
	then compares to expected_version. Under normal flow they always agree
	(the caller's row dict came from the same lock), but we simulate drift
	to pin the CAS invariant."""

	def setUp(self):
		self.asset = _make_audit_asset("CAS Test Asset")

	def tearDown(self):
		frappe.db.rollback()

	def test_D1_start_session_cas_detects_drifted_version(self):
		"""Call _set_asset_status with an expected_version that doesn't
		match the row — must throw 'Concurrent update'.
		"""
		with self.assertRaises(frappe.ValidationError) as ctx:
			lifecycle._set_asset_status(
				self.asset.name,
				new_status="Occupied",
				session=None,
				log_reason=None,
				operator="Administrator",
				previous="Available",
				expected_version=999,  # deliberately wrong
			)
		self.assertIn("Concurrent update", str(ctx.exception))

	def test_D2_vacate_cas_detects_drifted_version(self):
		"""Same CAS invariant on a Dirty transition."""
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Occupied")
		frappe.db.set_value("Venue Asset", self.asset.name, "version", 7)
		with self.assertRaises(frappe.ValidationError):
			lifecycle._set_asset_status(
				self.asset.name,
				new_status="Dirty",
				session=None,
				log_reason=None,
				operator="Administrator",
				previous="Occupied",
				expected_version=0,  # stale
			)

	def test_D3_mark_clean_cas_bumps_version_on_success(self):
		"""Happy path — _set_asset_status must bump version by exactly 1
		when the expected_version matches.
		"""
		frappe.db.set_value("Venue Asset", self.asset.name, {
			"status": "Dirty", "version": 3})
		lifecycle._set_asset_status(
			self.asset.name,
			new_status="Available",
			session=None,
			log_reason=None,
			operator="Administrator",
			previous="Dirty",
			expected_version=3,
		)
		self.assertEqual(
			frappe.db.get_value("Venue Asset", self.asset.name, "version"), 4)


# ---------------------------------------------------------------------------
# Group J — Realtime contracts (6 tests)
# ---------------------------------------------------------------------------


class TestRealtimeContracts(IntegrationTestCase):
	def setUp(self):
		self.asset = _make_audit_asset("Realtime Contract Asset")

	def tearDown(self):
		frappe.db.rollback()

	def test_J1_publish_never_called_inside_lock(self):
		"""Critical contract: publish_status_change must fire AFTER the
		lock releases. We instrument both the lock context manager and
		the publish helper to record ordering, then assert publish lands
		outside.

		Note: lifecycle.start_session_for_asset imports asset_status_lock
		and publish_status_change LOCALLY inside the function, so we
		patch their source modules (hamilton_erp.locks and
		hamilton_erp.realtime) — patching hamilton_erp.lifecycle.* would
		miss because the names never live on the lifecycle module.
		"""
		from unittest.mock import patch
		from hamilton_erp import locks, realtime
		events: list[str] = []
		real_lock = locks.asset_status_lock
		real_publish = realtime.publish_status_change

		from contextlib import contextmanager

		@contextmanager
		def tracking_lock(name, op):
			events.append("lock_enter")
			with real_lock(name, op) as row:
				yield row
			events.append("lock_exit")

		def tracking_publish(name, previous_status=None):
			events.append("publish")
			return real_publish(name, previous_status=previous_status)

		with patch("hamilton_erp.locks.asset_status_lock", tracking_lock), \
		     patch("hamilton_erp.realtime.publish_status_change", tracking_publish):
			lifecycle.start_session_for_asset(
				self.asset.name, operator="Administrator")
		self.assertEqual(events, ["lock_enter", "lock_exit", "publish"],
			f"Ordering violation: {events}")

	def test_J2_no_realtime_event_on_rejected_transition(self):
		"""If a transition is rejected inside the lock, NO realtime event
		may escape. publish_status_change sits after the `with` block, so
		an exception propagates before it's reached.
		"""
		from unittest.mock import patch
		frappe.db.set_value("Venue Asset", self.asset.name, "status", "Dirty")
		with patch("hamilton_erp.realtime.publish_status_change") as mock_pub:
			with self.assertRaises(frappe.ValidationError):
				# Dirty → can't start session
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator")
		mock_pub.assert_not_called()

	def test_J3_publish_exception_doesnt_corrupt_asset_state(self):
		"""If publish_status_change itself raises, the asset state change
		has already committed (publish is the LAST step). Verify that
		even in this pathological case, the DB still reflects the new
		status — the exception propagates but nothing rolls back.
		"""
		from unittest.mock import patch
		with patch("hamilton_erp.realtime.publish_status_change",
		           side_effect=RuntimeError("realtime broker down")):
			with self.assertRaises(RuntimeError):
				lifecycle.start_session_for_asset(
					self.asset.name, operator="Administrator")
		# State change survived the publish failure
		self.assertEqual(
			frappe.db.get_value("Venue Asset", self.asset.name, "status"),
			"Occupied",
		)

	def test_J4_c2_payload_contains_all_required_fields(self):
		"""Asset Board tile re-render needs all fields in the C2 payload:
		name, status, version, current_session, last_vacated_at,
		last_cleaned_at, hamilton_last_status_change, old_status.
		"""
		from unittest.mock import patch
		from hamilton_erp import realtime
		captured = {}
		def fake(event, payload, **kwargs):
			captured.update(payload)
		with patch.object(frappe, "publish_realtime", side_effect=fake):
			realtime.publish_status_change(
				self.asset.name, previous_status="Available")
		required = {
			"name", "status", "version", "current_session",
			"last_vacated_at", "last_cleaned_at",
			"hamilton_last_status_change", "old_status",
		}
		self.assertTrue(required.issubset(set(captured.keys())),
			f"C2 payload missing: {required - set(captured.keys())}")

	def test_J5_publish_status_change_sets_after_commit_true(self):
		"""after_commit=True is load-bearing: without it, the client
		receives an event for state that may still roll back.
		"""
		from unittest.mock import patch
		from hamilton_erp import realtime
		captured = {}
		def fake(event, payload, **kwargs):
			captured["kwargs"] = kwargs
		with patch.object(frappe, "publish_realtime", side_effect=fake):
			realtime.publish_status_change(
				self.asset.name, previous_status="Available")
		self.assertTrue(captured["kwargs"].get("after_commit"),
			"publish_status_change MUST use after_commit=True")

	def test_J6_board_refresh_uses_after_commit_true(self):
		"""publish_board_refresh is the bulk analog — same contract."""
		from unittest.mock import patch
		from hamilton_erp import realtime
		captured = {}
		def fake(event, payload, **kwargs):
			captured["kwargs"] = kwargs
		with patch.object(frappe, "publish_realtime", side_effect=fake):
			realtime.publish_board_refresh("bulk_clean", 10)
		self.assertTrue(captured["kwargs"].get("after_commit"),
			"publish_board_refresh MUST use after_commit=True")


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
