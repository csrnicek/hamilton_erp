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
		// Task 17 expands this. For the scaffold, just show the asset count.
		this.wrapper.html(
			`<div class="hamilton-asset-board">
				<p>${this.assets.length} ${__("assets loaded")}</p>
			</div>`
		);
	}
};
