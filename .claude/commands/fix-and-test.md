# Hamilton ERP — Fix and Test (Autonomous)
# Usage: /fix-and-test
# Runs all 7 test modules and autonomously fixes every failure without asking Chris.
# Only stop and ask Chris if you hit a decision that could cause data loss or
# change the fundamental design of the system.

## Step 1 — Pull latest
git pull origin main

## Step 2 — Run all 7 modules
Run each module and collect all failures and errors before doing anything:

cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_locks && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_checklist_complete && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_frappe_edge_cases && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_extreme_edge_cases

## Step 3 — Autonomous fix decision tree
Apply these rules IN ORDER for every failure, without asking Chris:

### MODULE NOT FOUND
→ Run: git pull origin main
→ If still missing after pull: create the file from scratch based on the module
  name and what the testing_checklist.md says it should contain.
→ Run the module again. If it passes, commit and continue.

### @unittest.skip with reason "Task N — X not yet implemented"
→ If Task N is complete (check CLAUDE.md task list): remove the @unittest.skip decorator.
→ Run the test. If it passes, commit.
→ If it fails after un-skipping: fix the test body to match current implementation,
  then run again. Commit when green.
→ If Task N is NOT complete: leave the skip. Move on.

### @unittest.skip with reason "Needs date mocking — deferred to Task N"
→ Leave the skip. Update reason to "Needs date mocking — deferred to Task 13" if vague.
→ Move on.

### ERROR (not FAIL) — test crashes before assertion
→ Read the full traceback.
→ If the error is "wrong premise" (test asserts X but reality is Y):
  Update the test to match reality. Document the real behavior in the docstring.
  Example: test expects ignore_permissions=True to bypass UI lock — it doesn't.
  Fix: change assertion to assertRaises(DocumentLockedError). Commit.
→ If the error is an import error: fix the import. Commit.
→ If the error is a missing fixture (Walk-in Customer, asset, etc.):
  Add the fixture to setUp. Commit.

### FAIL — assertion wrong
→ Read what was expected vs what was received.
→ If implementation changed and test is stale: update the test assertion. Commit.
→ If implementation has a bug: fix the implementation. Commit.
→ If both are ambiguous: fix the test to document current behavior with a clear
  comment explaining why. Commit.

### REDIS errors during test
→ Wait 15 seconds (TTL expires) and rerun. If still failing, add a
  frappe.cache().delete(key) in tearDown. Commit.

### NEVER ask Chris about:
- Which of two fix options to use — pick the safer one (document real behavior)
- Whether to skip a test — only skip if Task number is not yet complete
- Whether to commit — always commit after every fix
- Whether to continue — always continue until all 7 modules are green or
  you hit a STOP condition below

## Step 4 — STOP conditions (only these require asking Chris)
Stop and ask Chris only if:
1. A fix would change the fundamental design decision (e.g., change how locks work,
   change session_number format, change a DEC-0XX decision)
2. A fix would delete or modify production data
3. More than 5 tests are failing in the same module with the same root cause
   (likely a systemic issue, not individual test bugs)
4. A migration (bench migrate) is required to fix a failure

## Step 5 — Final report
Once all 7 modules are green (or only expected skips remain):
- Report: Module X: Y/Y for each module
- Report total: X passing, X skipped, 0 failing
- Commit all fixes with message: "test: autonomous fix pass — all 7 modules green"
- Push to GitHub
- Tell Chris: "All clear. Ready for Task 11."
