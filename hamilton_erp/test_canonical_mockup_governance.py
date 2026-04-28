"""Governance tests for V9_CANONICAL_MOCKUP.html and successor canonical files.

Per CLAUDE.md "V9 Canonical Mockup — Gospel Reference" rule 4: only ONE
V*_CANONICAL_MOCKUP.html may exist in docs/design/ at any time. When a
successor is created, the old file MUST be moved to docs/design/archive/.

This test fails if:
- More than one V*_CANONICAL_MOCKUP.html exists in docs/design/
- A bypass-pattern filename (case-variant, suffix-variant) appears in docs/design/
- An old asset_board*.html filename reappears in docs/design/
- The canonical file is missing entirely
- The canonical file's gospel declaration block has been stripped
- The canonical mockup body has been silently edited (fingerprint mismatch)
"""
import hashlib
import json
import os
import re

import frappe
from frappe.tests import IntegrationTestCase


def _hamilton_erp_root():
	"""Resolve the hamilton_erp app root directory."""
	return frappe.get_app_path("hamilton_erp", "..")


def _design_dir():
	"""Resolve docs/design/ inside the hamilton_erp repo (sibling of the app dir)."""
	return os.path.normpath(
		frappe.get_app_path("hamilton_erp", "..", "docs", "design")
	)


class TestCanonicalMockupGovernance(IntegrationTestCase):
	"""Enforces the single-canonical invariant for V*_CANONICAL_MOCKUP.html.

	If a future PR creates V10_CANONICAL_MOCKUP.html without archiving V9,
	these tests fail in CI before the change can ship — preventing the
	"two canonicals coexisting" ambiguity that this whole governance regime
	is built to avoid.
	"""

	def _load_manifest_or_fail(self):
		"""Load the canonical mockup manifest, converting raw Python errors
		(FileNotFoundError, JSONDecodeError, KeyError) into clean assertion
		failures with operator recovery guidance.

		Improves the failure UX of probes 1.1, 1.2, 1.3, 1.5 from the
		2026-04-28 adversarial review — those previously produced raw
		Python tracebacks with no recovery hint.
		"""
		manifest_path = os.path.join(
			_hamilton_erp_root(), "docs", "design",
			"canonical_mockup_manifest.json"
		)

		if not os.path.isfile(manifest_path):
			self.fail(
				f"\nCanonical mockup manifest is missing at {manifest_path}.\n"
				f"\n"
				f"This file is the source of truth for which mockup is\n"
				f"canonical and what its body fingerprint should be. It must\n"
				f"not be deleted.\n"
				f"\n"
				f"To recover:\n"
				f"  1. If accidental: revert with\n"
				f"     git checkout docs/design/canonical_mockup_manifest.json\n"
				f"  2. If intentional: that's a process failure. The manifest\n"
				f"     must exist whenever a canonical mockup exists. Restore\n"
				f"     from a known-good commit and consult the team before\n"
				f"     removing the regime."
			)

		try:
			with open(manifest_path) as f:
				manifest = json.load(f)
		except json.JSONDecodeError as e:
			self.fail(
				f"\nCanonical mockup manifest at {manifest_path} contains\n"
				f"invalid JSON: {e}\n"
				f"\n"
				f"To recover:\n"
				f"  1. Verify the file is well-formed JSON. Expected fields:\n"
				f"     canonical_version, canonical_path, source_commit,\n"
				f"     body_sha256, hash_scope.\n"
				f"  2. If unsure what changed, revert with:\n"
				f"     git checkout docs/design/canonical_mockup_manifest.json"
			)

		required_keys = ["canonical_version", "canonical_path",
		                 "body_sha256", "source_commit"]
		missing = [k for k in required_keys if k not in manifest]
		if missing:
			self.fail(
				f"\nCanonical mockup manifest is missing required fields:\n"
				f"  {missing}\n"
				f"\n"
				f"The manifest must contain all of: {required_keys}\n"
				f"\n"
				f"To recover:\n"
				f"  1. Add the missing fields. body_sha256 should be the\n"
				f"     SHA-256 of the canonical mockup body (excluding\n"
				f"     gospel block sentinels).\n"
				f"  2. If the manifest was reset to {{}}, revert with:\n"
				f"     git checkout docs/design/canonical_mockup_manifest.json"
			)

		return manifest

	def test_exactly_one_canonical_mockup_exists(self):
		"""Only ONE V*_CANONICAL_MOCKUP.html may exist in docs/design/.

		Catches both strict-pattern collisions (V9 + V10 cohabitation) and
		bypass-pattern variants (case differences, suffixes like _DRAFT or
		.bak) that would create ambiguity about which file is canonical.
		"""
		design_dir = _design_dir()
		self.assertTrue(
			os.path.isdir(design_dir),
			f"docs/design directory not found at {design_dir}",
		)

		# Strict canonical pattern (case-sensitive, exact filename)
		canonical_pattern = re.compile(r"^V\d+_CANONICAL_MOCKUP\.html$")
		# Permissive pattern catches case-variants and suffix-variants that
		# would bypass the strict pattern (V9_canonical_mockup.html,
		# V9_CANONICAL_MOCKUP.html.bak, V9_CANONICAL_MOCKUP_DRAFT.html, etc.).
		# Scoped to HTML-ish filenames only — the manifest (JSON) and other
		# governance docs may legitimately contain "canonical_mockup" in
		# their names without being canonical mockups themselves.
		bypass_pattern = re.compile(
			r"canonical[_\-]?mockup.*\.html?", re.IGNORECASE
		)

		# Recursive scan via os.walk, excluding archive/ subdirectory.
		# Subdirectories like docs/design/draft/ would otherwise allow a
		# near-canonical-named file to evade detection (Probe 5 of the
		# 2026-04-28 adversarial review).
		all_paths = []
		for root, dirs, files in os.walk(design_dir):
			# Skip archive/ — superseded canonicals legitimately live there
			if "archive" in root.split(os.sep):
				continue
			for fname in files:
				rel = os.path.relpath(os.path.join(root, fname), design_dir)
				all_paths.append(rel)

		# Match against the basename for the patterns
		canonicals = sorted(p for p in all_paths if canonical_pattern.match(os.path.basename(p)))
		permissive_matches = [p for p in all_paths if bypass_pattern.search(os.path.basename(p))]
		bypass_attempts = sorted(p for p in permissive_matches if p not in canonicals)

		self.assertEqual(
			bypass_attempts, [],
			f"Found files that resemble canonical mockups but don't match "
			f"the strict pattern ^V\\d+_CANONICAL_MOCKUP\\.html$: "
			f"{bypass_attempts}. These would create ambiguity about which "
			f"file is canonical. Either rename to match the strict pattern, "
			f"move to docs/design/archive/, or delete them.",
		)

		self.assertEqual(
			len(canonicals), 1,
			f"Expected exactly one V*_CANONICAL_MOCKUP.html in docs/design/, "
			f"found {len(canonicals)}: {canonicals}. "
			f"Per CLAUDE.md rule 4, when a successor canonical is created, "
			f"the old file MUST be moved to docs/design/archive/ before the "
			f"new file lands.",
		)

	def test_v9_canonical_mockup_present(self):
		"""The current canonical (per manifest) must exist on disk."""
		manifest = self._load_manifest_or_fail()

		canonical_path = os.path.join(
			_hamilton_erp_root(), manifest["canonical_path"]
		)
		self.assertTrue(
			os.path.isfile(canonical_path),
			f"Canonical mockup file declared in manifest "
			f"({manifest['canonical_path']}) not found at {canonical_path}. "
			f"Either: (a) the manifest's canonical_path field has been "
			f"redirected to a wrong path, or (b) the canonical file has "
			f"been moved/deleted. Verify the file exists and the manifest "
			f"path matches reality.",
		)

	def test_no_stale_mockup_filenames_in_design_dir(self):
		"""Old asset_board*.html naming must not reappear in docs/design/.

		The canonical mockup is at V*_CANONICAL_MOCKUP.html. Any other file
		matching the old asset_board* naming convention is stale legacy
		naming that should be archived or removed. The pattern is broad
		(case-insensitive, any suffix) to catch the many variants that
		exist in Chris's downloads (asset_board_FINAL_v2.html,
		asset_board_mockup_v7.html, asset_board_mockup_FINAL.html, etc.).
		"""
		design_dir = _design_dir()
		if not os.path.isdir(design_dir):
			return  # test_exactly_one_canonical_mockup_exists fails loudly

		stale_pattern = re.compile(r"^asset[_\-]?board.*\.html$", re.IGNORECASE)
		stale = sorted(
			f for f in os.listdir(design_dir)
			if stale_pattern.match(f)
		)

		self.assertEqual(
			stale, [],
			f"Found stale mockup filenames in docs/design/: {stale}. "
			f"These names were superseded by V*_CANONICAL_MOCKUP.html naming "
			f"in PR #16. Move them to docs/design/archive/ if they need to "
			f"be preserved.",
		)

	def test_canonical_mockup_has_gospel_block(self):
		"""Canonical mockup must contain the gospel declaration block."""
		path = os.path.join(_design_dir(), "V9_CANONICAL_MOCKUP.html")
		with open(path) as f:
			content = f.read(8192)  # First 8KB; gospel block sits at top

		markers = [
			"GOSPEL_BLOCK_START",
			"GOSPEL_BLOCK_END",
			"GOSPEL REFERENCE",
			"VERIFY BEFORE TRUSTING",
		]
		for marker in markers:
			self.assertIn(
				marker, content,
				f"Gospel block marker {marker!r} missing from canonical mockup. "
				f"The gospel declaration block at the top of the file is "
				f"required per PR #16 — do not remove or edit it casually.",
			)

	def test_canonical_mockup_body_fingerprint_matches_manifest(self):
		"""Content fingerprint test — fails if the canonical mockup body
		has been edited without going through the canonical-bump process.

		The body is the mockup content EXCLUDING the gospel block (between
		GOSPEL_BLOCK_START and GOSPEL_BLOCK_END sentinels, inclusive). This
		separation lets governance wording evolve without invalidating the
		approved design fingerprint.

		If this test fails, either:
		(a) The change is intentional. Update body_sha256 in
		    docs/design/canonical_mockup_manifest.json AND reference the
		    change in docs/decisions_log.md as an amendment in the same
		    commit. Or, if the design has changed substantially, create
		    V10_CANONICAL_MOCKUP.html and archive V9.
		(b) The change is unintentional. Revert with:
		      git checkout docs/design/V9_CANONICAL_MOCKUP.html
		"""
		manifest = self._load_manifest_or_fail()

		canonical_path = os.path.join(
			_hamilton_erp_root(), manifest["canonical_path"]
		)
		with open(canonical_path, "rb") as f:
			content_bytes = f.read()

		start_marker = b"<!-- GOSPEL_BLOCK_START -->"
		end_marker = b"<!-- GOSPEL_BLOCK_END -->"
		start_idx = content_bytes.find(start_marker)
		end_idx = content_bytes.find(end_marker)

		self.assertGreaterEqual(
			start_idx, 0,
			"GOSPEL_BLOCK_START sentinel not found in canonical mockup. "
			"The gospel block must be wrapped with sentinel comments so "
			"the fingerprint test can extract the body.",
		)
		self.assertGreater(
			end_idx, start_idx,
			"GOSPEL_BLOCK_END sentinel not found or appears before START. "
			"Gospel block markers are malformed.",
		)

		end_of_end = end_idx + len(end_marker)
		body = content_bytes[:start_idx] + content_bytes[end_of_end:]
		actual_hash = hashlib.sha256(body).hexdigest()
		expected_hash = manifest["body_sha256"]

		self.assertEqual(
			actual_hash, expected_hash,
			f"\nCanonical mockup body has changed.\n"
			f"Expected SHA-256 (from manifest): {expected_hash}\n"
			f"Actual SHA-256:                   {actual_hash}\n"
			f"\n"
			f"The canonical mockup body must not be silently edited. "
			f"If this change is intentional, update body_sha256 in "
			f"docs/design/canonical_mockup_manifest.json AND document "
			f"the change in docs/decisions_log.md as an amendment in "
			f"the same commit. If unintentional, revert:\n"
			f"  git checkout docs/design/V9_CANONICAL_MOCKUP.html",
		)
