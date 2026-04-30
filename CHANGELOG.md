# Changelog

All notable changes to Hamilton ERP since project inception.

Format follows [Keep a Changelog](https://keepachangelog.com/) with adaptations for the project's pre-1.0, single-developer, continuous-deploy state. Pre-1.0 means we don't bump versions on every PR — instead this file is organized chronologically by month, with each merged GitHub PR as a line item. The merged-PR title is the canonical change description; click through to the PR for the full body.

**Source of truth:** GitHub merged-PR list. This file is generated mechanically from `gh pr list --state merged`. Cross-reference `docs/decisions_log.md` for the design decisions referenced (DEC-NNN) and `docs/lessons_learned.md` for the post-incident learnings (LL-NNN) referenced in PR titles.

**What "merged" means here:** auto-squash-merged into `main` via the standard `gh pr merge --squash --delete-branch` workflow. Each merged PR is one squash commit on `main`.

---

## [Unreleased]

PRs open as of 2026-04-30 evening:

- **#51** — feat(asset-board): V9.1 Phase 2 retail cart → Sales Invoice (Canadian penny-elimination nickel rounding, 5 fresh-install gap fixes for CI parity)
- **#54** — test: regression-pin track_changes contract on 9 Hamilton DocTypes (auto-merge queued)
- **#55** — docs(research): remove false "adult" classification framing from PIPEDA doc (awaiting Chris review, no auto-merge)
- **#56** — test: pin fresh-install DB state with conformance test module (auto-merge queued)
- **#57** — docs: add operational runbook for incident response and routine ops (auto-merge queued)

---

## 2026-04 — Phase 1 implementation, V9 / V9.1 Asset Board, pre-Task-25 hardening

### April 30 (Wednesday) — Pre-Task-25 hardening

- **#53** — chore: purge no-op overtime scheduler stub + fix app_email placeholder
- **#52** — docs(research): PIPEDA Venue Session PII analysis with repo-state corrections
- **#49** — feat(asset-board): V9.1 Phase 2 retail cart UX (stub — Sales Invoice deferred)
- **#48** — refactor(tests): canonical `real_logs()` helper + migrate 5 ad-hoc sites
- **#47** — docs(lessons): six lessons from second autonomous run (2026-04-29 PM)
- **#46** — refactor: rename `test_override_doctype_class` → `test_extend_doctype_class` (Frappe v16 mixin pattern)
- **#45** — feat(task-25): permissions checklist — items 3, 4, 5, 6 (5/7 complete)
- **#44** — fix(asset-board): retail tab badge = in-stock count only (A29-2)
- **#43** — inbox: Frappe Claude Skill Package evaluation
- **#42** — feat(asset-board): V9.1 retail SKU foundation — Item Group tabs + retail tiles
- **#41** — fix(asset-board): V9 browser-test bugs + DEC-054 reversal
- **#40** — chore(taskmaster): flip Tasks 22, 23, 24 to done
- **#39** — docs(inbox): pre-handoff research — Prompts 1, 4, 5
- **#38** — docs(inbox): L029 audit verification — persistence works, PR #35 fixed the symptom
- **#37** — chore(audit): remove framework-testing + duplicate + dead-code per audit

### April 29 (Tuesday) — Second autonomous overnight run + V9 enrichment

- **#36** — inbox: V9 browser test session 2026-04-29
- **#35** — fix(api): include `reason` in `get_asset_board_data` field list
- **#34** — docs: AI bloat audit + test redundancy audit + LL-032 batching lesson
- **#33** — docs(inbox): visual regression research — defer to Phase 2 trigger
- **#32** — docs(lessons): restructure with LL-NNN IDs, severity, index, Top 10 Rules (PR B of 2)
- **#31** — docs(lessons): split narrative + risk content out of `lessons_learned.md` (PR A of 2)
- **#30** — docs(lessons): seven lessons from overnight autonomous run
- **#29** — chore(tests): replace stale `test_stress_simulation.py` with focused Phase 1 stress suite
- **#28** — docs(inbox): overnight autonomous run summary — PRs #24–#27
- **#27** — docs(reviews): pre-Task-25 3-AI deploy review prompts
- **#26** — test(phase1): H10+H11+H12 E2E — Tasks 22–24 consolidated
- **#25** — test(asset-board): pin V9 enrichment fields in schema snapshot
- **#24** — fix(asset-board): backend enrichment for V9 panels (E8/E11) — added `guest_name`, `oos_set_by` to API payload
- **#23** — docs(lessons): append 2026-04-28 V2 lessons (V9 conformance day)
- **#22** — fix(asset-board): V9 S3 button sizing + footer count cleanup (PR 5 of 5)

### April 28 (Monday) — V9 canonical mockup port (5-PR sequence) + governance lockdown

- **#21** — fix(asset-board): V9 vacate sub-buttons + tab structure + header (PR 4 of 5)
- **#20** — fix(asset-board): V9 OOS modal + Return modal + tile context (PR 3 of 5)
- **#19** — fix(asset-board): V9 3-state time model + tile rendering (PR 2 of 5)
- **#18** — fix(governance): close 5 demonstrated attacks + improve manifest UX
- **#17** — docs(lessons): record PR #16 governance findings deferred
- **#16** — docs: lock V9 mockup as canonical gospel reference (governance regime — fingerprint, presence guard)
- **#15** — fix(asset-board): tile expand overlay infrastructure (PR 1 of 5)
- **#14** — docs(decisions): document V9 removal of `data-asset-code` DOM attribute
- **#13** — docs(sync): `claude_memory.md` + `lessons_learned.md` after three-PR CI day
- **#12** — docs(claude.md): Frappe v16 conventions + PR completion template
- **#11** — docs: post-PR-9 inbox cleanup and Hamilton Launch Playbook
- **#9** — ci: vendor Frappe setup composite action to fix shared-workflow lookup

### April 27 (Sunday) — Production-practices audit

- **#10** — docs: comprehensive production-practices audit (lays groundwork for pre-Task-25 work)

### April 25 (Friday) — Asset Board V6 rebuild

- **#8** — feat(ui): Asset Board V6 rebuild — tabs, dark theme, tile expand (this is the foundation later refined into V9)

### April 16 (Wednesday) — Phase 1 Tasks 20 + 21

- **#4** — feat(task-21): bulk Mark Clean confirmation dialog (DEC-054)
- **#3** — feat(task-20): realtime listeners for cross-tab asset board sync

---

## Pre-PR-tracked work (April 8 – April 15)

GitHub PR-based change tracking started on 2026-04-16 with PR #3. Earlier work on Phase 0 (initial scaffold) and the first 19 tasks of Phase 1 was committed directly to `main` from a single-developer workflow without intermediate PRs. The decisions and lessons from that period are captured in:

- `docs/decisions_log.md` (DEC-001 through DEC-053 spans this window — Phase 0 + Phase 1 design decisions)
- `docs/lessons_learned.md` (LL-001 through LL-024 originate from this period)
- `docs/build_phases.md` (the original phase plan)
- `docs/superpowers/plans/2026-04-10-phase1-asset-board-and-session-lifecycle.md` (the 25-task implementation plan)

For a per-commit reconstruction of this period, run:

```bash
git log --reverse --oneline 92eeca6..origin/main -- '*.py' '*.json' '*.md' | head -100
```

(Replace `head -100` with a wider window for the full 350+ commit history.)

---

## How this changelog is maintained

**On every merged PR:** Add a line under the appropriate `## YYYY-MM` section (creating it if first PR of that month). Include the PR number, the merged-PR title verbatim, and a one-line gloss in parentheses if the title alone doesn't communicate the change.

**On every Unreleased PR opening:** Add a line under `[Unreleased]` while the PR is open. Move it to the dated section on merge.

**Never include in this file:**
- Per-commit detail (the PR is the unit; commit detail is in PR descriptions / `git log`)
- Internal-only refactor noise that isn't user-visible (use `git log` for that level)
- Speculative future work (use `docs/build_phases.md` or `docs/inbox.md`)

**Never delete from this file:** entries are append-only history. If a PR is reverted, add a new "Reverted: PR #N" entry under the appropriate date — don't remove the original.

**Mechanical regeneration:** if this file gets out of sync with the merged-PR list, regenerate the body from:

```bash
gh pr list --state merged --limit 200 --json number,title,mergedAt \
  -q '.[] | "\(.mergedAt[0:10])|\(.number)|\(.title)"' | sort -r
```

---

*Created 2026-04-30 as part of the pre-Task-25 handoff prep stack (overflow item from Stack #5). Source: GitHub merged-PR list at the time of generation.*
