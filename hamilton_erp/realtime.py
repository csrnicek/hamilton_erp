"""Realtime publishers — full impl in Task 13. Stubbed here so lifecycle
imports succeed during early TDD."""
from __future__ import annotations


def publish_status_change(asset_name: str, previous_status: str | None = None) -> None:
	pass  # replaced in Task 13


def publish_board_refresh(triggered_by: str, count: int) -> None:
	pass  # replaced in Task 13
