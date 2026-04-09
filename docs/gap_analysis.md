# Hamilton ERP — Full Gap Analysis
# AI Reviews vs Current Project Docs
# Date: 2026-04-09

## METHOD
Every point raised by ChatGPT, Gemini, and all 8 Grok documents compared
against current_state.md and decisions_log.md (DEC-001 to DEC-024).
Status: ✅ Captured | ⚠️ Partial | ❌ Missing

---

## A. ARCHITECTURE

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Standard POS + custom extensions correct | All | ✅ DEC-001 | None |
| v16 POS is Vue.js SPA — need loosely coupled extensions | Gemini | ❌ | Add to coding_standards |
| v16 POS uses pos_controller events (changed from v15) | Grok | ❌ | Add to coding_standards |
| Payment before assignment correct | All | ✅ DEC-002 | None |
| Edge case: all Deluxe rooms Dirty after guest pays Deluxe | Gemini/ChatGPT | ❌ | Define "tier unavailable" workflow |
| Edge case: split tender (cash+card) — which triggers assignment? | Grok/ChatGPT | ❌ | Need decision |
| Edge case: refund after assignment must auto-release asset | Grok/ChatGPT | ❌ | Need decision |
| Edge case: network failure after payment, before assignment | Grok | ⚠️ DEC-020 partial | Needs explicit recovery steps |
| One DocType for rooms/lockers correct | All | ✅ DEC-003 | None |
| Use POS Profile user assignment per operator | ChatGPT | ❌ | Add to config |
| Frappe Version + Activity Log instead of custom Asset Status Log | Grok | ❌ | Decision needed |
| Use frappe.printing + print_format instead of raw backend API | Grok | ❌ | Add to Phase 3 considerations |

---

## B. DOCTYPE SCHEMAS

### Venue Asset
| Field | Reviewer | Status | Action |
|---|---|---|---|
| company (Link) | Gemini/ChatGPT | ✅ Current state | None |
| is_active (Check) | ChatGPT | ✅ Current state | None |
| hamilton_last_status_change (Datetime) | Grok/ChatGPT | ✅ Current state | None |
| version (Int, hidden) | Grok/ChatGPT | ✅ Current state | None |
| reason (Text) | All | ✅ Current state | None |
| asset_code — immutable unique identifier | ChatGPT | ✅ DEC-030 | Added to schema |
| last_cleaned_at (Datetime) | ChatGPT | ✅ DEC-031 | Added to schema |
| last_vacated_at (Datetime) | ChatGPT | ✅ DEC-031 | Added to schema |
| Naming: VA-.#### | Grok | ✅ Current state | None |
| Indexes on status, display_order, category, tier | Grok | ✅ Current state | None |
| naming_series on every DocType | Grok | ❌ | Add to Phase 0 checklist |

### Venue Session
| Field | Reviewer | Status | Action |
|---|---|---|---|
| shift_record (Link) | Grok/ChatGPT | ✅ Current state | None |
| assignment_status (Select) | ChatGPT | ✅ Current state | None |
| customer (Link → Customer) | Gemini/ChatGPT | ✅ Current state | None |
| pricing_rule_applied (Data) | Grok/ChatGPT | ✅ Current state | None |
| under_25_applied (Check) | Grok/ChatGPT | ✅ Current state | None |
| comp_flag (Check) | ChatGPT | ✅ Current state | None |
| Forward compat fields (member_id, etc.) | All | ✅ Current state | None |
| member_id should be Link to Customer, not Data | Gemini | ❌ | Fix field type |
| POS Profile link on Venue Session | Gemini | ✅ DEC-032 | Not needed — single terminal always |
| session_number (auto-increment display ID) | ChatGPT | ✅ DEC-033 | Added to schema |
| checkin_rate_gross, checkin_rate_net, tax_amount | ChatGPT | ✅ DEC-034 | Not added — data lives on Sales Invoice |
| payment_status_snapshot | ChatGPT | ✅ DEC-035 | Not added — lives on Sales Invoice |
| refund_status | ChatGPT | ✅ DEC-036 | Not added — session status + Sales Invoice covers it |
| created_from_pos_invoice vs sales_invoice clarity | ChatGPT | ❌ | CRITICAL — POS Invoice vs Sales Invoice |

### Cash Drop
| Field | Reviewer | Status | Action |
|---|---|---|---|
| shift_record (Link) | Grok/ChatGPT | ✅ Current state | None |
| pos_closing_entry (Link) | Grok/ChatGPT | ✅ Current state | None |
| payment_mode_breakdown | ChatGPT | ✅ DEC-038 | Operator declares cash + card at shift close. Fields on Shift Record. |
| sealed_by, witnessed_by, bag_number | ChatGPT | ✅ DEC-037 | Not added — single operator, no witness, label TBD Phase 3 |

### Cash Reconciliation
| Field | Reviewer | Status | Action |
|---|---|---|---|
| cash_drop, manager, amounts, variance_flag | All | ✅ Current state | None |
| variance_amount (explicit Currency field) | ChatGPT | ✅ DEC-039 | Added to Cash Reconciliation schema |
| resolved_by, resolution_status | ChatGPT | ❌ | Decision needed |
| direct shift_record link | ChatGPT | ❌ | Can reach via cash_drop — decide if direct needed |

### Asset Status Log
| Field | Reviewer | Status | Action |
|---|---|---|---|
| venue_asset, status fields, reason, operator | All | ✅ Current state | None |
| venue_session link | ChatGPT | ❌ | Useful for traceability — add |
| source_doctype / source_name | ChatGPT | ❌ | Decision needed |
| autoname: autoincrement | Grok | ❌ | Add to schema |

### Shift Record
| Field | Reviewer | Status | Action |
|---|---|---|---|
| pos_profile, pos_opening_entry, pos_closing_entry | Grok/ChatGPT | ✅ Current state | None |
| board_corrections as child table | ChatGPT/Grok | ✅ DEC-024 | None |
| opening_float_declared_by | ChatGPT | ❌ | Add — who counted the float? |
| closing_state | ChatGPT | ❌ | Partial — we have status Open/Closed |
| reconciliation_status | ChatGPT | ❌ | Decision needed |

### Comp Admission Log
| Field | Reviewer | Status | Action |
|---|---|---|---|
| admission_item, comp_value, reason fields | All | ✅ Current state | None |
| approved_by | ChatGPT | ❌ | Low priority for Hamilton — decide |

### Hamilton Settings
| Field | Reviewer | Status | Action |
|---|---|---|---|
| float_amount, stay_duration, printer settings | All | ✅ Current state | None |
| grace_minutes | ChatGPT | ❌ | Add — for overtime calculation |
| assignment_timeout_minutes | ChatGPT | ❌ | Needed for recovery workflow |
| oos_reason_master / default values | ChatGPT | ❌ | Low priority — decide |
| printer_label_template_name | ChatGPT | ❌ | Add — which label template to use |

### Custom Fields on Standard DocTypes
| Field | Reviewer | Status | Action |
|---|---|---|---|
| hamilton_is_admission, hamilton_asset_category/tier, hamilton_is_comp | All | ✅ | None |
| hamilton_shift_record on Sales Invoice | Grok/ChatGPT | ✅ Current state | None |
| hamilton_pricing_rule_override on Item | Grok | ❌ | Needed for Under 25 trigger |
| hamilton_requires_asset_assignment on Item | ChatGPT | ❌ | Same as hamilton_is_admission — DUPLICATE, skip |

---

## C. PRICING RULES

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Non-stacking needs custom code | All | ✅ DEC-017 | None |
| Under 25 needs custom POS button | All | ✅ DEC-017 | None |
| Locker Special supported in v16 with day/time | Grok | ✅ DEC-014 | None |
| Priority setting for Locker Special vs Under 25 | Gemini | ❌ | Add to ERPNext config notes |
| HST-inclusive uses Company-level Tax Template | Grok/ChatGPT | ✅ DEC-018 | None |

---

## D. CASH CONTROL

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Multi-layer permissions needed | All | ✅ DEC-021 | None |
| Float carryover: does $200 stay or get dropped? | Gemini/ChatGPT | ❌ | CRITICAL — need decision from Chris |
| system_expected calculation method (deterministic) | Grok/ChatGPT | ❌ | Add calculate_system_expected method spec |
| system_expected freezing — when exactly? | ChatGPT | ❌ | Add to reconciliation spec |
| Refunds after drop affect reconciliation | Grok/ChatGPT | ❌ | Add to reconciliation spec |
| Comp admissions must NOT affect cash totals | Grok | ❌ | Add to reconciliation spec |
| Variance workflow — what happens after flag? | ChatGPT | ❌ | Add to manager workflow spec |

---

## E. SECURITY & PERMISSIONS

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Three roles: Operator, Manager, Admin | ChatGPT/Gemini | ✅ DEC-022 | None |
| Hamilton Auditor role | Gemini | ❌ | Decided not needed for Hamilton — skip |
| API bypass: whitelist checks must verify role server-side | Gemini/ChatGPT | ❌ | Add to coding_standards |
| Reports/pages/field masking | All | ✅ DEC-021 | None |

---

## F. FORWARD COMPATIBILITY

| Point | Reviewer | Status | Action |
|---|---|---|---|
| V5.4 null fields sufficient | Grok/Gemini | ✅ DEC-007 | None |
| member_id as Link to Customer, not Data | Gemini | ❌ | Fix in schema |
| Customer link on Venue Session | Both | ✅ Current state | None |
| Philadelphia: additive only | Grok | ✅ | None |
| Asset Board UI should be card-based for future member photo | Gemini | ❌ | Add to Phase 1 design notes |

---

## G. GENERAL / PHASE 0 ITEMS

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Concurrency #1 risk | All | ✅ DEC-019 | None |
| Hybrid locking: Redis + MariaDB + version | Grok | ✅ DEC-019 | None |
| FOR NO KEY UPDATE (not FOR UPDATE) in v16 | Grok | ❌ | Add explicitly to coding_standards |
| naming_series and autoname required on every DocType | Grok | ❌ | Add to Phase 0 checklist |
| Hamilton Desk/Workspace as Phase 0 deliverable | Gemini | ❌ | Add to Phase 0 deliverables |
| Daily cleanup job for orphaned sessions | All | ✅ DEC-020 | None |
| Frontend retry on concurrency failure | Grok | ❌ | Add to coding_standards |
| POS Invoice vs Sales Invoice — which does Hamilton use? | ChatGPT/Grok | ❌ | CRITICAL decision needed |
| calculate_system_expected method on Shift Record | Grok | ❌ | Add to Phase 3 spec |
| Bulk Mark All Clean | Gemini | ✅ DEC-023 | None |
| board_corrections as child table | ChatGPT/Grok | ✅ DEC-024 | None |
| Label printer cloud-to-local risk (QZ Tray) | Gemini | ❌ | Add to Phase 3 risk notes |
| Asset board card-based design for future Philadelphia | Gemini | ❌ | Add to Phase 1 design notes |
| Whitelisted methods required on Venue Asset | Grok | ❌ | Add to Phase 0 checklist |
| Lock TTL = 15 seconds, UUID token, Lua atomic release | Grok | ❌ | Add to coding_standards |
| Consistent lock ordering for multiple asset ops | Grok | ❌ | Add to coding_standards |
| MariaDB READ COMMITTED isolation consideration | Grok | ❌ | Add to coding_standards |

---

## SUMMARY OF GAPS

### CRITICAL — Decisions needed from Chris before coding:
1. **POS Invoice vs Sales Invoice** — In v16, POS creates POS Invoices by default, not Sales Invoices. Which does Hamilton use? This affects multiple DocType links.
2. **Float carryover** — Does the $200 float stay in the till and carry to next shift, or does it get dropped and physically replenished? This affects Shift Record schema and cash math.
3. **Tier unavailable after payment** — If guest pays for Deluxe but all Deluxe rooms are Dirty, what happens? Refund? Upgrade? Operator selects from available tier?
4. **Split tender** — If guest pays part cash, part card, does the system treat this as cash + card payment? Which triggers asset assignment?

### SCHEMA ADDITIONS needed:
5. member_id should be Link to Customer (not Data) — forward compat
6. hamilton_pricing_rule_override (Data) on Item — Under 25 trigger
7. venue_session link on Asset Status Log — traceability
8. grace_minutes + assignment_timeout_minutes on Hamilton Settings
9. variance_amount (Currency) on Cash Reconciliation
10. opening_float_declared_by on Shift Record
11. printer_label_template_name on Hamilton Settings
12. POS Profile link on Venue Session (Gemini)
13. naming_series defined on every DocType

### CODING STANDARDS additions needed:
14. FOR NO KEY UPDATE (not FOR UPDATE) in v16
15. v16 POS is Vue.js SPA — extensions must be loosely coupled
16. v16 uses pos_controller events (changed from v15)
17. Whitelisted methods required on Venue Asset: mark_vacant, mark_clean, set_out_of_service, return_to_service
18. Frontend retry logic on concurrency failures
19. Redis lock: 15s TTL, UUID token, Lua atomic release
20. Consistent lock ordering when locking multiple assets
21. API whitelist methods must verify role server-side
22. Lock sections = validate + save ONLY (no I/O, printing, email inside)

### BUSINESS LOGIC additions needed:
23. system_expected calculation method (deterministic, freeze point)
24. Refunds/credits affect reconciliation math — define how
25. Comp admissions must not affect cash totals in reconciliation
26. Variance workflow — what happens after a flag? Investigation process?
27. Refund auto-releases asset (H8/H9 test cases)

### PHASE 0 CHECKLIST additions:
28. Hamilton Desk/Workspace as Phase 0 deliverable
29. naming_series on every DocType
30. All Venue Asset whitelisted methods in Phase 0

