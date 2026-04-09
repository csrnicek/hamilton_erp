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
| v16 POS is Vue.js SPA — need loosely coupled extensions | Gemini | ✅ | Added to coding_standards.md §2.9 |
| v16 POS uses pos_controller events (changed from v15) | Grok | ✅ | Added to coding_standards.md §2.10 |
| Payment before assignment correct | All | ✅ DEC-002 | None |
| Edge case: all Deluxe rooms Dirty after guest pays Deluxe | Gemini/ChatGPT | ✅ DEC-028 | Operator checks board before ringing — no system change needed |
| Edge case: split tender (cash+card) — which triggers assignment? | Grok/ChatGPT | ✅ DEC-029 | Full payment confirmed → assignment triggers regardless of mix |
| Edge case: refund after assignment must auto-release asset | Grok/ChatGPT | ✅ DEC-051 | POS Return hook auto-releases asset Occupied→Dirty |
| Edge case: network failure after payment, before assignment | Grok | ⚠️ DEC-020 partial | Needs explicit recovery steps |
| One DocType for rooms/lockers correct | All | ✅ DEC-003 | None |
| Use POS Profile user assignment per operator | ChatGPT | ✅ | Add to Phase 2 ERPNext config — developer task |
| Frappe Version + Activity Log instead of custom Asset Status Log | Grok | ✅ | Keep custom Asset Status Log — richer operational data needed |
| Use frappe.printing + print_format instead of raw backend API | Grok | ✅ | Added to Phase 3 label printer considerations |

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
| naming_series on every DocType | Grok | ✅ | Added to build_phases.md Phase 0 |

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
| member_id should be Link to Customer, not Data | Gemini | ✅ | Fixed in current_state.md Bucket 1 |
| POS Profile link on Venue Session | Gemini | ✅ DEC-032 | Not needed — single terminal always |
| session_number (auto-increment display ID) | ChatGPT | ✅ DEC-033 | Added to schema |
| checkin_rate_gross, checkin_rate_net, tax_amount | ChatGPT | ✅ DEC-034 | Not added — data lives on Sales Invoice |
| payment_status_snapshot | ChatGPT | ✅ DEC-035 | Not added — lives on Sales Invoice |
| refund_status | ChatGPT | ✅ DEC-036 | Not added — session status + Sales Invoice covers it |
| created_from_pos_invoice vs sales_invoice clarity | ChatGPT | ✅ DEC-025 | Resolved — Sales Invoice in POS mode |

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
| resolved_by, resolution_status | ChatGPT | ✅ DEC-041 | Added to schema now, workflow deferred to Phase 3 |
| direct shift_record link | ChatGPT | ✅ DEC-042 | Added — developer decision, no input needed from Chris |

### Asset Status Log
| Field | Reviewer | Status | Action |
|---|---|---|---|
| venue_asset, status fields, reason, operator | All | ✅ Current state | None |
| venue_session link | ChatGPT | ✅ | Added to Asset Status Log in Bucket 1 |
| source_doctype / source_name | ChatGPT | ✅ | Skip — venue_session + venue_asset links already provide traceability |
| autoname: autoincrement | Grok | ✅ | Added to Asset Status Log in Bucket 1 |

### Shift Record
| Field | Reviewer | Status | Action |
|---|---|---|---|
| pos_profile, pos_opening_entry, pos_closing_entry | Grok/ChatGPT | ✅ Current state | None |
| board_corrections as child table | ChatGPT/Grok | ✅ DEC-024 | None |
| opening_float_declared_by | ChatGPT | ✅ DEC-043 | Skipped — operator field covers it, single-operator venue |
| closing_state | ChatGPT | ✅ | Covered by status Open/Closed on Shift Record |
| reconciliation_status | ChatGPT | ✅ DEC-044 | Added to Shift Record |

### Comp Admission Log
| Field | Reviewer | Status | Action |
|---|---|---|---|
| admission_item, comp_value, reason fields | All | ✅ Current state | None |
| approved_by | ChatGPT | ✅ DEC-045 | Skipped — reason_category + reason_note already covers why it was free |

### Hamilton Settings
| Field | Reviewer | Status | Action |
|---|---|---|---|
| float_amount, stay_duration, printer settings | All | ✅ Current state | None |
| grace_minutes | ChatGPT | ✅ DEC-046 | Added to Hamilton Settings |
| assignment_timeout_minutes | ChatGPT | ✅ DEC-046 | Added to Hamilton Settings |
| oos_reason_master / default values | ChatGPT | ✅ | Skip — free text reason field is sufficient for Hamilton |
| printer_label_template_name | ChatGPT | ✅ DEC-046 | Added to Hamilton Settings |

### Custom Fields on Standard DocTypes
| Field | Reviewer | Status | Action |
|---|---|---|---|
| hamilton_is_admission, hamilton_asset_category/tier, hamilton_is_comp | All | ✅ | None |
| hamilton_shift_record on Sales Invoice | Grok/ChatGPT | ✅ Current state | None |
| hamilton_pricing_rule_override on Item | Grok | ✅ DEC-047 | Skipped — hamilton_is_admission already sufficient |
| hamilton_requires_asset_assignment on Item | ChatGPT | ✅ DEC-047 | Duplicate of hamilton_is_admission — skipped |

---

## C. PRICING RULES

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Non-stacking needs custom code | All | ✅ DEC-017 | None |
| Under 25 needs custom POS button | All | ✅ DEC-017 | None |
| Locker Special supported in v16 with day/time | Grok | ✅ DEC-014 | None |
| Priority setting for Locker Special vs Under 25 | Gemini | ✅ | Added to ERPNext config — Locker Special priority higher than Under 25 |
| HST-inclusive uses Company-level Tax Template | Grok/ChatGPT | ✅ DEC-018 | None |

---

## D. CASH CONTROL

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Multi-layer permissions needed | All | ✅ DEC-021 | None |
| Float carryover: does $200 stay or get dropped? | Gemini/ChatGPT | ✅ DEC-027 | Float stays in till, operator sets aside before final drop |
| system_expected calculation method | Grok/ChatGPT | ✅ DEC-049 | Cash sales in drop period only. Float confirmed separately at start/end of shift. |
| system_expected freezing — when exactly? | ChatGPT | ✅ DEC-049 | Frozen at time of drop submission — all invoices up to that timestamp |
| Refunds after drop affect reconciliation | Grok/ChatGPT | ✅ DEC-051 | Refund reduces cash total for that period in reconciliation |
| Comp admissions must NOT affect cash totals | Grok | ✅ DEC-052 | Already handled — $0 comp invoices contribute $0 to cash formula |
| Variance workflow — what happens after flag? | ChatGPT | ✅ DEC-040 | Deferred to Phase 3 |

---

## E. SECURITY & PERMISSIONS

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Three roles: Operator, Manager, Admin | ChatGPT/Gemini | ✅ DEC-022 | None |
| Hamilton Auditor role | Gemini | ✅ | Not needed — Hamilton Admin role covers it (DEC-022) |
| API bypass: whitelist checks must verify role server-side | Gemini/ChatGPT | ✅ | Already in coding_standards.md §6.2 |
| Reports/pages/field masking | All | ✅ DEC-021 | None |

---

## F. FORWARD COMPATIBILITY

| Point | Reviewer | Status | Action |
|---|---|---|---|
| V5.4 null fields sufficient | Grok/Gemini | ✅ DEC-007 | None |
| member_id as Link to Customer, not Data | Gemini | ✅ | Fixed in current_state.md Bucket 1 |
| Customer link on Venue Session | Both | ✅ Current state | None |
| Philadelphia: additive only | Grok | ✅ | None |
| Asset Board UI should be card-based for future member photo | Gemini | ✅ | Added to Phase 1 design notes |

---

## G. GENERAL / PHASE 0 ITEMS

| Point | Reviewer | Status | Action |
|---|---|---|---|
| Concurrency #1 risk | All | ✅ DEC-019 | None |
| Hybrid locking: Redis + MariaDB + version | Grok | ✅ DEC-019 | None |
| FOR NO KEY UPDATE (not FOR UPDATE) in v16 | Grok | ✅ | Added to coding_standards.md §2.11 |
| naming_series and autoname required on every DocType | Grok | ✅ | Added to build_phases.md Phase 0 |
| Hamilton Desk/Workspace as Phase 0 deliverable | Gemini | ✅ | Added to build_phases.md Phase 0 |
| Daily cleanup job for orphaned sessions | All | ✅ DEC-020 | None |
| Frontend retry on concurrency failure | Grok | ✅ | Added to coding_standards.md §13.5 |
| POS Invoice vs Sales Invoice — which does Hamilton use? | ChatGPT/Grok | ✅ DEC-025 | Sales Invoice in POS mode |
| calculate_system_expected method on Shift Record | Grok | ✅ DEC-049 | Method defined — sum cash invoices in drop period |
| Bulk Mark All Clean | Gemini | ✅ DEC-023 | None |
| board_corrections as child table | ChatGPT/Grok | ✅ DEC-024 | None |
| Label printer cloud-to-local risk (QZ Tray) | Gemini | ✅ | Added to Phase 3 risks — evaluate QZ Tray if cloud→local printing is unreliable |
| Asset board card-based design for future Philadelphia | Gemini | ✅ | Added to Phase 1 design notes — card-based tiles support future member photo |
| Whitelisted methods required on Venue Asset | Grok | ✅ | Added to build_phases.md Phase 0 |
| Lock TTL = 15 seconds, UUID token, Lua atomic release | Grok | ✅ | Added to coding_standards.md §13.2 |
| Consistent lock ordering for multiple asset ops | Grok | ✅ | Added to coding_standards.md §13.4 |
| MariaDB READ COMMITTED isolation consideration | Grok | ✅ | Added to coding_standards.md §13.6 |

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

