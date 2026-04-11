# Hamilton ERP — Deploy to Frappe Cloud
# Usage: /deploy
# Fully autonomous. Runs all 7 test modules, fixes any failures, then pushes.
# Never stops to ask Chris unless a STOP condition is hit.

## STOP conditions (only these pause for Chris):
# 1. A fix requires changing a DEC-0XX design decision
# 2. bench migrate is required before deploy
# 3. More than 5 tests fail with the same root cause

## Step 1 — Pull latest and refresh context
git pull origin main

## Step 2 — Run /fix-and-test autonomously
Run all 7 modules. Fix every failure using the decision tree in fix-and-test.md.
Do not stop. Do not ask Chris. Fix and rerun until all 7 modules are green.

## Step 3 — Push to GitHub
cd ~/hamilton_erp && git push origin main

## Step 4 — Confirm and report
Tell Chris:
"All X tests passing. Pushed to GitHub. Frappe Cloud will auto-deploy to
hamilton-erp.v.frappe.cloud within 2-3 minutes."

## Step 5 — If ANY tests still failing after fix attempts
Stop. Tell Chris exactly which tests failed, what was tried, and why it could
not be fixed autonomously. This is the only time Chris needs to be involved.
