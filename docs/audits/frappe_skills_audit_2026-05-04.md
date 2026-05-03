# Frappe Skills Audit — 2026-05-04

**Scope.** Targeted anti-pattern audit using the Frappe Claude Skill Package
(installed 2026-05-03 per DEC-072). Cross-referenced against `decisions_log.md`
and `lessons_learned.md` — only findings not already documented are listed below.

**Codebase head.** `d2087dfaa31d3815e0f353640bd7fb4be40e2dd0`

**Method.** Static read of `hamilton_erp/api.py`, `hamilton_erp/lifecycle.py`,
`hamilton_erp/locks.py`, `hamilton_erp/hooks.py`, `hamilton_erp/setup/install.py`,
the nine operational DocType JSONs under `hamilton_erp/hamilton_erp/doctype/`,
and a sampling of patches and scripts. No runtime, no test execution, no DB
inspection.

## Summary

| Category | New findings |
|---|---|
| `db.set_value` misuse | 1 |
| `@frappe.whitelist` patterns | 4 |
| `hooks.py` configuration | 2 |
| DocType JSON conventions | 3 |
| Scheduler jobs | 0 |
| Permission bypass paths | 1 |

---

## Category 1 — `db.set_value` misuse

T3-1 / PR #175 already swept the operational controllers. The remaining
call sites fall into three buckets: `setup/install.py` (acceptable — install
hooks predate any track_changes audit window and run before the per-DocType
hook chain matters), `patches/` (acceptable — one-shot data migration), and
the `db_set("owner", ...)` post-insert in `submit_retail_sale`. Only the
last is worth a fresh look.

### F1.1 — `db_set("owner", real_user, update_modified=False)` after `Sales Invoice` submit
- **Location.** `hamilton_erp/api.py:706` (inside `submit_retail_sale`).
- **Pattern.** Anti-pattern #7 from `frappe-core-database` says `db_set` is
  acceptable for "hidden fields, counters, timestamps, performance-critical
  background jobs" but warns it bypasses `track_changes`. Sales Invoice has
  `track_changes` ON in ERPNext core, so this owner-rewrite produces zero
  rows in `tabVersion` for the ownership change. Anyone auditing "who
  recorded this sale" must read the ad-hoc `remarks` line, not the audit log.
- **Impact.** The audit-trail story for the ownership rewrite lives in a
  free-text `remarks` field. Easy to miss; impossible to query reliably
  ("show all SIs whose owner was rewritten by the cart"). `track_changes`
  would have given that for free.
- **Recommendation.** Either (a) accept and add a comment that "we deliberately
  skip the version row because the cart's audit trail is the SI itself plus
  the `remarks` footer," or (b) call `frappe.get_doc("Sales Invoice",
  si.name).save()` after the owner flip so the version row lands. Option (a)
  is probably correct (post-submit Sales Invoice writes are touchy in v16),
  but the trade-off is currently undocumented.
- **Why this is new.** DEC-072 references T3-1 swapping `set_value` for the
  Document API on Cash Drop. It does NOT discuss the deliberate `db_set` on
  the Sales Invoice owner field — that survived T3-1 because it's a post-
  submit ownership rewrite where `.save()` would re-trigger heavy ERPNext
  validation. Worth documenting either as a DEC carve-out or with an
  inline comment.

---

## Category 2 — `@frappe.whitelist` patterns

8 endpoints audited in `hamilton_erp/api.py`. Methods declarations and role
gates are well-handled across the board. Specific gaps:

### F2.1 — No rate limiting on any whitelisted endpoint
- **Location.** All 8 endpoints in `hamilton_erp/api.py` (lines 48, 259,
  317, 327, 337, 347, 357, 435).
- **Pattern.** `frappe-impl-whitelisted` SKILL.md recommends `@rate_limit`
  (or similar) on POST endpoints that mutate state, especially money / stock
  endpoints. None of Hamilton's endpoints declare rate limits.
- **Impact.** A compromised Operator session could fire `submit_retail_sale`,
  `start_walk_in_session`, `vacate_asset`, etc. as fast as the network allows.
  The three-layer lock (DEC-019) prevents asset-state corruption, but it
  does not prevent rapid-fire stock depletion via duplicate cart submits or
  log-flooding via repeated OOS toggles.
- **Recommendation.** Add `frappe.rate_limiter.rate_limit` or `@frappe.whitelist(rate_limit=...)` to the four state-mutating endpoints
  (`submit_retail_sale`, `start_walk_in_session`, `vacate_asset`, `set_asset_oos`).
  A modest cap (e.g. 30/min per user) would not impede a real operator and
  would catch a runaway client / abuse.
- **Why this is new.** No DEC or LL discusses rate limiting. LL-035 is about
  adversarial tests on money-touching endpoints (a different concern: test
  coverage, not request throttling).

### F2.2 — Return shape inconsistency across the 5 single-asset action endpoints
- **Location.** `hamilton_erp/api.py:325-380` — `start_walk_in_session`
  returns `{"session": session_name}`; `vacate_asset`, `clean_asset`,
  `set_asset_oos`, `return_asset_from_oos` all return `{"status": "ok"}`.
- **Pattern.** `frappe-impl-whitelisted` SKILL.md recommends a consistent
  envelope across an API surface so clients can branch on a single key.
  Hamilton's surface mixes `{"session": ...}`, `{"status": "ok"}`, and
  `{"status": "phase_1_disabled", ...}` (`assign_asset_to_session`).
- **Impact.** Client code in `asset_board.js` must special-case each
  endpoint. Idempotency wrappers (DEC-067 / T0-1) eventually need a
  uniform return envelope to record/replay; today they would have to
  serialize five different shapes.
- **Recommendation.** Settle on one envelope, e.g.
  `{"status": "ok", "session": ...}`. Cheap to standardize; pays off when
  T0-1 idempotency expands beyond Cash Drop.
- **Why this is new.** DEC-067 / LL-039 (idempotency) describes the
  contract for one specific endpoint family. Cross-endpoint shape
  consistency is not addressed anywhere.

### F2.3 — `assign_asset_to_session` is whitelisted but Phase-1 disabled, with no permission verb gate beyond `Venue Asset/write`
- **Location.** `hamilton_erp/api.py:259` (`assign_asset_to_session`).
- **Pattern.** Endpoint is reachable, returns a soft-disable message, and
  logs caller. Skill `frappe-impl-whitelisted` warns against shipping
  "wired-but-disabled" surfaces because they advertise a public attack
  contract that the implementation does not yet defend.
- **Impact.** Today, low-risk (returns a logged no-op). When Phase 2 lands,
  the role-gate model is `Venue Asset/write` — Hamilton Operator has that
  perm, so any operator could call this for any asset/SI pair. The actual
  authorization (operator owns the SI, asset is Available, etc.) is
  business-logic the disabled body never executed.
- **Recommendation.** When un-disabling for Phase 2: add a check that the
  caller is the SI's `owner` (or holds Hamilton Manager+) before invoking
  `start_session_for_asset`. Track in a Phase-2 checklist or DEC.
- **Why this is new.** No DEC has flagged this. The endpoint comment
  documents the Phase-1 no-op behavior but not the Phase-2 authorization
  gap.

### F2.4 — `get_asset_board_data` accepts no caller-scoped filter (returns the full venue)
- **Location.** `hamilton_erp/api.py:48` (`get_asset_board_data`).
- **Pattern.** Skill `frappe-impl-whitelisted` notes that GET endpoints
  returning lists should respect `User Permissions` or accept a tenancy
  filter. This endpoint reads `Venue Asset` with `frappe.has_permission(...read, throw=True)` then `frappe.get_all` — fine for a single-venue site,
  but Hamilton ERP is being rolled out across 6 venues (per CLAUDE.md).
- **Impact.** When venue rollout starts, this endpoint will leak every
  venue's asset list to every authenticated operator unless multi-tenancy
  is added at the route level (per-site bench, or company filter, or User
  Permission on `Venue Asset.company`). Today not exploitable because
  every site is a single venue, but it's a latent multi-tenancy gap.
- **Recommendation.** Add `filters={"company": frappe.defaults.get_user_default("Company"), ...}` or document that per-venue isolation is solved
  at the bench-site level, not the application level. Either is fine; the
  current code states neither.
- **Why this is new.** Multi-venue rollout is on the roadmap (CLAUDE.md
  reference) but no DEC documents the API-layer expectation. DEC-062/063/064
  cover merchant-classification, not asset-board tenancy.

---

## Category 3 — `hooks.py` configuration

`hooks.py` is short and clean. No event-name typos, no DocType drift on
`doc_events`, `extend_doctype_class` path verified to exist (`overrides/sales_invoice.py`). Two configuration-shape findings:

### F3.1 — `app_include_css` ships across the entire Desk; no scope guard
- **Location.** `hamilton_erp/hooks.py:18-21`.
- **Pattern.** Skill `frappe-syntax-hooks` notes that `app_include_css`
  loads the CSS for every Desk page, every user. The comment in `hooks.py`
  says the file is "scoped to .hamilton-asset-board / .hamilton-loading
  selectors so it does not bleed into other Frappe pages." That is true at
  the CSS-selector level but does not prevent the *download* on every page.
- **Impact.** Marginal — the CSS file is small. The skill flags this as a
  bundle-size hygiene anti-pattern, not a functional bug. With Phase 2
  client scripts the pattern compounds (each new page-specific bundle on
  every Desk hit).
- **Recommendation.** Move to `page_js` / `page_css` (page-scoped) or use
  `doctype_js` for DocType-specific assets. For the Asset Board Page itself,
  the JS already lives next to the Page record — the CSS could too.
- **Why this is new.** `hooks_audit.md` does not discuss bundle scoping.
  No DEC/LL covers it.

### F3.2 — No `boot_session` / `extend_bootinfo` hook to surface Hamilton Settings to the client
- **Location.** `hamilton_erp/hooks.py` (absent).
- **Pattern.** Skill `frappe-syntax-hooks` and `frappe-impl-hooks` describe
  `extend_bootinfo` as the canonical place to publish per-user / per-app
  config to the client without a round-trip. Hamilton's `_get_hamilton_settings`
  is fetched per request via `frappe.get_cached_doc("Hamilton Settings")`.
- **Impact.** Functional today (the cached_doc path is fast), but every
  Asset Board load includes a Hamilton Settings read in the response shape.
  An `extend_bootinfo` would let the client read settings off
  `frappe.boot.hamilton_settings` once at session start.
- **Recommendation.** Optional polish, not a defect. Worth flagging for
  Phase 2 when the Asset Board adds more per-session config (multi-tenancy,
  feature flags, role-aware UI).
- **Why this is new.** Not in any DEC/LL.

---

## Category 4 — DocType JSON conventions

9 operational DocTypes audited. `track_changes` is correctly set on 8 of 9
(the 9th, `Asset Status Log`, IS the audit log — correctly off, per
`lessons_learned.md` LL on audit coverage). `permlevel` use is appropriate
on `Comp Admission Log.comp_value` and `Shift Record.system_expected_card_total`. Three findings:

### F4.1 — Several Link fields in operational DocTypes lack `search_index`
- **Location.** Multiple DocTypes:
  - `Venue Asset.current_session` (Link → Venue Session)
  - `Venue Asset.company` (Link → Company)
  - `Venue Session.sales_invoice` (Link → Sales Invoice)
  - `Venue Session.admission_item`, `operator_checkin`, `operator_vacate`,
    `customer`, `member_id`, `shift_record`
  - `Cash Drop.operator`, `reconciliation`, `pos_closing_entry`
  - `Cash Reconciliation.cash_drop`, `shift_record`, `manager`, `resolved_by`
  - `Comp Admission Log.venue_session`, `sales_invoice`, `admission_item`,
    `operator`
  - `Asset Status Log.operator`
  - `Hamilton Board Correction.venue_asset`, `operator`
- **Pattern.** Skill `frappe-syntax-doctypes` recommends `search_index: 1`
  on Link fields used in filter / lookup queries. Frappe creates an index
  on `parent` and `name` automatically; FK columns are not indexed by
  default. List view filters and ORM `filters={"foo": "..."}` against
  these columns will table-scan.
- **Impact.** At Hamilton's volume (single venue, sub-1k assets, sub-100k
  sessions / year) this is not a perf problem. At rollout scale (6
  venues × multi-year history) the missing indices on `Venue Session.sales_invoice`,
  `Cash Drop.operator`, `Cash Reconciliation.cash_drop`, and the Comp Admission
  Log links will start to show up in slow-query logs.
- **Recommendation.** Add `search_index: 1` on the Link fields that appear
  in filter UIs and reports. The high-value targets are: `Cash Drop.operator`,
  `Cash Reconciliation.cash_drop`, `Cash Reconciliation.shift_record`,
  `Comp Admission Log.venue_session`, `Comp Admission Log.operator`,
  `Venue Session.sales_invoice`. Each costs one column-index on a small table.
- **Why this is new.** No DEC/LL discusses search-index hygiene. The
  Hamilton perf baseline test (`test_get_asset_board_data_under_one_second`)
  is single-venue; cross-venue scaling is not yet tested.

### F4.2 — Several status / date fields used as filter dimensions lack `search_index`
- **Location.** `Cash Drop.shift_date`, `Cash Drop.timestamp`,
  `Cash Drop.reconciled` (Check), `Cash Reconciliation.timestamp`,
  `Cash Reconciliation.variance_flag` (Select), `Comp Admission Log.timestamp`,
  `Shift Record.shift_date`, `Venue Session.session_start`,
  `Venue Session.session_end`.
- **Pattern.** Same skill — `frappe-syntax-doctypes` flags non-Link filter
  columns missing indices. `Cash Drop.reconciled` is the highest-signal
  one: any "show me unreconciled drops" query is a table-scan. Phase-3
  reconciliation reporting will hit this.
- **Impact.** Same scaling story as F4.1.
- **Recommendation.** Add `search_index: 1` on the highest-traffic filter
  fields: `Cash Drop.reconciled`, `Cash Drop.shift_date`, `Cash Reconciliation.variance_flag`, `Shift Record.shift_date`, `Venue Session.session_start`.
- **Why this is new.** Not in DEC/LL.

### F4.3 — `Venue Session.naming_rule` is "Random" but `session_number` is the human identifier
- **Location.** `Venue Session.json`: `autoname: hash`, `naming_rule: Random`,
  with a unique-validated `session_number` field maintained by application
  code (`_create_session` → `_next_session_number`).
- **Pattern.** Skill `frappe-syntax-doctypes` notes that the human-readable
  identifier and the DocType `name` should usually be the same field
  (`autoname: format:...` or `naming_rule: By "Naming Series" field`).
  Hamilton splits them: the URL-stable `name` is a hash; the operator-facing
  identifier is `session_number`. The split is intentional (DEC-056
  midnight-boundary fix references it) and is documented in `_create_session`,
  but the JSON does not pin the invariant.
- **Impact.** None today — the application code maintains the contract.
  Risk: a future migration that changes `autoname` would need to know
  `session_number` is the de facto identifier, and the JSON does not say so.
- **Recommendation.** Consider adding a comment-bearing `description` on
  `session_number` ("This is the human-readable identifier; `name` is a
  hash for URL stability — see `_create_session`") so future work doesn't
  miss it. Optional; lower priority than F4.1 / F4.2.
- **Why this is new.** DEC-056 covers the midnight-boundary correctness;
  it does not call out the autoname split as a documentation soft-spot.

---

## Category 5 — Scheduler jobs

**No new findings.** `hooks.py:84-90` documents that the Phase-1 stub
`check_overtime_sessions` was deliberately removed because it was a 96×/day
no-op. No `scheduler_events` are currently registered. The skill's
recommended patterns (try/except + Error Log wrapper, idempotency,
`frappe.in_test` short-circuits, no mid-execution commits) cannot be
audited against zero scheduled jobs.

When Phase 2 reintroduces overtime detection, the skill `frappe-impl-scheduler`
should be consulted before the first job lands. The hooks.py comment
("Phase 2 reintroduces a real overtime job ... with a wrapping try/except +
Error Log per Tier-1 audit requirements") already commits to that.

---

## Category 6 — Permission bypass paths

Most `ignore_permissions=True` call sites in this codebase are well-justified:
install hooks (`setup/install.py`, `patches/v0_1/seed_hamilton_env.py`) run
as Administrator and seed framework records; lifecycle controllers
(`lifecycle.py`) document the role-gate-then-bypass delegation pattern;
`submit_retail_sale` documents DEC-005 carve-out.

One finding worth surfacing:

### F6.1 — `_set_vacated_timestamp` and `_set_cleaned_timestamp` save the asset *outside* the asset row lock
- **Location.** `hamilton_erp/lifecycle.py:271` (`_set_vacated_timestamp`)
  and `hamilton_erp/lifecycle.py:377` (`_set_cleaned_timestamp`).
  The lock is acquired inside `vacate_session` / `mark_asset_clean`, and
  these two timestamp helpers are called *after* the `with asset_status_lock(...)`
  block exits (compare `start_session_for_asset` which calls everything
  inside the `with` block).
- **Pattern.** Skill `frappe-core-permissions` and the locking guidance
  in `frappe-impl-controllers` warn that any post-lock write to the same
  row using `ignore_permissions=True` is a soft-spot: it sidesteps both the
  application lock and the standard permission chain. DEC-019 (three-layer
  locking) is the canonical Hamilton lock contract; these two helpers run
  with `save(ignore_permissions=True)` outside that contract.
- **Impact.** Today the only writers to `last_vacated_at` / `last_cleaned_at`
  are these helpers, and they are called from a single place each, so the
  race window is narrow (between the lock release and the timestamp save).
  A future code path that writes to `Venue Asset` from a different surface
  (admin correction endpoint, scheduler, manual Desk save) could observe
  a stale `version` and conflict, since these helpers don't bump or check
  `version`.
- **Recommendation.** Either (a) move the timestamp writes inside the
  `asset_status_lock` block (so they share the lock contract), or (b) add
  an explicit comment on the two helpers explaining why they're safe
  outside the lock — referencing the actual invariant ("status has already
  flipped under the lock; these timestamps are non-conflicting metadata").
  Option (b) matches the existing "T3-1: see `_set_vacated_timestamp`
  above" comment pattern. The current comment talks about Document API
  vs `set_value` but does not address the *outside-the-lock* aspect.
- **Why this is new.** DEC-019 documents the three-layer lock for status
  transitions. DEC-070 documents the `get_doc_before_save() is None` soft-spot
  in Cash Drop guards. Neither covers the post-lock timestamp helpers in
  `lifecycle.py`. Possibly defensible — the timestamps are not part of
  the status state-machine — but the "why" should live in the code.

---

## Findings already covered by existing docs (NOT flagged)

- `frappe.set_user("Administrator")` + `frappe.flags.ignore_permissions = True`
  in `submit_retail_sale` — see DEC-005 (blind cash control) and the
  endpoint docstring's "Authorization model — delegated capability" section.
- `_mark_drop_reconciled` swap of `frappe.db.set_value` for `drop.save(ignore_permissions=True)` — see T3-1 / PR #175 / DEC-072
  cross-reference.
- `frappe.flags.allow_cash_drop_correction` carve-out flag — see DEC-066
  (admin-correction endpoint) and DEC-070 (defensive bypass soft-spot).
- `track_changes` configured on all 8 auditable DocTypes — see LL-038
  resolution and `lessons_learned.md` audit-coverage discussion.
- Removed `check_overtime_sessions` no-op scheduler — see hooks.py inline
  comment + the cleanup note in `inbox.md` history.
- Idempotency contract on whitelisted endpoints — see DEC-067 / LL-039 /
  T0-1.
- Frappe datetime → JS Date timezone trap — see LL-040.
- The dead `_ensure_audit_trail_enabled` install hook (track_changes is
  per-DocType in v16) — see LL-038.

---

## Audit limitations

- **Static analysis only.** No bench run, no test execution, no DB query
  inspection. Slow-query findings (F4.1 / F4.2) are inferred from JSON
  schema, not measured.
- **Sampling, not exhaustive.** Patches under `patches/v0_1/` were
  spot-checked, not fully audited. ERPNext core extensions in
  `hamilton_erp/overrides/` were not opened (only the `extend_doctype_class`
  registration was verified).
- **No multi-venue test harness.** F2.4 (multi-tenancy gap on
  `get_asset_board_data`) is a forward-looking finding; today's single-
  venue tests do not exercise it.
- **Client-side scripts not audited.** `asset_board.js` and the cart UI
  were not reviewed for client-side equivalents of the server-side patterns
  (other than the cross-reference to LL-040). The skill package's
  `frappe-syntax-clientscripts` was not used.
- **Skill package read-as-checklist, not as code-review oracle.** Findings
  reflect the auditor's interpretation of skill anti-patterns against
  Hamilton's code; a deeper pass with the `frappe-agent-validator` skill
  invoked directly would surface more (and would also produce more
  false-positives that the cross-reference step here filtered out).
- **Phase-2 / Phase-3 surfaces not audited.** Anything wired but disabled
  (`assign_asset_to_session` body, Cash Reconciliation system_expected
  calculation) was treated as "Phase-1 disabled" per the existing docs and
  not deeply re-reviewed.
