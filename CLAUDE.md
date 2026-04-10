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
