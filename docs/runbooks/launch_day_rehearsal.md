# Runbook 9 — Launch-Day Rehearsal Script

**Purpose:** the timeline + concrete actions that take Hamilton from "we think we're ready" to "we are open and operational, and we have proof at every gate." Designed to be run twice — once as a dry-run rehearsal at T-3 days, then again on T-0 (launch day) for real. The dry-run reveals what doesn't work *before* the night of.

**Audience:** Chris running the launch; an on-call collaborator if available.

**Estimated time:** 2 hours of active work spread across 7 days, plus 6 hours on launch day.

**Anchor:** the existing `docs/HAMILTON_LAUNCH_PLAYBOOK.md` is the *incident-response* playbook for the launch period (post-incident workflows, escalation paths, scenario responses). This runbook is the *pre-incident* timeline that prevents most incidents from happening. Read both.

---

## Why a rehearsal exists

Software launches that skip the rehearsal share a failure mode: the team finds out at 6pm on launch day that a critical config (default company, backup key, scheduler timing, perm grid) is wrong, and there's no time to fix it. The rehearsal exists to find these on Tuesday afternoon, not Saturday at 6pm.

Two specific rehearsal goals:

1. **Prove the go-live sequence end-to-end** at T-3 against a clean staging bench, so any gap surfaces with 3 days of slack.
2. **Lock in the final config** at T-1 so launch-day actions are limited to *running the playbook*, not *making decisions*.

---

## T-7: Readiness Gate (1 hour)

**Owner:** Chris.
**Outcome:** GO or NO-GO decision for the launch window. NO-GO triggers a slip; GO commits to the launch date.

### T-7.1 — Phase 1 BLOCKER status check (15 min)

Open the Phase 1 BLOCKER PR list:

```bash
gh pr list --search "Phase 1 BLOCKER in:title" --state all --limit 20
```

Every BLOCKER must be either MERGED or DEFERRED-WITH-NOTE. There must be no PENDING BLOCKER.

For Hamilton's specific BLOCKER set as of 2026-05-02:
- PR #99 (Cash Drop owner-isolation) — must be merged
- PR #100 (Venue Session PII masking) — must be merged
- PR #122 (tip-pull schema) — must be merged
- PR #123 (zero-value SI regression pin) — must be merged
- PR #124 (orphan-invoice integrity check) — merged, verified
- Cash Reconciliation `system_expected` (Audit 1 B1) — must be either implemented OR Cash Reconciliation must be admin-gated to Phase 3 only

### T-7.2 — Run the full audit pack against current `main` (15 min)

```bash
ls docs/audits/2026-05-02_*.md
```

Confirm 6 audits exist. Read the BLOCKER and HIGH findings. For each unresolved BLOCKER, decide: merge a fix, defer with note, or NO-GO the launch.

### T-7.3 — Backup drill: verified PASS within last 90 days (5 min)

```bash
ls docs/runbooks/drill_logs/ 2>/dev/null | tail -3
```

Confirm the most recent drill log is dated within 90 days and has outcome "PASS". If it's older or missing, schedule the drill for T-6 and gate the launch on its outcome.

### T-7.4 — Staff readiness signal (10 min)

Per `HAMILTON_LAUNCH_PLAYBOOK.md` §Staff readiness — confirm:
- All operators completed the iPad walkthrough
- Manager(s) have used the cash reconciliation flow at least once on staging
- Chris has briefed the floor on the rollback protocol (paper backup if system goes down)

### T-7.5 — Decision (15 min)

Write a GO/NO-GO into `docs/inbox.md` with date and reasoning.

```bash
# In docs/inbox.md, add a section:
## YYYY-MM-DD T-7 Readiness Gate

GO/NO-GO: [GO | NO-GO]
Reasoning: <one paragraph>
Outstanding items if GO: <list>
```

If NO-GO, the rest of this runbook is shelved until the next attempt. If GO, continue.

---

## T-5 to T-3: Dry-Run Rehearsal (4 hours over 3 days)

**Owner:** Chris.
**Outcome:** every step of the launch-day script has been executed once on staging, with a record of what worked and what didn't.

### T-5.1 — Provision staging matching production-to-be (30 min)

Use `docs/runbooks/fresh_site_install.md` to provision a staging bench identical to production.

```bash
# Site name: hamilton-rehearsal.frappe.cloud
# Same Frappe Cloud tier, same backup region, same encryption settings
# Run all 13 steps from Runbook 7
```

The point: if Runbook 7 doesn't work cleanly on staging, it won't work cleanly on production launch day.

### T-5.2 — Walk through the launch-day script on staging (2 hours)

Run every step of the launch-day section below (T-0 through T+1) against the rehearsal site. Don't skip anything. If a step fails, *stop and fix it now*, not on launch day.

The rehearsal site at the end of this should look exactly like production-at-launch, but for a parallel bench.

### T-5.3 — Document anything that surprised you (30 min)

Append to this runbook (or `docs/inbox.md`) any step that took longer than expected, any command that errored, any UI surprise. The goal: by launch day, Chris has zero surprises.

### T-3.1 — Run the orphan-invoice integrity check on staging (5 min)

```bash
bench --site hamilton-rehearsal.frappe.cloud execute hamilton_erp.integrity_checks.daily_orphan_check
```

Expected: silent (no orphans). If it crashes, the fix needs to land before T-0.

### T-3.2 — Confirm CI is green on `main` (5 min)

```bash
gh run list --workflow=tests.yml --branch main --limit 3
```

Latest 3 runs on `main` must all be `completed/success`. If any failed, investigate.

### T-3.3 — Print the launch-day commit SHA (sealed) (1 min)

This is the version going to production.

```bash
cd apps/hamilton_erp
git fetch origin main
LAUNCH_SHA=$(git rev-parse origin/main)
echo "Launch SHA: $LAUNCH_SHA"
echo "$LAUNCH_SHA" > /tmp/hamilton_launch_sha.txt
```

After this point, no `main` merges land in production until post-launch (T+1+). If a critical fix is needed, it goes through a hotfix branch with explicit GO/NO-GO.

---

## T-1 (the day before launch): Final Checks (1 hour)

**Owner:** Chris. Outcome: production is the locked launch SHA, all configs are pinned, all keys are documented.

### T-1.1 — Promote the launch SHA to production (15 min)

If production is on Frappe Cloud, deploy the locked SHA.

```bash
# Frappe Cloud UI: Bench → Apps → hamilton_erp → Update to commit <LAUNCH_SHA>
# Then:
bench --site hamilton.frappe.cloud migrate
```

Wait for migrate. Then run the conformance gates from Runbook 7 §8.

### T-1.2 — Lock in the global default Company (5 min)

Per Runbook 7 §11:

```bash
bench --site hamilton.frappe.cloud execute "frappe.defaults.get_global_default" --args "['company']" 2>&1 | tail -1
# Expected: Club Hamilton
```

If not set, run the Runbook 7 §11 SQL to set it. Critical for zero-value invoice fixture and Sales Invoice currency resolution.

### T-1.3 — Confirm scheduler is enabled (5 min)

The orphan-invoice integrity check (PR #124) runs daily.

```bash
bench --site hamilton.frappe.cloud doctor 2>&1 | grep -i scheduler
# Expected: "Scheduler is enabled"
```

If disabled: `bench --site hamilton.frappe.cloud enable-scheduler`.

### T-1.3b — Confirm `System Settings.enable_audit_trail = 1` (2 min)

T1-6 (per `docs/inbox/2026-05-04_audit_synthesis_decisions.md`). Hamilton's audit-trail story depends on this Frappe-level flag. If it's off, every `track_changes: 1` setting on individual DocTypes becomes inert.

```bash
bench --site hamilton.frappe.cloud mariadb -e \
  "SELECT value FROM tabSingles \
   WHERE doctype='System Settings' AND field='enable_audit_trail'" -B -N
# Expected: 1
```

If `0` or empty: investigate `_ensure_audit_trail_enabled` in `hamilton_erp/setup/install.py`. Possible causes — Frappe upgrade renamed the field (check the test `test_audit_trail_field_present_on_pinned_frappe`), the install hook didn't fire, or a manual System Settings save reset it.

### T-1.4 — Backup retention + encryption confirmed (10 min)

Per `docs/inbox.md` T0-FC-1, T0-FC-2, T0-FC-3:
- Backup encryption: ENABLED
- Backup region: Canada Central or US East (NOT Mumbai)
- Storage allocation: ≥ 20 GB

### T-1.5 — On-call coverage confirmed (5 min)

Per `HAMILTON_LAUNCH_PLAYBOOK.md` §12 (Chris becomes single point of failure). Confirm:
- Chris is on-call for the first 24 hours
- A backup contact is identified (even if it's just "call Chris's mobile")
- Chris's mobile is in operators' iPad contacts

### T-1.6 — Print + paper-laminate the rollback protocol (15 min)

Operators must have a physical copy of the "system is down" rollback protocol per `HAMILTON_LAUNCH_PLAYBOOK.md` §7 + §11. Print:
- Manual locker assignment paper log
- Cash transaction paper log
- Chris's contact info
- "Three things to do if the iPad doesn't work" checklist

Laminate. Place on the front desk.

### T-1.7 — Sign-off

```bash
{
  echo "=== T-1 Final-Check Sign-off ==="
  date -u
  echo "Launch SHA: $(cat /tmp/hamilton_launch_sha.txt)"
  echo ""
  echo "All T-1 gates: <PASS / FAIL list>"
  echo ""
  echo "GO confirmed by Chris: yes/no"
} | tee t-1_signoff_$(date -u +%Y%m%d).log
```

If any gate failed, **NO-GO and slip the launch**. There is no critical reason to launch on a date with a known unfixed issue.

---

## T-0: Launch Day (6 hours)

**Owner:** Chris.

### T-0 -2h: Pre-open (30 min)

- 2 hours before doors-open. Arrive at the venue.
- Boot all iPads / cash drawers / printers.
- Open the Asset Board on each iPad. All 59 tiles render. No console errors.
- Open Cash Drop and Cash Reconciliation forms — confirm they load.
- Each operator does a "throwaway" test: assign a test asset to a Walk-in customer, ring a $0 service, vacate, mark clean. Confirm Asset Board updates in real time.

If any iPad's Asset Board has stale data (per Audit 2 H1 — realtime publish failure), restart that iPad's browser. If multiple iPads have stale data, the bench-side scheduler / realtime queue is broken — escalate immediately.

### T-0 -30min: Final check (15 min)

- Scheduler is running (`bench doctor`).
- Backups completed last night (`Frappe Cloud UI → Backups → Latest`).
- Chris is on-call (cell phone on, charged, audible).

### T-0 doors-open: First hour (60 min, fully attentive)

- Watch the Asset Board live. Every assignment, every vacate, every mark-clean — verify it renders.
- Listen to operators. Any "the iPad froze" or "I clicked twice" is the leading indicator of the H6 idempotency / H1 race conditions from Audit 1. Capture the symptom and the asset code.
- Watch Frappe Cloud's error log every 15 min in a second tab.

### T-0 first cash drop (mid-shift): the proof point (30 min)

- The first cash drop of the night is the proof Hamilton's cash flow works end-to-end. Operator drops; Chris (or the floor manager) reconciles.
- Walk through the reconciliation while it's fresh.
- Variance flag: should be "Clean" (assuming variance is genuinely $0). If variance flag is "Possible Theft or Error" with $0 actual variance, that's Audit 1 B1 firing — *immediately* gate Cash Reconciliation behind admin role until B1 fix lands.

### T-0 close (30 min)

- Last assignment of the night. Last vacate. Last clean.
- Run end-of-shift cash reconciliation. Variance flag should be Clean (or, if not, it should match a real variance the operator reported).
- Confirm POS Closing Entry exists in ERPNext for the day's POS Sales Invoices.
- Run the orphan-invoice integrity check manually:
  ```bash
  bench --site hamilton.frappe.cloud execute hamilton_erp.integrity_checks.daily_orphan_check
  ```
  Expected: silent. If orphans appear, investigate before close-out.

### T-0 +1 (post-close): Mini retrospective (30 min)

Right after the operators leave. While the experience is fresh:

- Note any "weird" thing that happened during the shift, even if the operator handled it. The weird-thing list is the leading indicator for Day 2's improvements.
- Confirm all tiles on the Asset Board are correct (Available / Dirty as expected based on end-of-night state).
- Take a screenshot of the dashboard. Save with the date.

---

## T+1: Morning-After Audit (45 min)

**Owner:** Chris.

### T+1.1 — Read the daily orphan-check email (5 min)

The Task 35 daily integrity check (PR #124) runs at midnight site-time. By morning, you should have an email — either "no orphans" (silent — no email) or a list of orphan SIs.

If orphans exist, walk through each and link them to the day's POS Closing Entry per the runbook in `docs/RUNBOOK.md`.

### T+1.2 — Read Frappe Cloud error logs from the launch window (15 min)

Frappe Cloud UI → Bench → Logs. Look at the last 12-24 hours.

Categorize each error/warning:
- **Operational** (lock contention, idempotency rejection): expected, file as data for Audit 1 H6 follow-up
- **Code bug** (NameError, AttributeError): incident — investigate immediately
- **Permission denied** (operator hit a perm wall): expected if the perm grid is correct, file for review

### T+1.3 — Compare T-1 vs T+1 row counts (10 min)

```bash
# Production now
bench --site hamilton.frappe.cloud mariadb -e \
  "SELECT COUNT(*) AS sessions FROM \`tabVenue Session\`; \
   SELECT COUNT(*) AS sis FROM \`tabSales Invoice\` WHERE docstatus=1; \
   SELECT COUNT(*) AS drops FROM \`tabCash Drop\`; \
   SELECT COUNT(*) AS recons FROM \`tabCash Reconciliation\` WHERE docstatus=1;" \
  -B 2>&1 | tee t+1_morning_$(date -u +%Y%m%d).log
```

Compare against expectations: did the night produce roughly the expected count of each? (Example: 30 sessions, 30 SIs submitted, 1 drop, 1 reconciliation.)

### T+1.4 — Schedule the next reviews (5 min)

- Day 7: revisit anything from T+1 that was filed as "investigate"
- Day 30: review variance-flag distribution from a month of cash reconciliations — proves Audit 1 B1 is or isn't real
- Day 90: backup/restore drill (per Runbook 8 cadence)

### T+1.5 — Sign-off

```bash
{
  echo "=== Hamilton T+1 Morning-After Audit ==="
  date -u
  echo "Launch SHA: $(cat /tmp/hamilton_launch_sha.txt)"
  echo ""
  echo "Overnight orphans: <count from email>"
  echo "Errors in 24h log: <category breakdown>"
  echo "Row counts: <list>"
  echo ""
  echo "Outstanding investigation items: <list>"
} | tee t+1_signoff_$(date -u +%Y%m%d).log
```

Commit the sign-off log to the repo.

---

## What this runbook does NOT cover

- **Specific incident-response scenarios during launch** (key already assigned, payment without session, etc.) — `HAMILTON_LAUNCH_PLAYBOOK.md` is the source.
- **Hardware setup (printers, scanners, terminals)** — separate hardware runbook needed (Phase 2).
- **Marketing / customer-facing communications** — out of scope for code runbook.
- **Rollback procedure if launch must be aborted** — covered in `HAMILTON_LAUNCH_PLAYBOOK.md` §2 (paper backup) and §7 (internet outage). The rehearsal at T-5.2 should include a paper-rollback simulation.

---

## Cross-references

- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` — the incident-response playbook for during-launch.
- `docs/runbooks/fresh_site_install.md` (Runbook 7) — the install procedure this runbook calls at T-1.
- `docs/runbooks/backup_restore_drill.md` (Runbook 8) — the backup drill that gates T-7.3.
- `docs/audits/2026-05-02_*.md` — the 6 audits whose BLOCKER / HIGH findings gate T-7.1 and T-7.2.
- `docs/inbox.md` T0-FC-* items — Frappe Cloud production-readiness gates (encryption, region, storage).

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
