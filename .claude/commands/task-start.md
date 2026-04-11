# Hamilton ERP — Start Next Task
# Usage: /task-start
# Autonomous task kickoff. Reads current state, identifies next task, runs it.
# Never asks Chris which task is next — reads it from CLAUDE.md and the plan.

## Step 1 — Refresh
git pull origin main
Read CLAUDE.md to find current task number.
Read the plan doc to find the next unchecked task.

## Step 2 — Run /feature [next task number]
Dispatch the full feature workflow autonomously.
No confirmation needed from Chris.
