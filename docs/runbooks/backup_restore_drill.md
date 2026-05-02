# Runbook 8 — Backup / Restore Drill

**Purpose:** the *exercise* of doing a real restore, not the policy. Hamilton's backup *configuration* lives in `docs/RUNBOOK_BACKUP.md`; that doc is the source of truth for what gets backed up, retention, and the policy decisions. This runbook is the quarterly checklist that proves the backups actually work.

**Audience:** Chris, performing the drill solo. Estimated time: 90 minutes for a full restore-to-staging drill, 30 minutes for a partial-record restore drill.

**Cadence:** quarterly. First drill must be completed before Hamilton's go-live. Subsequent drills land on the calendar quarter (e.g. 2026-08-01, 2026-11-01, 2027-02-01, 2027-05-01).

**Why this exists:** an untested backup is a hope, not a backup. Every venue I've watched go down had backups that nobody had ever restored from. Common failure modes: backup file is encrypted with a key nobody remembers; backup is from before a critical migration; backup region is unreachable in a regional outage; restore process takes 12 hours and operations stop for a day. The drill reveals these *before* the real disaster.

---

## Pre-drill (one-time setup, 15 min)

Done once, then reused every quarter. Skip to the drill section if these are already in place.

### 0.1 — Provision a permanent staging bench

A **separate** Frappe Cloud bench that exists solely for restore drills. Cheapest tier ($10/mo, per `docs/RUNBOOK_BACKUP.md` §6) is fine; it's idle 99% of the time.

**Naming convention:** `hamilton-restore-drill.frappe.cloud` (or local equivalent).

**Why separate:** restoring to the production bench during a drill takes production offline. Restoring to a fresh bench every quarter wastes 30 min of provisioning. A persistent staging bench is the right balance.

### 0.2 — Confirm production backup encryption is on

Before any drill, confirm production backups are encrypted (per `docs/inbox.md` T0-FC-1). The drill is meaningless if the backups can't be decrypted.

```bash
# Frappe Cloud UI: Bench → Backups → Encryption: ENABLED
# Encryption key is stored in Frappe Cloud's vault; document the key location
# in 1Password or equivalent under "Hamilton — Frappe Cloud backup encryption key"
```

### 0.3 — Document the encryption key location

Write down (in 1Password):
- Frappe Cloud bench name
- Backup encryption key reference (Frappe Cloud may show it as a download or as a settings field)
- Whom to contact at Frappe Cloud support if the key is lost

**Stop the drill if you can't locate this.** A drill against unencrypted-able backups is theater.

### 0.4 — Backup-region check

Verify production backup region is **not Mumbai** (per `docs/inbox.md` T0-FC-2). Canada Central or US East are both fine; Mumbai has incident-history concerns.

```bash
# Frappe Cloud UI: Bench → Settings → Backup Region: Canada Central (or US East)
```

---

## The Drill (90 min)

### Phase A — Prepare (10 min)

**A.1 — Snapshot the current production state**

Before the drill, capture a "what production looked like at the time of this drill" snapshot for the post-drill comparison.

```bash
# Production bench
bench --site hamilton.frappe.cloud mariadb -e \
  "SELECT COUNT(*) AS venue_assets FROM \`tabVenue Asset\`; \
   SELECT COUNT(*) AS active_sessions FROM \`tabVenue Session\` WHERE status='Active'; \
   SELECT COUNT(*) AS submitted_recons FROM \`tabCash Reconciliation\` WHERE docstatus=1; \
   SELECT MAX(modified) AS latest_si FROM \`tabSales Invoice\`;" \
  -B 2>&1 | tee drill_prod_snapshot_$(date -u +%Y%m%dT%H%M%SZ).log
```

Keep the file. It's the comparison baseline for Phase D.

**A.2 — Pick the backup to restore**

Open Frappe Cloud → Bench → Backups. Pick a backup that is **24–48 hours old** (not the latest — testing the latest hides issues that only appear in older backups). Note the backup file's:
- Backup date / time
- Frappe Cloud's stated size (DB + private files + public files separately)
- Any "encrypted" indicator

**A.3 — Stop the staging bench (clean slate)**

```bash
# Frappe Cloud UI: Bench (staging) → Stop
# Wait until status is "Stopped"
```

If the staging bench has a leftover restored site from a previous drill, drop it now:
```bash
bench drop-site hamilton-restore-drill.frappe.cloud --no-backup --force
```

### Phase B — Restore (30–60 min, mostly waiting)

**B.1 — Download the backup files**

Frappe Cloud lets you download backups (or restore to a sibling bench directly). For a restore-drill, download:
- `*-database.sql.gz`
- `*-files.tar` (private files)
- `*-public-files.tar` (public files)
- `*-site_config_backup.json`

Three separate files for the data; one for the site config.

Time this. **The download time is part of the drill metric** — write it down. If a full backup download takes 8 hours, that's the worst-case RTO floor for total-site loss.

**B.2 — Initiate the restore on staging**

Two paths. Pick one.

**Path 1 — Frappe Cloud UI restore (preferred):**
- Frappe Cloud bench dashboard → Sites → New Site → "Restore from Backup"
- Upload the database SQL gz, public/private files, and the encryption key when prompted.
- Site name: `hamilton-restore-drill.frappe.cloud`.

**Path 2 — CLI restore (when UI fails or for local benches):**
```bash
cd /path/to/staging/frappe-bench
bench --site hamilton-restore-drill.frappe.cloud --force restore \
  /path/to/downloaded/database.sql.gz \
  --with-private-files /path/to/downloaded/private-files.tar \
  --with-public-files  /path/to/downloaded/public-files.tar \
  --encryption-key      "$(cat /path/to/key.txt)"
```

Time this end-to-end. **This is the production RTO for a partial-data scenario.** Document.

**B.3 — Wait for completion**

The restore typically takes 10–30 min for a small bench. Frappe Cloud UI shows progress. Don't multitask; watch for errors.

If the restore fails:
- Common causes: wrong encryption key (90% of failures), corrupt backup tar, version mismatch between backup-time Frappe and current bench Frappe.
- Document the failure in the drill log.
- **The drill counts as PASSING ONLY if the restore completes successfully end-to-end.** If it fails, the drill outcome is "FAIL" and the action item is to fix backups before next quarter.

### Phase C — Migrate + boot (10 min)

**C.1 — Run migrate on the restored site**

```bash
bench --site hamilton-restore-drill.frappe.cloud migrate
```

This catches the case where the restored DB was from an older Frappe / ERPNext version and the current bench has newer migrations. **Time this** — migrations on a real-world restore can take 20+ min if a major schema change landed between backup-time and now.

**C.2 — Start the bench**

```bash
bench --site hamilton-restore-drill.frappe.cloud use
bench start &> drill_bench.log &
```

Wait for redis ports + web server.

**C.3 — Smoke-check the restored site**

Open the staging URL in a browser. Log in as Administrator. Verify:
- ✅ Login succeeds
- ✅ Asset Board page loads (`/app/asset-board`)
- ✅ Asset count matches snapshot (Phase A.1)

### Phase D — Validate (15 min)

This is the actual point of the drill: prove the restored data is *exactly* what production had at backup time.

**D.1 — Compare row counts against the Phase A.1 snapshot**

```bash
bench --site hamilton-restore-drill.frappe.cloud mariadb -e \
  "SELECT COUNT(*) AS venue_assets FROM \`tabVenue Asset\`; \
   SELECT COUNT(*) AS active_sessions FROM \`tabVenue Session\` WHERE status='Active'; \
   SELECT COUNT(*) AS submitted_recons FROM \`tabCash Reconciliation\` WHERE docstatus=1; \
   SELECT MAX(modified) AS latest_si FROM \`tabSales Invoice\`;" \
  -B 2>&1 | tee drill_restored_snapshot_$(date -u +%Y%m%dT%H%M%SZ).log
```

Diff against `drill_prod_snapshot_*.log`. Acceptable difference: **whatever was modified between backup-time and Phase A.1 capture-time**. (E.g., production had 12 SIs added in the 24h gap; restored site has the older count. That's expected — the backup is older than production.)

**Unacceptable differences:**
- Restored count is *smaller* than backup-time count (some data didn't restore)
- Restored Venue Asset count != 59 (seed data lost)
- Critical DocTypes are empty when they shouldn't be (Hamilton Settings, POS Profile)

**D.2 — Spot-check a real record**

Pick a random Sales Invoice from the day before backup-time. Verify it exists on the restored site, has the same `grand_total`, same `customer`, same `posting_date`, same line items.

```bash
# Production
bench --site hamilton.frappe.cloud mariadb -e \
  "SELECT name, grand_total, customer, posting_date FROM \`tabSales Invoice\` \
   WHERE posting_date = '<backup_date>' ORDER BY creation LIMIT 1" -B
# Note the SI name + grand_total

# Restored
bench --site hamilton-restore-drill.frappe.cloud mariadb -e \
  "SELECT name, grand_total, customer, posting_date FROM \`tabSales Invoice\` \
   WHERE name='<the SI name>'" -B
# Expected: same values
```

If the values differ, the backup is corrupt or the restore was incomplete. **FAIL the drill.**

**D.3 — Test that the orphan-invoice integrity check (Task 35) runs cleanly on restored data**

```bash
bench --site hamilton-restore-drill.frappe.cloud execute hamilton_erp.integrity_checks.daily_orphan_check 2>&1 | tail -10
```

Expected: no exception, returns silently if no orphans, or logs orphans cleanly. If the check itself crashes, the restored DB has a schema issue.

**D.4 — Test that lifecycle works on restored data (Asset Board round-trip)**

```bash
bench --site hamilton-restore-drill.frappe.cloud console <<'EOF'
import frappe
asset = frappe.db.get_value('Venue Asset',
                            {'status':'Available'},
                            ['name','status'], as_dict=True)
print(f"Available asset on restored site: {asset.name} — status={asset.status}")
EOF
```

Expected: prints an asset name. If "no asset returned", the seed data may have been corrupt or the restore lost it.

### Phase E — Sign-off (5 min)

**E.1 — Write the drill log**

```bash
{
  echo "=== Hamilton backup/restore drill — sign-off ==="
  echo "Drill date (UTC): $(date -u)"
  echo "Operator: Chris"
  echo ""
  echo "Backup chosen:"
  echo "  Date: <enter the backup date>"
  echo "  Size: <enter the size from Frappe Cloud>"
  echo ""
  echo "Times:"
  echo "  Phase B.1 download:           <fill in>"
  echo "  Phase B.2 restore:            <fill in>"
  echo "  Phase C.1 migrate:            <fill in>"
  echo "  Phase D total validation:     <fill in>"
  echo ""
  echo "Validation outcome:"
  echo "  Row counts match expected:    <yes/no, attach drill_*.log>"
  echo "  Spot-check SI matches:        <yes/no>"
  echo "  Orphan check runs clean:      <yes/no>"
  echo "  Lifecycle round-trip works:   <yes/no>"
  echo ""
  echo "Drill outcome: <PASS / FAIL>"
  echo ""
  echo "Issues encountered:"
  echo "  <list issues, or 'none'>"
  echo ""
  echo "Action items for next drill:"
  echo "  <list>"
} > drill_signoff_$(date -u +%Y%m%dT%H%M%SZ).md
```

**E.2 — Commit the sign-off log to the repo**

```bash
cp drill_signoff_*.md /path/to/hamilton_erp/docs/runbooks/drill_logs/
cd /path/to/hamilton_erp
git checkout -b docs/drill-log-$(date -u +%Y-%m-%d)
git add docs/runbooks/drill_logs/
git commit -m "docs(runbook): backup/restore drill log $(date -u +%Y-%m-%d)"
git push -u origin HEAD
gh pr create --title "..." --body "Quarterly drill PASS/FAIL"
```

The drill log lives in the repo permanently — quarterly history of every drill, in one place.

**E.3 — Stop the staging bench**

```bash
# Frappe Cloud UI: Bench (staging) → Stop
```

Save Hamilton the $10/mo idle cost between drills.

---

## Quick-version: 30-min partial-record restore drill

Once the full-restore drill has passed at least once, alternate quarters can do a faster partial-record drill. This validates the same encryption + accessibility, without spending an hour on a full restore.

1. Pick a backup 7 days old.
2. Frappe Cloud UI → "Restore single record" (if available) OR download the SQL.gz, grep for the record manually:
   ```bash
   gunzip -c backup-database.sql.gz | grep "VA-0001" | head
   ```
3. Verify the record's data matches what production had 7 days ago.
4. Sign off as a partial drill.

Don't substitute partial drills for the full drill more than 1 quarter in 4. Full drills are the authoritative check.

---

## What this runbook does NOT cover

- **Configuration of Frappe Cloud's backup schedule** — that's `docs/RUNBOOK_BACKUP.md` §1 and §2.
- **Retention policy decisions** — `docs/RUNBOOK_BACKUP.md` §12.
- **Disaster-scenario branching** — `docs/RUNBOOK_BACKUP.md` §10 covers the 5 likely disaster types.
- **Off-site / S3 / external backup** — Frappe Cloud handles primary; if a second-tier backup is added, document it separately.

---

## Cross-references

- `docs/RUNBOOK_BACKUP.md` — the policy / configuration runbook this drill validates.
- `docs/inbox.md` T0-FC-1 (encryption), T0-FC-2 (region), T0-FC-3 (storage) — pre-launch backup gates.
- `.github/workflows/tests.yml` — CI's test_site setup is a related but distinct exercise.
- Runbook 7 (`docs/runbooks/fresh_site_install.md`) — restore-from-backup is similar to a fresh install plus existing data; the conformance gates from Runbook 7 §8 apply to restored sites too.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
