# Hamilton ERP — Field Masking & Sensitivity Audit

**Scope:** Every field on every DocType under `hamilton_erp/hamilton_erp/doctype/`.
**Generated:** 2026-04-30 (Task 25 item 7 — autonomous audit, recommendations only).
**Status:** Read-only audit. No field configs were changed. Implementation deferred to a follow-up PR (or PRs) sequenced by priority in the "Implementation order" section below.

This document is the second half of the Task 25 item-7 deliverable. The first half — the role-level permission grid — lives in `permissions_matrix.md`. That file answers "which roles can read this DocType?" This file answers "given that a role can read this DocType, which fields on it are sensitive enough to need extra masking, restriction, or encryption?"

---

## Why this matters

The Hamilton role grid is **row-level only**. It tells Frappe whether a user can open a record at all. Once they're in, every field is visible to them by default. That works for most fields, but it breaks down in three places:

1. **Blind reveal invariants.** Cash Reconciliation deliberately hides `system_expected` from operators until the manager submits a blind count (DEC-021, DEC-039). The same invariant applies to `Shift Record.system_expected_card_total` but is not currently enforced.
2. **PII forward-compat.** Venue Session ships with PII fields (`full_name`, `date_of_birth`, `scanner_data`) for the Philadelphia rollout. They are null at Hamilton today, but the schema is shared — once Philadelphia populates them, every Hamilton Operator who can read a session can read these fields too.
3. **Audit-trail accusation fields.** Free-text fields like `Cash Reconciliation.notes` and `Asset Status Log.reason` may contain accusations or HR-sensitive details. Even if the Operator cannot read the row, anyone who can has unmasked detail-view access.

Field masking is a defense-in-depth layer that closes these gaps without changing row-level perms.

---

## Sensitivity tiers

| Tier | Definition | Examples |
|---|---|---|
| **CRITICAL** | Regulated PII, identity-proof data, or theft-detection figures whose disclosure to the wrong role would defeat a documented security invariant. | `date_of_birth`, `scanner_data`, `system_expected*`, `variance_amount` |
| **HIGH** | Financial values, accusatory free-text, or PII linkages. Disclosure does not directly defeat an invariant but is meaningfully harmful (HR exposure, theft-signal leakage, customer privacy). | `declared_amount`, `comp_value`, `full_name`, `closing_float_actual` |
| **MEDIUM** | Operational metadata that is not directly sensitive but enables inference (who-did-what, free-text reason fields, network infra). | `operator` (User link), `reason` (free-text), `printer_ip_address` |
| **LOW** | Operational data with no sensitivity concern. Status flags, timestamps, asset codes, foreign keys to non-sensitive records. | `status`, `asset_code`, `session_number` |

## Recommendation taxonomy

| Recommendation | Mechanism | When to use |
|---|---|---|
| **Leave as-is** | No change. Existing role grid is sufficient. | LOW-tier fields, or MEDIUM-tier fields where the read role is already restricted (e.g., Cash Reconciliation Manager-only). |
| **Mask in list view** | Frappe v16 `mask: 1` field flag, or list-view formatter that returns `"•••"` for non-privileged roles. | Currency fields shown in a list/report where casual exposure to peers is the main risk. |
| **Mask in detail view** | `permlevel: 1` (or higher) on the field, paired with a permission row that grants `permlevel: 1` only to Manager+. Field renders as blank/masked for users who lack the permlevel. | Theft-detection figures (variance, system-expected) and PII that must be hidden in detail view, not just list view. |
| **Encrypt at rest** | `is_password: 1` (Data fields) or app-level encrypt/decrypt on save/load. Value never appears in raw DB dumps or fixture exports. | Raw scan blobs, MRZ data, or any field where DB dump leakage is the threat model. Not appropriate for currency (breaks aggregation) or for fields filtered/sorted in queries. |

> Frappe v16 introduced a `mask` field flag referenced in `permissions_matrix.md` line 55. The flag handles list-view masking but does **not** replace `permlevel` for detail-view enforcement. Use `mask` for the cosmetic case (peer browsing) and `permlevel` for the structural case (blind reveals, theft-detection).

---

## Audit by DocType

### 1. Asset Status Log

Read access today: Operator R, Manager R, Admin RWD.

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `venue_asset` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `operator` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. Operator-of-record is the audit-trail point; redacting it defeats the purpose. |
| `timestamp` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `previous_status` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `new_status` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `reason` | Text | MEDIUM | ✓ | ✓ | ✓ | Leave as-is — but document a coding-standard rule that Out-of-Service reasons must not contain personnel accusations or customer PII. Free-text discipline rather than masking. |
| `venue_session` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |

**Verdict:** No masking needed. Asset Status Log is intentionally a flat audit log. The protection model is "Operator cannot edit it" (already enforced), not "Operator cannot see it."

---

### 2. Cash Drop

Read access today: Operator RW, Manager R, Admin RWD.

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `operator` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. Operator-of-record is intentionally visible. |
| `shift_record` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `shift_date` | Date | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `shift_identifier` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `drop_type` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `drop_number` | Int | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `timestamp` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| **`declared_amount`** | Currency | **HIGH** | ✓ | ✓ | ✓ | **Mask in list view** for non-owner Operator records. Operator who entered the drop should see their own value; operators browsing other operators' drops should see `•••`. Recommend a v16 `mask: 1` flag combined with a `has_permission` hook that whitelists `doc.operator == frappe.session.user`. |
| `reconciled` | Check | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `reconciliation` | Link | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. Operator already has zero access to Cash Reconciliation rows (verified in permissions_matrix.md), so this link is a dead-end for them. |
| `pos_closing_entry` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |

**Verdict:** One field needs masking. `declared_amount` is the single case in this DocType where peer browsing leaks information (operator A learns operator B's till balance).

---

### 3. Cash Reconciliation

Read access today: Manager RWS, Admin RWDS. **Operator has no access at all.**

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `cash_drop` | Link | MEDIUM | — | ✓ | ✓ | Leave as-is |
| `shift_record` | Link | LOW | — | ✓ | ✓ | Leave as-is |
| `manager` | Link (User) | MEDIUM | — | ✓ | ✓ | Leave as-is |
| `timestamp` | Datetime | LOW | — | ✓ | ✓ | Leave as-is |
| **`actual_count`** | Currency | **CRITICAL** | — | ✓ | ✓ | Leave as-is at the DocType level (Operator cannot read). However, the **blind-entry invariant** (DEC-039) is enforced today by the JS form (the "reveal" section is hidden until submit). Recommend hardening with a server-side guard: `system_expected`, `operator_declared`, and `variance_amount` should be `permlevel: 1` and computed/written by a server hook only on submit. The form-level hide is a UX nicety; the real protection should be at field permlevel. |
| **`system_expected`** | Currency | **CRITICAL** | — | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**, granted only to Hamilton Admin (or to a dedicated "Hamilton Reconciliation Reviewer" permlevel-1 role). Today this field is read-only on the form and only revealed post-submit by JS. A bench shell or REST API caller can fetch it pre-submit. DEC-021 calls this out as "NEVER expose to operator-role users" — but the invariant should be defended structurally, not by JS. |
| **`operator_declared`** | Currency | **CRITICAL** | — | ✓ | ✓ | Same as `system_expected` — `permlevel: 1`. |
| **`variance_amount`** | Currency | **CRITICAL** | — | ✓ | ✓ | Same as `system_expected` — `permlevel: 1`. |
| `variance_flag` | Select | HIGH | — | ✓ | ✓ | Mask in detail view via `permlevel: 1`. The flag values include "Possible Theft or Error" — accusatory. Same permlevel rationale. |
| `notes` | Text | HIGH | — | ✓ | ✓ | Leave as-is. Manager+ only is correct. Encrypt-at-rest worth considering if reconciliation notes ever surface in DB dumps shared off-site (HR/legal sensitivity), but not a Phase 1 priority. |
| `resolved_by` | Link (User) | MEDIUM | — | ✓ | ✓ | Leave as-is |
| `resolution_status` | Select | MEDIUM | — | ✓ | ✓ | Leave as-is |

**Verdict:** Four fields need `permlevel: 1` to harden the blind-reveal invariant against API-level callers. The current JS-only protection is brittle — a `bench --site … console` user or a forged REST request could pull `system_expected` before the manager submits.

---

### 4. Comp Admission Log

Read access today: Operator RW, Manager R, Admin RWD.

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `venue_session` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `sales_invoice` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `admission_item` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| **`comp_value`** | Currency | **HIGH** | ✓ | ✓ | ✓ | **Mask in list and detail view via `permlevel: 1`** granted to Manager+. The existing `permissions_matrix.md` already flags this as Manager-only intent ("the comp's notional revenue cost"); today it is visible to Operator. This is an existing **GAP** — schema does not yet match the documented intent. |
| `operator` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is |
| `timestamp` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `reason_category` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `reason_note` | Text (max 500) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. Free-text but capped at 500 chars; documented mandatory-only-for-Other in DEC-016. Coding-standard rule applies (no PII in notes). |

**Verdict:** One field needs masking — `comp_value` is the exemplar case for "schema currently disagrees with documented intent." Fixing this should be the highest-priority follow-up because the gap is already on paper.

---

### 5. Hamilton Board Correction

This is a **child table** (`istable: 1`) embedded in Shift Record's `board_corrections` field. It has no permission rows of its own — access is governed entirely by the parent Shift Record. Operator can read all parent rows, therefore Operator can read all child rows.

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `venue_asset` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `old_status` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `new_status` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `reason` | Text | MEDIUM | ✓ | ✓ | ✓ | Leave as-is — same coding-standard rule as Asset Status Log (no personnel/customer details in free-text). |
| `operator` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is |
| `timestamp` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |

**Verdict:** No masking needed. Inherits parent's protection model. Audit-log style: visible-but-immutable to Operator.

---

### 6. Hamilton Settings (Single)

Read access today: Manager R, Admin RWC. **Operator has no access at all.**

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| **`float_amount`** | Currency | MEDIUM | — | ✓ | ✓ | Leave as-is. Manager+ only is correct. The amount is a venue-wide constant, not per-shift, and managers need to know it to reconcile. |
| `default_stay_duration_minutes` | Int | LOW | — | ✓ | ✓ | Leave as-is |
| **`printer_ip_address`** | Data | MEDIUM | — | ✓ | ✓ | **Encrypt at rest** is overkill, but worth considering as a future hardening if Hamilton Settings is ever exported as a fixture for support handoff. Today: leave as-is. Rationale: an internal IP address is mild infosec exposure if a fixture export ends up in a public bug report. |
| `printer_model` | Data | LOW | — | ✓ | ✓ | Leave as-is |
| `printer_label_template_name` | Data | LOW | — | ✓ | ✓ | Leave as-is |
| `grace_minutes` | Int | LOW | — | ✓ | ✓ | Leave as-is |
| `assignment_timeout_minutes` | Int | LOW | — | ✓ | ✓ | Leave as-is |
| `show_waitlist_tab` | Check | LOW | — | ✓ | ✓ | Leave as-is |
| `show_other_tab` | Check | LOW | — | ✓ | ✓ | Leave as-is |

**Verdict:** No masking needed today. Single DocType with no Operator access; row-level grid is sufficient. Watch `printer_ip_address` if fixture export practices change.

---

### 7. Shift Record

Read access today: Operator RW, Manager R, Admin RWD. **This DocType has the largest gap surface area.**

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `operator` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is |
| `shift_date` | Date | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `status` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `shift_start` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `shift_end` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| **`float_expected`** | Currency | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. The expected-float figure is theft-detection auxiliary data. Operator needs to know "what to count to" but does not need to see the figure pre-count if the workflow is blind. Lower priority than card variance below — defer to Phase 2 if it complicates shift-open UX. |
| **`float_actual`** | Currency | HIGH | ✓ | ✓ | ✓ | **Mask in list view** for non-owner records. Operator-of-record needs to see their own count; peers do not. |
| **`float_variance`** | Currency | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Variance is theft-signal data. Operators should not see variance on their own shift in real time — the workflow is "count, then manager investigates." |
| **`closing_float_actual`** | Currency | HIGH | ✓ | ✓ | ✓ | Same as `float_actual` — mask in list view for non-owner. |
| **`closing_float_variance`** | Currency | **CRITICAL** | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. DEC-050 closing-float variance is the strongest theft signal in Phase 1. Currently fully visible to the operator being audited. |
| `board_confirmed` | Check | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `board_corrections` | Table | (see Hamilton Board Correction) | ✓ | ✓ | ✓ | See child-table audit |
| `pos_profile` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `pos_opening_entry` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `pos_closing_entry` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| **`operator_declared_card_total`** | Currency | HIGH | ✓ | ✓ | ✓ | **Mask in list view** for non-owner records (same rationale as `float_actual`). Operator-of-record entered the value and needs to see it; peers don't. |
| **`system_expected_card_total`** | Currency | **CRITICAL** | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`** — granted only to Manager+. **This is the single most important gap in this audit.** DEC-038 + DEC-021 logic: card reconciliation is the same blind-count workflow as cash reconciliation. The operator reads the terminal batch report, enters their figure, and only after submission does the system-expected get revealed. Today this field is fully visible to Hamilton Operator pre-submit, defeating the blind-count invariant. The Cash Reconciliation DocType correctly hides `system_expected` from Operator (no row-level access at all); Shift Record makes the equivalent figure free-readable. |
| `reconciliation_status` | Select | MEDIUM | ✓ | ✓ | ✓ | Leave as-is |

**Verdict:** Six fields need protection. The `system_expected_card_total` gap is the highest-severity finding in the entire audit because it directly contradicts a documented invariant.

---

### 8. Venue Asset

Read access today: Operator RW, Manager RW, Admin RWD.

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `asset_code` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `asset_name` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `asset_category` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `asset_tier` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `status` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `current_session` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is — the session row's protection covers any PII reachable through the link. |
| `is_active` | Check | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `company` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `expected_stay_duration` | Int | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `display_order` | Int | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `hamilton_last_status_change` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `last_vacated_at` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `last_cleaned_at` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `reason` | Text | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. Out-of-Service reason — same coding-standard rule (no PII / no personnel accusations in free-text). |
| `version` | Int | LOW | (hidden) | (hidden) | (hidden) | Leave as-is. Already `hidden: 1`; serves as optimistic-locking counter. |

**Verdict:** No masking needed. Venue Asset is operational metadata only. PII risk is nil. `current_session` link is safe because session-row reads are governed by Venue Session's own perms.

---

### 9. Venue Session

Read access today: Operator RW, Manager RW, Admin RWD. **This DocType ships with PII fields for forward-compat (Philadelphia rollout) that are unprotected.**

| Field | Type | Tier | Op reads | Mgr reads | Adm reads | Recommendation |
|---|---|---|---|---|---|---|
| `session_number` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `venue_asset` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `sales_invoice` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `admission_item` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `status` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `assignment_status` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `session_start` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `session_end` | Datetime | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `operator_checkin` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is |
| `operator_vacate` | Link (User) | MEDIUM | ✓ | ✓ | ✓ | Leave as-is |
| `vacate_method` | Select | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `shift_record` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `customer` | Link | LOW | ✓ | ✓ | ✓ | Leave as-is — defaults to "Walk-in" at Hamilton; non-default values surface only at Philadelphia. |
| `pricing_rule_applied` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `under_25_applied` | Check | LOW | ✓ | ✓ | ✓ | Leave as-is |
| `comp_flag` | Check | LOW | ✓ | ✓ | ✓ | Leave as-is |
| **`identity_method`** | Data | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Forward-compat for Philadelphia identity verification (e.g., "ID Scan" vs "Member Card"). Method-type alone is meta-PII. |
| **`member_id`** | Link (Customer) | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. PII linkage. The Customer record may contain name/email/phone/membership history. |
| **`full_name`** | Data | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Direct PII identifier. Currently null at Hamilton, but the field exists and any data populated is freely readable. |
| **`date_of_birth`** | Date | **CRITICAL** | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Regulated PII (age verification, identity-theft surface). Particularly sensitive in a wellness-venue context. Currently null at Hamilton — but the schema risk is shipped to every venue. |
| `membership_status` | Data | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. Status string ("Active"/"Suspended"/etc.) is operationally needed at front desk. |
| **`block_status`** | Data | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Block reasons may be health- or behavior-related and constitute regulated information depending on jurisdiction. Front desk needs to know "blocked: yes/no"; the *reason* should be Manager+. Recommend splitting this into a boolean flag (Operator-readable) and a free-text reason field (Manager+ readable) when Philadelphia rolls out. |
| **`arrears_amount`** | Currency | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Arrears = amount owed, a credit-history-adjacent figure. Front desk needs to know "has arrears: yes/no"; the dollar figure should be Manager+. |
| `arrears_flag` | Check | MEDIUM | ✓ | ✓ | ✓ | Leave as-is. The flag itself is operationally needed at front desk. |
| `arrears_sku` | Data | LOW | ✓ | ✓ | ✓ | Leave as-is |
| **`scanner_data`** | Text | **CRITICAL** | ✓ | ✓ | ✓ | **Encrypt at rest** (app-level encrypt/decrypt — `is_password: 1` is a Data-only flag and would not work on a Text field, but the same threat model applies). Raw scan-blob may include MRZ data, ID document images, or barcode payloads with embedded PII. Should never be plaintext in DB dumps. Decrypt only at the verification step, never display in lists or default detail view. |
| **`eligibility_snapshot`** | Text | HIGH | ✓ | ✓ | ✓ | **Mask in detail view via `permlevel: 1`**. Snapshot of eligibility check at admission — may include health-adjacent data (medical clearance, age verification) depending on Philadelphia's eligibility rules. |

**Verdict:** Eight fields need protection. Hamilton has the field shapes today but no real data; Philadelphia rollout will populate them and the protection must land **before** that rollout, not after. Treat as a Phase 2 prerequisite, not a Phase 2 nice-to-have.

---

## Cross-cutting gaps

Pulling the per-DocType findings together, the audit surfaces five distinct gap classes:

### G1 — Blind-reveal invariants enforced by JS only (CRITICAL)

Two figures meet the same blind-count theft-detection definition as `Cash Reconciliation.system_expected` (DEC-021):

- `Cash Reconciliation.system_expected`, `operator_declared`, `variance_amount` — protected today by the JS form (reveal section hidden until submit). API-level callers bypass this.
- **`Shift Record.system_expected_card_total`** — protected by **nothing**. Operator can read pre-submit. **This is a documented invariant violation, not a hypothetical one.**

**Fix mechanism:** `permlevel: 1` on each field, paired with a permlevel-1 DocPerm row granted only to Hamilton Manager+ (or a dedicated "Hamilton Reconciliation Reviewer" permlevel-1 role to keep the regular Manager grid clean).

### G2 — Schema disagrees with documented intent (HIGH)

`permissions_matrix.md` lines 53–60 already state that `Comp Admission Log.value_at_door` (now `comp_value`) and the cash recon variance figures should be Manager+ only. Today, `comp_value` is freely readable by Hamilton Operator — the schema lags the doc. Closing this gap is the lowest-effort, highest-clarity fix because the design decision is already made.

**Fix mechanism:** `permlevel: 1` on `Comp Admission Log.comp_value`.

### G3 — Forward-compat PII shipped without protection (CRITICAL on rollout)

Eight Venue Session fields (`identity_method`, `member_id`, `full_name`, `date_of_birth`, `block_status`, `arrears_amount`, `scanner_data`, `eligibility_snapshot`) exist for Philadelphia but ship to all venues. Today at Hamilton they are null. On the day Philadelphia goes live, every Hamilton Operator inherits read access to PII they do not need.

**Fix mechanism:** Combination — `permlevel: 1` for the identifier fields (`full_name`, `date_of_birth`, `member_id`) and app-level encrypt-at-rest for `scanner_data`. Land this **before** Philadelphia, not after.

### G4 — Peer-browsing leakage on operator self-entered values (MEDIUM)

Currency fields where the operator who entered the value should see it but peers should not:

- `Cash Drop.declared_amount`
- `Shift Record.float_actual`, `closing_float_actual`, `operator_declared_card_total`

**Fix mechanism:** v16 `mask: 1` on the field combined with a `has_permission`-style hook that checks `doc.operator == frappe.session.user` (or equivalent) and returns the value only for the owner. Peers see a `•••` placeholder in lists and detail views.

### G5 — Free-text fields with no PII discipline rule (MEDIUM)

Six free-text fields could absorb personnel accusations or customer PII if Operators are not trained: `Asset Status Log.reason`, `Cash Reconciliation.notes`, `Hamilton Board Correction.reason`, `Comp Admission Log.reason_note`, `Venue Asset.reason`, `Cash Drop` (no Text field — N/A).

**Fix mechanism:** Documentation, not code. Add a coding-standards rule (or operator-handbook rule) that free-text reasons must not contain personnel names or customer PII. Optional: a `before_save` hook that scans for patterns matching User names and warns. Do NOT mask the field — the audit value depends on it being readable.

---

## Implementation order (priority queue for follow-up PRs)

If a follow-up PR (or sequence of PRs) implements these recommendations, suggest sequencing by severity × effort:

| # | Action | Severity | Est. effort | Why first/last |
|---|---|---|---|---|
| 1 | `permlevel: 1` on `Shift Record.system_expected_card_total` | CRITICAL (G1) | S | Smallest possible PR that closes a documented invariant violation. One field, one permlevel row, regression test. |
| 2 | `permlevel: 1` on `Cash Reconciliation.system_expected` + `operator_declared` + `variance_amount` + `variance_flag` | CRITICAL (G1) | S | Hardens existing JS-only protection. Same shape as #1. |
| 3 | `permlevel: 1` on `Comp Admission Log.comp_value` | HIGH (G2) | S | Schema-vs-doc parity fix. Already on paper. |
| 4 | Venue Session PII permlevel block — `full_name`, `date_of_birth`, `member_id`, `identity_method`, `block_status`, `arrears_amount`, `eligibility_snapshot` | CRITICAL on rollout (G3) | M | Block before Philadelphia rollout. Multiple fields, one permlevel row. |
| 5 | `Venue Session.scanner_data` encrypt-at-rest | CRITICAL on rollout (G3) | M-L | App-level encrypt/decrypt; needs a key-management decision. Schedule alongside #4 since both block Philadelphia. |
| 6 | `Shift Record` float-variance fields permlevel — `float_variance`, `closing_float_variance`, `float_expected` | HIGH (G1) | S | Same mechanism as #1; defer because the workflow integration is more sensitive (operator UX during shift open/close). |
| 7 | `mask: 1` on operator-self currency fields — `Cash Drop.declared_amount`, `Shift Record.float_actual`, `closing_float_actual`, `operator_declared_card_total` | MEDIUM (G4) | M | Requires `has_permission` ownership hook; not just a flag. Test against multi-operator browsing scenarios. |
| 8 | Coding-standard rule for free-text PII discipline | MEDIUM (G5) | S | Doc-only PR. Add to `coding_standards.md`. Optional `before_save` warning hook is a separate, larger PR. |

**Suggested PR cadence:** items #1–#3 in one bundled PR (smallest, all `permlevel: 1` mechanism, regression-test pattern is identical). Items #4–#5 as a Philadelphia-readiness bundle, sequenced before any Phila go-live milestone. Items #6–#7 as a Phase 1.5 hardening bundle. Item #8 is doc-only and can ship anytime.

---

## Mechanism reference

For implementers — the v16 / Frappe constructs referenced in this doc:

- **`permlevel: <int>`** on a field → field belongs to that permlevel; readable/writable only by roles with a DocPerm row granting that permlevel. Default permlevel is 0 (the row-level grid). A field at `permlevel: 1` requires a separate DocPerm row at level 1.
- **`mask: 1`** (Frappe v16) → list-view masking flag. Replaces value with placeholder in list views for users without explicit unmask grant. Does not protect against form-detail or API access; pair with `permlevel` for structural protection.
- **`is_password: 1`** → Data-field-only flag. Stores value encrypted at rest, never returned in JSON to the client. Not applicable to Currency, Date, Datetime, Int, Text. For Text fields requiring at-rest encryption, use app-level encrypt/decrypt in a `before_save` / `before_load` hook pair.
- **`has_permission(doc, ptype, user)` hook** (in `hooks.py`) → row-level filtering. Enforce ownership rules ("Operator sees only their own Cash Drops") here. Combine with `mask: 1` for field-level peer-browsing protection.
- **`hidden_depends_on` / `read_only_depends_on`** → conditional UI hide based on doc state. Cosmetic; bypasses at API. Use only for UX, never as a security control.

---

## See also

- `docs/permissions_matrix.md` — row-level role grid (Phase 1).
- `docs/decisions_log.md` — DEC-021 (blind reveal of system_expected), DEC-038 (card reconciliation workflow), DEC-039 (variance reveal-after-submit), DEC-041 (resolution status), DEC-050 (closing float variance).
- `hamilton_erp/test_security_audit.py::TestNoFrontDeskSelfEscalation` — regression coverage for role-grid escalation; field-level masking will need new regression tests in the same file when implemented.
- `docs/lessons_learned.md` LL-033 — audit summary and the "schema can lag documented intent" generalizable lesson.
