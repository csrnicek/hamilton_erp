# Canadian Privacy Law — Venue Session PII Implications

**Status:** Research-only reference document. No code changes yet.
**Scope:** PIPEDA obligations for the eight forward-compat PII fields on the Venue Session DocType.
**Hamilton context:** Numbered Ontario corporation, anonymous walk-in flow today, PII fields null at Hamilton; schema exists for future Philadelphia / DC rollout or future ID-scanning at Hamilton itself.
**Audience:** Chris (Privacy Officer by default), future developers, future legal counsel.

---

## Executive Summary

The eight PII fields on Venue Session (`full_name`, `date_of_birth`, `member_id`, `identity_method`, `block_status`, `arrears_amount`, `scanner_data`, `eligibility_snapshot`) are null at Hamilton today. The day any Hamilton venue (or Philadelphia, DC, Dallas) populates them, eight obligations attach simultaneously under PIPEDA — only one of which is a code change. The remaining seven are documentation, process, and contractual work that must be done before PII collection begins, not after.

**Single biggest pre-PII blocker:** the seven PII fields need field-level masking (`mask: 1` for most, with full blocking — `permlevel: 1` — for `scanner_data` per Section 5) plus encryption-at-rest for `scanner_data`. This work has not been scoped or implemented yet. It would be a new addition to **Task 25 item 7 (sensitive fields enumeration)** in `docs/permissions_matrix.md`, which currently covers Cash Drop and Cash Reconciliation fields but NOT Venue Session PII fields. See **DEC-021 (field-masking decision)** for the underlying invariant; the implementation pattern matches what `permissions_matrix.md` already documents for Cash Drop/Reconciliation.

**Single biggest finding from the research:** Frappe Cloud's public region list does **not** appear to include a Canadian region (`ca-central-1`). The live database currently runs from one of: Mumbai, Frankfurt, Bahrain, Cape Town, or N. Virginia. This means cross-border-disclosure language is mandatory in Hamilton's privacy notice — there is no "store everything in Canada" option available on the current Frappe Cloud platform. Confirm with Frappe support before assuming otherwise.

---

## 1. Which Law Applies

**PIPEDA** (federal — Personal Information Protection and Electronic Documents Act) is the only privacy law that applies to Hamilton today.

PIPEDA covers "every organization in respect of personal information that the organization collects, uses or discloses in the course of commercial activities." Hamilton is unambiguously a commercial activity; PIPEDA applies.

### Numbered-corporation specifics

None. The corporate structure (numbered vs named, sole-proprietor vs corporation, federally vs provincially incorporated) doesn't affect PIPEDA applicability. The trigger is "commercial activity," not entity type. A numbered corp gets the same PIPEDA obligations as a named one. The corporation **is** the "organization" for PIPEDA purposes.

### Ontario provincial laws — applicability check

| Law | Applies to Hamilton? | Why |
|---|---|---|
| **FIPPA** (Freedom of Information and Protection of Privacy Act) | NO | Public-sector law. Covers ministries, provincial agencies, colleges, universities, hospitals as public bodies. Not private-sector. |
| **MFIPPA** (Municipal Freedom of Information and Protection of Privacy Act) | NO | Same scope as FIPPA but for municipal bodies (cities, school boards, police services). Public-sector only. |
| **PHIPA** (Personal Health Information Protection Act) | NO | Applies to "Health Information Custodians": healthcare providers, hospitals, regulated health professionals. A bathhouse is not a Health Information Custodian. |
| **PIPEDA** (federal) | YES | Commercial activity by a Canadian organization. |

### PHIPA edge case

PHIPA could attach **only** if Hamilton ever operates inside a healthcare context — for example, a wellness clinic offering bathhouse-adjacent services with on-staff regulated nurses, naturopaths, or massage therapists collecting health information for clinical purposes. Phase 1, Phase 2, and Phase 3 do not contemplate this, but documenting for completeness.

The Ontario regulation on "public spas" under the Health Protection and Promotion Act covers physical safety (water quality, ventilation, etc.) — not information privacy.

### Bottom line

PIPEDA is the only privacy law that applies. No provincial overlay. This simplifies compliance substantially compared to Hamilton's potential US venues (Philadelphia, DC, Dallas), each of which would have its own state-level privacy regime to layer on top of federal rules — not relevant for Hamilton itself but worth flagging for the multi-venue platform refactor.

### Customer-perceived attendance sensitivity has no formal privacy-law category (but amplifies risk profile)

PIPEDA applies a uniform "real risk of significant harm" threshold and the same fair-information principles to every commercial business, regardless of category. There is no privacy-law carve-out tied to industry, and Hamilton operates under PIPEDA as a standard commercial business with no industry-specific obligations layered on top.

However, customer attendance at Hamilton is sensitive **from the customer's perspective** — disclosure may cause reputational, relational, or psychological harm to customers in a way that disclosure of, say, a coffee-shop visit would not. This perception **amplifies the real-risk-of-significant-harm calculation** in four ways — see Section 8 for the full discussion.

---

## 2. The Eight PII Fields — PIPEDA Principles Applied

PIPEDA's ten fair-information principles (accountability, identifying purposes, consent, limiting collection, limiting use/disclosure/retention, accuracy, safeguards, openness, individual access, challenging compliance) all apply when any PII field is populated. Per-field analysis:

| Field | Sensitivity | Justified Purpose | Today | Day-1 of Population |
|---|---|---|---|---|
| `customer` | **CRITICAL** (gateway field) | Link to ERPNext Customer DocType — gateway to the full Customer record (name, phone, email, address, transaction history) | Defaults to `Walk-in` (forward-compat per DEC-007 / `current_state.md`) | Day a real Customer is linked, ALL Customer-record PII becomes attached to the session via this Link field. Arguably more significant than `member_id` from a PIPEDA perspective: a populated `customer` exposes everything ERPNext stores on Customer, not just one identifier. Day-1 controls: (a) the same `mask: 1` discipline must extend to the linked Customer record's PII fields; (b) consent for the link must be documented at the Customer-creation step, not just at session creation; (c) retention rules attach to BOTH the Venue Session and the Customer record |
| `full_name` | HIGH | Member identification, age verification, dispute response | Null | Documented purpose required; consent at time of collection; `mask: 1` (operator sees placeholder, Manager+ sees value) |
| `date_of_birth` | CRITICAL | Age verification (AGCO age-verification requirement if licensed; otherwise local-licensing-equivalent or contractual age gate) | Null | `mask: 1` mandatory; ideally store only the boolean "verified over 18/19" rather than exact DOB unless ongoing membership requires it |
| `member_id` | HIGH | Membership-tier pricing; links to Customer history | Null | Justified for membership flow only; purge 90 days after membership lapse |
| `identity_method` | MEDIUM | Audit ("operator used what method to verify") | Null | Inseparable from the PII it audits — same retention as the PII itself |
| `block_status` | HIGH | Operational control (deny entry to blocklisted persons) | Null | Boolean flag is operationally necessary; reason text is over-collection unless documented and Manager-only |
| `arrears_amount` | HIGH | Collection of unpaid balances | Null | Justified for actual debt collection; purge after debt settled or written off + 6-year CRA window |
| `scanner_data` | **CRITICAL** | Age verification at the moment of admission | Null | **Verify-then-delete.** Persisting the raw scan is over-collection per Principle 4. See Section 7. |
| `eligibility_snapshot` | HIGH | Audit of eligibility decisions | Null | Justified IF eligibility decisions are appealable / auditable; same retention as the SI / Venue Session |

### Note on other forward-compat fields on Venue Session

The Venue Session DocType also contains three additional forward-compat fields that this analysis does NOT classify as primary PII but which are worth flagging because they may pull PII obligations along with them once populated:

- **`membership_status`** (Data) — present on the schema for Philadelphia / membership-tier rollout. Not standalone PII, but combined with `member_id` it becomes a profile fragment subject to the same retention discipline.
- **`arrears_flag`** (Check) — boolean companion to `arrears_amount`. Boolean alone is NOT PII, but its presence flags that arrears tracking is active for the session, which (combined with `customer`) ties debt-collection records to an identified person.
- **`arrears_sku`** (Data) — the SKU/category of the unpaid item. Not PII alone, but if it identifies a venue-specific product (e.g. a specific tier or a sensitive line item), the SKU + `customer` link could constitute over-collection unless the SKU is necessary for collection. Treat as Justified-Only-If-Needed, same as `arrears_amount`.

These three fields are documented here for completeness — operational decisions around them belong with the membership/arrears feature spec when those flows go live, not at PII landing.

### Most-important per-field rule

`scanner_data` should NEVER persist past the verification event. Treat it like a CVV — load, verify, immediately discard. Persisting raw ID document images / MRZ data creates outsize breach impact (extortion target, identity-theft enabler) without commensurate business need.

### The three principles that drive most operational decisions

- **Principle 4 — Limiting Collection.** "The collection of personal information must be limited to that which is needed for the purposes identified by the organization." Means: if Hamilton can verify age without storing the DOB long-term, it must.
- **Principle 5 — Limiting Use, Disclosure, and Retention.** "Personal information that is no longer required to fulfil the identified purposes should be destroyed, erased, or made anonymous." Means: written retention schedule with automated purge.
- **Principle 7 — Safeguards.** "Personal information shall be protected by security safeguards appropriate to the sensitivity of the information." Means: role-based access plus field-level masking (`mask: 1` for most PII; `permlevel: 1` for raw `scanner_data` — see Section 5 for the distinction) is the operational answer.

---

## 3. Retention Rules — What Hamilton Must Do

PIPEDA does not prescribe specific retention periods. It prescribes the **process**:

### Required: documented retention windows

A per-field retention schedule, in writing. Example template:

| Field | Retention | Purge Trigger |
|---|---|---|
| `full_name` | Active membership + 6 years (CRA window for SI) | Membership termination + 6 years |
| `date_of_birth` | Boolean "verified" flag retained; raw DOB deleted within 24h of verification unless ongoing membership | Verification + 24h, OR membership termination + 6 years |
| `scanner_data` | **Within 1 hour of verification.** Boolean "verified" flag retained. | Verification + 1 hour (ideally minutes) |
| `member_id` | Active membership duration | Termination + 90 days |
| `arrears_amount` | Until paid + 6 years | Settlement + 6 years |
| `block_status` | While block active | Block lifted + 90 days (appeal window) |
| `eligibility_snapshot` | With the SI / Venue Session, per CRA's 6-year window | SI retention expiry |

### Required: automated purge

A retention schedule on paper isn't compliance — automated deletion is. Hamilton needs a scheduled task (Frappe Scheduler Job — already on the Phase 2 reminder list) that purges expired PII while leaving operational fields in place.

This is **per-field**, not whole-record deletion. The Venue Session record itself is an accounting / operational document that has independent retention obligations under CRA rules. Only the PII fields get nulled out on the schedule above.

### Anonymization is an alternative to deletion

For aggregate analytics, replacing `member_id` with a hashed token while purging the underlying identifier preserves business value while satisfying the retention obligation. PIPEDA explicitly recognizes anonymization as a Principle 5–compliant alternative.

### Minimum-necessary discipline goes beyond retention

Hamilton must ALSO not collect what isn't needed in the first place. If Philadelphia adds a "favorite drink" field that's never used operationally, that's over-collection regardless of retention policy. Each new PII field added to any Venue Session variant needs a documented business justification.

---

## 4. Breach Notification — When, How, What

### Trigger: "real risk of significant harm"

PIPEDA's mandatory breach reporting (in force since 2018-11-01) applies to any breach involving personal information that poses a **real risk of significant harm** to one or more individuals.

Significant harm includes: "bodily harm, humiliation, damage to reputation or relationships, loss of employment, business or professional opportunities, financial loss, identity theft, negative effects on the credit record and damage to or loss of property."

### Two-tier real-risk test

1. **Sensitivity** of the breached information.
2. **Probability** of misuse.

### Hamilton-specific calibration

A venue where customer attendance is sensitive from the customer's perspective produces breach-impact data that plausibly meets "humiliation" and "damage to reputation/relationships" for many customers, even without financial impact. **Hamilton's real-risk threshold is lower than a generic retailer's** — meaning more breaches need reporting, even small ones. Note: this is a customer-privacy point, not a business classification — see Section 8 clarifying note.

### Three obligations on a reportable breach

1. **Report to the OPC** (Office of the Privacy Commissioner of Canada) using their breach-report form, "as soon as feasible" after determining a breach occurred.
2. **Notify affected individuals** "as soon as feasible" with enough detail to mitigate harm.
3. **Notify other organizations** that can help mitigate (e.g., Fiserv if card data was involved; Frappe Cloud if it's a hosting-side breach; an ID-verification vendor if scanner data leaked).

### Sub-threshold breach record-keeping

- ALL breaches must be recorded for 24 months regardless of whether they meet the reporting threshold.
- Failure to record sub-threshold breaches is itself a violation, separate from failure to report.
- Records must be available to the OPC on request.

### No minimum size

"Whether a breach affects one person or 1,000, it will still need to be reported if your assessment indicates there is a real risk of significant harm."

### Hamilton runbook items needed before PII populates

- **Breach-detection capability.** Sentry + uptime monitoring covers some scenarios; a dedicated audit-log review process is needed for slow-leak scenarios.
- **Documented breach-response playbook.** Who decides if the threshold is met (Privacy Officer = Chris by default); what notice to individuals looks like (template); what notice to OPC looks like (use OPC's form).
- **Breach log file** — `docs/breach_register.md` or similar, append-only, 24-month retention. Even "no harm" breaches go in.

---

## 5. Employee Access Controls — Minimum Necessary

PIPEDA Principle 7 (Safeguards) does not prescribe a specific RBAC model but is universally interpreted to require **need-to-know access**: more sensitive data = more restricted access.

### Hamilton's structural answer (not yet scoped — would extend Task 25 item 7)

- **`mask: 1` on PII fields (most).** Hamilton Operator role sees masked placeholders for Venue Session PII; Hamilton Manager+ sees values. This is a Frappe v16 field-level masking mechanism — same pattern `permissions_matrix.md` already uses for Cash Drop and Cash Reconciliation. **What `mask: 1` does:** UI shows a placeholder (e.g. `***`) for users without permlevel access to the field, but the field itself remains technically readable via API/scripting. **What `permlevel: 1` does (stricter):** the field is fully blocked at the permission layer — not even returned in API responses for unauthorized roles.
- **`permlevel: 1` (full blocking) for `scanner_data`.** Raw ID document data (MRZ scans, ID images) is too sensitive for masked placeholders — operators should not even be able to query the field. Use `permlevel: 1` here, not `mask: 1`. See DEC-021 (field-masking decision) for the underlying invariant.
- **Encryption-at-rest for `scanner_data`.** The field that should never persist long-term, but if it does even briefly, it's encrypted.
- **Audit log.** Frappe's built-in document audit trail captures writes; reads aren't tracked by default but can be added with a custom hook if a regulator ever asks.

### Specific to Hamilton's hospitality-staff context

Operators are in a position of trust with respect to customer privacy. Under-trained employees are a breach vector. PIPEDA Principle 7's "appropriate safeguards" is interpreted to include training.

**Operator privacy-and-confidentiality training should be a documented part of onboarding** — a 1-pager covering:
- What may be discussed outside work, what may not
- How to handle a customer's data-access request
- What to do if an Operator suspects another Operator is mishandling data

This is a documentation and onboarding-process item, not a code item. But it's required by PIPEDA before PII collection begins.

---

## 6. Data Residency — Live Database Region

### PIPEDA doesn't mandate Canadian residency

Personal information may be transferred outside Canada for processing, subject to two obligations:

1. **Comparable protection.** The receiving organization must provide protection equivalent to PIPEDA's standards. In practice this is achieved through a written **Data Processing Agreement (DPA)** with the foreign processor. Hamilton + Frappe Cloud need a DPA; Hamilton + Fiserv need one; any future cloud / SaaS service handling Hamilton's PII needs one.
2. **Notice to affected individuals.** Hamilton's privacy notice (the public-facing privacy policy + any in-product disclosure at PII collection) must inform individuals that their data may be transferred to foreign jurisdictions for processing AND that data may be accessed by courts, law enforcement, and national-security authorities in those jurisdictions.

### ⚠️ Frappe Cloud region availability — material finding

Per the public Frappe Cloud documentation and recent searches, available regions are:
- Mumbai (`ap-south-1`)
- Frankfurt (`eu-central-1`)
- Bahrain
- Cape Town
- N. Virginia (`us-east-1`)
- Plus Oracle Cloud Infrastructure (OCI) variants

**No Canadian region (`ca-central-1` / Montreal) appears in Frappe Cloud's public region list.** This contradicts an earlier assumption and is a material finding — if Chris wanted Canadian data residency for the live database, **Frappe Cloud may not support it on the current plan tier.** This needs confirmation with Frappe support before assuming otherwise.

### Region comparison for Hamilton's actual options

| Region | PIPEDA Implications | Practical |
|---|---|---|
| `us-east-1` (N. Virginia) | Cross-border to US. Requires notice, requires DPA, US Cloud Act / law-enforcement access disclosure. | Lowest latency from Hamilton, ON. **Most likely the right choice if Canadian region isn't available.** |
| `eu-central-1` (Frankfurt) | Cross-border to EU. EU has GDPR (stronger than PIPEDA), so privacy bar is met. | Defensible but slower latency. |
| `ap-south-1` (Mumbai) | Cross-border to India. India's Digital Personal Data Protection Act 2023 creates parallel obligations. | Default for Frappe but **worst privacy optics**; live DB here would be harder to defend in a privacy review. |
| `ca-central-1` (Montreal) — IF Frappe adds it | Canadian residency. Privacy notice can omit cross-border transfer language for the live DB. **Best optics.** | **May not be available** on current Frappe Cloud plans. Confirm with Frappe support. |

### Recommendation for Hamilton

1. **First choice:** `ca-central-1` if Frappe supports it. Open a support ticket with Frappe to confirm availability and pricing tier.
2. **Realistic second choice:** `us-east-1`. Lowest latency to Ontario, well-established privacy regime, easiest to obtain a DPA from a US-based processor.
3. **Backup region** (per the existing T0-FC-2 task in the inbox): also `ca-central-1` if available, otherwise `us-east-1`.
4. **Privacy notice** must mention Frappe Cloud as a processor + region of processing + cross-border-access disclosure. Boilerplate language is available from law firms; generic GDPR-style notices need adaptation for PIPEDA's specifics.

### Important caveat

The cross-border-transfer disclosure is required even if data **never leaves Canada in practice** — operationally Hamilton's data may still cross borders for support tickets, monitoring, or developer access from Frappe's own staff (potentially in India). The notice must reflect the realistic data flow, not just the storage location.

### Other cross-border processors to disclose

- **Fiserv** (merchant processor, MID 1131224). US infrastructure. Hamilton's cardholder PII (name on card via auth metadata, last-4, brand) crosses to the US for every Card transaction. Privacy notice MUST mention US transfer of payment data and acknowledge US Cloud Act / law-enforcement access.
- **Any future ID-scanner vendor** (see Section 7).
- **Any future SaaS service** handling Hamilton's PII (analytics, CRM, marketing, etc.).

---

## 7. ID-Scanning Feature — Specific Implications

If Hamilton ever adds ID-scanning (whether for age verification at admission or for member sign-up), the privacy obligations escalate substantially.

### AGCO context

Ontario's Alcohol and Gaming Commission requires age verification for licensed establishments (Hamilton may or may not be AGCO-licensed depending on whether liquor is served — verify before this becomes operative). AGCO accepts:
- Ontario Driver's Licence
- Canadian Passport
- Canadian Citizenship Card
- Canadian Armed Forces ID
- LCBO BYID card
- Secure Indian Status Card
- Permanent Resident Card
- Photo Card under the Photo Card Act 2008
- Foreign passports / EU national ID

**AGCO does NOT regulate ID retention** — that's PIPEDA's domain. So even though regulation says "verify age," PIPEDA says "don't keep more than you need."

### Industry context

ID-scanner vendors (Patronscan, IDScan.net) market to Canadian bars / nightclubs. Their typical workflow: scan → verify against age threshold → **store scan + customer info indefinitely for "blacklist" purposes.** This default retention pattern is **PIPEDA-non-compliant** for most Canadian deployments — it violates Principle 4 (limiting collection) and Principle 5 (limiting retention).

If Hamilton ever shops for an ID scanner, asking "do you delete the scan after verification?" is a hard requirement, not a nice-to-have.

### Hamilton-specific guidance for ID scanning

1. **Scan, verify, delete.** Process the scan in memory, extract the boolean "is this person 18+ / 19+ / 21+", retain only the boolean. The raw scan blob (`scanner_data` field) should be deleted within 1 hour, ideally within minutes.

2. **Consent at the moment of scan.** Operator UI must show a consent prompt: *"ID scan is for age verification only. Image will be deleted after verification. By continuing, you consent."* Customer must affirm. Consent is recorded as a boolean + timestamp on the Venue Session.

3. **Block-list separation.** If Hamilton needs to remember a problem customer (`block_status`), DO NOT keep the ID scan as the matching mechanism. Store a hashed identifier (one-way hash of name + DOB) that lets Hamilton recognize a returning blocked person without storing the raw ID. This is a PIPEDA "use anonymization where possible" win.

4. **Scanner choice matters.** Off-the-shelf scanners often store data on vendor cloud infrastructure outside Hamilton's control. Hamilton needs to:
   - Verify that the scanner's data flow doesn't transit a third-party cloud, OR
   - Ensure a DPA is in place with the scanner vendor.
   - Self-hosted scanners (just an ID reader + Hamilton's own software) avoid the third-party-processor problem entirely.

5. **AGCO interaction (if applicable):** AGCO doesn't require Hamilton to retain scan data. The ID is shown, age is verified, that's it. There's no regulatory reason to keep the scan beyond verification.

### Pre-ID-scanner-launch checklist

- Privacy notice updated with ID-scanning section (what's collected, why, how long retained).
- Operator training on the consent workflow.
- `scanner_data` field's `permlevel: 1` (full blocking, not just `mask: 1`) + encryption-at-rest locked in. This work would extend Task 25 item 7 (sensitive fields enumeration) in `docs/permissions_matrix.md`.
- Automated purge of `scanner_data` (Frappe Scheduler Job that deletes any `scanner_data` older than 1 hour).
- DPA with scanner vendor if any third-party hardware/software is involved.
- Breach-response plan updated: "what we do if a scanner image is leaked" — highly sensitive, almost certainly a reportable breach.

---

## 8. Customer-Perceived Sensitivity — Risk Amplification

> **Important — terminology clarification.** Hamilton is **not** classified as "adult" by any government body, payment network, or regulator. Hamilton operates as a standard commercial business — a standard merchant under Fiserv (R-008 explicitly downgraded the original assumption of high-risk classification), under PIPEDA without any industry-specific carve-out, and AGCO age-verification (if licensed) treats Hamilton like any other licensed establishment. The sensitivity discussion below is about **how customers may perceive attendance information being disclosed**, not about any formal classification of Hamilton itself.

The lack of formal classification does not change the privacy law that applies, but customer-perceived sensitivity of attendance amplifies Hamilton's real-risk-of-significant-harm calculation in four ways:

1. **Significant-harm threshold is easier to meet.** A breach exposing customer attendance at a venue where attendance is reputationally sensitive plausibly meets "humiliation, damage to reputation or relationships" for many customers, even without financial impact. This means more breaches must be reported even when they'd be sub-threshold for a generic retailer.

2. **Hostile-attack risk is higher.** Data breaches at venues whose customer lists carry reputational risk are a known target for blackmail / extortion (Ashley Madison 2015 is the canonical case — same threat model, regardless of how that company was classified). Hamilton's safeguards must be calibrated for this threat model — the `scanner_data` field's "delete after verify" rule is critical specifically because retained ID images would be a high-value extortion target.

3. **Customer expectations are higher.** Customers at venues where attendance is reputationally sensitive expect more confidentiality than customers at a coffee shop. PIPEDA doesn't formally raise the standard, but Hamilton's privacy notice should reflect this expectation: explicit commitment to anonymous walk-in by default, explicit description of what data is collected when (member sign-up, age verification, dispute response), explicit retention windows.

4. **Regulator scrutiny is potentially higher.** The OPC may give heightened attention to breach reports from businesses whose customer attendance is reputationally sensitive, given the harm profile. Not formal policy, just operational reality.

---

## 9. Pre-PII-Collection Blockers (Priority Order)

The day Hamilton (or Philadelphia, or any future PII-collecting venue) starts populating any of the eight fields, these items must already be in place:

| # | Item | Type | Status |
|---|---|---|---|
| 1 | **Field-masking implemented for Venue Session PII.** `mask: 1` on the six PII fields (full_name, date_of_birth, member_id, identity_method, block_status, arrears_amount, eligibility_snapshot) + `permlevel: 1` on `scanner_data` + encrypt-at-rest for `scanner_data`. See DEC-021. | **Code** | Not yet scoped — would extend Task 25 item 7 (sensitive fields enumeration) in `docs/permissions_matrix.md`, which today covers Cash Drop / Cash Reconciliation but NOT Venue Session PII |
| 2 | **Privacy notice posted publicly** on the venue website AND in-venue at admission. Drafted per PIPEDA's openness principle. | Documentation | Not started |
| 3 | **Privacy Officer identified.** Chris by default; document in `docs/venue_rollout_playbook.md`. | Documentation | Implicit; needs formalization |
| 4 | **Retention schedule documented** — per-field, with automated purge mechanism. | Documentation + code (scheduler job) | Not started |
| 5 | **Breach-response runbook** — who decides if reporting is needed, contact paths, log location. | Documentation | Not started |
| 6 | **Operator confidentiality training** as part of onboarding (1-pager). | Documentation + onboarding process | Not started |
| 7 | **Data-Processing Agreements** with Frappe Cloud and Fiserv (and any other cross-border processor). | Contractual | Not verified — Frappe ToS may already cover this |
| 8 | **Live database region confirmed** — `ca-central-1` if Frappe supports it; otherwise `us-east-1` with documented cross-border disclosure. | Operational | **Frappe support ticket needed** to confirm region availability |

**The first item is the only code change. The other seven are documentation, process, and contractual items — but they're equally non-optional under PIPEDA.**

---

## 10. Summary — What Changes When PII Populates

| Area | Today (Hamilton, anonymous walk-in) | Day 1 of PII-populated venue |
|---|---|---|
| PIPEDA applicability | Yes (commercial, Canadian) | Yes — same |
| Breach notification | Required for breaches with real risk of significant harm. Currently: minimal PII to breach. | Required — bar easier to meet given the customer-perceived-sensitivity harm profile (Section 8). |
| Breach record-keeping | Required for all breaches (24 months). | Same. |
| Retention schedule | Light — mostly transactional records (6-year CRA window). | Required: written, per-field, with automated purge. Add to `docs/`. |
| Minimum-necessary review | Trivial — none collected. | Active discipline: every PII field needs a documented justification; over-collection = breach risk. |
| Cross-border notice | None needed (no PII to transfer). | Required: privacy notice must mention Frappe region + Fiserv US payment processing + any future merchant. |
| Employee training | Implicit. | Documented privacy training as part of onboarding. |
| Field-masking implementation | Not yet scoped — fields exist but no `mask: 1`/`permlevel: 1` restrictions. Would extend Task 25 item 7 in `docs/permissions_matrix.md`. See DEC-021. | MANDATORY: `mask: 1` on the 6 masked PII fields + `permlevel: 1` (full blocking) on `scanner_data` + encrypt-at-rest for `scanner_data`. **Must land BEFORE PII lands.** |
| Privacy Officer | Not formally identified. | Required (can be Chris). |
| Privacy notice (public-facing) | Generic / minimal. | Detailed: what's collected, why, where it goes, retention, access rights, complaints. |
| Frappe Cloud region | Default; cross-border implicit but no PII to disclose. | **Region confirmed + privacy notice updated to disclose.** |

---

## Sources

### PIPEDA — basics, principles, retention

- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda_brief/
- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/
- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/
- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/principles/p_use/
- https://www.priv.gc.ca/en/privacy-topics/business-privacy/breaches-and-safeguards/safeguarding-personal-information/gd_rd_201406/
- https://www.priv.gc.ca/media/2038/guide_org_e.pdf
- https://www.listerlawyers.com/blog/understanding-pipeda-requirements-for-businesses-in-ontario/

### Breach notification

- https://www.priv.gc.ca/en/privacy-topics/business-privacy/breaches-and-safeguards/privacy-breaches-at-your-business/gd_pb_201810/
- https://www.nortonrosefulbright.com/en/knowledge/publications/ac3ee5c4/mandatory-privacy-breach-reporting-requirements-coming-into-force-in-canada-november-1
- https://www.mccarthy.ca/en/insights/blogs/techlex/real-risk-significant-harm-new-guidance-privacy-commissioner-canada
- https://gowlingwlg.com/en/insights-resources/articles/2023/canadian-privacy-breach-notification-requirements

### Cross-border data residency

- https://www.priv.gc.ca/en/privacy-topics/airports-and-borders/gl_dab_090127/
- https://captaincompliance.com/education/pipeda-cross-border-transfer/
- https://www.priv.gc.ca/en/opc-actions-and-decisions/research/explore-privacy-research/2021/tbdf_scassa_2105/
- https://www.blg.com/en/insights/2026/03/canada-privacy-laws-what-us-businesses-need-to-know

### Ontario provincial laws (applicability check)

- https://www.ontario.ca/laws/statute/90f31
- https://www.ipc.on.ca/en/fippa-mfippa-privacy-organizations
- https://www.ontario.ca/laws/statute/04p03
- https://crpo.ca/resource-articles/personal-health-information-protection-act-phipa/
- https://www.ontario.ca/page/personal-information-and-privacy-rules
- https://en.wikipedia.org/wiki/Personal_Health_Information_Protection_Act

### ID scanning / hospitality

- https://www.agco.ca/en/general/photo-identification

### Frappe Cloud regions

- https://frappe.io/cloud
- https://frappe.io/cloud/servers
- https://docs.frappe.io/cloud/servers/provider-comparision

---

*Document compiled from two parallel research outputs (2026-04-30). Material new finding from second pass: Frappe Cloud's public region list does not include `ca-central-1`. This supersedes the earlier assumption that Canadian-region hosting was a default option. Confirm with Frappe support before relying on Canadian residency in privacy notice or DPA language.*
