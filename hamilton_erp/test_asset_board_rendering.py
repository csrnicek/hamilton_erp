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


class TestV9VacateAndTabsAndHeader(IntegrationTestCase):
	"""Regression guards for V9 Vacate sub-buttons + tab list + header shift.

	Decisions covered: 1.1 (tab order), 1.2 (visibility), 4.6 (vacate sub-
	buttons), 6.1 (header shift indicator).
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

	def test_js_tabs_include_vip_per_v9_spec(self):
		"""V9 Decision 1.1 mandates VIP tab between Double and Waitlist."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			'id: "vip"', source,
			"VIP tab missing from tabs getter — V9 Decision 1.1 lists "
			"VIP as one of the 6 category tabs.",
		)

	def test_js_tabs_have_filter_for_auto_hide_empty(self):
		"""V9 Decision 1.2: tab visibility uses has-at-least-one-asset rule."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"this.assets.some(t.filter)", source,
			"Auto-hide-empty visibility check missing — V9 Decision 1.2 "
			"requires tabs to hide when no asset matches their filter.",
		)

	def test_js_vacate_uses_parent_button_pattern(self):
		"""V9 Decision 4.6: Vacate parent button → sub-buttons.

		Tap "Vacate" → expands to Key Return / Rounds. Direct vacate-key /
		vacate-rounds buttons WITHOUT a parent step is a Decision 4.6 violation.
		"""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			'data-action="vacate-toggle"', source,
			"vacate-toggle action missing — V9 Decision 4.6 requires a "
			"parent Vacate button that expands to sub-buttons.",
		)
		self.assertIn(
			"vacate_subs_open", source,
			"vacate_subs_open state flag missing — required to track "
			"whether sub-buttons are expanded.",
		)

	def test_js_header_includes_shift_indicator(self):
		"""V9 Decision 6.1: header shows current shift label."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"hamilton-header-shift", source,
			"hamilton-header-shift class missing — V9 Decision 6.1 "
			"requires shift indicator in the header.",
		)
		self.assertIn(
			"_compute_shift_label", source,
			"_compute_shift_label() helper missing.",
		)

	def test_css_defines_vacate_subs_classes(self):
		"""Vacate sub-buttons CSS must be present."""
		with open(self._css_path()) as f:
			css = f.read()
		self.assertIn(
			".hamilton-vacate-subs", css,
			".hamilton-vacate-subs CSS rule missing — required for V9 "
			"Decision 4.6 sub-buttons UI.",
		)
		self.assertIn(
			".hamilton-vacate-subs-shown", css,
			".hamilton-vacate-subs-shown CSS rule missing — required to "
			"display sub-buttons when parent Vacate is tapped.",
		)


class TestV9CosmeticPolish(IntegrationTestCase):
	"""Regression guards for V9 S3 button sizing + Decision 6.2 footer counts."""

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

	def test_css_action_buttons_use_v9_s3_sizing(self):
		"""V9 S3: primary buttons 12px font + 7px/6px padding for 50+ staff."""
		with open(self._css_path()) as f:
			css = f.read()
		# The .hamilton-action-btn rule should include 12px font and ~7px padding
		# (port of mockup .action-btn at line 444). The previous V6 sizing (8px
		# font, 5px/4px padding) was rejected for tablet readability.
		self.assertNotIn(
			"font-size: 8px;", css.split(".hamilton-action-btn")[1].split("}")[0]
			if ".hamilton-action-btn" in css else "",
			".hamilton-action-btn still uses 8px font — V9 S3 requires "
			"12px for shape recognition by 50+ staff at tablet glass.",
		)
		self.assertIn(
			"padding: 7px 6px;", css,
			"V9 S3 padding (7px 6px on .hamilton-action-btn) missing.",
		)

	def test_css_primary_buttons_use_solid_fill(self):
		"""V9 line 462: primary buttons use solid fills, not low-saturation
		hover-states from V6."""
		with open(self._css_path()) as f:
			css = f.read()
		# V9 primary buttons: hamilton-btn-green = #22c55e + #052e13 text
		self.assertIn("#22c55e", css,
			"V9 primary green color #22c55e missing.")
		self.assertIn("#ef4444", css,
			"V9 primary red color #ef4444 missing.")

	def test_js_footer_drops_dirty_count_per_v9_spec(self):
		"""V9 Decision 6.2: footer shows Available / Occupied / OOS only.

		The Dirty count was extra production cosmetic — V9 spec lists 3
		footer counts, not 4. Section header above the tile grid still
		shows the dirty count.
		"""
		with open(self._js_path()) as f:
			source = f.read()
		# Find the _render_footer body and verify Dirty count is not rendered
		# in the footer template.
		footer_section_match = source.split("_render_footer")[1].split("_update_tab_badges")[0] if "_render_footer" in source else ""
		self.assertNotIn(
			"${__(\"Dirty\")}", footer_section_match,
			"Footer still renders __(\"Dirty\") count — V9 Decision 6.2 "
			"specifies 3 footer counts (Available / Occupied / OOS).",
		)


class TestV9PanelEnrichment(IntegrationTestCase):
	"""Regression guards for V9 panel data enrichment (E8/E11).

	The asset board API enriches each asset with:
	- guest_name (only for Occupied tiles, from Venue Session.full_name)
	- oos_set_by (only for OOS tiles, resolved from Asset Status Log)

	These tests verify the API returns the fields with correct shape.
	"""

	def test_api_returns_guest_name_field_on_every_asset(self):
		"""guest_name must be present (None or string) on every asset row."""
		data = api.get_asset_board_data()
		for a in data["assets"]:
			self.assertIn(
				"guest_name", a,
				f"Asset {a.get('asset_code')} missing guest_name field. "
				f"V9 D6/E8 requires the API to enrich every asset row.",
			)

	def test_api_returns_oos_set_by_field_on_every_asset(self):
		"""oos_set_by must be present (None or string) on every asset row."""
		data = api.get_asset_board_data()
		for a in data["assets"]:
			self.assertIn(
				"oos_set_by", a,
				f"Asset {a.get('asset_code')} missing oos_set_by field. "
				f"V9 E11 requires the API to enrich every asset row.",
			)

	def test_api_does_not_set_guest_name_for_non_occupied(self):
		"""guest_name should be None for non-Occupied assets."""
		data = api.get_asset_board_data()
		for a in data["assets"]:
			if a["status"] != "Occupied":
				self.assertIsNone(
					a["guest_name"],
					f"Asset {a.get('asset_code')} (status {a['status']}) "
					f"has unexpected guest_name={a['guest_name']!r}. "
					f"Only Occupied tiles should carry guest_name.",
				)

	def test_api_does_not_set_oos_set_by_for_non_oos(self):
		"""oos_set_by should be None for non-OOS assets."""
		data = api.get_asset_board_data()
		for a in data["assets"]:
			if a["status"] != "Out of Service":
				self.assertIsNone(
					a["oos_set_by"],
					f"Asset {a.get('asset_code')} (status {a['status']}) "
					f"has unexpected oos_set_by={a['oos_set_by']!r}. "
					f"Only OOS tiles should carry oos_set_by.",
				)


class TestV9PanelEnrichmentJSContract(IntegrationTestCase):
	"""JS-side contract: rendered overlay reads guest_name and oos_set_by
	from the asset payload. Guards that JS stays in sync with API enrichment.
	"""

	@classmethod
	def _js_path(cls):
		return frappe.get_app_path(
			"hamilton_erp", "hamilton_erp", "page", "asset_board", "asset_board.js"
		)

	def test_js_reads_guest_name_from_asset(self):
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"asset.guest_name", source,
			"JS doesn't read asset.guest_name — V9 D6/E8 contract broken.",
		)

	def test_js_reads_oos_set_by_from_asset(self):
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"asset.oos_set_by", source,
			"JS doesn't read asset.oos_set_by — V9 E11 contract broken.",
		)


# ───────────────────────────────────────────────────────────────────────
# 2026-04-29 V9 browser-test session amendments
# Regression guards for Amendment 2026-04-29 in docs/decisions_log.md.
# ───────────────────────────────────────────────────────────────────────

class TestV9BrowserTestAmendments(IntegrationTestCase):
	"""Regression guards for the four fixes from Chris's 2026-04-29 browser test."""

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

	@classmethod
	def _api_path(cls):
		return frappe.get_app_path("hamilton_erp", "api.py")

	@classmethod
	def _realtime_path(cls):
		return frappe.get_app_path("hamilton_erp", "realtime.py")

	# A29-1 — Bulk Mark All Clean removed
	def test_api_does_not_define_mark_all_clean_endpoints(self):
		with open(self._api_path()) as f:
			source = f.read()
		for forbidden in (
			"def mark_all_clean_rooms",
			"def mark_all_clean_lockers",
			"def _mark_all_clean",
		):
			self.assertNotIn(
				forbidden, source,
				f"api.py still defines {forbidden!r} — A29-1 reverses DEC-054.",
			)

	def test_realtime_does_not_define_publish_board_refresh(self):
		with open(self._realtime_path()) as f:
			source = f.read()
		self.assertNotIn(
			"def publish_board_refresh", source,
			"realtime.py still defines publish_board_refresh — A29-1 removed it.",
		)

	def test_js_does_not_render_bulk_mark_all_clean_button(self):
		with open(self._js_path()) as f:
			source = f.read()
		for forbidden in (
			"hamilton-footer-bulk",
			"hamilton-bulk-list",
			"confirm_bulk_clean",
			"mark_all_clean_rooms",
			"mark_all_clean_lockers",
		):
			self.assertNotIn(
				forbidden, source,
				f"asset_board.js still references {forbidden!r} — A29-1 removed bulk Mark All Clean.",
			)

	def test_css_does_not_define_bulk_button(self):
		with open(self._css_path()) as f:
			source = f.read()
		for forbidden in (".hamilton-footer-bulk", ".hamilton-bulk-list"):
			self.assertNotIn(
				forbidden, source,
				f"asset_board.css still defines {forbidden!r} — A29-1 removed bulk Mark All Clean.",
			)

	# A29-6 — RTS modal SET line includes timestamp
	def test_js_defines_format_oos_set_time_helper(self):
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"_format_oos_set_time", source,
			"asset_board.js missing _format_oos_set_time helper — A29-6 requires the RTS SET line to include time-of-day.",
		)

	def test_js_rts_set_line_uses_at_time_pattern(self):
		"""The RTS modal SET line builds 'at HH:MM AM/PM' from oos_set_time."""
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"set_at_time = this._format_oos_set_time", source,
			"_open_return_modal doesn't compute set_at_time via the helper.",
		)
		self.assertIn(
			'__("at")', source,
			"asset_board.js doesn't translate the 'at' connector — RTS SET line format may not match OOS audit.",
		)

	# A29-5 — Dirty tile shows "Dirty for Xm" timer
	def test_dirty_tiles_render_elapsed_timer(self):
		with open(self._js_path()) as f:
			source = f.read()
		self.assertIn(
			"hamilton-dirty-elapsed", source,
			"asset_board.js doesn't emit the .hamilton-dirty-elapsed class — A29-5 requires Dirty-for-Xm timer.",
		)
		self.assertIn(
			'__("Dirty for")', source,
			"asset_board.js doesn't render the 'Dirty for' label — A29-5 wording missing.",
		)

	def test_css_styles_dirty_elapsed_timer(self):
		with open(self._css_path()) as f:
			source = f.read()
		self.assertIn(
			".hamilton-dirty-elapsed", source,
			"asset_board.css missing .hamilton-dirty-elapsed selector — A29-5 styling absent.",
		)


# ───────────────────────────────────────────────────────────────────────
# V9.1 Retail amendment regression guards
# Spec: docs/design/V9.1_RETAIL_AMENDMENT.md
# ───────────────────────────────────────────────────────────────────────

class TestV91RetailFoundation(IntegrationTestCase):
	"""Regression guards for the V9.1 retail SKU foundation."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Make sure the seed has run so the Drink/Food Item Group + 4 Items
		# exist for the integration assertions below. Idempotent.
		from hamilton_erp.patches.v0_1 import seed_hamilton_env
		seed_hamilton_env.execute()
		frappe.db.commit()

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

	# ── Backend / API tests ───────────────────────────────────

	def test_seed_creates_drink_food_item_group(self):
		self.assertTrue(
			frappe.db.exists("Item Group", "Drink/Food"),
			"Hamilton seed missing the V9.1 Drink/Food Item Group.",
		)

	def test_seed_creates_four_sample_items(self):
		expected_codes = {"WAT-500", "GAT-500", "BAR-PROT", "BAR-ENRG"}
		actual = set(frappe.get_all(
			"Item",
			filters={"item_code": ["in", list(expected_codes)]},
			pluck="item_code",
		))
		self.assertEqual(
			actual, expected_codes,
			f"V9.1 sample Items missing. Expected {expected_codes}, got {actual}.",
		)

	def test_get_asset_board_data_returns_items_and_retail_tabs_keys(self):
		from hamilton_erp import api
		data = api.get_asset_board_data()
		self.assertIn("items", data,
			"V9.1: API payload must include 'items' key (may be empty list).")
		self.assertIn("retail_tabs", data,
			"V9.1: API payload must include 'retail_tabs' key (may be empty list).")
		self.assertIsInstance(data["items"], list)
		self.assertIsInstance(data["retail_tabs"], list)

	def test_items_payload_shape_when_retail_configured(self):
		"""Configure retail_tabs in site_config and assert per-item shape.

		The site-config write happens via a Frappe helper that bypasses the
		normal request flow. We restore the previous value in tearDown.
		"""
		from hamilton_erp import api
		prior = frappe.conf.get("retail_tabs")
		try:
			# Set the per-test retail_tabs flag in process-local conf so
			# get_asset_board_data sees it.
			frappe.conf["retail_tabs"] = ["Drink/Food"]
			data = api.get_asset_board_data()
			self.assertEqual(data["retail_tabs"], ["Drink/Food"])
			self.assertGreaterEqual(
				len(data["items"]), 4,
				"V9.1: at least the 4 seeded items should appear when "
				"Drink/Food is configured.",
			)
			required_keys = {
				"name", "item_code", "item_name", "item_group",
				"image", "standard_rate", "stock",
			}
			sample = data["items"][0]
			missing = required_keys - set(sample.keys())
			self.assertEqual(
				missing, set(),
				f"V9.1: item row missing keys {missing}. Got: {sorted(sample.keys())}",
			)
			# Stock should be a number (0.0 if Bin missing).
			self.assertIsInstance(sample["stock"], (int, float))
		finally:
			# Restore prior state so other tests aren't polluted.
			if prior is None:
				frappe.conf.pop("retail_tabs", None)
			else:
				frappe.conf["retail_tabs"] = prior

	def test_no_retail_config_returns_empty_lists(self):
		from hamilton_erp import api
		prior = frappe.conf.get("retail_tabs")
		try:
			# Force retail_tabs to absent / empty.
			frappe.conf.pop("retail_tabs", None)
			data = api.get_asset_board_data()
			self.assertEqual(data["items"], [])
			self.assertEqual(data["retail_tabs"], [])
		finally:
			if prior is not None:
				frappe.conf["retail_tabs"] = prior

	# ── Frontend (JS source-substring) tests ──────────────────

	def test_js_reads_items_and_retail_tabs_from_api(self):
		with open(self._js_path()) as f:
			src = f.read()
		self.assertIn("r.message.items", src,
			"asset_board.js doesn't read message.items — V9.1 retail payload contract broken.")
		self.assertIn("r.message.retail_tabs", src,
			"asset_board.js doesn't read message.retail_tabs — V9.1 retail tab list contract broken.")

	def test_js_defines_render_retail_tile(self):
		with open(self._js_path()) as f:
			src = f.read()
		self.assertIn(
			"_render_retail_tile", src,
			"asset_board.js missing _render_retail_tile — V9.1-D6 tile shape not implemented.",
		)
		self.assertIn(
			"_render_retail_grid", src,
			"asset_board.js missing _render_retail_grid — retail tab content path not wired.",
		)

	def test_js_retail_tabs_have_item_filter(self):
		"""Retail tabs are built from this.retail_tabs and filter by item_group."""
		with open(self._js_path()) as f:
			src = f.read()
		self.assertIn("retail: true", src,
			"asset_board.js doesn't tag retail tab objects with retail:true — render dispatch broken.")
		self.assertIn("item_group", src,
			"asset_board.js retail tabs don't carry item_group reference for filtering.")

	def test_retail_tab_badge_counts_in_stock_only(self):
		"""V9 Amendment 2026-04-29 A29-2: tab badge = available count only.

		Retail's equivalent of 'Available' is 'stock > 0'. Out-of-stock
		items should NOT count toward the badge — operators read tab
		badges to answer 'what can I sell right now?'.
		"""
		with open(self._js_path()) as f:
			src = f.read()
		# Both code paths (initial render in render_shell + live update in
		# _update_tab_badges) must filter retail badge by stock > 0.
		self.assertIn(
			"get_retail_in_stock_count", src,
			"asset_board.js missing get_retail_in_stock_count helper — "
			"retail tab badge will count all items including out-of-stock.",
		)
		self.assertIn(
			"Number(it.stock) > 0", src,
			"asset_board.js doesn't filter retail badge by stock > 0 — "
			"violates A29-2 (tab badge = available count only).",
		)

	def test_css_defines_retail_tile_classes(self):
		with open(self._css_path()) as f:
			src = f.read()
		for cls in (
			".hamilton-retail-grid",
			".hamilton-retail-tile",
			".hamilton-retail-code",
			".hamilton-retail-stock",
			".hamilton-retail-name",
			".hamilton-retail-price",
		):
			self.assertIn(
				cls, src,
				f"asset_board.css missing {cls!r} — V9.1-D6 retail tile styling absent.",
			)


def tearDownModule():
	"""Restore dev state wiped by this module's tests.

	See hamilton_erp/test_helpers.py for why this exists.
	"""
	from hamilton_erp.test_helpers import restore_dev_state
	restore_dev_state()
