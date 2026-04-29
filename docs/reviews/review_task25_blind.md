# Phase 1 Pre-Deploy Review — Blind (no implementation context)

**Audience:** ChatGPT (frontier model), Grok (frontier model), and a fresh Claude (new tab, no project memory).

**Goal:** Identify risks in deploying a Frappe v16 / ERPNext v16 app to Frappe Cloud for a small live business (men's bathhouse — single venue, one operator most shifts) before the first paying-customer cutover. The reviewer has **no access** to the codebase or design docs — they evaluate only the stated facts and decisions below.

**Format you should respond in:**
1. **Top 5 risks ranked** — one sentence each, severity tag `[Blocker / High / Medium / Low]`.
2. **For each Blocker / High risk:** one-paragraph remediation plan that does not depend on rewriting Phase 1.
3. **Three concrete questions** the team should answer before flipping the live URL.

---

## What the team is about to do

A team is about to flip a custom Frappe/ERPNext v16 app live on Frappe Cloud (a managed Frappe hosting platform). The app manages 59 physical assets — 26 hotel-style rooms and 33 lockers — at a single brick-and-mortar venue. State machine: `Available → Occupied → Dirty → Available`, plus `Out of Service` as a side state.

It will replace a hand-written paper sign-in book that has been the source of truth for ~25 years.

## Operator profile

- One operator on duty most shifts, two on busy nights.
- Operators are venue staff, not technical users — the UI is a tile-based "Asset Board" page (single web page) on a tablet.
- Customers are anonymous walk-ins. No membership system. No POS integration in Phase 1.
- Cash is handled at a separate point of sale that this app does NOT yet integrate with — operators record asset state changes only.

## What is in production-ready code (not just specced)

- 17 test modules, ~340 server-side tests, all green on a dedicated test site.
- 18 dedicated end-to-end tests covering the three "hard" lifecycle scenarios (full turnover, OOS-from-any-state, illegal transition rejection).
- Three-layer locking on every state transition: Redis NX+TTL → MariaDB `SELECT FOR UPDATE` → optimistic version field. Lock body does **zero** I/O — realtime publishes happen `after_commit` only.
- Role-based access control: only users with the `Hamilton` role can hit the Asset Board API or see the workspace.
- Property-based tests (Hypothesis) on the session-number sequence and the state machine transitions.
- A schema-snapshot test that pins the API response shape — any field added or removed without an explicit allowlist update fails CI.

## What is **not** in this deploy

- POS / pricing / refunds / cash drops / shift reconciliation — **all Phase 2+**.
- No automated rollback. Frappe Cloud snapshot + revert is the rollback mechanism.
- No application performance monitoring (APM) — only Frappe's built-in error log + Sentry-equivalent on Frappe Cloud.
- No load testing has been run against the production environment specifically (staging-only). Concurrency is bounded by the venue having ≤2 operators.
- No external auth/SSO — accounts created by hand on the live site.

## What the team has explicitly decided

- **Locking key is asset-only**, not asset+operation: `hamilton:asset_lock:{asset_name}`. Rationale: an asset can only be in one transition at a time anyway, and per-operation keys leaked stale locks under crash conditions.
- **Audit log is short-circuited under `frappe.in_test = True`** to keep test isolation cheap. Production has it always enabled.
- **No `frappe.db.commit()` inside controllers** — let Frappe own the transaction boundary.
- **`@frappe.whitelist(methods=["GET"])` is the default** for any read API. Mutations are POST. Verb is pinned in tests.
- **First go-live is a single venue.** Multi-venue rollout is Phase 4.

## What the team is most worried about

1. The team has never deployed this app live before. The CI environment is Linux + Python 3.14 + MariaDB 12.2 + Redis. Frappe Cloud is the same stack — but every "first deploy" reveals environment differences.
2. The audit log behavior in production has not been observed under sustained load. The test guard makes the production path lower-coverage than ideal.
3. The owner is a beginner-level developer. The on-call rotation is "one person who reads the inbox in the morning."
4. The asset count is small (59) but the venue runs 24/7 and a wedged tile (stuck Occupied) blocks revenue immediately — there is no manual fallback.

---

## What you are reviewing

Given the constraints above, the team's **Top 5 risks ranked**, **remediation paragraphs**, and **three questions to answer before the cutover**.

Do not propose rewriting Phase 1. Do not ask for code. Do not ask for the test files.

## Why this prompt is "blind"

A reviewer without implementation context catches assumption errors that an in-the-codebase reviewer is too anchored to see. Pair this with the context-aware review (`review_task25_context.md`) — both reviewers must agree on the cutover plan before deploy.
