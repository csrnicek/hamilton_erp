# Task 9 Start — Full Refresh + Test Run + Dispatch
# Paste this entire block into Claude Code to start Task 9.
# It refreshes all context, runs the full test suite, then dispatches Task 9.

## STEP 1 — Pull latest from GitHub
git pull origin main

## STEP 2 — Read all context files (do this before anything else)
Read these files in order:
1. CLAUDE.md (project identity and rules)
2. docs/decisions_log.md (all decisions DEC-001 to DEC-055)
3. docs/coding_standards.md (tabs, I/O rules, locking rules)
4. docs/testing_guide.md (testing levels and when to run each)
5. docs/testing_checklist.md (all 14 categories, 106 test items)
6. hamilton_erp/lifecycle.py (the 5 completed lifecycle methods)
7. hamilton_erp/locks.py (three-layer lock implementation)
8. hamilton_erp/test_checklist_complete.py (new checklist test file)
9. docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md
   — read the Task 9 section specifically (search for "Task 9")

## STEP 3 — Run the complete test suite
Run ALL 5 test modules separately and report total passing/skipped/failing:

cd ~/frappe-bench-hamilton && source env/bin/activate &&   ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle &&   ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_locks &&   ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset &&   ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert &&   ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_checklist_complete

Report the results as:
- Module 1 (test_lifecycle): X/X
- Module 2 (test_locks): X/X
- Module 3 (test_venue_asset): X/X
- Module 4 (test_additional_expert): X/X
- Module 5 (test_checklist_complete): X passing, X skipped, X failing
- TOTAL: X passing, X skipped, X failing

## STEP 4 — Confirm context before dispatch
Before dispatching Task 9, confirm you have read and understood:
- DEC-033: session number format is {d}-{m}-{y}---{NNN}
  Example: "10-4-2026---001" for the first session on April 10 2026
- The Redis INCR key pattern for the counter
- The DB fallback behavior if Redis is unavailable
- The daily reset requirement (counter resets to 001 on a new day)
- Category P tests in test_checklist_complete.py are currently skipped
  and must pass after Task 9 completes

## STEP 5 — Dispatch Task 9
After confirming all the above, dispatch the Task 9 implementer subagent.
Task 9 implements _next_session_number() with:
- Redis INCR as the primary counter
- DB fallback if Redis is unavailable
- Format: {d}-{m}-{y}---{NNN} per DEC-033
- Daily reset to 001
- Remove @unittest.skip from Category P tests in test_checklist_complete.py
  once session_number is working
