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

## DEC-030 — Immutable asset_code Field on Venue Asset

**Date:** 2026-04-09
**Context:** Room layouts change and rooms can be renamed over time (e.g., Glory Hole rooms didn't exist 2 years ago). Historical records (Venue Session, Asset Status Log) must always point to the correct physical asset even after a rename.
**Decision:** Add `asset_code` (Data, unique, read-only after creation) to Venue Asset. Set once at creation and never changed. Format: `R001`–`R999` for rooms, `L001`–`L999` for lockers. The `asset_name` field remains the display name shown on POS and asset board and can be freely changed.
**Rationale:** Without an immutable identifier, renaming "Room 7" to "VIP Suite" would make historical records ambiguous. The asset_code provides a permanent reference that survives any renames or layout changes.

## DEC-031 — last_vacated_at and last_cleaned_at on Venue Asset

**Date:** 2026-04-09
**Context:** Operators need to see how long a room has been sitting Dirty on the asset board. Management needs to identify if a worker is leaving rooms dirty for the next shift to clean when they had time to clean them.
**Decision:** Add two timestamp fields to Venue Asset:
- `last_vacated_at` (Datetime, read-only) — set automatically when Occupied → Dirty. Asset board shows "Dirty since X hours."
- `last_cleaned_at` (Datetime, read-only) — set automatically when Dirty → Available. Shows how recently a room was turned over.

Analysis is powered by the existing Asset Status Log — every transition is already logged with operator and timestamp. Reports can query: "All rooms in Dirty state for >X minutes during Operator Y's shift" to identify performance issues.
**Rationale:** Operational visibility (how long is this room dirty?) and management accountability (is this operator cleaning rooms during their shift?). The Asset Status Log provides the historical data; the two fields on Venue Asset provide the live board display.

## DEC-032 — No POS Profile Link on Venue Session

**Date:** 2026-04-09
**Context:** Gemini suggested adding a POS Profile link to Venue Session to track which POS station created each session.
**Decision:** Not added. Hamilton is always single-terminal. POS Profile is already captured on Shift Record which is sufficient. No need to duplicate it on Venue Session.
**Rationale:** Adding a field Hamilton will never use adds schema noise. If a second terminal is ever added, this can be revisited.

## DEC-033 — Session Number Format: {day}-{month}-{year}---{sequence}

**Date:** 2026-04-09
**Context:** Staff need a short human-readable reference to look up specific sessions (e.g. "pull up session 9-4-2026---042") rather than long ERPNext document IDs.
**Decision:** Add `session_number` (Data, read-only, auto-generated) to Venue Session. Format: `{day}-{month}-{year}---{sequence}` with three dashes separating the date from the sequence. Example: `9-4-2026---001`. Sequence resets to 001 at midnight each day and increments continuously within the day. The sequence portion is displayed in bold in the UI — the stored value is plain text; bold formatting is applied by the frontend (asset board, receipts) on the digits after the `---`.
**Rationale:** Staff reference sessions by number during shifts and investigations. Daily reset keeps numbers short and human-readable. Three-dash separator makes the sequence visually distinct.

## DEC-034 — Do Not Duplicate Financial Amounts on Venue Session

**Date:** 2026-04-09
**Context:** ChatGPT suggested storing checkin_rate_gross, checkin_rate_net, and tax_amount directly on Venue Session for easier reporting.
**Decision:** Not added. All financial amounts live on the Sales Invoice which is already linked to Venue Session via the sales_invoice field. Reports query the Sales Invoice. Duplicating amounts on Venue Session risks data becoming out of sync if the invoice is amended or refunded.
**Rationale:** One number, one place, always accurate. The Sales Invoice is the accounting record of truth.

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

## DEC-017 — Non-Stacking Rule and Under 25 Trigger Both Require Custom Code

**Date:** 2026-04-09
**Context:** Three-AI review confirmed standard ERPNext Pricing Rules cannot enforce mutual exclusion or manual operator triggers.
**Decision:**
- Non-stacking (Under 25 cannot combine with Locker Special): requires custom server-side `validate` hook on Sales Invoice that detects both rules active and throws a plain-language error.
- Under 25 manual trigger: requires a custom POS button "Apply Under 25" — standard Pricing Rules auto-apply and cannot be conditionally triggered by operator after ID check.
**Rationale:** ERPNext Pricing Rule Priority controls order of application, not mutual exclusion. All three AI reviewers confirmed this. Custom validation is the only reliable approach.

---

## DEC-018 — HST-Inclusive Pricing Uses Company-Level Tax Template

**Date:** 2026-04-09
**Context:** Grok and ChatGPT flagged that Item Tax Template does not have "Include Tax in Rate" checkbox in v16 (open issue #51510 as of April 2026).
**Decision:** HST-inclusive pricing configured at Company level via Sales Taxes and Charges Template with "Included in Print Rate" flag set to 13% HST. Item Tax Template used only for item-level exemption overrides (0% for exempt retail items). Some custom JS may be needed for exact back-calculation on mixed admission + retail carts.
**Rationale:** Standard ERPNext v16 limitation. Company-level template is the correct workaround confirmed by two reviewers.

---

## DEC-019 — Hybrid Locking: Redis Advisory + MariaDB Row Lock + Version Field

**Date:** 2026-04-09
**Context:** All three AI reviewers identified asset assignment concurrency as the #1 production risk. Grok provided complete working implementation.
**Decision:** Three-layer locking on all Venue Asset status changes:
1. Redis advisory lock (fast pre-check, 15s TTL, UUID token, atomic Lua release)
2. MariaDB `FOR NO KEY UPDATE` row lock inside the Redis lock (strong DB integrity)
3. Optimistic `version` field on Venue Asset (catches any bypasses)
Lock sections must be minimal — validate + save only, no I/O inside lock.
Use `FOR NO KEY UPDATE` not `FOR UPDATE` in v16 (avoids blocking FK checks).
**Rationale:** Hamilton has 59 assets and multiple operators. Two operators assigning same asset simultaneously is a realistic scenario. Once asset status data becomes inconsistent in production it is expensive to fix. All three reviewers confirmed this is the #1 risk.

---

## DEC-020 — Paid-But-Unassigned Recovery State

**Date:** 2026-04-09
**Context:** All three reviewers flagged: if payment succeeds but asset assignment fails (network drop, operator closes tab), there is no defined recovery state.
**Decision:** Add `assignment_status` field (Select: Pending / Assigned / Failed, default Pending) to Venue Session. Venue Session is created at payment time with status Pending, then updated to Assigned when asset is confirmed. Add daily scheduled cleanup job that identifies sessions stuck in Pending for >15 minutes and flags them for operator review.
**Rationale:** Without a recovery state, paid admissions with no assigned asset create ghost sessions with no cleanup path.

---

## DEC-021 — Blind Cash Control Requires Multi-Layer Permissions

**Date:** 2026-04-09
**Context:** All three reviewers flagged that blocking POS Closing Entry alone is insufficient — operators can still see expected cash totals via Sales Register reports, list views, and API responses.
**Decision:** Blind cash control requires all of:
- Role Permission: Deny Create/Write on POS Closing Entry for Hamilton Operator
- Role Permission: Deny access to Sales Register report and any cash-total reports
- Frappe v16 field-level masking on sensitive cash fields visible to Operator role
- All whitelisted methods on Cash Drop page verify role server-side (never trust client)
**Rationale:** Defense in depth. A single permission setting is too brittle for a system specifically designed to prevent operators from seeing expected totals.

---

## DEC-022 — Three Roles: Operator, Manager, Admin

**Date:** 2026-04-09
**Context:** ChatGPT and Gemini flagged that two roles (Operator + Manager) is insufficient. Manager was defined as "reconciliation only" which is too narrow for real operations.
**Decision:** Three roles:
- **Hamilton Operator:** Day-to-day operations. POS, asset board, cash drops, shift start/close. No reconciliation, no settings, no POS Closing Entry.
- **Hamilton Manager:** Reconciliation screen, view-only on Cash Drop records, shift reports. Cannot change system settings or pricing.
- **Hamilton Admin:** System configuration. Hamilton Settings, asset master data, Item/pricing setup, role management. Not an operational role.
**Rationale:** Separates operational work (Operator), financial oversight (Manager), and system configuration (Admin) into clean boundaries.

---

## DEC-023 — Bulk "Mark All Clean" Action on Asset Board

**Date:** 2026-04-09
**Context:** Gemini flagged that manually clicking 59 assets clean every morning is operationally unworkable.
**Decision:** Add a "Mark All Clean" bulk action to the asset board that transitions all Dirty assets to Available in one tap. Requires operator confirmation. Logs each transition in Asset Status Log individually (not as a batch). Added to Phase 1 scope.
**Rationale:** Operational necessity. Morning shift would revolt at clicking 59 tiles individually.

---

## DEC-024 — board_corrections Changed to Child Table

**Date:** 2026-04-09
**Context:** ChatGPT and Grok flagged that free-text board_corrections on Shift Record is too loose for audit purposes.
**Decision:** Replace `board_corrections` (Text) on Shift Record with a child table `Hamilton Board Correction` containing: venue_asset (Link), old_status (Data), new_status (Data), reason (Text), operator (Link to User), timestamp (Datetime).
**Rationale:** Structured corrections are queryable, reportable, and attributable. Free text cannot be used for audit or investigation.

---

*Add new decisions below this line. Use the next sequential number.*

## DEC-025 — POS Uses Sales Invoice Mode (Not POS Invoice)

**Date:** 2026-04-09
**Context:** ERPNext v16 POS can create either POS Invoices (deferred, consolidated at shift close) or Sales Invoices (immediate, real-time accounting). ChatGPT and Grok flagged this as an unresolved question.
**Decision:** Hamilton uses "Sales Invoice in POS" mode. The POS Profile setting "Use Sales Invoice in POS" must be enabled. Every transaction creates a Sales Invoice immediately on submission.
**Rationale:** Asset assignment hook fires on Sales Invoice submission. Immediate creation is required — deferred POS Invoice mode would mean the asset assignment prompt never fires until shift close. All existing spec references to "Sales Invoice" are correct and unchanged.

---

## DEC-026 — Float Amount Corrected to $300, Configurable Per Venue

**Date:** 2026-04-09
**Context:** Float amount was previously recorded as $200 (spec example). Chris confirmed the actual Hamilton float.
**Decision:** Hamilton float is $300 per shift. Stored in Hamilton Settings DocType — not hardcoded. Each venue sets its own float amount independently.
**Rationale:** Float varies by venue and can change as business needs evolve. Configurable setting ensures no code change is needed when the amount changes.

---

## DEC-027 — Float Carryover: Operator Sets Float Aside, Drops Revenue Only

**Date:** 2026-04-09
**Context:** Needed to define how the $300 float is handled at shift end — does it get dropped with revenue or stay in the till?
**Decision:** Option B — operator physically counts out the $300 float and sets it aside for the next shift before doing their cash drop. Only cash above the float is dropped. The system_expected calculation for reconciliation must therefore be: total cash payments for the shift minus the float amount.
**Rationale:** This is how Hamilton actually operates. The float never goes into the safe — it transfers directly to the next shift. This keeps the drop math clean: drop = revenue only.

---

## DEC-028 — Tier Unavailable After Payment: No System Change Needed

**Date:** 2026-04-09
**Context:** Raised as a potential gap — what happens if a guest pays for a Deluxe room but all Deluxe rooms are Dirty when the operator goes to assign?
**Decision:** No new system workflow required. Operators check the asset board before ringing up a sale. If no Deluxe rooms are available the operator would not ring up a Deluxe admission. The rare race condition (room becomes Dirty between board check and assignment) is handled by server-side concurrency locking (DEC-019) — the asset simply won't appear as available in the assignment prompt.
**Rationale:** Operational procedure covers this naturally. Adding a complex "tier unavailable" recovery workflow would be over-engineering for Hamilton's single-operator environment.

---

## DEC-029 — Split Tender Accepted; Cash Portion Only Counts Toward Reconciliation

**Date:** 2026-04-09
**Context:** Hamilton accepts split payments (e.g., $20 cash + $21 card for a $41 room). Needed to define how this affects cash reconciliation math and asset assignment trigger.
**Decision:** Split tender is fully supported via standard ERPNext POS payment handling. Two rules:
1. Asset assignment triggers when the full transaction is confirmed in POS — regardless of payment mix.
2. For cash reconciliation, system_expected = sum of cash-mode payment amounts only on Sales Invoices for that shift period. Card portions are reconciled separately against the standalone terminal batch report.
**Rationale:** Standard ERPNext POS handles split tender natively. Card payments are never in the cash drawer so they must be excluded from cash reconciliation math.

---

*Add new decisions below this line. Use the next sequential number.*
