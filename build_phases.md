# Hamilton ERP — Build Phases

Sequenced build order for the Hamilton ERP custom Frappe app. Each phase must be functional and testable before moving to the next.

**Universal exit criteria for every phase:**
1. Every error message that can reach an operator screen must be reviewed against the plain-language standard in `coding_standards.md §8.4`. No phase is complete while any error message contains developer terms, stack traces, or placeholder text.
2. The 18-method pre-commit checklist (`coding_standards.md §9.5`) must pass with zero findings.
3. The false-positive audit (`coding_standards.md §9.6`) must pass with zero findings.
4. All decisions made or patterns established during the phase must be recorded in `decisions_log.md` and `current_state.md` before the phase is closed.

---

## Phase 0: Foundation

**Goal:** App scaffold exists, installs cleanly, all DocTypes are defined with correct schemas.

### Deliverables
- [ ] Frappe app created via `bench new-app hamilton_erp`
- [ ] `hooks.py` configured:
  - [ ] App metadata (name, title, publisher, description, version)
  - [ ] `required_apps = ["frappe", "erpnext"]`
  - [ ] Fixtures list (Custom Field, Property Setter, Role filters)
  - [ ] `after_install` hook pointing to setup script
  - [ ] `doc_events` stub for Sales Invoice (wired up in Phase 2)
- [ ] `patches.txt` created with `[pre_model_sync]` and `[post_model_sync]` sections
- [ ] All 7 custom DocTypes defined with complete field schemas (per build spec §9):
  - [ ] Venue Asset
  - [ ] Venue Session (including all forward-compatibility fields from V5.4)
  - [ ] Cash Drop
  - [ ] Cash Reconciliation
  - [ ] Asset Status Log
  - [ ] Shift Record
  - [ ] Comp Admission Log
- [ ] Custom fields on standard DocTypes defined via fixtures:
  - [ ] Item: `hamilton_is_admission`, `hamilton_asset_category`, `hamilton_asset_tier`, `hamilton_is_comp`
  - [ ] Sales Invoice: `hamilton_venue_session` (link), `hamilton_comp_reason` fields
- [ ] Custom roles created: `Hamilton Operator`, `Hamilton Manager`
- [ ] Role permissions set on all custom DocTypes
- [ ] Standard POS Closing Entry permission **removed** from Hamilton Operator role
- [ ] `after_install` setup script creates default roles and any required initial configuration
- [ ] App installs and migrates without errors on a clean ERPNext v16 site
- [ ] `bench export-fixtures` runs cleanly and exports only hamilton_erp fields
- [ ] GitHub repo initialized with this code

### Test criteria
- `bench --site [site] install-app hamilton_erp` succeeds
- `bench --site [site] migrate` succeeds
- All DocTypes visible in desk with correct fields
- No migration errors or missing columns
- Fixtures export/import cleanly on a second test site

### Status: COMPLETE (2026-04-08)
All deliverables built and hardened. 32 unit tests passing. 19 bugs found and fixed across six testing passes plus a false-positive audit. All decisions recorded in `decisions_log.md` (DEC-001 through DEC-013). See `current_state.md` for full change log.

---

## Phase 1: Asset Board and Session Lifecycle

**Goal:** Operator can see all assets, change states, and the full Available → Occupied → Dirty → Available lifecycle works.

### Deliverables
- [ ] Venue Asset controller with state transition validation (§5.1)
- [ ] Asset Status Log auto-created on every state change
- [ ] Asset board custom page — visual grid of all rooms and lockers
  - [ ] Color-coded tiles by state
  - [ ] Rooms and lockers visually separated
  - [ ] Room tier visually indicated
  - [ ] Tap tile to change state (context-appropriate actions)
  - [ ] Out of Service requires reason (mandatory)
  - [ ] Return to Service requires reason (mandatory)
- [ ] Venue Session creation (manual for now — POS integration comes in Phase 2)
  - [ ] Session start records operator, asset, timestamp
  - [ ] Vacate marks session complete, moves asset to Dirty
  - [ ] Vacate method field (Key Return / Discovery on Rounds)
- [ ] Realtime updates via `frappe.publish_realtime` (with `after_commit=True`) so board refreshes across tabs
- [ ] Realtime listener cleanup when leaving the asset board page
- [ ] Overtime overlay on tiles when session exceeds configured duration

### Test criteria
- QA test H10 (Vacate and Turnover) passes
- QA test H11 (Out of Service) passes
- QA test H12 (Occupied Asset Rejection) passes
- State transitions enforce the valid-only rule — invalid transitions throw errors
- Two browser tabs viewing the asset board stay in sync via realtime

---

## Phase 2: POS Integration and Check-in Flow

**Goal:** Full check-in flow works end-to-end — standard POS transaction triggers custom asset assignment.

### Deliverables
- [ ] ERPNext standard POS configured:
  - [ ] POS Profile for Hamilton (payment methods, default customer, item groups)
  - [ ] Admission items created (Standard Room, Deluxe Room, Locker, Comp variants)
  - [ ] Item Tax Templates (HST Taxable 13%, HST Exempt)
  - [ ] Tax templates assigned to all items
  - [ ] Retail items created (drinks, snacks, towels, etc.)
- [ ] `doc_events` hook on Sales Invoice `on_submit`:
  - [ ] Detects if cart contains an admission item (`hamilton_is_admission = 1`)
  - [ ] If yes → triggers asset assignment prompt via realtime event
  - [ ] If no → standard retail sale completes normally
- [ ] Asset assignment after payment:
  - [ ] Creates Venue Session linking Sales Invoice to Venue Asset
  - [ ] Moves asset to Occupied
  - [ ] Records operator identity
- [ ] Comp admission flow:
  - [ ] $0 admission item triggers mandatory reason prompt
  - [ ] Creates Comp Admission Log entry
  - [ ] Otherwise follows normal assignment flow
- [ ] Promotional Pricing Rules configured (at least one test promo, e.g., Half-Price Tuesday)

### Test criteria
- QA test H1 (Standard Room Check-in) passes
- QA test H2 (Standard Locker Check-in) passes
- QA test H3 (Check-in with Retail Items) passes
- QA test H4 (Cancel Mid-Transaction) passes
- QA test H5 (Comp Admission) passes
- QA test H6 (Standalone Retail Sale) passes
- QA test H7 (Tax Handling) passes
- QA test H20 (Auto-Applied Promotion) passes
- QA test H21 (No Promotion Active) passes

---

## Phase 3: Cash Handling and Shift Management

**Goal:** Blind cash drop system, shift start/close procedures, and manager reconciliation are fully operational.

### Deliverables
- [ ] Shift start screen (custom page):
  - [ ] POS Opening Entry created (standard)
  - [ ] Float verification prompt — operator enters actual count
  - [ ] Float variance logged in Shift Record
  - [ ] Asset board review and confirmation
  - [ ] Board corrections capability (mark rooms Vacant/Clean/OOS)
  - [ ] Shift start logged with all metadata
- [ ] Cash drop screen (custom page):
  - [ ] Operator enters declared amount only — **no expected totals shown**
  - [ ] Label prints with all required fields (venue, date, operator, shift, drop number, amount, timestamp)
  - [ ] Cash Drop record created
  - [ ] Available at any time during shift (mid-shift drops)
- [ ] Shift close screen (custom page):
  - [ ] Triggers final cash drop
  - [ ] Shift close confirmation
  - [ ] POS Closing Entry auto-created in background (standard ERPNext accounting satisfied)
  - [ ] Shift Record closed with end time
  - [ ] Operator logged out
- [ ] Manager reconciliation screen (custom page, manager-only access):
  - [ ] Select cash drop to reconcile (shows date, shift, operator, drop number — **no amounts**)
  - [ ] Manager enters actual count blind
  - [ ] On submit: three-way comparison revealed (system expected, operator declared, manager actual)
  - [ ] Variance flag auto-calculated (Clean / Possible Theft or Error / Operator Mis-declared)
  - [ ] Manager can add notes
  - [ ] Reconciliation logged
- [ ] Standard POS Closing Entry access blocked for Hamilton Operator role
- [ ] Label printer integration (browser print or direct — approach decided during this phase)

### Test criteria
- QA test H13 (Mid-Shift Cash Drop) passes
- QA test H14 (End-of-Shift Close-out) passes
- QA test H15 (Manager Reconciliation — Clean) passes
- QA test H16 (Manager Reconciliation — Variance) passes
- QA test H17 (Operator Cannot Access POS Closing) passes
- QA test H18 (Shift Start with Float Variance) passes
- QA test H19 (Shift Start Board Correction) passes

---

## Phase 4: Refunds, Polish, and Forward Compatibility

**Goal:** All remaining features complete. System is launch-ready.

### Deliverables
- [ ] Refund flow tested end-to-end via standard POS Return
- [ ] Refund reason captured in custom field
- [ ] Forward compatibility verification:
  - [ ] Venue Session contains all V5.4 fields (null at Hamilton)
  - [ ] `identity_method` defaults to `"not_applicable"`
  - [ ] All membership/arrears/scanner fields present and null
- [ ] Receipt print format configured and tested on thermal printer
- [ ] Full app deployed to staging environment matching production hardware
- [ ] All 22 QA test cases (H1–H22) pass
- [ ] Performance: check-in flow completes in ~10 seconds on tablet

### Test criteria
- QA test H8 (Line-Item Refund) passes
- QA test H9 (Full Transaction Refund) passes
- QA test H22 (Record Structure Integrity) passes
- All H1–H22 pass in sequence on staging hardware

---

## Phase 5: Deployment and Hardening (Post-Launch)

**Goal:** Production deployment, monitoring, and iteration based on real usage.

### Deliverables
- [ ] Production server provisioned (Frappe Cloud or self-hosted)
- [ ] Dual WAN router installed and tested (per build spec §12)
- [ ] All hardware connected and tested (tablet, receipt printer, label printer, card terminal)
- [ ] Operator training completed
- [ ] Manager trained on reconciliation workflow
- [ ] First week of live operations monitored
- [ ] Bug fixes and UX adjustments based on operator feedback

---

## Deferred (Not in Hamilton Pilot)

These items are explicitly deferred per build spec §14. Do not build them:

- Membership / identity / scanner system
- Arrears enforcement
- Eligibility snapshots
- Lock refresh / timeout / grace periods
- Payment uncertainty engine
- Offline operation software stack
- Local membership cache and sync
- Shared terminal clerk model
- Manager override hierarchy
- Shift / day / weekly review reports (basic reporting only)
- Vacant reversal and move guest
- Maintenance condition overlay
- Stripe payment integration
