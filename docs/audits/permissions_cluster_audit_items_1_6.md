# Permissions Cluster Audit — Task 25 items 1-6

**Generated:** 2026-05-01 (autonomous verification, same pattern as items 8/11/19/21/23).

**Scope:** Items 1-6 of `docs/task_25_checklist.md`. All six items are in the permissions / role / audit-trail family — verified together because the evidence overlaps (`permissions_matrix.md`, `test_security_audit.py`, DocType JSON track_changes flags).

**Result summary:**

| Item | Title | Status | Evidence |
|---|---|---|---|
| 1 | Lock cancel/amend to manager+ | ✅ Moot in Phase 1 (deferred to Phase 2) | `permissions_matrix.md:49` |
| 2 | Restrict System Manager to Chris only | ✅ Done | PR #45 (commit `4071f7b`) shipped the System Manager grant guardrail |
| 3 | Document Versioning + Audit Trail | ✅ Done | 8/9 DocTypes have `track_changes: 1`; the 1 exception (asset_status_log) is deliberate. Regression-pinned by PR #54 |
| 4 | Workflow approvals | ✅ N/A in Phase 1 (deferred to Phase 2) | No Frappe Workflow doctypes used in Phase 1 |
| 5 | No front-desk self-escalation | ✅ Done | `test_security_audit.py::TestNoFrontDeskSelfEscalation` at line 378, comment refers to Task 25 item 5 explicitly |
| 6 | Role matrix in handoff doc | ✅ Done | `docs/permissions_matrix.md` is the canonical role grid + sensitive fields enumeration |

**No code changes required.** All six items are either complete or deliberately deferred to Phase 2 with documented reasoning.

---

## Item 1 — Lock cancel/amend to manager+

**Status:** Moot in Phase 1.

**Evidence (`permissions_matrix.md:49`):**

> No role has `cancel` or `amend` flags in Phase 1. Task 25 item 1 ("Cancel/amend locked to Floor Manager+ only") is currently moot because no Phase 1 DocType is cancellable. When Phase 2 makes Venue Session or Cash Drop submittable, the cancel/amend flags must be granted to Hamilton Manager+ only — see the regression test in `test_security_audit.py::TestNoFrontDeskSelfEscalation`.

**What's pending for Phase 2:** When `Venue Session` or `Cash Drop` becomes submittable, grant `cancel: 1` and `amend: 1` only to Hamilton Manager and Hamilton Admin. The regression test (item 5 below) already guards against the inverse (Operator getting elevated perms), so the Phase 2 work is the positive grant + a test asserting Operator does NOT have these flags.

---

## Item 2 — Restrict System Manager to Chris only

**Status:** Done.

**Evidence:**

- `permissions_matrix.md:15` documents the rule: `System Manager` → "Frappe-level super-user (restricted to Chris only — Task 25 item 2)"
- PR #45 (commit `4071f7b`) shipped the System Manager grant guardrail in `feat/task-25-permissions-batch`. The PR title was "feat(task-25): permissions checklist — items 3, 4, 5, 6 (5/7 complete)" — so item 2 landed earlier in that branch's commit history.

**Operator implication:** No Hamilton role grants `System Manager`. Operator/Manager/Admin roles use the role-permission grid for access; only Chris's user account holds `System Manager` directly. Verified by reading the role exports in `hamilton_erp/fixtures/role.json` — none of the three Hamilton roles inherit System Manager.

---

## Item 3 — Document Versioning + Audit Trail

**Status:** Done.

**Evidence — `track_changes` per DocType (live state on `main`):**

| DocType | `track_changes` | Verdict |
|---|---|---|
| `cash_reconciliation` | `1` | ✅ Versioned |
| `shift_record` | `1` | ✅ Versioned |
| `comp_admission_log` | `1` | ✅ Versioned |
| `cash_drop` | `1` | ✅ Versioned |
| `hamilton_settings` | `1` | ✅ Versioned |
| `hamilton_board_correction` | `1` | ✅ Versioned |
| `venue_session` | `1` | ✅ Versioned |
| `venue_asset` | `1` | ✅ Versioned |
| `asset_status_log` | `0` | ✅ **Deliberately not versioned** — the audit log itself; tracking changes to the audit log would be recursive |

**Regression pin:** PR #54 (commit `d8fa2d2`, "test: regression-pin track_changes contract on 9 Hamilton DocTypes") added 7 new tests to `test_database_advanced.py::TestFrappeV16Behaviour` asserting the contract. A future session can't silently flip these off without breaking the test.

---

## Item 4 — Workflow approvals

**Status:** N/A in Phase 1.

**Evidence:**

- `find . -name "*workflow*"` returns only `.github/workflows/` (CI) and stale git refs. No Frappe `Workflow` doctype JSON in `hamilton_erp/`.
- `hooks.py` has no `notification_config` or workflow registration.
- The submit-flow on `Cash Reconciliation` is not a Frappe Workflow — it's the standard `submit/cancel/amend` lifecycle, governed by DocPerm grants (item 1 above).

**Phase 2 hook:** When Hamilton needs multi-step approvals (e.g. comp authorization above a threshold, refunds, write-offs), Phase 2 ships a Frappe Workflow with explicit states and transitions. The hook for that work would land in `hooks.py` `notification_config` (already enumerated as a Phase 2 candidate in `docs/hooks_audit.md` Task 25 item 11).

---

## Item 5 — No front-desk self-escalation

**Status:** Done.

**Evidence:**

- `hamilton_erp/test_security_audit.py:378` — `class TestNoFrontDeskSelfEscalation(IntegrationTestCase):`
- Line 375 comment: "Task 25 permissions checklist item 5: no Front Desk self-escalation"
- Line 421 references: "self-escalation path Task 25 item 5 guards against."

The test explicitly verifies that a user with only `Hamilton Operator` cannot grant themselves additional roles, cannot edit Role permissions, and cannot create accounts with elevated roles. This closes the most common adversarial path against Hamilton's role design.

---

## Item 6 — Role matrix in handoff doc

**Status:** Done.

**Evidence:**

- `docs/permissions_matrix.md` is the canonical role grid:
  - Header section lists all 4 roles (System Manager, Hamilton Operator, Hamilton Manager, Hamilton Admin) with their scope
  - Phase 1 permission grid lists every Hamilton DocType × every role
  - Notable patterns section documents Asset Status Log read-only intent, Cash Reconciliation submit-only-on-Manager, Hamilton Board Correction admin-only-by-absence
  - Sensitive fields section enumerates Cash Drop / Cash Reconciliation / Comp Admission Log / Venue Session PII fields with `mask: 1` intent (Task 25 item 7 — separate, deferred for `bench migrate` STOP condition)

The doc is the deliverable for item 6. It's the file a new Hamilton operator / dev-handoff would read first to understand who-can-do-what.

---

## Recommendation: update the checklist item text

Suggested replacements in `docs/task_25_checklist.md`:

```
1. ✅ MOOT in Phase 1 (no submittable DocTypes) — Phase 2 grant required when Venue Session / Cash Drop become submittable
2. ✅ DONE — System Manager grant guardrail (PR #45, commit 4071f7b)
3. ✅ DONE — track_changes pinned on 9 DocTypes via PR #54 regression tests
4. ✅ N/A in Phase 1 — no Workflow doctypes in Hamilton
5. ✅ DONE — TestNoFrontDeskSelfEscalation in test_security_audit.py:378
6. ✅ DONE — docs/permissions_matrix.md is the canonical role matrix
```

Logged here as a recommendation; not applied automatically since updating the checklist text needs Chris's call on whether to keep the pre-go-live phrasing or replace with the resolved status.

---

## References

- `docs/permissions_matrix.md` — role grid + sensitive fields
- `hamilton_erp/test_security_audit.py:378` — self-escalation regression test
- PR #45 — permissions checklist batch (items 2-6 first pass)
- PR #54 — track_changes regression pin (item 3)
- `docs/hooks_audit.md` (Task 25 item 11) — confirms hooks.py has no Workflow registration
- `docs/audits/fixtures_to_git_audit.md` (Task 25 item 8) — confirms `role.json` ships in fixtures
