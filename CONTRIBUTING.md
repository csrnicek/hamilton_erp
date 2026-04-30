# Contributing to Hamilton ERP

Hamilton ERP is a custom Frappe v16 / ERPNext v16 app for Club Hamilton. It's a single-developer project today (Chris), built primarily through AI-assisted pair programming with Claude Code. Contributions from outside the maintainer are welcome but rare; this document describes the conventions that any contributor (human or AI) is expected to follow.

If you've never worked on a Frappe app before, read the project's [`CLAUDE.md`](CLAUDE.md) first — it documents the project context, the local-dev environment, and the workflow rules that apply to every change.

---

## Before you start

### Read these in order
1. [`README.md`](README.md) — what this app does and where it runs.
2. [`CLAUDE.md`](CLAUDE.md) — project context, environment, workflow rules.
3. [`docs/decisions_log.md`](docs/decisions_log.md) — **LOCKED** design decisions. Don't propose changes that contradict these without an Amendment in the same PR.
4. [`docs/coding_standards.md`](docs/coding_standards.md) — especially §13 on locking discipline (DEC-019).
5. [`docs/lessons_learned.md`](docs/lessons_learned.md) — recurring-failure catalogue. Skim the "Top 10 Non-Negotiable Rules" at minimum.
6. [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — operational incident response (helpful context for understanding what's load-bearing).

### Set up your local bench
Run `bash scripts/init.sh` from a clone of this repo. The script:
- Verifies the version pins Frappe v16 hard-requires (Python 3.14, Node 24, MariaDB, redis-cli, frappe-bench)
- Initializes a bench at `~/frappe-bench-hamilton`
- Installs frappe + erpnext + payments + hamilton_erp
- Creates two sites: `hamilton-test.localhost` (browser dev — never run tests against this) and `hamilton-unit-test.localhost` (test site, wipe-able)
- Idempotent — re-running detects existing state

If `init.sh` fails, the error message tells you what's missing. The script does NOT install system packages for you; you'll see commands like `pyenv install 3.14.x`, `nvm install 24`, `brew install mariadb` to run first.

---

## Workflow

### One PR per change
Every change is a pull request against `main`, even single-line fixes. Direct commits to `main` are reserved for the maintainer's emergency fixes; everyone else opens a PR.

The PR is the unit of review and the unit of revert. If three logically separable changes ride together, that's three PRs, not one.

### Branch naming
Match what's already in the repo:
- `feat/<short-description>` — new functionality
- `fix/<short-description>` — bug fixes
- `chore/<short-description>` — refactor, cleanup, dependency bumps
- `docs/<short-description>` — documentation-only
- `test/<short-description>` — test-only additions

### Commit messages
Imperative mood, present tense. Sub-100-char first line. Body wrapped to 72 cols. Reference DEC-NNN, LL-NNN, or PR/issue numbers when relevant. Co-author tags for pair work or AI-assisted authoring.

Example:
```
fix(asset-board): include `reason` field in get_asset_board_data payload

Without this, both the OOS panel and Return-to-Service modal fall back to
"Reason unknown" forever — a user-visible bug. Pinned by the schema-snapshot
test in test_asset_board_rendering.

Closes the LL-029 root cause.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

### PR description
Use the template described in [`CLAUDE.md`](CLAUDE.md) "PR completion template" — Summary / Commits / Tests run / CI result / Files changed / Remaining risks / Rollback notes / Recommended merge / Open questions. Each section gets filled in or marked "N/A — [reason]"; never silently omitted.

---

## Coding conventions

### Tabs, not spaces
Project-wide convention. Matches Frappe formatter. `pyproject.toml` ignores W191 / E101 lint warnings to prevent the lint config from fighting the convention.

### Frappe v16 patterns
- Inherit from `frappe.tests.IntegrationTestCase` or `frappe.tests.UnitTestCase`, not plain `unittest.TestCase`.
- Use `@frappe.whitelist()` with the implicit `allow_guest=False`. Add `methods=["GET"]` or `methods=["POST"]` to constrain HTTP method.
- Use `frappe.db.get_value(..., for_update=True)` for race-protected reads on critical paths.
- **Never use `frappe.db.commit()` in controllers.** Let the framework manage transaction boundaries.
- Use `frappe.db.exists()` guards before any insert in install/seed/migration code (idempotency requirement).
- Use `frappe.db.delete()` not raw SQL for cleanup — transaction-safe, no-op on missing rows.
- Validate permissions in the controller, not in client-side JS.

These rules are enforced by Layer 1 conformance tests (Task 25) and CI lint checks. Violations should fail CI, not just earn a comment in code review.

### Locking discipline (DEC-019, coding_standards §13)
Any code that changes Venue Asset state goes through `lifecycle.<method>()` which acquires the three-layer lock. **Zero I/O inside the lock body.** Realtime broadcasts fire `after_commit=True`, never inside the lock. If you're tempted to add a `frappe.publish_realtime` inside a `lock_for_status_change` block, stop and read coding_standards §13 before continuing — there's a specific incident this rule prevents.

### Tests are self-contained
Each test creates and tears down its own data. Don't rely on a global seed surviving between tests. The conformance pin in `test_environment_health.test_59_assets_exist` is a deliberate canary — if it trips, a test wiped data without restoring it.

### When in doubt, match Frappe core
If a convention is unclear, look at how `frappe/frappe` itself does it. Inventing a new pattern is a higher bar than matching upstream.

---

## Tests

### Run before pushing
The full test suite must pass on `hamilton-unit-test.localhost` before any PR opens:

```bash
cd ~/frappe-bench-hamilton && source env/bin/activate
~/.pyenv/versions/3.14.x/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp
```

The 14-module suite is documented in [`.claude/commands/run-tests.md`](.claude/commands/run-tests.md). The `/run-tests` slash command runs the full suite; use that in Claude Code sessions.

### Never run tests against the dev site
`hamilton-test.localhost` is the **browser dev site**. Tests corrupt it (setup_wizard loops, role wipes, seed contamination). Always point `bench run-tests` at `hamilton-unit-test.localhost`.

### Pre-existing test failures
The current baseline includes failures that pre-exist on `main` and are documented in [`CLAUDE.md`](CLAUDE.md) "Common Issues":
- 6 setUpClass errors with `DocType Payment Gateway not found` — install `frappe/payments` (covered in `init.sh`).
- 2 environmental failures from seed-contamination (canary tests).

If your PR introduces a NEW failure, that's a regression. If it surfaces one of the documented pre-existing failures, that's the baseline — note it in the PR's "Tests run" section.

### What new tests should look like
- Add to the appropriate existing module (`test_lifecycle.py`, `test_locks.py`, etc.) — don't create a new file unless the feature warrants its own module.
- Pin the contract, not the implementation. A test that breaks every refactor is overfitted; a test that catches incorrect behaviour is a contract.
- For DocType JSON changes (anything requiring `bench migrate`), add a regression-pin test reading the JSON via `frappe.get_meta()` so future sessions can't silently break the contract.

---

## Documentation

### When to update which doc

| You changed... | You also update... |
|---|---|
| A locked design decision | `docs/decisions_log.md` (Amendment in same PR) |
| Fixed a bug after hitting it | `docs/lessons_learned.md` (LL-NNN entry) |
| Behaviour-affecting code | `CHANGELOG.md` (line under `[Unreleased]`) |
| A `@frappe.whitelist()` endpoint | `docs/api_reference.md` |
| `setup/install.py` or `patches/v0_1/` | `hamilton_erp/test_fresh_install_conformance.py` |
| Operational behaviour or failure mode | `docs/RUNBOOK.md` |
| Permissions on a DocType | `docs/permissions_matrix.md` |
| Frappe-cloud-specific behaviour | `docs/venue_rollout_playbook.md` |

If a PR changes code that should also update one of these and doesn't, that's a code-review finding, not "out of scope for this PR." The maintenance burden of stale docs is higher than the cost of one extra section in the PR.

### Don't write speculative docs
Hamilton ERP does NOT use docs to capture "this is what we'll do someday." Speculative work goes in:
- `docs/inbox.md` — ideas, research, notes-to-self
- `docs/build_phases.md` — phase plans (gates committed; details fluid)
- `docs/superpowers/plans/*.md` — task-level implementation plans

Promote from inbox / plans to a real doc only when the work has actually landed.

---

## What needs maintainer review

The maintainer (Chris) reviews every PR before merge. Auto-merge after CI is the standard pattern, but the maintainer reads the diff first.

Categories that always require explicit maintainer approval:
- Any change to a `LOCKED` design decision in `docs/decisions_log.md`
- Anything that requires `bench migrate` (DocType JSON, new patches)
- Anything that changes the auth / permission surface
- Anything that touches the cash-control invariants (DEC-005)
- Anything that touches the locking primitives (DEC-019)
- Multi-PR refactors where the PRs depend on each other

Categories that auto-merge after CI:
- Pure test additions (regression pins)
- Pure docs additions
- Internal refactors that don't change behaviour
- Dependency bumps within the same major version

The autonomous Claude Code agent uses `gh pr merge --auto --squash --delete-branch` for the second category and pauses at the first.

---

## Reporting issues

- **Bugs:** [GitHub issues](https://github.com/csrnicek/hamilton_erp/issues). Include reproduction steps, environment (local-bench / Frappe Cloud / which version), and a minimal example.
- **Security vulnerabilities:** see [`SECURITY.md`](SECURITY.md). Email csrnicek@yahoo.com — **never** open a public issue.
- **Operational incidents on Hamilton's live site:** see [`docs/RUNBOOK.md`](docs/RUNBOOK.md) §10 (Escalation).

---

## Working alongside an AI agent

This project is built primarily through AI-assisted pair programming. If you contribute as a human reviewer of AI-generated PRs, useful patterns:

- Treat the AI as a colleague who needs concrete, falsifiable feedback. "This is wrong because X" beats "I don't like this."
- The AI should leave a "Open questions for Chris" section in PR descriptions when judgment is required. If that section is empty and you have a question anyway, ask it as a PR comment — the AI may have missed something.
- The autonomous agent has STOP conditions documented in [`CLAUDE.md`](CLAUDE.md) "Autonomous Command Rules" — `bench migrate`, DEC-NNN changes, data-loss risk, systemic test failures. If you see the agent stop and standby, that's working as intended.

If you contribute as another AI agent, follow the same rules — read the docs, write self-contained tests, match Frappe v16 patterns, and never silently violate a LOCKED decision.

---

## License

Hamilton ERP is licensed under the MIT License. See `LICENSE` for the full text. Contributions are accepted under the same license; by opening a PR, you agree to license your contribution under MIT.

---

*Last updated 2026-04-30. Hamilton ERP is pre-1.0 and pre-Task-25 (handoff prep in progress). This document will tighten when Hamilton enters production-customer use.*
