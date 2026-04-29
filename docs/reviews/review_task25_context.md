# Phase 1 Pre-Deploy Review — Context-Aware (full implementation visibility)

**Audience:** ChatGPT, Grok, and a fresh Claude (new tab) with the Hamilton ERP repo loaded as context.

**Goal:** A second-opinion deploy review **with full implementation visibility**. Pair this with the blind review (`review_task25_blind.md`) — both must agree on the cutover plan.

**Format you should respond in:**
1. **Production-readiness checklist** — go/no-go on each of the items below, one line each.
2. **Top 3 latent bugs** the existing test suite would not catch, with file:line references.
3. **One thing to verify in `bench --site hamilton-erp.v.frappe.cloud console`** before flipping the URL.
4. **One thing to verify with `curl` against the live site** before flipping the URL.

---

## Repo to load as context

`https://github.com/csrnicek/hamilton_erp` (default branch: `main`).

If you are a Claude with code-tool access: clone it. If you are a frontier model with web search: read `CLAUDE.md`, `docs/decisions_log.md`, `docs/coding_standards.md`, `docs/phase1_design.md`, `hamilton_erp/lifecycle.py`, `hamilton_erp/locks.py`, `hamilton_erp/api.py`, `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`, `hamilton_erp/test_e2e_phase1.py`, and `.github/workflows/tests.yml`.

## Stack and environment

- **App:** `hamilton_erp` — custom Frappe/ERPNext v16 app.
- **Site (live):** `hamilton-erp.v.frappe.cloud` (private bench `hamilton-erp-bench`, bench-37550, N. Virginia region).
- **Site (test, local):** `hamilton-unit-test.localhost` — `allow_tests = true`, used by all `bench run-tests`.
- **Site (dev browser, local):** `hamilton-test.localhost` — never receives test runs (would corrupt setup wizard state).
- **Hard-pinned versions:** Python 3.14 (per Frappe 16.16.0 pyproject), Node 24 (per Frappe package.json `engines`), MariaDB 12.2.2, Redis (Frappe-bundled).
- **CI:** GitHub Actions, vendored Frappe setup composite action. `frappe/payments@develop` installed in CI to satisfy a transitive Link-field dependency on `Payment Gateway` for 6 IntegrationTestCase suites.

## Phase 1 scope (in this deploy)

State machine + lockings + Asset Board page. **No POS, no pricing, no refunds, no cash drops, no shift reconciliation.** Operators record asset state changes only; cash continues to flow through the existing manual process.

## Locking architecture

- **Key:** `hamilton:asset_lock:{asset_name}` (asset-only, not asset+operation — see DEC-024).
- **TTL:** 15 seconds.
- **Layers:**
  1. Redis `SETNX` with TTL.
  2. MariaDB `SELECT ... FOR UPDATE` on `tabVenue Asset` row inside the same transaction.
  3. Optimistic `version` column — increments on every state change; controllers refetch and check before save.
- **Lock body has zero I/O.** Realtime publishes happen `after_commit` (`frappe.publish_realtime` enqueued via Frappe's transaction hook).
- **Lock helper:** `hamilton_erp/locks.py` — context manager `asset_status_lock(asset_name, operation)`.
- **Realtime publisher:** `hamilton_erp/realtime.py` — events `hamilton_asset_status_changed`, `hamilton_asset_board_refresh`.

## Lifecycle public API

`hamilton_erp/lifecycle.py` exposes:

- `start_session_for_asset(asset_name, *, operator, customer=WALKIN_CUSTOMER) -> str` (returns Venue Session name)
- `vacate_session(asset_name, *, operator, vacate_method)` (`Key Return` | `Discovery on Rounds`)
- `mark_asset_clean(asset_name, *, operator, reason=None)`
- `set_asset_out_of_service(asset_name, *, operator, reason)` (reason **required**)
- `return_asset_to_service(asset_name, *, operator, reason)` (reason **required**)
- `_next_session_number(*, for_date=None)` — Redis INCR with DB fallback. Format: `S{YYYYMMDD}-{NNNN}`.

`venue_asset.py` whitelisted methods are thin delegators — they accept the same args, take the lock, and call into `lifecycle.py`.

## Audit log behavior

`_make_asset_status_log` (lifecycle.py:70 and following) creates an `Asset Status Log` doc on every state transition. It **short-circuits when `frappe.in_test == True`** — see lifecycle.py:86. The module attribute `frappe.in_test` is distinct from `frappe.local.flags.in_test`; both must be cleared for E2E tests to write real logs (see `test_e2e_phase1.py::real_logs`).

In production this guard is always `False`, so every transition writes a log row. **There has been no sustained load measurement of the audit log in production.**

## What the test suite covers

- 17 modules in `/run-tests`, ~340 server-side tests:
  - lifecycle (state transitions)
  - locks (3 layers)
  - venue_asset (whitelisted methods)
  - api_phase1 (read API + verb pinning)
  - asset_board_rendering (JS source-substring contracts on `asset_board.js`)
  - e2e_phase1 (H10/H11/H12 — 18 tests)
  - environment_health (smoke checks)
  - security_audit (SQL injection, XSS)
  - database_advanced (DB perf, MariaDB, Redis, fraud)
  - hypothesis (property-based: session number, state machine, cash math — cash math is dormant for Phase 1 but kept green)
  - others: utils, bulk_clean, additional_expert, checklist_complete, frappe_edge_cases, extreme_edge_cases, seed_patch.
- Schema snapshot test in `test_api_phase1.py` (`REQUIRED_ASSET_FIELDS`) — any field added or removed without explicit allowlist update fails CI.
- Verb pinning: `TestAssetBoardHTTPVerb` invokes `frappe.handler.execute_cmd` with a spoofed request method and asserts `GET → 200`, `POST → PermissionError`.

## What the test suite does NOT cover

- The Frappe Cloud production environment specifically (no dedicated production canary or smoke test there).
- Front-end interaction (Cypress / Playwright) — JS contracts are tested via source substring matching only.
- Realtime delivery from a process the test runner does NOT own (e.g. Frappe Cloud's async worker queue).
- Concurrent operator behavior beyond the property-based `Hypothesis` invariants.
- The `frappe.in_test` short-circuit in `_make_asset_status_log` — the audit log path is exercised only by `test_e2e_phase1.py` via the `real_logs()` context manager.

## Deploy mechanics

1. Push to `main` triggers Frappe Cloud auto-pull (~3 min).
2. Manual `bench migrate` on the cloud console runs the seed patch (`v0_1.seed_hamilton_env`).
3. Manual QA against `https://hamilton-erp.v.frappe.cloud/app/asset-board` (Administrator role + a Hamilton-only role) — full Phase 1 acceptance checklist (`docs/build_phases.md`).

Rollback: Frappe Cloud snapshot + revert. No data migration is run on this deploy that is irreversible — the seed patch is idempotent (uses `frappe.db.exists()` guards).

---

## What you are reviewing

Given the **actual implementation** visible to you:

1. **Production-readiness checklist** — for each of the items below, mark `GO`, `NO-GO`, or `NEEDS-CHECK` with one line of justification:
   - Locking integrity under simultaneous operator action
   - Audit log durability in production (no `in_test` short-circuit)
   - Realtime delivery to a second tablet within the 2-second target
   - Role gating (`Hamilton` role required to hit the API)
   - Schema snapshot drift protection
   - Idempotency of the seed patch
   - Rollback plan (snapshot + revert)
   - Verb pinning on the API
   - Performance baseline of `get_asset_board_data`
2. **Top 3 latent bugs** the test suite would not catch, with file:line references.
3. **One thing to verify in `bench --site hamilton-erp.v.frappe.cloud console`** before flipping the URL.
4. **One thing to verify with `curl` against the live site** before flipping the URL.

## Why this prompt has full context

The blind review (`review_task25_blind.md`) catches assumption errors. This context-aware review catches implementation errors. Both must pass before the cutover.
