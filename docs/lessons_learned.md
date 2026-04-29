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

## 2026-04-28 — PR #16 governance findings deferred

Three adversarial reviews on PR #16 surfaced findings deliberately not addressed in that PR. Documented here so future hardening can pick them up if they prove to be real problems:

1. Same-PR coupling attack: A PR that changes both V9_CANONICAL_MOCKUP.html and canonical_mockup_manifest.json (with matching new hash) but does NOT update decisions_log.md will pass all CI tests. Mitigation: code review (human + claude-review) should catch unexplained body changes. Hard enforcement deferred — would generate false positives on cosmetic manifest fixes.

2. Test method body integrity: test_governance_test_presence.py checks method NAMES exist, not method BODIES. A future session could replace a governance test body with `pass` while keeping the name. Mitigation: code review. Hard enforcement (test fingerprinting) deferred as overkill.

3. M2 data-dependency rule gap: CLAUDE.md says "port the mockup verbatim" but some mockup features need backend data not in production. Future sessions hitting this will need explicit guidance. Deferred to dedicated PR informed by PR 1's experience.

4. Bench worktree isolation doesn't work: Frappe bench symlinks apps/hamilton_erp to ~/hamilton_erp regardless of git worktree location. Destructive testing requires either a separate bench install or in-place backup/restore — never trust worktree isolation for bench-run probes.

5. CODEOWNERS / branch protection / change ceremony for governance files: Currently anyone with merge rights can change governance artifacts. Real regulated-industry hardening would add CODEOWNERS for docs/design/ and require dual approval. Deferred — out of scope for solo-developer phase.

These findings represent the diminishing-returns tail of three adversarial reviews. They're documented as known limitations, not active bugs.
# Lessons Learned — 2026-04-28 (Day 4)

## Context

Marathon session focused on hardening PR #16's canonical mockup governance, then pivoting to actual production fixes for the asset board. Surfaced major patterns about how Claude (chat), Claude Code, and Chris should collaborate going forward.

---

## The big lesson: stop overusing chat-Claude as middleware

**Pattern observed today:**
Chris asks Claude (chat) for a plan. Claude (chat) writes a 200-line prompt. Chris pastes into Claude Code. Claude Code executes. Claude (chat) interprets the result. Repeat 30 times.

**Cost:**
A documentation-file governance regime took 8+ hours of high-friction work because every step was mediated through chat-Claude writing prompts. Real production bugs in the asset board sat unfixed all day.

**Better pattern:**
1. Chris tells Claude Code the outcome they want, in plain English, at the highest possible level
2. Claude Code plans, executes, groups work into PRs, auto-merges on green
3. Claude Code reports at PR boundaries or when genuinely stuck
4. Chat-Claude is consulted only for interpretation of results, sanity checks on plans, or when Chris wants a second opinion

**Concrete example that worked:**
At end of day, Chris said: "Fix every divergence in your Phase 2 diff report so production matches V9. Group into PRs as you see fit. Auto-merge each when green. Only stop and ask if you're genuinely blocked."

That single sentence kicked off 5 PRs running autonomously. No micromanagement needed.

**Concrete example that didn't work:**
Three rounds of adversarial review on PR #16 (a docs-only PR) with chat-Claude writing each prompt. Each round predicted findings instead of trusting Claude Code to find them. Each round cost ~30 minutes. Net new actionable findings vs first review: maybe 30%.

---

## Patterns that compound badly

### 1. Predicting findings vs verifying findings

Chat-Claude tends to frame "what an adversarial review will probably find" as if it were already a finding. This amplifies anxiety and justifies more reviews. The first PR #16 senior dev review went well. The second adversarial review found real things. The third was hitting diminishing returns. The "expert review" was overkill.

**Rule:** Run the review. See what it actually finds. Don't ship hardening for predicted findings.

### 2. Over-disambiguation in prompts

Chat-Claude tends to write prompts that try to anticipate every edge case. This makes prompts long, brittle, and over-prescriptive. Claude Code can usually handle ambiguity if given a clear outcome.

**Rule:** When writing prompts for Claude Code, default to terse. Add detail only when a specific failure mode is likely.

### 3. Hardening governance instead of fixing production

We spent 8 hours hardening tests around a design reference file (V9_CANONICAL_MOCKUP.html — a static HTML mockup, not running production code). Meanwhile, the actual asset board operators will use at Hamilton has 60 divergences from the locked design, including 6 that will block launch.

**Rule:** When facing a choice between "harden the rules" and "fix the actual product," fix the product first. Rules can be hardened against future drift; broken UX can't be hardened away.

---

## Mockup-as-gospel pattern works

PR #16's "port the mockup verbatim, don't reinterpret" rule is the right pattern. It surfaced 60 production divergences immediately when applied honestly. Each previous Claude session had translated the spec instead of porting the mockup, and drift compounded.

**Rule going forward:** Every Phase 1+ task that touches asset board UI should start with "what does V9_CANONICAL_MOCKUP.html do for this — find it and port it." When mockup and production disagree, mockup wins.

---

## Adversarial review pattern (when to use, when not)

**Use it for:**
- Genuinely high-risk PRs (security, money, irreversible actions)
- When a PR will be the foundation of significant future work
- When previous PRs in the lineage already had bugs that adversarial review would have caught

**Don't use it for:**
- Routine PRs (most PRs)
- Documentation-only changes
- Internal tooling improvements
- Anything where the cost of fixing in follow-up exceeds the cost of finding pre-merge

**When using it, do this once, not three times:**
- Implementation
- Senior dev review
- Adversarial review (one source — Claude Code OR ChatGPT, not both for the same PR)
- Fix what's found
- Merge

The "keep hardening until reviewers stop finding things" pattern hits diminishing returns fast. Two rounds is usually enough.

---

## Bench symlink defeats worktree isolation

Tried to run destructive probes in a temporary git worktree (`/tmp/hamilton_pr16_probe`). Frappe bench symlinks `apps/hamilton_erp` to `~/hamilton_erp`, so tests run against the main repo regardless of which worktree is checked out.

**Implication:** Destructive testing requires either (a) a separate bench install, or (b) in-place backup/restore in the main repo with a strict STOP-ON-DIRTY rule.

We used in-place with backups today. It worked, but Claude Code crashes mid-probe would leave the working tree corrupted. For future destructive probing, set up a separate bench install.

---

## Branch protection is enforced

Direct push to main is rejected by GitHub branch protection (GH006 error). Every change goes through a PR with passing CI. This means:
- The "change ceremony" the adversarial review flagged as missing is partially in place
- We don't need CODEOWNERS for the solo-developer phase
- Auto-merge is safe because CI gates merging

**Caveat:** Branch protection is useful, but CI only protects what tests actually cover. Green CI means the tested contracts passed, not that the product is production-ready. Today's experience proves this — the asset board passed all CI tests for weeks while having 60 visible divergences from the locked design that no test covered.

**Rule:** Don't bother adding CODEOWNERS or required reviewers until a second engineer joins. But don't mistake green CI for "the product works." Browser verification on real test data is still required.

---

## Honesty rule applies to chat-Claude too

Chris's standing rule: "Before saying work is 'saved' or 'done,' verify by reading actual files/code. Distinguish 'spec/design committed' vs 'implementation working in running code.'"

Chat-Claude drifted from this several times today by:
- Predicting what reviews would find as if findings were verified
- Framing PR #16 hardening as "bulletproof production code" when it was governance for a docs file
- Letting Chris's gut checks ("what are we running these tests on?") deflect twice before acknowledging

**Rule for chat-Claude:** Apply the honesty rule symmetrically. Don't frame predictions as findings. Don't frame minor work as critical. When the user's gut catches something, take it seriously immediately, not after the third nudge.

---

## What actually worked today

Despite all the friction, we accomplished:

1. **PR #14:** V9 documentation reference fix (data-asset-code amendment)
2. **PR #16:** Locked V9 mockup as canonical with manifest + governance tests + sentinel markers
3. **PR #17:** Documented deferred findings (lessons_learned bridge entry)
4. **PR #18:** Closed 5 demonstrated attacks (same-PR coupling, test integrity, subdirectory bypass, manifest path redirection, manifest UX)
5. **Comprehensive V9 vs production diff:** 60 divergences identified, 6 critical, 14 significant, 40 minor
6. **5 follow-up PRs queued and running autonomously** (PR #15 overlay primitive, #19 time-state model, #20 OOS workflow, #21 vacate+tabs, #22 cosmetic polish)

The diff report alone is hours of work that nobody had done before. The governance regime is genuinely hardened against silent drift. Tomorrow we wake up with PRs already merged and the asset board significantly closer to V9.

---

## Workflow rules to add or reinforce

### Add to standing workflow

1. **High-level prompt rule:** When kicking off Claude Code work, default to one-sentence outcome statements. Add detail only when a specific failure mode is likely. Example: "Fix every V9 divergence, group into PRs, auto-merge each green, report at PR boundaries."

2. **Adversarial review budget:** Maximum two rounds per PR (senior + adversarial). After that, ship and address residual risks in follow-up PRs.

3. **Mockup-first for UI work:** Every UI task starts with `cat docs/design/V9_CANONICAL_MOCKUP.html` to load the spec into context, then porting the relevant sections verbatim.

4. **Production-vs-rules priority:** When facing a choice between hardening rules and fixing production, fix production first.

5. **Browser verification is non-negotiable for UI work:** Green CI does not equal working UI. Phase 1+ UI tasks must end with Chris clicking through the relevant flows in a real browser against the test site, against the V9 mockup as reference. "Done" only after that.

### Reinforce existing rules

- **Verify before claiming done** — applied to chat-Claude predictions too
- **Inbox.md as bridge** — used today for the lessons we're capturing now
- **Mockup as gospel** — proven by today's diff report

---

## Open items at end of day (2026-04-28)

- 5 PRs queued and running: #15 (CI in progress), #19 (committed locally), #20-22 (planned)
- Backend data enrichment deferred (E8 guest_name, E11 oos_set_by, E9 oos_days)
- Hamilton launch readiness still has multiple gaps
- Pre-Task-25 work approaching: three pre-handoff research prompts in docs/hamilton_pre_handoff_prompts.md
- Test coverage gap items 1-4 and 8-14 still pending review
- Frappe Cloud production hosting for Hamilton not yet set up

## Tomorrow's recommended start

1. Read this entry first thing
2. Check the 5 queued PRs — most or all should be merged
3. Browser-test the asset board against V9 mockup; confirm critical workflows work
4. If all 5 PRs merged cleanly: pivot to backend data enrichment (E8/E9/E11) or to Phase 1 Task 22+
5. If any PR got stuck: read the stuck report, decide scope of intervention

Do NOT start tomorrow by running adversarial reviews on yesterday's work. The governance is locked. Move forward.

---

*Captured 2026-04-28 ~17:30 by chat-Claude at Chris's request, after Chris correctly identified that chat-Claude was over-mediating and slowing down work. Edited based on second-pass review feedback that suggested softer language and a CI/coverage caveat.*

