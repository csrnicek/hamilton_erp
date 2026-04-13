frappe.provide("hamilton_erp");

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
		this.overtime_interval = null;
		this.init();
	}

	async init() {
		this.wrapper.html(`<div class="hamilton-loading">${__("Loading...")}</div>`);
		await this.fetch_board();
		this.render();
		this.bind_events();
		this.start_overtime_ticker();
		this.page.wrapper.on("page-destroyed", () => this.teardown());
		// Task 20: realtime
	}

	async fetch_board() {
		// type: "GET" is mandatory. api.get_asset_board_data is decorated
		// @frappe.whitelist(methods=["GET"]) — frappe.call defaults to POST
		// when type is omitted, and that mismatch produces a 403
		// "Not permitted" in every browser session while curl (which
		// defaults to GET) reports 200. See DEC-058 and the regression
		// test test_get_asset_board_data_http_verb in test_api_phase1.py.
		const r = await frappe.call({
			method: "hamilton_erp.api.get_asset_board_data",
			type: "GET",
			freeze: true,
			freeze_message: __("Loading board..."),
		});
		this.assets = r.message.assets;
		this.settings = r.message.settings;
	}

	render() {
		const rooms = this.assets.filter((a) => a.asset_category === "Room");
		const lockers = this.assets.filter((a) => a.asset_category === "Locker");
		const tierOrder = ["Single Standard", "Deluxe Single", "Glory Hole", "Double Deluxe"];

		const room_groups = tierOrder
			.map((tier) => {
				const tier_assets = rooms.filter((a) => a.asset_tier === tier);
				if (tier_assets.length === 0) return "";
				return `
					<div class="hamilton-tier-group">
						<h4 class="hamilton-tier-label">${frappe.utils.escape_html(tier)}</h4>
						<div class="hamilton-tier-grid">
							${tier_assets.map((a) => this.render_tile(a)).join("")}
						</div>
					</div>
				`;
			})
			.join("");

		const locker_tiles = lockers.map((a) => this.render_tile(a)).join("");

		this.wrapper.html(`
			<div class="hamilton-asset-board">
				<section class="hamilton-zone hamilton-zone-rooms">
					<div class="hamilton-zone-header">
						<h3>${__("Rooms")}</h3>
						<button class="btn btn-default btn-sm hamilton-bulk-rooms">
							${__("Mark All Dirty Rooms Clean")}
						</button>
					</div>
					${room_groups}
				</section>
				<section class="hamilton-zone hamilton-zone-lockers">
					<div class="hamilton-zone-header">
						<h3>${__("Lockers")}</h3>
						<button class="btn btn-default btn-sm hamilton-bulk-lockers">
							${__("Mark All Dirty Lockers Clean")}
						</button>
					</div>
					<div class="hamilton-tier-grid">${locker_tiles}</div>
				</section>
			</div>
		`);
	}

	render_tile(asset) {
		// Status is constrained by Venue Asset's Select field, but we still
		// escape every user-facing value here as defense-in-depth. The audit
		// test in test_security_audit.py pins this contract — if any of
		// asset_name, asset_code, or status is interpolated without
		// frappe.utils.escape_html, that test fails.
		const status_class = `hamilton-status-${asset.status.toLowerCase().replace(/ /g, "-")}`;
		const tier_short = asset.asset_tier === "Single Standard" ? "STD"
			: asset.asset_tier === "Deluxe Single" ? "DLX"
			: asset.asset_tier === "Glory Hole" ? "GH"
			: asset.asset_tier === "Double Deluxe" ? "2DLX"
			: asset.asset_tier === "Locker" ? "" : asset.asset_tier;
		return `
			<div class="hamilton-tile ${status_class}"
			     data-asset-name="${frappe.utils.escape_html(asset.name)}"
			     data-asset-code="${frappe.utils.escape_html(asset.asset_code || "")}"
			     data-status="${frappe.utils.escape_html(asset.status)}">
				<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>
				<div class="hamilton-tile-name">${frappe.utils.escape_html(asset.asset_name)}</div>
				${tier_short ? `<div class="hamilton-tile-tier">${tier_short}</div>` : ""}
			</div>
		`;
	}

	bind_events() {
		this.wrapper.on("click", ".hamilton-tile", (e) => {
			const name = $(e.currentTarget).data("asset-name");
			const asset = this.assets.find((a) => a.name === name);
			if (asset) this.open_popover(asset, e.currentTarget);
		});
		this.wrapper.on("click", ".hamilton-bulk-rooms", () =>
			this.confirm_bulk_clean("Room"));
		this.wrapper.on("click", ".hamilton-bulk-lockers", () =>
			this.confirm_bulk_clean("Locker"));
		// Dismiss popover on outside click
		$(document).on("click.hamilton-popover", (e) => {
			if (!$(e.target).closest(".hamilton-tile, .hamilton-popover").length) {
				this.close_popover();
			}
		});
	}

	close_popover() {
		$(".hamilton-popover").remove();
	}

	open_popover(asset, tile_el) {
		this.close_popover();
		const buttons = this.popover_buttons_for(asset);
		const $pop = $(`
			<div class="hamilton-popover" data-asset-name="${frappe.utils.escape_html(asset.name)}">
				<div class="hamilton-popover-header">
					<strong>${frappe.utils.escape_html(asset.asset_name)}</strong>
					<a class="hamilton-popover-info"
					   href="/app/venue-asset/${encodeURIComponent(asset.name)}"
					   target="_blank" rel="noopener">
					   <i class="fa fa-info-circle"></i>
					</a>
				</div>
				<div class="hamilton-popover-actions">
					${buttons}
				</div>
				<div class="hamilton-popover-reason" style="display:none;">
					<textarea class="form-control" rows="2"
					          placeholder="${__("Reason (required)")}"></textarea>
					<button class="btn btn-primary btn-sm hamilton-popover-confirm">
						${__("Confirm")}
					</button>
				</div>
				<div class="hamilton-popover-error" style="display:none;"></div>
			</div>
		`);
		$(tile_el).append($pop);
		this.wire_popover_actions($pop, asset);
	}

	popover_buttons_for(asset) {
		switch (asset.status) {
			case "Available":
				return `
					<button class="btn btn-sm btn-success" data-action="assign">
						${__("Assign Occupant")}
					</button>
					<button class="btn btn-sm btn-danger" data-action="oos">
						${__("Set Out of Service")}
					</button>
				`;
			case "Occupied":
				return `
					<button class="btn btn-sm btn-primary" data-action="vacate-key">
						${__("Vacate — Key Return")}
					</button>
					<button class="btn btn-sm btn-warning" data-action="vacate-rounds">
						${__("Vacate — Discovery on Rounds")}
					</button>
					<button class="btn btn-sm btn-danger" data-action="oos">
						${__("Set Out of Service")}
					</button>
				`;
			case "Dirty":
				return `
					<button class="btn btn-sm btn-success" data-action="clean">
						${__("Mark Clean")}
					</button>
					<button class="btn btn-sm btn-danger" data-action="oos">
						${__("Set Out of Service")}
					</button>
				`;
			case "Out of Service":
				return `
					<button class="btn btn-sm btn-success" data-action="return">
						${__("Return to Service")}
					</button>
				`;
			default:
				return "";
		}
	}

	wire_popover_actions($pop, asset) {
		const self = this;
		$pop.on("click", "[data-action]", function (e) {
			e.stopPropagation();
			const action = $(this).data("action");
			if (action === "oos" || action === "return") {
				$pop.find(".hamilton-popover-actions").hide();
				$pop.find(".hamilton-popover-reason").show();
				$pop.find("textarea").focus();
				$pop.data("pending-action", action);
			} else {
				self.run_action(asset, action, $pop);
			}
		});
		$pop.on("click", ".hamilton-popover-confirm", function (e) {
			e.stopPropagation();
			const reason = $pop.find("textarea").val().trim();
			if (!reason) {
				self.show_popover_error($pop, __("Reason is required"));
				return;
			}
			const action = $pop.data("pending-action");
			self.run_action(asset, action, $pop, {reason});
		});
	}

	async run_action(asset, action, $pop, extra = {}) {
		const api_map = {
			"assign":        {method: "hamilton_erp.api.start_walk_in_session",    args: {asset_name: asset.name}},
			"vacate-key":    {method: "hamilton_erp.api.vacate_asset",             args: {asset_name: asset.name, vacate_method: "Key Return"}},
			"vacate-rounds": {method: "hamilton_erp.api.vacate_asset",             args: {asset_name: asset.name, vacate_method: "Discovery on Rounds"}},
			"clean":         {method: "hamilton_erp.api.clean_asset",              args: {asset_name: asset.name}},
			"oos":           {method: "hamilton_erp.api.set_asset_oos",            args: {asset_name: asset.name, reason: extra.reason}},
			"return":        {method: "hamilton_erp.api.return_asset_from_oos",    args: {asset_name: asset.name, reason: extra.reason}},
		};
		const spec = api_map[action];
		if (!spec) return;
		$pop.find("button").prop("disabled", true);
		try {
			await frappe.call({
				method: spec.method,
				type: "POST",
				args: spec.args,
			});
			this.close_popover();
			// Refresh the board to reflect the new state
			await this.fetch_board();
			this.render();
		} catch (err) {
			const msg = (err && err.message) || __("Action failed");
			this.show_popover_error($pop, msg);
			$pop.find("button").prop("disabled", false);
		}
	}

	show_popover_error($pop, msg) {
		$pop.find(".hamilton-popover-error").text(msg).show();
	}

	// ── Task 21: Bulk Mark Clean confirmation dialog (DEC-054) ──
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
			title: __("Confirm Bulk Mark Clean — {0}", [category]),
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
					if (r.failed.length) {
						console.warn("Bulk Mark Clean failures:", r.failed);
					}
					d.hide();
					await this.fetch_board();
					this.render();
					this.refresh_overtime_overlays();
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

	// ── Task 19: Overtime ticker (2-stage visual) ──────────────
	start_overtime_ticker() {
		this.overtime_interval = setInterval(() => this.refresh_overtime_overlays(), 30_000);
		this.refresh_overtime_overlays();
	}

	refresh_overtime_overlays() {
		const grace = this.settings.grace_minutes || 15;
		const now = new Date();
		for (const asset of this.assets) {
			if (asset.status !== "Occupied" || !asset.session_start) continue;
			const start = new Date(asset.session_start);
			const elapsed_min = (now - start) / 60000;
			const stay = asset.expected_stay_duration || 360;
			const $tile = this.wrapper.find(
				`.hamilton-tile[data-asset-name="${$.escapeSelector(asset.name)}"]`
			);
			$tile.removeClass("hamilton-warning hamilton-overtime");
			$tile.find(".hamilton-time-badge").remove();
			if (elapsed_min > stay + grace) {
				$tile.addClass("hamilton-overtime");
				const over_min = Math.floor(elapsed_min - stay);
				$tile.append(
					`<div class="hamilton-time-badge hamilton-badge-ot">OT +${over_min}m</div>`
				);
			} else if (elapsed_min > stay) {
				$tile.addClass("hamilton-warning");
				const over_min = Math.floor(elapsed_min - stay);
				$tile.append(
					`<div class="hamilton-time-badge hamilton-badge-warn">⏱ +${over_min}m</div>`
				);
			}
		}
	}

	teardown() {
		if (this.overtime_interval) clearInterval(this.overtime_interval);
		$(document).off("click.hamilton-popover");
	}
};
