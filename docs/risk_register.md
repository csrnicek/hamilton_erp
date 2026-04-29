# Risk Register — Hamilton ERP

Known risks deliberately not addressed in current code. Each entry is something an adversarial reviewer flagged that we triaged as "real but not worth hard-enforcing today." The register exists so future hardening sessions can pick these up if they prove to be real problems in production.

This file is **not** a lessons-learned log. The lessons file (`docs/lessons_learned.md`) captures what we learned by hitting a problem. This file captures problems we know exist but have chosen not to fix yet, with the reasoning so the next session can re-evaluate.

---

## R-001 — Same-PR coupling attack on canonical mockup governance

- **Source:** Adversarial review of PR #16 (canonical mockup governance regime).
- **Description:** A PR that changes both `docs/design/V9_CANONICAL_MOCKUP.html` and `docs/design/canonical_mockup_manifest.json` (with a matching new SHA-256 hash) but does NOT update `docs/decisions_log.md` will pass all CI tests. The fingerprint integrity check verifies the manifest matches the file but doesn't verify that the change has been documented as an amendment.
- **Mitigation in place:** Code review (human + claude-review) should catch unexplained body changes. The CI `Enforce decisions_log update for manifest changes` step requires a `decisions_log.md` change in any PR that touches the manifest, which closes most of the attack surface.
- **Why deferred:** Hard programmatic enforcement (e.g. requiring a specific section ID in `decisions_log.md`) would generate false positives on cosmetic manifest fixes (e.g. adding a comment field).
- **Severity:** Low — requires intentional malicious-or-careless cooperation between two files.

## R-002 — Governance test body integrity

- **Source:** Adversarial review of PR #16.
- **Description:** `hamilton_erp/test_governance_test_presence.py` checks that the canonical mockup governance test method NAMES exist via AST traversal, but it does not fingerprint method BODIES. A future session could replace a governance test body with `pass` while keeping the name, and the presence guard would still pass.
- **Mitigation in place:** Code review. The presence guard plus the AST assertion-presence check (verifies each method has at least one `assert*` call) catches the most obvious neutering pattern.
- **Why deferred:** Hard enforcement (test fingerprinting against a known-good hash, recomputed on intentional changes) is overkill for a docs-file governance regime. The cost of maintaining the fingerprint exceeds the cost of catching this in code review.
- **Severity:** Low — same threat model as R-001.

## R-003 — M2 data-dependency rule gap (mockup vs production data)

- **Source:** Adversarial review of PR #16, surfaced again during V9 conformance work.
- **Description:** `CLAUDE.md` says "port the mockup verbatim" when implementing asset board UI. But some mockup features need backend data that doesn't exist in production yet (e.g. the V9 panels expected `guest_name` and `oos_set_by` fields that didn't exist on the API until PR #24). When this happens, sessions either (a) build a "graceful degradation" placeholder that drifts from the mockup or (b) silently skip the feature.
- **Mitigation in place:** PR #24 added the missing fields. Future similar gaps should be handled the same way: extend the API, then port the mockup feature against the new payload.
- **Why deferred:** Generalizing this into an explicit rule in `CLAUDE.md` was deferred until we'd seen a few more cases. PR #24 + PR #25 + lessons_learned LL-N+1 batched-lookup entry give us a reusable pattern.
- **Severity:** Medium — most likely to surface as a launch-week bug if we don't notice the gap.

## R-004 — Bench worktree isolation does not work

- **Source:** Discovered during PR #16 destructive probing.
- **Description:** Frappe bench symlinks `apps/hamilton_erp` to `~/hamilton_erp` regardless of git worktree location. Destructive probes run in a temporary worktree (`/tmp/hamilton_pr16_probe`) operate against the main working tree, not the worktree's checkout. A Claude Code crash mid-probe would leave the main repo in a corrupt state.
- **Mitigation in place:** Documented as a Lesson in `docs/lessons_learned.md` ("Bench symlink defeats worktree isolation"). For destructive testing we use in-place backup/restore in the main repo with a strict STOP-ON-DIRTY rule.
- **Why deferred:** Setting up a separate bench install for destructive probing is the right long-term solution but adds bench-management overhead. The in-place backup pattern works for low-frequency probing.
- **Severity:** Medium for solo work; would need to be addressed before any second developer joins.

## R-005 — No CODEOWNERS / dual approval for governance files

- **Source:** Adversarial review of PR #16.
- **Description:** Anyone with merge rights on the repo can change governance artifacts (`docs/design/V9_CANONICAL_MOCKUP.html`, `docs/design/canonical_mockup_manifest.json`, the governance test files). Branch protection requires CI to pass but does not require human review from a designated owner.
- **Mitigation in place:** Solo-developer phase — Chris is the only person with merge rights, so de facto dual approval doesn't apply.
- **Why deferred:** Real regulated-industry hardening would add `CODEOWNERS` for `docs/design/` and require dual approval. Out of scope for solo-developer phase. Re-evaluate when a second engineer joins.
- **Severity:** Low (solo phase) → Medium (multi-developer).

---

## Maintenance

**When to add:** After any adversarial review or post-mortem that surfaces a real-but-not-fixing-now finding.

**When to remove:** When the risk is mitigated by new code, or when re-evaluation determines the risk is no longer relevant (e.g. the feature it concerns has been removed).

**When to escalate:** If a risk's severity changes, or if production conditions make a deferred risk now actionable.

**Review cadence:** Re-read at every Phase boundary (Phase 1 → Phase 2, multi-venue rollout, etc.) and at every 3-AI checkpoint.

---

*Created 2026-04-29 from PR #16 deferred findings previously living in `docs/lessons_learned.md`.*
