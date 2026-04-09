# Hamilton ERP — Current State

Living tracker of what has been built, what is in progress, and what is blocked.

**Last updated:** 2026-04-09
**Current phase:** Pre–Phase 0 (Ready to start coding)

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
- Established GitHub as single source of truth (DEC-012)
- Removed all files from Claude Project knowledge base
- Added Project Instructions to auto-read from GitHub each session
- Recovered asset inventory, stay durations, float, and label printer decisions from previous chat
- Confirmed local path: `/Users/chrissrnicek/hamilton_erp`
- Confirmed all pricing, specials, and discount rules
- All blockers except retail item list, promo details, and dev environment are now resolved
- **Next session:** Start Phase 0 app scaffold

### 2026-04-08
- Created all 5 project `.md` files
- Recorded DEC-001 through DEC-011
- Deep-dive research on Frappe/ERPNext best practices
- Hosting decision: Frappe Cloud, Hetzner Ashburn Virginia, ~$40/mo
- Resolved asset inventory, stay durations, float, label printer

---

## Overall Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Foundation | Not started | Ready to begin |
| Phase 1: Asset Board & Sessions | Not started | — |
| Phase 2: POS Integration & Check-in | Not started | — |
| Phase 3: Cash Handling & Shifts | Not started | — |
| Phase 4: Refunds, Polish, Compatibility | Not started | — |
| Phase 5: Deployment & Hardening | Not started | — |

---

## Prerequisites

| Item | Status | Notes |
|---|---|---|
| ERPNext v16 development environment | Not set up | Docker or native bench |
| GitHub repository | ✅ Done | https://github.com/csrnicek/hamilton_erp (private) |
| Local repo path | ✅ Done | `/Users/chrissrnicek/hamilton_erp` |
| Developer Mode enabled on site | Pending | After site creation |
| Project knowledge files | ✅ Done | All in `/docs/` on GitHub |
| Hosting platform | ✅ Done | Frappe Cloud, Hetzner Ashburn VA, ~$40/mo |

---

## Hamilton Asset Inventory (CONFIRMED)

| Asset Type | Count | Display Name | Tier Name | Stay Duration | Regular Price |
|---|---|---|---|---|---|
| Locker | 33 | Lckr | Locker | 6 hours | $29.00 |
| Room | 11 | Sing STD | Single Standard | 6 hours | $36.00 |
| Room | 10 | Sing DLX | Deluxe Single | 6 hours | $41.00 |
| Room | 2 | Glory | Glory Hole | 6 hours | $45.00 |
| Room | 3 | Dbl DLX | Double Deluxe | 6 hours | $47.00 |
| **Total** | **59** | | | | |

All prices are **HST-inclusive** (13% Ontario HST back-calculated from inclusive price).

**Float:** $200 (configurable per venue)
**Label Printer:** Brother QL-820NWB, network WiFi, IP configurable

---

## Pricing Rules (CONFIRMED)

All prices, assets, and specials are configurable — never hardcoded. They live in:
- **Item Prices** → ERPNext Item Price records (change without code)
- **Venue Assets** → Venue Asset DocType records (add/remove assets without code)
- **Pricing Rules** → ERPNext Pricing Rules (add/change specials without code)
- **Hamilton Settings** → Custom settings DocType (float, stay duration, printer IP)

### Locker Special — $17.00
| Days | Hours |
|---|---|
| Monday – Friday | 9:00 AM – 11:00 AM |
| Sunday – Thursday | 4:00 PM – 7:00 PM |

Configured as an ERPNext Pricing Rule with day/time validity.
Applies to Locker item only. Price drops to $17 flat (not a % discount).

### Under 25 Discount — 50% off
- Applies to **all asset types** (Lckr, Sing STD, Sing DLX, Glory, Dbl DLX)
- Operator manually applies after confirming guest age by ID
- Applied at any time, any day
- **Does NOT stack with Locker Special** — if Locker Special is active, operator must choose one or the other
- Configured as an ERPNext Pricing Rule, manually triggered by operator

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
| Hamilton Settings | — | — | — | Float amount, stay duration, printer IP |

---

## Custom Fields on Standard DocTypes

| Standard DocType | Custom Field | Status | Notes |
|---|---|---|---|
| Item | `hamilton_is_admission` | — | Check field |
| Item | `hamilton_asset_category` | — | Select: Room / Locker |
| Item | `hamilton_asset_tier` | — | Select: Locker / Single Standard / Deluxe Single / Glory Hole / Double Deluxe |
| Item | `hamilton_is_comp` | — | Check field |
| Sales Invoice | `hamilton_venue_session` | — | Link to Venue Session |
| Sales Invoice | `hamilton_comp_reason` | — | Text |

---

## Custom Pages

| Page | Status | Notes |
|---|---|---|
| Asset Board | — | Primary custom UI |
| Asset Assignment Prompt | — | Post-POS overlay |
| Cash Drop Screen | — | Blind — no expected totals ever |
| Shift Start | — | Float verify + board confirm |
| Shift Close | — | Final drop + POS Closing auto-creation |
| Manager Reconciliation | — | Blind entry then reveal |

---

## Standard ERPNext Configuration

| Configuration | Status | Notes |
|---|---|---|
| POS Profile (Hamilton) | — | — |
| Items — Admission types | — | Lckr $29, Sing STD $36, Sing DLX $41, Glory $45, Dbl DLX $47 + comp variants |
| Items — Retail | — | 25+ items — list pending |
| Item Tax Template — HST Taxable | — | 13% Ontario HST, tax-inclusive |
| Item Tax Template — HST Exempt | — | 0% |
| Pricing Rule — Locker Special | — | $17, Mon–Fri 9–11am, Sun–Thu 4–7pm |
| Pricing Rule — Under 25 | — | 50% off all assets, manual, no stack with Locker Special |
| Mode of Payment — Card | — | No integration; operator confirms manually |
| Mode of Payment — Cash | — | Standard |
| Default Customer — Walk-in | — | Standard POS anonymous customer |
| Role Permissions — POS Closing blocked | — | Hamilton Operator cannot access POS Closing Entry |

---

## Blockers and Open Questions

| # | Question / Blocker | Status | Resolution |
|---|---|---|---|
| 1 | GitHub repo URL | ✅ Resolved | https://github.com/csrnicek/hamilton_erp |
| 2 | Room count and tier names | ✅ Resolved | 5 tiers, 59 total assets |
| 3 | Expected stay durations | ✅ Resolved | 6 hours all asset types |
| 4 | Fixed float amount | ✅ Resolved | $200, configurable |
| 5 | Label printer model | ✅ Resolved | Brother QL-820NWB, network print |
| 6 | Asset pricing | ✅ Resolved | See pricing table above |
| 7 | Pricing rules | ✅ Resolved | Locker Special + Under 25 — see above |
| 8 | Retail item list | ⏳ Open | Chris to provide 25+ items with prices and tax status |
| 9 | Comp admission reason categories | ✅ Resolved | Loyalty Card / Promo / Manager Decision / Other (Other = mandatory free-text, 500 char max) |
| 10 | Dev environment setup | ⏳ Open | Docker or native bench |

---

*GitHub is the single source of truth. Push after every session.*
