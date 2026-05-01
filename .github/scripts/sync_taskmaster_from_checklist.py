#!/usr/bin/env python3
"""Sync Taskmaster Task 25 subtasks from docs/task_25_checklist.md.

Single-direction derivation: the checklist file is the source of truth,
Taskmaster is the queryable mirror. Run this script anytime the checklist
changes; it updates `.taskmaster/tasks/tasks.json` to match.

Status markers in the checklist:

  Plain text                    -> Taskmaster status "pending"
  ✅ DONE                       -> "done"
  🔒 BLOCKED                    -> "blocked"
  🔍 REVIEW                     -> "review"
  ⏸ DEFERRED                    -> "deferred"

Marker placement: anywhere on the line for item N (e.g. "1. ✅ DONE — ...").

Exit codes:
  0  Sync ran cleanly (or was already in sync)
  1  Checklist file is malformed (e.g. missing items 1-23)
  2  Taskmaster file is missing or unreadable

Usage:
  python3 .github/scripts/sync_taskmaster_from_checklist.py            # write changes
  python3 .github/scripts/sync_taskmaster_from_checklist.py --check    # exit non-zero if drift exists
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKLIST = REPO_ROOT / "docs" / "task_25_checklist.md"
TASKMASTER = REPO_ROOT / ".taskmaster" / "tasks" / "tasks.json"

STATUS_MARKERS = {
    "✅ DONE": "done",
    "🔒 BLOCKED": "blocked",
    "🔍 REVIEW": "review",
    "⏸ DEFERRED": "deferred",
}


def parse_checklist(text: str) -> dict[int, str]:
    """Return {item_id: status} parsed from the checklist file."""
    statuses: dict[int, str] = {}
    line_re = re.compile(r"^\s*(\d+)\.\s+(.*)$")
    for line in text.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        item_id = int(m.group(1))
        if not 1 <= item_id <= 23:
            continue
        rest = m.group(2)
        status = "pending"
        for marker, mapped in STATUS_MARKERS.items():
            if marker in rest:
                status = mapped
                break
        statuses[item_id] = status
    return statuses


def load_taskmaster() -> dict:
    return json.loads(TASKMASTER.read_text())


def write_taskmaster(data: dict) -> None:
    TASKMASTER.write_text(json.dumps(data, indent=2) + "\n")


def apply(data: dict, statuses: dict[int, str]) -> bool:
    """Mutate `data` to match `statuses`. Return True if anything changed."""
    now = (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )
    changed = False
    for task in data["master"]["tasks"]:
        if task["id"] != "25":
            continue
        for sub in task.get("subtasks", []):
            sub_id = int(sub["id"])
            if sub_id in statuses:
                if sub["status"] != statuses[sub_id]:
                    sub["status"] = statuses[sub_id]
                    sub["updatedAt"] = now
                    changed = True
        break
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if drift exists; do not write.",
    )
    args = parser.parse_args()

    if not CHECKLIST.exists():
        print(f"checklist not found: {CHECKLIST}", file=sys.stderr)
        return 1
    if not TASKMASTER.exists():
        print(f"taskmaster not found: {TASKMASTER}", file=sys.stderr)
        return 2

    statuses = parse_checklist(CHECKLIST.read_text())
    missing = [i for i in range(1, 24) if i not in statuses]
    if missing:
        print(f"checklist missing items: {missing}", file=sys.stderr)
        return 1

    data = load_taskmaster()
    drift = apply(data, statuses)

    if args.check:
        if drift:
            print(
                "Taskmaster drift detected vs docs/task_25_checklist.md. "
                "Run `python3 .github/scripts/sync_taskmaster_from_checklist.py` "
                "to fix."
            )
            return 3
        print("Taskmaster is in sync with checklist.")
        return 0

    if drift:
        write_taskmaster(data)
        print(f"Synced Taskmaster from checklist; statuses: {statuses}")
    else:
        print("Already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
