# Asset Board UI — Approved Design Spec

Approved via interactive mockup V6 on 2026-04-13

---

## Tab Bar

Labels in order: Lockers · Single · Double · VIP · Waitlist · Other · Watch

- Short labels only — not "Single Rooms", "Double Rooms" etc.
- Watch tab sits on far right, separated from others by a flex spacer
- Watch tab is always visible regardless of venue feature flags
- Tab height: 56px (padding 17px top/bottom, 20px left/right)
- Font size: 15px, weight 700 active / 500 inactive
- Active tab: border 2px solid #bbb, background #2a2a2a, bottom border matches background
- Inactive tabs: border 2px solid #777, background #141414 — always visible (accessibility)
- Watch tab active: border 2px solid #f59e0b, background #2a1a00
- Watch tab inactive: border 2px solid #92400e, background #1a1000, text #d97706
- Regular tab badge: green, shows Available count for that tab only. Hidden on placeholder tabs.
- Watch tab badge: pulsing red, shows combined count of warning + overtime + OOS across all assets

## Feature Flag Tabs — Waitlist and Other

- Waitlist sits between VIP and Other
- Both controlled by Hamilton Settings boolean fields: show_waitlist_tab (default 0), show_other_tab (default 0)
- When hidden by flag, tab does not render at all
- When visible but empty, shows placeholder: "No assets configured — This tab is controlled by venue settings"
- Waitlist logic deferred to Phase 2. Tab is placeholder only for Phase 1.

Venue defaults:
- Hamilton: show_waitlist_tab=0, show_other_tab=0
- Philadelphia: show_waitlist_tab=1, show_other_tab=0
- DC / Crew Club: show_waitlist_tab=1, show_other_tab=1
- Dallas: show_waitlist_tab=0, show_other_tab=1

## Header

- Single row: Venue name · Asset Board · Shift name · Time (10px uppercase, left aligned)
- Far right of same row: green online dot + logged-in attendant name in uppercase
- NO summary strip in header — deliberately removed to avoid duplication with footer
- Tabs sit directly below the title row

## Footer

- Single strip showing per-status counts for the ACTIVE TAB only
- Updates as attendant switches tabs
- Format: coloured dot · label · count for each status
- Far right: "Tap to expand · Tap outside to close"
- This is the ONLY status count display on the screen — top strip was deliberately removed

## Tile Design

- Base size: width 95px, minHeight 75px
- Border: 3px solid — always visible (accessibility decision for 50+ staff)
- Border radius: 6px (subtle rounding only — no glow, no box-shadow on normal tiles, clean solid border only)
- No box-shadow on normal tiles — clean solid border only, no glow
- box-shadow only appears on: expanded tiles (lift shadow) and overtime pulsing tiles (spec intentional)
- Border colour driven by status dot colour normally
- Warning tiles: 3px amber border #f59e0b + ⏱ badge top-right corner
- Overtime tiles: 3px red border #ef4444 + pulsing animation + OT badge top-right corner
- Time shown ONLY on warning and overtime tiles — never on normal occupied tiles
- Normal occupied tiles: red dot + asset code + "Occupied" label only, no time

## Status Colours

- Available: bg #0f2010, dot #22c55e, text #4ade80
- Occupied: bg #200f0f, dot #ef4444, text #f87171
- Dirty: bg #201a0a, dot #f59e0b, text #fbbf24
- Out of Service: bg #141420, dot #6366f1, text #818cf8

## Tile Expand Behaviour (Task 18)

- Tap tile expands to 1.5x scale (2x was considered and rejected)
- Lifts above grid with drop shadow on expand
- Action buttons appear inside expanded tile
- Tap anywhere outside collapses instantly
- Only one tile expanded at a time — tapping a second tile collapses first, expands new one
- Smooth animation in and out (cubic-bezier spring)

## Action Buttons Inside Expanded Tile

- Available: "Assign Guest" (green)
- Occupied: "Vacate" (red) + "Extend Stay" (blue)
- Dirty: "Mark Clean" (amber)
- Out of Service: "Return to Service" (green)
- All tiles: "Set Out of Service" secondary button (grey, smaller)
- Occupied tiles show guest name + elapsed time above action buttons when expanded

## Tab Content Layout — Regular Tabs

Four labelled sections in this fixed order:
1. Available (green section header)
2. Needs Cleaning (amber section header)
3. Occupied (red section header)
4. Out of Service (purple section header)

Rules:
- Empty sections hidden entirely — no blank rows rendered
- Section header shows label + count
- Available: sorted by asset code order
- Needs Cleaning: sorted longest dirty time first
- Occupied: sorted longest occupied time first (overtime and warning naturally surface to top)
- Out of Service: sorted longest OOS time first

## Watch Tab Layout

- Grouped rows by category — one labelled row per category that has warning or overtime assets
- Category rows only appear if they have assets to show
- Each category row sorted longest time first
- OOS section always at bottom — all OOS assets across all categories sorted longest first
- OOS section shows count beside label
- Empty state: "All clear ✓ — No assets need attention right now"

## Overtime Ticker (Task 19)

- Runs on 30-second setInterval
- Stage 1 Warning: guest past expected stay duration → amber border + ⏱ badge
- Stage 2 Overtime: guest past stay duration + grace period → red pulsing border + OT badge
- Grace period configurable via Hamilton Settings grace_minutes field (default 15)
- QA shortcut: temporarily set expected_stay_duration to 1 minute on a test asset to verify visually

## Mockup Data Note

All asset data shown in mockups is test data only. Real data comes from the database at runtime. If a section has no assets it simply does not render.
