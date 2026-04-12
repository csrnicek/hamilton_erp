# Claude Memory — Extended Context for Hamilton ERP

Persistent reference for Claude Code sessions. Captures best practices, planning notes,
tooling decisions, and Phase 2 readiness that don't belong in code comments or decisions_log.md.

**Last updated:** 2026-04-12

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

6. **Always run the full 12-module suite, always on `hamilton-unit-test.localhost`.** Never run tests
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

### Feature Flags

Not currently implemented. When multi-venue ships:

- Use Hamilton Settings (Single DocType) or a new Feature Flag DocType.
- Gate new features behind flags so Hamilton can stay on the stable path while Philadelphia
  gets experimental features.
- Consider Frappe's `frappe.flags` for runtime feature gating during tests.

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

### Semantic Versioning

- [ ] Tag `v1.0.0` when all 25 tasks pass
- [ ] CHANGELOG.md entry for v1.0.0 with full feature list
- [ ] GitHub Release with Before/After table

### Testing Quality Gates

- [ ] **All 12 test modules green** — zero failures, skipped tests documented
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

## 6. Optimization Opportunities (from 2026-04-12 Code Review)

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
