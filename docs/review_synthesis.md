# Hamilton ERP — Three-AI Review Synthesis
**Date:** 2026-04-09
**Reviewers:** ChatGPT, Gemini, Grok (main + 6 deep-dive docs)

---

## OVERALL VERDICT

| Reviewer | Verdict | Confidence |
|---|---|---|
| ChatGPT | Not build-safe yet — several gaps must be fixed first | Moderate ERPNext depth |
| Gemini | Proceed to Phase 0 with minor additions | Strong ERPNext depth |
| Grok | Production-ready for Phase 0 — fix small gaps, then code | Strongest ERPNext depth + provided working code |

**Decision:** Grok and Gemini are the more authoritative ERPNext reviewers. ChatGPT raises valid points but over-engineers for Phase 0. The right path: record the agreed fixes as decisions, update schemas, then start coding.

---

## SECTION 1 — WHERE ALL THREE AGREE (Action required)

### 1.1 Concurrency / Race Conditions = #1 Risk
All three agree: two operators assigning the same asset simultaneously is the #1 production killer.

**Fix:** Server-side state machine enforcement + database row-level locking (`SELECT ... FOR UPDATE`).
Grok went further and provided complete working code:
- `lock_for_status_change()` context manager using MariaDB `FOR NO KEY UPDATE`
- Redis advisory lock (hybrid pattern) for fast pre-check
- Optimistic `version` field as secondary layer
- JS retry logic with friendly "Asset taken — refresh board" message

**Decision DEC-019:** Adopt Grok's hybrid locking pattern (Redis advisory + MariaDB row lock + version field).

### 1.2 Paid-But-Unassigned = Unresolved Gap
All three flagged: if payment succeeds but assignment fails (network drop, operator closes tab, all assets suddenly dirty), there is no defined recovery state.

**Fix:** Add `assignment_status` field (Select: Pending / Assigned / Failed) to Venue Session. Add daily cleanup job for orphaned sessions.

**Decision DEC-020:** Add assignment_status to Venue Session + daily orphan cleanup job.

### 1.3 Non-Stacking Pricing Requires Custom Code
All three agree: ERPNext Pricing Rule Priority controls order, not mutual exclusion. "Under 25 cannot combine with Locker Special" cannot be enforced purely in standard ERPNext.

**Fix:** Custom server-side `validate` hook on Sales Invoice that checks if both rules are active and throws an error.

**Decision DEC-017:** Non-stacking rule requires custom server-side validation on Sales Invoice.

### 1.4 Under 25 Manual Trigger Requires Custom Code
All three agree: standard Pricing Rules auto-apply when conditions match — they cannot be "operator manually applies after ID check" without custom code.

**Fix:** Custom POS button "Apply Under 25" that checks operator permission + sets a flag + applies 50% to admission lines only.

**Decision DEC-017 (extended):** Under 25 trigger requires custom POS button, not pure Pricing Rule.

### 1.5 Blind Cash Control Needs More Than One Permission
All three agree: blocking POS Closing Entry is necessary but not sufficient. Operators can still see expected totals via Sales Register reports, list views, API responses.

**Fix:** Role permissions on Reports and Pages too. Use Frappe v16 field-level masking on sensitive cash fields.

**Decision DEC-021:** Blind cash control requires role permissions on DocType + Reports + Pages + field masking.

### 1.6 DocType Schemas Have Missing Fields
All three flagged missing fields. Consolidated list of agreed additions:

**Venue Asset — add:**
- `company` (Link to Company) — multi-company ERPNext standard
- `is_active` (Check, default 1) — disable without deleting
- `hamilton_last_status_change` (Datetime, read-only) — set on every status change
- `version` (Int, hidden, default 0) — optimistic locking layer
- `reason` (Text) — for Out of Service transitions (already implied but make explicit)

**Venue Session — add:**
- `shift_record` (Link to Shift Record) — critical for reconciliation math
- `assignment_status` (Select: Pending/Assigned/Failed, default Pending)
- `customer` (Link to Customer, default Walk-in) — forward compat for Philadelphia membership
- `pricing_rule_applied` (Data) — audit which rule fired
- `under_25_applied` (Check) — audit trail for discount
- `comp_flag` (Check) — safety flag

**Cash Drop — add:**
- `shift_record` (Link to Shift Record)
- `pos_closing_entry` (Link to POS Closing Entry)

**Shift Record — add:**
- `pos_profile` (Link to POS Profile)
- `pos_opening_entry` (Link to POS Opening Entry)
- `pos_closing_entry` (Link to POS Closing Entry)

**Comp Admission Log — add:**
- `comp_value` (Currency) — what the comp was worth
- `admission_item` (Link to Item)

**Sales Invoice custom fields — add:**
- `hamilton_shift_record` (Link to Shift Record) — ties invoice to shift for reconciliation

---

## SECTION 2 — WHERE TWO REVIEWERS AGREE (Action required)

### 2.1 HST-Inclusive Has a v16 Limitation (ChatGPT + Grok)
Item Tax Template does NOT have "Include Tax in Rate" checkbox in v16 (open GitHub issue #51510). Must use Company-level Sales Taxes and Charges Template with "Included in Print Rate" flag instead.

**Decision DEC-018:** HST-inclusive pricing uses Company-level Tax Template with "Included in Print Rate" flag, not Item Tax Template. Some custom JS may be needed for mixed retail/admission carts.

### 2.2 Role Model Needs a Third Role (ChatGPT + Gemini)
Two roles is too thin. Hamilton Manager currently means "can access reconciliation screen only" — but managers also need to change settings, configure pricing, manage assets.

**Fix:** Add Hamilton Admin role for configuration tasks (settings, asset master, pricing). Three roles total:
- Hamilton Operator — day-to-day operations
- Hamilton Manager — reconciliation + reporting
- Hamilton Admin — system configuration

**Decision DEC-022:** Three roles: Operator, Manager, Admin.

### 2.3 Bulk "Mark All Clean" on Asset Board (Gemini + implied by all)
59 assets manually clicked clean every morning is unworkable.

**Fix:** Add "Mark All Dirty → Available" bulk action to asset board. Add to Phase 1 scope.

**Decision DEC-023:** Bulk "Mark All Clean" action added to Phase 1 asset board scope.

### 2.4 board_corrections Should Be a Child Table (ChatGPT + Grok)
Free text for board corrections is too loose for audit purposes.

**Fix:** Change Shift Record `board_corrections` to a child table with: asset, old_status, new_status, reason, operator.

**Decision DEC-024:** board_corrections changed to child table.

---

## SECTION 3 — CLARIFICATIONS (No action needed)

### 3.1 hamilton_is_admission Already Covers hamilton_requires_asset
Gemini suggested adding `hamilton_requires_asset` to Item. This is the same as `hamilton_is_admission` which already exists. No change needed — just a naming difference.

### 3.2 Forward Compatibility Fields (Conflict resolved)
- Grok + Gemini: sufficient
- ChatGPT: not sufficient, needs many more fields

**Decision:** Grok and Gemini are correct. The spec already says deferred ≠ absent, and we cannot anticipate every Philadelphia field today. Adding Customer link (per DEC above) is sufficient for now. ChatGPT is over-engineering this.

### 3.3 Standard Maintenance DocType for Out of Service (Gemini only)
Gemini suggested using ERPNext's standard Maintenance Visit / Asset Repair for Out of Service state. This is out of scope — our simple OOS state + reason + audit log is sufficient for Hamilton. Defer.

### 3.4 Label Printer Cloud-to-Local Issue (Gemini)
Gemini flagged that cloud-hosted Frappe printing to a local Brother QL-820NWB can be flaky. Suggested QZ Tray as a local print proxy. Good point — add to Phase 3 risk list but not a Phase 0 blocker.

---

## SECTION 4 — GROK'S ADDITIONAL DEEP-DIVE MATERIAL

Grok provided 6 additional technical documents that go beyond the review into actual implementation. Key assets:

### 4.1 Complete Venue Asset DocType JSON
Grok provided ready-to-use DocType JSON including all fields, permissions, indexes, sort order, and naming series (`VA-.####`). This is the canonical starting point for Phase 0.

### 4.2 Complete venue_asset.py Controller
Grok provided a working Python controller including:
- `validate_transition_with_lock()` with MariaDB `FOR NO KEY UPDATE`
- Redis advisory lock via `frappe.cache()`
- Atomic Lua script for token-based Redis release
- Version field for optimistic locking
- `assign_to_session()`, `mark_vacant()`, `mark_clean()`, `set_out_of_service()` whitelisted methods
- `log_status_change()` creating Asset Status Log records
- `publish_asset_update()` for real-time board sync

### 4.3 JavaScript Retry Logic
Grok provided JS snippet for Asset Board with graceful retry and "Asset taken — refresh board" UX.

### 4.4 Frappe v16 Caffeine Architecture Notes
Key points for Hamilton:
- v16 delivers ~2x performance via Caffeine (better caching, async)
- SocketIO realtime is faster in v16
- `FOR NO KEY UPDATE` preferred over `FOR UPDATE` in v16 (avoids blocking FK checks)
- Keep locked sections extremely short (validate + save only, no I/O)

---

## SECTION 5 — PHASE 0 READINESS

**Verdict: Ready to start Phase 0 after updating schemas.**

Remaining blockers before first line of code:
1. ✅ Update DocType schemas with agreed additions (above)
2. ✅ Record new decisions DEC-017 through DEC-024
3. ✅ Retail item list — NOT required for Phase 0 scaffold
4. ✅ Asset pricing already confirmed

**Phase 0 first task (all three agree):** Build Venue Asset DocType + state machine controller + concurrency locking + unit tests FIRST, before any custom pages or POS hooks. Everything else can iterate but broken asset state data in production is expensive to fix.

---

## SECTION 6 — NEW DECISIONS TO RECORD

| Decision | Summary |
|---|---|
| DEC-017 | Non-stacking + Under 25 manual trigger both require custom server-side code |
| DEC-018 | HST-inclusive uses Company-level Tax Template with "Included in Print Rate" |
| DEC-019 | Hybrid locking: Redis advisory + MariaDB FOR NO KEY UPDATE + version field |
| DEC-020 | assignment_status field on Venue Session + daily orphan cleanup job |
| DEC-021 | Blind cash control = DocType permissions + Report/Page permissions + field masking |
| DEC-022 | Three roles: Hamilton Operator / Hamilton Manager / Hamilton Admin |
| DEC-023 | Bulk "Mark All Clean" action on asset board (Phase 1) |
| DEC-024 | board_corrections on Shift Record → child table |

---

## SECTION 7 — ITEMS TO CARRY INTO CODING STANDARDS

Add to coding_standards.md:
- Always use `FOR NO KEY UPDATE` (not `FOR UPDATE`) for status changes in v16
- Always use `after_commit=True` on publish_realtime for state changes
- Lock sections must be minimal — no I/O, printing, email inside a lock
- Always increment version field on status changes
- Redis lock requires unique token + Lua atomic release + short TTL (15s)
