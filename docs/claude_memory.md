# Hamilton ERP — Deep Context

Extended memory for the claude.ai chat tab. Everything too detailed for the 30-slot memory limit lives here.

**Last updated:** 2026-04-12

---

## Project Overview

- Club Hamilton: anonymous walk-in venue, no membership, single operator 90% of time
- Stack: ERPNext POS (retail/payment/tax/promos) + custom Frappe app (asset board, session lifecycle, blind cash drops, manager reconciliation)
- Parent spec: V5.4. Key docs: hamilton_erp_build_specification.md, bathhouse_erpnext_v5_4_master_developer_specification.md
- Local path: ~/frappe-bench-hamilton. Dev site: hamilton-test.localhost. Test site: hamilton-unit-test.localhost
- Slash commands: /run-tests, /run-expert-tests, /deploy, /bug-triage, /feature, /task-start, /status, /coverage, /mutmut, /hypothesis

---

## Key Ops

Blind cash drops with label printer, three-way manager reconciliation, standalone card terminal (operator confirms), 25+ retail items in grid, physical keys, locked door with manual buzz-in, HST-inclusive (some items exempt), auto-applied promos, room tiers + single locker tier. Check-in: admission type -> retail -> pay -> assign asset from board.

---

## Test Suite

12 modules, 270 passing, 7 skipped (as of 2026-04-11). Modules: test_lifecycle, test_locks, test_venue_asset, test_additional_expert, test_checklist_complete, test_security_audit, test_environment_health + HTTP verb regression tests. ALWAYS run on hamilton-unit-test.localhost only -- never dev site. After every task: update .claude/commands/run-tests.md. When adding checks: add to docs/testing_checklist.md, convert to Python tests, update run-tests.md, commit all.

---

## Testing Rules

CRITICAL: Before writing any test, create a dedicated test site (appname-unit-test.localhost). Running tests on dev browser site causes wizard loops, 403 errors, session corruption -- cost a full day in Phase 1. At Phase 2 start: build test_environment_health.py covering setup_wizard gate, Administrator API access, role assignments, 59 assets exist, bench serve returning login not wizard, role x API permission matrix.

---

## 3-AI Review Checkpoints

- After Task 9: Done
- After Task 11: Done
- After Task 21: Full Asset Board UI complete (UPCOMING)
- After Task 25: Final Frappe Cloud deploy (UPCOMING)

Run: ChatGPT + Grok + fresh Claude tab

---

## Tooling Stack

1. **Remote Control** -- monitor/steer Claude Code from iPhone via Claude app Code tab
2. **Remote Tasks** -- overnight cloud runs, no Mac needed (Anthropic cloud, March 2026)
3. **GitHub Actions** -- auto-review commits via anthropics/claude-code-action@v1
4. **Claude Code Harness plugin** -- DO NOT install on Hamilton ERP. Conflicts with Taskmaster, CLAUDE.md, and Superpowers. Only for greenfield projects.

---

## Best Practices 1-15

1. Trunk-based dev -- commit small and often, every working function gets its own commit
2. GitHub Actions auto-test on every commit -- blocks bad merges, 30min setup
3. Cost visibility -- set Anthropic monthly spend cap + Claude Code Metrics Grafana dashboard
4. Enhance CLAUDE.md -- session startup rituals, hard stop rules (no commit if tests fail, no TODOs), Opus senior-Frappe-dev persona
5. Frappe Cloud rollback -- know backup restore button, 7-day history, 5min restore
6. Task 25 handoff doc is leverage for every future venue -- DC/Philly ~40% faster if thorough
7. One-page operator incident playbook before go-live -- login failures, board not loading, terminal down, full outage, escalation path to Chris
8. Mutation testing with mutmut at Task 25 -- /mutmut slash command exists
9. Property-based testing with Hypothesis at Task 21 -- /hypothesis slash command exists
10. DB migration safety net -- pre-deploy script: confirm backup <24hrs, test migration locally first
11. Structured logging -- every critical op writes machine-readable log (timestamp/operator/asset/outcome)
12. Contract testing vs ERPNext -- verify ERPNext APIs haven't changed after platform updates
13. Observability dashboard before go-live -- site uptime, sessions today, errors last hour
14. Semantic versioning from Task 25 -- git tag v1.0.0 && git push origin v1.0.0
15. Operator acceptance testing script -- simulate full shift before go-live

---

## DC / Multi-Venue Planning

- After Task 25: multi-venue refactor BEFORE DC build -- feature-flag platform, one app, per-site config
- DC adds: membership module, multi-tablet real-time sync (3 tablets), US tax config
- Philly: same setup as Hamilton (1 terminal) -- no race condition risk, but needs membership module
- Doc to create: docs/dc_sync_notes.md -- race condition research, lock system notes
- Membership module doc: docs/membership_module_notes.md -- covers Philly + DC

---

## Task 25 Checklist

- Run mutmut mutation testing
- Run Hypothesis property-based tests
- DB migration safety net script
- GitHub Actions CI wired up
- Set Anthropic monthly spend cap
- Verify Frappe Cloud backup restore
- Write operator incident playbook
- Semantic versioning: git tag v1.0.0
- Operator acceptance testing script
- Generate thorough technical handoff document
- Plan Phase 2 with new Taskmaster task list

---

## Optimization Audit (run at Task 25)

3 fixes only, one file at a time, full tests after each:

1. Delete utils.py -- entirely dead code
2. Add suppress_realtime param to mark_asset_clean -- kills wasted WebSocket msgs on bulk clean
3. Fold _set_vacated/_set_cleaned_timestamp into _set_asset_status -- eliminates 1 extra DB write

Leave all other design decisions alone -- they are correct trade-offs.
