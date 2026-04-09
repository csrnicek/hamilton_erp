# Hamilton ERP — External Review Package
**Date:** 2026-04-09
**Purpose:** Independent review of architecture, decisions, and readiness before Phase 0 coding begins
**Reviewer instructions:** See the Review Checklist section at the bottom of this document

---

# PART 1 — PROJECT OVERVIEW

## What We Are Building
Club Hamilton is a bathhouse/spa venue in Ontario, Canada. We are building a custom Frappe app (`hamilton_erp`) that extends the standard ERPNext v16 POS system to manage:
- A visual asset board showing 59 rooms and lockers with real-time status
- Guest check-in flow linking POS transactions to specific rooms/lockers
- Blind cash drop system (operators never see expected totals)
- Shift management (start, close, float verification)
- Manager three-way cash reconciliation
- Comp admission tracking with mandatory audit logging

**Key constraint:** Hamilton has no membership system. Guests are anonymous walk-ins. This is a pilot venue — the system must be forward-compatible with a future membership-enabled venue (Club Philadelphia).

**Tech stack:** ERPNext v16 / Frappe Framework v16, Python 3.11+, MariaDB, JavaScript

---

# PART 2 — BUILD SPECIFICATION (SUMMARY)

## Architecture Decision: Standard POS + Custom Extensions Only
- Standard ERPNext POS handles: items, cart, payment, tax, pricing rules, receipts, returns
- Custom Frappe app handles: asset board, session lifecycle, blind cash control, shift management, reconciliation
- Rule: Before building anything custom, ask "Does standard ERPNext already do this?"

## Asset Inventory (59 total)
| Asset Type | Count | Display Name | Regular Price | Stay Duration |
|---|---|---|---|---|
| Locker | 33 | Lckr | $29.00 HST-incl | 6 hours |
| Single Standard Room | 11 | Sing STD | $36.00 HST-incl | 6 hours |
| Deluxe Single Room | 10 | Sing DLX | $41.00 HST-incl | 6 hours |
| Glory Hole Room | 2 | Glory | $45.00 HST-incl | 6 hours |
| Double Deluxe Room | 3 | Dbl DLX | $47.00 HST-incl | 6 hours |

## Pricing Rules
**Locker Special — $17.00 flat:**
- Mon–Fri: 9:00 AM – 11:00 AM
- Sun–Thu: 4:00 PM – 7:00 PM
- Locker only. Configured as ERPNext Pricing Rule.

**Under 25 Discount — 50% off:**
- All asset types
- Operator manually applies after ID check
- Any time, any day
- Does NOT stack with Locker Special
- Configured as ERPNext Pricing Rule, manually triggered

## Tax
- Ontario HST 13%, tax-inclusive pricing
- Some retail items exempt (e.g. bottled water)
- ERPNext Item Tax Templates handle this natively

## Cash Handling
- Operators NEVER see expected cash totals — blind drop system
- Fixed float: $200 per shift (configurable)
- Manager performs three-way reconciliation: system expected vs operator declared vs manager actual count
- Label printer: Brother QL-820NWB (network WiFi, IP configurable)

## Comp Admissions
- Reason required: Loyalty Card / Promo / Manager Decision / Other
- "Other" requires mandatory free-text explanation (max ~500 chars)
- Full audit log

## Roles
- Hamilton Operator: can do everything except access POS Closing Entry or manager reconciliation
- Hamilton Manager: can access reconciliation screen only

## Forward Compatibility
- Venue Session DocType must contain all V5.4 fields (membership, identity, arrears, scanner) even though they are null at Hamilton
- "Deferred ≠ absent from schema"

---

# PART 3 — ALL ARCHITECTURAL DECISIONS (DEC-001 to DEC-016)

## DEC-001 — Standard POS, Custom Extensions Only
Use the standard ERPNext POS for all transaction, payment, tax, and promotion functionality. Custom development is limited to the asset board, session lifecycle, blind cash control, and manager reconciliation.

## DEC-002 — Payment Before Asset Assignment
Payment is collected and confirmed in the standard POS first. Asset assignment happens after payment confirmation, not during. Eliminates need for lock timeouts and payment uncertainty engine.

## DEC-003 — Single Entity Type for Rooms and Lockers
One DocType (Venue Asset) with asset_category (Room/Locker) and asset_tier fields. Same lifecycle, same state machine, same board UI.

## DEC-004 — Custom Fields Prefixed with `hamilton_`
All custom fields on standard DocTypes use the hamilton_ prefix to prevent namespace collisions.

## DEC-005 — Blind Cash Drop Replaces Standard POS Closing for Operators
Operators denied permission to POS Closing Entry. Use custom Cash Drop screen instead. System auto-creates POS Closing Entry in background for accounting integrity.

## DEC-006 — GitHub as Version Control and Deployment
App lives at https://github.com/csrnicek/hamilton_erp. Deployment via bench get-app.

## DEC-007 — Forward-Compatibility Fields Are Mandatory
All V5.4 fields must exist in Venue Session DocType even though null at Hamilton. Deferred ≠ absent from schema.

## DEC-008 — Asset Inventory and Display Names
59 assets across 5 tiers — see asset inventory table above.

## DEC-009 — Expected Stay Duration
6 hours for all asset types. Configurable per asset type.

## DEC-010 — Fixed Float Amount
$200 default. Configurable per venue via Hamilton Settings DocType.

## DEC-011 — Label Printer
Brother QL-820NWB, network WiFi, print via backend API. IP configurable as system setting.

## DEC-012 — GitHub is Single Source of Truth
GitHub repo is the only source of truth for all docs and code. Claude reads from GitHub at session start via browser tool and pushes via GitHub API automatically.

## DEC-013 — Asset Pricing (HST-Inclusive)
Lckr $29 / Sing STD $36 / Sing DLX $41 / Glory $45 / Dbl DLX $47. Stored as ERPNext Item Price records — never hardcoded.

## DEC-014 — Pricing Rules: Locker Special and Under 25
Locker Special $17 (time-based). Under 25 = 50% off all assets (manual). No stacking. Both as ERPNext Pricing Rules.

## DEC-015 — All Prices and Rules Are Configurable, Never Hardcoded
Prices → Item Price records. Assets → Venue Asset records. Promos → Pricing Rules. System values → Hamilton Settings DocType.

## DEC-016 — Comp Admission Reason Categories
Loyalty Card / Promo / Manager Decision / Other. "Other" = mandatory free-text, ~500 char max.

---

# PART 4 — CUSTOM DOCTYPES (7 custom + 1 settings)

### Venue Asset
asset_name, asset_category (Room/Locker), asset_tier, status (Available/Occupied/Dirty/Out of Service), current_session (link), expected_stay_duration, display_order

### Venue Session
venue_asset (link), sales_invoice (link), admission_item, session_start, session_end, status (Active/Completed), operator_checkin, operator_vacate, vacate_method (Key Return/Discovery on Rounds)
**Forward compat fields (null at Hamilton):** member_id, full_name, date_of_birth, membership_status, identity_method (= "not_applicable"), arrears_amount, arrears_flag, scanner_data, eligibility_snapshot, block_status

### Cash Drop
operator, shift_date, shift_identifier, drop_type (Mid-Shift/End-of-Shift), drop_number, declared_amount, timestamp, reconciled, reconciliation (link)

### Cash Reconciliation
cash_drop (link), manager, actual_count, system_expected, operator_declared, variance_flag (Clean/Possible Theft or Error/Operator Mis-declared), notes, timestamp

### Asset Status Log
venue_asset (link), previous_status, new_status, reason, operator, timestamp

### Shift Record
operator, shift_date, shift_start, shift_end, float_expected, float_actual, float_variance, board_confirmed, board_corrections, status (Open/Closed)

### Comp Admission Log
venue_session (link), sales_invoice (link), reason_category (Loyalty Card/Promo/Manager Decision/Other), reason_note (mandatory if Other, max 500 chars), operator, timestamp

### Hamilton Settings (Single DocType)
float_amount, default_stay_duration_minutes, printer_ip_address, printer_model

---

# PART 5 — CUSTOM FIELDS ON STANDARD DOCTYPES

| DocType | Field | Type | Purpose |
|---|---|---|---|
| Item | hamilton_is_admission | Check | Triggers asset assignment after POS |
| Item | hamilton_asset_category | Select (Room/Locker) | Filters asset board |
| Item | hamilton_asset_tier | Select | Links item to asset tier |
| Item | hamilton_is_comp | Check | Triggers comp reason prompt |
| Sales Invoice | hamilton_venue_session | Link → Venue Session | Links transaction to session |
| Sales Invoice | hamilton_comp_reason | Text | Comp reason if applicable |

---

# PART 6 — CUSTOM PAGES (6 screens)

1. **Asset Board** — real-time grid of all 59 assets, color-coded by state, tap to interact
2. **Asset Assignment Prompt** — post-POS overlay, filtered to available assets of correct type
3. **Cash Drop Screen** — operator enters declared amount only, no expected totals ever shown
4. **Shift Start** — float verify + asset board review and correction
5. **Shift Close** — final drop + auto POS Closing Entry creation
6. **Manager Reconciliation** — blind entry then three-way reveal

---

# PART 7 — STATE MACHINE (Venue Asset)

Valid transitions only:
- Available → Occupied (after payment + assignment)
- Available → Out of Service (with mandatory reason)
- Occupied → Dirty (operator marks Vacant)
- Occupied → Out of Service (with mandatory reason)
- Dirty → Available (operator marks Clean)
- Dirty → Out of Service (with mandatory reason)
- Out of Service → Available (with mandatory reason)

No other transitions permitted. Enforced server-side.

---

# PART 8 — WHAT IS DEFERRED (not built for Hamilton)

- Membership / identity / scanner system
- Arrears enforcement
- Payment uncertainty engine
- Offline operation software
- Shared terminal clerk model
- Manager override hierarchy
- Stripe payment integration
- Vacant reversal and move guest

---

# PART 9 — QA TEST CASES (22 tests, H1–H22)

H1 Standard Room Check-in | H2 Standard Locker Check-in | H3 Check-in with Retail | H4 Cancel Mid-Transaction | H5 Comp Admission | H6 Standalone Retail Sale | H7 Tax Handling | H8 Line-Item Refund | H9 Full Transaction Refund | H10 Vacate and Turnover | H11 Out of Service | H12 Occupied Asset Rejection | H13 Mid-Shift Cash Drop | H14 End-of-Shift Close-out | H15 Manager Reconciliation (Clean) | H16 Manager Reconciliation (Variance) | H17 Operator Cannot Access POS Closing | H18 Shift Start Float Variance | H19 Shift Start Board Correction | H20 Auto-Applied Promotion | H21 No Promotion Active | H22 Record Structure Integrity

---

# PART 10 — OPEN ITEMS (not yet decided)

1. Retail item list (25+ items) — prices and HST status — to be provided
2. Dev environment — Frappe Cloud (decided, setup pending)

---

# REVIEW CHECKLIST — QUESTIONS FOR THE REVIEWER

Please review the above and answer all of the following:

## A. Architecture Review
1. Is the "standard POS + custom extensions only" approach sound for ERPNext v16? Any risks?
2. Is "payment before asset assignment" the right call for eliminating lock timeouts? Any edge cases we haven't considered?
3. Is one DocType (Venue Asset) with a category field the right approach for rooms and lockers, or should they be separate DocTypes?
4. Are there any standard ERPNext features we should be using that we're building custom instead?

## B. DocType Schema Review
5. Are all 7 custom DocTypes complete? Is anything missing from any schema?
6. Are the forward-compatibility fields on Venue Session sufficient for a future membership-enabled venue?
7. Is Hamilton Settings the right approach for system constants (float, stay duration, printer IP)?
8. Are the custom fields on Item and Sales Invoice sufficient, or are we missing any?

## C. Pricing and Rules Review
9. Is the Under 25 discount (50% off, manually applied) implementable as a standard ERPNext Pricing Rule? How exactly should it be configured?
10. Is the Locker Special (flat price $17, day/time validity) implementable as a standard ERPNext Pricing Rule?
11. Is the non-stacking rule (Under 25 cannot combine with Locker Special) enforceable in standard ERPNext Pricing Rules?
12. Is HST-inclusive pricing (back-calculate 13% from inclusive price) handled correctly by standard ERPNext Item Tax Templates?

## D. Cash Control Review
13. Is the blind cash drop system (operators never see expected totals) achievable purely through role permissions on POS Closing Entry + a custom Cash Drop page?
14. Is the three-way reconciliation model (system expected vs operator declared vs manager actual) logically sound? Any gaps?
15. Is the background auto-creation of POS Closing Entry after a blind drop the right approach for accounting integrity?

## E. Security and Permissions Review
16. Is the role model (Hamilton Operator vs Hamilton Manager) sufficient? Any permission gaps?
17. Is blocking operator access to POS Closing Entry via Role Permissions the correct ERPNext mechanism?

## F. Forward Compatibility Review
18. Are the null V5.4 fields on Venue Session sufficient to support a future membership-enabled venue without schema migration?
19. Is there anything in the Hamilton build that would need to be rewritten (not just extended) for Philadelphia?

## G. General Gaps
20. What is the single biggest risk in this plan that we haven't addressed?
21. Is there anything missing that would prevent Phase 0 (app scaffold + DocTypes) from being built correctly right now?
22. Any other concerns, recommendations, or red flags?

