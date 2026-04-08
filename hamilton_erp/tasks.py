"""Scheduled background tasks for Hamilton ERP."""

import frappe


def check_overtime_sessions() -> None:
	"""Check all Active Venue Sessions for overtime and publish realtime alerts.

	Runs every 15 minutes per the scheduler_events in hooks.py.
	Phase 1 implementation. This is a no-op until the asset board is built.
	"""
	pass
