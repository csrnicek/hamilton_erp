# Run Hamilton ERP core passing tests
# Usage: /run-tests
# Runs all currently passing tests (44 as of Task 8).
# Updated automatically after each task.

cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle hamilton_erp.test_locks hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
