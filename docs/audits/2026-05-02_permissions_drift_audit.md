# Permissions Drift Audit — `permissions_matrix.md` vs DocType JSON — 2026-05-02

**Scope:** verify each Hamilton-owned DocType's `permissions` array against the canonical matrix at `docs/permissions_matrix.md`. Report drift in either direction (matrix-says-X-but-code-says-Y, *or* code-has-row-not-in-matrix). Also verify the masked-fields section's claims against the actual `permlevel: 1` field declarations.

**Mindset:** the matrix is supposed to be the human-readable mirror of the JSON. Any drift means future maintainers reading the matrix will get the wrong picture of who has access — that's a security audit hazard, not a doc nit.

**Method:** ran the regenerator script the matrix itself documents (lines 84–100), augmented with a `permlevel` column, against the live JSON in `hamilton_erp/hamilton_erp/doctype/*/*.json`. Diffed the live output against the matrix's "Phase 1 permission grid" + "Sensitive fields" + "Out of scope today" sections. Looked at field-name spelling, perm-row count, perm-level treatment, and any role × DocType cells.

**Severity counts:** **0 BLOCKER · 3 HIGH · 1 MEDIUM · 1 LOW.**

> No security drift in either direction — i.e., **no actual access escalation gap exists**. The DocType JSON correctly enforces the security model the matrix describes. The drift is in the matrix's *documentation* of that model: stale field names, omitted permlevel rows, and out-of-date "pending PR" language for masking work that has already shipped. The risk is to *future* PRs that read the matrix as authoritative and miss the live state.

---

## HIGH

### H1 — "Sensitive fields (Task 25 item 7)" lists three fields by names that do not exist in the actual DocType JSON

**File:** `docs/permissions_matrix.md:55–61`

The matrix promises masking treatment for:

| Matrix says | Actual JSON fieldname | DocType |
|---|---|---|
| `Cash Drop.amount` | `declared_amount` | Cash Drop |
| `Cash Reconciliation.expected_cash` | `system_expected` | Cash Reconciliation |
| `Cash Reconciliation.actual_cash` | `actual_count` | Cash Reconciliation |
| `Cash Reconciliation.variance` | `variance_amount` | Cash Reconciliation |
| `Comp Admission Log.value_at_door` | `comp_value` | Comp Admission Log |

**Failure scenario.** A new contributor is told "lock down PII" and goes to apply masking. They search the JSON for the matrix-cited field names. They don't exist. They either give up, ask a question (best case), or invent a new field with the matrix-named identity (worst case — schema fork).

**Why it happened.** The matrix appears to have been written from an earlier draft of the DocType design, and the field names were renamed before the JSON shipped. The matrix was not updated to match. (Cross-reference: `Comp Admission Log.comp_value` was masked in PR #98; the matrix still calls it `value_at_door`.)

**Recommended fix.** Update `permissions_matrix.md:55–61` to use the actual JSON field names. A regenerator script that walks the JSON for `permlevel >= 1` fields and prints a sensitive-field table would prevent recurrence (mirror of the perm-grid script the matrix already includes at lines 84–100).

### H2 — "Sensitive fields" section says masking will be done "in a separate PR (item 7)" but masking has *already* shipped for two of the three named DocTypes

**File:** `docs/permissions_matrix.md:55–58`

> "The following fields will receive v16 `mask: 1` field-masking treatment in a separate PR (item 7), so non-Manager roles see masked placeholders…"

**Live state:**

- **Comp Admission Log.comp_value** — `permlevel: 1` (PR #98 merged 2026-04-29).
- **Shift Record.system_expected_card_total** — `permlevel: 1` (some prior PR; date not bisected here).
- **Cash Drop.declared_amount** — no `permlevel` set in the JSON.
- **Cash Reconciliation.system_expected / actual_count / variance_amount** — no `permlevel` set in the JSON.

So the masking is *done* for 2 fields, *not done* for 4 fields, and the matrix says *all* are pending.

**Failure scenario.** A reviewer trusts the matrix and assumes Comp Admission Log's `comp_value` is unprotected. They write an audit ticket. They begin "fixing" something that's already fixed. Or worse — they write a fix in the wrong place and silently overwrite the existing `permlevel: 1`.

**Recommended fix.** Split the section into "Masked (already shipped)" and "Pending masking" subsections. Reference the merge PRs for the shipped items. Update the language to be present-tense for the shipped ones.

### H3 — The "Phase 1 permission grid" table omits the permlevel-1 read rows that exist in the live DocType JSON for Comp Admission Log and Shift Record

**File:** `docs/permissions_matrix.md:18–37` (the grid table).

Live JSON has these permlevel-1 rows that the matrix's table does not show:

| DocType | Role | permlevel | Read |
|---|---|---|---|
| Comp Admission Log | Hamilton Manager | 1 | ✓ |
| Comp Admission Log | Hamilton Admin | 1 | ✓ |
| Shift Record | Hamilton Manager | 1 | ✓ |
| Shift Record | Hamilton Admin | 1 | ✓ |

**Failure scenario.** Someone reads the matrix to answer "does Hamilton Manager see Comp Admission Log's `comp_value` field?" and concludes: yes, Manager has read on Comp Admission Log (matrix line 21), so Manager sees everything. **Wrong.** Manager has permlevel-0 read; permlevel-1 read is the *separate* row not shown in the grid. Without that second row, Manager would NOT see `comp_value` because the field is at permlevel 1.

The actual security model is correct in the JSON; the matrix's table format simply doesn't accommodate permlevel rows.

**Recommended fix.** Add a "permlevel" column to the grid (or a separate "Permlevel-1 read access" subsection). Either the regenerator script needs an extra column, or the matrix needs a second table specifically for permlevel rows. Worth doing alongside H2.

---

## MEDIUM

### M1 — `Shift Record.system_expected_card_total` masking is not mentioned in the matrix at all

**Files:** `docs/permissions_matrix.md:55–63` (Sensitive fields section); `hamilton_erp/hamilton_erp/doctype/shift_record/shift_record.json` (the masked field).

The matrix's "Sensitive fields" section lists Cash Drop / Cash Reconciliation / Comp Admission Log fields. It does not mention `Shift Record.system_expected_card_total`, which carries `permlevel: 1` in the JSON.

**Failure scenario.** A contributor asks "what's masked on Shift Record?". They check the matrix. They see `Shift Record` in the perm grid but no entry in the Sensitive Fields section. They conclude nothing is masked. Wrong — a card-total field is masked.

**Why it happened.** The Shift Record masking probably landed in a different PR / sprint than the Task 25 item 7 work, and the matrix wasn't updated.

**Recommended fix.** Add `Shift Record.system_expected_card_total` to the masked-fields list, with the rationale (operator-side card totals reveal the manager's expected reconciliation amount before the blind count — defeats the blind-count-then-reveal flow per DEC-039).

---

## LOW

### L1 — Hamilton Settings perm-row order is inverted between matrix and JSON

**Files:** `docs/permissions_matrix.md:31–32` (matrix lists Manager first, then Admin); `hamilton_erp/hamilton_erp/doctype/hamilton_settings/hamilton_settings.json` (JSON lists Admin first).

Cosmetic — both ends agree on the *contents* of the perm grid for Hamilton Settings (Admin: rwc; Manager: r). Just the row ordering is different. Not a security gap; called out only because future regenerator-script runs will produce a diff that confuses reviewers expecting a stable order.

**Recommended fix.** Decide on a canonical order (alphabetical-by-role works) and have the regenerator emit it consistently.

---

## Categories with no findings

- **No role escalation paths.** Every DocType's perm grid in the JSON matches what the matrix says about the access level (modulo the doc-side gaps in H1–H3, which describe the *matrix's* gaps not the JSON's). Hamilton Operator's perms are correctly limited; Hamilton Manager's perms are correctly limited; Hamilton Admin's perms are appropriately broad.
- **No DocType missing from the matrix.** All 9 Hamilton-owned DocTypes appear in the matrix's grid.
- **No DocType in the matrix that doesn't exist in the JSON.** Every row in the matrix corresponds to a real DocType.
- **Hamilton Board Correction's "no role perms" pattern is correctly documented** (matrix line 27 + Notable Patterns section). Frappe's default-deny means System Manager only — which is the correct model for an admin-only correction-of-record audit DocType.
- **Submit / Cancel / Amend gates are correct.** Cash Reconciliation is the only Phase 1 DocType with `submit`; matrix and JSON agree. No DocType has `cancel` or `amend` in Phase 1; matrix and JSON agree.

---

## Cross-references

- **Audit 5** (PII masking coverage, in progress) will deepen the field-by-field masking review. This audit only checks DocType-level perm rows + the Sensitive Fields documentation; that one will check field declarations against the PIPEDA research doc.
- **PR #100** (mask Venue Session PII fields, awaiting merge) will introduce 7 new permlevel-1 fields on Venue Session. When it lands, the matrix will need an update — H1, H2, H3 fixes should accommodate Venue Session in the same pass.
- **PR #98** (Comp Admission Log.comp_value masking) is the prior shipped item that the matrix's H2 stale "pending PR" language refers to. Cross-link in the matrix's "See also" section.

---

## What I did NOT audit

- **Frappe-level permission rules** beyond the DocType perms array (e.g., `permission_query_conditions`, `has_permission` overrides, `Custom DocPerm`). Out of scope; would need a separate audit.
- **Field-level read access at runtime** — the JSON declarations are correct but I did not verify that Frappe's runtime correctly enforces permlevel-1 (i.e., manager actually sees `comp_value` and operator actually doesn't). The integration tests in `test_security_audit.py` cover this; cross-reference rather than re-audit.
- **Hamilton Settings field-level permlevel.** The schema doesn't have any permlevel-1 fields on Hamilton Settings; not in scope here.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
