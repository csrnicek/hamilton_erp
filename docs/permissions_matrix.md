# Hamilton ERP — Permissions Matrix

**Generated from:** `hamilton_erp/hamilton_erp/doctype/*/*.json` (the `permissions` array on each DocType).
**Last updated:** 2026-04-29 (Task 25 permissions checklist item 6).

This file is the human-readable view of every Hamilton DocType's role-based access control. It is generated from the doctype JSON files; the source of truth is each DocType's own `permissions` array. The committed fixture set in `hamilton_erp/fixtures/role.json` declares the three Hamilton roles; per-doctype permission rows live with the doctype itself.

## Roles

| Role | Real-world equivalent |
|---|---|
| `Hamilton Operator` | Front Desk staff (the most numerous role) |
| `Hamilton Manager` | Floor Manager (escalation tier above Operator) |
| `Hamilton Admin` | Hamilton-specific super-user (the venue owner / domain operator) |
| `System Manager` | Frappe-level super-user (see "System Manager deployment checklist" — Task 25 item 2) |

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
- **Hamilton Board Correction** has no role permission rows. By Frappe convention, a DocType without explicit role perms is accessible only to System Manager — i.e., admin-only by absence. This is the correct default for a manual-correction audit DocType: nobody routinely creates these; only the System Manager role holder does, by hand.
- **Cash Reconciliation** does NOT grant Hamilton Operator any access. Front Desk staff cannot read end-of-shift reconciliations (which contain expected-vs-actual cash math). This is intentional — the operator who collected the cash is the same person whose math is being checked.

## System Manager deployment checklist (Task 25 item 2)

`System Manager` is the Frappe-level super-user. It can edit every DocType in the system, including `User`, `Role`, `DocPerm`, `Custom DocPerm`, `Has Role`, and `Role Profile`. Anyone with this role can grant or revoke any other role — including `System Manager` itself — on any user account. Treat it as the production root credential.

This file does **not** name the individuals who hold `System Manager`. Identities change (staff turnover, ownership change, vendor handoff); the deployment rule is what stays stable. Map the rule to people in `Hamilton Settings.system_manager_grant_log` (or in your tenant's equivalent runbook), not in this matrix.

### Who SHOULD hold `System Manager`

- **Exactly one human-owned account per venue tenant** — the role holder of record. This is the person accountable for role grants, password resets, and Frappe-Cloud-level operations on that site. Typical mapping: the venue owner or the venue's designated platform administrator.
- **Optionally: one break-glass account per tenant** — disabled by default, password rotated quarterly, enabled only during an incident with a paired audit log entry. Used when the primary account is locked out or compromised.

### Who must NOT hold `System Manager`

- Front Desk staff (`Hamilton Operator`).
- Floor Managers (`Hamilton Manager`).
- Vendor / contractor accounts beyond the duration of the engagement.
- Any service account or API integration. Service accounts use scoped API keys against narrower roles, never `System Manager`.

### Pre-deploy checklist

Run this before flipping the production URL on a new venue tenant, and re-verify quarterly:

1. **Inventory every account that holds `System Manager`.**
   ```bash
   bench --site <site> console
   >>> import frappe; frappe.get_all('Has Role',
   ...     filters={'role': 'System Manager', 'parenttype': 'User'},
   ...     fields=['parent'])
   ```
   Confirm the result list matches the documented role holders for that tenant. Anything unexpected is a finding.

2. **Confirm the structural Frappe default still holds.** No role other than `System Manager` may have `write/create/delete/submit/cancel/amend` on `User`, `Role`, `DocPerm`, `Custom DocPerm`, `Has Role`, or `Role Profile`. The regression test `TestSystemManagerGrantGuardrail` in `hamilton_erp/test_security_audit.py` enforces this on every CI run; running the test suite before deploy is the verification.

3. **Disable any break-glass account** that was enabled for prior incident work. Audit log entry must reference the closing ticket.

4. **Rotate the primary `System Manager` password and 2FA recovery codes** if the role holder has changed since the last deploy.

5. **Verify no service / API account holds `System Manager`.** API integrations use scoped roles (`Hamilton Operator`, `Hamilton Manager`, or a purpose-built role), not the platform super-user.

6. **Check `Custom DocPerm` for drift.** Per-tenant overlays can grant escalation perms that don't appear in the committed JSON. Run:
   ```bash
   bench --site <site> console
   >>> import frappe; frappe.get_all('Custom DocPerm',
   ...     filters={'parent': ['in', ['User','Role','DocPerm','Has Role','Role Profile','Custom DocPerm']]},
   ...     fields=['parent','role','write','create','delete','cancel','amend'])
   ```
   Any row whose role is not `System Manager` is a finding — fix it before deploy.

### Why this is documented as a checklist, not enforced in code

Steps 2 and 6 are enforced by `TestSystemManagerGrantGuardrail`. Steps 1, 3, 4, and 5 are *operational* invariants — they involve people, accounts, and out-of-band processes (password rotation, vendor offboarding) that the code can't see. The checklist exists so the operator running a deploy has a single canonical list, and so audits can attach to a stable artifact.

## Sensitive fields (Task 25 item 7)

The following fields will receive v16 `mask: 1` field-masking treatment in a separate PR (item 7), so non-Manager roles see masked placeholders:

- `Cash Drop.amount` — visible to Hamilton Operator (they entered it) but masked from any Operator looking at someone else's drop.
- `Cash Reconciliation.expected_cash`, `Cash Reconciliation.actual_cash`, `Cash Reconciliation.variance` — Hamilton Manager+ only.
- `Comp Admission Log.value_at_door` — Hamilton Manager+ only (the comp's notional revenue cost).

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
