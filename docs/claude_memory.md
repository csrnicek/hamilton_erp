# Claude Memory — Extended Context for Hamilton ERP

Persistent reference for Claude Code sessions. Captures project state, history,
best practices, planning notes, tooling decisions, and Phase 2 readiness that
don't belong in code comments or decisions_log.md.

**Last updated:** 2026-04-28

---

## Documents Map

These are the durable docs in this repo. Future sessions consult them in this order:

| Document | Purpose | When to consult |
|---|---|---|
| `CLAUDE.md` | Hard rules, conventions, PR completion template, autonomous command rules | Auto-loaded at session start. Never duplicate its content here. |
| `docs/claude_memory.md` | Project state, what shipped, current focus, durable history | This file. Read at session start for context. |
| `docs/decisions_log.md` | Locked design decisions (asset board V8/V9) | Before changing any asset board behavior. Follow Part 12 reversal protocol. |
| `docs/lessons_learned.md` | What went wrong + how it was fixed | When tackling something similar to a past failure. |
| `docs/HAMILTON_LAUNCH_PLAYBOOK.md` | Operational risks for opening weekend | Before any launch-readiness work. Top 12 risks ranked. |
| `docs/inbox/production_handoff_audit_merged_2026-04-25.md` | Outstanding handoff items (T1/T2 lists) | Before deciding next priority work. |
| `docs/inbox.md` | Transient scratch / triage zone (NOT durable) | Triage at start of each session. Promote durable items to this file or delete. |

CLAUDE.md is the source of truth for hard rules and PR template. This file complements it with project state, never duplicates rules.

---

## Top of Mind — Current Focus

- **Phase 1 Task 17** in progress: subtasks 17.1 + 17.2 done; 17.3-17.5 pending browser QA. Next priority work.
- **Three-PR CI infrastructure day complete (2026-04-28).** PR #9 (CI), PR #11 (docs cleanup + Hamilton Launch Playbook), PR #12 (CLAUDE.md improvements) all merged. See history section below.
- **Branch protection enforced on `main`.** Required status checks: `Server Tests` and `Linter`. Manual GitHub UI configuration; API-based setup blocked by token scope.
- **Tier 0 production monitoring archived** until Hamilton launch is imminent. Plan lives in `docs/inbox.md` (committed via PR #11) and the Hamilton Launch Playbook. Do NOT prompt to start it preemptively.
- **5 scratch notes** intentionally remain in working-tree `docs/inbox.md` (uncommitted): Throughput re-baseline, Test fixture factory, AoE bookmark, plus PR #11 + #12 MERGED audit entries. The PR MERGED entries are now promoted into this file (see history below) and can be deleted from inbox.md after PR #13 merges.
- **Next priority:** Phase 1 Task 17 browser QA (17.3-17.5), then Tasks 18-25 toward launch readiness.

---

## What shipped — April 28, 2026 (three-PR CI infrastructure day)

Three docs/infrastructure PRs merged in sequence. Hamilton ERP now has enforced CI, an operational risk audit, and improved Claude Code conventions.

### PR #9 — CI infrastructure (merged at 98c2d2a)

**What:** GitHub Actions CI that vendors the Frappe setup composite action (shared workflow lookup was broken). Install path productionized in `hamilton_erp/setup/install.py` via `_ensure_erpnext_prereqs()`, `_seed_hamilton_data()`, `_ensure_no_setup_wizard_loop()`. CI workflow runs install-app → conformance assertions → bench migrate → 464 tests.

**Why it mattered:** Closed Tier 1 items T1.1 and T1.4 from production_handoff_audit_merged_2026-04-25.md. Without enforced CI, install-path drift goes undetected for days. ChatGPT cross-review caught a critical architecture issue mid-PR (CI workarounds becoming a parallel install path) — pivoted to Path 1 (install path owns its setup logic, not the workflow).

**E1 fix included:** `_ensure_no_setup_wizard_loop()` runs on BOTH after_install and after_migrate. `bench install-app` doesn't fire after_migrate, so the heal must also run on after_install — caught in pre-merge safety review.

### PR #11 — Post-PR-9 docs cleanup + Hamilton Launch Playbook (merged at d34c107)

**What:** Surgical inbox.md split (KEEP only, 234 lines committed; DEFERRED restored as local scratch). Added `docs/HAMILTON_LAUNCH_PLAYBOOK.md` (463 lines, operational risk audit for opening weekend). Added `.claude/*.backup` to .gitignore.

**Why it mattered:** PR #9 left inbox.md with 8 transient sections that needed triage. The Launch Playbook is the operational-recovery document for Hamilton opening — top 3 risks (paid-but-no-session, staff trust, cash variance) are training/process, not engineering. Per ChatGPT's framing: opening weekend is operations recovery, not software correctness.

### PR #12 — CLAUDE.md improvements (merged at f0863db)

**What:** Two additions to CLAUDE.md:
- `## Frappe v16 Conventions` (line 20) — upstream doc links + 9 hard rules: tabs not spaces, frappe.tests.IntegrationTestCase, frappe.db.exists() guards before insert, no frappe.db.commit() in controllers, etc.
- `## PR completion template` (line 263) — standardized 7-section format every Claude Code PR uses (commits, tests, CI, files, risks, rollback, merge command, open questions)

**Why it mattered:** PR #9's CI marathon revealed that "follow Frappe v16 conventions" was too vague — sessions interpret it loosely against general training knowledge. Hard rules + upstream links make conventions actionable. PR template closes the ad-hoc PR summary problem.

### Branch protection enforced

Both `Server Tests` AND `Linter` are required status checks on `main` (set manually via GitHub UI on Apr 28). Branch protection BLOCKS merges that fail required checks. Manual UI step was needed because API tokens lacked admin scope to set required checks programmatically.

### Two-AI cross-review pattern proved essential

Claude Code + ChatGPT cross-review caught architectural drift one AI alone missed. Specifically: the Path 1 install pivot mid-PR-9. Going forward, treat ChatGPT review as part of the safety net for any non-trivial PR. Not optional for infrastructure work.

### Other changes Apr 28

- V8/ snapshot directory deleted (was untracked archive of pre-V9 design work; canonical content lives in `docs/decisions_log.md` and `docs/design/asset_board_mockup_v7.html` in main)
- Five inbox scratch notes intentionally preserved as transient (Throughput re-baseline, Test fixture factory, AoE bookmark, plus the three PR MERGED audit entries — the latter promoted to this file in PR #13)
- Tier 0 production monitoring archived until Hamilton launch is imminent

---

## 1. Hamilton ERP Best Practices (15 Rules)

These were derived from debugging sessions, code reviews, and production incidents
during Phase 0 and Phase 1 development (2026-03 through 2026-04).

### Frappe/ERPNext Platform

1. **`frappe.is_setup_complete()` reads `tabInstalled Application`**, not System Settings or DefaultValue.
   Filter is `app_name IN ('frappe','erpnext')`. Both rows must exist with `is_setup_complete=1`.
   Never edit `site_config.json` to force this — that's pre-v15 and not authoritative on v16.

2. **`frappe.call()` defaults to POST; curl defaults to GET.** A `@frappe.whitelist(methods=["GET"])`
   endpoint will 403 in the browser and pass every curl probe. When debugging "works in curl,
   403s in browser," jump straight to verb comparison. See DEC-058.

3. **Direct Python imports bypass `frappe.handler` entirely.** Tests that call `api.get_asset_board_data()`
   never exercise the HTTP verb gate, CSRF, or session auth. Use `frappe.handler.execute_cmd()`
   with a spoofed `frappe.local.request` for verb-gate regression tests.

4. **`IGNORE_TEST_RECORD_DEPENDENCIES` must be a list, not a boolean.** Frappe's `generators.py:115`
   does `to_remove += module.IGNORE_TEST_RECORD_DEPENDENCIES` which requires list concatenation.
   Setting it to `True` causes `TypeError: 'bool' object is not iterable`.

5. **`bench request` does not set `frappe.local.request.method`.** It crashes with `AttributeError`
   on any endpoint that checks `is_valid_http_method`. Use real curl or the `TestAssetBoardHTTPVerb`
   mock pattern instead.

### Testing

6. **Always run the full 16-module suite (353 tests, 7 skipped), always on `hamilton-unit-test.localhost`.** Never run tests
   on `hamilton-test.localhost` — it corrupts the dev browser state (setup_wizard loops, 403s, wiped roles).

7. **Redis uses non-default ports.** Cache is on port 13000, queue is on port 11000 (not 6379).
   Start them explicitly: `redis-server --port 13000 --daemonize yes && redis-server --port 11000 --daemonize yes`.

8. **Test site bootstrap is a 4-step sequence:** `bench migrate` -> ERPNext `setup_complete()` ->
   `seed_hamilton_env.execute()` -> `restore_dev_state()`. Each step depends on the previous.
   See the full procedure in CLAUDE.md or the memory file `project_unit_test_site_bootstrap.md`.

9. **Tabs not spaces in all Python files.** Coding standards (docs/coding_standards.md) section 11.
   Every `.py` file in hamilton_erp uses tabs. Mixing causes IndentationError across the entire module.

10. **`tearDown` uses `frappe.db.rollback()` — never `frappe.db.commit()` inside tests.** Commits inside
    tests leak state to subsequent test classes and cause cascading failures.

### Architecture

11. **Three-layer locking: Redis NX+TTL -> MariaDB FOR UPDATE -> optimistic version field.** The Redis
    advisory lock (Lua CAS release) prevents concurrent entry. MariaDB FOR UPDATE serializes DB access.
    The version field catches stale reads. Zero I/O inside the lock body — realtime fires after_commit only.

12. **Redis lock key is asset-only: `hamilton:asset_lock:{asset_name}`.** Not asset+operation. One lock
    per asset regardless of what operation is being performed. TTL is 15 seconds (`LOCK_TTL_MS = 15_000`).

13. **Deterministic lock ordering for bulk operations.** `_mark_all_clean(category)` sorts dirty assets
    by name before iterating, preventing deadlocks when multiple operators trigger bulk clean simultaneously.
    See coding_standards.md section 13.4.

14. **New assets must start as "Available".** Enforced by `venue_asset._validate_status_transition`.
    Walk-in customer fixture is required for session creation (DEC-055 section 1).

15. **Session number format: `{d}-{m}-{y}---{NNNN}`** with Redis INCR for the sequence counter and
    a DB fallback (`_db_max_seq_for_prefix`) when Redis is unavailable. See DEC-033 for the full spec.

---

## 2. DC Build Planning Notes

### Multi-Venue Refactor (Future)

The current Hamilton build is single-venue. The Philadelphia expansion will require:

- **Venue context isolation:** Every query, lock key, and realtime channel must be scoped to a venue.
  Current Redis keys like `hamilton:asset_lock:{asset_name}` will need a venue prefix.
- **Venue Asset naming:** Currently `VA-.####` globally. Multi-venue needs either venue-prefixed
  naming (`VA-HAM-.####`, `VA-PHI-.####`) or a separate `venue` Link field with compound uniqueness.
- **Asset Board per venue:** The current `/app/asset-board` page loads all 59 assets in one query.
  Multi-venue needs a venue selector or route parameter (`/app/asset-board/hamilton`).
- **Card-based tiles are forward-compatible:** The Phase 1 design uses self-contained cards specifically
  so Philadelphia can add member name/photo to each tile without restructuring the grid.

### Feature Flags (DEC-062)

Decision made 2026-04-14: Use Frappe's native `site_config.json` per-site configuration.
All flag reads centralized in `hamilton_erp/utils/venue_config.py` (to be created).
Never scatter `frappe.conf.get()` calls across the codebase.

Key flags per venue:
- `anvil_venue_id` — venue identifier string (hamilton, philadelphia, dc, dallas)
- `anvil_membership_enabled` — 0 or 1 (only DC = 1)
- `anvil_tax_mode` — CA_HST (Hamilton), US_NONE (US venues)
- `anvil_tablet_count` — integer (DC = 3, all others = 1)
- `anvil_currency` — CAD or USD

Schema to be documented in `docs/site_config_schema.md`.

### Race Condition Research

Documented race conditions and their mitigations:

| Race | Mitigation | Test |
|------|-----------|------|
| Double-booking same asset | Redis NX lock + MariaDB FOR UPDATE | test_locks.py, test_adversarial.py B01-B06 |
| Session number collision | Redis INCR + UniqueValidationError retry (3x) | test_adversarial.py C01-C06 |
| Bulk clean + single clean overlap | Deterministic lock ordering by asset name | test_adversarial.py E01-E05 |
| Stale read after concurrent write | Optimistic version field (TimestampMismatchError) | test_adversarial.py B05 |
| Redis TTL expiry during operation | 15s TTL with Lua CAS release script | test_locks.py |

---

## 3. Full Tooling Stack

### Development Tools

| Tool | Purpose | Status |
|------|---------|--------|
| **Claude Code (Opus 4.6)** | Primary development AI — architecture, business logic, debugging | Active |
| **Claude Code (Sonnet 4.6)** | Mechanical tasks — tests, docs, repetitive refactors | Active |
| **Taskmaster** (`eyaltoledano/claude-task-master`) | Task management with dependency graphs | Active |
| **Claude-Mem** (`thedotmack/claude-mem`) | Cross-session persistent memory | Active |
| **Superpowers** (`v2.1.97`) | Process skills — TDD, plans, code review, debugging, worktrees | Active |
| **Context7** | Library documentation fetching | Active |

### Plugins Evaluated and Rejected

| Plugin | Reason for rejection |
|--------|---------------------|
| **Claude Code Harness** (`Chachamaru127/claude-code-harness`) | Overwrites CLAUDE.md, duplicates Taskmaster (Plans.md), duplicates Superpowers (worker/reviewer agents), Japanese-language oriented, generates Node.js CI template unusable for Frappe. Uninstalled 2026-04-12. |

### CI/CD and Deployment

| Tool | Purpose | Status |
|------|---------|--------|
| **GitHub** (`csrnicek/hamilton_erp`) | Source control, PR reviews | Active |
| **Frappe Cloud** (`hamilton-erp.v.frappe.cloud`, N. Virginia) | Production hosting, auto-deploy on push | Active |
| **GitHub Actions** | Not yet configured. Future: run test suite on PR. | Planned |

### Remote Capabilities (Not Yet Configured)

| Tool | What it does | When to set up |
|------|-------------|----------------|
| **Remote Control** (`claude --remote`) | Run Claude Code sessions on cloud infrastructure | When local machine is insufficient or for overnight tasks |
| **Remote Tasks / Triggers** | Schedule recurring Claude Code tasks on a cron | When CI integration or automated monitoring is needed |
| **GitHub Actions + Claude** | Run test suite and Claude Code review on every PR | Phase 2 or when team grows beyond solo developer |

---

## 4. Task 25 Checklist — Phase 1 Completion

Task 25 is the final Phase 1 task: Frappe Cloud deploy + acceptance testing.
These items must all be complete before Phase 1 is marked done.

### Security & Permissions

- [ ] Cancel/amend locked to Floor Manager+ only
- [ ] System Manager restricted to Chris only
- [ ] Enable Document Versioning on all critical DocTypes (now, not at handoff)
- [ ] Enable Audit Trail in System Settings
- [ ] Verify no Front Desk role self-escalation possible
- [ ] Export role permission matrix as fixture
- [ ] Enable v16 Role-Based Field Masking on sensitive fields

### Code Quality

- [ ] Export all fixtures (Custom Fields, Roles, DocPerms, Property Setters)
- [ ] Verify `patches.txt` covers all manual setup steps
- [ ] Add venue config validation patch (fails loudly on missing flags)
- [ ] Audit `hooks.py` — remove wildcards, add try-except to all hook functions
- [ ] Add `pyproject.toml` with bounded v16 Frappe dependency
- [ ] Add GitHub Actions CI/CD workflow (`.github/workflows/ci.yml`)
- [ ] Clear Frappe Cloud error log
- [ ] Create `init.sh` (start bench, migrate, test, exit non-zero on failure)
- [ ] Tag `v1.0.0-hamilton-handoff`

### New Files to Create

- [ ] `VENUES.md` — all planned venues with site URLs, venue_id, config
- [ ] `docs/site_config_schema.md` — every `site_config.json` key hamilton_erp reads
- [ ] `hamilton_erp/utils/venue_config.py` — centralized flag reads
- [ ] `docs/lessons_learned.md` — DONE (created 2026-04-14)
- [ ] `docs/venue_rollout_playbook.md` — DONE (created 2026-04-14)
- [ ] `.github/workflows/ci.yml`

### Handoff Documentation

- [ ] `docs/operator_playbook.md` — Step-by-step guide for Club Hamilton operators
  - Shift start procedure
  - Asset board usage (tap to change state, color meanings)
  - Cash drop procedure
  - Common error messages and what to do
  - Who to contact when something breaks
- [ ] `docs/admin_guide.md` — For Chris as system administrator
  - How to add/remove assets
  - How to change Hamilton Settings (stay duration, float amount)
  - How to check Asset Status Logs
  - Frappe Cloud dashboard basics
- [ ] Every architectural decision + why
- [ ] Known bugs and deferred items with ticket/task references
- [ ] Role matrix
- [ ] Phase 2 scope summary

### Semantic Versioning

- [ ] Tag `v1.0.0` when all 25 tasks pass
- [ ] CHANGELOG.md entry for v1.0.0 with full feature list
- [ ] GitHub Release with Before/After table

### Testing Quality Gates

- [ ] **All 16 test modules green (353 tests, 7 skipped)** — zero failures, skipped tests documented
- [ ] **mutmut mutation testing** — run `mutmut run` against lifecycle.py and locks.py
  - Target: kill ratio > 80% on critical paths
  - Surviving mutants must be reviewed and either killed or documented as acceptable
- [ ] **Hypothesis property-based testing** — add to test_lifecycle.py
  - State machine property: no sequence of valid transitions can reach an invalid state
  - Session number property: generated numbers are always unique and correctly formatted
  - Lock property: lock acquire + release is always paired (no leaked locks)
- [ ] **Acceptance testing** — all QA tests H10, H11, H12 pass manually in browser
  - H10: Vacate and Turnover (manual session -> occupy -> vacate -> Dirty -> Available)
  - H11: Out of Service (mandatory reason, return-to-service flow)
  - H12: Occupied Asset Rejection (cannot double-book)

### Operator Playbook Outline

```
1. Starting Your Shift
   - Open hamilton-erp.v.frappe.cloud on the tablet
   - Log in with your operator credentials
   - Navigate to Asset Board (/app/asset-board)
   - Review current state of all rooms and lockers

2. Checking In a Guest
   [Phase 2 — POS integration required]

3. Managing Assets
   - Green tile = Available (ready for next guest)
   - Blue tile = Occupied (guest is inside)
   - Orange tile = Dirty (needs cleaning)
   - Red tile = Out of Service
   - Tap a tile to see available actions

4. Vacating a Room/Locker
   - Tap the blue (Occupied) tile
   - Select "Vacate" from the action menu
   - Choose method: Key Return or Discovery on Rounds
   - Tile turns orange (Dirty)

5. Marking Clean
   - Tap the orange (Dirty) tile
   - Select "Mark Clean"
   - Tile turns green (Available)
   - Or use "Mark All Clean" for bulk operations

6. Out of Service
   - Tap any tile -> "Set Out of Service"
   - Enter mandatory reason (e.g., "plumbing leak", "deep cleaning")
   - Tile turns red
   - To return: tap red tile -> "Return to Service" -> enter reason

7. Troubleshooting
   - Board not updating? Hard refresh (Cmd+Shift+R on Mac, Ctrl+Shift+R on PC)
   - 403 error? Log out and log back in
   - Asset stuck in wrong state? Contact Chris
```

---

## 5. Phase 2 Planning Reminders

### What Phase 2 Covers

Phase 2 is POS Integration and Check-in Flow. See `docs/build_phases.md` for the full spec.

**Core deliverable:** Standard ERPNext POS transaction triggers custom asset assignment.
Guest pays for admission at POS -> operator assigns a room/locker -> asset moves to Occupied.

### Prerequisites Before Starting Phase 2

- [ ] Phase 1 Task 25 complete (all acceptance tests passing)
- [ ] v1.0.0 tagged and deployed to Frappe Cloud
- [ ] Operator playbook reviewed by at least one non-developer

### Key Design Decisions to Make

1. **POS Profile configuration:** Which payment methods? Cash only for launch, or also card?
2. **Admission items:** Standard Room, Deluxe Room, Locker, Comp variants.
   Need Item Tax Templates (HST Taxable 13%, HST Exempt).
3. **Asset assignment UX after payment:** How does the operator pick which room/locker?
   Options: popover on Asset Board, dialog after POS submit, or auto-assign.
4. **Comp admission flow:** $0 item requires mandatory reason. Creates Comp Admission Log entry.
   DEC-055 deferred the comp flow to Phase 2.

### Technical Prep

- `hooks.py` already has a `doc_events` stub for Sales Invoice `on_submit` — wired up but empty.
- `api.py` has `assign_asset_to_session()` as a Phase 2 stub (`pass` body, `methods=["POST"]`).
- Venue Session doctype already has all V5.4 forward-compatibility fields (identity_method,
  membership fields, arrears fields — all nullable, defaulting to "not_applicable" where relevant).
- `test_adversarial.py` Family F (8 tests) are all `skipTest("Phase 2")` — they test financial
  integration paths that don't exist yet. These will be the first tests to unskip.

### Phase 2 QA Tests (from build_phases.md)

| Test | Description |
|------|-------------|
| H1 | Standard Room Check-in |
| H2 | Standard Locker Check-in |
| H3 | Check-in with Retail Items |
| H4 | Cancel Mid-Transaction |
| H5 | Comp Admission |
| H6 | Standalone Retail Sale |
| H7 | Tax Handling |
| H20 | Auto-Applied Promotion |
| H21 | No Promotion Active |

### Risks and Open Questions

- **POS Profile sharing:** Club Hamilton has one POS terminal. If a second terminal is added later,
  POS Profiles may need per-terminal configuration. Defer to Phase 4 if not needed at launch.
- **Payment integration:** Stripe/card terminal integration is explicitly deferred per build spec section 14.
  Phase 2 is cash-only unless Chris decides otherwise.
- **Item Group hierarchy:** ERPNext requires items in Item Groups. Need to decide: flat list
  (Admissions, Retail) or nested (Admissions > Rooms, Admissions > Lockers, Retail > Beverages, etc.).

---

## 6. Asset Board UI Design — Approved 2026-04-13

- Full spec in `docs/design/asset_board_ui.md` — approved via interactive mockup V6
- Two new Hamilton Settings fields required before Task 17 ships: `show_waitlist_tab`, `show_other_tab`
- Waitlist tab is Phase 2 placeholder only in Phase 1
- Top summary strip removed from header — footer is sole count display
- Accessibility standard applied throughout: 56px tab height, 15px font, 3px tile borders (staff aged 50+)
- Watch tab always visible regardless of venue feature flags
- Tab badges: green = available count per tab; Watch badge = warning + overtime + OOS combined, pulsing red
- Tile expand: 1.5x scale (2x was considered and rejected), one tile expanded at a time
- Tab content layout: four sections per tab (Available → Needs Cleaning → Occupied → Out of Service), empty sections hidden, time-based sorting within each section
- Watch tab aggregates warning + overtime + OOS across all categories, grouped by category row

---

## 7. Optimization Opportunities (from 2026-04-12 Code Review)

Identified during a full source review. No changes made — these are future improvements.

### High Impact

| File | Opportunity | Impact | Risk |
|------|-------------|--------|------|
| `lifecycle.py` | `_set_asset_status` does a second FOR UPDATE read that could be folded into the existing lock-body read | Medium | Medium |
| `api.py` | `_mark_all_clean` fires N+1 realtime publishes (one `publish_status_change` per asset + one final `publish_board_refresh`) | Medium | Low |

### Low Impact / Cleanup

| File | Opportunity | Impact | Risk |
|------|-------------|--------|------|
| `utils.py` | **Entirely dead code** — no Python file imports from it. Contains `create_asset_status_log`, `get_current_shift_record`, `get_next_drop_number`. All superseded by `lifecycle._make_asset_status_log`. | Low | None |
| `lifecycle.py` | `_set_vacated_timestamp` and `_set_cleaned_timestamp` are one-line DB writes that could be folded into `_set_asset_status` | Low | Low |
| `locks.py` | Extra Redis round-trip in finally block for TTL-expiry logging | Low | Low |

## 8. Fraud Research Findings (2026-04-14)

Key risks identified for ANVIL venues:

| Attack | Likelihood | Mitigation |
|--------|-----------|------------|
| **Cash skimming** (no session entered) | Highest | Key/barcode scan before payment (DEC-066, Phase 2) |
| **Transaction void after cash collected** | Medium | Lock cancel permission to Floor Manager+ only |
| **Offline mode abuse** (browser cache wipe) | Medium | Dual WAN failover, no offline-first mode |
| **Role self-escalation** | Medium | System Manager restricted to Chris only |
| **Direct DB access** | Low | Frappe Cloud managed — no direct DB access for staff |
| **Ghost employees / vendor fraud** | Low | Out of scope for Phase 1 — standard ERPNext controls |

Key scan/barcode decision (DEC-066): Physical key must be scanned BEFORE payment in Phase 2.
Dual purpose: fraud prevention + asset/payment verification. Pairs with blind cash reconciliation.

---

## 9. Production Hardening Checklist (Pre-Handoff)

Items from pre-handoff research sessions, April 2026. Cross-referenced with Task 25 checklist.

### Critical Items

- **pyproject.toml** — Frappe Cloud now requires ALL apps to have this at repo root with bounded dependency:
  `frappe = ">=16.0.0-dev,<17.0.0-dev"` (comma required, not space). Without it, deploys are blocked.
- **Fixtures export** — Custom Fields, Roles, DocPerms, Property Setters are DB-only until exported.
  Command: `bench --site {site} export-fixtures --app hamilton_erp`. Must be declared in `hooks.py` AND exported.
- **hooks.py audit** — Remove wildcard `doc_events {"*": ...}` (runs on every doc save site-wide).
  Every function called from hooks.py must have try-except + `frappe.log_error()`.
- **Document Versioning** — Enable BEFORE records are created (cannot retroactively get history).
  Enable on: Venue Asset, Venue Session, Cash Drop, Shift Record, any financial DocType.
- **Audit Trail** — Enable in System Settings. Tracks who did what actions across the whole site.

### Patches Needed

All UI configuration must become idempotent patches so new venues require zero manual clicking:
- `validate_venue_config` — fail loudly if required `site_config` keys missing
- `create_anvil_roles` — ANVIL Front Desk, Floor Manager, Manager
- `set_system_settings` — audit trail, document versioning
- `seed_asset_statuses` — status list
- `configure_session_numbering` — sequence format

### Other Items

- **init.sh** — Start bench, run migrations, run full test suite, exit non-zero on failure.
  Every session starts from known-good state.
- **Git tag** — `git tag v1.0.0-hamilton-handoff && git push origin --tags` before Philadelphia build.
- **Frappe Cloud error log** — Zero unacknowledged errors before handoff.

---

## 10. Knowledge Portability Strategy

Each new venue inherits the full Hamilton knowledge base:
- `docs/decisions_log.md` — architectural decisions + reasoning
- `docs/lessons_learned.md` — bugs, mistakes, fixes
- `docs/venue_rollout_playbook.md` — step-by-step venue setup checklist
- `docs/claude_memory.md` — session bridge and planning notes

**Inbox workflow:** `docs/inbox.md` bridges claude.ai and Claude Code.
- End of claude.ai session: paste summary into `inbox.md` on GitHub
- Start of Claude Code session: "read inbox.md, merge into docs, clear it"

Each venue build should be faster than the last.

---

## 11. Testing Strategy — Current Status and Gaps

### Adversarial Test Suite (`test_adversarial.py`)

45 total tests across 6 attack families. 37 active, 8 skipped (Family F — Phase 2 financial).

| Family | Tests | Description |
|--------|-------|-------------|
| A — State Machine Violations | 10 | Illegal transitions, double-actions |
| B — Concurrency & Lock Attacks | 6 | Contention, lock release after failure |
| C — Session Sequence Attacks | 6 | Format, monotonicity, rollover, cold Redis |
| D — Input Validation Attacks | 9 | None, empty, whitespace, bad kwargs |
| E — Bulk Operation Attacks | 5 | Bulk clean, skip-occupied, error isolation |
| F — Financial & Phase 2 | 9 (all skipped) | Functions don't exist yet |

Includes a crash reporter that writes JSON results to `/tmp/hamilton_adversarial_report.json`.
Family F tests unlock when Phase 2 financial integration is built.

### Advanced Database and Performance Tests (`test_database_advanced.py`)

51 tests across 8 categories (R1–R8). Added 2026-04-14. Covers infrastructure beneath the
application logic — verifies that MariaDB, Redis, and Frappe v16 behave the way Hamilton ERP
assumes they do.

| Category | Tests | Description |
|----------|-------|-------------|
| R1 — Database Indexes | 7 | INFORMATION_SCHEMA verification for all search_index fields |
| R2 — Query Performance | 6 | EXPLAIN plans, SLA timing (<100ms board, <200ms session, <50ms lock) |
| R3 — MariaDB Edge Cases | 7 | REPEATABLE-READ isolation, row locking, datetime(6), NULL handling, unique constraints |
| R4 — Redis Edge Cases | 7 | TTL, INCR overflow, Lua CAS release, NX semantics, cold-start DB fallback |
| R5 — Frappe v16 Behaviour | 9 | in_test flag, override classes, scheduler, roles, track_changes, autoname |
| R6 — Fraud Detection | 5 | Orphan sessions, duplicate assignment, bulk clean safety, OOS auto-close |
| R7 — Concurrency | 3 | Sequential lock acquisition, repeatable lifecycle, version monotonicity |
| R8 — Data Integrity | 7 | Timestamp ordering, field nullability, cleanup after state transitions |

Full specification: `docs/testing_guide.md` → "Advanced Database and Performance Tests".

### Stress Simulation (`test_load_10k.py`)

5 tests. Creates 50 Venue Assets, runs 200 complete check-in cycles each (10,000 total).
Tests session number uniqueness, Redis INCR correctness, connection pool exhaustion,
retry loop handling, and midnight boundary fix. Runtime: ~5-10 minutes on local bench.

### Mutation Testing (`scripts/mutation_test.py`)

Status: **Complete — 91% kill score (10/11 killed, 1 survivor).** Run on 2026-04-14.
Custom script because mutmut v2 fails on Python 3.14 and mutmut v3 is incompatible with
Frappe's bench-required test init. Script applies 15 mutations to lifecycle.py and locks.py,
runs bench tests after each, reports kill/survive.
- Survivor: `LOCK_TTL_MS = 1` — tests complete too fast for 1ms TTL to expire. Pinned by R4 TTL assertion.
- Target: lifecycle.py and locks.py. Kill ratio goal > 80% — **exceeded at 91%**.

### Property-Based Testing (`test_hypothesis.py`)

Status: **Complete — 8 tests, 0 failures across ~540 random inputs.** Run on 2026-04-14.
- P1 Session number format (4 tests): format, date encoding, positive sequence, 4-digit padding
- P2 State machine (2 tests): random action sequences never corrupt, lifecycle repeatable 1-5x
- P3 Cash math (2 tests): float sum precision, variance sign preservation

### Slow Query Log Analysis

Status: **Complete — 0 application queries exceeded 10ms.** Run on 2026-04-14.
MariaDB slow_query_log enabled at 10ms threshold during full 353-test run.
Only 2 queries exceeded 10ms — both were Frappe framework `information_schema.tables` scans (15ms, 11ms).
All Hamilton ERP queries (asset board, session creation, lock acquisition, session number LIKE) under 10ms.

### Database Indexes

Status: **Complete — all indexes verified.** All `search_index` fields in DocType JSON have
corresponding MariaDB indexes confirmed via `INFORMATION_SCHEMA.STATISTICS` (R1 tests).
Tables covered: tabVenue Asset, tabVenue Session, tabShift Record, tabCash Drop, tabAsset Status Log.

### Contract Testing

Status: **Not applicable for Phase 1.** No external API consumers exist.
Revisit when a second system (e.g., a mobile app, a kiosk) consumes hamilton_erp APIs.

### Structured Logging

`frappe.log_error()` is used in lifecycle.py for critical path failures.
No formal logging strategy documented. Phase 2 should define:
- What events to log (all state transitions? only errors?)
- Log format and retention (Frappe's built-in Error Log vs external)
- Alerting thresholds (e.g., >5 lock contentions in 1 minute)

### Observability Dashboard

Status: **Not built.** Belongs in Phase 2 or later.
Planned components:
- Asset state distribution (how many Available/Occupied/Dirty/OOS at any time)
- Session throughput (check-ins per hour, average stay duration)
- Lock contention rate (how often Redis NX fails)
- Error rate from Frappe Error Log
- Frappe Cloud native monitoring may suffice for Phase 1

### Two-Tab Realtime Sync Test

Phase 1 acceptance requirement from `build_phases.md`: two browser tabs viewing the asset
board must stay in sync within ~1 second of any state change via `frappe.publish_realtime`
with `after_commit=True`. This is a **manual** QA test — not automated.
Procedure: open two tabs to `/app/asset-board`, change state in tab A, verify tab B updates.

### Operator Acceptance Testing (Manual QA — H10, H11, H12)

These are manual browser tests on `hamilton-test.localhost`, not automated.
Run before each deploy to Frappe Cloud.

**H10 — Vacate and Turnover:**
1. Open Asset Board on tablet/browser
2. Tap an Available (green) room tile → Assign → tile turns blue (Occupied)
3. Tap the blue tile → Vacate → select "Key Return" → tile turns orange (Dirty)
4. Tap the orange tile → Mark Clean → tile turns green (Available)
5. Verify Asset Status Log shows all 4 transitions with correct timestamps

**H11 — Out of Service:**
1. Tap any Available tile → Set Out of Service
2. Verify mandatory reason field appears (cannot submit empty)
3. Enter reason → Submit → tile turns red (Out of Service)
4. Tap red tile → Return to Service → enter reason → tile turns green
5. Verify Asset Status Log shows OOS entry and return with reasons

**H12 — Occupied Asset Rejection:**
1. Occupy a room (Available → Occupied)
2. Attempt to occupy the same room again
3. Verify system rejects with appropriate error message
4. Verify the first session is unaffected

---

## Expert Testing Checklist

10 expert-level testing activities beyond unit/integration tests. Full details in `docs/testing_guide.md` → "Expert-Level Testing — Full Checklist".

### Before Go-Live
| # | Activity | Description |
|---|----------|-------------|
| 1 | Security Penetration | SQL injection, privilege escalation, CSRF bypass, rate limiting |
| 2 | Chaos Testing | Kill Redis mid-shift, network failure mid-transaction, bench restart mid-session |
| 3 | Data Migration | Seed 6 months historical data (10k+ sessions), verify patches and performance |

### Task 25
| # | Activity | Description |
|---|----------|-------------|
| 4 | ~~Property-Based (Hypothesis)~~ | ✅ Done 2026-04-14 — 8 tests, 0 failures, ~540 random inputs |
| 5 | ~~Mutation Testing~~ | ✅ Done 2026-04-14 — 91% kill score (10/11), custom script |
| 6 | Load Testing | 20 concurrent check-ins over 2 hours, measure degradation |
| 7 | ~~Slow Query Log~~ | ✅ Done 2026-04-14 — 0 app queries >10ms |

### Phase 2
| # | Activity | Description |
|---|----------|-------------|
| 8 | Contract Tests vs ERPNext | Sales Invoice, POS closing, GL entry hooks after ERPNext updates |
| 9 | Structured Logging | JSON log entries for session creation, lock acquisition, cash drops |
| 10 | STRIDE Threat Model | Every entry point, trust boundary, data flow, documented mitigation |

---

## Claude Code Operating Tips

### /compact Habit
Run `/compact` when context hits 70%. Context usage shows in the status bar at the bottom of Claude Code. Bloated context leads to worse code decisions — critical on long ERP build sessions.

### Proof Demand Technique
After Task 25 deploy, never just ask "did it work?" — demand proof:
> "Prove to me this works — show me the diff in behavior between main and this branch."
Claude runs both branches, compares outputs, and presents concrete evidence.

### Setup Audit (run after Phase 1)
Check the full Claude Code setup for gaps using this command inside Claude Code:
> "Fetch and follow the onboarding instructions from: https://raw.githubusercontent.com/FlorianBruniaux/claude-code-ultimate-guide/main/tools/onboarding-prompt.md"
Flags missing security hooks, incomplete MCP setup, and CI integration gaps.

## Engineering Blog Action Items — Completed 2026-04-15

### Skills and Agents Created
- `.claude/skills/frappe-v16/SKILL.md` — Frappe v16 platform rules (in_test flag, extend_doctype_class, type comparisons, Redis lock key format and bug history)
- `.claude/skills/hamilton-testing/SKILL.md` — test site, bench location, run commands, 5 core test files, baseline counts (270 passing / 7 skipped)
- `.claude/agents/security-reviewer.md` — Opus-powered security review subagent for Frappe role gaps, silent exceptions, string comparisons, hardcoded values
- PostToolUse test hook added to `.claude/settings.json` — runs full test suite after every `.py` edit (warn-only, `exitOnFailure: false`)

### Task 25 Workflow Notes
- Use `/clear` between every Task 25 sub-item — do not carry context across sub-items
- Use Plan Mode before starting any Task 25 item (Ctrl+Shift+P in Claude Code)
- The 36 `frappe.flags.in_test` replacements across 5 files should use the fan-out pattern: loop file by file with `claude -p`, one clean context per file
- Replace the manual 3-AI review with the Writer/Reviewer two-session pattern: Session A writes, Session B reviews from fresh context with no bias
- Do not deploy to Frappe Cloud until all entries in `docs/feature_status.json` show `"passes": true`
- Source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## Inbox Merge — 2026-04-15

### Tool Evaluations (DEC-067 through DEC-069)
- **Cognee** — rejected. Graph/vector memory is overkill; current docs system is sufficient.
- **Playwright** — deferred to Phase 2. Phase 1 is backend-only; Playwright useful for Asset Board UI tests and has GitHub Actions integration.
- **"Everything Claude Code"** — rejected. Multi-agent framework for large teams, not solo Frappe dev.
- **Karpathy 4 Principles** — already in Task 25 checklist. At Task 25, run `claude -p` with Karpathy prompt to strengthen CLAUDE.md.

### Phase 2 Testing Gaps Added to testing_checklist.md
5 gaps added (items 1–2 highest priority for Phase 2 start):
1. Dedicated test site isolation
2. Role × API permission matrix
3. Playwright UI tests
4. Background job / scheduler health tests
5. Frappe Recorder N+1 profiling

Plus 2 pre-production security items: SQL injection audit of `frappe.db.sql()` calls, XSS audit of `render_tile()` in `asset_board.js`.

### Frappe/ERPNext Mastery Guide Reference
Source: `github.com/mohamed-ameer/Frappe-ERPNext-Tutorial-Mastery`
**Caveat:** Community flagged parts as AI-generated with possible errors. Use as a **topic navigation index only** — verify all code independently.

**Relevant chapters by phase:**
- **Task 25:** Ch.12 (Security & RBAC), Ch.12.3 (Audit Logs), Ch.3 (Workflows), Ch.13 (Fixtures)
- **Phase 2:** Ch.13 (Background Jobs, Real-Time Sync), Ch.9.1 (Stripe), Ch.9.5 (Webhooks)
- **Before go-live:** Ch.11 (Frappe Cloud deployment), Ch.10.3 (Backup & Restore automation)

### Frappe Cloud Version Pinning (Task 25 action item)
- Before go-live, verify `hamilton-erp.v.frappe.cloud` is pinned to a specific stable v16 minor version — do not auto-update to latest.
- Current latest: v16.14.0 (released 2026-04-14). Removes forced six-decimal rounding on valuation rate fields — verify no impact on Hamilton's session pricing after any platform update.
- Task 25 checklist: (1) check running version, (2) confirm auto-update settings in Frappe Cloud dashboard, (3) pin to current stable minor, (4) document pinned version here.

---

## Session Checkpoint — 2026-04-16 00:15 EDT

### What was built
- **Asset Board V6 rebuild** — complete rewrite of `asset_board.js` (403 lines) and `asset_board.css` (473 lines) per approved design spec `docs/design/asset_board_ui.md`
- **Hamilton Settings feature flags** — added `show_waitlist_tab` and `show_other_tab` fields to Hamilton Settings DocType, wired to `api.py`
- **Visual gap fixes** — pinned footer via `calc(100vh - 85px)`, status-coloured section headers, active tab border overlap technique
- **Security audit compliance** — XSS tests updated for V6 tile template (`asset.name` not `asset.asset_name`), `frappe.utils.escape_html` used inline (no alias)
- **CSS refinements** — `box-shadow: none` on normal tiles (shadow only on expanded + overtime), `text-overflow: ellipsis` on tile status labels to prevent "OUT OF SERVICE" wrapping
- **Tab rename** — "VIP" tab renamed to "GH Room" to match the asset tier name
- **Saturday night simulation** — `hamilton_erp/scripts/saturday_night_sim.py` created; hamilton-test.localhost populated with 5 occupied rooms (overtime), 3 dirty, 1 OOS for visual QA
- **Tier migration** — ran `bench migrate` on hamilton-test.localhost to sync "Glory Hole" → "GH Room" schema change
- **Import fix** — `test_stress_simulation.py` updated from `frappe.tests.utils` to `frappe.tests`

### Decisions made
- Tab labels: Lockers · Single · Double · GH Room · Waitlist · Other · Watch (VIP label rejected in favour of tier name)
- `box-shadow: none` as default on `.hamilton-tile` — intentional shadows only on expanded tiles and overtime pulsing
- Border-radius 6px added to design spec as formal rule
- Session_start backdating via direct MariaDB SQL is acceptable for simulation data (doesn't violate state machine invariants)

### Current branch state
- Branch: `feature/asset-board-ui-rebuild`
- Latest commit: `c9302d9` (Saturday night sim script)
- PR #8 open: "feat(ui): Asset Board V6 rebuild — tabs, dark theme, tile expand"
- All core tests pass (security audit, lifecycle, API, rendering, adversarial, database, hypothesis)
- Pre-existing failures: `test_stress_simulation.py` Phase 2 stubs, `test_load_10k` timeout

### Next steps
- Continue populating simulation data per full Saturday night plan (lockers, remaining rooms)
- Visual QA in browser against spec
- Merge PR #8 when visual QA passes
- Resume Taskmaster task queue (Tasks 17–22 are the Asset Board UI tasks)

## 2026-04-24 — V9 Asset Board Shipped to main

**V9 is live on `main`.** Squash commit `1cc9125` ("feat(asset-board): ship V9 — apply M1-M5 + S1-S6 + countdown colour reversal") merged PR #8 into `main` on 2026-04-24. **PR #8 is merged and closed.** The `feature/asset-board-ui-rebuild` remote branch was deleted as part of the squash merge.

**Locked source of truth:** `docs/design/asset_board_mockup_v7.html` is now the V9 source-of-truth mockup. All 68 interactive tests pass. Do not edit it without first checking `docs/decisions_log.md` and following the Part 12 protocol for reversing a locked decision.

**V9 integration plan archived:** `docs/design/archive/v9_integration_plan.md` (moved from `docs/design/` via `git mv` in commit `9eb5ff9`). Treat the archived plan as historical — V9 is shipped, the plan is no longer a live spec.

**decisions_log.md Part 3.1 amended on 2026-04-24:** countdown text colour reversed from amber to red (`#f87171`) for the time-status row on overtime tiles. The original amber rule was overturned same-day after the v9_color_test.html A/B prototype; the amendment note is recorded in Part 3.1 of `docs/decisions_log.md`.

Locked design rules (consult `docs/decisions_log.md` before changing any of these):
- Single overtime state (no two-stage warning/overtime)
- "Xm late" / "Xm left" wording (no +/- signs)
- OT badge on top border of tile (not corner)
- Status text removed from tiles
- Tab visibility = enabled_in_config AND has_at_least_one_asset
- OOS reasons are GLOBAL (single list for all venues, amendable in Phase 2 via DocType)
- Occupied tiles have NO Set Out of Service button
- Lockers have NO Dirty state
- Countdown threshold = 60 minutes (hardcoded in V9; Phase 2 makes it venue-configurable)
- Countdown text colour = red `#f87171` (amended 2026-04-24, was amber)
- "Set Out of Service" button label = "Set OOS"; sub-button = "Rounds" (M1)
- Time-status text = 12px bold (M3)
- "Needs Cleaning" section header renamed to "Dirty" (S1)

Next: proceed to Tasks 23–25 per existing Phase 1 plan.

## Drift Prevention Rule (added 2026-04-27)

The full rule lives in `CLAUDE.md` at the repo root: "Verify Before Claiming Done."

Summary: read actual code before claiming anything is shipped, distinguish
spec-committed from implementation-working, state uncertainty plainly. The
2026-04-24 V9 incident is the canonical example of why this rule exists.

Two more drift-prevention layers are pending:
- Layer 2 (~90 min): GitHub Actions CI — Tier 1 item T1.1 in production_handoff_audit_merged_2026-04-25.md
- Layer 1 (~4 hours, Task 25): V9 conformance tests — one test per locked decision in decisions_log.md
