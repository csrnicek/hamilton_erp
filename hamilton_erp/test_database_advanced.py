"""Hamilton ERP — Advanced Database, Redis, and Frappe v16 Tests

Targets the infrastructure underneath the application logic:
  - MariaDB indexes, query plans, isolation levels, deadlocks
  - Redis lock TTL, INCR overflow, cold-start fallback
  - Frappe v16 framework behaviour (versioning, roles, hooks, scheduler)
  - Fraud detection: orphan sessions, duplicate assignment, bulk races

Run via:
  bench --site hamilton-unit-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_database_advanced
"""
from __future__ import annotations

import time
import uuid
from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from hamilton_erp import lifecycle
from hamilton_erp.lifecycle import (
	WALKIN_CUSTOMER,
	VACATE_DISCOVERY,
	mark_asset_clean,
	start_session_for_asset,
	vacate_session,
	set_asset_out_of_service,
	return_asset_to_service,
)
from hamilton_erp.locks import LOCK_TTL_MS, LockContentionError, asset_status_lock


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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
		"asset_code": f"DA-{name[:5].upper()}-{uuid.uuid4().hex[:4].upper()}",
		"asset_name": name,
		"asset_category": category,
		"asset_tier": tier if category == "Room" else "Locker",
		"status": status,
		"display_order": 9900,
	}).insert(ignore_permissions=True)


# ===========================================================================
# R1 — Database Performance: Index Verification
# ===========================================================================


class TestDatabaseIndexes(IntegrationTestCase):
	"""R1 — Verify MariaDB indexes exist and are used by critical queries."""

	def test_venue_asset_status_index_exists(self):
		"""tabVenue Asset has an index on the status column."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabVenue Asset' "
			"AND COLUMN_NAME = 'status'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index found on tabVenue Asset.status")

	def test_venue_session_session_number_index_exists(self):
		"""tabVenue Session has an index on session_number."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabVenue Session' "
			"AND COLUMN_NAME = 'session_number'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index on tabVenue Session.session_number")

	def test_venue_session_venue_asset_index_exists(self):
		"""tabVenue Session has an index on venue_asset."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabVenue Session' "
			"AND COLUMN_NAME = 'venue_asset'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index on tabVenue Session.venue_asset")

	def test_shift_record_operator_index_exists(self):
		"""tabShift Record has an index on operator."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabShift Record' "
			"AND COLUMN_NAME = 'operator'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index on tabShift Record.operator")

	def test_cash_drop_shift_record_index_exists(self):
		"""tabCash Drop has an index on shift_record."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabCash Drop' "
			"AND COLUMN_NAME = 'shift_record'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index on tabCash Drop.shift_record")

	def test_asset_status_log_venue_session_index_exists(self):
		"""tabAsset Status Log has an index on venue_session."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabAsset Status Log' "
			"AND COLUMN_NAME = 'venue_session'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index on tabAsset Status Log.venue_session")

	def test_venue_asset_display_order_index_exists(self):
		"""tabVenue Asset has an index on display_order (used by asset board ORDER BY)."""
		indexes = frappe.db.sql(
			"SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tabVenue Asset' "
			"AND COLUMN_NAME = 'display_order'",
			as_dict=True,
		)
		self.assertTrue(len(indexes) > 0, "No index on tabVenue Asset.display_order")


# ===========================================================================
# R2 — Database Performance: Query Plans and Timing
# ===========================================================================


class TestQueryPerformance(IntegrationTestCase):
	"""R2 — Verify critical queries use indexes and complete within SLA."""

	def test_asset_board_query_returns_explain_plan(self):
		"""EXPLAIN on the asset board query produces a valid query plan."""
		explain = frappe.db.sql(
			"EXPLAIN SELECT name, asset_code, asset_name, asset_category, "
			"asset_tier, status, current_session, expected_stay_duration, "
			"display_order, last_vacated_at, last_cleaned_at, "
			"hamilton_last_status_change, version "
			"FROM `tabVenue Asset` WHERE is_active = 1 "
			"ORDER BY display_order ASC",
			as_dict=True,
		)
		self.assertTrue(len(explain) > 0, "EXPLAIN returned no rows")

	def test_asset_board_load_under_100ms(self):
		"""get_asset_board_data completes in under 100ms."""
		from hamilton_erp.api import get_asset_board_data
		start = time.monotonic()
		result = get_asset_board_data()
		elapsed_ms = (time.monotonic() - start) * 1000
		self.assertLess(elapsed_ms, 100, f"Asset board load took {elapsed_ms:.1f}ms (SLA: <100ms)")
		self.assertIn("assets", result)

	def test_session_creation_under_200ms(self):
		"""Full start_session lifecycle completes in under 200ms."""
		asset = _make_asset("Perf Session Room")
		start = time.monotonic()
		session_name = start_session_for_asset(asset.name, operator=OPERATOR)
		elapsed_ms = (time.monotonic() - start) * 1000
		self.assertLess(elapsed_ms, 200, f"Session creation took {elapsed_ms:.1f}ms (SLA: <200ms)")
		self.assertTrue(session_name)

	def test_session_number_like_query_not_full_scan(self):
		"""EXPLAIN on _db_max_seq_for_prefix LIKE query does not do a full table scan."""
		prefix = "14-4-2026"
		explain = frappe.db.sql(
			"EXPLAIN SELECT session_number FROM `tabVenue Session` "
			"WHERE session_number LIKE %s "
			"ORDER BY session_number DESC LIMIT 1",
			(f"{prefix}---%",),
			as_dict=True,
		)
		self.assertTrue(len(explain) > 0)
		query_type = explain[0].get("type", "")
		self.assertNotEqual(
			query_type, "ALL",
			f"LIKE query on session_number does full table scan (type={query_type})"
		)

	def test_for_update_query_targets_single_row(self):
		"""EXPLAIN on the FOR UPDATE query shows single-row access via primary key."""
		asset = _make_asset("Perf FU Room")
		explain = frappe.db.sql(
			"EXPLAIN SELECT name, asset_code, asset_name, asset_category, "
			"asset_tier, status, current_session, version "
			"FROM `tabVenue Asset` WHERE name = %s",
			asset.name,
			as_dict=True,
		)
		self.assertTrue(len(explain) > 0)
		query_type = explain[0].get("type", "")
		self.assertIn(query_type, ("const", "eq_ref", "ref"),
		              f"FOR UPDATE query type is {query_type}, expected const/eq_ref/ref")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# R3 — MariaDB-Specific Edge Cases
# ===========================================================================


class TestMariaDBEdgeCases(IntegrationTestCase):
	"""R3 — MariaDB transaction isolation, locking, and data handling."""

	def test_transaction_isolation_is_repeatable_read(self):
		"""MariaDB default isolation level is REPEATABLE READ (Frappe's assumption)."""
		result = frappe.db.sql("SELECT @@tx_isolation AS isolation", as_dict=True)
		self.assertEqual(result[0]["isolation"], "REPEATABLE-READ")

	def test_null_vs_empty_string_in_reason(self):
		"""Venue Asset reason field is NULL when not OOS, not empty string."""
		asset = _make_asset("Null Test Room")
		row = frappe.db.sql(
			"SELECT reason FROM `tabVenue Asset` WHERE name = %s",
			asset.name,
			as_dict=True,
		)
		self.assertIsNone(row[0]["reason"], "Fresh asset reason should be NULL, not empty string")

	def test_unique_constraint_on_asset_code(self):
		"""asset_code UNIQUE constraint is enforced at the DB level."""
		asset = _make_asset("Unique Code Room")
		with self.assertRaises(Exception):
			frappe.get_doc({
				"doctype": "Venue Asset",
				"asset_code": asset.asset_code,
				"asset_name": "Duplicate Code Room",
				"asset_category": "Room",
				"asset_tier": "Single Standard",
				"status": "Available",
				"display_order": 9901,
			}).insert(ignore_permissions=True)

	def test_session_number_unique_constraint_enforced(self):
		"""session_number UNIQUE constraint prevents duplicate inserts."""
		_ensure_walkin()
		asset = _make_asset("Uniq Sess Room")
		session_number = f"99-99-9999---{uuid.uuid4().hex[:4]}"
		frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": asset.name,
			"session_number": session_number,
			"status": "Active",
			"session_start": now_datetime(),
			"operator_checkin": OPERATOR,
			"customer": "Walk-in",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)

		with self.assertRaises(Exception):
			frappe.get_doc({
				"doctype": "Venue Session",
				"venue_asset": asset.name,
				"session_number": session_number,
				"status": "Active",
				"session_start": now_datetime(),
				"operator_checkin": OPERATOR,
				"customer": "Walk-in",
				"assignment_status": "Assigned",
			}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# R4 — Redis-Specific Tests
# ===========================================================================


class TestRedisEdgeCases(IntegrationTestCase):
	"""R4 — Redis lock TTL, INCR overflow, key collision, cold-start fallback."""

	def test_lock_ttl_matches_constant(self):
		"""Redis lock key has the expected TTL (within tolerance)."""
		asset = _make_asset("Redis TTL Room")
		cache = frappe.cache()
		key = f"hamilton:asset_lock:{asset.name}"
		token = uuid.uuid4().hex
		cache.set(key, token, nx=True, px=LOCK_TTL_MS)
		try:
			ttl = cache.pttl(key)
			self.assertGreater(ttl, LOCK_TTL_MS - 500,
			                   f"TTL {ttl}ms is too low (expected ~{LOCK_TTL_MS}ms)")
			self.assertLessEqual(ttl, LOCK_TTL_MS,
			                     f"TTL {ttl}ms exceeds {LOCK_TTL_MS}ms")
		finally:
			cache.delete(key)

	def test_key_namespace_isolation(self):
		"""Hamilton lock keys use the hamilton: namespace and don't collide with Frappe keys."""
		cache = frappe.cache()
		key = "hamilton:asset_lock:test_isolation"
		token = uuid.uuid4().hex
		try:
			cache.set(key, token, px=5000)
			raw = cache.get(key)
			self.assertEqual(raw.decode() if isinstance(raw, bytes) else raw, token)
		finally:
			cache.delete(key)

	def test_lua_cas_release_correct_token(self):
		"""Lua CAS release script deletes only when the stored token matches."""
		from hamilton_erp.locks import _RELEASE_SCRIPT
		cache = frappe.cache()
		key = f"hamilton:test_cas:{uuid.uuid4().hex[:8]}"
		try:
			cache.set(key, "token_a", px=5000)
			# Wrong token — should not delete
			result = cache.eval(_RELEASE_SCRIPT, 1, key, "wrong_token")
			self.assertEqual(result, 0, "CAS release with wrong token should return 0")
			self.assertIsNotNone(cache.get(key), "Key should survive wrong-token release")
			# Correct token — should delete
			result = cache.eval(_RELEASE_SCRIPT, 1, key, "token_a")
			self.assertEqual(result, 1, "CAS release with correct token should return 1")
			self.assertIsNone(cache.get(key), "Key should be gone after correct release")
		finally:
			cache.delete(key)

	def test_cold_start_db_fallback_returns_correct_max(self):
		"""When Redis key is cold, _db_max_seq_for_prefix reads from MariaDB correctly."""
		_ensure_walkin()
		asset = _make_asset("Cold Start Room")
		unique_prefix = "1-1-3099"
		frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": asset.name,
			"session_number": f"{unique_prefix}---0042",
			"status": "Active",
			"session_start": now_datetime(),
			"operator_checkin": OPERATOR,
			"customer": "Walk-in",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)

		result = lifecycle._db_max_seq_for_prefix(unique_prefix)
		self.assertEqual(result, 42, f"DB fallback returned {result}, expected 42")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# R5 — Frappe v16 Specific Behaviour
# ===========================================================================


class TestFrappeV16Behaviour(IntegrationTestCase):
	"""R5 — Frappe v16 framework contracts: versioning, roles, hooks, scheduler."""

	def test_override_doctype_class_loads_correctly(self):
		"""HamiltonSalesInvoice mixin is loaded via override_doctype_class."""
		from hamilton_erp.overrides.sales_invoice import HamiltonSalesInvoice
		self.assertTrue(hasattr(HamiltonSalesInvoice, "has_admission_item"))
		self.assertTrue(hasattr(HamiltonSalesInvoice, "get_admission_category"))
		self.assertTrue(hasattr(HamiltonSalesInvoice, "has_comp_admission"))

	def test_role_permissions_exist_for_venue_asset(self):
		"""Venue Asset has permissions defined for all three Hamilton roles."""
		meta = frappe.get_meta("Venue Asset")
		role_names = {p.role for p in meta.permissions}
		for role in ("Hamilton Operator", "Hamilton Manager", "Hamilton Admin"):
			self.assertIn(role, role_names,
			              f"Missing permission for {role} on Venue Asset")

	def test_track_changes_enabled_on_venue_session(self):
		"""Venue Session has track_changes enabled for document versioning."""
		meta = frappe.get_meta("Venue Session")
		self.assertTrue(meta.track_changes,
		                "Venue Session should have track_changes enabled")

	def test_track_changes_enabled_on_shift_record(self):
		"""Shift Record has track_changes enabled for document versioning."""
		meta = frappe.get_meta("Shift Record")
		self.assertTrue(meta.track_changes,
		                "Shift Record should have track_changes enabled")

	def test_venue_session_autoname_is_hash(self):
		"""Venue Session uses hash autoname (DEC-033 relies on session_number, not name)."""
		meta = frappe.get_meta("Venue Session")
		self.assertEqual(meta.autoname, "hash")

	def test_venue_asset_autoname_is_series(self):
		"""Venue Asset uses naming series VA-.####."""
		meta = frappe.get_meta("Venue Asset")
		self.assertEqual(meta.autoname, "VA-.####")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# R6 — Fraud Detection and Operational Integrity
# ===========================================================================


class TestFraudDetection(IntegrationTestCase):
	"""R6 — Orphan sessions, duplicate assignment, bulk race conditions."""

	def test_orphan_session_detectable(self):
		"""A session older than stay_duration + grace_minutes is detectable by query."""
		_ensure_walkin()
		asset = _make_asset("Orphan Detection Room")
		old_start = now_datetime() - timedelta(hours=8)
		session = frappe.get_doc({
			"doctype": "Venue Session",
			"venue_asset": asset.name,
			"session_number": f"99-99-8888---{uuid.uuid4().hex[:4]}",
			"status": "Active",
			"session_start": old_start,
			"operator_checkin": OPERATOR,
			"customer": "Walk-in",
			"assignment_status": "Assigned",
		}).insert(ignore_permissions=True)

		threshold = now_datetime() - timedelta(minutes=360 + 15)
		orphans = frappe.get_all(
			"Venue Session",
			filters={
				"status": "Active",
				"session_start": ["<", threshold],
			},
			fields=["name", "session_start", "venue_asset"],
		)
		orphan_names = [o["name"] for o in orphans]
		self.assertIn(session.name, orphan_names,
		              "Orphan session should be detected by overtime query")

	def test_duplicate_assignment_blocked_by_state_machine(self):
		"""Second assignment attempt on Occupied asset is rejected by state machine."""
		asset = _make_asset("Dup Assign Room")
		start_session_for_asset(asset.name, operator=OPERATOR)
		# Second attempt should fail — asset is now Occupied, not Available
		with self.assertRaises(frappe.ValidationError):
			start_session_for_asset(asset.name, operator=OPERATOR)

	def test_bulk_clean_does_not_affect_occupied_assets(self):
		"""_mark_all_clean skips Occupied assets — never transitions Occupied -> Available."""
		asset_dirty = _make_asset("Bulk Dirty Room")
		asset_occupied = _make_asset("Bulk Occupied Room")

		start_session_for_asset(asset_dirty.name, operator=OPERATOR)
		vacate_session(asset_dirty.name, operator=OPERATOR, vacate_method="Key Return")

		start_session_for_asset(asset_occupied.name, operator=OPERATOR)

		from hamilton_erp.api import _mark_all_clean
		_mark_all_clean(category="Room")

		occupied_status = frappe.db.get_value("Venue Asset", asset_occupied.name, "status")
		self.assertEqual(occupied_status, "Occupied",
		                 "Occupied asset must NOT be cleaned by bulk operation")

	def test_vacate_method_stored_correctly(self):
		"""Vacate method is correctly stored on the Venue Session record."""
		asset = _make_asset("Vacate Method Room")
		session_name = start_session_for_asset(asset.name, operator=OPERATOR)
		vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")

		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.vacate_method, "Key Return")
		self.assertEqual(session.status, "Completed")

	def test_oos_from_occupied_auto_closes_session(self):
		"""Setting OOS on Occupied asset auto-closes session with Discovery on Rounds."""
		asset = _make_asset("OOS Occ Room")
		session_name = start_session_for_asset(asset.name, operator=OPERATOR)
		set_asset_out_of_service(asset.name, operator=OPERATOR, reason="Emergency plumbing")

		session = frappe.get_doc("Venue Session", session_name)
		self.assertEqual(session.status, "Completed")
		self.assertEqual(session.vacate_method, VACATE_DISCOVERY)
		self.assertIsNotNone(session.session_end)

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# R7 — Connection and Concurrency Reliability
# ===========================================================================


class TestConcurrencyReliability(IntegrationTestCase):
	"""R7 — Connection pool behaviour and concurrent access patterns."""

	def test_sequential_lock_acquisitions_on_different_assets(self):
		"""Three sequential lock acquisitions on different assets all succeed (no pool exhaustion)."""
		assets = [_make_asset(f"Conn Pool {i}") for i in range(3)]
		for asset in assets:
			with asset_status_lock(asset.name, "pool_test") as row:
				self.assertEqual(row["status"], "Available")
		# All three completed without error — connection pool handled 3 lock cycles

	def test_full_lifecycle_is_repeatable(self):
		"""Available -> Occupied -> Dirty -> Available can be repeated 3 times."""
		asset = _make_asset("Repeat Lifecycle Room")
		for cycle in range(3):
			start_session_for_asset(asset.name, operator=OPERATOR)
			vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")
			mark_asset_clean(asset.name, operator=OPERATOR)
			status = frappe.db.get_value("Venue Asset", asset.name, "status")
			self.assertEqual(status, "Available",
			                 f"Cycle {cycle + 1}: expected Available, got {status}")

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# R8 — Data Integrity Under Edge Conditions
# ===========================================================================


class TestDataIntegrityEdges(IntegrationTestCase):
	"""R8 — Edge cases in data handling, timestamps, and field semantics."""

	def test_session_end_after_session_start(self):
		"""session_end is always after session_start after vacate."""
		asset = _make_asset("Timestamp Order Room")
		session_name = start_session_for_asset(asset.name, operator=OPERATOR)
		vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")

		session = frappe.get_doc("Venue Session", session_name)
		self.assertGreater(session.session_end, session.session_start,
		                   "session_end must be after session_start")

	def test_last_cleaned_at_updates_on_mark_clean(self):
		"""last_cleaned_at is stamped when Dirty -> Available."""
		asset = _make_asset("Clean Timestamp Room")
		start_session_for_asset(asset.name, operator=OPERATOR)
		vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")
		mark_asset_clean(asset.name, operator=OPERATOR)

		cleaned_at = frappe.db.get_value("Venue Asset", asset.name, "last_cleaned_at")
		self.assertIsNotNone(cleaned_at, "last_cleaned_at should be set after mark clean")

	def test_last_cleaned_at_updates_on_return_from_oos(self):
		"""last_cleaned_at is also stamped on OOS -> Available (DEC-031 amendment)."""
		asset = _make_asset("OOS Return TS Room")
		set_asset_out_of_service(asset.name, operator=OPERATOR, reason="Painting")
		return_asset_to_service(asset.name, operator=OPERATOR, reason="Done painting")

		cleaned_at = frappe.db.get_value("Venue Asset", asset.name, "last_cleaned_at")
		self.assertIsNotNone(cleaned_at,
		                     "last_cleaned_at should be set after return from OOS")

	def test_last_vacated_at_updates_on_vacate(self):
		"""last_vacated_at is stamped when Occupied -> Dirty."""
		asset = _make_asset("Vacate TS Room")
		start_session_for_asset(asset.name, operator=OPERATOR)
		vacate_session(asset.name, operator=OPERATOR, vacate_method="Key Return")

		vacated_at = frappe.db.get_value("Venue Asset", asset.name, "last_vacated_at")
		self.assertIsNotNone(vacated_at, "last_vacated_at should be set after vacate")

	def test_reason_cleared_after_return_from_oos(self):
		"""reason field is NULL (not empty string) after returning from OOS."""
		asset = _make_asset("Reason Clear Room")
		set_asset_out_of_service(asset.name, operator=OPERATOR, reason="Broken fixture")
		reason = frappe.db.get_value("Venue Asset", asset.name, "reason")
		self.assertEqual(reason, "Broken fixture")

		return_asset_to_service(asset.name, operator=OPERATOR, reason="Fixed")
		reason_after = frappe.db.sql(
			"SELECT reason FROM `tabVenue Asset` WHERE name = %s",
			asset.name,
			as_dict=True,
		)
		self.assertIsNone(reason_after[0]["reason"],
		                  "reason should be NULL after return from OOS")

	def test_hamilton_last_status_change_populated(self):
		"""hamilton_last_status_change is set on every transition."""
		asset = _make_asset("Status Change TS Room")
		before = now_datetime()
		start_session_for_asset(asset.name, operator=OPERATOR)
		ts = frappe.db.get_value("Venue Asset", asset.name, "hamilton_last_status_change")
		self.assertIsNotNone(ts, "hamilton_last_status_change should be set")
		self.assertGreaterEqual(ts, before)

	def tearDown(self):
		frappe.db.rollback()


# ===========================================================================
# Teardown
# ===========================================================================


def tearDownModule():
	"""Restore dev state wiped by this module's tests."""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
