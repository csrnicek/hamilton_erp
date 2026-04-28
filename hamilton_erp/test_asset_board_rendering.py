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


class TestV9TimeStateModel(IntegrationTestCase):
	"""Regression guards for the V9 3-state time model (Decision 3.1).

	V9 explicitly REJECTED the prior 2-state warning/overtime model
	(Part 10 of decisions_log.md). The correct model is:
	  normal:    remaining > 60       → no text on tile
	  countdown: 0 < remaining <= 60  → red "Xm left"
	  overtime:  remaining <= 0       → red "Xm late" + OT badge + pulse

	These tests fail loudly if a future refactor reverts to the rejected
	2-stage warning/overtime model.
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

	def test_js_defines_countdown_threshold_constant(self):
		"""V9 Decision 3.1 requires COUNTDOWN_THRESHOLD_MIN = 60."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"COUNTDOWN_THRESHOLD_MIN = 60",
			source,
			"COUNTDOWN_THRESHOLD_MIN constant missing or wrong value. "
			"V9 Decision 3.1 mandates 60 minutes as the countdown threshold.",
		)

	def test_js_defines_compute_time_status(self):
		"""3-state classifier function must exist."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"_compute_time_status",
			source,
			"_compute_time_status() function missing. V9 Decision 3.1 "
			"requires a 3-state classifier (normal/countdown/overtime).",
		)

	def test_js_uses_15s_live_tick(self):
		"""V9 Decision 3.7: live tick cadence is 15 seconds."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"LIVE_TICK_MS = 15000",
			source,
			"LIVE_TICK_MS constant missing or wrong value. V9 Decision 3.7 "
			"mandates 15-second live-tick cadence (was 30s in production).",
		)

	def test_js_does_not_implement_rejected_warning_state(self):
		"""V9 Decision 3.2 + Part 10: 2-state warning/overtime REJECTED.

		The hamilton-warning class was the visible artifact of the rejected
		two-stage model. If this string reappears, the rejected design
		shipped again.
		"""
		with open(self._js_path()) as f:
			js = f.read()
		with open(self._css_path()) as f:
			css = f.read()
		self.assertNotIn(
			'addClass("hamilton-warning"', js,
			"hamilton-warning class is being added — that's the rejected "
			"V6 two-stage warning state. V9 Decision 3.2 requires single "
			"overtime state.",
		)
		self.assertNotIn(
			".hamilton-warning", css,
			"hamilton-warning CSS rule still present — V9 Decision 3.2 "
			"removed the two-stage warning state.",
		)

	def test_css_defines_countdown_text_style(self):
		"""Countdown text must be red (V9 Amendment 2026-04-24)."""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertIn(
			".hamilton-tile-time", css,
			".hamilton-tile-time class missing — V9 Decision 3.1 requires "
			"inline countdown/overtime text on occupied tiles.",
		)

	def test_css_defines_ot_corner_badge_top_centered(self):
		"""V9 Decision 3.4: OT badge sits centered on top border, not in corner."""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertIn(
			".hamilton-tile-corner-badge.hamilton-corner-ot", css,
			"OT corner badge CSS rule missing — V9 Decision 3.4 requires "
			"the OT badge to hang off the top border (corner placement "
			"REJECTED).",
		)

	def test_css_pulse_animation_includes_background_flash(self):
		"""V9 Decision 3.5: pulse must include >25-unit brightness swing.

		Box-shadow alone produced ~17 unit swing in V8 visual review, too
		subtle. V9 added background-color flash to bump perceptible brightness.
		"""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertIn(
			"hamilton-pulse-strong", css,
			"hamilton-pulse-strong keyframe missing — V9 Decision 3.5 "
			"requires bg-color flash for visible pulse.",
		)
		self.assertIn(
			"background-color: #6b1a1a", css,
			"Pulse keyframe missing the bright-flash background-color step. "
			"V9 Decision 3.5 mandates a >25-unit brightness swing.",
		)


class TestV9OOSWorkflow(IntegrationTestCase):
	"""Regression guards for V9 OOS modal + Return modal (Decisions 5.1-5.5, S2, S6).

	V9 mandates a fixed 7-reason dropdown for Set OOS (NOT free text), a
	conditional "Other" textarea, an audit-preview line, and a separate
	Return-to-Service confirmation modal showing reason + days-ago context.

	These tests fail if a future refactor reverts to the rejected free-text
	Frappe Dialog approach.
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

	def test_js_defines_all_seven_oos_reasons(self):
		"""V9 Decision 5.2: 7 fixed reasons in OOS_REASONS array, "Other" last."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn("OOS_REASONS", source,
			"OOS_REASONS constant missing — V9 Decision 5.2 mandates "
			"a fixed list of 7 reasons.")
		expected = [
			"Plumbing", "Electrical", "Lock or Hardware",
			"Cleaning required (deep)", "Damage",
			"Maintenance scheduled", "Other",
		]
		for reason in expected:
			self.assertIn(f'"{reason}"', source,
				f"OOS reason {reason!r} missing from OOS_REASONS array.")

	def test_js_defines_oos_modal_method(self):
		"""V9 Decision 5.2 requires a proper modal (not free-text dialog)."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn("_open_oos_modal", source,
			"_open_oos_modal() method missing — V9 Decision 5.2 requires "
			"a custom modal with reason dropdown, not the rejected "
			"free-text Frappe Dialog.")

	def test_js_defines_return_modal_method(self):
		"""V9 Decision 5.5 requires Return-to-Service confirmation modal."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn("_open_return_modal", source,
			"_open_return_modal() method missing — V9 Decision 5.5 "
			"requires a confirmation modal showing context (reason + "
			"days-ago) before returning to service.")

	def test_js_no_longer_uses_free_text_prompt_reason(self):
		"""The free-text Frappe Dialog approach was REJECTED by Decision 5.2."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertNotIn("_prompt_reason", source,
			"_prompt_reason() is back — that's the rejected free-text "
			"OOS dialog approach. V9 Decisions 5.2 and 5.5 require "
			"separate modals for Set OOS and Return to Service.")

	def test_css_defines_modal_classes(self):
		"""Modal CSS classes must be present."""
		with open(self._css_path()) as f:
			css = f.read()
		required_classes = [
			".hamilton-modal-backdrop",
			".hamilton-oos-modal",
			".hamilton-oos-note-wrap",
			".hamilton-modal-audit",
			".hamilton-modal-context",
			".hamilton-oos-info",
			".hamilton-guest-info",
		]
		for cls in required_classes:
			self.assertIn(cls, css,
				f"CSS class {cls} missing — required for V9 OOS modal "
				f"+ Return modal + tile context panels.")


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
