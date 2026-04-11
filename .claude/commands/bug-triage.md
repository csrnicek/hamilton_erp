# Hamilton ERP — Bug Triage
# Usage: /bug-triage [description of the problem]
# Fully autonomous diagnosis. Fixes what it can. Only stops for STOP conditions.

## STOP conditions:
# 1. Fix requires changing a DEC-0XX design decision
# 2. Fix requires modifying production data on Frappe Cloud
# 3. Root cause is in Frappe/ERPNext core (not our code)

## Step 1 — Refresh context
git pull origin main
Read CLAUDE.md, docs/decisions_log.md, docs/coding_standards.md

## Step 2 — Diagnose
Search codebase for code relevant to: $ARGUMENTS
Check git log for recent changes: git log --oneline -10
Run the full test suite to find which tests catch it

## Step 3 — Fix autonomously
Apply the fix. Prefer the most conservative change.
Do not ask Chris which approach to use — pick the safer option.

## Step 4 — Verify
Run /fix-and-test. All 7 modules must be green before committing.

## Step 5 — Commit and report
git add -A && git commit -m "fix: [description]"
git push origin main
Tell Chris: "Bug fixed. Root cause: [explanation]. Commit: [SHA]."
Severity: Critical / High / Low
