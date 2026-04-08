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

*Add new decisions below this line. Use the next sequential number.*
