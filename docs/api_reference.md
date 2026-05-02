# Hamilton ERP — API Reference

**Audience:** Frontend developers integrating with the Asset Board, integration partners, and senior contractors auditing the public surface.
**Scope:** Every `@frappe.whitelist()` endpoint in `hamilton_erp/api.py`. As of 2026-05-01 (main branch), **8 endpoints** — PR #51 added `submit_retail_sale` (cart → POS Sales Invoice) on 2026-04-30. The bulk `mark_all_clean_*` endpoints were removed and stay removed per `docs/decisions_log.md` "A29-1 Bulk 'Mark All Clean' feature REMOVED."
**Source of truth:** `hamilton_erp/api.py`. When this doc and the code disagree, the code wins; update this doc to match.

---

## Conventions

### Calling
- All endpoints require an authenticated session — `allow_guest=False` is the implicit default of `@frappe.whitelist()`. Guest calls return 403.
- Permission gating is `frappe.has_permission("Venue Asset", "<action>", throw=True)` at function entry. The `Hamilton Operator` role grants `read + write` on Venue Asset; absence raises `frappe.PermissionError`.
- POST endpoints accept `Content-Type: application/x-www-form-urlencoded` (Frappe's default for client-side `frappe.call()`) or `application/json`. GET endpoints accept query params.

### URL pattern
- `/api/method/hamilton_erp.api.<endpoint_name>`
- The Hamilton Asset Board JS uses `frappe.call({ method: "hamilton_erp.api.<endpoint_name>", args: {...} })` exclusively.

### Locking and concurrency
- Every mutating endpoint goes through `lifecycle.<method>()` which acquires the three-layer lock (Redis advisory + MariaDB `FOR UPDATE` + `version` field check) per DEC-019 and `coding_standards.md` §13.
- A concurrent caller hitting the same asset receives `LockContentionError` (HTTP 417 / `frappe.exceptions.LockContentionError`). Clients should retry once after a short wait; persistent contention indicates a stale Redis key (see `RUNBOOK.md` §4.2).
- Realtime broadcasts (`hamilton_asset_status_changed`) fire `after_commit=True` — they reach other tabs only after the writer's transaction commits, never before.

### Error shapes
Frappe wraps unhandled exceptions in `{"exc_type": "...", "exception": "...", "_error_message": "..."}` envelopes with appropriate HTTP status codes. Hamilton-specific errors that callers should handle by name:

| Exception | Meaning | Recommended client behaviour |
|---|---|---|
| `frappe.PermissionError` | User lacks role / DocType perm | Show "Not authorized" — do NOT retry |
| `LockContentionError` | Three-layer lock conflict | Retry once after 1s; if still failing, show toast and `RUNBOOK.md` §4.2 |
| `frappe.TimestampMismatchError` | Optimistic-lock version mismatch | Soft refresh the asset board — another tab beat this one |
| `frappe.ValidationError` | State-machine rejected the transition | Show the message; the requested transition is invalid for the current state |

---

## Endpoints

### `get_asset_board_data` (GET)

**Purpose:** Initial Asset Board load. Single batched query shape — no N+1. Same payload feeds the first render and any "force refresh" client action.

**Permissions:** `Venue Asset.read`. Granted to Hamilton Operator+.

**Args:** None.

**Returns:**
```json
{
  "assets": [
    {
      "name": "VA-31874",
      "asset_code": "R001",
      "asset_name": "Sing STD 1",
      "asset_category": "Room",
      "asset_tier": "Single Standard",
      "status": "Available",
      "current_session": null,
      "expected_stay_duration": 360,
      "display_order": 1,
      "last_vacated_at": null,
      "last_cleaned_at": null,
      "hamilton_last_status_change": "2026-05-01T02:50:18",
      "version": 0,
      "reason": null,
      "session_start": null,
      "guest_name": null,
      "oos_set_by": null
    }
  ],
  "settings": {
    "grace_minutes": 15,
    "default_stay_duration_minutes": 360
  }
}
```

**Per-asset fields:**

| Field | Type | When populated |
|---|---|---|
| `name` | string | Always — Frappe primary key (e.g. `VA-31874`) |
| `asset_code` | string | Always — operator-facing label (e.g. `R001`, `L007`) |
| `asset_name` | string | Always — friendly name (e.g. `Sing STD 1`) |
| `asset_category` | enum | Always — `Room` or `Locker` |
| `asset_tier` | string | Always — `Single Standard`, `Deluxe Single`, `GH Room`, `Double Deluxe`, `Locker` |
| `status` | enum | Always — `Available`, `Occupied`, `Dirty`, `Out of Service` |
| `current_session` | string\|null | When status=`Occupied` — Venue Session name |
| `expected_stay_duration` | int (min) | Always — overtime calculation base |
| `display_order` | int | Always — Asset Board grid ordering |
| `last_vacated_at` | datetime\|null | When asset has been vacated at least once |
| `last_cleaned_at` | datetime\|null | When asset has been cleaned at least once |
| `hamilton_last_status_change` | datetime | Always — drives "X minutes ago" UI |
| `version` | int | Always — optimistic-lock counter |
| `reason` | string\|null | When status=`Out of Service` — operator-entered reason |
| `session_start` | datetime\|null | When status=`Occupied` — drives countdown / overtime |
| `guest_name` | string\|null | When status=`Occupied` — Walk-in sessions are null (V9 D6/E8) |
| `oos_set_by` | string\|null | When status=`Out of Service` — User.full_name (V9 E11) |

**Performance contract:** Total queries = 4 regardless of occupancy. Asset list (1) + Venue Sessions for Occupied (1) + Asset Status Logs for OOS (1) + Users for OOS-set-by + guest names (1). Pinned by `test_api_phase1.test_get_asset_board_data_under_one_second` and the schema snapshot in `test_asset_board_rendering`.

**Error cases:** 403 if Administrator lost `Hamilton Operator` role (RUNBOOK §3.2). 500 if `Hamilton Settings` singleton missing (RUNBOOK §3.1).

---

### `start_walk_in_session` (POST)

**Purpose:** Walk-in flow — assign a session to an Available asset without a Sales Invoice.

**Permissions:** `Venue Asset.write`.

**Args:**
- `asset_name` (string, required) — Venue Asset's `name` (e.g. `VA-31874`).

**Returns:**
```json
{ "session": "VS-31875" }
```

**Behaviour:**
- Transitions the asset Available → Occupied inside the three-layer lock.
- Creates a Venue Session with `customer = "Walk-in"`, `assignment_status = "Assigned"`, fresh `session_number` (DEC-033 format), `session_start = now()`.
- Fires `hamilton_asset_status_changed` realtime event after commit.
- Idempotency: NOT idempotent. Calling twice in rapid succession may create two sessions on the same asset (the lock prevents the second from succeeding, raising `LockContentionError`).

**Error cases:**
- `LockContentionError` — concurrent caller. Retry once.
- `frappe.ValidationError` — asset is not Available (Occupied / Dirty / OOS).
- `frappe.TimestampMismatchError` — version mismatch from another tab.
- 403 — caller lacks `Venue Asset.write`.

**Lifecycle:** Delegates to `hamilton_erp.lifecycle.start_session_for_asset`.

---

### `vacate_asset` (POST)

**Purpose:** End an Occupied session. Asset transitions Occupied → Dirty.

**Permissions:** `Venue Asset.write`.

**Args:**
- `asset_name` (string, required).
- `vacate_method` (string, required) — `Key Return` or `Discovery on Rounds`. Distinguishes operator-confirmed vs operator-discovered vacancies for audit.

**Returns:**
```json
{ "status": "ok" }
```

**Behaviour:**
- Sets the linked Venue Session's `session_end = now()` and `vacate_method`.
- Sets the asset's `last_vacated_at = now()`, transitions to `Dirty`.
- Fires `hamilton_asset_status_changed` after commit.

**Error cases:** Same as `start_walk_in_session`, plus `ValidationError` if asset is not Occupied.

**Lifecycle:** Delegates to `hamilton_erp.lifecycle.vacate_session`.

---

### `clean_asset` (POST)

**Purpose:** Single-asset Mark Clean. Asset transitions Dirty → Available.

**Permissions:** `Venue Asset.write`.

**Args:**
- `asset_name` (string, required).

**Returns:**
```json
{ "status": "ok" }
```

**Behaviour:**
- Sets the asset's `last_cleaned_at = now()`, transitions to `Available`.
- Fires `hamilton_asset_status_changed` after commit.
- Bulk variants (`mark_all_clean_rooms`, `mark_all_clean_lockers`) were removed in the DEC-054 reversal (PR #41, 2026-04-30) — see `test_asset_board_rendering.test_api_does_not_define_mark_all_clean_endpoints` for the regression pin. Per-tile clean is the only supported flow.

**Error cases:** `ValidationError` if asset is not Dirty.

**Lifecycle:** Delegates to `hamilton_erp.lifecycle.mark_asset_clean`.

---

### `set_asset_oos` (POST)

**Purpose:** Take an asset Out of Service. Reason is mandatory.

**Permissions:** `Venue Asset.write`.

**Args:**
- `asset_name` (string, required).
- `reason` (string, required) — operator-entered free text. Surfaces on the Asset Board OOS panel and in `Asset Status Log` for audit.

**Returns:**
```json
{ "status": "ok" }
```

**Behaviour:**
- Transitions any state (Available, Occupied, Dirty) → `Out of Service`.
- If status was Occupied, the linked Venue Session is closed (vacate_method=`OOS Override`).
- Fires `hamilton_asset_status_changed` after commit.

**Error cases:** `ValidationError` if `reason` is empty / whitespace-only.

**Lifecycle:** Delegates to `hamilton_erp.lifecycle.set_asset_out_of_service`.

---

### `return_asset_from_oos` (POST)

**Purpose:** Return an Out-of-Service asset to Available. Reason is mandatory (the resolution note).

**Permissions:** `Venue Asset.write`.

**Args:**
- `asset_name` (string, required).
- `reason` (string, required) — resolution note. Shows in Asset Status Log.

**Returns:**
```json
{ "status": "ok" }
```

**Behaviour:**
- Transitions `Out of Service` → `Available`.
- Fires `hamilton_asset_status_changed` after commit.

**Error cases:** `ValidationError` if asset is not OOS, or if reason is empty.

**Lifecycle:** Delegates to `hamilton_erp.lifecycle.return_asset_to_service`.

---

### `assign_asset_to_session` (POST) — Phase 2 stub, do NOT call

**Purpose:** Future Phase 2 endpoint that will assign an asset after POS payment is confirmed (Sales Invoice on_submit path).

**Permissions:** `Venue Asset.write`.

**Args:**
- `sales_invoice` (string, required).
- `asset_name` (string, required).

**Returns:** Currently raises (Phase 2 not yet built). Endpoint must not be exposed in any UI until Phase 2 ships.

**Phase 2 plan:** Will create a Venue Session linked to both the Sales Invoice and the asset, transitioning the asset Available → Occupied. The operator UX of "scan QR → confirm payment → assign locker" routes through this method post-Phase-2.

**For now:** Treat as not-implemented. Calls return Frappe's not-yet-implemented exception; do not document as a usable endpoint to integration partners.

---

### `submit_retail_sale` (POST)

**Purpose:** Create and submit a POS Sales Invoice from the cart drawer (V9.1-D8 cart UX). Called by `_open_cash_payment_modal` in `asset_board.js` when the operator confirms payment. Shipped 2026-04-30 in PR #51 (V9.1 Phase 2 cart → POS Sales Invoice with QBO-mirrored accounting seed).

**Permissions (delegated capability model):**
- Caller must hold a Hamilton role (Hamilton Operator / Hamilton Manager / Hamilton Admin) OR System Manager / Administrator. Enforced by `_check_retail_sale_permission`.
- The Sales Invoice itself is created with `ignore_permissions=True` because Hamilton Operator does not have direct Sales Invoice perms by design — direct write would bypass the constrained cart UX and the blind-cash invariants. **The cart IS the only legitimate write surface; the role gate is the only authorization check.**

**Args:**
- `items` (list of objects, required) — cart lines, each `{item_code: str, qty: int, unit_price: float}`. Accepted as a JSON-encoded string (frappe.xcall serializes lists over the wire) or as a list. **`unit_price` is validated server-side against `Item.standard_rate` (within $0.01 tolerance); mismatches raise ValidationError to defeat client-side price tampering.** The rate written to the Sales Invoice is always the server-side value.
- `cash_received` (Currency, required) — must be ≥ the rounded total. Change is computed and returned. Negative values rejected.
- `payment_method` (string, optional, default `"Cash"`) — `"Cash"` or `"Card"`. **Card raises ValidationError today** ("Card payments are Phase 2 next iteration; not yet implemented"). The argument exists now so the rounding contract is stable across phases — `_should_round_to_nickel` gates rounding by payment method, and Card is intentionally not yet wired.

**Returns:**
```json
{
  "sales_invoice": "ACC-SINV-...",
  "grand_total": 11.30,           // pre-rounding total (HST included)
  "rounded_total": 11.30,         // what the customer actually pays
  "rounding_adjustment": 0.0,     // rounded_total - grand_total
  "change": 8.70                  // cash_received - rounded_total
}
```

**Canadian penny-elimination rounding (2013):**
- Cash sales round the post-tax `grand_total` to the nearest 5¢. HST is computed first on the unrounded subtotal; the `rounding_adjustment` posts as a separate GL entry to `Company.round_off_account` (DEC-038 + Canadian nickel rule + CLAUDE.md "CAD nickel rounding is site-global").
- Card sales settle to the exact cent (`disable_rounded_total=1`). Tap-to-pay = Card per V9.1-D14.

**Pre-submit guards (in order):**
1. Hamilton role check — raises PermissionError if caller has no Hamilton role.
2. `payment_method` check — raises ValidationError on unknown method or `Card`.
3. Cart shape — raises ValidationError on empty cart or non-list items.
4. `cash_received >= 0` — raises ValidationError on negative.
5. POS Profile `Hamilton Front Desk` exists — raises ValidationError if not (operator instructed to run `bench migrate`).
6. Walk-in customer exists (configurable per venue via `frappe.conf.hamilton_walkin_customer`).
7. Per-item rate validation against `Item.standard_rate` — raises ValidationError on mismatch.
8. Pre-submit stock check via `Bin.actual_qty` — produces clean operator errors for "cart has more than stock." True concurrent last-unit races still surface as raw ERPNext stock-ledger errors on the second submit; Hamilton is single-operator most of the time so this gap is accepted.

**Stock impact:** Sales Invoice is created with `is_pos=1, update_stock=1` so submission auto-creates the Stock Ledger Entry that decrements warehouse stock on the Hamilton warehouse.

**Raises:**
- `PermissionError` — caller lacks any Hamilton role.
- `ValidationError` — empty cart, `cash_received < amount due`, unknown item, rate mismatch, insufficient stock, unsupported `payment_method`, `payment_method="Card"` (Phase 2 not yet shipped), POS Profile or Walk-in customer missing.

**Source:** `hamilton_erp/api.py:404` (`submit_retail_sale`).

**Tests:** `hamilton_erp/test_retail_sales_invoice.py` — 18 tests covering 9 seed-verification + 9 end-to-end submit_retail_sale flow + 10 adversarial tests (rounding gates, permission elevation, stock pre-checks).

---

## Sales Invoice doc-event hook

This is NOT a `@frappe.whitelist()` endpoint — it's a doc-event handler registered in `hamilton_erp/hooks.py:doc_events["Sales Invoice"]["on_submit"]`. Documented here because it's part of the runtime API surface.

### `on_sales_invoice_submit(doc, method)`

**Triggered by:** Frappe firing the `on_submit` doc event after any Sales Invoice transitions to `submitted`.

**Behaviour:** Currently a thin shim. Phase 2 hooks the cart → Sales Invoice → Venue Session creation flow here. The V9.1 retail cart UX (PR #49 stub, PR #51 implementation) populates this path.

**Signature:** Standard Frappe doc-event signature — `doc` is the Sales Invoice, `method` is the event name string. No return value.

---

## Realtime events (read-only consumers)

These are Frappe realtime events emitted by `hamilton_erp/realtime.py`. Frontend consumers subscribe via `frappe.realtime.on("event_name", handler)`.

### `hamilton_asset_status_changed`

**Emitted by:** Every successful state transition (start, vacate, clean, OOS, return).

**Payload:** Subset of the asset record — at minimum `{name, status, current_session, version, hamilton_last_status_change}`. Frontend should treat this as a hint to refresh that one tile, not a full record replacement.

**Scope:** Site-wide broadcast (DEC-055 / Q8). All connected tabs receive every event. Per-user / per-room scoping deferred to Phase 2 (`docs/inbox.md` 2026-04-29 §10 finding 5 — security gap, audit pending).

**Timing:** Fires `after_commit=True` (per `coding_standards.md` §13). Listeners only see committed state — never partial / rolled-back transitions.

### `hamilton_asset_board_refresh`

**Emitted by:** Bulk operations or admin-triggered "refresh the whole board" actions.

**Payload:** None — a signal, not data. Frontend should re-call `get_asset_board_data` on receipt.

**Scope:** Site-wide.

---

## Versioning and deprecation

Hamilton ERP is pre-1.0 (`hooks.py:app_version = "0.1.0"`). The endpoint surface is small and stable; if it changes incompatibly, the change goes through:

1. New endpoint with a versioned name (e.g. `vacate_asset_v2`).
2. Old endpoint kept around for at least one Frappe Cloud deploy cycle.
3. CHANGELOG.md and `docs/decisions_log.md` get a new entry.
4. `tests/` gets a regression test against the old endpoint to confirm it still works.

Any breaking change without that ritual is a regression — file an issue against the PR that introduced it.

---

## Related references

- `hamilton_erp/api.py` — source of truth for endpoint signatures
- `hamilton_erp/lifecycle.py` — the underlying state-machine helpers each POST endpoint delegates to
- `hamilton_erp/locks.py` — three-layer locking primitive (DEC-019, coding_standards §13)
- `docs/decisions_log.md` — locked design decisions referenced above (DEC-019, DEC-033, DEC-054, DEC-055)
- `docs/RUNBOOK.md` — operational incident response when an endpoint misbehaves
- `hamilton_erp/test_api_phase1.py` — endpoint contract tests
- `hamilton_erp/test_asset_board_rendering.py` — JS↔API integration tests + the negative test pinning that bulk endpoints don't exist

---

*Created 2026-04-30 as part of the pre-Task-25 handoff prep stack (overflow item from Stack #5). Source of all signatures: \`hamilton_erp/api.py\` at HEAD of \`main\`.*
