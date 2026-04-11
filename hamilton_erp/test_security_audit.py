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
		# Find every ${...asset.asset_name...} interpolation in the HTML
		# template and assert it is wrapped in escape_html.
		pattern = re.compile(r"\$\{([^}]*asset\.asset_name[^}]*)\}")
		matches = pattern.findall(html)
		self.assertTrue(
			matches,
			"render_tile HTML template does not reference asset.asset_name "
			"at all — did the field get renamed? Update the test or the JS.",
		)
		for expr in matches:
			self.assertIn(
				"frappe.utils.escape_html", expr,
				f"asset.asset_name interpolated without escape_html: "
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


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	This module is read-only (parses source files), so nothing should
	need restoring. We call restore_dev_state() anyway to stay
	consistent with every other test module.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
