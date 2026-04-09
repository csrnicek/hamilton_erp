# Hamilton ERP — Current State

Living tracker of what has been built, what is in progress, and what is blocked.

**Last updated:** 2026-04-09
**Current phase:** Pre–Phase 0 (Project setup — nothing built yet)

---

## ⚠️ SESSION PROTOCOL — READ FIRST

**Every conversation in this project must update this file before ending.**

At the end of each session, produce an updated `current_state.md` and tell the user:
> "Here is the updated `current_state.md` — please replace the version in your Project knowledge base with this file."

Update frequency: any session longer than ~1 hour should also checkpoint mid-session.

What to update each session:
- Change statuses in all tables (— → In Progress → Done)
- Add any new blockers or resolved blockers
- Add any new decisions to `decisions_log.md` (and note them here)
- Update "Last updated" date and "Current phase"
- Note what was worked on and what to pick up next under "Session Notes"

---

## Session Notes

### 2026-04-09 (this session)
- Diagnosed why conversations feel disconnected: each chat is separate by design; the fix is disciplined end-of-session file updates
- Established the session update protocol above
- Confirmed: hosting decision is **Frappe Cloud, Hetzner Ashburn (Virginia), dedicated plan ~$40/mo**
- No code has been written yet — still Pre-Phase 0
- **Next session should start Phase 0: app scaffold**

### 2026-04-08
- Created all 5 project `.md` files: `build_phases.md`, `decisions_log.md`, `current_state.md`, `coding_standards.md`, `reference_links.md`
- Recorded DEC-001 through DEC-007 in decisions log
- Deep-dive research on Frappe/ERPNext best practices — findings incorporated into `coding_standards.md` and `reference_links.md`
- Hosting decision made: Frappe Cloud Hetzner Ashburn Virginia dedicated plan

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
| ERPNext v16 development environment | Not set up | Docker or native bench — developer's choice (see `reference_links.md` §5) |
| GitHub repository created | Not created | Repo name: `hamilton_erp` — create before Phase 0 coding starts |
| Developer Mode enabled on site | Pending | Requires `bench set-config developer_mode 1` after site creation |
| Project knowledge files in Claude Project | ✅ Done | All 5 `.md` files uploaded; session update protocol now in place |
| Hosting platform decided | ✅ Done | Frappe Cloud, Hetzner Ashburn VA, dedicated ~$40/mo |

---

## Custom DocTypes

| DocType | Schema Defined | Controller Built | Tests Written | Notes |
|---|---|---|---|---|
| Venue Asset | — | — | — | |
| Venue Session | — | — | — | Must include all V5.4 forward-compat fields (DEC-007) |
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
| Item | `hamilton_asset_category` | — | Select: Room / Locker |
| Item | `hamilton_asset_tier` | — | Select: Standard / Deluxe / etc. |
| Item | `hamilton_is_comp` | — | Check field |
| Sales Invoice | `hamilton_venue_session` | — | Link to Venue Session |
| Sales Invoice | `hamilton_comp_reason` | — | Text — comp reason |

---

## Custom Pages

| Page | Status | Notes |
|---|---|---|
| Asset Board | — | Primary custom UI |
| Asset Assignment Prompt | — | Post-POS overlay showing available assets |
| Cash Drop Screen | — | Blind — no expected totals shown ever |
| Shift Start | — | Float verify + board confirm |
| Shift Close | — | Final drop + POS Closing auto-creation |
| Manager Reconciliation | — | Blind entry then reveal |

---

## Standard ERPNext Configuration

| Configuration | Status | Notes |
|---|---|---|
| POS Profile (Hamilton) | — | Payment methods, default customer, item groups |
| Items — Admission types | — | Standard Room, Deluxe Room, Locker, Comp variants |
| Items — Retail | — | 25+ items (drinks, snacks, towels, supplies) — list TBD |
| Item Tax Template — HST Taxable | — | 13% Ontario HST, tax-inclusive |
| Item Tax Template — HST Exempt | — | 0% |
| Pricing Rules (promos) | — | At least one test promo for QA — definitions TBD |
| Mode of Payment — Card | — | No integration; operator confirms manually |
| Mode of Payment — Cash | — | Standard |
| Default Customer — Walk-in | — | Standard POS anonymous customer |
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
| 1 | GitHub repo URL | Open | Create repo, update `reference_links.md` §6 |
| 2 | Room count and tier names | Open | TBD during setup |
| 3 | Expected stay durations (rooms + lockers) | Open | Values TBD per spec §13 |
| 4 | Fixed float amount | Open | Example $200 — confirm actual with Hamilton |
| 5 | Label printer model | Open | Dymo or Brother — decide in Phase 3 |
| 6 | Retail item list (25+ items) | Open | Need complete list with prices and tax status |
| 7 | Promotional pricing rules | Open | Need specific promo definitions (days, discount amount) |
| 8 | Comp admission reason categories | Open | Spec lists: Loyalty Card / Promo / Manager Decision / Other — confirm |
| 9 | Dev environment setup | Open | Docker or native bench — developer's choice |

---

*This file is the source of truth for project status. Replace in Claude Project knowledge base after every session.*
