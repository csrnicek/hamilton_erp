# Hamilton ERP — Bug Triage
# Usage: /bug-triage [description of the problem]
# Use this when something breaks at Club Hamilton or in the ERP system.

For the reported bug: $ARGUMENTS

1. Read CLAUDE.md and docs/current_state.md to understand current project state
2. Search the codebase for the relevant code section
3. Check git log for recent changes that might have caused it: git log --oneline -10
4. Run the full test suite to see if any tests catch it:
   cd ~/frappe-bench-hamilton && source env/bin/activate && \
   ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle hamilton_erp.test_locks hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset hamilton_erp.test_additional_expert hamilton_erp.test_checklist_complete
5. Identify root cause with specific file and line number
6. Propose fix with minimal code change
7. Estimate severity: Critical (data loss/corruption) / High (feature broken) / Low (cosmetic)
8. State whether a hotfix to Frappe Cloud is needed immediately or can wait for next task

Be specific. Reference file names and line numbers. Plain English explanation for Chris.
