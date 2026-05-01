# `== "1"` / `== "0"` String Comparison Audit (Task 25 item 23)

**Generated:** 2026-05-01 (Task 25 item 23 — autonomous audit).

**Item premise:** Audit production code for `== "1"` / `== "0"` patterns where checkbox / Int fields are compared as strings, which fails when the field stores an integer.

**Audit result:** **No violations found.** All numeric comparisons in the codebase use the correct typed pattern (`int(x) == 1`, `qty === 0` in JS, etc.). Closing item 23 as "no action needed."

---

## What the gotcha looks like

In Frappe codebases, checkbox fields and Int fields can be stored as either strings or integers depending on how they were set (DB read returns int, form-submission JSON often returns string). Code that compares with a string literal will silently fail when the field happens to be the integer form:

```python
# WRONG — fails when doc.is_active is the integer 1
if doc.is_active == "1":
    ...

# RIGHT — coerce to int first
if int(doc.is_active or 0) == 1:
    ...

# ALSO RIGHT — let Python truthy-check handle it
if doc.is_active:
    ...
```

The same gotcha exists in JavaScript with `==` vs `===` — which is why Hamilton's JS uses `===` consistently.

---

## Inventory

`grep -rnE '== ["\']?[01]["\']?'` against `hamilton_erp/` returns the following matches in production code (excluding `docs/`, `patches/`, and test files):

| File | Line | Match | Verdict |
|---|---|---|---|
| `setup/install.py` | 67 | `if int(current or 0) == 1:` | ✅ Correct — coerced to int before comparison |
| `setup/install.py` | 939 | `if current == 0 or abs(current - 0.01) < 0.001:` | ✅ Correct — `current` is a float (currency value) |
| `asset_board.js` | 272 | `if (sec_assets.length === 0) continue;` | ✅ Correct — strict-equal on numeric `.length` |
| `asset_board.js` | 304 | `if (attention.length === 0)` | ✅ Correct — same |
| `asset_board.js` | 444 | `if (!items || items.length === 0)` | ✅ Correct — same |
| `asset_board.js` | 510 | `if (qty === 0)` | ✅ Correct — strict-equal on Int |
| `asset_board.js` | 552 | `if (lines.length === 0)` | ✅ Correct — same |
| `asset_board.js` | 727 | `if (h === 0) return \`${m}m\`;` | ✅ Correct — same |
| `asset_board.js` | 1217 | `if (days === 1) return __("1 day ago");` | ✅ Correct — same |

**String-form matches (`== "0"` / `== "1"` / `== '0'` / `== '1'`): zero across all .py and .js files.**

The string-quoted "1" in `__("1 day ago")` at `asset_board.js:1217` is i18n display text, not a comparison — it is the second argument inside `__()`, not part of the `===` left-hand side.

---

## What this means for Hamilton

Hamilton's codebase **never** compares an integer/checkbox field to a string literal. The pattern is consistently:

- Python: `int(x or 0) == N` for explicit int coercion when the source might be string-or-int
- Python: truthy-check `if x:` when 0 / falsy is the only "off" value
- JS: `=== N` strict-equal for numeric fields
- JS: `=== ""` strict-equal for string fields

This is a hidden Frappe footgun the codebase has avoided. No remediation is required.

---

## Patterns that DON'T appear (intentionally — would have been bugs)

For completeness, the patterns NOT present in the codebase, any of which would have been an item-23 violation:

```python
# Hypothetical violations — none of these exist in hamilton_erp/
if doc.disabled == "1":              # disabled is Check (Int 0/1), would fail when stored as int
if frappe.db.get_value(...) == "0":  # get_value returns native type
if cstr(doc.is_admin) == "1":        # cstr coerces to string, but downstream code compares to int
```

If a future PR introduces any of these patterns, a regression test in `test_security_audit.py` should fail it. Adding such a regression test was considered for this PR but deferred — there are no current violations to pin against, so the test would have nothing to assert.

---

## Recommendation: update the checklist item text

The Task 25 checklist line for item 23 currently reads:

> 23. Audit `== "1"` / `== "0"` string comparisons

Suggested replacement (post-merge):

> 23. ✅ DONE 2026-05-01 — string-comparison audit found zero violations. See `docs/audits/string_comparison_audit.md`.

---

## References

- Frappe checkbox/Int field documentation: https://frappeframework.com/docs/v16/user/en/concepts/doctypes#field-types
- Hamilton's int-coercion pattern in `hamilton_erp/setup/install.py:67`
- Hamilton's strict-equal pattern in `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`
- Related: `docs/audits/in_test_flags_audit.md` (Task 25 item 21 — same shape, also "premise was wrong, no action needed")
