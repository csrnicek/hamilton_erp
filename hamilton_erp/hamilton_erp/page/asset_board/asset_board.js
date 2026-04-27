frappe.provide("hamilton_erp");
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
		this.overtime_interval = null;
		this.clock_interval = null;
		this.init();
	}

	// Tab definitions — order matches V6 spec: docs/design/asset_board_ui.md
	get tabs() {
		return [
			{ id: "lockers", label: __("Lockers"), filter: (a) => a.asset_category === "Locker" },
			{ id: "single", label: __("Single"), filter: (a) => a.asset_category === "Room" && (a.asset_tier === "Single Standard" || a.asset_tier === "Deluxe Single") },
			{ id: "double", label: __("Double"), filter: (a) => a.asset_category === "Room" && a.asset_tier === "Double Deluxe" },
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
		const visible_tabs = this.tabs.filter((t) => {
			if (t.feature_flag) return this.settings[t.feature_flag];
			return true;
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

		this.wrapper.html(`
			<div class="hamilton-board">
				<div class="hamilton-header">
					<div class="hamilton-header-left">
						<span class="hamilton-header-venue">CLUB HAMILTON</span>
						<span class="hamilton-header-sep">&middot;</span>
						<span class="hamilton-header-title">ASSET BOARD</span>
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

		// Click outside to collapse expanded tile
		$(document).on("click.hamilton-board", (e) => {
			if (this.expanded_asset
				&& !$(e.target).closest(".hamilton-tile, .hamilton-expand-panel").length) {
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
		this.refresh_overtime_overlays();
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
	_render_watch_content() {
		const now = new Date();
		const grace = this.settings.grace_minutes || 15;
		const attention = [];

		for (const a of this.assets) {
			if (a.status === "Out of Service") {
				attention.push({...a, _watch: "oos"});
			} else if (a.status === "Occupied" && a.session_start) {
				const elapsed = (now - new Date(a.session_start)) / 60000;
				const stay = a.expected_stay_duration || 360;
				if (elapsed > stay + grace) {
					attention.push({...a, _watch: "overtime"});
				} else if (elapsed > stay) {
					attention.push({...a, _watch: "warning"});
				}
			}
		}

		if (attention.length === 0) {
			return `<div class="hamilton-watch-empty">
				All clear &#10003; &mdash; ${__("No assets need attention right now")}
			</div>`;
		}

		const warn_ot = attention.filter((a) => a._watch !== "oos");
		const oos = attention.filter((a) => a._watch === "oos");
		let html = "";

		// Group warning/overtime by category
		if (warn_ot.length > 0) {
			const groups = {};
			for (const a of warn_ot) {
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
	_render_tile(asset) {
		const status_cls = `hamilton-status-${asset.status.toLowerCase().replace(/ /g, "-")}`;
		return `
			<div class="hamilton-tile ${status_cls}"
			     data-asset-name="${frappe.utils.escape_html(asset.name)}"
			     data-status="${frappe.utils.escape_html(asset.status)}">
				<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>
			</div>
		`;
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
		$tile.addClass("hamilton-expanded");
		$tile.append(this._render_expand_panel(asset));

		$tile.find("[data-action]").on("click.action", (e) => {
			e.stopPropagation();
			const action = $(e.currentTarget).data("action");
			if (action === "oos" || action === "return") {
				this._prompt_reason(asset, action);
			} else {
				this._run_action(asset, action);
			}
		});
	}

	collapse_expanded() {
		this.wrapper.find(".hamilton-tile.hamilton-expanded").removeClass("hamilton-expanded");
		this.wrapper.find(".hamilton-expand-panel").remove();
		this.expanded_asset = null;
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
			case "Occupied":
				if (asset.session_start) {
					info = `<div class="hamilton-expand-info">${this._format_elapsed(new Date(asset.session_start))}</div>`;
				}
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-red" data-action="vacate-key">${__("Vacate \u2014 Key Return")}</button>
					<button class="hamilton-action-btn hamilton-btn-red" data-action="vacate-rounds">${__("Vacate \u2014 Rounds")}</button>
				`;
				break;
			case "Dirty":
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-amber" data-action="clean">${__("Mark Clean")}</button>
					<button class="hamilton-action-btn hamilton-btn-grey hamilton-btn-sm" data-action="oos">${__("Set OOS")}</button>
				`;
				break;
			case "Out of Service":
				buttons = `
					<button class="hamilton-action-btn hamilton-btn-green" data-action="return">${__("Return to Service")}</button>
				`;
				break;
		}

		return `<div class="hamilton-expand-panel">${info}${buttons}</div>`;
	}

	// ── Reason prompt for OOS / Return ──────────────────────
	_prompt_reason(asset, action) {
		const title = action === "oos"
			? __("Set OOS")
			: __("Return to Service");
		const d = new frappe.ui.Dialog({
			title: title,
			fields: [{
				fieldtype: "Small Text",
				fieldname: "reason",
				label: __("Reason"),
				reqd: 1,
			}],
			primary_action_label: __("Confirm"),
			primary_action: (values) => {
				d.hide();
				this._run_action(asset, action, {reason: values.reason});
			},
		});
		d.show();
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

		$footer.html(`
			<div class="hamilton-footer-counts">
				<span class="hamilton-footer-item">
					<span class="hamilton-footer-dot dot-available"></span>
					${__("Available")} ${counts.available}
				</span>
				<span class="hamilton-footer-item">
					<span class="hamilton-footer-dot dot-dirty"></span>
					${__("Dirty")} ${counts.dirty}
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
		const now = new Date();
		const grace = this.settings.grace_minutes || 15;
		let count = 0;
		for (const a of this.assets) {
			if (a.status === "Out of Service") {
				count++;
			} else if (a.status === "Occupied" && a.session_start) {
				const elapsed = (now - new Date(a.session_start)) / 60000;
				const stay = a.expected_stay_duration || 360;
				if (elapsed > stay) count++;
			}
		}
		return count;
	}

	// ── Overtime ticker (Task 19) ───────────────────────────
	start_overtime_ticker() {
		this.overtime_interval = setInterval(() => {
			this.refresh_overtime_overlays();
			this._update_tab_badges();
		}, 30_000);
	}

	refresh_overtime_overlays() {
		const grace = this.settings.grace_minutes || 15;
		const now = new Date();
		for (const asset of this.assets) {
			const $tile = this.wrapper.find(
				`.hamilton-tile[data-asset-name="${$.escapeSelector(asset.name)}"]`
			);
			if (!$tile.length) continue;

			$tile.removeClass("hamilton-warning hamilton-overtime");
			$tile.find(".hamilton-time-badge").remove();

			if (asset.status !== "Occupied" || !asset.session_start) continue;

			const start = new Date(asset.session_start);
			const elapsed_min = (now - start) / 60000;
			const stay = asset.expected_stay_duration || 360;

			if (elapsed_min > stay + grace) {
				$tile.addClass("hamilton-overtime");
				const over = Math.floor(elapsed_min - stay);
				$tile.append(`<div class="hamilton-time-badge badge-ot">${over}m late</div>`);
			} else if (elapsed_min > stay) {
				$tile.addClass("hamilton-warning");
				const over = Math.floor(elapsed_min - stay);
				$tile.append(`<div class="hamilton-time-badge badge-warn">&#9201; ${over}m late</div>`);
			}
		}
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
};
