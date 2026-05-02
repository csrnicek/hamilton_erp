# PII Masking Coverage Audit — 2026-05-02

**Scope:** every Hamilton-owned DocType field that holds (or will hold) Personally Identifiable Information per `docs/research/pipeda_venue_session_pii.md`. Verify that each field has appropriate masking (DocType-level role gate, `permlevel` field-level mask, or full encryption-at-rest), and flag the gaps. Includes the gateway `customer` Link and the forward-compat fields catalogued in PIPEDA research §2.

**Mindset:** PIPEDA Principle 7 (safeguards) and Principle 5 (limiting retention) require both *access controls* and *purge mechanisms*. Today every Venue Session PII field is null — but the schema is shipping nationwide. The moment any one venue lights up membership / scanner / arrears flows, every other venue's operators inherit visibility unless masking is in place beforehand. **Hunt the day-1-of-population failure mode**, not the today-it's-empty status.

**Method:** enumerated every DocType field whose name suggests sensitivity, plus all explicitly-`permlevel`-marked fields. Cross-referenced against PIPEDA research §2 (the eight PII fields + three forward-compat). Inspected git state of PR #100 (Venue Session masking, awaiting merge). Looked for any retention/purge/anonymization code (`grep purge|retention|delete_after|anonymize`) — found none.

**Severity counts:** **0 BLOCKER · 4 HIGH · 2 MEDIUM · 1 LOW.**

> No active BLOCKER today because no PII is populated. **The HIGH-rank findings convert directly to BLOCKER on the day Philadelphia (or any membership venue) ships.** PR #100 covers most of the masking gap; PR #100 does NOT cover retention, encryption-at-rest, or the `customer` Link gateway.

---

## HIGH

### H1 — Seven PII fields on Venue Session have NO `permlevel` masking on `main` today; PR #100 is the inflight fix

**Files:** `hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json` (live state on `main`); PR #100 (`feat/task-25-item-7-venue-session-pii-masking`).

Live `main` state:

| Field | PIPEDA sensitivity | `permlevel` on main | Covered by PR #100 |
|---|---|---|---|
| `full_name` | HIGH | none (0) | ✓ → 1 |
| `date_of_birth` | CRITICAL | none (0) | ✓ → 1 |
| `member_id` | HIGH | none (0) | ✓ → 1 |
| `identity_method` | MEDIUM | none (0) | ✓ → 1 |
| `block_status` | HIGH | none (0) | ✓ → 1 |
| `arrears_amount` | HIGH | none (0) | ✓ → 1 |
| `eligibility_snapshot` | HIGH | none (0) | ✓ → 1 |

**Failure scenario.** Philadelphia ships Phase 2 with the membership flow. `member_id`, `full_name`, `date_of_birth` start populating. Hamilton's existing test_site database had these fields all-null until that point. Hamilton Operators continue to have row-level read on Venue Session (per the perm grid). Without permlevel-1 masking, every Hamilton Operator sees Philadelphia members' PII — even though Hamilton has no operational reason to see Philadelphia's member list. PIPEDA Principle 7 (safeguards) violation. PIPEDA Principle 4 (limiting collection) implication: information that gets collected for Philadelphia leaks operationally to Hamilton operators just by virtue of the shared schema.

**Why it's allowed today.** The masking work is staged across PR #98 (Comp Admission Log, merged), PR #99 (Cash Drop owner-isolation, awaiting review), and PR #100 (Venue Session, awaiting review). PR #100 is *ready* but not yet merged.

**Recommended fix.** Land PR #100 before any non-Hamilton venue or any membership flow lights up. Per the audit-mode constraint of this audit, I do not propose to fix it tonight; I document that PR #100's merge is the pre-launch gate.

### H2 — `scanner_data` has no masking AND no encryption-at-rest; the latter is the bigger gap

**Files:** `hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json` (no `permlevel` on `scanner_data`); `docs/research/pipeda_venue_session_pii.md:65` (sensitivity = **CRITICAL** "verify-then-delete").

PR #100 explicitly **defers** `scanner_data` to a later session because it needs encryption-at-rest in addition to permlevel masking. The PIPEDA research recommends `verify-then-delete` (don't persist the raw scan at all).

**Failure scenario.** The first time a venue runs an ID scanner workflow, the raw scan output (driver's licence barcode contents, sometimes including SIN-equivalent identifiers, full address, license issuance jurisdiction) lands in plaintext in `tabVenue Session.scanner_data`. Frappe Cloud's standard backups are encrypted at rest at the VM-disk layer (per Frappe Cloud docs), but anyone with `read` perm on Venue Session sees the plaintext through the Frappe API. The DocType-level read includes Hamilton Operator. **Catastrophic exposure** at first population unless verify-then-delete is implemented.

**Why it's allowed.** Field exists in the schema for forward-compat. No code currently writes to it. The encrypt-at-rest decision needs key management (site_config secret vs. KMS vs. Frappe Cloud vault) which is its own design session.

**Recommended fix.** Two-track:

1. **Short-term:** When `scanner_data` masking lands, also implement a `before_save` hook that throws if `scanner_data` is populated by an Operator (even with permlevel-1 read denial, Operator can still WRITE without it). The verify-then-delete pattern: `before_insert` runs the verification, captures the verified-over-NN flag and (optionally) age, then **clears** `scanner_data` before save.
2. **Long-term:** Use Frappe's encrypted-field mechanism (`Password` field type or custom encryption) once the key-management session resolves. PIPEDA research §6 and §7 cover this.

### H3 — Venue Session's `customer` Link is the gateway to Customer record PII, but Hamilton-side masking does not extend across the Link

**Files:** `hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json` (`customer` field); `docs/research/pipeda_venue_session_pii.md:60` (gateway sensitivity = **CRITICAL**).

```
customer: Link to Customer (ERPNext core DocType)
```

**Failure scenario.** The day a Venue Session row points at a non-Walk-in Customer, the linked Customer record exposes its full ERPNext attribute set (customer_name, mobile_no, email_id, customer_primary_address, all transaction history) — all visible through the Link if the operator has read on `Customer`. Hamilton's seeding (`_ensure_hamilton_customer_groups`) gives the operator role read access on Customer. No Hamilton-side override masks the Customer record's fields per-permlevel, because `Customer` is an ERPNext-core DocType and Hamilton's perm grid only governs Hamilton-owned DocTypes.

The PIPEDA research at line 60 is explicit: *"a populated `customer` exposes everything ERPNext stores on Customer, not just one identifier."*

**Why it's allowed.** Hamilton's perm scoping stops at Hamilton-owned DocTypes. Cross-DocType masking through Link fields requires either (a) an ERPNext core override / Custom DocPerm, or (b) Hamilton-side wrappers that hide the Link from operators by design.

**Recommended fix.** Decision required (does not fit a single PR). Three viable patterns:

1. **Custom DocPerm** on `Customer` to restrict which roles can read which fields — needs to be exported as fixture, increases the seed-data surface area.
2. **Hamilton-only Link target** — replace the `customer` Link with a Hamilton-owned `Hamilton Member` DocType that has Hamilton-controlled perms; the Hamilton Member can in turn link to ERPNext Customer. Indirection layer.
3. **Mask the link itself** — `permlevel: 1` on the `customer` field of Venue Session. Operator sees a placeholder; Manager+ sees the linked customer name. Doesn't solve the underlying Customer-record exposure but reduces the attack surface to manager-only.

Pattern 3 is the lightest-touch and is consistent with PR #100's mechanism. Worth considering as a Phase 1 minimum.

### H4 — Zero retention / purge / anonymization code in the codebase; PIPEDA Principle 5 (limiting retention) cannot be enforced

**Files:** entire `hamilton_erp/`; verified by `grep purge|retention|delete_after|anonymize` returning no relevant matches outside lock TTL strings.

**Failure scenario.** PIPEDA Principle 5 requires that personal information is retained only as long as necessary for the identified purpose. PIPEDA research §3 (`pipeda_venue_session_pii.md:97–127`) catalogs per-field retention windows: 90 days post-membership-lapse for `member_id`, 6-year-CRA-window after debt settled for `arrears_amount`, etc. None of these are implemented as scheduler jobs, controllers, or anonymization helpers. There is no automated purge.

The day Hamilton populates any PII field, the retention clock starts ticking and Hamilton has no automated mechanism to honor it. Manual purge is not a defensible position under PIPEDA — it's a compliance gap.

**Why it's allowed today.** No PII populated → no retention obligation triggered. The compliance gap is dormant.

**Recommended fix.** Phase 2 work item (probably its own ticket, not piggy-backed on Task 25): scheduler job(s) that walk Venue Session (and once linked, Customer + Comp Admission Log) and purge / anonymize per the PIPEDA research's retention table. Document the scheduler in `docs/research/pipeda_venue_session_pii.md` Section 3 — add a "Status: NOT IMPLEMENTED" subsection so the gap is visible in the same doc that promises the policy.

---

## MEDIUM

### M1 — `Asset Status Log.operator`, `Cash Drop.operator`, `Cash Reconciliation.manager`, `Comp Admission Log.operator`, `Hamilton Board Correction.operator`, `Shift Record.operator`, `Venue Session.operator_checkin/operator_vacate` are all `Link to User`

These are operationally necessary (audit trail must identify who did the work). They are *PII at the User level* (User holds email, full_name, mobile_no, etc.), but they are not masked because (a) audit integrity requires identifying the operator, and (b) the User record's own perms govern downstream exposure.

**Failure scenario.** A non-Hamilton-Admin role (e.g. Hamilton Manager) wants to identify the operator for a 2am incident. They click through the Link. Frappe loads the User record. User contains email, mobile_no, etc. — the Manager sees those even though their operational need is just the operator's username.

**Why it's tolerable.** User-record exposure is governed by Frappe's User DocType perms (System Manager only by default, Hamilton Manager has nothing on User unless granted). The Link in Hamilton context is bound by `User`'s own perm grid.

**Recommended fix.** Verify (Audit 4 follow-up) that Hamilton roles do NOT have User read perm. If they don't, this is fine. If they do, mask the User Link's downstream fields per `permissions_matrix.md` Sensitive Fields section (extend the matrix to include cross-DocType Link exposure — currently scoped to Hamilton DocTypes only).

### M2 — `Hamilton Settings.printer_ip_address` is operational config, not PII, but worth flagging as a sensitivity-adjacent field

**File:** `hamilton_erp/hamilton_erp/doctype/hamilton_settings/hamilton_settings.json` (printer_ip_address field).

Not PII per any of the privacy frameworks. Flagged here for completeness because the audit's regex for sensitivity hints picked it up. No action required for PIPEDA. If a security review (separate audit) flags internal-network IPs as sensitive, revisit.

---

## LOW

### L1 — The three forward-compat fields PIPEDA research §2 flags (`membership_status`, `arrears_flag`, `arrears_sku`) have no masking either

Per PIPEDA research lines 73–82: not standalone PII, but combine with `member_id` / `customer` / `arrears_amount` to form profile fragments. PR #100 does NOT cover them.

**Failure scenario.** Same as H1, but lower severity because alone they are not identifying. The combination `(customer, arrears_flag=True, arrears_sku=...)` ties a debt-collection record to an identified person.

**Recommended fix.** When the membership / arrears feature spec lands, decide whether these need masking. If yes, fold into the same permlevel-1 masking pattern as H1. If no (operationally required for operators), document the decision in `decisions_log.md`.

---

## Categories with no findings

- **DocType-level perm gates as a substitute for field-level masking.** Cash Reconciliation has Manager+Admin only at the DocType level — Operator has no read at all, so field-level masking is unnecessary there. The matrix's Sensitive Fields section misleadingly lists `Cash Reconciliation.expected_cash, actual_cash, variance` as needing masking; in fact the DocType-level deny is sufficient. Cross-ref Audit 4 H1.
- **Comp Admission Log.comp_value** masking — already implemented (PR #98 merged). Verified at JSON line 91 (`permlevel: 1`).
- **Shift Record.system_expected_card_total** masking — already implemented. Verified at JSON line 192 (`permlevel: 1`).
- **PII in Cash Drop.** No genuine PII fields on Cash Drop. The operator and amount fields are operational.
- **PII in Venue Asset.** No PII fields. Asset names, codes, tiers, statuses are all operational data.

---

## Cross-references

- **`docs/research/pipeda_venue_session_pii.md`** — the canonical PIPEDA analysis. This audit treats it as the source of truth for which fields are PII; if the research is out of date, this audit is too.
- **PR #100** — the inflight Venue Session masking PR. H1 documents the gap that PR #100 closes; H2 / H3 / H4 are gaps PR #100 does NOT close.
- **PR #98** — Comp Admission Log masking, merged. Reference pattern for PR #100.
- **`docs/permissions_matrix.md`** — DocType-level perm grid. Audit 4 catalogs that doc's drift; this audit relies on the JSON-level reality.

---

## What I did NOT audit

- **ERPNext core Customer DocType field-level access.** Out of scope; would require an ERPNext-side audit. Covered in H3 as a structural gap.
- **Network-layer protections** (TLS, firewall, etc.). Frappe Cloud's standard hardening. Out of scope for a code audit.
- **Audit log / version history exposure.** Audit 6 (in progress) covers this.
- **Backups and at-rest encryption.** Frappe Cloud handles VM-disk encryption; Hamilton-side encrypted fields (for `scanner_data`) are deferred. Cross-references Runbook 8.

---

**Author:** Claude (audit pass run 2026-05-02 in Hamilton ERP audit + docs mode).
**Reviewer:** Chris (pending).
