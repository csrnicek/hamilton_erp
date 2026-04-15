# Frappe v16 — Hamilton ERP Platform Rules

## Test flag

Use `frappe.in_test` not `frappe.flags.in_test`. The latter is deprecated in Frappe v16
and may not be reliably set in all contexts (e.g., pytest without bench runner).
There were 36 occurrences across 5 files that needed fixing — grep before assuming
they're all gone.

## DocType class extension

Use `extend_doctype_class` not `override_doctype_class` in hooks.py.
`override_doctype_class` replaces the entire class; `extend_doctype_class` merges
your methods into the existing class, preserving upstream behavior.

Currently hooks.py line 69 uses `override_doctype_class` — this should be migrated
to `extend_doctype_class` when touching that area.

## Type comparisons

Always use real type comparisons. Never use string comparisons like `== "1"` or `== "0"`.
Frappe checkbox fields return `1`/`0` as integers, not strings. String comparison
silently passes in some contexts and fails in others.

## Redis lock key format

The correct format is: `hamilton:asset_lock:{asset_name}`

- Key is **asset-only** — no operation suffix
- All operations on the same asset serialize against one key
- TTL is 15 seconds (`LOCK_TTL_MS = 15_000`)
- Defined in `hamilton_erp/locks.py` line 67

### Lock key bug history

The key previously included an operation suffix (`hamilton:asset_lock:{asset_name}:{operation}`).
This was wrong because two different operations on the same asset (e.g., assign + vacate)
could both acquire separate locks, defeating the purpose of mutual exclusion. Fixed during
ChatGPT review on 2026-04-10. A regression test exists in `test_locks.py` —
`test_lock_key_format_is_asset_only`.
