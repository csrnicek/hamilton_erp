# Hamilton ERP — Claude Code Context

## Drift Prevention — Verify Before Claiming Done

Before saying anything is "shipped", "complete", or "closes the gap":

1. Read the actual implementation code, not just the commit message
2. Distinguish "spec/design committed" from "implementation working in running code" — these are NOT the same
3. Run the test suite if available, and verify the tests cover the spec (not just the old behavior)
4. Confirm visually in a browser if the change is user-facing
5. State uncertainty plainly. "I don't know" and "let me verify" are real answers

Past failure to learn from: 2026-04-24, V9 was described as shipped when only the
mockup file shipped — the live `asset_board.js` was still on V8. The gap was
discovered three days later as a 20-item divergence audit. Do not repeat this
pattern.

When in doubt, the answer is "let me check first."

## Plugin Data Freshness — Single Source of Truth

Project artifacts have ONE canonical location, which is always a version-controlled file in this repo. Plugin state (Taskmaster, Claude-Mem, auto-memory) is a *mirror* — never canonical. When plugin state contradicts the file, trust the file and update the plugin.

### Same-day-write rule for Task 25 sub-items

Any new Task 25 sub-item identified during planning must be added to `docs/task_25_checklist.md` the same day it's identified. Never let a sub-item live only in `inbox.md`, memory, or chat history.

**Direction of truth:** `docs/task_25_checklist.md` is canonical. `.taskmaster/tasks/tasks.json` Task 25 subtasks are derived from it.

**Auto-sync mechanism (`.github/workflows/sync-taskmaster.yml`):**

- **Pre-merge guard** — every PR that touches the checklist or Taskmaster JSON runs `python3 .github/scripts/sync_taskmaster_from_checklist.py --check`. CI fails if the two files disagree, forcing the author to update both.
- **Post-merge auto-sync** — when a push to main modifies `docs/task_25_checklist.md`, the workflow re-derives Taskmaster from the checklist and opens a follow-up PR with the JSON update (auto-merge enabled).

**Status markers in the checklist** (machine-parseable):

| Marker | Taskmaster status |
|---|---|
| `✅ DONE` | `done` |
| `🔒 BLOCKED` | `blocked` |
| `🔍 REVIEW` | `review` |
| `⏸ DEFERRED` | `deferred` |
| (no marker) | `pending` |

To update an item's status: edit the checklist line. The workflow handles the JSON.

### Same-day-write rules — broader

The same principle applies to every artifact type that has a canonical home:

| Artifact | Canonical file (must update same day) | Plugin mirror |
|---|---|---|
| Task 25 sub-item | `docs/task_25_checklist.md` (CANONICAL) | Taskmaster Task 25 subtasks (auto-derived; see auto-sync workflow above) |
| Top-level task | Taskmaster `.taskmaster/tasks/tasks.json` | none — Taskmaster is canonical |
| Decision (DEC-NNN) | `docs/decisions_log.md` | none — file is canonical |
| Lesson (LL-NNN) | `docs/lessons_learned.md` | none — file is canonical |
| Risk (R-NNN) | `docs/risk_register.md` | none — file is canonical |
| Inbox handoff item | `docs/inbox.md` | none — file is canonical (cleared on `/start`) |

If a session identifies one of these and only writes it to chat or to a plugin (Claude-Mem observation, auto-memory entry), the next session can't see it. The artifact effectively didn't happen.

### Stale-plugin-data discipline

Plugins persist across sessions. Their state can drift from the current file state when:
- A file is updated but the plugin observation isn't
- A plugin observation is created from a hypothesis that turned out wrong
- A bug is fixed but the memory entry that flagged it isn't cleared

**Concrete example to learn from (2026-05-01):** Claude-Mem observation 1063 said "hooks.py Line 69 Uses `override_doctype_class` — Known Bug to Fix." A 2026-05-01 verification showed `hooks.py:69` already correctly uses `extend_doctype_class`. The bug was fixed; the memory observation was never updated. Acting on the stale memory would have wasted a PR cycle "fixing" code that was already correct.

**The rule:** before acting on plugin data that names a specific file/function/flag, verify against the current file state. If the plugin contradicts the file, the plugin is stale — clear or update it, then act on the file's reality.

### When canonical files contradict each other

The pre-existing rule still applies: design specs (`docs/design/V10_CANONICAL_MOCKUP.html`) and decisions (`docs/decisions_log.md`) win over scattered references in inbox / memory / chat. If two canonical files disagree, surface it as a decision needing Chris's call rather than picking one silently.

## V10 Canonical Mockup — Gospel Reference

The file `docs/design/V10_CANONICAL_MOCKUP.html` is INTENDED to be the canonical
V10 specification for the Asset Board UI. Whether it currently IS canonical
depends on the verification checks in the gospel block at the top of the file
(canonical chain intact, manifest points here, content integrity via fingerprint
test, recency). Verify those checks before trusting the file as authoritative.

V9 is archived at `docs/design/archive/V9_CANONICAL_MOCKUP.html`. The V10 body is
byte-identical to V9 (the asset-board visual spec hasn't changed); V10 was
bumped to bookkeep the V9.1 retail amendment, whose spec lives in
`docs/design/V9.1_RETAIL_AMENDMENT.md` rather than inlined in the HTML.

**Rules for Claude:**

1. When implementing or modifying any Asset Board UI code, port from this file.
   Do not interpret the design spec — port the mockup verbatim, only changing
   selectors that differ between mockup and production conventions
   (`.tile` → `.hamilton-tile`, etc.).
2. If the mockup and production disagree on visual or behavioral specifics,
   the mockup wins. Production drift is the bug.
3. Do not modify the canonical mockup file casually. Changes require explicit
   Chris approval and should be documented as amendments in
   `docs/decisions_log.md`.
4. If a future design change fully supersedes this file, the next Claude
   session should create a new version-numbered canonical file (e.g.,
   `V11_CANONICAL_MOCKUP.html`) — do not edit the V10 file in place.

**For port-from-mockup work:**
- Read the mockup's relevant function/CSS section
- Read production's current implementation
- Bring production into byte-for-byte alignment with the mockup, only
  changing selectors as needed
- Verify in browser that production matches the mockup
- Add regression tests guarding the ported pattern

## Frappe v16 Conventions

When writing any Frappe code, consult these sources before writing:

- Frappe docs: https://frappeframework.com/docs/v16/user/en
- Frappe wiki: https://github.com/frappe/frappe/wiki
- ERPNext contributing guide: https://github.com/frappe/erpnext/blob/develop/CONTRIBUTING.md
- Reference implementation: read existing patterns in apps/frappe/ source code

If a convention is unclear, prefer matching what frappe/frappe itself does over inventing something new.

### Production version pinning — tagged v16 minor release, NEVER branch HEAD or develop

Hamilton ERP production deploys on Frappe Cloud must pin both `frappe` and `erpnext` to a **specific tagged v16 minor release** (e.g., `v16.3.4`), NOT to the `version-16` branch HEAD and NOT to `develop`.

**Three tiers, three behaviors:**
- **Tagged minor (e.g. `v16.3.4`):** immutable point-in-time. The release that production runs.
- **`version-16` branch HEAD:** the active polish wave. ~10 fixes/month land in POS / Sales Invoice / Stock / Permissions areas (verified by issue tracker survey, 2026-04-30). Changes weekly. Acceptable for staging; never production.
- **`develop` branch:** v17 work. Pre-release breaking changes land continuously. Never use anywhere except experimental forks.

The version-16 branch survey (2026-04-30) showed ~50 PRs merged across the four functional areas in 3.5 months post-GA; auto-deploying HEAD would have introduced production churn from those changes whether or not Hamilton's flow is affected.

### Disable auto-upgrade on the production bench

Frappe Cloud's private bench supports disabling auto-upgrades. Hamilton's production bench MUST have auto-upgrade disabled.

**Manual upgrade cadence:**
1. **Monthly review window** — first week of each month, check `version-16` tag list for new minor releases.
2. **Smoke-test in staging** — apply the new minor to the staging site, run Hamilton's full test suite (`/run-tests`) plus a manual cart-Confirm flow.
3. **Promote to production** — only after staging is green for at least 48 hours of soak time.

The 30-day cadence is faster than ERPNext's typical implementation cycle but matches the polish-wave fix pace. If a critical CVE or data-corruption bug is announced, off-cycle upgrades are warranted; otherwise, monthly is the rhythm.

**Local dev / CI exception:** CI's vendored `frappe-setup` action installs `frappe/payments@develop` (per `.github/workflows/tests.yml` and the "Common Issues" section below) because frappe/payments has no `version-16` branch yet — CI-only and acceptable. The Hamilton ERP custom app itself tracks `main` on production. The pinning rule above applies to frappe + erpnext; Hamilton's own app updates ship through git tags on `main`.

**Watch:** if frappe/payments cuts a `version-16` branch, switch the workflow checkout AND any production install of payments to it. See `docs/inbox.md` 2026-04-28 entry on the frappe/payments production-deploy decision.

### Hard rules that override defaults

- Tests must be self-contained — each test creates and tears down its own data, no reliance on global seed
- Use tabs, not spaces (matches Frappe formatter; lint config in pyproject.toml ignores W191/E101)
- Inherit from `frappe.tests.IntegrationTestCase` or `frappe.tests.UnitTestCase`, not plain `unittest.TestCase`
- Use `frappe.db.get_value(..., for_update=True)` for race-condition protection on critical reads
- Never use `frappe.db.commit()` in controllers — let the framework handle transaction boundaries
- Use `@frappe.whitelist()` with `allow_guest=False` as the default for any callable method
- Validate permissions in controllers, not in client-side JS
- Use `frappe.db.exists()` guards before any insert in install/seed/migration code (idempotency requirement)
- Use `frappe.db.delete()` not raw SQL for cleanup operations (transaction-safe, returns no-op on missing rows)

These rules are enforced by Layer 1 conformance tests (Task 25) and CI lint checks. Violations should fail CI, not just earn a comment in code review.

## Hamilton accounting / multi-venue conventions (PR #51 audit)

These rules came out of the pre-merge audit on PR #51 (V9.1 Phase 2 cart → POS Sales Invoice). They apply to any future flow that creates Sales Invoices, taxes, currency-rounded amounts, or card payments.

### CAD nickel rounding is site-global (Audit Issue B)

The Hamilton seed sets `Currency CAD.smallest_currency_fraction_value = 0.05` so cash POS sales round to the nearest nickel per Canada's 2013 penny-elimination rule. This setting affects **every CAD invoice on the site**, not just the cart's POS invoices.

If a future Hamilton flow creates a CAD invoice for a non-cash workflow (B2B vendor invoice, membership invoice, intercompany invoice, etc.), it must explicitly set `disable_rounded_total=1` on that invoice — otherwise it will silently round to nickels. The cart's `submit_retail_sale` is the reference pattern: nickel rounding is gated by `payment_method` and disabled for Card payments.

### One Sales Taxes Template per place-of-supply jurisdiction (Audit Issue G)

CRA's place-of-supply rule for in-store retail: HST/GST is determined by where the goods are delivered (= the venue's location). Hamilton's "Ontario HST 13%" template covers Ontario only.

When the next venue rolls out:
- **Philadelphia (PA, 6% sales tax + 8% on prepared food):** create a separate Sales Taxes Template per Philadelphia's place of supply. Don't try to make a "global" template that handles multiple provinces — each venue's template must reflect its own jurisdiction.
- **DC (6% standard, 10% on alcohol/restaurant):** separate template.
- **Item-level overrides** (zero-rated basic groceries, mixed food/grocery treatment) need ERPNext's Item Tax Template, not Sales Taxes Template. Hamilton's 4 SKUs are all 13%-taxable so this isn't an issue today, but Phase 2+ menu expansion may surface it.

The seed must accept a per-venue tax template name via `frappe.conf` (analogous to `hamilton_company` and `hamilton_walkin_customer`) before the second venue ships.

### Phase 1 vs Phase 2 payment surface (current scope — explicit)

What's live at Hamilton today vs what's queued for Phase 2 / Phase 3. Read this before answering any "is X live now?" question about cash, card, refund, or settlement.

| Surface | Phase 1 (live now) | Phase 2 / Phase 3 (queued) |
|---|---|---|
| **Cash POS Sales Invoice** | ✅ LIVE via PR #51 (`submit_retail_sale` API + cart UX, ships QBO-mirrored CoA + Hamilton accounting seed). The cart Confirm creates a real POS Sales Invoice that decrements stock and posts to GL. | — |
| **Card POS — standalone terminal** | ⚠️ STANDALONE Fiserv terminal (Clover Flex C405). Operator types the cart amount on the terminal manually; ERPNext records the Sales Invoice with payment_method = "Card" but does NOT integrate with the terminal. R-009 (MATCH list 1% chargeback threshold) is latent. | — |
| **Card POS — integrated** | ❌ NOT live | Phase 2 — Clover Connect API integration so ERPNext pushes the cart amount to the terminal and the operator cannot mistype. See `docs/design/cash_reconciliation_phase3.md` §5. |
| **Refunds** | ❌ NOT live (cash-side stub only via Sales Invoice cancel/amend, manager-only) | Phase 1 BLOCKER — cash-side via Task 31; full design Phase 2. See `docs/design/refunds_phase2.md` (review-pending). |
| **Voids (mid-shift)** | ❌ NOT live | Phase 1 BLOCKER — Task 33. |
| **Comps** | ✅ LIVE via Comp Admission Log + zero-value Sales Invoice flow | Phase 1 BLOCKER — manager-PIN gate via Task 32. |
| **Membership** | ❌ NOT live (Hamilton is anonymous walk-in only — `anvil_membership_enabled = 0`) | DC priority — Task TBD; see `docs/design/manager_override_phase2.md` for context. |
| **Settlement reconciliation** | ❌ NOT live | Phase 2 audit layer — see `docs/design/cash_reconciliation_phase3.md` §5. |
| **Tip pull from till** | ❌ schema NOT present | Phase 1 BLOCKER (schema only) via Task 34; full UX Phase 2. See `docs/design/tip_pull_phase2.md`. |

For a beginner reading this for the first time: Phase 1 ships with **cash sales fully integrated** (real Sales Invoice + GL + sales tax + receipt) and **card sales handled by the standalone terminal** (no software integration; operator types amount on the terminal, customer taps card, terminal prints its own receipt). Phase 2 adds the integrated card path, the refund flow, and the void flow. Phase 3 adds the variance system + portable reconciliation + tip math. The ledger of which Phase 1 BLOCKERs must close before Hamilton launches is in `.taskmaster/tasks/tasks.json` (Tasks 30, 31-37).

### Card payments require SAQ-A validation before going live (Audit Issue I)

When the Phase 2 next iteration adds Card payments (merchant abstraction, terminal integration), the merchant adapter must keep card data outside Hamilton's network — terminal handles all card data, the SI stores only references (last 4, brand, auth code, merchant_transaction_id). This is the SAQ-A integration model.

Before going live with Card:
1. Confirm the chosen processor (Fiserv per Hamilton's existing setup, or backup) supports a SAQ-A integration model.
2. Confirm the receipt printer integration (Epson TM-T20III) doesn't print full PANs — last 4 only.
3. Re-attest SAQ-A annually, naming the processor explicitly.

If a future integration ever transits card data through Hamilton's network in plaintext, scope expands to SAQ-D and a QSA assessment ($5-50k/year). Avoid this by keeping the merchant terminal as the only place card data exists.

### Hardware procurement is per-venue, never bulk (hard rule)

Hardware procurement is per-venue, on each venue's own go-live schedule. Never order hardware for multiple venues at once. Each venue's rollout includes its own hardware evaluation against the current spec, sourced and tested independently.

Why: multi-venue bulk orders compound risk — a spec error, a model EOL announcement, a connectivity-survey miss, or a venue-specific regulatory issue (provincial sales tax, US-state PCI scope, language-of-receipts) becomes a multi-site sunk cost instead of a single-site lesson. Each venue rollout is also separated by months in practice; the spec drifts (Bluetooth-only models get USB-C variants, Brother releases a successor, a processor changes terminals) and the spec-of-record at evaluation time is the spec that must apply.

How to apply:
- Phase 0 of `docs/venue_rollout_playbook.md` runs hardware evaluation independently per venue.
- Hamilton's hardware order does NOT presume Philadelphia, DC, or Dallas use the same models — re-evaluate at each rollout.
- Acceptable to keep cross-venue stylistic continuity (same printer family, same scanner brand) when current spec still recommends it; not acceptable to lock it in advance.
- Spares are part of the venue's own order, not a corporate stockroom shipped between sites.

## About Chris (the human you are working with)

- **Experience level:** Beginner with coding, terminal, and developer tools
- **Always give:** Explicit step-by-step instructions specifying exactly which window or app to type commands in
- **Never assume:** That Chris knows what a command does, where to type it, or what the output means
- **Always explain:** What just happened in plain English after each step completes

## Communication preferences

- Be direct and concise — no filler phrases, no excessive praise
- **State consequences before actions. Never after.** Before running anything irreversible (drop site, force push, delete files, run migration, install global package, swap merchant config), say what will happen and what could go wrong, then stop. Don't act first and explain the consequences in the post-mortem. Chris is a beginner — he needs to know the cost of "yes" before he says yes, not after.
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
- **Frappe v16 hard requirements (do NOT pick lower versions for CI or any new bench):**
  - **Python: 3.14** (`>=3.14,<3.15` per Frappe 16.16.0's pyproject.toml). 3.13 fails with `frappe depends on Python>=3.14,<3.15`. 3.11 fails earlier with `SyntaxError: type ConfType = _dict[str, Any]` (PEP 695 syntax).
  - **Node: 24** (Frappe's package.json declares `engines.node >= 24`). Node 20 fails `yarn install --check-files` with `frappe-framework: The engine "node" is incompatible with this module. Expected version ">=24". Got "20.20.2"`.
  - **Why this is here:** I burned three CI runs in a single session by overriding the vendored Frappe action's defaults of 3.14 and 24 to "conservative" lower values. The defaults are not preferences — they're hard requirements. Match upstream version pins exactly unless you have specific evidence the upstream is wrong.
- **Dev browser site:** `hamilton-test.localhost` — Chris's manual testing site. **NEVER run the test suite here.** Tests corrupt it (setup_wizard loops, 403s, wiped roles).
- **Unit-test site:** `hamilton-unit-test.localhost` — dedicated Frappe test site. `allow_tests = true`. All `bench run-tests` invocations point here. Safe to wipe/reinstall.
- **MariaDB root password:** `admin`
- **App path:** `~/hamilton_erp` (symlinked into bench)
- **Run tests:** `cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp`

### Recommended debugging tools

See `docs/testing_checklist.md` → "Debugging Shortcuts and Workflow Tips" for full usage.
- **`bench console --autoreload`** — REPL with Frappe context. Point at test or dev site, never production.
- **`bench doctor` + `show-pending-jobs`** — MANDATORY first step for Redis/scheduler issues. Or run `/debug-env`.

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

### Phase 1 implementation plan
Full plan: `docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md`
- 25 tasks, TDD, Subagent-Driven Development
- Test harness: 26 tests passing (6 lifecycle, 3 locks, 17 venue_asset)
- 6 pre-existing IntegrationTestCase setUpClass failures from transitive Link-field dependency on Payment Gateway. NOT actually stubs — real tests with real assertions. Frappe's `IntegrationTestCase.setUpClass` walks every Link-field on the test's DocType recursively; for shift_record/comp_admission_log/cash_reconciliation/cash_drop/venue_session/asset_status_log, the chain ends at Payment Gateway which lives in `frappe/payments` (not in vanilla frappe + erpnext). Local dev benches that have frappe/payments installed pass; CI now installs frappe/payments@develop to fix this (see .github/workflows/tests.yml). Production deploys may also need frappe/payments — see docs/inbox.md 2026-04-28 entry.

## Workflow rules

1. **Always read these docs at session start:** `docs/current_state.md`, `docs/decisions_log.md`, `docs/coding_standards.md`, `docs/build_phases.md`, `docs/lessons_learned.md`, `docs/venue_rollout_playbook.md`, `docs/design/V10_CANONICAL_MOCKUP.html` (asset board UI gospel — see V10 Canonical Mockup section above), `docs/design/asset_board_ui.md` (legacy spec — V10 mockup wins on conflict)
2. **Use Subagent-Driven Development** for all Phase 1 tasks — dispatch implementer → spec reviewer → code quality reviewer → fix → re-review
3. **Push to GitHub after every task** — every commit goes to `origin/main`
4. **Never use browser automation** — always give Chris manual instructions instead
5. **Test before committing** — run the relevant test modules and confirm green before git add
6. **Explain test results in plain English** — Chris is a beginner; "15/15 passing" needs a one-line explanation of what that means

## Session Startup

At the start of every session, do these steps automatically without being asked:

1. Run `/debug-env` to confirm Redis, MariaDB, and the test site are all healthy before touching anything else. If anything is broken, stop and tell Chris in plain English what is wrong.
2. Run `/run-tests` to confirm the test suite is fully green. If any tests are failing, stop and tell Chris before proceeding.
3. Check Taskmaster with `/taskmaster:next` to identify the next task and summarize it in plain English — what it involves and what was completed last session.

Do not skip step 1 or 2. A broken environment or failing tests must be resolved before any new work begins.

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

## Things that frustrate Chris (avoid these)
- Going in circles with multiple failed attempts before finding the right answer
- Using browser automation that never works
- Not saying upfront when something should be done in Claude Code vs the browser
- Excessive confirmation prompts — use `shift+tab` to allow all edits for the session
- Vague instructions that don't specify exactly where to type a command

## Common Issues and Solutions

### Tests fail with setUpClass errors
If failures are in the 6 doctype tests (shift_record/comp_admission_log/cash_reconciliation/cash_drop/venue_session/asset_status_log) with `DoesNotExistError: DocType Payment Gateway not found` — frappe/payments isn't installed in the bench. CI installs it from develop branch automatically; for local dev: `bench get-app https://github.com/frappe/payments && bench --site SITE install-app payments`.

Other setUpClass errors warrant investigation — they're not the documented Payment Gateway issue.

### Redis lock contention during tests
A previous crash left a Redis key. Wait 15s for TTL expiry, or `redis-cli FLUSHDB` (test site ONLY).

### TimestampMismatchError on asset save
Always re-fetch with `frappe.get_doc()` inside the lock — never use a cached instance.

### session_number not populated
Check Redis (`bench doctor`), check VenueSession controller has before_insert, run `bench migrate` if doctype JSON changed.

## Pre-Deploy Checklist (before pushing to Frappe Cloud)

1. All entries in `docs/feature_status.json` must show `"passes": true`
2. Run /run-tests — zero failures
3. Run `bench migrate` locally — clean
4. No debug `print()` or `frappe.log()` in code
5. Check 3-AI review checkpoint (Task 9, 11, 21, 25)
6. Push to GitHub — auto-deploys in ~3 minutes

## Testing Rules (Permanent)

### Reference: docs/testing_guide.md
The complete testing guide lives at `docs/testing_guide.md`. It includes:
- All 4 testing levels (run-tests, coverage, mutmut, hypothesis)
- Advanced database/performance test specification (R1–R8)
- Known test gaps to resolve before Task 25
- Expert-level testing checklist (10 items with priorities: Before Go-Live / Task 25 / Phase 2)

### Always run the full test suite — on the dedicated test site only
Every test run must include every module — never run just one or two — and **always** point at `hamilton-unit-test.localhost`. Tests on `hamilton-test.localhost` corrupt the dev browser state (setup_wizard loops, 403s, wiped roles). See `docs/testing_checklist.md` top-of-file WARNING.

Use the `/run-tests` slash command — it runs all 14 modules against `hamilton-unit-test.localhost` automatically.

### When Chris asks for more code checks
This is a permanent rule — never skip any of these steps:
1. Add the new tests to `docs/testing_checklist.md`
2. Immediately convert them to running Python tests in the appropriate file
3. Update `.claude/commands/run-tests.md` to include any new test module
4. Commit all files to GitHub

Never add to the checklist without also writing the Python tests.
Never write Python tests without updating the run-tests command.
Never update run-tests without committing everything to GitHub.

## Current Project State
Current task status: see `docs/current_state.md`

## Test Suite

14 modules, 306+ passing, 15 skipped. See `.claude/commands/run-tests.md` for the full list.
Baseline: any drop in passing count is a regression — stop and report.

## Slash Commands

All in `.claude/commands/`. Run `/run-tests` for the full suite.

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

## PR completion template

When a PR is ready for human review, leave a summary in `docs/inbox.md` (under today's date heading) AND in the PR description with these sections:

### Commits made
[Output of `git log --oneline main..HEAD` — full list of commits on the branch.]

### Tests run
[Which test suites ran. CI run ID(s). Local test run output if applicable. Whether all tests passed or which were skipped.]

### CI result
[Latest CI run conclusion with a link. Pass/fail counts for Server Tests + Linter. Note if any required check is still pending.]

### Files changed
[Output of `git diff main...HEAD --stat`.]

### Remaining risks
[Anything that could go wrong in production. Things tested locally but not in CI. Things that depend on environment setup. Anything Chris should verify before deploying. If "none," say so explicitly.]

### Rollback notes
[How to revert if this breaks production. Specific commands. Whether any data migrations are reversible. If irreversible (e.g. DocType field rename with data migration), flag explicitly.]

### Recommended merge command
[Specific gh CLI command. Squash vs. merge commit. Whether to delete the branch.]

### Open questions for Chris
[Decisions that need Chris's judgment before or after merge. Empty list is fine if there are none.]

If any section is N/A, write "N/A — [reason]" — never omit sections silently.

This template applies to ALL PRs Claude Code creates, including docs-only PRs (where CI result and rollback may be trivial but should still be stated). It exists so session handoff is durable: tomorrow-Chris reading the inbox can fully reconstruct what landed and why without re-running git commands.

## Context Compaction Rule

When compacting, always preserve: modified file list, failing test names, and Redis lock key format (`hamilton:asset_lock:{asset_name}`).

## Design Spec Rules (Permanent)

These rules apply to every session, every task, forever.

### Rule 1 — Inbox first (read every session; inbox is a working queue)
Before starting any task, read `docs/inbox.md`.

**Inbox is a working queue, not a transient handoff.** It accumulates active operational items that intentionally survive across sessions: open queued tasks, multi-PR series notes, hardware procurement reminders, pending Chris-decisions, and other items that haven't yet earned a canonical home in `claude_memory.md`, `decisions_log.md`, `lessons_learned.md`, `risk_register.md`, or a design doc. **Do NOT auto-clear inbox.md at session start.**

What to do at session start:
1. **Read inbox.md in full.** Surface anything time-sensitive or session-relevant.
2. **Promote where appropriate** — if an inbox item has matured into a canonical artifact (DEC-NNN, R-NNN, LL-NNN, design doc), MOVE it into the canonical home and remove from inbox. Promotion is a one-way ratchet; once promoted, the inbox loses the item.
3. **Add new items as you go** — when you queue something for "later," add it to inbox.md with a date stamp. The queue rule from CLAUDE.md "Same-day-write rules — broader" applies: if an item belongs in `task_25_checklist.md` / `decisions_log.md` / `lessons_learned.md` / `risk_register.md`, write it there directly; only use inbox for items that don't yet have a canonical home.
4. **Sweep when it grows past readability** — when inbox.md exceeds ~2000 lines, do a one-time triage pass to archive completed items (move to `docs/inbox/archive/YYYY-MM.md`) and promote stragglers to canonical files. The sweep is opportunistic, not session-mandatory.

The earlier "merge into claude_memory.md and clear" wording was the original 2026-04 design when inbox was a thin claude.ai → Claude Code handoff. Reality drifted: the inbox is now a session-spanning queue. **This rule reflects current reality (2026-05-01).** If a future workflow simplification can collapse inbox back to a transient handoff, restore the auto-clear behavior — but don't auto-clear today.

### Rule 2 — Design spec before any frontend code
Before writing any code for any frontend task (JS, CSS, HTML, page templates):
- Check docs/design/ for a spec file matching the feature
- If one exists, read it in full before writing a single line of code
- If none exists, stop and tell Chris before proceeding

### Rule 3 — Required startup reads (every session)
Read all of these at the start of every Claude Code session, in this order:
1. docs/claude_memory.md
2. CLAUDE.md
3. docs/inbox.md
4. docs/design/V10_CANONICAL_MOCKUP.html (asset board UI gospel — supersedes asset_board_ui.md on any conflict; see "V10 Canonical Mockup — Gospel Reference" section earlier in this file for the full rule set)
5. docs/design/asset_board_ui.md (legacy spec, kept for reference only — V10 mockup wins on conflict)
6. docs/decisions_log.md (LOCKED asset-board design decisions — consult BEFORE changing any asset board behaviour)
7. docs/phase1_design.md §5.6 (frontend sessions only — note that file is now banner-marked HISTORICAL; consult only the §5.6 frontend popover spec, NOT the file's overall design claims, which have diverged from production)

### Rule 4 — End of session commit
At the end of every session, before stopping:
- Run git status
- If anything is uncommitted, commit and push it
- Append a checkpoint to docs/claude_memory.md summarising: what was built, decisions made, current task status, next step
- Never end a session with uncommitted work or an empty checkpoint

## Permanent Automation Rules — DO NOT REMOVE

### Session Start (every single session, no exceptions)
Run /start before responding to anything. This is not optional.
If /start has not run, run it now before reading this further.

### Frontend Code Rule
Before writing ANY JS, CSS, or HTML:
- Check docs/design/ for a matching spec file
- If found: read it completely before writing one line of code
- If not found: stop and tell Chris — do not guess or use old spec

### End of Session Rule
Before stopping for any reason:
- git status — commit and push anything uncommitted
- Append checkpoint to docs/claude_memory.md
- git add docs/claude_memory.md && git commit -m "chore: end of session checkpoint" && git push origin HEAD -y

### inbox.md Rule
inbox.md is the bridge from claude.ai planning to Claude Code building.
Check it at session start (via /start) AND whenever PreCompact fires.
Never let inbox.md sit unread for more than one session.
