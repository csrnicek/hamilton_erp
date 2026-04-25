# Hamilton ERP — Developer Handoff Audit & Checklist

**Purpose:** Prepare `hamilton_erp` (Frappe v16 custom app, AI-built, beginner author) for handover to an experienced Frappe/ERPNext developer who has never seen this codebase.

**Use this document as:** a working checklist. Walk it top-to-bottom with Claude Code in your terminal. Items marked 💸 are the ones that will cause a developer to bill extra hours if missing — fix those first.

**How this differs from your existing Task 25 list:** your current list is solid on the technical hardening side (permissions, audit trail, fixtures, CI/CD). This adds the *handoff-specific* items — onboarding docs, code quality audit, and the things that make an outsider productive on day one rather than week three.

---

## Part 1 — The "Day One Productivity" Test

A clean handoff means a senior Frappe developer can do all of this **without messaging you** within 30 minutes of receiving the repo:

1. Clone the repo and read a single doc (`README.md`) that tells them what this app does, why it exists, and where to find everything else.
2. Run one setup script (or follow a numbered list ≤ 10 steps) to get a working dev site with realistic data.
3. Run the test suite and see all green.
4. Open one architecture doc that explains the 10 DocTypes, how they relate, and the non-obvious decisions (workflow-only status, child table for multi-asset, Redis lock pattern).
5. Make a trivial change (e.g., add a field), migrate, and see it work.

**If any of those five things requires asking you a question, that's billable hours.** Everything below is in service of passing this test.

---

## Part 2 — Documentation: What Must Exist

The Frappe ecosystem has a fairly standard "shape" for app documentation. Senior devs will look for these files in roughly this order. Missing files don't *break* anything — they just send the developer to Slack/email.

### Required at repo root

- 💸 **`README.md`** — One page. Must contain: what the app does in two sentences, supported Frappe/ERPNext version (v16), install command, how to run tests, link to deeper docs. **No marketing copy.** A senior dev will judge the codebase by this file in the first 60 seconds.
- 💸 **`LICENSE`** — Frappe defaults to MIT. Pick one and commit it. Missing license = legal ambiguity for a contractor.
- **`CHANGELOG.md`** — Even a thin one. List what shipped at each tag. If you don't tag versions, start now (`v0.1.0` is fine).
- **`.gitignore`** — Confirm it excludes `__pycache__`, `*.pyc`, `node_modules`, `.env`, `sites/`, IDE folders. AI-generated repos often miss this and ship junk.
- **`pyproject.toml`** — Pin your Python dependencies with versions. AI tends to leave these unpinned ("requests" instead of "requests>=2.31,<3").

### Required in `docs/`

You already have several of these. Audit them against this list:

- 💸 **`ARCHITECTURE.md`** (or `architecture.md`) — The single most important file for a new developer. Should contain:
  - DocType relationship diagram (even ASCII art is fine — see template below).
  - Why singleton pattern was used for Bathhouse Settings.
  - Why child table (not separate doc) for multi-asset transactions.
  - Why workflow-only status management on Bathhouse Asset.
  - Why PIN-based staff identity instead of standard User auth.
  - Redis lock pattern explanation (when, why, what fails without it).
  - On-demand shift total computation (vs. stored field).
- 💸 **`SETUP.md`** — Step-by-step from "fresh laptop" to "working dev site." Assume reader has bench installed but nothing else. Include exact commands. Test it yourself by running it on a clean machine — or have Claude Code spin up a fresh container and verify.
- **`decisions_log.md`** — You have this. Confirm every architectural decision has a "why" (not just "what"). The "why" is what saves billable hours later.
- **`lessons_learned.md`** — You have this. Keep it. A senior dev reading this will trust the codebase more, not less, because it shows the author understood failures.
- **`TESTING.md`** — How to run tests, how to add tests, what's covered, what's intentionally not covered (and why).
- **`DEPLOYMENT.md`** — How to deploy to Frappe Cloud. Site name, app install order, fixture sync, post-install steps, how to roll back.
- **`venue_rollout_playbook.md`** — You have this. Make sure it's referenced from `README.md`.
- **`api_surface.md`** (new) — Every `@frappe.whitelist()` method in the app, what it does, who can call it, expected inputs/outputs. AI-generated apps often have orphaned whitelisted methods nobody documented.
- **`troubleshooting.md`** (new) — Top 10 errors a developer might hit (failed migration, lock not releasing, fixture conflict), with fixes. Pull these from your own pain points over the past weeks.

### Architecture diagram template (drop into ARCHITECTURE.md)

```
Bathhouse Settings (Singleton)
    │
    ├── Bathhouse Location (1:N)
    │       │
    │       ├── Bathhouse Asset (1:N) — workflow-managed status
    │       ├── Bathhouse Shift (1:N) — totals computed on demand
    │       └── Bathhouse Incident (1:N)
    │
    └── Membership Type (1:N)
            └── Bathhouse Membership (N:1 → User/Customer)

Sales Invoice (extended)
    └── Bathhouse Assignment (child table) — links to N Bathhouse Assets

Bathhouse Receivable Log — flat audit ledger, no parent
```

---

## Part 3 — CLAUDE.md: Briefing the Next AI Session

The research is clear on this: **shorter is better**. Claude Code's own team injects a system reminder telling Claude to ignore CLAUDE.md content that isn't relevant to the current task — so a bloated file actively makes things worse, not better. The HumanLayer guide notes models follow ~150–200 instructions reliably, and quality drops fast past that.

Your current CLAUDE.md is annotated "LOCKED" — that's good as a snapshot, but for handoff you want a *lean* version that briefs a fresh AI session in under 30 seconds of reading.

### What CLAUDE.md must contain

Keep this under 200 lines. Beyond that, prune.

```markdown
# Hamilton ERP

Frappe v16 custom app for multi-venue bathhouse operations.
Pilot venue: Club Hamilton. Future venues use feature flags, not forks.

## Stack
- Frappe Framework v16
- ERPNext v16
- MariaDB (NOT Postgres — assumption point)
- Redis for asset locking

## Run / Test / Build
- Dev site: `bench --site hamilton-unit-test.localhost serve`
- Run all tests: `bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp`
- Run one module: `bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.bathhouse.doctype.bathhouse_asset.test_bathhouse_asset`
- Migrate: `bench --site hamilton-unit-test.localhost migrate`
- Build assets: `bench build --app hamilton_erp`

## Code style
- Follow Frappe core conventions (tabs, not spaces — yes, tabs).
- All user-facing strings: wrap in `_("...")` (Python) or `__("...")` (JS).
- DB access: prefer `frappe.db.get_value`, `frappe.qb`, `frappe.get_all`. Raw SQL only when query builder cannot express it; never use `.format()` for SQL params.
- Functions ≤ 30 lines. If longer, split.
- Type hints on whitelisted API methods (we set `require_type_annotated_api_methods = True`).

## Architecture pointers
- See `docs/ARCHITECTURE.md` for the full picture before editing DocTypes.
- See `docs/decisions_log.md` for "why" on locked-in choices.
- Asset status changes ONLY via workflow — never direct field write.
- Multi-asset transactions use child table `Bathhouse Assignment` on Sales Invoice.
- Race conditions on assignment use `frappe.db.get_value(..., for_update=True)` + Redis lock.

## Things NOT to do
- Do NOT use `override_doctype_class` in hooks.py — use `extend_doctype_class`.
- Do NOT use `frappe.flags.in_test` — v16 uses `frappe.in_test`.
- Do NOT compare Frappe doc fields to `"1"` / `"0"` — v16 returns real types.
- Do NOT touch the Redis lock TTL without reading `lessons_learned.md`.

## Open issues / known gotchas
- (link to GitHub issues or a short list)
```

### What does NOT belong in CLAUDE.md

- Long architectural narratives (those go in `ARCHITECTURE.md`).
- Project history (that goes in `lessons_learned.md`).
- Personal preferences ("Chris likes…").
- Anything about your specific dev environment (laptop specs, terminal preferences).
- Anything that's already enforced by a linter or hook — Claude isn't a linter.

---

## Part 4 — Test Suite: What "Production-Ready" Means

Your 270 tests across 12 modules is a strong starting point. The audit isn't about *count* — it's about *coverage of the right things*.

### What MUST be tested (in priority order)

1. 💸 **Workflow transitions** — every state change for Bathhouse Asset. Test both legal transitions and rejected illegal ones (`assertRaises`).
2. 💸 **Race conditions** — the Redis lock + `for_update=True` pattern. Mock-test concurrent assignment attempts. This is *the* hard problem in your domain and the developer will check it first.
3. 💸 **Permissions** — for each role (manager, staff, system manager), test that they can / cannot read, write, submit, cancel, amend each DocType. The Frappe Helpdesk testing guide explicitly calls this out as required.
4. 💸 **Validation logic** — every `validate()` method. Edge cases: empty values, nulls, max lengths, special characters.
5. **Whitelisted API methods** — every `@frappe.whitelist()` method needs a test for: happy path, missing params, unauthorized user, malformed input.
6. **Workflow approvals** — if managers must approve cancels/amends, test that non-managers are blocked.
7. **Computed fields / on-demand totals** — shift totals especially. Test with zero transactions, one transaction, many transactions, voided transactions.
8. **Receivable log / audit trail** — verify entries are written, never deleted, and survive cancellation of source docs.

### What CAN be skipped (be explicit in `TESTING.md`)

- Standard Frappe framework behavior (don't test that `frappe.get_doc` works).
- UI rendering (Frappe doesn't lend itself to JS unit tests easily; document this as an explicit non-goal).
- Third-party library internals.

### Coverage targets

A reasonable bar for a custom Frappe app:
- 70%+ line coverage on custom Python code.
- 100% coverage of workflow transitions and permission boundaries.
- Every `@frappe.whitelist()` method has at least one test.

Run `bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --coverage` and commit the coverage report or a screenshot of it to `docs/`. A senior dev seeing this will trust the suite immediately.

### Red flags in test suites a senior dev will spot

- Tests with no assertions (just exercising code).
- Tests that always pass because of `try/except: pass`.
- Tests that depend on each other (run order matters).
- Tests that don't clean up (rely on full DB reset between runs).
- Tests committing to the database without rollback (your code calls `frappe.db.commit()` — these MUST be mocked, per the Frappe Press testing guide).
- Identical tests with renamed function (AI duplication tell).

---

## Part 5 — Fixtures, Patches, Setup Scripts

This is what gets a developer from `git clone` to working site. The acceptance test: a fresh site comes up in **under 30 minutes** with realistic data, with no manual UI clicking.

### Fixtures — what to export to git

In `hooks.py`, the `fixtures` list should include everything needed to make the app *work*, not just *install*:

- All custom DocTypes (auto-included by Frappe).
- All Custom Fields the app adds to standard DocTypes (e.g., extensions to Sales Invoice).
- All Workflows (Bathhouse Asset workflow, plus any cancel/amend approval flows).
- All Workflow States and Workflow Actions used.
- All Roles created by the app (and any default Role Profiles).
- Print Formats specific to the app.
- Notification configs (if any).
- Property Setters (configuration changes to standard DocTypes).
- Server Scripts / Client Scripts if the app uses them.

**Export command:** `bench --site hamilton-unit-test.localhost export-fixtures --app hamilton_erp`

This produces JSON files in `hamilton_erp/fixtures/`. Commit them. **Then test the install on a fresh site** — fixtures are the most common silent breakage point.

### Patches — what belongs there

Frappe runs `patches.txt` entries once per site, in order. Use them for:
- Renaming a DocType field after data already exists.
- Backfilling computed fields.
- Migrating old workflow states to new ones.

**Do NOT use patches for:** initial data setup (that's a setup script). One-off cleanups (delete those after they run on production).

Audit your `patches.txt` — every entry should have a comment explaining what it does and what site state it expects. AI tends to leave undocumented patches that nobody understands six months later.

### Setup script

Create `hamilton_erp/setup/install.py` or use `after_install` hook. It should:
- Create default Bathhouse Settings (singleton).
- Create the Hamilton location record.
- Set up demo asset records (lockers, rooms, etc.).
- Set up a test Membership Type.
- Set up demo staff users with PINs (in dev only — gate with a check).

Critical: the install must be **idempotent** — running it twice must not error or duplicate records.

### Demo data script (separate from install)

Create `hamilton_erp/setup/demo_data.py` invoked via a bench command. Generates realistic test data — a week of shifts, mock transactions, sample incidents. **This is what lets a developer click around and understand the app immediately** instead of staring at empty lists.

```bash
bench --site hamilton-unit-test.localhost execute hamilton_erp.setup.demo_data.create_all
```

Document this command in `SETUP.md`.

---

## Part 6 — Common Problems in AI-Generated ERPNext Codebases

Research from Sonar, CodeScene, and academic studies (CodeRabbit's PR analysis showed AI-co-authored PRs have ~1.7× more issues than human-authored) identifies consistent patterns. Here are the ones that appear in Frappe codebases specifically. Walk this list against `hamilton_erp`:

### 1. Code duplication
AI generates similar logic in multiple places instead of extracting helpers. GitClear's 2020–2024 analysis found an 8× increase in duplicated 5+ line blocks in AI-assisted code.
**How to find it:** `grep` for repeated function bodies. Look for near-identical blocks across DocType controllers.
**Fix:** Extract to `hamilton_erp/utils/` modules. Common helpers: `get_active_assets_at_location`, `compute_shift_total`, `acquire_asset_lock`.

### 2. Dead / orphan code
Functions never called, imports never used, whitelisted methods nothing references.
**How to find it:** `pip install vulture && vulture hamilton_erp/` flags unused code with confidence scores.
**Fix:** Delete it. Every dead function is a question the next developer has to answer.

### 3. Wrong abstraction level
AI tends to over-build (the OAuth2 flow story from the agilepainrelief blog is typical). Look for: complex class hierarchies where a function would do, custom config systems where Frappe's existing settings would do, custom email senders when `frappe.sendmail` exists.
**Fix:** Prefer Frappe primitives. If the framework already does it, don't reimplement it.

### 4. High cyclomatic complexity
Sonar's data: Claude 3.7 Sonnet flagged 422 instances of high complexity in their study. Frappe controllers especially get unwieldy `validate()` methods.
**How to find it:** `pip install radon && radon cc hamilton_erp -a -nb` shows complexity per function. Anything graded D or F (CC ≥ 21) needs splitting.
**Fix:** Extract guard clauses, split conditionals into named methods. The Frappe coding standards explicitly say: more than one level of indentation in a method = doing more than one thing.

### 5. Missing error handling
AI generates the happy path, silently skips error cases. Common Frappe-specific gaps:
- Calling `frappe.get_doc()` on a name that might not exist (no `frappe.db.exists()` check).
- Calling `frappe.db.get_value(..., as_dict=True)` and accessing a key without checking the result is not None.
- File operations without `try/except`.
- External API calls (Stripe, Twilio if any) without retry or timeout handling.

### 6. SQL injection / unsanitized input
Per Frappe's security wiki: `.format()` in SQL is a vulnerability. Audit every `frappe.db.sql(` call:
- Does it use `%s` placeholders, not `.format()`?
- If user input goes in a variable, is it escaped via `frappe.db.escape()`?
- Could it be rewritten with `frappe.qb` or `frappe.db.get_all()` instead?

### 7. `ignore_permissions=True` overuse
This is the single biggest red flag in Frappe code. Every use needs a comment explaining why bypassing permissions is necessary and safe. Many AI-generated controllers add it reflexively to avoid permission errors during development — and ship that way.
**Find them:** `grep -rn "ignore_permissions=True" hamilton_erp/`
**Audit:** for each, justify or remove.

### 8. Poor function/variable names
AI naming smells: `process_data`, `handle_thing`, `do_validate`, `helper`, `utils`, `stuff`. Frappe convention is verb-noun and specific: `validate_asset_assignment`, `compute_shift_total_amount`, `acquire_asset_lock`.

### 9. Missing database indexes
DocType JSON files have an `"index": 1` flag per field. AI rarely sets it. Audit every DocType:
- Fields used in `WHERE` clauses → need indexes.
- Foreign-key-style Link fields → usually need indexes (especially the high-cardinality ones).
- Status fields filtered constantly → need indexes.
For Hamilton specifically: `Bathhouse Asset.status`, `Bathhouse Asset.location`, `Bathhouse Assignment.asset`, `Bathhouse Shift.staff_pin`, `Bathhouse Shift.location`, `Bathhouse Receivable Log.session_id`.

### 10. Inconsistent style
AI rotates between `frappe.db.get_value`, `frappe.get_value`, `frappe.db.sql`, raw queries — sometimes for the same task. Pick one and refactor. Frappe coding standards prioritize: query builder → `frappe.db.get_value` / `frappe.get_all` → raw SQL only as last resort.

### 11. DocType definition gaps
Open each `.json` file in `hamilton_erp/bathhouse/doctype/*/`:
- Every field has a `description` (shows as tooltip — saves training time).
- Required fields are flagged.
- Read-only computed fields are flagged read-only.
- `track_changes: 1` is set if the doc should have audit history.
- `is_submittable` is intentional (true = needs cancel/amend logic).
- Naming series is set if names should be human-readable (e.g., `BHA-.YYYY.-.####`).

### 12. Missing translations
The Frappe coding standard mandates `_("...")` and `__("...")` wrapping. Even for English-only apps, this is required — it's how Frappe surfaces UI strings consistently. Audit every user-facing string and `frappe.throw()`/`frappe.msgprint()` call.

---

## Part 7 — Security & Permissions: Most Commonly Overlooked

Per Frappe's security guidelines and ERPNext code-review wiki:

- 💸 **`@frappe.whitelist()` on internal helpers.** Whitelisting exposes a method to HTTP — anyone can call it. Audit: every whitelisted method is an *intentional public API*. If it's an internal helper, remove the decorator.
- 💸 **`allow_guest=True` on whitelisted methods.** Search for this — it means *unauthenticated* users can hit the endpoint. Should be near-zero in your app.
- 💸 **Permission checks inside whitelisted methods.** Even with `@frappe.whitelist()`, the function body should call `frappe.has_permission()` or rely on standard doc permissions. AI often skips this.
- 💸 **System Manager role assignments.** Verify only your account has it. Per your existing checklist — confirm this is locked down.
- **Role permissions per DocType.** Open each DocType → Permissions tab. Audit who has read/write/create/cancel/amend/submit. Default permissions from `bench new-doctype` are usually too permissive.
- **Field-level permissions (perm levels).** Sensitive fields (cost rates, staff PINs, customer payment data) should be on a higher perm level than the doc itself, restricted to managers.
- **Field masking on display.** Staff PINs, partial card numbers, etc. — verify they don't leak into list views or reports.
- **File path handling.** If any code accepts a filename or path from user input, verify it cannot escape the site directory (Frappe's "File" doctype API does this for you — use it).
- **`frappe.get_attr(method)(*args)`** — search for this pattern. It's Frappe's "exec arbitrary Python" footgun. Should not exist in your code.
- **Stored secrets.** No API keys, passwords, or tokens in source. Use Frappe's `Site Config` or environment variables. Run `git log -p | grep -iE 'secret|password|api_key|token'` to check history.
- **Audit trail completeness.** `track_changes: 1` on financial DocTypes. Document Versioning enabled at site level. Bathhouse Receivable Log entries cannot be deleted.
- **Brute force on PIN auth.** Since PIN-based staff identity replaces standard auth, verify there's a rate limiter or attempt counter. Standard Frappe login has this; your custom flow may not.

---

## Part 8 — hooks.py: What a Senior Developer Expects

`hooks.py` is the first file most experienced Frappe devs open after `README.md`. It tells them *what the app does without reading the code*. Here's what they want to see — and what makes them lose confidence.

### Expected (clean shape)

```python
# App identity
app_name = "hamilton_erp"
app_title = "Hamilton ERP"
app_publisher = "ANVIL Corp"
app_description = "Multi-venue bathhouse operations: assets, sessions, shifts, memberships."
app_email = "..."
app_license = "MIT"
app_version = "0.1.0"

# Required apps — explicit
required_apps = ["frappe", "erpnext"]

# Doc events — grouped logically, with comments per non-obvious hook
doc_events = {
    "Sales Invoice": {
        "validate": "hamilton_erp.bathhouse.sales_invoice.validate_assignments",
        "on_submit": "hamilton_erp.bathhouse.sales_invoice.create_receivable_log",
    },
    "Bathhouse Asset": {
        "validate": "hamilton_erp.bathhouse.doctype.bathhouse_asset.bathhouse_asset.validate_workflow_only_status",
    },
}

# Scheduled jobs — explicit frequencies, comments
scheduler_events = {
    "hourly": [
        "hamilton_erp.bathhouse.scheduler.detect_stale_assets",
    ],
}

# Fixtures — explicit list (not auto-everything)
fixtures = [
    {"dt": "Workflow", "filters": [["name", "in", ["Bathhouse Asset Workflow"]]]},
    {"dt": "Workflow State", "filters": [["name", "in", ["Available", "In Use", "Cleaning", "Out of Service"]]]},
    {"dt": "Role", "filters": [["name", "in", ["Bathhouse Manager", "Bathhouse Staff"]]]},
    {"dt": "Custom Field", "filters": [["dt", "in", ["Sales Invoice"]]]},
    # ...
]

# Type-annotated APIs (v16 feature — turn this on)
require_type_annotated_api_methods = True
export_python_type_annotations = True
```

### Red flags that lose developer confidence immediately

1. **Wildcard `"*"` in `doc_events`.** Performance disaster — runs on every doc save in the system.
2. **Functions referenced in hooks that don't exist.** Run `grep` on every hook target and verify the function exists in code. AI sometimes hallucinates these.
3. **`override_doctype_class` instead of `extend_doctype_class`.** You already flagged this in your existing list. Per your memory, it's at line 69. Fix before handoff.
4. **No `required_apps`.** Means the app silently breaks if installed without ERPNext.
5. **`fixtures = "*"`** or omitting the filter. Exports everything in the database — including data from other apps. Saw this once; the fixture file was 80MB.
6. **Empty `boot_session`, `extend_bootinfo`, etc. with comments saying "TODO".** Senior devs read TODOs as "this is broken or incomplete."
7. **Inline lambdas in hook values.** Hook values must be string paths to functions. AI sometimes writes lambdas — they fail silently.
8. **No comments on non-obvious hooks.** Why does `Sales Invoice.on_submit` write to a receivable log? A one-line comment saves a 30-minute investigation.
9. **Hooks referencing private (`_underscore`) functions.** Hooks should call public, named, tested functions.
10. **Blocking work in `before_request` / `after_request`.** Adds latency to every HTTP request. Should be near-empty.

### `hooks.py` audit command for Claude Code

Have Claude Code run these and fix what they surface:

```bash
# Find every function referenced in hooks.py and verify it exists
grep -oE '"hamilton_erp\.[a-z_.]+"' hamilton_erp/hooks.py | sort -u | while read ref; do
  module=$(echo $ref | tr -d '"' | rev | cut -d. -f2- | rev)
  func=$(echo $ref | tr -d '"' | rev | cut -d. -f1 | rev)
  echo "Checking: $ref"
  python -c "import ${module}; getattr(${module}, '${func}')" 2>&1 | head -1
done
```

---

## Part 9 — "Works" vs "Maintainable": The Real Difference

This is the question your Phase 2 developer will be silently asking on day one. Here's what separates the two:

| Code that works | Code that's maintainable |
|-----------------|--------------------------|
| The happy path returns the right answer. | The error paths are explicit and named. |
| Variable names made sense to the author at the time. | Variable names make sense to a reader who wasn't there. |
| Functions do what they need to. | Each function does **one thing**, named for that thing. |
| Comments explain *what* the code does. | Comments explain *why* it does it that way. |
| Tests exist. | Tests document the contract — what's promised, what's forbidden. |
| Architecture lives in the author's head. | Architecture lives in `ARCHITECTURE.md` and `decisions_log.md`. |
| Changes require touching many files. | Changes are local — one concept, one place. |
| New developers ask "why is this here?" | New developers find the answer in the file. |
| Edge cases are discovered in production. | Edge cases are tested or documented as out-of-scope. |
| Code is consistent with itself. | Code is consistent with framework conventions (Frappe core). |

A useful self-check: **for each non-obvious decision in your codebase, can you point to a file that explains it?** If the answer is "it's in my head" or "I told Claude in a chat once" — that's billable hours waiting to happen.

---

## Part 10 — Prioritized Handoff Checklist

Walk top-to-bottom. Items marked 💸 will cost you billable hours from your developer if missed.

### Tier 1 — Block handoff if not done (1–2 days of work)

- [ ] 💸 `README.md` is one page, accurate, and tested. Has install command, test command, links to deeper docs.
- [ ] 💸 `LICENSE` file present.
- [ ] 💸 `docs/SETUP.md` walks fresh-laptop → working dev site in ≤ 30 min. **You actually run it on a clean environment to verify.**
- [ ] 💸 `docs/ARCHITECTURE.md` explains all 10 DocTypes, their relationships, and the 6 key locked-in decisions (singleton, child table, workflow-only, PIN auth, Redis lock, on-demand totals).
- [ ] 💸 `CLAUDE.md` is under 200 lines, follows the template above, no narrative bloat.
- [ ] 💸 `hooks.py` audit complete: all referenced functions exist, no wildcards, `extend_doctype_class` not `override_`, all 36 instances of `frappe.flags.in_test` replaced with `frappe.in_test`.
- [ ] 💸 Fixtures exported and committed; **fresh site install verified** to produce identical state.
- [ ] 💸 All `@frappe.whitelist()` methods audited: justified as public API or decorator removed; permission check inside body.
- [ ] 💸 No `allow_guest=True` anywhere unintentional.
- [ ] 💸 No `ignore_permissions=True` without a comment explaining why.
- [ ] 💸 All `frappe.db.sql` calls use `%s` placeholders, not `.format()`.
- [ ] 💸 System Manager role assignment locked to your account only.
- [ ] 💸 Test suite passes 100% on a fresh site (not just locally). Document the run command.
- [ ] 💸 Workflow transitions, permission boundaries, and race condition tests all green and reviewed.

### Tier 2 — Strongly recommended (2–3 days of work)

- [ ] `docs/decisions_log.md` reviewed: every decision has a "why."
- [ ] `docs/lessons_learned.md` reviewed: kept honest, no rewriting history.
- [ ] `docs/TESTING.md` exists: how to run, what's covered, what's out of scope.
- [ ] `docs/DEPLOYMENT.md` exists: Frappe Cloud setup steps.
- [ ] `docs/api_surface.md` exists: every whitelisted method documented.
- [ ] `docs/troubleshooting.md` exists: top 10 errors with fixes.
- [ ] Demo data script exists and is documented.
- [ ] All DocType JSONs reviewed: descriptions on fields, indexes set, naming series set.
- [ ] `vulture` run: dead code removed.
- [ ] `radon` run: no functions graded D or F unaddressed.
- [ ] All user-facing strings wrapped in `_()` / `__()`.
- [ ] All `==  "1"` / `== "0"` string comparisons replaced (v16 type change).
- [ ] Git history scrubbed for secrets (use `git log -p | grep -iE 'secret|password|api_key|token'`).
- [ ] CI/CD workflow on GitHub Actions: runs tests on every PR, blocks merge on failure.
- [ ] Coverage report committed to docs (or CI badge in README).
- [ ] Pre-commit hooks set up (black, ruff, basic linting). Frappe Cloud's standard `.pre-commit-config.yaml` is a good starting point.

### Tier 3 — Nice to have (improves trust, saves billable hours)

- [ ] Architecture diagram as PNG/SVG (not just ASCII), embedded in `ARCHITECTURE.md`.
- [ ] Video walkthrough (10–15 min) of the app for the new developer. Loom is fine.
- [ ] Tagged `v0.1.0` release on GitHub with release notes.
- [ ] Dependency versions pinned in `pyproject.toml`.
- [ ] `.editorconfig` for consistent formatting across editors.
- [ ] Issue templates and PR template in `.github/`.
- [ ] Contributing guide for the new developer's specific working style (branching, commit message format).
- [ ] Onboarding email/doc explicitly listing: "here is what's done, here is what's next, here is what's broken, here is what's intentionally deferred."

### Tier 4 — Phase 2 prep (do during/after handoff)

- [ ] Multi-venue refactor plan documented before any DC build (per your memory note).
- [ ] DC sync notes captured in `dc_sync_notes.md`.
- [ ] Phase 2 Taskmaster list created (check-in flow, POS, Stripe Terminal, etc.).
- [ ] Frappe Cloud production hosting confirmed and documented.
- [ ] Pre-handoff research prompts from `docs/hamilton_pre_handoff_prompts.md` run.

---

## Part 11 — The "What This Will Cost You If Missing" Heuristic

For each Tier 1 item, here's the realistic billable-hours cost when a developer hits the gap cold:

| Missing item | Realistic billable hours wasted |
|---|---|
| No `SETUP.md` | 2–4 hrs (figuring out env, dependencies, fixture order) |
| No `ARCHITECTURE.md` | 4–8 hrs over first week (re-deriving why decisions were made) |
| Bloated `CLAUDE.md` | Compounds — bad AI suggestions cost ~30 min each, dozens of times |
| Broken fixtures | 2–6 hrs (debugging install, then re-deriving config) |
| Hook references to nonexistent functions | 1–3 hrs (silent failures are the worst kind) |
| `ignore_permissions=True` everywhere | 3–8 hrs (security review forced when it should be a glance) |
| No tests for race conditions | Eventually: a production incident, then 8+ hrs of debugging |
| No `api_surface.md` | 30 min per whitelisted method the dev has to reverse-engineer |
| No troubleshooting doc | The dev pings you for every gotcha you already solved |

A dev billing $100–$200/hr means a weak handoff costs **$2,000–$5,000 in the first month** alone. Tier 1 is your highest-ROI work.

---

## Part 12 — Final Sanity Check (the night before sending the repo)

Run this exact sequence. If any step fails, the handoff isn't ready:

```bash
# 1. Clean clone test
cd /tmp
git clone https://github.com/csrnicek/hamilton_erp.git
cd hamilton_erp

# 2. README has install command? (eyeball it)
head -50 README.md

# 3. Setup doc walks through it?
cat docs/SETUP.md | head -100

# 4. Fresh site install (use a fresh bench or container)
# (Follow your own SETUP.md — DO NOT improvise)

# 5. Tests run and pass
bench --site [test-site] run-tests --app hamilton_erp

# 6. Coverage report runs
bench --site [test-site] run-tests --app hamilton_erp --coverage

# 7. App appears in /app and basic UI loads
# (Open browser, log in, navigate to a Bathhouse Asset list view)

# 8. Demo data script populates realistic data
bench --site [test-site] execute hamilton_erp.setup.demo_data.create_all

# 9. hooks.py reference check
grep -oE '"hamilton_erp\.[a-z_.]+"' hamilton_erp/hooks.py | sort -u
# (verify each one resolves)

# 10. Secret scan on git history
git log -p | grep -iE 'secret|password|api_key|token|aws|stripe_sk'
```

If all 10 pass with no manual intervention, you're handoff-ready.

---

## Appendix — Quick wins to ask Claude Code to do for you

These are the "delegate to Sonnet, walk away" tasks. Run each as a single Claude Code session:

1. "Read every `.py` file in `hamilton_erp/` and list every function that has zero callers anywhere in the codebase."
2. "List every `frappe.db.sql` call and flag any using `.format()` for parameter substitution."
3. "List every `@frappe.whitelist()` method and check whether the function body has a `frappe.has_permission()` or equivalent permission check."
4. "Audit every DocType JSON in `hamilton_erp/bathhouse/doctype/` for: missing field descriptions, missing indexes on Link/status fields, missing `track_changes`, missing `naming_series`."
5. "Count cyclomatic complexity for every function. List anything over 15."
6. "Find every `ignore_permissions=True` and group by file. For each, generate a one-line justification or flag for removal."
7. "Generate `docs/api_surface.md` from every `@frappe.whitelist()` method, including the docstring, parameters, and grep results showing where it's called from."
8. "Audit `hooks.py`: verify every function reference resolves to an actual importable function in the codebase."
9. "Generate the Tier 1 docs from this checklist using only what exists in the codebase plus my `decisions_log.md` and `lessons_learned.md`. Flag anything you can't generate confidently."
10. "Re-export fixtures, then diff against the committed fixture files. Show me what changed."

---

**Document version:** 1.0 — Hamilton ERP handoff prep
**Use alongside:** existing `docs/decisions_log.md`, `docs/lessons_learned.md`, `docs/venue_rollout_playbook.md`, `docs/hamilton_pre_handoff_prompts.md`.
