# Hamilton ERP — Complete Feature Implementation
# Usage: /feature [task number or feature name]
# Fully autonomous. Implements the task end-to-end using Subagent-Driven Development.
# Never stops to ask Chris unless a STOP condition is hit.

## STOP conditions (only these pause for Chris):
# 1. A decision conflicts with an existing DEC-0XX entry
# 2. bench migrate would drop or alter existing data columns
# 3. The task spec is ambiguous about a fundamental design choice

## Step 1 — Refresh context
git pull origin main
Read: CLAUDE.md, docs/decisions_log.md, docs/coding_standards.md,
      docs/testing_checklist.md, docs/testing_guide.md,
      docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md
      (find the section for task: $ARGUMENTS)

## Step 2 — Implement (Subagent-Driven, fully autonomous)
1. Dispatch implementer subagent — implement the full task
2. Dispatch spec compliance reviewer — verify against plan
3. Dispatch code quality reviewer — verify code quality
4. Apply all CHANGES_REQUIRED fixes autonomously
5. Re-run reviewer if critical issues were found
Do not ask Chris which fix to apply — pick the safer, more conservative option.

## Step 3 — Run /fix-and-test
Run all 7 modules. Fix every failure autonomously using fix-and-test.md decision tree.
Do not stop until all 7 modules are green or a STOP condition is hit.

## Step 4 — Commit and push
git add -A && git commit -m "feat: [task description]"
git push origin main

## Step 5 — Update run-tests.md if new test modules were added
If a new test_*.py file was created, add it to .claude/commands/run-tests.md
and commit that too.

## Step 6 — Report to Chris
"Task [N] complete. X tests passing, X skipped. Commit: [SHA]. Ready for Task [N+1]."

## 3-AI review checkpoints — remind Chris at these tasks:
- Task 11 (seed patch) 🔜
- Task 21 (full Asset Board UI)
- Task 25 (final Frappe Cloud deploy)
