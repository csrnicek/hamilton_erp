# Runbook 7 — Fresh-Site Install

**Purpose:** take a blank Frappe Cloud bench (or a fresh local bench) → a fully provisioned Hamilton ERP site that passes every CI conformance gate. No prior state assumed.

**Audience:** Chris, or a senior Frappe contractor onboarding a second venue.

**Estimated time:** 25–40 minutes for a Frappe Cloud bench; 60–90 minutes for a local bench (slow first compile).

**Last verified:** 2026-05-02. Anchor: CI workflow `.github/workflows/tests.yml` runs this exact sequence on every PR; if CI is green, this runbook is current.

---

## Pre-flight checklist (5 min)

Before running any commands, confirm all of these. Stop if any fail.

| Check | Command (Frappe Cloud) | Expected |
|---|---|---|
| Frappe Cloud bench provisioned | UI: bench dashboard exists | Bench in "Active" state |
| Python 3.11 (Frappe Cloud default) or 3.14 (CI parity) | `python3 --version` | `3.11.x` or `3.14.x` |
| Node 24 | `node --version` | `v24.x` |
| MariaDB 11.8 | bench dashboard or `mariadb --version` | `11.8.x` |
| Redis ports 11000 + 13000 free | (Frappe Cloud handles automatically) | bench can start |
| `frappe-bench` installed | `which bench` | path returned |
| `git` clean clone of hamilton_erp ready | `git clone https://github.com/csrnicek/hamilton_erp.git` | clone succeeds |
| GitHub access for frappe/frappe `version-16` and frappe/erpnext `version-16` | `git ls-remote https://github.com/frappe/frappe version-16` | sha returned |
| GitHub access for frappe/payments `develop` | `git ls-remote https://github.com/frappe/payments develop` | sha returned |

**If any check fails:** resolve before proceeding. Most common failure: Frappe Cloud bench tier doesn't include Python 3.14 (only 3.11). That's fine — CI parity is nice-to-have, not required.

---

## Step 1 — Bench init (5 min)

```bash
# Frappe Cloud: skip — bench is already initialized.
# Local only:
bench init frappe-bench-hamilton \
  --frappe-branch version-16 \
  --skip-assets \
  --no-backups \
  --python "$(which python3)"

cd frappe-bench-hamilton
```

**Validate:**
```bash
ls apps/frappe   # Should show frappe app dir
cat sites/common_site_config.json  # Should show redis_cache, redis_queue ports
```

---

## Step 2 — Get apps in dependency order (10 min)

Order matters. ERPNext depends on Frappe; payments adds POS dependencies; hamilton_erp depends on all three.

```bash
bench get-app --skip-assets --branch version-16 erpnext https://github.com/frappe/erpnext
bench get-app --skip-assets --branch develop      payments https://github.com/frappe/payments
bench get-app --skip-assets                       hamilton_erp https://github.com/csrnicek/hamilton_erp
```

**About frappe/payments / develop branch:**
> frappe/payments has no `version-16` branch yet (only v14, v15, v15-hotfix, develop as of 2026-04-28). The `develop` branch ships the `Payment Gateway` DocType that hamilton_erp's tests transitively depend on (User → ERPNext POS chain → Payment Gateway). Switch to `version-16` once it exists. Reference: `.github/workflows/tests.yml:90–102` and `docs/inbox.md` 2026-04-28 entry.

**Validate:**
```bash
ls apps/  # Should show: erpnext, frappe, hamilton_erp, payments
```

---

## Step 3 — Install hamilton_erp test extras (1 min, optional locally)

```bash
env/bin/pip install -e "apps/hamilton_erp[test]"
```

This adds `hypothesis` to the bench env (used for property-based tests). Skip on Frappe Cloud production benches.

---

## Step 4 — Configure bench credentials (1 min)

```bash
bench set-config -g root_login    root
bench set-config -g root_password root
bench set-config -g admin_password admin
```

For production: replace `admin` with a strong randomly-generated password. Frappe Cloud handles this in the UI.

---

## Step 5 — Trim Procfile for non-dev deploys (CI parity, optional locally) (1 min)

```bash
sed -i.bak '/^watch:/d'    Procfile
sed -i.bak '/^schedule:/d' Procfile  # KEEP if testing the orphan-invoice scheduler (Task 35)
```

For a Hamilton production bench, **keep `schedule:`** (the daily orphan-invoice integrity check, Task 35 / PR #124, runs on this).

---

## Step 6 — Start bench in background (2 min)

```bash
bench start &> bench_start.log &
```

Wait for redis to come up:
```bash
for i in $(seq 1 30); do
  if redis-cli -p 13000 ping >/dev/null 2>&1 && \
     redis-cli -p 11000 ping >/dev/null 2>&1; then
    echo "redis ready (attempt $i)"
    break
  fi
  sleep 2
done
```

**Validate:**
```bash
redis-cli -p 13000 ping  # → PONG
redis-cli -p 11000 ping  # → PONG
```

---

## Step 7 — Create the Hamilton site (10 min)

This is the load-bearing step. The `bench new-site --install-app hamilton_erp` invocation triggers hamilton_erp's `after_install` hook, which seeds Customer Groups, Territories, the "Walk-in" Customer, the "Club Hamilton" Company (if no other Hamilton-named company exists), the POS Profile, and the 59 Venue Asset records.

```bash
bench new-site hamilton.localhost \
  --db-type mariadb \
  --db-host 127.0.0.1 \
  --db-port 3306 \
  --mariadb-root-password root \
  --admin-password admin \
  --no-mariadb-socket \
  --install-app erpnext \
  --install-app payments \
  --install-app hamilton_erp \
  --verbose
```

**Replace `hamilton.localhost`** with the production site name (e.g. `hamilton.frappe.cloud`, `hamilton-test.localhost`, etc.).

**If this step fails:** the after_install hook is the most likely culprit. Check the bench log; typical failures are missing fixture references or a previously-installed site state polluting the seed. Capture the full traceback and consult the install.py error path.

**Validate (the install conformance gates from `.github/workflows/tests.yml:213–249`):**
```bash
# 1. desktop:home_page = "setup-wizard" must NOT be present (after_install clears it)
bench --site hamilton.localhost mariadb -e \
  "SELECT COUNT(*) FROM tabDefaultValue \
   WHERE parent='__default' AND defkey='desktop:home_page' \
   AND defvalue='setup-wizard'" -B -N | tail -1
# Expected: 0

# 2. hamilton_erp.is_setup_complete = 1 (and frappe + erpnext)
for app in frappe erpnext hamilton_erp; do
  bench --site hamilton.localhost mariadb -e \
    "SELECT is_setup_complete FROM \`tabInstalled Application\` \
     WHERE app_name='$app' LIMIT 1" -B -N | tail -1
done
# Each line expected: 1
```

---

## Step 8 — Run `bench migrate` (3 min)

Even though `install-app` did most of the work, `bench migrate` fires the `after_migrate` hook, which is registered to fire `_ensure_no_setup_wizard_loop` and other idempotent cleanups. Production deploys = `install-app + migrate`, so we replicate that.

```bash
bench --site hamilton.localhost migrate
```

**Validate** (the post-migrate conformance gate from `.github/workflows/tests.yml:262–321`):
```bash
# All of these should print the indicated value
bench --site hamilton.localhost execute frappe.db.exists --kwargs "{'dt':'Customer Group','dn':'All Customer Groups'}"
# Expected: All Customer Groups
bench --site hamilton.localhost execute frappe.db.exists --kwargs "{'dt':'Customer Group','dn':'Individual'}"
# Expected: Individual
bench --site hamilton.localhost execute frappe.db.exists --kwargs "{'dt':'Customer','dn':'Walk-in'}"
# Expected: Walk-in

# Venue Asset count = 59 per DEC-054
bench --site hamilton.localhost execute frappe.db.count --kwargs "{'dt':'Venue Asset'}" | tail -1
# Expected: 59

# Payment Gateway DocType present (frappe/payments installed)
bench --site hamilton.localhost mariadb -e \
  "SELECT COUNT(*) FROM tabDocType WHERE name='Payment Gateway'" -B -N | tail -1
# Expected: 1
```

---

## Step 9 — Site config: enable tests + server scripts (production: skip step; staging: run) (1 min)

```bash
# DEV / STAGING ONLY
bench --site hamilton.localhost set-config allow_tests 1 --parse
bench --site hamilton.localhost set-config server_script_enabled 1 --parse
```

For production: skip both. Tests run on staging (CI runs on `test_site`, never on production).

---

## Step 10 — Smoke-test the deploy (5 min)

Don't trust install conformance alone — exercise the round-trip from API to DB.

```bash
# 10.1: Asset Board renders
bench --site hamilton.localhost execute hamilton_erp.api.get_asset_board_data | head -10
# Expected: dict with 'assets' key, len(assets) == 59

# 10.2: A round-trip lifecycle: assign → vacate → mark clean
# (Manual via the Frappe Desk UI is faster than scripted; if scripting:)
bench --site hamilton.localhost console <<'EOF'
import frappe
asset = frappe.db.get_value('Venue Asset', {'status':'Available'}, ['name','asset_code'], as_dict=True)
print(f"Test asset: {asset.name} / {asset.asset_code}")
EOF
# Expected: prints VA-NNNN / SOMECODE
```

```bash
# 10.3: Run the full hamilton_erp test suite (staging only)
bench --site hamilton.localhost run-tests --app hamilton_erp 2>&1 | tail -5
# Expected: "OK" status
```

---

## Step 11 — Set the global default Company (production go-live) (1 min)

After step 8, `Club Hamilton` exists but isn't pinned as the global default. Several flows (notably the zero-value invoice fixture and the Sales Invoice currency resolution) need a global default to avoid edge-case bugs.

```bash
bench --site hamilton.localhost mariadb -e \
  "INSERT INTO tabDefaultValue (name, defkey, defvalue, parent, parenttype, parentfield) \
   VALUES (UUID(), 'company', 'Club Hamilton', '__default', 'DefaultValue', 'system_defaults') \
   ON DUPLICATE KEY UPDATE defvalue='Club Hamilton';"
```

**Or via Frappe Desk:** Setup → Settings → Global Defaults → Default Company → "Club Hamilton" → Save.

**Validate:**
```bash
bench --site hamilton.localhost execute "frappe.defaults.get_global_default" --args "['company']" 2>&1 | tail -1
# Expected: Club Hamilton
```

---

## Step 12 — Configure backups + retention (production go-live) (5 min)

See `docs/runbooks/backup_restore_drill.md` (Runbook 8) for the standalone backup configuration. At minimum, on Frappe Cloud production:

- Set the bench's backup region to **Canada Central** or **US East** (NOT Mumbai — see `docs/inbox.md` T0-FC-2).
- Enable backup encryption BEFORE any PII or card data populates (per `docs/inbox.md` T0-FC-1).
- Verify storage allocation ≥ 20 GB (per `docs/inbox.md` T0-FC-3).

---

## Step 13 — Sign-off (final gate)

Print the bench's go-live state to a runbook log file:

```bash
{
  echo "=== Hamilton fresh-site install — sign-off ==="
  date -u
  echo "--- Bench branches ---"
  for app in frappe erpnext payments hamilton_erp; do
    cd "apps/$app"
    echo "$app: $(git rev-parse --short HEAD)  ($(git rev-parse --abbrev-ref HEAD))"
    cd ../..
  done
  echo "--- Site state ---"
  bench --site hamilton.localhost mariadb -e "SELECT COUNT(*) AS venue_assets FROM \`tabVenue Asset\`" -B -N
  echo "--- Default company ---"
  bench --site hamilton.localhost mariadb -e \
    "SELECT defvalue FROM tabDefaultValue WHERE parent='__default' AND defkey='company'" -B -N
} | tee fresh_install_signoff_$(date -u +%Y%m%dT%H%M%SZ).log
```

**Hand-off:** the resulting `fresh_install_signoff_*.log` file goes to Chris for archive. Production go-live is gated on Chris's manual review of this file.

---

## Failure modes and recovery

| Symptom | Likely cause | Recovery |
|---|---|---|
| `after_install` hook fails partway | Missing ERPNext fixture (Customer Group, Territory) | Re-run the failed app's install: `bench --site X install-app erpnext` then continue from step 7 |
| `bench migrate` errors on hamilton_erp patches | Patches assume something the install didn't seed | Capture traceback; cross-reference `hamilton_erp/patches.txt` and `hamilton_erp/setup/install.py` |
| `Payment Gateway DocType not found` | frappe/payments install failed silently | Re-run `bench get-app --skip-assets payments https://github.com/frappe/payments`, then `bench --site X install-app payments`, then re-run step 8 |
| `Venue Asset count != 59` | Seed data has drifted or test pollution | Drop the site (`bench drop-site X`), restart from step 7 |
| Setup wizard loops at first login | `desktop:home_page='setup-wizard'` not cleared by after_migrate | Manually run: `bench --site X mariadb -e "DELETE FROM tabDefaultValue WHERE parent='__default' AND defkey='desktop:home_page'"` then refresh browser |

---

## What this runbook does NOT cover

- Frappe Cloud-specific UI clicks (region, plan, app installation through dashboard) — Frappe Cloud's own docs are authoritative.
- Custom domain / SSL configuration — Frappe Cloud handles this in dashboard.
- Email / SMTP setup — separate runbook needed when first email goes out (Phase 2).
- iPad / kiosk client setup — separate hardware runbook (out of scope here).
- Backup / restore — see Runbook 8.
- Launch-day choreography — see Runbook 9.

---

## Cross-references

- `.github/workflows/tests.yml` — the CI sequence this runbook mirrors. If they drift, CI is wrong.
- `docs/RUNBOOK.md` — existing operational runbook (operator-side workflows, not install).
- `docs/RUNBOOK_BACKUP.md` — the longer-form backup doc (Runbook 8 distills this).
- `hamilton_erp/setup/install.py` — `_ensure_hamilton_company`, `_seed_hamilton_data`, `_ensure_no_setup_wizard_loop`. Read these to understand what after_install + after_migrate actually do.
- `docs/decisions_log.md` DEC-054 (59 venue assets), DEC-061 (per-venue currency). These are the seed-data invariants this runbook validates.
