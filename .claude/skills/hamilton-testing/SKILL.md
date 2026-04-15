# Hamilton ERP — Testing Skill

## Test site

`hamilton-unit-test.localhost` — dedicated test site with `allow_tests = true`.
**NEVER** run tests on `hamilton-test.localhost` (the dev browser site) — it corrupts
setup wizard state, roles, and causes 403 loops.

## Bench location

`~/frappe-bench-hamilton`

## Run a single test module

```bash
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests \
  --app hamilton_erp --module hamilton_erp.tests.[test_file_name]
```

Replace `[test_file_name]` with one of the 5 core modules below.

## Run the full suite

```bash
cd ~/frappe-bench-hamilton && source env/bin/activate && \
  ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-unit-test.localhost run-tests \
  --app hamilton_erp
```

Or use the `/run-tests` slash command which runs all 14 modules individually.

## The 5 core test files

1. `test_lifecycle.py` — 29 tests, core lifecycle methods
2. `test_locks.py` — 3 tests, Redis + FOR UPDATE lock
3. `test_venue_asset.py` — 17 tests, doctype controller
4. `test_additional_expert.py` — 45 tests, expert edge cases
5. `test_checklist_complete.py` — 43 + 11 skipped, checklist items as Python

## Baseline

270 passing / 7 skipped across the 5 core modules.
Any drop in passing count is a regression — **stop and report it**.

## Workflow

Always run a **single test module first** before running the full suite.
This catches failures fast without waiting for all 14 modules.
