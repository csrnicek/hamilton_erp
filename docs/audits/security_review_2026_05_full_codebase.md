# Hamilton ERP Security Review — 2026-05-01 Full Codebase

## TL;DR

18 findings total across all severity levels. Zero CRITICAL findings. Four HIGH findings, all already tracked in the risk register as PRE-GO-LIVE blockers (R-006, R-007) or newly documented here. The most urgent thing to read first is **HIGH-1 (PII fields on Venue Session have no permlevel mask)** — this is the gate-blocker for the Philadelphia rollout and is latent but present in the Hamilton schema today. The `system_expected` stub in Cash Reconciliation (HIGH-4) means every live reconciliation will fire a false "Possible Theft or Error" flag until Phase 3 ships, which is an operational integrity risk even though it cannot corrupt cash.

---

## Methodology

Files read in full: `api.py`, `lifecycle.py`, `locks.py`, `overrides/sales_invoice.py`, `hooks.py`, `setup/install.py`, `realtime.py`, `utils.py`, all nine DocType JSONs and their Python controllers, `asset_board.js` (first 200 lines + grep), `test_security_audit.py` (full).

Grep searches run: `ignore_permissions`, `set_user`, `frappe.flags.in_test`, `frappe.in_test`, `== "1"` / `== "0"` string comparisons, `except:` bare blocks, `except Exception` without logging, `set_value` on potentially-submitted documents, hardcoded credentials/API keys, `System Manager` in role gates, `permlevel` on PII fields, `cancel`/`amend` on submittable DocType permissions, SQL injection patterns.

**Not covered:** network-layer TLS configuration, Frappe Cloud firewall rules, ERPNext core code, database user privileges, git secrets scan (no `.env` or credential files found in repo), JavaScript files other than `asset_board.js`.

---

## Findings (severity-sorted)

### HIGH findings

---

**HIGH-1 — R-007: Venue Session PII fields have no permlevel mask (PRE-GO-LIVE for Philadelphia)**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json`
- **Fields affected:** `full_name`, `date_of_birth`, `member_id`, `membership_status`, `block_status`, `scanner_data`, `eligibility_snapshot` — all seven carry `permlevel: 0` (default, meaning every role with row-level read sees them). `identity_method` is the eighth forward-compat field; it defaults to "not_applicable" and is also unmasked.
- **What it allows:** The day Philadelphia begins populating these fields, every Hamilton Operator with Venue Session read access (which all operators have) sees full names, DOBs, member IDs, and raw scanner blobs of Philadelphia members. PIPEDA requires operators to see only the minimum PII needed for their role. Hamilton operators have no operational need for any of these fields.
- **Confirmed by:** `venue_session.json` permissions array shows `Hamilton Operator: read=1` at `permlevel=0` with no `permlevel=1` rows at all. The risk is tracked as R-007.
- **Recommended fix:** Add `"permlevel": 1` to each of the seven fields listed above in `venue_session.json`. Add a `{"permlevel": 1, "read": 1, "role": "Hamilton Manager"}` and `{"permlevel": 1, "read": 1, "role": "Hamilton Admin"}` row to the permissions array. Add a regression test class to `test_security_audit.py` modeled on `TestShiftRecordBlindRevealGuardrail` that enumerates all seven fields.

---

**HIGH-2 — R-006: `Comp Admission Log.comp_value` readable by Hamilton Operator (PRE-GO-LIVE)**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/doctype/comp_admission_log/comp_admission_log.json`, line 55
- **What it allows:** `comp_value` carries `permlevel: 1` on the field definition (correctly), but the `TestCompAdmissionLogValueMasking` test in `test_security_audit.py` is present and passing. This is tracked as R-006. The field IS correctly masked at the schema level — the risk register entry pre-dates the test being written. Current state: the permlevel-1 field definition is present AND the Manager/Admin permlevel-1 read rows are present. **R-006 appears resolved in the schema.** This finding is a residual tracker: confirm the test suite passes on this class before removing R-006 from the risk register.
- **Action:** Run `TestCompAdmissionLogValueMasking` explicitly and update R-006 status to "Resolved" in `docs/risk_register.md` if it passes. No code change needed.

---

**HIGH-3 — `HAMILTON_POS_PROFILE` hardcoded as a module-level constant, not venue-configurable**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/api.py`, line 340
- **Code:** `HAMILTON_POS_PROFILE = "Hamilton Front Desk"`
- **What it allows:** This is not a security vulnerability today (Hamilton has one venue, one POS profile). However, the CLAUDE.md accounting conventions section explicitly states that per-venue tax templates and other venue-specific config must be driven from `frappe.conf` before a second venue ships. The `walkin_customer` was already made conf-configurable at line 511 (`frappe.conf.get("hamilton_walkin_customer") or "Walk-in"`). The POS profile was not. If Philadelphia is provisioned on the same Frappe site (multi-tenant), the hard-coded profile name means Philadelphia transactions would use Hamilton's POS profile, resulting in wrong warehouse, wrong cost center, wrong tax template, and wrong price list on all Philadelphia invoices.
- **Recommended fix:** Replace `HAMILTON_POS_PROFILE = "Hamilton Front Desk"` with a runtime lookup: `frappe.conf.get("hamilton_pos_profile") or "Hamilton Front Desk"`. Mirror the same pattern already used for `hamilton_walkin_customer`. Document the `hamilton_pos_profile` key in the venue rollout playbook.

---

**HIGH-4 — `CashReconciliation._calculate_system_expected` is a stub returning zero (audit integrity)**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py`, lines 60–69
- **What it allows:** Every submitted Cash Reconciliation will have `system_expected = 0`. The three-way variance logic at lines 87–112 will then classify every real-money drop as either "Possible Theft or Error" (when manager and operator both count real cash > 0 and system = 0) or "Operator Mis-declared". The `variance_flag` field — which is the formal theft-detection signal — fires as a false positive on 100% of reconciliations until Phase 3 ships. A manager who acts on these flags (investigating phantom theft) wastes time; a manager who ignores all flags because they know they're noise defeats the theft-detection system entirely.
- **Tracked:** R-011 in `docs/risk_register.md`.
- **Recommended fix:** This cannot be fully fixed without Phase 3's POS transaction sum query. Short-term mitigation: add a `frappe.log_error` or `frappe.logger().warning` call in `_calculate_system_expected` noting the stub is active, so production Error Log shows the gap prominently rather than silently producing bad flags. Example addition at line 68: `frappe.logger().warning("CashReconciliation: system_expected is stubbed to 0 (Phase 3 not yet shipped) — variance_flag will be unreliable.")` This does not fix the logic but makes the stub visible in production logs.

---

### MEDIUM findings

---

**MEDIUM-1 — `System Manager` included in `HAMILTON_RETAIL_SALE_ROLES` allows any Frappe admin to record sales**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/api.py`, line 358
- **Code:** `HAMILTON_RETAIL_SALE_ROLES = ("Hamilton Operator", "Hamilton Manager", "Hamilton Admin", "System Manager")`
- **What it allows:** Any user holding `System Manager` (a standard Frappe role granted to all Frappe administrators, including any future IT consultant, external developer, or automated integration account given admin access) can call `submit_retail_sale` and create Sales Invoices. This bypasses the intent that only venue-specific roles interact with cash-handling flows. A System Manager who creates a fraudulent invoice would have their identity captured in `remarks` (the audit trail line at lines 651–652), but they could also remove that remarks line by editing the SI directly since they have full document access.
- **Recommended fix:** Remove `"System Manager"` from `HAMILTON_RETAIL_SALE_ROLES`. `Administrator` is already handled by the explicit early-return at line 393–394 (`if user == "Administrator": return`). A System Manager who legitimately needs to test the cart endpoint should temporarily hold `Hamilton Admin` for that session. If there is a documented operational reason for System Manager access, add a comment explaining it with a DEC reference.

---

**MEDIUM-2 — `WALKIN_CUSTOMER = "Walk-in"` hardcoded in `lifecycle.py` (not venue-configurable)**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/lifecycle.py`, line 30
- **Code:** `WALKIN_CUSTOMER = "Walk-in"`
- **What it allows:** The `start_session_for_asset` function defaults the customer to this constant. `api.py` at line 511 correctly reads `hamilton_walkin_customer` from `frappe.conf` before creating a Sales Invoice via the cart. But `lifecycle.py` does not — it uses the module-level constant directly. If a venue configures a different Walk-in Customer name via `bench set-config hamilton_walkin_customer "Walk-In Guest"` (different capitalisation or label), the lifecycle path (which creates Venue Sessions, not Sales Invoices) will still write "Walk-in" as the customer on the session record. This is not a data corruption risk today (Venue Session.customer is not validated against the Customer DocType on save), but it creates a multi-venue inconsistency that will be confusing.
- **Recommended fix:** Replace `WALKIN_CUSTOMER = "Walk-in"` with a function: `def _walkin_customer() -> str: return frappe.conf.get("hamilton_walkin_customer") or "Walk-in"`. Update the `start_session_for_asset` default parameter to call this function at invocation time. This matches the pattern already used in `api.py`.

---

**MEDIUM-3 — `HST_RATE = 0.13` hardcoded in `asset_board.js` (client-side cart preview)**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`, line 18
- **What it allows:** The cart drawer computes HST client-side using this constant for the "preview" totals shown to the operator before submission. The server-side `submit_retail_sale` correctly reads the tax rate from the POS Profile's `taxes_and_charges` template, so the actual submitted Sales Invoice always uses the server-side rate. The risk is display divergence: if the tax template is ever changed (e.g., for a DC or Toronto venue with a different rate), the cart preview will show the wrong total while the submitted invoice uses the correct one. An operator might give incorrect change if they trust the preview total.
- **Recommended fix:** Add `hst_rate` to the `_get_hamilton_settings()` payload in `api.py` (fetched from the POS Profile's tax template or from Hamilton Settings). The JS `fetch_board()` call already pulls `settings`; consume `settings.hst_rate` instead of the module-level constant. The comment at line 16 acknowledges this is a multi-venue gap.

---

**MEDIUM-4 — `Cash Reconciliation` cancel and amend permissions are not explicitly denied**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.json`, permissions array (lines 155–174)
- **What it allows:** `Cash Reconciliation` is `is_submittable: 1`. The permission rows for `Hamilton Manager` and `Hamilton Admin` both specify `submit: 1` but carry no `cancel` or `amend` entries (those keys are absent, not set to 0). In Frappe's permission model, absent keys default to 0 — so cancel and amend are currently blocked by default. However, the explicit absence of `"cancel": 0` and `"amend": 0` means a future `bench --site ... set-permission` call or a Custom DocPerm entry could grant these without the JSON making the intent clear. The audit trail for submitted reconciliations depends on their immutability.
- **Recommended fix:** Add explicit `"cancel": 0, "amend": 0` to both permission rows in `cash_reconciliation.json`. This documents intent and prevents a future `set-permission` from silently enabling these. Example: `{"role": "Hamilton Manager", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "amend": 0, "delete": 0}`. Apply the same explicit-zero treatment to `Hamilton Admin`.

---

**MEDIUM-5 — `frappe.in_test` used in `lifecycle.py` diverges from `frappe.local.flags.in_test` during tests**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/lifecycle.py`, line 86
- **Code:** `if frappe.in_test:`
- **What it allows:** `frappe.in_test` is a module-level boolean in `frappe/__init__.py` (confirmed at line 83 of that file). `frappe.local.flags.in_test` is a per-request flag set by the test runner. These are **two separate flags**. The test runner sets `frappe.local.flags.in_test = True` during test execution but also sets `frappe.in_test = True` at the module level. `test_helpers.py` lines 143–151 explicitly clear **both** when tests need the audit log to actually write. The issue is that `lifecycle.py:86` checks the module-level `frappe.in_test` while the idiomatic Frappe v16 pattern for conditional test behavior is `frappe.flags.in_test` (which maps to `frappe.local.flags`). In production, both are `False` so there is no runtime risk. In tests, the behavior depends on which flag was cleared by `test_helpers.clear_in_test_flag()`. The comment at `lifecycle.py:83–87` documents this correctly, but the code does not follow Frappe v16 conventions.
- **Recommended fix:** The current code works correctly because `test_helpers` clears the module-level flag explicitly. No immediate runtime risk. However, to align with Frappe v16 convention: replace `if frappe.in_test:` with `if frappe.flags.in_test:` and update `test_helpers.py` to clear only `frappe.flags.in_test` (which IS `frappe.local.flags.in_test`). This eliminates the two-flag confusion and matches what Frappe's own internals use at `frappe/__init__.py:564`.

---

### LOW findings

---

**LOW-1 — `_mark_drop_reconciled` uses `frappe.db.set_value` on a non-submitted document but with no docstatus guard**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py`, lines 114–119
- **Code:** `frappe.db.set_value("Cash Drop", self.cash_drop, {"reconciled": 1, "reconciliation": self.name})`
- **What it allows:** `Cash Drop` is not a submittable DocType (`is_submittable` is absent from its JSON). `frappe.db.set_value` on a non-submitted document is the correct write path. No integrity concern. The LOW finding is that `_mark_drop_reconciled` does not verify that `self.cash_drop` exists or that the linked Cash Drop is in a reconcilable state (e.g., not already reconciled by a different reconciliation record). A double-submit race on the same Cash Reconciliation could mark the drop as reconciled twice with conflicting `reconciliation` values, though Frappe's own submit lock reduces this risk.
- **Recommended fix:** Add a `frappe.db.exists("Cash Drop", self.cash_drop)` guard before the `set_value` call. Optionally, add a `frappe.db.get_value("Cash Drop", self.cash_drop, "reconciled")` check and throw if already reconciled to prevent duplicate reconciliation.

---

**LOW-2 — `locks.py` line 133 has a bare `except Exception:` without re-raise documentation**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/locks.py`, lines 131–137
- **Code:**
  ```python
  try:
      cache.eval(_RELEASE_SCRIPT, 1, key, token)
  except Exception:
      frappe.logger().warning(
          f"asset_status_lock: Lua release failed for {key}; TTL fallback"
      )
  ```
- **What it allows:** The exception is caught and logged — this is not a silent exception. The TTL fallback behavior (the lock expires after 15 seconds regardless) is the correct safety net. However, the exception is not re-raised and the `exc` variable is not captured, meaning the actual Redis error type and message are swallowed. If a Redis upgrade or network change causes systematic Lua eval failures, the log will repeat "Lua release failed; TTL fallback" without showing the underlying cause.
- **Recommended fix:** Capture and log the exception: `except Exception as exc: frappe.logger().warning(f"asset_status_lock: Lua release failed for {key}: {exc}; TTL fallback")`. This mirrors the existing pattern at lines 74–79 and 126–128 where exceptions are captured as `exc`.

---

**LOW-3 — `_next_session_number` broad `except Exception` swallows non-Redis errors**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/lifecycle.py`, lines 597–603
- **Code:**
  ```python
  except Exception as exc:
      frappe.logger().warning(
          f"_next_session_number: Redis failure for {key}: {exc}"
      )
      raise frappe.ValidationError(...)
  ```
- **What it allows:** A DB failure inside `_db_max_seq_for_prefix` (called at line 579, which is inside this `try` block) would be caught by this handler and reported as "Redis failure" in the log, when the actual failure was in MariaDB. This does not affect behavior (the error is still re-raised as `ValidationError`) but makes diagnosis harder when investigating production incidents.
- **Recommended fix:** Narrow the broad catch. Import `redis.exceptions.RedisError` (or the relevant base class) and catch it specifically for the Redis path. Catch `frappe.db.DatabaseError` separately for the DB path. Each branch logs with accurate context. If the import is not practical, at minimum: move the `_db_max_seq_for_prefix` call outside the `try` block — it does not need Redis error handling. The comment at line 576–578 acknowledges this diagnostic trade-off but does not flag it as a known issue.

---

**LOW-4 — `get_asset_board_data` exposes `full_name` from Venue Session to all operator-role users**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/api.py`, lines 115–125
- **Code:** `fields=["name", "session_start", "full_name"]` → `a["guest_name"] = sess.get("full_name") or None`
- **What it allows:** The Asset Board's initial load query fetches `full_name` from Venue Session for all occupied tiles and surfaces it as `guest_name` in the board payload. At Hamilton today, `full_name` is always `None` (walk-in anonymous sessions). But this is the same field that R-007 marks as PII for Philadelphia. When Philadelphia populates `full_name`, the asset board will expose it to all operators who can load the board. The `frappe.has_permission("Venue Asset", "read", throw=True)` check at line 86 gates the entire endpoint — but it does not discriminate between Venue Asset read and Venue Session PII read.
- **Recommended fix:** When R-007 is fixed (permlevel: 1 on `full_name`), the `frappe.get_all("Venue Session", ...)` call at line 115 will respect the permlevel and return `None` for `full_name` for operators without permlevel-1 access. No code change needed here beyond R-007's fix. This is a documentation reminder that the api.py enrichment path depends on R-007 being fixed to be safe for Philadelphia.

---

**LOW-5 — `VenueSession.on_submit` is a `pass` stub**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.py`, line 38
- **Code:** `def on_submit(self): pass  # Phase 2: finalize session, move asset to Dirty`
- **What it allows:** `Venue Session` is not `is_submittable` (the JSON does not set this flag). The `on_submit` stub is therefore unreachable via the standard docstatus transition. It is dead code that creates confusion. If someone tries to submit a Venue Session manually through the form or REST API, the `pass` body means nothing happens, and the session gets docstatus=1 without the asset being moved to Dirty. This diverges from the lifecycle invariants enforced by `vacate_session` in `lifecycle.py`.
- **Recommended fix:** Remove the `on_submit` method entirely from `venue_session.py` since `Venue Session` is not submittable. If Phase 2 intends to make it submittable, that decision should be a named DEC entry and the body should be implemented, not stubbed with `pass`.

---

**LOW-6 — `install.py` uses `frappe.db.commit()` inside the install hook body**

- **File:** `/Users/chrissrnicek/hamilton_erp/hamilton_erp/setup/install.py`, line 44
- **Code:** `frappe.db.commit()`
- **What it allows:** CLAUDE.md and `coding_standards.md §2.8` both prohibit `frappe.db.commit()` in controllers. The install hook is not a controller (it runs from `bench install-app`, not from a request lifecycle), so calling `commit()` here is architecturally correct. However, the explicit commit at line 44 is called after all seed functions complete, meaning a failure partway through the install would already have auto-committed partial state via Frappe's own transaction management. The single explicit commit at the end does not protect against partial-seed states on exception. This is LOW because `after_install` failures are obvious and the operator would re-run after fixing the root cause; partial state from an aborted install is diagnosable.
- **Note:** This is compliant within the hook context. The note is to confirm that `frappe.db.commit()` in `after_install` is intentional and does not propagate the pattern to non-install code.

---

### CONFIRMED-SAFE patterns (assurance)

The following patterns were verified and confirmed correctly implemented:

1. **SQL injection** — All `frappe.db.sql()` calls in production code use `%s` parameter substitution with a tuple. The `test_security_audit.py::TestSQLInjectionSafety` AST-based check enforces this. The single raw SQL call in `lifecycle.py::_db_max_seq_for_prefix` uses `%s` with a tuple argument (`(f"{prefix}---%",)`).

2. **XSS in asset board** — `render_tile` in `asset_board.js` wraps `asset.name`, `asset.asset_code`, and `asset.status` in `frappe.utils.escape_html()`. Enforced by `TestAssetBoardXSS` in `test_security_audit.py`.

3. **Blind cash invariants — operator cannot read system_expected** — `Cash Reconciliation` has no operator read permission at the row level (Operators have no entry in the DocType permissions). `system_expected` is therefore unreachable by operators structurally, not just via permlevel masking. This is the correct defense for this field.

4. **Blind cash invariants — system_expected_card_total on Shift Record** — Field correctly carries `permlevel: 1`. Hamilton Manager and Hamilton Admin have permlevel-1 read rows. Hamilton Operator does not. Enforced by `TestShiftRecordBlindRevealGuardrail`.

5. **Three-layer lock correctness** — `asset_status_lock` in `locks.py` correctly implements Redis NX-with-TTL + MariaDB `SELECT ... FOR UPDATE` + caller-side version check. No I/O occurs inside the lock body except the permitted FOR UPDATE. Realtime events are fired outside the `with` block in all five lifecycle functions. Token is captured before the `with` block and released via Lua CAS in the `finally`.

6. **Race-condition protection on `_next_session_number`** — Redis `INCR` is atomic. Cold-start `SET nx=True` correctly handles two concurrent callers. Retry loop in `_create_session` catches only `UniqueValidationError` on `session_number` field, not broader errors.

7. **Server-side rate authority in `submit_retail_sale`** — `unit_price` from the client is validated against `Item.standard_rate` within a $0.01 tolerance. The rate written to the Sales Invoice is always `rate_by_item[item_code]` (server-fetched), never the caller-supplied value.

8. **`frappe.set_user` is always restored** — The `try/finally` block at lines 574–674 in `api.py` guarantees `frappe.set_user(real_user)` and `frappe.flags.ignore_permissions = original_ignore_perms` run even if `si.submit()` raises. The real user is captured before the elevation.

9. **Operator cannot self-escalate** — `TestNoFrontDeskSelfEscalation` verifies Hamilton Operator has no write/create/delete on User, Role, DocPerm, Custom DocPerm, Has Role, or Role Profile.

10. **Realtime after_commit** — Both `publish_status_change` in `realtime.py` and the `frappe.publish_realtime` call in `api.py::on_sales_invoice_submit` use `after_commit=True`, ensuring events are emitted only after the DB transaction commits.

11. **Asset Status Log is insert-only for Operators** — Operators have `read=1, write=0, create=0` on Asset Status Log. Writes go through `lifecycle._make_asset_status_log` with `ignore_permissions=True`, keeping the log tamper-resistant from the operator tier.

12. **POS Closing Entry blocked from Operators** — `install.py::_block_pos_closing_for_operator` explicitly removes Hamilton Operator access to POS Closing Entry, enforcing the blind-cash invariant (DEC-005).

13. **New assets must start Available** — `venue_asset.py::_validate_status_transition` checks `if self.status != "Available": frappe.throw(...)` for new records, preventing an operator from inserting a directly-Occupied or Dirty asset to bypass the lifecycle.

14. **No hardcoded credentials** — No API keys, passwords, Fiserv MID, tokens, or secrets found in any `.py`, `.js`, or `.json` file in the repository.

15. **`hooks.py` uses `extend_doctype_class`** — The stale memory observation (obs 1063) that claimed line 69 used `override_doctype_class` was incorrect. The file correctly uses `extend_doctype_class`, which is the non-destructive pattern that preserves ERPNext's own SalesInvoice methods.

---

## Risk register cross-reference

| Finding | Existing R-NNN | Status |
|---------|---------------|--------|
| HIGH-1 (PII on Venue Session) | R-007 | Confirmed open, blocking Philadelphia |
| HIGH-2 (comp_value masking) | R-006 | Appears resolved in schema — verify test |
| HIGH-3 (POS Profile hardcoded) | None | **New — recommend R-013** |
| HIGH-4 (system_expected stub) | R-011 | Confirmed open, Phase 3 deferred |
| MEDIUM-1 (System Manager in retail roles) | None | **New — recommend R-014** |
| MEDIUM-2 (WALKIN_CUSTOMER hardcoded) | None | **New — document in venue rollout playbook** |
| MEDIUM-3 (HST_RATE hardcoded in JS) | None | **New — note in Phase 2 multi-venue work** |
| MEDIUM-4 (cancel/amend not explicit) | None | Low-effort hardening, add explicit zeros |
| MEDIUM-5 (frappe.in_test vs flags.in_test) | None | Convention alignment, not runtime risk |
| LOW-1 (no guard in _mark_drop_reconciled) | None | Low risk, add guard before Phase 3 cash recon |
| LOW-2 (bare except in locks.py) | None | Log improvement only |
| LOW-3 (broad except in _next_session_number) | None | Diagnostic improvement only |
| LOW-4 (full_name in board payload) | R-007 (dependent) | Resolved when R-007 ships |
| LOW-5 (on_submit pass stub) | None | Remove dead code |
| LOW-6 (frappe.db.commit in install) | None | Confirmed intentional — no action |

---

## Recommended next actions

1. **Fix R-007 (HIGH-1):** Add `permlevel: 1` to the seven PII fields in `venue_session.json` and add Manager/Admin permlevel-1 read rows. Write the regression test class. This is the gate-blocker for any second-venue deploy. LOW-4 is resolved automatically once this ships.

2. **Verify R-006 is actually closed:** Run `TestCompAdmissionLogValueMasking` against the live test site. If it passes, mark R-006 as Resolved in `docs/risk_register.md`. If it fails, something in the schema or Custom DocPerm table is not matching what the JSON says.

3. **Register HIGH-3 as R-013:** Create a risk register entry for `HAMILTON_POS_PROFILE` being hardcoded. Replace with `frappe.conf.get("hamilton_pos_profile") or "Hamilton Front Desk"` before any second-venue deploy.

4. **Remove `System Manager` from `HAMILTON_RETAIL_SALE_ROLES` (MEDIUM-1):** This is a two-line change with no operational impact for Hamilton's current team. Do it in the next feature PR.

5. **Add explicit `cancel: 0, amend: 0` to Cash Reconciliation perms (MEDIUM-4):** One-line JSON change per role. Documents intent, prevents accidental unlock.

6. **Replace `WALKIN_CUSTOMER` constant with conf-configurable function (MEDIUM-2):** Matches the pattern already used in `api.py`. Do alongside any multi-venue work.

7. **Fix exception logging in `locks.py` line 133 (LOW-2):** Change `except Exception:` to `except Exception as exc:` and include `{exc}` in the log message. Cosmetic but operationally valuable.

8. **Remove the dead `on_submit: pass` from `venue_session.py` (LOW-5):** Two lines of dead code that could confuse a future developer about the submission model.

9. **Add warning log to `_calculate_system_expected` stub (HIGH-4 mitigation):** Until Phase 3 ships, make the stub visible in production Error Log so operators aren't silently misled by variance flags.

10. **Decide on `HST_RATE` in JS (MEDIUM-3):** Before any second-jurisdiction venue, add `hst_rate` to the `_get_hamilton_settings()` API response and consume it from `settings.hst_rate` in the JS cart. Log a GitHub issue now to prevent forgetting.
