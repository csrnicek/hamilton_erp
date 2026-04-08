# Hamilton ERP — Build Specification

**Version:** Hamilton ERP (Final Architecture)  
**Parent Specification:** Bathhouse ERPNext V5.4 Master Developer Specification  
**Target Platform:** ERPNext v16 / Frappe Framework v16  
**Venue:** Club Hamilton  
**Purpose:** Standalone build specification for the Hamilton pilot. Defines exactly what to build, what to defer, and how the Hamilton build connects forward to the full V5.4 specification when membership-enabled venues come online.

**Implementation Note:** Hamilton ERP uses the **standard ERPNext POS** for the transaction, payment, retail, tax, and promotion engine. Custom development is limited to the **asset board, session lifecycle, blind cash control, and manager reconciliation** — implemented as a custom Frappe app that extends the standard POS, not replaces it.

---

## 1. Architecture Decision: Standard POS + Custom Extensions

### 1.1 Core principle

Use standard ERPNext features wherever possible. Build custom only where Hamilton's operational requirements are not met by standard functionality.

### 1.2 Standard ERPNext POS handles

The following features use **unmodified standard ERPNext POS** and must not be custom-built:

| Feature | ERPNext Component |
|---|---|
| Item catalog / button grid | POS Item Group, POS Profile |
| Multi-item cart | Standard POS cart |
| Card + Cash payment methods | POS Payment Method, Mode of Payment |
| Tax-inclusive pricing | Item Tax Template (HST taxable vs exempt per item) |
| Promotional pricing with day/time rules | Promotional Pricing Rule |
| Guest receipts (print) | POS Print Format |
| Email receipts (future) | Standard Sales Invoice email |
| Sales returns / partial refunds | POS Return against Sales Invoice |
| Walk-in anonymous customer | Default POS Customer ("Walk-in") |
| POS Opening Entry (float declaration) | Standard POS Opening Entry |
| Item management and configuration | Item, Item Group, Item Price |
| Inventory tracking (future) | Stock module — activate later |

### 1.3 Custom Frappe app handles

The following features require a **custom Frappe app** (e.g., `hamilton_erp`):

| Feature | Why Custom |
|---|---|
| Asset board (room/locker status grid) | No standard equivalent in ERPNext |
| Session lifecycle (Occupied → Dirty → Available) | Not a standard ERPNext concept |
| Asset assignment linked to POS transaction | Connecting an admission item to a specific room/locker |
| Blind cash drop system | Standard POS Closing shows expected totals — violates cash control |
| Shift start board verification | Custom operational procedure |
| Manager three-way reconciliation (blind entry then reveal) | No standard equivalent |
| Comp admission reason tracking and reporting | Standard POS can do $0 items but not the reason/reporting layer |
| Overtime visual overlay on asset tiles | Custom UI |
| Label printer integration for cash drop envelopes | Custom print format |
| Cash drop label printing | Custom |

### 1.4 Standard POS Closing — disabled for operators

The standard POS Closing Entry screen shows expected cash totals, which violates the blind cash control model. The implementation must:

1. **Remove operator access** to the standard POS Closing Entry via Role Permissions
2. **Build a custom Cash Drop page** that the operator uses instead (blind — no expected totals shown)
3. **Create the standard POS Closing Entry in the background** automatically after the blind drop is submitted, so ERPNext's accounting layer receives the data it needs

The operator never sees the standard POS Closing screen. The accounting record is created behind the scenes.

### 1.5 Developer instruction

Before building any feature, the developer must ask: "Does standard ERPNext already do this?" If yes, use it. If it almost does it, extend it. Only build from scratch when there is no standard equivalent.

---

## 2. Hamilton Operating Context

### 2.1 Venue profile

Club Hamilton operates as an anonymous walk-in venue:

- No membership system
- No identity capture
- No scanner
- No arrears
- Guests pay at the door, receive a key for a room or locker, and enter through a locked door

### 2.2 Staffing model

Hamilton operates with a **single staff member** approximately 90% of the time:

- One operator covers front desk, floor, and management functions
- There is no separate Manager role on-site during solo shifts
- Multi-staff shifts occur but are the exception, not the norm

### 2.3 Asset types

Hamilton has two asset categories with different pricing:

- **Rooms** — multiple price tiers (e.g., standard room, deluxe room). Each room belongs to a configured tier. The system determines the price from the room number → tier mapping.
- **Lockers** — single price tier

Rooms and lockers follow the same lifecycle but are visually separated in the UI and priced differently.

### 2.4 Hours of operation

- Monday–Thursday: 10:00 AM – Midnight (14 hours)
- Friday: opens 10:00 AM and remains open continuously through the weekend
- Sunday: closes at Midnight

The Friday–Sunday period is a continuous 62-hour operation.

### 2.5 Shift structure

- Monday–Thursday: two shifts per day (approximately 10 AM–6 PM and 6 PM–Midnight)
- Friday–Sunday: approximately 8-hour shifts rotating through the continuous weekend

Each shift change triggers a cash drop and operator handoff. The system must support 2–3 shift changes per day.

### 2.6 Payment environment

- **Card:** standalone terminal (not integrated with POS). Operator keys the amount into the terminal separately.
- **Cash:** physical cash handling with a fixed float per shift
- The POS does not communicate with the card terminal. The operator confirms payment in the POS after collecting it externally.

**Future integration:** Stripe payment integration is planned. The data model must include fields for `terminal_transaction_id`, `payment_provider`, `integration_status`, and `payment_gateway_reference` that remain null until integrated.

### 2.7 Retail sales

Hamilton sells 25+ retail items (drinks, snacks, towels, supplies, etc.) at the front desk. These are sold both at check-in (bundled with admission) and as standalone sales to guests mid-visit. Retail is managed through the **standard ERPNext POS item catalog**.

### 2.8 Physical key system

Guests receive a physical key or wristband for their assigned room or locker. The key is handed to the guest after the operator assigns the specific asset. Guests return the key to the front desk when leaving (approximately 95% of the time). Approximately 5% of the time, the guest leaves without returning the key and the operator discovers the vacancy on rounds.

---

## 3. Design Philosophy

The five core principles from V5.4 apply, adapted for Hamilton's context:

1. **Fast normal flow** — anonymous check-in should take seconds
2. **Strict operational control** — assets must be tracked accurately; no ghost occupancy
3. **No silent guessing** — if payment fails, the system says so; if an asset is occupied, it's occupied
4. **Auditability** — every transaction is logged and attributable to the operator on shift
5. **Forward compatibility** — the record structure must support the full V5.4 specification even though Hamilton doesn't use most of it
6. **Cash control** — the system must never show expected totals to operators; all cash reconciliation uses blind procedures
7. **Standard-first** — use standard ERPNext features wherever possible; custom-build only where operationally required

---

## 4. Check-in Flow

### 4.1 Normal check-in sequence

1. **Guest states what they want** — "room" or "locker"
2. **Operator selects admission type** in the standard POS — taps the admission item (e.g., "Standard Room"), system shows the price (auto-determined by tier and any active Promotional Pricing Rule)
3. **Operator adds retail items** if the guest wants anything (Coke, towel, etc.) — optional, from the standard POS item grid
4. **Operator collects payment** — keys amount into standalone card terminal or accepts cash
5. **Operator confirms payment** in the standard POS — selects Card or Cash mode of payment, submits
6. **System prompts for asset assignment** — custom screen appears showing the asset board; operator taps an Available room or locker to assign
7. **System locks asset → moves to Occupied → session starts**
8. **Operator hands key to guest**
9. **Guest enters through locked door** (operator buzzes them in manually)

### 4.2 Key design points

- Steps 1–5 happen entirely within the **standard ERPNext POS**
- Step 6 is the handoff to the **custom asset board** — triggered automatically after POS submission when the cart contains an admission item
- Payment happens **before** asset assignment. The asset lock occurs after payment is confirmed, not during the payment step. This eliminates the need for lock timeouts during payment.
- Admission items are configured as standard ERPNext Items with a custom flag (e.g., `is_admission = 1`) that triggers the asset assignment step

### 4.3 Cart model

A single POS transaction can contain any combination of:

- One admission item (room or locker — triggers asset assignment after payment)
- Zero or more retail items
- Or retail items only (no admission — standard retail sale, no asset assignment triggered)

One cart, one payment, one Sales Invoice.

### 4.4 Standalone retail sale

When a guest already inside returns to the desk to buy something:

- Operator rings it up in the **standard POS** as a normal sale
- No admission item in the cart → no asset assignment triggered
- Standard POS handles the entire transaction

### 4.5 Comp admissions

The operator may record a **complimentary (free) admission**:

- Admission item is added to cart at $0 (or a dedicated "Comp Admission" item with zero price)
- The **custom app** requires a **reason** (mandatory, selected from a predefined list + optional free-text note) before allowing submission
- Full audit logging (who, when, why, which asset)

The system tracks all comps for reporting:

- Total comps per shift, per day, per week
- Breakdown by reason category
- Which operator authorized each comp

---

## 5. Asset Board and Session Lifecycle (Custom)

### 5.1 Asset board

The custom app provides a visual board showing all rooms and all lockers with their current state. This is the primary custom UI component.

#### Asset states

Four primary states:

| State | Meaning | Color |
|---|---|---|
| Available | Ready for assignment | Distinct available color |
| Occupied | Guest checked in | Distinct occupied color |
| Dirty | Guest vacated, needs turnover | Distinct dirty color |
| Out of Service | Not assignable | Distinct OOS color |

#### State transitions

- Available → Occupied (check-in completed and asset assigned)
- Occupied → Dirty (operator marks Vacant — triggered by key return or discovery on rounds)
- Dirty → Available (operator marks Clean)
- Any → Out of Service (operator action, reason required)
- Out of Service → Available (operator action, reason required)

No other transitions are valid. The system must enforce this.

#### Assignability

Only **Available** assets may be assigned. No override exists.

#### Rooms and lockers separated

Rooms and lockers must be visually separated in the UI. They are the same entity type with a category field and a tier field, not two separate systems.

#### Overtime visual indicator

Each asset type has a configurable **expected stay duration** (e.g., rooms = 4 hours, lockers = 8 hours — values TBD). When a session exceeds that duration, the tile gets an **overtime overlay** — a visible signal that does not replace the Occupied state color. No overtime charge is applied. This is informational only, helping the operator identify potential abandoned rooms.

### 5.2 Asset locking

When an operator assigns an asset after payment, it becomes a **true lock**. No other transaction may take that asset until:

- the session ends (operator marks Vacant)
- the asset is marked Out of Service

#### No lock timeout needed

Because payment occurs before asset assignment, there is no period where an asset is locked during an in-progress transaction. The asset moves directly from Available to Occupied upon assignment.

### 5.3 Session lifecycle

- A session begins when check-in completes (payment confirmed, asset assigned, state moves to Occupied)
- A session ends when the operator marks the asset **Vacant** (state moves to Dirty)
- Only the operator may end the session (via the asset board)
- The same operator handles cleaning and marks the asset **Clean** (state moves to Available)

#### Two vacate triggers

1. **Key return** (95%) — guest hands key back at the desk, operator marks Vacant immediately
2. **Discovery on rounds** (5%) — operator finds an empty room/locker during a walkthrough, marks Vacant from the board

Both are the same action in the system.

### 5.4 Asset assignment link to transaction

When the custom asset assignment step completes, the system must record the link between:

- The Sales Invoice (created by standard POS)
- The specific asset assigned (room/locker number)
- The session record (custom DocType tracking Occupied → Dirty → Available lifecycle)

This is a custom DocType (e.g., `Venue Session`) that references the Sales Invoice and the asset.

### 5.5 Out of Service

Marking an asset Out of Service requires:

- A reason (mandatory)
- Full audit logging

Returning an asset to service requires:

- A reason (mandatory)
- Full audit logging

---

## 6. Standard ERPNext Configuration

### 6.1 Items setup

Admission items are configured as standard ERPNext Items:

- "Standard Room" — with custom field `is_admission = 1`, `asset_category = Room`, `asset_tier = Standard`
- "Deluxe Room" — with custom field `is_admission = 1`, `asset_category = Room`, `asset_tier = Deluxe`
- "Locker" — with custom field `is_admission = 1`, `asset_category = Locker`
- "Comp Admission (Room)" — $0, `is_admission = 1`, `is_comp = 1`
- "Comp Admission (Locker)" — $0, `is_admission = 1`, `is_comp = 1`
- All retail items (Coke, towel, chips, etc.) — standard items, no custom flags needed

Room tier names and exact counts are TBD — to be configured during setup.

### 6.2 Tax configuration

- **Item Tax Template "HST Taxable"** — 13% Ontario HST, tax-inclusive
- **Item Tax Template "HST Exempt"** — 0%, applied to exempt items (e.g., bottled water)
- Each item is assigned the appropriate tax template
- The system back-calculates HST from the inclusive price for reporting and remittance

### 6.3 Promotional pricing

- Promotions are configured as **Pricing Rules** in standard ERPNext
- Each rule has day/time validity conditions (e.g., "Half-Price Tuesday" active every Tuesday)
- When active, the system **automatically applies** the promotional price — no operator selection required
- The operator **cannot override** the promotional price. If a promo needs to stop, it must be changed in configuration.
- Standard ERPNext Pricing Rules support this natively

### 6.4 POS Profile

- Configure a POS Profile for Hamilton with:
  - Allowed payment methods: Card, Cash
  - Default customer: "Walk-in"
  - Item groups visible in POS
  - Warehouse / cost center for Hamilton
  - Print format for receipts

### 6.5 Payment methods

- **Mode of Payment: Card** — no integration; operator confirms manually
- **Mode of Payment: Cash** — standard cash handling

### 6.6 Receipts

- Receipts use a **standard POS Print Format**
- Printed on a thermal receipt printer when the guest requests one
- Email receipt capability is standard in ERPNext (deferred for launch but available)

### 6.7 Refunds

- Refunds use the **standard POS Return** workflow against the original Sales Invoice
- Line-item level refunds supported (return specific items from a transaction)
- Reason for refund is captured in a custom field on the Sales Invoice or a linked record
- Full audit trail maintained by standard ERPNext document versioning

---

## 7. Cash Handling and Shift Management (Custom)

### 7.1 Core cash control principle

**The system must never show expected cash totals to the operator at any point — not during their shift, not at close-out, not after submission.** All cash reconciliation uses blind procedures. This prevents operators from reverse-engineering a "correct" count to cover theft.

### 7.2 Standard POS Closing — disabled

- Operators are **denied permission** to the standard POS Closing Entry DocType
- The operator uses the custom Cash Drop page instead
- After a blind drop is submitted, the system **automatically creates a POS Closing Entry in the background** so ERPNext's accounting layer receives the data it needs

### 7.3 Fixed float

Each shift begins with a **fixed float** of a configured amount (e.g., $200). The float amount is a system constant per location, configurable in ERPNext.

### 7.4 Cash drop workflow

Cash drops may occur at any time during a shift (mid-shift) and must occur at end of shift. The workflow is identical for both:

1. Operator initiates a **Cash Drop** on the custom page
2. Operator counts the cash they are dropping (excluding the float)
3. Operator enters the **declared drop amount**
4. System prints a **label** on the label printer containing:
   - Venue name
   - Date
   - Operator name
   - Shift identifier
   - Drop type: Mid-Shift or End-of-Shift
   - Sequential drop number for the shift (Drop 1, Drop 2, etc.)
   - Declared amount
   - Timestamp
5. Operator affixes the label to the cash envelope, seals it
6. Operator drops the envelope in the safe
7. System logs the drop: operator ID, declared amount, drop number, timestamp, drop type

The system **never** shows the operator any expected totals or variance.

### 7.5 End-of-shift close-out

End-of-shift is a specific cash drop with additional steps:

1. Operator counts out the **fixed float** and sets it aside for the next shift
2. Operator drops all remaining cash using the standard cash drop workflow (§7.4)
3. Operator confirms **shift close** on the custom page
4. System records the shift as closed: operator, end time, total drops for the shift
5. System **automatically creates the POS Closing Entry in the background** with the correct totals
6. Operator logs out

The system records the **card transaction total** for the shift as well. This is informational — card reconciliation happens against the standalone terminal's batch report separately.

### 7.6 Shift start procedure

When an incoming operator starts their shift:

1. Operator logs in
2. Standard **POS Opening Entry** is created (float amount declared)
3. Custom prompt: **Verify float** — operator counts the float and confirms it matches the expected amount
4. If the float does not match, the operator enters the actual amount and the variance is logged as a shift-start exception
5. Custom prompt: system shows the **current asset board** — operator reviews it against physical reality
6. Operator either confirms **"Board is accurate"** or makes corrections (marking rooms Vacant/Clean/OOS as needed)
7. Shift start confirmation is logged: operator, time, float confirmed (yes/no + amount if variance), board confirmed (yes/no + corrections if any)

### 7.7 Manager cash reconciliation (Custom)

The manager performs reconciliation on-site by opening cash drop envelopes:

1. Manager opens the **custom reconciliation screen**
2. Manager selects a cash drop envelope (by date, shift, operator, drop number)
3. System shows **only**: date, shift, operator name, drop number — **no dollar amounts**
4. Manager counts the actual cash in the envelope
5. Manager enters the **actual count** — blind, no system numbers visible
6. Manager submits
7. **Only after submission** does the system reveal the three-way comparison:
   - **System expected total** (sum of cash transactions for that drop period)
   - **Operator declared amount** (what the operator said they were dropping)
   - **Manager actual count** (what the manager just entered)
8. System flags variances:
   - All three match: **Clean** — no action needed
   - Operator declared matches manager actual, but differs from system expected: **Possible theft or transaction error** — investigation required
   - Manager actual differs from operator declared: **Operator mis-declared** — investigation required
9. Manager can add notes to the reconciliation record
10. Reconciliation is logged: manager ID, timestamp, all three amounts, variance flag, notes

### 7.8 Label printer

A small label printer (e.g., Dymo LabelWriter, Brother QL series) is required at each front desk station for cash drop envelope labels. This is a mandatory hardware requirement for Hamilton launch.

---

## 8. Operator Identity and Permissions

### 8.1 Simplified staff model

Hamilton operates with a **shift login** model:

- The operator logs in at the start of their shift (after float verification and board confirmation)
- All transactions during the shift are attributed to that operator
- The operator logs out at the end of their shift (after end-of-shift cash drop)
- If a second staff member arrives, they log in under their own identity

### 8.2 Solo operator permissions

Because Hamilton typically has one person on shift, the operator role at Hamilton combines Front and Manager permissions for all operational actions.

| Action | Hamilton Operator |
|---|---|
| Ring up sales in POS | Yes |
| Confirm payment | Yes |
| Assign asset | Yes |
| Mark Vacant / Clean | Yes |
| Mark Out of Service (with reason) | Yes |
| Return to Service (with reason) | Yes |
| Process refund (with reason) | Yes |
| Record comp admission (with reason) | Yes |
| Initiate cash drop | Yes |
| Close shift | Yes |
| Cancel transaction | Yes |
| **Access standard POS Closing Entry** | **No — blocked** |
| **Access manager reconciliation screen** | **No — manager only** |

The manager reconciliation screen is a separate permission — only the manager may access it.

### 8.3 Audit attribution

Every transaction and action must record:

- The operator's identity (from shift login)
- Date and time
- Terminal (for future multi-terminal support)
- Action taken
- Reason (where required)

---

## 9. Custom DocTypes

The custom Frappe app introduces the following DocTypes:

### 9.1 Venue Asset

Represents a room or locker.

- `asset_name` (e.g., "Room 7", "Locker 22")
- `asset_category` (Room / Locker)
- `asset_tier` (Standard / Deluxe / etc. — for rooms; single tier for lockers)
- `status` (Available / Occupied / Dirty / Out of Service)
- `current_session` (link to Venue Session, if occupied)
- `expected_stay_duration` (minutes — for overtime calculation)
- `location` (link to venue / company)
- `display_order` (for board layout)

### 9.2 Venue Session

Represents an active or completed guest session.

- `venue_asset` (link to Venue Asset)
- `sales_invoice` (link to standard Sales Invoice created by POS)
- `admission_item` (which admission item was purchased)
- `session_start` (datetime — when asset was assigned)
- `session_end` (datetime — when marked Vacant)
- `status` (Active / Completed)
- `operator_checkin` (link to User who checked the guest in)
- `operator_vacate` (link to User who marked Vacant)
- `vacate_method` (Key Return / Discovery on Rounds)
- Forward compatibility fields (all null at Hamilton):
  - `member_id`, `full_name`, `date_of_birth`, `membership_status`
  - `identity_method` (set to "not_applicable")
  - `arrears_amount`, `arrears_flag`, `arrears_sku`
  - `scanner_data`, `eligibility_snapshot`, `block_status`

### 9.3 Cash Drop

Represents a single cash drop envelope.

- `operator` (link to User)
- `shift_date` (date)
- `shift_identifier` (text — e.g., "Evening")
- `drop_type` (Mid-Shift / End-of-Shift)
- `drop_number` (sequential integer for the shift)
- `declared_amount` (currency)
- `timestamp` (datetime)
- `reconciled` (Yes / No)
- `reconciliation` (link to Cash Reconciliation, if reconciled)

### 9.4 Cash Reconciliation

Represents the manager's verification of a cash drop.

- `cash_drop` (link to Cash Drop)
- `manager` (link to User)
- `actual_count` (currency — what the manager counted)
- `system_expected` (currency — calculated from POS transactions, revealed only after submission)
- `operator_declared` (currency — copied from Cash Drop)
- `variance_flag` (Clean / Possible Theft or Error / Operator Mis-declared)
- `notes` (text)
- `timestamp` (datetime)

### 9.5 Asset Status Log

Audit trail for every asset state change.

- `venue_asset` (link to Venue Asset)
- `previous_status`
- `new_status`
- `reason` (mandatory for OOS and Return to Service)
- `operator` (link to User)
- `timestamp` (datetime)

### 9.6 Shift Record

Tracks shift start/end and related metadata.

- `operator` (link to User)
- `shift_date` (date)
- `shift_start` (datetime)
- `shift_end` (datetime)
- `float_expected` (currency)
- `float_actual` (currency)
- `float_variance` (currency)
- `board_confirmed` (Yes / No)
- `board_corrections` (text — what was corrected)
- `status` (Open / Closed)

### 9.7 Comp Admission Log

Tracks comp admissions with mandatory reasons.

- `venue_session` (link to Venue Session)
- `sales_invoice` (link to Sales Invoice)
- `reason_category` (Loyalty Card / Promo / Manager Decision / Other)
- `reason_note` (free text)
- `operator` (link to User)
- `timestamp` (datetime)

---

## 10. UI Components (Custom)

### 10.1 Asset board

The primary custom screen. Shows all rooms and lockers with current state.

- Tiles are small and high-density
- Show asset number and current state (color-coded)
- Rooms and lockers in separate visual groups
- Room tier visually distinguishable (subtle indicator)
- Tap a tile to interact (assign during check-in, vacate, mark clean, OOS, etc.)
- Out of Service assets are visible but not selectable for check-in
- Overtime appears as an overlay, not a replacement of the state color

### 10.2 Asset assignment prompt

Appears after a POS transaction containing an admission item is submitted:

- Shows the asset board filtered to Available assets of the correct category (rooms or lockers)
- Operator taps to assign
- Assignment completes the check-in → creates Venue Session

### 10.3 Cash drop screen

Replaces the standard POS Closing for operators:

- "New Cash Drop" button available at any time
- Operator enters declared amount
- System prints label
- No expected totals shown — ever

### 10.4 Shift start screen

Shown when operator logs in:

- Float verification prompt (enter actual count)
- Asset board review and confirmation
- Board correction capability (mark rooms Vacant/Clean/OOS)

### 10.5 Shift close screen

End-of-shift workflow:

- Triggers final cash drop
- Shift close confirmation
- Automatic POS Closing Entry creation in background
- Logout

### 10.6 Manager reconciliation screen

Accessed only by manager role:

- Select a cash drop to reconcile
- Enter actual count (blind — no amounts shown)
- Submit → three-way comparison revealed
- Add notes, flag variances

---

## 11. Audit Logging

### 11.1 Core principle

Every transaction and every state change must be logged. This is non-negotiable.

### 11.2 Standard ERPNext audit

The following are handled by standard ERPNext document versioning and logging:

- All Sales Invoices (POS transactions) with full line items, amounts, payments
- Sales Returns / refunds
- POS Opening and Closing entries
- User login / logout
- Document amendments

### 11.3 Custom audit

The custom app must log (via the custom DocTypes defined in §9):

- All asset state changes (Asset Status Log)
- All sessions (Venue Session — start, end, operator, method)
- All cash drops (Cash Drop)
- All reconciliations (Cash Reconciliation)
- All shift records (Shift Record — float, board verification)
- All comp admissions (Comp Admission Log)

### 11.4 Forward compatibility fields

The Venue Session DocType must contain **all fields** defined in the full V5.4 transaction model that Hamilton does not use. These fields remain null at Hamilton:

- identity_method (set to "not_applicable")
- member_id, full_name, date_of_birth
- membership_status
- arrears_amount, arrears_flag, arrears_sku
- scanner_data, eligibility_snapshot, block_status, snapshot_server_state

A developer must never omit these fields because Hamilton doesn't use them.

---

## 12. Hardware Requirements

| Hardware | Purpose | Required for Launch |
|---|---|---|
| Tablet (iPad or Android) | Primary POS device (web browser) | Yes |
| Label printer (Dymo/Brother) | Cash drop envelope labels | Yes |
| Receipt printer (small thermal) | Guest receipts on request | Yes |
| Standalone card terminal | Card payments | Yes (existing) |
| Cash drawer / till | Cash storage during shift | Yes (existing) |
| Drop safe | Sealed envelope storage | Yes (existing) |
| Dual WAN router (per V5.4 §11.1) | Network failover | Yes |

---

## 13. System Constants and Timers

| Constant | Value |
|---|---|
| Fixed float amount | Configurable per location (e.g., $200) |
| Expected stay duration (rooms) | Configurable per asset type (TBD) |
| Expected stay duration (lockers) | Configurable per asset type (TBD) |
| HST rate | 13% (Ontario) |
| Expected check-in time | ~10 seconds |

---

## 14. What Hamilton ERP Defers

The following V5.4 sections are **entirely deferred** and must not be built for the Hamilton pilot:

| V5.4 Section | Topic | Reason Deferred |
|---|---|---|
| §3 | Identity Rules | No membership at Hamilton |
| §4 | Membership and Eligibility | No membership at Hamilton |
| §5 | Arrears Rules | No arrears at Hamilton |
| §6.5–6.7 | Lock refresh / timeout / grace | Payment before assignment eliminates the need |
| §7.2 | Maintenance condition | Four states sufficient for Hamilton |
| §8.3 | Vacant reversal | Cancel and redo at Hamilton |
| §8.4 | Move guest / asset correction | Cancel and redo at Hamilton |
| §9.3–9.4 | Payment uncertainty engine | Standalone terminal; binary confirm model |
| §10 | Interrupted flow and recovery | Cancel and redo at Hamilton |
| §11 (software) | Offline operation software | Dual WAN hardware required; offline software deferred |
| §12 | Local membership cache | No membership data to cache |
| §13 | POS tablet sync architecture | No cache to sync |
| §14 | Sync integrity rules | No sync to manage |
| §15 | Manager overrides and pattern detection | Solo operator; no override hierarchy |
| §16 | Shift / day / weekly review reports | Deferred to Phase 3 scope |
| §30.8 full | Shared terminal clerk model | Simplified shift login sufficient |

### 14.1 Deferred ≠ absent from schema

Deferral means the **business logic and UI** for these features are not built. The **data model** (fields in Venue Session and other DocTypes) must still exist to support forward compatibility.

---

## 15. QA Test Cases

### Check-in Flow

**Test Case H1 — Standard Room Check-in**
**Steps:** select "Standard Room" in POS → confirm "Paid by Card" → assign room on asset board
**Expected:** Sales Invoice created; room moves to Occupied; Venue Session created linking invoice to asset

**Test Case H2 — Standard Locker Check-in**
**Steps:** select "Locker" in POS → confirm "Paid by Cash" → assign locker on asset board
**Expected:** locker moves to Occupied; correct locker price on invoice

**Test Case H3 — Check-in with Retail Items**
**Steps:** select "Standard Room" + Coke + towel in POS → confirm payment → assign room
**Expected:** one Sales Invoice with three line items; room moves to Occupied

**Test Case H4 — Cancel Mid-Transaction**
**Steps:** start adding items in POS → cancel
**Expected:** no Sales Invoice created; no asset assigned; POS returns to ready state

**Test Case H5 — Comp Admission**
**Steps:** select "Comp Admission (Room)" → system prompts for reason → enter "loyalty card" → submit → assign room
**Expected:** $0 Sales Invoice; Comp Admission Log created with reason; room moves to Occupied

### Retail

**Test Case H6 — Standalone Retail Sale**
**Steps:** add Coke + chips in POS (no admission item) → confirm payment
**Expected:** Sales Invoice created; no asset assignment prompted; no Venue Session

**Test Case H7 — Tax Handling**
**Steps:** add 3× water (exempt) + 1× energy drink (taxable) → confirm payment
**Expected:** correct total; HST calculated only on energy drink; water shows no tax

### Refunds

**Test Case H8 — Line-Item Refund**
**Steps:** find original Sales Invoice → POS Return → select Coke only → submit
**Expected:** Coke refunded; room admission and session remain active; return linked to original invoice

**Test Case H9 — Full Transaction Refund**
**Steps:** POS Return on entire Sales Invoice
**Expected:** full amount refunded; original invoice preserved in audit

### Asset Lifecycle

**Test Case H10 — Vacate and Turnover**
**Steps:** tap Occupied room → mark Vacant → tap Dirty room → mark Clean
**Expected:** room moves Occupied → Dirty → Available; Asset Status Log entries created

**Test Case H11 — Out of Service**
**Steps:** mark available room OOS with reason "plumbing issue"
**Expected:** room moves to OOS; reason in Asset Status Log; room not selectable

**Test Case H12 — Occupied Asset Rejection**
**Steps:** attempt to assign an Occupied room during check-in
**Expected:** not selectable; only Available rooms shown

### Cash Handling

**Test Case H13 — Mid-Shift Cash Drop**
**Steps:** initiate cash drop → enter $350 → submit
**Expected:** label prints; Cash Drop record created; no expected total shown

**Test Case H14 — End-of-Shift Close-out**
**Steps:** final cash drop → confirm shift close → log out
**Expected:** Cash Drop recorded; Shift Record closed; POS Closing Entry created in background; operator logged out

**Test Case H15 — Manager Reconciliation (Clean)**
**Steps:** manager selects drop → enters actual count matching declared → submits
**Expected:** three-way comparison shown; all match; flagged Clean

**Test Case H16 — Manager Reconciliation (Variance)**
**Steps:** manager enters actual count differing from declared
**Expected:** variance flagged; three-way comparison shown; manager adds notes

**Test Case H17 — Operator Cannot Access POS Closing**
**Steps:** operator attempts to navigate to POS Closing Entry
**Expected:** permission denied

### Shift Management

**Test Case H18 — Shift Start with Float Variance**
**Steps:** operator logs in → float count doesn't match → enters actual amount
**Expected:** variance logged in Shift Record; shift proceeds

**Test Case H19 — Shift Start Board Correction**
**Steps:** operator logs in → Room 5 shows Occupied but is empty → marks Vacant
**Expected:** correction logged; board accurate; shift confirmed with corrections noted

### Promotions

**Test Case H20 — Auto-Applied Promotion**
**Preconditions:** "Half-Price Tuesday" Pricing Rule active
**Steps:** select room admission on a Tuesday
**Expected:** promo price applied automatically; shown on invoice

**Test Case H21 — No Promotion Active**
**Steps:** select room admission on a non-promo day
**Expected:** standard price applied

### Forward Compatibility

**Test Case H22 — Record Structure Integrity**
**Steps:** complete a check-in; inspect Venue Session in ERPNext
**Expected:** all V5.4 fields present; identity/membership/arrears fields null; identity_method = "not_applicable"

---

## 16. Relationship to V5.4

### 16.1 Hamilton ERP is a subset of V5.4

Every feature built for Hamilton ERP must conform to the V5.4 specification. Hamilton ERP does not contradict V5.4 — it defers portions of it and adds Hamilton-specific operational features (cash handling, retail via standard POS, shift management).

### 16.2 Pre-Philadelphia build

After Hamilton is operational, the following must be built before deploying at Club Philadelphia:

- Full identity / scanner / membership / eligibility flow (V5.4 §3, §4)
- Arrears enforcement (V5.4 §5)
- Eligibility snapshot (V5.4 §4.4)
- Meaningful progress lock refresh (V5.4 §6.5–6.7)
- Payment uncertainty engine (V5.4 §9.3–9.4)
- Interrupted flow and recovery / restart packets (V5.4 §10)
- Offline software stack (V5.4 §11, §12, §13, §14)
- Shared terminal clerk model with re-authentication (V5.4 §30.8)
- Manager override model and permissions split (V5.4 §15, §21)
- Shift / day / weekly review reports (V5.4 §16)
- Vacant reversal and move guest (V5.4 §8.3, §8.4)
- Maintenance condition overlay (V5.4 §7.2)
- Stripe payment integration (replacing standalone terminal confirmation)

### 16.3 What carries forward from Hamilton to all venues

The following Hamilton ERP features are **not in V5.4** but apply to all venues and should carry forward:

- Blind cash drop system with label printing
- Manager three-way cash reconciliation
- Comp admission tracking with mandatory reasons
- Shift start / close procedures with float verification and board confirmation
- Standard ERPNext POS as the transaction engine (with custom extensions)

V5.4 should be updated to incorporate these once Hamilton validates the model.

### 16.4 Nothing built for Hamilton should need to be rewritten for Philadelphia

If the Hamilton build is done correctly — full schema, inactive states present, null-safe field handling, standard ERPNext POS as the base — then Philadelphia is purely additive.

---

## 17. Scope Clarification

### Hamilton ERP is:
- A build specification for the Hamilton pilot venue
- A strict subset of V5.4 (for check-in and asset management)
- A standard ERPNext POS configuration (for retail, payment, tax, promotions, receipts)
- A custom Frappe app specification (for asset board, sessions, cash control, reconciliation)
- A forward-compatible foundation for the full V5.4 rollout

### Hamilton ERP is not:
- A replacement for V5.4 (V5.4 remains the master specification)
- A standalone product (it is designed to grow into the full spec)
- A complete ERPNext technical architecture document
- A hardware specification

---

## 18. Future Integration Points

The following are not in scope for Hamilton ERP but the system should be designed to accommodate them:

| Integration | Description | When |
|---|---|---|
| Stripe payments | Integrated card terminal replacing standalone confirmation | Pre-Philadelphia |
| Email receipts | Send receipt to guest's email address | Post-launch |
| Door buzzer | Automatic door release on check-in completion | Future |
| Digital loyalty | System-tracked loyalty program replacing physical punch cards | V3 or V4 |
| Inventory management | Stock tracking, low-stock alerts, reorder points | Post-launch (standard ERPNext Stock module) |
| Capacity counter | Live guest count derived from active sessions | Post-launch |

---

## 19. Final Core Statement

> Hamilton ERP builds a complete front-desk operating system — standard ERPNext POS for transactions, a custom asset board for room and locker management, and a blind cash control system for financial integrity — while preserving the full structural foundation for the membership-enabled venues that follow.
