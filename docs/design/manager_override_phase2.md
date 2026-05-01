# Manager Override — Phase 2 Design Intent

**Status:** Design intent — not implementation spec
**Phase:** Phase 2 (activates when `anvil_tablet_count > 1` triggers multi-operator)
**Authored:** 2026-05-01
**Source:** Phase B audit (`docs/audits/pos_business_process_gap_audit.md` process #8), informed by Phase A research (G-028 no manager-override workflow), `docs/hamilton_erp_build_specification.md` §8 (combined operator/manager permissions today), and the recurring need from refund / void / comp / discount design intents that all want a graduated control gate
**Implementation status today:** §8.2 of build spec gives Hamilton Operator the same permissions as Hamilton Manager for all operational actions (combined "Front + Manager" role). The Hamilton Manager role exists separately for cash reconciliation only (build spec §7.7). No graduated threshold control. No PIN dialog. No second-factor authorization. V5.4 §15 (manager overrides and pattern detection) is in the deferred list (build spec §14).

---

## Why this document exists

Manager override is the cross-cutting concern shared by every "I changed my mind / something needs special approval" flow: refunds (`refunds_phase2.md`), voids (`voids_phase1.md`), comps (Comp Admission Log workflow), discounts, OOS marking on revenue-impacting assets, price overrides, after-hours access, etc. Building a separate authorization gate for each flow would result in inconsistent UX, duplicate code, and gaps where one flow forgets to enforce a check.

Hamilton's solo-operator phase (today) doesn't need this. The operator is the manager. There's nobody to defer to. But solo-operator is a specific, time-limited configuration, not a forever-architecture. The day Hamilton hires a second operator, every "operator can self-approve unlimited refunds" path is a fraud surface. DC opens with multi-operator overlapping shifts from day 1; manager override is mandatory there.

The document captures the reasoning for a single shared override service that all caller flows consume. Each design choice is non-obvious: thresholds are venue-configurable and per-action, PINs are time-windowed and not stored long-term, audit logs distinguish self-authorized from delegated-authorized events, and the system exposes a manager dashboard for pattern detection that is the structural defense against subtle abuse.

If a future implementer thinks "let me just add a hardcoded $100 threshold to refunds" — re-read §3. Per-action venue-configured thresholds + a single override service is the correct architecture; ad-hoc threshold logic produces a system that drifts and silently fails to enforce.

---

## 1. The override service abstraction

### The decision

A **single shared `override.request(action, amount, context, requested_by)` service** evaluates whether the action is permitted at the requested amount and returns either:
- `auto_approved` (operator self-authorized; logs as "self-authorized")
- `pin_required` (UI prompts for PIN)
- `pin_authorized` (PIN entered, validated; action proceeds, logs as "PIN-authorized")
- `remote_approval_required` (district manager out-of-band)
- `denied` (action exceeds even district approval; structural block)

All caller flows (refund, void, comp, discount, OOS, price override) call this service. None implement their own threshold logic.

### Why one service

Three reasons:

1. **Consistency.** Every caller flow gets the same authorization UX. Operator learns one PIN dialog, not seven different ones. Audit log uses one schema.

2. **Defense against drift.** When thresholds change (venue raises refund threshold from $50 to $100), the change happens in one place. No risk of refund flow updating but void flow staying at the old threshold.

3. **Single-source-of-truth audit.** All authorization events live in one Override Log table. Pattern detection (§5) reads one stream. Manager dashboard renders one feed.

### Service interface (Phase 2 implementation contract)

```python
def request(
    action: str,             # "refund", "void", "comp", "discount", etc.
    amount: float,           # the dollar value being authorized (refund amount, comp value, etc.)
    context: dict,           # caller-flow specific (original_si, asset, customer, etc.)
    requested_by: str,       # frappe.session.user
) -> dict:
    """Returns authorization decision. Caller flow uses decision to proceed or block."""
```

The function reads:
- Venue's Override Profile for the requested action's thresholds.
- Current operator's role and authorization state.
- Recent override history (rate-limit checks, see §5).

It writes (synchronously, before returning) an Override Log record capturing the request. Whether approved or denied, the request is logged. This is the audit invariant.

---

## 2. Three tiers of authorization

### Tier 1 — Self-authorized (operator only)

Operator can authorize an action below threshold A without manager intervention. The system logs the operator as "self-authorized." Audit trail captures the timestamp; no PIN entered.

Use cases: small refunds, low-value comps, minor discount tweaks. The threshold A is venue-configurable and per-action — Hamilton's defaults (when DC opens):

| Action | Threshold A (self) | Threshold B (manager) | Threshold C (district) |
|---|---|---|---|
| Refund | $50 | $200 | $500 |
| Void | $0 (any void = manager) | $200 | $500 |
| Comp | $0 (any comp = manager) | $100 | $500 |
| Discount | 10% | 25% | 50% |
| OOS revenue-impact | n/a | always-manager | always-district above $1000/day |
| Price override | $0 (always-manager) | $50 | n/a |

Hamilton's solo-operator phase: threshold A = effectively-infinite (operator self-approves all). The thresholds activate when `anvil_tablet_count > 1` is set on the venue profile.

### Tier 2 — Manager PIN at terminal

Above threshold A, the operator initiates the action; UI prompts "Manager approval required: enter PIN." A user with Hamilton Manager role (or higher) types their PIN. PIN is validated against `User.password` (using Frappe's password verification). On success, action proceeds; Override Log captures both the requesting operator and the approving manager.

Why "at terminal": the PIN is entered on the same tablet where the operator initiated the action. Manager must be physically present at the venue. Cannot be a phone-based remote approval (that's Tier 3).

### Tier 3 — District manager remote approve

Above threshold B, even on-venue manager cannot approve. UI prompts "District approval required: SMS sent." The district manager (Hamilton Admin role at minimum) receives an SMS with a one-time code, types it back into the manager's phone, manager relays the code to the terminal. The terminal validates the code against the request.

Phase 3 refinement: replace the SMS relay with a direct admin-app push notification + tap-to-approve. SMS is the Phase 2 minimum; the bottleneck is reliable.

### Why graduated thresholds

Three tiers reflect three different fraud profiles:
- **Tier 1 (operator self):** typo fixes and small-customer-service decisions. Volume is high; per-event impact is low. Self-authorization is fine.
- **Tier 2 (manager PIN):** decisions that affect a meaningful chunk of one transaction. Volume is medium; per-event impact is meaningful. Requires a second human at the venue.
- **Tier 3 (district):** decisions that affect a meaningful chunk of a day's revenue. Volume is rare; per-event impact is large. Requires out-of-band authorization to defeat manager + operator collusion.

Without tiering: either everything requires manager (kills throughput; manager is a bottleneck) or everything is self-authorized (fraud surface). Tiering matches authorization friction to event impact.

---

## 3. Per-action thresholds — venue-configurable, NOT hardcoded

### The decision

Threshold values live in an **Override Profile** DocType (one per venue). The service reads the profile at request time. Hardcoded defaults in code are the LAST fallback, never the canonical values.

### Why per-venue

Same reasoning as `cash_reconciliation_phase3.md` §3:
1. Regulatory variation (state/province retail rules).
2. Operational variation (DC peak vs Hamilton low-volume → different threshold appropriateness).
3. Theft-experience adaptation (each venue's thresholds tighten or loosen as patterns emerge).

If thresholds are hardcoded, changing them requires a code deploy. Code deploys mean change is friction-laden; venues drift from optimal thresholds.

### Why per-action (within a venue)

A venue's risk profile differs by action. Hamilton might be lenient on refunds ($50 self-approve — refund-required friction is bad customer experience for legitimate complaints) but strict on comps ($0 self-approve — comp fraud is the structural risk because operator can give themselves a free admission disguised as a goodwill gesture).

A single "all overrides" threshold can't capture this. Per-action thresholds let venues tune each control surface to its own risk profile.

### Override Profile schema

```
Override Profile (Phase 2 DocType, linked per venue)
- venue (link to Company)
- refund_self_threshold (Currency)
- refund_manager_threshold (Currency)
- refund_district_threshold (Currency)
- void_self_threshold (Currency)
- void_manager_threshold (Currency)
- ... (one row per action × tier)
- pin_window_seconds (Int, default 300) — how long after PIN entry can subsequent actions reuse it
- high_rate_alert_threshold (Int, default 5) — overrides per shift before manager dashboard alert
```

When a new venue is provisioned, fixtures seed default thresholds; venue manager tunes via Frappe desk. Phase 2 implementer chooses the exact field set.

---

## 4. PIN mechanics

### PIN lifecycle

- Each user with Hamilton Manager+ role has a PIN. PIN is stored as a hashed value (Frappe's standard password handling). Rotated quarterly per `RUNBOOK.md` security cadence.
- PIN entry happens on the requesting operator's terminal — manager walks over, types PIN, walks away.
- After successful PIN entry, the system marks the override as authorized AND opens a 5-minute "PIN-warm" window for subsequent operations by the same operator that fall under the same threshold tier. After the window, next operation requires fresh PIN.
- PIN-warm window is venue-configurable (`pin_window_seconds`, default 300).

### Why a 5-minute warm window

A bursty refund / void / comp at the same minute (correct multiple errors during a busy moment) shouldn't require manager to type PIN N times. One PIN per "session of authorizations" is the natural rhythm.

But the window must be short. Long windows let an operator pretend to ask for one approval and then process a string of fraudulent reversals. 5 minutes is the rough floor — long enough for a manager to step away, short enough that the manager wouldn't reasonably leave for the duration.

### PIN-bypass loophole

Subtle attack: operator builds rapport with manager, accumulates 5-minute trust windows, processes fraudulent transactions toward end of each window when manager isn't watching closely.

Defense: high-rate-alert. Manager dashboard surfaces operators with > N override events per shift. Investigation is expected when threshold crossed. This is the same pattern as void rate detection in `voids_phase1.md` §4.

### PIN entry on a tablet — physical security

Tablet PIN entry is in plain view of the operator. Manager must shield the keypad with their body or use a numeric pad with randomized digit positions. Phase 2 implementer chooses; default is a randomized PIN pad on each entry (defeats shoulder-surfing).

### District manager remote approve — out-of-band

The SMS round-trip is intentional: even if the operator and manager collude, the district manager is out-of-band. The SMS code arrives on the district manager's phone, not the operator's tablet. The district manager sees the request context (action + amount + venue + operator) before typing the code; they have the option to deny and call.

### District manager bypass loophole

Not all venues will use district manager. Single-venue venues, or first-shift-of-the-month edge cases, may operate without district approval available. Defense: `district_required_threshold = infinity` for those venues; manager-PIN handles all events. The district tier is a Phase 3 add for venues that scale to multi-tier hierarchies.

---

## 5. Pattern detection — manager dashboard

### The decision

The override service writes every authorization event to an Override Log. A scheduled job aggregates the log and surfaces patterns to the manager dashboard. This is the structural defense against subtle abuse.

### What patterns to surface

- **High-rate operator:** > N overrides per shift (default 5).
- **Repeat-target customer:** > M overrides involving the same customer in a week (potential collusion).
- **End-of-shift cluster:** disproportionate overrides in last 30 minutes of shift (cash-skim cleanup pattern).
- **Same-action repeat:** > 3 voids OR > 3 refunds in same hour by same operator.
- **Off-hours overrides:** overrides outside venue's normal manager hours.
- **Threshold-edge clustering:** 80%+ of an operator's overrides hover just below a threshold (gaming the system).

Each pattern produces a "Pattern Alert" record visible to manager + admin. Manager dashboard ranks operators by alert count; drill-down shows specific events.

### Why patterns matter more than per-event PIN

A single fraudulent override can slip past PIN (manager not paying attention, manager-collusion, social engineering). Patterns are statistical — over time, fraud creates signal even if individual events look fine. The audit defense is the long-tail aggregation.

This is the same defensive principle as blind cash drop's three-number triangulation (`cash_reconciliation_phase3.md` §1) — multiple imperfect signals together produce a robust signal.

### False positives

Patterns will sometimes fire on legitimate operator behavior (a busy night with many voids, a regular customer with repeated comps). Manager investigates; if false positive, marks the alert as "reviewed — legitimate" with comment. Audit trail captures the dismissal so a pattern of dismissals (manager hand-waving real fraud) is itself detectable.

---

## 6. Hamilton's solo-operator phase — what to do today

### Today (solo operator)

- Override Profile is provisioned for Hamilton with `*_self_threshold = infinity` (operator self-approves all).
- Override Log is still written for every authorization event.
- Manager dashboard exists but has no Pattern Alerts (nothing to compare against).
- The infrastructure is in place; the gates are open.

### Day Hamilton hires its second operator

- Update Override Profile for Hamilton: tighten thresholds to defaults from §2.
- Hamilton Manager role is now meaningful (the second operator is NOT a manager; current operator IS).
- Manager dashboard activates pattern detection.
- Audit Log retroactively shows "self-authorized" events from the solo-operator era — these are correctly logged but unflagged.

### When DC opens

- DC's Override Profile is provisioned with stricter defaults from day 1 (multi-operator from go-live).
- District manager (Chris) gets SMS access wired up.
- DC manager dashboard active from day 1.

This phasing means the override service ships at Phase 1 (infrastructure), activates at Phase 2 (when multi-operator reality requires it), and scales to district control at Phase 3 (when ANVIL multi-venue chain matures).

---

## 7. Open and deferred

| Item | Status | Owner | Notes |
|---|---|---|---|
| Default threshold values per action | TBD final | Chris + ops manager input | §2 table is starter values |
| PIN-warm window default | 300s, venue-configurable | Phase 2 implementer | Tune based on early multi-op feedback |
| District manager SMS gateway | TBD provider | Phase 3 implementer | Twilio / Vonage / built-in Frappe SMS |
| Pattern detection algorithm details | High-level only | Phase 2 implementer | Specific thresholds for each pattern type |
| Tablet PIN-pad design (randomized vs static) | Default randomized | Phase 2 implementer | Shoulder-surfing defense |
| Override receipt printing | Pairs with receipt printer pipeline | Phase 2 implementer | Override events optionally printed for manager-signed log |
| Cross-venue district approval | Phase 3 | Phase 3 implementer | One district manager covering multiple venues |
| DEC formalization for override service | Deferred | Phase 2 implementer | DEC-NNN |
| Migration plan from solo-operator to multi-operator | Phase 2 implementer | When Hamilton hires #2 | Documented runbook step |

---

## 8. Browser test plan (Phase 2)

1. **Tier 1 self-authorize.** Operator initiates $30 refund. Threshold A = $50. UI shows confirmation tap, no PIN. Action completes. Override Log: type=self-authorized.
2. **Tier 2 manager PIN required.** Operator initiates $100 refund. Threshold A = $50, B = $200. UI shows "Manager approval required" + PIN keypad. Wrong PIN entered → reject. Correct PIN entered → action completes. Override Log: type=PIN-authorized, manager=manager_user, operator=op_user.
3. **PIN-warm window reuse.** After Tier 2 PIN, operator initiates second $80 refund within 5 minutes. UI does NOT re-prompt PIN; reuses warm authorization. Override Log captures the reuse.
4. **PIN-warm window expiry.** Operator initiates $80 refund 6 minutes after first PIN. UI re-prompts PIN.
5. **Tier 3 district approve.** Operator initiates $300 refund. Threshold B = $200, C = $500. UI shows "District approval required" + SMS. Code arrives on district manager phone; entered into terminal. Action completes. Override Log captures district_authorizer.
6. **Above all thresholds — denied.** Operator initiates $1000 refund. Threshold C = $500. UI shows "Action exceeds maximum override; create a manual reversal entry." Action denied.
7. **Per-action threshold differs.** Same operator: $50 refund auto-approves; $50 comp requires manager PIN (different threshold table per action).
8. **Override Log captures all events.** After mixed shift (auto-approves + PIN-approves + denials), query Override Log. Verify: all events present, types distinguishable, requesting operator and authorizing manager (where applicable) all captured.
9. **High-rate alert fires.** Operator processes 6 self-authorized refunds in shift (threshold = 5). Pattern Alert created. Manager dashboard shows alert.
10. **End-of-shift cluster alert.** Operator processes 4 voids in last 20 minutes of shift, 0 in first 90% of shift. Pattern Alert: end-of-shift cluster.
11. **Tablet PIN-pad randomized.** PIN entry triggers pad render. Verify digit positions differ between two consecutive entries.
12. **Cross-operator PIN.** Operator A's terminal prompts for PIN. Operator B (also manager-role) walks over and types B's PIN. Override Log records B as authorizer (not A).
13. **Pattern Alert dismissal logged.** Manager reviews alert; marks "reviewed — legitimate" + comment. Audit log captures dismissal. Operator's alert count resets.
14. **Solo-operator (Hamilton today) behaviour.** With `*_self_threshold = infinity`, all override requests auto-approve. Override Log records every event but never prompts PIN. Pattern alerts never fire (no reference points yet).

---

## Cross-references

### Foundational decisions
- **DEC-005** — Blind cash drop replaces standard POS Closing for operators (`docs/review_package.md` line 94). Override service must integrate with blind reconciliation (refunds/voids reduce expected cash via the same mechanism).
- **DEC-016** — Comp Admission reason categories (`docs/review_package.md` line 127). Comps are one consumer of the override service.
- **DEC-038** — Card reconciliation parallels cash reconciliation. Override events apply equally to card-side flows.

### Phase A research
- **G-028** — No native manager-override workflow. This document is the Hamilton response.
- **G-014** — Receipt reprint fraud. Reprint is one of the actions that should consume override service (Phase 2.5).
- **G-015** — No fixed-amount discount in POS. When Hamilton adds discounts, override service governs above-threshold use.

### Risk register
- **R-006** — Comp Admission Log `comp_value` permlevel. Override service captures who authorized comp; permlevel hides amount from operator UI.
- **R-008** — Single-acquirer SPOF. Not directly related but: card-side override events (refund auths) feed the chargeback ratio defense (R-009).

### Existing code
- **`hamilton_erp/api.py:404`** — `submit_retail_sale` is the cart-side entrypoint. Phase 2 override-aware versions of refund / void / comp call into the override service before completing.
- **`hamilton_erp/hamilton_erp/doctype/comp_admission_log/comp_admission_log.json`** — comp DocType already exists; Phase 2 adds override-link field.
- **`docs/permissions_matrix.md`** — Hamilton Manager role definition. Override service reads role assignments to determine PIN-eligibility.

### Other design intent docs
- **`docs/design/refunds_phase2.md`** §4 — refund's manager-PIN gate consumes this service.
- **`docs/design/voids_phase1.md`** §4 — void's manager-PIN gate consumes this service.
- **`docs/design/cash_reconciliation_phase3.md`** — variance investigation may consume override for "manual override of variance flag."
- **`docs/design/tip_pull_phase2.md`** — large tip pulls may consume override.

### Build spec
- `docs/hamilton_erp_build_specification.md` §8.2 (combined operator/manager today) and §14 (V5.4 §15 deferred). This document supersedes the deferral when multi-op activates.

---

## Notes for the Phase 2 implementer

1. Read this document twice. Then read `docs/permissions_matrix.md` (existing role definitions) and the four caller-flow design intents (refunds, voids, comps, tip-pull).
2. Build the Override Profile DocType first — fixtures seed Hamilton's solo-operator-infinite-threshold profile.
3. Build the override service as a single module (`hamilton_erp/services/override.py`). All caller flows import from this module.
4. Implement the three tiers in order: Tier 1 (self-authorized) is the simplest; Tier 2 (manager PIN) requires UI work; Tier 3 (district SMS) requires SMS gateway integration.
5. Override Log is critical — write the schema first, get the audit trail right, then layer the service on top.
6. Manager dashboard is Phase 2.5 — ship Tiers 1–2 + Override Log first; pattern detection follows.
7. Test the PIN-warm window edge cases carefully. The 5-minute boundary is where subtle bugs live.
8. Solo-operator behaviour (Hamilton today) must work with `*_self_threshold = infinity`. The infrastructure is in place; gates are wide open. When Hamilton hires #2, the only change is updating the Override Profile.
9. Implement all 14 browser tests above. Pattern detection tests (9, 10, 13) require seeded data.
10. Document the migration runbook step "Hamilton hires second operator → tighten Override Profile thresholds" in `RUNBOOK.md`.
