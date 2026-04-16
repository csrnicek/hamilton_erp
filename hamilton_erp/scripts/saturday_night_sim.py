"""Saturday Night Simulation — populate hamilton-test.localhost with realistic data.

Run with:
  bench --site hamilton-test.localhost execute hamilton_erp.scripts.saturday_night_sim.run

This script uses lifecycle functions (not raw DB writes) so all locks, logs,
audit trails, and session records are created properly.  After lifecycle
transitions, it adjusts session_start times via DB to simulate various
check-in times for the overtime ticker.
"""
import frappe
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Target layout
# ---------------------------------------------------------------------------

# (asset_code, target_status, hours_ago_or_reason)
# hours_ago is only meaningful for Occupied; reason is for OOS.
PLAN = [
    # Single Standard (R001–R011)
    ("R001", "Occupied", 5.5),
    ("R002", "Occupied", 5.2),
    ("R003", "Occupied", 5.0),
    ("R004", "Occupied", 5.8),
    ("R005", "Occupied", 6.0),
    ("R006", "Occupied", 2.0),
    ("R007", "Occupied", 2.0),
    ("R008", "Dirty", None),
    ("R009", "Dirty", None),
    ("R010", "Available", None),
    ("R011", "Available", None),

    # Deluxe Single (R012–R021)
    ("R012", "Occupied", 7.0),
    ("R013", "Occupied", 7.5),
    ("R014", "Occupied", 7.2),
    ("R015", "Occupied", 1.0),
    ("R016", "Occupied", 1.0),
    ("R017", "Dirty", None),
    ("R018", "Dirty", None),
    ("R019", "OOS", "Plumbing issue"),
    ("R020", "Available", None),
    ("R021", "Available", None),

    # GH Room (R022–R023)
    ("R022", "Occupied", 3.0),
    ("R023", "Dirty", None),

    # Double Deluxe (R024–R026)
    ("R024", "Occupied", 6.0),
    ("R025", "Available", None),
    ("R026", "Available", None),

    # Lockers (L001–L033)
    ("L001", "Occupied", 8.0),   # deep overtime
    ("L002", "Occupied", 6.5),   # overtime
    ("L003", "Occupied", 5.0),   # overtime
    ("L004", "Occupied", 4.0),   # warning zone
    ("L005", "Occupied", 3.5),   # normal
    ("L006", "Occupied", 2.0),   # normal
    ("L007", "Occupied", 1.5),   # normal
    ("L008", "Occupied", 1.0),   # normal
    ("L009", "Occupied", 0.5),   # just arrived
    ("L010", "Occupied", 0.25),  # just arrived
    ("L011", "Dirty", None),
    ("L012", "Dirty", None),
    ("L013", "Dirty", None),
    ("L014", "Dirty", None),
    ("L015", "Dirty", None),
    ("L016", "OOS", "Lock broken"),
    ("L017", "Available", None),
    ("L018", "Available", None),
    ("L019", "Available", None),
    ("L020", "Available", None),
    ("L021", "Available", None),
    ("L022", "Available", None),
    ("L023", "Available", None),
    ("L024", "Available", None),
    ("L025", "Available", None),
    ("L026", "Available", None),
    ("L027", "Available", None),
    ("L028", "Available", None),
    ("L029", "Available", None),
    ("L030", "Available", None),
    ("L031", "Available", None),
    ("L032", "Available", None),
    ("L033", "Available", None),
]


def _lookup(asset_code):
    """Return (doc_name, current_status) for an asset_code."""
    row = frappe.get_value(
        "Venue Asset",
        {"asset_code": asset_code},
        ["name", "status"],
        as_dict=True,
    )
    if not row:
        raise ValueError(f"No Venue Asset with asset_code={asset_code}")
    return row["name"], row["status"]


def _reset_to_available(doc_name, current_status, operator):
    """Transition an asset back to Available regardless of current state."""
    from hamilton_erp.lifecycle import (
        mark_asset_clean,
        return_asset_to_service,
        vacate_session,
    )

    if current_status == "Available":
        return
    if current_status == "Occupied":
        vacate_session(doc_name, operator=operator, vacate_method="Key Return")
        # Now it's Dirty — fall through
        current_status = "Dirty"
    if current_status == "Dirty":
        mark_asset_clean(doc_name, operator=operator)
        return
    if current_status == "Out of Service":
        return_asset_to_service(doc_name, operator=operator, reason="Sim reset")
        return


def _set_target(doc_name, target, hours_ago_or_reason, operator):
    """Transition an Available asset to the target state."""
    from hamilton_erp.lifecycle import (
        mark_asset_clean,
        set_asset_out_of_service,
        start_session_for_asset,
        vacate_session,
    )

    if target == "Available":
        return  # already there

    if target == "Occupied":
        session_name = start_session_for_asset(doc_name, operator=operator)
        # Adjust session_start to simulate the check-in time
        if hours_ago_or_reason:
            past = datetime.now() - timedelta(hours=hours_ago_or_reason)
            frappe.db.set_value("Venue Session", session_name, "session_start", past)
        return

    if target == "Dirty":
        # Create a session then immediately vacate it
        start_session_for_asset(doc_name, operator=operator)
        vacate_session(doc_name, operator=operator, vacate_method="Key Return")
        return

    if target == "OOS":
        reason = hours_ago_or_reason or "Simulation OOS"
        set_asset_out_of_service(doc_name, operator=operator, reason=reason)
        return


def _fix_legacy_tiers():
    """Rename any remaining 'Glory Hole' tiers to 'GH Room' on this site."""
    count = frappe.db.count("Venue Asset", {"asset_tier": "Glory Hole"})
    if count:
        frappe.db.sql(
            "UPDATE `tabVenue Asset` SET asset_tier = %s WHERE asset_tier = %s",
            ("GH Room", "Glory Hole"),
        )
        frappe.db.commit()
        print(f"  Fixed {count} assets with legacy 'Glory Hole' tier → 'GH Room'")


def run():
    operator = "Administrator"
    now = datetime.now()
    print(f"Saturday Night Simulation — {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Processing {len(PLAN)} assets...\n")

    # Phase 0: fix legacy tier names
    print("Phase 0 — Fixing legacy tier names...")
    _fix_legacy_tiers()
    print("  Done.\n")

    # Phase 1: reset every planned asset to Available
    print("Phase 1 — Resetting all planned assets to Available...")
    for code, _, _ in PLAN:
        doc_name, status = _lookup(code)
        if status != "Available":
            _reset_to_available(doc_name, status, operator)
            print(f"  {code} ({doc_name}): {status} → Available")
    frappe.db.commit()
    print("  Done.\n")

    # Phase 2: apply target states
    print("Phase 2 — Applying Saturday night layout...")
    for code, target, extra in PLAN:
        doc_name, status = _lookup(code)
        if target == "Available":
            continue
        _set_target(doc_name, target, extra, operator)
        label = target
        if target == "Occupied" and extra:
            label = f"Occupied ({extra}h ago)"
        elif target == "OOS":
            label = f"OOS ({extra})"
        print(f"  {code}: → {label}")
    frappe.db.commit()
    print("  Done.\n")

    # Phase 3: summary
    print("Phase 3 — Final counts:")
    from collections import Counter
    assets = frappe.get_all(
        "Venue Asset",
        fields=["status"],
        filters={"is_active": 1},
    )
    counts = Counter(a["status"] for a in assets)
    for s in ["Available", "Occupied", "Dirty", "Out of Service"]:
        print(f"  {s}: {counts.get(s, 0)}")
    print(f"  Total: {sum(counts.values())}")
    print("\nSimulation complete. Reload the Asset Board to see the data.")
