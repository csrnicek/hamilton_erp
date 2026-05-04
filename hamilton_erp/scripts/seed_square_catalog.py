#!/usr/bin/env python3
"""Seed ERPNext Items from Square catalog export.

Usage:
    bench --site hamilton-test.localhost execute hamilton_erp.scripts.seed_square_catalog.seed_items

Reads the Square catalog CSV from ~/Downloads/ and creates ERPNext Item records with:
- CAD currency
- 13% HST Ontario tax template
- Item groups mapped from Square categories
- Standard rates from Square prices

Skips items that already exist (by item_code).
"""
import csv
import os
from pathlib import Path

import frappe
from frappe import _


def seed_items():
	"""Seed ERPNext Items from Square catalog CSV."""
	csv_path = Path.home() / "Downloads" / "B29AXT4K4428E_catalog-2026-05-04-1602.csv"

	if not csv_path.exists():
		frappe.throw(_("CSV file not found at {0}").format(csv_path))

	# Ensure HST tax template exists
	_ensure_hst_tax_template()

	# Ensure Item Groups exist
	_ensure_item_groups()

	created_count = 0
	skipped_count = 0
	error_count = 0

	with open(csv_path, "r", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			# Skip empty rows
			if not row.get("Token"):
				continue

			item_code = _generate_item_code(row)

			# Skip if item already exists
			if frappe.db.exists("Item", item_code):
				print(f"Skipping existing item: {item_code}")
				skipped_count += 1
				continue

			try:
				_create_item_from_row(row, item_code)
				created_count += 1
				print(f"Created item: {item_code} - {row['Item Name']}")
			except Exception as exc:
				error_count += 1
				print(f"Error creating item {item_code}: {exc}")
				frappe.log_error(
					title=f"Square catalog seed error: {item_code}",
					message=f"Row: {row}\n\nError: {exc}"
				)

	frappe.db.commit()

	summary = f"""
Square catalog seed complete:
- Created: {created_count}
- Skipped (already exist): {skipped_count}
- Errors: {error_count}
- Total rows processed: {created_count + skipped_count + error_count}
	"""
	print(summary)
	return summary


def _generate_item_code(row: dict) -> str:
	"""Generate ERPNext item_code from Square row.

	Uses Square Token as the unique identifier, prefixed with HAM- for Hamilton.
	"""
	token = row["Token"].strip()
	return f"HAM-{token}"


def _create_item_from_row(row: dict, item_code: str):
	"""Create an ERPNext Item from a Square catalog row."""
	item_name = row["Item Name"].strip()
	variation = row.get("Variation Name", "").strip()

	# Construct full name (Item Name + Variation if present)
	if variation and variation != "Regular":
		full_name = f"{item_name} - {variation}"
	else:
		full_name = item_name

	# Map category to Item Group
	item_group = _map_item_group(row.get("Categories", ""))

	# Parse price
	price_str = row.get("Price", "").strip()
	if price_str == "variable" or not price_str:
		standard_rate = 0.0
	else:
		try:
			standard_rate = float(price_str)
		except ValueError:
			standard_rate = 0.0

	# Determine if stock item (retail items are stock, rooms/lockers are not)
	category = row.get("Categories", "")
	is_stock_item = 1 if "Retail Items" in category else 0

	# Create Item doc
	item = frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": full_name,
		"item_group": item_group,
		"stock_uom": "Nos",
		"is_stock_item": is_stock_item,
		"include_item_in_manufacturing": 0,
		"valuation_method": "FIFO",
		"standard_rate": standard_rate,
		"description": row.get("Description", "").strip() or full_name,
		"disabled": 0,
		# Hamilton-specific custom fields (if they exist)
		"hamilton_square_token": row["Token"].strip(),
		"hamilton_is_admission": 1 if category in ("Rooms", "Lockers") else 0,
	})

	# Add tax template (HST 13% Ontario)
	item.append("taxes", {
		"item_tax_template": "HST 13% Ontario - CH"
	})

	item.insert(ignore_permissions=True)

	# Set item price in CAD
	if standard_rate > 0:
		# Check if Item Price already exists
		existing_price = frappe.db.exists("Item Price", {
			"item_code": item_code,
			"price_list": "Standard Selling"
		})
		if not existing_price:
			frappe.get_doc({
				"doctype": "Item Price",
				"item_code": item_code,
				"price_list": "Standard Selling",
				"currency": "CAD",
				"price_list_rate": standard_rate,
			}).insert(ignore_permissions=True)


def _map_item_group(category_path: str) -> str:
	"""Map Square category to ERPNext Item Group.

	Square categories are hierarchical like "Retail Items > Gun Oil & Swiss Navy Lube".
	We'll use the top-level category as the Item Group.
	"""
	if not category_path:
		return "All Item Groups"

	# Extract top-level category
	parts = [p.strip() for p in category_path.split(">")]
	top_level = parts[0] if parts else "All Item Groups"

	# Map to ERPNext Item Groups
	mapping = {
		"Retail Items": "Hamilton Retail",
		"Rooms": "Hamilton Rooms",
		"Lockers": "Hamilton Lockers",
	}

	return mapping.get(top_level, "All Item Groups")


def _ensure_item_groups():
	"""Ensure Hamilton Item Groups exist."""
	groups = ["Hamilton Retail", "Hamilton Rooms", "Hamilton Lockers"]

	for group_name in groups:
		if not frappe.db.exists("Item Group", group_name):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": group_name,
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)
			print(f"Created Item Group: {group_name}")


def _ensure_hst_tax_template():
	"""Ensure HST 13% Ontario item tax template exists."""
	template_name = "HST 13% Ontario - CH"

	if frappe.db.exists("Item Tax Template", template_name):
		return

	# First ensure the tax account exists
	tax_account = "HST Ontario - CH"
	if not frappe.db.exists("Account", tax_account):
		# Create tax account under Duties and Taxes
		parent_account = frappe.db.get_value(
			"Account",
			{"account_name": "Duties and Taxes", "company": "Club Hamilton"},
			"name"
		)

		if not parent_account:
			frappe.throw(_("Cannot find 'Duties and Taxes' account for Club Hamilton"))

		frappe.get_doc({
			"doctype": "Account",
			"account_name": "HST Ontario",
			"parent_account": parent_account,
			"company": "Club Hamilton",
			"account_type": "Tax",
			"tax_rate": 13.0,
			"is_group": 0,
		}).insert(ignore_permissions=True)
		print(f"Created tax account: {tax_account}")

	# Create item tax template
	frappe.get_doc({
		"doctype": "Item Tax Template",
		"title": "HST 13% Ontario",
		"company": "Club Hamilton",
		"taxes": [{
			"tax_type": tax_account,
			"tax_rate": 13.0,
		}],
	}).insert(ignore_permissions=True)
	print(f"Created Item Tax Template: {template_name}")


if __name__ == "__main__":
	# For direct execution via bench execute
	seed_items()
