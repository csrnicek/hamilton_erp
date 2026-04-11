# Hamilton ERP — Smart Deploy
# Usage: /deploy
# Deploys to Frappe Cloud after running tests.
# Always runs tests first — never deploys broken code.

Step 1 — Run full test suite first:
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_locks && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_additional_expert && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_checklist_complete

Step 2 — If ALL tests pass, push to GitHub:
cd ~/hamilton_erp && git push origin main

Step 3 — Confirm deploy:
Tell Chris: "All X tests passed. Pushed to GitHub. Frappe Cloud will auto-deploy to hamilton-erp.v.frappe.cloud within 2-3 minutes."

Step 4 — If ANY tests fail:
Stop immediately. Do NOT push. Tell Chris exactly which tests failed and why.
Do not deploy broken code under any circumstances.
