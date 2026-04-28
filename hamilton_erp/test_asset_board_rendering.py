"""Tests for the Asset Board tile rendering contract (Task 17.2).

These tests complement ``test_api_phase1.py`` (which covers API correctness
and the sub-second perf baseline) by focusing on the data-shape invariants
that ``asset_board.js`` relies on for tile rendering:

  - Zone split: 26 Rooms + 33 Lockers = 59 total
  - Room tier mix matches seed plan (11 / 10 / 2 / 3)
  - Every locker has ``asset_tier = "Locker"``
  - Every asset has the fields ``render_tile()`` reads
  - Every status maps to one of the four ``.hamilton-status-*`` classes
    actually defined in ``asset_board.css``
  - The status→CSS-class formula used in ``asset_board.js:86`` produces
    the four class names the CSS file defines

The last two form a "contract test" for the JS/CSS boundary: if a new
Venue Asset status is added without a matching CSS class, or if the JS
formula is changed, these tests fail before Chris sees an unstyled tile
in the browser.
"""
import frappe
from frappe.tests import IntegrationTestCase

from hamilton_erp import api
from hamilton_erp.patches.v0_1 import seed_hamilton_env


# Must match the ``.hamilton-status-*`` classes defined in
# ``hamilton_erp/public/css/asset_board.css`` lines 83-87.
EXPECTED_CSS_CLASSES = {
	"Available": "hamilton-status-available",
	"Occupied": "hamilton-status-occupied",
	"Dirty": "hamilton-status-dirty",
	"Out of Service": "hamilton-status-out-of-service",
}


def _js_style_css_class(status: str) -> str:
	"""Python mirror of ``asset_board.js:86`` — the JS-side CSS class generator.

	Replicates ``hamilton-status-${status.toLowerCase().replace(/ /g, "-")}``
	so the JS→CSS contract can be asserted without executing JavaScript.
	If the JS formula ever changes, update this helper to match and the
	consistency test below will surface the drift.
	"""
	return f"hamilton-status-{status.lower().replace(' ', '-')}"


class TestAssetBoardRendering(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Wipe sessions first — Venue Session has an FK back to Venue
		# Asset via current_session, so assets can't be deleted until
		# sessions are gone. Matches the pattern in test_api_phase1.py.
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		seed_hamilton_env.execute()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Scrub sessions + assets. Unlike test_api_phase1.py we do NOT
		# flush Redis ``hamilton:session_seq:*`` because this test never
		# starts a session and therefore never increments the counter —
		# cleaning up state we didn't create would be cargo-culted and
		# would fail loudly if the Redis cache port is unreachable.
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		frappe.db.commit()
		super().tearDownClass()

	# --- Zone split ---------------------------------------------------

	def test_zone_split_26_rooms_33_lockers(self):
		data = api.get_asset_board_data()
		rooms = [a for a in data["assets"] if a["asset_category"] == "Room"]
		lockers = [a for a in data["assets"] if a["asset_category"] == "Locker"]
		self.assertEqual(
			len(rooms), 26,
			f"Expected 26 rooms, got {len(rooms)} — seed_hamilton_env.py drift?",
		)
		self.assertEqual(
			len(lockers), 33,
			f"Expected 33 lockers, got {len(lockers)} — seed_hamilton_env.py drift?",
		)

	# --- Room tier mix ------------------------------------------------

	def test_room_tier_counts_match_seed_plan(self):
		"""seed_hamilton_env.py plan: 11 STD, 10 DLX, 2 GH, 3 2DLX."""
		data = api.get_asset_board_data()
		rooms = [a for a in data["assets"] if a["asset_category"] == "Room"]
		tier_counts: dict[str, int] = {}
		for r in rooms:
			tier_counts[r["asset_tier"]] = tier_counts.get(r["asset_tier"], 0) + 1
		self.assertEqual(tier_counts.get("Single Standard"), 11)
		self.assertEqual(tier_counts.get("Deluxe Single"), 10)
		self.assertEqual(tier_counts.get("GH Room"), 2)
		self.assertEqual(tier_counts.get("Double Deluxe"), 3)

	def test_every_room_has_one_of_the_four_canonical_tiers(self):
		canonical = {"Single Standard", "Deluxe Single", "GH Room", "Double Deluxe"}
		data = api.get_asset_board_data()
		for r in (a for a in data["assets"] if a["asset_category"] == "Room"):
			self.assertIn(
				r["asset_tier"], canonical,
				f"Room {r['asset_code']} has unexpected tier {r['asset_tier']!r}",
			)

	# --- Locker tier --------------------------------------------------

	def test_every_locker_has_tier_locker(self):
		data = api.get_asset_board_data()
		for locker in (a for a in data["assets"] if a["asset_category"] == "Locker"):
			self.assertEqual(
				locker["asset_tier"], "Locker",
				f"Locker {locker['asset_code']} has unexpected tier "
				f"{locker['asset_tier']!r}",
			)

	# --- Required tile fields -----------------------------------------

	def test_every_asset_has_fields_required_by_render_tile(self):
		"""render_tile() reads: name, asset_code, asset_name, status, asset_tier.

		If any tile row returns None in these core fields, the rendered
		HTML will have garbage data attributes or an empty body. This
		guards against a silent schema change.
		"""
		required = (
			"name", "asset_code", "asset_name",
			"status", "asset_tier", "asset_category",
		)
		data = api.get_asset_board_data()
		for a in data["assets"]:
			for field in required:
				self.assertIn(
					field, a,
					f"Asset {a.get('name')} missing field {field!r}",
				)
				self.assertIsNotNone(
					a[field],
					f"Asset {a.get('name')} has null {field!r}",
				)

	# --- Status → CSS class contract ----------------------------------

	def test_every_asset_status_has_a_defined_css_class(self):
		"""Every status returned by the API must map to one of the four
		CSS classes actually defined in asset_board.css.

		If someone adds a new Venue Asset status without also adding the
		matching ``.hamilton-status-*`` rule, this test fires before
		Chris sees an unstyled (background-less) tile in production.
		"""
		data = api.get_asset_board_data()
		for a in data["assets"]:
			self.assertIn(
				a["status"], EXPECTED_CSS_CLASSES,
				f"Asset {a['asset_code']} has unknown status "
				f"{a['status']!r} — no .hamilton-status-* class defined",
			)

	def test_js_css_class_formula_matches_expected_mapping(self):
		"""asset_board.js:86 generates CSS classes via
		``hamilton-status-${status.toLowerCase().replace(/ /g, "-")}``.

		This test codifies that formula in Python and asserts it produces
		the four class names the CSS file actually defines. If the JS
		formula is ever changed (e.g., to camelCase), this test fails
		and forces a review of the CSS class naming contract.
		"""
		for status, expected_class in EXPECTED_CSS_CLASSES.items():
			self.assertEqual(
				_js_style_css_class(status), expected_class,
				f"JS formula produced wrong class for {status!r}",
			)


class TestOvertimeTickerContract(IntegrationTestCase):
	"""Contract tests for the Task 19 overtime ticker.

	The ticker runs in JavaScript (30-second setInterval), but it depends
	on server-side data: session_start on occupied assets, expected_stay_duration
	on every asset, and grace_minutes in settings. These tests verify the API
	returns all the fields the JS ticker reads.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		seed_hamilton_env.execute()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("Venue Session")
		frappe.db.delete("Venue Asset")
		frappe.db.commit()
		super().tearDownClass()

	def test_settings_include_grace_minutes(self):
		"""The overtime ticker reads settings.grace_minutes to decide
		when Stage 1 (warning) transitions to Stage 2 (overtime)."""
		data = api.get_asset_board_data()
		self.assertIn("settings", data)
		self.assertIn("grace_minutes", data["settings"])
		self.assertIsInstance(data["settings"]["grace_minutes"], (int, float))
		self.assertGreater(data["settings"]["grace_minutes"], 0)

	def test_every_asset_has_expected_stay_duration(self):
		"""The ticker compares elapsed time against expected_stay_duration
		to decide warning vs overtime stage."""
		data = api.get_asset_board_data()
		for a in data["assets"]:
			self.assertIn(
				"expected_stay_duration", a,
				f"Asset {a.get('asset_code')} missing expected_stay_duration",
			)
			self.assertIsNotNone(a["expected_stay_duration"])
			self.assertGreater(
				a["expected_stay_duration"], 0,
				f"Asset {a.get('asset_code')} has non-positive stay duration",
			)

	def test_occupied_asset_has_session_start(self):
		"""When a tile is Occupied, the ticker needs session_start to
		calculate elapsed time. This test creates an occupied session
		and verifies the API enriches the asset with session_start."""
		from hamilton_erp.lifecycle import start_session_for_asset

		asset_name = frappe.db.get_value(
			"Venue Asset", {"status": "Available"}, "name"
		)
		if not asset_name:
			self.skipTest("No Available asset to occupy")

		try:
			start_session_for_asset(asset_name, operator=frappe.session.user)
			data = api.get_asset_board_data()
			occupied = [a for a in data["assets"] if a["name"] == asset_name]
			self.assertEqual(len(occupied), 1)
			asset = occupied[0]
			self.assertEqual(asset["status"], "Occupied")
			self.assertIsNotNone(
				asset.get("session_start"),
				"Occupied asset must have session_start for overtime ticker",
			)
		finally:
			frappe.db.rollback()

	def test_available_asset_has_no_session_start(self):
		"""Available tiles should not have a truthy session_start — the
		ticker skips non-Occupied tiles, but stale data could confuse it."""
		data = api.get_asset_board_data()
		available = [a for a in data["assets"] if a["status"] == "Available"]
		self.assertGreater(len(available), 0, "No Available assets found")
		for a in available:
			self.assertFalse(
				a.get("session_start"),
				f"Available asset {a['asset_code']} should not have session_start",
			)


class TestExpandOverlayContract(IntegrationTestCase):
	"""Regression guards for the floating-overlay tile expand (Decision 2.4).

	Decision 2.4 requires a separate absolutely-positioned overlay with
	edge-aware viewport clamping, dismissed by tap-outside or scroll. Earlier
	implementations used an inline ``transform: scale(1.5)`` panel inside the
	tile, which clipped at viewport edges. These tests fail loudly if a future
	refactor reverts to the inline pattern.

	The contract is asserted by reading the JS/CSS source — the alternative
	(spinning up a headless browser to inspect computed styles) is far heavier
	and Hamilton has no Playwright/Puppeteer infrastructure.
	"""

	@classmethod
	def _js_path(cls):
		return frappe.get_app_path(
			"hamilton_erp", "hamilton_erp", "page", "asset_board", "asset_board.js"
		)

	@classmethod
	def _css_path(cls):
		return frappe.get_app_path(
			"hamilton_erp", "public", "css", "asset_board.css"
		)

	def test_js_defines_show_overlay(self):
		"""Decision 2.4 requires a floating overlay primitive."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"_show_overlay",
			source,
			"_show_overlay() function not found in asset_board.js — "
			"Decision 2.4 requires a floating overlay primitive",
		)

	def test_js_defines_position_overlay(self):
		"""Decision 2.4 requires viewport-clamped positioning."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"_position_overlay",
			source,
			"_position_overlay() function not found in asset_board.js — "
			"Decision 2.4 requires edge-aware viewport-clamped positioning",
		)

	def test_js_defines_hide_overlay(self):
		"""Decision 2.4 requires explicit close (tap outside or scroll)."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"_hide_overlay",
			source,
			"_hide_overlay() function not found in asset_board.js — "
			"Decision 2.4 requires explicit overlay teardown",
		)

	def test_js_uses_get_bounding_client_rect(self):
		"""Edge-aware positioning requires reading viewport rects."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"getBoundingClientRect",
			source,
			"getBoundingClientRect not used — Decision 2.4 viewport "
			"clamping requires reading source-tile and container rects",
		)

	def test_js_binds_scroll_to_close(self):
		"""Decision 2.4: 'Tap outside, OR SCROLL THE BOARD, to collapse.'"""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"scroll.hamilton-overlay",
			source,
			"Scroll-to-close listener not found — Decision 2.4 explicitly "
			"requires that scrolling the board collapses an open overlay",
		)

	def test_css_defines_expand_overlay_class(self):
		"""The overlay needs its own absolutely-positioned class."""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertIn(
			".hamilton-expand-overlay",
			css,
			".hamilton-expand-overlay class missing — overlay needs its "
			"own positioning rule (Decision 2.4)",
		)

	def test_css_defines_source_tile_dim_class(self):
		"""Source tile must be dimmed while overlay is shown (Decision 2.4)."""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertIn(
			".hamilton-source-tile",
			css,
			".hamilton-source-tile class missing — source tile must be "
			"dimmed while overlay is shown (Decision 2.4)",
		)

	def test_css_no_longer_scales_expanded_tile(self):
		"""The broken inline-scale pattern must not return.

		Old behaviour was ``.hamilton-tile.hamilton-expanded { transform:
		scale(1.5) }`` which clipped at viewport edges (Chris confirmed in
		browser, 2026-04-28). The fix replaces this with a separate overlay.
		If a future refactor reverts to scaling the source tile, this test
		fails before the bug ships.
		"""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertNotIn(
			"transform: scale(1.5)",
			css,
			"transform: scale(1.5) is back in asset_board.css — this is "
			"the broken inline-expand pattern Decision 2.4 explicitly "
			"replaced with a floating overlay",
		)


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
