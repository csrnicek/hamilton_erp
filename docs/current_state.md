# Hamilton ERP — Current State

Living tracker of what has been built, what is in progress, and what is blocked. Update this file as work progresses.

**Last updated:** 2026-04-08  
**Current phase:** Pre–Phase 0 (Project setup)

---

## Overall Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Foundation | Not started | App scaffold, DocTypes, roles, permissions |
| Phase 1: Asset Board & Sessions | Not started | — |
| Phase 2: POS Integration & Check-in | Not started | — |
| Phase 3: Cash Handling & Shifts | Not started | — |
| Phase 4: Refunds, Polish, Compatibility | Not started | — |
| Phase 5: Deployment & Hardening | Not started | — |

---

## Prerequisites

| Item | Status | Notes |
|---|---|---|
| ERPNext v16 development environment | Not set up | Need bench with ERPNext v16 installed |
| GitHub repository created | Not created | Repo name: `hamilton_erp` |
| Developer Mode enabled on site | — | Requires `bench set-config developer_mode 1` |
| Project knowledge files uploaded | In progress | Spec uploaded; coding standards, references, phases, decisions, this file pending |

---

## Custom DocTypes

| DocType | Schema Defined | Controller Built | Tests Written | Notes |
|---|---|---|---|---|
| Venue Asset | — | — | — | |
| Venue Session | — | — | — | Must include all V5.4 forward-compat fields |
| Cash Drop | — | — | — | |
| Cash Reconciliation | — | — | — | |
| Asset Status Log | — | — | — | |
| Shift Record | — | — | — | |
| Comp Admission Log | — | — | — | |

---

## Custom Fields on Standard DocTypes

| Standard DocType | Custom Field | Status | Notes |
|---|---|---|---|
| Item | `hamilton_is_admission` | — | Check field |
| Item | `hamilton_asset_category` | — | Link or Select: Room / Locker |
| Item | `hamilton_asset_tier` | — | Link or Select: Standard / Deluxe / etc. |
| Item | `hamilton_is_comp` | — | Check field |
| Sales Invoice | `hamilton_venue_session` | — | Link to Venue Session |

---

## Custom Pages

| Page | Status | Notes |
|---|---|---|
| Asset Board | — | Primary custom UI |
| Cash Drop Screen | — | Blind — no expected totals |
| Shift Start | — | Float verify + board confirm |
| Shift Close | — | Final drop + POS Closing auto-creation |
| Manager Reconciliation | — | Blind entry then reveal |
| Asset Assignment Prompt | — | Post-POS overlay showing available assets |

---

## Standard ERPNext Configuration

| Configuration | Status | Notes |
|---|---|---|
| POS Profile (Hamilton) | — | Payment methods, default customer, item groups |
| Items — Admission types | — | Standard Room, Deluxe Room, Locker, Comp variants |
| Items — Retail | — | 25+ items (drinks, snacks, towels, supplies) |
| Item Tax Template — HST Taxable | — | 13% Ontario HST, tax-inclusive |
| Item Tax Template — HST Exempt | — | 0% |
| Pricing Rules (promos) | — | At least one test promo for QA |
| Mode of Payment — Card | — | No integration |
| Mode of Payment — Cash | — | Standard |
| Default Customer — Walk-in | — | Standard POS customer |
| Role Permissions — POS Closing blocked | — | Hamilton Operator cannot access POS Closing Entry |

---

## QA Test Cases (Build Spec §15)

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
| H18 | Shift Start with Float Variance | — | 3 |
| H19 | Shift Start Board Correction | — | 3 |
| H20 | Auto-Applied Promotion | — | 2 |
| H21 | No Promotion Active | — | 2 |
| H22 | Record Structure Integrity | — | 4 |

---

## Blockers and Open Questions

| # | Question / Blocker | Status | Resolution |
|---|---|---|---|
| 1 | GitHub repo URL | Open | Need to create repo and update `reference_links.md` |
| 2 | Room count and tier names | Open | TBD during setup — spec says "values TBD" |
| 3 | Expected stay durations | Open | Rooms and lockers — values TBD per spec §13 |
| 4 | Fixed float amount | Open | Spec says configurable, example $200 — confirm actual |
| 5 | Label printer model and driver approach | Open | Dymo or Brother — decide during Phase 3 |
| 6 | Retail item list (25+ items) | Open | Need complete list with prices and tax status |
| 7 | Promotional pricing rules | Open | Need specific promo definitions (which days, what discount) |
| 8 | Comp admission reason categories | Open | Spec lists: Loyalty Card / Promo / Manager Decision / Other — confirm |
| 9 | Development environment setup | Open | Docker or native bench — developer's choice |

---

*Update this file after each work session. Change statuses, add blockers, record completions.*
