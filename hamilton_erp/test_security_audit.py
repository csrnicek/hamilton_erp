"""Static security audit tests for hamilton_erp.

These tests do NOT exercise runtime behavior — they parse source files
and enforce safety invariants that are hard to catch at runtime:

  1. Every ``frappe.db.sql()`` call in the package uses ``%s`` parameter
     substitution, never ``%``, ``.format()``, or f-string interpolation
     of a non-constant value. This blocks SQL injection before code
     review sees it.
  2. Every user-facing value rendered into a tile by
     ``asset_board.js::render_tile`` is passed through
     ``frappe.utils.escape_html`` before being interpolated into the
     HTML template literal. This blocks stored XSS via asset_name,
     asset_code, and status fields.

Why static, not dynamic: a runtime test that injects ``<script>`` into
an asset_name would only catch regressions that happen to break the
specific payload we picked. A source-level audit catches the CLASS
of mistake — any new interpolation without an escape wrapper fails
the test, whether or not an attacker has discovered a payload for it.

These tests are fast (no DB setup, no HTTP) and should be the first
line of defense on every /run-tests invocation.
"""
import ast
import re
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

# Package root — every .py file under this directory is in scope for
# the SQL audit. Resolved at import time so the test is robust to
# different bench layouts.
PACKAGE_ROOT = Path(__file__).resolve().parent

# Asset Board JS lives under the page scaffold, not the package root.
ASSET_BOARD_JS = (
	PACKAGE_ROOT / "hamilton_erp" / "page" / "asset_board" / "asset_board.js"
)


# ---------------------------------------------------------------------------
# SQL injection audit
# ---------------------------------------------------------------------------


def _iter_python_files(root: Path):
	"""Yield every .py file under root, skipping __pycache__, venvs, and
	this audit module itself.

	The audit module is excluded because its docstrings contain *example*
	unsafe patterns (``frappe.db.sql(f"...")``) used to document what the
	test catches. Including itself in the scan would create a false
	positive on every run.
	"""
	for path in root.rglob("*.py"):
		if "__pycache__" in path.parts:
			continue
		if path.name == "test_security_audit.py":
			continue
		yield path


def _sql_call_first_arg(call: ast.Call) -> ast.AST | None:
	"""Return the first positional arg of a ``frappe.db.sql(...)`` call.

	Returns None if the call is not a ``frappe.db.sql`` invocation.
	"""
	f = call.func
	if not isinstance(f, ast.Attribute) or f.attr != "sql":
		return None
	if not isinstance(f.value, ast.Attribute) or f.value.attr != "db":
		return None
	if not isinstance(f.value.value, ast.Name) or f.value.value.id != "frappe":
		return None
	return call.args[0] if call.args else None


def _is_unsafe_sql_literal(node: ast.AST) -> tuple[bool, str]:
	"""Return (is_unsafe, reason) for a ``frappe.db.sql`` first argument.

	Safe forms:
	  - Plain string constant (no interpolation)
	  - Implicit string concatenation of plain constants
	  - f-string whose only interpolations are ``ast.FormattedValue``
	    nodes whose value is itself a Constant (very rare) — treated
	    as unsafe because a Constant-in-FormattedValue has no reason
	    to exist except as placeholder for a swap
	  - BinOp where both sides are constants

	Unsafe forms:
	  - f-string (``JoinedStr``) with any FormattedValue component
	  - ``"... %s ..." % (values,)`` — the ``%`` operator
	  - ``"...".format(...)`` — the str.format method
	  - String concatenation of a constant with a Name
	"""
	# Plain string constant — safe
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return (False, "")

	# f-string with any dynamic component — unsafe
	if isinstance(node, ast.JoinedStr):
		for v in node.values:
			if isinstance(v, ast.FormattedValue):
				return (True, "f-string (JoinedStr) with dynamic interpolation")
		# All-constant JoinedStr (technically not unsafe, but why?)
		return (False, "")

	# ``"...".format(...)`` — unsafe
	if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
		if node.func.attr == "format":
			return (True, "str.format() call on SQL literal")

	# ``"... %s ..." % (...)`` — unsafe (the % operator returns a str here,
	# not a placeholder for parameter substitution)
	if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
		# Only unsafe if the left side is a string constant — ``%s``
		# substitution via the BinOp is interpolation, not parameterization.
		if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
			return (True, "% operator on SQL literal (interpolation, not parameterization)")

	# String + Name concatenation — unsafe
	if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
		def _has_nonconst(n):
			if isinstance(n, ast.Constant):
				return False
			if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
				return _has_nonconst(n.left) or _has_nonconst(n.right)
			return True
		if _has_nonconst(node):
			return (True, "string concatenation with non-constant value")

	# Anything else (a plain Name variable, a Subscript, etc.) — we allow
	# it. Those represent "the SQL text comes from a variable defined
	# elsewhere"; statically proving they are safe is out of scope. The
	# grep below catches the common unsafe patterns directly.
	return (False, "")


class TestSQLInjectionSafety(IntegrationTestCase):
	"""AST-based scan for unsafe SQL interpolation in frappe.db.sql calls."""

	def test_no_frappe_db_sql_uses_string_interpolation(self):
		"""Every frappe.db.sql() first arg must be a plain constant.

		Rationale: parameter substitution (``%s`` with a tuple second
		arg) is the ONLY supported safe path in Frappe. Any dynamic
		construction of the SQL string itself is a code smell and,
		with untrusted input, a SQL injection.
		"""
		violations: list[str] = []
		for py_file in _iter_python_files(PACKAGE_ROOT):
			source = py_file.read_text()
			try:
				tree = ast.parse(source, filename=str(py_file))
			except SyntaxError:
				continue
			for node in ast.walk(tree):
				if not isinstance(node, ast.Call):
					continue
				first = _sql_call_first_arg(node)
				if first is None:
					continue
				unsafe, reason = _is_unsafe_sql_literal(first)
				if unsafe:
					rel = py_file.relative_to(PACKAGE_ROOT)
					violations.append(
						f"{rel}:{node.lineno}: {reason}"
					)
		self.assertEqual(
			violations, [],
			"Unsafe frappe.db.sql interpolation found. Use %s parameter "
			"substitution with a tuple as the second argument. "
			"Violations:\n  " + "\n  ".join(violations),
		)

	def test_regex_catches_obvious_format_string_bugs(self):
		"""Second-line defense: grep-based scan for ``sql(f"..."``.

		The AST-based check above is authoritative, but a simple grep
		catches the same class of bug with a different failure mode —
		if someone writes ``frappe.db.sql(f"DELETE FROM tab{name}")``
		the AST test catches it and so does this one. Redundancy is
		cheap.
		"""
		pattern = re.compile(r"""frappe\.db\.sql\(\s*f['"]""")
		hits: list[str] = []
		for py_file in _iter_python_files(PACKAGE_ROOT):
			source = py_file.read_text()
			for idx, line in enumerate(source.splitlines(), start=1):
				if pattern.search(line):
					rel = py_file.relative_to(PACKAGE_ROOT)
					hits.append(f"{rel}:{idx}: {line.strip()}")
		self.assertEqual(
			hits, [],
			"frappe.db.sql called with an f-string — use %s parameter "
			"substitution instead. Hits:\n  " + "\n  ".join(hits),
		)


# ---------------------------------------------------------------------------
# asset_board.js XSS audit
# ---------------------------------------------------------------------------


class TestAssetBoardXSS(IntegrationTestCase):
	"""Parse asset_board.js and verify render_tile escapes every user value.

	Why parse the JS source: render_tile builds an HTML template literal
	by interpolating asset fields. Any ``${asset.something}`` that is NOT
	wrapped in ``frappe.utils.escape_html(...)`` is a stored-XSS vector —
	if a malicious asset_name ever lands in the DB, the board renders
	it raw.

	The test isolates the ``render_tile`` method's body (everything
	between ``render_tile(asset) {`` and its matching closing brace) and
	checks that every ``${asset.<field>}`` expression for the three
	user-facing fields (asset_name, asset_code, status) is wrapped in
	``frappe.utils.escape_html``.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.assertTrue_static = cls.failureException
		cls.js_source = ASSET_BOARD_JS.read_text()

	def _extract_render_tile_body(self) -> str:
		"""Return the text of the render_tile method body."""
		marker = "render_tile(asset) {"
		start = self.js_source.find(marker)
		self.assertNotEqual(
			start, -1,
			f"Could not locate render_tile in {ASSET_BOARD_JS} — has "
			"the method been renamed or removed?",
		)
		# Brace-match from the opening { after the marker
		body_start = start + len(marker) - 1  # position of the {
		depth = 0
		for i in range(body_start, len(self.js_source)):
			ch = self.js_source[i]
			if ch == "{":
				depth += 1
			elif ch == "}":
				depth -= 1
				if depth == 0:
					return self.js_source[body_start:i + 1]
		self.fail("Unbalanced braces in render_tile body")

	def _extract_html_template(self) -> str:
		"""Return just the ``return `...`;`` HTML template literal.

		This is the portion of render_tile that actually emits HTML.
		Earlier template literals in the function (e.g. the
		``status_class`` assignment, which transforms ``asset.status``
		into a CSS token) are excluded because they do NOT render into
		user-visible HTML — they produce a class name that the browser
		treats as a CSS identifier, not an HTML attribute value.

		JS template literals CAN nest (``${cond ? `<a>${x}</a>` : ""}``),
		so the closing backtick is found by tracking ``${...}`` interp
		depth. When we see ``${`` we increment depth; matching ``}`` at
		depth > 0 decrements. A backtick at interp-depth 0 and template-
		nesting depth 0 is the outer close.
		"""
		body = self._extract_render_tile_body()
		return_idx = body.find("return `")
		self.assertNotEqual(
			return_idx, -1,
			"render_tile has no `return ``...``;` template literal — "
			"did the emit path change?",
		)
		tick_start = body.find("`", return_idx)
		# Stack-based walker. Each entry is either "T" (inside a
		# template literal) or "I" (inside a ${...} interpolation).
		# The outer backtick we just saw opens a T.
		stack = ["T"]
		i = tick_start + 1
		while i < len(body):
			ch = body[i]
			nxt = body[i + 1] if i + 1 < len(body) else ""
			top = stack[-1]
			if top == "T":
				if ch == "`":
					stack.pop()
					if not stack:
						return body[tick_start:i + 1]
					i += 1
					continue
				if ch == "$" and nxt == "{":
					stack.append("I")
					i += 2
					continue
				i += 1
				continue
			# top == "I"
			if ch == "}":
				stack.pop()
				i += 1
				continue
			if ch == "`":
				stack.append("T")
				i += 1
				continue
			i += 1
		self.fail("Unterminated template literal in render_tile return value")

	def test_asset_name_is_escaped_in_render_tile(self):
		html = self._extract_html_template()
		# V6 tiles no longer render asset.asset_name (display name).
		# They DO render asset.name (Frappe doc ID) in data-asset-name.
		# Check that every ${...asset.name...} interpolation is escaped.
		pattern = re.compile(r"\$\{([^}]*asset\.name[^}]*)\}")
		matches = pattern.findall(html)
		self.assertTrue(
			matches,
			"render_tile HTML template does not reference asset.name "
			"at all — did the field get renamed? Update the test or the JS.",
		)
		for expr in matches:
			self.assertIn(
				"frappe.utils.escape_html", expr,
				f"asset.name interpolated without escape_html: "
				f"${{{expr}}} — this is an XSS vector.",
			)

	def test_asset_code_is_escaped_in_render_tile(self):
		html = self._extract_html_template()
		pattern = re.compile(r"\$\{([^}]*asset\.asset_code[^}]*)\}")
		matches = pattern.findall(html)
		self.assertTrue(
			matches,
			"render_tile HTML template does not reference asset.asset_code.",
		)
		for expr in matches:
			self.assertIn(
				"frappe.utils.escape_html", expr,
				f"asset.asset_code interpolated without escape_html: "
				f"${{{expr}}} — this is an XSS vector.",
			)

	def test_status_is_escaped_in_render_tile(self):
		"""asset.status must be escaped wherever it is rendered to HTML.

		Note: the ``status_class`` string is derived from ``asset.status``
		via ``.toLowerCase().replace(/ /g, "-")`` and used as a CSS class
		token. That path is NOT checked by this test because the tokenizer
		transforms the value, the fix is upstream (constrain status at
		the DocType level, which Venue Asset already does via a Select
		field), AND the CSS class assignment happens outside the
		``return \\`...\\`;`` HTML template literal. What this test DOES
		check is every ``${...asset.status...}`` expression inside the
		HTML template — those must be escaped.
		"""
		html = self._extract_html_template()
		pattern = re.compile(r"\$\{([^}]*asset\.status[^}]*)\}")
		matches = pattern.findall(html)
		self.assertTrue(
			matches,
			"render_tile HTML template does not reference asset.status "
			"in any HTML interpolation — did it get removed?",
		)
		for expr in matches:
			self.assertIn(
				"frappe.utils.escape_html", expr,
				f"asset.status interpolated without escape_html: "
				f"${{{expr}}} — this is an XSS vector. Wrap with "
				"frappe.utils.escape_html(asset.status).",
			)


# ───────────────────────────────────────────────────────────────────────
# Task 25 permissions checklist item 5: no Front Desk self-escalation
# ───────────────────────────────────────────────────────────────────────

class TestNoFrontDeskSelfEscalation(IntegrationTestCase):
	"""Hamilton Operator (=Front Desk) must not have permissions that
	would let an operator change their own role or anyone else's.

	Specifically: the Operator role must NOT have write/create/delete
	permission on User, Role, DocPerm, Has Role, or Custom DocPerm.
	If any of these slip in via a future Custom DocPerm fixture or a
	stray PermissionError, this test fails before deploy.

	The check runs at the database level (Custom DocPerm + DocPerm
	tables) rather than via `frappe.permissions.has_permission` because
	we want to catch the static configuration regression — not the
	per-request runtime behavior, which is harder to test in
	IntegrationTestCase.
	"""

	ESCALATION_RISK_DOCTYPES = [
		"User",
		"Role",
		"DocPerm",
		"Custom DocPerm",
		"Has Role",
		"Role Profile",
	]
	FORBIDDEN_FLAGS = ("write", "create", "delete", "submit", "cancel", "amend")

	def test_hamilton_operator_cannot_mutate_escalation_doctypes(self):
		role = "Hamilton Operator"
		for dt in self.ESCALATION_RISK_DOCTYPES:
			for table in ("DocPerm", "Custom DocPerm"):
				rows = frappe.get_all(
					table,
					filters={"parent": dt, "role": role},
					fields=["name"] + list(self.FORBIDDEN_FLAGS),
				)
				for r in rows:
					granted = [f for f in self.FORBIDDEN_FLAGS if r.get(f)]
					self.assertEqual(
						granted, [],
						f"Hamilton Operator has forbidden permission(s) on "
						f"{dt!r} via {table} ({r['name']}): {granted}. "
						"Front Desk operators must not be able to modify "
						"users, roles, or permissions — that's the "
						"self-escalation path Task 25 item 5 guards against.",
					)


# ---------------------------------------------------------------------------
# Field masking audit — gap #1 (Task 25 item 7 / DEC-038)
# ---------------------------------------------------------------------------


import json as _json  # noqa: E402 — avoid shadowing the existing top-level imports

_SHIFT_RECORD_JSON = (
	PACKAGE_ROOT
	/ "hamilton_erp"
	/ "doctype"
	/ "shift_record"
	/ "shift_record.json"
)


class TestShiftRecordBlindRevealGuardrail(IntegrationTestCase):
	"""Field masking audit gap #1 — system_expected_card_total must be
	hidden from Hamilton Operator at the API layer, not just the form.

	Why this exists: ``Shift Record.system_expected_card_total`` is the
	card-mode parallel of ``Cash Reconciliation.system_expected``
	(DEC-021 + DEC-038). Both are blind-reveal theft-detection figures:
	the operator enters their counted total *first*, then the manager
	reviews the system-expected. If the operator can read
	system-expected before they submit their count, the blind-reveal
	invariant is defeated — they can match the figure to hide skims.

	The Cash Reconciliation DocType enforces this structurally: Hamilton
	Operator has *no row-level read* on Cash Reconciliation at all.
	Shift Record cannot use the same approach because operators DO need
	to read their own shift row (it tracks cash drops, comps, etc.) —
	they only need to be blocked from this one field. That's exactly
	what ``permlevel`` is for.

	The fix is two coupled JSON edits:

	  1. Set ``"permlevel": 1`` on the field itself.
	  2. Add a permission row at level 1 for Hamilton Manager and
	     Hamilton Admin (and NOT for Hamilton Operator).

	Either edit alone is broken: edit 1 without edit 2 hides the field
	from everyone (no role has permlevel-1 access); edit 2 without edit
	1 grants permlevel-1 access to a level that has no fields, which
	does nothing. This test asserts both edits are present and
	consistent — if a future contributor reverts either half, the test
	catches the regression before the blind-reveal invariant is broken
	in production.

	Static JSON parse: same philosophy as the rest of this module — we
	read the committed schema file rather than spinning up a DB. A
	runtime test would require a full Shift Record + permlevel seed and
	would only catch regressions that happen to cross the specific
	read path the test exercises. The static check catches the *class*
	of misconfig.
	"""

	BLIND_REVEAL_FIELD = "system_expected_card_total"
	REQUIRED_PERMLEVEL = 1
	# Operator must NOT have permlevel-1 read. Manager and Admin must.
	MUST_HAVE_PERMLEVEL_READ = ("Hamilton Manager", "Hamilton Admin")
	MUST_NOT_HAVE_PERMLEVEL_READ = ("Hamilton Operator",)

	def setUp(self):
		# Parse once per test method — cheap, isolates each assertion.
		self.schema = _json.loads(_SHIFT_RECORD_JSON.read_text())
		self.field = next(
			(f for f in self.schema.get("fields", [])
				if f.get("fieldname") == self.BLIND_REVEAL_FIELD),
			None,
		)
		self.assertIsNotNone(
			self.field,
			f"Field {self.BLIND_REVEAL_FIELD!r} no longer exists on "
			"Shift Record — either it was renamed (update this test) "
			"or removed (revisit DEC-038 first).",
		)

	def test_field_has_permlevel_1(self):
		"""The schema half: the field itself must declare permlevel: 1.

		If this is missing or zero, the field is exposed at level 0
		(default), which means every role with row-level read sees it.
		That includes Hamilton Operator — which is the gap.
		"""
		self.assertEqual(
			self.field.get("permlevel"), self.REQUIRED_PERMLEVEL,
			f"Shift Record.{self.BLIND_REVEAL_FIELD} is missing "
			f"permlevel: {self.REQUIRED_PERMLEVEL}. This field is the "
			"card-mode blind-reveal theft-detection figure (DEC-038, "
			"parallel to DEC-021). Without permlevel, Hamilton "
			"Operator can read system-expected before submitting their "
			"counted figure, defeating the blind-reveal invariant.",
		)

	def test_managers_have_permlevel_1_read(self):
		"""The permissions half: Manager and Admin must hold a
		permlevel-1 read row.

		Without this, the field is invisible to *everyone* — including
		the roles who are supposed to review it at submit. The schema
		half (permlevel on the field) and the permissions half
		(permlevel rows in the perms array) move together; testing one
		without the other lets a half-fix slip in.
		"""
		permlevel_reads = {
			p.get("role")
			for p in self.schema.get("permissions", [])
			if p.get("permlevel") == self.REQUIRED_PERMLEVEL
			and p.get("read")
		}
		missing = [r for r in self.MUST_HAVE_PERMLEVEL_READ
			if r not in permlevel_reads]
		self.assertEqual(
			missing, [],
			f"Shift Record permission grid is missing permlevel-"
			f"{self.REQUIRED_PERMLEVEL} read rows for {missing}. "
			"Without these, the blind-reveal field is hidden from "
			"the very roles that need to review it. Add a "
			'permission row {"permlevel": '
			f'{self.REQUIRED_PERMLEVEL}, "read": 1, "role": '
			'<role>} for each missing role.',
		)

	def test_operator_does_not_have_permlevel_1_read(self):
		"""The negative case: Hamilton Operator must NOT have
		permlevel-1 read.

		This is the actual security invariant. The two tests above
		assert the structure is *present* and *correct shape*. This
		one asserts the structure is *not granting access to the
		wrong role*. A future fixture that adds Operator at level 1
		(by accident or by misunderstanding the DEC-038 design) is
		caught here before merge.
		"""
		offenders = [
			p for p in self.schema.get("permissions", [])
			if p.get("permlevel") == self.REQUIRED_PERMLEVEL
			and p.get("read")
			and p.get("role") in self.MUST_NOT_HAVE_PERMLEVEL_READ
		]
		self.assertEqual(
			offenders, [],
			f"Shift Record grants permlevel-{self.REQUIRED_PERMLEVEL} "
			"read to a role that must not have it: "
			f"{[p.get('role') for p in offenders]}. The "
			f"{self.BLIND_REVEAL_FIELD} field is a blind-reveal "
			"theft-detection figure (DEC-038); only Manager+ may "
			"see it before the operator submits their counted "
			"total. Remove the offending permlevel row.",
		)


# ---------------------------------------------------------------------------
# T1-3 — Hamilton Operator runtime read on the Asset Board
# ---------------------------------------------------------------------------


class TestAssetBoardOperatorReadAccess(IntegrationTestCase):
	"""T1-3 (per docs/inbox/2026-05-04_audit_synthesis_decisions.md).

	The synthesis claimed Hamilton Operator hits 403 when calling
	``hamilton_erp.api.get_asset_board_data`` because that function reads
	Hamilton Settings via ``frappe.get_cached_doc("Hamilton Settings")``
	(api.py:241-256), and Hamilton Operator has no permission row on
	Hamilton Settings.

	Two outcomes are possible at runtime:

	(a) ``get_cached_doc`` returns the cached singleton without re-checking
	    perms on cache hit. Operator gets the data, no 403. The synthesis's
	    403 claim is theoretical; the bug is invisible in practice.

	(b) ``get_cached_doc`` checks perms on every call. Operator gets
	    PermissionError on every Asset Board load. Production blocker.

	**This test resolves the question by exercising the runtime path.**

	If this test PASSES: T1-3 closes as a no-issue (case (a) is reality).
	No follow-up PR is needed.

	If this test FAILS with PermissionError: T1-3 is confirmed real.
	The follow-up fix is to grant Hamilton Operator ``read`` on
	Hamilton Settings (one JSON change to hamilton_settings.json,
	bench-migrate-required, schedule into the Phase 3 migrate window).
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.operator_email = "asset-board-operator-read-test@example.com"
		if not frappe.db.exists("User", cls.operator_email):
			frappe.get_doc({
				"doctype": "User",
				"email": cls.operator_email,
				"first_name": "AssetBoardOpTest",
				"send_welcome_email": 0,
				"enabled": 1,
				"roles": [{"role": "Hamilton Operator"}],
			}).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		email = getattr(cls, "operator_email", None)
		if email and frappe.db.exists("User", email):
			frappe.delete_doc("User", email, ignore_permissions=True, force=True)
		super().tearDownClass()

	def setUp(self):
		frappe.clear_cache()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.clear_cache()

	def test_hamilton_operator_can_load_asset_board_data(self):
		"""Hamilton-Operator-only User must be able to call
		``hamilton_erp.api.get_asset_board_data`` without PermissionError.

		If this fails with PermissionError on Hamilton Settings: T1-3
		confirmed real; schedule the JSON-perm follow-up fix per the
		decisions doc (Phase 3 migrate window).
		"""
		from hamilton_erp.api import get_asset_board_data

		frappe.set_user(self.operator_email)
		try:
			result = get_asset_board_data()
		except frappe.PermissionError as exc:
			self.fail(
				"Hamilton Operator hit PermissionError loading Asset Board: "
				f"{exc}\n\n"
				"T1-3 in docs/inbox/2026-05-04_audit_synthesis_decisions.md "
				"is now confirmed. Follow-up fix: grant Hamilton Operator "
				"\"read\" on Hamilton Settings via the permissions array in "
				"hamilton_settings.json. Schedule into the Phase 3 "
				"bench-migrate window."
			)

		self.assertIn(
			"settings", result,
			f"get_asset_board_data response missing 'settings' key: {list(result.keys())}",
		)
		self.assertIn(
			"grace_minutes", result["settings"],
			f"settings payload missing 'grace_minutes': {result['settings']}",
		)


# ---------------------------------------------------------------------------
# Field masking audit — gap #2 (Task 25 item 7 / Comp Admission Log.comp_value)
# ---------------------------------------------------------------------------


_COMP_ADMISSION_LOG_JSON = (
	PACKAGE_ROOT
	/ "hamilton_erp"
	/ "doctype"
	/ "comp_admission_log"
	/ "comp_admission_log.json"
)


class TestCompAdmissionLogValueMasking(IntegrationTestCase):
	"""Field masking audit gap #2 — comp_value must be hidden from
	Hamilton Operator at the API layer.

	Why this exists: ``Comp Admission Log.comp_value`` is the notional
	revenue cost of a comp ("if I gave this away, what was it worth?").
	Per ``docs/permissions_matrix.md`` "Sensitive fields" section, this
	field is Hamilton Manager+ only — exposing it to Operators creates
	a margin-leak signal (peers can see what each comp cost) AND a
	self-justification path for inflated comps (operator sees value,
	knows what to write to look reasonable).

	Same shape as ``TestShiftRecordBlindRevealGuardrail`` (gap #1):
	two coupled JSON edits (``permlevel: 1`` on the field + Manager/
	Admin permlevel-1 read rows in the perm grid) must move together.
	Either edit alone is broken; this test asserts both are present
	and consistent.

	Phase 2 wiring contract (also documented in the field's
	``description``): code creating Comp Admission Log records must
	run with permlevel:1 write access (e.g. ``ignore_permissions=True``
	under Administrator elevation), or ``comp_value`` silently lands
	as ``None`` because the Operator-role context can't write the
	masked field. The cart's ``submit_retail_sale`` is the reference
	pattern.

	Static JSON parse — same philosophy as
	``TestShiftRecordBlindRevealGuardrail``. We read the committed
	schema rather than spinning up a DB; a runtime test would only
	catch regressions on a specific read path. The static check
	catches the *class* of misconfig.
	"""

	MASKED_FIELD = "comp_value"
	REQUIRED_PERMLEVEL = 1
	# Operator must NOT have permlevel-1 read. Manager and Admin must.
	MUST_HAVE_PERMLEVEL_READ = ("Hamilton Manager", "Hamilton Admin")
	MUST_NOT_HAVE_PERMLEVEL_READ = ("Hamilton Operator",)

	def setUp(self):
		self.schema = _json.loads(_COMP_ADMISSION_LOG_JSON.read_text())
		self.field = next(
			(f for f in self.schema.get("fields", [])
				if f.get("fieldname") == self.MASKED_FIELD),
			None,
		)
		self.assertIsNotNone(
			self.field,
			f"Field {self.MASKED_FIELD!r} no longer exists on "
			"Comp Admission Log — either it was renamed (update this "
			"test) or removed (revisit the field-masking audit first).",
		)

	def test_field_has_permlevel_1(self):
		"""The schema half: the field itself must declare permlevel: 1."""
		self.assertEqual(
			self.field.get("permlevel"), self.REQUIRED_PERMLEVEL,
			f"Comp Admission Log.{self.MASKED_FIELD} is missing "
			f"permlevel: {self.REQUIRED_PERMLEVEL}. Without permlevel, "
			"every Hamilton Operator with row-level read sees the "
			"comp's notional revenue cost — margin leak + "
			"self-justification path for inflated comps.",
		)

	def test_managers_have_permlevel_1_read(self):
		"""The permissions half: Manager and Admin must hold a
		permlevel-1 read row.

		Without this, the field is invisible to *everyone* — including
		the roles authorized to review it. The schema half (permlevel
		on the field) and the permissions half (permlevel rows in the
		perms array) move together; testing one without the other lets
		a half-fix slip in.
		"""
		permlevel_reads = {
			p.get("role")
			for p in self.schema.get("permissions", [])
			if p.get("permlevel") == self.REQUIRED_PERMLEVEL
			and p.get("read")
		}
		missing = [r for r in self.MUST_HAVE_PERMLEVEL_READ
			if r not in permlevel_reads]
		self.assertEqual(
			missing, [],
			f"Comp Admission Log permission grid is missing "
			f"permlevel-{self.REQUIRED_PERMLEVEL} read rows for "
			f"{missing}. Without these, comp_value is invisible to "
			"the very roles authorized to review it. Add a permission "
			'row {"permlevel": '
			f'{self.REQUIRED_PERMLEVEL}, "read": 1, "role": '
			'<role>} for each missing role.',
		)

	def test_operator_does_not_have_permlevel_1_read(self):
		"""The negative case: Hamilton Operator must NOT have
		permlevel-1 read.

		This is the actual security invariant — the field-masking
		audit gap #2's whole point. A future fixture that adds Operator
		at level 1 (by accident or misunderstanding the design) is
		caught here before merge.
		"""
		offenders = [
			p for p in self.schema.get("permissions", [])
			if p.get("permlevel") == self.REQUIRED_PERMLEVEL
			and p.get("read")
			and p.get("role") in self.MUST_NOT_HAVE_PERMLEVEL_READ
		]
		self.assertEqual(
			offenders, [],
			f"Comp Admission Log grants permlevel-"
			f"{self.REQUIRED_PERMLEVEL} read to a role that must not "
			f"have it: {[p.get('role') for p in offenders]}. "
			f"comp_value is the field-masking audit gap #2 — Manager+ "
			"only. Remove the offending permlevel row.",
		)


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	This module is read-only (parses source files), so nothing should
	need restoring. We call restore_dev_state() anyway to stay
	consistent with every other test module.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
