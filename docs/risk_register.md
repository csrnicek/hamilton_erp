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

## R-006 — `Comp Admission Log.comp_value` readable by Hamilton Operator (PRE-GO-LIVE BLOCKER)

- **Source:** Field masking audit (Task 25 item 7), 2026-04-30. Field-level gap #2.
- **Description:** `permissions_matrix.md` "Sensitive fields" section already names `Comp Admission Log.value_at_door` (now `comp_value`) as Hamilton Manager+ only — but the DocType JSON grants Hamilton Operator full read on the field. Schema lags documented intent. An operator can see the notional revenue cost of comps they (or peers) issued, which leaks margin information and creates a self-justification path for inflated comps.
- **Mitigation in place:** None at the schema level. Operators have row-level read on Comp Admission Log so they can list comps they're issuing — the gap is the field, not the row.
- **Why deferred:** Sequenced *after* gap #1 (Shift Record blind reveal) because gap #1 directly contradicts a documented invariant (DEC-038); gap #2 contradicts a documented intent line in `permissions_matrix.md` but no decision-log invariant. The fix is the same shape: `permlevel: 1` on `comp_value` + paired Manager/Admin permlevel-1 read rows + a regression test in `test_security_audit.py` modeled on `TestShiftRecordBlindRevealGuardrail`.
- **Severity:** **HIGH — pre-go-live blocker.** Must land before the production URL flips. Track as the next PR after gap #1.

## R-007 — Venue Session PII fields (Philadelphia forward-compat) readable by Hamilton Operator (PRE-GO-LIVE BLOCKER)

- **Source:** Field masking audit (Task 25 item 7), 2026-04-30. Field-level gap #3.
- **Description:** Eight fields ship on `Venue Session` for the Philadelphia rollout: `identity_method`, `member_id`, `full_name`, `date_of_birth`, `block_status`, `arrears_amount`, `scanner_data`, `eligibility_snapshot`. They are null at Hamilton today (Hamilton uses anonymous walk-in sessions), but the schema is shared across venues. The day Philadelphia begins populating these fields, every Hamilton Operator with row-level read on Venue Session inherits read access to PII (full names, DOB, ID scan blobs) they have no operational need to see — and that no Hamilton operator is contractually trained to handle.
- **Mitigation in place:** None. The fields render at Hamilton today as blank because they're null in storage; the moment data lands, Hamilton operators can see it.
- **Why deferred:** Hamilton goes to production first; Philadelphia rollout is post-go-live. The gap is latent at Hamilton but becomes immediate the day Philadelphia lights up. Fix mechanism: `permlevel: 1` on each of the eight fields + Manager/Admin permlevel-1 read rows + regression test class. The test must enumerate all eight fields, not just one.
- **Severity:** **HIGH — pre-go-live blocker for Philadelphia, deferable for Hamilton-only deploy.** If Hamilton ships before this fix, OK; Philadelphia *cannot* ship without it. Practical interpretation: must land before any second-venue rollout. Recommend landing alongside gap #2 to retire the field-masking audit cleanly.

## R-008 — Single-acquirer SPOF (downgraded for Hamilton's actual classification)

- **Source:** PR #51 deeper audit (2026-04-30, Topic 2 — merchant redundancy patterns).
- **Description:** Hamilton currently processes card payments through Fiserv (MID 1131224) as a **standard merchant**, NOT under high-risk classification. The deeper audit researched the worst case for adult-classified processors (Stripe-style algorithmic termination without notice, 5-year MATCH list listings, 4-12 week re-onboarding for a new high-risk processor). For Hamilton's actual setup, the risk profile is much lower:
  - **Notice period:** Standard Fiserv merchant agreements provide 30-day termination notice (versus zero-day for high-risk algorithmic processors).
  - **Re-onboarding:** A standard-classified merchant who needs to switch acquirers can typically onboard a backup in 1-2 weeks (versus 4-12 weeks for high-risk).
  - **MATCH list:** Standard merchants with clean chargeback history rarely land on MATCH; the 1% chargeback ratio threshold (R-009) is the real watch line.
- **Mitigation in place:** Standard MID classification means termination requires substantial cause (chargeback noise, AML flag, prolonged inactivity). Fiserv is a tier-1 acquirer with established adult-hospitality acceptance via the MID's MCC; a sudden re-classification to high-risk is unlikely without warning.
- **Why deferred:** The original Phase 2 hardware backlog assumed high-risk classification and called for pre-onboarded multiple merchants. With standard classification, the backup-merchant work drops in priority — still useful as a true SPOF mitigation, but not a launch blocker. Phase 3+ depending on how chargeback history develops in the first year of operation.
- **Severity:** **MEDIUM (downgraded from HIGH).** Hamilton operating as standard via Fiserv is meaningfully different from the adult-industry default.
- **Watch points:** (a) Fiserv re-classifies the MID to high-risk, (b) chargeback ratio approaches the 0.65% Visa-monitored threshold, (c) Fiserv changes terms on the MID. Any of these escalates this risk back to HIGH.

## R-009 — MATCH list 1% chargeback threshold (latent until card payments ship)

- **Source:** PR #51 deeper audit (2026-04-30, Topic 2).
- **Description:** Mastercard's MATCH list (Member Alert To Control High-Risk merchants — a.k.a. Terminated Merchant File) is the cross-network blacklist that prevents a terminated merchant from being onboarded by another acquirer for **5 years** from listing date. The trigger isn't a single bad transaction; it's sustained chargeback noise. Visa's "monitored" threshold is **0.65% chargebacks-to-transactions ratio** in a rolling quarter; Visa's "high-risk" threshold (where penalties begin) is **0.9-1.0% depending on volume**. Crossing 1% sustained for two quarters is the typical MATCH listing trigger.
- **Mitigation in place:** None today. Phase 1 has zero card transactions (cart is cash-only). Phase 2 next iteration adds card processing.
- **Why deferred:** Pre-card-payment-launch, this risk doesn't exist (no chargebacks possible without card transactions). Becomes active the day Phase 2 next ships card payments.
- **Severity:** **HIGH (latent — activates when card payments go live).** A 5-year MATCH listing would force Hamilton onto high-risk processors only, with worse rates and shorter notice windows — the exact situation R-008 is currently below.
- **Watch points (post-card-launch):** Track chargeback ratio monthly. Alert at 0.5% (early warning), 0.65% (Visa monitored — escalation conversation), 0.9% (active mitigation required). Phase 2 next iteration's CE3.0 evidence capture (10 EMV fields per inbox spec, including `auth_code`, `card_entry_method`, `card_cvm`, `card_aid`) is the operational defense — chip-read with proper CVM shifts liability to the issuer for fraud chargebacks.

## R-010 — ERPNext v16 polish-wave fix cadence

- **Source:** v16 production-readiness survey (2026-04-30, github.com/frappe/erpnext issue tracker + version-16 backport PR list).
- **Description:** ERPNext v16 GA'd 2026-01-12. In the 3.5 months since, **~10 fixes per month** have been backported into the `version-16` branch across each of POS / Sales Invoice / Stock / Permissions areas (~50 PRs total in 3.5 months). Two open issues are particularly relevant to Hamilton's current and near-term flows:
  - **[#54183](https://github.com/frappe/erpnext/issues/54183)** "POS Closing Failure Due to Timestamp Mismatch of Return Invoices" — Return invoices update stock at POS Closing time instead of creation time, causing stock-validation failures during close when returns are reused in subsequent sales. **Latent for Hamilton today** (Phase 1 has no returns), **active when Phase 3 returns ship**.
  - **[#50787](https://github.com/frappe/erpnext/issues/50787)** "POS Closing Entry fails due to Stock Validation Error when Refunds are processed in the batch" — Same family. Open since v15. Active the day Hamilton processes its first refund.
- **Mitigation in place:** Phase 1 doesn't process returns/refunds, so neither bug is currently triggerable. Hamilton's elevation pattern in `submit_retail_sale` (set user to Administrator + ignore_permissions=True) is robust against the permission-check tightenings landing in v16.
- **Why deferred:** Both are open upstream issues. Hamilton can't fix them in the Hamilton ERP custom app — they're inside ERPNext's `pos_invoice.py` and `sales_invoice.py`. Watch for upstream fixes; design Phase 3 returns/refunds AROUND the bugs (e.g., process returns immediately, not batched at POS Closing) until upstream lands a fix.
- **Severity:** **HIGH (latent — activates with Phase 3 returns/refunds).** A POS Closing failure during a busy shift's reconciliation = manual workaround under pressure = exactly the kind of incident Tier 0 monitoring is meant to catch but can't fix.
- **Watch points:**
  - Monthly upgrade review (per CLAUDE.md cadence) checks for fixes to #54183 and #50787 in the version-16 backport list.
  - Phase 3 returns/refunds design must explicitly account for these two issues OR depend on upstream fixes shipping first.
  - The general ~10/month fix pace means Hamilton's monthly upgrade window WILL touch a doctype Hamilton uses; the staging-then-production promotion process (per CLAUDE.md) is the structural defense.

## R-011 — Cash Reconciliation variance system non-functional at Phase 1 (false-alarm risk)

- **Source:** Phase 1 controller audit on 2026-05-01; cross-referenced in Phase 3 design intent doc (`docs/design/cash_reconciliation_phase3.md`, PR #108).
- **Description:** `hamilton_erp/hamilton_erp/doctype/cash_reconciliation/cash_reconciliation.py::_calculate_system_expected` is a placeholder that hardcodes `self.system_expected = flt(0)` and is marked "Phase 3 implementation." Until Phase 3 wires up the real "sum of cash payment lines on submitted Sales Invoices for the shift period" calculation, every real reconciliation runs the three-way variance against `system = 0`. Concrete consequence: any drop with non-zero cash will trigger `variance_flag = "Possible Theft or Error"` (when manager ≈ operator but system differs) or `"Operator Mis-declared"` (when manager ≈ system = 0 but operator declared real cash). The flag will fire on EVERY reconciliation because operator and manager will both report real cash > 0 and system_expected = 0 will always disagree.
- **Mitigation in place:** Manager training. Until Phase 3 ships, managers must ignore the `variance_flag` value entirely and treat the count as Clean if A (operator-declared) ≈ C (manager-counted) and the printed envelope label matches the operator declaration. The flag is noise, not signal, while system_expected is stubbed.
- **Why deferred:** Wiring up the real `system_expected` calculator is non-trivial — it has to query Sales Invoices for the shift period, sum cash payment lines, subtract tip pulls, and apply the venue-specific reconciliation profile (`docs/design/cash_reconciliation_phase3.md` §3). Doing it half-right is worse than not doing it at all (drives downstream variance flags wrong). Phase 3 ships the full design, not a partial.
- **Severity:** **MEDIUM.** No data corruption; false-positive flag pattern only. Risk is operational: a manager who doesn't know to ignore the flag will investigate phantom theft on every drop, eroding trust in the system over time. Mitigation depends entirely on training discipline, not code.
- **Watch points:**
  - Hamilton manager onboarding must explicitly state "ignore variance flag until Phase 3" and reference this risk entry.
  - Phase 3 implementation kickoff (Task 25 successor or new task) MUST include the real `system_expected` calculator as the first deliverable, before any other Phase 3 cash recon work.
  - If manager attrition replaces the trained-to-ignore manager with a new manager unaware of the workaround, the false-alarm pattern reactivates; this is a process risk, not a code risk.
- **Linked work:** Phase 3 redesign captured in `docs/design/cash_reconciliation_phase3.md` (PR #108). Gap #4 Cash Reconciliation field masking (deferred to Phase 3 alongside variance redesign per 2026-05-01 directive — Item 7 ships as 4 of 5 gaps complete).

## R-012 — Cash Drop envelope label print pipeline unbuilt (PRE-GO-LIVE BLOCKER)

- **Source:** Cash Drop envelope label investigation on 2026-05-01; cross-referenced in Phase 3 design intent doc (`docs/design/cash_reconciliation_phase3.md`, PR #108).
- **Description:** `docs/hamilton_erp_build_specification.md` §7.4 step 4 specifies that the system "prints a label on the label printer containing: Venue name, Date, Operator name, Shift identifier, Drop type, Drop number, Declared amount, Timestamp" when an operator submits a Cash Drop. This pipeline is **unbuilt today**. The Cash Drop submit hook does not invoke any print routine. `Hamilton Settings.printer_label_template_name` is a name field with nothing on the other end — no `Label Template` DocType exists, no print_format renders it, no print endpoint dispatches to the Brother QL-820NWB. The operator submits a Cash Drop, the record is saved, no label is printed, no envelope is labeled.
- **Why this is a BLOCKER (not deferable):** The blind cash drop anti-theft design (DEC-005, DEC-021, captured in `docs/design/cash_reconciliation_phase3.md` §1) depends on the operator NEVER writing a number on the envelope by hand. Handwritten numbers can be doctored; pre-printed labels with the system's record cannot. Without the print pipeline, operators must either (a) write the declared amount on the envelope by hand — which breaks the anti-tampering invariant — or (b) drop unlabeled envelopes that the manager identifies later by Frappe UI listing — which makes manager-side reconciliation a forensics exercise instead of a physical-envelope-to-system-record match. **Either fallback defeats the design.** Hamilton cannot launch Phase 1 with this gap; the print pipeline must ship before go-live.
- **Mitigation in place:** None. The risk is OPEN.
- **Status:** OPEN — Phase 1 BLOCKER. Must be closed before Hamilton go-live, NOT deferred to Phase 2 / Phase 3.
- **Severity:** **HIGH (BLOCKER).** Defeats DEC-005 blind cash drop invariant operationally; without it, blind drop is theatre. The design intent doc (PR #108) explicitly calls this out: "today the print pipeline is unbuilt... until that pipeline lands, the blind-write discipline degrades to a procedural rule (operator writes nothing manually, manager identifies envelopes by Cash Drop record listed in Frappe)" — that procedural rule is not durable under operator turnover or shift fatigue.
- **Linked work:** Taskmaster Task 30 — "Cash Drop envelope label print pipeline (Phase 1 BLOCKER)." See `.taskmaster/tasks/tasks.json`.
- **What ships in Task 30:**
  - `Label Template` DocType (or first-cut equivalent) holding the cash drop envelope template
  - Cash Drop `on_submit` hook that renders the template with the 8 spec fields and dispatches to the printer at `Hamilton Settings.printer_ip_address`
  - Brother QL-820NWB printer integration (P-touch Template engine per `docs/research/label_printer_evaluation_2026_05.md`, OR raster fallback for first-cut)
  - Hamilton Settings entry for the cash drop template name
  - Tests confirming label content matches the 8 spec fields and prints reliably under simulated submit conditions
  - Operator-side error handling: if print fails, surface a clear blocker on the Cash Drop submit (operator cannot drop an unlabeled envelope into the safe).

## R-013 — Deferred stock validation explodes at POS Closing when same-shift returns are batched

- **Source:** Phase A research output (`docs/research/erpnext_pos_business_process_gotchas.md` G-002), surfaced in Task 29's morning brief on 2026-05-01 as "the single 'we wish we'd known' gotcha."
- **Description:** ERPNext defers stock validation from Sales Invoice submit time to POS Closing Entry time. When a same-shift return is included in the batch (operator returns an item, then sells it again the same shift, or returns are processed alongside sales at end of shift), the deferred validator hits an inconsistency between the running stock ledger and the post-close ledger and rejects the entire POS Closing Entry. The pattern reported across at least 4 GitHub issues spanning ERPNext v13 → v16 (still open as of 2026-Q2): teams test in staging without same-shift returns, go live, hit it on day three, enable `Allow Negative Stock` as a workaround, forget to re-disable it, and two weeks later the stock ledger has sold more than was ever in the warehouse. The negative-stock workaround silently corrupts inventory accuracy.
- **Hamilton's current exposure:** **Latent** — Phase 1 ships without any return/refund flow, so same-shift returns cannot occur. The bug is not currently triggerable. Risk activates the moment Phase 2 returns ship (Task 31 — cash-side refunds — is the entry point).
- **Mitigation in place (Phase 1):** Phase 1 has no returns. The `Allow Negative Stock` setting on Hamilton sites is OFF and must stay OFF.
- **Mitigation required (Phase 2 — when Task 31 ships):** Refund design must explicitly route AROUND this bug. Specifically, refunds must commit a Sales Invoice Return immediately (`update_stock = 1` at the time of refund), NEVER deferring stock impact to POS Closing Entry batch. Under no circumstances should `Allow Negative Stock` be turned on as a "fix." Task 31's design and test strategy already include this routing requirement. The first refund night after Phase 2 launch must explicitly verify: (a) refund created a paired SI Return, (b) stock ledger updated immediately, (c) end-of-shift POS Closing Entry submits without error.
- **Why this is in the risk register, not just a gotcha:** Hamilton's monthly version pin process (per CLAUDE.md "Disable auto-upgrade on the production bench") could pull a v16 minor that has this bug fixed upstream, OR could pull one that worsens the workaround surface. The watch-points below define what to monitor.
- **Severity:** **HIGH (latent — activates with Phase 2 returns).** When it fires, the symptom is a POS Closing Entry that won't submit during a busy shift's close-out. The wrong response (enable Allow Negative Stock) silently corrupts the stock ledger; the right response (route refunds with immediate stock update) requires architectural discipline.
- **Watch points:**
  - Monthly upgrade review (per CLAUDE.md cadence) checks for fixes to ERPNext Issues #54183 and #50787 (same family per R-010) AND for fixes to G-002 specifically in the version-16 backport list.
  - Phase 2 Task 31 (cash-side refunds) MUST include a regression test verifying same-shift refund + sale combinations don't break POS Closing Entry submission.
  - If Hamilton ever processes a same-shift return + sale combination and the closing fails, the FIRST response is NOT "enable Allow Negative Stock." Read this risk entry first.
- **References:**
  - G-002 in `docs/research/erpnext_pos_business_process_gotchas.md` — the field-research gotcha
  - R-010 in this register — sibling risk on ERPNext v16 polish-wave fix cadence (Issues #54183, #50787)
  - Task 31 — cash-side refunds (the design must route around this)
  - `docs/design/refunds_phase2.md` — design intent doc captures the routing requirement (review-pending)

---

## Maintenance

**When to add:** After any adversarial review or post-mortem that surfaces a real-but-not-fixing-now finding.

**When to remove:** When the risk is mitigated by new code, or when re-evaluation determines the risk is no longer relevant (e.g. the feature it concerns has been removed).

**When to escalate:** If a risk's severity changes, or if production conditions make a deferred risk now actionable.

**Review cadence:** Re-read at every Phase boundary (Phase 1 → Phase 2, multi-venue rollout, etc.) and at every 3-AI checkpoint.

---

*Created 2026-04-29 from PR #16 deferred findings previously living in `docs/lessons_learned.md`.*
