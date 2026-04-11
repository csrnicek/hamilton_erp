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
import ast
import socket
from pathlib import Path

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

	def test_regression_installed_application_is_setup_complete_is_authoritative(self):
		"""Pin the authoritative source of ``frappe.is_setup_complete()``.

		REGRESSION — 2026-04-11: dev site was stuck in an infinite
		``/app/setup-wizard`` redirect loop. The naive fix was to set
		``System Settings.setup_complete`` or write to ``tabDefaultValue``
		with ``key='setup_complete'``. Neither worked. After several
		hours of chasing ghosts, the actual source was found:

		    Frappe v16 reads ``tabInstalled Application.is_setup_complete``
		    for each installed app (``frappe`` and ``erpnext``). If EITHER
		    row has ``is_setup_complete = 0``, ``frappe.is_setup_complete()``
		    returns False and the browser loops on the setup wizard.

		This test locks that contract in place so no future refactor of
		``frappe.is_setup_complete()`` — or a test that resets the wrong
		table — silently reintroduces the loop. It verifies BOTH the
		field name (``is_setup_complete``, not ``setup_complete``) and
		the table (``tabInstalled Application``, not ``tabDefaultValue``
		or ``tabSystem Settings``) are the authoritative location.

		If this test fails, do NOT patch ``System Settings`` or
		``tabDefaultValue``. The fix is:

		    UPDATE `tabInstalled Application`
		       SET is_setup_complete = 1
		     WHERE parent = 'hamilton-test.localhost';
		"""
		# 1. The table must exist.
		self.assertTrue(
			frappe.db.table_exists("Installed Application"),
			"tabInstalled Application does not exist. This is the table "
			"frappe.is_setup_complete() reads; without it the function "
			"returns False unconditionally and the setup-wizard loop "
			"kicks in. Run `bench migrate` to restore it.",
		)

		# 2. frappe.is_setup_complete() in Frappe v16 filters on
		#    app_name IN ('frappe', 'erpnext'). Those exact rows MUST
		#    exist and be is_setup_complete=1. We assert the filter
		#    AND the column name here so a refactor that renames
		#    either one trips this test before the browser does.
		rows = frappe.db.sql(
			"""
			SELECT app_name, is_setup_complete
			  FROM `tabInstalled Application`
			 WHERE app_name IN ('frappe', 'erpnext')
			""",
			as_dict=True,
		)
		found_apps = {r.app_name for r in rows}
		self.assertEqual(
			found_apps, {"frappe", "erpnext"},
			f"tabInstalled Application is missing a row for one of "
			f"('frappe', 'erpnext'). Found: {found_apps}. "
			"frappe.is_setup_complete() (Frappe v16 "
			"__init__.py:1519) filters on exactly these two app_names; "
			"if either is missing the function returns False.",
		)

		incomplete = [r.app_name for r in rows if not r.is_setup_complete]
		self.assertEqual(
			incomplete, [],
			f"tabInstalled Application.is_setup_complete is 0 for: "
			f"{incomplete}. This is the field frappe.is_setup_complete() "
			"reads — NOT System Settings.setup_complete, NOT "
			"tabDefaultValue.setup_complete. Fix with: UPDATE "
			"`tabInstalled Application` SET is_setup_complete = 1 "
			"WHERE app_name IN ('frappe', 'erpnext').",
		)

		# 3. frappe.is_setup_complete() must agree. If it does not, the
		#    function's internals have been refactored and this test
		#    needs to be updated alongside the new source of truth.
		self.assertTrue(
			frappe.is_setup_complete(),
			"tabInstalled Application rows are all is_setup_complete=1 "
			"but frappe.is_setup_complete() returned False. The function's "
			"internals have changed — update this regression test to "
			"match the new authoritative source before proceeding.",
		)

	def test_regression_desktop_home_page_not_setup_wizard(self):
		"""Pin: ``tabDefaultValue.desktop:home_page`` must not equal ``setup-wizard``.

		REGRESSION — 2026-04-11: Asset Board in Chrome flashed/refreshed
		~40 times per second. Every loop iteration: browser loaded
		``/desk``, desk JS read ``frappe.boot.home_page``, found
		``"setup-wizard"``, loaded the setup-wizard page, which ran
		``frappe.pages["setup-wizard"].on_page_load`` — and the first
		thing that handler does is::

		    if (frappe.boot.setup_complete) {
		        window.location.href = frappe.boot.apps_data.default_path || "/desk";
		    }

		So setup-wizard immediately full-page-redirected back to
		``/desk``, which re-read ``home_page=setup-wizard``, and round
		and round. Two Frappe code paths disagreed — one said "your
		home page is setup-wizard" and another said "bounce out of
		setup-wizard when setup is complete" — producing an infinite
		redirect storm.

		The root cause was a stale row in ``tabDefaultValue``::

		    parent   defkey              defvalue
		    __default desktop:home_page   setup-wizard

		This row is written by ERPNext's ``setup_complete()`` flow under
		some conditions and is NEVER cleared by subsequent bootstraps,
		test teardowns, or ``bench migrate``. It survives Redis flushes,
		session deletions, and full bench restarts — because it's just
		a MariaDB row. ``frappe/boot.py:add_home_page()`` reads this
		exact default to build ``bootinfo.home_page``.

		The contract pinned here: IF ``frappe.is_setup_complete()`` is
		True THEN no row in ``tabDefaultValue`` may have
		``defkey='desktop:home_page' AND defvalue='setup-wizard'``. The
		two conditions cannot coexist without reproducing the flash loop.

		If this test fails, the fix is::

		    DELETE FROM `tabDefaultValue`
		     WHERE defkey='desktop:home_page' AND defvalue='setup-wizard';

		Do NOT paper over it by clearing Redis or deleting sessions —
		those are symptoms; the MariaDB row is the cause.
		"""
		if not frappe.is_setup_complete():
			# Setup hasn't completed yet, so the setup-wizard home_page
			# is legitimate. The loop only triggers once setup_complete
			# flips True — which is what the OTHER regression test above
			# verifies must be the case on a dev site.
			self.skipTest(
				"frappe.is_setup_complete() is False — the bad home_page "
				"row is not a loop trigger in that state. The "
				"is_setup_complete regression test covers the other half."
			)

		bad_rows = frappe.db.sql(
			"""
			SELECT parent, defkey, defvalue
			  FROM `tabDefaultValue`
			 WHERE defkey = 'desktop:home_page'
			   AND defvalue = 'setup-wizard'
			""",
			as_dict=True,
		)
		self.assertEqual(
			bad_rows, [],
			f"tabDefaultValue has {len(bad_rows)} row(s) setting "
			f"desktop:home_page='setup-wizard' while "
			"frappe.is_setup_complete() is True. This is the 2026-04-11 "
			"Asset Board flash-loop regression. frappe/boot.py:"
			"add_home_page() will embed this value in bootinfo.home_page, "
			"pageview.show() will load the setup-wizard page as the desk "
			"home, and setup_wizard.js:34 will window.location.href back "
			"to /desk — infinite loop. Fix: DELETE FROM `tabDefaultValue` "
			"WHERE defkey='desktop:home_page' AND defvalue='setup-wizard'. "
			f"Offending rows: {bad_rows}"
		)

	def test_all_redis_keys_use_hamilton_namespace(self):
		"""Every Redis key written by hamilton_erp must start with ``hamilton:``.

		Frappe's redis instances are shared between apps (cache on 13000,
		queue on 11000). If hamilton_erp writes to a bare key like
		``asset_lock:RM-101`` it can collide with any other app that does
		the same — and worse, ``frappe.cache().delete_keys("asset_lock*")``
		in another app would silently wipe our locks.

		This test walks every production .py file in hamilton_erp and
		finds ``cache.set/get/delete/incr/set_value/get_value/delete_value``
		calls. For each call, it extracts the string literal backing the
		first argument (resolving simple local-variable assignments) and
		asserts it starts with ``hamilton:``.

		Keys we expect to find:
		  - ``hamilton:asset_lock:{asset_name}`` (locks.py)
		  - ``hamilton:session_seq:{prefix}`` (lifecycle.py)

		If you add a new Redis key, prefix it with ``hamilton:``. If this
		test starts failing on a new key, don't suppress it — prefix the key.
		"""
		# Frappe's cache API calls we care about. Any AST call where the
		# function attribute is in this set is a candidate.
		CACHE_METHODS = {
			"set", "get", "delete",
			"set_value", "get_value", "delete_value",
			"incr", "incrby", "decr",
			"hset", "hget", "hdel",
			"expire", "ttl",
			"sadd", "srem", "smembers",
			"lpush", "rpush", "lpop", "rpop", "lrange",
			"setex",
		}
		# Only flag calls where the receiver chain contains ``cache(``
		# or a name bound to ``frappe.cache()``. Matching any method
		# named ``set`` would hit dict/set operations everywhere.
		CACHE_RECEIVER_HINTS = ("cache", "redis")

		def _receiver_chain_str(node: ast.AST) -> str:
			"""Best-effort textual dump of a receiver expression."""
			if isinstance(node, ast.Name):
				return node.id
			if isinstance(node, ast.Attribute):
				return f"{_receiver_chain_str(node.value)}.{node.attr}"
			if isinstance(node, ast.Call):
				return f"{_receiver_chain_str(node.func)}()"
			return ""

		def _resolve_key_literal(arg: ast.AST, func_body: list) -> str | None:
			"""Return the string literal backing ``arg``, if determinable.

			Handles:
			  - Plain Constant string
			  - JoinedStr (f-string) where the first segment is a Constant
			    (``f"hamilton:asset_lock:{name}"`` → ``hamilton:asset_lock:``)
			  - Name bound via simple assignment earlier in the function
			    to one of the above
			"""
			if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
				return arg.value
			if isinstance(arg, ast.JoinedStr):
				first = arg.values[0] if arg.values else None
				if isinstance(first, ast.Constant) and isinstance(first.value, str):
					return first.value
				return None
			if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
				# ``"hamilton:" + name`` — look at left side.
				return _resolve_key_literal(arg.left, func_body)
			if isinstance(arg, ast.Name):
				# Walk back through the function body for an assignment.
				for stmt in func_body:
					if isinstance(stmt, ast.Assign):
						for tgt in stmt.targets:
							if isinstance(tgt, ast.Name) and tgt.id == arg.id:
								return _resolve_key_literal(stmt.value, func_body)
			return None

		package_root = Path(__file__).resolve().parent
		violations: list[str] = []
		# Track that we actually found SOMETHING to audit; if the walker
		# matches zero calls across the whole package, the matcher is
		# broken and we'd silently pass.
		scanned_calls = 0

		for py_file in package_root.rglob("*.py"):
			if "__pycache__" in py_file.parts:
				continue
			if py_file.name.startswith("test_"):
				continue
			if py_file.name == "test_environment_health.py":
				continue
			try:
				tree = ast.parse(py_file.read_text(), filename=str(py_file))
			except SyntaxError:
				continue

			# Walk every FunctionDef so we can resolve local-var key refs.
			for func in ast.walk(tree):
				if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
					continue
				for node in ast.walk(func):
					if not isinstance(node, ast.Call):
						continue
					if not isinstance(node.func, ast.Attribute):
						continue
					if node.func.attr not in CACHE_METHODS:
						continue
					receiver = _receiver_chain_str(node.func.value)
					if not any(hint in receiver for hint in CACHE_RECEIVER_HINTS):
						continue
					if not node.args:
						continue

					scanned_calls += 1
					key_literal = _resolve_key_literal(node.args[0], func.body)
					if key_literal is None:
						# Couldn't resolve — be strict and flag, since an
						# un-inspectable key could be a bare non-prefixed
						# string at runtime.
						rel = py_file.relative_to(package_root)
						violations.append(
							f"{rel}:{node.lineno}: {receiver}.{node.func.attr}(...) "
							f"— could not statically resolve key literal. "
							f"Assign the key to a local var with a Constant or "
							f"f-string whose first segment starts with 'hamilton:'."
						)
						continue
					if not key_literal.startswith("hamilton:"):
						rel = py_file.relative_to(package_root)
						violations.append(
							f"{rel}:{node.lineno}: {receiver}.{node.func.attr}(...) "
							f"uses bare key '{key_literal}' — must start with "
							f"'hamilton:' to avoid collisions with other apps "
							f"sharing the redis instance."
						)

		self.assertGreater(
			scanned_calls, 0,
			"Redis namespace scanner found zero cache calls in hamilton_erp/ — "
			"the AST matcher is broken (it should have found at least the "
			"asset_lock key in locks.py and the session_seq key in lifecycle.py). "
			"Fix the scanner before trusting this test.",
		)
		self.assertEqual(
			violations, [],
			"Redis keys without 'hamilton:' namespace prefix:\n  "
			+ "\n  ".join(violations),
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
