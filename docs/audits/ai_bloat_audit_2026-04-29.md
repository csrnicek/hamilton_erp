# AI Bloat Audit (Task 25 item 19, report-first)

**Generated:** 2026-04-29 across three independent methods (Claude prompt audit, automated tools, manual file review).
**Promoted to canonical doc:** 2026-05-01 (Task 25 item 19 — "report-first, approve, test, commit" workflow).
**Status:** REPORT ONLY. No code changes have shipped from this audit yet. Cleanup PRs follow after Chris-approves the findings.

This file consolidates the AI bloat audit findings that previously lived only in `docs/inbox.md` so the audit is a findable canonical reference (per the same-day-write rule in `CLAUDE.md` "Plugin Data Freshness").

---

## 2026-04-29 — AI bloat audit (3 methods)

**Goal:** Find what to clean up before Task 25 (Frappe Cloud deploy + handoff) so the production codebase is as small as possible.

**Headline:** Codebase is in good shape overall (radon CC avg = A on 52 production blocks, MI grade A across every production module). Real bloat is concentrated in three places: (1) the parallel "DocType whitelisted methods" API in `venue_asset.py` that duplicates `api.py` and is never called from any UI; (2) two pieces of dead JS code in `asset_board.js` that read `asset.oos_days` and `asset.reason` fields the API never returns — **this is a USER-FACING BUG: operators see "Reason unknown" on every OOS tile**; (3) one near-verbatim ~40-line duplicate between `_show_overlay` and `_redraw_overlay`. Phase 2 not-yet-built stubs are intentional placeholders, NOT bloat.

### Method 1 — Claude-prompt audit (top findings)

#### Dead code

1. **`hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py:75-110` — five DocType whitelisted methods are never called from any production UI.** `assign_to_session`, `mark_vacant`, `mark_clean`, `set_out_of_service`, `return_to_service` are exact 1-line delegators to `lifecycle.*`. The Asset Board JS (`asset_board.js:855-859`) calls top-level `hamilton_erp.api.start_walk_in_session` / `vacate_asset` / `clean_asset` / `set_asset_oos` / `return_asset_from_oos` — never the doctype-bound variants. Only `test_venue_asset.py:218,225` references `mark_vacant`/`set_out_of_service`. ~36 lines of parallel API surface that exists only to be tested. Cheapest fix: delete the doctype methods + their two test references.

2. **`hamilton_erp/hamilton_erp/page/asset_board/asset_board.js:344-351` — OOS day-counter badge code is unreachable.** The block reads `asset.oos_days` and renders `<span class="hamilton-oos-days">…d</span>`. But `api.py:get_asset_board_data` (lines 89-95 field list) does NOT include `oos_days` in its enrichment. The `if (asset.oos_days != null)` guard always evaluates false; the `oos_days_html` variable is always empty.

3. **`hamilton_erp/hamilton_erp/page/asset_board/asset_board.js:631, 769` — `asset.reason` is read in two places, never sent by the API.** The OOS expand panel renders `asset.reason` (line 631) and the Return-to-Service modal context line (line 769) reads `asset.reason`. `api.py:get_asset_board_data` does not include `reason` in its `frappe.get_all` field list, so `asset.reason` is always `undefined` and both spots fall back to `__("Reason unknown")`. **USER-FACING BUG.** Fix: add `"reason"` (and `"hamilton_last_status_change"` if computing oos_days server-side) to the `frappe.get_all` field list at `api.py:91`. 5-min fix, zero risk.

4. **`hamilton_erp/tasks.py:4` — `check_overtime_sessions()` is a no-op `pass` body wired into scheduler_events every 15 minutes.** Intentional Phase 1 placeholder per docstring; consumes a scheduler slot that fires 96×/day to do nothing. Acceptable until Phase 2.

#### Unused imports / vars

5. None of substance found. Vulture's flags on `hooks.py` top-level vars (`app_title`, `app_publisher`, `doc_events`, `extend_doctype_class`, etc.) are false positives — Frappe loads these by string name.

#### Over-commenting

6. **`lifecycle.py:138-198` — `_create_session` has a 60-line docstring before 35 lines of code.** A third of it is provenance metadata ("3-AI review I3", "Fix 10, DEC-056") that belongs in `decisions_log.md`, not the source file. Consider keeping operational what+why; move review/decision provenance to `# Decision: DEC-056. Review: lessons_learned.md 2026-04-10.` Saves ~40 lines.

7. **`lifecycle.py:437-446` — 10-line comment justifying why `_set_cleaned_timestamp` is separate from `_set_vacated_timestamp`.** Defensive justification longer than the 3-line function body. Reduce to one line: `# Separate from _set_vacated_timestamp because OOS entry sets neither.`

8. **`locks.py:79-83` — `# TODO(phase-2): distinguish transient contention from stuck-lock recovery…`** Floating TODO with no plan. Either file as Taskmaster Phase 2 task or delete.

9. **`api.py:11-43` — `on_sales_invoice_submit` docstring (24 lines) is longer than the function body (10 lines).** Most describes the `extend_doctype_class` registration mechanism (already documented in `hooks.py`). Trim to ~5 lines: purpose, phase status, realtime payload contract.

#### Duplicated patterns

10. **`asset_board.js:271-308` (`_show_overlay`) and `:533-572` (`_redraw_overlay`) — ~40 lines of near-verbatim duplication.** HTML construction (`status_cls`, `code_html`, `actions_html`, the `<div class="hamilton-expand-overlay…">` template), the `find("[data-action]").on("click.action", …)` handler, and the 6-branch action dispatcher are duplicated verbatim. Only difference: `_show_overlay` adds source-tile dim class + scroll listener; `_redraw_overlay` skips both. Extract `_build_overlay(asset)` returning the `$overlay` element + bound action handler. Saves ~30 lines.

11. **`api.py:280-326` and `venue_asset.py:75-110` — 5 paired wrappers.** Each pair is 6-9 lines of `has_permission` + `from … import` + 1-line delegator. Five of these per file = ~80 lines that could be 0 if either file is deleted. See finding #1.

12. **`api.py:216-230` — `mark_all_clean_rooms()` and `mark_all_clean_lockers()`** are 5-line wrappers around `_mark_all_clean(category=...)`. Could collapse into one whitelisted endpoint. **Verdict: borderline; leave as-is for audit clarity** (2 narrow endpoints permission/audit cleaner than 1 generic).

#### Over-abstraction (mostly verdict: keep)

13. `api.py:180-194 _get_hamilton_settings()` — called once but the defaults-on-fresh-install logic is non-trivial. Keep.
14. `realtime.py:77-92 publish_board_refresh()` — 1-line wrapper around `frappe.publish_realtime`. Pins event-name contract for Phase 2 callers. Keep.
15. `lifecycle.py:59-61 _require_oos_entry` — 3 lines, called once. Borderline; leave as-is.

### Method 2 — Automated tools (vulture + radon)

**vulture findings (production code only, after filtering Frappe-by-name hooks):** zero real dead code. Vulture is largely uninformative on Frappe codebases because the framework dispatches by name (vulture cannot resolve `doc_events`, `extend_doctype_class`, doctype controller class names, or string-method `frappe.call` callsites in JS).

**radon cyclomatic complexity:** average production CC is 2.79 (grade A). Only one above grade A:
- `api.py:52 get_asset_board_data` — grade D (CC ≈ 19). **Justified** (4 query-and-enrich passes to keep query count constant; pinned by `test_get_asset_board_data_under_one_second`).
- `locks.py:46 asset_status_lock` — grade B (CC ≈ 7). **Justified** (TTL check + Lua release branches per 3-AI review).
- `setup/install.py:168 _create_roles` — grade B (CC ≈ 6). **Justified** (idempotent guards inflate count; benign).

**radon maintainability index:** every production module rates A. None below 65. **No MI red flags.**

### Method 3 — Manual file review

**`realtime.py` (92 lines):** Comments are load-bearing (the `after_commit=True` invariant is non-obvious). Two functions emit different events with different payloads — cannot collapse without losing event-name contract. **Verdict: clean.**

**`utils.py` (30 lines):** No production callers in Phase 1; `test_utils.py` is 100%-covered. Cash-Drop adjacent, scheduled for Phase 3. **Verdict: keep — referenced in build phase plan.**

**`venue_session.py` (54 lines):** `before_insert` docstring is 18 lines for a 5-line function with speculative provenance. Could compress to 2 lines. `_set_defaults` and `_validate_session_end` could be inlined into `validate` but the helper-pair pattern is consistent with `venue_asset.py`. **Verdict: trim docstring; leave helpers.**

### Recommended cleanup actions before Task 25

1. **Fix `asset.reason` and `asset.oos_days` user-facing bug.** Effort: 5 min. Add `"reason"` (and `"hamilton_last_status_change"` if computing oos_days server-side) to `api.py:91` field list. **Highest priority — operators see "Reason unknown" on every OOS tile.**

2. **Delete the parallel DocType-method API in `venue_asset.py:75-110`.** Effort: 20 min. ~36 lines + 2 test updates. Risk: low (no JS or Python production caller).

3. **Extract `_build_overlay()` from `_show_overlay` / `_redraw_overlay`.** Effort: 30 min. ~30 lines saved. Risk: medium (Operator action path; needs manual click-test of each action in each status before/after).

4. **Trim `_create_session` docstring** (`lifecycle.py:138-198`). Effort: 15 min. ~40 lines. Risk: zero.

5. **Resolve or delete `TODO(phase-2)` in `locks.py:79-83`.** Effort: 5 min.

**Total realistic cleanup: ~110 lines deleted, 1 user-visible bug fixed, ~75 minutes of work.**

### What is NOT bloat (verified)

- **Triple-layer locking pattern** (Redis + FOR UPDATE + version CAS) — load-bearing per DEC-013.
- **`lifecycle._make_asset_status_log` short-circuits when `frappe.in_test`** — documented (Grok review 2026-04-10); tests that need real logs explicitly clear `frappe.in_test`.
- **`venue_session.before_insert` local import** — prevents documented circular-import hazard.
- **`api.py:get_asset_board_data` 4-query batched enrichment** — pins 1s SLA, multi-venue plan has ~200+ assets per site.
- **Phase 2 stubs** (`assign_asset_to_session` throw, `tasks.check_overtime_sessions` no-op) — intentional.
- **`setup/install.py` layered patches** — each guard fixes a documented Frappe bug.
- **`hooks.py` top-level vars + DocType controller classes** — Frappe loads by string name; vulture false positives.
- **`utils.py` (0 Phase 1 callers)** — Phase 3 cash-drop scheduled work.
- **`venue_asset.py:_validate_status_transition`** — encapsulates state-machine guard + new-record rule; right grain.

### Test suite redundancy audit

**Goal:** Find tests to delete or consolidate before Task 25 to keep the test suite lean as Phase 1 closes.

**Headline:** ~494 tests across 30 modules with 4 high-overlap clusters (state-machine invalid transitions, lock-release-on-exception, version-CAS sweeps, "after vacate, current_session is None"). At least 35-50 tests are pure restatements of an invariant already pinned elsewhere; another ~10-15 are testing Frappe (TimestampMismatch, MandatoryError, DuplicateEntryError) rather than Hamilton. Net cull target: **~50 tests / ~1,200 LOC, no coverage loss.**

**Suite size today:** 494 test methods across 30 modules. Largest concentrations: `test_lifecycle.py` (62), `test_checklist_complete.py` (63), `test_database_advanced.py` (51), `test_asset_board_rendering.py` (45), `test_adversarial.py` (45 — 8 skipped).

#### Pure redundancy (delete or consolidate)

**1. Invalid state-machine transitions tested in 4 places.** The 9 invalid edges of the FSM are exhaustively covered in `test_additional_expert.py::TestAllInvalidTransitions` (5 tests). They are also re-covered by `test_venue_asset.py` doctype tests, `test_e2e_phase1.py::TestH12OccupiedAssetRejection` (5 tests), and `test_lifecycle.py::TestLifecycleHelpers::test_require_transition_throws_on_mismatch`. Recommend deleting `TestAllInvalidTransitions` (~55 LOC) — it duplicates the doctype-folder tests at the same layer.

**2. "Lock released after exception" tested 7+ times** across `test_additional_expert.py`, the 5 inline `verify-release` blocks in `test_lifecycle.py` (lines 132-134, 206-208, 286-288, 422-424, 491-493), `test_extreme_edge_cases.py`, `test_checklist_complete.py`, `test_database_advanced.py`, and `test_adversarial.py::TestFamilyB`. Recommend deleting the 5 inline `verify-release` blocks — the dedicated lock-release tests cover this. ~30 LOC.

**3. Version increments by 1 on each transition — tested 8 times.** Canonical full-sweep: `test_checklist_complete.py::TestEntryExitActionsChecklist::test_version_increments_on_every_transition`. Plus `test_lifecycle.py::TestVersionCAS::test_D3` (direct CAS test). Recommend deleting `test_database_advanced.py::test_version_increments_monotonically` and `test_checklist_complete.py::TestGuardBoundaries::test_version_increments_correctly`. ~15 LOC.

**4. "current_session is None after vacate" tested 5 times.** Recommend deleting `test_database_advanced.py::test_current_session_cleared_after_vacate` and `test_extreme_edge_cases.py::test_current_session_never_silently_left_populated_after_vacate`. ~25 LOC.

**5. "OOS reason whitespace rejected" tested 6 times.** Recommend folding `TestGuardConditionBoundaries::test_oos_reason_single_space_is_rejected` and `test_oos_reason_tab_only_is_rejected` into the F1/F2 NBSP/newline set as parametrized cases. ~15 LOC.

#### Low-value tests (consider deleting)

**1. `test_hamilton_settings.py` is literally `class TestHamiltonSettings(IntegrationTestCase): pass`.** Zero assertions. Delete the file or write the missing tests.

**2. `test_lifecycle.py::TestNamedConstants` (5 tests, lines 880-907).** Pins literal strings. `assertEqual(lifecycle.WALKIN_CUSTOMER, "Walk-in")` is `assertEqual(x, x)` if the import works. ~25 LOC. Delete.

**3. `test_lifecycle.py::TestHamiltonSettingsDefaults` (4 tests, lines 910-940).** Already covered by `test_seed_patch.py::test_seed_populates_hamilton_settings`. ~25 LOC. Fold into seed test or delete.

**4. `test_database_advanced.py::test_frappe_in_test_flag_is_true` (line 468).** Tests the test runner's flag. ~5 LOC. Delete.

**5. `test_database_advanced.py::test_after_migrate_hook_is_importable` and `test_scheduler_job_is_importable` (lines 479-484).** "Function is callable / importable" smoke tests with zero logic. ~10 LOC. Delete.

**6. `test_environment_health.py::test_redis_cache_port_reachable` and `test_redis_queue_port_reachable`.** Belong in `/debug-env`, not the suite. If Redis is down, every test fails 30s later anyway. ~30 LOC. Demote.

#### Framework-testing (delete or refactor to test Hamilton instead)

These test Frappe/MariaDB/redis-py behavior, not Hamilton's. If the framework ships a different version with different behavior, they fail for reasons unrelated to Hamilton.

- `test_frappe_edge_cases.py::test_timestamp_mismatch_on_concurrent_save` — testing Frappe's conflict detection. Hamilton's CAS tests cover what we rely on. Delete.
- `test_frappe_edge_cases.py::test_xss_stripped_from_oos_reason` — testing Frappe's `strip_html_tags`. Hamilton-side XSS test is in `test_security_audit.py`. Delete.
- `test_frappe_edge_cases.py::test_mandatory_field_enforced_on_insert` — testing Frappe's required-field validator. Delete.
- `test_frappe_edge_cases.py::test_new_doc_with_fields_pattern` — testing Frappe's constructor signature. Delete.
- `test_frappe_edge_cases.py::test_frappe_ui_lock_prevents_second_lock` and `test_frappe_ui_lock_persists_across_instances` — testing Frappe's `Document.lock()`. Delete (keep the third test in the class — `test_lifecycle_bypasses_frappe_ui_lock` is Hamilton-specific).
- `test_frappe_edge_cases.py::TestNamingAndSequence::test_asset_code_unique_constraint_raises_duplicate_entry` — testing the MariaDB UNIQUE constraint. Same invariant in `test_database_advanced.py`. Keep one, delete the duplicate.
- `test_database_advanced.py::TestMariaDBEdgeCases::test_global_isolation_matches_session`, `test_for_update_locks_row_not_table`, `test_datetime_microsecond_precision` — testing MariaDB defaults. Keep one (the isolation test, since Frappe relies on it); delete the other 3. Document MariaDB requirements in `docs/coding_standards.md`.
- `test_database_advanced.py::TestRedisEdgeCases::test_incr_returns_integer`, `test_incr_at_large_values`, `test_nx_flag_prevents_overwrite` — testing redis-py contracts. Hamilton-side is pinned by `test_lifecycle.py::test_C3_incr_return_value_cast_to_int`. Delete.

**Total: ~14 tests, ~200 LOC.**

#### Pinned-to-implementation (refactor to test behavior, not strings)

**Implementation pins (refactor or delete):**

- `test_asset_board_rendering.py::test_js_defines_show_overlay`, `_position_overlay`, `_hide_overlay` — greps for specific function names. If overlay refactored to an `OverlayManager` class, fails without user-visible regression. Demote to a single test that asserts the file contains "overlay". ~50 LOC.
- `test_js_defines_countdown_threshold_constant` — asserts `COUNTDOWN_THRESHOLD_MIN = 60` appears verbatim. If renamed, fails for non-bug. Same problem with `LIVE_TICK_MS = 15000`. Delete.
- `test_js_reads_guest_name_from_asset` — greps for `asset.guest_name` in the JS source. Destructuring would break. Change to regex allowing destructuring patterns, or move to behavioral test.

**Acceptable behavior pins (keep):**
- `test_js_defines_all_seven_oos_reasons` — pins user-visible reason list.
- `test_css_no_longer_scales_expanded_tile` — pins absence of broken pattern.
- `test_js_does_not_implement_rejected_warning_state` — pins absence of rejected design.
- `test_js_footer_drops_dirty_count_per_v9_spec` — pins V9 Decision 6.2.

#### Slow + redundant (cull)

- `test_extreme_edge_cases.py::test_concurrent_writes_do_not_exceed_connection_pool` — runs 5 full lifecycle cycles for "no leaks." Implicit in every other test. Delete (~1.5s + 20 LOC).
- `test_extreme_edge_cases.py::test_bulk_operation_completes_within_hetzner_request_timeout` — 5-asset perf assertion loosely coupled to 59-asset Nginx reality. Delete or replace with 59-asset stress test (~1s + 30 LOC).
- `test_extreme_edge_cases.py::test_slow_query_does_not_block_indefinitely` — full lifecycle + `< 10s` assertion. If anything takes 10s, operators notice instantly. Delete (~12 LOC).
- `test_database_advanced.py::test_lock_acquisition_under_50ms` — flaky on shared CI. Delete or relax to <500ms (~10 LOC).

#### Recommended actions before Task 25

Ranked by ROI:

1. **Delete framework-testing tests** (~14 tests, ~200 LOC). Effort: 30 min. Risk: zero — these don't test Hamilton.
2. **Delete `TestNamedConstants` and `TestHamiltonSettingsDefaults` from `test_lifecycle.py`** (9 tests, ~50 LOC). Effort: 5 min. Risk: zero.
3. **Delete duplicate "current_session is None after vacate" tests** (2 tests, ~25 LOC). Effort: 5 min.
4. **Delete the 5 inline `verify-release` blocks in `test_lifecycle.py`** (~30 LOC). Effort: 10 min.
5. **Delete `TestAllInvalidTransitions`** in `test_additional_expert.py` (5 tests, ~55 LOC). Effort: 5 min.
6. **Delete or fold the implementation-string overlay/constant pins** in `test_asset_board_rendering.py` (5-6 tests, ~70 LOC). Effort: 15 min.
7. **Delete `test_hamilton_settings.py` empty pass-class** OR write the actual tests it implies. Effort: 5-30 min.

**Total cull target: ~50 tests, ~500-700 LOC. Suite drops from 494 to ~440 tests. No coverage loss against the lines that matter.**

#### What is NOT redundancy (verified)

- **Schema snapshot in `test_api_phase1.py`** vs. doctype-folder tests — pins API contract vs. individual DocType fields. Keep both.
- **Hypothesis property tests** vs. unit tests — property tests deliberately exercise the same state machine via random sequences. Keep both.
- **6 doctype-folder test files** — layer-1 conformance tests per CLAUDE.md. Keep all 6.
- **Stress simulation 11 tests** — real threads + commits exercise concurrency unit tests can't. Keep all.
- **`test_e2e_phase1.py` 18 "real_logs" tests** — turn off `in_test` short-circuit so audit-log path runs. Different layer. Keep all 18.
- **`test_locks.py::test_A1` and `test_A4`** — different scales (deterministic vs. stress). Keep both.
- **`test_lifecycle.py::TestAuditTrailExactlyOneLog`** — pins 1:1 contract against double-logging. Keep.
- **`test_api_phase1.py::TestAssetBoardHTTPVerb`** — only test driving through `frappe.handler.execute_cmd` with spoofed verb. Documented in DEC-058. Keep.
- **`test_database_advanced.py::TestDatabaseIndexes` (7 tests)** — pin Hamilton's index requirements (Frappe doesn't auto-create on Link fields). Keep all 7.


---

# Browser test session 2026-04-29 — V9 production verification

**Result:** All 6 critical V9 launch-blockers from yesterday confirmed fixed. 25 tests run. Production matches V9 spec for the locker + room lifecycle.

## Bugs to fix

1. **RTS modal shows "Reason unknown"** — OOS reason captured at SET OOS isn't read back on Return-to-Service. Same root cause likely affects asset-record persistence. Repro: OOS L029 with "Lock or Hardware" → click L029 → modal shows "Reason unknown" instead.

2. **RTS modal "SET" line missing timestamp** — shows "by Administrator" but should match OOS audit format ("by ADMINISTRATOR at HH:MM AM/PM").

3. **Watch tab missing active-state styling** — selected tab looks identical whether on it or not. Other tabs invert correctly.

4. **No "dirty since X minutes" timer on dirty tiles** — V9 spec wanted this for cleaner prioritization. Missing on both lockers and rooms.

## Decisions to log in decisions_log.md

- **Tab badge = Available count only** (sellable now). Verified consistent across Lockers, Single, Double, GH Room.
- **Watch badge = OT + OOS combined** (everything needing attention).
- **Watch tab grouping by sub-category subtitles** (e.g. "Single Standard 4") — extends to all tabs per earlier V9.1 amendment discussion.
- **Header PM SHIFT + ADMINISTRATOR are read-only** by design. Shift change / logout live on dedicated pages, not header.

## Minor

- Expanded tile shows "26h 24m elapsed" but collapsed tile shows "26h 24m late" — pick one word.

## Already queued (no action needed)
- L029 audit log query.

---


---

## Suggested cleanup-PR sequence (post-approval)

If/when Chris approves the findings, the cleanup ships as several small PRs rather than one big one. Suggested sequence (smallest blast radius first):

1. **Fix dead-JS bug — add `reason` and `hamilton_last_status_change` to API field list.** Closes finding #3 (USER-FACING BUG: "Reason unknown" on every OOS tile). 5-line change to `api.py:91`. Highest priority — fixes a live UX bug.
2. **Delete `venue_asset.py:75-110` parallel whitelisted methods + their two test references.** Closes finding #1 (~36 lines of unused parallel API). Update `test_venue_asset.py:218,225` to call the canonical `lifecycle.*` functions instead.
3. **Delete the unreachable OOS day-counter JS block.** Closes finding #2.
4. **Refactor `_show_overlay` / `_redraw_overlay` to share `_build_overlay`.** Closes finding #10 (~30 lines saved).
5. **Trim over-comments in `lifecycle.py:138-198`, `lifecycle.py:437-446`, `api.py:11-43`.** Closes findings #6, #7, #9. Optional — if Chris values the provenance metadata, leave as-is.

Each cleanup PR ships independently with its own tests. None of these changes are mechanical-rename refactors that touch many files; the blast radius is contained.

## Decision-log entries warranted

If approved, the cleanup PRs should also produce one `docs/decisions_log.md` entry:
- **DEC-NNN: Hamilton API surface convention.** Decision text: "Whitelisted methods on hamilton_erp DocType controllers (e.g. `venue_asset.py`) are not part of the public API surface. Operator-callable endpoints live in `hamilton_erp.api.*` only. DocType controller methods are reserved for framework-driven hooks (validate, on_submit, etc.) and internal lifecycle delegation." This codifies finding #1's resolution so the parallel-API mistake doesn't recur.

## How this audit was produced

Three methods, run independently, then triangulated:

1. **Claude-prompt audit** — explicit prompts asking Claude to find dead code, unused imports, over-commenting, duplicated patterns, and over-abstraction. Produced 15 specific findings.
2. **Automated tools** — `vulture` (dead code detector) and `radon` (CC + MI). Vulture was uninformative on Frappe codebases (framework dispatches by name, so all hooks read as unused). Radon produced one grade-D function (`get_asset_board_data`, justified) and uniformly grade-A maintainability index.
3. **Manual file review** — read the smaller production files end-to-end to spot patterns the prompts miss.

The triangulation matters: the user-facing bug in finding #3 surfaced in method 1 (Claude prompt) but was confirmed by method 3 (manual review of `api.py:91` field list). Method 2 alone would have missed it entirely.

## References

- Source: `docs/inbox.md` 2026-04-29 entry (lines 483-702 at promotion time).
- Related: `docs/lessons_learned.md` LL-031 (agents may diagnose broadly but execute narrowly), `docs/risk_register.md` (no related risk yet).
- Cross-references: `docs/hooks_audit.md` (Task 25 item 11) confirms `hooks.py` top-level vars are correct (false positives in vulture).

---

## Status updates — Chris's review (2026-05-01)

Chris worked through the 15 findings on 2026-05-01 with a current-state verification (many findings had been resolved between the original 2026-04-29 audit and the review date — see `~/Downloads/pr78_ai_bloat_audit.md` review export). Final disposition per finding:

| # | Outcome | PR / note |
|---|---|---|
| 1 | ✅ Already done | `venue_asset.py:75-110` whitelisted methods deleted on 2026-04-29 (predates this audit's review) |
| 2 | ✅ DELETED option (b) | PR #92 — dead `oos_days_html` removed; Phase 2 task 28 queued for proper stale-OOS visibility (12-14px badge, color-coded by staleness, section-header summary) |
| 3 | ✅ Already done | `api.py:91` field list now includes `"reason"` — user-facing "Reason unknown" bug is fixed |
| 4 | ✅ Already done | `tasks.py` removed via PR #53; `hooks.py:85` documents the former Phase 1 stub |
| 5 | ✅ Verified false positives | vulture findings on `hooks.py` top-level vars are framework-dispatched-by-name; confirmed in `docs/hooks_audit.md` |
| 6 | ✅ Aggressive trim shipped | PR #93 — `_create_session` docstring 60 → 25 lines; kept retry contract / exception scope / DEC-056 reference; removed Task 11 review provenance and "Fix 10" labels |
| 7 | ✅ Trim shipped | PR #93 (combined with #6) — `_set_cleaned_timestamp` comment 7 → 3 lines |
| 8 | ✅ Already done | PR #72 (`adfc226`) linked the `locks.py:81` TODO to GitHub issue #71 |
| 9 | ✅ Trim shipped | PR #94 — `on_sales_invoice_submit` docstring 18 → 11 lines; removed framework re-explanation that's already in `hooks.py` |
| 10 | ⏸ **DEFERRED** to a planned session — see below |
| 11 | ✅ Already done | duplicate of #1; resolved by the 2026-04-29 cleanup |
| 12 | ✅ KEEP per audit | `mark_all_clean_*` wrappers — moot since DEC-054 reversal removed the entire bulk Mark All Clean feature on 2026-04-29 (Amendment A29-1) |
| 13 | ✅ KEEP per audit | `_get_hamilton_settings()` — defaults-on-fresh-install logic is non-trivial; inlining would muddy the caller |
| 14 | ✅ Already done | `publish_board_refresh` was removed (DEC-054 reversed) — see `realtime.py:77-79` for the removal note |
| 15 | ✅ KEEP per audit | `_require_oos_entry` — borderline; inlining would lose the named intent |

### Finding #10 — deferred to a planned session

**Decision (2026-05-01):** Chris reviewed the refactor scope and deferred. The `_show_overlay` / `_redraw_overlay` duplication is real (~40 lines), but extracting `_build_overlay` carries non-trivial regression risk because:

1. **The overlay is the action surface** — every Mark Clean, Vacate, OOS, Return-to-Service action goes through it. Click-handler binding (`.off('click.action')` vs `.on('click.action')`) is order-sensitive.
2. **Vacate-sub-buttons state** — the parent → sub-button flip (Key Return / Discovery on Rounds) lives in instance state and the redraw path. Refactor must preserve this state machine.
3. **CI doesn't cover the regression surface** — Server Tests don't exercise JS overlay rendering. The refactor passes CI by default; real regressions surface only in browser testing.

**What needs to happen for the refactor to ship safely:**
1. Read both functions side-by-side end-to-end (~120 lines combined) before extracting
2. Add a Playwright/manual browser regression test for each action path (Mark Clean, Vacate Key Return, Vacate Discovery on Rounds, OOS modal flow + cancel, Return-to-Service modal flow + cancel) BEFORE refactoring
3. Refactor with the test as the regression net
4. Browser-verify on `hamilton-test.localhost`

**Estimated effort:** half a day of careful work. Not a 5-minute autonomous PR.

**Tracking:** this audit doc is the canonical record. Schedule a planned session when the asset-board JS test surface is ready (currently `test_asset_board_rendering.py` is grep-based, not interactive).

**Cleanup PRs sequence above (line 241) supersedes:** items 1, 2, 3 of that sequence have shipped; item 4 (`_build_overlay` refactor) is deferred per this entry; item 5 (over-comment trim) is shipped via PRs #93 + #94. The sequence is closed.
