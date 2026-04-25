# Hamilton ERP — Production & Handoff Readiness Audit (Merged)

**Date:** 2026-04-25
**Source prompt:** `docs/hamilton_pre_handoff_prompts.md` → Prompt 1 (ERPNext Production Best Practices Audit)
**Companion document:** `docs/inbox/prompt5_handoff_audit_2026-04-25.md` (developer-handoff readiness lens)
**This file is a merge** of two independent audits (one autonomous Claude Code research run + one fresh claude.ai research run on the same prompt). When two independent audits agree, the priority is real. Items appearing in both are doubly-validated.

**Audience:** Chris (beginner) preparing to hand off `hamilton_erp` to a professional Frappe/ERPNext v16 developer after Task 25, and to operate the system in production at Club Hamilton.

**Goal:** Catch every common production-incident risk and "I'll bill you extra for that" handoff item *before* go-live and handoff, while it's still cheap to fix.

---

## Legend

- 🔴 **Hard to fix after go-live or after handoff** — must be done now, before it's too late.
- 💰 **Will cost billable hours if missing or messy** — devs charge to clean these up.
- ✅ **Concrete action** — paste-able command or file change.
- 🟡 **Tier 2** — strongly recommended; missing this causes incidents within first month.
- 🟢 **Already done well** — verified in current repo state.

---

## Section 0 — The "If You Do Nothing Else" Top 10

Before Task 25 closes, these are non-negotiable. If items 1–8 aren't done, the dev's first invoice will include 5–15 hours of cleanup before they can start real work.

1. ✅ **Every custom field, property setter, workflow, role, and notification you created in the UI is exported as a fixture and committed to Git.** (See §4.)
2. ✅ **A working GitHub Actions CI runs your 270+ tests automatically on every push.** (See §7.) — Single highest-leverage 90 minutes in the entire pre-handoff list.
3. ✅ **Both Audit Trail and Document Versioning ("Track Changes") are enabled on every financial DocType** (Sales Invoice, Bathhouse Receivable Log, Bathhouse Shift, Venue Asset, Venue Session, Cash Drop, Cash Reconciliation, Shift Record, Asset Status Log). (See §9.) — 🔴 Permanent damage if delayed; every day = lost audit history that cannot be recovered.
4. ✅ **System Manager role is restricted to your account only. Cancel and Amend rights are locked to manager roles only.** (See §8.)
5. ✅ **`hooks.py` is audited:** no wildcards (`"*"`) in `doc_events`, every handler wrapped in `try/except`, `override_doctype_class` → `extend_doctype_class` correction applied. (See §6.)
6. ✅ **Every manual setting that has to exist on a fresh site** (PIN policies, default values, custom workflows, notification config) **is in a patch or `after_install` hook**, not just done by hand. (See §5.)
7. ✅ **A working `init.sh` / `bench-bootstrap.sh` exists at the repo root** that a new dev can run on a clean laptop and have the test site up in <30 minutes. (See §13.)
8. ✅ **A `docs/HANDOFF.md` exists** explaining decisions, gotchas, what's not done, and how to deploy. (See §14.)
9. ✅ **Frappe Cloud production hosting is set up and a backup-restore drill has been done end-to-end.** (See §11.) — 🔴 First restore attempt always finds something missing (encryption key, version mismatch, fixture conflict). Must be rehearsed before go-live, not after.
10. ✅ **A `.env.example` and a list of every secret/API key the system uses is documented** (and none are committed to Git).

---

## Section 1 — The "Saturday Night At 11pm" Test

If your phone rings at 11:07pm Saturday and the operator says *"the asset board is frozen, every tile is stuck on Dirty, the cash drawer screen says 'unauthorized,' and Frappe Cloud is showing 504s"* — can you, with no developer present:

1. **See what broke.** Frappe Cloud → Error Log → filter to last 30 minutes. There must be one snapshot per failure with stack trace, request body, user.
2. **See what was scheduled.** Scheduled Job Log → confirm the 15-minute overtime cron actually fired in the last hour.
3. **See what changed last.** Version → Venue Asset → see who set 12 rooms to OOS in the last hour and why.
4. **Roll back to a known-good state.** Frappe Cloud → Backups → restore most recent pre-incident snapshot to a sandbox site, verify, then promote.
5. **Re-run a stuck patch.** SSH (or Frappe Cloud terminal) → `bench --site $SITE execute hamilton_erp.patches.v0_1.seed_hamilton_env`.
6. **Roll forward to a hotfix.** Push to main → Frappe Cloud auto-deploys → confirm via health endpoint.

If any of these is "I don't know how" or "we'd have to call the developer" — that's a Tier 1 production gap.

---

## Section 2 — Repo State Snapshot (verified 2026-04-25)

What Hamilton has today, factual:

| Area | What's there | Status |
|---|---|---|
| `hooks.py` | 95 lines, well-commented, fixtures filtered, 1 doc_event, 1 cron (15 min), `after_install` + `after_migrate` | 🟢 Clean shape |
| `patches.txt` | 2 patches, both in `[post_model_sync]` | 🟢 Clean structure; idempotency to verify |
| `fixtures/` | `role.json`, `property_setter.json`, `custom_field.json`, all filtered by `%-hamilton_%` pattern | 🟢 Filtered correctly; verify export round-trip |
| `setup/install.py` | `_create_roles()` idempotent; `ensure_setup_complete()` heals `is_setup_complete` after migrate; `_block_pos_closing_for_operator()` enforces blind cash control | 🟢 Defensive and well-documented |
| `.github/workflows/` | Only `claude-review.yml` (PR review bot). **No test runner workflow.** | 🔴 **Tier 1 gap** |
| `pyproject.toml` | `frappe = ">=16.0.0,<17.0.0"`, `erpnext = ">=16.0.0,<17.0.0"`, ruff configured (line 110, py311, tab indent, double quotes) | 🟢 v16-pinned, formatter wired |
| `README.md` | 2 lines (`# hamilton_erp` + `Hamilton ERPNext Implement`) | 🔴 **Tier 1 gap** |
| Test count | 19 `test_*.py` files, ~306+ tests passing per `claude_memory.md` baseline | 🟢 Strong |
| Whitelist endpoints | 9 `@frappe.whitelist(...)` in `api.py`, all with explicit `methods=[...]`, all gated by `frappe.has_permission(..., throw=True)` | 🟢 Method-restricted, permission-checked |
| Type annotations | Partial — newer endpoints have parameter type hints, older return-type only | 🟡 Tier 2 |
| `ignore_permissions=True` | 4 call sites in `lifecycle.py` (insert + save) | 🟡 Tier 2 — needs justification block in code |
| `permission_query_conditions` / `has_permission` hooks | None defined | 🟡 Tier 3 — fine for single-venue, must address for multi-venue |
| Scheduler events | 1 cron job (`*/15 * * * *` → overtime check) | 🟢 Defined; need health monitoring |
| DocType indexes | 8 doctypes with `in_list_view`/`search_index` markers; `test_database_advanced.py` enforces specific indexes | 🟢 Verified by tests |
| `docs/` | Extensive — decisions_log, lessons_learned, coding_standards, design specs, current_state, build_phases, testing_guide, venue_rollout_playbook, troubleshooting | 🟢 Strongest area |

**Headline:** the application code is in good shape. The gaps are operational — CI, README, audit trail enablement, scheduler health, backup verification, and the "what do we do at 11pm" runbook.

---

## Section 3 — Custom App Structure & Upgrade Safety

### What "upgrade-safe" actually means

When Frappe/ERPNext releases v16.16, v17, etc., your custom app must keep working without you re-doing customizations. Three rules make this happen:

1. **Never edit code inside `apps/frappe/` or `apps/erpnext/`.** All your code lives in `apps/hamilton_erp/`. You already do this.
2. **Don't enable Developer Mode on production.** Developer mode allows the framework to write JSON files back to disk when you save DocTypes via the UI. On production, those writes go into a non-Git-tracked location and break the next `bench update`. 🔴
3. **Customize via your own app, not via the Customize Form on production.** Property Setters and Custom Fields created in the production UI are stored only in the production database — not in your repo — and are wiped or duplicated on a fresh-site install. The fix is fixtures (§4).

### What v16 / Frappe Cloud expects

A v16 custom app on Frappe Cloud must:

1. Pin Frappe and ERPNext compatible major versions in `pyproject.toml` under `[tool.bench.frappe-dependencies]` — comma-separated, not space-separated. Hamilton has `frappe = ">=16.0.0,<17.0.0"` ✅.
2. Have a `modules.txt` listing every module — Hamilton has this ✅.
3. Have a `patches.txt` with section headers `[pre_model_sync]` and `[post_model_sync]` — Hamilton has this ✅.
4. Have an `__init__.py` exporting `__version__` (or `dynamic = ["version"]` in `pyproject.toml` reading from `__init__.py`) — Hamilton has the latter ✅.

### Overriding standard ERPNext DocTypes the right way

Hamilton extends Sales Invoice. The way to do this without breaking on upgrade is `extend_doctype_class` in `hooks.py`:

```python
# hooks.py
extend_doctype_class = {
    "Sales Invoice": "hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice",
}
```

🔴 Memory notes you have/had `override_doctype_class` in `hooks.py:69` and need to switch to `extend_doctype_class`. **This is now in place** per current repo state, but verify before handoff. The difference: `override_doctype_class` *replaces* the ERPNext class entirely (you lose every future ERPNext bug fix to that DocType). `extend_doctype_class` *inherits* from it (you keep ERPNext's logic and add yours on top). This is one of the most common mistakes in custom apps and a v16 best practice.

### Upgrade-safety gotchas

- **Do not edit standard ERPNext DocTypes via JSON edits in your custom app.** Customisations belong in Custom Field, Property Setter, or Customize Form — all of which Hamilton's fixtures pattern correctly captures.
- **`extend_doctype_class` is silently ignored if the standard doctype doesn't load before your override.** `required_apps = ["frappe", "erpnext"]` (which Hamilton has) gates this correctly.
- **Frappe v15+ dropped the default index on the `modified` column.** If any Hamilton query orders by or filters on `modified`, add an explicit index to that DocType's JSON.

### v16-specific checks (memory items)

Frappe v16 changed several internals. Confirm before handoff:

- ✅ Replace `frappe.flags.in_test` → `frappe.in_test` (36 occurrences across 5 files).
- ✅ Audit any `frappe.db.get_value(...) == "1"` or `== "0"` — v16 returns real booleans/integers, not strings. String comparisons silently break.
- ✅ Drop dependencies on the legacy PDF engine — v16 uses Chrome-based PDF rendering. Retest custom Print Formats.

### Action items

- [ ] **Tier 2** Add a docstring at the top of `hooks.py` summarising what each hook block does and why (non-obvious decisions only).
- [ ] **Tier 2** Add an `app_compatibility.md` to `docs/` listing the exact Frappe minor + ERPNext minor + MariaDB version that Hamilton is verified against. Update on every Frappe Cloud upgrade.
- [ ] **Tier 3** Add a `before_uninstall` hook that prints a warning and bails out unless `--force` is passed, to prevent accidental wipes during dev.

---

## Section 4 — Fixtures: What, Why, How

### What fixtures are (in plain English)

A fixture is a JSON file in your app's `fixtures/` folder that captures **records you created through the Frappe UI** so they can be re-created automatically on any new site that installs your app. Without fixtures, every customization you made by clicking around in the browser exists *only* in your current local database.

If your dev installs `hamilton_erp` on a fresh staging site tomorrow and your custom fields aren't in fixtures, **none of them appear**. The dev will assume your app is broken. They are not wrong — it is broken without fixtures. 💰

### What to put in fixtures

At minimum:
- `Custom Field` (every custom field added to a standard DocType)
- `Property Setter` (every label, validation, default, hidden flag changed via Customize Form)
- `Custom DocPerm` (custom permission rows added via Role Permission Manager — these are NOT auto-included)
- `Workflow`, `Workflow State`, `Workflow Action Master` (your asset workflow lives here)
- `Role` (any custom roles like "Hamilton Operator", "Hamilton Manager", "Hamilton Admin")
- `Role Profile` and `Module Profile`
- `Print Format` (any custom invoice/receipt formats)
- `Notification` and `Email Template`
- `Client Script` and `Server Script` (if any were authored via UI)
- `Dashboard`, `Number Card`, `Dashboard Chart`
- `Web Form` (if used)
- `Report` (only with a filter to exclude standard ERPNext reports)

### Hamilton's current setup

```python
fixtures = [
    {"dt": "Custom Field",    "filters": [["name", "like", "%-hamilton_%"]]},
    {"dt": "Property Setter", "filters": [["name", "like", "%-hamilton_%"]]},
    {"dt": "Role",            "filters": [["name", "in", ["Hamilton Operator", "Hamilton Manager", "Hamilton Admin"]]]},
]
```

The `%-hamilton_%` filter convention is **excellent** — it prevents `bench export-fixtures` from accidentally vacuuming up custom fields from ERPNext or other apps. This is the #1 fixtures bug in the wild and Hamilton has solved it.

### Critical gotchas

- 🔴 **Filter your fixtures.** Without filters, `bench export-fixtures` exports `Custom Field` rows that ERPNext patches added (e.g. `Project-github_sync_id`). When your fixture is re-imported on another site, it tries to add ERPNext's own custom fields and may conflict.
- 💰 **Re-run `export-fixtures` every time you change something via the UI.** Then commit the JSON. If you skip this, the dev will discover the running site has 30 things that aren't in Git.
- ✅ Add a pre-commit reminder: a one-line note at the top of `decisions_log.md` saying "if you customized via UI today, run `bench export-fixtures` before committing."

### Action items

- [ ] **Tier 1** Run `bench --site hamilton-unit-test.localhost export-fixtures --app hamilton_erp` and **diff the result against the committed JSON files**. Any drift means the local dev site has customisations that haven't been exported. Common culprit: a Custom Field named without the `-hamilton_` suffix that the filter misses.
- [ ] **Tier 1** Verify `git status` after the export above is **empty**. If any fixture file changed, commit it.
- [ ] **Tier 2** Add a missing fixture type if any of these exist on the dev site: **Workflow**, **Workflow State**, **Workflow Action Master**, **Print Format**, **Email Template**, **Notification**, **Web Form**, **Custom DocPerm**, **Server Script**, **Client Script**, **Translation**.
- [ ] **Tier 2** Audit `Custom DocPerm` rows on hamilton-test.localhost. The `_block_pos_closing_for_operator()` deletes one row at install time but doesn't export it as a fixture — meaning a fresh install on Philadelphia would have to re-run `after_install`. That's fine *if* `after_install` is idempotent (it is) and *if* it runs (it does, on `bench install-app`). Document clearly in venue rollout playbook.
- [ ] **Tier 3** Add a `make export-fixtures` (or bench alias) that does the export + git status check in one step.

### Alternative: code-first custom fields

For new custom fields going forward, a more rigorous pattern is to define them in `after_install`:

```python
# hamilton_erp/install.py
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    custom_fields = {
        "Sales Invoice": [
            {"fieldname": "bathhouse_shift", "label": "Shift",
             "fieldtype": "Link", "options": "Bathhouse Shift", "insert_after": "posting_date"},
        ],
    }
    create_custom_fields(custom_fields, ignore_validate=True)
```

Then register in `hooks.py`:

```python
after_install = "hamilton_erp.install.after_install"
```

This is **more robust** than fixtures for production apps because the custom fields are guaranteed to be present and consistent — no JSON drift. Worth doing now.

---

## Section 5 — Patches: Automating Site Setup

### What patches are

A patch is a one-time Python script that runs during `bench migrate`. Frappe tracks which patches have run in `tabPatch Log` so each runs **exactly once per site**.

You use patches for:
- Renaming a DocType field and migrating existing data.
- Backfilling new required fields on existing records.
- Cleaning up data after a refactor.
- Setting up site-wide defaults that fixtures can't handle.

### Folder layout (the convention)

```
hamilton_erp/
├── patches.txt
└── patches/
    ├── __init__.py
    └── v0_1/
        ├── __init__.py
        ├── seed_hamilton_env.py
        └── rename_glory_hole_to_gh_room.py
```

### `patches.txt` format

```
[pre_model_sync]
# Patches that run BEFORE DocType schema migrations
# (use when a column rename would break unless data is migrated first)

[post_model_sync]
# Patches that run AFTER DocType schema migrations (most patches go here)
hamilton_erp.patches.v0_1.seed_hamilton_env
hamilton_erp.patches.v0_1.rename_glory_hole_to_gh_room
```

### Patch template

```python
# hamilton_erp/patches/v0_1/seed_hamilton_env.py
import frappe

def execute():
    settings = frappe.get_single("Bathhouse Settings")
    if not settings.staff_pin_length:
        settings.staff_pin_length = 4
        settings.save()
    frappe.db.commit()
```

### Hamilton's current setup

Two patches, both post-sync. Naming is good (descriptive, versioned). The recent rename patch (`Glory Hole → GH Room`) is exactly the kind of one-shot DB rename that belongs here.

### Critical gotchas

- 🔴 **Patches must be idempotent.** Always check before you write. If your patch sets a default and runs again on a site that's already had a manager change that default, you'll wipe their work. Pattern: `if not settings.staff_pin_length:` — never blindly assign.
- 💰 **No reverse patches.** Frappe doesn't support rolling back. If your patch corrupts data, you restore from backup. Always test on a fresh local site before pushing.
- ✅ For very common one-liners, write them inline in `patches.txt`: `execute:frappe.delete_doc("Report", "Old Report Name", ignore_missing=True)`
- ⚠️ For large data migrations (>10,000 rows), batch the work or you'll hit `TooManyWritesError`. Process in chunks of 500–1000.

### Action items

- [ ] **Tier 1** Read both patches and confirm idempotency. Each should start with a guard like `if frappe.db.get_value(...) == "expected": return`.
- [ ] **Tier 1** Manually run `bench --site hamilton-unit-test.localhost execute hamilton_erp.patches.v0_1.seed_hamilton_env` **twice in a row**. Second run must produce zero changes and zero errors.
- [ ] **Tier 2** Add a `patches/README.md` explaining the version-folder convention and the rule "every patch is named for what it does, not when it was added."
- [ ] **Tier 2** Add an empty `patches/v0_2/` folder with `__init__.py` so the next patch has an obvious home.

### Why this matters for handoff

When your dev sets up the DC/Crew Club site after Hamilton goes live, they'll run `bench install-app hamilton_erp` on a fresh site. If your initial Hamilton config (default cancel/amend permissions, default PIN length, workflow defaults) lives only in clicks-on-the-screen rather than in a patch or `after_install`, they'll spend hours reverse-engineering the Hamilton config to replicate it. 💰

---

## Section 6 — `hooks.py` Best Practices

### Frappe's official best practices for `hooks.py`

1. **Use specific DocType events instead of wildcards** for performance.
2. **Add try/except blocks** in handlers to prevent breaking the application.
3. **Name hook methods clearly** (`validate_customer_credit_limit`, not `validate1`).
4. **Add comments explaining why** each hook exists.
5. **Test hooks in development before deploying.**

### What Hamilton has

```python
fixtures = [...]                              # filtered, scoped — good
after_install = "...install.after_install"    # idempotent — good
after_migrate = "...install.ensure_setup_complete"  # heals dev-site bug — good
extend_doctype_class = {"Sales Invoice": "...HamiltonSalesInvoice"}  # v16 idiom — good
doc_events = {"Sales Invoice": {"on_submit": "...on_sales_invoice_submit"}}  # narrow scope — good
scheduler_events = {"cron": {"*/15 * * * *": ["...check_overtime_sessions"]}}  # explicit cron — good
```

This is a clean `hooks.py`. No wildcards, no `"*"` doc_event subscriptions, no try/except blocks hiding errors. Comments explain *why* each hook exists, not just what it does.

### The wildcard trap 🔴

If you have:

```python
doc_events = {
    "*": {
        "on_update": "hamilton_erp.handlers.maybe_log_change"
    }
}
```

…that handler runs on **every save of every DocType** — including User, ToDo, File, Email Queue, every internal Frappe save. Tanks performance.

**Fix:** Always list specific DocTypes.

### The try/except pattern

Without it, one bad handler (e.g. a Slack notification that fails because the network is down) blocks users from saving documents. With it, the save succeeds and the failure is logged.

```python
import frappe

def broadcast_asset_change(doc, method=None):
    try:
        notify_front_desk(doc)
    except Exception:
        frappe.log_error(
            title="broadcast_asset_change failed",
            message=frappe.get_traceback()
        )
        # Do NOT re-raise — let the document save succeed
```

### Performance traps to avoid (none of which Hamilton has — keep it that way)

- **`doc_events = {"*": {...}}`** — wildcard subscriptions fire on every save of every doctype. Never use.
- **`override_whitelisted_methods`** — overriding a frappe core method affects every custom app on the site. Use `extend_doctype_class` instead, which Hamilton already does.
- **`get_permission_query_conditions`** that does a `frappe.db.sql()` on every list view load. If used, cache aggressively.
- **`before_save` doing network I/O** — never do HTTP calls or external DB calls inside doc_events. They block the user's request thread. Enqueue a background job:

```python
def on_submit(doc, method=None):
    frappe.enqueue(
        "hamilton_erp.tasks.send_receipt_email",
        doc_name=doc.name,
        queue="default",
        timeout=300,
    )
```

- **`scheduler_events` with broad cron expressions** like `"* * * * *"` (every minute) running heavy work. Hamilton's `*/15 * * * *` is appropriate.
- **No DB writes in `validate`.** `validate` runs on every save *and* every form load. Writes here will deadlock under load. Move to `on_update`, `on_submit`, or `after_insert`.
- **No `frappe.get_doc()` loops without limits.** If a handler iterates over hundreds of related docs, it should use `frappe.get_all()` for reads, and only `get_doc()` for the few that need saving.

### Action items

- [ ] **Tier 1** For every function path in `hooks.py`, confirm the function exists. A typo causes silent failures that surface days later. Audit script:
  ```bash
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
  ```
- [ ] **Tier 1** Apply the `override_doctype_class` → `extend_doctype_class` correction at `hooks.py:69` if not yet done. Single line change + verify no logic depends on full override behavior.
- [ ] **Tier 2** Add `boot_session = "hamilton_erp.boot.boot_session"` to push Hamilton-specific config (feature flags, asset board endpoint) into `frappe.boot` on login. Saves one API call per page load.
- [ ] **Tier 2** Document which doctypes Hamilton's `on_sales_invoice_submit` *can* receive. Currently filters by `has_admission_item()` — but a future contributor may not know retail-only sales pass through silently.
- [ ] **Tier 3** Consider adding `validate_modified` to lock concurrent edits on Venue Asset more aggressively. Currently the `version` field + Redis lock handle this; defense-in-depth doesn't hurt.

---

## Section 7 — CI/CD with GitHub Actions: 🔴 The Single Biggest Gap

### Current state

`.github/workflows/` contains exactly one file: `claude-review.yml` (PR review bot). **There is no test-runner workflow.** This means:

- A push to main can break the test suite without being caught until someone runs tests locally.
- A PR can be merged with no automated verification that 306+ tests still pass.
- The first time anyone learns the suite is red is when Frappe Cloud auto-deploys the broken commit.

**This is the highest-priority production readiness gap in the entire audit.**

### Why this matters more than it sounds

Without CI, your "270+ passing tests" is a *claim*. With CI, every push runs them automatically and posts a green ✅ or red ❌ on the PR. The dev's first question on Day 1 will be "how do I run the tests?" — if CI is set up, the answer is "you don't, the bot does." If not, you'll spend 30 minutes walking them through your local bench setup. 💰

Frappe v16's `bench new-app` command auto-generates a CI workflow file. If your bench was older at app creation, you don't have it; copy a template below.

### Option A — Frappe's shared test workflow (simpler, recommended for now)

Save as `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  pull_request:
  push:
    branches: [main, develop]
  workflow_dispatch:

jobs:
  test:
    name: Server Tests
    uses: frappe/frappe/.github/workflows/_base-server-tests.yml@version-16
    with:
      enable-postgres: false
      parallel-runs: 2
```

This uses Frappe's shared test workflow, maintained by the Frappe team. Handles MariaDB setup, Frappe + ERPNext at version-16, your app installation, `bench run-tests`, and PR reporting.

### Option B — Self-contained workflow (more control, more lines)

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

### Linter workflow (optional but recommended)

Save as `.github/workflows/lint.yml`:

```yaml
name: Linter

on:
  pull_request:
  push:
    branches: [main]

jobs:
  lint:
    name: Linter
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .
```

### Type-check workflow (optional, recommended for handoff)

```yaml
name: Type Check
on:
  pull_request:
jobs:
  typecheck:
    uses: frappe/frappe/.github/workflows/_base-type-check.yml@version-16
```

### Action items

- [ ] **Tier 1** Create `.github/workflows/tests.yml`. Fail loud (don't `continue-on-error`).
- [ ] **Tier 1** Add a branch protection rule on main: PRs cannot merge unless `tests` is green. Settings → Branches → Branch protection rules → require PR review and require CI to pass.
- [ ] **Tier 1** Push a trivial change to a PR. Confirm the green check shows up before asking the dev to look.
- [ ] **Tier 1** Add a CI badge to `README.md`: `![Tests](https://github.com/csrnicek/hamilton_erp/actions/workflows/tests.yml/badge.svg)`.
- [ ] **Tier 2** Add `lint.yml` workflow (ruff check + format check) on every PR.
- [ ] **Tier 2** Add a `bench migrate` step after the test step to catch patches that fail in non-test contexts.
- [ ] **Tier 3** Add a nightly cron workflow re-running the suite against `version-16` (latest) Frappe + ERPNext to catch upstream regressions before they hit Frappe Cloud.
- [ ] **Tier 3** Cache the bench environment between runs (shaves 5–7 minutes off each run).

### What this will cost if missing

A single bad commit reaching Frappe Cloud auto-deploy = ~30 minutes downtime + a bench rollback that touches database state + an emergency hotfix push. CI prevents this. **This is the highest-leverage 90 minutes of work in the entire pre-handoff list.**

---

## Section 8 — Permissions, v16 Field Masking, User Permissions

### The three layers of Frappe permissions (memorize these)

1. **Role Permissions** — what a Role can do to a DocType (read/write/create/delete/submit/cancel/amend).
2. **User Permissions** — restricting a specific user to specific *records* (e.g., user can only see Bathhouse Asset records where Location = "Hamilton").
3. **Permission Levels** (perm levels 0–9) — restricting *which fields* a role can read/edit. Default is 0 (everyone with role access). A field at perm level 1 is hidden unless the role explicitly has perm level 1 access too.

### What v16 brings

Frappe v16 deepens the field-level permission system. Each field on a DocType has a numeric "permlevel" (default 0). You can grant Read/Write to permlevel 1 to one role and Read-only to another role — letting a `Hamilton Operator` see a Venue Asset's room number and status but not its purchase price (permlevel 1).

Hamilton has three roles and zero field-level permissions in use. That's fine for Phase 1 (single-operator model). Phase 2 (POS, Manager-tier) will need them.

### What's already done well

- `Hamilton Operator`, `Hamilton Manager`, `Hamilton Admin` roles created idempotently in `after_install`.
- All 9 whitelisted API endpoints call `frappe.has_permission(..., throw=True)` before doing work — gold standard.
- `_block_pos_closing_for_operator()` removes the standard POS Closing Entry permission for operators, enforcing blind cash control (DEC-005).
- All API endpoints declare `methods=["GET"]` or `methods=["POST"]` explicitly — closes the HTTP-method CSRF gap (CVE-2026-41317).

### Pre-handoff permissions checklist (🔴 — much harder to fix after go-live)

These are *much* harder to fix after a venue goes live, because by then real users have done real things and you can't change rules without auditing every existing record:

- [ ] **Cancel** and **Amend** rights on Sales Invoice, Bathhouse Receivable Log, Bathhouse Shift restricted to "Bathhouse Manager" or "Accounts Manager" only — NOT staff roles.
- [ ] **System Manager** role assigned only to your user. No staff. No "ops" account. No shared account. (System Manager can do *anything* — including delete the audit trail.)
- [ ] **Delete** permission on financial DocTypes restricted to System Manager only.
- [ ] **Read** permission on `Bathhouse Membership` (which holds member personal data) restricted appropriately — staff can read, but should they be able to *export* or *report* on it? Consider perm level 1 for sensitive fields.
- [ ] Test the full permission matrix by switching to a non-admin user (Frappe has Set User as Test User in dev mode) and trying every action.

### v16 Field Masking — the new feature

This is one of the headline v16 features. Sensitive fields can be **visible but masked** based on roles — placeholders like `xxxx` show data exists without revealing it. Different from hiding the field (which signals the field doesn't exist at all).

Use cases for Hamilton:
- Member phone numbers: visible but masked unless role = Manager.
- Member email: same.
- Cash Drop totals: visible but masked unless role = Manager / Accounts Manager.
- Staff PIN (if stored at all — should be hashed, never plaintext): always masked.

To enable field masking in v16:
1. Go to the DocType (e.g., Bathhouse Membership) → Customize Form.
2. Open the field (e.g., "phone").
3. Set "Permission Level" to a non-zero number (e.g., 1).
4. In Role Permissions Manager, give the manager role "Read" permission at level 1, but don't give the staff role level 1.
5. Configure the masking rule in v16's new role-based field masking settings.

After setup, **add this configuration to your fixtures**:
```python
fixtures = [
    # ... existing entries ...
    "Custom DocPerm",  # ← captures perm level rules
    "Property Setter", # ← captures field perm level changes
]
```

### Permission gotcha on child tables

🔴 Child tables (like your asset assignment child table on Sales Invoice) **don't show up in Role Permission Manager**. To restrict fields on a child table, set the Perm Level on the child-table field, then set the Perm Level on the **parent's** Role Permissions Manager. The dev will hit this within an hour of starting if you haven't already.

### Document-level permissions via hooks

If you need conditional permissions (e.g., "managers can edit any shift, staff can only edit their own"), use a `permission_query_conditions` hook in `hooks.py`:

```python
permission_query_conditions = {
    "Bathhouse Shift": "hamilton_erp.permissions.get_shift_permission_query",
}

has_permission = {
    "Bathhouse Shift": "hamilton_erp.permissions.has_shift_permission",
}
```

These functions filter list views and document access based on the logged-in user.

### Action items

- [ ] **Tier 1** Audit every field on every Hamilton DocType for whether it should be permlevel 0 (visible to all roles with Read) or permlevel 1+ (manager/admin only). Likely candidates for permlevel 1: `expected_revenue`, `cash_drop_expected_total`, anything with cost or financial info. Even if Hamilton doesn't use these fields today, planning the levels now means Phase 2 doesn't require a schema migration.
- [ ] **Tier 2** Run `bench --site $SITE list-permissions --doctype "Venue Asset"` (or use Role Permission Manager UI) and screenshot/export the matrix. Commit to `docs/security/permission_matrix.md`.
- [ ] **Tier 2** Document `ignore_permissions=True` usage. Every call site in `lifecycle.py` (4 places) needs a one-line comment: *why* it's safe to bypass permissions here. Lock-protected? Already validated upstream? Internal background job?
- [ ] **Tier 3** For multi-venue (Phase 2 Philadelphia/DC/Dallas), implement `permission_query_conditions` on `Venue Asset` to filter by venue. Without this, a Hamilton operator could see Philadelphia assets in a List View. Single-venue today = no risk; multi-venue = critical.

---

## Section 9 — Audit Trail vs Document Versioning

These sound the same but they're not. Both should be on for your financial DocTypes.

### Document Versioning (per-DocType field-level history)

**What it is:** When enabled on a DocType, every save creates a row in the `Version` table recording exactly which fields changed, from what value to what value, by whom, when.

**How to enable:** Customize Form on the DocType → check "Track Changes" property → save.

**Why it matters:** Without it, the form's "Activity" tab only shows "user X edited this on date Y" — no field-level detail. With it, you can see "Manager Alice changed credit_limit from $500 to $5000 on 2025-04-01" and that's evidence in a fraud investigation.

**Required for:**
- Sales Invoice (extended)
- Bathhouse Receivable Log
- Bathhouse Shift / Shift Record
- Bathhouse Membership
- Bathhouse Asset / Venue Asset (assignment changes already tracked via workflow, but enable for safety)
- Bathhouse Settings (singleton — config drift is a top audit issue)
- Venue Session
- Cash Drop / Cash Reconciliation
- Asset Status Log

🔴 **If you don't enable Track Changes before going live, you have no field-level history of pre-go-live changes.** The audit trail starts only from when you turned it on. Turn it on now. Every day delayed = a day of audit history that cannot be recovered.

### Audit Trail (the comparison report)

**What it is:** A separate ERPNext report that shows the **diff between two versions** of a document side-by-side, including child-table additions/removals. Reads from the same `Version` table that Track Changes populates.

**How to use:** Search "Audit Trail" in Awesomebar → select DocType → select document → click Compare.

**Why it matters:** Document Versioning is the data; Audit Trail is the readable report. Auditors and managers will want both.

### What's missing from Frappe out of the box (be aware) 💰

- There's no built-in "consolidated change report across all DocTypes for a date range" in v16. Auditors often ask for this. If needed, your dev will build a custom Query Report against `tabVersion` — about 4–8 hours of work. Flag in `phase_2_wishlist.md`.
- The Activity Log table tracks logins, deletions, and other system events. It's *not* deleted by document deletion, so it survives even if a user nukes a Sales Invoice. Don't disable. Default retention is fine.

### Action items

- [ ] **Tier 1** Enable Track Changes on every financial DocType listed above. ~20 minutes of UI clicks.
- [ ] **Tier 1** Enable Audit Trail (System Settings) for Hamilton Operator/Manager/Admin roles. ~10 minutes.
- [ ] **Tier 2** Configure Log Settings retention for Activity Log, Version, Email Queue. ~15 minutes.
- [ ] **Tier 2** Add `docs/operations/audit.md` (where to look for "who did what"). ~30 minutes.
- [ ] **Tier 3** Build saved report "Operator Activity by Shift" combining Shift Record + Activity Log. ~60 minutes.

---

## Section 10 — Frappe Scheduler Jobs (Nightly Automation)

### How scheduling works

The scheduler is a separate Frappe process (always running on Frappe Cloud) that wakes up roughly every 4 minutes, checks which scheduled jobs are due, and queues them for the worker pool via Redis Queue.

You declare jobs in `hooks.py`:

```python
scheduler_events = {
    "all": [
        # runs every 4 minutes — use sparingly
    ],
    "hourly": [
        "hamilton_erp.tasks.hourly.check_active_assets",
    ],
    "daily": [
        "hamilton_erp.tasks.daily.detect_stale_assets",
        "hamilton_erp.tasks.daily.reconcile_yesterday_shifts",
        "hamilton_erp.tasks.daily.verify_cash_drops",
    ],
    "weekly": [
        "hamilton_erp.tasks.weekly.send_manager_summary",
    ],
    "cron": {
        "30 3 * * *": [
            # 3:30 AM daily — quiet hours, after the venue closes
            "hamilton_erp.tasks.cron.nightly_cleanup",
        ],
    },
}
```

### Hamilton's current setup

One job, every 15 minutes, checking for overtime sessions. The cron expression is correct (Frappe v16 supports standard 5-field cron). The function path is real (`tasks.py:check_overtime_sessions`).

### Phase 2 candidates (from memory notes)

- Stale asset detection (asset assigned but no activity for >X hours)
- Session reconciliation (orphaned sessions)
- Cash drop verification (missing/incomplete drops from yesterday)

These should run between 3 AM and 5 AM local time when the venue is closed. Use `cron` syntax for precision.

### What can go wrong in production

1. **The scheduler stops.** Most common silent failure. The Frappe scheduler is a separate process; if it crashes, no error appears anywhere obvious — overtime detection just stops. By the time someone notices, you have 50 sessions that should have been flagged.
2. **The job throws and the next run runs the broken code.** No automatic backoff. A bad deploy can cause errors every 15 minutes for 12 hours straight, filling the Error Log.
3. **The job takes longer than the interval.** If `check_overtime_sessions` ever takes >15 minutes, the next run starts before the previous one finished. RQ allows this; it's expensive.
4. **The job runs during a deploy.** New code, mid-job. Half the work runs against the old schema, half against the new.
5. **Frappe's max-500 queued jobs limit.** Once exceeded, `frappe.enqueue` starts failing silently.

### Critical gotchas

- 🔴 **Always wrap scheduler functions in try/except.** A job that throws an unhandled exception logs the error, but if it loops over records, one bad record can kill the whole job. Iterate with try/except *inside* the loop:

```python
def detect_stale_assets():
    assets = frappe.get_all("Bathhouse Asset", filters={"status": "Assigned"})
    for asset in assets:
        try:
            check_one_asset(asset.name)
        except Exception:
            frappe.log_error(
                title=f"detect_stale_assets failed for {asset.name}",
                message=frappe.get_traceback()
            )
            # keep going to next asset
```

- 🔴 **Cron times are in the server's timezone, not yours.** Frappe Cloud servers run UTC by default. 3 AM EST = 7 AM UTC = `0 7 * * *`. Test it.
- ✅ **Verify the scheduler is enabled per site.** Run `bench --site hamilton-unit-test.localhost scheduler enable`. On Frappe Cloud, enabled by default but check the site dashboard.
- ✅ **Test scheduler functions manually before relying on the cron:** `bench --site hamilton-unit-test.localhost execute hamilton_erp.tasks.daily.detect_stale_assets`. If that doesn't work, the cron won't either.

### The scheduler heartbeat pattern 💰

A common production failure is the scheduler silently stopping. Add one job that updates a `Bathhouse Settings.last_scheduler_run` (or `Hamilton Settings.scheduler_last_seen`) timestamp every 5 minutes. Then add a Manager-facing alert if `scheduler_last_seen > now() - interval 15 minute`. **Cheapest dead-scheduler detector.**

### Action items

- [ ] **Tier 1** Add a "scheduler heartbeat" job (every 5 minutes, writes timestamp to a Log doctype or Settings field). Add separate Manager-facing alert if heartbeat is stale.
- [ ] **Tier 1** Wrap the body of `check_overtime_sessions` in a `try/except` that logs to Error Log via `frappe.log_error()` with a specific title (`"Overtime Detection Failed"`) and re-raises.
- [ ] **Tier 2** Add an integration test asserting `check_overtime_sessions` completes in <2 seconds against a populated test database. Catches O(n²) regressions before they reach prod.
- [ ] **Tier 2** Add bench command alias for one-off manual runs: `bench --site $SITE execute hamilton_erp.tasks.check_overtime_sessions`. Document in `docs/operations/runbook.md`.
- [ ] **Tier 3** If Hamilton ever adds heavy nightly jobs (cleanup, archival), use `cron_long` instead of `cron` so they run on the long-running worker queue and don't starve short jobs.

---

## Section 11 — Frappe Cloud Operations

### Where errors actually live

Several layers — a new dev will want to see all of them:

1. **Error Log DocType** (in Desk, search "Error Log") — Python exceptions caught by Frappe with full traceback. First place to look. Same as `frappe.log_error()`.
2. **`web.log` and `web.err.log`** — STDOUT/STDERR of the web process. SSH into the bench (Frappe Cloud Private Bench feature) and run `tail -f logs/web.err.log`.
3. **`worker.log` and `worker.err.log`** — STDOUT/STDERR of background workers (where scheduler jobs and queued jobs run).
4. **`scheduler.log`** — the scheduler's own log. Useful when scheduled jobs aren't running.
5. **Frappe Cloud dashboard → Site Overview → Analytics** — request duration histograms, background job duration histograms, slow queries.

### Error log monitoring

Frappe Cloud captures every server exception as an Error Log row with stack trace, request body, user, and snapshot ID. Files corresponding to each snapshot land in `./sites/$SITE/error-snapshots/`.

- [ ] **Tier 1** Configure Log Settings → Error Log → set retention to at least 90 days. Default is 30, too short for "a customer complained two months ago" investigations. Add to `hooks.py`:
  ```python
  log_clearing_doctypes = {
      "Error Log": 90,    # days
      "Activity Log": 365,
      "Communication": 730,
  }
  ```
- [ ] **Tier 1** Configure email alerts on Error Log → set notification rule that emails Chris when Error Log frequency exceeds N per hour. Tune N after a week of baseline (likely 5–10).
- [ ] **Tier 2** Add a saved report "Errors in last 24h grouped by exception type" pinned to System Manager dashboard. First thing anyone sees on login.
- [ ] **Tier 2** Document the exact path: "to view today's errors, go to [Frappe Cloud dashboard URL] → Sites → hamilton-erp → Error Log." Put in `docs/HANDOFF.md`.
- [ ] **Tier 3** Consider Slack/Telegram webhook on critical errors. ~2 hours of dev work — much cheaper to scope now than discover the need at 11pm Saturday.

### Backups

Frappe Cloud takes daily backups by default. **Daily is not enough for a venue that does cash transactions.**

- [ ] **Tier 1** Enable Frappe Cloud's hourly backups on hamilton-erp.v.frappe.cloud. (Setting in Frappe Cloud dashboard → Backups.)
- [ ] **Tier 1** Enable backup encryption. Once enabled, **save the encryption key in a separate password manager from the Frappe Cloud login**. If you ever need to restore a backup to a fresh site, you need the key from the original `site_config.json` to read encrypted password fields. Lose the key = lose every encrypted password (email, API, social login).
- [ ] **Tier 1** **Run a real restore drill:** spin up a fresh Frappe Cloud site, restore the most recent hamilton backup, verify you can log in and the asset board loads. Document the procedure in `docs/operations/disaster_recovery.md`. **This must be done before go-live, not after.** The first restore attempt always finds something missing (encryption key, version mismatch, fixture import).
- [ ] **Tier 2** Configure offsite backup destination in Frappe Cloud (S3 or equivalent). Default Frappe Cloud backups live on the same infrastructure; a region-wide outage takes both prod and backup with it.

### Version pinning

Already noted in `claude_memory.md` (Frappe Cloud Version Pinning). Repeating for completeness:

- [ ] **Tier 1** Before go-live: pin hamilton-erp.v.frappe.cloud to a specific stable v16 minor (e.g., v16.14.0). Disable auto-update to latest. Document the pinned version in `docs/app_compatibility.md`. **Reason:** v16.14.0 (released 2026-04-14) removed forced six-decimal rounding on valuation rate fields; future minor versions may make similar invariant-breaking changes that need to be deliberately tested before adoption.

### Site config & secrets

Hamilton's `site_config.json` on Frappe Cloud will contain (minimum): the encryption key, the database password, and any third-party API keys (Phase 2: Stripe). These are not in the repo. They cannot be in the repo.

- [ ] **Tier 1** Audit `site_config.json` on prod. Confirm none of these are committed to git: `db_password`, `encryption_key`, `admin_password`, any `stripe_*`, any `mail_password`. Run: `git log --all -p -- "**/site_config*.json" | head -200` to see if anything ever leaked historically.
- [ ] **Tier 1** Save the prod `site_config.json` (with secrets) to a password manager entry separate from Frappe Cloud login. If you ever need to restore the site to non-Frappe-Cloud infrastructure, you need this file.
- [ ] **Tier 2** Document the secrets inventory in `docs/operations/secrets.md` (where each secret lives, who has access, rotation cadence) — without the actual values.
- [ ] **Tier 2** Set up a quarterly reminder to rotate the encryption key (process: take backup, restore to new site with new key, cut over, decommission old). Yearly is acceptable for low-risk single-tenant deployments.

### Uptime monitoring

Frappe Cloud auto-monitors HTTP response and emails you if down. For external uptime monitoring (recommended — never trust the host to monitor itself), use a free Uptime Robot or Better Stack check on `https://hamilton-erp.v.frappe.cloud/api/method/ping`.

---

## Section 12 — Production Security Hardening

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
| Brute force on PIN auth (since PIN replaces standard auth) | Credential stuffing | 🟡 Verify rate limiter or attempt counter exists |

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
- [ ] **Tier 1** Verify rate limiter or attempt counter exists for PIN-based staff identity. Standard Frappe login has this; custom flow may not.
- [ ] **Tier 2** Add a CI step that fails the build if any new `frappe.whitelist()` is added without explicit `methods=[...]`:
  ```bash
  grep -rn "@frappe.whitelist()" hamilton_erp/ --include="*.py" | grep -v test_ | grep -v "methods=" && exit 1 || exit 0
  ```
- [ ] **Tier 2** Add CSRF-rejection integration test for state-changing endpoints. Validate every state-changing endpoint **rejects** a request without an `X-Frappe-CSRF-Token` header.
- [ ] **Tier 2** Audit Hamilton's User Permissions on prod: which users have `System Manager`? Anyone with that role can read/write everything. Likely correct list: Chris + 1 backup admin.
- [ ] **Tier 3** Add `frappe.rate_limit()` to the bulk-action endpoints (`mark_all_clean_rooms`, `mark_all_clean_lockers`). Even 60/minute is enough to stop a runaway client from DoS'ing the database.
- [ ] **Tier 3** Subscribe to GitHub security advisories on `frappe/frappe` and `frappe/erpnext`. The 2025–2026 CVE rate has been roughly one per quarter; you want to know within hours, not weeks.

### What will cost billable hours if missing

A penetration test (which the new developer may run as part of acceptance) will find every missing justification comment, every `allow_guest`, every rate-limit-free bulk endpoint. Each finding becomes a billable hour to fix and re-test. Hamilton is in good shape — finishing the last 10% (justification comments, rate limits, CSRF assertion) is faster than reacting to the audit later.

---

## Section 13 — Environment Bootstrap (`init.sh`)

### What this is and why it matters for handoff

The `init.sh` pattern came out of Anthropic's research on long-running agents. The idea: a single script that, when run on a fresh machine, sets up the *entire* dev environment for the project. You'll see this same idea elsewhere as `setup.sh`, `bootstrap.sh`, or `make dev`.

For Hamilton ERP: when the new developer clones your repo on a fresh laptop, they should be able to run **one command** and have a working test bench in 20–30 minutes, no Slack questions to you.

Without it, every new dev costs 2–6 hours of "doesn't work on my machine" troubleshooting on day one. 💰

### Hamilton's current state

There is no `init.sh`. Setup instructions are spread across CLAUDE.md (mentions paths), `docs/testing_checklist.md`, and `docs/troubleshooting.md`.

### Recommended `init.sh` for `hamilton_erp`

Save at the repo root (not inside the app folder):

```bash
#!/usr/bin/env bash
# init.sh — Hamilton ERP dev environment bootstrap
# Usage: ./init.sh
# What it does: clones bench, installs Frappe v16 + ERPNext v16,
# installs hamilton_erp from the current directory, creates a test site.

set -euo pipefail

BENCH_DIR="${BENCH_DIR:-$HOME/frappe-bench-hamilton}"
SITE_NAME="${SITE:-hamilton-unit-test.localhost}"
PYTHON_VERSION="3.12"
NODE_VERSION="20"
FRAPPE_BRANCH="version-16"

echo "==> Checking prerequisites..."
command -v python3 >/dev/null || { echo "Python 3 required"; exit 1; }
command -v node >/dev/null    || { echo "Node.js required"; exit 1; }
command -v redis-cli >/dev/null || { echo "Redis required"; exit 1; }
command -v mariadb >/dev/null || { echo "MariaDB required"; exit 1; }

if [ ! -d "$BENCH_DIR" ]; then
  echo "==> Initializing bench at $BENCH_DIR..."
  pip install --user frappe-bench
  bench init --frappe-branch "$FRAPPE_BRANCH" --python "python${PYTHON_VERSION}" "$BENCH_DIR"
fi

cd "$BENCH_DIR"

if [ ! -d "apps/erpnext" ]; then
  echo "==> Installing ERPNext..."
  bench get-app erpnext --branch "$FRAPPE_BRANCH"
fi

if [ ! -d "apps/hamilton_erp" ]; then
  echo "==> Installing hamilton_erp from current directory..."
  bench get-app hamilton_erp "${OLDPWD}"
fi

if [ ! -d "sites/$SITE_NAME" ]; then
  echo "==> Creating test site $SITE_NAME..."
  bench new-site "$SITE_NAME" --admin-password admin --mariadb-root-password root
  bench --site "$SITE_NAME" install-app erpnext
  bench --site "$SITE_NAME" install-app hamilton_erp
fi

echo "==> Running migrations..."
bench --site "$SITE_NAME" migrate

echo "==> Running tests to verify setup..."
bench --site "$SITE_NAME" run-tests --app hamilton_erp || echo "Tests failed — check output above"

echo ""
echo "==> Done. Next steps:"
echo "    cd $BENCH_DIR"
echo "    bench start          # in one terminal"
echo "    open http://${SITE_NAME}:8000  # username: Administrator, password: admin"
```

Make it executable: `chmod +x init.sh` and commit.

### What to also include in repo root

- `CLAUDE.md` — already in your roadmap. Standard onboarding file for AI tooling.
- `AGENTS.md` — same purpose for non-Claude AI tooling (Codex CLI, etc.).
- `README.md` — for humans. Should contain: what the app is, prereqs, link to `init.sh`, link to `docs/HANDOFF.md`, link to deployed production URL.

### Action items

- [ ] **Tier 2** Create `init.sh` at repo root.
- [ ] **Tier 2** Add `docs/setup.md` covering: (1) clone, (2) `bench init`, (3) `bench get-app`, (4) `bench new-site`, (5) `./init.sh`. Should fit on one page. New dev should reach a green test run inside 30 minutes.
- [ ] **Tier 3** Add a `docs/troubleshooting.md` cross-reference at the bottom of `init.sh` so obvious failure modes (Redis not running, MariaDB password wrong, Python version mismatch) point at the right doc section.

### What will cost billable hours if missing

A developer who has to figure out the bench setup from `claude_memory.md` + `CLAUDE.md` + `testing_checklist.md` will burn 2–4 hours and arrive grumpy. A 40-line `init.sh` plus a one-page setup doc converts that into 20 minutes.

---

## Section 14 — What a Clean Professional Handoff Looks Like

This is the single most important section. The handoff package determines whether your dev's first invoice is "8 hours catching up" or "30 hours catching up plus 5 hours of frustrated email back-and-forth."

### The handoff package — file by file

Every item below should exist in the repo at handoff:

#### Top-level

- ✅ `README.md` — what the app does, who it's for, prereqs, quick-start link.
- ✅ `init.sh` — see §13.
- ✅ `CLAUDE.md` — AI-assistant onboarding file.
- ✅ `.env.example` — every env var, with placeholder values, no real secrets.
- ✅ `.github/workflows/tests.yml` — CI passing.

#### `docs/` folder

- ✅ `HANDOFF.md` — see template below.
- ✅ `decisions_log.md` — every architectural decision and why. (You already have this — verify current.)
- ✅ `lessons_learned.md` — every dead-end you hit and how you got out.
- ✅ `venue_rollout_playbook.md` — step-by-step "how to install on a new venue's site."
- ✅ `dc_sync_notes.md` — preserve race-condition lock system context.
- ✅ `data_model.md` — diagram or list of every custom DocType, its fields, its relationships. Your dev's first question.
- ✅ `permissions_matrix.md` — table of Role × DocType × Permissions. Their second question.
- ✅ `phase_2_wishlist.md` — explicit list of what's *not* done, with priority.
- ✅ `troubleshooting.md` — known issues + fixes (e.g., "if scheduler stops, run X").
- ✅ `app_compatibility.md` — verified Frappe/ERPNext/MariaDB versions.
- ✅ `setup.md` — paired with `init.sh`.
- ✅ `operations/disaster_recovery.md` — backup/restore drill procedure.
- ✅ `operations/runbook.md` — manual bench commands the operator might need.
- ✅ `operations/audit.md` — where to look for "who did what."
- ✅ `operations/secrets.md` — where each secret lives (without values).
- ✅ `security/permission_matrix.md` — the matrix referenced above.

### `docs/HANDOFF.md` template

```markdown
# Hamilton ERP — Developer Handoff

## At-a-glance
- App name: hamilton_erp
- Frappe version: v16 (version-16 branch)
- ERPNext version: v16
- Production: hamilton-erp.v.frappe.cloud
- Repo: github.com/csrnicek/hamilton_erp
- Owner: Chris Srnicek (csrnicek@yahoo.com)

## What this app does
[2-3 paragraphs explaining the business, the venue, what staff use it for]

## Architecture decisions (read decisions_log.md for full context)
- Single Frappe site per venue, NOT multi-tenant.
- PIN-based staff identity (not Frappe User accounts for floor staff).
- Custom locking system in `hamilton_erp/locking.py` — DO NOT REMOVE.
- Workflow-only management of Bathhouse Asset.status field.
- Race-condition protection via frappe.db.get_value(..., for_update=True).

## What's done (Phase 1, Tasks 1-25)
[Bulleted list]

## What's NOT done (Phase 2 wishlist)
[Bulleted list with rough priorities]

## How to deploy
[Step by step, including: how to push, how it deploys to Frappe Cloud, how to roll back]

## How to run tests
1. ./init.sh
2. cd ~/frappe-bench-hamilton
3. bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp

## How to monitor production
1. Frappe Cloud dashboard: [URL]
2. Error Log in Desk: [link]
3. SSH into bench: [instructions]

## Known issues / gotchas
- [List of every "if X happens, do Y"]

## Whom to contact
- Owner / business decisions: Chris (email, phone)
- Frappe Cloud account: [details]
- GitHub access: [details]
```

### What separates a clean handoff from a messy one

- **Clean:** Every architectural decision has a "why" written down. Messy: reasons live only in Slack threads.
- **Clean:** Tests are green on `main`. Messy: "the tests pass on my laptop, just ignore the failures on CI."
- **Clean:** `git log` shows meaningful commit messages. Messy: 47 commits titled "fix" and "wip."
- **Clean:** No `TODO` or `FIXME` in code without a corresponding GitHub Issue. Messy: hundreds of TODOs.
- **Clean:** Dead code, commented-out code, and unused imports removed. Messy: archaeology required.
- **Clean:** Secrets in environment variables, documented in `.env.example`. Messy: hard-coded API keys.
- **Clean:** All custom UI changes captured in fixtures. Messy: half the workflows exist only in production database.

### Pre-handoff git hygiene checklist

Run these before pinging the dev:

```bash
cd ~/frappe-bench-hamilton/apps/hamilton_erp

# 1. Ensure you're on main
git checkout main
git pull

# 2. Look for accidentally-committed secrets
git log -p | grep -iE "password|api[_-]?key|secret|token" | head -50
# If anything looks real, you have a security incident. Rotate the secret AND
# rewrite git history (or accept it's leaked and rotate). Tell the dev.

# 3. Look for stale TODOs
grep -rn "TODO\|FIXME\|XXX\|HACK" hamilton_erp/ | wc -l
# Convert meaningful ones to GitHub Issues. Delete the rest.

# 4. Look for dead code (commented-out blocks)
grep -rn "^[[:space:]]*#.*def \|^[[:space:]]*#.*class " hamilton_erp/ | head -20

# 5. Run the linter
ruff check . && ruff format --check .

# 6. Run the tests
cd ~/frappe-bench-hamilton
bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp

# 7. Check fixtures are exported and committed
bench --site hamilton-unit-test.localhost export-fixtures --app hamilton_erp
git status apps/hamilton_erp/hamilton_erp/fixtures/
```

### What the dev will charge extra for if you skip the above

| Missing item | Typical extra cost |
|---|---|
| Fixtures not exported / not in repo | 4–10 hours to figure out what's customized |
| No CI / tests don't run for them | 2–4 hours to get a working bench |
| `extend_doctype_class` not used (override instead) | 4–8 hours to refactor before they can safely upgrade |
| No `init.sh` or equivalent | 2–6 hours setup, recurring per environment |
| No HANDOFF.md / decisions_log.md | 8–20 hours of "archaeology" to understand the codebase |
| Track Changes not enabled | Can't be fixed retroactively — data loss is permanent |
| Wildcard `doc_events` | 2–4 hours of "why is the system slow?" investigation |
| No `.env.example` | 1–3 hours of "what API keys does this need?" |
| Secrets committed to Git | Security incident response, ~5–20 hours |
| Bench commands run in production by hand (vs. patches) | Re-derivation work for every new venue, 4–8 hours each |

Conservative total of "wasted billable hours from skipping pre-handoff cleanup": **30–80 hours.** At developer rates ($100–$200/hr), that's $3,000–$16,000 in cleanup billing.

---

## Section 15 — Prioritized Master Action Checklist

Walk top-to-bottom. Items marked 🔴 will cost real money or permanent damage if missed.

### Tier 1 — Block production launch / handoff (~7.5 hours of work)

| # | Item | Section | Est. Time |
|---|---|---|---|
| T1.1 | Create `.github/workflows/tests.yml` — full CI test runner | §7 | 90 min |
| T1.2 | Add branch protection on `main` requiring tests green | §7 | 5 min |
| T1.3 | Verify `bench export-fixtures` produces zero diff against committed JSON | §4 | 30 min |
| T1.4 | Verify both patches are idempotent (run twice, expect no-op) | §5 | 30 min |
| T1.5 | Audit every function path in `hooks.py` resolves to a real function | §6 | 15 min |
| T1.6 | Apply `override_doctype_class` → `extend_doctype_class` correction at `hooks.py:69` | §3, §6 | 15 min |
| T1.7 | Add justification comments above every `ignore_permissions=True` in `lifecycle.py` | §12 | 30 min |
| T1.8 | Enable Track Changes on Venue Asset, Venue Session, Cash Drop, Cash Reconciliation, Shift Record, Asset Status Log, Bathhouse Receivable Log, Bathhouse Settings | §9 | 20 min |
| T1.9 | Enable Audit Trail (System Settings) for Hamilton roles | §9 | 10 min |
| T1.10 | Enable Frappe Cloud hourly backups + backup encryption + save key to password manager | §11 | 30 min |
| T1.11 | Run real backup → restore drill on a fresh Frappe Cloud site, document procedure in `docs/operations/disaster_recovery.md` | §11 | 90 min |
| T1.12 | Pin Frappe Cloud site to specific v16 minor version, disable auto-update | §11 | 15 min |
| T1.13 | Audit `site_config.json` for committed secrets (history scan) | §11 | 15 min |
| T1.14 | Configure Error Log retention (90 days) and email alerting | §11 | 20 min |
| T1.15 | Add scheduler heartbeat job + dead-scheduler alert | §10 | 60 min |
| T1.16 | Wrap `check_overtime_sessions` in try/except with `frappe.log_error()` | §10 | 15 min |
| T1.17 | Write a real `README.md` (replaces 2-line placeholder) with CI badge | §2, §7 | 30 min |
| T1.18 | Replace `frappe.flags.in_test` → `frappe.in_test` (36 occurrences, 5 files) | §3 | 30 min |
| T1.19 | Audit `== "1"` / `== "0"` string comparisons for v16 type changes | §3 | 30 min |
| T1.20 | Verify rate limiter exists for PIN-based staff identity | §12 | 15 min |
| T1.21 | Document `check_overtime_sessions` Phase 2 stub with TODO + link to phase_2_wishlist | §10 | 10 min |
| T1.22 | Audit field permlevels for sensitive fields (cost, financial, member PII) | §8 | 60 min |

### Tier 2 — Strongly recommended (~8 hours of work)

| # | Item | Section | Est. Time |
|---|---|---|---|
| T2.1 | Add `lint.yml` workflow (ruff check + format check) | §7 | 20 min |
| T2.2 | Add `bench migrate` step to CI | §7 | 15 min |
| T2.3 | Document permlevel for every field on Hamilton DocTypes | §8 | 60 min |
| T2.4 | Export permission matrix to `docs/security/permission_matrix.md` | §8 | 30 min |
| T2.5 | Configure Log Settings retention for Activity Log, Version, Email Queue | §9 | 15 min |
| T2.6 | Add `docs/operations/audit.md` | §9 | 30 min |
| T2.7 | Add integration test asserting `check_overtime_sessions` <2s against populated DB | §10 | 45 min |
| T2.8 | Document manual-run bench commands in `docs/operations/runbook.md` | §10 | 45 min |
| T2.9 | Configure Frappe Cloud offsite backup destination (S3 or equivalent) | §11 | 20 min |
| T2.10 | Document secrets inventory (without values) in `docs/operations/secrets.md` | §11 | 30 min |
| T2.11 | Add CI guard rejecting new `@frappe.whitelist()` without `methods=[...]` | §12 | 15 min |
| T2.12 | Add CSRF-rejection integration test for state-changing endpoints | §12 | 60 min |
| T2.13 | Audit System Manager role assignments on prod | §12 | 10 min |
| T2.14 | Create `init.sh` and `docs/setup.md` (30-min onboarding) | §13 | 90 min |
| T2.15 | Add empty `patches/v0_2/` placeholder + `patches/README.md` | §5 | 15 min |
| T2.16 | Add `app_compatibility.md` documenting verified Frappe/ERPNext/MariaDB versions | §3 | 20 min |
| T2.17 | Add saved Error Log report "Errors in last 24h by exception type" pinned to dashboard | §11 | 15 min |
| T2.18 | Add `boot_session` hook to push Hamilton config to `frappe.boot` | §6 | 30 min |
| T2.19 | Write `docs/HANDOFF.md` from template | §14 | 60 min |
| T2.20 | Write `docs/data_model.md` | §14 | 60 min |
| T2.21 | Write `.env.example` with all env vars and placeholder values | §14 | 20 min |
| T2.22 | Write `docs/phase_2_wishlist.md` consolidating all Phase 2 items | §14 | 30 min |

### Tier 3 — Nice to have (~3 hours of work, saves operational toil)

| # | Item | Section | Est. Time |
|---|---|---|---|
| T3.1 | Cache bench environment in CI (shaves 5–7 min off each run) | §7 | 30 min |
| T3.2 | Nightly cron workflow against latest `version-16` | §7 | 30 min |
| T3.3 | Add `before_uninstall` hook with safety prompt | §3 | 15 min |
| T3.4 | Add `make export-fixtures` (or bench alias) with built-in git diff check | §4 | 15 min |
| T3.5 | Build saved report "Operator Activity by Shift" combining Shift Record + Activity Log | §9 | 60 min |
| T3.6 | Add `frappe.rate_limit()` to bulk-action endpoints | §12 | 30 min |
| T3.7 | Subscribe to security advisories on `frappe/frappe` + `frappe/erpnext` | §12 | 5 min |
| T3.8 | Set quarterly encryption-key rotation reminder | §11 | 5 min |
| T3.9 | Slack/Telegram webhook on critical errors | §11 | 120 min |
| T3.10 | External uptime monitor (Uptime Robot / Better Stack) | §11 | 15 min |

### Tier 4 — Phase 2 prep (do during/after handoff, not before)

| # | Item | Section |
|---|---|---|
| T4.1 | Implement `permission_query_conditions` on `Venue Asset` for venue isolation | §8 |
| T4.2 | Adopt `cron_long` queue for any future heavy nightly jobs | §10 |
| T4.3 | Add `validate_modified` on Venue Asset for defense-in-depth concurrency | §6 |
| T4.4 | Migrate to code-first custom fields (away from fixtures) | §4 |
| T4.5 | v16 Field Masking on member PII (phone, email) | §8 |

---

## Section 16 — The "What This Will Cost You If Missing" Heuristic

Use this when prioritising. For each Tier 1 item, the cost-of-missing is roughly:

| Missing item | Worst-case incident | Est. dollar cost |
|---|---|---|
| CI test runner | Bad commit auto-deploys → 30 min downtime + emergency rollback | $500–$2k (lost revenue + dev time) |
| Backup restore drill not done | Real restore needed, encryption key lost or version mismatch → can't restore | $5k–$50k (data loss + reconstruction) |
| Audit trail not enabled | Cash discrepancy, no record of who did what → forensic SQL day | $1k–$3k (dev time) |
| Track Changes delayed by N days | Audit history for those N days is permanently lost | Permanent — incalculable in bad scenario |
| Scheduler heartbeat | Scheduler crashes silently at 6pm Friday, overtime detection dead all weekend | Operational chaos, customer disputes |
| `ignore_permissions` not justified | Pen-test or new dev finding → 2-hour security review | $300–$600 (dev time) |
| Site config secrets in git history | Anyone with repo read access can read prod credentials | Catastrophic |
| Version pinning | Frappe v16.15 ships breaking change overnight, asset board breaks | $1k + rushed rollback |

**Heuristic:** Tier 1 items map to incidents that cost more than the time to fix them. Always do them first.

---

## Section 17 — Final Pre-Deploy Sanity Check (the night before going live)

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

# 9. Frappe Cloud version matches expected pin (eyeball in dashboard)

# 10. Backup taken in last hour (Frappe Cloud dashboard)

# 11. Restore drill documented and recently rehearsed (within last 30 days)
ls -la docs/operations/disaster_recovery.md
```

If any step is red, do not deploy.

---

## Section 18 — The First 24–48 Hours After Handoff (What to Watch For)

Once you've handed over the keys:

1. **The dev will run `init.sh` on their laptop.** If anything breaks, they'll ping you. Be available the first day.
2. **They'll ask "where's the production environment?"** Have the Frappe Cloud login + 2FA backup codes ready (in 1Password / equivalent).
3. **They'll ask "what's the deploy process?"** Document this in HANDOFF.md before they ask.
4. **They'll likely refactor `hooks.py` and the override pattern.** Normal and good. Don't panic.
5. **They may push back on architectural decisions.** Have your `decisions_log.md` ready so the conversation is "here's why we chose this; what would you do differently and why?" instead of "we did this because Claude said so."
6. **They'll find bugs your tests didn't catch.** Normal. Track in GitHub Issues.

---

## Appendix A — Quick-Win Bash Commands to Run Before Handoff

These are one-shot commands to surface obvious gaps. Run them, fix what they find.

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

1. **Frappe Cloud-specific dashboard configuration is documented from public sources** (frappe.io/cloud, the Frappe blog). The actual Frappe Cloud dashboard UI was not used during research. Treat action items as "go find this in Frappe Cloud and turn it on" not "click here, then click there."

2. **Field-level permission (permlevel) examples are general, not Hamilton-specific.** Tier 1 task T1.22 (audit field permlevels) is the work of doing that — flagged as work to do, not work done.

3. **Frappe v16's exact new RBAC features beyond the v15 baseline are under-documented in public sources.** v16 release notes I could find emphasised performance and new doctypes, not security. If v16 introduced a permission feature that supersedes anything here, verify against `docs.frappe.io/framework/v16/...`.

4. **Audit Trail at System Settings level** is referenced in docs but the exact UI path was not verified. T1.9 will require ~5 min of clicking around to confirm location.

5. **Backup encryption key rotation procedure** is documented in general terms but Frappe doesn't ship a one-command rotation tool. The "take backup, restore to new site with new key, cut over" flow is the established pattern from forum discussion, not officially blessed.

6. **The CI workflow templates are starting points.** Will need ~1 cycle of trial-and-error against actual GitHub Actions runners to nail down: exact MariaDB image tag, whether the test site needs `--mariadb-socket` or `--no-mariadb-socket`, whether `bench get-app` needs `--branch version-16` or `--branch develop`. Budget the full 90-minute estimate (T1.1) accordingly.

7. **`Custom DocPerm` and the `_block_pos_closing_for_operator()` flow** — Hamilton's pattern (delete the row in `after_install`) works on first install but won't be re-applied if the row is recreated by an ERPNext upgrade. A future ERPNext minor that ships a fresh `POS Closing Entry` permission row could silently grant operators access to expected cash totals. Worth converting to a fixture or a periodic check.

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
- [Frappe v16 release notes — frappe.io/framework/version-16](https://frappe.io/framework/version-16)
- [Frappe shared CI workflows — github.com/frappe/frappe/wiki/Shared-Test-CI-Actions](https://github.com/frappe/frappe/wiki/Shared-Test-CI-Actions)

### Practitioner blogs and community
- [Mastering ERPNext 16: The Complete Guide to Custom Apps — David Muraya](https://davidmuraya.com/blog/develop-erpnext-custom-app/)
- [How to setup CI/CD for the Frappe Applications using GitHub Actions — Frappe DevOps](https://frappedevops.hashnode.dev/how-to-setup-ci-cd-for-the-frappe-applications-using-github-actions)
- [Frappe DevOps Toolkit: Monitor, Fix, and Deploy Like a Pro — Pranav Dixit](https://medium.com/@pranavdixit20/frappe-devops-toolkit-monitor-fix-and-deploy-like-a-pro-26d1be6a8015)
- [Frappe Framework v16 Release: Key Features & Impact — Indictran](https://www.indictranstech.com/frappe-framework-v16-whats-new-in-2026/)
- [Separation of Concerns: Logging in APIs over Frappe Framework — Alaa Alsalehi](https://alaa-alsalehi.medium.com/separation-of-concerns-logging-in-apis-over-frappe-framework-aae487326f37)
- [Installing Custom Apps in ERPNext — Aalam Info Solutions](https://medium.com/@aalam-info-solutions-llp/installing-custom-apps-in-erpnext-a-comprehensive-guide-to-move-data-custom-fields-and-doctypes-0b07ca60199e)
- [Fixtures and Custom Fields in Frappe and ERPNext — Code with Karani](https://codewithkarani.com/2021/09/06/fixtures-and-custom-fields-in-and-frappe-erpnext/)
- [Understanding Frappe's Encryption Key — Frappe Forum](https://discuss.frappe.io/t/understanding-frappe-s-encryption-key-data-security-backups-and-migration/152853)
- [Anthropic Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

### Security references
- [SQL Injection, Insufficient ACLs in Frappe Framework — Altion Security](https://www.altion.dk/posts/frappe-security-vulnerabilities)
- [CVE-2026-41317 — Frappe Press CSRF on API secret generation](https://cvefeed.io/vuln/detail/CVE-2026-41317)
- [Frappe Framework Vulnerabilities — CSIRT.SK](https://csirt.sk/frappe-framework-vulnerabilities.html)

### Product updates referenced
- [Frappe Product Updates — March 2026](https://frappe.io/blog/product-updates/product-updates-for-march-2026)
- [Frappe Product Updates — February 2026](https://frappe.io/blog/product-updates/product-updates-for-february-2026)

---

## Companion Document

For developer-handoff readiness (different lens, complementary checklist), see `docs/inbox/prompt5_handoff_audit_2026-04-25.md` (or its archived location after merge).

Items appearing in both documents are not duplicate work — they are doubly-validated priorities. Examples:
- README.md gap (both audits flag it)
- CI test workflow (both audits flag it)
- `ignore_permissions` justification (both audits flag it)
- Setup script / `init.sh` (both audits flag it)
- Track Changes / Audit Trail (both audits flag it)
- `extend_doctype_class` correction (both audits flag it)

When two independent audits agree, the priority is real.

---

*End of merged production & handoff readiness audit. Walk top-to-bottom with Claude Code. Items in Tier 1 are ~7.5 hours; Tier 2 is ~8 hours; Tier 3 is ~3 hours. Total Tier 1+2+3: ~18.5 hours of focused work. Worth roughly $3,000–$16,000 in cleanup billing avoided.*
