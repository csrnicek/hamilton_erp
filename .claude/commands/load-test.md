# Hamilton ERP — 10,000 Check-in Load Test
# Usage: /load-test
# WARNING: This takes 5-10 minutes. Do not run during normal dev workflow.
# Run before major releases or after infrastructure changes.
# Safe — runs against hamilton-test.localhost only. Zero risk to Frappe Cloud.

cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp \
    --module hamilton_erp.test_load_10k \
    --verbose

# Expected results:
# - 10,000 check-ins completed: 10,000/10,000
# - Duplicate session numbers: 0
# - Null/empty session numbers: 0
# - Bad format: 0
# - Wrong date prefix: 0
# - Throughput: 50-150 check-ins/sec on M1 Max local bench
# - All 5 subtests passing
