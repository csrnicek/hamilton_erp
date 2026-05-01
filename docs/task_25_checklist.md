# Task 25 Checklist

**Source of truth** for the Task 25 pre-go-live work. Each item is a discrete unit of work; the autonomous batch covers items 8, 11, 18, 19, 20, 21, 22, 23 (with 9, 10, 12 conditional on whether they are already complete).

**Last synced:** 2026-05-01 (Taskmaster auto-sync workflow added — see below).

## Status markers

Each item below is tagged with a machine-parseable status marker. The status markers are also mirrored in `.taskmaster/tasks/tasks.json` (Task 25 subtasks) by the `sync-taskmaster` GitHub Actions workflow on every push to main that touches this file. **This file is canonical**; Taskmaster derives from it.

| Marker | Taskmaster status |
|---|---|
| `✅ DONE` | `done` |
| `🔒 BLOCKED` | `blocked` |
| `🔍 REVIEW` | `review` |
| `⏸ DEFERRED` | `deferred` |
| (no marker) | `pending` |

To update the status of an item: edit the line below to add or change the marker. The auto-sync workflow handles the Taskmaster JSON update.

## Items

1. ✅ DONE — Lock cancel/amend to manager+ (moot in Phase 1, no submittable doctypes; Phase 2 hook documented in `docs/audits/permissions_cluster_audit_items_1_6.md`)
2. ✅ DONE — Restrict System Manager to Chris only (PR #45)
3. ✅ DONE — Document Versioning + Audit Trail (8/9 DocTypes `track_changes:1`, regression-pinned by PR #54)
4. ✅ DONE — Workflow approvals (N/A in Phase 1, no Frappe Workflow doctypes; Phase 2 hook documented)
5. ✅ DONE — No front-desk self-escalation (`test_security_audit.py::TestNoFrontDeskSelfEscalation`)
6. ✅ DONE — Role matrix in handoff doc (`docs/permissions_matrix.md`)
7. 🔒 BLOCKED — Field masking (Cash Drop, Reconciliation, Comp Admission Log, Venue Session PII per PIPEDA) — bench migrate STOP condition; held for Chris-supervised session
8. ✅ DONE — Fixtures to Git (PR #81 audit: 14/14 tracked)
9. ✅ DONE — Patches (`patches.txt` has 6 patches in `[post_model_sync]`)
10. ✅ DONE — GitHub Actions CI/CD (3 workflows live: claude-review, lint, tests)
11. ✅ DONE — hooks.py audit (PR #77 audit: PASS, no code changes required)
12. ✅ DONE — Clear error log (operational process documented in `docs/RUNBOOK.md`)
13. ✅ DONE — Audit `docs/claude_memory.md` (current per PR #84 audit; refreshed PR #70)
14. ✅ DONE — `docs/decisions_log.md` (current per PR #84 audit; DEC-061 most recent)
15. ✅ DONE — `docs/lessons_learned.md` (current per PR #84 audit; LL-001 → LL-037)
16. ✅ DONE — `docs/venue_rollout_playbook.md` (PR #85 added v16 pinning + init.sh + Hamilton accounting conventions references)
17. ✅ DONE — `CLAUDE.md` (current per PR #84 audit; v16 pinning + accounting + plugin freshness rule)
18. ✅ DONE — `scripts/init.sh` (PR #59, idempotent fresh-bench bootstrap)
19. 🔍 REVIEW — AI bloat audit (PR #78 — report only; awaiting Chris review before cleanup PRs ship)
20. ✅ DONE — Document `check_overtime_sessions` stub (PR #53 purged the stub; `hooks.py:85` documents former Phase 1 stub)
21. ✅ DONE — Replace 36× `frappe.flags.in_test` → `frappe.in_test` (PR #79 audit: premise was wrong; codebase already correct)
22. ✅ DONE — `extend_doctype_class` fix in `hooks.py:69` (already correct on main; memory observation 1063 was stale)
23. ✅ DONE — Audit `== "1"` / `== "0"` string comparisons (PR #80 audit: zero violations found)
