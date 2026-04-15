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
    },
    {
      "category": "asset_lifecycle",
      "description": "Asset moves from Available to Occupied after session start",
      "passes": false
    }
  ]
}
```

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
   numbering format, branch/PR naming rules. Add this line: "When compacting, always
   preserve: modified file list, failing test names, and Redis lock key format."

2. CREATE FRAPPE SKILL: Create .claude/skills/frappe-v16/SKILL.md containing these v16
   rules: use frappe.in_test not frappe.flags.in_test, use extend_doctype_class not
   override_doctype_class in hooks.py, always use real type comparisons not string
   comparisons like == "1" or == "0", Redis lock key format is [FILL IN CORRECT FORMAT
   FROM CLAUDE_MEMORY.MD — do not guess], and document the lock key bug that was fixed
   (key must NOT include operation suffix).

3. CREATE TESTING SKILL: Create .claude/skills/hamilton-testing/SKILL.md containing:
   test site is hamilton-unit-test.localhost, bench is ~/frappe-bench-hamilton, run a
   single test with: bench --site hamilton-unit-test.localhost run-tests --app
   hamilton_erp --module hamilton_erp.tests.[test_file_name], run the full suite with:
   bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp, the 5 test
   files are test_lifecycle.py test_locks.py test_venue_asset.py
   test_additional_expert.py test_checklist_complete.py, baseline is 270 passing /
   7 skipped, always run a single test first before the full suite.

4. CREATE SECURITY SUBAGENT: Create .claude/agents/security-reviewer.md — a subagent
   using model opus with tools Read Grep Glob Bash, focused on: Frappe role permissions,
   cancel/amend locks, System Manager restrictions, hardcoded values, silent exceptions,
   and string comparisons that should be real type comparisons (== "1" / == "0").

5. CREATE TEST HOOK: Write a Claude Code hook that runs the Hamilton unit test suite
   after every Python file edit using: bench --site hamilton-unit-test.localhost
   run-tests --app hamilton_erp. The hook should warn and report failures but NOT
   block the edit, since tests are intentionally broken during active development.

6. Commit items 1–5 to GitHub with message:
   "chore: add skills, subagent, hook from engineering blog review"

7. Update claude_memory.md to note:
   - Skills are now set up: frappe-v16 and hamilton-testing in .claude/skills/
   - Security subagent is now set up in .claude/agents/
   - Use /clear between Task 25 sub-items
   - Use Plan Mode (Ctrl+Shift+P) before starting any Task 25 item
   - Use fan-out pattern for the 36 frappe.flags.in_test replacements across 5 files
   - Use Writer/Reviewer two-session pattern instead of manual 3-AI review
   - Do not deploy to Frappe Cloud until all features in docs/feature_status.json
     show "passes": true
