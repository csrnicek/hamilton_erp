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

// V9.1-D11: Ontario HST applied flat to all retail line totals. Single rate,
// no per-item taxability flag (Phase 2). When a venue outside Ontario
// onboards, this becomes a per-venue config in site_config.json.
const HST_RATE = 0.13;

// F1.4 polish — Canadian penny-elimination rule (2013): cash totals round
// to the nearest 0.05. Mirrors the server-side
// frappe.utils.round_based_on_smallest_currency_fraction call applied to
// the post-tax grand_total in submit_retail_sale. Used by the cart drawer
// + cash payment modal so the operator's pre-Confirm preview matches what
// the server will actually charge — without this, a $7.91 cart shows
// "Change $12.09" but the server returns $12.10 and the Confirm gate
// blocks an operator who types $7.90.
function roundToNickel(value) {
	return Math.round(value * 20) / 20;
}

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
		// V9.1 cart state (Phase 2 retail UX, supersedes V9.1-D7).
		// Each line: {item_code, item_name, qty, unit_price}. Unit price
		// is captured at add-to-cart time so drawer math doesn't re-fetch.
		// Per-session JS state only — cart is lost on page reload by design
		// (operators ring up sales atomically; abandonment != continuation).
		this.cart = [];
		// V9.1-D8: drawer collapses to a one-row summary; expands on tap.
		this.cart_expanded = false;
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
		// Asset-category tabs (V9). Watch always renders far right.
		const asset_tabs = [
			{ id: "lockers", label: __("Lockers"), filter: (a) => a.asset_category === "Locker" },
			{ id: "single", label: __("Single"), filter: (a) => a.asset_category === "Room" && (a.asset_tier === "Single Standard" || a.asset_tier === "Deluxe Single") },
			{ id: "double", label: __("Double"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "Double Deluxe" },
			{ id: "vip", label: __("VIP"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "VIP" },
			{ id: "gh-room", label: __("GH Room"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "GH Room" },
			{ id: "waitlist", label: __("Waitlist"), feature_flag: "show_waitlist_tab", placeholder: true },
			{ id: "other", label: __("Other"), feature_flag: "show_other_tab", placeholder: true },
		];
		// V9.1 retail tabs from site_config.retail_tabs. Each Item Group
		// becomes one retail tab. Tab id is "retail-<slug>" so it can't
		// collide with asset tab ids.
		const retail_tabs = (this.retail_tabs || []).map((group_name) => ({
			id: `retail-${group_name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
			label: group_name,
			retail: true,
			item_group: group_name,
			item_filter: (it) => it.item_group === group_name,
		}));
		return [
			...asset_tabs,
			...retail_tabs,
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
		// V9.1 retail amendment — items from configured Item Groups + the
		// per-venue retail_tabs list. Empty for venues without retail config.
		this.items = r.message.items || [];
		this.retail_tabs = r.message.retail_tabs || [];
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
			// V9.1 retail tabs: visible only if their Item Group has at
			// least one Item (combined config + data rule extends to retail).
			if (t.retail) return this.items.some(t.item_filter);
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
			} else if (t.retail) {
				// V9 spec consistency (Amendment 2026-04-29 A29-2): tab badge =
				// available count only. For retail, "available" means in-stock
				// (stock > 0). Out-of-stock SKUs don't count toward the
				// "what can I sell right now?" signal.
				const count = this.items.filter(
					(it) => t.item_filter(it) && Number(it.stock) > 0
				).length;
				badge = `<span class="hamilton-badge hamilton-badge-available">${count}</span>`;
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
				<div class="hamilton-cart-drawer"></div>
				<div class="hamilton-footer"></div>
			</div>
		`);
		this._render_cart_drawer();
		this._bind_cart_events();

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
		} else if (tab.retail) {
			// V9.1 retail tab — render Item tiles instead of asset tiles.
			const tab_items = this.items.filter(tab.item_filter);
			$content.html(this._render_retail_grid(tab_items));
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

		// Time text on tile — V9 Decision 3.3 wording:
		//   countdown → "Xm left" (red)
		//   overtime  → "Xm late" / "Xh Xm late" (red)
		//   dirty     → "Dirty for Xm" (added 2026-04-29 from V9 browser-test
		//               session — helps cleaners prioritize stalest tiles)
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
		} else if (asset.status === "Dirty" && asset.hamilton_last_status_change) {
			const dirty_at = new Date(asset.hamilton_last_status_change);
			const dirty_min = Math.max(0, Math.floor((new Date() - dirty_at) / 60000));
			time_html = `<div class="hamilton-tile-time hamilton-dirty-elapsed">${__("Dirty for")} ${this._format_minutes(dirty_min)}</div>`;
		}

		return `
			<div class="${classes.join(" ")}"
			     data-asset-name="${frappe.utils.escape_html(asset.name)}"
			     data-status="${frappe.utils.escape_html(asset.status)}">
				${corner_badge}
				<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>
				${time_html}
			</div>
		`;
	}

	// ── V9.1 Retail tiles ───────────────────────────────────
	// Per docs/design/V9.1_RETAIL_AMENDMENT.md decisions D5–D7. Retail
	// tiles are READ-ONLY in V9.1 — click does nothing. Cart UX is
	// round-2 work and will define the click behavior.
	_render_retail_grid(items) {
		if (!items || items.length === 0) {
			return `<div class="hamilton-empty">${__("No items in this category")}</div>`;
		}
		return `<div class="hamilton-retail-grid">${items.map((it) => this._render_retail_tile(it)).join("")}</div>`;
	}

	_render_retail_tile(item) {
		// Stock state palette per V9.1-D6:
		//   in stock (>=4) → green (matches asset Available)
		//   low (1-3)      → amber (matches asset Dirty)
		//   out (0)        → red   (matches asset Occupied)
		const stock = Number(item.stock || 0);
		let state_cls = "hamilton-status-available";
		if (stock <= 0) state_cls = "hamilton-status-occupied";
		else if (stock <= 3) state_cls = "hamilton-status-dirty";

		const price = (Number(item.standard_rate) || 0).toFixed(2);
		// V9.1-D9: tap retail tile = add to cart. Show "in cart: N" pill on
		// tiles that already have a line so operators can see what's been
		// added without opening the drawer.
		const in_cart = this._cart_qty_for(item.item_code);
		const cart_pill = in_cart > 0
			? `<span class="hamilton-retail-incart">${__("In cart")} ${in_cart}</span>`
			: "";
		return `
			<div class="hamilton-tile hamilton-retail-tile ${state_cls}"
			     data-item-code="${frappe.utils.escape_html(item.item_code)}"
			     data-stock="${stock}">
				<div class="hamilton-retail-row1">
					<span class="hamilton-retail-code">${frappe.utils.escape_html(item.item_code || "")}</span>
					<span class="hamilton-retail-stock">${stock}</span>
				</div>
				<div class="hamilton-retail-name">${frappe.utils.escape_html(item.item_name || "")}</div>
				<div class="hamilton-retail-price">$${price}</div>
				${cart_pill}
			</div>
		`;
	}

	// ── V9.1 Phase 2 — Cart state machine ──────────────────
	// All cart operations are pure JS state; no realtime, no DB. Drawer
	// rerenders happen via _render_cart_drawer() called by callers.

	_cart_qty_for(item_code) {
		const line = this.cart.find((c) => c.item_code === item_code);
		return line ? line.qty : 0;
	}

	_cart_add(item_code) {
		const item = (this.items || []).find((it) => it.item_code === item_code);
		if (!item) return;
		const existing = this.cart.find((c) => c.item_code === item_code);
		if (existing) {
			existing.qty += 1;
		} else {
			this.cart.push({
				item_code,
				item_name: item.item_name || item_code,
				qty: 1,
				unit_price: Number(item.standard_rate) || 0,
			});
		}
	}

	_cart_set_qty(item_code, qty) {
		qty = Math.max(0, Math.floor(Number(qty) || 0));
		if (qty === 0) {
			this.cart = this.cart.filter((c) => c.item_code !== item_code);
			return;
		}
		const line = this.cart.find((c) => c.item_code === item_code);
		if (line) line.qty = qty;
	}

	_cart_remove(item_code) {
		this.cart = this.cart.filter((c) => c.item_code !== item_code);
	}

	_cart_clear() {
		this.cart = [];
		this.cart_expanded = false;
	}

	_cart_subtotal() {
		return this.cart.reduce((s, c) => s + c.qty * c.unit_price, 0);
	}

	_cart_hst() {
		// V9.1-D11: 13% HST applied to the subtotal. Rounded half-up to
		// 2 decimals at this layer; the Sales Invoice line will recompute
		// when the backend wiring lands.
		return Math.round(this._cart_subtotal() * HST_RATE * 100) / 100;
	}

	_cart_total() {
		return Math.round((this._cart_subtotal() + this._cart_hst()) * 100) / 100;
	}

	_cart_line_count() {
		return this.cart.reduce((s, c) => s + c.qty, 0);
	}

	// ── V9.1 Phase 2 — Cart drawer ──────────────────────────

	_render_cart_drawer() {
		const $drawer = this.wrapper.find(".hamilton-cart-drawer");
		if (!$drawer.length) return;
		const lines = this.cart;
		if (lines.length === 0) {
			// V9.1-D8: drawer hidden entirely when cart is empty.
			$drawer.removeClass("hamilton-cart-shown hamilton-cart-expanded").html("");
			return;
		}
		$drawer.addClass("hamilton-cart-shown");
		if (this.cart_expanded) {
			$drawer.addClass("hamilton-cart-expanded");
		} else {
			$drawer.removeClass("hamilton-cart-expanded");
		}
		const subtotal = this._cart_subtotal().toFixed(2);
		const hst = this._cart_hst().toFixed(2);
		// F1.4: drawer summary shows the nickel-rounded total — matches
		// what the server will charge for cash payments. Without this,
		// the operator's mental math diverges from the rounded total they
		// will actually collect at Confirm.
		const total = roundToNickel(this._cart_total()).toFixed(2);
		const summary = `
			<div class="hamilton-cart-summary">
				<span class="hamilton-cart-count">${this._cart_line_count()} ${__("items")}</span>
				<span class="hamilton-cart-summary-total">$${total}</span>
				<span class="hamilton-cart-toggle">${this.cart_expanded ? "▼" : "▲"}</span>
			</div>
		`;
		const expanded = this.cart_expanded ? `
			<div class="hamilton-cart-body">
				<div class="hamilton-cart-lines">
					${lines.map((c) => `
						<div class="hamilton-cart-line" data-item-code="${frappe.utils.escape_html(c.item_code)}">
							<span class="hamilton-cart-line-name">${frappe.utils.escape_html(c.item_name)}</span>
							<button class="hamilton-cart-qty-btn" data-act="dec">−</button>
							<span class="hamilton-cart-qty">${c.qty}</span>
							<button class="hamilton-cart-qty-btn" data-act="inc">+</button>
							<span class="hamilton-cart-line-total">$${(c.qty * c.unit_price).toFixed(2)}</span>
						</div>
					`).join("")}
				</div>
				<div class="hamilton-cart-totals">
					<div class="hamilton-cart-totals-row"><span>${__("Subtotal")}</span><span>$${subtotal}</span></div>
					<div class="hamilton-cart-totals-row"><span>${__("HST 13%")}</span><span>$${hst}</span></div>
					<div class="hamilton-cart-totals-row hamilton-cart-totals-grand"><span>${__("Total")}</span><span>$${total}</span></div>
				</div>
				<div class="hamilton-cart-actions">
					<button class="hamilton-cart-clear">${__("Clear")}</button>
					<button class="hamilton-cart-pay">${__("Cash payment")}</button>
				</div>
			</div>
		` : "";
		$drawer.html(summary + expanded);
	}

	_bind_cart_events() {
		this.wrapper.off("click.cart")
			.on("click.cart", ".hamilton-cart-summary", () => {
				this.cart_expanded = !this.cart_expanded;
				this._render_cart_drawer();
			})
			.on("click.cart", ".hamilton-cart-qty-btn", (e) => {
				e.stopPropagation();
				const $line = $(e.currentTarget).closest(".hamilton-cart-line");
				const code = $line.data("item-code");
				const act = $(e.currentTarget).data("act");
				const cur = this._cart_qty_for(code);
				this._cart_set_qty(code, act === "inc" ? cur + 1 : cur - 1);
				this._render_cart_drawer();
				if (this.active_tab && this.active_tab.startsWith("retail-")) {
					this.render_active_tab();
				}
			})
			.on("click.cart", ".hamilton-cart-clear", (e) => {
				e.stopPropagation();
				this._cart_clear();
				this._render_cart_drawer();
				if (this.active_tab && this.active_tab.startsWith("retail-")) {
					this.render_active_tab();
				}
			})
			.on("click.cart", ".hamilton-cart-pay", (e) => {
				e.stopPropagation();
				this._open_cash_payment_modal();
			});
	}

	// ── V9.1 Phase 2 — Cash payment modal ──────────────────
	// V9.1-D12 (revised 2026-04-30): cash-only single tender, real Sales
	// Invoice creation. Confirm calls submit_retail_sale on the backend,
	// which builds + submits a POS Sales Invoice (is_pos=1, update_stock=1)
	// against the "Hamilton Front Desk" POS Profile. Stock decrements
	// automatically via the Stock Ledger Entry that submission generates.
	_open_cash_payment_modal() {
		this._close_modals();
		// F1.4: modal shows the nickel-rounded total — what the customer
		// actually pays for a Cash sale. The unrounded grand_total is
		// visible to the server (computed in submit_retail_sale and
		// returned in the response), but the operator's pre-Confirm view
		// matches the post-Confirm reality.
		const total = roundToNickel(this._cart_total()).toFixed(2);
		const $modal = $(`
			<div class="hamilton-modal-backdrop hamilton-shown" data-modal="cash">
				<div class="hamilton-oos-modal hamilton-cash-modal" onclick="event.stopPropagation()">
					<div class="hamilton-oos-modal-title">${__("Cash payment")}</div>
					<div class="hamilton-modal-context">
						<div class="hamilton-modal-row">
							<span class="hamilton-modal-key">${__("Total")}:</span>
							<span class="hamilton-modal-val">$${total}</span>
						</div>
						<div class="hamilton-modal-row">
							<span class="hamilton-modal-key">${__("Cash received")}:</span>
							<input type="number" step="0.01" min="0"
							       class="hamilton-cash-received" placeholder="${total}">
						</div>
						<div class="hamilton-modal-row hamilton-cash-change-row" style="display:none">
							<span class="hamilton-modal-key">${__("Change")}:</span>
							<span class="hamilton-modal-val hamilton-cash-change">$0.00</span>
						</div>
					</div>
					<div class="hamilton-modal-actions">
						<button class="hamilton-modal-btn hamilton-modal-btn-cancel">${__("Cancel")}</button>
						<button class="hamilton-modal-btn hamilton-modal-btn-confirm" disabled>${__("Confirm")}</button>
					</div>
				</div>
			</div>
		`);
		this.wrapper.find(".hamilton-board").append($modal);

		const $received = $modal.find(".hamilton-cash-received");
		const $changeRow = $modal.find(".hamilton-cash-change-row");
		const $change = $modal.find(".hamilton-cash-change");
		const $confirm = $modal.find(".hamilton-modal-btn-confirm");
		$received.on("input", () => {
			const got = Number($received.val()) || 0;
			// F1.4: Confirm gate + change preview both use the
			// nickel-rounded due so an operator who types the actual
			// rounded amount (e.g. $7.90 on a $7.91 cart) gets Confirm
			// enabled — matches the server's rounded amount_due.
			const due = roundToNickel(this._cart_total());
			if (got >= due) {
				$change.text(`$${(got - due).toFixed(2)}`);
				$changeRow.show();
				$confirm.prop("disabled", false);
			} else {
				$changeRow.hide();
				$confirm.prop("disabled", true);
			}
		});
		$modal.on("click", (e) => { if (e.target === $modal[0]) this._close_modals(); });
		$modal.find(".hamilton-modal-btn-cancel").on("click", () => this._close_modals());
		$modal.find(".hamilton-modal-btn-confirm").on("click", () => {
			const cash_received = Number($received.val()) || 0;
			// Snapshot cart before clearing — needed for the API payload
			// and to restore on error so the operator doesn't lose work.
			const cart_snapshot = this.cart.map((c) => ({
				item_code: c.item_code,
				qty: c.qty,
				unit_price: c.unit_price,
			}));
			$confirm.prop("disabled", true).text(__("Processing..."));
			frappe.xcall("hamilton_erp.api.submit_retail_sale", {
				items: cart_snapshot,
				cash_received: cash_received,
			}).then((result) => {
				this._close_modals();
				this._cart_clear();
				this._render_cart_drawer();
				const change_str = (result.change || 0).toFixed(2);
				frappe.show_alert({
					message: __("Sale {0} — change ${1}", [result.sales_invoice, change_str]),
					indicator: "green",
				}, 5);
				// Refresh board so retail tile stock counts update.
				this.fetch_board();
			}).catch((err) => {
				$confirm.prop("disabled", false).text(__("Confirm"));
				const msg = (err && err.message) ? err.message : String(err);
				frappe.show_alert({
					message: __("Sale failed: {0}", [msg]),
					indicator: "red",
				}, 7);
				// Cart intentionally NOT cleared — operator can retry.
			});
		});
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

			// V9.1-D9 (supersedes D7): retail tile click adds 1 to cart.
			// The drawer + tile pill rerender to reflect the new line.
			if ($tile.hasClass("hamilton-retail-tile")) {
				const item_code = $tile.data("item-code");
				if (!item_code) return;
				const stock = Number($tile.data("stock") || 0);
				if (stock <= 0) {
					frappe.show_alert({
						message: __("Out of stock"),
						indicator: "red",
					});
					return;
				}
				this._cart_add(item_code);
				this._render_cart_drawer();
				this.render_active_tab();  // refreshes tile in-cart pill
				return;
			}

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
				//
				// Finding #5 (DEC-071): on the Watch tab, skip the parent
				// "Vacate" toggle and surface Key Return / Rounds inline.
				// Watch tab tiles are by definition overtime/OOS attention
				// items \u2014 operators shouldn't have to two-tap their way to
				// the action they came here to perform.
				if (this.active_tab === "watch") {
					buttons = `
						<button class="hamilton-action-btn hamilton-btn-red" data-action="vacate-rounds">${__("Vacate (Rounds)")}</button>
						<button class="hamilton-action-btn hamilton-btn-red" data-action="vacate-key">${__("Vacate (Key Return)")}</button>
					`;
				} else {
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
				}
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
		// Per browser-test 2026-04-29: include time-of-day to match the OOS
		// audit format ("by NAME at HH:MM AM/PM"). hamilton_last_status_change
		// is always populated by every state transition, so the timestamp
		// renders even when the days-ago row would be empty.
		const set_at_time = this._format_oos_set_time(asset);
		const who_part = asset.oos_set_by
			? `${__("by")} ${frappe.utils.escape_html(asset.oos_set_by)}`
			: "";
		const time_part = set_at_time
			? `${__("at")} ${frappe.utils.escape_html(set_at_time)}`
			: "";
		const who_time = [who_part, time_part].filter(Boolean).join(" ");
		let set_value = "";
		if (who_time && days_text) {
			set_value = `${who_time} · ${frappe.utils.escape_html(days_text)}`;
		} else if (who_time) {
			set_value = who_time;
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

	_format_oos_set_time(asset) {
		// Time-of-day the asset entered its current OOS state, taken from
		// hamilton_last_status_change. Used by the RTS modal SET line to
		// match the OOS audit format ("by NAME at HH:MM AM/PM"). Returns
		// null when the timestamp is missing or unparseable.
		if (!asset.hamilton_last_status_change) return null;
		const set_at = new Date(asset.hamilton_last_status_change);
		if (isNaN(set_at.getTime())) return null;
		return this._format_time(set_at);
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

	// Bulk Mark All Clean was REMOVED 2026-04-29 (DEC-054 reversed). Cleaning
	// happens per-tile via the Dirty tile's expand-overlay "Mark Clean" action.

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

		// V9 Decision 6.2: footer shows 3 status counts (Available / Occupied /
		// OOS). Dirty count is tracked but not displayed in the footer per
		// spec \u2014 dirty tiles are visible in the section above the footer
		// with their own count.
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
			</div>
			<div class="hamilton-footer-right">
				<span class="hamilton-footer-hint">${__("Tap to expand \u00b7 Tap outside to close")}</span>
			</div>
		`);
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
			} else if (tab.retail) {
				const count = this.get_retail_in_stock_count(tab);
				$tab.append(`<span class="hamilton-badge hamilton-badge-available">${count}</span>`);
			} else if (!tab.placeholder && !tab.feature_flag) {
				const count = this.get_tab_available_count(tab);
				$tab.append(`<span class="hamilton-badge hamilton-badge-available">${count}</span>`);
			}
		}
	}

	get_tab_available_count(tab) {
		return this.assets.filter(tab.filter).filter((a) => a.status === "Available").length;
	}

	get_retail_in_stock_count(tab) {
		// V9 spec consistency (Amendment 2026-04-29 A29-2): tab badge counts
		// only items operators can sell right now. Retail equivalent of
		// "Available" is "stock > 0".
		return this.items.filter(
			(it) => tab.item_filter(it) && Number(it.stock) > 0
		).length;
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
