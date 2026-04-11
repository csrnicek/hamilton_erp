# Hamilton ERP — Complete Feature Implementation
# Usage: /feature [feature name or task number]
# Implements a Phase 1 task using the full Subagent-Driven Development workflow.

For feature/task: $ARGUMENTS

## Phase 1 — Refresh context
1. git pull origin main
2. Read CLAUDE.md, docs/decisions_log.md, docs/coding_standards.md
3. Read the task section in docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md
4. Read docs/testing_checklist.md — check which Category P/O tests apply to this task

## Phase 2 — Implementation (Subagent-Driven)
1. Dispatch implementer subagent
2. Dispatch spec compliance reviewer
3. Dispatch code quality reviewer
4. Apply any CHANGES_REQUIRED fixes
5. Re-run reviewer if critical issues were found

## Phase 3 — Testing
Run the full test suite (all 5 modules separately):
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_locks && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_checklist_complete

Report: X passing, X skipped, X failing.

## Phase 4 — Commit and close
1. git add + git commit with descriptive message
2. git push origin main
3. Update .claude/commands/run-tests.md if new test modules were added
4. Report to Chris: task complete, X tests passing, commit SHA

## 3-AI review checkpoints (remind Chris at these):
- After Task 9 (lifecycle complete) ✅ Done
- After Task 11 (seed patch)
- After Task 21 (full Asset Board UI)
- After Task 25 (final Frappe Cloud deploy)
