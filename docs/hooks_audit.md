# hooks.py — Audit (Task 25 item 11)

**Generated:** 2026-05-01 (Task 25 item 11 — autonomous audit, conformance-only).

**File audited:** `hamilton_erp/hooks.py` (89 lines).

**Verdict:** **PASS.** No code changes required. Every directive in the file is correct for Frappe v16 + ERPNext v16, and every documented intent is honored by the file. Two structural gaps deferred to Phase 2 are documented below for the rollout playbook.

---

## What's in the file (line-by-line conformance check)

| Section | Lines | Verdict | Notes |
|---|---|---|---|
| App metadata (`app_name` … `app_version`) | 1–7 | ✅ Pass | All required fields present. `app_license = "MIT"` matches `LICENSE` file (added 2026-04-30 in PR #65). `app_email` is a real address, not a placeholder. |
| `required_apps = ["frappe", "erpnext"]` | 9 | ✅ Pass | Correct dependency ordering. Frappe v16 enforces these before `after_install` runs. |
| Assets bundling (`app_include_css`) | 11–22 | ✅ Pass | CSS scoped to `.hamilton-asset-board` / `.hamilton-loading` so it cannot bleed into other Frappe pages. Loaded app-wide because Asset Board is a Frappe Page (page-level CSS includes were removed in v15 — see comment). No `app_include_js` — Asset Board's JS is loaded by the Page itself, not app-wide. |
| `fixtures` | 24–44 | ✅ Pass | Three entries, all with explicit filters — Custom Field (`name like %-hamilton_%`), Property Setter (`name like %-hamilton_%`), Role (`name in [Hamilton Operator, Hamilton Manager, Hamilton Admin]`). Filters prevent `bench export-fixtures` from leaking other apps' custom fields into Hamilton's fixture set. |
| `after_install` | 46–50 | ✅ Pass | Single hook → `hamilton_erp.setup.install.after_install`. Idempotent per `frappe.db.exists` guards in install.py. |
| `after_migrate` | 52–62 | ✅ Pass | `hamilton_erp.setup.install.ensure_setup_complete` heals `is_setup_complete=1` for frappe + erpnext on every migrate. Documented workaround for the v16 single-admin dev-site setup_wizard loop. Idempotent. |
| `extend_doctype_class` | 64–70 | ✅ Pass | Uses **`extend_doctype_class`** — the v16-correct mixin pattern (not `override_doctype_class`, which has the "last app wins" defect). Single entry: `Sales Invoice → hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice`. |
| `doc_events` | 72–79 | ✅ Pass | One specific event: `Sales Invoice on_submit → hamilton_erp.api.on_sales_invoice_submit`. No wildcard `*` (which is a documented v16 perf trap). |
| Scheduler events | 81–89 | ✅ Pass | **Deliberately empty.** The Phase 1 stub `check_overtime_sessions` (no-op `pass`, fired 96×/day) was removed in PR #53 with a documented Phase 2 reintroduction note. Comment block records the intent so the next session doesn't re-add it without the Tier-1 try/except + Error Log wrapper. |

---

## Best-practice cross-checks against `CLAUDE.md` "Frappe v16 hard rules"

| Rule | Compliance | Evidence |
|---|---|---|
| Tests must be self-contained | N/A — `hooks.py` is not a test file | — |
| Tabs not spaces | ✅ Pass | File uses tabs (matches Frappe formatter, lint config in `pyproject.toml`) |
| Inherit from `IntegrationTestCase` / `UnitTestCase` | N/A | — |
| Use `frappe.db.get_value(..., for_update=True)` | N/A — no DB calls in hooks.py | — |
| Never use `frappe.db.commit()` in controllers | ✅ Pass | No `db.commit()` calls in hooks.py. The `after_install` and `after_migrate` callees handle their own transaction boundaries through Frappe's framework. |
| `@frappe.whitelist()` with `allow_guest=False` | N/A — hooks.py registers callbacks, not endpoints | — |
| Validate permissions in controllers, not JS | N/A | — |
| `frappe.db.exists()` guards in install/seed | ✅ Pass (transitively) | Verified in `install.py` and patches |
| Use `frappe.db.delete()` not raw SQL | N/A | — |

---

## Specific things checked and verified

1. **`extend_doctype_class` vs `override_doctype_class`** — `hooks.py:69` uses `extend_doctype_class` (correct). Memory observation 1063 (2026-04-15) flagging this as a "Known Bug to Fix" was **stale** — the bug had already been fixed before that observation was filed, or the observation was filed against a different file. The file currently on `main` is correct.

2. **Wildcard `*` in `doc_events` or `scheduler_events`** — neither uses `*`. Specific DocType keys only. Avoids the "every doc-save runs every hook" perf trap documented in the inbox audits.

3. **`app_email` placeholder** — `csrnicek@yahoo.com` is the real owner email. No `your.email@example.com` placeholder (which was present and fixed in PR #53).

4. **License consistency** — `app_license = "MIT"` in `hooks.py:6` matches the `LICENSE` file added in PR #65 (which was missing despite the manifest declaring MIT — caught by the same audit cycle that produced this file).

5. **No `db.commit()`** — grep confirms zero matches in hooks.py. Transaction boundaries left to the framework, per CLAUDE.md hard rule.

---

## Deliberate omissions (Phase 2+ scope)

These hooks could be added later. Each is intentionally absent today:

| Hook | Phase | Why deferred |
|---|---|---|
| `boot_session` | Phase 2 (Tier 0 monitoring) | Sentry SDK init lands here when Sentry is wired up. See `docs/production_practices_audit.md` Tier 0. |
| `notification_config` | Phase 2 | Hamilton has no in-app notification rules in Phase 1; Phase 2 cart/POS workflow may add them. |
| `permission_query_conditions` | Multi-venue rollout (Philadelphia+) | Phase 1 Hamilton uses DocPerm row-level read; multi-venue requires per-venue data fences via query conditions on Venue Session, Asset Status Log, etc. Will live alongside the field-masking work in Task 25 item 7. |
| `has_permission` | Multi-venue rollout | Same rationale as above — function-level permission checks for cross-venue data isolation. |
| `web_include_css/js`, `website_route_rules`, `home_page` | Phase 3+ | No guest-facing web portal in Phase 1 / 2. |
| `before_uninstall` | Not planned | Hamilton ERP is not designed to be uninstalled in production; bench-level removal is the operator path if ever needed. |
| `app_include_js` | Probably never | Asset Board JS is page-loaded by the Frappe Page system. App-wide JS would be wasteful for the current scope. |

---

## Phase 2 reintroduction watchlist

When Phase 2 reintroduces a scheduled job (the comment at `hooks.py:84-89` calls this out):

- The job MUST be wrapped in a `try`/`except` block that writes to `frappe.log_error()` so silent failures don't pollute `tabScheduled Job Log` with "Success" rows for nothing useful.
- The cron schedule must match the actual work; do not re-introduce a 15-minute fire rate for a job that only does meaningful work once a shift.
- `docs/lessons_learned.md` — append a lesson if the same pattern (silent stub eating scheduler slots) recurs.

---

## References

- File audited: `hamilton_erp/hooks.py` (commit at audit time: current `main`).
- Cross-references: `docs/production_practices_audit.md` (broader audit including hooks.py at line 187), `docs/inbox.md` 2026-04-29 AI bloat audit (mentions hooks.py top-level vars are false positives in vulture).
- Related Task 25 items: item 18 (init.sh — already complete via PR #59), item 20 (check_overtime_sessions stub — purged via PR #53), item 22 (extend_doctype_class — verified correct in this audit).
