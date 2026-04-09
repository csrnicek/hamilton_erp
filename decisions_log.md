# Hamilton ERP — Decisions Log

Records architectural and implementation decisions made during development. This prevents revisiting settled questions and provides context for why things were built a certain way.

**Format:** Each decision gets a number, date, context, decision, and rationale.

---

## DEC-001 — Standard POS, Custom Extensions Only

**Date:** 2026-04-08  
**Context:** Needed to decide whether to build a custom POS or use ERPNext's standard POS.  
**Decision:** Use the standard ERPNext POS for all transaction, payment, tax, and promotion functionality. Custom development is limited to the asset board, session lifecycle, blind cash control, and manager reconciliation.  
**Rationale:** The build spec (§1.1) mandates standard-first. The standard POS handles items, cart, payment, tax, pricing rules, receipts, and returns natively. Building a custom POS would duplicate thousands of lines of tested code and create a maintenance burden. Custom code hooks into POS events (e.g., after Sales Invoice submission) rather than replacing the POS.

---

## DEC-002 — Payment Before Asset Assignment

**Date:** 2026-04-08  
**Context:** The V5.4 spec includes lock timeouts and refresh mechanisms for assets held during payment. Hamilton needs a simpler approach.  
**Decision:** Payment is collected and confirmed in the standard POS first. Asset assignment happens after payment confirmation, not during.  
**Rationale:** This eliminates the need for lock timeouts, refresh mechanisms, and the payment uncertainty engine entirely. An asset moves directly from Available to Occupied — there is no "locked pending payment" state. See build spec §4.2.

---

## DEC-003 — Single Entity Type for Rooms and Lockers

**Date:** 2026-04-08  
**Context:** Rooms and lockers could be modeled as separate DocTypes or as one DocType with a category field.  
**Decision:** One DocType (`Venue Asset`) with `asset_category` (Room/Locker) and `asset_tier` (Standard/Deluxe/etc.) fields.  
**Rationale:** Same lifecycle, same state machine, same board UI — just different visual grouping and pricing. Two DocTypes would duplicate all logic. Build spec §5.1 confirms this approach.

---

## DEC-004 — Custom Fields Prefixed with `hamilton_`

**Date:** 2026-04-08  
**Context:** Need to add fields to standard DocTypes (Item, Sales Invoice) without conflicting with ERPNext upgrades or other apps.  
**Decision:** All custom fields on standard DocTypes use the `hamilton_` prefix.  
**Rationale:** Prevents namespace collisions during ERPNext upgrades. Makes it immediately clear which fields are custom. Standard Frappe practice for multi-app environments.

---

## DEC-005 — Blind Cash Drop Replaces Standard POS Closing for Operators

**Date:** 2026-04-08  
**Context:** The standard POS Closing Entry shows expected cash totals, which violates Hamilton's blind cash control model.  
**Decision:** Operators are denied permission to POS Closing Entry. They use the custom Cash Drop screen instead. The system auto-creates POS Closing Entries in the background after blind drops so ERPNext accounting stays intact.  
**Rationale:** Build spec §7.1–7.2. The blind model prevents operators from reverse-engineering a "correct" count. The background POS Closing Entry ensures the GL and accounting reports remain accurate.

---

## DEC-006 — GitHub Required for Deployment

**Date:** 2026-04-08  
**Context:** Need to decide on version control and deployment strategy.  
**Decision:** The `hamilton_erp` app lives in a GitHub repository. Deployment to any bench environment uses `bench get-app [repo-url]`.  
**Rationale:** Frappe's bench tooling is built around Git. `bench get-app` pulls from a Git repo. Version control is essential for rollbacks, branching, and collaboration. The repo should be created early so code structure matches from the start.

---

## DEC-007 — Forward-Compatibility Fields Are Mandatory

**Date:** 2026-04-08  
**Context:** Hamilton doesn't use membership, identity, arrears, or scanner features. Should those fields exist in the schema?  
**Decision:** Yes. All V5.4 fields must exist in the Venue Session DocType even though they are null at Hamilton.  
**Rationale:** Build spec §11.4 and §14.1. "Deferred ≠ absent from schema." When Philadelphia comes online, the Venue Session records must already have the correct columns. Adding columns later to a table with production data is riskier than creating them empty now.

---

---

## DEC-008 — Cash Reconciliation and Venue Session Are Submittable Documents

**Date:** 2026-04-08  
**Context:** Both DocTypes have `before_submit`/`on_submit` lifecycle hooks, but the original JSON files were missing `is_submittable: 1`. Those hooks silently never fired.  
**Decision:** Both `cash_reconciliation.json` and `venue_session.json` have `is_submittable: 1` and the Hamilton Manager permission row includes `submit: 1` in both JSON and in `install.py`.  
**Rationale:** Frappe only fires `before_submit`/`on_submit` hooks on submittable documents. Without this flag the blind cash reveal flow (before_submit populates operator_declared, system_expected, variance_flag) and the Phase 2 session-close flow (on_submit moves asset to Dirty) would never execute, regardless of how correct the Python code was.

---

## DEC-009 — Variance Flag Uses Four-Branch Logic with system_matches_operator Fallthrough

**Date:** 2026-04-08  
**Context:** The original three-branch implementation returned "Operator Mis-declared" for all cases where manager≠operator AND manager≠system, including the case where system≈operator but manager found less cash (physically missing money).  
**Decision:** A fourth branch explicitly checks `system_matches_operator`. When POS and operator agree but the manager's physical count is less, the result is "Possible Theft or Error" rather than "Operator Mis-declared".  
**Rationale:** Build spec §7.7. If the POS recorded $500 and the operator declared $500 but the manager found $489, the cash is physically missing from the envelope. That is a theft/error scenario, not an operator mis-declaration. Misclassifying it as "Operator Mis-declared" would obscure genuine shortages.

---

## DEC-010 — install.py Grants submit=1 to Hamilton Manager via Dedicated Submittable Loop

**Date:** 2026-04-08  
**Context:** The generic `standard_manager_doctypes` loop in `_grant_manager_permissions()` grants read/write/create/delete but not submit. Venue Session and Cash Reconciliation both need submit. A Custom DocPerm row with submit=0 overrides the JSON's submit=1.  
**Decision:** A separate loop over `("Venue Session", "Cash Reconciliation")` grants full permissions including `submit=1` after the generic loop runs. The generic loop's submit=0 row is immediately overwritten by the dedicated loop.  
**Rationale:** Keeps the generic loop simple (no conditional logic per DocType) while ensuring submittable DocTypes get the correct permission. Adding new submittable DocTypes in future phases requires only adding them to the dedicated tuple.

---

## DEC-011 — display_order Default Is 0, Not NULL

**Date:** 2026-04-08  
**Context:** `venue_asset.json` had no default on `display_order`. When sorted `ORDER BY display_order asc`, NULL values in MySQL sort before 0, making any un-ordered asset appear above explicitly-ordered ones non-deterministically.  
**Decision:** `display_order` defaults to `0`. All assets that have not been manually ordered appear together at position 0, with `name asc` as the tiebreaker.  
**Rationale:** Deterministic sort output required by §9.5. Any future data migration for pre-existing records should run `UPDATE tabVenue Asset SET display_order=0 WHERE display_order IS NULL` before Phase 1 go-live.

---

## DEC-012 — get_next_drop_number Guards Against Blank shift_record

**Date:** 2026-04-08  
**Context:** `frappe.db.count("Cash Drop", {"shift_record": None})` counts drops with a null shift_record rather than raising an error. If called when no active shift exists, every call would silently return 1, producing duplicate drop numbers.  
**Decision:** `get_next_drop_number()` throws a plain-language error immediately if `shift_record` is blank. Callers must ensure an active shift exists before invoking this function.  
**Rationale:** Silent wrong-number generation is harder to debug than an explicit early failure. The error message ("Cannot create a Cash Drop: no active shift found. Please start a shift first.") tells the operator exactly what to do.

---

## DEC-013 — test_operator_cannot_access_cash_reconciliation Uses Two Independent Checks

**Date:** 2026-04-08  
**Context:** The original test only queried `Custom DocPerm`. On a fresh site where `install.py` has not yet run, that table is empty. The `for perm in perms` loop executed zero iterations and the test passed vacuously — zero assertions were checked.  
**Decision:** The test now performs two independent checks: (1) `frappe.get_meta("Cash Reconciliation").permissions` confirms the DocType JSON has zero Hamilton Operator rows — this fires even on a fresh site; (2) the Custom DocPerm query confirms install.py has not accidentally added operator access at runtime.  
**Rationale:** A security test that passes with zero assertions provides false confidence. Both checks together ensure the test fails correctly in all environments: pre-install, post-install, and post-migration.

---

*Add new decisions below this line. Use the next sequential number.*
