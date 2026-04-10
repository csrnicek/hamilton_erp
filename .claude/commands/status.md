# Show current project status
# Usage: /status
# Shows what phase we are on, last commit, and test results.

Run these commands and summarize the output in plain English:
1. cd ~/hamilton_erp && git log --oneline -5
2. cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp 2>&1 | grep -E "✔|✗|ERROR|passed|failed|error"
3. cat ~/hamilton_erp/docs/current_state.md | head -30

Then tell Chris: what task we are on, how many tests are passing, and what the next step is.
