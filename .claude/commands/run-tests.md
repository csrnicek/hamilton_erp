# Run Hamilton ERP tests
# Usage: /run-tests [module]
# Runs the test suite for the specified module, or all hamilton_erp tests if no module given.

cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp $ARGUMENTS
