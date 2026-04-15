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

1. **Always read these docs at session start:** `docs/current_state.md`, `docs/decisions_log.md`, `docs/coding_standards.md`, `docs/build_phases.md`, `docs/lessons_learned.md`, `docs/venue_rollout_playbook.md`
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

## Inbox Workflow (claude.ai ↔ Claude Code bridge)

`docs/inbox.md` bridges research done in claude.ai with implementation in Claude Code.
- **End of claude.ai session:** Chris pastes a summary into `docs/inbox.md` on GitHub
- **Start of Claude Code session:** "read inbox.md, merge into docs, clear it"
- Merge targets: `claude_memory.md`, `decisions_log.md`, `lessons_learned.md`, `venue_rollout_playbook.md`, `CLAUDE.md`
- After merging, clear `inbox.md` to a single heading: `# Inbox`

## Karpathy 4 Principles

Apply these to every task:
1. **Think Before Coding** — understand the problem fully before writing code
2. **Simplicity First** — the simplest solution that works is the right one
3. **Surgical Changes** — change only what needs to change, nothing more
4. **Goal-Driven Execution** — every action must serve the stated goal

## Things that frustrate Chris (avoid these)
- Going in circles with multiple failed attempts before finding the right answer
- Using browser automation that never works
- Not saying upfront when something should be done in Claude Code vs the browser
- Excessive confirmation prompts — use `shift+tab` to allow all edits for the session
- Vague instructions that don't specify exactly where to type a command

## Common Issues and Solutions
Troubleshooting guide for known issues: `docs/troubleshooting.md`

## Pre-Deploy Checklist (before pushing to Frappe Cloud)

Run this before every deploy to hamilton-erp.v.frappe.cloud:

1. Run /run-tests — all 14 modules must pass, zero failures
2. Run bench migrate locally to verify migrations are clean
3. Check git log --oneline -5 — commit messages must be descriptive
4. Verify no debug print() statements or frappe.log() left in code
5. Confirm CLAUDE.md 3-AI review checkpoint is not due (check Task number)
6. Push to GitHub — Frappe Cloud auto-deploys within 3 minutes
7. Check hamilton-erp.v.frappe.cloud after 3 minutes to confirm site loads

## Testing Rules (Permanent)

### Reference: docs/testing_guide.md
The complete testing guide lives at `docs/testing_guide.md`. It includes:
- All 4 testing levels (run-tests, coverage, mutmut, hypothesis)
- Advanced database/performance test specification (R1–R8)
- Known test gaps to resolve before Task 25
- Expert-level testing checklist (10 items with priorities: Before Go-Live / Task 25 / Phase 2)

### Always run the full test suite — on the dedicated test site only
Every test run must include every module — never run just one or two — and **always** point at `hamilton-unit-test.localhost`. Tests on `hamilton-test.localhost` corrupt the dev browser state (setup_wizard loops, 403s, wiped roles). See `docs/testing_checklist.md` top-of-file WARNING.

Use the `/run-tests` slash command — it runs all 14 modules against `hamilton-unit-test.localhost` automatically. If you must run a single module by hand:
