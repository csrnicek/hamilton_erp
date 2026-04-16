"""Rename asset_tier "Glory Hole" → "GH Room" on all Venue Assets.

Idempotent: the WHERE clause only matches rows that still have the old value.
"""
import frappe


def execute():
	frappe.db.sql(
		'UPDATE `tabVenue Asset` SET asset_tier = %s WHERE asset_tier = %s',
		("GH Room", "Glory Hole"),
	)
