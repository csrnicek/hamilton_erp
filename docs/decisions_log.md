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
- `last_cleaned_at` (Datetime, read-only) — set automatically when Dirty → Available **OR when Out of Service → Available**. Shows how recently a room was turned over or returned from maintenance.

Analysis is powered by the existing Asset Status Log — every transition is already logged with operator and timestamp. Reports can query: "All rooms in Dirty state for >X minutes during Operator Y's shift" to identify performance issues.
**Rationale:** Operational visibility (how long is this room dirty?) and management accountability (is this operator cleaning rooms during their shift?). The Asset Status Log provides the historical data; the two fields on Venue Asset provide the live board display.

**Amendment 2026-04-10 (Phase 1 Task 8):** `last_cleaned_at` is also stamped on `Out of Service → Available` transitions via `return_asset_to_service`. Rationale: returning an asset from OOS is the end of a maintenance or repair cycle, functionally equivalent to a cleaning turnover for "how recently was this room serviced?" board display. Without this, an asset that went Available → OOS (plumbing) → Available would show a stale `last_cleaned_at` from before the outage, misrepresenting how recently the asset was touched. The semantic edge case (a "board correction" OOS followed by immediate return, where no physical work was done) is accepted as a minor overstatement — the Asset Status Log still records the full transition chain with operator and reason for anyone drilling into a specific asset's history. Flagged by code review during Task 8 implementation.

## DEC-032 — No POS Profile Link on Venue Session

**Date:** 2026-04-09
**Context:** Gemini suggested adding a POS Profile link to Venue Session to track which POS station created each session.
**Decision:** Not added. Hamilton is always single-terminal. POS Profile is already captured on Shift Record which is sufficient. No need to duplicate it on Venue Session.
**Rationale:** Adding a field Hamilton will never use adds schema noise. If a second terminal is ever added, this can be revisited.

## DEC-033 — Session Number Format: {day}-{month}-{year}---{sequence}

**Date:** 2026-04-09
**Context:** Staff need a short human-readable reference to look up specific sessions (e.g. "pull up session 9-4-2026---0042") rather than long ERPNext document IDs.
**Decision:** Add `session_number` (Data, read-only, auto-generated) to Venue Session. Format: `{day}-{month}-{year}---{sequence}` with three dashes separating the date from the sequence. Example: `9-4-2026---0001`. Sequence resets to 0001 at midnight each day and increments continuously within the day. The sequence portion is displayed in bold in the UI — the stored value is plain text; bold formatting is applied by the frontend (asset board, receipts) on the digits after the `---`.
**Rationale:** Staff reference sessions by number during shifts and investigations. Daily reset keeps numbers short and human-readable. Three-dash separator makes the sequence visually distinct.
**Addendum (2026-04-10, Task 11):** The trailing sequence was widened from 3 to 4 digits (`:03d` → `:04d`). The cold-Redis DB fallback uses a lexicographic `ORDER BY session_number DESC` that only matches numeric ordering while all sequences share the same width; with 3 digits, a hypothetical `---1000` row would have sorted before `---999` and broken the fallback. 4 digits raises the ceiling to 9999/day — well above any realistic single-day volume at Club Hamilton — and eliminates the sort bug permanently.

## DEC-034 — Do Not Duplicate Financial Amounts on Venue Session

**Date:** 2026-04-09
**Context:** ChatGPT suggested storing checkin_rate_gross, checkin_rate_net, and tax_amount directly on Venue Session for easier reporting.
**Decision:** Not added. All financial amounts live on the Sales Invoice which is already linked to Venue Session via the sales_invoice field. Reports query the Sales Invoice. Duplicating amounts on Venue Session risks data becoming out of sync if the invoice is amended or refunded.
**Rationale:** One number, one place, always accurate. The Sales Invoice is the accounting record of truth.

## DEC-034 — Do Not Duplicate Financial Amounts on Venue Session

**Date:** 2026-04-09
**Context:** ChatGPT suggested storing checkin_rate_gross, checkin_rate_net, and tax_amount directly on Venue Session for easier reporting.
**Decision:** Not added. All financial amounts live on the Sales Invoice which is already linked to Venue Session via the sales_invoice field. Reports query the Sales Invoice. Duplicating amounts on Venue Session risks data becoming out of sync if the invoice is amended or refunded.
**Rationale:** One number, one place, always accurate. The Sales Invoice is the accounting record of truth.

## DEC-035 — Do Not Store Payment Status Snapshot on Venue Session

**Date:** 2026-04-09
**Context:** ChatGPT suggested storing a payment_status_snapshot on Venue Session.
**Decision:** Not added. Same reasoning as DEC-034 — payment data lives on the linked Sales Invoice. Duplicating it risks sync issues on refunds or amendments.
**Rationale:** Sales Invoice is the single source of truth for all payment data.

## DEC-036 — No refund_status Field on Venue Session

**Date:** 2026-04-09
**Context:** ChatGPT suggested adding a refund_status field to Venue Session.
**Decision:** Not added. When a refund happens via POS Return, the session ends and the asset is released — this is already visible from the session status and the linked Sales Invoice. A separate refund_status field would duplicate information already captured elsewhere.
**Rationale:** Session status + Sales Invoice together tell the complete story. No duplication needed.

## DEC-037 — No sealed_by, witnessed_by, or bag_number on Cash Drop

**Date:** 2026-04-09
**Context:** ChatGPT suggested adding witnessed_by, sealed_by, and bag_number to Cash Drop for auditability.
**Decision:** Not added. Hamilton is single-operator — there is no witness. No numbered bags used. Envelope label content is TBD and will be addressed in Phase 3 when the label printer is implemented.
**Rationale:** Unnecessary fields for a single-operator venue. Label details deferred to Phase 3.

## DEC-038 — Operator Declares Both Cash and Card Totals at Shift Close

**Date:** 2026-04-09
**Context:** Operators need to be accountable for all payment streams, not just cash. At shift close, the operator should consciously acknowledge both cash drops and card terminal totals.
**Decision:** At shift close, the operator:
1. Sees a summary of their own declared cash drops for the shift (e.g. Drop 1: $300, Drop 2: $300) — their own numbers only, never system expected totals.
2. Enters their final cash drop amount.
3. Enters the card terminal batch total (read directly from the standalone terminal).

Two new fields added to Shift Record:
- `operator_declared_card_total` (Currency) — what the operator reads from the terminal and enters manually.
- `system_expected_card_total` (Currency) — auto-calculated from card-mode Sales Invoices for the shift.

Card reconciliation is 2-way (operator declared vs system expected). Cash reconciliation remains 3-way (system expected vs operator declared vs manager physical count).

The shift close screen shows the operator their OWN declared drop amounts as a running total. It never shows the system's expected cash total — the blind model is preserved.
**Rationale:** Forces operator awareness of all incoming transactions. Operator cannot claim ignorance of card totals. Cash blind model is maintained.

## DEC-039 — Add variance_amount to Cash Reconciliation

**Date:** 2026-04-09
**Context:** The reconciliation screen shows three numbers (system expected, operator declared, manager actual). The manager has to do mental math to calculate the difference. A mockup confirmed that showing the variance as a single calculated number (e.g. -$70.00 in red) makes the result immediately obvious.
**Decision:** Add `variance_amount` (Currency, read-only, auto-calculated) to Cash Reconciliation. Value = manager_actual_count minus system_expected. Negative = short, positive = over, zero = clean. Only revealed after manager submits their blind count — never shown before submission. Visible on the reconciliation screen, the Cash Reconciliation record, and any management reports.
**Rationale:** Eliminates mental math during investigations. The -$263 in red jumps out instantly vs reading three separate numbers and calculating the difference.

## DEC-040 — Post-Variance Workflow Deferred to Phase 3

**Date:** 2026-04-09
**Context:** After a manager flags a variance (theft, mis-declared, or over), what happens next? Investigation process, notifications, escalation path — these were not defined.
**Decision:** Deferred to Phase 3 when the Manager Reconciliation screen is built. The screen will display the variance and flag; the investigation workflow will be defined then based on operational input from Hamilton.
**Rationale:** Getting the data model and display right is Phase 0-3 work. The investigation process is an operational procedure that is best defined once the screen is in front of real managers.

## DEC-041 — Add resolved_by and resolution_status to Cash Reconciliation Now

**Date:** 2026-04-09
**Context:** After a variance is flagged, the investigation workflow is deferred to Phase 3. However the schema fields needed to track resolution should be added now.
**Decision:** Add two fields to Cash Reconciliation, both null until Phase 3 workflow is built:
- `resolved_by` (Link → User) — manager who signs off that the investigation is complete
- `resolution_status` (Select: Open / Resolved / Dismissed / Escalated) — outcome of the investigation
**Rationale:** Per DEC-007, deferred ≠ absent from schema. Adding now takes 30 seconds. Adding later requires a migration script on live data. Zero cost now, real cost later.

## DEC-042 — Direct Shift Record Link on Cash Reconciliation

**Date:** 2026-04-09
**Context:** Cash Reconciliation already reaches Shift Record via Cash Drop (two hops). ChatGPT suggested a direct link.
**Decision:** Add `shift_record` (Link → Shift Record) directly on Cash Reconciliation. Auto-populated when reconciliation is created. Developer implementation decision — no operational impact.
**Rationale:** Faster report queries. Zero schema cost now. Would require a migration patch if added later.

## DEC-043 — Skip opening_float_declared_by on Shift Record

**Date:** 2026-04-09
**Context:** ChatGPT suggested tracking who physically counted the float at shift start.
**Decision:** Not added. At Hamilton, the operator on shift IS always the person who counts the float. The existing `operator` field on Shift Record already captures this. Redundant at a single-operator venue.
**Rationale:** Adds no information at Hamilton. Can be revisited if a venue ever has multiple staff counting floats separately.

## DEC-044 — Add reconciliation_status to Shift Record

**Date:** 2026-04-09
**Context:** A manager needs to see at a glance whether all cash drops from a shift have been reconciled.
**Decision:** Add `reconciliation_status` (Select: Pending / Partially Reconciled / Fully Reconciled) to Shift Record. Auto-updated by the system each time a Cash Reconciliation is submitted for a drop in that shift.
**Rationale:** Operational visibility — manager can scan the shift list and immediately see which shifts still have unreconciled envelopes. Easier to add now than later.

## DEC-045 — Skip approved_by on Comp Admission Log

**Date:** 2026-04-09
**Context:** ChatGPT suggested adding approved_by to track who authorised a comp admission.
**Decision:** Not added. The reason is already fully captured by existing fields: reason_category (Loyalty Card / Promo / Manager Decision / Other) and reason_note (mandatory free text for Other). At Hamilton, the operator on shift IS the authoriser. No separate approval field needed.
**Rationale:** Redundant at a single-operator venue. Existing reason fields already explain why the admission was free.

## DEC-046 — Add grace_minutes, assignment_timeout_minutes, printer_label_template_name to Hamilton Settings

**Date:** 2026-04-09
**Context:** Three configurable system constants needed for overtime detection, session cleanup, and label printing.
**Decision:** Add to Hamilton Settings DocType:
- `grace_minutes` (Int, default 15) — extra minutes after stay duration before overtime indicator fires on asset board
- `assignment_timeout_minutes` (Int, default 15) — minutes before a paid-but-unassigned session is flagged by cleanup job
- `printer_label_template_name` (Data) — label template name for Brother QL-820NWB
**Rationale:** All three are operational constants that will need tuning. Storing them as configurable settings means no code change required when values need adjusting.

## DEC-047 — Skip hamilton_pricing_rule_override on Item

**Date:** 2026-04-09
**Context:** Grok suggested adding hamilton_pricing_rule_override to Item to support the Under 25 discount trigger.
**Decision:** Not added. The existing hamilton_is_admission field already identifies which items are admission items. The Under 25 custom POS button applies 50% to all items where hamilton_is_admission = 1. No additional flag needed.
**Rationale:** hamilton_is_admission is sufficient. Adding a duplicate eligibility flag creates maintenance overhead with no benefit.

## DEC-048 — Under 25 Discount Rules: Admission Only, One Per Transaction

**Date:** 2026-04-09
**Context:** Clarifying exactly what the Under 25 discount applies to and how abuse is prevented.
**Decision:** Two explicit rules:

**Rule 1 — Admission items only:**
The Under 25 discount applies ONLY to items where `hamilton_is_admission = 1` (rooms and lockers). Retail items (drinks, snacks, towels, etc.) are always full price regardless of guest age. The custom "Apply Under 25" POS button must only discount admission line items in the cart.

**Rule 2 — One admission per transaction:**
A POS cart can contain a maximum of ONE admission item (enforced by spec §4.3 and server-side validation). This prevents a single Under 25 transaction being used to admit multiple people at 50% off. If an operator attempts to add a second admission item, the system blocks it.

**Rationale:** Rule 1 confirmed by Chris — guest buys a Coke and a locker, only the locker is discounted. Rule 2 confirmed by Chris — prevents abuse where one 23-year-old's discount is used to admit multiple guests.
**Rationale:** Both rules must be enforced server-side, not just in the UI.

## DEC-049 — system_expected Calculation Formula

**Date:** 2026-04-09
**Context:** The reconciliation screen needs to calculate what cash should be in each drop envelope.
**Decision:** system_expected for any drop = sum of cash-mode payments on Sales Invoices during that drop's time period. The float is never included in this calculation. The float is a constant that starts in the till, stays in the till, and is confirmed separately at shift start and end.
**Example:** Shift has $1,050 cash sales. Drop 1 at 2pm covers $400 of sales → system_expected = $400. Final drop covers $650 of sales → system_expected = $650. Float of $300 remains in till — never dropped.
**Rationale:** Confirmed by Chris. Clean, auditable, deterministic.

---

## DEC-050 — Operator Confirms Float at Both Shift Start and Shift End

**Date:** 2026-04-09
**Context:** The float must be accounted for at both ends of a shift to ensure it wasn't taken or lost during the shift.
**Decision:** Two float confirmation steps:
1. **Shift Start:** Operator counts the float and enters actual amount. System compares to expected $300. Variance logged in `float_actual` / `float_variance` on Shift Record.
2. **Shift End:** After final cash drop, operator counts the remaining float and confirms it equals $300. Amount entered in `closing_float_actual`. Variance logged in `closing_float_variance`. This float is then left in the till for the next operator.

New fields added to Shift Record: `closing_float_actual` (Currency), `closing_float_variance` (Currency).
**Rationale:** If $300 goes in at shift start and $285 comes out at shift end, something happened during the shift. Both checks together create a complete float accountability chain.

## DEC-051 — Refund Auto-Releases Asset (Occupied → Dirty)

**Date:** 2026-04-09
**Context:** When a guest gets a full refund after being assigned a room, the room must be released automatically. Nothing currently handles this.
**Decision:** When a POS Return (refund) is submitted against a Sales Invoice that has a linked Venue Session, the system must automatically:
1. Move the asset from Occupied → Dirty (needs cleaning)
2. Mark the Venue Session as Completed with vacate_method = "Refund"
3. Log the transition in Asset Status Log with reason "Refund processed"
Implementation: doc_events hook on Sales Invoice `on_cancel` or POS Return `on_submit` that checks for a linked hamilton_venue_session and triggers the release.
**Rationale:** Without this, a refunded guest could theoretically still occupy a room in the system while physically gone, and the room would never be cleaned or re-assigned.

## DEC-052 — Comp Admissions Do Not Affect Cash Totals

**Date:** 2026-04-09
**Context:** Comp admissions ($0 transactions) must not inflate or distort the cash reconciliation totals.
**Decision:** No special handling required. Comp admissions create a Sales Invoice with $0 cash payment. The system_expected formula (sum of cash-mode payments) naturally results in $0 contribution from comp invoices. Comps are invisible to cash reconciliation by design.
**Rationale:** The formula already handles this correctly. A $0 payment adds $0 to the expected total. No additional code needed.

## DEC-053 — Comp Admission Log: reason_note 500-char Limit Needs Controller

**Date:** 2026-04-09
**Context:** DEC-016 specifies reason_note is mandatory when reason_category = Other, max 500 characters. The JSON has max_length: 500 set on the Text field, but Frappe v16 does NOT enforce max_length on Text fieldtype (only on Data fieldtype).
**Decision:** The mandatory condition is correctly enforced via mandatory_depends_on. The 500-char limit must be enforced server-side in the Comp Admission Log controller validate() method in Phase 2.
**Implementation note:** Add to controller: if self.reason_category == "Other" and self.reason_note and len(self.reason_note) > 500: frappe.throw(_("Reason note must be 500 characters or fewer."))
**Rationale:** Phase 0 blocker-free. Controller work deferred to Phase 2.

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

**Date:** 2026-04-09 (revised 2026-04-10)
**Context:** All three AI reviewers identified asset assignment concurrency as the #1 production risk. Grok provided complete working implementation.
**Decision:** Three-layer locking on all Venue Asset status changes:
1. Redis advisory lock (fast pre-check, 15s TTL, UUID token, atomic Lua release)
2. MariaDB `FOR UPDATE` row lock inside the Redis lock (strong DB integrity)
3. Optimistic `version` field on Venue Asset (catches any bypasses)

Lock sections must be minimal — validate + save only, no I/O inside lock.

**SQL lock syntax:** Use `FOR UPDATE` — this is the MariaDB row-level exclusive lock. Do **not** use `FOR NO KEY UPDATE`; that is PostgreSQL-only syntax and will error in MariaDB (Frappe's database). See `coding_standards.md` §2.11 for the correct code pattern. FK-child-blocking is mitigated by the short lock window (Redis gates entry to this section so contention is milliseconds, not seconds).

**Revision note (2026-04-10):** Original decision said "FOR NO KEY UPDATE" — that was a carry-over from a PostgreSQL draft and was incorrect. Corrected to `FOR UPDATE` before any Phase 1 locking code was written.
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

## DEC-054 — Mark All Clean Bulk Action: Rules, Scope, and Audit Flag

**Date:** 2026-04-10
**Context:** DEC-023 added a "Mark All Clean" bulk action to the Asset Board for Phase 1 but left five operational details unresolved: who can press it, scope, confirmation UX, concurrency strategy, and whether it could defeat the audit intent of DEC-031 (`last_vacated_at` / `last_cleaned_at` + Asset Status Log being used to detect operators who leave rooms dirty).
**Decision:**

1. **Permission:** Hamilton Operator role can trigger the bulk action. Morning open is the primary use case — requiring a manager tap at 9am defeats the purpose.
2. **Scope:** Two separate buttons on the Asset Board — "Mark All Dirty Rooms Clean" and "Mark All Dirty Lockers Clean". Rooms and lockers have different cleaning workflows and must not be bulk-cleared together.
3. **Confirmation dialog:** Shows the list of assets about to be marked clean (asset_code + asset_name) plus a Confirm / Cancel pair. Cheap, catches mistakes before they happen.
4. **Concurrency:** Implemented as a loop over the single-asset `mark_clean` whitelisted method. Assets are sorted by `name` before locking (§13.4 deadlock-prevention rule). Each asset goes through the full three-layer lock (Redis advisory + MariaDB `FOR UPDATE` + version field). Failures (e.g. an asset was just re-occupied between the confirmation and the action) are reported at the end without aborting the batch — the Asset Board then refreshes via the standard realtime channel.
5. **Audit hardening:** Every `Asset Status Log` entry created by the bulk action sets `reason = "Bulk Mark Clean — morning reset"` (or similar distinguishing string). Individual `mark_clean` calls from a single tile tap have `reason = null` (no reason required for Dirty → Available). Reports can then slice cleanings by reason to compare individual physical cleanings vs bulk operations. This addresses the tension with DEC-031: the bulk button is permitted but always leaves a machine-readable trail so management can detect overuse without changing operator permissions.

**Rationale:** Operationally, morning-open with 59 assets and zero workers is the reality — the button must exist and must be fast. DEC-031's audit intent is preserved because every bulk transition is still logged individually with a distinguishing reason string. Managers retain full visibility without a permission fence that would force them into the building every morning.

---

## DEC-055 — Phase 1 Scope Additions from 3-AI Review Follow-Up

**Date:** 2026-04-10
**Context:** A second pass through the Phase 0 codebase using ChatGPT, Gemini, and Grok surfaced four findings that affect Phase 1 scope. ChatGPT's findings were all accurate. Grok and Gemini produced a number of false alarms (reviewed stale repo state, were wrong about Frappe file layout, and were wrong about valid `naming_rule` values) whose valid findings were already covered by the existing Phase 1 plan. The four items below are the surviving real issues that must be handled.
**Decision:**

1. **Walk-in Customer must exist before any Venue Session can be created.** The `Venue Session` DocType sets `customer` default to `"Walk-in"`, but no Customer document with that name is shipped by ERPNext or created by Phase 0. Without one, every session creation in Phase 1 will fail with a link-validation error. The Phase 1 seed migration patch (scoped in DEC-054 / Q6) must also create a Customer named `"Walk-in"` if it does not exist, with a minimal customer_group and territory per ERPNext defaults. Idempotent — skip if already present.

2. **Lock down system-owned fields on Venue Session as each controller method lands.** These fields must be operator-writable only via server code, not directly in the Frappe form: `sales_invoice`, `admission_item`, `operator_checkin`, `shift_record`, `pricing_rule_applied`, `under_25_applied`, `comp_flag`. As Phase 1 implements each whitelisted method that writes one of these, set `read_only: 1` on the field in `venue_session.json` in the same commit. Prevents operator tampering in the UI while allowing server-side flows (Phase 2 POS integration, Phase 3 shift flows) to set them.

3. **Hamilton Settings singleton must be seeded with defaults.** The seed migration patch from DEC-054 must also create the `Hamilton Settings` single-doctype record if it doesn't already exist, with `float_amount = 300`, `default_stay_duration_minutes = 360`, `grace_minutes = 15`, `assignment_timeout_minutes = 15`. Without this, Phase 1 code that reads these values via `frappe.db.get_single_value("Hamilton Settings", ...)` will get None and the overtime/cleanup logic will silently do nothing.

4. **Hamilton Workspace permission tightening — quick fix applied 2026-04-10.** The Phase 0 workspace JSON had `"public": 1` and empty `"roles": []`, which exposed the workspace to every user on the site. Fixed immediately on 2026-04-10: set `"public": 0` and added `"roles": [Hamilton Operator, Hamilton Manager, Hamilton Admin]`. Committed separately from this decision. Workspace is now visible only to the three Hamilton roles.

**Rationale:** Items 1 and 3 are gap-fillers — the DocType defaults assume records that Phase 0 never created, and any Phase 1 code that touches them would fail on a fresh install. Item 2 closes a blind spot where the form UI would let operators overwrite financial and audit-critical links that are supposed to be server-managed. Item 4 was a straight configuration bug in the Phase 0 workspace export. All four are either true Phase 1 scope additions (1, 2, 3) or quick fixes that should not wait for the full Phase 1 rollout (4). Grok and Gemini review findings that reviewed stale repo state or were wrong about Frappe internals are explicitly not recorded — ChatGPT's findings were the only accurate ones in this second pass.

---

## DEC-056 — Session Number Prefix Pinned to session_start, Not Retry Wall-Clock

**Date:** 2026-04-10
**Context:** During the Task 11 3-AI review, reviewers flagged a midnight-boundary race in `lifecycle._create_session`. The original implementation captured `session_start = frappe.utils.now_datetime()` fresh inside each retry attempt, and relied on `VenueSession.before_insert` to auto-populate `session_number` via `_next_session_number()` — which in turn read `frappe.utils.nowdate()` on every call. If a collision retry straddled midnight at a 24-hour venue, the retry would derive a new-day date prefix while the new `session_start` timestamp also advanced to the new day — leaving the operator's actual check-in moment ambiguous and potentially emitting rows whose `session_number` prefix did not match the day the session was physically entered. Club Hamilton is open overnight Friday and Saturday (and overnight hours may expand), so this is a real operational scenario, not a theoretical race.
**Decision:**

1. **`session_start` is captured ONCE at the top of `lifecycle._create_session`**, before the retry loop begins. All retry attempts reuse the same `session_start` timestamp — the operator's actual check-in moment, not the wall-clock at the time of any particular retry.

2. **`session_number` is generated explicitly in `_create_session`**, not inside `VenueSession.before_insert`, using a new keyword argument `_next_session_number(for_date=start_date)`. `start_date` is derived from `session_start.date()` ONCE, outside the retry loop, and passed unchanged to every retry attempt. `_next_session_number` uses the passed date to build the prefix (e.g. `15-3-2099`), never falling back to `nowdate()` when `for_date` is provided.

3. **`VenueSession.before_insert` retains its fallback generator path** for callers that legitimately omit `session_number` (historic rows, direct-insert tests, future bulk import). It only runs when `self.session_number` is empty, so the explicit value set by `_create_session` bypasses it cleanly.

4. **`_next_session_number()` with no arguments continues to default to today's date via `nowdate()`.** This is the only call path that reads wall-clock. All retry-sensitive callers must pass `for_date=` explicitly.

5. **The test `test_midnight_boundary_session_number_matches_session_start`** (in `test_lifecycle.py::TestCreateSessionMidnightBoundary`) enforces the contract: it patches `hamilton_erp.lifecycle.now_datetime` to return day X on the first call and day Y on any later call, pre-seeds a colliding decoy row under day X's prefix, and asserts that both retry attempts receive `for_date=day_X.date()` and that the final session's `session_number` prefix and `session_start.date()` both equal day X.

**Rationale:** The simpler fix — "just capture session_start once" — is only half the answer. The dangerous half is the session_number prefix, because the prefix encodes the business date and is what operators, managers, and reports group by. An operator who checks a guest in at 23:59:30 on Saturday expects that session's number to read `Saturday-...`, not `Sunday-...`, regardless of how many insert retries the backend burned crossing midnight. Pinning the prefix to `session_start.date()` makes the business-day boundary explicit and immutable from the moment the operator taps the button. The implementation cost is one kwarg on `_next_session_number` and one extra line in `_create_session`; the safety guarantee is absolute and testable end-to-end. Alternative approaches (e.g. "just generate once and reuse") were rejected because retries legitimately need a FRESH sequence number (the old one collided) — only the DATE must stay pinned, not the full session_number.

---

## DEC-057 — Test-Class Isolation: tearDownClass Must Scrub DB + Redis When Committing

**Date:** 2026-04-10
**Context:** During Task 14 (Asset Board API), a new test module `hamilton_erp/test_api_phase1.py` was added to exercise `get_asset_board_data` and the bulk Mark-All-Clean endpoints. These tests create real `Venue Asset` and `Venue Session` records and must `frappe.db.commit()` so the API under test can read them via a fresh query path. After the commit, a subsequent run of `test_lifecycle.TestSessionNumberGenerator` failed with `AssertionError: '11-4-2026---0095' != '11-4-2026---0006'` — the generator's "first call of the day returns 0001" invariant was destroyed because test_api_phase1 had left ~90 committed `Venue Session` rows bearing today's prefix, and the Redis session-sequence counter `hamilton:session_seq:{d-m-y}` was also still warm from those commits. Frappe's `IntegrationTestCase` auto-rollback does not cover data already committed, and cross-module test ordering is non-deterministic, so any test class that commits bleeds into every test class that runs after it in the same bench process.

Package-root test modules (modules that live in `hamilton_erp/test_*.py` rather than under a doctype folder) compound the problem: they cannot use `IGNORE_TEST_RECORD_DEPENDENCIES`. Frappe v16 raises `NotImplementedError: IGNORE_TEST_RECORD_DEPENDENCIES is only implement for test modules within a doctype folder` because the flag relies on `cls.doctype`, which is only derivable for doctype-scoped tests. The good news is the auto-seed cascade is skipped entirely for package-root modules, so the flag is unnecessary there — but the test author has to know this, and nothing in Frappe's docs warns about the side effect on committed state.

**Decision:**

1. **Any `IntegrationTestCase` subclass that calls `frappe.db.commit()` MUST define `tearDownClass` with the full scrub triple**, in this exact order:

   ```python
   @classmethod
   def tearDownClass(cls):
       frappe.db.delete("Venue Session")
       frappe.db.delete("Venue Asset")
       year, month, day = frappe.utils.nowdate().split("-")
       prefix = f"{int(day)}-{int(month)}-{int(year)}"
       frappe.cache().delete(f"hamilton:session_seq:{prefix}")
       frappe.db.commit()
       super().tearDownClass()
   ```

   Delete Venue Session FIRST (it has a FK-style link to Venue Asset via `current_session` round-trip), then Venue Asset, then flush the Redis session counter for today's prefix, then `commit()` so the scrub persists, then `super().tearDownClass()`. Missing any step leaves the next test class in a dirty state.

2. **The Redis flush is load-bearing, not decorative.** `_next_session_number()` has a cold-Redis fallback that queries the max existing `session_number` for today's prefix from MariaDB and returns `max + 1`. If the DB is scrubbed but Redis still holds the high-water counter, the next test class's first session will be numbered `{prefix}---{high_water + 1}` instead of `{prefix}---0001`. Both stores must be cleaned together.

3. **`setUpClass` should also scrub the same triple.** `tearDownClass` handles the common case (normal test exit), but a prior run that crashed mid-test leaves uncommitted scrubs undone. Running the scrub at the top of `setUpClass` makes each test class self-healing against bench-process corpse state from previous runs. The cost is negligible (~5 ms for an empty DELETE) compared to the debugging cost of a leaked row.

4. **Package-root test modules (`hamilton_erp/test_*.py`) MUST NOT set `IGNORE_TEST_RECORD_DEPENDENCIES`.** Frappe v16 raises `NotImplementedError` because the flag requires `cls.doctype`, which package-root modules do not define. These modules skip the auto-seed cascade entirely regardless (no `cls.doctype` → no dependency graph to walk), so the flag is unnecessary. Add a comment at the top of every package-root test module noting this, so future authors do not add it back reflexively.

5. **Doctype-scoped test modules (`hamilton_erp/hamilton_erp/doctype/*/test_*.py`) SHOULD continue to set `IGNORE_TEST_RECORD_DEPENDENCIES = True`** at module scope. This is unchanged — they still need the flag to avoid the broken Phase 0 stub cascade. This decision is only about package-root modules and about committed-state scrub.

6. **Code review must reject any new `IntegrationTestCase` subclass that commits without both the `tearDownClass` scrub AND the `setUpClass` scrub**, the same way code review rejects I/O inside a lock body (coding_standards.md §13). Treat this as a hard rule, not a suggestion — the failure mode (non-deterministic cross-module test pollution) is exactly the kind of flaky-test problem that destroys confidence in the suite over time.

**Rationale:** Three alternatives were considered and rejected. **(a) "Just don't commit in tests"** — impossible for Task 14 because `get_asset_board_data` is tested through `frappe.call`, which executes in a fresh request context that cannot see an uncommitted transaction from the test. **(b) "Run each test module against a fresh site"** — would cost minutes per run and break the developer workflow where Chris runs `/run-tests` and expects sub-minute feedback. **(c) "Mock the lifecycle layer so tests don't need real data"** — defeats the purpose of an integration test and would miss exactly the kind of cross-layer race that DEC-056 just fixed.

The scrub triple is cheap (one DELETE, one DELETE, one Redis DEL), deterministic (no dependency on test ordering), and self-documenting (any new test author reading the tearDownClass can see exactly what state their test owns). It also slots cleanly into the existing `IntegrationTestCase` lifecycle without requiring any Frappe framework changes. The rule is simple enough to enforce in review without needing a linter: "does this test class call `commit()`? If yes, does it have the scrub triple in both setUpClass and tearDownClass? If no to either, reject."

This decision is recorded now specifically because the bug it prevents is invisible until a second committing test class exists in the same bench process — which is exactly what happens as Phase 1 adds more API-surface integration tests. Waiting for the next cross-module failure to re-learn the rule would cost hours of bisecting phantom test failures each time.

---

## DEC-058 — HTTP Verb Allowlist on Whitelisted Reads: Decorator and Caller MUST Match

**Date:** 2026-04-11
**Context:** On 2026-04-11 Chris reported the Asset Board returning 403 "Not permitted" in both Chrome and Safari on fresh sessions. Curl tests against `/api/method/hamilton_erp.api.get_asset_board_data` consistently returned 200 with 59 assets, and every Python test in `test_api_phase1.py` was green. The bug was invisible for weeks because:

1. `api.py:51` decorates `get_asset_board_data` with `@frappe.whitelist(methods=["GET"])`.
2. `hamilton_erp/page/asset_board/asset_board.js` called `frappe.call({method: "hamilton_erp.api.get_asset_board_data", freeze: true, freeze_message: ...})` with no `type` parameter. The `frappe.call` client helper defaults to **POST** when `type` is omitted.
3. `frappe.handler.is_valid_http_method` (invoked inside `execute_cmd` on every `/api/method/*` request) reads `frappe.local.request.method` and rejects anything not in the `@whitelist(methods=[...])` list by raising `frappe.PermissionError("Not permitted")`.
4. Every `test_api_phase1.py` case invoked `api.get_asset_board_data()` as a direct Python import, bypassing `frappe.handler` entirely. The verb gate was never exercised in the test suite.
5. `curl` defaults to GET, so manual curl verification *always* succeeded — masking the bug every time it was checked.

The Asset Board page had therefore **never successfully rendered in a browser session** since its first commit (`7740be9 feat(page): Asset Board scaffold at /app/asset-board`). Every reported sighting of "it worked" was either a curl probe, a realtime update, or a cached screenshot.

**Decision:**

1. **Every `@frappe.whitelist(methods=[...])` decorator MUST be matched by an explicit `type: "<VERB>"` in every `frappe.call` caller.** Read endpoints (`methods=["GET"]`) require `type: "GET"`. Write endpoints (`methods=["POST"]`) require `type: "POST"` or may rely on `frappe.call`'s POST default (but explicit is preferred and reviewers should not flag it as noise). Do NOT omit the allowlist and rely on `frappe.call`'s default — the default is framework-defined behavior that can shift between Frappe versions and hides the caller's intent from reviewers.

2. **Every new or modified whitelisted endpoint MUST be paired with a `TestAssetBoardHTTPVerb`-style test class** that runs the endpoint through `frappe.handler.execute_cmd` with a spoofed `frappe.local.request.method`. One test per allowed verb asserting success, plus one test per **disallowed** verb asserting `frappe.PermissionError`. Direct Python import of the endpoint function is NOT sufficient — it bypasses the exact layer where the bug lives. The `_run_execute_cmd_with_verb` helper in `test_api_phase1.py::TestAssetBoardHTTPVerb` is the reference implementation.

3. **Code review MUST reject any PR that adds or edits `@frappe.whitelist(methods=[...])` without also adding/updating the HTTP-verb pin test.** Treat this as a hard rule, the same way DEC-057 mandates the scrub triple for committing tests. The cost of the test is ~5 lines per verb; the cost of the bug it prevents is Chris losing hours to "curl works, browser doesn't."

4. **Curl verification of whitelisted endpoints MUST be done with an explicit `-X POST` or `-X GET` flag that matches the browser's actual request verb.** A bare `curl /api/method/...` uses GET and can silently mask verb-mismatch bugs. If the endpoint is POST-only, curl verification should send POST.

5. **The `methods=[...]` kwarg is not optional on new endpoints.** Frappe's default (if omitted) is `["GET", "POST", "PUT", "DELETE"]` — every verb is allowed, which defeats the purpose of the guard. Every new `@frappe.whitelist` in `hamilton_erp/` MUST specify `methods=` explicitly, matching the actual semantics of the endpoint (read vs write).

**Rationale:** The bug took hours to diagnose because it looked like a security/session issue (403 in browser, 200 in curl). The real cause was two lines of code in two different files diverging on an implicit default. The fix is one `type: "GET"` in the JS caller (`hamilton_erp/page/asset_board/asset_board.js`), but the preventative structure is what this decision codifies: (a) explicit verbs on both sides, (b) tests that exercise the exact handler layer where the gate runs, (c) curl verification that matches the browser's actual verb, (d) decorator allowlists are mandatory, not optional.

An alternative — relaxing the decorator to `methods=["GET", "POST"]` — was rejected. The decorator is not the bug; it's the only defense against a POS operator triggering a read endpoint with unexpected side effects via browser-console POST. Keep the gate; match the caller.

This bug also demonstrates why "curl says it works" is not equivalent to "the browser says it works." Curl and the browser use different verb defaults (GET vs POST for `frappe.call`), different cookie handling, and different CSRF expectations. Future debugging of "works in curl, fails in browser" symptoms should jump directly to verb comparison before considering session/CSRF/cache explanations.

---

## DEC-059 — Dedicated Test Site (`hamilton-unit-test.localhost`): Rationale and Bootstrap Procedure

**Date:** 2026-04-11
**Context:** Through Tasks 1–13 the entire test suite ran against `hamilton-test.localhost` — the same site Chris used for manual browser testing. Test teardowns wipe roles, defaults, and User records, which corrupted the dev browser state in three reproducible ways after every `bench run-tests` invocation:

1. `tabDefaultValue.setup_complete` default flipped back to 0 → infinite `/app/setup-wizard` redirect loop on the next browser request. (Later discovered the real source is `tabInstalled Application.is_setup_complete` — see DEC-060.)
2. The `Hamilton Operator` role got stripped from `Administrator` → Asset Board returned 403 "Not permitted" on `get_asset_board_data`.
3. All 59 `Venue Asset` rows got deleted → Asset Board rendered an empty grid.

The interim fix was `hamilton_erp/test_helpers.py::restore_dev_state()`, called from every test module's `tearDownModule`. This worked but was fragile: any test author who forgot the `tearDownModule` call left the dev site broken for the rest of the session, and the heal itself took ~200ms per module which was noise in fast TDD loops.

**Decision:**

1. **`hamilton-unit-test.localhost` is the authoritative test site.** All `bench run-tests` invocations, including the `/run-tests` slash command, MUST point at this site. The slash commands in `.claude/commands/run-tests.md` and friends were repointed on 2026-04-11 (commit `0cf1fb1 fix(commands): repoint all remaining commands to dedicated test site`).

2. **`hamilton-test.localhost` is the dev browser site and is NEVER touched by the test runner.** Running tests here is a CLAUDE.md §Testing Rules violation — the top-of-file WARNING in `docs/testing_checklist.md` pins this. If a future contributor accidentally runs `bench --site hamilton-test.localhost run-tests`, recovery is a full `/debug-env` + `restore_dev_state()` + Redis flush + browser hard-refresh.

3. **`restore_dev_state()` is retained as a defense-in-depth heal** for the case where Step 2 is violated despite the rules. It is still called from every test module's `tearDownModule` per the commit history. On `hamilton-unit-test.localhost` it is a no-op in practice (tests wiping a dedicated test site is fine — the heal is just cheap insurance for the cross-site case).

4. **Bootstrap procedure for a fresh `hamilton-unit-test.localhost` site** is a 4-step sequence that MUST be run in order. A fresh `bench new-site` + `install-app hamilton_erp` + `set-config allow_tests true` does NOT leave the site in a state where the suite passes:

   a. **`bench --site hamilton-unit-test.localhost migrate`** — fires the `after_migrate` hook (`hamilton_erp.setup.install.ensure_setup_complete`) which heals `tabInstalled Application.is_setup_complete` for `frappe` and `erpnext`. This is DEC-060's hook path.

   b. **ERPNext `setup_complete()` with a minimal payload** — `language=English, country=Canada, timezone=America/Toronto, currency=CAD, company_name="Club Hamilton", full_name="Administrator", email="admin@example.com"`. This creates the "All Customer Groups" and "All Territories" baseline records that the Walk-in customer depends on. Without this step, `seed_hamilton_env.execute()` fails silently when trying to create the Walk-in customer because the required parent Customer Group and Territory don't exist.

   c. **`seed_hamilton_env.execute()`** — creates the 59 Venue Assets (26 rooms + 33 lockers), the Walk-in customer, and the Hamilton Settings singleton with defaults. Idempotent per DEC-054.

   d. **`hamilton_erp.test_helpers.restore_dev_state()`** — assigns the `Hamilton Operator` role to `Administrator`. The test suite assumes Administrator has this role; most of the Phase 1 tests will fail with permission errors otherwise.

   Steps b–d MUST be wrapped in `frappe.flags.in_test = False` + `frappe.db.commit()` so the setup wizard completion sticks — the test runner otherwise rolls them back.

5. **`bench execute hamilton_erp.test_helpers.restore_dev_state` does NOT work** — `bench execute`'s eval scope does not auto-import the app package, and the call fails with `NameError: hamilton_erp is not defined`. Use `bench console <<'PY' ... PY` with explicit `from hamilton_erp.test_helpers import restore_dev_state` instead.

**Rationale:** Dev/test site sharing was always a latent bug. It became an active bug in Tasks 13–16 when the test count and committing-test-class count both grew enough that a single `bench run-tests` run reliably corrupted the dev browser. The separate-sites approach is the Frappe community's standard pattern (every upstream Frappe app splits dev and test sites), and the migration cost was one day of slash command updates plus the bootstrap sequence above. The rule is now: dev and test sites are **never** the same site, and `hamilton-test.localhost` is protected by the test runner's site targeting in `.claude/commands/*.md`.

The 4-step bootstrap procedure is non-obvious. It is worth codifying here because a fresh bench clone — from another machine, a new contributor, or a Frappe Cloud staging environment — needs this exact sequence to reach a working test harness. The alternative ("read the source to figure out what state is expected") is what cost the 2026-04-11 debugging session.

---

## DEC-060 — `frappe.is_setup_complete()` Reads `tabInstalled Application`, Not `tabDefaultValue` or `System Settings`

**Date:** 2026-04-11
**Context:** On 2026-04-11, during a full restart of `hamilton-test.localhost` after a test run wiped dev state, the browser began a ~40-requests-per-second redirect loop on `/app` → `/app/setup-wizard` → `/app`. Three separate heal attempts failed to break the loop because they targeted the wrong source of truth:

1. **`frappe.db.set_default("setup_complete", "1")`** — writes to `tabDefaultValue` with `parent='__default'`. This is what every blog post and Stack Overflow answer recommends. It has **no effect** on `frappe.is_setup_complete()` in Frappe v16. The row is legacy and no boot-flow code reads it.

2. **`frappe.db.set_single_value("System Settings", "setup_complete", 1)`** — writes the `setup_complete` field on the System Settings singleton. This is what the ERPNext setup wizard visibly toggles. It is **also** not read by `frappe.is_setup_complete()` in v16.

3. **Setting `tabDefaultValue.desktop:home_page = 'setup-wizard'`** — was accidentally introduced by an earlier heal attempt. This was the actual cause of the observed `/app/setup-wizard` loop (pinned by `test_regression_desktop_home_page_not_setup_wizard`), not the `setup_complete` flag, but during diagnosis it was assumed to be a setup_complete issue and the heal attempts above were tried first.

The authoritative source, revealed by reading `frappe/__init__.py::is_setup_complete()` directly on 2026-04-11, is a query against `tabInstalled Application` filtered to `app_name IN ('frappe', 'erpnext')`. Other installed apps — including `hamilton_erp` — are irrelevant to this check. The row for `hamilton_erp` can have `is_setup_complete=0` forever and the boot flow will not care.

**Decision:**

1. **Any code that needs to mark setup as complete on a dev or test site MUST target `tabInstalled Application.is_setup_complete` for `frappe` AND `erpnext`.** Do NOT use `frappe.db.set_default("setup_complete", ...)`, `frappe.db.set_single_value("System Settings", "setup_complete", ...)`, or any variant. Those writes are cosmetic in v16 and serve only as legacy-caller syncs.

2. **The canonical heal pattern is in `hamilton_erp/setup/install.py::ensure_setup_complete`** (wired as the `after_migrate` hook in `hooks.py:60`):

   ```python
   for app_name in ("frappe", "erpnext"):
       if frappe.db.exists("Installed Application", {"app_name": app_name}):
           current = frappe.db.get_value("Installed Application",
               {"app_name": app_name}, "is_setup_complete")
           if current != 1:
               frappe.db.set_value("Installed Application",
                   {"app_name": app_name}, "is_setup_complete", 1)
   ```

   The same pattern is duplicated in `hamilton_erp/test_helpers.py::restore_dev_state` step 1. Both are idempotent.

3. **`frappe.db.set_default("setup_complete", "1")` and `frappe.db.set_single_value("System Settings", "setup_complete", ...)` are still called alongside the authoritative heal** as defense-in-depth for any legacy code path that might read from those sources. They are cheap, idempotent, and their presence makes the heal robust to future Frappe version drift that might re-introduce a legacy reader.

4. **The `after_migrate` hook in `hooks.py` is load-bearing.** Frappe's `InstalledApplications.update_versions()` runs on every `bench migrate` and CAN flip `is_setup_complete` back to 0 on single-admin dev sites where it cannot auto-detect a non-Administrator System User. Without the `ensure_setup_complete` after_migrate hook, every `bench migrate` invocation is a potential re-trigger of the setup-wizard redirect loop. Commit `7c866a6 fix(setup): target tabInstalled Application.is_setup_complete + add after_migrate self-heal` introduced this on 2026-04-11 and the hook MUST NOT be removed.

5. **Diagnosing "am I in setup-wizard-loop land?" on any Hamilton site starts with:**

   ```
   bench --site <site> console <<'PY'
   import frappe
   print(frappe.is_setup_complete())
   for a in ("frappe", "erpnext"):
       print(a, frappe.db.get_value("Installed Application",
           {"app_name": a}, "is_setup_complete"))
   PY
   ```

   If `frappe.is_setup_complete()` is False, the fix is the `ensure_setup_complete` heal pattern above. If it is True but the browser still loops, the bug is elsewhere (typically `tabDefaultValue.desktop:home_page='setup-wizard'` — see the regression pin `test_regression_desktop_home_page_not_setup_wizard` in `test_environment_health.py`).

**Rationale:** The misleading signal — "set_default and set_single_value both accept the write without error" — is what made this bug cost hours. Frappe's data model has three overlapping stores for "is this site set up": `tabDefaultValue`, `System Settings`, and `tabInstalled Application`. Only the third is authoritative in v16. The other two are legacy stores kept for backwards compatibility with apps that still read them (if any). A heal routine that targets only the legacy stores silently accepts the write, reports success, and leaves the real source untouched — which is exactly what happened during initial diagnosis on 2026-04-11.

Codifying this in a DEC entry is valuable because the knowledge cannot be recovered from reading Hamilton code alone — the heal pattern in `install.py` looks like "belt and suspenders" without the context that only the first loop (the `Installed Application` writes) is actually load-bearing. A future contributor cleaning up "cosmetic" code might remove the authoritative write and leave only the legacy cosmetic writes, re-introducing the bug. The inline docstrings in `install.py` and `test_helpers.py` now reference DEC-060 by number to make the codification discoverable from the code.

This decision also completes the triage set for 2026-04-11: DEC-058 (HTTP verb mismatch), DEC-059 (dedicated test site), and DEC-060 (real setup_complete source). Together they document every non-obvious root cause from that day's debugging arc.

---

*Add new decisions below this line. Use the next sequential number.*
