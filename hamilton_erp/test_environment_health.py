"""Environment health smoke tests for Hamilton ERP.

This module is the canary for dev-site regressions. Every test here
catches a class of failure that has bitten Chris in the past and is
not covered by the behavioral test modules:

  - setup_wizard redirect loop (tabInstalled Application.is_setup_complete
    silently flipping back to 0 after bench migrate or test runs)
  - Administrator losing the Hamilton Operator role (tests wipe User roles)
  - Seed data being wiped without being re-seeded (empty Asset Board)
  - Walk-in Customer missing (blocks start_session on anonymous guests)
  - get_asset_board_data returning 403 to Administrator (permission or
    Hamilton Settings access regression)
  - Bench serving the setup-wizard instead of the login page (the
    definitive observable symptom of the is_setup_complete=0 bug)
  - Redis cache (13000) or queue (11000) not reachable — Frappe can
    boot but sessions and background jobs silently break

Tests that require the bench webserver running (HTTP probes) skip
gracefully when port 8000 is unreachable, so ``bench run-tests``
does not fail on a cold machine. The redis tests use a low-level
socket connect rather than the frappe cache wrapper so a misconfigured
connection pool is surfaced as a test failure, not a framework error.
"""
import socket

import frappe
import requests
from frappe.tests import IntegrationTestCase

from hamilton_erp import api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BENCH_HOST = "127.0.0.1"
BENCH_PORT = 8000
REDIS_CACHE_PORT = 13000
REDIS_QUEUE_PORT = 11000


def _bench_is_up() -> bool:
	"""Return True if something is listening on the bench webserver port.

	Used by the HTTP probe test to skip gracefully when bench is not
	running (e.g. during CI or a cold dev laptop). The test is a smoke
	check — we want it to fail LOUDLY when bench is up and serving the
	wrong thing, and SILENTLY skip when bench is off.
	"""
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.settimeout(0.5)
		try:
			sock.connect((BENCH_HOST, BENCH_PORT))
			return True
		except (ConnectionRefusedError, socket.timeout, OSError):
			return False


def _redis_ping(port: int) -> bool:
	"""Low-level PING to a Redis port. Returns True on +PONG.

	Bypasses ``frappe.cache()`` because a misconfigured pool would
	return True for cache but hide a broken queue (or vice versa).
	We want each port tested independently.
	"""
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.settimeout(1.0)
		try:
			sock.connect((BENCH_HOST, port))
			sock.sendall(b"PING\r\n")
			reply = sock.recv(64)
			return reply.startswith(b"+PONG")
		except (ConnectionRefusedError, socket.timeout, OSError):
			return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnvironmentHealth(IntegrationTestCase):
	"""Read-only smoke tests. No setUp/tearDown state mutation."""

	def test_setup_wizard_gate_is_open(self):
		"""frappe.is_setup_complete() must return True on a dev site.

		This reads from tabInstalled Application.is_setup_complete for
		both 'frappe' and 'erpnext'. If either is 0, the dev browser
		falls into the setup_wizard redirect loop on next page load.
		"""
		self.assertTrue(
			frappe.is_setup_complete(),
			"frappe.is_setup_complete() returned False — dev browser "
			"will loop on /app/setup-wizard. Run the after_migrate "
			"ensure_setup_complete() hook or restore_dev_state().",
		)

	def test_administrator_has_hamilton_operator_role(self):
		"""Administrator needs Hamilton Operator to access the Asset Board.

		The custom ``asset-board`` Frappe Page and every whitelisted
		endpoint in ``hamilton_erp.api`` require this role. Tests that
		wipe the User table strip it, and restore_dev_state() re-adds it.
		"""
		admin_roles = {
			r.role for r in frappe.get_doc("User", "Administrator").roles
		}
		self.assertIn(
			"Hamilton Operator", admin_roles,
			"Administrator is missing the Hamilton Operator role — "
			"Asset Board will 403. Run restore_dev_state().",
		)

	def test_59_assets_exist(self):
		"""Exactly 59 Venue Assets (26 rooms + 33 lockers) per DEC-054 §1.

		If this fails, a test wiped the asset table without running
		``seed_hamilton_env.execute()`` in its tearDownClass. The
		Asset Board will render an empty grid until the seed is replayed.
		"""
		count = frappe.db.count("Venue Asset")
		self.assertEqual(
			count, 59,
			f"Expected 59 Venue Assets, found {count}. "
			"Seed was wiped and not restored — run seed_hamilton_env.execute().",
		)

	def test_asset_board_api_accessible_as_administrator(self):
		"""get_asset_board_data() must return 59 assets for Administrator.

		Regression test for the 403 we hit during Task 17.2 where the
		browser session had a stale role list in Redis. Calls the API
		directly rather than via HTTP so the test passes even when
		bench is not serving (Python path only).
		"""
		original_user = frappe.session.user
		try:
			frappe.set_user("Administrator")
			data = api.get_asset_board_data()
		finally:
			frappe.set_user(original_user)
		self.assertEqual(
			len(data["assets"]), 59,
			f"get_asset_board_data() returned {len(data['assets'])} "
			"assets, expected 59.",
		)
		self.assertIn(
			"settings", data,
			"get_asset_board_data() did not return the 'settings' key — "
			"Hamilton Settings read may have failed silently.",
		)

	def test_bench_serves_login_not_wizard(self):
		"""HTTP probe: /app must redirect to /login, NOT /app/setup-wizard.

		This is the definitive external symptom of the is_setup_complete=0
		bug. Skips silently when bench is not running so ``bench run-tests``
		on a cold machine does not fail; fails loudly when bench IS up
		and serving the wrong redirect.
		"""
		if not _bench_is_up():
			self.skipTest(
				f"bench not listening on {BENCH_HOST}:{BENCH_PORT} — "
				"skipping HTTP probe"
			)
		r = requests.get(
			f"http://hamilton-test.localhost:{BENCH_PORT}/app",
			allow_redirects=False,
			timeout=3,
		)
		# Expect a redirect (302/303) to /login. Not /app/setup-wizard.
		location = r.headers.get("Location", "")
		self.assertNotIn(
			"setup-wizard", location,
			f"/app redirected to {location!r} — site is stuck in the "
			"setup_wizard loop. is_setup_complete is 0 somewhere.",
		)

	def test_redis_cache_port_reachable(self):
		"""Redis cache on port 13000 must respond to PING.

		If this fails, ``frappe.cache()`` calls silently return None
		and session roles + form defaults break in non-obvious ways.
		"""
		self.assertTrue(
			_redis_ping(REDIS_CACHE_PORT),
			f"Redis cache on port {REDIS_CACHE_PORT} did not respond to "
			"PING. Start it with: "
			"redis-server ~/frappe-bench-hamilton/config/redis_cache.conf",
		)

	def test_redis_queue_port_reachable(self):
		"""Redis queue on port 11000 must respond to PING.

		If this fails, background jobs (email, scheduled tasks,
		long-running lifecycle operations) queue up but never execute.
		Tests pass, dev browser looks fine — and then nothing happens.
		"""
		self.assertTrue(
			_redis_ping(REDIS_QUEUE_PORT),
			f"Redis queue on port {REDIS_QUEUE_PORT} did not respond to "
			"PING. Start it with: "
			"redis-server ~/frappe-bench-hamilton/config/redis_queue.conf",
		)

	def test_walk_in_customer_exists(self):
		"""The 'Walk-in' Customer must exist per DEC-055 §1.

		Every anonymous session is invoiced against this customer. If
		it is missing, start_session raises LinkValidationError and
		the Asset Board appears broken from the user's perspective.
		"""
		self.assertTrue(
			frappe.db.exists("Customer", "Walk-in"),
			"'Walk-in' Customer is missing from the database. "
			"Run seed_hamilton_env.execute() to re-create it.",
		)


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	This module is read-only, so nothing should actually need
	restoring — but we call restore_dev_state() anyway to stay
	consistent with every other test module (see test_helpers.py
	for why). Idempotent and cheap.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
