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

## Model Selection

At the start of every task, suggest the appropriate model for the work. Chris pays for both and the wrong choice wastes either money (Opus on trivial tasks) or accuracy (Sonnet on hard reasoning). Do this BEFORE starting the task, so Chris can switch with `/model` before any tool calls burn budget on the wrong tier.

**Use Sonnet for:**
- Test writing (unit tests, audit tests, regression pins)
- Security audits (SQL-injection scans, XSS checks, schema snapshots)
- Documentation updates (CLAUDE.md, testing_checklist.md, slash commands)
- Repetitive, well-defined, mechanical tasks
- Running a test suite and reporting pass/fail
- Small refactors with no design judgment (rename, extract variable)

**Use Opus for:**
- New business logic (lifecycle methods, locking, state transitions)
- Architectural decisions (anything that touches `docs/decisions_log.md`)
- Complex debugging where the root cause is unclear
- Planning (multi-step features, /feature, /task-start)
- Any task involving lifecycle / locks / state machine / concurrency
- Code review of security- or correctness-critical paths
- Anything where getting it wrong could corrupt data or break an invariant

**What to say at task start:**

If the task is Sonnet-appropriate:

> "This task is Sonnet-appropriate. Type `/model` to switch if you are currently on Opus."

If the task is Opus-appropriate:

> "This task requires Opus reasoning. Type `/model` to switch if you are currently on Sonnet."

Say it ONCE per task, at the top of the response, before the first tool call. Do not repeat it mid-task unless the task scope shifts (e.g. "add a test" becomes "and also redesign the lock helper").

The slash commands in `.claude/commands/` have `# Recommended model: ...` headers — honor those when the user invokes a slash command.

## Technical environment

- **Machine:** M1 Max MacBook Pro, 64GB RAM ("Chris's laptop")
- **OS:** macOS
- **Local bench:** `~/frappe-bench-hamilton` (Frappe v16, ERPNext v16, Python 3.14, Node 24, MariaDB 12.2.2, Redis)
- **Dev browser site:** `hamilton-test.localhost` — Chris's manual testing site. **NEVER run the test suite here.** Tests corrupt it (setup_wizard loops, 403s, wiped roles).
- **Unit-test site:** `hamilton-unit-test.localhost` — dedicated Frappe test site. `allow_tests = true`. All `bench run-tests` invocations point here. Safe to wipe/reinstall.
- **MariaDB root password:** `admin`
- **App path:** `~/hamilton_erp` (symlinked into bench)
- **Run tests:** `cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp`

### Recommended debugging tools

Before writing custom debug scripts or adding `print()` statements, reach for these first. Full usage notes live in `docs/testing_checklist.md` → "Debugging Shortcuts and Workflow Tips".

- **`bench console --autoreload`** — Interactive REPL with Frappe context loaded. The `--autoreload` flag re-imports any `.py` you edit, so you don't have to `exit()` and relaunch between tries. Use for: "what does this ORM query return", poking at real Redis state, inspecting a live Venue Asset row. Always point at `hamilton-unit-test.localhost` or `hamilton-test.localhost` — never production.
- **`bench request`** — Invokes a Frappe HTTP route with full request lifecycle (auth, permission, hooks) and returns the response in your terminal. Much faster than the browser, and failures show a real stack trace. Use for: reproducing a 403/500 from the Asset Board, verifying a new whitelisted endpoint signature.
- **`bench doctor` + `show-pending-jobs`** — **MANDATORY first debug step** on any symptom that could be "Redis is down", "the scheduler didn't run", or "a previous test left a stuck job". Run these BEFORE writing a repro, BEFORE opening a debugger, BEFORE grepping code. Or just run `/debug-env` which does this plus Redis PING + `is_setup_complete` + role check in one shot.

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
- See `docs/decisions_log.md` for DEC-001 through DEC-060
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

## Session Startup

At the start of every session, automatically check Taskmaster for the current project status and tell Chris which task is next, what it involves, and what was completed last session. Do this without being asked. Use `/taskmaster:next` to identify the next task and summarize it in plain English before doing anything else.

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

### Always run the full test suite — on the dedicated test site only
Every test run must include every module — never run just one or two — and **always** point at `hamilton-unit-test.localhost`. Tests on `hamilton-test.localhost` corrupt the dev browser state (setup_wizard loops, 403s, wiped roles). See `docs/testing_checklist.md` top-of-file WARNING.

Use the `/run-tests` slash command — it runs all 12 modules against `hamilton-unit-test.localhost` automatically. If you must run a single module by hand:
```
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.<module>
```

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

- Tasks 1-16 complete. Task 17 is next.
- Local bench: ~/frappe-bench-hamilton. Python 3.14, Node 24, MariaDB 12.2.2 (root pw: admin), Redis. Site: hamilton-test.localhost.
- hamilton_erp symlinked into bench from ~/hamilton_erp.

## Test Suite — 14 Modules (306+ passing, 15 skipped)

| Module | Tests | Notes |
|---|---|---|
| test_lifecycle | 29 | Core lifecycle methods |
| test_locks | 3 | Redis + FOR UPDATE lock |
| test_venue_asset | 17 | Doctype controller |
| test_additional_expert | 45 | Expert edge cases |
| test_checklist_complete | 43 + 11 skipped | Checklist items as Python |
| test_frappe_edge_cases | ~30 | Frappe v16 edge cases |
| test_extreme_edge_cases | ~30 | Frappe Cloud incidents, Hetzner, MariaDB, Redis |
| test_api_phase1 | ~10 | API endpoints + HTTP verb regression (DEC-058) |
| test_seed_patch | ~5 | Seed data integrity |
| test_security_audit | ~10 | SQL injection, XSS, permission escalation |
| test_environment_health | ~8 | Setup wizard gate, roles, asset count |
| test_asset_board_rendering | 7 | Card rendering, tier badges, color coding |
| test_adversarial | 36 + 8 skipped | 6 attack families (A-F), crash reporter |
| test_load_10k | ~3 | 10,000 session stress test |

Skipped tests unlock progressively:
- 8 in test_adversarial Family F unlock at Phase 2 (financial integration)
- 3 in test_checklist_complete unlock after Task 13 / Phase 2

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
