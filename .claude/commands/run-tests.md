# Run Hamilton ERP tests
# Usage: /run-tests
# Runs all current passing test modules (36 tests as of Task 6).
# Updated automatically after each task.

cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle hamilton_erp.test_locks hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
