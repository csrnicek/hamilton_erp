# Inbox

## Task 25 Addition — Feature Status JSON

At Task 25, before go-live, create a file at docs/feature_status.json listing every
user-facing feature of the Asset Board. Each feature starts marked as "passes": false
and only gets flipped to true after real end-to-end testing. Use JSON format (not
Markdown) because Claude is less likely to accidentally overwrite or rewrite JSON files.

Example format:
```json
{
  "features": [
    {
      "category": "asset_lifecycle",
      "description": "Operator can start a session on an available room",
      "passes": false
    }
  ]
}
```

Do not deploy to Frappe Cloud until every feature shows "passes": true.

Source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## Task 25 Addition — Feature Status JSON

At Task 25, before go-live, create a file at docs/feature_status.json listing every
user-facing feature of the Asset Board. Each feature starts marked as "passes": false
and only gets flipped to true after real end-to-end testing. Use JSON format (not
Markdown) because Claude is less likely to accidentally overwrite or rewrite JSON files.

Example format:
{
  "features": [
    {
      "category": "asset_lifecycle",
      "description": "Operator can start a session on an available room",
      "passes": false
    },
    {
      "category": "asset_lifecycle",
      "description": "Asset moves from Available to Occupied after session start",
      "passes": false
    }
  ]
}

Do not deploy to Frappe Cloud until every feature shows "passes": true.

Source: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

---

## Engineering Blog Action Items — April 15, 2026

### Immediate setup tasks for Claude Code to complete:

0. CREATE FEATURE STATUS FILE: Create docs/feature_status.json with "passes": false
   for every user-facing Asset Board feature. Cover these categories at minimum:
   asset_lifecycle (start session, vacate, mark clean, set out of service, return to
   service), session_numbering (format is {d}-{m}-{y}---{NNN}), locking (Redis lock
   prevents double-assignment), and UI (asset board displays correct status after each
   transition). Commit with message: "chore: add feature_status.json pre-deploy gate"

1. CLAUDE.md AUDIT: Read the current CLAUDE.md. Delete any line that Claude could
   already infer from reading the code (standard Python, standard Frappe, standard git).
   Keep only Hamilton-specific things: test site URL, Redis lock key format, session
   numbering format, branch/PR naming rules. Add this line at the bottom: "When
   compacting, always preserve: modified file list, failing test names, and Redis
   lock key format."

2. CREATE FRAPPE SKILL: Before writing anything, read the file
   hamilton_erp/hamilton_erp/doctype/bathhouse_asset/bathhouse_asset.py and look for
   the Redis lock key string used in the locking functions. Also read claude_memory.md
   for context on the lock key bug that was fixed (the key must NOT include the
   operation suffix). Use the exact key format you find in the code — do not invent one.
   Then create .claude/skills/frappe-v16/SKILL.md containing:
   - Use frappe.in_test not frappe.flags.in_test (36 occurrences across 5 files to fix)
   - Use extend_doctype_class not override_doctype_class in hooks.py line 69
   - Always use real type comparisons, never string comparisons like == "1" or == "0"
   - The correct Redis lock key format is: [read from bathhouse_asset.py as instructed]
   - Lock key bug history: key previously included operation suffix — this was wrong
     and was fixed

3. CREATE TESTING SKILL: Create .claude/skills/hamilton-testing/SKILL.md containing:
   - Test site: hamilton-unit-test.localhost
   - Bench location: ~/frappe-bench-hamilton
   - Run a single test: bench --site hamilton-unit-test.localhost run-tests
     --app hamilton_erp --module hamilton_erp.tests.[test_file_name]
   - Run the full suite: bench --site hamilton-unit-test.localhost run-tests
     --app hamilton_erp
   - The 5 test files: test_lifecycle.py, test_locks.py, test_venue_asset.py,
     test_additional_expert.py, test_checklist_complete.py
   - Baseline is 270 passing / 7 skipped — any drop in passing count is a regression,
     stop and report it
   - Always run a single test first before running the full suite

4. CREATE SECURITY SUBAGENT: Create .claude/agents/security-reviewer.md with this
   exact content:

   ---
   name: security-reviewer
   description: Reviews Hamilton ERP code for security and permission vulnerabilities
   tools: Read, Grep, Glob, Bash
   model: opus
   ---
   You are a senior Frappe/ERPNext security reviewer. Review code for:
   - Frappe role permission gaps (cancel and amend must be locked to manager roles)
   - System Manager access that should be restricted to the venue owner only
   - Hardcoded values that should come from Bathhouse Settings or site config
   - Silent exceptions: bare except blocks or pass after except with no logging
   - String comparisons like == "1" or == "0" that should be real type comparisons
   - Any frappe.flags.in_test usage that should be frappe.in_test
   Provide specific file name, line number, and a suggested fix for each issue found.

5. CREATE TEST HOOK: Create a Claude Code hook that runs after every Python file edit.
   The hook should run: bench --site hamilton-unit-test.localhost run-tests --app
   hamilton_erp and print a pass/fail summary. The hook should warn and report failures
   but NOT block the edit — tests are intentionally broken during active development.

6. Commit items 1 through 5 to GitHub with message:
   "chore: add skills, subagent, and test hook from engineering blog review"

7. Update claude_memory.md to add the following notes:
   - .claude/skills/frappe-v16/ and .claude/skills/hamilton-testing/ are now set up
   - .claude/agents/security-reviewer.md is now set up using opus
   - Use /clear between every Task 25 sub-item — do not carry context across sub-items
   - Use Plan Mode before starting any Task 25 item (Ctrl+Shift+P in Claude Code)
   - The 36 frappe.flags.in_test replacements across 5 files should use the fan-out
     pattern: loop file by file with claude -p, one clean context per file
   - Replace the manual 3-AI review with the Writer/Reviewer two-session pattern:
     Session A writes, Session B reviews from fresh context with no bias
   - Do not deploy to Frappe Cloud until all entries in docs/feature_status.json
     show "passes": true
