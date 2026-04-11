# Run Hamilton ERP FULL test suite
# Usage: /run-tests
# Always runs ALL tests including expert edge cases (45 core + ~52 expert).
# Updated automatically after each task.
# Note: some expert tests require Tasks 9+ to pass — failures are expected
# until those tasks complete. Always report the full pass/fail count.

cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle hamilton_erp.test_locks hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset hamilton_erp.test_additional_expert
