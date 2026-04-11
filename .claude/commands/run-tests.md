# Recommended model: Sonnet — test running is mechanical
#
# Run Hamilton ERP FULL test suite
# Usage: /run-tests
#
# Runs against hamilton-unit-test.localhost — the DEDICATED test site.
# Never point /run-tests at hamilton-test.localhost — that's the dev
# browser site and test teardowns corrupt it (setup_wizard loops,
# 403s, lost roles). See docs/testing_checklist.md top-of-file warning.
# All 12 modules run every time.
# (test_asset_board_rendering added in Task 17.2 — +7 tests.)
# (test_environment_health added post-Task 17 — +10 smoke tests after security-audit sweep.)
# (test_security_audit added 2026-04-11 — +5 SQL-injection / XSS audit tests.)
# For autonomous fixing of failures use /fix-and-test instead.

cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_locks && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_checklist_complete && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_frappe_edge_cases && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_extreme_edge_cases && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_seed_patch && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_api_phase1 && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_asset_board_rendering && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_security_audit && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_environment_health
