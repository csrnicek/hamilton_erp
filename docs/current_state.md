# Hamilton ERP — Current State

Living tracker of what has been built, what is in progress, and what is blocked.

**Last updated:** 2026-04-13
**Current phase:** Phase 1 in progress — Tasks 1–17 complete, Task 18 next. Asset board UI design fully approved via interactive mockup V6 on 2026-04-13. Full design spec saved to `docs/design/asset_board_ui.md`. Tasks 17, 18, and 19 have approved visual designs — ready for implementation. New additions beyond original Phase 1 plan captured in spec: tabbed layout, Watch tab, feature flag tabs (Waitlist/Other), grouped status sections with time sorting, attendant name in header.

---

## ⚠️ SESSION PROTOCOL — READ FIRST

**Every conversation in this project must:**
1. Read all docs from https://github.com/csrnicek/hamilton_erp/tree/main/docs at session start
2. Push updated `.md` files to GitHub every hour during the session
3. Push all code immediately after writing it
4. Update this file and push before closing out

---

## Session Notes

### 2026-04-11 (Phase 1 Tasks 9–16 + full debugging arc)

**Phase 1 progress:**
- Tasks 1–16 all complete and committed. Task 17 (Asset Board bind_events / interaction handlers) is the next pending item. Taskmaster (`.taskmaster/tasks/tasks.json`) confirms: 16 done, 1 in-progress, 8 pending.
- Full 12-module test suite green on `hamilton-unit-test.localhost` — 197+ tests, 11 skipped (progressive unlocks per CLAUDE.md §Test Suite).

**Dedicated test site (DEC-059):**
- Created `hamilton-unit-test.localhost` and repointed every slash command in `.claude/commands/*.md` at it. Commit `0cf1fb1 fix(commands): repoint all remaining commands to dedicated test site`.
- Bootstrap sequence codified: `bench migrate` → ERPNext `setup_complete()` → `seed_hamilton_env.execute()` → `restore_dev_state()`. Full rationale in DEC-059.
- Rule: `hamilton-test.localhost` is dev browser site ONLY. `bench run-tests` NEVER touches it. CLAUDE.md §Testing Rules pins this.

**Flash-loop root cause and fix (DEC-060 + regression test):**
- Browser hit a ~40-requests-per-second redirect loop on `/app` → `/app/setup-wizard` → `/app`. Two root causes:
  1. `frappe.is_setup_complete()` reads `tabInstalled Application.is_setup_complete` filtered to `app_name IN ('frappe','erpnext')` — NOT `tabDefaultValue.setup_complete`, NOT `System Settings.setup_complete`. Every heal attempt that targeted the legacy stores silently accepted the write and left the real source untouched. Fix: `after_migrate` hook `hamilton_erp.setup.install.ensure_setup_complete` (commit `7c866a6`) + same pattern in `test_helpers.py::restore_dev_state` step 1. Codified in DEC-060.
  2. `tabDefaultValue.desktop:home_page='setup-wizard'` was set by an earlier heal attempt. When coexisting with `is_setup_complete=True`, `setup_wizard.js:34` redirects `window.location.href` to `/desk` without returning, and `pageview.js:52` reads `bootinfo.home_page='setup-wizard'` — the loop. Fix: `test_helpers.py::restore_dev_state` step 4 deletes the row on every teardown. Pinned by `test_regression_desktop_home_page_not_setup_wizard` in `test_environment_health.py`. Commits `e969091` (test) and `738eaff` (heal).

**HTTP verb mismatch bug (DEC-058):**
- Chris reported 403 "Not permitted" on Asset Board in both Chrome and Safari on fresh sessions, while curl consistently returned 200. Red herring: assumed CSRF, stale session, Redis cache, role strip. Real cause:
  - `api.py:51` — `@frappe.whitelist(methods=["GET"])`
  - `asset_board.js:30` — `frappe.call({method: "..."})` with no `type`, defaulting to POST.
  - `frappe.handler.is_valid_http_method` rejected the POST with `PermissionError("Not permitted")` before the body ran.
- Every test in `test_api_phase1.py` called the function as a direct Python import, bypassing `frappe.handler` and the verb gate. Curl defaults to GET, so curl never caught it either. The Asset Board had NEVER successfully rendered in a browser since it was first scaffolded (`7740be9`).
- **Fix:** one line — added `type: "GET"` to `asset_board.js`. Ran `bench build --app hamilton_erp` + `bench clear-cache`. Curl verification now uses `-X GET` matching the browser verb.
- **Regression test:** new class `TestAssetBoardHTTPVerb` in `test_api_phase1.py` — invokes `frappe.handler.execute_cmd` with a spoofed `frappe.local.request.method` and asserts both GET→59 assets and POST→`PermissionError`. This is the exact layer where the verb gate runs; direct Python import would not catch it.
- **Prevention:** DEC-058 mandates a verb-pin test for every `@frappe.whitelist(methods=[...])` endpoint going forward. Explicit `type:` on every `frappe.call`. Code review rejects any PR that edits the decorator without updating the pin.

**Debugging shortcuts documented (CLAUDE.md):**
- `bench console --autoreload`, `bench request`, `bench doctor` + `show-pending-jobs`, `/debug-env` slash command — MANDATORY first debug step.
- `bench start` orphan-schedule recovery steps added to `.claude/commands/debug-env.md` (`lsof config/scheduler_process`, `ps -ax -o ppid,pid,command | awk '$1==1 && /frappe|bench/'`, kill PPID=1 orphans). Commit `61c2383`.
- Model selection guidance added to CLAUDE.md — Sonnet for mechanical/test/doc work, Opus for lifecycle/locks/architectural decisions. Task-opening self-check at top of every response.

**Commits this session (chronological):**
- `7c866a6` — `tabInstalled Application.is_setup_complete` fix + `after_migrate` heal
- `63a1f97` — environment health smoke test module
- `2e348d0` — security audit, schema snapshot, regression, audit trail tests
- `5d77003` — dedicated test site migration + debugging shortcuts + model selection
- `0cf1fb1` — repoint remaining commands at dedicated test site
- `12350de` — cleanup of remaining uncommitted changes
- `61c2383` — bench start recovery added to `/debug-env`
- `e969091` — regression pin for `desktop:home_page` flash loop
- `738eaff` — `test_helpers.py` heals `desktop:home_page` on teardown

**Next actions:**
- Resume Task 18 (tile expand / popover / action buttons) via Subagent-Driven Development.
- Two new Hamilton Settings fields (`show_waitlist_tab`, `show_other_tab`) must be added to DocType JSON before Task 17 can ship to Frappe Cloud.

### 2026-04-13 (Asset Board UI design approval)

- **Full UI design approved** via interactive mockup V6 — authoritative spec saved to `docs/design/asset_board_ui.md`
- Tasks 17, 18, and 19 now have approved visual designs — ready for implementation
- New scope additions captured in spec: tabbed layout (Lockers/Single/Double/VIP/Waitlist/Other/Watch), Watch tab (cross-category alert aggregation), feature flag tabs (Waitlist/Other controlled by Hamilton Settings), grouped status sections with time-based sorting, attendant name in header
- Two new Hamilton Settings fields required: `show_waitlist_tab` (Check, default 0), `show_other_tab` (Check, default 0)
- Accessibility standards applied throughout: 56px tab height, 15px font, 3px tile borders (staff aged 50+)
- Top summary strip deliberately removed from header — footer is sole status count display

### 2026-04-10 (Phase 1 planning + M0 local bench setup)
- **Phase 1 design doc finalized** — Asset Board + Session Lifecycle spec committed
- **Phase 1 implementation plan written** — 25 tasks, `docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md`
- Plan updated for Frappe v16 version drift: Python 3.14 (was 3.11), Node 24 (was 20)
- **M0 local bench setup COMPLETE**
  - Bench path: `~/frappe-bench-hamilton`
  - Python 3.14 (system, `/Library/Frameworks/Python.framework/Versions/3.14`)
  - Node 24 LTS (via nvm, set as default)
  - MariaDB 12.2.2 (Homebrew, root auth fixed via `chrissrnicek` unix_socket grant)
  - Redis managed by bench (cache=13000, queue=11000)
  - Site: `hamilton-test.localhost` (developer_mode=1, allow_tests=1)
  - erpnext v16 + hamilton_erp installed
  - hamilton_erp mounted as symlink → `/Users/chrissrnicek/hamilton_erp` for in-place editing
  - `bench start` smoke test: HTTP 200, 25KB HTML
  - Test harness: **Ran 15 tests in 0.23s** — 14 expected failures from stale Phase 0 "Standard" tier names (fixed in Phase 1 Task 1)
- Test cascade blocker resolved via module-level `IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Venue Session"]` in `test_venue_asset.py`
- Dev seed helper added: `hamilton_erp/scripts/seed_test_fixtures.py` (not in install path)
- **Phase 1 execution mode:** Subagent-Driven Development — fresh subagent per task with review gates
- New plugins available during Phase 1: Context7 (live Frappe v16 docs) + Frontend Design (Asset Board polish)
- **TODO:** GitHub repo `csrnicek/hamilton_erp` is still public — needs to be made private

### 2026-04-09 (E5 live test + deployment)
- **Phase 0 E5 live test PASSED — bench migrate ran with zero errors on Frappe Cloud**
- Frappe Cloud site: hamilton-erp.v.frappe.cloud on private bench hamilton-erp-bench (bench-37550, N. Virginia, USA)
- requirements.txt deleted (pyproject.toml is authoritative)
- Next step: run ERPNext setup wizard, then 3-AI code review

### 2026-04-09 (Phase 0 coding session)
- **Phase 0 coding complete**
- 9 custom DocTypes built and verified (111 total fields)
- 7 custom field fixtures on Item + Sales Invoice correct
- 3 roles (Hamilton Operator, Hamilton Manager, Hamilton Admin) in role.json, hooks.py, and install.py
- POS Closing Entry blocked for Hamilton Operator (DEC-005)
- Hamilton Workspace with 8 DocTypes in 3 role-based sections (Operations / Oversight / Administration)
- 39 Python files compile clean, 12 JSON files parse clean
- Redundant Custom DocPerm functions removed from install.py — permissions defined in DocType JSONs
- All work committed and pushed to GitHub

### 2026-04-09 (earlier — design session)
- Three-AI review completed (ChatGPT, Gemini, Grok)
- Grok provided complete Venue Asset DocType JSON + controller code + locking patterns
- Recorded DEC-017 through DEC-024 from review findings
- DocType schemas updated with agreed additions
- New roles defined: Operator / Manager / Admin
- Concurrency locking approach confirmed: hybrid Redis + MariaDB + version field
- All 4 critical decisions resolved: DEC-025 through DEC-029
- Float corrected to $300 (was $200)
- POS Invoice vs Sales Invoice resolved: use Sales Invoice mode
- Float carryover: operator sets aside, drops revenue only
- Split tender: cash portion only counts toward reconciliation

### Previous sessions
- All pricing confirmed, blockers 1–9 resolved except retail item list
- GitHub as single source of truth established (DEC-012)
- Asset inventory, stay durations, float, label printer all confirmed

---

## Overall Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Foundation | **Complete — E5 passed** | 9 DocTypes, 3 roles, workspace, fixtures. Live on Frappe Cloud + local bench. |
| Phase 1: Asset Board & Sessions | **In progress — Tasks 1–17 complete** | 25 tasks via Subagent-Driven Development. 306+ tests passing (14 modules). UI design approved 2026-04-13. |
| Phase 2: POS Integration & Check-in | Not started | — |
| Phase 3: Cash Handling & Shifts | Not started | — |
| Phase 4: Refunds, Polish, Compatibility | Not started | — |
| Phase 5: Deployment & Hardening | Not started | — |

---

## Prerequisites

| Item | Status | Notes |
|---|---|---|
| ERPNext v16 development environment | ✅ Live | hamilton-erp.v.frappe.cloud (bench-37550, N. Virginia) |
| Local bench environment | ✅ Live | `~/frappe-bench-hamilton` — Python 3.14, Node 24, MariaDB 12.2.2, site `hamilton-test.localhost`. hamilton_erp mounted via symlink for in-place edits. |
| GitHub repository | ⚠️ Public — make private | https://github.com/csrnicek/hamilton_erp |
| Local repo path | ✅ Done | `/Users/chrissrnicek/hamilton_erp` |
| Hosting platform | ✅ Done | Frappe Cloud, Hetzner Ashburn VA, ~$40/mo |
| Three-AI architecture review | ✅ Done | ChatGPT + Gemini + Grok — see review_synthesis.md |
| Phase 1 implementation plan | ✅ Done | `docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md` |

---

## Hamilton Asset Inventory (CONFIRMED)

| Asset Type | Count | Display Name | Price | Stay Duration |
|---|---|---|---|---|
| Locker | 33 | Lckr | $29.00 | 6 hours |
| Single Standard | 11 | Sing STD | $36.00 | 6 hours |
| Deluxe Single | 10 | Sing DLX | $41.00 | 6 hours |
| Glory Hole | 2 | Glory | $45.00 | 6 hours |
| Double Deluxe | 3 | Dbl DLX | $47.00 | 6 hours |

All prices HST-inclusive. Float: $300 (configurable per venue). Label printer: Brother QL-820NWB.

**Pricing Rules:**
- Locker Special: $17 flat — Mon–Fri 9–11am, Sun–Thu 4–7pm
- Under 25: 50% off all assets, operator manually applies, no stacking with Locker Special

---

## Custom DocTypes (FINAL SCHEMAS)

### Venue Asset
| Field | Type | Notes |
|---|---|---|
| asset_code | Data | Immutable unique code set at creation — never changes (e.g. R001, L001). Survives renames. |
| asset_name | Data | Display name shown on POS and asset board — can be changed |
| asset_category | Select | Room / Locker |
| asset_tier | Select | Locker / Single Standard / Deluxe Single / Glory Hole / Double Deluxe |
| status | Select | Available / Occupied / Dirty / Out of Service |
| current_session | Link → Venue Session | |
| expected_stay_duration | Int | Minutes (default 360 = 6hrs) |
| display_order | Int | For board layout |
| company | Link → Company | Required for ERPNext multi-company |
| is_active | Check | Default 1 |
| hamilton_last_status_change | Datetime | Read-only, set automatically |
| last_vacated_at | Datetime | Set when Occupied → Dirty. Drives "Dirty since X" display on board. |
| last_cleaned_at | Datetime | Set when Dirty → Available. Shows how recently room was turned over. |
| version | Int | Hidden, default 0 — optimistic locking |
| reason | Text | Mandatory for Out of Service |

Indexes on: `status`, `display_order`, `asset_category`, `asset_tier`
Naming: `VA-.####`

### Venue Session
| Field | Type | Notes |
|---|---|---|
| session_number | Data | Auto-generated. Format: {day}-{month}-{year}---{sequence}. Example: 9-4-2026---001. Resets to 001 at midnight. Sequence bolded in UI display. |
| venue_asset | Link → Venue Asset | |
| sales_invoice | Link → Sales Invoice | |
| admission_item | Link → Item | |
| session_start | Datetime | |
| session_end | Datetime | |
| status | Select | Active / Completed |
| assignment_status | Select | Pending / Assigned / Failed (default Pending) |
| operator_checkin | Link → User | |
| operator_vacate | Link → User | |
| vacate_method | Select | Key Return / Discovery on Rounds |
| shift_record | Link → Shift Record | |
| customer | Link → Customer | Default Walk-in (forward compat) |
| pricing_rule_applied | Data | Audit which rule fired |
| under_25_applied | Check | Audit trail |
| comp_flag | Check | |
| *Forward compat fields (all null at Hamilton):* | | |
| identity_method | Data | Default "not_applicable" |
| member_id | Link → Customer | Forward compat — null at Hamilton |
| full_name | Data | |
| date_of_birth | Date | |
| membership_status | Data | |
| arrears_amount | Currency | |
| arrears_flag | Check | |
| arrears_sku | Data | |
| scanner_data | Text | |
| eligibility_snapshot | Text | |
| block_status | Data | |

### Cash Drop
| Field | Type | Notes |
|---|---|---|
| operator | Link → User | |
| shift_date | Date | |
| shift_identifier | Data | e.g. "Evening" |
| shift_record | Link → Shift Record | |
| drop_type | Select | Mid-Shift / End-of-Shift |
| drop_number | Int | Sequential per shift |
| declared_amount | Currency | |
| timestamp | Datetime | |
| reconciled | Check | |
| reconciliation | Link → Cash Reconciliation | |
| pos_closing_entry | Link → POS Closing Entry | Background-created |

### Cash Reconciliation
| Field | Type | Notes |
|---|---|---|
| cash_drop | Link → Cash Drop | |
| shift_record | Link → Shift Record | Direct link for faster reporting — also reachable via cash_drop |
| manager | Link → User | |
| actual_count | Currency | Manager's blind count |
| system_expected | Currency | Revealed only after submission |
| operator_declared | Currency | From Cash Drop |
| variance_amount | Currency | Auto-calculated: manager_actual - system_expected. Negative = short, positive = over. Revealed only after manager submits blind count. |
| variance_flag | Select | Clean / Possible Theft or Error / Operator Mis-declared |
| notes | Text | |
| resolved_by | Link → User | Manager who signed off investigation — null until resolved |
| resolution_status | Select | Open / Resolved / Dismissed / Escalated — null until actioned |
| timestamp | Datetime | |

### Asset Status Log
**Autoname:** `autoincrement` — fast sequential IDs, no naming series needed.

| Field | Type | Notes |
|---|---|---|
| venue_asset | Link → Venue Asset | |
| previous_status | Data | |
| new_status | Data | |
| reason | Text | |
| operator | Link → User | |
| venue_session | Link → Venue Session | Traceability — which session caused this change |
| timestamp | Datetime | |
### Shift Record
| Field | Type | Notes |
|---|---|---|
| operator | Link → User | |
| shift_date | Date | |
| shift_start | Datetime | |
| shift_end | Datetime | |
| float_expected | Currency | |
| float_actual | Currency | |
| float_variance | Currency | Variance at shift START (float_actual - float_expected) |
| closing_float_actual | Currency | Float counted by operator at shift END before handoff |
| closing_float_variance | Currency | Variance at shift END (closing_float_actual - float_expected) |
| board_confirmed | Check | |
| board_corrections | Child Table | Hamilton Board Correction |
| pos_profile | Link → POS Profile | |
| pos_opening_entry | Link → POS Opening Entry | |
| pos_closing_entry | Link → POS Closing Entry | |
| operator_declared_card_total | Currency | Operator reads terminal batch report and enters at shift close |
| system_expected_card_total | Currency | Auto-calculated from card-mode Sales Invoices for the shift |
| reconciliation_status | Select | Pending / Partially Reconciled / Fully Reconciled — auto-updated as drops are reconciled |
| status | Select | Open / Closed |

### Comp Admission Log
| Field | Type | Notes |
|---|---|---|
| venue_session | Link → Venue Session | |
| sales_invoice | Link → Sales Invoice | |
| admission_item | Link → Item | |
| comp_value | Currency | What the comp was worth |
| reason_category | Select | Loyalty Card / Promo / Manager Decision / Other |
| reason_note | Text | Mandatory if Other, max 500 chars |
| operator | Link → User | |
| timestamp | Datetime | |

### Hamilton Settings (Single DocType)
| Field | Type | Notes |
|---|---|---|
| float_amount | Currency | Default $300 — configurable per venue |
| default_stay_duration_minutes | Int | Default 360 |
| printer_ip_address | Data | Brother QL-820NWB IP |
| printer_model | Data | |
| grace_minutes | Int | Extra minutes after stay duration before overtime fires (default 15) |
| assignment_timeout_minutes | Int | Minutes before paid-but-unassigned session is flagged for cleanup (default 15) |
| printer_label_template_name | Data | Label template name for Brother QL-820NWB |
| show_waitlist_tab | Check | "Show Waitlist Tab" — controls whether Waitlist tab appears on Asset Board (default 0) |
| show_other_tab | Check | "Show Other Tab" — controls whether Other tab appears on Asset Board (default 0) |

### Hamilton Board Correction (Child DocType for Shift Record)
| Field | Type | Notes |
|---|---|---|
| venue_asset | Link → Venue Asset | |
| old_status | Data | |
| new_status | Data | |
| reason | Text | |
| operator | Link → User | |
| timestamp | Datetime | |

---

## Custom Fields on Standard DocTypes

| DocType | Field | Type | Notes |
|---|---|---|---|
| Item | hamilton_is_admission | Check | Triggers asset assignment after POS |
| Item | hamilton_asset_category | Select | Room / Locker |
| Item | hamilton_asset_tier | Select | Tier name |
| Item | hamilton_is_comp | Check | Triggers comp reason prompt |
| Sales Invoice | hamilton_venue_session | Link → Venue Session | |
| Sales Invoice | hamilton_comp_reason | Text | |
| Sales Invoice | hamilton_shift_record | Link → Shift Record | Ties invoice to shift |

---

## Roles (CONFIRMED — 3 roles)

| Role | Access |
|---|---|
| Hamilton Operator | POS, asset board, cash drops, shift start/close. No reconciliation, no settings, no POS Closing Entry. |
| Hamilton Manager | Reconciliation screen, view-only Cash Drop, shift reports. No settings. |
| Hamilton Admin | Hamilton Settings, asset master, items/pricing, role management. Not operational. |

---

## Custom Pages

| Page | Status | Phase |
|---|---|---|
| Asset Board | UI design approved (V6 mockup 2026-04-13). Spec: `docs/design/asset_board_ui.md` | 1 |
| Asset Assignment Prompt | Not started | 2 |
| Cash Drop Screen | Not started | 3 |
| Shift Start | Not started | 3 |
| Shift Close | Not started | 3 |
| Manager Reconciliation | Not started | 3 |

---

## Standard ERPNext Configuration

| Configuration | Status | Notes |
|---|---|---|
| POS Profile (Hamilton) | Not started | Must enable "Use Sales Invoice in POS" setting |
| Items — Admission types | Not started | 5 tiers + comp variants |
| Items — Retail | Not started | List pending |
| HST Tax Template | Not started | Company-level, "Included in Print Rate" (DEC-018) |
| Pricing Rule — Locker Special | Not started | $17, Mon–Fri 9–11am, Sun–Thu 4–7pm |
| Pricing Rule — Under 25 | Not started | 50% off, custom trigger button |
| Non-stacking validation | Not started | Custom server-side validate hook |
| Mode of Payment — Card/Cash | Not started | — |
| Role Permissions | Not started | DocType + Reports + Pages + field masking |
| Hamilton Desk/Workspace | Not started | Phase 0 |

---

## Blockers

| # | Blocker | Status |
|---|---|---|
| 1 | GitHub repo | ✅ https://github.com/csrnicek/hamilton_erp |
| 2 | Room/locker counts | ✅ 59 assets, 5 tiers |
| 3 | Stay durations | ✅ 6 hours all |
| 4 | Float amount | ✅ $300, configurable (DEC-026) |
| 5 | Label printer | ✅ Brother QL-820NWB |
| 6 | Asset pricing | ✅ See above |
| 7 | Pricing rules | ✅ Locker Special + Under 25 defined |
| 8 | Retail item list | ⏳ Chris to provide |
| 9 | Comp reasons | ✅ Loyalty Card / Promo / Manager Decision / Other |
| 10 | Dev environment | ✅ Frappe Cloud |

---

## QA Test Cases

| Test | Description | Status | Phase |
|---|---|---|---|
| H1 | Standard Room Check-in | — | 2 |
| H2 | Standard Locker Check-in | — | 2 |
| H3 | Check-in with Retail Items | — | 2 |
| H4 | Cancel Mid-Transaction | — | 2 |
| H5 | Comp Admission | — | 2 |
| H6 | Standalone Retail Sale | — | 2 |
| H7 | Tax Handling | — | 2 |
| H8 | Line-Item Refund | — | 4 |
| H9 | Full Transaction Refund | — | 4 |
| H10 | Vacate and Turnover | — | 1 |
| H11 | Out of Service | — | 1 |
| H12 | Occupied Asset Rejection | — | 1 |
| H13 | Mid-Shift Cash Drop | — | 3 |
| H14 | End-of-Shift Close-out | — | 3 |
| H15 | Manager Reconciliation (Clean) | — | 3 |
| H16 | Manager Reconciliation (Variance) | — | 3 |
| H17 | Operator Cannot Access POS Closing | — | 3 |
| H18 | Shift Start Float Variance | — | 3 |
| H19 | Shift Start Board Correction | — | 3 |
| H20 | Auto-Applied Promotion | — | 2 |
| H21 | No Promotion Active | — | 2 |
| H22 | Record Structure Integrity | — | 4 |

---

*GitHub is the single source of truth. Push after every session.*
