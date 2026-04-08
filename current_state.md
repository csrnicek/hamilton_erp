# Hamilton ERP — Current State

Living tracker of what has been built, what is in progress, and what is blocked. Update this file after each work session.

**Last updated:** 2026-04-08  
**Current phase:** Phase 0 complete — scaffold built, DocTypes defined, roles configured

---

## Overall Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Foundation | **Complete** | App scaffold, all 7 DocTypes, fixtures, roles, patches.txt, install hook |
| Phase 1: Asset Board & Sessions | Not started | — |
| Phase 2: POS Integration & Check-in | Not started | — |
| Phase 3: Cash Handling & Shifts | Not started | — |
| Phase 4: Refunds, Polish, Compatibility | Not started | — |
| Phase 5: Deployment & Hardening | Not started | — |

---

## Phase 0 Deliverables

| Deliverable | Status | Notes |
|---|---|---|
| App scaffold (pyproject.toml, setup.py, requirements.txt, .gitignore) | **Done** | — |
| `hooks.py` with metadata, required_apps, fixtures, after_install, doc_events stub, scheduler | **Done** | — |
| `patches.txt` with [pre_model_sync] / [post_model_sync] sections | **Done** | Empty — no patches yet |
| `modules.txt` registering Hamilton ERP module | **Done** | — |
| `after_install` setup script (setup/install.py) | **Done** | Creates roles, permissions, blocks POS Closing for Operator |
| `overrides/sales_invoice.py` | **Done** | HamiltonSalesInvoice class stub |
| `api.py` + `utils.py` + `tasks.py` | **Done** | Stubs wired, Phase 2/1 fills them out |
| All 7 DocTypes with JSON, controller, JS, tests | **Done** | See below |
| Custom fields fixture (Item + Sales Invoice) | **Done** | `fixtures/custom_field.json` |
| Roles fixture | **Done** | `fixtures/role.json` |

---

## Custom DocTypes

| DocType | Schema (JSON) | Controller | Tests | Notes |
|---|---|---|---|---|
| Venue Asset | **Done** | **Done** (validation skeleton) | **Done** | State transition validation in controller |
| Venue Session | **Done** | **Done** | **Done** | All V5.4 forward-compat fields included; identity_method defaults to not_applicable |
| Cash Drop | **Done** | **Done** | **Done** | |
| Cash Reconciliation | **Done** | **Done** (variance logic) | **Done** | Manager-only permissions; operator has zero access |
| Asset Status Log | **Done** | **Done** | **Done** | Reason required for OOS transitions |
| Shift Record | **Done** | **Done** | **Done** | float_variance calculated automatically |
| Comp Admission Log | **Done** | **Done** | **Done** | |

---

## Custom Fields on Standard DocTypes

| Standard DocType | Custom Field | Status | Notes |
|---|---|---|---|
| Item | `hamilton_is_admission` | **Done** | Check field; in fixtures/custom_field.json |
| Item | `hamilton_asset_category` | **Done** | Select: Room/Locker |
| Item | `hamilton_asset_tier` | **Done** | Select: Standard/Deluxe |
| Item | `hamilton_is_comp` | **Done** | Check field |
| Sales Invoice | `hamilton_venue_session` | **Done** | Link to Venue Session; read-only |
| Sales Invoice | `hamilton_comp_reason` | **Done** | Select: reason categories |

---

## Prerequisites (still pending before first bench install)

| Item | Status | Notes |
|---|---|---|
| ERPNext v16 development environment | Not set up | Need bench with ERPNext v16 installed |
| GitHub repository created | Not created | Create repo and push this code |
| Developer Mode enabled on site | — | `bench --site [site] set-config developer_mode 1` |

---

## Custom Pages (Phase 1+)

| Page | Status | Notes |
|---|---|---|
| Asset Board | — | Phase 1 |
| Cash Drop Screen | — | Phase 3 |
| Shift Start | — | Phase 3 |
| Shift Close | — | Phase 3 |
| Manager Reconciliation | — | Phase 3 |
| Asset Assignment Prompt | — | Phase 2 |

---

## Standard ERPNext Configuration (Phase 2+)

| Configuration | Status | Notes |
|---|---|---|
| POS Profile (Hamilton) | — | Phase 2 |
| Items — Admission types | — | Phase 2 |
| Items — Retail | — | Phase 2 |
| Item Tax Template — HST Taxable | — | Phase 2 |
| Item Tax Template — HST Exempt | — | Phase 2 |
| Pricing Rules (promos) | — | Phase 2 |
| Mode of Payment — Card | — | Phase 2 |
| Mode of Payment — Cash | — | Phase 2 |
| Default Customer — Walk-in | — | Phase 2 |
| Role Permissions — POS Closing blocked | Handled in after_install | Phase 0 ✓ |

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
| H22 | Record Structure Integrity | — | 4 (partially tested in test_venue_session.py) |

---

## Blockers and Open Questions

| # | Question / Blocker | Status | Resolution |
|---|---|---|---|
| 1 | GitHub repo URL | Open | Create repo, push code, update reference_links.md |
| 2 | Room count and tier names | Open | TBD during setup |
| 3 | Expected stay durations | Open | Rooms and lockers — values TBD |
| 4 | Fixed float amount | Open | Spec example $200 — confirm actual |
| 5 | Label printer model and driver approach | Open | Decide during Phase 3 |
| 6 | Retail item list (25+ items) | Open | Need complete list with prices and tax status |
| 7 | Promotional pricing rules | Open | Need specific promo definitions |
| 8 | Comp admission reason categories | Open | Spec lists: Loyalty Card / Promo / Manager Decision / Other — in schema |
| 9 | Development environment setup | Open | Docker or native bench — developer's choice |

---

*Update this file after each work session. Change statuses, add blockers, record completions.*
