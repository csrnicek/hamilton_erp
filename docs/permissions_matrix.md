# Hamilton ERP — Permissions Matrix

**Generated from:** `hamilton_erp/hamilton_erp/doctype/*/*.json` (the `permissions` array on each DocType).
**Last updated:** 2026-04-30 (Task 25 permissions checklist item 6 + PIPEDA Venue Session PII cross-link added in PR #52).

This file is the human-readable view of every Hamilton DocType's role-based access control. It is generated from the doctype JSON files; the source of truth is each DocType's own `permissions` array. The committed fixture set in `hamilton_erp/fixtures/role.json` declares the three Hamilton roles; per-doctype permission rows live with the doctype itself.

## Roles

| Role | Real-world equivalent |
|---|---|
| `Hamilton Operator` | Front Desk staff (the most numerous role) |
| `Hamilton Manager` | Floor Manager (escalation tier above Operator) |
| `Hamilton Admin` | Hamilton-specific super-user (Chris) |
| `System Manager` | Frappe-level super-user (restricted to Chris only — Task 25 item 2) |

## Phase 1 permission grid

| DocType | Role | Read | Write | Create | Delete | Submit | Cancel | Amend |
|---|---|---|---|---|---|---|---|---|
| Asset Status Log | Hamilton Operator | ✓ |  |  |  |  |  |  |
| Asset Status Log | Hamilton Manager | ✓ |  |  |  |  |  |  |
| Asset Status Log | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |
| Cash Drop | Hamilton Operator | ✓ | ✓ | ✓ |  |  |  |  |
| Cash Drop | Hamilton Manager | ✓ |  |  |  |  |  |  |
| Cash Drop | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |
| Cash Reconciliation | Hamilton Manager | ✓ | ✓ | ✓ |  | ✓ |  |  |
| Cash Reconciliation | Hamilton Admin | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |
| Comp Admission Log | Hamilton Operator | ✓ | ✓ | ✓ |  |  |  |  |
| Comp Admission Log | Hamilton Manager | ✓ |  |  |  |  |  |  |
| Comp Admission Log | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |
| Hamilton Board Correction | _(no role perms — admin-only by absence)_ | — | — | — | — | — | — | — |
| Hamilton Settings | Hamilton Manager | ✓ |  |  |  |  |  |  |
| Hamilton Settings | Hamilton Admin | ✓ | ✓ | ✓ |  |  |  |  |
| Shift Record | Hamilton Operator | ✓ | ✓ | ✓ |  |  |  |  |
| Shift Record | Hamilton Manager | ✓ |  |  |  |  |  |  |
| Shift Record | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |
| Venue Asset | Hamilton Operator | ✓ | ✓ | ✓ |  |  |  |  |
| Venue Asset | Hamilton Manager | ✓ | ✓ |  |  |  |  |  |
| Venue Asset | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |
| Venue Session | Hamilton Operator | ✓ | ✓ | ✓ |  |  |  |  |
| Venue Session | Hamilton Manager | ✓ | ✓ |  |  |  |  |  |
| Venue Session | Hamilton Admin | ✓ | ✓ | ✓ | ✓ |  |  |  |

## Notable patterns

- **Asset Status Log** is read-only for non-admin roles. The audit trail must not be editable by the operators it audits.
- **Cash Reconciliation** has `submit` permission for Manager + Admin, the only Phase 1 DocType with `submit`. End-of-shift reconciliations are the one workflow that follows the Frappe submit/cancel/amend lifecycle in Phase 1.
- **No role has `cancel` or `amend` flags in Phase 1.** Task 25 item 1 ("Cancel/amend locked to Floor Manager+ only") is currently moot because no Phase 1 DocType is cancellable. When Phase 2 makes Venue Session or Cash Drop submittable, the cancel/amend flags must be granted to Hamilton Manager+ only — see the regression test in `test_security_audit.py::TestNoFrontDeskSelfEscalation`.
- **Hamilton Board Correction** has no role permission rows. By Frappe convention, a DocType without explicit role perms is accessible only to System Manager — i.e., admin-only by absence. This is the correct default for a manual-correction audit DocType: nobody routinely creates these; only Chris does, by hand. Per **DEC-066** (decisions_log.md, 2026-05-03), this DocType is also the corrective surface for `Asset Status Log` and `Comp Admission Log` rows — when T1-2 strips `delete` from Hamilton Admin on those audit logs, Hamilton Board Correction is the sanctioned path for typo / mis-attribution correction. Original audit rows stay pristine; correction is its own audit-logged record. The endpoint is `hamilton_erp.api.submit_admin_correction` (whitelisted POST) — gated to Hamilton Admin / System Manager. For Cash Drop targets, the endpoint sets `frappe.flags.allow_cash_drop_correction` to bypass T0-4's `_validate_immutable_after_first_save` / `_validate_immutable_after_reconciliation` guards.
- **Cash Reconciliation** does NOT grant Hamilton Operator any access. Front Desk staff cannot read end-of-shift reconciliations (which contain expected-vs-actual cash math). This is intentional — the operator who collected the cash is the same person whose math is being checked.

## Sensitive fields (Task 25 item 7)

The following fields will receive v16 `mask: 1` field-masking treatment in a separate PR (item 7), so non-Manager roles see masked placeholders:

- `Cash Drop.amount` — visible to Hamilton Operator (they entered it) but masked from any Operator looking at someone else's drop.
- `Cash Reconciliation.expected_cash`, `Cash Reconciliation.actual_cash`, `Cash Reconciliation.variance` — Hamilton Manager+ only.
- `Comp Admission Log.value_at_door` — Hamilton Manager+ only (the comp's notional revenue cost).

### Out of scope today — Venue Session PII

Venue Session has eight forward-compat PII fields (`full_name`, `date_of_birth`, `member_id`, `identity_method`, `block_status`, `arrears_amount`, `scanner_data`, `eligibility_snapshot`) plus the `customer` Link gateway. They are null on Hamilton today (anonymous walk-in) but will populate at Philadelphia / DC / Dallas rollout, and on Hamilton if membership ever launches. When that happens, this section MUST extend to cover them BEFORE any PII actually lands — `mask: 1` for the masked fields and `permlevel: 1` (full blocking) for `scanner_data`, plus encryption-at-rest for `scanner_data`.

PIPEDA legal analysis and per-field justified-purpose / retention rules: `docs/research/pipeda_venue_session_pii.md`. See DEC-021 for the underlying field-masking decision.

## Maintenance

When a DocType's `permissions` array changes, regenerate this matrix:

```bash
python3 -c "
import json, os
DOCTYPES = sorted(d for d in os.listdir('hamilton_erp/hamilton_erp/doctype') if os.path.isfile(f'hamilton_erp/hamilton_erp/doctype/{d}/{d}.json'))
FLAGS = ['read','write','create','delete','submit','cancel','amend']
print('| DocType | Role | ' + ' | '.join(f.title() for f in FLAGS) + ' |')
print('|---|---|' + '|'.join(['---']*len(FLAGS)) + '|')
for d in DOCTYPES:
    with open(f'hamilton_erp/hamilton_erp/doctype/{d}/{d}.json') as fh: data = json.load(fh)
    label = data.get('name', d)
    perms = data.get('permissions', [])
    if not perms:
        print(f'| {label} | _(no role perms)_ | ' + ' | '.join(['—']*len(FLAGS)) + ' |')
        continue
    for p in perms:
        cells = ['✓' if p.get(fl) else '' for fl in FLAGS]
        print(f'| {label} | {p.get(\"role\",\"\")} | ' + ' | '.join(cells) + ' |')
"
```

Paste the output into the "Phase 1 permission grid" table above. Then update the "Notable patterns" section if any role × DocType cell that previously had `submit/cancel/amend` no longer does (or vice versa).

## See also

- `hamilton_erp/fixtures/role.json` — Hamilton role definitions (committed fixtures)
- `hamilton_erp/test_security_audit.py::TestNoFrontDeskSelfEscalation` — regression test that Hamilton Operator cannot mutate User / Role / DocPerm
- `docs/decisions_log.md` — locked design decisions including audit trail
- `docs/lessons_learned.md` LL-018 — fixtures-must-be-exported invariant for multi-venue rollout
