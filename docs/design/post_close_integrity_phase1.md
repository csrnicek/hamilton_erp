# Post-Close Orphan-Invoice Integrity Check — Phase 1 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 1-BLOCKER
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #34), informed by Phase A research (G-023 — Sales Invoice creation skipped during POS Close, silent failure mode), G-010 (close timestamp off-by-one), and G-030 (invoice number gaps on draft deletion)
**Implementation status today:** No daily integrity check exists. The cart's `submit_retail_sale` writes Sales Invoices directly with `is_pos=1, update_stock=1`, bypassing the typical "POS Invoice → consolidated Sales Invoice" two-step ERPNext pattern. But the end-of-shift cash drop flow (build spec §7.5 step 5) does invoke a background POS Closing Entry that consolidates POS Invoices. If that consolidation step fails silently — the documented G-023 failure mode — a night's worth of sales activity has no consolidated SI, no GL posting, no P&L line.

---

## Why this document exists

This is the design intent for Hamilton's smallest Phase 1 BLOCKER but its highest blast radius. The implementation is tiny — one scheduled job, one alert, one extra reconciliation field. The audit value is enormous — a single silent failure during a busy night makes that night's revenue invisible to the books until manual review weeks later, when bank deposits and sales totals fail to reconcile.

The document captures three things: (1) what failure modes the integrity check defends against (G-023, G-010, G-030 each contribute), (2) why a daily scheduled check is the right cadence (not per-transaction, not weekly), and (3) what the alert payload contains so the operator/manager can act on it.

If a future implementer thinks "this is just a `frappe.get_all` query, why does it need a design doc" — re-read §3. The query shape is trivial; the recovery semantics are not. Without a documented recovery path, the alert fires and nobody knows what to do.

---

## 1. Failure modes this guard catches

### G-023 — Silent skip during POS Close consolidation

POS Closing Entry runs a background job to create the consolidated Sales Invoice. The job can fail silently (exception swallowed, Redis queue timeout, worker process killed). The parent POS Closing Entry submits successfully. Looks like a clean close from the operator's perspective. But the consolidated Sales Invoice doesn't exist. POS Invoices are marked as `consolidated_invoice = NULL` (or empty string) and `status = "Submitted"` — they're orphans.

GL impact: the per-transaction POS Invoice posts (revenue, tax, payment) happened at sale time. The consolidation typically creates a single Sales Invoice that mirrors the same posting but at the company-level. If consolidation skips, the per-transaction posts remain — so the GL might be partly correct — but reporting layers that aggregate by Sales Invoice (not POS Invoice) miss this revenue. Bank reconciliation against ERPNext's Sales Invoice list won't find the matching record.

Hamilton's exposure: the cart `submit_retail_sale` posts directly as Sales Invoice (not POS Invoice), bypassing G-023's most-direct trigger. But end-of-shift consolidation may still run and may still skip. Plus, future flows (refunds, voids, comps issued via Comp Admission Log) may take different paths through ERPNext's POS layer.

### G-010 — Close timestamp off-by-one

POS Closing Entry's time-range filter excludes invoices created at exactly the closing timestamp. Such invoices remain unconsolidated for that closing entry AND for the next shift's opening entry (which starts after the prior close). Permanently orphaned.

Likelihood at Hamilton: low (probability of exact-second collision is small at single-operator volume). But end-of-shift is the highest-volume moment of the day; collisions concentrate there.

### G-030 — Invoice number gaps on draft deletion

Frappe naming series increments on document creation, not submission. A draft created and then cancelled-deleted leaves a gap in the sequence. While not strictly an orphan-invoice problem, the gap detection logic is the same shape — surface unexpected sequence breaks for review.

Hamilton's exposure: medium. CRA doesn't strictly require contiguous sequences for small businesses, but the audit-readiness defense is to catch and explain gaps before an audit asks about them.

### Other latent failure modes

- **Stock ledger fail-after-SI-submit** — stock decrement fails with a database error after SI is submitted; SI says "submitted" but stock is wrong.
- **Hooks raise post-submit** — Hamilton's `on_sales_invoice_submit` hook (api.py:14) creates Venue Sessions; if it raises after SI submit, SI exists but session doesn't.
- **Concurrent submit collision** — two operators on two tablets submit at near-same time; one races ahead and the other's transaction goes into a partial state.

The integrity check, designed properly, surfaces all of the above as variants of the same audit pattern.

---

## 2. The integrity check — what it does

### The decision

A **daily scheduled job** runs at 4 AM venue-local-time (between shifts), executes a small set of queries against the prior day's POS / Sales Invoice activity, and emits an alert (visible to manager + admin) for any anomaly found.

### Queries to run

```python
# Query 1: orphaned POS Invoices (G-023 primary defense)
orphans = frappe.get_all("POS Invoice", filters={
    "creation": [">=", shift_window_start],
    "creation": ["<", today_4am],
    "status": "Submitted",
    "consolidated_invoice": ["in", ["", None]],
})

# Query 2: pre-close exact-timestamp matches (G-010)
# For each POS Closing Entry in the prior day, find any POS Invoice with
# posting_time = closing_time that is NOT in the closing entry's invoice list.
edge_cases = ...  # detailed query

# Query 3: naming series gaps (G-030)
# Find sequence breaks in HAMILTON-INVOICE naming for the prior day.
gaps = ...  # detailed query

# Query 4: stock-vs-SI mismatch (latent failure modes)
# For each Sales Invoice in the prior day, verify stock ledger entries
# exist matching the SI's items. Flag mismatches.
stock_mismatches = ...  # detailed query

# Query 5: SI-vs-VenueSession mismatch (Hamilton-specific)
# For each admission-item Sales Invoice in the prior day, verify a
# matching Venue Session exists. Hamilton's on_sales_invoice_submit hook
# should have created it; mismatches indicate hook failure.
session_mismatches = ...  # detailed query
```

Each query is bounded by the prior day's window. The job runs once daily (4 AM venue-local), checks the 24-hour window ending at the start of today's first shift.

### Alert payload

When any query returns rows, an `Integrity Alert` record is created with:
- `alert_date` (the day being checked)
- `alert_type` (orphaned_invoice / timestamp_edge / sequence_gap / stock_mismatch / session_mismatch)
- `affected_records` (Table — list of POS Invoice / Sales Invoice / sequence numbers)
- `severity` (HIGH for orphans, MEDIUM for sequence gaps, etc.)
- `recovery_path` (free text — the specific runbook step to take)
- `acknowledged_by` (User, set when manager reviews)
- `acknowledged_timestamp`
- `resolution_notes`

The alert is visible to Hamilton Manager + Hamilton Admin. Frappe desk shows a notification badge until acknowledged.

### Why daily, not per-transaction

Per-transaction integrity checks would slow down the cart and create false alarms (a check that fires before a hook completes is racing the system it's checking). Daily is the right cadence because:
- Most failure modes manifest at the shift boundary (consolidation, stock ledger, etc.).
- A 24-hour delay between failure and detection is acceptable — failures don't propagate further within a day.
- The daily aggregate gives manager review a coherent unit of work.

### Why 4 AM (and venue-local)

Between shifts. After the prior day's last close-out is committed (typically by midnight). Before the morning shift's first transaction (typically 8-10 AM). 4 AM venue-local handles all timezones cleanly.

For Hamilton (Eastern), 4 AM EST. For DC (Eastern), same. For Dallas (Central), 4 AM CST. The job uses `frappe.utils.get_user_time_zone` (or venue-attached timezone) to compute "yesterday."

---

## 3. Recovery semantics — what to do when alert fires

### The decision

Each `alert_type` has a documented recovery path. Manager opens the alert, reads the recovery instructions, executes them, marks the alert acknowledged with resolution notes.

### Recovery paths by alert type

| Alert type | Recovery path |
|---|---|
| `orphaned_invoice` | Manager creates a manual Sales Invoice referencing the orphan POS Invoice, posts it, links the original POS Invoice's `consolidated_invoice` field. (Phase 1.5 add: a one-click "consolidate this orphan" button.) |
| `timestamp_edge` | Manager submits the unconsolidated invoice via a one-off journal entry, OR re-runs POS Closing Entry's consolidation logic for that specific invoice. Documented in `RUNBOOK.md` §X. |
| `sequence_gap` | Manager investigates the gap (was a draft deleted? Did a transaction error?). If explained, marks acknowledged with note. If unexplained, escalates to Chris for compliance review. |
| `stock_mismatch` | Manager creates a manual Stock Reconciliation entry for the affected item. Investigates root cause (concurrent operations? hook failure?). |
| `session_mismatch` | Manager creates a Venue Session manually for the affected admission Sales Invoice. Investigates why the hook failed (look at error log around SI's creation timestamp). |

### Why explicit recovery paths matter

An alert with no documented recovery is a stress trigger for the manager and a "we'll figure it out later" situation that doesn't get figured out. Explicit recovery paths convert each alert from "investigate" to "execute step 1, 2, 3."

The recovery paths above are starter content. Phase 1 implementer should validate each path against actual ERPNext mechanics during build; Phase 1.5 should make some recovery paths one-click (consolidating an orphan especially).

### What if recovery doesn't work

Each alert type has an "escalate to Chris" tier. Recovery instructions explicitly include the escalation step at the bottom: "If the above doesn't resolve, page Chris with the alert ID." This is the same pattern as `RUNBOOK.md` §7.1's "page Chris immediately" for blind-cash invariant violations.

---

## 4. Alert visibility — manager + admin only

### The decision

Integrity alerts are visible to Hamilton Manager + Hamilton Admin roles. NOT visible to Hamilton Operator. Reasoning:

1. **Operator action is not the recovery path.** Recovery requires Frappe-desk access (which operators don't have per `permissions_matrix.md`) and accounting judgment (which operators don't have by role).

2. **Operator cannot fix orphan invoices anyway.** The fix is a manual SI creation by manager. Showing the alert to operator would just be informational — and informational alerts get tuned out.

3. **Operator could be the source of the failure.** If the operator's session has caused (or been involved in) the orphan, surfacing the alert to them is a tip-off if there's any malicious behavior. Manager investigates blindly.

### Alert delivery channels

- **Frappe desk notification badge** for managers logged in.
- **Email to manager + admin** at alert creation time (configurable per venue).
- **Manager dashboard shows alert count**, with drill-down.
- **Phase 2 add:** SMS to admin if alert remains unacknowledged for > 24 hours (escalation tier).

---

## 5. Operational rhythm — how managers consume alerts

### Daily morning workflow

1. Manager arrives ~8 AM. Logs into Frappe desk.
2. Notification badge shows "1 Integrity Alert (HIGH)."
3. Manager opens the alert. Reads alert_type and affected_records.
4. Manager reads recovery_path text.
5. Manager executes recovery (follows runbook step or creates a one-off entry).
6. Manager writes resolution_notes ("Recovered orphan POS-2026-04-30-INV-0023 via manual SI creation; root cause = Redis queue worker restart at 11:47 PM").
7. Manager marks alert acknowledged. Notification clears.

### Pattern of zero alerts

Most days, no alerts fire. The integrity check job runs, finds nothing, no alert is created. Manager sees no notification. This is correct.

If alerts fire frequently (more than 1 per week), it indicates a systemic issue — bugs in Hamilton's hooks, infrastructure instability, or upstream ERPNext bugs (R-010 polish-wave issues like #54183, #50787). Manager reports systemic patterns to Chris.

### Pattern of un-acknowledged alerts

If an alert sits unacknowledged for > 24 hours, Phase 2 SMS escalation fires to admin. After 72 hours unacknowledged, the audit-trail itself is a problem (something is HIGH severity and nobody is acting on it).

---

## 6. What this is NOT

- **Not a substitute for cash reconciliation.** Cash reconciliation runs per-shift; integrity check runs per-day. They catch different failure modes.
- **Not a real-time monitor.** Failures can persist up to 24 hours before detection. For real-time monitoring, separate Tier 0 monitoring layer is needed (Phase 2+).
- **Not an auto-recovery system.** It detects and surfaces; manager executes recovery. Auto-recovery is dangerous — bad fix code can compound the failure.
- **Not a substitute for testing.** It catches production failures the test suite missed. Both layers are needed.
- **Not a tax remediation tool.** If the integrity check finds revenue gaps from past months, those need accountant + tax-professional input, not just runbook steps.

---

## 7. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Exact recovery scripts per alert type | Starter content in §3 | Phase 1 implementer | Validate against ERPNext mechanics during build; refine into runbook |
| One-click "consolidate orphan" UI | Deferred to Phase 1.5 | Phase 1.5 implementer | Phase 1 ships with manual SI creation |
| SMS escalation for unacknowledged alerts | Deferred to Phase 2 | Phase 2 implementer | Pairs with override-service SMS infrastructure |
| Tier 0 real-time monitoring | Deferred to Phase 2+ | Phase 2 implementer | Separate from this daily check |
| Pattern detection across days | Deferred to Phase 2 | Phase 2 implementer | Aggregate alerts to surface systemic issues |
| Cross-venue admin dashboard | Deferred to Phase 3 | Phase 3 implementer | When ANVIL multi-venue |
| Auto-recovery for safe alert types | Deferred indefinitely | Risky; manager judgment is the safety net | Maybe never |
| DEC for integrity-check-cadence | Deferred | Phase 2 implementer | DEC-NNN: daily-at-4AM is canonical |
| Email template per alert type | Deferred to Phase 1.5 | Phase 1.5 implementer | Default text in Phase 1 |
| Per-venue alert routing rules | Deferred to Phase 2 | Multi-venue rollout | Hamilton manager vs Philadelphia manager — different recipients |

---

## 8. Browser test plan

1. **Happy day — no alerts.** Run the integrity job after a normal day. Zero `Integrity Alert` records created. Notification badge is clear.
2. **Orphan invoice triggers alert.** Manually create a POS Invoice with `status="Submitted"` and `consolidated_invoice=""`. Run the integrity job. One `Integrity Alert` record created with type=orphaned_invoice. Affected records list contains the orphan.
3. **Sequence gap triggers alert.** Create POS Invoice INV-001, INV-002, INV-004 (skip INV-003). Run integrity job. Alert with type=sequence_gap fires.
4. **Stock mismatch triggers alert.** Create Sales Invoice for towel; manually delete the corresponding Stock Ledger Entry. Run integrity job. Alert with type=stock_mismatch fires.
5. **Session mismatch triggers alert.** Create admission Sales Invoice; manually delete the corresponding Venue Session. Run integrity job. Alert with type=session_mismatch fires.
6. **Alert visible to manager only.** Hamilton Operator user has no notification badge for the alert. Hamilton Manager does.
7. **Alert acknowledgement clears notification.** Manager opens alert, writes resolution notes, marks acknowledged. Notification badge clears.
8. **Alert email sent at creation.** When alert is created, email is sent to manager + admin. Verify email content includes alert_type, affected_records, recovery_path.
9. **Daily job runs at 4 AM venue-local.** Schedule the job. Verify it runs at 4 AM EST for Hamilton, 4 AM CST for Dallas (when Dallas opens).
10. **Multiple alert types in one run.** Seed orphan + gap + mismatch in the same day. Run job. Three separate alert records created (one per type).
11. **Alert with affected_records list rendered.** UI for viewing alert shows affected records as a clickable list — clicking a row navigates to the underlying SI / POS Invoice / etc.
12. **Resolution notes mandatory.** Attempt to mark alert acknowledged without filling resolution_notes. System throws: "Resolution notes required."

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Integrity check is the system-side audit complementing operator/manager blind reconciliation.
- **DEC-019** — Three-layer locking on asset state changes (`docs/coding_standards.md` §13). Integrity check catches lock-failure side effects.

### Phase A research
- **G-023** — Silent skip during POS Close consolidation. Primary defense.
- **G-010** — Close timestamp off-by-one. Secondary defense.
- **G-030** — Invoice number gaps. Tertiary defense.
- **R-010** — ERPNext v16 polish-wave fix cadence. Open issues #54183 and #50787 will surface as integrity alerts when refunds ship in Phase 3 if upstream isn't yet patched.

### Risk register
- **R-006** — Comp Admission Log permlevel. Integrity check's session_mismatch type catches when comp's session-creation hook fails.
- **R-010** — ERPNext upstream bugs. Integrity check is the structural defense against upstream issues that aren't yet fixed.

### Existing code
- **`hamilton_erp/api.py:14`** — `on_sales_invoice_submit` hook creates Venue Sessions. Session-mismatch alert catches hook failures.
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` writes Sales Invoices. Stock-mismatch alert catches stock ledger inconsistencies.
- **`hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py`** — cash reconciliation provides per-shift integrity at cash level; this integrity check provides per-day integrity at SI level. Both layers needed.

### Other design intent docs
- **`docs/design/cash_reconciliation_phase3.md`** — sister integrity layer. Cash reconciliation operates on the cash side per-shift; this integrity check operates on the SI side per-day.
- **`docs/design/refunds_phase2.md`** — refunds are a likely future source of orphan invoices (R-010 issues #54183, #50787). The integrity check is the safety net.
- **`docs/design/voids_phase1.md`** — voids create cancelled SIs; integrity check verifies cancellation completed cleanly.

### Build spec
- `docs/hamilton_erp_build_specification.md` §7.5 — end-of-shift creates POS Closing Entry in background. This is the trigger event for G-023 failures.
- `docs/hamilton_erp_build_specification.md` §11 (Audit Logging) — this integrity check is one form of audit infrastructure complementing the document versioning.

### Operations
- `docs/RUNBOOK.md` — Phase 1 implementer adds runbook entries for each alert type's recovery path.

---

## Notes for the Phase 1 implementer

1. Read this document. Then read `RUNBOOK.md` (existing operational handling patterns).
2. Build the `Integrity Alert` DocType. Field set per §2's "Alert payload."
3. Build the daily scheduled job in `hamilton_erp/scheduled_tasks/integrity_check.py`. Register in `hooks.py`'s `scheduler_events` → `daily` (or use `cron` for the 4 AM venue-local timing).
4. Implement the five queries in §2. Start with Query 1 (orphan invoices) — it's the highest-blast-radius failure mode.
5. Email delivery uses Frappe's `frappe.sendmail`. Recipients = users with Hamilton Manager + Hamilton Admin roles.
6. Recovery paths in §3 are starter content. Validate each against actual ERPNext mechanics during build. Refine into `RUNBOOK.md` entries.
7. Test the cron timing carefully. Frappe's scheduled events run UTC by default; Hamilton needs venue-local 4 AM. Consider running every hour and checking "is_4am_venue_local" inside the job.
8. Acknowledgement workflow: alert.acknowledged_by + acknowledged_timestamp + resolution_notes. Mandatory resolution_notes per Test 12.
9. Run all 12 browser tests before merging.
10. Document the alert types and recovery paths prominently in `RUNBOOK.md` so manager has them at hand.
11. Implementation effort: small. Day or two. The audit value is large.

This is the cheapest BLOCKER to close. Ship it early.
