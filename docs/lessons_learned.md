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

## Lesson: `frappe.flags.in_test` vs `frappe.in_test` — two independent attributes, must clear both

- **What happened:** PRs #5/#6/#7 (E2E tests, Apr 14) defined a `real_logs()` context manager that toggled `frappe.flags.in_test` to make `_make_asset_status_log` write real audit logs during E2E tests. But the guard reads `frappe.in_test`, which is a *separate* module-level attribute. The toggle silently no-op'd: the guard still saw `True`, the audit log path was skipped, and any "exactly N log entries" assertion would fail. The bug went undetected for two weeks because the PRs sat stale; surfaced 2026-04-29 when PR #26 consolidated them and re-ran their tests against current main.
- **Time cost:** ~30 minutes to find and fix during the PR #26 consolidation.
- **Root cause:** Frappe v16 has *both* `frappe.in_test` (module-level boolean at `frappe/__init__.py:83`) and `frappe.local.flags.in_test` (request-scoped flag). Frappe's own test runner sets both via `frappe.tests.utils.toggle_test_mode(enable)`. They are NOT aliased — toggling one leaves the other unchanged, and code that reads only one silently no-ops when the other was the one toggled.
- **The fix:** A `real_logs()` helper that toggles **both** attributes, with a docstring pointing back to this lesson. Canonical version in `hamilton_erp/test_e2e_phase1.py::real_logs`; reused verbatim in `test_stress_simulation.py`.
- **Prevention for next venue:** Grep for `frappe.flags.in_test = ` and `frappe.in_test = ` in test code; ensure any toggle pairs them. Reuse `real_logs()` rather than re-rolling. The frappe.tests.utils.toggle_test_mode() helper is the official "set both" entry point — prefer it for new code.
- **Relevant commit/DEC:** PR #26 (consolidated H10/H11/H12 E2E), commit fixing `real_logs()` to clear both attributes.

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

## Lesson: Bench symlink defeats `git worktree` isolation

- **What happened:** Tried to run destructive probes in a temporary git worktree (`/tmp/hamilton_pr16_probe`) to keep the main checkout untouched. Frappe bench symlinks `apps/hamilton_erp` back to `~/hamilton_erp` regardless of which worktree is active, so `bench run-tests` operated against the main working tree the whole time. A Claude Code crash mid-probe would have left the working tree corrupted.
- **Time cost:** ~1 hour of confused debugging plus the cleanup.
- **Root cause:** `bench install-app` records the absolute path of the app at install time as a symlink under `apps/`. Switching the project's git worktree later doesn't update the symlink target.
- **The fix:** Use in-place backup/restore in the main repo with a STOP-ON-DIRTY rule for any destructive test. For frequent destructive probing, set up a separate bench install with its own clone.
- **Prevention for next venue:** Any session about to run a destructive probe must verify which path `bench` actually targets (`ls -l ~/frappe-bench-hamilton/apps/hamilton_erp`) before running anything, and must back up the affected files first.
- **Relevant commit/DEC:** Discovered during PR #16 probing on 2026-04-28.

---

## Lesson: Port the canonical mockup verbatim — do not interpret

- **What happened:** Three previous Claude sessions had implemented asset board UI features by reading the design spec and writing what felt like the right code. Each session translated the spec into its own interpretation. Drift compounded silently for weeks until a 60-divergence diff was run against `docs/design/V9_CANONICAL_MOCKUP.html`.
- **Time cost:** Weeks of accumulated drift, ~6 hours of cleanup spread across PRs #15, #19, #20, #21, #22.
- **Root cause:** "Implement the design spec" is an interpretation task. Two LLM sessions on the same spec produce different code. The right pattern is byte-for-byte porting of the canonical mockup file, only changing selectors that differ between mockup and production conventions.
- **The fix:** Lock V9_CANONICAL_MOCKUP.html as the canonical reference (PR #16 governance regime). Every UI task starts with reading the relevant section of the mockup, then bringing production into alignment by copy-paste rather than re-implementation.
- **Prevention for next venue:** When a venue's UI is "done," its canonical mockup file should be locked the same way. Production drift is a bug, not a creative liberty.
- **Relevant commit/DEC:** PR #16 (governance regime), CLAUDE.md "V9 Canonical Mockup — Gospel Reference" section.

---

## Lesson: Adversarial review budget — two rounds, not three

- **What happened:** PR #16 (a docs-only governance regime for a static HTML mockup file) went through three rounds of adversarial review. Round 1 (senior dev) found real things. Round 2 (adversarial probes) found a few more real things. Round 3 ("expert review") was hitting diminishing returns — most findings were predicted attacks, not demonstrated bugs. Net cost: ~3 hours that could have shipped real production fixes.
- **Time cost:** ~3 hours per extra round, plus opportunity cost of deferred production work.
- **Root cause:** "Keep hardening until reviewers stop finding things" treats every potential finding as equally severe. In practice, round 1 catches the cheap wins, round 2 catches the subtle wins, round 3 produces predictions of what reviews *might* find rather than verified bugs.
- **The fix:** Cap adversarial review at two rounds per PR. After that, ship and address residual risks in follow-up PRs (which are themselves easier to review because the diff is small).
- **Prevention for next venue:** This is a workflow rule, not a venue-specific thing. Apply to every PR. Use adversarial review for genuinely high-risk PRs (security, money, irreversible actions); skip for routine PRs and documentation changes.
- **Relevant commit/DEC:** Lesson surfaced 2026-04-28, captured here from the day-4 retrospective.

---

## Lesson: Green CI means tested contracts passed, not "the product works"

- **What happened:** The asset board passed every CI test for weeks while having 60 visible divergences from the locked V9 design. Phase 1 conformance tests covered API contracts, lifecycle transitions, and locking behavior — but no test covered "does the tile render with the right colors and copy in the browser." Each Claude session that ran `/run-tests` saw green and assumed the product was healthy.
- **Time cost:** Weeks of unnoticed drift; the divergence audit and 5-PR fix series ran 2026-04-28.
- **Root cause:** Server-side tests cover server-side contracts. UI work needs UI verification — either browser automation tests (which are expensive and brittle) or a human clicking through the canonical flows in a real browser against the canonical mockup as reference.
- **The fix:** UI tasks end with `/test-this` style browser walkthrough against the V9 mockup. "Done" only after that, even if CI is green.
- **Prevention for next venue:** Add a UI verification step to the venue rollout playbook. Browser verification on real test data is non-negotiable for UI work; green CI is a precondition, not a sign-off.
- **Relevant commit/DEC:** Captured 2026-04-28; reinforced by PRs #15/#19/#20/#21/#22 V9 conformance series.

---
## 2026-04-29 — Overnight autonomous run lessons

Six PRs landed/queued in a single overnight session (#24 through #29). The substance of the work — backend enrichment, schema pinning, E2E coverage, stress sim rewrite — is in the PRs and inbox. These are the lessons that generalize beyond the work itself:

### Lesson 1: Frappe test threads need an explicit `frappe.db.commit()`

**What happened:** PR #29's first CI run looked fine locally (`frappe.db.commit()` not necessary because the test runner committed at request boundary). I assumed `frappe.destroy()` would also commit. It does the opposite — it closes the connection with the transaction in whatever state it was, and any uncommitted writes get rolled back when the connection is dropped. The two threading tests in `TestStressConcurrentAssign` and `TestStressCrossAssetIsolation` showed `success=0` even when the lock and lifecycle calls had clearly executed.

**Root cause:** Frappe relies on the HTTP request boundary to auto-commit. Test threads have no request boundary. Without an explicit `frappe.db.commit()` after a successful operation, the transaction never reaches durable state.

**The fix:** Each thread body runs `frappe.db.commit()` immediately after its lifecycle call, with a `frappe.db.rollback()` in the except path. Documented inline in `hamilton_erp/test_stress_simulation.py::_attempt_assign`.

**Prevention:** When writing any thread body that calls a Frappe controller, the structure is `frappe.init` → `frappe.connect` → operation → `frappe.db.commit()` → `frappe.destroy()`. CLAUDE.md bans `frappe.db.commit()` in *controllers*; tests are not controllers and need it.

---

### Lesson 2: Cross-thread MVCC visibility — main connection's snapshot won't see thread commits

**What happened:** Even after the threading bug above was fixed, the post-condition `assertEqual(asset.status, "Occupied")` in `test_two_threads_only_one_wins` failed locally. The thread had committed; the main connection's `frappe.get_doc(...)` still saw "Available".

**Root cause:** MariaDB defaults to REPEATABLE READ. The test's main connection started its transaction (and snapshot) at `setUp` when it inserted the asset. The thread then committed an UPDATE — but that commit is invisible to the main connection until it ends its own snapshot.

**The fix:** Call `frappe.db.rollback()` on the main connection before re-reading post-thread state. That releases the snapshot; the next `get_value` sees committed reality. See `test_stress_simulation.py:147` for the exact pattern.

**Prevention:** Any test that asserts on state written by a thread must either rollback the main connection first or use a fresh `frappe.db.get_value` call that explicitly sidesteps the cached snapshot.

---

### Lesson 3: Test site name varies between local and CI — capture `frappe.local.site`

**What happened:** Local stress sim tests used `frappe.init(site="hamilton-unit-test.localhost")` in thread bodies. Locally they passed; CI failed with `IncorrectSitePath: 404 Not Found: hamilton-unit-test.localhost does not exist`.

**Root cause:** Local dev bench creates `hamilton-unit-test.localhost`. CI workflow (`.github/workflows/tests.yml`) creates `test_site`. Hardcoding either name is hostile to the other environment.

**The fix:** In `setUp`, capture `self.site = frappe.local.site` and pass `self.site` into `frappe.init(site=self.site)` in the thread body. The runner's site is always available on `frappe.local`. See `test_stress_simulation.py:108` for the pattern.

**Prevention:** Grep for `frappe.init(site="` literal strings — they should not exist in tests. Use `frappe.local.site`.

---

### Lesson 4: Stale PRs need their tests re-run against current main, not just rebased

**What happened:** PRs #5, #6, #7 were 95 commits behind main. They had `claude-review SUCCESS` from April 14 but predated the Server Tests CI workflow. Rebasing them and merging would have looked sound — but the tests would have failed in the new CI, because they depended on a test-helper bug (`real_logs()` toggling the wrong attribute, see Lesson 1 in this section). The bug only became visible by re-running the tests against current main.

**Root cause:** A "successful" review on a PR snapshot in time does not survive long enough drift. The tests were green when the PR was opened because the production code at that time *also* read `frappe.flags.in_test`; the production code changed in a later commit to read `frappe.in_test`, and the test scaffolding never followed.

**The fix:** Replace-not-rebase for PRs >50 commits behind main, or at minimum run their tests locally against current main before merging.

**Prevention:** Treat any PR more than ~30 commits behind main as needing local test verification, not just CI re-run on the same branch. The CI configuration may have changed; the production code definitely has.

---

### Lesson 5: Schema snapshot pinning catches silent API regressions

**What happened:** PR #24 added `guest_name` and `oos_set_by` fields to `get_asset_board_data`. The existing schema snapshot test used `assertGreaterEqual` against a base set of `REQUIRED_ASSET_FIELDS` — new fields could be silently dropped from the API payload and no test would fail. PR #25 pinned both new fields explicitly so any future regression that drops them fails CI loudly.

**Why this matters:** API payload regressions are some of the most expensive bugs because they only surface in the consuming UI. The schema snapshot test is cheap — one set membership check per field — and turns silent regressions into loud failures.

**Prevention:** Every new field added to `get_asset_board_data` (or any whitelisted read API) should be added to `REQUIRED_ASSET_FIELDS` in the same PR. Make this a checklist item in the PR template, or enforce it via CI.

---

### Lesson 6: Taskmaster estimates can be wildly wrong when the API has shifted underneath

**What happened:** Taskmaster Task 26 said "Estimated 15 minutes" for "Replace `from hamilton_erp.lifecycle import assign_asset` references". Reality: 42 tests in `test_stress_simulation.py` were already `@unittest.skip`'d for weeks, the old `assign_asset` had a different signature than the new `start_session_for_asset`, the old `vacate_asset` is now `vacate_session` with a new required parameter, the `acquire_lock` and `release_lock` functions don't exist (only the context manager), and the `assignment_status` field was renamed to `status`. A 15-minute import rewrite is actually a 2-3 hour structural rewrite.

**Root cause:** The estimate was written when the imports were the only thing wrong. As the rest of the codebase refactored, the gap widened, but the estimate did not get re-evaluated. The task description still read "stale imports" when the reality was "stale everything".

**The fix:** Delete + replace, not line-by-line repair. PR #29 dropped the 1007-line legacy file (-920) and replaced it with a focused 287-line file (+287) of 11 actually-running stress tests scoped to Phase 1.

**Prevention:** When picking up a Taskmaster task that's been pending more than a few weeks, re-read the actual code before trusting the estimate. If the gap between the task description and current state has widened, write a fresh task spec instead of executing the stale one.

---

### Lesson 7: Batched lookups for list-enrichment APIs — no N+1

**What happened:** PR #24 added `guest_name` (from Venue Session) and `oos_set_by` (from Asset Status Log → User) to every asset in the `get_asset_board_data` payload. The naïve approach is one extra SELECT per asset (×59 assets × 2 fields = 118 round trips). The implementation uses 4 batched queries instead: one for assets, one for sessions filtered by `current_session IN (...)`, one for status logs filtered by `venue_asset IN (...) AND new_status = 'Out of Service'`, one for users filtered by `name IN (...)`. Then in-Python lookup against dicts.

**Why this matters:** On a 59-asset board this is the difference between a ~60ms response and a ~600ms response. The latter is well outside the 1-second tile-render budget set in `phase1_design.md`.

**Prevention:** When enriching a list response with related-doctype fields, the structure is always: collect the join keys → one batched `frappe.get_all` per doctype with `filters={...: ["in", keys]}` → assemble dicts in Python. See `hamilton_erp/api.py::get_asset_board_data` for the canonical pattern.

---

**What happened:** PR #9 set up GitHub Actions CI for hamilton_erp. The Tests workflow failed at every step of the install path on a fresh runner: missing `apps/frappe`, wrong Python version, wrong Node version, Redis ordering wrong, missing `hypothesis`, missing seed data, missing ERPNext root records, fresh-ERPNext `desktop:home_page='setup-wizard'` row. I fixed each in turn — 12 commits — and ended up with the workflow YAML containing inline Python heredocs that created Customer Group + Territory roots, raw SQL DELETE for the `tabDefaultValue` row, and a standalone `pip install hypothesis`. Each fix advanced the workflow by one step but accumulated a parallel install path that production would never run. Frappe Cloud deploys would have hit every one of those errors freshly because none of the workarounds existed in app code.

**What to do differently:** When CI fails at install or bootstrap, the first question is *"would this also fail on a fresh production deploy?"* If the answer is yes, the bug is in the app's install path, not in the CI workflow. Fix `setup/install.py` (or the relevant patch) so the install hook handles the missing precondition itself. CI then becomes a verifier — its only setup logic is `bench init` + `install-app` + run tests + assert outcomes — and the same code that makes CI pass also makes a fresh production install succeed. The pivot in PR #9 (commit `4c5d6c2`) reverted the 5 workaround commits, moved the bootstrap into `_ensure_erpnext_prereqs()` and `_seed_hamilton_data()` in `hamilton_erp/setup/install.py:after_install()`, moved the `desktop:home_page` cleanup into `ensure_setup_complete()` (after_migrate), declared `hypothesis` as a `[project.optional-dependencies] test` extra in `pyproject.toml`, and added a conformance-assertion CI step that proves the install path produced the expected records. Net: fewer lines of code, less duplication, and the install path actually works on every fresh bench — CI or production.

The drift-prevention rule shipped earlier the same day (`Verify Before Claiming Done` in CLAUDE.md) earned a sibling: **"If a test/CI fix needs logic that lives only in the test/CI environment, ask whether production has that logic. If not, the fix belongs in the app."**


