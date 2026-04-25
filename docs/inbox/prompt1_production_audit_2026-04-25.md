# Hamilton ERP — ERPNext v16 / Frappe Cloud Production Readiness Audit

**Date:** 2026-04-25
**Source prompt:** `docs/hamilton_pre_handoff_prompts.md` → Prompt 1 (ERPNext Production Best Practices Audit)
**Author:** Claude Code (Opus 4.7), autonomous research run, this Claude Code session
**Companion document:** `docs/inbox/prompt5_handoff_audit_2026-04-25.md` (handoff readiness — different lens, complementary checklist)

---

## What This Document Is

This is a **production readiness** audit, not a handoff readiness audit. The two are different:

- **Handoff readiness** (Prompt 5) asks: "Will the next developer be able to onboard and maintain this without billing extra hours?"
- **Production readiness** (this doc) asks: "Will this app survive a Saturday night at 11pm with 60 walk-ins, a wedged Redis, a stuck patch, a credentials leak, and the operator on a flaky LTE link?"

Some items appear in both. Where they do, this doc references Prompt 5 instead of repeating. Where they diverge, this doc focuses on **the moments after launch** — production incidents, scheduler dead-ends, audit demands, secret rotations, version upgrades, backups that turn out not to restore.

The findings are repo-aware: I read `hooks.py`, `patches.txt`, `setup/install.py`, the API surface, the workflows directory, the doctype JSON files, and `pyproject.toml`. Recommendations are prioritised by **what breaks production if missing**, not by general best practice.

---

## Part 1 — The "Saturday Night At 11pm" Test

If your phone rings at 11:07pm on a Saturday and the operator says "the asset board is frozen, every tile is stuck on Dirty, the cash drawer screen says 'unauthorized,' and Frappe Cloud is showing 504s" — can you, with no developer present, do these things?

1. **See what broke.** Open Frappe Cloud → Error Log → filter to the last 30 minutes. There must be one snapshot per failure with a stack trace, the request body, and the user.
2. **See what was scheduled.** Open Scheduled Job Log → confirm the 15-minute overtime cron actually fired in the last hour.
3. **See what changed last.** Open Version → Venue Asset → see who set 12 rooms to OOS in the last hour and why.
4. **Roll back to a known-good state.** Open Frappe Cloud → Backups → restore the most recent pre-incident snapshot to a sandbox site, verify, then promote.
5. **Re-run a stuck patch.** SSH (or Frappe Cloud terminal) → `bench --site $SITE execute hamilton_erp.patches.v0_1.seed_hamilton_env`.
6. **Roll forward to a hotfix.** Push to main → Frappe Cloud auto-deploys → confirm via health endpoint.

If any of these is "I don't know how" or "we'd have to call the developer" — that's a Tier 1 production gap. The rest of this doc is the work to make all six "yes" before you go live.

---

## Part 2 — Repo State Snapshot (verified 2026-04-25)

What Hamilton actually has today, factual:

| Area | What's there | Status |
|---|---|---|
| `hooks.py` | 95 lines, well-commented, fixtures filtered, 1 doc_event, 1 cron (15 min), `after_install` + `after_migrate` | ✅ Clean shape |
| `patches.txt` | 2 patches, both in `[post_model_sync]` | ✅ Clean structure, idempotency to verify |
| `fixtures/` | `role.json`, `property_setter.json`, `custom_field.json`, all filtered by `%-hamilton_%` pattern | ✅ Filtered correctly; verify export round-trip |
| `setup/install.py` | `_create_roles()` is idempotent; `ensure_setup_complete()` heals `is_setup_complete` after migrate; `_block_pos_closing_for_operator()` enforces blind cash control | ✅ Defensive and well-documented |
| `.github/workflows/` | Only `claude-review.yml` (PR review bot). **No test runner workflow.** | 🔴 **Tier 1 gap** |
| `pyproject.toml` | `frappe = ">=16.0.0,<17.0.0"`, `erpnext = ">=16.0.0,<17.0.0"`, ruff configured (line 110, py311, tab indent, double quotes) | ✅ v16-pinned, formatter wired |
| `README.md` | 2 lines (`# hamilton_erp` + `Hamilton ERPNext Implement`) | 🔴 **Tier 1 gap** |
| Test count | 19 `test_*.py` files, ~306+ tests passing per `claude_memory.md` baseline | ✅ Strong |
| Whitelist endpoints | 9 `@frappe.whitelist(...)` in `api.py`, all with explicit `methods=[...]`, all gated by `frappe.has_permission(..., throw=True)` | ✅ Method-restricted, permission-checked |
| Type annotations | Partial — newer endpoints have parameter type hints, older return-type only | 🟡 Tier 2 |
| `ignore_permissions=True` | 4 call sites in `lifecycle.py` (insert + save) | 🟡 Tier 2 — needs justification block in code |
| `permission_query_conditions` / `has_permission` hooks | None defined | 🟡 Tier 3 — fine for single-venue, must address for multi-venue |
| Scheduler events | 1 cron job (`*/15 * * * *` → overtime check) | ✅ Defined; need health monitoring |
| DocType indexes | 8 doctypes with `in_list_view`/`search_index` markers; `test_database_advanced.py` enforces specific indexes | ✅ Verified by tests |
| `docs/` | Extensive — decisions_log, lessons_learned, coding_standards, design specs, current_state, build_phases, testing_guide, venue_rollout_playbook, troubleshooting | ✅ Strongest area |

**Headline:** the application code is in good shape. The gaps are operational — CI, README, audit trail enablement, scheduler health, backup verification, and the "what do we do at 11pm" runbook.

---

## Part 3 — Custom App Structure & Upgrade Safety

### What v16 / Frappe Cloud expects

A v16 custom app on Frappe Cloud must:

1. Pin Frappe and ERPNext compatible major versions in `pyproject.toml` under `[tool.bench.frappe-dependencies]` — **comma**-separated, not space-separated. Hamilton has `frappe = ">=16.0.0,<17.0.0"` which is correct.
2. Have a `modules.txt` listing every module — Hamilton has this.
3. Have a `patches.txt` with section headers `[pre_model_sync]` and `[post_model_sync]` — Hamilton has this.
4. Have an `__init__.py` exporting `__version__` (or `dynamic = ["version"]` in `pyproject.toml` reading from `__init__.py`) — Hamilton has the latter.

### Upgrade-safety gotchas

- **Do not edit standard ERPNext DocTypes via JSON edits in your custom app.** Customisations belong in Custom Field, Property Setter, or Customize Form — all of which Hamilton's fixtures pattern correctly captures.
- **`extend_doctype_class` is the right v16 idiom for extending standard doctypes.** Hamilton uses it for `Sales Invoice → HamiltonSalesInvoice`. Don't monkey-patch.
- **`extend_doctype_class` is silently ignored if the standard doctype doesn't load before your override.** `required_apps = ["frappe", "erpnext"]` (which Hamilton has) gates this correctly.
- **Frappe v15+ dropped the default index on the `modified` column.** If any Hamilton query orders by or filters on `modified`, add an explicit index to that DocType's JSON.

### Action items

- [ ] **Tier 2** Add a docstring at the top of `hooks.py` summarising what each hook block does and why (non-obvious decisions only). The existing comments are good but don't tell you "why this app exists" in 30 seconds.
- [ ] **Tier 2** Add an `app_compatibility.md` to `docs/` listing the exact Frappe minor + ERPNext minor + MariaDB version that Hamilton is verified against. Update on every Frappe Cloud upgrade.
- [ ] **Tier 3** Add a `before_uninstall` hook that prints a warning and bails out unless `--force` is passed, to prevent accidental wipes during dev.

---

## Part 4 — Fixtures: What They Are, Why They Matter, How to Verify

### What they are

Fixtures are the bridge between "manual UI configuration on one site" and "automatically applied on every other site." When you customise a Doctype via Customize Form, add a Custom Field, change a Property Setter, or define a Role — those are stored in the database, not in your app code. Without fixtures, they exist on hamilton-test.localhost and nowhere else.

When `bench --site $SITE export-fixtures --app hamilton_erp` runs, Frappe writes the matching rows to `hamilton_erp/fixtures/*.json`. When `bench migrate` runs on another site, those JSON files are imported.

### Hamilton's current setup

```python
fixtures = [
    {"dt": "Custom Field",     "filters": [["name", "like", "%-hamilton_%"]]},
    {"dt": "Property Setter",  "filters": [["name", "like", "%-hamilton_%"]]},
    {"dt": "Role",             "filters": [["name", "in", ["Hamilton Operator", "Hamilton Manager", "Hamilton Admin"]]]},
]
```

The `%-hamilton_%` filter convention is **excellent** — it prevents `bench export-fixtures` from accidentally vacuuming up custom fields from ERPNext or other apps installed on the same site. This is the #1 fixtures bug in the wild and Hamilton has already solved it.

### Gaps to verify

- [ ] **Tier 1** Run `bench --site hamilton-unit-test.localhost export-fixtures --app hamilton_erp` on a clean install and **diff the result against the committed JSON files**. Any drift means the local dev site has customisations that haven't been exported. Common culprit: a Custom Field named without the `-hamilton_` suffix that the filter misses.
- [ ] **Tier 1** Verify `git status` after the export above is **empty**. If any fixture file changed, commit it.
- [ ] **Tier 2** Add a missing fixture type if any of these exist on the dev site: **Workflow**, **Workflow State**, **Workflow Action Master**, **Print Format**, **Email Template**, **Notification**, **Web Form**, **Custom DocPerm**, **Server Script**, **Client Script**, **Translation**. Hamilton's three (Custom Field, Property Setter, Role) cover the basics; the rest only matter if Hamilton has used them.
- [ ] **Tier 2** Audit `Custom DocPerm` rows on hamilton-test.localhost. Hamilton's `_block_pos_closing_for_operator()` deletes one row at install time but doesn't export it as a fixture — meaning a fresh install on Philadelphia would have to re-run `after_install`. That's fine *if* `after_install` is idempotent (it is) and *if* it runs (it does, on `bench install-app`). Document this clearly in the venue rollout playbook.
- [ ] **Tier 3** Add a `make export-fixtures` (or `bench` alias) that does the export + git status check in one step, so future maintainers don't forget.

### What will cost billable hours if missing

A developer who finds 30 unexported customisations during handoff has to either (a) re-customise each on Philadelphia by hand, (b) write a one-time patch that backfills them, or (c) export them now and risk capturing unrelated junk. Option (c) is what the `%-hamilton_%` filter is meant to prevent — preserve that filter convention.

---

## Part 5 — Patches: Automating Site Setup So No Manual UI Config Is Needed

### What patches are for

Patches are one-time, idempotent migrations that run on `bench migrate`. They are versioned by directory (`patches/v0_1/`, `patches/v0_2/`, etc.) and ordered by `patches.txt`. Each patch should:

1. Be safe to run multiple times (idempotent).
2. Do exactly one thing.
3. Log what it did.
4. Never call `frappe.db.commit()` inside the patch body — Frappe handles transaction boundaries.

### Hamilton's current setup

```
[post_model_sync]
hamilton_erp.patches.v0_1.seed_hamilton_env
hamilton_erp.patches.v0_1.rename_glory_hole_to_gh_room
```

Two patches, both post-sync. The naming is good (descriptive, versioned). The recent rename patch (`Glory Hole → GH Room`) is exactly the kind of one-shot DB rename that belongs here.

### Gaps to verify

- [ ] **Tier 1** Read both patches and confirm idempotency. Specifically: each one should start with a guard like `if frappe.db.get_value(...) == "expected": return` so re-running is a no-op. If they currently re-run their work blindly, a `bench migrate` on a healthy site could corrupt data.
- [ ] **Tier 1** Manually run `bench --site hamilton-unit-test.localhost execute hamilton_erp.patches.v0_1.seed_hamilton_env` **twice in a row**. Second run must produce zero changes and zero errors.
- [ ] **Tier 2** Add a `patches/README.md` explaining the version-folder convention and the rule "every patch is named for what it does, not when it was added."
- [ ] **Tier 2** Add an empty `patches/v0_2/` folder with `__init__.py` so the next patch has an obvious home and doesn't get dumped in `v0_1/` because that's where the others live.

### What will cost billable hours if missing

Non-idempotent patches are the #1 cause of "we ran bench migrate and the site is broken." A developer takes ~3 hours to forensically untangle a corrupted seed run. Idempotency-first is a 10-minute discipline up front.

---

## Part 6 — `hooks.py`: The Performance and Correctness Audit

### What Hamilton has

```python
fixtures = [...]                              # filtered, scoped — good
after_install = "...install.after_install"    # idempotent — good
after_migrate = "...install.ensure_setup_complete"  # heals dev-site bug — good
extend_doctype_class = {"Sales Invoice": "...HamiltonSalesInvoice"}  # v16 idiom — good
doc_events = {"Sales Invoice": {"on_submit": "...on_sales_invoice_submit"}}  # narrow scope — good
scheduler_events = {"cron": {"*/15 * * * *": ["...check_overtime_sessions"]}}  # explicit cron — good
```

This is a clean `hooks.py`. No wildcards, no `"*"` doc_event subscriptions, no try/except blocks hiding errors. The comments explain *why* each hook exists, not just what it does.

### Performance traps to avoid (none of which Hamilton has — keep it that way)

- **`doc_events = {"*": {...}}`** — wildcard subscriptions fire on every save of every doctype. ERPNext has hundreds of doctypes. Even a no-op handler costs measurable latency on Sales Invoice saves. Never use wildcards.
- **`override_whitelisted_methods`** — overriding a frappe core method affects every custom app on the site. Use `extend_doctype_class` instead, which Hamilton already does.
- **`get_permission_query_conditions`** that does a `frappe.db.sql()` on every list view load. If used, cache aggressively.
- **`before_save` doing network I/O** — never do HTTP calls or external DB calls inside doc_events. They block the user's request thread. Enqueue a background job instead.
- **`scheduler_events` with broad cron expressions** like `"* * * * *"` (every minute) running heavy work. Hamilton's `*/15 * * * *` is appropriate.

### Audit checklist

- [ ] **Tier 1** For every function path in `hooks.py`, confirm the function exists. A typo in a hook path causes silent failures that only surface when the hook fires (which may be days later for `after_uninstall`). Use:
  ```bash
  grep -E "^\s*\"" hamilton_erp/hooks.py | grep -oE "hamilton_erp\.[a-z_.]+" | while read fn; do
    file=$(echo "$fn" | tr '.' '/' | sed 's/^/hamilton_erp\//' | xargs -I {} echo "{}.py")
    echo "$fn → $file"
  done
  ```
- [ ] **Tier 2** Add `boot_session = "hamilton_erp.boot.boot_session"` if you want to push Hamilton-specific config (feature flags, asset board endpoint) into the JS `frappe.boot` object on login. Saves an extra API call per page load.
- [ ] **Tier 2** Document which doctypes Hamilton's `on_sales_invoice_submit` *can* receive. Currently it filters by `has_admission_item()` — but a future contributor may not know that retail-only sales pass through silently.
- [ ] **Tier 3** Consider adding `validate_modified` to lock concurrent edits on Venue Asset more aggressively. Currently the `version` field + Redis lock handle this, but a defense-in-depth layer doesn't hurt.

---

## Part 7 — CI/CD with GitHub Actions: 🔴 The Single Biggest Gap

### Current state

`.github/workflows/` contains exactly one file: `claude-review.yml` (qodo-ai/pr-agent for PR comments). **There is no test-runner workflow.** This means:

- A push to main can break the test suite without being caught until someone runs tests locally.
- A PR can be merged by Claude with no automated verification that 306+ tests still pass.
- The first time anyone learns the suite is red is when Frappe Cloud auto-deploys the broken commit.

This is the highest-priority production readiness gap in the entire audit.

### What a Frappe-aware CI workflow looks like

A minimal, repo-aware workflow for Hamilton:

```yaml
# .github/workflows/tests.yml
name: tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mariadb:
        image: mariadb:10.6
        env:
          MARIADB_ROOT_PASSWORD: admin
        ports: ["3306:3306"]
        options: >-
          --health-cmd="healthcheck.sh --connect --innodb_initialized"
          --health-interval=10s --health-timeout=5s --health-retries=10
      redis-cache:
        image: redis:6-alpine
        ports: ["13000:6379"]
      redis-queue:
        image: redis:6-alpine
        ports: ["11000:6379"]

    steps:
      - uses: actions/checkout@v4
        with:
          path: hamilton_erp

      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }

      - uses: actions/setup-node@v4
        with: { node-version: "20" }

      - name: Install bench
        run: |
          pip install frappe-bench
          bench init --skip-redis-config-generation --frappe-branch version-16 frappe-bench
          cd frappe-bench
          bench get-app --branch version-16 erpnext
          bench get-app ../hamilton_erp
          bench new-site --mariadb-root-password admin --admin-password admin --no-mariadb-socket --install-app erpnext --install-app hamilton_erp ci.localhost

      - name: Run tests
        working-directory: frappe-bench
        run: bench --site ci.localhost run-tests --app hamilton_erp
```

This is ~50 lines and replicates `/run-tests` in CI.

### Action items

- [ ] **Tier 1** Create `.github/workflows/tests.yml`. Fail loud (don't `continue-on-error`).
- [ ] **Tier 1** Add a branch protection rule on main: PRs cannot merge unless `tests` is green.
- [ ] **Tier 2** Add a second workflow `lint.yml` that runs `ruff check` and `ruff format --check` on every PR. Hamilton already has ruff configured in `pyproject.toml`.
- [ ] **Tier 2** Add a `bench migrate` step after the test step to catch patches that fail on a non-test site.
- [ ] **Tier 3** Add a nightly cron workflow that re-runs the suite against `version-16` (latest) Frappe + ERPNext to catch upstream regressions before they hit Frappe Cloud.
- [ ] **Tier 3** Cache the bench environment between runs (the bench setup is the slow part — caching shaves 5–7 minutes off each run).

### What this will cost if missing

A single bad commit reaching Frappe Cloud auto-deploy = ~30 minutes downtime + a bench rollback that touches database state + an emergency hotfix push. CI prevents this. **This is the highest-leverage 90 minutes of work in the entire pre-handoff list.**

---

## Part 8 — Role-Based Permissions, Field Masking, User Permissions

### What v16 brings

Frappe v16 deepens the field-level permission system. Each field on a DocType has a numeric "permlevel" (default 0). You can grant Read/Write to permlevel 1 to one role and Read-only to another role — letting a `Hamilton Operator` see a Venue Asset's room number and status but not its purchase price (permlevel 1).

Hamilton has three roles and zero field-level permissions in use. That's fine for Phase 1 (single-operator model). Phase 2 (POS, Manager-tier) will need them.

### What's already done well

- `Hamilton Operator`, `Hamilton Manager`, `Hamilton Admin` roles created idempotently in `after_install`.
- All 9 whitelisted API endpoints call `frappe.has_permission(..., throw=True)` before doing work — this is the gold standard.
- `_block_pos_closing_for_operator()` removes the standard POS Closing Entry permission for operators, enforcing the blind cash control model (DEC-005).
- All API endpoints declare `methods=["GET"]` or `methods=["POST"]` explicitly — this prevents the HTTP-method CSRF gap that hit Frappe Press in CVE-2026-41317 (where a state-changing endpoint was reachable via GET, bypassing CSRF).

### Action items

- [ ] **Tier 1** Audit every field on every Hamilton DocType for whether it should be permlevel 0 (visible to all roles with Read) or permlevel 1+ (manager/admin only). Likely candidates for permlevel 1: `expected_revenue`, `cash_drop_expected_total`, anything with cost or financial info. Even if Hamilton doesn't use these fields today, planning the levels now means Phase 2 doesn't require a schema migration.
- [ ] **Tier 2** Run `bench --site $SITE list-permissions --doctype "Venue Asset"` (or use Role Permission Manager in the UI) and screenshot/export the matrix. Commit to `docs/security/permission_matrix.md`. This becomes the "what should be true" reference for handoff and for future audits.
- [ ] **Tier 2** Document `ignore_permissions=True` usage. Every call site in `lifecycle.py` (4 places) needs a one-line comment: *why* it's safe to bypass permissions here. Lock-protected? Already validated upstream? Internal background job? Each one needs a justification or a refactor.
- [ ] **Tier 3** For multi-venue (Phase 2 Philadelphia/DC/Dallas), implement `permission_query_conditions` on `Venue Asset` to filter by venue. Without this, a Hamilton operator could see Philadelphia assets in a List View. Single-venue today = no risk; multi-venue = critical.

### What will cost billable hours if missing

A developer who finds undocumented `ignore_permissions=True` calls assumes the worst (security hole). They will either rewrite them or schedule a 2-hour security review with you. A one-line comment per call site closes the question for free.

---

## Part 9 — Audit Trail vs Document Versioning

These are two **different** features that get confused:

| Feature | What it does | When to use |
|---|---|---|
| **Document Versioning** | Per-DocType opt-in (Customize Form → Track Changes). Every change to a tracked field creates a Version row with the diff and the user. | "Who changed this field, when, from what to what?" — supports operational audit. |
| **Audit Trail** | Site-wide setting (System Settings → Audit Trail). Logs every read/write/delete across all DocTypes for users in specific roles. | "What did this user touch in their entire shift?" — supports compliance audit. |

Hamilton needs both. Operationally, you want to know who marked a room OOS at 11:42pm. Compliance-wise, you want to know which operator was active during a cash-drop discrepancy.

### Action items

- [ ] **Tier 1** Enable Track Changes on these DocTypes minimum: **Venue Asset**, **Venue Session**, **Cash Drop**, **Cash Reconciliation**, **Shift Record**, **Asset Status Log**. Do this once via Customize Form, then export the result as a Property Setter fixture so it propagates to Philadelphia/DC/Dallas.
- [ ] **Tier 1** Enable Audit Trail at System Settings level for the `Hamilton Operator`, `Hamilton Manager`, and `Hamilton Admin` roles.
- [ ] **Tier 2** Configure Log Settings → retention. Default Frappe retention can be aggressive (30 days); for compliance, Hamilton likely needs 1+ years on Activity Log, Error Log, Version. Set explicitly.
- [ ] **Tier 2** Add a brief operations doc `docs/operations/audit.md` explaining where to look for "who did what" — Version Log, Activity Log, Error Log, Asset Status Log (Hamilton-custom).
- [ ] **Tier 3** Build a saved report "Operator Activity by Shift" combining Shift Record + Activity Log filtered by user. Use this when reconciling cash drops.

### What will cost billable hours if missing

The first time you have a cash-drop discrepancy and can't reconstruct who was on shift at 10:14pm + what they marked + what the cash drawer was last expected to be, you will spend an entire day reading raw MariaDB tables. Audit trail = 10 minutes of UI configuration today. Forensic SQL spelunking = a billable day later.

---

## Part 10 — Frappe Scheduler Jobs & Background Workers

### Hamilton's current setup

```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": ["hamilton_erp.tasks.check_overtime_sessions"],
    },
}
```

One job, every 15 minutes, checking for overtime sessions. The cron expression is correct (Frappe v16 supports standard 5-field cron). The function path is real (`tasks.py:check_overtime_sessions`).

### What can go wrong in production

1. **The scheduler stops.** The most common production silent failure. The Frappe scheduler is a separate process; if it crashes, no error appears anywhere obvious — overtime detection just stops happening. By the time someone notices, you have 50 sessions that should have been flagged.
2. **The job throws and the next run runs the broken code.** No automatic backoff. A bad deploy can cause the scheduler to log errors every 15 minutes for 12 hours straight, filling the Error Log.
3. **The job takes longer than the interval.** If `check_overtime_sessions` ever takes >15 minutes (because it's iterating every Venue Session ever created), the next run starts before the previous one finished. RQ allows this; it's expensive.
4. **The job runs on a bench update during a deploy.** New code, mid-job. Half the work runs against the old schema, half against the new.
5. **Frappe sets a max of 500 queued jobs.** Once exceeded, `frappe.enqueue` starts failing silently. A scheduler that fans out heavy work can hit this.

### Action items

- [ ] **Tier 1** Add a "scheduler heartbeat" job that runs every 5 minutes and writes a timestamp to a Log doctype (or to `Hamilton Settings.scheduler_last_seen`). Then add a separate Manager-facing alert if `scheduler_last_seen > now() - interval 15 minute`. This is the cheapest dead-scheduler detector.
- [ ] **Tier 1** Wrap the body of `check_overtime_sessions` in a `try/except` that logs to Error Log via `frappe.log_error()` with a specific title (`"Overtime Detection Failed"`) and re-raises. Without this, scheduler failures are silent. With this, you get one clear Error Log entry per failure that's easy to filter.
- [ ] **Tier 2** Add an integration test that asserts `check_overtime_sessions` completes in <2 seconds against a populated test database. Catches O(n²) regressions before they reach prod.
- [ ] **Tier 2** Add bench command alias for one-off manual runs: `bench --site $SITE execute hamilton_erp.tasks.check_overtime_sessions`. Document in `docs/operations/runbook.md` so the operator can poke it manually if the scheduler is down.
- [ ] **Tier 3** If Hamilton ever adds heavy nightly jobs (cleanup, archival), use `cron_long` instead of `cron` so they run on the long-running worker queue and don't starve short jobs.

---

## Part 11 — Frappe Cloud Operations

### Error log monitoring

Frappe Cloud captures every server exception as an Error Log row with a stack trace, the request body, the user, and a snapshot ID. Files corresponding to each snapshot land in `./sites/$SITE/error-snapshots/`.

- [ ] **Tier 1** Configure Log Settings → Error Log → set retention to at least 90 days. Default is 30, which is too short for "a customer complained two months ago" investigations.
- [ ] **Tier 1** Configure email alerts on Error Log → set a notification rule that emails Chris when Error Log frequency exceeds N per hour. Tune N after a week of baseline (likely 5–10).
- [ ] **Tier 2** Add a saved report "Errors in last 24h grouped by exception type" pinned to the System Manager dashboard. First thing anyone sees on login.

### Backups

Frappe Cloud takes daily backups by default. **Daily is not enough for a venue that does cash transactions.**

- [ ] **Tier 1** Enable Frappe Cloud's hourly backups on hamilton-erp.v.frappe.cloud. (Setting in Frappe Cloud dashboard → Backups.)
- [ ] **Tier 1** Enable backup encryption. Once enabled, **save the encryption key in a separate password manager from the Frappe Cloud login**. If you ever need to restore a backup to a fresh site, you need the key from the original `site_config.json` to read encrypted password fields. Lose the key = lose every encrypted password (email, API, social login).
- [ ] **Tier 1** Run a real restore drill: spin up a fresh Frappe Cloud site, restore the most recent hamilton backup to it, verify you can log in and the asset board loads. Document the procedure in `docs/operations/disaster_recovery.md`. **This must be done before go-live, not after.** The first restore attempt always finds something missing (the encryption key, the right Frappe version, a fixture that didn't import).
- [ ] **Tier 2** Configure offsite backup destination in Frappe Cloud (S3 or equivalent). Default Frappe Cloud backups live on the same infrastructure; a region-wide outage takes both prod and backup with it.

### Version pinning

Already noted in `claude_memory.md` (Frappe Cloud Version Pinning). Repeating here for completeness:

- [ ] **Tier 1** Before go-live: pin hamilton-erp.v.frappe.cloud to a specific stable v16 minor (e.g., v16.14.0). Disable auto-update to latest. Document the pinned version in `docs/app_compatibility.md`. **Reason:** v16.14.0 (released 2026-04-14) removed forced six-decimal rounding on valuation rate fields; future minor versions may make similar invariant-breaking changes that need to be deliberately tested before adoption.

### Site config & secrets

Hamilton's `site_config.json` on Frappe Cloud will contain (minimum): the encryption key, the database password, and any third-party API keys (Phase 2: Stripe). These are not in the repo. They cannot be in the repo.

- [ ] **Tier 1** Audit `site_config.json` on prod. Confirm none of these are committed to git: `db_password`, `encryption_key`, `admin_password`, any `stripe_*`, any `mail_password`. Run: `git log --all -p -- "**/site_config*.json" | head -200` to see if anything ever leaked historically.
- [ ] **Tier 1** Save the prod `site_config.json` (with secrets) to a password manager entry separate from Frappe Cloud login. If you ever need to restore the site to non-Frappe-Cloud infrastructure, you need this file.
- [ ] **Tier 2** Document the secrets inventory in `docs/operations/secrets.md` (where each secret lives, who has access, rotation cadence) — without the actual values.
- [ ] **Tier 2** Set up a quarterly reminder to rotate the encryption key (process: take backup, restore to new site with new key, cut over, decommission old). Yearly is acceptable for low-risk single-tenant deployments.

---

## Part 12 — Production Security Hardening

### What's already done well in Hamilton

- Every whitelisted endpoint declares `methods=["GET"]` or `methods=["POST"]`. **This single discipline closes the entire CSRF-via-GET attack class.**
- Every endpoint calls `frappe.has_permission(..., throw=True)` before doing work.
- `frappe.db.sql()` is used in only **2 places** (`lifecycle.py:660`, `locks.py:95`) — both with parameterised queries. SQL injection surface is tiny.
- Tests in `test_adversarial.py` actively try to break the lifecycle/lock model.

### Common production security holes (none of which Hamilton currently has — keep it that way)

| Pattern | Risk | Hamilton status |
|---|---|---|
| `@frappe.whitelist()` without `methods=[...]` | CSRF via GET | ✅ All endpoints declare method |
| `@frappe.whitelist(allow_guest=True)` on a state-changing endpoint | Anonymous access | ✅ Not used |
| `ignore_permissions=True` without justification | Privilege escalation | 🟡 4 sites in lifecycle.py — need justification comments |
| `frappe.db.sql(f"... {user_input} ...")` | SQL injection | ✅ Only 2 SQL calls; both parameterised |
| `frappe.get_attr(user_input)` | Arbitrary code execution | ✅ Not used (verified via grep) |
| User-supplied filter dict passed unvalidated to `frappe.get_all` | Data leak via filter manipulation | ✅ Endpoints take typed scalars, not dicts |
| `frappe.utils.escape_html` not called on user input rendered in JS | XSS | ✅ Per Prompt 5 audit, used inline in `asset_board.js` |

### Action items

- [ ] **Tier 1** Add a justification comment above every `ignore_permissions=True` site in `lifecycle.py`. Template:
  ```python
  # ignore_permissions=True is safe here because:
  # - Caller is gated by frappe.has_permission("Venue Asset", "write") at API entry (api.py:N)
  # - Asset is held under hamilton:asset_lock:{name} for the duration of this save
  # - The mutation is bounded to fields owned by lifecycle.py (status, current_session, last_*_at)
  ```
- [ ] **Tier 1** Run a one-shot audit of guest-accessible endpoints:
  ```bash
  grep -rn "allow_guest" hamilton_erp/ | grep -v test_
  ```
  Confirm zero results. Re-run on every release.
- [ ] **Tier 2** Add a CI step that fails the build if any new `frappe.whitelist()` is added without explicit `methods=[...]`. One-liner:
  ```bash
  grep -rn "@frappe.whitelist()" hamilton_erp/ --include="*.py" | grep -v test_ | grep -v "methods=" && exit 1 || exit 0
  ```
- [ ] **Tier 2** Run `bench --site $SITE migrate-to` against a fresh CSRF-aware integration test. Validate that every state-changing endpoint **rejects** a request without an `X-Frappe-CSRF-Token` header.
- [ ] **Tier 2** Audit Hamilton's User Permissions on prod: which users have `System Manager`? Anyone with that role can read/write everything, bypassing the role model. Likely correct list: Chris + 1 backup admin. Anyone else is a finding.
- [ ] **Tier 3** Add `rate_limit` to the bulk-action endpoints (`mark_all_clean_rooms`, `mark_all_clean_lockers`). Frappe v16 supports `frappe.rate_limit()` — even 60/minute is enough to stop a runaway client from DoS'ing the database.
- [ ] **Tier 3** Subscribe to GitHub security advisories on `frappe/frappe` and `frappe/erpnext`. The 2025–2026 CVE rate has been roughly one per quarter; you want to know within hours, not weeks.

### What will cost billable hours if missing

A penetration test (which the new developer may run as part of acceptance) will find every missing justification comment, every `allow_guest`, every rate-limit-free bulk endpoint. Each finding becomes a billable hour to fix and re-test. Hamilton is in good shape — finishing the last 10% (justification comments, rate limits, CSRF assertion) is faster than reacting to the audit later.

---

## Part 13 — Environment Bootstrap (`init.sh` Pattern)

### What it is

A single shell script at the repo root that sets up the dev environment from a clean machine. Anthropic's harness research recommends this pattern: any developer (or AI agent) can run `./init.sh` and end up with a working bench, a fresh test site, and a passing test run.

### Hamilton's current state

There is no `init.sh`. Setup instructions are spread across CLAUDE.md (mentions paths), `docs/testing_checklist.md`, and `docs/troubleshooting.md`.

### Action items

- [ ] **Tier 2** Create `init.sh` at repo root. Template:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail

  BENCH_DIR="${BENCH_DIR:-$HOME/frappe-bench-hamilton}"
  SITE="${SITE:-hamilton-unit-test.localhost}"
  PYTHON="${PYTHON:-$HOME/.pyenv/versions/3.11.9/bin/python}"

  echo "==> Verifying bench at $BENCH_DIR"
  test -d "$BENCH_DIR" || { echo "Run bench init first; see docs/setup.md"; exit 1; }

  cd "$BENCH_DIR"
  source env/bin/activate

  echo "==> Verifying site $SITE"
  bench --site "$SITE" doctor
  bench --site "$SITE" show-pending-jobs

  echo "==> Running test suite"
  bench --site "$SITE" run-tests --app hamilton_erp

  echo "==> Done."
  ```
- [ ] **Tier 2** Add a `docs/setup.md` covering: (1) clone, (2) `bench init`, (3) `bench get-app`, (4) `bench new-site`, (5) `./init.sh`. Should fit on one page. New developer should reach a green test run inside 30 minutes.
- [ ] **Tier 3** Add a `docs/troubleshooting.md` cross-reference at the bottom of `init.sh` so the obvious failure modes (Redis not running, MariaDB password wrong, Python version mismatch) point at the right doc section.

### What will cost billable hours if missing

A developer who has to figure out the bench setup from `claude_memory.md` + `CLAUDE.md` + `testing_checklist.md` will burn 2–4 hours and arrive grumpy. A 40-line `init.sh` plus a one-page setup doc converts that into 20 minutes.

---

## Part 14 — Prioritized Production Readiness Checklist

This is the master action list, sorted by what breaks production if missing.

### Tier 1 — Block production launch (the "must do before go-live" list)

| # | Item | Section | Est. Time |
|---|---|---|---|
| T1.1 | Create `.github/workflows/tests.yml` — full CI test runner | Part 7 | 90 min |
| T1.2 | Add branch protection on `main` requiring tests green | Part 7 | 5 min |
| T1.3 | Verify `bench export-fixtures` produces zero diff against committed JSON | Part 4 | 30 min |
| T1.4 | Verify both patches are idempotent (run twice, expect no-op) | Part 5 | 30 min |
| T1.5 | Audit every function path in `hooks.py` resolves to a real function | Part 6 | 15 min |
| T1.6 | Add justification comments above every `ignore_permissions=True` in `lifecycle.py` | Part 12 | 30 min |
| T1.7 | Enable Track Changes on Venue Asset, Venue Session, Cash Drop, Cash Reconciliation, Shift Record, Asset Status Log | Part 9 | 20 min |
| T1.8 | Enable Audit Trail (System Settings) for Hamilton Operator/Manager/Admin roles | Part 9 | 10 min |
| T1.9 | Enable Frappe Cloud hourly backups + backup encryption + save key to password manager | Part 11 | 30 min |
| T1.10 | Run a real backup → restore drill on a fresh Frappe Cloud site, document procedure in `docs/operations/disaster_recovery.md` | Part 11 | 90 min |
| T1.11 | Pin Frappe Cloud site to specific v16 minor version, disable auto-update | Part 11 | 15 min |
| T1.12 | Audit `site_config.json` for committed secrets (history scan) | Part 11 | 15 min |
| T1.13 | Configure Error Log retention (90 days minimum) and email alerting | Part 11 | 20 min |
| T1.14 | Add scheduler heartbeat job + dead-scheduler alert | Part 10 | 60 min |
| T1.15 | Wrap `check_overtime_sessions` in try/except with `frappe.log_error()` | Part 10 | 15 min |
| T1.16 | Write a real `README.md` (replaces the 2-line placeholder) | Part 2 | 30 min |

**Tier 1 subtotal: ~7.5 hours of work.** This is the minimum to block-or-pass for production.

### Tier 2 — Strongly recommended (incidents within first month if missing)

| # | Item | Section | Est. Time |
|---|---|---|---|
| T2.1 | Add `lint.yml` workflow (ruff check + format check) | Part 7 | 20 min |
| T2.2 | Add `bench migrate` step to CI (catches patches that fail in non-test contexts) | Part 7 | 15 min |
| T2.3 | Audit and document permlevel for every field on Hamilton DocTypes | Part 8 | 60 min |
| T2.4 | Export permission matrix to `docs/security/permission_matrix.md` | Part 8 | 30 min |
| T2.5 | Configure Log Settings retention for Activity Log, Version, Email Queue | Part 9 | 15 min |
| T2.6 | Add `docs/operations/audit.md` (where to look for "who did what") | Part 9 | 30 min |
| T2.7 | Add integration test asserting `check_overtime_sessions` <2s against populated DB | Part 10 | 45 min |
| T2.8 | Document manual-run bench commands in `docs/operations/runbook.md` | Part 10 | 45 min |
| T2.9 | Configure Frappe Cloud offsite backup destination (S3 or equivalent) | Part 11 | 20 min |
| T2.10 | Document secrets inventory (without values) in `docs/operations/secrets.md` | Part 11 | 30 min |
| T2.11 | Add CI guard rejecting new `@frappe.whitelist()` without `methods=[...]` | Part 12 | 15 min |
| T2.12 | Add CSRF-rejection integration test for state-changing endpoints | Part 12 | 60 min |
| T2.13 | Audit System Manager role assignments on prod | Part 12 | 10 min |
| T2.14 | Create `init.sh` and `docs/setup.md` (30-min onboarding) | Part 13 | 90 min |
| T2.15 | Add empty `patches/v0_2/` placeholder + `patches/README.md` | Part 5 | 15 min |
| T2.16 | Add `app_compatibility.md` documenting verified Frappe/ERPNext/MariaDB minor versions | Part 3 | 20 min |
| T2.17 | Add a saved Error Log report "Errors in last 24h by exception type" pinned to dashboard | Part 11 | 15 min |
| T2.18 | Add `boot_session` hook to push Hamilton config to `frappe.boot` (saves an API call per page load) | Part 6 | 30 min |

**Tier 2 subtotal: ~8 hours of work.** Optional but high-leverage.

### Tier 3 — Nice to have (saves operational toil)

| # | Item | Section | Est. Time |
|---|---|---|---|
| T3.1 | Cache bench environment in CI (shaves 5–7 min off each run) | Part 7 | 30 min |
| T3.2 | Nightly cron workflow against latest `version-16` Frappe + ERPNext | Part 7 | 30 min |
| T3.3 | Add `before_uninstall` hook with safety prompt | Part 3 | 15 min |
| T3.4 | Add `make export-fixtures` (or bench alias) with built-in git diff check | Part 4 | 15 min |
| T3.5 | Build saved report "Operator Activity by Shift" combining Shift Record + Activity Log | Part 9 | 60 min |
| T3.6 | Add `frappe.rate_limit()` to bulk-action endpoints | Part 12 | 30 min |
| T3.7 | Subscribe to security advisories on `frappe/frappe` + `frappe/erpnext` | Part 12 | 5 min |
| T3.8 | Set quarterly encryption-key rotation reminder | Part 11 | 5 min |

**Tier 3 subtotal: ~3 hours of work.**

### Tier 4 — Phase 2 prep (do during/after handoff, not before)

| # | Item | Section |
|---|---|---|
| T4.1 | Implement `permission_query_conditions` on `Venue Asset` for venue isolation | Part 8 |
| T4.2 | Adopt `cron_long` queue for any future heavy nightly jobs | Part 10 |
| T4.3 | Add `validate_modified` on Venue Asset for defense-in-depth concurrency | Part 6 |

---

## Part 15 — The "What This Will Cost You If Missing" Heuristic

Use this when prioritising. For each Tier 1 item, the cost-of-missing is roughly:

| Missing item | Worst-case incident | Est. dollar cost |
|---|---|---|
| CI test runner | Bad commit auto-deploys → 30 min downtime + emergency rollback | $500–$2k (lost revenue + dev time) |
| Backup restore drill not done | Real restore needed, encryption key lost or version mismatch → can't restore | $5k–$50k (data loss + reconstruction) |
| Audit trail not enabled | Cash discrepancy, no record of who did what → forensic SQL day | $1k–$3k (dev time) |
| Scheduler heartbeat | Scheduler crashes silently at 6pm Friday, overtime detection dead all weekend | Operational chaos, customer disputes |
| `ignore_permissions` not justified | Pen-test or new dev finding → 2-hour security review | $300–$600 (dev time) |
| Site config secrets in git history | Anyone with repo read access can read prod credentials | Catastrophic |
| Version pinning | Frappe v16.15 ships breaking change overnight, asset board breaks | $1k + rushed rollback |

**Heuristic:** Tier 1 items map to incidents that cost more than the time to fix them. Always do them first.

---

## Part 16 — Final Pre-Deploy Sanity Check (the night before going live)

Before flipping hamilton-erp.v.frappe.cloud from staging to production:

```bash
# 1. Working tree is clean
git status                     # must be empty
git log origin/main..HEAD      # must be empty (everything pushed)

# 2. Test suite is green on the latest commit
bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp

# 3. CI is green on the latest commit
gh run list --workflow=tests.yml --limit=1   # must show success

# 4. Fixtures are clean (no drift)
bench --site hamilton-unit-test.localhost export-fixtures --app hamilton_erp
git diff --stat hamilton_erp/fixtures/       # must be empty

# 5. Patches are idempotent (run twice)
for p in $(grep '^hamilton_erp' hamilton_erp/patches.txt); do
  bench --site hamilton-unit-test.localhost execute "$p"
  bench --site hamilton-unit-test.localhost execute "$p"   # second run is no-op?
done

# 6. hooks.py functions resolve
python -c "
from importlib import import_module
import hamilton_erp.hooks as h
for path in [h.after_install, h.after_migrate]:
    mod, _, fn = path.rpartition('.')
    getattr(import_module(mod), fn)
print('All hook paths resolve')
"

# 7. No committed secrets
git log --all -p -- "**/site_config*.json" | head -50    # must show nothing sensitive

# 8. No allow_guest endpoints
grep -rn "allow_guest" hamilton_erp/ --include="*.py" | grep -v test_   # must be empty

# 9. Frappe Cloud version matches expected pin
# (eyeball in Frappe Cloud dashboard)

# 10. Backup taken in last hour (Frappe Cloud dashboard)

# 11. Restore drill documented and recently rehearsed (within last 30 days)
ls -la docs/operations/disaster_recovery.md
```

If any step is red, do not deploy.

---

## Appendix A — Quick-Win Bash Commands to Run Before Handoff

These are one-shot commands to surface the obvious gaps. Run them, fix what they find.

```bash
# 1. Find every function referenced in hooks.py and verify it exists
python <<'PY'
import importlib
import hamilton_erp.hooks as h
paths = []
for k, v in vars(h).items():
    if isinstance(v, str) and "hamilton_erp" in v:
        paths.append((k, v))
    if isinstance(v, dict):
        for kk, vv in v.items():
            if isinstance(vv, str) and "hamilton_erp" in vv:
                paths.append((f"{k}.{kk}", vv))
            elif isinstance(vv, dict):
                for kkk, vvv in vv.items():
                    if isinstance(vvv, list):
                        for fn in vvv:
                            paths.append((f"{k}.{kk}.{kkk}", fn))
for label, path in paths:
    mod, _, fn = path.rpartition('.')
    try:
        m = importlib.import_module(mod)
        getattr(m, fn)
        print(f"OK   {label}: {path}")
    except Exception as e:
        print(f"FAIL {label}: {path}  ({e})")
PY

# 2. Find every whitelist endpoint and check method declaration
grep -rn "@frappe.whitelist" hamilton_erp/ --include="*.py" | grep -v test_

# 3. Find every ignore_permissions=True without a comment
grep -B 2 "ignore_permissions=True" hamilton_erp/*.py | head -60

# 4. Count tests
ls hamilton_erp/test_*.py | wc -l

# 5. Verify fixtures export is clean
bench --site hamilton-unit-test.localhost export-fixtures --app hamilton_erp
git diff --stat hamilton_erp/fixtures/

# 6. Find any TODOs / FIXMEs that should be tickets
grep -rn "TODO\|FIXME\|XXX\|HACK" hamilton_erp/ --include="*.py" | grep -v test_

# 7. Find unused imports
ruff check --select F401 hamilton_erp/

# 8. Find functions over 50 lines (potential refactor candidates)
python <<'PY'
import ast, pathlib
for f in pathlib.Path("hamilton_erp").rglob("*.py"):
    if "test_" in f.name: continue
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines = (node.end_lineno or 0) - node.lineno
            if lines > 50:
                print(f"{f}:{node.lineno}  {node.name}  ({lines} lines)")
PY
```

---

## Appendix B — Caveats & Research Gaps

Honest notes on where this audit is thinner than I'd like:

1. **Frappe Cloud-specific dashboard configuration is documented from public sources** (frappe.io/cloud, the Frappe blog). I did not log into the actual Frappe Cloud dashboard to verify the exact UI paths for things like "enable hourly backups" or "configure email alerting." Treat the action items as "go find this in Frappe Cloud and turn it on" not "click here, then click there."

2. **Field-level permission (permlevel) examples are general, not Hamilton-specific.** I did not enumerate every field on every Hamilton DocType to recommend a specific permlevel. The Tier 2 audit task (T2.3) is the work of doing that — I flagged it as work to do, not work I did.

3. **Frappe v16's exact new RBAC features beyond the v15 baseline are under-documented in public sources.** The v16 release notes I could find emphasised performance and new doctypes, not security. If v16 introduced a permission feature that supersedes anything in this doc, verify against `docs.frappe.io/framework/v16/...` (which was incomplete at the time of this research).

4. **Audit Trail at System Settings level is referenced in docs but I did not find the exact UI path or the JSON shape of the trail rows.** Tier 1 item T1.8 will require ~5 min of clicking around to confirm the location.

5. **Backup encryption key rotation procedure is documented in general terms** but Frappe doesn't ship a one-command rotation tool. The "take backup, restore to new site with new key, cut over" flow in T3.8 is the established pattern from forum discussion, not an officially blessed procedure. Document carefully when you do it.

6. **The CI workflow in Part 7 is a template.** It will need ~1 cycle of trial-and-error against actual GitHub Actions runners to nail down: the exact MariaDB image tag, whether the test site needs `--mariadb-socket` or `--no-mariadb-socket`, whether `bench get-app` needs `--branch version-16` or `--branch develop`. Budget 90 minutes (T1.1) accordingly.

7. **`Custom DocPerm` and the `_block_pos_closing_for_operator()` flow** — Hamilton's pattern (delete the row in `after_install`) works on first install but won't be re-applied if the row is recreated by an ERPNext upgrade. A future ERPNext minor version that ships a fresh `POS Closing Entry` permission row could silently grant operators access to expected cash totals. Worth converting to a fixture or a periodic check.

---

## Appendix C — Sources

### Frappe / ERPNext official
- [Fixtures and Custom Fields — frappe/erpnext wiki](https://github.com/frappe/erpnext/wiki/Export-Custom-field-using-export-fixtures)
- [Code Security Guidelines — frappe/erpnext wiki](https://github.com/frappe/erpnext/wiki/Code-Security-Guidelines)
- [Database Migrations — Frappe docs](https://docs.frappe.io/framework/v15/user/en/database-migrations)
- [Logging — Frappe docs](https://docs.frappe.io/framework/user/en/logging)
- [Profiling and Monitoring — Frappe docs](https://docs.frappe.io/framework/v15/user/en/profiling)
- [Background Jobs — Frappe docs](https://docs.frappe.io/framework/user/en/api/background_jobs)
- [Audit Trail — Frappe docs](https://docs.frappe.io/framework/user/en/audit-trail)
- [Document Versioning — Frappe docs](https://docs.frappe.io/erpnext/user/manual/en/document-versioning)
- [Versioning and Audit Trail — Frappe blog](https://frappe.io/blog/erpnext-features/versioning-and-audit-trail)
- [Role Based Permissions — Frappe docs](https://docs.frappe.io/erpnext/user/manual/en/role-based-permissions)
- [Field Level Permission Management — Frappe docs](https://docs.frappe.io/erpnext/changing-the-properties-of-a-field-based-on-role)
- [How to Enable Backup Encryption — Frappe docs](https://docs.frappe.io/framework/user/en/guides/basics/how-to-enable-backup-encryption)
- [Restore & Migrate Site — Frappe Cloud docs](https://docs.frappe.io/cloud/sites/migrate-an-existing-site)
- [Backup on Frappe Cloud](https://frappe.io/cloud/backup)
- [Monitoring — Frappe Cloud docs](https://frappecloud.com/docs/sites/monitoring)
- [MariaDB slow queries in your site — Frappe Cloud FAQ](https://docs.frappe.io/cloud/faq/mariadb-slow-queries-in-your-site)
- [Database Optimization — Frappe docs](https://docs.frappe.io/framework/user/en/database-optimization-hardware-and-configuration)
- [REST API — Frappe docs](https://docs.frappe.io/framework/user/en/api/rest)
- [ERPNext Performance Tuning — frappe/erpnext wiki](https://github.com/frappe/erpnext/wiki/ERPNext-Performance-Tuning)
- [Restoring From ERPNext Backup — frappe/erpnext wiki](https://github.com/frappe/erpnext/wiki/Restoring-From-ERPNext-Backup)

### Practitioner blogs and community
- [Mastering ERPNext 16: The Complete Guide to Custom Apps — David Muraya](https://davidmuraya.com/blog/develop-erpnext-custom-app/)
- [How to setup CI/CD for the Frappe Applications using GitHub Actions — Frappe DevOps](https://frappedevops.hashnode.dev/how-to-setup-ci-cd-for-the-frappe-applications-using-github-actions)
- [Frappe DevOps Toolkit: Monitor, Fix, and Deploy Like a Pro — Pranav Dixit](https://medium.com/@pranavdixit20/frappe-devops-toolkit-monitor-fix-and-deploy-like-a-pro-26d1be6a8015)
- [Frappe Framework v16 Release: Key Features & Impact — Indictran](https://www.indictranstech.com/frappe-framework-v16-whats-new-in-2026/)
- [Separation of Concerns: Logging in APIs over Frappe Framework — Alaa Alsalehi](https://alaa-alsalehi.medium.com/separation-of-concerns-logging-in-apis-over-frappe-framework-aae487326f37)
- [Installing Custom Apps in ERPNext: Comprehensive Guide — Aalam Info Solutions](https://medium.com/@aalam-info-solutions-llp/installing-custom-apps-in-erpnext-a-comprehensive-guide-to-move-data-custom-fields-and-doctypes-0b07ca60199e)
- [Fixtures and Custom Fields in Frappe and ERPNext — Code with Karani](https://codewithkarani.com/2021/09/06/fixtures-and-custom-fields-in-and-frappe-erpnext/)
- [Understanding Frappe's Encryption Key — Frappe Forum](https://discuss.frappe.io/t/understanding-frappe-s-encryption-key-data-security-backups-and-migration/152853)

### Security references
- [SQL Injection, Insufficient ACLs in Frappe Framework — Altion Security](https://www.altion.dk/posts/frappe-security-vulnerabilities)
- [CVE-2026-41317 — Frappe Press CSRF on API secret generation](https://cvefeed.io/vuln/detail/CVE-2026-41317)
- [Frappe Framework Vulnerabilities — CSIRT.SK](https://csirt.sk/frappe-framework-vulnerabilities.html)

### Product updates referenced
- [Frappe Product Updates — March 2026](https://frappe.io/blog/product-updates/product-updates-for-march-2026)
- [Frappe Product Updates — February 2026](https://frappe.io/blog/product-updates/product-updates-for-february-2026)

---

## Companion Document

For developer-handoff readiness (different lens, complementary checklist), see `docs/inbox/prompt5_handoff_audit_2026-04-25.md`.

Items appearing in both documents are not duplicate work — they are doubly-validated priorities. Examples:
- README.md gap (both audits flag it)
- CI test workflow (both audits flag it)
- `ignore_permissions` justification (both audits flag it)
- Setup script / `init.sh` (both audits flag it)

When two independent audits agree, the priority is real.
