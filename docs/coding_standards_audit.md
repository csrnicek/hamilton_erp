# Hamilton ERP — Coding Standards Audit

**Date:** 2026-04-15
**Auditor:** Claude Code (Opus 4.6)
**Scope:** All production Python and JavaScript files in `hamilton_erp/`
**Excludes:** Documentation files (`docs/`), except where they contain executable code patterns

---

## Summary

| # | Category | Result | Issues |
|---|----------|--------|--------|
| 1 | Core Frappe/ERPNext file modifications | PASS | 0 |
| 2 | `override_doctype_class` vs `extend_doctype_class` | FAIL | 1 |
| 3 | Monkey patching of core methods | PASS | 0 |
| 4 | Raw SQL without parameterization | PASS | 0 |
| 5 | Hardcoded site names, URLs, or credentials | ADVISORY | 1 |
| 6 | Direct database writes bypassing `frappe.db` | PASS | 0 |
| 7 | Missing `@frappe.whitelist` decorators | PASS | 0 |
| 8 | `hooks.py` wildcard entries without guards | PASS | 0 |
| 9 | Silent exception handling (`except: pass`) | ADVISORY | 1 |
| 10 | ERPNext core imports (upgrade risk) | ADVISORY | 1 |

**Total: 1 actionable issue, 3 advisories, 6 clean categories.**

---

## 1. Core Frappe/ERPNext File Modifications

**Result: PASS — no issues found.**

`git diff HEAD` and `git status` on both `apps/frappe/` and `apps/erpnext/` returned
empty. No Hamilton code touches core files. All customization is done through the
correct extension mechanisms: `hooks.py`, `overrides/`, `doc_events`, and
`fixtures`.

---

## 2. `override_doctype_class` vs `extend_doctype_class`

**Result: FAIL — 1 issue found.**

| File | Line | Current | Should Be |
|------|------|---------|-----------|
| `hamilton_erp/hooks.py` | 69 | `override_doctype_class` | `extend_doctype_class` |

**What it does now:**
```python
override_doctype_class = {
    "Sales Invoice": "hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice",
}
```

**Why this is wrong:** `override_doctype_class` *replaces* the entire Sales Invoice
controller class with `HamiltonSalesInvoice`. If another custom app also overrides
Sales Invoice, only one wins — the other is silently discarded.
`extend_doctype_class` *merges* your methods into the existing class, so multiple
apps can safely extend the same DocType.

**Fix:**
```python
# hooks.py line 69 — change the key name
extend_doctype_class = {
    "Sales Invoice": "hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice",
}
```

No changes needed in `overrides/sales_invoice.py` — the class already subclasses
`SalesInvoice` correctly. Frappe's `extend_doctype_class` loader handles the
rest.

**Known issue:** Documented in `.claude/skills/frappe-v16/SKILL.md:12-17`.

---

## 3. Monkey Patching of Core Methods

**Result: PASS — no issues found.**

Searched for: `setattr(frappe`, `setattr(erpnext`, `monkey_patch`, `monkeypatch`
patterns across all `.py` files. Zero matches in production code. (One match in
`docs/superpowers/plans/` is a planning document, not executable code.)

---

## 4. Raw SQL Without Proper Parameterization

**Result: PASS — no issues found.**

All `frappe.db.sql()` calls in production code use `%s` parameterized queries:

| File | Line | Query | Parameterized? |
|------|------|-------|----------------|
| `locks.py` | 95-100 | `SELECT ... FROM tabVenue Asset WHERE name = %s FOR UPDATE` | Yes |
| `lifecycle.py` | 660-665 | `SELECT session_number ... WHERE session_number LIKE %s` | Yes |

No f-string SQL (`frappe.db.sql(f"...")`), no `.format()` SQL, and no string
concatenation in SQL found in any production file. The f-string SQL patterns that
appear in `test_security_audit.py` are documentation examples showing what NOT to
do — they are inside docstrings, not executable code.

Test files (`test_locks.py`, `test_helpers.py`, `test_checklist_complete.py`,
`test_load_10k.py`, `test_environment_health.py`, `test_database_advanced.py`,
`test_stress_simulation.py`) also use `%s` parameterization consistently.

**Existing safeguard:** `test_security_audit.py` includes an automated AST-based
scanner that parses every `.py` file for unsafe `frappe.db.sql()` patterns. This
test runs on every `bench run-tests` invocation, providing continuous regression
protection.

---

## 5. Hardcoded Site Names, URLs, or Credentials

**Result: ADVISORY — 1 minor item, no security risk.**

| File | Line | Value | Risk |
|------|------|-------|------|
| `scripts/mutation_test.py` | 23 | `SITE = "hamilton-unit-test.localhost"` | Low |
| `hooks.py` | 6 | `app_email = "chris@hamilton.example.com"` | None |
| `.env.example` | 2-12 | Placeholder API keys (`"your_..._here"`) | None |

**Details:**
- `mutation_test.py` hardcodes the test site name. This is a dev-only script (not
  shipped to production), but should ideally read from an environment variable or
  `sites/currentsite.txt` for portability.
- `hooks.py` uses the `.example.com` domain per RFC 2606 — this is correct.
- `.env.example` contains only placeholder values — this is the correct pattern.
- No real credentials, API keys, or production URLs found anywhere in the codebase.

**Fix (optional, low priority):**
```python
# scripts/mutation_test.py line 23
import os
SITE = os.environ.get("HAMILTON_TEST_SITE", "hamilton-unit-test.localhost")
```

---

## 6. Direct Database Writes Bypassing `frappe.db`

**Result: PASS — no issues found.**

Searched for: `cursor()`, `pymysql`, `mariadb`, `.execute()` patterns. Zero matches
in production code. All database access goes through:
- `frappe.db.sql()` — for raw queries (parameterized, per category 4)
- `frappe.db.get_value()` / `frappe.db.set_value()` — for single-field reads/writes
- `frappe.get_doc().save()` / `.insert()` — for full document operations
- `frappe.get_all()` — for filtered list queries
- `frappe.db.count()` — for aggregate counts
- `frappe.db.exists()` — for existence checks
- `frappe.db.delete()` — for record deletion (used once in `install.py:95`)

---

## 7. Missing `@frappe.whitelist` Decorators on API Methods

**Result: PASS — no issues found.**

Every client-callable endpoint has `@frappe.whitelist(methods=[...])` with an
explicit HTTP verb restriction (per DEC-058):

| File | Line | Method | Verb |
|------|------|--------|------|
| `api.py` | 51 | `get_asset_board_data` | GET |
| `api.py` | 124 | `assign_asset_to_session` | POST |
| `api.py` | 141 | `mark_all_clean_rooms` | POST |
| `api.py` | 153 | `mark_all_clean_lockers` | POST |
| `api.py` | 205 | `start_walk_in_session` | POST |
| `api.py` | 215 | `vacate_asset` | POST |
| `api.py` | 225 | `clean_asset` | POST |
| `api.py` | 235 | `set_asset_oos` | POST |
| `api.py` | 245 | `return_asset_from_oos` | POST |

Internal helpers (`_get_hamilton_settings`, `_mark_all_clean`, `on_sales_invoice_submit`)
correctly omit `@frappe.whitelist` — they are not client-callable.

Every whitelisted endpoint also calls `frappe.has_permission(..., throw=True)` as
its first statement, providing defense-in-depth permission checks beyond
Frappe's built-in role-based gate.

The JavaScript in `asset_board.js` correctly specifies `type: "GET"` or
`type: "POST"` on every `frappe.call()` to match the server-side verb
restriction (lines 39-44 for GET, lines 253-257 for POST).

---

## 8. `hooks.py` Wildcard Entries Without `try/except` Guards

**Result: PASS — no issues found.**

`hooks.py` contains zero wildcard (`"*"`) entries. All hook registrations target
specific doctypes or specific function paths:

- `doc_events`: Only `"Sales Invoice"` (line 77)
- `scheduler_events`: Only one cron job (line 91)
- `after_install`: Single function path (line 48)
- `after_migrate`: Single function path (line 60)
- `fixtures`: Filtered by name patterns, not `"*"` (lines 29-42)

---

## 9. Silent Exception Handling

**Result: ADVISORY — 1 item in production code (acceptable with documentation).**

**Zero bare `except: pass` patterns found.** All exception handlers use
`except Exception` (which correctly excludes `SystemExit` and `KeyboardInterrupt`).

| File | Line | Pattern | Silent? | Verdict |
|------|------|---------|---------|---------|
| `locks.py` | 124-125 | `except Exception: pass` | Yes | Acceptable |
| `locks.py` | 130-134 | `except Exception:` + `logger.warning()` | No | Correct |
| `api.py` | 194-195 | `except Exception as e:` + append to `failed` | No | Correct |
| `lifecycle.py` | 637-643 | `except Exception as exc:` + `logger.warning()` + re-raise as `ValidationError` | No | Correct |

**Detail on `locks.py:124-125`:**
```python
try:
    token_now = cache.get(key)
    if token_now != token.encode():
        frappe.logger().warning(...)
except Exception:
    pass  # <-- silent
```

This is in the `finally` block of `asset_status_lock`, in a **diagnostic-only**
code path that checks whether the Redis TTL expired during the critical section.
The silence is intentional and well-documented in the surrounding comments:
- Any exception here would mask the primary exception from the critical section
- The actual lock release happens in the immediately following `try` block
- MariaDB `FOR UPDATE` preserved data integrity regardless

**Recommendation:** No change needed. The `pass` is correct here — adding logging
could mask the primary exception's stack trace. The existing inline comments
(lines 108-115) document the rationale.

Test files contain additional `except Exception: pass` patterns in
cleanup/teardown paths — these are acceptable in test code.

---

## 10. ERPNext Core Imports (Upgrade Risk)

**Result: ADVISORY — 1 item (unavoidable, but should be documented).**

| File | Line | Import |
|------|------|--------|
| `overrides/sales_invoice.py` | 8 | `from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice` |

**Why this is flagged:** This import path is tightly coupled to ERPNext's internal
module structure. If ERPNext renames, moves, or restructures the Sales Invoice
controller in a future version, this import breaks at startup — taking down the
entire Hamilton ERP app.

**Why it cannot be avoided:** The `override_doctype_class` / `extend_doctype_class`
pattern *requires* importing the parent class to subclass it. This is the standard
Frappe pattern for extending core DocTypes. Every custom app that extends a core
DocType has this same coupling.

**Mitigation:**
1. Pin this file as a mandatory checkpoint in the upgrade playbook
   (`docs/venue_rollout_playbook.md`). Before any ERPNext version bump, verify
   that the import path still resolves.
2. The existing test `test_override_doctype_class_loads_correctly`
   (`test_database_advanced.py:472`) already validates this at test time — it
   will catch a broken import before deployment.

**No other ERPNext imports exist in production code.** The only other match
(`test_frappe_edge_cases.py:407`) is in test code.

---

## Additional Observations (Not Requested, But Noteworthy)

### XSS Protection
All user-facing values in `asset_board.js` are wrapped in
`frappe.utils.escape_html()` (lines 60, 109-114, 145-148). The `render_tile`
function escapes `asset.name`, `asset.asset_code`, `asset.asset_name`, and
`asset.status`. The `$.escapeSelector()` call on line 312 prevents selector
injection in the overtime ticker. This is correct and thorough.

### Permission Checks
Every `@frappe.whitelist` endpoint calls `frappe.has_permission(..., throw=True)`
before any data access. The `get_asset_board_data` endpoint (line 74) checks
read permission; all mutation endpoints check write permission. This is
defense-in-depth beyond Frappe's built-in role gate.

### Locking Discipline
The three-layer lock pattern in `locks.py` (Redis advisory + MariaDB FOR UPDATE +
version field CAS) is sound. No I/O occurs inside the lock section per
`coding_standards.md` section 13. Realtime publishes happen *after* the lock exits.

### `frappe.db.commit()` Hygiene
`install.py` calls `frappe.db.commit()` in `after_install` (line 12) and
`ensure_setup_complete` (line 55). These are migration/install hooks where
explicit commits are required. No production request-path code calls
`frappe.db.commit()`, which is correct per `coding_standards.md` section 2.8.

---

## Action Items

| Priority | Action | File | Line |
|----------|--------|------|------|
| **HIGH** | Change `override_doctype_class` to `extend_doctype_class` | `hooks.py` | 69 |
| Low | Make test site name configurable in mutation_test.py | `scripts/mutation_test.py` | 23 |
| Low | Add ERPNext import checkpoint to upgrade playbook | `docs/venue_rollout_playbook.md` | — |
