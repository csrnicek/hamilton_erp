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
