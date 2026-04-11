# Hamilton ERP — Claude Code Context

## About Chris (the human you are working with)

- **Experience level:** Beginner with coding, terminal, and developer tools
- **Always give:** Explicit step-by-step instructions specifying exactly which window or app to type commands in
- **Never assume:** That Chris knows what a command does, where to type it, or what the output means
- **Always explain:** What just happened in plain English after each step completes

## Communication preferences

- Be direct and concise — no filler phrases, no excessive praise
- When something fails, diagnose properly before suggesting a fix — do not guess and iterate
- If a task is better done in Claude Code terminal than the browser, say so immediately
- Never use browser automation tools to navigate or click on behalf of Chris — it never works
- When blocked, stop and ask rather than trying workarounds that waste time
- Surface errors early — do not try to silently fix problems that Chris should know about

## Technical environment

- **Machine:** M1 Max MacBook Pro, 64GB RAM ("Chris's laptop")
- **OS:** macOS
- **Local bench:** `~/frappe-bench-hamilton` (Frappe v16, ERPNext v16, Python 3.14, Node 24, MariaDB 12.2.2, Redis)
- **Test site:** `hamilton-test.localhost`
- **MariaDB root password:** `admin`
- **App path:** `~/hamilton_erp` (symlinked into bench)
- **Run tests:** `cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp`

## Project: Hamilton ERP

Custom Frappe/ERPNext v16 app for Club Hamilton — a men's bathhouse in Hamilton, Ontario.

- **Frappe Cloud site:** `hamilton-erp.v.frappe.cloud` (live, N. Virginia)
- **GitHub repo:** `https://github.com/csrnicek/hamilton_erp`
- **Current phase:** Phase 1 — Asset Board and Session Lifecycle

### What this app does
- Manages 59 physical assets (26 rooms, 33 lockers) with states: Available → Occupied → Dirty → Available, plus Out of Service
- Three-layer locking (Redis + MariaDB FOR UPDATE + optimistic version field) prevents double-booking
- Blind cash control (operators drop cash without seeing expected totals)
- Single operator most of the time, anonymous walk-in guests, no membership

### Key decisions (always respect these)
- See `docs/decisions_log.md` for DEC-001 through DEC-055
- Locking: `docs/coding_standards.md` §13 — zero I/O inside lock body, realtime after_commit only
- Redis key is asset-only: `hamilton:asset_lock:{asset_name}` — NOT asset+operation
- FOR UPDATE (not FOR NO KEY UPDATE) — MariaDB syntax
- Tabs not spaces — all Python files use tabs per coding_standards.md §11

### Phase 1 implementation plan
Full plan: `docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md`
- 25 tasks, TDD, Subagent-Driven Development
- Test harness: 26 tests passing (6 lifecycle, 3 locks, 17 venue_asset)
- 6 pre-existing setUpClass failures in Phase 0 stub doctypes — known, out of scope

## Workflow rules

1. **Always read these docs at session start:** `docs/current_state.md`, `docs/decisions_log.md`, `docs/coding_standards.md`, `docs/build_phases.md`
2. **Use Subagent-Driven Development** for all Phase 1 tasks — dispatch implementer → spec reviewer → code quality reviewer → fix → re-review
3. **Push to GitHub after every task** — every commit goes to `origin/main`
4. **Never use browser automation** — always give Chris manual instructions instead
5. **Test before committing** — run the relevant test modules and confirm green before git add
6. **Explain test results in plain English** — Chris is a beginner; "15/15 passing" needs a one-line explanation of what that means

## 3-AI review checkpoints (remind Chris at these points)
Run ChatGPT + Grok + Claude (new tab) review after:
- Task 9 (all 5 lifecycle methods complete)
- Task 11 (seed patch done)
- Task 21 (full Asset Board UI complete)
- Task 25 (final Frappe Cloud deploy)

Review files are saved at:
- Blind review prompt: `docs/reviews/review_task9_blind.md`
- Context-aware review prompt: `docs/reviews/review_task9_context.md`

## Things that frustrate Chris (avoid these)
- Going in circles with multiple failed attempts before finding the right answer
- Using browser automation that never works
- Not saying upfront when something should be done in Claude Code vs the browser
- Excessive confirmation prompts — use `shift+tab` to allow all edits for the session
- Vague instructions that don't specify exactly where to type a command


## Common Issues and Solutions

### Tests fail with setUpClass errors
**Symptom:** Phase 0 stub doctypes (asset_status_log, comp_admission_log, cash_drop, venue_session, shift_record, cash_reconciliation) fail with setUpClass errors.
**Cause:** Pre-existing issue — these doctypes don't set IGNORE_TEST_RECORD_DEPENDENCIES.
**Action:** Ignore these. They are out of scope. Only fix if they appear in the 5 core test modules.

### bench run-tests only runs the last --module
**Symptom:** Running multiple --module flags only runs the last one.
**Fix:** Run each module as a separate bench command. Use /run-tests slash command which does this correctly.

### Redis lock contention error during tests
**Symptom:** LockContentionError on an asset that should be free.
**Cause:** A previous test crashed and left a Redis key. The key has a 15s TTL and will expire.
**Fix:** Wait 15 seconds and retry. Or flush Redis: `redis-cli FLUSHDB` (test site only — NEVER on production).

### TimestampMismatchError on asset save
**Symptom:** frappe.TimestampMismatchError when saving a Venue Asset.
**Cause:** Two instances of the same doc were loaded, one saved, the other tried to save with a stale modified timestamp.
**Fix:** Always re-fetch with `frappe.get_doc()` inside the lock — never use a cached instance.

### session_number not populated on Venue Session
**Symptom:** session.session_number is empty after insert.
**Cause:** before_insert hook not running, or Redis down.
**Fix:** Check Redis is running (`bench doctor`). Check VenueSession controller has before_insert defined. Run `bench migrate` if doctype JSON was changed.

### Asset stuck in wrong status after failed operation
**Symptom:** Asset shows Occupied but no active session exists.
**Cause:** Transaction rolled back but Redis key was not released, or DB state corrupted manually.
**Fix:** Use /bug-triage. Check Asset Status Log for last known good state. Manually correct via bench console with `frappe.db.set_value()` — document the correction in a comment.

### Frappe Cloud deploy not reflecting latest code
**Symptom:** hamilton-erp.v.frappe.cloud shows old behavior after push.
**Cause:** Frappe Cloud auto-deploy takes 2-3 minutes. Or bench migrate did not run.
**Fix:** Wait 3 minutes. Check Frappe Cloud dashboard for deploy status. If stuck, trigger manual redeploy from dashboard.

### bench migrate fails on venue_session.json change
**Symptom:** Migration error when adding unique constraint or read_only field.
**Cause:** Existing data violates the new constraint (duplicate session_numbers).
**Fix:** Check for duplicates: `frappe.db.sql("SELECT session_number, COUNT(*) FROM tabVenue Session GROUP BY session_number HAVING COUNT(*) > 1")`. Fix duplicates before migrating.

### MariaDB "too many connections" error
**Symptom:** Can't connect to MySQL server — too many connections.
**Cause:** Connection pool exhausted, usually from a crashed worker that didn't close connections.
**Fix:** `sudo systemctl restart mariadb` on local bench. On Frappe Cloud, contact support or restart bench via dashboard.

## Pre-Deploy Checklist (before pushing to Frappe Cloud)

Run this before every deploy to hamilton-erp.v.frappe.cloud:

1. Run /run-tests — all 7 modules must pass, zero failures
2. Run bench migrate locally to verify migrations are clean
3. Check git log --oneline -5 — commit messages must be descriptive
4. Verify no debug print() statements or frappe.log() left in code
5. Confirm CLAUDE.md 3-AI review checkpoint is not due (check Task number)
6. Push to GitHub — Frappe Cloud auto-deploys within 3 minutes
7. Check hamilton-erp.v.frappe.cloud after 3 minutes to confirm site loads

## Testing Rules (Permanent)

### Always run the full test suite
Every test run must include ALL 7 modules — never run just one or two:
```
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_locks && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_checklist_complete && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_frappe_edge_cases && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_extreme_edge_cases
```
Or use the /run-tests slash command which does this automatically.

### When Chris asks for more code checks
This is a permanent rule — never skip any of these steps:
1. Add the new tests to `docs/testing_checklist.md`
2. Immediately convert them to running Python tests in the appropriate file
   (test_checklist_complete.py, test_additional_expert.py, or a new test_*.py file)
3. Update `.claude/commands/run-tests.md` to include any new test module
4. Commit all files to GitHub

Never add to the checklist without also writing the Python tests.
Never write Python tests without updating the run-tests command.
Never update run-tests without committing everything to GitHub.

## Current Project State

- Tasks 1-10 complete. Task 11 is next.
- Local bench: ~/frappe-bench-hamilton. Python 3.14, Node 24, MariaDB 12.2.2 (root pw: admin), Redis. Site: hamilton-test.localhost.
- hamilton_erp symlinked into bench from ~/hamilton_erp.

## Test Suite — 7 Modules (197+ passing, 11 skipped)

| Module | Tests | Notes |
|---|---|---|
| test_lifecycle | 29 | Core lifecycle methods |
| test_locks | 3 | Redis + FOR UPDATE lock |
| test_venue_asset | 17 | Doctype controller |
| test_additional_expert | 45 | Expert edge cases |
| test_checklist_complete | 43 + 11 skipped | Checklist items as Python |
| test_frappe_edge_cases | ~30 | Frappe v16 edge cases |
| test_extreme_edge_cases | ~30 | Frappe Cloud incidents, Hetzner, MariaDB, Redis |

Skipped tests unlock progressively:
- 3 unlock after Task 10 (session_number wired)
- 5 unlock after Task 11 (seed patch)
- 3 unlock after Task 13 / Phase 2

## Slash Commands — All in .claude/commands/

| Command | Purpose |
|---|---|
| /run-tests | Run all 7 modules |
| /fix-and-test | Run all 7 modules + autonomously fix all failures |
| /deploy | Fix-and-test then push to GitHub |
| /feature [N] | Full subagent implementation of task N |
| /task-start | Auto-detect and run next task |
| /bug-triage | Diagnose and fix a reported bug |
| /status | Project status report |
| /coverage | Coverage report |
| /mutmut | Mutation testing |
| /hypothesis | Property-based testing |
| /task9-start | Full refresh + test + dispatch for Task 9 |

## Autonomous Command Rules (Permanent)

All slash commands run autonomously. Opus never stops to ask Chris for input
unless one of these STOP conditions is hit:

1. A fix would change a DEC-0XX design decision
2. A fix risks data loss or production data modification
3. More than 5 tests fail with the same root cause (systemic issue)
4. bench migrate is required

Everything else — picking fix options, committing, pushing, continuing —
happens without Chris. Chris does not want to be part of the workflow
when he is just approving routine decisions.
