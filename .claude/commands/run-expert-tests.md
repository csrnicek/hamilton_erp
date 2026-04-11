# Run Hamilton ERP expert test suite
# Usage: /run-expert-tests
# Runs the full expert test suite including additional edge cases.
# Many of these tests require Tasks 7-9 to be complete before they pass.
# Run after Task 9 to see full coverage.

cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert
