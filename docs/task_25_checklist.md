# Task 25 Checklist

Source of truth for the Task 25 pre-go-live work. Each item is a discrete unit of work; the autonomous batch covers items 8, 11, 18, 19, 20, 21, 22, 23 (with 9, 10, 12 conditional on whether they are already complete).

1. Lock cancel/amend to manager+
2. Restrict System Manager to Chris only
3. Document Versioning + Audit Trail
4. Workflow approvals
5. No front-desk self-escalation
6. Role matrix in handoff doc
7. Field masking (Cash Drop, Reconciliation, Comp Admission Log, Venue Session PII per PIPEDA)
8. Fixtures to Git
9. Patches
10. GitHub Actions CI/CD
11. hooks.py audit
12. Clear error log
13. Audit claude_memory.md
14. decisions_log.md
15. lessons_learned.md
16. venue_rollout_playbook.md
17. Update CLAUDE.md
18. init.sh
19. AI bloat audit (report-first, approve, test, commit)
20. Document check_overtime_sessions stub (Phase 2 TODO)
21. Replace 36× frappe.flags.in_test → frappe.in_test
22. extend_doctype_class fix in hooks.py:69
23. Audit == "1" / == "0" string comparisons
