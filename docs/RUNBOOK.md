# Hamilton ERP — Operational Runbook

**Audience:** Whoever is on-call when Hamilton ERP misbehaves at 2 a.m. — Chris, a future operator, or a senior Frappe contractor brought in for an incident.
**Scope:** Production (Frappe Cloud at `hamilton-erp.v.frappe.cloud`) plus local-dev and unit-test bench.
**Canonical:** This document is assembled from `docs/lessons_learned.md`, `docs/decisions_log.md`, `CLAUDE.md` "Common Issues", and the production-handoff audits in `docs/inbox/archive/`. Where this runbook conflicts with those sources, treat the source as canonical and update this runbook.

> **Production safety reminder.** Hamilton ERP runs blind cash control (DEC-005), three-layer locking on asset state changes (DEC-019, `coding_standards.md` §13), and atomic session-number generation (DEC-033). Do not modify any of those invariants while resolving an incident. If a fix would cross one of those boundaries, page Chris and stop.

---

## 0. Quick Reference

| Symptom | Most-likely cause | First action |
|---|---|---|
| Asset Board renders empty | Seed wiped without re-seed | §3.1 |
| Asset Board returns 403 to Administrator | `Hamilton Operator` role lost from Administrator | §3.2 |
| Bench serves setup-wizard instead of login | `Installed Application.is_setup_complete=0` | §3.3 |
| `TimestampMismatchError` on asset save | Cached doc instance used inside lock | §4.1 |
| `LockContentionError` on every transition | Stale Redis key from a previous crash | §4.2 |
| `session_number` empty on new sessions | Redis down OR `before_insert` regression | §4.3 |
| Tests show `DocType Payment Gateway not found` | `frappe/payments` not installed in this bench | §6.1 |
| Operator sees expected-cash totals | DEC-005 violation — STOP, page Chris | §7.1 |
| Bench process won't start | Redis or MariaDB down | §5.1 |
| Realtime updates silent across tabs | RQ workers / Redis queue down | §5.2 |
| Frappe Cloud deploy didn't take | Migration ran but assets not rebuilt | §8.2 |

---

## 1. Where to Look First

### Logs and dashboards
- **Frappe Cloud Error Log:** Desk → "Error Log" doctype, sort by `creation` descending. Hamilton has no external error monitoring (Sentry deferred — `docs/inbox.md` 2026-04-29 §10 finding 9). Read this first on every incident.
- **Frappe Cloud Scheduled Job Log:** Desk → "Scheduled Job Log". As of 2026-04-30 there are NO scheduled jobs registered; `tasks.py` was deleted (Amendment 2026-04-30 in `decisions_log.md`). Any rows in here means a Phase 2 reintroduction landed.
- **MariaDB slow-query log:** Frappe Cloud bench → `bench --site SITE mariadb` → `SHOW VARIABLES LIKE 'slow_query%'` then check the configured path.
- **Browser console (asset board):** Asset Board is vanilla JS — `console.log` calls in `asset_board.js` show up directly in DevTools. JS errors there usually mean a payload field changed without the JS being updated (e.g. PR #24 added `guest_name` and `oos_set_by`).
- **Redis:** `redis-cli -p 13000 KEYS 'hamilton:*'` (local bench port from LL-025; production uses Frappe Cloud's managed Redis — port may differ).

### Health-check commands
- `/debug-env` slash command — `.claude/commands/debug-env.md` — confirms Redis, MariaDB, and the test site are healthy.
- `bench --site SITE doctor` — Frappe's built-in scheduler/queue health check.
- `bench --site SITE show-pending-jobs` — what's stuck in the RQ queue.

---

## 2. Logging On to Production

Frappe Cloud sites are accessed via:
- **Desk URL:** `https://hamilton-erp.v.frappe.cloud/app`
- **bench:** Frappe Cloud's web terminal — Apps & Sites → hamilton-erp → bench shell. Local clones do NOT have access to production data; do not attempt to debug production via local commands.
- **GitHub deploy:** push to `main` triggers an auto-deploy in ~3 minutes. CI must be green or Frappe Cloud refuses the deploy.

For ANY destructive command on production:
1. **Read `docs/lessons_learned.md` LL-030** ("Production recovery — rollback before live debugging") FIRST.
2. Take a Frappe Cloud snapshot before proceeding (Frappe Cloud → Backups → "Create Backup Now").
3. If you cannot reproduce the issue on the local bench against `hamilton-test.localhost`, do not attempt a fix in production — page Chris.

---

## 3. Asset Board Recovery

### 3.1 — Asset Board renders empty

**Symptom:** Operator opens `/app/asset-board`, the grid is blank or shows fewer than 59 tiles.

**Most-likely cause:** A test or migration wiped `tabVenue Asset` without restoring the seed. `test_environment_health.test_59_assets_exist` is designed to catch this in CI; if it slipped past CI, the seed was wiped after CI ran.

**Diagnose:**
```bash
bench --site SITE console
>>> import frappe; frappe.db.count("Venue Asset")
```
- 0 → full wipe; run `_seed_hamilton_data` (below).
- 1–58 → partial wipe; the seed is idempotent so re-running fills the gaps.
- ≥59 → not a wipe; check the JS payload via DevTools instead — likely a frontend regression.

**Fix:**
```bash
bench --site SITE console
>>> from hamilton_erp.patches.v0_1.seed_hamilton_env import execute
>>> execute()
>>> frappe.db.commit()
```
Idempotent — safe to run repeatedly. Verify with `frappe.db.count("Venue Asset") == 59`.

If this happens in production: take a snapshot first, then re-seed in the bench shell. If it recurs, page Chris — something is wiping the table programmatically.

### 3.2 — Asset Board returns 403 to Administrator

**Symptom:** Administrator opens `/app/asset-board` → 403 Forbidden.

**Cause:** Administrator lost the `Hamilton Operator` role. Tests have wiped User roles in the past (LL-001 traces).

**Fix:**
```bash
bench --site SITE console
>>> from hamilton_erp.test_helpers import restore_dev_state
>>> restore_dev_state()
>>> frappe.db.commit()
```
Or manually:
```python
admin = frappe.get_doc("User", "Administrator")
if "Hamilton Operator" not in {r.role for r in admin.roles}:
    admin.append("roles", {"role": "Hamilton Operator"})
    admin.save(ignore_permissions=True)
```

### 3.3 — Bench serves setup-wizard instead of login

**Symptom:** Visiting the site URL redirects to `/setup-wizard`. Login page never appears. Most visible after a deploy or `bench migrate`.

**Cause:** `tabInstalled Application.is_setup_complete=0` (per LL-001) AND `tabDefaultValue` has a `desktop:home_page='setup-wizard'` row. Both are healed by `setup/install.py:_ensure_no_setup_wizard_loop`, which runs from BOTH `after_install` and `after_migrate`. If the wizard loop is back, one of those hooks didn't fire.

**Diagnose:**
```bash
bench --site SITE console
>>> frappe.db.sql("SELECT app_name, is_setup_complete FROM `tabInstalled Application`", as_dict=True)
>>> frappe.db.sql("SELECT * FROM tabDefaultValue WHERE defkey='desktop:home_page'", as_dict=True)
```

**Fix:** Run the heal manually:
```bash
bench --site SITE console
>>> from hamilton_erp.setup.install import _ensure_no_setup_wizard_loop
>>> _ensure_no_setup_wizard_loop()
>>> frappe.db.commit()
>>> frappe.clear_cache(doctype="Installed Application")
```

Then reload the browser. If it returns to setup-wizard within minutes, something is flipping `is_setup_complete=0` actively — page Chris.

---

## 4. Concurrency and Locking Issues

### 4.1 — TimestampMismatchError on asset save

**Symptom:** Front desk operator taps an action; asset state change throws `TimestampMismatchError`.

**Cause:** A controller is using a cached `Venue Asset` doc instance and the row underneath was modified by another request. Per `coding_standards.md` §13, you MUST `frappe.get_doc()` fresh inside the lock, never reuse a cached instance.

**Fix:** In the controller path, replace cached references with a fresh fetch. This is a code-fix, not a runtime fix — open a PR. If it recurs at runtime, page Chris and document the call chain that produced the cached read.

### 4.2 — LockContentionError on every transition

**Symptom:** Operators see "Asset is being modified by another operator. Try again." for every tap, even when no one else is acting.

**Cause:** A previous Frappe / Claude / test crash left a Redis key with no holder. The key TTL is 15 seconds (per `locks.py:LOCK_TTL_MS`), so the natural fix is to wait 15s.

**Fix:**
1. Wait 15 seconds and retry. If the issue clears, stop here.
2. If it persists past 15s, the lock holder is alive but stuck. On the test/dev bench:
   ```bash
   redis-cli -p 13000 DEL hamilton:asset_lock:VA-XXXXX
   ```
3. **NEVER `FLUSHDB` on production.** Frappe Cloud's Redis hosts session data, RQ queue state, and DB cache. A flush logs out every user and drops every queued job.
4. If contention persists across multiple assets → systemic Redis issue → §5.1.

### 4.3 — session_number not populated

**Symptom:** New `Venue Session` rows have `session_number=NULL` or duplicate values.

**Cause:** Per LL-007, the session number is generated by Redis INCR (with DB-fallback reconciliation) inside `VenueSession.before_insert`. NULL means either Redis is down or the controller's `before_insert` isn't running.

**Diagnose:**
```bash
bench --site SITE doctor          # Redis up?
bench --site SITE show-pending-jobs  # RQ alive?
```
Then check the controller is wired:
```python
import inspect
from hamilton_erp.hamilton_erp.doctype.venue_session.venue_session import VenueSession
inspect.getsource(VenueSession.before_insert)
```

**Fix:** If Redis is down, see §5.1. If `before_insert` is missing, the doctype was modified without re-syncing — run `bench --site SITE migrate` (production deploy: redeploy from main branch).

---

## 5. Infrastructure Health

### 5.1 — Bench process won't start

**Symptom:** `bench start` exits immediately, or pages don't load.

**Cause:** Redis or MariaDB is down. Frappe requires both at boot.

**Diagnose:**
```bash
brew services list | grep -E 'mariadb|redis'   # local-bench
bench --site SITE doctor                       # any bench
```

**Fix (local bench):**
```bash
brew services start mariadb@12.2.2
brew services start redis
```

**Fix (Frappe Cloud):** Frappe Cloud's managed Redis and MariaDB are not user-restartable. Open a Frappe Cloud support ticket. While waiting, the site is hard-down — there is no graceful degradation path.

### 5.2 — Realtime updates silent across tabs

**Symptom:** Operator A taps "Vacate" on R001; Operator B's tab does not update until refresh.

**Cause:** Realtime broadcast (`hamilton_asset_status_changed` event) is wired in `realtime.py` and fires `after_commit=True`. Silent updates mean either:
- RQ worker is down (events queued but not delivered)
- Redis pub/sub channel not reachable
- Browser dropped the SocketIO connection

**Diagnose:**
```bash
bench --site SITE doctor
bench --site SITE show-pending-jobs
```
Browser-side: open DevTools → Network → WS — confirm the SocketIO connection is open and receiving messages.

**Fix:**
- If RQ worker is down: `bench start` (local) or restart in Frappe Cloud bench shell.
- If Redis is down: §5.1.
- If only one specific browser is silent: hard-refresh that tab. SocketIO can drop without reconnecting.

---

## 6. Test Suite Recovery

### 6.1 — `DocType Payment Gateway not found` errors

**Symptom:** 6 setUpClass errors in the doctype tests (shift_record, comp_admission_log, cash_reconciliation, cash_drop, venue_session, asset_status_log) — all `DoesNotExistError: DocType Payment Gateway not found`.

**Cause:** `frappe/payments` is not installed in this bench. Frappe's `IntegrationTestCase.setUpClass` walks every Link-field on the test's DocType recursively; the chain ends at Payment Gateway which lives in `frappe/payments`, not vanilla frappe + erpnext.

**Fix (local dev):**
```bash
bench get-app https://github.com/frappe/payments
bench --site hamilton-unit-test.localhost install-app payments
```
**Fix (CI):** Already handled — `.github/workflows/tests.yml` installs `frappe/payments@develop`.
**Fix (production):** May or may not be needed — see `docs/inbox.md` 2026-04-28 entry. If Hamilton ever uses Payment Entry / Payment Reconciliation, install it; otherwise it's a test-time-only dependency.

### 6.2 — `test_59_assets_exist` fails locally

**Symptom:** `test_environment_health.test_59_assets_exist` fails with `Expected 59 Venue Assets, found N` where N != 59.

**Cause:** Per the test docstring: "If this fails, a test wiped the asset table without running `seed_hamilton_env.execute()` in its tearDownClass." This test is a deliberate canary — it trips on contamination, telling you another test misbehaved.

**Fix:** Re-seed via the bench console (§3.1 Fix). Then identify which test class contaminated the table — `git log -p -- hamilton_erp/test_*.py` for the recent changes. Fix the offending tearDown.

The new `test_fresh_install_conformance.py` (PR #56, 2026-04-30) uses existence-only assertions on R001-R026 / L001-L033 specifically to NOT trip on contamination — because what it pins is the install contract, not the live state.

### 6.3 — Redis lock contention during tests

**Symptom:** Test `LockContentionError` even when the test should be the only writer.

**Cause:** A previous crashed test left a Redis key. The lock TTL is 15s.

**Fix:**
- Wait 15s and re-run the test.
- Test site only: `redis-cli -p 13000 FLUSHDB`. **NEVER on dev or prod.**

---

## 7. Cash Control Incidents

### 7.1 — Operator sees expected-cash totals — STOP

**Symptom:** Anywhere in the app, an operator (Hamilton Operator role) can see expected cash totals or variance.

**Cause:** DEC-005 violation. The blind cash control invariant is that operators NEVER see expected/actual/variance. Cash Reconciliation is Hamilton Manager+ only; the standard POS Closing Entry is scrubbed of Hamilton Operator perms by `_block_pos_closing_for_operator`.

**Fix:**
1. **STOP** — this is a P0 cash-handling regression.
2. Page Chris immediately.
3. Take a Frappe Cloud snapshot.
4. Do not attempt to "patch around" the visibility — find the entry point that's exposing the field. Likely culprits:
   - A new Custom DocPerm row was added (run install.py:_block_pos_closing_for_operator manually to remove it)
   - Field masking (`mask: 1`) was supposed to be in place but isn't (Task 25 item 7 — see `docs/research/pipeda_venue_session_pii.md` and `docs/permissions_matrix.md`)
   - A new whitelisted endpoint returns the field without masking

---

## 8. Deploy and Migration Issues

### 8.1 — `bench migrate` fails

**Symptom:** `bench migrate` errors out.

**Cause:** Almost always one of:
- A patch in `patches.txt` raised — read the traceback.
- A DocType JSON change is incompatible with existing data (e.g. NOT NULL added with no default).
- `frappe/payments` link-field walk finds an uninstalled app (§6.1).

**Fix:** Read the traceback first. Common patterns:
- "DocType X not found" → install the missing app or revert the link.
- Patch traceback → fix the patch or comment out the line in `patches.txt` and re-run; do NOT delete the patch from `patches.txt` since it tracks completion state.
- Schema mismatch → write a `pre_model_sync` patch that migrates existing rows before the schema flip.

LL-003 covers the `scheduler_events` migrate hazard — changes to scheduler config require migrate.

### 8.2 — Frappe Cloud deploy didn't take

**Symptom:** GitHub push merged to main, ~3 minutes elapsed, but the change isn't visible on production.

**Cause:** Frappe Cloud auto-deploys but JS asset rebuilds can lag or fail silently if the build step errors. The migrate phase usually succeeds but the `bench build` step may not.

**Diagnose:**
- Frappe Cloud → Deploys → most recent deploy → check status.
- If the deploy shows "Success": hard-refresh the browser; the JS file may be cached.
- If the deploy shows "Failed" or stalled: read the deploy log in Frappe Cloud's UI.

**Fix:**
- Trigger a manual rebuild from Frappe Cloud → Apps & Sites → hamilton-erp → Bench → Deploy.
- If it keeps failing, page Chris with the deploy log link.

---

## 9. Routine Operations

### Pre-deploy checklist (before pushing to Frappe Cloud)
1. All entries in `docs/feature_status.json` show `"passes": true`.
2. `/run-tests` — zero failures.
3. `bench migrate` locally — clean.
4. No debug `print()` or `frappe.log()` in code.
5. Check 3-AI review checkpoint (Task 9, 11, 21, 25 per `CLAUDE.md`).
6. Push to GitHub — auto-deploys in ~3 minutes.

### Daily operator handoff (per shift)
- Cash Drop entered for the shift's takings.
- Cash Reconciliation completed by Hamilton Manager (NOT Operator).
- Asset Board state matches physical state — any "Out of Service" tile has a documented reason.
- No "Active" Venue Sessions older than `expected_stay_duration + grace_minutes` (overtime sessions need explicit operator action — vacate or extend).

### Weekly maintenance
- Review `tabError Log` for new error types since last week.
- Review `tabScheduled Job Log` for failures (currently empty since `tasks.py` was deleted; once Phase 2 reintroduces overtime detection, this becomes a real check).
- Check Frappe Cloud → Backups — confirm daily backups are running.

---

## 10. Escalation

| Tier | Trigger | Action |
|---|---|---|
| Tier 0 | Anything in §3 / §4 that resolves on the first try | Document in `docs/lessons_learned.md` if it was a new pattern |
| Tier 1 | Recurring issue, or any §7 incident | Page Chris (text + email) |
| Tier 2 | Production data loss risk, OR fix would change a DEC-0XX | STOP — do not act without Chris's explicit approval |
| Tier 3 | Frappe Cloud platform issue (Redis / MariaDB / deploy infra) | Open a Frappe Cloud support ticket; copy deploy log + error log |

**Chris's contact:** csrnicek@yahoo.com (per `hooks.py:app_email`).

**For senior-Frappe-developer escalation** (a contractor brought in mid-incident), share these files in this order:
1. This runbook
2. `docs/decisions_log.md` (DEC-001 through DEC-061 + amendments)
3. `docs/coding_standards.md` (especially §13 locking)
4. `docs/lessons_learned.md` (the recurring-failure catalogue)

---

## Maintenance

**This runbook should be updated when:**
- Any new DEC-NNN that affects production behaviour is added (cross-link from the relevant section).
- A new failure mode is observed in production or in tests that wasn't covered.
- An existing fix recipe is found to be wrong or incomplete (update the recipe; don't leave stale text).
- Frappe Cloud platform changes (Redis port, deploy mechanism, monitoring options).

**This runbook should NOT be:**
- A duplicate of `docs/lessons_learned.md`. Cross-link instead.
- A duplicate of `docs/coding_standards.md`. Reference the relevant §.
- A code-walkthrough. The audience is on-call ops, not a code reviewer.

**Source-of-truth rule:** when this runbook conflicts with `docs/decisions_log.md`, the decisions log wins. Update this runbook to match.

---

*Created 2026-04-30 from CLAUDE.md "Common Issues" + lessons_learned.md + production_handoff_audit_merged_2026-04-25.md as part of pre-Task-25 handoff prep (Stack #5 of the autonomous overnight stack).*
