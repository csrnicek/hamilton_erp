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
		// Task 17: bind_events, Task 18: popover, Task 19: overtime, Task 20: realtime
	}

	async fetch_board() {
		const r = await frappe.call({
			method: "hamilton_erp.api.get_asset_board_data",
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
			     data-status="${asset.status}">
				<div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>
				<div class="hamilton-tile-name">${frappe.utils.escape_html(asset.asset_name)}</div>
				${tier_short ? `<div class="hamilton-tile-tier">${tier_short}</div>` : ""}
			</div>
		`;
	}
};
