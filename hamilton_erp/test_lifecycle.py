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
