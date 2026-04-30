# Asset Board — Design Decisions Log

**Status:** LOCKED. Decisions on this page are FINAL and must not be re-opened without an explicit discussion and documented reversal.

**Last updated:** 2026-04-30 (DEC-061 + Amendment 2026-04-30 retail cart + Amendment 2026-04-30 scheduler stub purge)
**Source-of-truth mockup:** `docs/design/V9_CANONICAL_MOCKUP.html`
**PR:** #8 on branch `feature/asset-board-ui-rebuild`
**Mockup interactive tests:** 59 automated tests, all passing (pulse visibility, tile sizing, state transitions, modal flows, tab configuration, countdown behaviour)

---

## Part 1 — Tab structure and visibility

### 1.1 Seven-tab structure (fixed order)

Tabs in the board always render in this order: Lockers, Single, Double, VIP, Waitlist, Other, Watch.

Watch is always far right with a flex spacer pushing it. The other six are category tabs (map 1:1 to asset categories).

### 1.2 Tab visibility — combined config + data rule

A tab renders ONLY when BOTH conditions are true:
1. **Enabled in `venueConfig.tabs[tabName]`** — admin-controlled per venue
2. **Has at least one asset in that category** — system-controlled, auto-hides empty tabs

Watch tab is always visible regardless (it's a filtered view, not category-based).

**Reasoning:**
- Explicit admin control (you decide what Philadelphia's staff can see)
- Plus self-healing behaviour (adding the first Double to a venue makes the tab appear; removing the last one hides it)
- No empty-tab placeholder ever shows in normal operation

**Rejected alternatives:**
- Per-tab config alone — could leave empty tabs visible, looks unprofessional
- Auto-hide alone — no way to preserve a tab for scheduled future use, and no admin-level "Philadelphia does not have Doubles" guardrail

### 1.3 Tab config structure (per-venue)

```
venueConfig.tabs = {
  lockers:  true|false,
  single:   true|false,
  double:   true|false,
  vip:      true|false,
  waitlist: true|false,
  other:    true|false,
}
```

In production this loads from each venue's `site_config.json`. Hamilton production config: `lockers/single/double/vip = true`, `waitlist/other = false`.

### 1.4 Defensive fallback

If the currently-open tab becomes invisible (admin disables it, or last asset removed), render falls back to the first visible tab. No blank boards ever shown.

---

## Part 2 — Tile visual design

### 2.1 Tile size (iPad 11 / 1080×810 viewport)

Tile: 95×58 px baseline, 3px solid border always present, border radius 8px. Asset code in 17px bold, white text.

### 2.2 Status-only colour coding (no status text on tiles)

Status is conveyed by:
- Tile border colour (green/red/amber/purple)
- Tile background colour (dark matching border)
- Section header the tile sits under

Status text like "AVAILABLE" / "OCCUPIED" was REMOVED from tiles. Redundant and crowded the small tile.

### 2.3 Status colours (V6 spec hex)

| Status | Background | Border + dot | Text |
|---|---|---|---|
| Available | #0f2010 | #22c55e | #4ade80 |
| Occupied | #200f0f | #ef4444 | #f87171 |
| Dirty | #201a0a | #f59e0b | #fbbf24 |
| OOS | #141420 | #6366f1 | #818cf8 |

OOS is PURPLE, not grey. Deliberate.

### 2.4 Tap-to-expand interaction

Tap any tile → floats a separate overlay anchored near the source tile with `min-width: 130px` and content-driven height. Source tile stays at normal size underneath (dimmed). Edge-aware positioning clamps overlay to viewport. Tap outside, **or scroll the board**, to collapse.

Tiles NEVER stretch their row — the expanded view is a separate absolutely-positioned overlay over the source tile. Source tile stays in grid at normal size underneath.

### 2.5 Watch tab counter badge

Pulsing red badge in tab label. Count includes all overtime tiles across all categories, plus all OOS tiles. When zero, badge hidden.

### Amendment 2026-04-24 (V9 ship 1cc9125): data-asset-code removed from tile DOM attributes

V9 deliberately removed `data-asset-code` from the tile's DOM attributes. Rationale and current state:

- `data-asset-name` (Frappe docname / primary key) is now the sole canonical DOM lookup key for tiles
- `asset_code` continues to render as the visible top-left label inside `.hamilton-tile-code` div, but is no longer queryable as a DOM attribute
- All JS selectors use `[data-asset-name="..."]` exclusively (see `asset_board.js` around line 558)
- Two commits in repo history touched the literal string `data-asset-code`: 029ff98 (V8 add), 1cc9125 (V9 remove)
- Zero downstream code, CSS, or tests reference the missing attribute

Original Task 17.4 spec ("verify data-asset-code exists") is officially superseded by this amendment.

---

## Part 3 — Time-status states (Occupied tiles)

### 3.1 Three states (final — locked)

Based on `remaining = expectedMin - elapsedMin`:

| State | Condition | Visual | Text |
|---|---|---|---|
| Normal | `remaining > 60` | plain red-bordered occupied tile | no text |
| Countdown | `0 < remaining <= 60` | plain red-bordered occupied tile + red text | `"Xm left"` red |
| Overtime | `remaining <= 0` | pulsing red border + OT badge on top border | `"Xm late"` / `"2h 20m late"` red |

Threshold constant: `COUNTDOWN_THRESHOLD_MIN = 60`.

**Amendment 2026-04-24:** Countdown text colour reversed from amber to red. Reason: in V9 visual review, the amber countdown text on a red Occupied tile read as visually similar to the all-amber Dirty tile next to it, creating ambiguity for staff scanning the board. Red countdown text matches the Occupied tile border, eliminates the orange-overlap with Dirty, and is still distinguished from Overtime by (a) the word "left" vs "late", (b) the absence of the OT badge, and (c) the absence of the pulse animation.

### 3.2 Single overtime state — no warning/overtime two-stage

Late is late. Originally the V6 spec had a two-stage system (amber warning for first 15 min, then red overtime). REJECTED because:
- Two tiles at 10min late and 140min late looked too similar (both ambered)
- Amber border on an occupied tile conflicted with the Dirty status amber
- Number (10m vs 2h 20m) already tells you how bad; the colour adding duplicate severity info is redundant
- Staff aged 50+ at a busy front desk need binary signals, not subtle stage transitions

### 3.3 "Xm late" / "Xm left" wording (not "+10m" / "-10m")

The sign syntax was tested and rejected. Two rules:
- Countdown uses "left" (reads instantly)
- Overtime uses "late" (reads instantly)
- No "+" or "-" signs anywhere

### 3.4 OT badge position

OT badge sits centered ON the top border of the tile, like a tab hanging off the top edge. Previously tested in corner position — overlapped the room code. Corner position REJECTED permanently.

### 3.5 Pulsing animation

Pulsing applies ONLY to overtime tiles (not countdown, not warning). 1.4 sec cycle. Keyframe uses background-color + box-shadow ring to achieve 50+ unit brightness swing (tested pixel-by-pixel to confirm visibility — earlier box-shadow-only ripple was too subtle at 17 units).

```
@keyframes pulse-strong {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.9);
    background-color: var(--occupied-bg);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
    background-color: #6b1a1a;
  }
}
```

### 3.6 Tile sort order in Occupied section

Sorted by `elapsedMin` DESCENDING. Longest-occupied first. Puts most-urgent items at top of list where staff look first. Overtime tiles naturally bubble to top of the Occupied section for free.

### 3.7 Live-tick cadence (V9)

The board re-renders every **15 seconds** so countdown→overtime transitions surface without requiring a user interaction. The tick is guarded — it skips re-render while an expanded overlay or modal is open so in-flight DOM (form selections, typed notes) is preserved.

Constant: `LIVE_TICK_MS = 15000`. Cheap on Frappe; visually imperceptible to staff. Phase 2 may make this venue-configurable but the default stays here.

---

## Part 4 — State machine (asset status transitions)

### 4.1 Valid state transitions

```
    Available ──(assign guest)──> Occupied
    Occupied ──(vacate)──> Dirty (rooms only) OR Available (lockers)
    Dirty ──(mark clean)──> Available
    Dirty ──(set OOS)──> OOS
    Available ──(set OOS)──> OOS
    OOS ──(return to service)──> Available
```

### 4.2 Lockers skip the Dirty state

Lockers go directly from Occupied back to Available on vacate. No "Dirty" section ever renders on the Lockers tab. Rooms (Single/Double/VIP) go through Dirty as a required cleaning step.

Code comment documents this in `renderRegularTab()`.

### 4.3 Action buttons per state (FINAL)

| State | Buttons shown when tile expanded |
|---|---|
| Available | Assign Guest, Set Out of Service |
| Occupied | Vacate (→ expands to Key Return / Discovery on Rounds), Extend Stay (greyed, Phase 2) |
| Dirty | Mark Clean, Set Out of Service |
| OOS | Return to Service |

### 4.4 Occupied tiles do NOT have "Set Out of Service"

REMOVED. Rationale: you can't take a room out of service while a guest is in it. Must vacate first. If a guest reports an issue during their stay, staff processes vacate first, then OOS during cleaning.

### 4.5 "Are you sure?" secondary confirm REJECTED for Set OOS on Available

The OOS reason dropdown IS the speed check. Adding a separate "Are you sure?" before the reason dropdown would be two friction points for one action. The dropdown forces a deliberate selection which catches accidental taps.

### 4.6 Vacate sub-buttons (Occupied state)

Tapping Vacate doesn't immediately vacate. It expands to two sub-buttons:
- **Key Return** — normal checkout path (used when guest returns the key/card themselves)
- **Discovery on Rounds** — catch-all for rooms discovered empty during staff rounds (guest left without formal checkout)

This distinction matters for session logging and auditing. Both actions transition Occupied → Dirty (or → Available for lockers).

---

## Part 5 — Out-of-Service (OOS) workflow

### 5.1 OOS reason list — global, amendable

Single reason list shared across ALL venues. Not per-venue. Global is amendable in Phase 2 via an admin UI (Frappe DocType).

### 5.2 Current list (7 reasons)

```
const OOS_REASONS = [
  'Plumbing',
  'Electrical',
  'Lock or Hardware',
  'Cleaning required (deep)',
  'Damage',
  'Maintenance scheduled',
  'Other',
];
```

"Other" must always be last. When selected, it triggers a required note field.

### 5.3 Phase 2 amendment flow

Wire `OOS_REASONS` to a Frappe DocType (`OOS Reason`) with:
- `reason_name` (string)
- `is_active` (bool, for soft-delete)
- `display_order` (int, for sorting)

Admins can add/deactivate reasons via the Frappe UI. SOFT-DELETE only — never hard-delete. Historical OOS records must preserve their original reason label for audit/insurance purposes even after the taxonomy changes.

### 5.4 Tapping OOS tile — shows full context

Expanded OOS tile displays:
- Reason (e.g. "Lock or Hardware") in purple
- "Set by M. CHEN · 4 days ago" meta line
- Day counter (Xd) in bottom-right corner
- Return to Service button

Data captured: `oosReason`, `oosSetBy`, `oosSetAt` (implicit from `oosDays` calculation).

### 5.5 Return to Service — required confirmation modal

Tapping "Return to Service" does NOT immediately return the asset. Opens a modal showing:
- Reason (what was wrong)
- Who set it OOS
- Days ago
- Audit preview line: "By confirming, this action will be recorded as: Returned to service by {current attendant} at {current time}"
- Cancel / Confirm reason resolved buttons

Confirmation records `oosReturnedBy` and `oosReturnedAt` going forward (Phase 2 wiring).

### 5.6 Rejected alternatives for OOS taxonomy

- **Per-venue reason lists** — rejected because it fragments cross-venue reports ("Plumbing" vs "Plumbing Issue" split queries)
- **Global + venue extras** — considered but adds two sources of truth for admins to manage

---

## Part 6 — Header and footer

### 6.1 Header (single row)

Left: `Club Hamilton · Asset Board · PM Shift · 14:23`
Right: `● A. NOLAN` (green online dot + current attendant name, uppercase)

Time displays in 24-hour format (`HH:mm`). Attendant name is the logged-in user of the current tablet session.

### 6.2 Footer (per-tab counts)

Status counts for ACTIVE TAB ONLY:
- `● Available 25 ● Occupied 6 ● OOS 2` (dot-label-count format)

Far right: `Tap to expand · Tap outside to close` help text.

---

## Part 7 — Tier-name-agnostic UI

### 7.1 UI must never hardcode tier names

Lockers can be "Regular" or "Deluxe" or venue-specific names. Rooms can be "Single Standard", "GH Room", "Double Deluxe", etc. Different venues will use different tier names.

**Code must render whatever `room_subtype` the DB returns.** No hardcoded tier strings in the UI layer. Order of subtypes within a tab can be derived from a config field (`room_subtype_order`) or from first-seen order in data.

### 7.2 Category is fixed, subtypes are not

The 6 category tabs (Lockers/Single/Double/VIP/Waitlist/Other) are the stable UI taxonomy. Within each category, subtypes (e.g. "Regular", "TV", "Glory Hole") are venue-specific and rendered from data.

---

## Part 8 — iPad viewport constraints

### 8.1 Target device

iPad 11th gen (and iPad 10), 1080×810 CSS pixels in landscape. Safari chrome deducts ~95-140px from usable height.

### 8.2 Mockup tablet simulates this

Mockup's `.tablet` container renders at 1080×716 usable height (matching iPad 11 Safari landscape with address bar visible). Tile expansion logic clamps to this viewport — 11 viewport-containment tests verify the expanded tile never clips off-screen at any position.

### 8.3 Font sizes chosen for staff 50+

Asset code: 17px. Time text: **12px bold** (was 10px in V8 — bumped in V9 per Grok review for legibility next to 17px asset codes; tile min-height stays 58px and content fits comfortably). Tab labels: 15px. Tab height: 56px (accessibility).

---

## Part 9 — Testing standards

### 9.1 Before presenting any mockup to Chris

ALL scenarios must be tested programmatically first. Chris is NOT the tester. Specifically:
- Run the interactive test suite (currently 59 tests)
- Sample pixel data of animations over multiple frames to confirm visual effects are actually visible
- Take screenshots of each tab state and visually inspect
- Verify tile sizes on actual iPad viewport
- Only then present to Chris

### 9.2 Key pixel-level checks that are easy to skip

- Pulse animation brightness swing (must be >25 units to read as "pulsing")
- OT badge does NOT overlap room code (geometric rect check)
- Tile height uniform across states (no text blow-out)
- Expanded tile stays within viewport at all corners/edges

---

## Part 10 — Explicitly rejected ideas (do not revisit)

| Idea | Why rejected |
|---|---|
| Two-stage warning/overtime | Too subtle; staff aged 50+ need binary signals |
| Amber border on occupied warning tile | Conflicted with Dirty status amber |
| "+10m" / "-10m" sign syntax for time | Sign parsing too slow at a glance |
| OT badge in corner of tile | Overlapped room code (R003 partially hidden) |
| Status text ("AVAILABLE") on tiles | Redundant with colour + section header |
| Per-venue OOS reason list | Fragments cross-venue reporting |
| "Are you sure?" before Set OOS on Available | Reason dropdown is already the speed check |
| Set OOS button on Occupied tiles | Can't OOS while guest is present — must vacate first |
| Dirty state for lockers | Lockers don't go through cleaning cycle |
| "No assets configured" placeholder for empty enabled tabs | Combined config+data rule makes this unreachable — auto-hide instead |
| Pulsing animation on countdown tiles | Pulse is for most-urgent state only (overtime) |
| Pulsing animation on all late tiles regardless of severity | Too visually chaotic on a busy night |

---

## Part 11 — Pending items (not yet implemented)

The following are KNOWN OPEN ITEMS but NOT a reason to revisit the decisions above:

1. **Expanded-tile text wrap fix** — at 1.5× scale, some action button labels wrap awkwardly ("EXTEND STAY PHASE 2", "SET OUT OF SERVICE"). Fix by widening buttons, shrinking font, or shortening labels.

2. **Phase 2 wiring:**
   - OOS Reason DocType (admin-editable list)
   - Extend Stay flow (currently greyed Phase 2)
   - Vacate backend logic (Key Return vs Discovery on Rounds) wiring to session records
   - Scheduler job `check_overtime_sessions` (stub in Phase 1)
   - Countdown threshold as venue-configurable (currently hardcoded 60)

3. **Multi-venue refactor** — after Task 25, before DC build. Not part of V8 asset board work.

---

## Amendment 2026-04-30 — V9.1 Phase 2 retail cart UX (stub PR)

V9.1-D8 through V9.1-D14 added to `docs/design/V9.1_RETAIL_AMENDMENT.md`. V9.1-D7 is now SUPERSEDED by V9.1-D9 (tap retail tile = add to cart). Brief summary:

- **V9.1-D8:** Cart drawer is a slide-up dark drawer fixed at the bottom of the asset board. Hidden when cart is empty, collapsed (one row) by default, expanded on tap.
- **V9.1-D9:** Tap retail tile = add 1 to cart. Out-of-stock guard shows "Out of stock" toast.
- **V9.1-D10:** Qty controls = − / + buttons in the drawer. qty=0 removes the line.
- **V9.1-D11:** HST 13% applied flat (`HST_RATE = 0.13` JS constant). Per-venue tax becomes a `site_config.json` flag when Hamilton ships its second venue.
- **V9.1-D12:** Cash payment, single tender, modal. **Confirm button is a STUB** — Sales Invoice creation lands in a follow-up PR once Hamilton's accountant decides on HST tax account, income account, cost center, and warehouse names.
- **V9.1-D13:** Cart state is per-session JS-only, no DB persistence.
- **V9.1-D14:** Out of scope: card payments, split tender, receipt printing, discounts, admission items in cart, loyalty pricing.

The cart UX is browser-testable end-to-end. The Sales Invoice piece deliberately deferred so operator UX iteration doesn't pollute the chart of accounts.

---

## Amendment 2026-04-30 — `check_overtime_sessions` scheduler stub purged

Pre-Task-25 cleanup. The `*/15 * * * *` cron registration in `hooks.py:scheduler_events` and the no-op `pass`-bodied `check_overtime_sessions` function in `tasks.py` were removed. The `tasks.py` module was deleted entirely (the stub was its only contents).

Why:

- The job fired 96 times per day to do nothing, contributing only "Success" rows to `tabScheduled Job Log`.
- Senior-Frappe-developer pre-handoff audits flagged it as a 60-second-spot trust regression (`docs/inbox.md` 2026-04-29 entry, prompt 1 finding §10).
- The `inbox.md` recommendation was binary: implement the body or delete the registration. Implementation requires Phase 2 overtime UX which isn't built yet, so deletion is the right pre-handoff state.

What changes for Phase 2:

- When overtime UX lands, reintroduce a real scheduler job with the Tier-1 wrapping pattern from the production handoff audit: `try/except` body wrapping `frappe.log_error()` with title `"Overtime Detection Failed"`, per-session try/except with summary failure, integration test asserting <2s runtime against populated DB.
- Re-add `tasks.py` module at that point with the full body — do not resurrect the stub.

Files touched: `hamilton_erp/hooks.py` (removed scheduler_events block), deleted `hamilton_erp/tasks.py`, updated `docs/testing_guide.md` (removed stale test row), updated `docs/phase1_design.md` (§2.2 + §11 list item 6).

---

## Amendment 2026-04-29 (b) — V10 canonical bump + V9.1 retail amendment

The canonical mockup pointer was bumped from V9 to V10. **The V10 file's body is byte-identical to V9** — the body SHA-256 in `docs/design/canonical_mockup_manifest.json` is unchanged. The bump bookkeeps the V9.1 retail amendment, whose visual + behavioural spec lives in `docs/design/V9.1_RETAIL_AMENDMENT.md` rather than inlined in the canonical HTML. V9 is archived to `docs/design/archive/V9_CANONICAL_MOCKUP.html`.

The full V9.1 retail decisions (V9.1-D1 through V9.1-D7) are documented in the amendment file. They are summarized here for cross-reference:

- **V9.1-D1:** SKUs live in ERPNext `Item` (no custom DocType).
- **V9.1-D2:** Inventory tracked per venue via `Bin`/`Warehouse`.
- **V9.1-D3:** Tabs map to ERPNext `Item Group`.
- **V9.1-D4:** Per-venue `site_config.json` key `retail_tabs` lists Item Groups.
- **V9.1-D5:** Tab framework data-driven; combined config + data rule extends.
- **V9.1-D6:** Retail tile shape — code + stock badge + name + price; stock state palette reuses asset palette (green ≥4, amber 1–3, red 0).
- **V9.1-D7:** Retail tile click is a no-op in V9.1 (cart UX is round 2).

Round 2 deferred work (NOT in V9.1, will land after browser test): cart UX, add-to-cart, payment flow, refunds/voids, operator price overrides, multi-warehouse selection, low-stock alerts.

---

## Amendment 2026-04-29 — V9 browser-test session

After end-to-end browser testing on hamilton-test.localhost on 2026-04-29 (25 tests, 6 critical V9 launch-blockers all confirmed fixed), the following decisions were made and locked.

### A29-1 Bulk "Mark All Clean" feature REMOVED (DEC-054 reversed)

**Status:** REMOVED. The footer "Mark All Clean" button, the `mark_all_clean_rooms` and `mark_all_clean_lockers` whitelisted endpoints, the `_mark_all_clean` helper, and the bulk-aware `bulk_reason` parameter on `mark_asset_clean` are all deleted.

**Reasoning:** Operator browser testing on 2026-04-29 showed cleaning happens per-tile via the Dirty tile's expand-overlay "Mark Clean" action. The bulk endpoint was an opt-in shortcut that bypassed the per-tile audit context and was never used in live flow. Removing it eliminates a parallel API surface and ~140 lines of code/tests with zero coverage loss.

**Reverses:** DEC-054 (the original Bulk Mark All Clean spec) and supersedes any references to it elsewhere in this document.

### A29-2 Tab badge = Available count ONLY

Each per-category tab badge displays the count of **Available** assets in that category — the "sellable now" count. Confirmed consistent across Lockers, Single, Double, GH Room during browser test.

**Reasoning:** Operators look at tab badges to answer "what can I sell right now?" — not "how many tiles are in this tab?" The Available count is the only number that maps to that question.

### A29-3 Watch badge = Overtime + OOS combined

The Watch tab badge is the count of (overtime tiles) + (Out-of-Service tiles) — all tiles needing operator attention.

**Reasoning:** The Watch tab is a "needs attention" filtered view. Combining OT and OOS in one badge gives the operator a single number that answers "how many things need me right now?".

### A29-4 Header PM SHIFT and ADMINISTRATOR are read-only by design

The header shows current shift label (e.g. PM SHIFT) and operator identity (e.g. ADMINISTRATOR) as **non-interactive text**. Tapping either does nothing.

**Reasoning:** Shift change and logout are infrequent operations that live on dedicated pages. Making header text tappable creates accidental-tap risk during shift-change moments when the operator is busy with handoff. Surface area minimized.

### A29-5 Dirty tile shows "Dirty for Xm" timer

Dirty tiles render a "Dirty for Xm" timer in the same position as the countdown/overtime time text on Occupied tiles. Computed client-side from `asset.hamilton_last_status_change`. Updates with the live tick (15s cadence).

**Reasoning:** Cleaners need a prioritization signal among multiple Dirty tiles. The oldest Dirty tile is the most urgent.

### A29-6 RTS modal SET line includes timestamp

The Return-to-Service modal's "Set:" context row now formats as `"by NAME at HH:MM AM/PM"` (with optional " · X days ago" appended when the days-ago row is non-empty). Time-of-day is taken from `hamilton_last_status_change`.

**Reasoning:** Matches the OOS audit-line format ("Set out of service by NAME at HH:MM AM/PM") shown elsewhere in the modal. Operators returning a tile to service need to see when it went OOS, not just who set it.

**Supersedes:** the prior Decision 5.5 "Set:" row format (which showed only `"by NAME · X days ago"` — no time-of-day).

---

## Part 12 — How to use this document

Before making ANY change to the asset board, search this document first. If the change touches a decision already locked here:
1. Do NOT silently change behaviour
2. Surface the conflict: "This would reverse Decision X.Y"
3. Get explicit approval from Chris to reverse
4. If reversed, update this document with the reversal and reasoning
5. Only then change the code

The point of this document is to stop re-opening settled questions. Respect it.
