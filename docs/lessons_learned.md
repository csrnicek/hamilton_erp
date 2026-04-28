# Lessons Learned — Hamilton ERP

Hard-won knowledge from Phase 0 and Phase 1 development. Each entry documents a real bug,
debugging dead-end, or production surprise so the next venue build avoids repeating it.

**Template:**
```
## Lesson: [Title]
- **What happened:** ...
- **Time cost:** ...
- **Root cause:** ...
- **The fix:** ...
- **Prevention for next venue:** ...
- **Relevant commit/DEC:** ...
```

---

## Lesson: `frappe.is_setup_complete()` reads the wrong table

- **What happened:** After a test run wiped dev state, the browser entered a ~40-req/s redirect loop between `/app` and `/app/setup-wizard`. Three separate heal attempts targeted the wrong data stores (`tabDefaultValue`, `System Settings`) and silently succeeded without fixing anything.
- **Time cost:** ~4 hours of debugging on 2026-04-11.
- **Root cause:** Frappe v16 reads `tabInstalled Application.is_setup_complete` for `frappe` and `erpnext` — not `tabDefaultValue` or `System Settings`. Both legacy stores accept writes without error but have no effect on `frappe.is_setup_complete()`.
- **The fix:** Target `tabInstalled Application` directly. Added `ensure_setup_complete` as an `after_migrate` hook so every `bench migrate` auto-heals the flag. Commit `7c866a6`.
- **Prevention for next venue:** The `after_migrate` hook ships with the codebase. New venues get it automatically. The bootstrap procedure in DEC-059 documents the exact setup sequence.
- **Relevant commit/DEC:** DEC-060, commit `7c866a6`

---

## Lesson: `frappe.call()` defaults to POST, `curl` defaults to GET

- **What happened:** Asset Board API endpoint decorated with `methods=["GET"]` returned 403 in the browser but passed every curl test and every direct Python import test.
- **Time cost:** ~2 hours.
- **Root cause:** `frappe.call()` sends POST by default. A `@frappe.whitelist(methods=["GET"])` endpoint will reject POST. Curl tests default to GET and pass. Direct Python imports bypass the HTTP verb gate entirely.
- **The fix:** Changed the decorator to `methods=["GET"]` AND ensured `frappe.call` uses `type: "GET"` on the frontend. Added regression tests that mock `frappe.local.request` to verify verb enforcement. Commit in DEC-058 arc.
- **Prevention for next venue:** Verb-gate regression tests ship with the test suite. The `TestAssetBoardHTTPVerb` pattern tests the actual HTTP layer.
- **Relevant commit/DEC:** DEC-058

---

## Lesson: Dev site and test site must be separate

- **What happened:** Running `bench run-tests` on `hamilton-test.localhost` (the dev browser site) corrupted it: setup_wizard loops, 403 errors, wiped roles, deleted Venue Assets. Required full `restore_dev_state()` recovery after every test run.
- **Time cost:** Cumulative ~6 hours across Tasks 13-16.
- **Root cause:** Test teardown resets DB state that the dev browser relies on. `setup_complete` flags get flipped, roles get stripped from Administrator, and test data cleanup deletes production-like records.
- **The fix:** Created dedicated `hamilton-unit-test.localhost` site for all test runs. Repointed all slash commands. Added top-of-file WARNING to `testing_checklist.md`.
- **Prevention for next venue:** Every venue gets two sites from day one: `{venue}-dev.localhost` and `{venue}-test.localhost`. This is now a bootstrap requirement in DEC-059.
- **Relevant commit/DEC:** DEC-059, commit `0cf1fb1`

---

## Lesson: Session number NNN > 999 breaks sort order

- **What happened:** Session number format `{d}-{m}-{y}---{NNN}` uses a 3-digit zero-padded sequence. When NNN exceeds 999, the string sort breaks (1000 sorts before 200).
- **Time cost:** None yet — caught during code review before it hit production.
- **Root cause:** 3-digit padding (`{:03d}`) is insufficient for high-volume venues.
- **The fix:** Deferred to Task 11 with a `:04d` fix noted. Hamilton's single-venue daily volume won't hit 999, but DC with 3 tablets might.
- **Prevention for next venue:** Apply 4-digit padding from day one on any new venue. The fix is a one-line format string change.
- **Relevant commit/DEC:** DEC-033

---

## Lesson: `scheduler_events` changes require `bench migrate`

- **What happened:** Added a new scheduled job to `hooks.py` under `scheduler_events`. The job never ran.
- **Time cost:** ~30 minutes.
- **Root cause:** Frappe reads `scheduler_events` from hooks at migrate time and caches the schedule. Changing `hooks.py` without running `bench migrate` means the scheduler never picks up the new job.
- **The fix:** Always run `bench migrate` after any change to `scheduler_events` in `hooks.py`.
- **Prevention for next venue:** Document in venue rollout playbook. Add to CI checklist.
- **Relevant commit/DEC:** N/A — operational knowledge

---

## Lesson: Redis uses non-default ports on local bench

- **What happened:** Redis commands targeting port 6379 (the default) silently connected to nothing or to a different Redis instance. Lock operations appeared to succeed but had no effect.
- **Time cost:** ~1 hour.
- **Root cause:** Local Frappe bench uses cache on port 13000 and queue on port 11000, configured in `common_site_config.json`.
- **The fix:** Always check `common_site_config.json` for actual Redis ports. Start them explicitly: `redis-server --port 13000 --daemonize yes && redis-server --port 11000 --daemonize yes`.
- **Prevention for next venue:** Include Redis port verification in the `/debug-env` slash command (already done).
- **Relevant commit/DEC:** N/A — operational knowledge

---

## Lesson: Fixtures are invisible to Git unless exported

- **What happened:** Custom Fields, Roles, and Property Setters configured in the ERPNext UI exist only in the database. They are invisible to Git and will be lost when a new venue site is created.
- **Time cost:** N/A — caught during pre-handoff research, not in production.
- **Root cause:** Frappe stores UI configuration in the database. The fixture export system (`bench export-fixtures`) creates JSON files that Git can track, but this must be done explicitly.
- **The fix:** Export all fixtures before handoff. Declare them in `hooks.py`. Both steps required.
- **Prevention for next venue:** Add fixture export to the venue rollout playbook as a mandatory step. Run `bench export-fixtures --app hamilton_erp` after any UI configuration change.
- **Relevant commit/DEC:** Task 25 checklist

---

## Lesson: `IGNORE_TEST_RECORD_DEPENDENCIES` must be a list, not a boolean

- **What happened:** Setting `IGNORE_TEST_RECORD_DEPENDENCIES = True` in a test module caused `TypeError: 'bool' object is not iterable`.
- **Time cost:** ~30 minutes.
- **Root cause:** Frappe's `generators.py:115` does `to_remove += module.IGNORE_TEST_RECORD_DEPENDENCIES` which requires list concatenation.
- **The fix:** Use `IGNORE_TEST_RECORD_DEPENDENCIES = []` (empty list), not `True`.
- **Prevention for next venue:** Documented in claude_memory.md best practices rule 4. Grep for `= True` in test files during code review.
- **Relevant commit/DEC:** N/A — Frappe quirk

---

## Lesson: mutmut v3 incompatible with Frappe bench environment

- **What happened:** mutmut v3 copies source to a `mutants/` directory and runs pytest from there. Frappe's test infrastructure requires `bench run-tests` which initializes the full bench context (DB connection, Redis, module registry). The copied `mutants/` directory has no bench context, so all tests fail with "Module Hamilton ERP not found."
- **Time cost:** ~45 minutes trying both v2 and v3 before building a custom solution.
- **Root cause:** mutmut v3 rewrote its architecture to use file copying instead of in-place mutation. mutmut v2 mutates in-place but crashes on Python 3.14 with a serialization error in the `copy` module.
- **The fix:** Built `scripts/mutation_test.py` — a lightweight custom mutation script that modifies files in-place, runs `bench run-tests`, and restores originals. 91% kill score on first run.
- **Prevention for next venue:** Ship `scripts/mutation_test.py` as part of the codebase. Don't install mutmut.
- **Relevant commit/DEC:** Commit `69c7992`

---

## Lesson: `frappe.flags.in_test` vs `frappe.in_test` — paired change required

- **What happened:** Code using `frappe.flags.in_test` worked under `bench run-tests` but is actually deprecated in Frappe v16. The correct attribute is `frappe.in_test` (a module-level global, not a flags attribute).
- **Time cost:** ~20 minutes.
- **Root cause:** Frappe v16 moved the test flag from `frappe.flags.in_test` to `frappe.in_test`. Both exist but `frappe.flags.in_test` may not be reliably set in all contexts (e.g., pytest without bench runner).
- **The fix:** Update production code (lifecycle.py) to use `frappe.in_test` and update all test scaffolding to match. This is a paired change — updating one without the other silently breaks test-mode detection.
- **Prevention for next venue:** Grep for `frappe.flags.in_test` during code review. Always use `frappe.in_test`.
- **Relevant commit/DEC:** N/A — Frappe v16 migration knowledge

---

## Lesson: `property_setter.json` must exist even if empty

- **What happened:** Frappe fixture export creates `property_setter.json`. If the file is missing, `bench migrate` on a new site silently skips Property Setter fixtures — no error, no warning, just silent data loss.
- **Time cost:** Caught during pre-handoff research, not in production.
- **Root cause:** Frappe's fixture loader checks for file existence. A missing fixture file is treated as "no fixtures to load" rather than an error.
- **The fix:** Always include `property_setter.json` in the app's fixtures directory, even if it contains just `[]`. Run `bench export-fixtures` regularly.
- **Prevention for next venue:** Include in the venue rollout playbook. The fixture export step is now mandatory.
- **Relevant commit/DEC:** Task 25 checklist

---

## Lesson: `pyproject.toml` must declare `frappe-dependencies` or Frappe Cloud blocks deploys

- **What happened:** Frappe Cloud refused to deploy the app because `pyproject.toml` was missing the `[tool.bench.frappe-dependencies]` section declaring minimum Frappe and ERPNext versions.
- **Time cost:** ~15 minutes.
- **Root cause:** Frappe Cloud's deploy pipeline checks `pyproject.toml` for dependency declarations. Without them, it can't determine compatibility and blocks the deploy.
- **The fix:** Added `[tool.bench.frappe-dependencies]` with `frappe = ">=16.0.0,<17.0.0"` and `erpnext = ">=16.0.0,<17.0.0"`.
- **Prevention for next venue:** Template `pyproject.toml` with the dependency section pre-filled.
- **Relevant commit/DEC:** N/A — Frappe Cloud operational requirement

---

*Add new lessons below this line.*

---

## 2026-04-27 — CI bootstrap trap

**What happened:** PR #9 set up GitHub Actions CI for hamilton_erp. The Tests workflow failed at every step of the install path on a fresh runner: missing `apps/frappe`, wrong Python version, wrong Node version, Redis ordering wrong, missing `hypothesis`, missing seed data, missing ERPNext root records, fresh-ERPNext `desktop:home_page='setup-wizard'` row. I fixed each in turn — 12 commits — and ended up with the workflow YAML containing inline Python heredocs that created Customer Group + Territory roots, raw SQL DELETE for the `tabDefaultValue` row, and a standalone `pip install hypothesis`. Each fix advanced the workflow by one step but accumulated a parallel install path that production would never run. Frappe Cloud deploys would have hit every one of those errors freshly because none of the workarounds existed in app code.

**What to do differently:** When CI fails at install or bootstrap, the first question is *"would this also fail on a fresh production deploy?"* If the answer is yes, the bug is in the app's install path, not in the CI workflow. Fix `setup/install.py` (or the relevant patch) so the install hook handles the missing precondition itself. CI then becomes a verifier — its only setup logic is `bench init` + `install-app` + run tests + assert outcomes — and the same code that makes CI pass also makes a fresh production install succeed. The pivot in PR #9 (commit `4c5d6c2`) reverted the 5 workaround commits, moved the bootstrap into `_ensure_erpnext_prereqs()` and `_seed_hamilton_data()` in `hamilton_erp/setup/install.py:after_install()`, moved the `desktop:home_page` cleanup into `ensure_setup_complete()` (after_migrate), declared `hypothesis` as a `[project.optional-dependencies] test` extra in `pyproject.toml`, and added a conformance-assertion CI step that proves the install path produced the expected records. Net: fewer lines of code, less duplication, and the install path actually works on every fresh bench — CI or production.

The drift-prevention rule shipped earlier the same day (`Verify Before Claiming Done` in CLAUDE.md) earned a sibling: **"If a test/CI fix needs logic that lives only in the test/CI environment, ask whether production has that logic. If not, the fix belongs in the app."**


## 2026-04-28 — Three-PR CI infrastructure day

### Lesson: CI passing != production-ready

PR #9 initially had CI workarounds (frappe/payments install via workflow, broken stress simulation skipped, vendored composite action) that made CI green without exercising the real install path. ChatGPT review caught this: "tests.yml is becoming a parallel install path."

**Fix:** Pivoted to Path 1 — install path owns its setup logic (`_ensure_erpnext_prereqs`, `_seed_hamilton_data`, `_ensure_no_setup_wizard_loop` in `hamilton_erp/setup/install.py`). CI workflow trimmed to: bench init → install-app → conformance assertions → tests.

**Rule going forward:** Workflow-only seed logic creates fake-green builds. The install path must produce the expected state on its own; CI just verifies it.

### Lesson: Install lifecycle hooks fire on different events

`ensure_setup_complete()` was called only on `after_migrate`. But `bench install-app` doesn't fire `after_migrate` — it fires `after_install`. So fresh installs (CI, new venues) never ran the heal logic.

**Fix:** Refactored into `_ensure_no_setup_wizard_loop()` called from BOTH `after_install` and `after_migrate`. Pre-migrate conformance step in CI proves install-app alone produces correct state.

**Rule going forward:** Any install-time logic must consider both lifecycle events. Verify in CI with a pre-migrate conformance step.

### Lesson: Branch protection requires manual UI configuration

The GitHub API for setting required status checks returns 404 even with admin scope on Personal Access Tokens. Manual UI step was the only path.

**Fix:** Documented in PR #9 cleanup and PR #11 prep: branch protection setup is a one-time manual step at https://github.com/csrnicek/hamilton_erp/settings/branches.

**Rule going forward:** When automating repo setup for new venues (DC, Philly), expect this manual step. Document it in venue_rollout_playbook.md.

### Lesson: Two-AI cross-review catches drift one AI misses

Claude Code building PR #9 was iterating CI workarounds. ChatGPT reviewing the same diff immediately spotted "this is becoming a parallel install path." Single-AI review would have shipped the workaround.

**Rule going forward:** For infrastructure or architecturally-significant PRs, cross-review with a second AI before merge. ChatGPT is currently the chosen second reviewer.

### Lesson: Stash before switching branches when working tree has divergent base

Working tree had +134 line scratch in docs/inbox.md based on PR #11's cleaned blob (b5b4ea5). main carries a different blob for inbox.md. Naive `git checkout main` would have either three-way-merged into a confusing state or blocked the switch.

**Fix:** `git stash push -m "..."` isolates the diff. Pop after the destination branch reaches the right base.

**Rule going forward:** When working tree has uncommitted changes relative to a different blob than the destination branch, stash first.

### Lesson: docs-only PRs still run full CI (and that's a feature)

Branch protection gates checks at the workflow level, not the file-change level. So a docs-only PR runs the full Server Tests suite (~22 minutes). Initially felt like overhead. But it confirmed that no docs PR accidentally smuggled in a code change someone missed in review.

**Rule going forward:** Don't try to skip CI for docs PRs. The 22-minute wait is the safety check.
