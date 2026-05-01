# Fixtures to Git — Audit (Task 25 item 8)

**Generated:** 2026-05-01 (Task 25 item 8 — autonomous audit).

**Item premise:** Ensure every fixture-class artifact (Custom Fields, Property Setters, Roles, DocType schemas, Pages, Workspaces) is committed to git so a fresh checkout can reconstruct the full schema without DB manipulation.

**Audit result:** **PASS. All 14 fixture-class JSON files are git-tracked.** No action required. Closing item 8 as already complete with the inventory below.

---

## What "fixtures" means in this audit

Two layers:

1. **Frappe `fixtures = [...]` config** — exported via `bench export-fixtures`, stored under `hamilton_erp/fixtures/*.json`. These are filtered subsets of Custom Field / Property Setter / Role / etc. that ship with the app and are reapplied on `bench migrate`.

2. **Doctype-style JSON shipped under `app_name/app_name/`** — DocType schemas (`doctype/*/`), Pages (`page/*/`), Workspaces (`workspace/*/`). These are loaded by Frappe's app loader directly from the file tree and don't go through the fixtures system. They function as fixtures-by-disk.

Item 8's scope is "everything that lets a fresh `bench install-app` reconstruct the full schema." That covers both layers.

---

## Layer 1 — `hamilton_erp/fixtures/` directory

`ls -la hamilton_erp/fixtures/`:

| File | Size | Tracked? | Entries | Notes |
|---|---|---|---|---|
| `custom_field.json` | 10076 bytes | ✅ Git-tracked | 7 entries | `bench export-fixtures` filtered by `name like %-hamilton_%` |
| `role.json` | 831 bytes | ✅ Git-tracked | 3 entries | Hamilton Operator, Hamilton Manager, Hamilton Admin |
| `property_setter.json` | 2 bytes (`[]`) | ✅ Git-tracked | 0 entries | **Empty file required** — see LL-026 in lessons_learned. Frappe's exporter creates the file even when empty; the file must be tracked so its presence pins the "no overrides" intent. |

**`hooks.py:30-44` `fixtures` config:**

```python
fixtures = [
    {"dt": "Custom Field",    "filters": [["name", "like", "%-hamilton_%"]]},
    {"dt": "Property Setter", "filters": [["name", "like", "%-hamilton_%"]]},
    {"dt": "Role",            "filters": [["name", "in", ["Hamilton Operator", "Hamilton Manager", "Hamilton Admin"]]]},
]
```

✅ Filters are explicit (no leakage from other apps' Custom Fields). Verified during `docs/hooks_audit.md` (Task 25 item 11).

---

## Layer 2 — DocType / Page / Workspace JSONs

`find hamilton_erp -name "*.json" -path "*/doctype/*" -o -name "*.json" -path "*/page/*" -o -name "*.json" -path "*/workspace/*"`:

| Path | Type | Tracked? |
|---|---|---|
| `hamilton_erp/hamilton_erp/doctype/comp_admission_log/comp_admission_log.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/asset_status_log/asset_status_log.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/shift_record/shift_record.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/hamilton_board_correction/hamilton_board_correction.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/cash_drop/cash_drop.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/doctype/hamilton_settings/hamilton_settings.json` | DocType | ✅ |
| `hamilton_erp/hamilton_erp/page/asset_board/asset_board.json` | Page | ✅ |
| `hamilton_erp/hamilton_erp/workspace/hamilton_erp/hamilton_erp.json` | Workspace | ✅ |

**Verification command:**

```bash
for f in $(find hamilton_erp -name "*.json"); do
    if ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        echo "UNTRACKED: $f"
    fi
done
```

Result: zero untracked files. All 14 JSON artifacts ship in the git tree.

---

## What this audit did NOT verify (out of scope without bench access)

This is a static-tree audit — it confirms that what's on disk is in git. It cannot confirm:

1. **Whether the fixtures are up-to-date with the live database state.** A developer who edits a Custom Field in the Frappe UI and forgets to run `bench export-fixtures` would create drift between the live state and what's on disk. The next deploy would silently lose the unsynced edit.
2. **Whether Workspace customizations made post-install on the dev site are exported.** Workspaces are notoriously easy to drift because the UI lets you reorder cards / hide sections without prompting an export.
3. **Whether the production site (`hamilton-erp.v.frappe.cloud`) has the same fixtures applied as the dev/test sites.** This requires a deploy verification, not a tree audit.

These three are covered by Task 25 item 12 (Clear error log) and the production-deploy verification in the original Task 25 plan (steps 1-4: trigger Frappe Cloud bench update, run migrate, walk the acceptance checklist). Out of scope here.

---

## Pre-deploy guardrail recommendation

Item 8's audit is "static check — green." For ongoing freshness, the right structural defense is a CI check that runs `bench export-fixtures --app hamilton_erp` against a fresh-install site and fails if the result differs from what's checked in. This isn't currently in CI. **Recommend adding a Phase 2 CI job** that catches fixture drift before it lands in production.

The CI job would:
1. Run `bench --site test_site install-app hamilton_erp`
2. Run `bench --site test_site export-fixtures --app hamilton_erp`
3. Fail if `git diff --exit-code hamilton_erp/fixtures/` shows changes

This adds ~30s to each CI run and catches the "developer forgot to commit fixture export" class of drift.

Logging here as a follow-up rather than implementing in this PR (item 8's scope is verification, not new CI infrastructure).

---

## Recommendation: update the checklist item text

Current line 8 in `docs/task_25_checklist.md`:

> 8. Fixtures to Git

Suggested replacement (post-merge):

> 8. ✅ DONE 2026-05-01 — fixtures and DocType/Page/Workspace JSONs all git-tracked (14 files). See `docs/audits/fixtures_to_git_audit.md`. Phase 2 follow-up: CI job for fixture-drift detection.

---

## References

- LL-026 in `docs/lessons_learned.md` — "`property_setter.json` must exist even if empty"
- `docs/hooks_audit.md` (Task 25 item 11) — verifies `fixtures` config in hooks.py is correct
- Frappe v16 fixtures docs: https://frappeframework.com/docs/v16/user/en/python-api/hooks#fixtures
- Frappe Workspace export gotchas: https://github.com/frappe/frappe/wiki (workspace JSON drift is a recurring issue across versions)
