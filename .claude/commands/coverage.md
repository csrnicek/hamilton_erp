# Run tests with coverage report
# Usage: /coverage
# Shows exactly which lines of lifecycle.py and locks.py are not covered by any test.
# Any uncovered line is a potential hidden bug.
# Run after /run-tests to see gaps.

cd ~/frappe-bench-hamilton && source env/bin/activate && python -m pytest --cov=hamilton_erp --cov-report=term-missing --cov-config=.coveragerc $(find apps/hamilton_erp/hamilton_erp -name "test_*.py" | head -20) 2>&1 | tail -40
