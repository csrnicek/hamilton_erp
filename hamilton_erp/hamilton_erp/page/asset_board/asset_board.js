frappe.provide("hamilton_erp");

// V9 Decision 3.1: 3-state time model on occupied tiles.
//   normal:    remaining > 60       → no text on tile
//   countdown: 0 < remaining <= 60  → red "Xm left"
//   overtime:  remaining <= 0       → red "Xm late" + OT badge + pulse
// Per V9_CANONICAL_MOCKUP.html line 932 and decisions_log.md Part 3.1.
const COUNTDOWN_THRESHOLD_MIN = 60;

// V9 Decision 3.7: live-tick cadence so countdown→overtime transitions
// surface without a user interaction. 15s is cheap on Frappe and visually
// imperceptible. Per V9_CANONICAL_MOCKUP.html line 1498.
const LIVE_TICK_MS = 15000;

// V9 Decision 5.2: 7 fixed OOS reasons in a global list. "Other" must
// always remain the last option — it's the required escape hatch and
// triggers the conditional note field. Per V9_CANONICAL_MOCKUP.html
// line 823. Phase 2 will wire this to an admin-editable DocType.
const OOS_REASONS = [
	"Plumbing",
	"Electrical",
	"Lock or Hardware",
	"Cleaning required (deep)",
	"Damage",
	"Maintenance scheduled",
	"Other",
];
//

frappe.pages["asset-board"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Asset Board"),
		single_column: true,
	});
	new hamilton_erp.AssetBoard(page);
};

hamilton_erp.AssetBoard = class AssetBoard {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.assets = [];
		this.settings = {};
		this.active_tab = "lockers";
		this.expanded_asset = null;
		this.$overlay = null;
		// V9 Decision 4.6: Vacate sub-buttons. When Vacate parent is tapped,
		// flip this flag to true so the overlay renders Key Return / Rounds
		// sub-buttons instead of the parent. Reset on overlay close.
		this.vacate_subs_open = false;
		this.overtime_interval = null;
		this.clock_interval = null;
		this.init();
	}

	// Tab definitions — V9 spec order per decisions_log.md Part 1.1:
	//   lockers / single / double / vip / waitlist / other / watch.
	// Hamilton-specific extension: gh-room tab between vip and waitlist
	// because Hamilton's actual asset_tier set includes "GH Room" rooms
	// that don't fit any V9-standard category. Other venues without GH
	// Room assets get auto-hidden via the categoryHasAssets check.
	// V9 Decision 1.2: tab visibility = enabled-in-config AND has-at-least-one-asset.
	get tabs() {
		return [
			{ id: "lockers", label: __("Lockers"), filter: (a) => a.asset_category === "Locker" },
			{ id: "single", label: __("Single"), filter: (a) => a.asset_category === "Room" && (a.asset_tier === "Single Standard" || a.asset_tier === "Deluxe Single") },
			{ id: "double", label: __("Double"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "Double Deluxe" },
			{ id: "vip", label: __("VIP"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "VIP" },
			{ id: "gh-room", label: __("GH Room"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "GH Room" },
			{ id: "waitlist", label: __("Waitlist"), feature_flag: "show_waitlist_tab", placeholder: true },
			{ id: "other", label: __("Other"), feature_flag: "show_other_tab", placeholder: true },
			{ id: "watch", label: __("Watch"), watch: true },
		];
	}

	async init() {
		this.wrapper.html(`<div class="hamilton-loading">${__("Loading Asset Board...")}</div>`);
		await this.fetch_board();
		this.render_shell();
		this.render_active_tab();
		this.start_overtime_ticker();
		this.start_clock();
		this.listen_realtime();
		this.page.wrapper.on("page-destroyed", () => this.teardown());
	}

	// type: "GET" is mandatory — see DEC-058
	async fetch_board() {
		const r = await frappe.call({
			method: "hamilton_erp.api.get_asset_board_data",
			type: "GET",
			freeze: true,
			freeze_message: __("Loading board..."),
		});
		this.assets = r.message.assets;
		this.settings = r.message.settings;
	}

	// ── Shell: header + tabs + content area + footer ────────
	render_shell() {
		// V9 Decision 1.2: combined visibility rule.
		// A tab renders only when BOTH:
		//   1. enabled in config (feature_flag check OR no flag = always-on)
		//   2. has at least one asset matching its filter (auto-hide empty)
		// Watch tab is always visible regardless.
		// Mockup parallel: getTabs() at V9_CANONICAL_MOCKUP.html line 967.
		const visible_tabs = this.tabs.filter((t) => {
			if (t.watch) return true;
			if (t.feature_flag && !this.settings[t.feature_flag]) return false;
			if (t.placeholder) return true;  // placeholder tabs (Waitlist/Other) skip asset check
			if (typeof t.filter !== "function") return true;
			return this.assets.some(t.filter);
		});

		const tab_html = visible_tabs.map((t) => {
			const cls = ["hamilton-tab"];
			if (t.id === this.active_tab) cls.push("active");
			if (t.watch) cls.push("hamilton-tab-watch");

			let badge = "";
			if (t.watch) {
				const count = this.get_watch_count();
				if (count > 0) {
					badge = `<span class="hamilton-badge hamilton-badge-watch">${count}</span>`;
				}
			} else if (!t.placeholder) {
				const count = this.get_tab_available_count(t);
				badge = `<span class="hamilton-badge hamilton-badge-available">${count}</span>`;
			}

			return `<button class="${cls.join(" ")}" data-tab="${t.id}">
				${frappe.utils.escape_html(t.label)}${badge}
			</button>`;
		}).join("");

		const user_name = frappe.boot.user.full_name || frappe.session.user;
		const now = this._format_time(new Date());
		const shift = this._compute_shift_label(new Date());

		this.wrapper.html(`
			<div class="hamilton-board">
				<div class="hamilton-header">
					<div class="hamilton-header-left">
						<span class="hamilton-header-venue">CLUB HAMILTON</span>
						<span class="hamilton-header-sep">&middot;</span>
						<span class="hamilton-header-title">ASSET BOARD</span>
						<span class="hamilton-header-sep">&middot;</span>
						<span class="hamilton-header-shift">${frappe.utils.escape_html(shift)}</span>
						<span class="hamilton-header-sep">&middot;</span>
						<span class="hamilton-header-time">${now}</span>
					</div>
					<div class="hamilton-header-right">
						<span class="hamilton-online-dot"></span>
						<span class="hamilton-header-user">${frappe.utils.escape_html(user_name).toUpperCase()}</span>
					</div>
				</div>
				<div class="hamilton-tab-bar">${tab_html}</div>
				<div class="hamilton-content"></div>
				<div class="hamilton-footer"></div>
			</div>
		`);

		// Tab click handler
		this.wrapper.on("click", ".hamilton-tab", (e) => {
			const tab_id = $(e.currentTarget).data("tab");
			if (tab_id !== this.active_tab) {
				this.active_tab = tab_id;
				this.collapse_expanded();
				this.wrapper.find(".hamilton-tab").removeClass("active");
				$(e.currentTarget).addClass("active");
				this.render_active_tab();
			}
		});

		// Click outside to collapse expanded overlay (Decision 2.4)
		$(document).on("click.hamilton-board", (e) => {
			if (this.expanded_asset
				&& !$(e.target).closest(".hamilton-tile, .hamilton-expand-overlay").length) {
				this.collapse_expanded();
			}
		});
	}

	// ── Render the active tab's content + footer ────────────
	render_active_tab() {
		const tab = this.tabs.find((t) => t.id === this.active_tab);
		if (!tab) return;

		const $content = this.wrapper.find(".hamilton-content");

		if (tab.watch) {
			$content.html(this._render_watch_content());
		} else if (tab.placeholder) {
			$content.html(`<div class="hamilton-placeholder">
				${__("No assets configured")} &mdash; ${__("This tab is controlled by venue settings")}
			</div>`);
		} else {
			const tab_assets = this.assets.filter(tab.filter);
			$content.html(this._render_status_sections(tab_assets));
		}

		this._render_footer();
		// _render_tile() now embeds time-state (countdown/overtime) directly,
		// so no post-render mutation pass is needed (V9 Decision 3.1 port).
		this._bind_tile_events();
	}

	// ── Status-sorted sections within a tab ─────────────────
	_render_status_sections(assets) {
		const sections = [
			{ status: "Available", label: __("Available"), cls: "section-available", sort: this._sort_by_code },
			{ status: "Dirty", label: __("Dirty"), cls: "section-dirty", sort: this._sort_by_dirty_time },
			{ status: "Occupied", label: __("Occupied"), cls: "section-occupied", sort: this._sort_by_occupied_time },
			{ status: "Out of Service", label: __("Out of Service"), cls: "section-oos", sort: this._sort_by_oos_time },
		];

		let html = "";
		for (const sec of sections) {
			const sec_assets = assets.filter((a) => a.status === sec.status).sort(sec.sort);
			if (sec_assets.length === 0) continue;
			html += `
				<div class="hamilton-section ${sec.cls}">
					<div class="hamilton-section-header">
						<span class="hamilton-section-dot"></span>
						<span class="hamilton-section-label">${sec.label}</span>
						<span class="hamilton-section-count">${sec_assets.length}</span>
					</div>
					<div class="hamilton-tile-grid">
						${sec_assets.map((a) => this._render_tile(a)).join("")}
					</div>
				</div>
			`;
		}
		return html || `<div class="hamilton-empty">${__("No assets in this tab")}</div>`;
	}

	// ── Watch tab ───────────────────────────────────────────
	// Per V9 Decision 3.2: single overtime state (no warning). Watch tab
	// shows OOS + OVERTIME tiles only. Mockup parallel: isWatched() at
	// V9_CANONICAL_MOCKUP.html line 941.
	_render_watch_content() {
		const attention = [];

		for (const a of this.assets) {
			if (a.status === "Out of Service") {
				attention.push({...a, _watch: "oos"});
			} else if (this._compute_time_status(a) === "overtime") {
				attention.push({...a, _watch: "overtime"});
			}
		}

		if (attention.length === 0) {
			return `<div class="hamilton-watch-empty">
				All clear &#10003; &mdash; ${__("No assets need attention right now")}
			</div>`;
		}

		const overtime = attention.filter((a) => a._watch === "overtime");
		const oos = attention.filter((a) => a._watch === "oos");
		let html = "";

		// Group overtime tiles by category
		if (overtime.length > 0) {
			const groups = {};
			for (const a of overtime) {
				const cat = a.asset_tier || a.asset_category;
				if (!groups[cat]) groups[cat] = [];
				groups[cat].push(a);
			}
			for (const [cat, items] of Object.entries(groups)) {
				items.sort(this._sort_by_occupied_time);
				html += `
					<div class="hamilton-section">
						<div class="hamilton-section-header">
							<span class="hamilton-section-label">${frappe.utils.escape_html(cat)}</span>
							<span class="hamilton-section-count">${items.length}</span>
						</div>
						<div class="hamilton-tile-grid">
							${items.map((a) => this._render_tile(a)).join("")}
						</div>
					</div>
				`;
			}
		}

		// OOS section at bottom
		if (oos.length > 0) {
			oos.sort(this._sort_by_oos_time);
			html += `
				<div class="hamilton-section section-oos">
					<div class="hamilton-section-header">
						<span class="hamilton-section-dot"></span>
						<span class="hamilton-section-label">${__("Out of Service")}</span>
						<span class="hamilton-section-count">${oos.length}</span>
					</div>
					<div class="hamilton-tile-grid">
						${oos.map((a) => this._render_tile(a)).join("")}
					</div>
				</div>
			`;
		}

		return html;
	}

	// ── Single tile ─────────────────────────────────────────
	// Security: every user-facing value is escaped with frappe.utils.escape_html.
	// The test_security_audit.py XSS tests pin this contract by checking the
	// literal string "frappe.utils.escape_html" appears in each interpolation.
	// Port of mockup computeTimeStatus() at V9_CANONICAL_MOCKUP.html line 933.
	// 3-state model (V9 Decision 3.1): null | 'normal' | 'countdown' | 'overtime'.
	// Replaces production's prior 2-state warning/overtime model (which was
	// explicitly REJECTED by Part 10 of decisions_log.md).
	_compute_time_status(asset) {
		if (asset.status !== "Occupied" || !asset.session_start) return null;
		const now = new Date();
		const elapsed_min = (now - new Date(asset.session_start)) / 60000;
		const stay = asset.expected_stay_duration || 360;
		const remaining = stay - elapsed_min;
		if (remaining <= 0) return "overtime";
		if (remaining <= COUNTDOWN_THRESHOLD_MIN) return "countdown";
		return "normal";
	}

	_render_tile(asset) {
		// Port of mockup tileHTML() at V9_CANONICAL_MOCKUP.html line 990.
		// Tile classes: status + (countdown|overtime if applicable). The
		// hamilton-source-tile class for dimming is added separately by
		// _show_overlay() since production renders the overlay as a sibling
		// element rather than re-rendering the whole board.
		const status_cls = `hamilton-status-${asset.status.toLowerCase().replace(/ /g, "-")}`;
		const ts = this._compute_time_status(asset);
		const classes = ["hamilton-tile", status_cls];
		if (ts === "countdown") classes.push("hamilton-countdown");
		if (ts === "overtime") classes.push("hamilton-overtime");

		// Corner badge — only on overtime tiles. V9 Decision 3.4 mandates
		// tab-on-top-border position (corner placement was REJECTED).
		let corner_badge = "";
		if (ts === "overtime") {
			corner_badge = `<span class="hamilton-tile-corner-badge hamilton-corner-ot">OT</span>`;
		}

		// OOS day counter (bottom-right) — V8 addition. Conditional on
		// asset.oos_days being supplied by the API. If backend doesn't
		// enrich, no counter renders (graceful degrade).
		let oos_days_html = "";
		if (asset.status === "Out of Service" && asset.oos_days != null) {
			oos_days_html = `<span class="hamilton-oos-days">${frappe.utils.escape_html(String(asset.oos_days))}d</span>`;
		}

		// Time text on tile — V9 Decision 3.3 wording:
		//   countdown → "Xm left" (red)
		//   overtime  → "Xm late" / "Xh Xm late" (red)
		//   normal    → no text (keeps board quiet)
		let time_html = "";
		if (ts === "countdown") {
			const elapsed_min = (new Date() - new Date(asset.session_start)) / 60000;
			const stay = asset.expected_stay_duration || 360;
			const remaining = Math.max(0, Math.floor(stay - elapsed_min));
			time_html = `<div class="hamilton-tile-time hamilton-countdown">${this._format_minutes(remaining)} left</div>`;
		} else if (ts === "overtime") {
			const elapsed_min = (new Date() - new Date(asset.session_start)) / 60000;
			const stay = asset.expected_stay_duration || 360;
			const over_by = Math.floor(elapsed_min - stay);
			time_html = `<div class="hamilton-tile-time">${this._format_minutes(over_by)} late</div>`;
		}

		return `
			<div class="${classes.join(" ")}"
			     data-asset-name="${frappe.utils.escape_html(asset.name)}"
			     data-status="${frappe.utils.escape_html(asset.status)}">
				${corner_badge}
				<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>
				${time_html}
				${oos_days_html}
			</div>
		`;
	}

	_format_minutes(minutes) {
		// Port of mockup fmtElapsed() at V9_CANONICAL_MOCKUP.html line 947.
		const h = Math.floor(minutes / 60);
		const m = minutes % 60;
		if (h === 0) return `${m}m`;
		return `${h}h ${m}m`;
	}

	// ── Tile expand / collapse ──────────────────────────────
	_bind_tile_events() {
		this.wrapper.off("click.tile").on("click.tile", ".hamilton-tile", (e) => {
			e.stopPropagation();
			const $tile = $(e.currentTarget);
			if ($(e.target).closest(".hamilton-action-btn").length) return;
			const name = $tile.data("asset-name");

			if (this.expanded_asset && this.expanded_asset.name === name) {
				this.collapse_expanded();
				return;
			}

			const asset = this.assets.find((a) => a.name === name);
			if (asset) this._expand_tile(asset, $tile);
		});
	}

	_expand_tile(asset, $tile) {
		this.collapse_expanded();
		this.expanded_asset = asset;
		this._show_overlay(asset, $tile);
	}

	collapse_expanded() {
		this._hide_overlay();
		this.expanded_asset = null;
		this.vacate_subs_open = false;
	}

	// ── Floating overlay primitive (Decision 2.4) ───────────
	// Per decisions_log.md Part 2.4: tap-to-expand renders a separate
	// absolutely-positioned overlay over the source tile, edge-aware
	// clamped to viewport, dismissed by tap outside or scroll. The source
	// tile stays in the grid (dimmed) so its row never stretches.
	//
	// Reference implementation: docs/design/asset_board_mockup_v7.html
	// positionExpandedOverlay() (around line 1283).
	_show_overlay(asset, $tile) {
		$tile.addClass("hamilton-source-tile");
		// Port of mockup expandedOverlayHTML() at
		// docs/design/asset_board_mockup_v7.html line 975+.
		// The overlay echoes the source tile's structure (status class +
		// tile-code) so it reads as "the tile expanded" rather than "a
		// separate panel beside the tile". Action buttons go inside a
		// hamilton-tile-actions wrapper (mockup .tile-actions equivalent).
		// Out-of-scope for this PR (deferred to PR 2/3/5):
		//   - corner badge (.tile-corner-badge.ot) — PR 3
		//   - time-text (.tile-time countdown/overtime) — PR 3
		//   - oos-days counter (.oos-days) — PR 2
		//   - guest-info / oos-info rich panels — PR 2/5
		const status_cls = `hamilton-status-${asset.status.toLowerCase().replace(/ /g, "-")}`;
		const code_html = `<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>`;
		const actions_html = this._render_expand_panel(asset);
		const $overlay = $(
			`<div class="hamilton-expand-overlay hamilton-tile ${status_cls}">
				${code_html}
				<div class="hamilton-tile-actions">${actions_html}</div>
			</div>`
		);
		const $board = this.wrapper.find(".hamilton-board");
		$board.append($overlay);
		this.$overlay = $overlay;

		$overlay.find("[data-action]").on("click.action", (e) => {
			e.stopPropagation();
			const action = $(e.currentTarget).data("action");
			if (action === "oos") {
				this.collapse_expanded();
				this._open_oos_modal(asset);
			} else if (action === "return") {
				this.collapse_expanded();
				this._open_return_modal(asset);
			} else if (action === "vacate-toggle") {
				// V9 Decision 4.6: tap Vacate parent → expand sub-buttons.
				// Tap again ("Cancel Vacate") → collapse them.
				// Re-render the overlay in place to update the button labels.
				this.vacate_subs_open = !this.vacate_subs_open;
				this._redraw_overlay(asset, $tile);
			} else {
				this._run_action(asset, action);
			}
		});

		this._position_overlay($tile, $overlay);

		// Scroll on the asset content area visually detaches the overlay
		// from its source — close on first scroll (V9 M4 in mockup).
		this.wrapper.find(".hamilton-content").on(
			"scroll.hamilton-overlay",
			() => this.collapse_expanded()
		);
	}

	_position_overlay($tile, $overlay) {
		const tile_el = $tile.get(0);
		const overlay_el = $overlay.get(0);
		const board_el = this.wrapper.find(".hamilton-board").get(0);
		if (!tile_el || !overlay_el || !board_el) return;

		const t_rect = tile_el.getBoundingClientRect();
		const b_rect = board_el.getBoundingClientRect();

		// Match overlay width to source tile so the anchor reads consistently
		overlay_el.style.width = t_rect.width + "px";

		// Initial position: directly over the source tile, in board-relative coords
		let x = t_rect.left - b_rect.left;
		let y = t_rect.top - b_rect.top;
		overlay_el.style.left = x + "px";
		overlay_el.style.top = y + "px";

		// Re-measure overlay after it's in the DOM to get content-driven height
		const o_rect = overlay_el.getBoundingClientRect();

		// Edge-aware clamp: shift left/up if the overlay overflows the board
		const padding = 6;
		const overflow_right = o_rect.right - (b_rect.right - padding);
		const overflow_bottom = o_rect.bottom - (b_rect.bottom - padding);
		if (overflow_right > 0) x -= overflow_right;
		if (overflow_bottom > 0) y -= overflow_bottom;
		// Then clamp left/top so we never push off the opposite edge
		if (x < padding) x = padding;
		if (y < padding) y = padding;

		overlay_el.style.left = x + "px";
		overlay_el.style.top = y + "px";
	}

	_hide_overlay() {
		this.wrapper.find(".hamilton-content").off("scroll.hamilton-overlay");
		this.wrapper.find(".hamilton-source-tile").removeClass("hamilton-source-tile");
		if (this.$overlay) {
			this.$overlay.find("[data-action]").off("click.action");
			this.$overlay.remove();
			this.$overlay = null;
		}
		// Clean up any stragglers from the old inline-expand era
		this.wrapper.find(".hamilton-expand-overlay").remove();
	}

	// Re-render the overlay in place without dismissing it. Used when
	// toggling Vacate parent → sub-buttons (V9 Decision 4.6) so the user's
	// tap doesn't close the overlay.
	_redraw_overlay(asset, $tile) {
		// Tear down just the overlay (not the source-tile dim or scroll listener)
		if (this.$overlay) {
			this.$overlay.find("[data-action]").off("click.action");
			this.$overlay.remove();
			this.$overlay = null;
		}
		// Rebuild
		const status_cls = `hamilton-status-${asset.status.toLowerCase().replace(/ /g, "-")}`;
		const code_html = `<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>`;
		const actions_html = this._render_expand_panel(asset);
		const $overlay = $(
			`<div class="hamilton-expand-overlay hamilton-tile ${status_cls}">
				${code_html}
				<div class="hamilton-tile-actions">${actions_html}</div>
			</div>`
		);
		this.wrapper.find(".hamilton-board").append($overlay);
		this.$overlay = $overlay;

		$overlay.find("[data-action]").on("click.action", (e) => {
			e.stopPropagation();
			const action = $(e.currentTarget).data("action");
			if (action === "oos") {
				this.collapse_expanded();
				this._open_oos_modal(asset);
			} else if (action === "return") {
				this.collapse_expanded();
				this._open_return_modal(asset);
			} else if (action === "vacate-toggle") {
				this.vacate_subs_open = !this.vacate_subs_open;
				this._redraw_overlay(asset, $tile);
			} else {
				this._run_action(asset, action);
			}
		});

		this._position_overlay($tile, $overlay);
	}

	_render_expand_panel(asset) {
		let info = "";
		let buttons = "";

		switch (asset.status) {
			case "Available":
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-green" data-action="assign">${__("Assign Guest")}</button>
					<button class="hamilton-action-btn hamilton-btn-grey hamilton-btn-sm" data-action="oos">${__("Set OOS")}</button>
				`;
				break;
			case "Occupied": {
				// V9 Decision (mockup): guest-info panel above Vacate buttons.
				// Mockup parallel: V9_CANONICAL_MOCKUP.html line 1086 (guest-info).
				// Production lacks asset.guest_name; gracefully degrade to elapsed-only.
				let guest_name_html = "";
				if (asset.guest_name) {
					guest_name_html = `<div class="hamilton-guest-name">${frappe.utils.escape_html(asset.guest_name)}</div>`;
				}
				let elapsed_html = "";
				if (asset.session_start) {
					const elapsed = this._format_elapsed(new Date(asset.session_start));
					elapsed_html = `<div class="hamilton-guest-elapsed">${frappe.utils.escape_html(elapsed)} ${__("elapsed")}</div>`;
				}
				if (guest_name_html || elapsed_html) {
					info = `<div class="hamilton-guest-info">${guest_name_html}${elapsed_html}</div>`;
				}
				// V9 Decision 4.6: Vacate parent button \u2192 sub-buttons (Key
				// Return / Rounds). Tap "Vacate" to expand, sub-buttons
				// appear in styled .hamilton-vacate-subs container.
				// Mockup parallel: V9_CANONICAL_MOCKUP.html lines 1090-1097.
				const vacate_subs_class = this.vacate_subs_open
					? "hamilton-vacate-subs hamilton-vacate-subs-shown"
					: "hamilton-vacate-subs";
				const parent_label = this.vacate_subs_open
					? __("Cancel Vacate")
					: __("Vacate");
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-red" data-action="vacate-toggle">${parent_label}</button>
					<div class="${vacate_subs_class}">
						<button class="hamilton-action-btn hamilton-vacate-sub-btn" data-action="vacate-key">${__("Key Return")}</button>
						<button class="hamilton-action-btn hamilton-vacate-sub-btn" data-action="vacate-rounds">${__("Rounds")}</button>
					</div>
				`;
				break;
			}
			case "Dirty":
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-amber" data-action="clean">${__("Mark Clean")}</button>
					<button class="hamilton-action-btn hamilton-btn-grey hamilton-btn-sm" data-action="oos">${__("Set OOS")}</button>
				`;
				break;
			case "Out of Service": {
				// V9 Decision 5.4: tapping OOS tile shows full context
				// (reason + who-set + days-ago) above Return button.
				// Mockup parallel: V9_CANONICAL_MOCKUP.html line 1112 (oos-info).
				// Mockup format: "Set by M. CHEN · 4 days ago"
				const reason = asset.reason
					? frappe.utils.escape_html(asset.reason)
					: __("Reason unknown");
				const days_text = this._format_oos_days_ago(asset);
				const who_text = asset.oos_set_by
					? `${__("by")} ${frappe.utils.escape_html(asset.oos_set_by)}`
					: "";
				// Combinations:
				//   who + days → "Set by M. CHEN · 4 days ago"
				//   who only   → "Set by M. CHEN"
				//   days only  → "Set: 4 days ago"
				//   neither    → omitted
				let meta_text = "";
				if (who_text && days_text) {
					meta_text = `${__("Set")} ${who_text} · ${frappe.utils.escape_html(days_text)}`;
				} else if (who_text) {
					meta_text = `${__("Set")} ${who_text}`;
				} else if (days_text) {
					meta_text = `${__("Set")}: ${frappe.utils.escape_html(days_text)}`;
				}
				const meta_line = meta_text
					? `<div class="hamilton-oos-info-meta">${meta_text}</div>`
					: "";
				info = `
					<div class="hamilton-oos-info">
						<div class="hamilton-oos-info-reason">${reason}</div>
						${meta_line}
					</div>
				`;
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-green" data-action="return">${__("Return to Service")}</button>
				`;
				break;
			}
		}

		// Caller (_show_overlay) wraps in .hamilton-tile-actions per mockup
		// pattern, so this returns inner content only. Mockup parallel:
		// renderActions() returns the inner buttons, expandedOverlayHTML()
		// wraps them in <div class="tile-actions">.
		return `${info}${buttons}`;
	}

	// ── OOS modal (V9 Decisions 5.1, 5.2, S2, S6) ──────────
	// Replaces the prior free-text Frappe Dialog. Mockup parallel:
	// openOOSModal() at V9_CANONICAL_MOCKUP.html line 1405.
	_open_oos_modal(asset) {
		this._close_modals();
		const user = (frappe.boot.user.full_name || frappe.session.user || "").toUpperCase();
		const time_str = this._format_time(new Date());

		const reason_options = OOS_REASONS.map(
			(r) => `<option value="${frappe.utils.escape_html(r)}">${frappe.utils.escape_html(r)}</option>`
		).join("");

		const $modal = $(`
			<div class="hamilton-modal-backdrop hamilton-shown" data-modal="oos">
				<div class="hamilton-oos-modal" onclick="event.stopPropagation()">
					<div class="hamilton-oos-modal-title">${__("Set OOS")}</div>
					<div class="hamilton-oos-modal-asset">${frappe.utils.escape_html(asset.asset_code || asset.name)}</div>
					<label for="hamilton-oos-reason">${__("Reason")}</label>
					<select id="hamilton-oos-reason" class="hamilton-oos-reason-select">
						<option value="">— ${__("Select reason")} —</option>
						${reason_options}
					</select>
					<div class="hamilton-oos-note-wrap hamilton-hidden">
						<div class="hamilton-oos-note-header">
							<label for="hamilton-oos-note">${__('Note (required for "Other")')}</label>
							<button type="button" class="hamilton-oos-note-clear">${__("Clear")}</button>
						</div>
						<textarea id="hamilton-oos-note" placeholder="${__("Describe the issue...")}"></textarea>
					</div>
					<div class="hamilton-modal-audit">
						${__("By confirming, this action will be recorded as:")}<br>
						<strong>${__("Set out of service by")} ${frappe.utils.escape_html(user)} ${__("at")} ${time_str}</strong>
					</div>
					<div class="hamilton-modal-actions">
						<button class="hamilton-modal-btn hamilton-modal-btn-cancel">${__("Cancel")}</button>
						<button class="hamilton-modal-btn hamilton-modal-btn-confirm">${__("Confirm")}</button>
					</div>
				</div>
			</div>
		`);

		this.wrapper.find(".hamilton-board").append($modal);

		const $select = $modal.find(".hamilton-oos-reason-select");
		const $note_wrap = $modal.find(".hamilton-oos-note-wrap");
		const $note = $modal.find("#hamilton-oos-note");

		// V9 S6: toggle the wrapping element so label, textarea, and Clear
		// button all show/hide together.
		$select.on("change", () => {
			if ($select.val() === "Other") {
				$note_wrap.removeClass("hamilton-hidden");
			} else {
				$note_wrap.addClass("hamilton-hidden");
			}
		});

		$modal.find(".hamilton-oos-note-clear").on("click", () => {
			$note.val("").focus();
		});

		// Click backdrop to close
		$modal.on("click", (e) => {
			if (e.target === $modal[0]) this._close_modals();
		});

		$modal.find(".hamilton-modal-btn-cancel").on("click", () => this._close_modals());

		$modal.find(".hamilton-modal-btn-confirm").on("click", async () => {
			const reason_value = $select.val();
			if (!reason_value) {
				frappe.show_alert({message: __("Please select a reason"), indicator: "orange"});
				return;
			}
			let final_reason = reason_value;
			if (reason_value === "Other") {
				const note = ($note.val() || "").trim();
				if (!note) {
					frappe.show_alert({message: __('Note is required for "Other"'), indicator: "orange"});
					return;
				}
				final_reason = `Other: ${note}`;
			}
			this._close_modals();
			await this._run_action(asset, "oos", {reason: final_reason});
		});
	}

	// ── Return-to-Service modal (V9 Decision 5.5) ─────────
	// Mockup parallel: openReturnModal() at V9_CANONICAL_MOCKUP.html line 1445
	// + renderReturnModalBody() at line 1456.
	_open_return_modal(asset) {
		this._close_modals();
		const user = (frappe.boot.user.full_name || frappe.session.user || "").toUpperCase();
		const time_str = this._format_time(new Date());
		const reason = asset.reason || __("Reason unknown");
		const days_text = this._format_oos_days_ago(asset);

		// V9 mockup format: "Set by M. CHEN · 4 days ago" — combined who+when.
		const set_by_who = asset.oos_set_by
			? `${__("by")} ${frappe.utils.escape_html(asset.oos_set_by)}`
			: "";
		let set_value = "";
		if (set_by_who && days_text) {
			set_value = `${set_by_who} · ${frappe.utils.escape_html(days_text)}`;
		} else if (set_by_who) {
			set_value = set_by_who;
		} else if (days_text) {
			set_value = frappe.utils.escape_html(days_text);
		}
		const days_row = set_value
			? `<div class="hamilton-modal-row">
					<span class="hamilton-modal-key">${__("Set")}:</span>
					<span class="hamilton-modal-val">${set_value}</span>
				</div>`
			: "";

		const $modal = $(`
			<div class="hamilton-modal-backdrop hamilton-shown" data-modal="return">
				<div class="hamilton-oos-modal" onclick="event.stopPropagation()">
					<div class="hamilton-oos-modal-title">${__("Return to Service")}</div>
					<div class="hamilton-oos-modal-asset">${frappe.utils.escape_html(asset.asset_code || asset.name)}</div>
					<div class="hamilton-modal-context">
						<div class="hamilton-modal-row">
							<span class="hamilton-modal-key">${__("Reason")}:</span>
							<span class="hamilton-modal-val">${frappe.utils.escape_html(reason)}</span>
						</div>
						${days_row}
					</div>
					<div class="hamilton-modal-audit">
						${__("By confirming, this action will be recorded as:")}<br>
						<strong>${__("Returned to service by")} ${frappe.utils.escape_html(user)} ${__("at")} ${time_str}</strong>
					</div>
					<div class="hamilton-modal-actions">
						<button class="hamilton-modal-btn hamilton-modal-btn-cancel">${__("Cancel")}</button>
						<button class="hamilton-modal-btn hamilton-modal-btn-confirm">${__("Confirm reason resolved")}</button>
					</div>
				</div>
			</div>
		`);

		this.wrapper.find(".hamilton-board").append($modal);

		$modal.on("click", (e) => {
			if (e.target === $modal[0]) this._close_modals();
		});

		$modal.find(".hamilton-modal-btn-cancel").on("click", () => this._close_modals());

		$modal.find(".hamilton-modal-btn-confirm").on("click", async () => {
			this._close_modals();
			// Backend `return_asset_from_oos` API still requires a reason
			// argument. Use a static "Resolved" marker — the audit trail
			// captures the operator + timestamp via Frappe's standard fields.
			await this._run_action(asset, "return", {reason: "Resolved"});
		});
	}

	_close_modals() {
		this.wrapper.find(".hamilton-modal-backdrop").remove();
	}

	_format_oos_days_ago(asset) {
		// V9 mockup uses asset.oosDays + asset.oosSetBy fields. Production
		// derives from asset.hamilton_last_status_change (the asset's own
		// last status change timestamp). If unavailable, returns null and
		// the caller skips rendering the row.
		if (!asset.hamilton_last_status_change) return null;
		const now = new Date();
		const set_at = new Date(asset.hamilton_last_status_change);
		const ms = now - set_at;
		if (isNaN(ms) || ms < 0) return null;
		const days = Math.floor(ms / 86400000);
		if (days <= 0) return __("Today");
		if (days === 1) return __("1 day ago");
		return `${days} ${__("days ago")}`;
	}

	// ── Run action against API — type: "POST" per DEC-058 ──
	async _run_action(asset, action, extra = {}) {
		const api_map = {
			"assign":        {method: "hamilton_erp.api.start_walk_in_session",  args: {asset_name: asset.name}},
			"vacate-key":    {method: "hamilton_erp.api.vacate_asset",           args: {asset_name: asset.name, vacate_method: "Key Return"}},
			"vacate-rounds": {method: "hamilton_erp.api.vacate_asset",           args: {asset_name: asset.name, vacate_method: "Discovery on Rounds"}},
			"clean":         {method: "hamilton_erp.api.clean_asset",            args: {asset_name: asset.name}},
			"oos":           {method: "hamilton_erp.api.set_asset_oos",          args: {asset_name: asset.name, reason: extra.reason}},
			"return":        {method: "hamilton_erp.api.return_asset_from_oos",  args: {asset_name: asset.name, reason: extra.reason}},
		};
		const spec = api_map[action];
		if (!spec) return;

		try {
			await frappe.call({method: spec.method, type: "POST", args: spec.args});
			this.collapse_expanded();
			await this.fetch_board();
			this.render_active_tab();
			this._update_tab_badges();
		} catch (err) {
			frappe.msgprint({
				title: __("Action Failed"),
				message: (err && err.message) || String(err),
				indicator: "red",
			});
		}
	}

	// ── Bulk clean (DEC-054) ────────────────────────────────
	confirm_bulk_clean(category) {
		const dirty = this.assets.filter(
			(a) => a.asset_category === category && a.status === "Dirty"
		);
		if (dirty.length === 0) {
			frappe.show_alert({message: __("No dirty assets to clean"), indicator: "orange"});
			return;
		}
		const list_html = `
			<p>${__("The following {0} assets will be marked clean:", [dirty.length])}</p>
			<ul class="hamilton-bulk-list">
				${dirty.map((a) =>
					`<li><strong>${frappe.utils.escape_html(a.asset_code)}</strong>
					 ${frappe.utils.escape_html(a.asset_name)}</li>`
				).join("")}
			</ul>
		`;
		const d = new frappe.ui.Dialog({
			title: __("Confirm Bulk Mark Clean \u2014 {0}s", [category]),
			fields: [{fieldtype: "HTML", options: list_html}],
			primary_action_label: __("Mark All Clean"),
			primary_action: async () => {
				d.get_primary_btn().prop("disabled", true);
				const method = category === "Room"
					? "hamilton_erp.api.mark_all_clean_rooms"
					: "hamilton_erp.api.mark_all_clean_lockers";
				try {
					const r = await frappe.xcall(method, {});
					frappe.show_alert({
						message: __("{0} cleaned, {1} failed",
							[r.succeeded.length, r.failed.length]),
						indicator: r.failed.length ? "orange" : "green",
					});
					d.hide();
					await this.fetch_board();
					this.render_active_tab();
					this._update_tab_badges();
				} catch (err) {
					frappe.msgprint({
						title: __("Bulk Mark Clean failed"),
						message: (err && err.message) || String(err),
						indicator: "red",
					});
					d.get_primary_btn().prop("disabled", false);
				}
			},
		});
		d.show();
	}

	// ── Footer ──────────────────────────────────────────────
	_render_footer() {
		const tab = this.tabs.find((t) => t.id === this.active_tab);
		const $footer = this.wrapper.find(".hamilton-footer");

		if (!tab || tab.watch || tab.placeholder) {
			$footer.html("");
			return;
		}

		const tab_assets = this.assets.filter(tab.filter);
		const counts = {
			available: tab_assets.filter((a) => a.status === "Available").length,
			dirty: tab_assets.filter((a) => a.status === "Dirty").length,
			occupied: tab_assets.filter((a) => a.status === "Occupied").length,
			oos: tab_assets.filter((a) => a.status === "Out of Service").length,
		};

		const bulk_category = tab.id === "lockers" ? "Locker" : "Room";
		const bulk_btn = counts.dirty > 0
			? `<button class="hamilton-footer-bulk" data-category="${bulk_category}">${__("Mark All Clean")}</button>`
			: "";

		// V9 Decision 6.2: footer shows 3 status counts (Available / Occupied / OOS).
		// Dirty count is tracked but not displayed in the footer per spec \u2014
		// dirty tiles are visible in the section above the footer with their
		// own count. The "Mark All Clean" button still appears when dirty>0.
		$footer.html(`
			<div class="hamilton-footer-counts">
				<span class="hamilton-footer-item">
					<span class="hamilton-footer-dot dot-available"></span>
					${__("Available")} ${counts.available}
				</span>
				<span class="hamilton-footer-item">
					<span class="hamilton-footer-dot dot-occupied"></span>
					${__("Occupied")} ${counts.occupied}
				</span>
				<span class="hamilton-footer-item">
					<span class="hamilton-footer-dot dot-oos"></span>
					${__("OOS")} ${counts.oos}
				</span>
				${bulk_btn}
			</div>
			<div class="hamilton-footer-right">
				<span class="hamilton-footer-hint">${__("Tap to expand \u00b7 Tap outside to close")}</span>
			</div>
		`);

		$footer.find(".hamilton-footer-bulk").on("click", (e) => {
			this.confirm_bulk_clean($(e.currentTarget).data("category"));
		});
	}

	// ── Tab badges ──────────────────────────────────────────
	_update_tab_badges() {
		for (const tab of this.tabs) {
			const $tab = this.wrapper.find(`.hamilton-tab[data-tab="${tab.id}"]`);
			$tab.find(".hamilton-badge").remove();

			if (tab.watch) {
				const count = this.get_watch_count();
				if (count > 0) {
					$tab.append(`<span class="hamilton-badge hamilton-badge-watch">${count}</span>`);
				}
			} else if (!tab.placeholder && !tab.feature_flag) {
				const count = this.get_tab_available_count(tab);
				$tab.append(`<span class="hamilton-badge hamilton-badge-available">${count}</span>`);
			}
		}
	}

	get_tab_available_count(tab) {
		return this.assets.filter(tab.filter).filter((a) => a.status === "Available").length;
	}

	get_watch_count() {
		// Per V9 Decision 3.2: single overtime state (no warning).
		// Watch count = OOS + OVERTIME (not warning, not countdown).
		let count = 0;
		for (const a of this.assets) {
			if (a.status === "Out of Service") {
				count++;
			} else if (this._compute_time_status(a) === "overtime") {
				count++;
			}
		}
		return count;
	}

	// ── Live tick (V9 Decision 3.7) ─────────────────────────
	// Re-render the active tab on a 15s cadence so countdown→overtime
	// transitions surface without user interaction. Skip the tick if an
	// overlay or modal is open so in-flight DOM (form selections, typed
	// notes) is preserved. Mockup parallel: liveTick() at line 1498 of
	// V9_CANONICAL_MOCKUP.html.
	start_overtime_ticker() {
		this.overtime_interval = setInterval(() => {
			// Skip during expanded overlay — the source-tile dim + overlay
			// would be wiped by a re-render and recreated mid-interaction.
			if (this.expanded_asset) return;
			this.render_active_tab();
			this._update_tab_badges();
		}, LIVE_TICK_MS);
	}

	// ── Header clock ────────────────────────────────────────
	start_clock() {
		this.clock_interval = setInterval(() => {
			this.wrapper.find(".hamilton-header-time").text(
				this._format_time(new Date())
			);
		}, 1000);
	}

	// ── Realtime listeners (Task 20) ────────────────────────
	listen_realtime() {
		frappe.realtime.on("hamilton_asset_status_changed",
			(d) => this.apply_status_change(d));
		frappe.realtime.on("hamilton_asset_board_refresh",
			() => this.full_refresh());
	}

	apply_status_change(payload) {
		const local = this.assets.find((a) => a.name === payload.name);
		if (!local) return;
		if (payload.version != null && local.version != null
			&& payload.version <= local.version) return;
		Object.assign(local, payload);
		this.render_active_tab();
		this._update_tab_badges();
	}

	async full_refresh() {
		await this.fetch_board();
		this.render_active_tab();
		this._update_tab_badges();
	}

	// ── Cleanup ─────────────────────────────────────────────
	teardown() {
		if (this.overtime_interval) clearInterval(this.overtime_interval);
		if (this.clock_interval) clearInterval(this.clock_interval);
		$(document).off("click.hamilton-board");
		frappe.realtime.off("hamilton_asset_status_changed");
		frappe.realtime.off("hamilton_asset_board_refresh");
	}

	// ── Sorting helpers ─────────────────────────────────────
	_sort_by_code(a, b) {
		return (a.display_order || 0) - (b.display_order || 0);
	}
	_sort_by_dirty_time(a, b) {
		const ta = a.last_vacated_at ? new Date(a.last_vacated_at) : new Date();
		const tb = b.last_vacated_at ? new Date(b.last_vacated_at) : new Date();
		return ta - tb;
	}
	_sort_by_occupied_time(a, b) {
		const ta = a.session_start ? new Date(a.session_start) : new Date();
		const tb = b.session_start ? new Date(b.session_start) : new Date();
		return ta - tb;
	}
	_sort_by_oos_time(a, b) {
		const ta = a.hamilton_last_status_change ? new Date(a.hamilton_last_status_change) : new Date();
		const tb = b.hamilton_last_status_change ? new Date(b.hamilton_last_status_change) : new Date();
		return ta - tb;
	}

	// ── Format helpers ──────────────────────────────────────
	_format_time(date) {
		return date.toLocaleTimeString("en-US", {
			hour: "2-digit", minute: "2-digit", hour12: true,
		});
	}
	_format_elapsed(start) {
		const diff = Math.floor((new Date() - start) / 60000);
		const h = Math.floor(diff / 60);
		const m = diff % 60;
		return h > 0 ? `${h}h ${m}m` : `${m}m`;
	}

	// V9 Decision 6.1: header shows current shift label.
	// Mockup parallel: STATE.shift static "PM Shift" at line 794. Production
	// derives from current hour as a sensible default until shift_record
	// integration ships.
	_compute_shift_label(date) {
		const hour = date.getHours();
		if (hour >= 6 && hour < 12) return __("AM Shift");
		if (hour >= 12 && hour < 18) return __("PM Shift");
		return __("Night Shift");
	}
};
