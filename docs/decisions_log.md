# Hamilton ERP — Decisions Log

Records architectural and implementation decisions made during development. This prevents revisiting settled questions and provides context for why things were built a certain way.

**Format:** Each decision gets a number, date, context, decision, and rationale.

---

## DEC-001 — Standard POS, Custom Extensions Only

**Date:** 2026-04-08
**Context:** Needed to decide whether to build a custom POS or use ERPNext's standard POS.
**Decision:** Use the standard ERPNext POS for all transaction, payment, tax, and promotion functionality. Custom development is limited to the asset board, session lifecycle, blind cash control, and manager reconciliation.
**Rationale:** The build spec (§1.1) mandates standard-first. The standard POS handles items, cart, payment, tax, pricing rules, receipts, and returns natively. Building a custom POS would duplicate thousands of lines of tested code and create a maintenance burden.

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
**Decision:** One DocType (`Venue Asset`) with `asset_category` (Room/Locker) and `asset_tier` fields.
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
**Rationale:** Build spec §7.1–7.2. The blind model prevents operators from reverse-engineering a "correct" count.

---

## DEC-006 — GitHub Required for Deployment

**Date:** 2026-04-08
**Context:** Need to decide on version control and deployment strategy.
**Decision:** The `hamilton_erp` app lives in a GitHub repository at https://github.com/csrnicek/hamilton_erp. Deployment to any bench environment uses `bench get-app [repo-url]`.
**Rationale:** Frappe's bench tooling is built around Git. Version control is essential for rollbacks, branching, and collaboration.

---

## DEC-007 — Forward-Compatibility Fields Are Mandatory

**Date:** 2026-04-08
**Context:** Hamilton doesn't use membership, identity, arrears, or scanner features. Should those fields exist in the schema?
**Decision:** Yes. All V5.4 fields must exist in the Venue Session DocType even though they are null at Hamilton.
**Rationale:** Build spec §11.4 and §14.1. "Deferred ≠ absent from schema." Adding columns later to a table with production data is riskier than creating them empty now.

---

## DEC-008 — Asset Inventory and Display Names

**Date:** 2026-04-08
**Context:** Room and locker counts, tier names, and display names were TBD in the original spec.
**Decision:** Club Hamilton has 59 assets across 5 tiers:

| Asset Type | Count | Display Name | Tier Name |
|---|---|---|---|
| Locker | 33 | Lckr | Locker |
| Room | 11 | Sing STD | Single Standard |
| Room | 10 | Sing DLX | Deluxe Single |
| Room | 2 | Glory | Glory Hole |
| Room | 3 | Dbl DLX | Double Deluxe |
| **Total** | **59** | | |

**Rationale:** Display names are abbreviated for POS screen and asset board readability. Full tier names used in reporting.

---

## DEC-009 — Expected Stay Duration

**Date:** 2026-04-08
**Context:** The spec listed stay durations as TBD. These drive the overtime overlay on the asset board.
**Decision:** 6 hours for all asset types (rooms and lockers).
**Rationale:** Operationally confirmed by Chris. Same duration for all assets keeps overtime logic simple. Value is configurable per asset type in the system — this is the Hamilton default.

---

## DEC-010 — Fixed Float Amount

**Date:** 2026-04-08
**Context:** The spec listed float as "configurable, e.g., $200." Hamilton's actual value needed to be confirmed.
**Decision:** Hamilton default float is $200. The float amount is a configurable system setting per venue — not hardcoded.
**Rationale:** $200 confirmed by Chris. Configurable because it will vary when other venues (e.g., Philadelphia) come online.

---

## DEC-011 — Label Printer Model and Integration Approach

**Date:** 2026-04-08
**Context:** Cash drop envelope labels require a label printer. Model and integration method were TBD.
**Decision:** Brother QL-820NWB. Network-connected (WiFi). Print via Brother network API from the Frappe backend. Printer IP address is a configurable system setting — not hardcoded.
**Rationale:** Better Linux/Docker support than Dymo. Network-connected means no dependency on which tablet is physically plugged in. Configurable IP means printer can be swapped or moved without code changes.

---

## DEC-012 — GitHub is Single Source of Truth for All Docs and Code

**Date:** 2026-04-09
**Context:** Docs were living in multiple places (Claude Project knowledge base, local filesystem, GitHub) causing confusion about which was authoritative.
**Decision:** GitHub repo (`https://github.com/csrnicek/hamilton_erp`) is the single source of truth. All `.md` files live in `/docs/`. Local filesystem is the working copy — push to GitHub to make it official. Claude Project knowledge base contains no uploaded files; Claude reads from GitHub at session start via Chrome browser tool.
**Rationale:** One source of truth eliminates confusion. Git provides version history. Claude's Project Instructions enforce the read-from-GitHub habit at session start.

---

*Add new decisions below this line. Use the next sequential number.*

## DEC-013 — Asset Pricing (HST-Inclusive)

**Date:** 2026-04-09
**Context:** Asset prices were TBD in the original spec.
**Decision:** All prices are HST-inclusive (13% Ontario HST back-calculated):

| Asset | Display Name | Price |
|---|---|---|
| Locker | Lckr | $29.00 |
| Single Standard | Sing STD | $36.00 |
| Deluxe Single | Sing DLX | $41.00 |
| Glory Hole | Glory | $45.00 |
| Double Deluxe | Dbl DLX | $47.00 |

**Rationale:** Prices stored as ERPNext Item Price records — never hardcoded. Configurable by manager without code changes.

---

## DEC-014 — Pricing Rules: Locker Special and Under 25 Discount

**Date:** 2026-04-09
**Context:** Hamilton has two special pricing rules that needed full definition.
**Decision:**

**Locker Special — $17.00 flat price:**
- Monday–Friday: 9:00 AM – 11:00 AM
- Sunday–Thursday: 4:00 PM – 7:00 PM
- Applies to Locker item only
- Configured as ERPNext Pricing Rule with day/time validity

**Under 25 Discount — 50% off:**
- Applies to all asset types
- Operator manually applies after confirming guest age by ID
- Any time, any day
- Does NOT stack with Locker Special — operator chooses one or the other
- Configured as ERPNext Pricing Rule, manually triggered

**Rationale:** Both rules configured as standard ERPNext Pricing Rules — no custom code needed. Configurable by manager without code changes. Non-stacking rule prevents double discounting.

---

## DEC-015 — All Prices and Rules Are Configurable, Never Hardcoded

**Date:** 2026-04-09
**Context:** Prices, asset inventory, and promotional rules will change over time and vary by venue.
**Decision:** Nothing business-configurable is hardcoded:
- Asset prices → ERPNext Item Price records
- Asset inventory → Venue Asset DocType records
- Promotions → ERPNext Pricing Rules
- Float, stay duration, printer IP → Hamilton Settings DocType

**Rationale:** Managers can change prices, add assets, or modify specials without any code changes or developer involvement.

---

*Add new decisions below this line. Use the next sequential number.*

## DEC-016 — Comp Admission Reason Categories and "Other" Handling

**Date:** 2026-04-09
**Context:** Comp admission reasons were listed as TBD in the spec.
**Decision:** Four reason categories:
1. Loyalty Card
2. Promo
3. Manager Decision
4. Other — requires mandatory free-text explanation (operator must type reason before submit allowed)

**Other field rules:**
- Appears only when "Other" is selected
- Free-text input, limited to ~500 characters (a few sentences)
- Field is mandatory — form cannot submit without it
- Logged in full in the Comp Admission Log

**Rationale:** The first three categories are self-explanatory and need no further detail. "Other" is an exception case — requiring a typed explanation creates an audit trail and discourages casual abuse of the comp system.

---

*Add new decisions below this line. Use the next sequential number.*
