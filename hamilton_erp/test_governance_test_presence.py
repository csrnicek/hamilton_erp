"""Presence guard for canonical mockup governance tests.

This test exists because a single test file is a single point of failure.
A future careless or malicious session could delete
test_canonical_mockup_governance.py to bypass the governance regime.

This test file asserts:
1. The governance test file exists
2. It contains all expected test method names

If this test fails, the governance regime has been weakened. Either:
(a) The deletion was intentional — explain why in the commit message and
    update this presence guard accordingly
(b) The deletion was accidental — revert the deletion

This is not a perfect protection (a determined session could delete BOTH
files), but it raises friction and prevents accidental deletion or
incomplete refactors.

Stronger future protections (deferred):
  - CODEOWNERS protection for governance files
  - Required human review for governance file changes
  - Policy that governance tests cannot be changed in the same PR as the
    canonical mockup itself
"""
import ast
import os

import frappe
from frappe.tests import IntegrationTestCase


def _hamilton_erp_root():
	return frappe.get_app_path("hamilton_erp", "..")


class TestGovernanceTestPresence(IntegrationTestCase):

	GOVERNANCE_TEST_PATH = "hamilton_erp/test_canonical_mockup_governance.py"

	EXPECTED_TEST_METHODS = [
		"test_exactly_one_canonical_mockup_exists",
		"test_v9_canonical_mockup_present",
		"test_no_stale_mockup_filenames_in_design_dir",
		"test_canonical_mockup_has_gospel_block",
		"test_canonical_mockup_body_fingerprint_matches_manifest",
	]

	def test_governance_test_file_exists(self):
		"""The governance test file must not be deleted."""
		path = os.path.join(_hamilton_erp_root(), self.GOVERNANCE_TEST_PATH)
		self.assertTrue(
			os.path.isfile(path),
			f"Governance test file missing: {self.GOVERNANCE_TEST_PATH}. "
			f"This file is the primary enforcement of the V9 canonical "
			f"mockup governance regime (per PR #16). It must not be "
			f"deleted. If it needs to be renamed or restructured, update "
			f"GOVERNANCE_TEST_PATH in this file accordingly.",
		)

	def test_governance_test_methods_all_present(self):
		"""Every expected governance test method must exist in the file."""
		path = os.path.join(_hamilton_erp_root(), self.GOVERNANCE_TEST_PATH)
		if not os.path.isfile(path):
			self.fail(
				f"Cannot check methods — governance test file missing: "
				f"{self.GOVERNANCE_TEST_PATH}"
			)

		with open(path) as f:
			governance_source = f.read()

		for method_name in self.EXPECTED_TEST_METHODS:
			self.assertIn(
				f"def {method_name}(", governance_source,
				f"Expected governance test method '{method_name}' is "
				f"missing from {self.GOVERNANCE_TEST_PATH}. The governance "
				f"regime requires all listed test methods. If a method has "
				f"been intentionally renamed or removed, update "
				f"EXPECTED_TEST_METHODS in this presence guard accordingly.",
			)

	def test_governance_test_methods_have_assertions(self):
		"""Each governance test method must contain at least one assertion call.

		Closes Probe 4 of the 2026-04-28 adversarial review: a method body
		replaced with `pass` while keeping the method name intact would pass
		the name-only check above but silently do nothing. AST parsing
		confirms the body actually contains an assertion call.
		"""
		path = os.path.join(_hamilton_erp_root(), self.GOVERNANCE_TEST_PATH)
		with open(path) as f:
			tree = ast.parse(f.read())

		ASSERTION_NAMES = {
			"assertEqual", "assertNotEqual",
			"assertTrue", "assertFalse",
			"assertIn", "assertNotIn",
			"assertIsNone", "assertIsNotNone",
			"assertGreater", "assertGreaterEqual",
			"assertLess", "assertLessEqual",
			"assertRaises", "assertRaisesRegex",
			"assertAlmostEqual",
			"fail",
		}

		for node in ast.walk(tree):
			if not isinstance(node, ast.FunctionDef):
				continue
			if node.name not in self.EXPECTED_TEST_METHODS:
				continue

			has_assertion = False
			for sub in ast.walk(node):
				if isinstance(sub, ast.Call):
					func = sub.func
					if isinstance(func, ast.Attribute):
						if func.attr in ASSERTION_NAMES:
							has_assertion = True
							break
				if isinstance(sub, ast.Assert):
					has_assertion = True
					break

			self.assertTrue(
				has_assertion,
				f"\nGovernance test method '{node.name}' contains no\n"
				f"assertion calls. The method body appears to be empty,\n"
				f"`pass`-only, or otherwise non-functional.\n"
				f"\n"
				f"Each governance test must contain at least one assertion\n"
				f"call (e.g., self.assertEqual, self.assertTrue, self.fail).\n"
				f"\n"
				f"To recover:\n"
				f"  1. If the method was intentionally weakened: don't.\n"
				f"     Restore the method body from a known-good commit:\n"
				f"     git checkout {self.GOVERNANCE_TEST_PATH}\n"
				f"  2. If the assertion was renamed or moved: ensure the\n"
				f"     governance test method body contains a call from\n"
				f"     the recognized assertion list.",
			)
