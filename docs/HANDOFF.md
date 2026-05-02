# Hamilton ERP — Senior Developer Handoff

**Target audience:** Senior Frappe v16 / ERPNext v16 developer, zero prior context on this project.
**Goal:** Productive contribution within 2 days.
**Written:** 2026-05-01

---

## Table of Contents

1. [What This App Does](#1-what-this-app-does)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [The 9 Custom DocTypes](#3-the-9-custom-doctypes)
4. [The 8 Whitelisted Endpoints](#4-the-8-whitelisted-endpoints)
5. [Hard Rules You Must Know](#5-hard-rules-you-must-know)
6. [Phase 1 BLOCKER Status](#6-phase-1-blocker-status)
7. [Risks to Track](#7-risks-to-track)
8. [Where Design Intent Lives](#8-where-design-intent-lives)
9. [The Most Surprising Things About This Codebase](#9-the-most-surprising-things-about-this-codebase)
10. [Day 1 / Day 2 Onboarding Script](#10-day-1--day-2-onboarding-script)

---

## 1. What This App Does

`hamilton_erp` is a custom Frappe v16 / ERPNext v16 application for Club Hamilton, a men's bathhouse in Hamilton, Ontario, Canada. The app extends standard ERPNext — it never forks core; all extensions go through `hooks.py`, `extend_doctype_class`, fixtures, and whitelisted API methods. The app is live at `hamilton-erp.v.frappe.cloud` and is in active pre-launch development.

**Phase 1** is the current work. It delivers three things: an operator-facing **Asset Board** — a tablet-optimized live grid of all 59 venue assets (26 rooms, 33 lockers) — a **session lifecycle** state machine that tracks each asset through Available → Occupied → Dirty → Available (plus Out of Service from any state), and a **blind cash control** system where operators declare cash without ever seeing expected totals or variance. Every status-changing operation is protected by a three-layer lock (Redis advisory + MariaDB `FOR UPDATE` + optimistic version field). The test suite sits at 306+ passing tests across 14 modules.

**Phase 2 and beyond** adds multi-venue rollout (Philadelphia, DC, Dallas), POS-driven session creation via Sales Invoice, retail catalogue cart, integrated card payments via a processor-abstraction layer (primary + backup per venue, per DEC-064), membership flows, manager override service, and full cash reconciliation. Venue Session already carries 10 forward-compatibility fields for Philadelphia's identity/membership system; they are null at Hamilton today. Phase 2+ is architecturally anticipated but not yet built. Task 38 (multi-venue refactor) is planned but not yet entered in Taskmaster.

---

## 2. Architecture at a Glance

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser — Asset Board (vanilla JS class, ~294 lines)            │
│  Frappe Page: /app/asset-board                                   │
│  Source: hamilton_erp/public/js/asset_board.js                   │
│  CSS:    hamilton_erp/public/css/asset_board.css                 │
└──────────┬──────────────────────────────────┬────────────────────┘
           │ frappe.call(method=...)           │ frappe.realtime.on(...)
           ▼                                   ▼
┌──────────────────────┐           ┌───────────────────────────────┐
│  hamilton_erp.api    │           │  hamilton_erp.realtime        │
│  8 @whitelist methods│           │  publish_realtime wrapper     │
│  (api.py)            │           │  always fires after_commit    │
└──────────┬───────────┘           └───────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  hamilton_erp.lifecycle  (lifecycle.py)                          │
│  start_session_for_asset · vacate_session · mark_asset_clean     │
│  set_asset_out_of_service · return_asset_to_service              │
│  VALID_TRANSITIONS dict is the canonical state machine           │
└──────────┬───────────────────────────────────────────────────────┘
           │ every transition wraps in:
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  hamilton_erp.locks  (locks.py)                                  │
│  asset_status_lock(asset_name, operation) — context manager      │
│  Layer 1: Redis NX set, 15s TTL, UUID token, Lua CAS release     │
│  Layer 2: MariaDB SELECT … FOR UPDATE                            │
│  Layer 3: Optimistic version field — caller's responsibility     │
│  Key: hamilton:asset_lock:{asset_name}  (asset-only, NOT +op)    │
└──────────┬───────────────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Frappe DocTypes (9 custom — see §3)                             │
└──────────────────────────────────────────────────────────────────┘

Retail / POS path (V9.1, partially shipped):
  Asset Board cart drawer
    → hamilton_erp.api.submit_retail_sale
    → POS Sales Invoice (is_pos=1, update_stock=1, ignore_permissions=True)
    → hooks.py doc_event on_submit
    → hamilton_erp.api.on_sales_invoice_submit
    → frappe.publish_realtime("show_asset_assignment", ..., after_commit=True)

Sales Invoice class extension (hooks.py extend_doctype_class):
  "Sales Invoice": "hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice"
  Adds: has_admission_item(), get_admission_category(), has_comp_admission()
```

The Asset Board is a Frappe Page (`/app/asset-board`), not a standard Desk view. CSS is loaded app-wide via `app_include_css` in `hooks.py` because page-level CSS includes were removed in Frappe v15+.

There are currently **no scheduler events registered**. The Phase 1 stub `check_overtime_sessions` was a no-op and was removed. Phase 2 reintroduces a real overtime job.

---

## 3. The 9 Custom DocTypes

All live under `hamilton_erp/hamilton_erp/doctype/`.

| DocType | Purpose | Key Fields |
|---|---|---|
| **Venue Asset** | Physical room or locker; the primary entity the asset board renders | `asset_code` (operator-visible label, e.g. `R001`), `asset_category` (Room/Locker), `asset_tier`, `status` (Available/Occupied/Dirty/Out of Service), `current_session` → Venue Session, `is_active`, `expected_stay_duration` (minutes), `display_order`, `hamilton_last_status_change`, `version` (optimistic lock counter), `reason` (OOS reason text) |
| **Venue Session** | One guest's stay in one asset — created on check-in, closed on vacate | `session_number` (zero-padded 4-digit, Redis INCR), `venue_asset`, `sales_invoice`, `status` (Active/Completed), `session_start/end`, `operator_checkin/vacate`, `vacate_method` (Key Return / Discovery on Rounds), `comp_flag`; plus 10 Philadelphia forward-compat PII fields (`identity_method`, `member_id`, `full_name`, `date_of_birth`, `block_status`, `arrears_amount`, `scanner_data`, `eligibility_snapshot`, etc.) — all null at Hamilton |
| **Asset Status Log** | Immutable audit trail of every status change | `venue_asset`, `operator`, `timestamp`, `previous_status`, `new_status`, `reason`, `venue_session` |
| **Shift Record** | One operator's shift from open to close | `operator`, `shift_date`, `status`, `shift_start/end`, `float_expected`, `float_actual`, `float_variance`, `closing_float_actual`, `closing_float_variance` |
| **Cash Drop** | A single blind cash drop by an operator into the safe | `operator`, `shift_record`, `shift_date`, `shift_identifier`, `drop_type`, `drop_number`, `timestamp`, `declared_amount`, `reconciled`, `reconciliation` (→ Cash Reconciliation) |
| **Cash Reconciliation** | Manager's three-way variance check against a Cash Drop | `cash_drop`, `shift_record`, `manager`, `timestamp`, `actual_count` (manager physical count), `system_expected` (Phase 3 stub — currently hardcoded 0; see R-011), `operator_declared`, `variance_amount`, `variance_flag`, `notes` |
| **Comp Admission Log** | Audit record for every complimentary admission issued | `venue_session`, `sales_invoice`, `admission_item`, `comp_value` (notional door value — Hamilton Manager+ only, R-006), `operator`, `timestamp`, `reason_category`, `reason_note` |
| **Hamilton Settings** | Singleton config for the venue | `float_amount`, `default_stay_duration_minutes`, `printer_ip_address`, `printer_model`, `printer_label_template_name` (currently nothing on the other end — R-012 BLOCKER), `grace_minutes`, `assignment_timeout_minutes`, `show_waitlist_tab`, `show_other_tab` |
| **Hamilton Board Correction** | Manual override log when a manager corrects an asset state outside normal workflow | `venue_asset`, `old_status`, `new_status`, `reason`, `operator`, `timestamp` |

**Roles:** `Hamilton Operator` (read+write on Venue Asset, can call all asset-board endpoints), `Hamilton Manager` (Operator perms + Cash Reconciliation access + reveal mode), `Hamilton Admin` (full). Defined as fixtures in `hooks.py` and synced on `bench migrate`.

**Custom fields on standard DocTypes** follow the naming convention `{doctype}-hamilton_{fieldname}` and are exported as fixtures — never created manually in the UI.

---

## 4. The 8 Whitelisted Endpoints

All live in `hamilton_erp/api.py`. Full request/response shapes, error envelopes, and performance contracts: [`docs/api_reference.md`](api_reference.md).

| Endpoint | Method | One-line summary |
|---|---|---|
| `get_asset_board_data` | GET | Returns all 59 active assets enriched with session data + OOS metadata, plus retail items and Hamilton Settings; 4 total queries regardless of occupancy (no N+1). |
| `start_walk_in_session` | POST | Creates a Venue Session and transitions an Available asset to Occupied; the anonymous walk-in path (no Sales Invoice required). |
| `vacate_asset` | POST | Closes the session on an Occupied asset and transitions it to Dirty; requires `vacate_method` (Key Return or Discovery on Rounds). |
| `clean_asset` | POST | Transitions a single Dirty asset to Available; creates an Asset Status Log entry. |
| `set_asset_oos` | POST | Sets any non-OOS asset Out of Service; `reason` is mandatory. |
| `return_asset_from_oos` | POST | Returns an OOS asset to Available; `reason` (resolution note) is mandatory. |
| `assign_asset_to_session` | POST | **Phase 2 stub — throws immediately. Do not call.** Will wire the Sales Invoice on_submit → Venue Session creation path when Phase 2 ships. |
| `submit_retail_sale` | POST | Creates and submits a POS Sales Invoice from the cart drawer; validates server-side rates against `Item.standard_rate`, applies Canadian nickel rounding for Cash, checks stock before insert. Returns `{sales_invoice, grand_total, rounded_total, rounding_adjustment, change}`. Card payment_method is accepted as a parameter but throws — merchant integration is Phase 2 next iteration. |

**One doc_event hook** (wired in `hooks.py`): `on_sales_invoice_submit` → `hamilton_erp.api.on_sales_invoice_submit`. After a Sales Invoice submits, if it contains an admission item, fires `show_asset_assignment` realtime event to the operator's terminal. Currently a thin shim; Phase 2 completes the assignment flow.

**Two realtime events** emitted by successful transitions:
- `hamilton_asset_status_changed` — per-asset status update; client refreshes that one tile.
- `hamilton_asset_board_refresh` — signal-only (no data); client re-calls `get_asset_board_data`.

Both fire with `after_commit=True`. Never fire inside the lock body.

---

## 5. Hard Rules You Must Know

These are enforced by CI, conformance tests, and code review. Violating them will fail a PR.

### Test sites — never mix them

**`hamilton-unit-test.localhost` is the ONLY site for `bench run-tests`.** Running tests against `hamilton-test.localhost` (the dev browser site) corrupts it — setup_wizard loops, 403s, wiped roles. This is a one-way trip. The `/run-tests` slash command always points at the test site. Never override this.

### Production version pinning

Frappe Cloud production runs on a **specific tagged v16 minor release** (e.g. `v16.3.4`). Never pin to `version-16` branch HEAD; never pin to `develop`. Auto-upgrade is **disabled** on the production bench. Manual upgrade cadence: monthly review window → staging soak (48h minimum) → promote. Rationale: ~10 fixes/month land in `version-16` HEAD; auto-pulling invites churn. Full rule: `CLAUDE.md → "Production version pinning"`.

### Python/Node version pins are not preferences

Frappe v16 requires **Python 3.14** (`>=3.14,<3.15`) and **Node 24** (`engines.node >= 24`). Do not "conservatively" downgrade these. 3.13 fails `frappe depends on Python>=3.14,<3.15`. Node 20 fails `yarn install --check-files`. These are upstream hard requirements, not preferences.

### Tabs, not spaces

`pyproject.toml` lint config ignores W191/E101 for this reason. Match Frappe's formatter.

### Lock body discipline (§13.3 of `docs/coding_standards.md`)

**Zero I/O inside the lock body.** Permitted inside: read current status from DB, validate transition, update status field, save document, create Asset Status Log entry. **Never inside the lock:** `frappe.publish_realtime`, `frappe.enqueue`, print, email, external API calls. Realtime fires **after** the `with asset_status_lock(...)` block closes, which means after the DB transaction commits.

### Lock key format

The Redis lock key is **`hamilton:asset_lock:{asset_name}`** — asset-only. It is NOT keyed on `(asset, operation)`. An early design in `phase1_design.md` specified `:operation` as a suffix but that design was reversed (ChatGPT review 2026-04-10) because asset+operation keying allowed two concurrent callers to mutate the same asset via different operation paths. The `locks.py` comment documents this. Do not reintroduce an operation suffix.

### Test class inheritance

Inherit from `frappe.tests.IntegrationTestCase` or `frappe.tests.UnitTestCase`. Never from `unittest.TestCase` directly. Tests must be self-contained — create and tear down their own data, no reliance on global seed.

### frappe/payments install in CI

`frappe/payments` has no `version-16` branch as of 2026-05-01. CI installs it from `develop`. Production may also require it installed (see `docs/inbox.md` 2026-04-28 entry on the frappe/payments production-deploy decision). The 6 pre-existing `setUpClass` failures in the test suite (for doctype tests that chain into `Payment Gateway`) are the documented baseline — not regressions, not stubs. They pass in CI because CI installs frappe/payments.

### Other hard rules from `coding_standards.md` §12

- Use `frappe.db.get_value(..., for_update=True)` for race-condition-sensitive reads.
- Never `frappe.db.commit()` in controllers — framework manages transaction boundaries.
- `@frappe.whitelist()` default is `allow_guest=False`; do not override unless explicitly required.
- Validate permissions in controllers, not in client-side JS.
- Use `frappe.db.exists()` guards in install/seed/migration code (idempotency).
- Use `frappe.db.delete()` not raw SQL for cleanup.

### Inbox.md is a working queue, not a transient buffer

`docs/inbox.md` is the bridge from claude.ai planning sessions to Claude Code implementation. Do NOT auto-clear it. Check it at every session start. Per `CLAUDE.md` Rule 1: before starting any task, read `docs/inbox.md`; if it has content, merge it into canonical docs and clear it. Content that lives only in inbox.md is not yet canonical.

---

## 6. Phase 1 BLOCKER Status

These 8 tasks (IDs 30-37 in Taskmaster) must all ship before Hamilton goes live. Tasks 34, 35, 36 shipped 2026-05-01. Tasks 30, 31, 32, 33, 37 remain open.

| Task | Title | Status | Notes |
|---|---|---|---|
| **30** | Cash Drop envelope label print pipeline | **OPEN** | The print pipeline is entirely unbuilt. `Hamilton Settings.printer_label_template_name` points at nothing — no `Label Template` DocType, no print format, no Brother QL-820NWB dispatch. The blind cash drop anti-theft design (DEC-005) depends on pre-printed labels; without them, operators hand-write amounts on envelopes, which defeats the tamper-evident design. This is the highest-urgency open BLOCKER. See `docs/risk_register.md` R-012 for the full anatomy and what Task 30 must ship. |
| **31** | Cash-side refunds | **OPEN** | No refund surface exists. The operator path today is to navigate Frappe Desk directly — which violates the "operators don't access Desk" invariant. ERPNext's standard POS Return also has known bugs (G-019 overrefund from `paid_amount`, G-020 partial returns blocked). Read `docs/design/refunds_phase2.md` before implementing. |
| **32** | Comps manager-PIN gate | **OPEN** | `Comp Admission Log` fields are writable by Hamilton Operator with no PIN challenge or second-factor. Any operator can issue unlimited comps. Read `docs/design/manager_override_phase2.md` for the single shared override service design that this task plugs into. |
| **33** | Voids — mid-shift transaction undo | **OPEN** | No void surface in the cart UI. Operators who need to cancel a just-submitted Sales Invoice must navigate Frappe Desk manually. Read `docs/design/voids_phase1.md` — voids are time-boxed, reason-required, and reconciliation-aware; they are NOT a generic cancel button. |
| **34** | Tip-pull schema | **SHIPPED 2026-05-01 (PR #122)** | Tip Pull DocType schema is in place. Full workflow (UX, GL postings, per-venue rounding-rule resolution) is Phase 2. Cash reconciliation integrates tip pulls in Phase 3. |
| **35** | Post-close orphan-invoice integrity check | **SHIPPED 2026-05-01 (PR #124)** | Daily scheduled job that detects Sales Invoices created via `submit_retail_sale` that have no corresponding POS Closing Entry consolidation (G-023 silent failure mode). Read `docs/design/post_close_integrity_phase1.md` for the recovery semantics — the query shape is trivial but the recovery path matters. |
| **36** | Zero-value comp invoice regression test | **SHIPPED 2026-05-01 (PR #123)** | Regression test verifying that comp admissions with `comp_value=0` do not create broken Sales Invoices. Verify-only task; no implementation changes. |
| **37** | Receipt printer integration — Epson TM-m30III | **OPEN** | No receipt printer integration exists. POS profile is `Hamilton Front Desk`. The TM-m30III is the spec'd hardware; integration must go through ERPNext's print format path, not custom socket code. |

**Task 25** (Deploy to Frappe Cloud + manual QA on real hardware) is the Phase 1 gate task — pending all BLOCKERs clearing.

---

## 7. Risks to Track

Full entries with mitigations and watch-points: [`docs/risk_register.md`](risk_register.md). Only the watch-line for each:

| Risk | Summary | Severity |
|---|---|---|
| **R-006** | `Comp Admission Log.comp_value` is readable by Hamilton Operator — leaks margin info, enables self-justification for inflated comps. Fix: `permlevel: 1` on `comp_value` + Manager/Admin permlevel-1 read rows + regression test in `test_security_audit.py`. | **HIGH — PRE-GO-LIVE BLOCKER** |
| **R-007** | 8 Philadelphia PII fields on `Venue Session` (full_name, DOB, scanner_data, etc.) will be readable by Hamilton Operator the moment Philadelphia begins populating them. Fix same shape as R-006. | **HIGH — PRE-GO-LIVE BLOCKER for Philadelphia** |
| **R-009** | Mastercard MATCH list: sustained >1% chargeback ratio triggers a 5-year merchant blacklisting. Latent until card payments ship. CE3.0 EMV fields (auth_code, card_entry_method, card_cvm, card_aid) are the operational defense via liability shift. | **HIGH (latent — activates with Phase 2 card payments)** |
| **R-010** | ERPNext v16 `version-16` branch HEAD receives ~10 fixes/month. Two open upstream issues (#54183, #50787) affect POS Closing when returns are batched. Latent until Phase 3 refunds ship. Monthly upgrade review is the structural defense. | **HIGH (latent — activates with Phase 3 returns)** |
| **R-011** | `cash_reconciliation.py._calculate_system_expected` is hardcoded to `flt(0)`. Every real reconciliation fires a false `variance_flag`. Manager training is the only mitigation until Phase 3 ships the real calculator. | **MEDIUM — operational false-alarm risk** |
| **R-012** | Cash Drop envelope label print pipeline is entirely unbuilt (→ Task 30). Defeats DEC-005 blind cash drop anti-theft design operationally. | **HIGH — BLOCKER (see §6 Task 30)** |
| **R-013** | ERPNext deferred-stock validation fails at POS Closing when same-shift returns are batched. `Allow Negative Stock` is the wrong "fix" — it silently corrupts the stock ledger. Correct mitigation: route refunds with `update_stock=1` at creation time, never batched at POS Close. Latent until Task 31 (refunds) ships. | **HIGH (latent — activates with Phase 2 returns)** |

---

## 8. Where Design Intent Lives

Before implementing any BLOCKER task, read the corresponding design intent doc. These capture the **why** behind each decision. Misapplying the mechanics without the reasoning produces a system that LOOKS right but silently breaks the trust model.

All live in `docs/design/`:

| File | Covers | Required before |
|---|---|---|
| [`cash_reconciliation_phase3.md`](design/cash_reconciliation_phase3.md) | Blind drop philosophy (three-number triangulation, reveal-after-3, Final Cash Amount to GL), variance system design, tip-pull integration, venue-configurable recon profiles | Phase 3 cash recon implementation; any change to `Cash Reconciliation` controller |
| [`refunds_phase2.md`](design/refunds_phase2.md) | Refund-event taxonomy (cancel-before-fulfillment vs. cash refund vs. card settlement), ERPNext POS Return bug wrappers (G-019, G-020), audit trail and GL correctness | Task 31 (cash-side refunds) |
| [`voids_phase1.md`](design/voids_phase1.md) | Time-boxed operator void, reason-required, reconciliation-aware; why "just expose the cancel button" is the wrong path | Task 33 (voids) |
| [`manager_override_phase2.md`](design/manager_override_phase2.md) | Single shared `override.request()` service, venue-configurable per-action thresholds, time-windowed PINs, audit log distinguishing self-authorized from delegated-authorized | Task 32 (comps PIN gate) and any future flow needing a graduated control gate |
| [`tip_pull_phase2.md`](design/tip_pull_phase2.md) | Tip Pull DocType data model, GL postings (tips are operator compensation, not venue revenue), per-venue rounding-rule resolution, multi-currency handling, reconciliation integration | Phase 2 tip-pull UX (schema shipped in Task 34; workflow is Phase 2) |
| [`post_close_integrity_phase1.md`](design/post_close_integrity_phase1.md) | What G-023/G-010/G-030 failure modes the daily integrity check defends against, why daily cadence, what the alert payload contains, and the recovery path | Task 35 is shipped; consult this if the job ever fires in production and you need to know what to do |

**Asset Board UI:** `docs/design/V10_CANONICAL_MOCKUP.html` is the gospel specification for the asset board visual design. If the production JS and the mockup disagree on visual or behavioral specifics, the mockup wins — production drift is the bug. Do not edit the mockup file; changes require an explicit amendment and a new version-numbered canonical file (V11). The V10 body is byte-identical to V9 (visual spec unchanged); V10 was bumped to bookkeep the V9.1 retail amendment.

**Asset board design decisions:** `docs/decisions_log.md` locks DEC-001 through DEC-064+. Before making any change to asset-board behavior, search this document. If the change touches a locked decision, surface the conflict rather than making the change silently.

---

## 9. The Most Surprising Things About This Codebase

These are the things that will cost a new developer hours if they hit them cold.

### 1. The Redis lock key is asset-only — never asset+operation

`locks.py` line 67: `key = f"hamilton:asset_lock:{asset_name}"`. There is no `:operation` suffix. An early design document (`docs/phase1_design.md`) specified `hamilton:asset_lock:{asset_name}:{operation}` and that spec is still in the file with a banner marking it HISTORICAL. If you read that doc before reading `locks.py`, you will implement the wrong key format. Always verify the lock key against the source file, not the design doc. The rationale: asset+operation keying allowed two concurrent callers to mutate the same asset simultaneously via different operation paths (e.g. one vacating while another marking OOS). Asset-only keying serializes all mutations on the same asset regardless of operation type.

### 2. V10_CANONICAL_MOCKUP.html is the design authority — production drift is the bug

`docs/design/V10_CANONICAL_MOCKUP.html` is not documentation. It is the executable specification for the asset board UI. When implementing or modifying any asset board JS, port from the mockup verbatim — change selectors where production conventions differ (`.tile` → `.hamilton-tile`), but do not interpret the design. If the current `asset_board.js` and the mockup disagree, the mockup is correct. This rule caused a significant divergence audit in April 2026 (V9 was described as shipped when only the mockup file shipped; the live JS was still V8; the gap was a 20-item audit). The rule exists to prevent that pattern.

### 3. Bulk Mark All Clean was deliberately removed — regression tests pin its absence

Task 15 in Taskmaster (`api.py — bulk mark_all_clean_rooms / mark_all_clean_lockers`) shows status `done`, but the endpoints are commented out of `api.py` with an explanation. The feature was removed on 2026-04-29 (DEC-054 reversed) after live browser testing showed operators never used it — cleaning happens per-tile via the Dirty tile's expand overlay. Regression tests in the test suite verify the bulk endpoints do NOT exist. If you see Taskmaster shows Task 15 as `done` and assume the endpoints are live, you will look for code that is intentionally absent.

### 4. `cash_reconciliation._calculate_system_expected` is a stub that always returns 0

`cash_reconciliation.py` has `self.system_expected = flt(0)` hardcoded and is marked "Phase 3 implementation." Until Phase 3, every real reconciliation fires a false `variance_flag` because the system always expects $0 but operators declare real cash. The mitigation is manager training, not code. Do NOT "fix" this with a quick `frappe.get_all` query — the Phase 3 design (`docs/design/cash_reconciliation_phase3.md`) describes a non-trivial calculation (sum cash payment lines on submitted SIs for the shift period, subtract tip pulls, apply venue-specific recon profile). Doing it half-right produces worse fraud signals than leaving it as a stub.

### 5. Brew Redis on 6379 must stay off while bench is running

Bench's Redis instances run on ports 11000 (queue) and 13000 (cache + socketio) per `sites/common_site_config.json`. A separate `brew services redis` instance running on 6379 causes two problems: (a) any code path that calls `redis.Redis()` with no args defaults to 6379 and silently succeeds against an empty, unrelated Redis with no Frappe data, masking config bugs; (b) multiple `redis-server` processes in `ps aux` look like a port conflict and make `bench start` failures harder to diagnose. The fix is permanent: `brew services stop redis`. Do NOT run `brew services start redis` on this machine. Bench owns Redis. See `docs/lessons_learned.md` 2026-05-01 entry for the full investigation and verification steps.

---

## 10. Day 1 / Day 2 Onboarding Script

### Day 1 Morning — Environment, tests, required reading

**1. Clone and bootstrap**
```bash
git clone https://github.com/csrnicek/hamilton_erp.git ~/hamilton_erp
bash ~/hamilton_erp/scripts/init.sh
```
`init.sh` verifies Python 3.14 and Node 24 are present, bootstraps `~/frappe-bench-hamilton`, and creates both `hamilton-test.localhost` (dev browser site) and `hamilton-unit-test.localhost` (test site). If a prereq is missing, the script tells you what to install. Do not proceed until it exits clean.

**2. Confirm the test suite is green**
```bash
cd ~/frappe-bench-hamilton && source env/bin/activate
bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp
```
Or use the `/run-tests` slash command in Claude Code, which runs all 14 modules against `hamilton-unit-test.localhost`. Baseline: 306+ passing, 15 skipped, 6 pre-existing `setUpClass` failures (the `Payment Gateway` link-field issue documented in `CLAUDE.md → "Common Issues"`). Any deviation from this baseline is a regression — stop and report before doing anything else.

**3. Required reading (in this order)**
- `CLAUDE.md` — project context, environment, conventions, autonomy levels
- `docs/decisions_log.md` — locked design decisions DEC-001 through DEC-064+; pay special attention to DEC-005 (blind cash), DEC-019 (three-layer lock), DEC-054 reversal (bulk clean removed), DEC-062/063/064 (merchant classification and processor architecture)
- `docs/review_package.md` — DEC-001 through DEC-016 from the pre-coding architectural review; DEC-005 (blind cash drop) and DEC-011 (Brother label printer spec) are especially relevant
- `docs/risk_register.md` — R-006/R-007/R-009/R-012 are PRE-GO-LIVE BLOCKERs; understand what they mean before touching any of those surfaces

### Day 1 Afternoon — Codebase walkthrough

**4. Read the source layer by layer**

Start with `hamilton_erp/hooks.py` (89 lines — short; the full wiring map). Then `hamilton_erp/locks.py` (137 lines — the entire concurrency model). Then `hamilton_erp/lifecycle.py` (651 lines — the state machine; read `VALID_TRANSITIONS` dict first, then the five public functions). Then `hamilton_erp/api.py` (the 8 endpoints; note the `submit_retail_sale` docstring explains the authorization model, rate authority, and rounding contract in detail).

**5. Read the API and coding standards docs**
- `docs/api_reference.md` — full request/response shapes, error envelopes, performance contracts (4-query limit on `get_asset_board_data` is pinned by a test)
- `docs/coding_standards.md` §13 — the entire locking standards section; memorize the lock-body rules before writing any state-changing code

**6. Walk through the asset board JS**

`hamilton_erp/public/js/asset_board.js` (~294 lines). Read it alongside `docs/design/V10_CANONICAL_MOCKUP.html` to understand what the mockup mandates vs. what's currently in production. CSS is in `hamilton_erp/public/css/asset_board.css`.

**7. Review the design intent docs for open BLOCKERs**

Skim `docs/design/refunds_phase2.md`, `docs/design/voids_phase1.md`, `docs/design/manager_override_phase2.md`. These are the three most complex open BLOCKERs. You don't need to internalize them Day 1, but you need to know they exist and where they are before you write code.

### Day 2 — First contribution

**Pick a BLOCKER task from Taskmaster.** Recommended starting point for a first PR:

- **Task 37** (receipt printer — Epson TM-m30III) if you have hardware integration experience. Scope is well-defined: wire ERPNext print format → Epson network print path.
- **Task 33** (voids) is moderate complexity. Read `docs/design/voids_phase1.md` completely before writing a line — the design choices (time-boxing, reason-required, reconciliation-aware) are non-obvious but clearly documented.
- **Task 31** (cash-side refunds) is the most complex open BLOCKER. Read `docs/design/refunds_phase2.md` and `docs/risk_register.md` R-013 before starting.

**Before writing any code for an open BLOCKER:**
1. Read the corresponding design intent doc (§8 of this document)
2. Read the Taskmaster task description — each BLOCKER task has implementation guidance
3. Check `docs/decisions_log.md` for any locked decisions covering the surface you're touching
4. Run `/run-tests` after every meaningful change; confirm the baseline holds

**PR workflow:**
- Branch from `main`; commit messages follow conventional commits (`feat:`, `fix:`, `test:`, `docs:`)
- Every PR that touches `docs/task_25_checklist.md` or `.taskmaster/tasks/tasks.json` must pass the sync guard in `.github/workflows/sync-taskmaster.yml`
- PR description must follow the template in `CLAUDE.md → "PR completion template"` — 9 required sections including CI result, rollback notes, and remaining risks

---

## Key File Index

| What you need | Where it is |
|---|---|
| Project conventions, environment, version pins | `CLAUDE.md` |
| Locked design decisions (DEC-001 through DEC-064+) | `docs/decisions_log.md` |
| Coding standards, §13 locking | `docs/coding_standards.md` |
| API surface, error shapes, performance contracts | `docs/api_reference.md` |
| Risk register with mitigations | `docs/risk_register.md` |
| Recurring failure catalogue (LL-001 through LL-037) | `docs/lessons_learned.md` |
| Task list with all 37 current tasks | `.taskmaster/tasks/tasks.json` |
| Phase 1 / 2 / 3 / 4 plan | `docs/build_phases.md` |
| Operational runbook (incident response, Redis, rollback) | `docs/RUNBOOK.md` |
| Role/DocType permissions matrix | `docs/permissions_matrix.md` |
| Testing guide (4 levels, coverage, mutmut, hypothesis) | `docs/testing_guide.md` |
| Task 25 sub-item checklist (canonical for Task 25 scope) | `docs/task_25_checklist.md` |
| Asset Board UI gospel | `docs/design/V10_CANONICAL_MOCKUP.html` |
| V9.1 retail amendment spec | `docs/design/V9.1_RETAIL_AMENDMENT.md` |
| Venue rollout playbook (Phase A–F deploy checklist) | `docs/venue_rollout_playbook.md` |
| Three-layer lock implementation | `hamilton_erp/locks.py` |
| State machine helpers | `hamilton_erp/lifecycle.py` |
| All 8 whitelisted endpoints | `hamilton_erp/api.py` |
| App wiring (hooks, fixtures, doc_events, extend_doctype_class) | `hamilton_erp/hooks.py` |
| HamiltonSalesInvoice extension | `hamilton_erp/overrides/sales_invoice.py` |

---

*This document was written from direct inspection of source files, not from memory or re-derivation. When this doc and the source files disagree, the source files win — update this doc to match.*
