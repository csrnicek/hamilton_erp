# Recommended model: Sonnet — this is diagnostic/mechanical work

# Hamilton ERP — Environment Diagnostic
# Usage: /debug-env
# Autonomous environment health report. Runs the standard Frappe doctor
# checks plus Hamilton-specific sanity checks in one shot. Produces a
# PASS/FAIL line for each probe so Chris can see at a glance which
# layer is broken.
#
# This command does NOT modify anything — it is pure read-only
# diagnostics. Safe to run at any time.

## Step 1 — bench doctor (scheduler + Redis + worker health)
# Run against hamilton-unit-test.localhost. doctor is site-scoped but
# most of its output (Redis, scheduler, workers) applies to the whole
# bench, so picking any installed site is fine.
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost doctor

## Step 2 — show-pending-jobs (anything stuck in the queue?)
# A stuck job from a previous crashed test run is the #1 cause of
# "why is this test hanging" symptoms. Check both sites because the
# queue is shared.
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost show-pending-jobs
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost show-pending-jobs

## Step 3 — Redis PING on cache (13000) and queue (11000)
# Low-level TCP PING, not frappe.cache() — so a misconfigured pool
# can't make a failed cache look healthy. Expected reply: +PONG.
(printf 'PING\r\n' | nc -w 1 127.0.0.1 13000) && echo "Redis cache (13000): PASS" || echo "Redis cache (13000): FAIL"
(printf 'PING\r\n' | nc -w 1 127.0.0.1 11000) && echo "Redis queue (11000): PASS" || echo "Redis queue (11000): FAIL"

## Step 4 — frappe.is_setup_complete() sanity check
# The definitive source for the setup_wizard-loop bug. If this returns
# False, the dev browser will loop on /app/setup-wizard on the next
# page load.
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost console <<'PY'
import frappe
ok = frappe.is_setup_complete()
print(f"frappe.is_setup_complete() on hamilton-test.localhost: {'PASS' if ok else 'FAIL'} ({ok})")
PY
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost console <<'PY'
import frappe
ok = frappe.is_setup_complete()
print(f"frappe.is_setup_complete() on hamilton-unit-test.localhost: {'PASS' if ok else 'FAIL'} ({ok})")
PY

## Step 5 — Administrator has Hamilton Operator role
# If this is missing the Asset Board 403s and every whitelisted
# endpoint in hamilton_erp.api blocks. This is also the regression
# canary for a test teardown that wiped the User table without
# running restore_dev_state.
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost console <<'PY'
import frappe
roles = {r.role for r in frappe.get_doc("User", "Administrator").roles}
ok = "Hamilton Operator" in roles
print(f"Administrator Hamilton Operator role on hamilton-test.localhost: {'PASS' if ok else 'FAIL'}")
if not ok:
    print(f"  Current roles: {sorted(roles)}")
PY

## Bench Start Recovery
# If `bench start` fails immediately with `schedule.1 stopped (rc=0)`,
# an orphan `bench schedule` process from a prior run is holding the
# scheduler FileLock. honcho treats schedule.1's clean exit as a
# reason to kill the whole process group, so web/worker/socketio go
# down with it.
#
# Diagnosis — find the orphan:
lsof ~/frappe-bench-hamilton/config/scheduler_process
ps -ax -o ppid,pid,command | awk '$1==1 && /frappe|bench/'
#
# Kill the PID that lsof prints, then rerun `bench start`.
# (PPID=1 in the awk output is the giveaway — those processes were
# adopted by launchd after honcho died without reaping them.)

## Step 6 — Report
# After all checks have run, summarize for Chris in plain English:
#   - Which layers PASSED
#   - Which layers FAILED and what to run next
# Example summary:
#   "bench doctor green, no pending jobs, Redis both ports reachable,
#    is_setup_complete True on both sites, Administrator has the role.
#    Environment is healthy — rerun /run-tests."
#
# If any probe failed, name the specific fix command, e.g.:
#   "Redis queue (11000) did not respond. Start it with:
#    redis-server ~/frappe-bench-hamilton/config/redis_queue.conf"
