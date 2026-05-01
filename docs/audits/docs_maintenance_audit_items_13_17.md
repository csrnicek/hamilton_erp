# Docs Maintenance Audit — Task 25 items 13-17

**Generated:** 2026-05-01 (autonomous verification, same pattern as items 8/11/19/21/23 and 1-6).

**Scope:** Items 13-17 of `docs/task_25_checklist.md`. All five are "this canonical doc is up-to-date" checks. Verified together because the freshness signal is the same (header dates, recent commits, content-vs-current-state spot checks).

**Result summary:**

| Item | File | Status | Notes |
|---|---|---|---|
| 13 | `docs/claude_memory.md` | ✅ Current | 844 lines; last refreshed 2026-04-30 (PR #70 freshness sweep + PR #61 third-run checkpoint) |
| 14 | `docs/decisions_log.md` | ✅ Current | 543 lines; "Last updated: 2026-04-30 (DEC-061 + retail cart + scheduler stub purge)" |
| 15 | `docs/lessons_learned.md` | ✅ Current | 781 lines, 35 LL entries (LL-001 → LL-037); active recent additions (LL-033 in PR #50, LL-034/035/036/037 in PR #51) |
| 16 | `docs/venue_rollout_playbook.md` | ⚠️ Partially stale | 156 lines; last substantive touch was inbox merge commit `6825520`. Content is structurally sound but missing the v16 hard-pinning rule (added to CLAUDE.md 2026-05-01) and the new Hamilton accounting conventions (PR #51 audit). Recommend a small refresh PR — out of scope for this verification audit. |
| 17 | `CLAUDE.md` | ✅ Current and active | 445 lines; touched by PR #51 (Hamilton accounting conventions) and the in-flight PR #76 (plugin freshness rule). User added Frappe v16 production version pinning section 2026-05-01. |

**No code changes required.** Item 16 has a follow-up recommendation (refresh playbook with v16 pinning + accounting conventions) but the playbook structure itself is sound.

---

## Item 13 — claude_memory.md

**Status:** Current.

**Evidence:**
- 844 lines (verified `wc -l`)
- Header line 7: "**Last updated:** 2026-04-30 (third autonomous overnight run — see latest Checkpoint section)"
- Last commits touching the file:
  - `9e148fd` — PR #70 docs sweep (date refresh + outdated claims fix)
  - `3785c66` — PR #61 third autonomous run end-of-session checkpoint
  - `50ce7a0` — PR #16 V9 mockup canonicalization

The third-run checkpoint is the most recent substantive addition; the freshness sweep mechanically updated dates on 2026-04-30. No staleness flags.

---

## Item 14 — decisions_log.md

**Status:** Current.

**Evidence:**
- 543 lines
- Header line 5: "**Last updated:** 2026-04-30 (DEC-061 + Amendment 2026-04-30 retail cart + Amendment 2026-04-30 scheduler stub purge)"
- Last commits:
  - `3c87fb3` — PR #51 (added DEC-061 + Amendment for retail cart)
  - `9e148fd` — PR #70 (freshness sweep)
  - `b71fc83` — PR #53 (Amendment for scheduler stub purge)

The decisions log is one of the most actively maintained docs in the repo. Recent decisions cover retail cart accounting (DEC-061), scheduler stub purge (Amendment), and the pre-Task-25 hardening cycle. No backlog of unrecorded decisions surfaced during today's session.

---

## Item 15 — lessons_learned.md

**Status:** Current.

**Evidence:**
- 781 lines
- 35 LL entries verified by `grep -c "^### LL-"` (LL-001 through LL-037 with two intentional gaps: LL-032 was renumbered as a Top-10 rule, and the original LL-024 was inadvertently re-used as LL-N+1 in PR #21 then resolved to LL-024 batched lookups)
- Recent additions:
  - LL-033 (PR #50, "Schema can lag documented intent")
  - LL-034 (PR #51, "Concurrent Claude Code agents race on git checkout")
  - LL-035 (PR #51, "Whitelisted endpoints need adversarial tests in the first PR")
  - LL-036 (PR #51, "Paper receipt as occupancy token")
  - LL-037 (PR #51, "Frappe v16 site_config 60s cache")

**Top 10 rules section** at the head of the file is up to date and reflects the current operating discipline.

---

## Item 16 — venue_rollout_playbook.md

**Status:** ⚠️ Partially stale (recommend follow-up refresh).

**Evidence:**
- 156 lines
- Last substantive commit: `6825520` "docs: merge inbox into structured docs — fraud research, multi-venue arch, production hardening" (predates the recent v16 work)
- Content **is** structurally sound — Phase A site creation, Phase B install, Phase C smoke-test sequencing is correct
- Content **is missing** the following 2026-04-30 → 2026-05-01 additions:
  - The v16 production version pinning rule (added to CLAUDE.md 2026-05-01 by Chris): rollout playbook should reference "pin frappe + erpnext to a tagged v16 minor release, NOT to `version-16` HEAD"
  - The Hamilton accounting conventions section from PR #51 (CAD nickel rounding, Cost Center on Round Off, POS Profile write-off requirements)
  - The init.sh bootstrap script reference (PR #59) — the playbook should point operators at `scripts/init.sh` for fresh-bench setup

**Recommendation:** open a small follow-up PR `docs(rollout): refresh playbook with 2026-05-01 deltas` adding three short subsections. **Out of scope for this audit** which is verification-only; logging here so the next session picks it up. Could be a Phase 2 starter task.

---

## Item 17 — CLAUDE.md

**Status:** Current and actively maintained.

**Evidence:**
- 445 lines
- Recent commits:
  - PR #51 — added "Hamilton accounting / multi-venue conventions (PR #51 audit)" section
  - PR #42 — added retail SKU foundation references
  - 2026-05-01 — Chris added Frappe v16 production version pinning section (lines 67-91, manual edit)
  - In-flight: PR #76 (plugin freshness rule under "Plugin Data Freshness — Single Source of Truth"), queued for auto-merge
- All section headings reviewed; no stale references to V8 / V9 (current is V10 mockup / V9.1 retail amendment per the gospel block); no outdated test counts
- "About Chris" section accurate; "Technical environment" section pins Python 3.14 / Node 24 (current correct versions per CI workflow)

**Cross-check vs. PR #76 (in flight):** the plugin freshness rule going into PR #76 doesn't conflict with CLAUDE.md content elsewhere; it slots in cleanly between Drift Prevention and V10 Canonical Mockup sections.

---

## Recommendation: update the checklist item text

Suggested replacements in `docs/task_25_checklist.md`:

```
13. ✅ DONE 2026-05-01 — claude_memory.md current (last refreshed PR #70)
14. ✅ DONE 2026-05-01 — decisions_log.md current (DEC-061 + recent amendments)
15. ✅ DONE 2026-05-01 — lessons_learned.md current (LL-001 → LL-037)
16. ⚠️  PARTIALLY STALE — venue_rollout_playbook.md needs refresh: v16 pinning + accounting + init.sh references
17. ✅ DONE 2026-05-01 — CLAUDE.md current (v16 pinning, accounting conventions, plugin freshness rule)
```

Logged as recommendations; not applied to the checklist file in this PR (separate update).

---

## Follow-up issue for item 16

A small refresh PR would close item 16 fully. Suggested scope:

1. Add a one-paragraph subsection under "Phase A — Frappe Cloud Site Creation" pointing operators at the v16 pinning rule (link to CLAUDE.md "Production version pinning" section) so they don't auto-pull `version-16` HEAD.
2. Add a one-paragraph subsection under "Phase B — Install" referencing `scripts/init.sh` for local-bench bootstrap and the Hamilton accounting conventions (CAD nickel rounding etc.) that the seed installs automatically.
3. Refresh the header date.

Blast radius: docs-only, ~30 lines added. CI risk: zero. Reviewer time: ~2 minutes.

---

## References

- `docs/claude_memory.md`, `docs/decisions_log.md`, `docs/lessons_learned.md`, `docs/venue_rollout_playbook.md`, `CLAUDE.md` (the audited files)
- PR #51 — added Hamilton accounting conventions to CLAUDE.md
- PR #70 — freshness sweep (mechanical date refreshes)
- PR #59 — `scripts/init.sh` (referenced as missing from venue_rollout_playbook)
- PR #76 (in-flight) — adds plugin freshness rule to CLAUDE.md
- This audit's siblings: `docs/audits/permissions_cluster_audit_items_1_6.md`, `docs/audits/hooks_audit.md`, `docs/audits/fixtures_to_git_audit.md`, etc.
