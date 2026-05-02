# Hamilton ERP — Backup & Restore Runbook

**Audience:** Chris Srnicek (owner / system admin) and any future ops staff.
**Scope:** Production site `hamilton-erp.v.frappe.cloud` on Frappe Cloud. Covers what is backed up, how to restore it, and what to do when things go wrong.
**Companion doc:** `docs/RUNBOOK.md` covers incident response. This runbook covers data preservation and recovery only.
**Status:** Hamilton has not launched yet. Sections marked **[PRE-LAUNCH]** describe steps that must be completed before go-live. Everything else describes the ongoing operating posture once live.

---

## 0. Quick Reference

| Scenario | Action | Section |
|---|---|---|
| Routine recovery (delete wrong record, etc.) | Frappe Cloud dashboard → Backups → Restore | §4 |
| Single record deleted by mistake | Partial restore via bench console | §5 |
| Quarterly restore test | Staging site restore + smoke test | §6 |
| Pre-launch setup | Work through pre-launch checklist | §11 |
| Want to know what's backed up | Read §1 and §3 | §1, §3 |

---

## 1. What Gets Backed Up Automatically (Frappe Cloud)

Frappe Cloud runs **daily automatic backups** for every hosted site. You do not have to do anything to enable this — it happens by default.

Each daily backup contains:
- The full MariaDB database (every DocType record, custom fields, configured fixtures)
- Public files (logos, images, email attachments accessible without login)
- Private files (Sales Invoice PDFs, document attachments that require login to view)

**Retention:** Frappe Cloud's default is approximately 30 days of daily backups. Verify the exact retention for Hamilton's plan at:
> Frappe Cloud dashboard → Apps & Sites → hamilton-erp → **Backups** tab

**Important limitation:** These are consumer-grade backups. They are reliable for routine "I need yesterday's data" recovery. They are NOT a regulatory-grade audit trail. For CRA (Canada Revenue Agency) compliance, you need your own offsite copies with 7-year retention — that is covered in §2 and §12.

---

## 2. What Gets Backed Up Manually (Additional Safety)

The Frappe Cloud daily backups are your first safety net. The manual weekly backup is your second, independent safety net — stored somewhere Frappe Cloud has no access to.

### Why bother with manual backups?

- Frappe Cloud keeps ~30 days. CRA requires 6 years. You need your own long-term archive.
- If Frappe Cloud itself has a major incident, you want a copy that isn't on their infrastructure.
- The manual backup also captures `site_config.json`, which Frappe Cloud does not always include in automated backups.

### How to run a manual backup

**[PRE-LAUNCH]** This requires a Frappe Cloud **private bench** plan (not the shared/auto-deploy plan). SSH access is only available on private bench plans. Confirm your plan has SSH before go-live.

Once SSH is available:

1. Open a terminal on your MacBook.
2. Connect to the Frappe Cloud bench shell: Frappe Cloud dashboard → Apps & Sites → hamilton-erp → **Bench Shell** (or use the SSH key you configured).
3. Run the backup command:
   ```bash
   bench --site hamilton-erp.v.frappe.cloud backup --with-files
   ```
4. The command creates a `.tar.gz` file in `~/frappe-bench/sites/hamilton-erp.v.frappe.cloud/private/backups/`. The filename includes the timestamp (e.g., `20260501_120000-hamilton_erp-database.sql.gz`).
5. Copy the file off the server to your offsite storage (see below). Example using `scp` from your MacBook:
   ```bash
   scp frappe-user@bench-host:~/frappe-bench/sites/hamilton-erp.v.frappe.cloud/private/backups/20260501_*.tar.gz ~/Desktop/hamilton-backups/
   ```
   Replace `frappe-user@bench-host` with the SSH credentials from the Frappe Cloud dashboard.

### Where to store manual backups

Two good options:

| Option | Cost | Notes |
|---|---|---|
| **AWS S3** | ~$0.023/GB/month | Familiar, reliable. Enable versioning + SSE-S3 encryption (server-side, no extra config). |
| **Backblaze B2** | ~$0.006/GB/month | Cheaper. S3-compatible API. Native encryption at rest. Good choice if you want to minimize cost. |

**Either option must have:**
- Versioning enabled (so you can recover even if a backup file is overwritten)
- Encryption at rest (S3 SSE-S3 or B2 native)
- 1-year minimum retention (configure lifecycle rules to auto-delete after your retention window)

**[PRE-LAUNCH]** Set up the bucket, test the upload, and confirm encryption is enabled before Hamilton goes live.

**Store the bucket credentials (access key + secret) in 1Password or Bitwarden. Never commit them to the GitHub repo.**

### Suggested backup cadence

Run the manual backup weekly, every Sunday evening, before the week closes. Pair it with the weekly maintenance window already described in `docs/RUNBOOK.md` §9.

A cron job on the Frappe Cloud bench scheduler can automate this if the plan supports it — check with Frappe Cloud support. If not, set a repeating Sunday calendar reminder to run it manually.

---

## 3. What Is in Each Backup

### In the backup

| Item | Where it lives | Why it matters |
|---|---|---|
| MariaDB dump | `.sql.gz` in the tarball | Every DocType record: Sales Invoices, Sessions, Cash Drops, Assets, Settings, Customers |
| Public files | `public/files/` in the tarball | Logos, attachments visible without login |
| Private files | `private/files/` in the tarball | Invoice PDFs, Comp Admission Log attachments — require login to view |
| `site_config.json` | Included in `bench backup --with-files` | Per-venue feature flags: `hamilton_company`, `anvil_venue_id`, `anvil_tax_mode`, `anvil_currency`, etc. |

### NOT in the backup

| Item | Where it actually lives |
|---|---|
| Hamilton ERP application code | GitHub: `csrnicek/hamilton_erp` on branch `main` |
| ERPNext / Frappe framework code | GitHub: `frappe/frappe` and `frappe/erpnext`, pinned to a specific v16 minor tag |
| Local dev bench configuration | Your MacBook at `~/frappe-bench-hamilton/` |

**The code is safe in GitHub.** If you restore a database backup, you re-deploy code from GitHub separately (see §4, Step 4). The database and the code are independent.

---

## 4. Restore Procedure — Full Site

**When to use this:** catastrophic data loss, accidental wipe of the site database, ransomware (unlikely on Frappe Cloud's managed infrastructure, but worth having the plan), or a botched migration that corrupted data beyond easy repair.

**Before you start:** This procedure wipes the current live site database and replaces it with the backup. There is no merge option — it's an overwrite. If there is any data from between the backup timestamp and now that you need, try to export it manually before restoring.

### Steps

**Step 1 — Identify the restore point.**
- Go to Frappe Cloud dashboard → Apps & Sites → hamilton-erp → Backups tab.
- Find the backup dated just before the incident. Note the exact timestamp.
- If you need a backup older than 30 days, you need the offsite manual backup from S3/B2 (see §2).

**Step 2 — Restore from Frappe Cloud dashboard.**
- Still in the Backups tab, find the backup row and click **Restore**.
- Frappe Cloud will ask you to confirm — this wipes the current site database.
- Confirm and wait. Typical restore time is 5–15 minutes depending on database size.
- You will receive an email or notification when the restore completes.

**Step 3 — Verify data integrity.**
- Log in to `https://hamilton-erp.v.frappe.cloud/app`.
- Open a known recent record: a Sales Invoice from the last shift before the incident, or a recent Cash Drop.
- Confirm the record looks correct and all fields are populated.
- Open the Asset Board and confirm the 59 assets (26 rooms, 33 lockers) are visible.

**Step 4 — Re-deploy code if needed.**
- After a database restore, the code on the site still reflects whatever was deployed before the restore.
- If the v16 minor pin of frappe/erpnext has shifted since the backup was taken (e.g., you upgraded the site since that backup), you may need to re-pin and redeploy.
- To trigger a fresh deploy: push a trivial change to `main` on GitHub (or use Frappe Cloud's manual deploy button).
- Frappe Cloud will re-run migrations after deploy. These are safe to run against a restored database as long as the pinned version matches what the backup was on.

**Step 5 — Re-confirm site_config.json values.**
After a restore, spot-check the per-venue config values via bench console or Frappe Cloud's Site Config editor:
- `hamilton_company` — should be `"Hamilton Inc"`
- `anvil_venue_id` — should be `"hamilton"`
- `anvil_tax_mode` — should be `"hst_ontario"`
- `anvil_currency` — should be `"CAD"`
- Any other values you have set per `docs/venue_rollout_playbook.md` Phase B.

If any are missing or wrong, re-apply them via `bench set-config` (instructions in `docs/venue_rollout_playbook.md` §Phase B).

---

## 5. Restore Procedure — Partial (Single Record)

**When to use this:** a specific DocType record was deleted by mistake — for example, an operator accidentally deleted a Cash Drop record, or a Venue Session record was corrupted.

This is more complex than a full restore and requires bench console access (SSH, private bench plan required).

### Steps

**Step 1 — Get the backup tarball for the relevant date.**
- If within 30 days: download the backup from Frappe Cloud dashboard → Backups → download the `.sql.gz` file.
- If older than 30 days: retrieve from your offsite S3/B2 storage.

**Step 2 — Extract just the affected table.**
- On your local MacBook, unzip the SQL dump:
  ```bash
  gunzip -k 20260501_120000-hamilton_erp-database.sql.gz
  ```
- Use `grep` to find and extract just the INSERT statements for the table you need. For example, to extract Cash Drop records:
  ```bash
  grep "INSERT INTO \`tabCash Drop\`" 20260501_120000-hamilton_erp-database.sql > cash_drop_restore.sql
  ```
- Identify the specific row(s) for the record you need by scanning the output for the `name` or date field.

**Step 3 — Import the extracted record.**
- Connect to the Frappe Cloud bench shell via SSH.
- Copy the SQL snippet to the bench server.
- Open the MariaDB console:
  ```bash
  bench --site hamilton-erp.v.frappe.cloud mariadb
  ```
- Paste the INSERT statement(s) for just the deleted record. If the record's `name` already exists (e.g., it was modified rather than deleted), you may need a `REPLACE INTO` instead of `INSERT INTO`.

**Step 4 — Re-run any dependent patches.**
Some records trigger patch behavior (e.g., session numbering sequences). After importing a raw SQL record, check whether any after-insert logic needs to be re-run manually via `bench console`.

**Step 5 — Verify referencing records.**
Foreign-key (Link field) relationships in Frappe are not enforced at the database level — they're enforced by the application. After restoring a record, confirm that any records that reference it still link correctly. For example, if you restored a Venue Session, confirm the related Asset Status Log entries still point to valid session names.

---

## 6. Test Restore — Quarterly

**Why:** A backup you have never tested is a backup you cannot trust. The only way to know the restore procedure works is to run it.

**Cadence:** First Monday of each quarter (January, April, July, October).

### Steps

1. Spin up a temporary Frappe Cloud staging site, or use `hamilton-staging.v.frappe.cloud` if it exists.
2. In the staging site's Backups tab, restore the most recent production backup.
3. Wait for the restore to complete, then log in.
4. Run the smoke test:
   - Verify the Asset Board loads and shows 59 assets.
   - Create and cancel a test session.
   - Submit a test Cart (if cart is live by the time you run this).
   - Check that one recent production Sales Invoice appears and its totals look correct.
5. Tear down the staging site after the test to avoid unnecessary cost.
6. If anything failed during the test, document it in `docs/lessons_learned.md` as a new LL entry. Fix the gap before the next quarter.

**If the staging site will persist:** keep it on a separate Frappe Cloud site plan. Never restore production backups to `hamilton-test.localhost` (local dev bench) — local restores can work but the environment differences make them unreliable as a restore-procedure test.

---

## 7. What Is Critical Data (Cannot Be Re-Derived)

These records are your legal and operational record of truth. Loss of these means loss of evidence you may need for tax audits, cash reconciliation disputes, or regulatory inquiries.

| DocType | Why it's critical | Retention requirement |
|---|---|---|
| **Sales Invoice** | Legal record of revenue. CRA requires 6-year retention from the end of the fiscal year the sale occurred. | 7 years (CRA 6 + 1 buffer) |
| **Cash Drop** | Cash audit trail. Used to reconcile operator cash drops against Sales Invoice totals. | 7 years |
| **Cash Reconciliation** | Shift-end cash audit record (blind — operators don't see expected totals). DEC-005 invariant. | 7 years |
| **Comp Admission Log** | Record of complimentary admissions with approver identity. | 7 years |
| **Venue Session** | Occupancy log. Connects asset usage to Sales Invoices and shift records. | 7 years |
| **Customer** | Walk-in customer is a single shared record (current). Phase 2 membership records are PII under PIPEDA — must be handled with care if the customer requests deletion. | PIPEDA "as long as necessary for the purposes" — consult your PIPEDA posture in `docs/research/pipeda_venue_session_pii.md` |
| **Hamilton Settings** | Per-venue configuration (tax mode, currency, feature flags). Phase 2 will have one record per venue. | Indefinite |
| **Shift Record** | Maps operator identity to a shift window. Links to Cash Reconciliation. | 7 years |

---

## 8. What Is NOT Critical Data (Can Be Re-Derived)

Losing these is annoying but not a legal or business emergency.

| DocType | Why it's not critical |
|---|---|
| **Asset Status Log** | Audit trail of room/locker state transitions (Available → Occupied → Dirty → Available). Useful for troubleshooting but not a financial record. Can be reconstructed by replaying Venue Sessions. |
| **Bin (stock levels)** | ERPNext's inventory count. Hamilton's 4 SKUs (Day Pass, Locker, etc.) can be physically recounted and re-entered. |
| **Pricing Rule** | The pricing rules (DEC-014) are documented in `docs/decisions_log.md` and can be re-applied from the seed. |
| **Error Log** | Frappe's internal error log. Useful for debugging but not a business record. |

---

## 9. Frappe Cloud-Specific Gotchas

**Private bench plan required for SSH.** Frappe Cloud's auto-deploy/shared plans do not expose SSH access. The manual weekly backup procedure in §2 requires SSH. Confirm you are on a private bench plan before go-live. If you are not, the manual backup is not possible — you are dependent on Frappe Cloud's 30-day daily backups only.

**Restore wipes the database — there is no merge.** When you click Restore in the Frappe Cloud dashboard, the current site's database is wiped and replaced with the backup. If there is any data between the backup timestamp and now that you need, export it first. This is not a "merge restore" — it's an overwrite.

**Auto-deploy re-runs migrations after restore.** Hamilton's GitHub `main` branch triggers an auto-deploy on every push. After a database restore, if a code push lands while the site is in a transitional state, Frappe Cloud will re-run `bench migrate` against the restored database. This is usually safe. It becomes a problem only if the v16 pin of frappe/erpnext on the site is different from what the backup was running — an out-of-version migration can fail or silently corrupt data. **Always verify the v16 minor pin matches between the backup and the current deploy.** See CLAUDE.md "Production version pinning" for the full rule.

**Frappe Cloud backup does not include the custom app code.** The backup captures the database and files. The Hamilton ERP Python/JS code lives in GitHub. If you restore the database to a point before a schema change (new custom field, new DocType), but deploy the current code, `bench migrate` will re-apply the schema change against the restored database — this is the expected behavior, and it's safe.

**Backups for future venues are independent.** Philadelphia, DC, Dallas, and Ottawa are (or will be) separate Frappe Cloud sites. Each site has its own backup schedule. You cannot restore Philadelphia's backup onto Hamilton's site. Manage each venue's backups independently.

---

## 10. Disaster Scenarios and Responses

### Frappe Cloud-side outage
**What it means:** Frappe Cloud's infrastructure has a problem. Hamilton's site is unavailable. You cannot log in, operators cannot use the system.

**Response:**
1. Check Frappe Cloud's status page at `https://status.frappe.cloud`.
2. If confirmed Frappe Cloud outage: wait. You cannot fix this yourself — it's their infrastructure.
3. Document the outage window (start time, end time) for tax and regulatory purposes if it affects a filing period.
4. If the outage extends past a shift end, operators should record cash drops on paper using the shift report form in the operations binder. Re-enter them when the system is back.
5. Send a customer-facing apology if the outage is customer-visible (e.g., operators can't check guests in). Keep it simple: "Our system is temporarily unavailable; we're working on it."

### GitHub repository access lost
**What it means:** You've lost access to `csrnicek/hamilton_erp` on GitHub.

**Response:**
1. Production continues running on the last-deployed code from `main`. No data is lost. No immediate emergency.
2. Contact GitHub Support for account recovery at `https://support.github.com`.
3. While locked out: do not push any code changes. If a critical bug must be fixed, use Frappe Cloud's bench console to apply a patch directly, then push via GitHub once access is restored.
4. When access is restored, audit for any unauthorized commits (GitHub's commit history is your audit log).

### MariaDB corruption mid-write
**What it means:** A write to the database was interrupted (power loss, network drop, process crash) and a record is in a partial state. Rare on Frappe Cloud's managed infrastructure, which uses InnoDB with WAL (write-ahead logging — a database technique that ensures partial writes can be rolled back on crash).

**Response:**
1. Identify the affected record(s) by checking the Frappe Error Log (Desk → Error Log).
2. Attempt to re-save or delete-and-recreate the corrupted record via Frappe Desk.
3. If the database itself is corrupted (not just a record): restore from the most recent backup (§4). Document any transactions that occurred between the backup and the corruption for retroactive manual re-entry.
4. File the incident in `docs/lessons_learned.md`.

### Data loss while Phase 2 venues are live
**What it means:** A Hamilton data loss or restore affects other venues, or vice versa.

**Response:**
Each venue is a separate Frappe Cloud site with its own database. Restoring Hamilton does NOT affect Philadelphia or DC. Restore independently per venue. Do not attempt to merge data across venue sites — each venue's records are site-scoped and the `name` fields (Frappe's primary keys) may collide if you try to merge SQL dumps across sites.

### Ransomware (unlikely but plan for it)
**What it means:** Someone gains unauthorized access to the Frappe Cloud bench and encrypts or deletes files.

**Response:**
1. Frappe Cloud's managed infrastructure makes this extremely unlikely — you do not have direct OS-level access to the server.
2. If it somehow occurs: contact Frappe Cloud support immediately. Do not attempt recovery yourself.
3. Restore from your offsite S3/B2 backup (§2), which is outside Frappe Cloud's infrastructure.
4. Rotate all credentials (Frappe Cloud account password, GitHub PAT, S3/B2 access keys) after recovery.

---

## 11. Pre-Launch Backup Checklist

Complete these before Hamilton goes live. Do not skip any item.

- [ ] **Confirm Frappe Cloud daily backup is enabled.** Log in to Frappe Cloud → Apps & Sites → hamilton-erp → Backups tab. Verify that at least one backup exists and the schedule shows "daily."
- [ ] **Confirm your plan includes SSH access (private bench plan).** If not, you cannot run manual backups. Either upgrade the plan or document the limitation explicitly.
- [ ] **Set up offsite cloud storage.** Create an S3 bucket (AWS) or B2 bucket (Backblaze) with versioning and encryption at rest enabled. Record the bucket name and region.
- [ ] **Store bucket credentials in your password manager.** Access key + secret go in 1Password or Bitwarden. Never in the GitHub repo. Never in a text file on your desktop.
- [ ] **Run one manual backup end-to-end.** Connect via SSH, run `bench --site hamilton-erp.v.frappe.cloud backup --with-files`, copy the resulting file to S3/B2, and verify it arrived. This proves the full chain works before you need it.
- [ ] **Run a test restore to staging.** Follow §6. Confirm the restore procedure works before go-live. Document the result.
- [ ] **Set a quarterly restore-test reminder.** Add a recurring event to your calendar: "Hamilton ERP backup restore test" — first Monday of January, April, July, October.
- [ ] **Confirm CRA 7-year retention is covered.** Your offsite storage lifecycle rules should retain files for at least 7 years. Log in to S3/B2 and verify the lifecycle policy is set.

---

## 12. Backup Retention Schedule

| Tier | Retention | Where stored | Notes |
|---|---|---|---|
| Daily | 30 days | Frappe Cloud (automatic) | Routine recovery window |
| Weekly | 12 weeks (3 months) | Offsite S3/B2 | Manual bench backup, run every Sunday |
| Monthly | 12 months | Offsite S3/B2 | Retain the last Sunday backup of each month |
| Annual | 7 years | Offsite S3/B2 | Retain the last backup of each calendar year |

**Why 7 years:** CRA (Canada Revenue Agency) requires businesses to retain financial records for 6 years from the end of the fiscal year. The 7-year retention adds a one-year buffer for late assessments or filing corrections.

**How to implement tiered retention in S3/B2:**
In AWS S3 or Backblaze B2, set lifecycle rules (also called "lifecycle policies") that automatically delete files based on their age and a prefix (folder path). A practical structure:

```
hamilton-backups/
  daily/      ← delete after 30 days
  weekly/     ← delete after 90 days
  monthly/    ← delete after 365 days
  annual/     ← delete after 2556 days (7 years)
```

When you run the manual backup, copy it to the appropriate prefix. The lifecycle rules handle deletion automatically. You never need to manually delete old backups.

---

## Maintenance

**Owner of this document:** Chris Srnicek.
**Review cadence:** Update this document whenever the backup setup changes (new storage provider, new plan, new venue added, retention policy change).
**Related docs:**
- `docs/RUNBOOK.md` — incident response for live outages
- `docs/venue_rollout_playbook.md` — Phase A (site creation) is where backup setup begins for each new venue
- `docs/decisions_log.md` — DEC-005 (blind cash control), DEC-019 (locking), DEC-033 (session numbering) are the invariants never to violate during a restore
- `docs/lessons_learned.md` — file new LL entries for every restore-test failure or real incident
