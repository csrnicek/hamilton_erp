# Hamilton ERP — Current State

Living tracker of what has been built, what is in progress, and what is blocked.

**Last updated:** 2026-04-09
**Current phase:** Pre–Phase 0 — Schema finalized. Ready to start coding.

---

## ⚠️ SESSION PROTOCOL — READ FIRST

**Every conversation in this project must:**
1. Read all docs from https://github.com/csrnicek/hamilton_erp/tree/main/docs at session start
2. Push updated `.md` files to GitHub every hour during the session
3. Push all code immediately after writing it
4. Update this file and push before closing out

---

## Session Notes

### 2026-04-09 (this session)
- Three-AI review completed (ChatGPT, Gemini, Grok)
- Grok provided complete Venue Asset DocType JSON + controller code + locking patterns
- Recorded DEC-017 through DEC-024 from review findings
- DocType schemas updated with agreed additions
- New roles defined: Operator / Manager / Admin
- Concurrency locking approach confirmed: hybrid Redis + MariaDB + version field
- **Phase 0 is ready to start — Venue Asset DocType + state machine first
- All 4 critical decisions resolved: DEC-025 through DEC-029
- Float corrected to $300 (was $200)
- POS Invoice vs Sales Invoice resolved: use Sales Invoice mode
- Float carryover: operator sets aside, drops revenue only
- Split tender: cash portion only counts toward reconciliation**

### Previous sessions
- All pricing confirmed, blockers 1–9 resolved except retail item list
- GitHub as single source of truth established (DEC-012)
- Asset inventory, stay durations, float, label printer all confirmed

---

## Overall Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Foundation | **Ready to start** | All schemas finalized |
| Phase 1: Asset Board & Sessions | Not started | — |
| Phase 2: POS Integration & Check-in | Not started | — |
| Phase 3: Cash Handling & Shifts | Not started | — |
| Phase 4: Refunds, Polish, Compatibility | Not started | — |
| Phase 5: Deployment & Hardening | Not started | — |

---

## Prerequisites

| Item | Status | Notes |
|---|---|---|
| ERPNext v16 development environment | ✅ Decided | Frappe Cloud |
| GitHub repository | ✅ Done | https://github.com/csrnicek/hamilton_erp (private) |
| Local repo path | ✅ Done | `/Users/chrissrnicek/hamilton_erp` |
| Hosting platform | ✅ Done | Frappe Cloud, Hetzner Ashburn VA, ~$40/mo |
| Three-AI architecture review | ✅ Done | ChatGPT + Gemini + Grok — see review_synthesis.md |

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
| float_variance | Currency | |
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
| Asset Board | Not started | 1 |
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
| 4 | Float amount | ✅ $200, configurable |
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
