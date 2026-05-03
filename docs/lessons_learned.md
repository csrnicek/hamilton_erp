# Lessons Learned — Hamilton ERP

Hard-won knowledge from Phase 0 and Phase 1 development. Each entry is a real bug, debugging dead-end, or production surprise so the next venue (DC, Philly, Toronto, Ottawa, Dallas) avoids repeating it.

**This is the curated lessons log.** Full session retrospectives live in `docs/retrospectives/`. Known risks not fixing now live in `docs/risk_register.md`.

---

## Top 10 Non-Negotiable Rules

These are the rules that have already cost us hours (or would cost us days) when broken. If you're a new developer or a fresh agent session, read these before changing anything.

1. **Never modify Frappe or ERPNext core.** All Hamilton logic lives in `hamilton_erp` via hooks, fixtures, custom fields, and doctype overrides. (LL-029)
2. **CI must verify the real install path, not create a parallel one.** Workflow-only seed logic creates fake-green builds. Fix the install path; let CI verify it. (LL-010, LL-011)
3. **Dev site and test site must be separate.** `bench run-tests` corrupts the dev browser site. (LL-012)
4. **UI-created configuration must be exported as fixtures or created code-first.** Custom Fields, Roles, Property Setters live only in the database otherwise. (LL-018)
5. **Run `bench migrate` after `scheduler_events` or fixture changes.** The framework caches both at migrate time. (LL-003, LL-026)
6. **Green CI does not mean the product works.** CI covers tested contracts; UI work needs a real-browser walkthrough. (LL-020)
7. **Use a separate bench install for destructive probes.** Frappe bench symlinks `apps/hamilton_erp` back to `~/hamilton_erp`; `git worktree` does not isolate it. (LL-027)
8. **Any PR more than ~30 commits behind main must be retested against current main.** Don't trust a stale "claude-review SUCCESS." (LL-016)
9. **Don't use ChatGPT as prompt middleware** when Claude Code can execute the outcome directly. Give Claude Code the outcome in one sentence, not a 200-line prompt. (LL-022)
10. **For asset board UI work, port `V9_CANONICAL_MOCKUP.html` verbatim** unless a documented decision overrides it. (LL-019)

---

## Index

| ID | Category | Severity | Lesson |
|---|---|---|---|
| LL-001 | Frappe Framework | S1 | `frappe.is_setup_complete()` reads `tabInstalled Application` |
| LL-002 | Frappe Framework | S2 | `frappe.call()` defaults to POST; `curl` defaults to GET |
| LL-003 | Frappe Framework | S2 | `scheduler_events` changes require `bench migrate` |
| LL-004 | Frappe Framework | S2 | `frappe.flags.in_test` and `frappe.in_test` are independent — clear both |
| LL-005 | Frappe Framework | S3 | `IGNORE_TEST_RECORD_DEPENDENCIES` must be a list, not `True` |
| LL-006 | Frappe Framework | S2 | `pyproject.toml` must declare `frappe-dependencies` for Frappe Cloud |
| LL-007 | Frappe Framework | S2 | Session number sequence pads to 4 digits to preserve sort order |
| LL-010 | CI / Install / Deploy | S1 | CI must own the real install path, not duplicate it |
| LL-011 | CI / Install / Deploy | S1 | Install hooks fire on different events — `after_install` vs `after_migrate` |
| LL-012 | Testing | S1 | Dev site and test site must be separate |
| LL-013 | Testing | S2 | Test threads need explicit `frappe.db.commit()` |
| LL-014 | Testing | S2 | Cross-thread MVCC visibility — main snapshot won't see thread commits |
| LL-015 | Testing | S2 | Test site name varies between local and CI — capture `frappe.local.site` |
| LL-016 | Testing | S1 | Stale PRs need tests rerun against current main, not just rebased |
| LL-017 | Testing | S2 | Schema snapshot pinning catches silent API regressions |
| LL-018 | Fixtures / Config | S1 | UI-created artifacts are invisible to Git unless exported |
| LL-019 | UI / Asset Board | S1 | Port the canonical mockup verbatim — do not interpret |
| LL-020 | UI / Asset Board | S1 | Green CI means tested contracts passed, not "the product works" |
| LL-021 | Performance | S2 | Batched lookups for list enrichment APIs — no N+1 |
| LL-022 | AI Workflow | S2 | Don't use ChatGPT as prompt middleware |
| LL-023 | AI Workflow | S2 | Adversarial review budget — two rounds, not three |
| LL-024 | AI Workflow | S2 | Taskmaster estimates can be wildly wrong when the API has shifted |
| LL-032 | AI Workflow | S3 | Batch small same-file docs additions into one PR |
| LL-025 | Operational | S3 | Redis uses non-default ports on local bench |
| LL-026 | Operational | S2 | `property_setter.json` must exist even if empty |
| LL-027 | Operational | S2 | Bench symlink defeats `git worktree` isolation |
| LL-028 | Operational | S3 | mutmut v3 incompatible with Frappe bench environment |
| LL-034 | Operational | S2 | Concurrent Claude Code agents on the same repo race on `git checkout` and nuke uncommitted work |
| LL-029 | Production Safety | S0 | Never modify Frappe / ERPNext core |
| LL-030 | Production Safety | S0 | Production recovery — rollback before live debugging |
| LL-031 | Production Safety | S0 | Agents may diagnose broadly but execute narrowly |
| LL-033 | Production Safety | S1 | Schema can lag documented intent — `permissions_matrix.md` named fields Manager-only that the JSON still exposes to Operator |
| LL-035 | Production Safety | S1 | Whitelisted endpoints touching money / stock / permissions need adversarial tests in the **first** PR — hardening passes are 5x the cost |
| LL-036 | UI / Asset Board | S2 | Paper receipt as occupancy token is a defensible-but-fragile control — digital state must remain canonical, paper is operator UX |
| LL-037 | Operational | S2 | Frappe v16 caches `site_config` for 60 seconds — `bench set-config` changes don't take immediate effect on running workers |

**Severity scale:** S0 — data corruption / financial integrity / production outage. S1 — release blocker. S2 — serious developer-time sink. S3 — annoyance / local workflow only.

---

## Read This First If You Are Working On...

- **CI / install path:** LL-001, LL-010, LL-011, LL-018
- **Tests / concurrency:** LL-004, LL-013, LL-014, LL-015, LL-016, LL-017
- **UI / Asset Board:** LL-019, LL-020, LL-021
- **Frappe Cloud deploy:** LL-001, LL-006, LL-018, LL-026, LL-029, LL-030
- **Adding a new lesson:** see "Maintenance" section at end
- **Destructive probing:** LL-027 + `docs/risk_register.md` R-004
- **A new venue rollout:** Top 10 Rules + Frappe Framework section

---

## Frappe / ERPNext Framework Lessons

### LL-001 — `frappe.is_setup_complete()` reads `tabInstalled Application`

- **Category:** Frappe Framework
- **Severity:** S1
- **Applies to:** Fresh installs, CI, Frappe Cloud deploy
- **What happened:** After a test run wiped dev state, the browser entered a ~40-req/s redirect loop between `/app` and `/app/setup-wizard`. Three separate heal attempts targeted the wrong data stores (`tabDefaultValue`, `System Settings`) and silently succeeded without fixing anything.
- **Time cost:** ~4 hours on 2026-04-11.
- **Root cause:** Frappe v16 reads `tabInstalled Application.is_setup_complete` for `frappe` and `erpnext` — not `tabDefaultValue` or `System Settings`. Both legacy stores accept writes without error but have no effect on `frappe.is_setup_complete()`.
- **The fix:** Target `tabInstalled Application` directly. Added `ensure_setup_complete` as an `after_migrate` hook so every `bench migrate` auto-heals the flag.
- **Detection:** A fresh bench install or test reset triggers a redirect loop on `/app`.
- **Prevention for next venue:** The `after_migrate` hook ships with the codebase. New venues get it automatically. Bootstrap procedure in DEC-059.
- **References:** DEC-060, commit `7c866a6`, `hamilton_erp/setup/install.py::ensure_setup_complete`.

### LL-002 — `frappe.call()` defaults to POST; `curl` defaults to GET

- **Category:** Frappe Framework
- **Severity:** S2
- **Applies to:** Any whitelisted method with a `methods=[...]` decorator
- **What happened:** Asset Board API endpoint decorated with `methods=["GET"]` returned 403 in the browser but passed every curl test and every direct Python import test. Browser was the only failing path.
- **Time cost:** ~2 hours.
- **Root cause:** `frappe.call()` sends POST by default. A `@frappe.whitelist(methods=["GET"])` endpoint will reject POST. Curl tests default to GET and pass. Direct Python imports bypass the HTTP verb gate entirely, so test_api_phase1 passed too.
- **The fix:** Pass `type: "GET"` on every `frappe.call`. Pin verb behavior in tests via `frappe.handler.execute_cmd` with a spoofed `frappe.local.request.method`.
- **Detection:** Endpoint works in curl + tests, fails in browser.
- **Prevention for next venue:** Verb-gate regression tests ship with the test suite. Every `@frappe.whitelist(methods=[...])` endpoint needs a verb-pin test.
- **References:** DEC-058, `hamilton_erp/test_api_phase1.py::TestAssetBoardHTTPVerb`.

### LL-003 — `scheduler_events` changes require `bench migrate`

- **Category:** Frappe Framework
- **Severity:** S2
- **Applies to:** Any change to `scheduler_events` in `hooks.py`
- **What happened:** Added a new scheduled job to `hooks.py` under `scheduler_events`. The job never ran.
- **Time cost:** ~30 minutes.
- **Root cause:** Frappe reads `scheduler_events` from hooks at migrate time and caches the schedule. Changing `hooks.py` without running `bench migrate` means the scheduler never picks up the new job.
- **The fix:** Always run `bench migrate` after any change to `scheduler_events` in `hooks.py`.
- **Detection:** New scheduled job doesn't run, scheduler logs don't mention it.
- **Prevention for next venue:** Document in venue rollout playbook. Add to CI checklist.
- **References:** Operational knowledge.

### LL-004 — `frappe.flags.in_test` and `frappe.in_test` are independent

- **Category:** Frappe Framework
- **Severity:** S2
- **Applies to:** Any code that toggles test mode in setUp/tearDown
- **What happened:** PRs #5/#6/#7 (E2E tests, Apr 14) defined a `real_logs()` context manager that toggled `frappe.flags.in_test` to make `_make_asset_status_log` write real audit logs during E2E tests. But the guard reads `frappe.in_test`, which is a *separate* module-level attribute. The toggle silently no-op'd: the guard still saw `True`, the audit log path was skipped, and any "exactly N log entries" assertion would fail. Surfaced 2026-04-29 when PR #26 consolidated them and re-ran their tests against current main.
- **Time cost:** ~30 minutes to find and fix.
- **Root cause:** Frappe v16 has *both* `frappe.in_test` (module-level boolean at `frappe/__init__.py:83`) and `frappe.local.flags.in_test` (request-scoped flag). Frappe's own test runner sets both via `frappe.tests.utils.toggle_test_mode(enable)`. They are NOT aliased — toggling one leaves the other unchanged.
- **The fix:** A `real_logs()` helper that toggles both attributes. Canonical version in `hamilton_erp/test_e2e_phase1.py::real_logs`; reused verbatim in `test_stress_simulation.py`.
- **Detection:** Audit log assertions silently pass against zero entries.
- **Prevention for next venue:** Grep for `frappe.flags.in_test = ` and `frappe.in_test = ` in test code; ensure any toggle pairs them. Prefer `frappe.tests.utils.toggle_test_mode()` for new code.
- **References:** PR #26, `hamilton_erp/test_e2e_phase1.py::real_logs`.

### LL-005 — `IGNORE_TEST_RECORD_DEPENDENCIES` must be a list, not `True`

- **Category:** Frappe Framework
- **Severity:** S3
- **Applies to:** Test modules that opt out of test record dependencies
- **What happened:** Setting `IGNORE_TEST_RECORD_DEPENDENCIES = True` in a test module caused `TypeError: 'bool' object is not iterable`.
- **Time cost:** ~30 minutes.
- **Root cause:** Frappe's `generators.py:115` does `to_remove += module.IGNORE_TEST_RECORD_DEPENDENCIES`, which requires list concatenation.
- **The fix:** Use `IGNORE_TEST_RECORD_DEPENDENCIES = []` (empty list), not `True`.
- **Detection:** TypeError on test collection.
- **Prevention for next venue:** Documented in `claude_memory.md` best practices rule 4. Grep for `= True` next to that constant during code review.
- **References:** Frappe quirk.

### LL-006 — `pyproject.toml` must declare `frappe-dependencies`

- **Category:** Frappe Framework
- **Severity:** S2
- **Applies to:** Frappe Cloud deploys
- **What happened:** Frappe Cloud blocked deploys because `pyproject.toml` did not declare which Frappe app version range was required.
- **Time cost:** Caught during pre-handoff research, not in production.
- **Root cause:** Frappe Cloud's deploy validator requires `frappe-dependencies` in `pyproject.toml`. Without it, the validator can't determine compatibility.
- **The fix:** Add `frappe-dependencies` to `pyproject.toml` with version constraints.
- **Detection:** Frappe Cloud deploy fails with a dependency declaration error.
- **Prevention for next venue:** Include in the venue rollout playbook. Verify in CI by deploying to a test bench.
- **References:** Pre-handoff research notes.

### LL-007 — Session number sequence pads to 4 digits

- **Category:** Frappe Framework / Naming Convention
- **Severity:** S2
- **Applies to:** Session number generation (`_next_session_number()`)
- **What happened:** The original session number format used a 3-digit zero-padded sequence (`{:03d}`). At >999 sessions per day, string sort breaks (1000 sorts before 200).
- **Time cost:** None — caught during code review before it hit production.
- **Root cause:** 3-digit padding is insufficient for high-volume venues. Hamilton's single-venue daily volume won't hit 999, but DC with 3 tablets might.
- **The fix:** 4-digit zero padding (`{:04d}`). One-line format string change.
- **Detection:** Sequence number sorted lexicographically appears wrong (1000 before 200).
- **Prevention for next venue:** Apply 4-digit padding from day one. Today's `_next_session_number` already does this.
- **References:** DEC-033, format `{d}-{m}-{y}---{NNNN}` (per `hamilton_erp/lifecycle.py:572` docstring).

---

## CI / Install / Deploy Lessons

### LL-010 — CI must own the real install path, not duplicate it

- **Category:** CI / Install / Deploy
- **Severity:** S1
- **Applies to:** GitHub Actions workflows, fresh deploys to Frappe Cloud
- **What happened:** PR #9 set up GitHub Actions CI for hamilton_erp. The Tests workflow failed at every install step on a fresh runner. Each fix added inline Python heredocs to the workflow, accumulating a parallel install path that production would never run. Frappe Cloud deploys would have hit every error freshly.
- **Time cost:** A 12-commit CI marathon, plus the rewrite.
- **Root cause:** When CI fails at install, it's tempting to add workarounds in the workflow. But workarounds in the workflow mean the app's install path is broken — production will hit the same errors.
- **The fix:** Pivoted to "install path owns its setup logic." `_ensure_erpnext_prereqs()`, `_seed_hamilton_data()`, `_ensure_no_setup_wizard_loop()` now live in `hamilton_erp/setup/install.py::after_install`. CI workflow trimmed to: bench init → install-app → conformance assertions → tests.
- **Detection:** When CI needs special seed/setup logic that production does not have, the app install path is probably broken.
- **Prevention for next venue:** Conformance step in CI runs *before* migrate to verify install-app alone produced the expected state. Same install code path runs in CI and production.
- **References:** PR #9 (commit `4c5d6c2`), `hamilton_erp/setup/install.py`, `.github/workflows/tests.yml`.

### LL-011 — Install hooks fire on different events: `after_install` vs `after_migrate`

- **Category:** CI / Install / Deploy
- **Severity:** S1
- **Applies to:** Any install-time logic
- **What happened:** `ensure_setup_complete()` was called only on `after_migrate`. But `bench install-app` doesn't fire `after_migrate` — it fires `after_install`. So fresh installs (CI, new venues) never ran the heal logic.
- **Time cost:** Surfaced during PR #9 cleanup; ~1 hour to refactor.
- **Root cause:** `after_install` and `after_migrate` are different lifecycle events. New-bench installs use the former; existing-bench updates use the latter.
- **The fix:** Refactor install-time logic into helpers called from BOTH hooks. Pre-migrate conformance step in CI proves install-app alone produces correct state.
- **Detection:** Fresh install lacks state that exists on dev machines.
- **Prevention for next venue:** Any new install-time code must handle both lifecycle events. Conformance step in CI verifies install-app alone produces expected state.
- **References:** `hamilton_erp/setup/install.py::after_install`, `.github/workflows/tests.yml::pre-migrate-conformance`.

---

## Testing Lessons

### LL-012 — Dev site and test site must be separate

- **Category:** Testing
- **Severity:** S1
- **Applies to:** Local development environment
- **What happened:** Running `bench run-tests` on `hamilton-test.localhost` (the dev browser site) corrupted it: setup_wizard loops, 403 errors, wiped roles, deleted Venue Assets. Required full `restore_dev_state()` recovery after every test run.
- **Time cost:** Cumulative ~6 hours across Tasks 13-16.
- **Root cause:** Test teardown resets DB state that the dev browser relies on. `setup_complete` flags get flipped, roles get stripped, test data cleanup deletes production-like records.
- **The fix:** Created dedicated `hamilton-unit-test.localhost` site for all test runs. Repointed all slash commands. Added top-of-file WARNING to `testing_checklist.md`.
- **Detection:** Dev site shows setup-wizard loop or missing data after a test run.
- **Prevention for next venue:** Every venue gets two sites from day one: `{venue}-dev.localhost` and `{venue}-test.localhost`. Bootstrap requirement in DEC-059.
- **References:** DEC-059, commit `0cf1fb1`.

### LL-013 — Test threads need explicit `frappe.db.commit()`

- **Category:** Testing
- **Severity:** S2
- **Applies to:** Any threaded test that mutates Frappe data
- **What happened:** Stress simulation threading tests showed `success=0` even when the lock and lifecycle calls had executed. The thread had run, but `frappe.destroy()` rolled back the uncommitted transaction.
- **Time cost:** ~30 min to diagnose during PR #29.
- **Root cause:** Frappe relies on the HTTP request boundary to auto-commit. Test threads have no request boundary. `frappe.destroy()` closes the connection with the transaction in whatever state it was, and uncommitted writes get rolled back.
- **The fix:** Each thread body runs `frappe.db.commit()` immediately after its lifecycle call, with a `frappe.db.rollback()` in the except path. CLAUDE.md bans commit in *controllers*; tests are not controllers.
- **Detection:** Threaded tests that "should have worked" show no committed changes.
- **Prevention for next venue:** Thread bodies that call Frappe controllers follow the structure `frappe.init` → `frappe.connect` → operation → `frappe.db.commit()` → `frappe.destroy()`.
- **References:** `hamilton_erp/test_stress_simulation.py::_attempt_assign`.

### LL-014 — Cross-thread MVCC visibility

- **Category:** Testing
- **Severity:** S2
- **Applies to:** Tests that assert on state written by a thread
- **What happened:** Even after the threading commit bug was fixed, the post-condition `assertEqual(asset.status, "Occupied")` failed locally. Thread had committed; main connection's read still saw "Available."
- **Time cost:** ~15 minutes.
- **Root cause:** MariaDB defaults to REPEATABLE READ. The test's main connection started its transaction (and snapshot) at setUp. The thread's later UPDATE is invisible to the main connection until it ends its own snapshot.
- **The fix:** Call `frappe.db.rollback()` on the main connection before re-reading post-thread state. That releases the snapshot; the next read sees committed reality.
- **Detection:** Thread successfully ran and committed, main connection still sees pre-thread state.
- **Prevention for next venue:** Any test that asserts on state written by a thread must rollback the main connection first or use a fresh `frappe.db.get_value`.
- **References:** `hamilton_erp/test_stress_simulation.py:147`.

### LL-015 — Test site name varies between local and CI

- **Category:** Testing
- **Severity:** S2
- **Applies to:** Threaded tests that call `frappe.init(site=...)`
- **What happened:** Local stress sim tests used `frappe.init(site="hamilton-unit-test.localhost")`. CI failed: `IncorrectSitePath: 404 Not Found: hamilton-unit-test.localhost does not exist`.
- **Time cost:** ~10 minutes (one CI cycle).
- **Root cause:** Local dev bench creates `hamilton-unit-test.localhost`. CI workflow creates `test_site`. Hardcoding either name is hostile to the other environment.
- **The fix:** In setUp, capture `self.site = frappe.local.site` and pass `self.site` into `frappe.init(site=self.site)` in the thread body.
- **Detection:** CI fails with `IncorrectSitePath` on a test that passes locally.
- **Prevention for next venue:** Grep for `frappe.init(site="` literal strings — they should not exist in tests.
- **References:** `hamilton_erp/test_stress_simulation.py:108`.

### LL-016 — Stale PRs need tests rerun against current main

- **Category:** Testing / AI Workflow
- **Severity:** S1
- **Applies to:** Any PR more than ~30 commits behind main
- **What happened:** PRs #5, #6, #7 were 95 commits behind main. They had `claude-review SUCCESS` from April 14 but predated the Server Tests CI workflow. Rebasing and merging would have looked sound — but the tests would have failed in the new CI because they depended on a test-helper bug (`real_logs()` toggling the wrong attribute, see LL-004). The bug only became visible by re-running the tests against current main.
- **Time cost:** Discovered during PR #26 consolidation.
- **Root cause:** A "successful" review on a PR snapshot in time does not survive long enough drift. Production code can change underneath the test scaffolding.
- **The fix:** Replace-not-rebase for PRs >50 commits behind main. For PRs 30-50 commits behind, run the tests locally against current main before merging.
- **Detection:** A PR sat unreviewed for weeks; no CI run on the latest main commit.
- **Prevention for next venue:** Treat any PR more than ~30 commits behind main as needing local test verification, not just CI re-run on the same branch.
- **References:** PR #26 (consolidated H10/H11/H12 E2E).

### LL-017 — Schema snapshot pinning catches silent API regressions

- **Category:** Testing
- **Severity:** S2
- **Applies to:** Read APIs that return enriched payloads
- **What happened:** PR #24 added `guest_name` and `oos_set_by` fields to `get_asset_board_data`. The existing schema snapshot test used `assertGreaterEqual` against a base set of `REQUIRED_ASSET_FIELDS` — new fields could be silently dropped from the API payload and no test would fail.
- **Time cost:** None — addressed proactively in PR #25.
- **Root cause:** Subset checks on API contracts let silent regressions through. Strict membership checks fail loudly.
- **The fix:** Pin every new field in `REQUIRED_ASSET_FIELDS` in the same PR that adds it.
- **Detection:** None automated; relies on review.
- **Prevention for next venue:** Make this a checklist item in the PR template, or enforce it via a CI step (any new field added to `get_asset_board_data` must appear in `REQUIRED_ASSET_FIELDS`).
- **References:** PR #25, `hamilton_erp/test_api_phase1.py::REQUIRED_ASSET_FIELDS`.

---

## Fixtures / Configuration Lessons

### LL-018 — UI-created artifacts are invisible to Git unless exported

- **Category:** Fixtures / Configuration
- **Severity:** S1
- **Applies to:** All venue rollouts and Frappe Cloud deploys
- **What happened:** Custom Fields, Roles, and Property Setters configured in the ERPNext UI exist only in the database. They are invisible to Git and will be lost when a new venue site is created.
- **Time cost:** Caught during pre-handoff research.
- **Root cause:** Frappe stores UI configuration in the database. The fixture export system (`bench export-fixtures`) creates JSON files that Git can track, but this must be done explicitly.
- **The fix:** Export all fixtures before handoff. Declare them in `hooks.py`. Both steps required. **Permanent rule:** every UI-created ERPNext/Frappe artifact must either be created code-first in install/patch logic, or be exported as a fixture and committed.
- **Detection:** New venue site is missing custom fields, roles, or property setters that exist on the dev site.
- **Prevention for next venue:** Add fixture export to the venue rollout playbook as a mandatory step. Run `bench export-fixtures --app hamilton_erp` after any UI configuration change.
- **References:** Task 25 checklist, `hamilton_erp/hooks.py::fixtures`.

---

## UI / Asset Board Lessons

### LL-019 — Port the canonical mockup verbatim — do not interpret

- **Category:** UI / Asset Board
- **Severity:** S1
- **Applies to:** Any asset board UI work
- **What happened:** Three previous Claude sessions had implemented asset board UI features by reading the design spec and writing what felt like the right code. Each session translated the spec into its own interpretation. Drift compounded silently for weeks until a 60-divergence diff was run against `docs/design/V9_CANONICAL_MOCKUP.html`.
- **Time cost:** Weeks of accumulated drift, ~6 hours of cleanup spread across PRs #15, #19, #20, #21, #22.
- **Root cause:** "Implement the design spec" is an interpretation task. Two LLM sessions on the same spec produce different code. The right pattern is byte-for-byte porting of the canonical mockup file, only changing selectors that differ between mockup and production conventions.
- **The fix:** Lock V9_CANONICAL_MOCKUP.html as the canonical reference (PR #16 governance regime). Every UI task starts with reading the relevant section of the mockup, then bringing production into alignment by copy-paste.
- **Detection:** Run a diff against the mockup periodically; any drift is a bug.
- **Prevention for next venue:** When a venue's UI is "done," its canonical mockup file should be locked the same way. Production drift is a bug, not creative liberty.
- **References:** PR #16 (governance regime), `CLAUDE.md` "V9 Canonical Mockup — Gospel Reference" section.

### LL-020 — Green CI means tested contracts passed, not "the product works"

- **Category:** UI / Asset Board
- **Severity:** S1
- **Applies to:** All UI / POS / customer-facing work
- **What happened:** The asset board passed every CI test for weeks while having 60 visible divergences from the locked V9 design. Phase 1 conformance tests covered API contracts, lifecycle transitions, and locking — but no test covered "does the tile render with the right colors and copy in the browser."
- **Time cost:** Weeks of unnoticed drift; the divergence audit and 5-PR fix series ran 2026-04-28.
- **Root cause:** Server-side tests cover server-side contracts. UI work needs UI verification — either browser automation tests (expensive and brittle) or a human clicking through the canonical flows in a real browser against the canonical mockup as reference.
- **The fix:** UI tasks end with a browser walkthrough against the V9 mockup. "Done" only after that, even if CI is green.
- **Detection:** UI works in tests, looks wrong in browser.
- **Prevention for next venue:** Add a UI verification step to the venue rollout playbook. Browser verification on real test data is non-negotiable for UI work.
- **References:** PRs #15/#19/#20/#21/#22 V9 conformance series.

---

## Performance Lessons

### LL-021 — Batched lookups for list-enrichment APIs — no N+1

- **Category:** Performance
- **Severity:** S2
- **Applies to:** Any read API that enriches a list with related-doctype fields
- **What happened:** PR #24 added `guest_name` (from Venue Session) and `oos_set_by` (from Asset Status Log → User) to every asset in the `get_asset_board_data` payload. The naïve approach is one extra SELECT per asset (~118 round trips for 59 assets × 2 fields). The implementation uses 4 batched queries instead.
- **Time cost:** None — addressed correctly the first time during PR #24.
- **Root cause:** Per-row enrichment in a loop is the classic N+1 antipattern.
- **The fix:** Collect join keys → one batched `frappe.get_all` per related doctype with `filters={key_field: ["in", keys]}` → assemble dicts in Python.
- **Detection:** Profile the API; tile-render budget is 1 second per `phase1_design.md`.
- **Prevention for next venue:** When enriching a list response with related-doctype fields, the structure is always: collect keys → batched `get_all` → in-Python assembly. Canonical pattern in `hamilton_erp/api.py::get_asset_board_data`.
- **References:** PR #24, `hamilton_erp/api.py::get_asset_board_data`.

---

## AI / Claude Code Workflow Lessons

### LL-022 — Don't use ChatGPT as prompt middleware

- **Category:** AI Workflow
- **Severity:** S2
- **Applies to:** All Claude Code sessions
- **What happened:** Pattern observed Day 4: Chris asks ChatGPT for a plan → ChatGPT writes a 200-line prompt → Chris pastes into Claude Code → Claude Code executes → ChatGPT interprets the result → repeat. A documentation-file governance regime took 8+ hours of high-friction work because every step was mediated through chat-Claude writing prompts. Real production bugs in the asset board sat unfixed all day.
- **Time cost:** ~8 hours on Day 4 alone.
- **Root cause:** Treating ChatGPT as the planner and Claude Code as the executor adds a translation layer that loses signal in both directions. Claude Code can plan its own work given a clear outcome.
- **The fix:** Give Claude Code the outcome directly, in plain English, at the highest level. Use ChatGPT for second opinions, sanity checks, and interpretation — not for writing prompts.
- **Detection:** Sessions where you copy-paste prompts back and forth between ChatGPT and Claude Code more than twice.
- **Prevention for next venue:** Default to one-sentence outcome statements: *"Fix every V9 divergence, group into PRs, auto-merge each green, report at PR boundaries."*
- **References:** `docs/retrospectives/2026-04-28.md` "The big lesson" section.

### LL-023 — Adversarial review budget — two rounds, not three

- **Category:** AI Workflow
- **Severity:** S2
- **Applies to:** Any high-risk PR
- **What happened:** PR #16 (a docs-only governance regime for a static HTML mockup file) went through three rounds of adversarial review. Round 1 (senior dev) found real things. Round 2 (adversarial probes) found a few more real things. Round 3 ("expert review") was hitting diminishing returns — most findings were predicted attacks, not demonstrated bugs.
- **Time cost:** ~3 hours per extra round, plus opportunity cost.
- **Root cause:** "Keep hardening until reviewers stop finding things" treats every potential finding as equally severe. In practice, round 1 catches cheap wins, round 2 catches subtle wins, round 3 produces predictions of what reviews *might* find.
- **The fix:** Cap adversarial review at two rounds per PR. After that, ship and address residual risks in follow-up PRs.
- **Detection:** Round-3 findings are dominated by "an attacker could potentially..." instead of "here is a demonstrated bug."
- **Prevention for next venue:** Workflow rule. Use adversarial review for genuinely high-risk PRs (security, money, irreversible actions); skip for routine PRs and documentation changes.
- **References:** `docs/retrospectives/2026-04-28.md` "Adversarial review pattern" section.

### LL-024 — Taskmaster estimates can be wildly wrong when the API has shifted

- **Category:** AI Workflow
- **Severity:** S2
- **Applies to:** Any Taskmaster task pending more than a few weeks
- **What happened:** Taskmaster Task 26 said "Estimated 15 minutes" for "Replace `from hamilton_erp.lifecycle import assign_asset` references". Reality: 42 tests in `test_stress_simulation.py` were already `@unittest.skip`'d for weeks, the old `assign_asset` had a different signature than the new `start_session_for_asset`, the old `vacate_asset` is now `vacate_session` with a new required parameter, the `acquire_lock` and `release_lock` functions don't exist (only the context manager), and the `assignment_status` field was renamed to `status`. A 15-minute import rewrite is actually a 2-3 hour structural rewrite.
- **Time cost:** Found during PR #29.
- **Root cause:** The estimate was written when the imports were the only thing wrong. As the rest of the codebase refactored, the gap widened, but the estimate did not get re-evaluated.
- **The fix:** Delete + replace, not line-by-line repair. PR #29 dropped the 1007-line legacy file and replaced it with a focused 287-line file of 11 actually-running stress tests scoped to Phase 1.
- **Detection:** The task description and the current code disagree on function names, signatures, or doctype fields.
- **Prevention for next venue:** When picking up a Taskmaster task that's been pending more than a few weeks, re-read the actual code before trusting the estimate. If the gap has widened, write a fresh task spec.
- **References:** PR #29.

### LL-032 — Batch small same-file docs additions into one PR

- **Category:** AI Workflow
- **Severity:** S3
- **Applies to:** Sequential session work that piles up additions to `docs/inbox.md`, `docs/lessons_learned.md`, or other shared docs files
- **What happened:** During the 2026-04-29 session, four sequential prompts each asked for "append findings to docs/inbox.md, one PR, auto-merge on green" — visual regression research, AI bloat audit, test suite redundancy audit, and the docs-batching lesson itself. Each prompt was treated as one PR. Four PRs against the same file is four CI runs (~20 min Server Tests each) of branch-protection serialization for what could have been one squash commit and one CI run.
- **Time cost:** ~60 minutes of CI wall time per extra PR cycle. The work itself is the same; the PR overhead is pure waste.
- **Root cause:** Defaulting to "one prompt → one PR" when prompts are atomic from the user's perspective. The user gave four atomic prompts; each was treated as atomic on the PR side too. But the file only updates one way — appending — and the destinations were the same file, so they could have been bundled.
- **The fix:** When sequential additions target the same shared docs file, default to one PR with sections separated by `---` and a single squash commit message that lists each section. Ask once if unsure.
- **Detection:** Two or more queued PRs both target the same docs file (e.g. both modify `docs/inbox.md`); each is small (<100 lines added); each would auto-merge.
- **Prevention for next venue:** Extend session-start checklist: "If multiple small docs PRs are queued for the same file, batch them." A single PR with three subsections is faster, easier to review, and produces a cleaner history.
- **References:** This session, 2026-04-29 — PR #33 (visual regression research) shipped as its own PR before user said "combine the queued audits into one PR."

---

## Operational Lessons

### LL-025 — Redis uses non-default ports on local bench

- **Category:** Operational
- **Severity:** S3
- **Applies to:** Local development
- **What happened:** Redis commands targeting port 6379 (the default) silently connected to nothing or to a different Redis instance. Lock operations appeared to succeed but had no effect.
- **Time cost:** ~1 hour.
- **Root cause:** Local Frappe bench uses cache on port 13000 and queue on port 11000, configured in `common_site_config.json`.
- **The fix:** Always check `common_site_config.json` for actual Redis ports. Start them explicitly: `redis-server --port 13000 --daemonize yes && redis-server --port 11000 --daemonize yes`.
- **Detection:** Redis commands "succeed" but don't visibly change state.
- **Prevention for next venue:** `/debug-env` slash command verifies Redis ports.
- **References:** `.claude/commands/debug-env.md`.

### LL-026 — `property_setter.json` must exist even if empty

- **Category:** Operational / Fixtures
- **Severity:** S2
- **Applies to:** Frappe fixture management
- **What happened:** Frappe fixture export creates `property_setter.json`. If the file is missing, `bench migrate` on a new site silently skips Property Setter fixtures — no error, no warning, just silent data loss.
- **Time cost:** Caught during pre-handoff research.
- **Root cause:** Frappe's fixture loader checks for file existence. A missing fixture file is treated as "no fixtures to load" rather than an error.
- **The fix:** Always include `property_setter.json` in the app's fixtures directory, even if it contains just `[]`. Run `bench export-fixtures` regularly.
- **Detection:** New venue site is missing property setters.
- **Prevention for next venue:** Include in the venue rollout playbook. The fixture export step is now mandatory.
- **References:** Task 25 checklist.

### LL-027 — Bench symlink defeats `git worktree` isolation

- **Category:** Operational
- **Severity:** S2
- **Applies to:** Destructive testing / probing
- **What happened:** Tried to run destructive probes in a temporary git worktree (`/tmp/hamilton_pr16_probe`) to keep the main checkout untouched. Frappe bench symlinks `apps/hamilton_erp` back to `~/hamilton_erp` regardless of which worktree is active, so `bench run-tests` operated against the main working tree the whole time. A Claude Code crash mid-probe would have left the working tree corrupted.
- **Time cost:** ~1 hour of confused debugging plus the cleanup.
- **Root cause:** `bench install-app` records the absolute path of the app at install time as a symlink under `apps/`. Switching the project's git worktree later doesn't update the symlink target.
- **The fix:** Use in-place backup/restore in the main repo with a STOP-ON-DIRTY rule. For frequent destructive probing, set up a separate bench install with its own clone.
- **Detection:** `ls -l ~/frappe-bench-hamilton/apps/hamilton_erp` shows the symlink points to the main repo even from inside a worktree.
- **Prevention for next venue:** Any session about to run a destructive probe must verify which path `bench` actually targets before running anything, and must back up the affected files first. See `docs/risk_register.md` R-004.
- **References:** Discovered during PR #16 probing on 2026-04-28.

### LL-028 — mutmut v3 incompatible with Frappe bench environment

- **Category:** Operational
- **Severity:** S3
- **Applies to:** Mutation testing on Frappe codebases
- **What happened:** mutmut v3 copies source to a `mutants/` directory and runs pytest from there. Frappe's test infrastructure requires `bench run-tests` which initializes the full bench context (DB connection, Redis, module registry). The copied `mutants/` directory has no bench context, so all tests fail with "Module Hamilton ERP not found."
- **Time cost:** ~45 minutes trying both v2 and v3 before building a custom solution.
- **Root cause:** mutmut v3 rewrote its architecture to use file copying instead of in-place mutation. mutmut v2 mutates in-place but crashes on Python 3.14 with a serialization error in the `copy` module.
- **The fix:** Custom mutation runner that mutates in-place against the actual app path and runs `bench run-tests`. See `.claude/commands/mutmut.md`.
- **Detection:** mutmut v3 invocations fail with "Module Hamilton ERP not found."
- **Prevention for next venue:** Use the custom runner. Don't try to install mutmut v3 against a Frappe bench.
- **References:** `.claude/commands/mutmut.md`.

---

## Production Safety Lessons

### LL-029 — Never modify Frappe / ERPNext core

- **Category:** Production Safety
- **Severity:** S0
- **Applies to:** All code changes
- **Rule:** All custom business logic must live in `hamilton_erp`. Do not edit `frappe/` or `erpnext/` core files.
- **Why this is S0:** Core modifications break upgrades. A future `bench update --upgrade` would either overwrite the change (silent feature loss) or fail to merge (deploy blocker). Either way, recovery is expensive — the next venue rollout would be on top of a fork rather than a clean Frappe/ERPNext install.
- **Correct extension points:**
  - `hooks.py` (lifecycle, doc events, scheduler events, fixtures)
  - `extend_doctype_class` (override controllers without forking the doctype)
  - Custom Fields (added via fixtures, not by editing core JSON)
  - Custom DocTypes (live in `hamilton_erp/hamilton_erp/doctype/`)
  - Patches (one-time data migrations in `hamilton_erp/patches/`)
- **What happened so far:** No core modifications have shipped. This rule is documented preemptively because the cost of breaking it is high and the cost of following it is zero.
- **Detection:** Any diff that touches `apps/frappe/` or `apps/erpnext/` files.
- **Prevention for next venue:** Branch protection check that blocks changes under core paths. Add CODEOWNERS entry that flags any core diff for explicit human override.
- **References:** Frappe upgrade documentation; review recommendation 2026-04-29.

### LL-030 — Production recovery — rollback before live debugging

- **Category:** Production Safety
- **Severity:** S0
- **Applies to:** Live production incidents on `hamilton-erp.v.frappe.cloud`
- **Rule:** At 2am, if a recent deploy caused broad breakage, rollback first. Debug later in staging. Frappe Cloud's snapshot + revert mechanism is the rollback path.
- **Why this is S0:** Live debugging on production at 2am, by a tired single operator, with venue customers waiting at the front desk, is the highest-risk debugging environment. One miskeyed SQL UPDATE corrupts data permanently. A rollback to a known-good snapshot is reversible.
- **Forbidden:**
  - Live-editing business logic in production.
  - Manually repairing invoices/payments without review.
  - Direct SQL UPDATE/DELETE on production data without a backup snapshot taken first.
- **What happened so far:** No production incidents yet (Hamilton hasn't gone live). Rule documented preemptively.
- **Detection:** Operator opens a `bench --site hamilton-erp.v.frappe.cloud console` during a live incident.
- **Prevention for next venue:** Document the rollback procedure in the venue rollout playbook + Hamilton Launch Playbook. Practice it on staging before go-live.
- **References:** `docs/HAMILTON_LAUNCH_PLAYBOOK.md`.

### LL-031 — Agents may diagnose broadly but execute narrowly

- **Category:** Production Safety
- **Severity:** S0
- **Applies to:** Future Night Watch agents, autonomous Claude Code sessions, any agent with production access
- **Rule:** Agents can read logs, summarize, and recommend. Agents can only execute pre-approved safe actions.
- **Why this is S0:** An agent with broad write access to production can cause data corruption faster than a human can intervene. The asymmetry between "diagnose" (read) and "execute" (write) is the safety boundary.
- **Safe actions (auto-execute permitted):**
  - Restart workers
  - Restart scheduler
  - Retry failed non-financial jobs
  - Disable feature flag
  - Rollback last deploy
- **Forbidden actions (always require human approval):**
  - Modify Sales Invoices
  - Modify Payments
  - Change customer identity
  - Change asset last-renter history
  - Delete audit logs
  - Direct SQL UPDATE/DELETE
- **What happened so far:** No autonomous agents in production yet. Rule documented preemptively for the Night Watch system.
- **Detection:** Agent action log contains any "Forbidden" item without an explicit human approval token.
- **Prevention for next venue:** Per-action allowlist in agent harness. Forbidden actions require an explicit approval flow.
- **References:** Future Night Watch system design.

### LL-033 — Schema can lag documented intent — audit field configs against design docs, not just role grids

- **Category:** Production Safety
- **Severity:** S1
- **Applies to:** Any DocType where field-level sensitivity is asserted in design docs, decisions, or permission matrices but enforced only at the row level in JSON.
- **What happened:** Task 25 item 7 audit (autonomous, 2026-04-30) compared every Hamilton DocType field against documented sensitivity intent. Three classes of gap surfaced: (a) the `permissions_matrix.md` "Sensitive fields" section already named `Comp Admission Log.comp_value` as Manager-only, but the DocType JSON grants Hamilton Operator full read on it; (b) `Shift Record.system_expected_card_total` is the same blind-count theft-detection figure as `Cash Reconciliation.system_expected` (DEC-021) but is fully readable by Operator pre-submit, defeating DEC-038's blind-count workflow at the API layer; (c) Venue Session ships eight forward-compat PII fields (`full_name`, `date_of_birth`, `scanner_data`, etc.) for Philadelphia rollout — null at Hamilton today, but freely readable by Operator the moment Philadelphia populates them.
- **Time cost:** ~30 min for the audit pass. Time cost of the unmitigated gaps would be measured in incident hours if exploited.
- **Root cause:** Frappe's role-permission grid is row-level. Granting `read: 1` on a DocType grants read on every field on it. Field-level enforcement (`permlevel`, `mask`, `is_password`) is an opt-in second layer. The Phase 1 build leaned on JS form hides and convention to enforce field-level rules that should have been declared in JSON. JS hides bypass at the API; convention does not survive contributors.
- **The fix:** Two parts. (1) The audit itself, captured in `docs/field_masking_audit.md` — every field, sensitivity tier, current role read access, recommendation, and a prioritized implementation queue. (2) No field configs were changed in this pass; remediation is sequenced as follow-up PRs starting with the smallest-blast-radius gaps (one-field `permlevel: 1` edits with regression tests).
- **Detection:** Whenever `permissions_matrix.md`, `decisions_log.md`, or any design doc names a field as "Manager-only" or "blind reveal" or "sensitive," the DocType JSON should be checked the same day. Add this check to the coding-standards review (alongside the existing role-grid check).
- **Prevention for next venue:** Two structural changes recommended. (a) Before any Philadelphia rollout that populates the Venue Session PII fields, the `permlevel: 1` block on those fields must land — Philadelphia cannot be the first venue to discover the gap in production. (b) For new DocTypes, add a field-sensitivity column to the schema review checklist. Three questions per field: "Could a peer-Operator browsing this leak a theft signal?" "Is this PII?" "Is this a blind-reveal figure?" Any 'yes' triggers a `permlevel`/`mask`/`is_password` decision before the JSON is committed.
- **Generalizes:** Documented intent is not enforcement. Whenever a design doc, decision log, or matrix names a field-level rule, treat it as a TODO that must be matched in JSON, not as a fact about the system. The schema is the authority; the doc is the spec the schema must satisfy.
- **References:** `docs/field_masking_audit.md`, `docs/permissions_matrix.md` lines 53–60, DEC-021, DEC-038, DEC-039, DEC-050, `hamilton_erp/test_security_audit.py::TestNoFrontDeskSelfEscalation`.

### LL-034 — Concurrent Claude Code agents on the same repo race on `git checkout` and nuke uncommitted work

- **Category:** Operational
- **Severity:** S2
- **Applies to:** Any session where more than one Claude Code agent (interactive sessions, Ralph-loop, scheduled `/loop`, autonomous agents) is operating on the same checkout. The single physical worktree at `/Users/chrissrnicek/hamilton_erp` is shared by every bench-installed app (see LL-027), so this hits any multi-agent setup without explicit coordination.
- **What happened:** During the field-masking-audit gap-#1 ship (2026-04-30), an interactive session made three working-tree edits (`shift_record.json`, `test_security_audit.py`, `risk_register.md`), staged them, ran tests green, and was about to commit. Between the test run and the commit, another agent on the same worktree did `git checkout` to a different feature branch — silently discarding the staged-but-uncommitted changes. The reflog showed `feat/v91-retail-cart-ux-stub → feat/v91-cart-sales-invoice → main → feat/security-shift-record-card-permlevel → feat/v91-cart-sales-invoice` happening in rapid succession across what looked like a single session's tool calls. The session had to redo all three edits on the dedicated branch and commit-push immediately to lock them in.
- **Time cost:** ~15 minutes of redo work plus the diagnostic time to figure out *why* the working tree kept going clean. First-pass hypothesis ("the harness is auto-resetting me") was wrong; the actual cause was a separate concurrent agent. The reflog made it obvious in retrospect.
- **Root cause:** Git stages + working tree are checkout-scoped, not session-scoped. Two agents that both call `git checkout` on the same `.git` race each other: whichever runs second discards the first's uncommitted work without warning. There is no per-session lock around the working tree, and `bench`'s symlink (LL-027) means multiple bench installs that share an app folder share the same git state.
- **The fix:** Two patterns, pick one:
  1. **One agent per worktree.** If a second concurrent run is needed, give it a separate `git worktree add` (and accept that LL-027 means it can't run `bench run-tests` against the second worktree's checkout — the second agent has to stay code-only). For interactive + scheduled-loop combinations, this is the cleanest split.
  2. **Commit-push-immediately pattern.** When two agents share the worktree, never leave changes uncommitted across tool calls. Edit → test → stage → commit → push as one tight sequence; treat anything in the working tree as ephemeral. Don't run long-form analysis between an edit and its commit. This is the workaround that shipped gap #1 once the race was identified.
- **Detection:** `git reflog` after a "wait, my changes are gone" moment shows back-to-back `checkout: moving from X to Y` entries the current session never issued. If those checkouts came from another agent, this lesson applies.
- **Prevention for next venue:** Document the active-agent expectation per-repo in `CLAUDE.md` ("only one Claude Code session may have uncommitted changes at a time") and have scheduled loops do their work in a separate worktree. For multi-venue rollout where Night Watch agents (LL-031) might run alongside interactive work, the agent harness must hold a worktree-scoped lock or operate on its own checkout.
- **References:** This session's reflog, 2026-04-30. Related: LL-027 (bench symlink defeats `git worktree`), R-004 in `docs/risk_register.md`. Discovered while shipping field-masking gap #1 (`feat/security-shift-record-card-permlevel`, commit `a2c9803`).

### LL-035 — Whitelisted endpoints touching money / stock / permissions need adversarial tests in the *first* PR

- **Category:** Production Safety
- **Severity:** S1
- **Applies to:** Any new `@frappe.whitelist()` endpoint that creates / submits Sales Invoice, Purchase Invoice, Stock Entry, Payment Entry, or any DocType that mutates inventory, GL entries, or role/permission state. The threshold is "could a malicious or compromised client cause real-world harm by calling this with crafted arguments?" — if yes, this lesson applies.
- **What happened:** PR #51 (V9.1 Phase 2 cart → POS Sales Invoice, 2026-04-30) shipped the initial implementation of `submit_retail_sale` with happy-path tests only — Sales Invoice creation, HST math, stock decrement, return values, validation rejections for empty cart and insufficient cash. Source-of-truth review one day later surfaced **five issues** that the happy-path tests had silently allowed:
  1. Permission gate used `frappe.has_permission("Sales Invoice", "create")` which Hamilton Operator does not have — tests passed only because they ran as Administrator. Real operators would have hit a permission error on every cart Confirm.
  2. Server trusted client-supplied `unit_price` as the Sales Invoice rate — a compromised browser could submit lower prices and the server would persist them.
  3. No pre-submit stock check — concurrent sales of the last unit produced raw ERPNext stack-trace exceptions instead of clean operator errors.
  4. `has_permission` gate paired with `ignore_permissions=True` was contradictory — neither effective authorization nor clean delegation.
  5. Documented design contract (V9.1-D14 "Out of scope") contradicted the shipped implementation.
- **Time cost:** Hardening pass took ~3 hours (10 new adversarial tests, 1 fix to existing tests, full-suite re-run, audit-trail-preserving Administrator elevation pattern, helper extraction for the rounding gate). The original happy-path tests took ~30 minutes. **Fixing after the fact was ~5x the cost** of writing the adversarial tests upfront — and that's before counting the source-of-truth review that surfaced the issues, the doc updates, and the cumulative branch churn.
- **Root cause:** Two compounding pressures favor happy-path-only tests in a first PR. (a) Happy-path tests are easier to write because they don't require thinking adversarially — the developer designed the function and tests it the way they imagined operators would call it. (b) The first PR feels like "implementation"; adversarial tests feel like "polish" that can come later. Both are wrong for money/stock/permission endpoints because the adversarial cases ARE the design contract — what happens when client lies, what happens when stock is short, what happens when role is wrong.
- **The fix:** For any new whitelisted endpoint that touches money, stock, or permissions, the **initial** PR must include tests for these adversarial categories before requesting review:
  - **Auth gate:** at least one test per role that should be allowed AND at least one per role that should be rejected. Run as a non-Administrator user. If the function is meant to be operator-callable, test with a real operator-role user. If it's manager-only, test the rejection-when-operator path.
  - **Server-side authority for any client-supplied numeric:** test that a tampered value is rejected (price, qty, discount, tax rate, anything that affects money). The server's authoritative source must be the one written to disk; the client value is informational at best.
  - **Resource-availability pre-checks:** test that the function fails cleanly (operator-friendly message) when the resource isn't available — out-of-stock, account missing, customer missing, profile missing. Raw ERPNext stack traces in operator UIs are operationally hostile.
  - **Permission-elevation contract:** if the function uses `ignore_permissions=True`, the role gate and the elevation must be a documented delegation pattern, not a contradiction. The test for the role gate must use a real non-Administrator user; the test for the delegation must verify audit trail (Sales Invoice `owner` reflects the actual operator, not the elevated session).
  - **Doc-contract alignment:** if the implementation contradicts a "deferred to round 2" / "out of scope" line in a design doc, the test fails. Use a regression test that reads the design doc and the code and asserts the contract holds — same pattern as `test_canonical_mockup_governance.py` for the V10 mockup.
- **Prevention for next venue:** Bake the checklist into the PR template for any commit that touches `hamilton_erp/api.py`, `hamilton_erp/lifecycle.py`, or any controller that overrides `validate` / `on_submit`. The reviewer should fail any new whitelisted money/stock/perm endpoint that doesn't include all five categories in the initial PR. The lesson here is that hardening-after-the-fact is not just "more work" — it's **PR churn, doc-revision churn, and cumulative review fatigue** that compounds across a multi-PR session.
- **Detection:** When reviewing any PR that adds an `@frappe.whitelist()` decorator, scan the test additions in the same diff. If the test class only contains happy-path tests (returns success / asserts on the created doc) and no rejection-path tests for tampered input or missing role, flag it.
- **Generalizes:** This applies to ANY codebase with money / stock / perm-touching endpoints, not just Frappe. The 5x ratio holds because adversarial tests are easier to write WHILE the implementation is fresh (the developer remembers what they trusted and what they validated); they're much harder to retrofit because retrofitting requires re-reasoning about the function's contract from scratch.
- **References:** PR #51 (`feat/v91-cart-sales-invoice`), commits `95cccc3` (initial happy-path) → `afd875e` (hardening pass with 10 new adversarial tests). Related: LL-016 (stale PRs need re-test against main), LL-029 (never modify Frappe core), DEC-005 + DEC-021 (blind cash invariants — exactly the kind of contract that adversarial tests are designed to enforce). Source-of-truth review notes in this session's transcript, 2026-04-30.

### LL-036 — Paper receipt as occupancy token: defensible-but-fragile control; digital state stays canonical

- **Category:** UI / Asset Board
- **Severity:** S2
- **Applies to:** Hamilton's Phase 2 hardware backlog (Epson TM-T20III receipt printing) and any future operator UX where a physical artifact is meant to mirror digital state. Especially relevant for the "paper receipt on key hook = occupied" control pattern.
- **What happened (research, not incident):** PR #51 deeper audit (2026-04-30) compared three receipt-as-control patterns used in the industry: (a) **wristband + RFID** — single token holds locker access AND running charges (SoJo Spa, King Spa); (b) **locker-number-as-folio** — all charges accumulate to the locker number, single consolidated receipt at exit (BRC Day Spa); (c) **paper-receipt-as-control-token** — every transaction prints, customer copy + key-hook copy. Hamilton's Phase 2 backlog assumes pattern (c). The pattern works, but the audit surfaced a sharp edge: a single mis-discarded hook receipt creates a phantom-vacant room in the physical view while the digital state still shows occupied. Operators who treat the paper as canonical will flip the digital state to match the (incorrect) paper, propagating the discrepancy.
- **Time cost:** Research only — no incident, but the pattern is a known trap in retail/hospitality audits. The hotel-industry "night audit" exists precisely because physical state and PMS state drift.
- **Root cause:** The mental model that "the paper IS the truth" is intuitive for operators but operationally wrong. The Sales Invoice is the audit record; the GL entry posts on submit; the printed paper is a projection of that record at one moment. Treating the projection as authoritative inverts the data flow.
- **The fix (when Phase 2 hardware ships):** Document the canonicality rule in operator training and in the receipt printer integration code:
  1. The Sales Invoice (`name` field, e.g. `ACC-SINV-2026-00012`) is canonical. The printed receipt is a copy.
  2. Discrepancy resolution always favors the digital state — operator who finds an empty room with a hook receipt looks up the SI by the printed `name`, not the other way around.
  3. The receipt itself MUST print the SI `name` prominently (top of receipt, not just at the bottom in small print) so any audit / dispute / chargeback investigation can pull the canonical record by reference.
  4. A "no-sale" event (drawer opened without a transaction) is a separate audit-trail concern that ERPNext doesn't natively track. If Hamilton's drawer-open events become an audit need, it's a custom DocType + integration with the cash drawer hardware — Phase 3+ scope.
- **Detection:** During Phase 2 browser-test of the receipt printer integration: deliberately tear up a hook receipt mid-shift, confirm the operator UI flow recovers (look up SI by guest/locker, NOT by re-creating a receipt). If the recovery flow requires re-printing or a new SI, the canonicality is wrong.
- **Prevention for next venue:** The next venue (DC, Toronto, Philly) should evaluate switching to wristband+RFID (pattern a) which removes this trap entirely — the wristband IS the digital state's projection, and lost wristbands are a recoverable event. Hamilton retrofitting to wristband would be capital expense; new venues with greenfield hardware spec should consider it.
- **Generalizes:** Any physical artifact that mirrors digital state (printed labels, hook receipts, paper-tag inventory, even hand-written sticky notes on workstations) creates a drift surface. The artifact is operator UX, not data. Whenever a process design depends on "the paper says X," there's a hidden assumption that the paper hasn't been mishandled — and at scale, paper always gets mishandled. Architecture must make digital state recoverable from the artifact, not the other way around.
- **References:** PR #51 deeper audit Topic 1 (2026-04-30), Hotel night-audit pattern (RoomMaster, Prostay), SAM4POS dual-station printer / electronic journal pattern. Related: docs/inbox.md 2026-04-30 Phase 2 hardware backlog (Epson TM-T20III spec).

### LL-037 — Frappe v16 caches `site_config` for 60 seconds — `bench set-config` is not immediate

- **Category:** Operational
- **Severity:** S2
- **Applies to:** Any operational change that uses `bench set-config <key> <value>` against a running production site, especially Hamilton's per-venue config keys: `hamilton_company`, `hamilton_walkin_customer`, `retail_tabs`, future `hamilton_descriptor_used`, future merchant config in `hamilton_merchants`. Also relevant when toggling Hamilton's existing flags during incident response.
- **What happened (research, not incident):** v16 production-readiness survey (2026-04-30) surfaced this from the v15→v16 migration wiki: "Site config and common site configs are cached for up to one minute" — a deliberate v16 perf optimization that means `set-config` writes propagate to running workers on a 60-second clock, not instantly. In v15 the cache was effectively per-request; v16 made it minute-scale to reduce DB chatter on a hot path.
- **Time cost:** Research only — no incident. But the trap is obvious: an operator runs `bench set-config hamilton_walkin_customer "Anonymous"` to fix a misconfiguration during a Saturday-night incident, retries the failing request immediately, gets the same failure, and concludes the config change didn't work — when actually it did, but won't be visible for up to 60 seconds.
- **Root cause:** v16's deliberate caching trade-off. `frappe.conf.get(key)` reads from a process-local cache that refreshes on a TTL, not from the file system on every call. Workers hold their cache independently; restarting one worker doesn't clear another's.
- **The fix:** Two patterns, depending on urgency:
  1. **Wait 60 seconds.** For routine config changes (planned tier upgrades, post-deploy verification), simply waiting is fine. Set the runbook expectation: "after `bench set-config`, allow up to 60 seconds for changes to take effect."
  2. **Restart workers explicitly.** For incident-response config changes where the 60-second wait is too long, run `bench restart` (or `supervisorctl restart all` on Frappe Cloud private benches) immediately after `set-config`. This forces every worker to drop its cache and re-read from disk on the next request.
- **Detection:** Symptom is "I changed the config but the behavior didn't change." If the behavior is still wrong after a `bench restart`, then the config change actually didn't apply or there's a different bug. If the behavior changes after a `bench restart` but not before, this lesson explains why.
- **Prevention for next venue:** Document the 60-second TTL in `docs/venue_rollout_playbook.md` so each new venue's runbook includes the wait-or-restart guidance. Also: any Hamilton tooling that reads `frappe.conf.get` in a hot path (the cart's `submit_retail_sale` reads `hamilton_walkin_customer` per-call) should be aware that the value is cache-fresh-as-of-last-60s, not real-time. For most use cases this is fine; for security-critical flags (where stale-by-60s could be a problem), restart-after-change is the discipline.
- **Generalizes:** Every cache has a TTL. v15's "every request reads disk" model was wasteful but had instant feedback; v16's "minute-scale cache" model is performant but feedback-delayed. Whenever an operational tool changes behavior between major versions, the operator runbook needs the delta documented — otherwise muscle-memory from the old version bites in the new one.
- **References:** v15→v16 migration wiki (`https://github.com/frappe/frappe/wiki/Migrating-to-version-16`), 2026-04-30 v16 production-readiness research session. Related: LL-026 (`property_setter.json` caching), LL-029 (never modify Frappe core — including its caching behavior).

---

## Maintenance

**Where new content goes:**

- **Raw session notes** → `docs/inbox.md` immediately. The inbox is the bridge between session and durable docs.
- **Within 7 days,** convert raw notes into one of:
  - a durable Lesson here (with LL-XXX ID, category, severity, references), OR
  - a risk register entry in `docs/risk_register.md`, OR
  - a runbook/playbook step, OR
  - delete/archive.

**What this file is NOT:**

- Not a session diary (use retrospectives in `docs/retrospectives/`).
- Not a status log (use `docs/inbox.md` or `docs/current_state.md`).
- Not a known-risk register (use `docs/risk_register.md`).
- Not a TODO list (use Taskmaster).

**Adding a new lesson:**

1. Write it under the appropriate category section using the template format below.
2. Assign the next free LL-XXX ID.
3. Add a row to the Index table.
4. If severity is S0 or S1 and the lesson generalizes, consider adding it to the Top 10 Rules.
5. If the lesson cross-cuts categories, add it to the most-relevant category and reference it from the others.

**Lesson entry template:**

```markdown
## LL-NNN — [Title]

- **Category:** [Frappe Framework / CI / Testing / Fixtures / UI / Performance / AI Workflow / Operational / Production Safety]
- **Severity:** [S0 / S1 / S2 / S3]
- **Applies to:** [environment / scope where this applies]
- **What happened:** [The story, briefly]
- **Time cost:** [Estimate]
- **Root cause:** [Why it happened]
- **The fix:** [What we did]
- **Detection:** [How to catch it earlier next time]
- **Prevention for next venue:** [What ships with the codebase to prevent recurrence]
- **References:** [PR / commit / DEC / file path]
```

**Severity scale:**

- **S0** — Data corruption, financial integrity, production outage. Cannot ship without addressing.
- **S1** — Release blocker. Holds Phase or venue rollout.
- **S2** — Serious developer-time sink. Costs hours when hit.
- **S3** — Annoyance / local workflow only. Costs minutes when hit.

---

*Last restructure: 2026-04-29 — split narrative content into `docs/retrospectives/`, governance findings into `docs/risk_register.md`, and added LL-XXX IDs, severity tags, category sections, an index table, a Top 10 Rules section, three new S0 lessons (Upgrade Safety, Production Recovery, Agent Safety), and a maintenance policy. Based on two external reviews of the previous file.*

---

## 2026-04-29 (PM) — Second autonomous run lessons

A second overnight session — V9.1 retail badge fix → Task 25 permissions batch → 3-audit code-quality refactors. Six discrete lessons surfaced; appended below in lighter format than the LL-XXX entries because most are operational gotchas rather than architectural rules.

### `frappe.db.get_single_value` raises on missing fields, not None

- **Surfaced by:** Task 25 permissions PR (#45) initial CI failure on the new `_ensure_audit_trail_enabled` helper.
- **What I assumed:** `frappe.db.get_single_value("System Settings", "enable_audit_trail")` would return `None` if the field didn't exist on this Frappe build, so a defensive `if current is None: return` would handle version variance.
- **Reality:** It raises `frappe.exceptions.ValidationError` ("Field <strong>enable_audit_trail</strong> does not exist on <strong>System Settings</strong>") before returning anything. The defensive None check is unreachable.
- **Fix:** Gate via `frappe.get_meta("System Settings").has_field("enable_audit_trail")` first, then read/write only when present.
- **Generalizes:** Any `db.get_single_value` (or `db.get_value` with a fieldname that may not exist on this build) needs a `meta.has_field` gate first if you're trying to be defensive about Frappe version variance.

### `bench set-config <key> '[...]'` stores values as JSON-encoded strings, not lists

- **Surfaced by:** V9.1 browser test prep — `bench set-config retail_tabs '["Drink/Food"]'` wrote `"retail_tabs": "[\"Drink/Food\"]"` to `site_config.json`, not `"retail_tabs": ["Drink/Food"]`.
- **Effect:** `frappe.conf.get("retail_tabs")` returned the string `"[\"Drink/Food\"]"`. My API's `if not isinstance(tabs, list)` check rejected it; retail tab silently empty.
- **Fix:** Use `bench set-config --parse retail_tabs '...'` (parses the value as JSON before storing), or hand-edit `sites/<site>/site_config.json` directly.
- **Generalizes:** Any non-string config value (list, dict, bool, int) needs `--parse`. Default behavior is "store as string" which is correct for strings only.

### Manually-started Redis collides with `bench start`'s Procfile-managed Redis

- **Surfaced by:** Recovering bench from a stopped state. I started Redis manually on ports 13000+11000 to unblock `bench migrate`, then ran `bench start`. `bench start`'s `redis_queue.1` process tried to bind port 11000, hit my Redis still listening, exited 1, and tore down all sibling processes (web, socketio, schedule, watch, worker).
- **Fix:** Pick one regime. Either (a) let bench own Redis via `bench start`, or (b) manage Redis manually and don't run `bench start`. Mixing them leaves the supervisor and the orphan in a fight.
- **Generalizes:** When debugging a partial bench state, kill the manual Redis instances (`redis-cli -p 13000 shutdown nosave; redis-cli -p 11000 shutdown nosave`) before running `bench start`. Bench's Procfile expects to own those ports.

### Once a seed patch is marked completed, new helpers added to its `execute()` don't auto-run on existing sites

- **Surfaced by:** V9.1 retail seed (Drink/Food + 4 Items) didn't appear on `hamilton-test.localhost` after `bench migrate` — the `seed_hamilton_env` patch was already in `tabPatch Log` from earlier installs, so its (newly extended) `execute()` was skipped.
- **Why:** Frappe's patch runner reads `tabPatch Log` and skips already-completed patches. Adding new logic to a completed patch's body is a no-op on existing sites.
- **Workaround used tonight:** `bench --site SITE execute hamilton_erp.patches.v0_1.seed_hamilton_env._ensure_retail_items` to manually run just the new helper.
- **Better long-term:** When a seed adds a new artifact, also wire the new helper into `after_install` (which runs on EVERY install regardless of patch log) so fresh sites pick it up automatically. Or add a NEW patch file (`patches/v0_2/seed_v9_1_retail.py`) so `bench migrate` runs it as a new patch.
- **Generalizes:** Patches are append-only, semantically. Don't mutate completed patches; add new ones. Or wire into `after_install`/`after_migrate` hooks which run unconditionally.

### Three code-quality audits surfaced one fix and zero antipatterns

- **`frappe.in_test` audit:** zero `frappe.flags.in_test` slips in production code. The defensive "toggle both" pattern from LL-004 is followed in canonical helpers (`real_logs()` in `test_e2e_phase1.py` + `test_stress_simulation.py`). Older test files use single-attribute ad-hoc toggles — works because production reads only `frappe.in_test`, not defensive but not broken either. **No refactor.**
- **`extend_doctype_class` audit:** production code (`hooks.py:69`) uses the v16-canonical `extend_doctype_class` correctly. Only stale references were `test_override_doctype_class_loads_correctly` (test method name) and one upgrade-checkpoint comment in `overrides/sales_invoice.py`. **Fixed in PR #46** (rename + comment update).
- **`== 1` / `== 0` audit:** one production-code use, in `_ensure_audit_trail_enabled` (`int(current or 0) == 1`) — explicit int comparison is intentional because Frappe's `get_single_value` returns may be string or int depending on field type. 25 occurrences in tests are all `assertEqual(count, N)` — correct test idiom, not antipattern. **No refactor.**

**Audit lesson:** drift accumulates in test names and comments more than in production code. The actual code patterns followed canonical Frappe v16 in every audit.

### V9.1 retail tab badge: spec consistency caught at code-review time

- **Surfaced by:** Reading the V9.1 implementation against Amendment 2026-04-29 A29-2 ("tab badge = Available count only"). The retail tab badge counted total Items in the Item Group, not in-stock Items.
- **Fix:** Filter retail badge by `Number(it.stock) > 0` in both render paths (initial render in `render_shell()` + live update in `_update_tab_badges()`). Extracted `get_retail_in_stock_count(tab)` helper so both paths use the same logic. PR #44.
- **Generalizes:** When extending a tab framework with a new tab kind (retail tabs alongside asset tabs), the live-update path is the most common place to forget. Asset tabs had `_update_tab_badges` updated when they shipped; retail tabs needed the same. Pattern: any badge logic must exist in BOTH `render_shell` (first render) and `_update_tab_badges` (per-tick update); they should compute the same value.


---

## 2026-04-30 — V9.1 Phase 2 cart UX stub

Built the retail cart UX (drawer, qty controls, HST math, cash payment modal) as a stub PR — the Sales Invoice creation step is deliberately a no-op pending accounting prerequisites. Three lessons surfaced; appended below.

### Investigate accounting state BEFORE designing a Sales Invoice flow

When the user asked for "payment flow that creates an ERPNext Sales Invoice," the natural instinct was to dive into the cart UX and figure out the Sales Invoice creation as I went. Spending 5 minutes querying the dev-site's accounting state first surfaced that the prereqs were essentially absent: no warehouses under Hamilton's company, no cost center, no HST tax account, no Sales Taxes and Charges Template, no Item Defaults on the seeded retail items, default warehouse on Stock Settings = NULL.

**Generalizes:** for any feature that creates ERPNext financial documents (Sales Invoice, Purchase Invoice, Stock Entry, Payment Entry), the prereq chain is large and venue-specific. The single highest-leverage 5-minute task is to query the existing accounting state on the target site before deciding scope.

### Stub the irreversible step; ship the UX for browser iteration

Cart UX is iterative — drawer placement, qty button shape, HST display, payment modal flow — and the operator's first browser-test reaction is going to drive multiple rounds of revision. Sales Invoice creation is irreversible bookkeeping: once the chart of accounts is committed, changing it is painful (existing transactions reference the old accounts).

**Pattern:** stub the irreversible step with a clear toast ("Sales Invoice creation pending accounting setup"), build the rest of the UX end-to-end, and let the user validate the iteration-friendly part before the locked-in part is wired. The cart state, math, drawer rendering, and modal flow all work without touching ERPNext accounting.

### Pin the stub contract in tests so future PRs don't quietly cross the line

When a PR ships a stub, the next PR's author may not read the design doc and may think the stub is "incomplete code that needs filling in." Without an explicit guard, they'll wire `frappe.xcall("hamilton_erp.api.submit_retail_sale", ...)` into the confirm button and break the deferred-accounting contract.

**Pattern:** add a regression test that asserts the stub method body does NOT contain `frappe.xcall`, `frappe.db.insert`, or other side-effect call patterns. The test fails CI when the stub is "completed" without first wiring the accounting prereqs. See `test_v91_payment_modal_does_not_call_frappe_db_or_xcall` in `test_asset_board_rendering.py` for the implementation.

> **Update 2026-04-30 (b):** the inverse stub-contract test was replaced when the follow-up PR wired Sales Invoice creation. New test (`test_js_payment_modal_calls_submit_retail_sale`) asserts the positive contract — `frappe.xcall` IS called and points at `hamilton_erp.api.submit_retail_sale`. Lesson stands: stub contracts are valuable for the period when the stub exists; flipping them to positive contracts at completion is the natural lifecycle.

---

## 2026-04-30 (b) — Sales Invoice wiring + accounting seed (follow-up to cart UX stub)

The follow-up PR landed the accounting prereqs (QBO-mirrored names locked by Chris's accountant: `GST/HST Payable`, `4260 Beverage`, `4210 Food`, warehouse + cost center "Hamilton", POS Profile "Hamilton Front Desk") and replaced the cart Confirm stub with a real `submit_retail_sale` API. Four lessons surfaced.

### "WP" was a Frappe demo fixture, not Hamilton's company

When investigating accounting state, an early query returned `default_income_account = "Sales - WP"` and led to a working assumption that "WP" was Hamilton's company abbreviation. Five minutes later, querying `tabCompany` directly showed: WP = "Wind Power LLC", a Frappe demo fixture with USD currency and country=United States. Hamilton had no real company on the dev site at all — the `Sales - WP` account was a side effect of the demo fixture's CoA scaffold.

**Generalizes:** Frappe ships demo data (customers, items, companies) as part of the test fixture loader. Any query that returns "expected-shaped" data on a non-greenfield site should be cross-checked against `tabCompany` / `tabCustomer` etc. directly before treating the result as production state. The shape lies; the row count tells the truth.

### Standard CoA template auto-runs when a Company is inserted

ERPNext's Company doctype has a controller that, on insert, calls `create_chart_of_accounts` if `chart_of_accounts="Standard"` and `create_chart_of_accounts_based_on="Standard Template"` are set. This populates ~70 accounts (Income, Direct/Indirect Income, Assets, Liabilities, Duties and Taxes, Cost of Goods Sold, Cash, Bank, etc.) plus the root warehouse and root cost center.

**Pattern:** for fresh-install seeds, creating the Company is the cheapest way to get a usable CoA scaffold. Layer venue-specific accounts on top — don't try to build the CoA from scratch.

**Caveat:** the parent group names are slightly variable across CoA templates ("Indirect Income" vs. "Sales", "Duties and Taxes" vs. "Tax Accounts"). The seed uses a `_find_account_parent(company, root_type, preferred_names)` helper that searches by `root_type` and prefers named matches. This is more robust than hard-coding `"Indirect Income - {abbr}"`.

### Mode of Payment Account is per-(company, mode); idempotency must check by company

`Mode of Payment` is a global doctype with a child table `accounts` of `Mode of Payment Account` rows. Each row is keyed by `company` and points to a `default_account`. A POS Sales Invoice's payment posting needs the row for the invoice's company; without it, submit fails with `Account not specified for Cash`.

**Pattern:** when seeding a company, append a Mode of Payment Account row for each mode the company will use. Idempotency check is `existing = next((a for a in mop.accounts if a.company == company), None)` — by-company, not by-account. Otherwise re-runs append duplicate rows.

### POS Sales Invoice payment math: `payments[0].amount` is collected, not tendered

ERPNext records `payments[i].amount` as the amount collected in that method (i.e. minus change), not the cash tendered. Change is captured separately via `change_amount`. For a $11.30 sale where the customer hands over $20:
- `payments[0].mode_of_payment = "Cash"`
- `payments[0].amount = 11.30` (collected)
- `change_amount = 8.70` (returned)
- `paid_amount = 11.30` (sum of payments.amount)
- `outstanding_amount = 0`

If you mistakenly set `payments[0].amount = 20` (cash tendered) and `change_amount = 8.70`, ERPNext's validator computes `paid_amount = 20`, then `outstanding = grand_total - paid_amount = -8.70`, and either errors or posts a phantom GL line. The correct pattern is `amount = grand_total` and `change_amount = cash_received - grand_total`, which is what `submit_retail_sale` does.

## 2026-05-01 — Brew-managed Redis on 6379 must NOT run alongside bench's Redis

A separate `brew services redis` had been running on `127.0.0.1:6379` for months alongside bench's own Redis instances on `127.0.0.1:11000` (queue) and `127.0.0.1:13000` (cache + socketio).

**The two are unrelated** — Frappe/bench reads the explicit `redis_cache` / `redis_queue` URLs from `sites/common_site_config.json` and never touches 6379. But the brew Redis being there caused two real problems:

1. **False mental model.** Two visible `redis-server` processes made it look like there was a port fight. There wasn't — different ports — but the noise made `bench start` failures harder to diagnose. (When `bench start` actually DOES fail with "address in use," it's because a previous `bench start` left orphaned redis-server processes on 11000/13000, not because of the brew instance on 6379.)

2. **Silent fallback hiding config bugs.** Any code path that calls `redis.Redis()` with no args defaults to `localhost:6379`. With brew Redis running, that call silently succeeds against an unrelated empty Redis with no Frappe data. With brew Redis stopped, the same call fails fast with `ConnectionRefusedError` — the bug surfaces immediately.

**Fix applied:** `brew services stop redis` (and `brew services list` confirms `redis: none`). The launchd plist at `~/Library/LaunchAgents/homebrew.mxcl.redis.plist` has `KeepAlive=true`, so `stop` is a one-shot kill; if it ever re-appears at login, run `brew services stop redis` again or remove the plist entirely with `rm ~/Library/LaunchAgents/homebrew.mxcl.redis.plist`.

**Rule for future Claude sessions:** never `brew services start redis` on this machine. Bench owns Redis. If a tool wants Redis on 6379, it's wrong — fix the tool to read bench's config or point it at 11000/13000 explicitly.

**Verification after stopping brew Redis:**
- `lsof -i :6379` returns empty
- `lsof -i :11000 -i :13000` shows bench redis still bound
- `curl -sI http://hamilton-test.localhost:8000/login` returns `200 OK`
- `bench --site hamilton-unit-test.localhost migrate` runs clean

If a project ever needs a separate Redis (different DB, isolated dev env), spin it up on a non-default port (e.g. 6380) and document it in that project's CLAUDE.md — never reclaim 6379.

---

## LL-038 — Verify install-hook target fields exist on the pinned framework version, not just in design intent

**Date discovered:** 2026-05-03 (during T1-6 implementation, per `docs/inbox/2026-05-04_audit_synthesis_decisions.md`).

**The finding.** `hamilton_erp/setup/install.py:46-69` defines `_ensure_audit_trail_enabled()`, which is supposed to flip `System Settings.enable_audit_trail = 1` after every install/migrate. The intent (per `task_25_checklist.md` Task 25 item 3, marked DONE) was to centrally enable Frappe's tamper-evident audit log so every Hamilton DocType change after handoff is automatically traceable.

**The reality.** **The field `enable_audit_trail` does not exist on Frappe v16.14.0**. Verified two ways:
- `frappe.get_meta("System Settings").has_field("enable_audit_trail")` returns `False`.
- `grep enable_audit_trail apps/frappe/` returns zero hits across the entire pinned Frappe repo.

The hook's defensive branch (`if not meta.has_field("enable_audit_trail"): logger.info(...); return`) silently no-ops on every install. The `frappe.logger().info` it emits never bubbles up to anyone. Hamilton has been running with `_ensure_audit_trail_enabled` doing literally nothing for the entire app lifetime — the whole hook is dead code.

**What actually carries audit coverage on v16.** Per-DocType `track_changes: 1`. Frappe v15+ removed any global "enable audit trail" master flag and made it strictly per-DocType. Hamilton's `track_changes: 1` settings on `Cash Drop`, `Cash Reconciliation`, `Comp Admission Log`, `Hamilton Board Correction`, `Hamilton Settings`, `Shift Record`, `Venue Asset`, `Venue Session` (8 of 9 operational DocTypes) ARE working — every save writes a `tabVersion` row. `Asset Status Log` is correctly `track_changes: 0` because it IS the audit log.

**What the lesson is.** Four independent reviewers (Claude.ai chat, ChatGPT, Claude Code self-audit, Claude Code verification — including this author twice) read the install hook, read the Task 25 checklist, read the decisions docs, and trusted the hook's stated intent without checking whether the target field exists in the running Frappe schema. Word-by-word verification missed it because the question "does Frappe v16 actually have this field?" was never asked. Each reviewer assumed the prior reviewer had checked.

**Rule for the future.** When an install hook says "ensure X is enabled," verify X actually exists on the pinned framework version BEFORE trusting the hook does anything. Five-second check:

```python
# In a bench console session, against the actual pinned Frappe:
frappe.get_meta("<DocType>").has_field("<field>")
# Or grep the framework source:
grep -rn "<field_name>" apps/frappe/ apps/erpnext/
```

If the field doesn't exist, the hook is dead code regardless of how thoroughly its docstring describes the intent. The same lens applies to any code that depends on a framework-side field: a defensive `if hasattr(...)` or `if meta.has_field(...)` that silently skips on `False` is a code smell — it can hide a missing prereq forever.

**What's pinned now.** PR #161 (T1-6 per the audit synthesis) added `test_track_changes_enabled_on_all_auditable_hamilton_doctypes` to `test_fresh_install_conformance.py`. That test asserts the v16 audit mechanism (per-DocType `track_changes`) is actually configured on every Hamilton operational DocType. Future PRs that add a new Hamilton DocType must extend that test's `AUDITABLE_DOCTYPES` list, or the regression-pin breaks.

**Cleanup follow-up (not urgent).** `_ensure_audit_trail_enabled` in `setup/install.py:46-69` is dead code. Two options for a future cleanup PR:

1. **Delete it.** The v16 mechanism is per-DocType `track_changes`, regression-pinned by PR #161. The install hook adds nothing.
2. **Rewrite it to verify.** Replace the no-op defensive skip with a hard `frappe.throw` if `enable_audit_trail` is missing. That way a future Frappe upgrade that re-introduces the field would be detected, AND a future Frappe upgrade that broke the field would surface as a loud install failure.

Either is small; neither is a launch blocker. Worth opening as a docs/inbox follow-up for cleanup-PR scheduling.

**Cross-references:**
- `docs/inbox/2026-05-04_audit_synthesis_decisions.md` T1-6 (the item that surfaced this)
- PR #161 (the regression pin shipped 2026-05-03)
- `hamilton_erp/setup/install.py:46-69` (the dead hook)
- `task_25_checklist.md` Task 25 item 3 (the design-intent claim that turned out to be partially wrong)

---

## LL-040 — Frappe datetime strings are UTC-without-suffix; `new Date(str)` parses them ambiguously

**What happened.** A 2026-05-03 Asset Board walkthrough showed `"-29m elapsed"` on a session that had started 1 minute earlier. Root cause: `asset_board.js` was calling `new Date(asset.session_start)` directly on the value Frappe's API returned — `"2026-05-03 18:31:00"` — which Chrome interprets as **local time**, not UTC. For an operator outside UTC, this pushed the session_start into the future and produced negative elapsed-minute math.

The same pattern was duplicated in seven call sites across the file: `session_start`, `hamilton_last_status_change`, `last_vacated_at` were all being parsed via `new Date(...)` and all silently misrendered when the operator's timezone differed from UTC.

**Lesson.** Frappe stores Datetime fields as UTC strings without a timezone suffix:

```
"2026-05-03 18:31:00"   ← Frappe's wire format (UTC, no suffix)
"2026-05-03T18:31:00Z"  ← ISO 8601 UTC with explicit Z
```

`new Date(str)` is consistent only on the second form. The first form is parsed:
- **Chrome / Edge / Node:** as local time. Most browsers do this.
- **Safari (older):** sometimes returns `Invalid Date`.
- **Firefox:** as local time, but with a deprecation warning in some versions.

The lesson generalizes: **never pass a Frappe datetime field directly to `new Date()` in client-side JavaScript.** Always normalize first.

**The pattern shipped in DEC-071.**

```js
function parseFrappeDatetime(str) {
    if (!str) return null;
    return new Date(str.replace(" ", "T") + "Z");
}
```

Top-level helper in `asset_board.js`. Every site that previously did `new Date(asset.SOMETHING)` for a Frappe datetime field now goes through this helper. Returns `null` for nullish inputs so callers can short-circuit cleanly.

**Why not use `frappe.datetime.str_to_obj()`?** Frappe's helper exists and is mostly correct, but on a Frappe Page (vs. a Form view) the `frappe.datetime` namespace is loaded only after the page bundle resolves. The 4-line `parseFrappeDatetime` is dependency-free and avoids that timing trap.

**What's pinned now.** No regression test directly — JS unit tests in this repo are source-substring contracts (see `test_asset_board_rendering.py::TestV91RetailCartUXStub`). A future PR could pin "every elapsed-time computation in `asset_board.js` flows through `parseFrappeDatetime`" via a substring assertion. For now, the smell is small enough that code review catches it: any `new Date(...something_that_looks_like_a_field_name...)` is suspect.

**Endpoints / fields that should be audited under this lesson.** Anything that:

1. Is a `frappe.utils.now_datetime()` / `frappe.utils.nowdate()` / Datetime / Date field on a DocType, AND
2. Is returned by a whitelisted endpoint AND consumed by client-side code that does timezone-sensitive math (elapsed, sort by recency, "X minutes ago" rendering).

In Hamilton ERP specifically: `Venue Asset.session_start` (via the joined Venue Session), `Venue Asset.last_vacated_at`, `Venue Asset.last_cleaned_at`, `Venue Asset.hamilton_last_status_change`, and any future Phase 2 timestamp surfacing on the board. All currently fixed by DEC-071.

**Cross-references:**
- DEC-071 in `docs/decisions_log.md` (the design decision)
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js::parseFrappeDatetime` (the helper)
- 2026-05-03 Asset Board walkthrough (the originating finding)

