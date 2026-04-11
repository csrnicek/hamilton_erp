# Run Hypothesis property-based testing
# Usage: /hypothesis
# Generates hundreds of random inputs to find edge cases automatically.
# Install first: pip install hypothesis --break-system-packages
# Requires hamilton_erp/test_hypothesis.py to exist (create in Task 9 hardening).

cd ~/frappe-bench-hamilton && source env/bin/activate && python -m pytest ~/hamilton_erp/hamilton_erp/test_hypothesis.py -v 2>&1
