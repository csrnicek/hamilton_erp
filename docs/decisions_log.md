# Asset Board — Design Decisions Log

**Status:** LOCKED. Decisions on this page are FINAL and must not be re-opened without an explicit discussion and documented reversal.

**Last updated:** 2026-05-01 (DEC-062 standard-merchant classification + DEC-063 per-venue processor choice + DEC-064 primary+backup processor architecture)
**Source-of-truth mockup:** `docs/design/V10_CANONICAL_MOCKUP.html` (V10 body is byte-identical to V9; the bump bookkeeps the V9.1 retail amendment. V9 archived at `docs/design/archive/V9_CANONICAL_MOCKUP.html`.)
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
- **V9.1-D7:** Retail tile click is a no-op in V9.1 (cart UX is round 2). **SUPERSEDED 2026-04-30 by V9.1-D9** (tap retail tile = add 1 to cart; cart UX shipped in PR #49).

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

## Amendment 2026-04-30 (b) — Hamilton accounting names locked from QBO mirror

After the V9.1 Phase 2 cart UX shipped as PR #49 (UX-only stub), Chris's accountant decided the accounting prerequisites should mirror Hamilton's existing QBO chart-of-accounts naming. The follow-up PR (also 2026-04-30) seeds these as part of `_ensure_hamilton_accounting` in `hamilton_erp/setup/install.py`:

- **HST account:** `GST/HST Payable` (account_type=Tax, root_type=Liability, tax_rate=13)
- **Income — beverages:** `4260 Beverage` (Water, Sports Drinks, future drink SKUs)
- **Income — food:** `4210 Food` (Protein Bar, Energy Bar, future food SKUs)
- **Warehouse:** `Hamilton`
- **Cost Center:** `Hamilton`
- **POS Profile:** `Hamilton Front Desk` — operator-invisible, named target of `submit_retail_sale`
- **Sales Taxes Template:** `Ontario HST 13%` referencing the GST/HST Payable account

Per ERPNext convention, account/warehouse/cost center names are appended with the company abbreviation suffix (e.g. `4260 Beverage - CH` for company `Club Hamilton` abbr `CH`).

**Why mirror QBO:** Hamilton's books have run on QBO since opening. Mirroring the names exactly means QBO sync (Phase 3) and any cross-system reporting can match by name without a translation table. The accountant signed off; locking them prevents drift.

**Production pinning:** Sites that already have a non-`Club Hamilton` company configured can pin it via `bench --site SITE set-config hamilton_company "<existing name>"`. The seed augments the pinned company with Hamilton-specific accounts rather than creating a sibling Club Hamilton.

**Reverses:** the placeholders proposed in V9.1-D12 of the UX-stub PR (e.g. `HST Payable - WP`, `Sales - WP`, the "Retail Sales" suggestion). Those were exploratory and were never written to code.

**Related:** Phase 2 hardware + integration backlog (Epson TM-T20III receipt printer, merchant abstraction with `merchant_transaction_id` capture per Card sale, tap-to-pay treated as "Card" not separate) is documented in `docs/inbox.md` under 2026-04-30. That work follows this PR.

---

## Amendment 2026-04-30 (c) — Canadian penny-elimination rounding (cash sales only)

After PR #51 hardening, source-of-truth review surfaced that Hamilton's POS Sales Invoice flow was setting `disable_rounded_total=1` unconditionally — sidestepping Canada's 2013 cash-rounding rule. Per the Government of Canada Budget 2012 backgrounder, cash transactions must round to the nearest 5¢ after HST is calculated; electronic payments (debit, credit, cheque, e-transfer, gift card) settle to the cent.

This amendment locks the implementation:

- **Rounding pattern** matches the CRA rule exactly:
  - Totals ending in 1, 2 → round down to 0
  - Totals ending in 3, 4 → round up to 5
  - Totals ending in 6, 7 → round down to 5
  - Totals ending in 8, 9 → round up to next 0
  - Implemented via Frappe's `round_based_on_smallest_currency_fraction` with `Currency CAD.smallest_currency_fraction_value = 0.05`. Verified by `test_rounding_pattern_matches_cra_rule`, which exhaustively tests all terminal digits.
- **HST calculated first.** Subtotal × 13% is computed to the cent on the unrounded subtotal; the rounding adjustment never enters the tax math. The CRA still receives the exact HST amount.
- **Payment-method gate.** Cash → round; Card → exact-cent (`disable_rounded_total=1` on the SI). The gate lives in `hamilton_erp.api._should_round_to_nickel` and is parameterized via `submit_retail_sale(payment_method)`. Default is `"Cash"`; `"Card"` throws at the entry point until Phase 2 next iteration ships the merchant-abstraction work — but the rounding gate is correct for Card now.
- **Accounting treatment (Path B per the research).** The 1–4¢ rounding adjustment posts as a separate GL entry to `Company.round_off_account` (`Round Off - {abbr}`) on submit. Net annual rounding gain/loss runs through the Round Off account.
- **Seed responsibilities** (in `_ensure_hamilton_accounting`):
  - `_ensure_round_off_account_linked` sets `Company.round_off_account` and `Company.round_off_cost_center` so `make_gle_for_rounding_adjustment` can post.
  - `_ensure_cad_nickel_rounding` sets `Currency CAD.smallest_currency_fraction_value = 0.05` (overrides Frappe's default of 0.01). Idempotent; doesn't overwrite operator-customized values other than the default.
- **Patch entry** `hamilton_erp.patches.v0_1.seed_canadian_nickel_rounding` re-applies the two new seed steps on existing sites via `bench migrate`. Fresh installs run them via `after_install`.

**Why mathematically-equivalent-not-identical:** Frappe's algorithm rounds half-up at the midpoint (0.025); the CRA rule never produces a 0.025 input because cash totals are always in 0.01 increments. The exhaustive terminal-digit test covers every cash-total possibility (0.00–0.09 mod 0.10) and matches.

**Reverses:** the unconditional `disable_rounded_total=1` introduced in PR #51's first hardening pass. That was a stop-gap fix for ERPNext's POS round-to-whole-dollar default; the proper fix is nickel rounding gated by payment method.

**Production note:** The Currency-level setting (`smallest_currency_fraction_value=0.05`) affects every CAD invoice on the site, not just cart sales. For Hamilton this is correct (retail-only, no B2B CAD invoices). When a future B2B flow lands and needs exact-cent CAD invoicing, that flow must explicitly set `disable_rounded_total=1` on its invoices.

**Reference:** docs/inbox.md 2026-04-30 research report; Wikipedia "Cash rounding"; Frappe `round_based_on_smallest_currency_fraction` in `frappe/utils/data.py`; ERPNext `make_gle_for_rounding_adjustment` in `erpnext/accounts/doctype/sales_invoice/sales_invoice.py`.

---

## Amendment 2026-05-01 — DEC-062: Hamilton ERP / ANVIL Corp business classification

**Decision:** Hamilton ERP and the ANVIL Corp venues (Hamilton Ontario, Philadelphia, DC, Dallas) operate as **standard commercial businesses**, NOT adult-classified businesses. This is the canonical position for all merchant relationships, regulatory framing, and processor research going forward.

**Cited evidence:**
- **Fiserv MID 1131224** is registered as a standard-classified merchant, NOT under high-risk classification. Confirmed in `docs/risk_register.md` R-008 (the original assumption of high-risk was deliberately downgraded after MID-level verification).
- **PIPEDA**: Hamilton operates under PIPEDA as a standard commercial business with no industry-specific obligations layered on top. Per `docs/research/pipeda_venue_session_pii.md` §1.3 (line 51) and the explicit clarifying note at §8 (line 296): *"Hamilton is **not** classified as 'adult' by any government body, payment network, or regulator."*
- **Card networks**: standard MCC categorization (likely 7298 health/beauty/spa or 7299 services-not-elsewhere-classified per inbox 2026-04-30 research note); not high-risk MCCs (5967 adult content, 7273 dating, etc.). Exact MCC pending Fiserv confirmation but does not affect the classification decision.

**What this decision does NOT claim:**
- Customers may still perceive their attendance as sensitive — that's a customer-privacy concern, addressed by PIPEDA's "real risk of significant harm" threshold (covered separately in `pipeda_venue_session_pii.md`). The customer-privacy posture and the business-classification posture are distinct.
- Some payment processors (Stripe, Square) may *perceive* bathhouse-hospitality as adult-adjacent within their own risk models. The processor's risk classification is THEIR internal categorization, not Hamilton's actual legal/operational classification. `docs/research/merchant_processor_comparison.md` "Adult-classification policy by processor" section is defensibly framed as a description of each processor's stance toward perceived-adult-adjacent businesses, not as a claim about Hamilton.

**Implication for multi-venue rollout:**
Philadelphia, DC, and Dallas inherit the same standard-merchant baseline. Processor selection (per `merchant_processor_comparison.md`) follows the rationale that:
- Fiserv at Hamilton works because Hamilton's MID is already standard.
- Stripe Terminal at the new venues works because Stripe's TOS draws the line at "adult content" (porn, sex work), not "adult-adjacent hospitality" (bars, bathhouses) where the new venues fall.
- Helcim, Square, etc. are evaluated on the same standard-merchant baseline.

**Reverses (implicitly):** the older inbox.md framing at lines 1665-1799 ("Bathhouses are adult-classified", "CRITICAL for adult-classified businesses") that pre-dated the R-008 downgrade. PR #55 (merged 2026-05-01) removed this framing from the PIPEDA research doc; this DEC formalizes the position and is the canonical citation for the sweep landing in the same PR.

**References:**
- `docs/risk_register.md` R-008 — operational evidence (Fiserv standard classification confirmed)
- `docs/research/pipeda_venue_session_pii.md` §51, §144, §296 — PIPEDA framing (standard commercial business)
- PR #55 — "remove false 'adult' classification framing from PIPEDA doc" (precedent cleanup that motivated this DEC)
- `docs/research/merchant_processor_comparison.md` — research that motivates this DEC

**Deferred questions** (not blocked by this DEC):
- Exact MCC code on Fiserv MID 1131224 — flagged in inbox.md launch-prep checklist; pending Fiserv confirmation. Decision stands regardless of which standard-tier MCC the MID uses.
- Per-venue processor relationships in Philadelphia/DC/Dallas — those are operational selections, not classification decisions; this DEC sets the baseline they inherit. See DEC-063 below for the per-venue selection rule.

---

## Amendment 2026-05-01 — DEC-063: Per-venue primary processor choice

**Decision:** Each ANVIL Corp venue picks its own primary card processor at rollout based on local availability, iPad / ERPNext integration quality, hardware fit, fees, and risk policy. There is **no single corporate-wide processor mandate.**

**Why per-venue, not corporate-wide:**
- **Currency:** Hamilton runs CAD; Philadelphia / DC / Dallas run USD. Cross-border processors that look attractive on paper (e.g. Stripe Terminal) introduce currency-conversion friction or per-venue MID overhead that makes single-processor mandates expensive.
- **Local availability:** Helcim's Canadian rates are competitive but US support is partner-only. Fiserv's Canadian and US footprints are different ISO networks — pricing varies by venue.
- **iPad / ERPNext SDK fit:** Some processors (Stripe Terminal, Clover Connect) have first-class iOS SDKs; others (Moneris) require custom adapters. Hamilton's existing Fiserv MID predates the iPad cart and may need a different terminal model than a greenfield venue would pick.
- **Risk policy:** Even though all ANVIL venues operate as standard merchants per DEC-062, individual processors apply different *perceived* adult-adjacency stances. A processor that's fine at venue A may flag at venue B based on the local underwriter.

**What this means in practice:**
- Hamilton stays on Fiserv (MID 1131224, standard-classified, already running).
- Philadelphia / DC / Dallas choose at rollout based on the per-venue criteria above. Stripe Terminal is the current default recommendation for the new venues per `merchant_processor_comparison.md`, but is not mandated — each venue's site survey can override.
- Cross-venue reporting and reconciliation must work with multiple processors. The processor-abstraction layer (DEC-064 + Phase 2 spec) provides the substrate.

**Override clause:** If a future ANVIL Corp policy requires a single processor across all venues (e.g. negotiated enterprise rates with Adyen at Phase 3 scale), DEC-063 is reversed by an explicit Amendment that names the new corporate-wide processor and the rationale. Until then, per-venue choice stands.

**References:**
- DEC-062 — standard-merchant baseline that DEC-063 inherits
- DEC-064 — primary + backup architecture that DEC-063 plugs into
- `docs/research/merchant_processor_comparison.md` — per-venue recommendation table
- `docs/design/pos_hardware_spec.md` — terminal hardware varies per chosen processor

---

## Amendment 2026-05-01 — DEC-064: Every venue must have a primary AND backup processor

**Decision:** Every ANVIL Corp venue must have **both** a primary AND a backup card processor pre-approved, integration-tested, and ready to swap to in hours — not days, not weeks. The processor-abstraction layer (Phase 2 work) must support this architecturally.

**Why this matters:**
- **Termination risk is real even at standard merchants** (DEC-062). Rate disputes, M&A churn, chargeback ratio drift past R-009 thresholds, AML flags, account-review holds — any of these can put a single-processor venue offline for days while a new MID is approved. ANVIL's Saturday-night peak doesn't survive a multi-day outage.
- **Hours, not days.** "Backup that takes 4 weeks to onboard" is not a backup; it's a recovery plan. The backup must be onboarded BEFORE the incident, settle a $1 test transaction, and have a swap mechanism gated by config (not code).
- **Architecture, not heroics.** The processor-abstraction layer (Phase 2) is what makes this work — without per-venue config that selects which processor handles a given transaction, "swap to backup" means an emergency code deploy at 2am Saturday. Unacceptable.

**What this requires:**

1. **Per-venue config, not per-app config.** Each venue's `site_config.json` (or equivalent) lists its primary AND backup processor with their respective adapter names. Switching is a config flip + bench restart, not a code change.
2. **Both processors integration-tested at venue rollout.** A backup that's "approved but never tested" is also not a backup. Rollout playbook (PR C, item 11) includes the test step.
3. **Adapter parity.** The processor-abstraction layer must support the same operations (charge, refund, void, capture, settle) across primary AND backup adapters. New venues that choose a processor without an existing adapter trigger adapter development as part of rollout, not after.
4. **Operational runbook.** Operators / on-call must know how to invoke the swap. The runbook (`docs/RUNBOOK.md`) includes a "primary processor down" procedure with the exact `bench set-config` command and verification steps.

**Open instances (status as of 2026-05-01):**
- **Hamilton:** Primary = Fiserv (running). Backup = NOT YET SELECTED. New open task in `inbox.md` (PR C, item 13) to select + pre-approve a backup. Helcim was the prior suggestion; reassess against current options.
- **Philadelphia / DC / Dallas:** Primary + backup pending per-venue rollout.

**Override clause:** The "two processors per venue" rule may be relaxed only with an explicit Amendment naming the venue and the operational mitigation (e.g. very-low-volume venue where 24h offline is acceptable, or a venue using a multi-acquirer aggregator that itself has internal redundancy). Until then, two-processors-per-venue stands.

**References:**
- DEC-062 — standard-merchant baseline
- DEC-063 — per-venue processor choice (DEC-064 sits on top)
- `docs/risk_register.md` R-008 — Single-acquirer SPOF (downgraded but not eliminated)
- `docs/risk_register.md` R-009 — MATCH list 1% chargeback threshold (one of the termination triggers DEC-064 defends against)
- `docs/inbox.md` 2026-04-30 Phase 2 hardware backlog — original "Merchant abstraction" spec; DEC-064 confirms it must support primary + backup, not just primary

---

## Amendment 2026-05-03 — DEC-066: Audit-log corrections via Hamilton Board Correction (no Admin delete)

**Context.** T1-2 (per `docs/inbox/2026-05-04_audit_synthesis_decisions.md`) removes the `delete` permission from Hamilton Admin on the two audit-log DocTypes (`Asset Status Log`, `Comp Admission Log`) so audit logs become append-only at the perm-grid level. That fix is operationally fragile on its own: if a manager spots a genuine typo in an audit row (operator mis-attribution, fat-fingered status, wrong reason), there has to be a sanctioned way to correct the record — otherwise the only paths are (a) bypass the audit invariant via raw SQL or (b) live with the drift. Both are worse than what we have today.

**Decision.** **Extend the existing `Hamilton Board Correction` DocType to handle audit-log corrections.** Pattern (a) of the two patterns considered.

**Pattern (a) — chosen — extend Hamilton Board Correction.** The DocType already exists with `track_changes: 1` and admin-only-by-Frappe-convention permissions (per `permissions_matrix.md` Notable Patterns). Today it captures Venue Asset corrections via a `venue_asset` Link + `old_status` / `new_status` / `reason` / `operator` / `timestamp`. Extension shape:

- Replace the `venue_asset` Link with a polymorphic target via Frappe's standard pattern: `target_doctype` (Select: `Venue Asset`, `Asset Status Log`, `Comp Admission Log`) + `target_name` (Dynamic Link, options field is `target_doctype`).
- Add `target_field` (Data, optional — for field-level corrections like "wrong reason on a single row").
- Keep `old_status` / `new_status` for backward-compat on Venue Asset records (or rename to `old_value` / `new_value` and use the same fields polymorphically — preferred).
- `reason` (existing Text, made `reqd: 1`) — every correction must explain itself.
- `operator` (existing Link to User) becomes "the person who performed the correction" — auto-set to `frappe.session.user` in `before_insert`.
- `timestamp` auto-set in `before_insert`.

The Hamilton Board Correction row IS the correction record. The original audit-log row stays pristine. Forensic reconstruction = read the original row + any Hamilton Board Correction rows pointing at it.

**Pattern (b) — rejected — new `Audit Log Correction` DocType.** Cleaner separation in principle, but: (i) creates a third correction-tracking surface alongside Hamilton Board Correction and ERPNext's own version table, fragmenting the audit forensic story; (ii) requires a brand-new DocType migrate vs an extension of an existing one; (iii) duplicates the perm-grid + admin-only-by-convention pattern that Hamilton Board Correction already encodes. The one place pattern (b) wins is strict immutability of the audit-log row's surface — which (a) also achieves because the original row is not modified, only referenced.

**What this unblocks.** T1-2 (drop `delete` from Hamilton Admin on `Asset Status Log` + `Comp Admission Log`). Without DEC-066's pattern, T1-2 would create an audit log that managers cannot correct without violating the invariant. With DEC-066, the correction surface exists and is itself audit-logged.

**Manager workflow on launch (the operational story).**

1. Manager spots a typo or mis-attribution on an `Asset Status Log` or `Comp Admission Log` row during reconciliation review.
2. Manager opens a new `Hamilton Board Correction` (via the standard form or a future button on the audit-row form).
3. Manager fills in:
   - `target_doctype` (e.g. `Asset Status Log`)
   - `target_name` (the audit row's `name`)
   - `target_field` (optional — e.g. `reason`)
   - `old_value` / `new_value` (what the row says vs what it should say)
   - `reason` (free text — REQUIRED — explaining why the correction is being made)
4. Save submits the correction as its own audit row. Original audit row is untouched.
5. Future reads of the audit row should surface "this row has N corrections — see Hamilton Board Correction <ids>" via a server-side helper.

**What still needs implementing (not in this DEC).**

- ~~DocType schema change to add the polymorphic target fields. This requires `bench migrate`.~~ **Shipped 2026-05-03** — `Hamilton Board Correction` schema converted from child table to standalone DocType with `target_doctype` (Select), `target_name` (Dynamic Link), `target_field`, `old_value`, `new_value`, plus `reason`/`operator`/`timestamp` made required. Legacy fields kept in collapsible "Legacy (pre-DEC-066)" section. `bench migrate` required.
- ~~Server-side helper~~ **Shipped 2026-05-03** — `submit_admin_correction()` whitelisted endpoint in `hamilton_erp/api.py`. Hamilton Admin / System Manager only. Audit-log targets (Asset Status Log, Comp Admission Log) are logged-only; mutable targets (Cash Drop, Venue Asset) are mutated AND logged. Cash Drop mutations set `frappe.flags.allow_cash_drop_correction` to bypass T0-4's immutability guards.
- Optional UI button on `Asset Status Log` / `Comp Admission Log` form views to open a pre-filled Hamilton Board Correction. **Deferred** — endpoint can be called from a JS client script today; the form button is ergonomic, not load-bearing.
- Server-side helper (e.g. `get_corrections_for(doctype, name)`) for the read path. **Deferred** — Hamilton Board Correction list view filtered on `target_doctype` + `target_name` covers the read path today.

**Permission grid.** No change to Hamilton Board Correction's permissions. It remains admin-only by Frappe convention (no role rows = System Manager only). Only Chris can issue corrections. **This is intentional** — corrections are infrequent and high-trust; making them widely available defeats the audit-log immutability they're designed to support.

**Closing T1-2.** With DEC-066 documented, T1-2 (drop delete from Hamilton Admin on the audit logs) can ship independently. The `_implementation_ of DEC-066's polymorphic target is a separate, schedulable PR — not a launch blocker.

**References.**
- `docs/inbox/2026-05-04_audit_synthesis_decisions.md` T1-CORRECT (the request) and T1-2 (the unblocked downstream item)
- `docs/permissions_matrix.md` Notable Patterns — Hamilton Board Correction "no role perms" pattern
- `hamilton_erp/hamilton_erp/doctype/hamilton_board_correction/hamilton_board_correction.json` — current schema
- A1 / A2 / A3 / A4 audit findings on Asset Status Log + Comp Admission Log Admin delete

---

## Amendment 2026-05-03 — DEC-068: Tier 1 cash-handling polish bundle (F1.4 + F3.5 + F3.8)

Three small Tier 1 audit findings shipped together because they're independent, low-risk, and overlap in their reviewers' attention (cash flow + reconciliation labelling).

**F1.4 — Client-side nickel rounding in cart drawer + cash modal.**

The cart drawer summary and cash payment modal previewed the unrounded grand_total (`subtotal + 13% HST`), while the server applies Canadian penny-elimination rounding (Amendment 2026-04-30 (c)) and charges the rounded amount. The drift was small (≤4¢) but produced two operator-visible bugs:

1. **Preview mismatch.** A $7.91 cart with $20 cash showed "Change $12.09" pre-Confirm; the server returned $12.10.
2. **Confirm-gate stuck.** The Confirm button gated on `cash_received >= unrounded_total`. An operator who typed the actual rounded amount due ($7.90 for a $7.91 cart) couldn't enable Confirm because the JS thought $7.91 was owed.

Fix: added a top-level `roundToNickel(value)` helper at `asset_board.js` (mirrors `frappe.utils.round_based_on_smallest_currency_fraction(value, "CAD")`). Used in:
- `_render_cart_drawer` — drawer summary `total` shows the rounded value.
- `_open_cash_payment_modal` — `total` displayed in the modal AND `due` in the Confirm-gate input handler both use the rounded value.

The API payload still sends raw cart items; the server retains rate authority and applies its own rounding. Pure UX correction.

**F3.5 — Configurable cash variance tolerance via Hamilton Settings.**

`cash_reconciliation.py` previously hardcoded `_VARIANCE_TOLERANCE_PCT = 0.02` and `_VARIANCE_TOLERANCE_MIN = 1.00`. Tightening the tolerance for high-volume cash days, or loosening it for venues with chronic small-bill miscount noise, required a code edit and a release. New behavior: `_get_variance_tolerance()` reads from two new Hamilton Settings fields:

- `cash_variance_tolerance_percent` (Percent, default 2.0)
- `cash_variance_tolerance_minimum` (Currency, default 1.00)

Defaults preserve the existing variance-flag behavior on fresh-install / migrate-pending sites; the function falls back to the module-level defaults when Settings is missing or either field is blank. Cached via `frappe.get_cached_doc` so a busy reconciliation cycle doesn't N+1 the Settings table.

**F3.8 — Rename "Operator Mis-declared" catch-all → "Multi-source Variance".**

`_set_variance_flag` had two branches that emitted the label `"Operator Mis-declared"`:

1. **Specific case** — manager + system agree, operator differs. This branch IS specifically operator misdeclaration and is unchanged.
2. **Catch-all `else`** — none of the three values agree. The cause is genuinely ambiguous (operator misdeclared *and* cash missing *and* POS error all consistent with the data). The previous label pre-judged the operator as the bad actor. Renamed to `"Multi-source Variance"` — describes the data shape (multiple sources disagree) without naming a cause. HR-impact reduction.

Added `Multi-source Variance` to the `variance_flag` Select options in `cash_reconciliation.json`. `Operator Mis-declared` stays as a valid value because the specific-attribution branch still uses it correctly.

**Tests.**

- F1.4: three new pinning tests in `test_asset_board_rendering.py::TestV91RetailCartUXStub` — helper exists with canonical math, drawer summary uses it, cash modal Confirm-gate uses it.
- F3.5: `test_f35_tolerance_reads_from_hamilton_settings_override` in `test_cash_reconciliation.py` — tightening the tolerance via Settings flips a previously-Clean variance to a flagged variance. Restores original Settings values in teardown.
- F3.8: two tests in `test_cash_reconciliation.py` — three-way disagreement produces `Multi-source Variance`; specific-attribution case (manager+system agree, operator differs) still produces `Operator Mis-declared`.

**STOP.** `bench migrate` REQUIRED — F3.5 adds two new fields to `Hamilton Settings`, F3.8 adds a Select option to `Cash Reconciliation`. Bundle into the same Phase 3 migrate window as PR #170 (DEC-066) and PR #171 (T0-1 / DEC-067).

**Why bundled.** All three findings are LOW or MEDIUM severity, all touch cash-handling UX, and all fit comfortably under one reviewer's attention. Splitting into three PRs would triple the review/CI/migrate overhead for genuinely small changes.

**References.**
- `docs/inbox/2026-05-04_audit_synthesis_decisions.md` (T3-2 / T3-3 / T3-6 if mapped through, or original A1 F-codes F1.4 / F3.5 / F3.8)
- `hamilton_erp/api.py::submit_retail_sale` (server-side rounding contract that F1.4's preview now matches)
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js::roundToNickel`
- `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py::_get_variance_tolerance`
- `hamilton_erp/hamilton_erp/doctype/hamilton_settings/hamilton_settings.json` — new fields
## Amendment 2026-05-03 — DEC-069: T0-2 Path B — hard-disable Cash Reconciliation variance classification until Phase 3

**Decision.** `_set_variance_flag` short-circuits unconditionally to `variance_flag = "Pending Phase 3"` and `variance_amount = actual_count - system_expected` (NEW-1 bundled). The three-way classifier (Clean / Possible Theft or Error / Operator Mis-declared) is not invoked at Phase 1. Managers reconcile cash physically per the manual procedure documented in `HAMILTON_LAUNCH_PLAYBOOK.md` #3 and `RUNBOOK.md` §7.2 (manager counts envelope, matches declared amount on printed label, signs paper). Path A (the real `system_expected` calculation) ships in Phase 3 as part of the Cash Reconciliation redesign documented in `docs/design/cash_reconciliation_phase3.md`.

**Why.** `_calculate_system_expected` is a Phase 3 placeholder hardcoded to 0. The previous classifier ran every reconciliation against `system = 0` and produced a false-positive variance flag on every drop with non-zero cash — see R-011 in `docs/risk_register.md` for the full failure characterization. Mitigation pre-DEC-069 was operator training to *ignore* the flag, which is a process risk that decays under shift fatigue and operator turnover.

The audit synthesis (`docs/inbox/2026-05-04_audit_synthesis_decisions.md`) classified this as a launch BLOCKER conditional on the Phase 1 scope decision (Path A vs Path B). Path B was selected because (a) Cash Reconciliation is *not* in the Phase 1 launch scope, (b) the manual reconciliation procedure is operationally identical to what managers do today on paper at other venues, and (c) Path A's full implementation has its own rollout and validation requirements that don't fit the launch window.

**Mechanism.**

1. `cash_reconciliation.json` — `"Pending Phase 3"` added to the `variance_flag` Select options (alongside the existing four). Bundle into the Phase 3 migrate window.
2. `cash_reconciliation.py::_set_variance_flag` — body replaced with two assignments: `self.variance_amount = flt(self.actual_count) - flt(self.system_expected)` and `self.variance_flag = "Pending Phase 3"`. The previous three-way logic is gone, not commented out — restoring it requires reverting this DEC explicitly.
3. `cash_reconciliation.js::refresh` — adds an orange dashboard headline on the form referencing `HAMILTON_LAUNCH_PLAYBOOK.md` #3 and `RUNBOOK.md` §7.2, so a manager opening a Cash Reconciliation today knows what they're seeing and where the manual procedure lives.
4. `RUNBOOK.md` §7.2 — explicit manual reconciliation steps + the closed-deferred note for R-011.
5. `HAMILTON_LAUNCH_PLAYBOOK.md` #3 — pinned to the manual procedure as the Phase 1 rule.

**NEW-1 bundled.** The audit found that `variance_amount` was never written, so the form's Currency field was empty even after reveal. NEW-1 fixes this with one line: `self.variance_amount = flt(self.actual_count) - flt(self.system_expected)`. Until Phase 3 the value equals `actual_count` (since `system_expected = 0`) — but the same line continues to work correctly against the real calculation when Phase 3 lands. Bundling NEW-1 here keeps `_set_variance_flag` as the one place that owns reveal-time field writes.

**Tests.** `test_t0_2_path_b_variance_flag_pending_phase_3_for_any_inputs` in `test_cash_reconciliation.py` pins the contract: four representative input shapes that previously produced each of the four legacy classifications all resolve to `"Pending Phase 3"`, and `variance_amount` is non-zero where `actual_count` is non-zero. A future regression that re-enables the classifier without also delivering the real `system_expected` calculator surfaces here.

**STOP.** `bench migrate` REQUIRED — Select option change. Bundle into the Phase 3 migrate window (alongside DEC-066 / DEC-067 / DEC-068 / T0-4 + T1-4).

**Closing R-011.** The watch-points in R-011 ("manager onboarding must explicitly state ignore variance flag", "Phase 3 implementation must include real system_expected calculator first", "manager attrition reactivates the false-alarm pattern") are superseded by Path B: the flag now reads "Pending Phase 3" by code, not by training. R-011 status flips to **Closed (deferred to Phase 3)**.

**Reversal cost.** Reverting Path B requires (a) restoring the three-way classifier body in `_set_variance_flag`, (b) ensuring `_calculate_system_expected` is no longer a placeholder (or accepting the false-positive flag pattern again), and (c) removing the dashboard headline from the JS. Path A then becomes the natural reversal target — the path forward, not back to the broken classifier.

**References.**
- `docs/inbox/2026-05-04_audit_synthesis_decisions.md` T0-2 Path B
- `docs/risk_register.md` R-011
- `docs/design/cash_reconciliation_phase3.md` (Phase 3 redesign target)
- `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py::_set_variance_flag`
- `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.js::refresh`

---

## Amendment 2026-05-03 — DEC-070: `get_doc_before_save() is None` defensive bypass in Cash Drop guards (soft-spot documented)

**What this DEC documents.** Both `_validate_immutable_after_first_save` and `_validate_immutable_after_reconciliation` in `cash_drop.py` (T0-4, PR #168) include a defensive bypass of the form:

```python
def _validate_immutable_after_first_save(self):
    if self.is_new():
        return
    if getattr(frappe.flags, "allow_cash_drop_correction", False):
        return
    original = self.get_doc_before_save()
    if original is None:
        return  # ← the soft-spot
    changed = [f for f in _IMMUTABLE_AFTER_FIRST_SAVE if self.get(f) != original.get(f)]
    ...
```

The `if original is None: return` line is reached only on UPDATEs of existing docs (because `self.is_new()` short-circuits inserts above it). Under Frappe v16 today, `get_doc_before_save()` reliably returns the pre-save Document instance during a normal `db_update` path. The bypass exists to swallow an unknown-trigger edge case rather than throw — a deliberate "fail open" choice when the pre-save snapshot is unavailable.

**Why the morning review of PRs #165–#169 flagged this.**

The reviewer's concern (recorded in `docs/inbox.md` 2026-05-03 cleanup follow-ups, now closed): "if a future Frappe minor changes the semantics of `get_doc_before_save` (e.g. returns an empty `Document` instead of `None`), the guard silently no-ops and the immutability invariant breaks." On closer read the failure mode is the opposite — an empty-Document return would make `original.get(f)` always return `None`, the field-change comparison would flag every field as "changed", and the validator would *falsely throw* on every save (blocking, not bypassing). Either way: the bypass is defending against a code path we cannot describe today, which is itself a code smell.

**The decision.**

1. **Keep the bypass for now.** Cash Drop guards are recently shipped (PR #168, 2026-05-03); we have zero production telemetry on whether `get_doc_before_save()` ever returns `None` post-`is_new()` for a Hamilton Cash Drop. Removing the bypass and letting the guard throw on `None` could surface a real edge case as a launch-week regression. Defensive-but-documented is the right Phase 1 posture.

2. **Pin `self.is_new()` as the only "new doc" check.** Already in place. Any future contributor adding a similar guard to Cash Drop or any Hamilton-owned DocType MUST use `self.is_new()` for the new-doc short-circuit, NOT `if self.get_doc_before_save() is None`. Documented contract.

3. **Replace the bypass with a fail-loud assertion when telemetry justifies.** Once production has run ≥30 days with no `Asset lock TTL expired`-style Error Log entries indicating a `get_doc_before_save() is None` post-insert hit (we don't currently log that path — the next step is to add `frappe.log_error(title="Cash Drop guard saw get_doc_before_save() is None unexpectedly")` in the bypass), revisit this DEC and consider promoting `if original is None` to `frappe.throw(...)`. The fail-loud version surfaces the unknown trigger as an investigable Error Log entry instead of silently passing.

**What this DEC is NOT.**

- Not a deferred bug fix. The current code is correct under the documented Frappe v16 contract for `get_doc_before_save`.
- Not a "remove the bypass" mandate. The bypass earns its keep until we have data showing it never fires.
- Not a generalization. Other Hamilton DocTypes that do field-immutability checks should follow the `is_new()` pin contract above; the `is None` defensive pattern stays scoped to Cash Drop where it currently lives.

**Follow-up work (not blocking).** Add a `frappe.log_error(title="Cash Drop unexpected get_doc_before_save None")` instrumentation inside both bypasses so we get production data on whether this code path ever fires. If it never fires in 30 days, replace with `frappe.throw`. If it does fire, the Error Log entry shows under what conditions, and we can write a real validator for that path.

**References.**
- `hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.py::_validate_immutable_after_first_save` (line ~153)
- `hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.py::_validate_immutable_after_reconciliation` (line ~193)
- DEC-066 — admin-correction endpoint that uses the `frappe.flags.allow_cash_drop_correction` carve-out path the bypass was paired with
- Audit synthesis morning review of PRs #165–#169 (2026-05-03), originally surfaced in `docs/inbox.md` cleanup follow-ups
## Amendment 2026-05-03 — DEC-067: T0-1 idempotency on `submit_retail_sale`

**Decision.** `hamilton_erp.api.submit_retail_sale` accepts an optional `client_request_id` parameter; duplicate calls with the same id return the original Sales Invoice's response payload without creating a second SI. Idempotency state is persisted in a new DocType `Cash Sale Idempotency` (one row per token, unique-indexed on `client_request_id`, retention window 24 h via daily scheduler purge).

**Why.** Pre-T0-1 code path: the cart's `_open_cash_payment_modal` did not clear the cart on error and the comment at `asset_board.js:710` was explicit — `// Cart intentionally NOT cleared — operator can retry.` Combined with the lack of an idempotency contract on the server, an operator who saw a "Sale failed" toast after a network drop *post-commit but pre-response* could re-tap Confirm and produce a second SI: double cash payment line, double stock decrement, customer charged twice. Audit-synthesis classified this as a launch BLOCKER — see `docs/inbox/2026-05-04_audit_synthesis_decisions.md` T0-1.

**Mechanism (server).**

1. `submit_retail_sale` accepts `client_request_id: str | None = None`.
2. **Fast path:** if the id is provided AND a `Cash Sale Idempotency` row exists with that key, the endpoint returns a reconstructed response payload from the linked Sales Invoice via `_build_retail_sale_response()` — no new write.
3. **Normal path:** the existing SI insert + submit flow runs unchanged.
4. **Tail:** on success the endpoint inserts a `Cash Sale Idempotency` row linking the token to `si.name`. The unique constraint on `client_request_id` is the durable enforcement against the narrow concurrent-retry race — the loser's insert raises `UniqueValidationError`, rolling back its just-submitted SI; the operator retries and the fast path returns the winner's payload.

**Mechanism (client).** `_open_cash_payment_modal` generates a UUID via `crypto.randomUUID()` *once per modal open* (not per click), captured in a closure variable, and passes it as `client_request_id` on every Confirm tap. Same modal session = same UUID = idempotent retries. New modal open = new UUID = new transaction.

**Why a separate DocType (vs. stuffing the field on Sales Invoice).** The idempotency record lives on its own retention schedule (24 h purge via `purge_old_idempotency_records` daily scheduler job). Sales Invoices are accounting records and must not be deleted; idempotency tokens are operational and should be GC'd aggressively. The unique index is also scoped only to the keys we care about.

**Why the tail-write pattern (vs. claim-key-first).** The spec considered inserting the idempotency row *before* SI creation (claim the key, then write the SI, then update the row with `si.name`). Tradeoff: claim-first prevents duplicate SIs even on the tight race, but requires a two-phase write and an orphan-cleanup path for crashes between claim and SI submit. Tail-write is simpler and the race window is narrower than the claim path's orphan window — the loser's `UniqueValidationError` rolls back its own SI in the same transaction. Acceptable for a Hamilton-scale operator (1–2 cashiers, single venue). Phase 2 may revisit if multi-cashier concurrency becomes the norm.

**Retention.** 24 h, set in `purge_old_idempotency_records`. The window outlives the operational network-retry window (seconds to minutes) and matches the shift-reconciliation window operators work in, so any retry that's still relevant to a same-shift operator falls inside it. Older rows are dead state.

**Permissions.** `Cash Sale Idempotency` has zero role-permission rows (admin-only by absence, System Manager only). The endpoint inserts with `ignore_permissions=True` — same delegated-capability pattern as the `Sales Invoice` write itself.

**Tests.** Four pinning tests in `test_retail_sales_invoice.py::TestSubmitRetailSaleIdempotency`:
- Same `client_request_id` returns the same SI; stock decrements only once.
- Two distinct ids produce two distinct SIs.
- Calls without `client_request_id` work exactly as before; no idempotency rows created.
- The idempotency row's `sales_invoice` link points at the original SI.

**Operational mitigation that this DEC retires.** The pre-T0-1 advice "train operators that 'Sale failed' might mean 'succeeded but network dropped — verify SI exists in Desk before retrying'" is no longer needed — the cart can retry safely.

**STOP.** `bench migrate` REQUIRED before this DEC's code goes live. New DocType has no rows on the production DB until migrate runs.

**References.**
- `docs/inbox/2026-05-04_audit_synthesis_decisions.md` T0-1
- `hamilton_erp/api.py::submit_retail_sale`, `_build_retail_sale_response`, `purge_old_idempotency_records`
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js::_open_cash_payment_modal`
- `hamilton_erp/hamilton_erp/doctype/cash_sale_idempotency/`

---

## Amendment 2026-05-03 — DEC-071: Asset Board UI walkthrough fixes (findings #1–#6)

Six UI findings surfaced during a 2026-05-03 Asset Board walkthrough. Each shipped as its own PR; collected here as a single design decision because they all sharpen the operator-side rendering contract.

**Finding #1 — Negative elapsed time on new sessions ("-29m elapsed" on a session 1 minute old).**
Root cause: Frappe stores Datetime fields as UTC strings without a timezone suffix (`"2026-05-03 18:31:00"`). The browser parsing `new Date("2026-05-03 18:31:00")` interprets the string as *local* time on Chrome, so an operator outside UTC sees a negative-offset interpretation of "now minus session_start". A fresh session in EST showed -29m because the local interpretation pushed the session into the future.
Fix: a top-level `parseFrappeDatetime(str)` helper in `asset_board.js` that explicitly converts the Frappe string to ISO 8601 UTC (`"2026-05-03T18:31:00Z"`). All `new Date(asset.session_start)` / `new Date(asset.hamilton_last_status_change)` / `new Date(a.last_vacated_at)` call sites updated to use it. Same root-cause class fixed everywhere it appeared.
Captured as LL-040 so future code that consumes Frappe datetimes via JSON inherits the lesson.

**Finding #2 — Retail tile redesign: no SKU, name top centered, price bottom centered (or OUT OF STOCK), no red.**
Three tile-rendering issues collapsed into one redesign per the walkthrough spec:
- The SKU code (`BAR-ENRG`, `WAT-500`, etc.) was rendering on every retail tile. Operators sell by name + price, never by SKU. Removed.
- Item name moved to centered-top, price to centered-bottom. When `stock <= 0`, the price slot is replaced by the literal string "OUT OF STOCK".
- Color states reduced to two: green border (in stock) or grey border (out of stock). The previous amber low-stock state was conflating "running low" with "different category"; the previous red OOS state was conflating with Occupied (red border) elsewhere on the board. **No red anywhere on retail tiles** — red is reserved for asset Occupied.
- The previous "Out of stock" toast on tile-tap (small, red, ≈2s fade) was redundant once the tile itself shows OUT OF STOCK without any tap. Removed; tap on an OOS tile is now a silent no-op.

CSS additions: `.hamilton-retail-oos` (grey palette), `.hamilton-retail-oos-label` (the in-tile label). The new `.hamilton-retail-tile` flex layout anchors name top / price (or OOS label) bottom; stock count parks small in the top-right corner.

**Finding #3 — OOS toast.**
Subsumed by finding #2's "no toast — OUT OF STOCK shows on the tile" clause. No separate fix.

**Finding #4 — Watch tab section order didn't match tab bar order.**
Watch grouped overtime tiles by raw `asset_tier` and emitted sections in arbitrary insertion order — "Deluxe Single" might appear before "Single Standard" (both belong under the Single tab) and Lockers showed up wherever they happened to land. Fix: iterate `this.tabs` in tab-bar order (Lockers, Single, Double, VIP, GH Room), filter overtime tiles against each tab's existing `filter` function, emit a section per non-empty tab. Section headers use the tab labels ("Single") instead of raw tier names. Watch now visually mirrors the tab bar above it.

**Finding #5 — Single-tap Vacate on Watch tab.**
The Watch tab surfaces overtime + OOS tiles for fast triage. The existing tile-expand flow worked but produced a two-step Vacate UX (tap "Vacate" parent, sub-buttons reveal, tap "Key Return" or "Rounds"). Two taps inside an attention-flagged context is friction — operators came to Watch because they already know the room is overtime. Fix: when `active_tab === "watch"`, skip the parent toggle and surface two single-tap buttons inline: `Vacate (Rounds)` and `Vacate (Key Return)`. Both reuse the existing `data-action="vacate-rounds"` / `"vacate-key"` handlers, so the underlying lifecycle paths are unchanged. Other tabs keep the V9 D4.6 two-step flow.

**Finding #6 — No stock seeded on fresh install.**
`seed_hamilton_env._ensure_retail_items` documented that "inventory is NOT seeded by this patch" and left stocking to a manual `bench --site … console` step. In practice, fresh installs were unusable: every retail tile rendered as OOS until someone remembered to run a Stock Entry. Fix: `_ensure_retail_initial_stock()` runs after `_ensure_retail_item_defaults` and seeds **per-item realistic opening quantities** via Material Receipt Stock Entries:
- Water 500ml × 100
- Sports Drink 500ml × 50
- Protein Bar × 50
- Energy Bar × 50

Quantities live as the `opening_stock` key on each entry in `HAMILTON_RETAIL_ITEMS`. Idempotent: only seeds when the Bin's `actual_qty` is `<= 0`. Skips silently when company / warehouse aren't yet seeded (matches the existing skip-on-prereqs-missing pattern in `_ensure_retail_item_defaults`).

**References.**
- LL-040 — the Frappe datetime → JS Date timezone trap (parseFrappeDatetime contract)
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js` — parseFrappeDatetime helper, _render_retail_tile, click handler, _render_watch_content, _render_expand_panel
- `hamilton_erp/public/css/asset_board.css` — `.hamilton-retail-oos`, `.hamilton-retail-oos-label`, restructured `.hamilton-retail-tile` flex layout
- `hamilton_erp/patches/v0_1/seed_hamilton_env.py::_ensure_retail_initial_stock` — opening-stock seed

---

## Amendment 2026-05-03 — DEC-072: Frappe Claude Skill Package adopted alongside Context7

**Numbering note.** DEC-066 through DEC-071 are documented on still-open feature branches (PRs #170, #171, #172, #174, #178, #179) that haven't merged to main yet. DEC-072 is registered here on its own docs PR; the lower-numbered DECs land when their PRs merge.

**Decision.** Install the Frappe Claude Skill Package (`OpenAEC-Foundation/Frappe_Claude_Skill_Package`, 60 deterministic skills, MIT) as personal skills at `~/.claude/skills/frappe-*`. Reference it from `CLAUDE.md` under Frappe v16 Conventions. Use **alongside** the existing Context7 tool, not as a replacement.

**Why.** A 2026-05-03 evaluation prompted by the inbox queue ("Pre-DC: evaluate Frappe Claude Skill Package") tested whether the skill package meaningfully improves output quality over Context7 on a real Hamilton scenario.

**Test prompt.** "When should I use `frappe.db.set_value` vs `frappe.get_doc().save()` in a controller? I need to update a flag field on a related Cash Drop after a Cash Reconciliation submits — specifically the `reconciled` boolean and a `reconciliation` link. The Cash Drop has `track_changes=1` and a `validate` hook." This is the exact bug-class T3-1 (PR #175) just fixed.

**Context7 answer.** Mechanically describes both methods. States `set_value` "bypasses DocType validations and signals." Doesn't volunteer that `track_changes` is bypassed. Doesn't make a recommendation for the user's scenario. Tone: API reference.

**Skill package answer (`frappe-core-database` SKILL.md + anti-patterns reference).** Decision tree: *"With validations + hooks → `frappe.get_doc().save()`. Direct DB (no hooks) → `frappe.db.set_value()` or `doc.db_set()`."* Anti-pattern #7 makes the rule explicit: *"`db_set`/`set_value` is acceptable ONLY for: hidden fields, counters, timestamps, performance-critical background jobs."* For Hamilton's scenario (operational flag, audit-relevant via `track_changes`, on a controller-validated DocType), the answer is unambiguous: ORM path. The skill catches the exact lesson Hamilton learned the hard way during T3-1.

**Verdict.** Additive, not redundant.

- **Context7** — what does this method do? (API reference, live, generic)
- **Skill package** — when SHOULD I use which method? (decision trees, anti-patterns, v14/v15/v16 differences)

The two layers don't overlap. Context7 stays for "show me the latest signature for `frappe.X.Y`." Skills handle "I'm about to write a controller — flag the gotchas before I code."

**Coverage spot-check against bugs Hamilton hit during 2026-05-02/03:**

| Hamilton bug | Skill that catches it |
|---|---|
| T3-1: `db.set_value` bypasses `track_changes` | `frappe-core-database` anti-pattern #7 |
| T0-4 / DEC-070: `get_doc_before_save() is None` defensive bypass | `frappe-syntax-controllers` lifecycle methods |
| T1-5: `UniqueValidationError` race on concurrent submit | `frappe-impl-controllers` flags + concurrency |
| T0-1 / DEC-067: idempotency on `@frappe.whitelist` endpoints | `frappe-impl-whitelisted` workflows |
| LL-040: `new Date(frappe_datetime_string)` timezone trap | Not directly covered — JS-side trap. Skills focus on server-side patterns. `frappe-syntax-clientscripts` is the closest neighbour. |

**Boundaries / what's intentionally not duplicated.**

The skill package documents *generic Frappe patterns*. Hamilton's `decisions_log.md` / `lessons_learned.md` document *Hamilton-specific decisions* (DEC-005 blind cash, DEC-019 three-layer locking, etc.). These are different layers — generic Frappe doesn't override Hamilton conventions; Hamilton conventions don't try to teach generic Frappe. No content was copied between repos.

**What changed.**

- `~/.claude/skills/frappe-*` — 60 skill folders installed (personal skills, MIT, drop-in copy from `skills/source/` flattened).
- `CLAUDE.md` — Frappe v16 Conventions section now lists the skill package as the first source to consult.
- `docs/inbox.md` — "Pre-DC: evaluate Frappe Claude Skill Package" entry removed (this DEC closes it).

**Reversibility.** Trivial. To remove: `rm -rf ~/.claude/skills/frappe-*`, revert the CLAUDE.md change, and add a note here. Skills don't write to the repo, modify settings, or alter Claude Code's harness configuration — they're just markdown files Claude Code auto-discovers.

**Update cadence.** No automated update. The upstream repo is active (last commit 2026-04-01); periodically check `git log` and pull fresh skill content if a meaningful release lands. Don't auto-update — review changes first to avoid drift surprises.

**References.**
- https://github.com/OpenAEC-Foundation/Frappe_Claude_Skill_Package — upstream
- `~/.claude/skills/frappe-core-database/` — example skill used in the test prompt
- T3-1 (PR #175) — the Hamilton bug whose decision tree the skills would have surfaced proactively
- `docs/inbox.md` — closed entry that triggered this evaluation

---

## Amendment 2026-05-04 — DEC-077: Accept `db_set("owner", ...)` post-submit on Sales Invoice (audit F1.1)

**Decision.** The `db_set("owner", real_user, update_modified=False)` call in `submit_retail_sale` (api.py ~706) stays as-is. We deliberately accept that the ownership rewrite does not produce a `tabVersion` row; the `Sales Invoice.remarks` line ("Recorded via cart by {user}") and the doctype's `track_changes` history on the remarks field together provide the durable audit trail.

**Why.** The alternative — `frappe.get_doc("Sales Invoice", si.name).save()` after the owner flip — would re-trigger ERPNext's heavy post-submit validation chain (taxes, GL re-post, payment matching) on a document that is already in the desired state. The cost / risk of that path is much higher than the audit-trail benefit of one extra `tabVersion` row, especially given (a) the cart elevation is already audit-tracked via S3.2's planned dedicated log row (DEC-082) and (b) the remarks-line edits are themselves track_changes-captured. Phase-2 upgrade path: introduce a dedicated tracked Custom Field `cart_recorded_by` (Link → User) on Sales Invoice and `db_set` to it instead of overloading `owner`. Defer until Phase 2 to avoid a Custom Field migration in Phase 1.

**What changed.** Documentation only — no code change in this PR. DEC-077 added.

**References.** Audit `docs/audits/frappe_skills_audit_2026-05-04.md` § F1.1; DEC-005 (blind cash); DEC-067 (idempotency); planned DEC-082 / S3.2 (dedicated cart elevation audit log); skill `frappe-core-database` (db_set anti-pattern #7).

---

## Amendment 2026-05-03 — DEC-101: Audible + persistent overtime alert

**Decision.** When ANY asset transitions from not-overtime to overtime, the Asset Board (a) plays a short tone via WebAudio and (b) renders a persistent red banner at the top of the board. The banner stays visible regardless of tab and clears only when ALL overtime assets are resolved. Tapping the banner jumps to the Watch tab.

**Why audible + persistent.** The Watch tab badge alone is a passive signal — operators only see it if they happen to look at the tab bar. Overtime is a cash-handling deadline (the operator must vacate or extend); a missed transition silently extends the customer's stay without billing. The tone fires the operator's attention even when they're at the door or in the cart drawer; the banner persists so a momentary glance away doesn't lose the signal. Combined, they meet "real signal" rather than "checkable status."

**Why operator cannot dismiss without action — design rationale (rejected alternative).** A "dismiss" button on the banner was considered and rejected. The rationale for "dismissible" was operator agency — they shouldn't have to look at the banner if they're already aware. The rationale for "not dismissible" was the failure mode: an operator dismisses the banner, then forgets, and the overtime quietly persists into another shift. The cost of an annoying-but-unmissable banner is much smaller than the cost of a silently-aged overtime that sits past the cash-drop deadline. The banner is the cheap insurance; the operator can act on the asset (vacate / mark clean / extend) and the banner clears itself on the next 15-second tick.

**Audio mechanism.** No bundled mp3, no network fetch. A short (220 ms) 880 Hz square envelope is generated on demand via WebAudio (`AudioContext` + `OscillatorNode`). The context is created lazily on the first beep so the browser's autoplay-gate user-gesture requirement is naturally satisfied (by then the operator has already navigated to the page). Failure modes (denied AudioContext, unsupported browser) are caught silently — the visual banner is the durable signal; audio is best-effort.

**Detection mechanism — name-set transition.** On every live-tick (15 s, the existing cadence), the JS computes the current set of overtime asset names and compares to the previous tick's set. Only NEW members of the set trigger the beep. This avoids re-beeping every 15 seconds for the same overtime asset (which would push the operator to mute their tab — the worst outcome).

**What changed.**
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js` — new methods `_detect_overtime_transitions`, `_play_overtime_beep`, `_update_overtime_banner`. Constructor now initializes `overtime_seen` (Set) and `overtime_audio_ctx` (lazy). Live-tick now calls the detector and banner updater on every tick (banner update runs even when the overlay is open; tab re-render does not).
- `hamilton_erp/public/css/asset_board.css` — `.hamilton-overtime-banner` styling with a subtle pulse animation.
- `hamilton_erp/test_asset_board_rendering.py` — substring contract tests.

**Migrate flag.** None.

**References.** Existing `_compute_time_status` returning `"overtime"` (asset_board.js:402). DEC-071 Watch tab grouping. Live-tick cadence `LIVE_TICK_MS = 15000`.

---

## Amendment 2026-05-03 — DEC-104: Offline banner — non-blocking, cash-warning

**Decision.** When the Asset Board loses its server connection, render a full-width dark-red banner at the top: "System offline — do not process cash until reconnected." The banner auto-dismisses when the connection returns. Operators cannot dismiss it manually; it is not modal — interaction with the board continues.

**Why a banner, not a modal blocking interaction.** A modal would prevent the operator from reading current board state during the outage. That's a regression: the operator may legitimately need to scan the room/locker assignments to answer a guest, complete a vacate the system already accepted, or note a Dirty asset that just freed up. Blocking those reads adds friction with no safety benefit — the data they're reading was committed before the outage and is still on screen.

The dangerous surface during an outage is *cash processing*: a Sales Invoice submit that fails halfway, leaving the customer charged on their card but no SI in the database (the inverse of T0-1's idempotency case). The banner's wording flags exactly that surface ("do not process cash") rather than blocking everything indiscriminately.

**Detection — both Frappe Socket.IO AND browser online/offline events.** We hook two surfaces:
1. `frappe.realtime.socket.on("disconnect"|"connect"|"reconnect", ...)` — the Socket.IO client that Frappe wraps. Catches server-side outages (the Frappe socket dies but the operator's Wi-Fi is fine). Wrapped in try/catch so we don't fail on Frappe builds that hide the underlying socket.
2. `window.addEventListener("offline"|"online", ...)` — browser-level network change. Catches OS-level outages (Wi-Fi off, ethernet unplugged) before the Socket.IO heartbeat times out, surfacing the banner faster.

The two surfaces are belt-and-suspenders. Either firing shows the banner; both must clear before the banner is hidden (well, in practice the second clear is a no-op because `_show_offline_banner` is idempotent on element presence).

**On-load check.** If the operator opens the Asset Board while already offline (Wi-Fi off when they navigate), `navigator.onLine === false` triggers the banner immediately rather than waiting for the next online/offline event. Without this, operators load a stale board with no warning.

**Lifecycle / teardown.** Both `_on_offline` and `_on_online` are stashed on `this` so `teardown()` can detach them by reference. Anonymous handlers passed to `addEventListener` cannot be removed cleanly; binding once + storing the reference is the standard pattern.

**What changed.**
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js` — `listen_realtime` now calls `_setup_offline_listeners`. New `_setup_offline_listeners`, `_show_offline_banner`, `_hide_offline_banner` methods. `teardown` detaches the listeners.
- `hamilton_erp/public/css/asset_board.css` — `.hamilton-offline-banner` styling.
- `hamilton_erp/test_asset_board_rendering.py` — substring contract tests under `TestOfflineBannerContract`.

**Migrate flag.** None.

**References.** `frappe.realtime.socket` (Socket.IO client wrapper); `navigator.onLine` MDN; DEC-101 (overtime banner — different colour palette + animation, intentionally distinct).
## Amendment 2026-05-04 — DEC-073: Multi-venue isolation lives at the bench level, not in API filters (audit F2.4)

**Decision.** `hamilton_erp.api.get_asset_board_data` does NOT filter assets by company/venue. Per-venue isolation is solved by deploying one Frappe Cloud site per venue, NOT by adding a `filters={"company": ...}` clause inside the endpoint.

**Why this came up.** Frappe skills audit 2026-05-04 (F2.4) flagged that the endpoint has no caller-scoped filter. Read literally, it would leak every venue's assets to every authenticated operator if a second venue's data ever lived on the same site.

**Why we're not adding a filter.** Hamilton's multi-venue strategy is already site-per-venue (per DEC-062, DEC-063, DEC-064). Each venue gets its own Frappe Cloud bench + site. No two venues share a database. The board endpoint runs against a single-tenant DB; cross-venue leakage is operationally impossible. Adding a `company` filter would imply the endpoint guards multi-tenancy (it doesn't; the bench does) and risks fail-open silent zero-asset boards if `frappe.defaults.get_user_default("Company")` returns None.

**What this DEC pins.**

1. Hamilton ERP runs **one bench per venue, one site per bench**. This is the only multi-tenancy boundary.
2. Endpoints in `hamilton_erp/api.py` are **not required** to add company/venue filters.
3. If a future requirement pushes toward shared-bench multi-tenancy, this DEC must be reversed and `Venue Asset.company`-scoped filters added across every endpoint that returns asset / session / cash data.

**Pre-second-venue checklist.**
- [ ] Confirm the new venue has its own Frappe Cloud bench + site.
- [ ] Confirm `frappe.conf.hamilton_company` is pinned per site.
- [ ] If shared-bench is ever proposed, reverse DEC-073 explicitly, then audit every endpoint for tenant filters before going live.

**References.**
- F2.4 in `docs/audits/frappe_skills_audit_2026-05-04.md`
- DEC-062 / DEC-063 / DEC-064 — the per-venue architecture
- `hamilton_erp/api.py::get_asset_board_data` — endpoint with intentionally no tenant filter
## Amendment 2026-05-04 — DEC-085: Unified `{"status": "ok", ...}` envelope on action endpoints (audit F2.2)

**Decision.** All single-asset action endpoints (`start_walk_in_session`, `vacate_asset`, `clean_asset`, `set_asset_oos`, `return_asset_from_oos`) return `{"status": "ok", ...}` with optional extra keys for endpoint-specific data. `start_walk_in_session` now returns `{"status": "ok", "session": session_name}` instead of `{"session": session_name}`.

**Why.** The audit F2.2 flagged that the surface mixed `{"session": ...}`, `{"status": "ok"}`, and `{"status": "phase_1_disabled"}`. Idempotency wrappers (DEC-067 / T0-1) and future client code benefit from a single `status` key to branch on. The Asset Board JS does not consume the return value today, so the change is non-breaking.

**What changed.** `hamilton_erp/api.py::start_walk_in_session` updated to add `"status": "ok"`. Other four already return `{"status": "ok"}`. `assign_asset_to_session`'s `phase_1_disabled` envelope is left as-is (intentional — it signals a different state).

**References.** Audit `docs/audits/frappe_skills_audit_2026-05-04.md` § F2.2; DEC-067 (idempotency); skill `frappe-impl-whitelisted` (return envelope consistency).

---

## Amendment 2026-05-04 — DEC-074: Rate limiting on mutating whitelisted endpoints (audit F2.1)

**Decision.** All 7 state-mutating whitelisted endpoints in `hamilton_erp/api.py` carry `@rate_limit(limit=60, seconds=60)` (per-IP). The GET endpoint `get_asset_board_data` is intentionally NOT rate-limited (read-only, called every 15 s by the live-tick).

**Why.** Frappe skills audit F2.1 flagged the absence of rate limiting on whitelisted endpoints. A compromised operator session could fire `submit_retail_sale` / `vacate_asset` / etc. as fast as the network allows; the three-layer lock prevents asset-state corruption but not rapid-fire stock depletion or cash-line spam.

**Budget.** 60/min per IP. A real cashier rings 1–2 sales/minute at peak; lifecycle operations fire <30/minute on a busy weekend. The budget is well above legitimate use, restrictive enough to bound runaway scripts or compromised-session abuse. Per-IP keying (Frappe's default) maps to per-tablet at the front desk.

**Endpoints covered (7).** `assign_asset_to_session`, `start_walk_in_session`, `vacate_asset`, `clean_asset`, `set_asset_oos`, `return_asset_from_oos`, `submit_retail_sale`. Same 60/60 budget — distinct per-endpoint budgets would be premature optimization without operational data.

**Endpoints NOT covered.**
- `get_asset_board_data` — GET, read-only, frequent live-tick.
- `submit_admin_correction` (PR #170) — still on a feature branch as of 2026-05-04. Follow-up commit on main should add the same `@rate_limit` after #170 merges.
- `purge_old_idempotency_records` — scheduler hook, not whitelisted.

**Re-tuning.** Constants `_RL_LIMIT` / `_RL_WINDOW_SECONDS` at the top of `api.py`. Single edit + redeploy if the budget needs adjustment.

**References.**
- F2.1 in `docs/audits/frappe_skills_audit_2026-05-04.md`
- Skill `frappe-impl-whitelisted` rate-limiting workflow
## Amendment 2026-05-04 — DEC-081: Rate-limit `get_asset_board_data` (audit S3.1)

**Decision.** `@rate_limit(key="asset_board_get", limit=120, seconds=60)` added to `get_asset_board_data`. 120 req/min/IP is generous (normal Asset Board polls roughly twice/min per terminal) and bounds runaway client loops without impeding real operators.

**Why.** DEC-074 covered mutating endpoints; `get_asset_board_data` is the hottest read endpoint in the system and was excluded by design. It runs four DB round trips per call. A misconfigured polling loop on one terminal can degrade response time for every operator. Adding a per-IP rate limit closes this defense-in-depth gap with no behaviour change for normal usage.

**What changed.** `hamilton_erp/api.py`: imported `rate_limit` from `frappe.rate_limiter`, decorated `get_asset_board_data`. No schema change.

**References.** Audit `docs/audits/security_hardening_audit_2026-05-04.md` § S3.1; DEC-074 (mutating-endpoint rate limits, on unmerged feature branch); skill `frappe-impl-whitelisted` (rate_limit guidance).
## Amendment 2026-05-04 — DEC-107: Multi-venue processor decisions; adapter region keying; Slice clarification

**Decision.** Locks the per-venue card-processor stack for the four near-term venues, the Fiserv adapter region-keying scheme, the build order for the US driver, and the correct interpretation of "Slice" in Hamilton's research history. Supersedes the open questions raised by DEC-105.

### Per-venue processor stack

| Venue | Country | Stack | Processor relationship |
|---|---|---|---|
| **Hamilton** (Hamilton, ON) | Canada | Clover Flex C405 (per DEC-106) | **Fiserv direct** (Hamilton's existing MID, Direct Platform / Canada EMV) |
| **DC** (Washington, DC) | USA | Slice/Clover terminal | **Fiserv ISO** (Slice Merchant Services rails through Fiserv) |
| **Philadelphia** | USA | Slice/Clover terminal | **Fiserv ISO** (same as DC) |
| Dallas, TX (Phase 3+) | USA | TBD | Per DEC-063 — venue-time decision |

DC and Philadelphia share **identical adapter code** — same Slice/Clover stack, same Fiserv ISO upstream, same Commerce Hub / Rapid Connect API surface. One driver, two site configs.

### Adapter region keying — `anvil_venue_id` only, no separate `fiserv_region` key

The Fiserv adapter region (CA vs US) is **derived from `frappe.conf.anvil_venue_id`** at adapter init. No parallel `fiserv_region` config key (contrary to DEC-105's proposal). The mapping lives in the adapter module:

```python
_VENUE_TO_REGION = {
    "hamilton": "CA",
    "dc": "US",
    "philadelphia": "US",
    # Phase 3+: dallas, toronto, washington-backup, etc.
}
```

**Why no separate key.** The venue is already the source of truth for everything region-specific — currency (CAD vs USD), tax rate, legal entity, CRA registration vs IRS EIN. A parallel `fiserv_region` key would risk drift: a misconfigured site could declare itself `anvil_venue_id="hamilton"` but `fiserv_region="US"` and silently route Hamilton transactions through the US driver. Deriving region from venue eliminates that drift class.

**This supersedes DEC-105's open question 1.** When PR #221 lands, the adapter implementation reads `anvil_venue_id`; no `fiserv_region` key is added.

### Build order for the US driver

The Fiserv-USA driver builds **first for Philadelphia** as part of Philly's go-live. Same code is reused verbatim for DC when DC opens — no per-venue branching beyond the venue→region map. **Philly drives the timeline; DC inherits.**
The Fiserv-USA driver builds **first for DC** as part of DC's go-live. Same code is reused verbatim for Philadelphia when Philly opens — no per-venue branching beyond the venue→region map. **DC drives the timeline; Philly inherits.**

The Fiserv-CA driver (Hamilton) is the **Phase 2 hardware track** — answers DEC-105's open question 2. Hamilton's existing C405 runs standalone today (operator types the cart amount manually); the integrated path lands as part of Phase 2 alongside the receipt printer (DEC-098). No code in Phase 1 depends on the integrated path.

### "Slice" — dual-pricing UX angle and the Fiserv-ISO rail-sharing finding

The original Slice interest was the **dual-pricing UX model** (cash-discount / surcharge presentation that Slice's pizza POS made operationally clean for SAB merchants). Hamilton's interest was the *user-experience pattern* — how Slice presents transparent dual pricing at the terminal — not the upstream rails.

Rail-sharing — the discovery that Slice/Clover (specifically **Slice Merchant Services**, not the Adyen-backed pizza-consumer app) routes through **Fiserv ISO** in the US — was a **separate, later research discovery** while evaluating DC/Philly options. It happens to align with Hamilton's existing Fiserv relationship (Canada side), which is why DC and Philly inherit the Fiserv adapter pattern.

**Naming-collision warning preserved.** "Slice" appears in three commercial contexts:

1. **Slice (consumer pizza POS)** — runs on Adyen. Not relevant to Hamilton.
2. **Slice Merchant Services** — separate commercial entity; ISO routing through Fiserv. **This is the Slice that matters for DC and Philly.**
3. **Slice / Clover terminals** — hardware sold under the Slice Merchant Services umbrella; same Clover hardware family as Hamilton's C405, different processor relationship (ISO vs direct).

Future research that mentions "Slice" must disambiguate which entity is meant.

### Per-site config shape

Each site's `site_config.json`:

```json
{
  "anvil_venue_id": "hamilton" | "dc" | "philadelphia" | ...,
  "card_terminal_ip": "192.168.0.136",
  "card_terminal_serial": "C045UQ24930247",
  "fiserv_merchant_id": "1131224"
}
```

Adapter reads `anvil_venue_id`, looks up region, instantiates `FiservCanadaDriver` or `FiservUSADriver`, dispatches to the terminal at `card_terminal_ip` using `fiserv_merchant_id`. No region-specific code paths in the calling app.

### What this DEC closes

- DEC-105 Q1 (config key name) → **no separate key; derive from `anvil_venue_id`**.
- DEC-105 Q2 (Fiserv-CA driver placement) → **Phase 2 hardware track**.
- DEC-105 Q3 (first US venue) → **Fiserv ISO via Slice/Clover for Philadelphia first**; same code reused for DC.
- DEC-105 Q3 (first US venue) → **Fiserv ISO via Slice/Clover for DC**, same code reused for Philly.
- DEC-105 Q4 (Slice interest) → **dual-pricing UX**; rail-sharing is a separate, complementary finding for DC/Philly.

### What this DEC does NOT promise

- Does NOT define the Fiserv-USA driver implementation. Ships at DC's Phase 2 card-go-live.
- Does NOT decide Dallas / Washington-backup / Toronto. Per DEC-063, those are venue-time choices.
- Does NOT lock the dual-pricing UX implementation. That's a separate Phase 2+ design decision.

### References

- DEC-062 — Hamilton ERP / ANVIL Corp business classification.
- DEC-063 — per-venue primary processor choice.
- DEC-064 — primary + backup processor mandate.
- DEC-096 — frappe/payments omitted (Path A).
- DEC-105 — Pasigono / Fiserv research (the open questions answered here).
- DEC-106 — Hamilton terminal Clover Flex C405; SAQ-A scope.

---

## Amendment 2026-05-04 — DEC-108: Tier-2 escalation contacts

**Decision.** When Chris is unreachable, the front desk escalates in this order: (1) **Craig** — existing on-call contact, number in the venue front-desk binder; (2) **Austin LeFrense — 905-920-0487**.

**Why.** The launch playbook and emergency runbook previously listed "Tier-2: [name + phone]" as a placeholder. With opening weekend approaching, the Tier-2 chain needs concrete names and a documented order so a stressed operator at 11pm does not have to guess. Two named fallbacks in series gives Hamilton a realistic chance of reaching a human inside the 30-minute SLA when Chris is on a flight or asleep.

**What changed.**
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — "Who to call" table now lists Craig as Tier-2 first call and Austin LeFrense (905-920-0487) as Tier-2 second call.
- `docs/RUNBOOK_EMERGENCY.md` — added a "Tier-2 Escalation Chain" block under the contact header at the top of the file so the chain is visible from the first triage page.

**References.** None — this is the first decision pinning the Tier-2 contact list. Future amendments to either contact (number change, replacement person) supersede this DEC.

---

## Amendment 2026-05-04 — DEC-111: Hamilton tablet count = 1

**Decision.** Hamilton runs **one** front-desk tablet — a single transaction lane with one scanner, one card reader, one receipt printer, one cash drawer, one label printer.

**Why.** Hamilton's floor traffic and front-desk geometry support a single transaction station. The asset board, cart drawer, and key-assignment flows are designed for portrait/landscape on a 10.9-inch standard iPad and a single operator at the desk. Confirming the count at 1 closes off any drift toward a multi-tablet purchase order and pins the Phase-B seed value (`anvil_tablet_count = 1`) and the per-venue reference table. This DEC also clarifies that "two tablets racing for the same key" scenarios in the launch playbook are written as future-proof / multi-venue concurrency tests, not Hamilton's actual hardware footprint.

**What changed.**
- `docs/design/pos_hardware_spec.md` — per-venue tablet count list now annotates Hamilton's "1" with a DEC-111 reference.
- `docs/venue_rollout_playbook.md` — Phase B reference table cell for Hamilton's tablet count cites DEC-111.
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — Hardware / Network checklist row prepended with a Hamilton-tablet-count = 1 confirmation pointing to DEC-111.

**References.** `seed_hamilton_env.execute` patch (`bench --site {site} set-config anvil_tablet_count 1`). `docs/design/pos_hardware_spec.md` §3 (Standard iPad rationale). DEC-098 (receipt printer). DEC-106 (Hamilton terminal).

---

## Amendment 2026-05-04 — DEC-079: Add `search_index: 1` on high-traffic status / date filter fields (audit F4.2)

**Decision.** `search_index: 1` added to non-Link filter dimensions the audit identified as highest-value: `Cash Drop.reconciled` (Check), `Cash Drop.shift_date` (Date), `Cash Reconciliation.variance_flag` (Select), `Shift Record.shift_date` (Date), `Venue Session.session_start` (Datetime). Other F4.2 fields (`Cash Drop.timestamp`, `Cash Reconciliation.timestamp`, `Comp Admission Log.timestamp`, `Venue Session.session_end`) deferred until they appear in slow-query logs.

**Why.** `Cash Drop.reconciled` is the highest-signal one — every "show me unreconciled drops" query is a table-scan today. `shift_date` and `session_start` drive every operational and reporting filter. Adding the indices now is cheap (small tables) and avoids a future migrate-required hotfix at the 6-venue rollout. Phase-3 reconciliation reporting will hit `reconciled` and `variance_flag` hardest; pinning them now removes that perf cliff.

**What changed.** JSON edits to four DocType definitions: `cash_drop.json` (reconciled, shift_date), `cash_reconciliation.json` (variance_flag), `shift_record.json` (shift_date), `venue_session.json` (session_start). `bench migrate` REQUIRED. Bundle into the next Phase 3 migrate window with #168 / #170 / #171 / #172 / #174 / #192 (DEC-078 sibling).

**References.** Audit `docs/audits/frappe_skills_audit_2026-05-04.md` § F4.2; skill `frappe-syntax-doctypes`; DEC-078 (sibling Link-field pass).
## Amendment 2026-05-04 — DEC-114: Mark dual-tablet race-condition risk as N/A for Hamilton

**Decision.** The "two tablets, one key, simultaneous assignment" race-condition check (Risk #6 in `HAMILTON_LAUNCH_PLAYBOOK.md`) is marked **N/A for Hamilton's go-live**. The corresponding Operations-readiness checklist row is also marked N/A. No pre-launch concurrency test, chaos test, or Playwright script is required for Hamilton.

**Why.** Per DEC-111, Hamilton runs **one** front-desk tablet. Concurrent assignment of the same physical key from two tablets is not physically possible at this venue. The original Risk #6 was written as a future-proof multi-tablet concern; DEC-111 confirmed Hamilton's actual hardware footprint is single-tablet, which makes the risk inapplicable to this site.

**Scope.** This DEC marks the risk N/A for **Hamilton only**. The original Risk #6 section content stays in the playbook unedited below the N/A banner — it remains the canonical reference for **DC and Philly** when those venues open and seed `anvil_tablet_count > 1`. The single source of truth for "is this venue multi-tablet?" is the per-site config key `anvil_tablet_count`; if Hamilton ever expands to a second tablet, this DEC must be reversed (per the Part 12 protocol) and the Risk #6 chaos test re-introduced as a launch blocker.

**What changed.**
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — Operations-readiness checklist row marked `[x] N/A for Hamilton (DEC-114)` with strikethrough on the original question. Risk #6 section prepended with an N/A banner explaining the single-tablet rationale and reactivation criterion for multi-tablet venues.
- `docs/decisions_log.md` — this entry.

**References.** DEC-111 (Hamilton tablet count = 1). `anvil_tablet_count` site config seeded to 1 in `seed_hamilton_env.execute`. Risk #6 in `HAMILTON_LAUNCH_PLAYBOOK.md` (preserved in full below the N/A banner for DC/Philly use).

---

## Amendment 2026-05-04 — DEC-112: Frappe Cloud update policy

**Decision.** Frappe Cloud updates to the Hamilton production bench may run **only Monday or Tuesday, 9 AM – 5 PM EST**, **only with prior owner (Chris) approval**, and **never automatically**. Thursday midnight through Monday 9 AM EST is a hard no-update blackout window. The policy is configured in the Frappe Cloud dashboard as a pre-launch setup step.

**Why.** Hamilton's revenue concentrates Thursday evening through Sunday. An auto-pulled minor release that breaks a workflow during peak revenue is the worst possible time to debug. Restricting updates to early-week business hours gives 4–5 days of operational distance to identify and roll back a bad update before the next peak. Owner approval per update aligns with the production-pinning rule in CLAUDE.md ("manual promotion after staging soak; ~10 fixes/month land in `version-16` HEAD and auto-pulling them invites production churn").

**What changed.**
- `docs/operations/frappe_cloud_update_policy.md` — new doc capturing the window, approval rule, blackout window, pre-launch setup steps, and violation procedure.
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — Frappe Cloud / Production checklist row replaced with the explicit policy from this DEC, citing the operations doc.

**References.** CLAUDE.md → "Production version pinning — tagged v16 minor release, NEVER branch HEAD or develop." `docs/venue_rollout_playbook.md` Phase A step 2 (production version pin). DEC-098 (receipt printer). `RUNBOOK_EMERGENCY.md` (post-violation paging).

---

## Amendment 2026-05-04 — DEC-110: Bookkeeper review deferred to Phase 2

**Decision.** The "bookkeeper/accountant has reviewed at least one test day-close" item is **deferred to Phase 2**. Phase-1 launch does not require bookkeeper sign-off.

**Why.** Hamilton's accounting integration (QBO mirror, multi-venue chart-of-accounts wiring, day-close GL postings) ships in Phase 2. In Phase 1, day-close produces operational records (Cash Drop, Sales Invoice with the correct tax + price list — see Amendment 2026-04-30 (b)) but the books are not yet wired to QBO for true tie-out. Asking a bookkeeper to review a Phase-1 day-close would generate findings that are already in the Phase-2 backlog and would add launch-week noise without changing the launch decision.

**What changed.**
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — Tax / Accounting checklist row "Bookkeeper/accountant has reviewed at least one test day-close" struck through with a deferred-to-Phase-2 note pointing to this DEC.

**References.** Amendment 2026-04-30 (b) (Hamilton accounting names locked from QBO mirror). DEC-062 (Hamilton ERP / ANVIL Corp business classification). Phase 2 hardware + accounting backlog in `docs/build_phases.md` and `docs/inbox.md`.

---

## Amendment 2026-05-04 — DEC-109: Staff PIN policy (per-operator, June 2026 setup)

**Decision.** Every front-desk operator gets their own PIN. No shared accounts. Temporary PINs are provisioned per-named-operator in **June 2026** as a pre-launch setup step; the operator changes the PIN at first login.

**Why.** The audit trail (DEC-077, document versioning on Venue Session / Bathhouse Assignment / Cash Drop / Comp Admission Log) only works if every action attributes to a real human. A shared "frontdesk" account would make forensic reconstruction impossible after a cash variance or comp dispute. Provisioning in June (not at go-live) keeps the launch-day checklist short and gives Chris time to walk each operator through the change-on-first-login flow during their practice shifts.

**What changed.**
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — Staff readiness Go/No-Go now lists per-operator PIN policy plus the June 2026 setup step. The Permissions / People section in Part 4 calls out the same setup as a pre-launch task with a DEC-109 reference.

**References.** DEC-077 (audit-log post-submit owner correction). RUNBOOK §3.2 (account recovery). Part 4 "Permissions" and "People" sections of the launch playbook.

---

## Amendment 2026-05-04 — DEC-078: Add `search_index: 1` on high-traffic Link fields (audit F4.1)

**Decision.** `search_index: 1` added to the Link fields the audit identified as highest-value filter targets: `Cash Drop.operator`, `Cash Reconciliation.cash_drop`, `Cash Reconciliation.shift_record`, `Comp Admission Log.venue_session`, `Comp Admission Log.operator`, `Venue Session.sales_invoice`. Other Link fields listed in F4.1 deferred until they show up in slow-query logs.

**Why.** Frappe creates an index on `parent` and `name` only — Link FK columns are not auto-indexed. List-view filters and ORM `filters={"foo": "..."}` queries against these columns table-scan. At Hamilton's current single-venue volume the perf cost is invisible, but at the 6-venue rollout these particular columns are the ones reconciliation reporting and audit lookups hit hardest. Adding the index now is cheap (small tables) and avoids a future migrate-required hotfix.

**What changed.** JSON edits to four DocType definitions: `cash_drop.json`, `cash_reconciliation.json`, `comp_admission_log.json`, `venue_session.json`. `bench migrate` REQUIRED — DocType JSON `search_index` adds create new MariaDB indices. Bundle into the next Phase 3 migrate window with #168 / #170 / #171 / #172 / #174.

**References.** Audit `docs/audits/frappe_skills_audit_2026-05-04.md` § F4.1; skill `frappe-syntax-doctypes` (search_index hygiene).

---

## Part 12 — How to use this document

Before making ANY change to the asset board, search this document first. If the change touches a decision already locked here:
1. Do NOT silently change behaviour
2. Surface the conflict: "This would reverse Decision X.Y"
3. Get explicit approval from Chris to reverse
4. If reversed, update this document with the reversal and reasoning
5. Only then change the code

The point of this document is to stop re-opening settled questions. Respect it.
