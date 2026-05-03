# Security Hardening Audit — 2026-05-04

**Scope.** Multi-source security audit using four security skill packages
installed 2026-05-04:

  - Trail of Bits Skills (trailofbits/skills) — 16 skills loaded
    (audit-context-building, semgrep, sarif-parsing, supply-chain-risk-auditor,
    insecure-defaults, modern-python, sharp-edges, constant-time-analysis,
    zeroize-audit, variant-analysis, spec-to-code-compliance, entry-point-analyzer,
    differential-review, agentic-actions-auditor, fp-check, second-opinion)
  - OWASP 2025/2026 (agamm/claude-code-owasp) — 1 skill loaded
    (owasp-security; covers OWASP Top 10:2025, ASVS 5.0, LLM Top 10 2025,
    Agentic AI Top 10 2026)
  - Cybersecurity (AgriciDaniel/claude-cybersecurity) — 1 skill loaded
    (cybersecurity; 8-dimension audit + STRIDE + language references)
  - Security Auditor (wrsmith108/claude-skill-security-auditor) — 1 skill loaded
    (npm-audit oriented; limited applicability — Hamilton is Python/Frappe.
    Used as a check that we have no JavaScript runtime deps to audit. Confirmed:
    no package.json / package-lock.json in `hamilton_erp/`. The `asset_board.js`
    file imports nothing and runs inside Frappe's bundled jQuery/Bootstrap.)

Cross-referenced against `decisions_log.md`, `lessons_learned.md`,
`risk_register.md`, and the prior security review
(`docs/audits/security_review_2026_05_full_codebase.md`, 2026-05-01).
The Frappe skills audit referenced in the audit prompt
(`docs/audits/frappe_skills_audit_2026-05-04.md`) does not exist on disk
at audit time (2026-05-04 ~3:50pm EST); cross-reference was therefore
limited to existing artifacts. Only NEW findings are listed below — items
already covered by an existing DEC, LL, R-NNN, or the 2026-05-01 review
are catalogued in the "Findings already covered" section rather than
re-raised.

**Codebase head.** `e99feec8aceb04e206566cf90b71b001df852660`

## Summary

| Severity      | New findings |
|---------------|--------------|
| Critical      | 0            |
| High          | 1            |
| Medium        | 4            |
| Low           | 4            |
| Informational | 3            |
| **Total**     | **12**       |

The High finding is a Phase-2 forward-looking risk: today's realtime
broadcast surface does not honour PII boundaries, so the day Philadelphia
populates `Venue Session.full_name` (the trigger condition for R-007) the
PII will leak to ALL connected operators via the `hamilton_asset_status_changed`
channel even after the permlevel mask lands on the schema. That is the only
finding that becomes a true vulnerability in production; everything else is
defense-in-depth or operational hygiene.

## Findings

### S2.1 — Realtime broadcast leaks session-linked PII once R-007 fields are populated   `High`

- **Source skills.** owasp-security (A01 Broken Access Control, A02 Cryptographic
  Failures / data-in-transit scoping); cybersecurity (Information Disclosure
  STRIDE category); tob-entry-point-analyzer (broadcast surface as exfil sink).
- **OWASP / CWE.** OWASP A01:2025 (Broken Access Control), CWE-359 (Exposure of
  Private Personal Information to Unauthorized Actor), CWE-200 (Generic
  Information Exposure).
- **Location.** `hamilton_erp/realtime.py:84-89` (`publish_status_change`) and
  `hamilton_erp/api.py:42-50` (`on_sales_invoice_submit`).
- **Pattern.** `publish_status_change` calls
  `frappe.publish_realtime("hamilton_asset_status_changed", row, after_commit=True)`
  with NO `user=` / `room=` / `event_type=` parameter. The default is a global
  broadcast: every authenticated socket subscribed to the event receives the
  payload. The payload includes `current_session` (the Venue Session PK).
  Any subscriber who can resolve a Venue Session name to its row sees its
  fields; today the operator role can read the session row at permlevel 0 and
  HIGH-1 / R-007 in the prior audit confirms `full_name` and `date_of_birth`
  ride at permlevel 0. After R-007 ships and PII fields move to permlevel 1,
  a second hardening pass is required: either narrow the realtime channel to
  the operating-shift user, or strip `current_session` from the broadcast
  payload entirely (only the asset row's status fields are needed for the
  Asset Board re-render; the session linkage is already enriched per-tile by
  `get_asset_board_data`).
- **Impact.** Today: low (Hamilton has no PII populated; `full_name` is null
  for walk-ins). At Philadelphia rollout (R-007 trigger): every connected
  operator's browser console / Network tab will show member full names and
  DOBs of every member in flight, regardless of whether that operator is
  even on shift. Defeats the permlevel mask R-007 will install.
- **Recommendation.** Two-part fix, applied before Philadelphia populates
  `full_name`:
  1. Drop `current_session` from the `publish_status_change` payload — the
     Asset Board does not consume it on the wire today (the polled
     `get_asset_board_data` enriches per-tile).
  2. If `current_session` must remain on the wire for a future feature, scope
     the publish to the on-shift user via `user=current_shift_operator` or
     introduce a per-venue room. The same pattern applies to
     `on_sales_invoice_submit` (`api.py:42`), which already correctly uses
     `user=frappe.session.user`.
- **Why this is new.** R-007 covers the schema permlevel (data-at-rest);
  this finding is the data-in-transit broadcast that the permlevel mask
  cannot enforce. No DEC/LL/R/audit currently scopes the realtime payload.

---

### S3.1 — `get_asset_board_data` lacks rate limiting   `Medium`

- **Source skills.** owasp-security (A06 Insecure Design / rate limiting,
  ASVS L1 4.1.1); cybersecurity (DoS dimension); tob-insecure-defaults.
- **OWASP / CWE.** OWASP A06:2025, CWE-770 (Allocation of Resources Without
  Limits or Throttling), CWE-799 (Improper Control of Interaction Frequency).
- **Location.** `hamilton_erp/api.py:59-198` (`get_asset_board_data`).
- **Pattern.** DEC-074 added `@rate_limit(60/60s)` to all mutating endpoints.
  `get_asset_board_data` is a GET and was excluded by design. It is the
  hottest read endpoint in the system (called every initial board mount and
  on every realtime refresh fallback), runs four DB round trips per call,
  and has no per-IP throttle. A compromised operator session or a runaway
  client polling loop can saturate MariaDB with full-table scans of
  `tabVenue Asset` (LIMIT 500) plus three batched lookups indefinitely.
- **Impact.** No data-loss risk; pure availability risk. A misconfigured
  Asset Board polling loop on one terminal can degrade response time for
  every other operator. At Phase 2 with multiple venues on a shared bench
  (DEC-073 isolates per-bench, but the abuse from inside one venue is
  not isolated), the impact compounds.
- **Recommendation.** Add `@rate_limit(limit=120, seconds=60, key=...)` to
  `get_asset_board_data`. 120/min is generous (board polls ~once/30s per
  operator under normal load) but bounds runaway loops. Match the
  per-IP keying already used by the existing endpoints.
- **Why this is new.** DEC-074 explicitly limits its scope to "mutating
  whitelisted endpoints" and `get_asset_board_data` is read-only. Not in
  R-NNN, no LL.

---

### S3.2 — `submit_retail_sale` elevation has no dedicated audit row   `Medium`

- **Source skills.** owasp-security (A09 Security Logging Failures, ASVS L2
  7.1.1); cybersecurity (audit dimension, repudiation under STRIDE);
  tob-insecure-defaults (privilege elevation hygiene).
- **OWASP / CWE.** OWASP A09:2025, CWE-778 (Insufficient Logging), CWE-279
  (Incorrect Execution-Assigned Permissions).
- **Location.** `hamilton_erp/api.py:629-736` (`submit_retail_sale`,
  `frappe.set_user("Administrator")` at line 633, restored at line 736).
- **Pattern.** The retail-cart flow elevates to `Administrator` for the
  duration of the Sales Invoice insert because Hamilton Operator does not
  hold direct SI write perms. The audit trail captures the real operator
  in `Sales Invoice.remarks` ("Recorded via cart by {user}") and via the
  `db_set("owner", real_user)` override. There is NO dedicated log entry
  recording the elevation event itself, with timestamp, original user,
  reason, and resulting SI name. A System Manager who later removes or
  edits the `remarks` line — no DocPerm prevents that edit — erases the
  only durable signal that an operator-driven sale ever occurred under
  elevated credentials. Frappe's `track_changes:1` on Sales Invoice will
  capture the remarks-field edit, but a reviewer has to know to look.
- **Impact.** Forensic gap: in a dispute about who actually rang up
  invoice X, the `remarks` line is the only first-party Hamilton signal,
  and it is mutable. The `creation` / `modified_by` columns on SI both
  point at `Administrator` (the elevated session), which is misleading.
- **Recommendation.** Insert one immutable audit row per elevation, before
  the `si.insert()` call, into a small log doctype (`Hamilton Cart Audit
  Log` or extend `Asset Status Log` with a `cart_invoice` field): record
  `real_user`, `pos_profile`, `cart_total`, `payment_method`, `timestamp`,
  and (after submit) `sales_invoice`. Operators have read-only / admins
  no-delete on the row. This is defense-in-depth above the existing
  `remarks` field.
- **Why this is new.** DEC-066 covers admin-correction elevation (Hamilton
  Board Correction); it does NOT cover the cart's elevation to
  Administrator. Prior audit MEDIUM-1 flagged System Manager as a member
  of `HAMILTON_RETAIL_SALE_ROLES` but did not address audit-trail
  hardening for the elevation itself.

---

### S3.3 — Realtime publish payload is unauthenticated on receive   `Medium`

- **Source skills.** owasp-security (A07 Auth failures, A01); cybersecurity
  (Spoofing / Tampering STRIDE); tob-agentic-actions-auditor (untrusted
  payload sinks).
- **OWASP / CWE.** OWASP A07:2025, CWE-345 (Insufficient Verification of
  Data Authenticity), CWE-602 (Client-Side Enforcement of Server-Side
  Security).
- **Location.** `hamilton_erp/page/asset_board/asset_board.js`, the
  realtime listener that consumes `hamilton_asset_status_changed` (around
  the `frappe.realtime.on(...)` registration — search by event name), and
  `hamilton_erp/realtime.py:86-89` on the publisher side.
- **Pattern.** `frappe.publish_realtime` payloads are delivered through
  Frappe's socketio bus. Frappe authenticates the *socket connection*
  but does not sign or HMAC the payload, so any code path that can call
  `publish_realtime("hamilton_asset_status_changed", ...)` — including a
  rogue Server Script, a compromised cron job, or a future buggy doc_event
  — can spoof an asset state change to every connected operator. The JS
  listener accepts the payload as ground truth and re-renders the tile.
  Server-side state remains correct (DB is unchanged), but operators may
  act on the spoofed state (mark a still-occupied tile clean, etc.) until
  the next polled refresh.
- **Impact.** Low likelihood (requires existing code-execution access),
  bounded blast radius (de-syncs operator UI, does not corrupt DB), but
  no detection: the spoofed event leaves no trace in `Asset Status Log`.
- **Recommendation.** Two options, in order of effort:
  1. Cheap: have the JS listener re-fetch the affected asset via
     `frappe.db.get_value("Venue Asset", row.name, [...])` before
     committing the tile re-render. One extra round trip per event,
     but the truth lives in the DB. Already partially done for the
     polled refresh path.
  2. Better: include a server-derived nonce or HMAC in the payload and
     verify it client-side. Frappe does not ship this primitive; would
     need a small helper in `realtime.py`.
  Option 1 is the right cost/value trade today.
- **Why this is new.** No DEC/LL/R/audit covers realtime payload integrity.

---

### S3.4 — No security linter (Bandit / Ruff `S` ruleset) in CI   `Medium`

- **Source skills.** tob-modern-python (Python toolchain hygiene); cybersecurity
  (CI/CD dimension); owasp-security (A03 Supply Chain Failures, ASVS V14).
- **OWASP / CWE.** OWASP A03:2025, OWASP A05:2025 (Security Misconfiguration).
- **Location.** `pyproject.toml:39-49` (`[tool.ruff.lint] select = ["F", "E", "W", "I"]`).
- **Pattern.** Ruff lint is enabled with the `F` (pyflakes), `E` (pycodestyle
  errors), `W` (warnings), and `I` (isort) rule families. The `S` family
  (`flake8-bandit`-equivalent — covers `assert`, `subprocess` shell=True,
  unsafe deserialization, weak crypto, hardcoded passwords, etc.) is NOT
  selected. There is also no separate Bandit invocation in CI. This means
  a future PR can introduce `subprocess.run(..., shell=True)`, an unsafe
  code-execution primitive, or untrusted-deserialization sinks and pass
  lint without a security-test signal. The custom AST scanner in
  `test_security_audit.py` covers the `frappe.db.sql` + f-string case
  specifically but not the broader bandit ruleset.
- **Impact.** Risk is regression-shaped: today's code is clean (no
  unsafe-deserialization, `subprocess`, code-execution-via-string, or
  `shell=True` in the package per the audit grep at 2026-05-04 15:45).
  Tomorrow's code review may miss a new instance.
- **Recommendation.** Add `"S"` to the Ruff `select` list. Carve out the
  test directory if `assert` triggers (`per-file-ignores = { "test_*.py" = ["S101"] }`).
  Run on the next CI cycle to surface any pre-existing matches and triage
  them in a single follow-up PR.
- **Why this is new.** No DEC/LL/R/audit covers static-analysis ruleset
  scope. `LL-035` covers adversarial test coverage but not lint config.

---

### S4.1 — Logger calls in `assign_asset_to_session` mix f-string and `.format()`   `Low`

- **Source skills.** tob-sharp-edges (footgun pattern); cybersecurity (logging
  failures dimension).
- **OWASP / CWE.** CWE-117 (Improper Output Neutralization for Logs); also
  rated low by the prior audit's no-finding on log injection because the
  payload eventually reaches the rotating log only.
- **Location.** `hamilton_erp/api.py:299-303`.
- **Pattern.** The log line interleaves f-string interpolation and a
  trailing `.format()` call. The `!r` on the f-string side correctly
  renders user input via `repr()` (defeats line-break injection). The
  `.format()` call then re-interprets the *result* of the concatenated
  string, which contains `{sales_invoice!r}` literal text from the
  f-string — except both interpolations have already collapsed to literals
  before `.format()` runs, so it works. A future edit that adds another
  `{name}` placeholder to the f-string side without noticing the
  `.format()` chain will silently break or, worse, allow format-string
  side effects (`{0.__class__.__bases__[0]...}` style attribute walking
  on attacker-controlled keys).
- **Impact.** No exploit today. Footgun-class — a small refactor can
  introduce CWE-134 (Use of Externally-Controlled Format String) if the
  developer doesn't realize the `.format()` is still wired in.
- **Recommendation.** Collapse to a single f-string covering the whole
  message (no trailing `.format()`). No behaviour change; eliminates the
  dual-interpolation footgun.
- **Why this is new.** Prior audit's LOW findings cover broad-except logging
  and timestamps; this is a narrower string-formatting brittleness.

---

### S4.2 — `_create_session` retry catches by stringifying the exception message   `Low`

- **Source skills.** tob-sharp-edges (i18n-fragile error matching);
  owasp-security Python pitfalls section.
- **OWASP / CWE.** CWE-754 (Improper Check for Unusual or Exceptional
  Conditions).
- **Location.** `hamilton_erp/lifecycle.py:225-234`.
- **Pattern.** `if "session_number" not in str(exc): raise` — the retry
  loop decides whether the unique-constraint violation was on
  `session_number` (retry) or some other unique field (re-raise) by
  substring-matching the exception's stringified message. Frappe wraps
  MariaDB errors in `frappe._()`-translated text; on a non-en-US locale
  the message can be "Le champ Numéro de session doit être unique" or
  similar, depending on translations. The string match would then fail,
  and a `session_number` collision would re-raise instead of retry, even
  though it's the very case the loop was built for.
- **Impact.** Hamilton runs on `en-US` today, so this is dormant. The
  moment a French-Canadian operator session sets `frappe.lang = "fr"` (a
  PIPEDA-likely scenario for the Quebec / Toronto market expansion),
  retries fail at the wrong branch and operators see "Session number
  collision — please try again" on first attempt instead of the silent
  retry.
- **Recommendation.** Match on a stable signal — the constraint name from
  MariaDB or the `frappe.UniqueValidationError` field metadata if the
  Frappe API exposes it. As a fallback, parse the `unique_keys` attribute
  if present on the exception, or check `len(...).args` for a structured
  shape. Document the chosen signal as locale-stable.
- **Why this is new.** No LL covers locale-fragile error matching.

---

### S4.3 — `_db_max_seq_for_prefix` swallows malformed-row case with only `frappe.log_error`   `Low`

- **Source skills.** owasp-security (A09 logging); cybersecurity (data
  integrity).
- **OWASP / CWE.** CWE-754, CWE-209 (Information Exposure Through Error
  Messages — inverted: not exposing enough operationally).
- **Location.** `hamilton_erp/lifecycle.py:594-619`.
- **Pattern.** When a malformed `session_number` is found in the DB, the
  function logs to Error Log and returns 0. The next INCR yields 1, which
  could collide with already-persisted rows. The retry loop in
  `_create_session` catches the resulting UniqueValidationError, but the
  underlying data corruption (a malformed session_number row) goes
  unfixed — and Error Log entries are easy to miss in a 200-row Error
  Log table.
- **Impact.** No security exposure; operational integrity. If something
  ever writes a malformed `session_number`, the system self-heals by
  retrying but never raises an alarm beyond a single Error Log row.
- **Recommendation.** Raise a `frappe.ValidationError` *after* logging,
  scoped to the cold-start path so it doesn't break steady-state. OR add
  a Notification rule on Error Log title contains "Malformed session_number"
  so Chris is paged on the first occurrence.
- **Why this is new.** Prior audit's LOW-3 covers the broad-except in
  `_next_session_number`'s outer wrapper. This is a different code path
  inside the cold-fallback helper.

---

### S4.4 — `dependencies = []` in `pyproject.toml` declares no runtime SBOM   `Low`

- **Source skills.** tob-supply-chain-risk-auditor; owasp-security A03 Supply
  Chain.
- **OWASP / CWE.** OWASP A03:2025 (Supply Chain Failures), OWASP A06:2025
  (Vulnerable Components).
- **Location.** `pyproject.toml:10` (`dependencies = []`).
- **Pattern.** The `[project] dependencies` array is empty. Frappe and
  ERPNext are declared via `[tool.bench.frappe-dependencies]` (a Frappe-
  specific section honoured by `bench install-app`, not by `pip` or any
  standard Python tool). `hypothesis` is the only optional/test dep and
  is unpinned (`test = ["hypothesis"]`, no version constraint). `pip-audit`
  / `safety` / GitHub Dependabot — none of which understand
  `tool.bench.frappe-dependencies` — see an empty dependency tree and
  produce a clean report.
- **Impact.** Hamilton inherits whatever Frappe/ERPNext version the bench
  has installed. A CVE in Frappe v16.13.2 (the version pinned in the
  `extend_doctype_class` UPGRADE CHECKPOINT) is invisible to standard
  Python supply-chain tooling.
- **Recommendation.** Either (a) duplicate the Frappe/ERPNext version
  pins into `[project] dependencies` so `pip-audit` can see them, or (b)
  add a CI step that runs `pip list --format=json` from inside the bench
  venv and feeds the result to `pip-audit --requirement -`. Option (b)
  is more accurate. Add a SECURITY-DEPS.md note explaining the
  Frappe-specific dependency declaration so future CI authors don't miss
  the gap.
- **Why this is new.** No DEC/LL/R covers supply-chain/SBOM for the app.
  LL-006 covers `frappe-dependencies` correctness but not auditability.

---

### S5.1 — `on_sales_invoice_submit` doc_event fires on every Sales Invoice in the system   `Informational`

- **Source skills.** tob-entry-point-analyzer (event-handler scope);
  owasp-security (LLM06-style excessive scope, mapped to web).
- **OWASP / CWE.** CWE-1188 (Insecure Default Initialization of Resource).
- **Location.** `hamilton_erp/hooks.py:78-82` and `hamilton_erp/api.py:24-50`.
- **Pattern.** The `doc_events` registration is global to the Sales
  Invoice DocType (`{"Sales Invoice": {"on_submit": "hamilton_erp.api.on_sales_invoice_submit"}}`).
  Any Sales Invoice submitted anywhere in the bench (POS, manual desk
  insert, import, future ERPNext flow) runs Hamilton's hook. The hook
  early-returns when no admission item is present (`if not doc.has_admission_item(): return`),
  so the impact is bounded — but every submit pays the cost of the
  `has_admission_item()` scan over child rows. More importantly, a
  future code change to the early-return condition (or a child row
  with `hamilton_is_admission` truthy outside Hamilton's control) would
  fire the realtime publish to whoever submitted the invoice.
- **Impact.** No security impact today. Performance: small per-submit cost.
  Future: tight coupling to ERPNext's SI submit path.
- **Recommendation.** Two options:
  1. Defensive guard at top of `on_sales_invoice_submit`: check
     `doc.pos_profile == HAMILTON_POS_PROFILE` before the admission scan.
     One extra attribute read; bounds the trigger to Hamilton's POS
     surface.
  2. Move to `extend_doctype_class`-driven `on_submit` rather than a
     global doc_event. The override class already exists.
- **Why this is new.** No DEC/LL/R covers doc_event scoping. Prior audit
  LOW-5 covers VenueSession.on_submit being a stub, not the SI hook scope.

---

### S5.2 — Permission gate on `assign_asset_to_session` fires before the no-op return   `Informational`

- **Source skills.** tob-fp-check (verify before flag); owasp-security A04
  (Insecure Design).
- **OWASP / CWE.** Borderline CWE-657 (Violation of Secure Design Principles —
  defense-in-depth-not-applied).
- **Location.** `hamilton_erp/api.py:299-310`.
- **Pattern.** `assign_asset_to_session` is documented as a Phase-1 no-op
  (returns `{"status": "phase_1_disabled", ...}`). It still runs
  `frappe.has_permission("Venue Asset", "write", throw=True)` and writes
  user-supplied parameters to the logger before returning the disabled
  response. A guest / unauthenticated caller would be rejected by the
  permission check (good); an authenticated low-privilege caller without
  Venue Asset write would get a 403 *as if* the endpoint did something.
  This is reasonable behaviour for an endpoint that will eventually be
  active, but it conflicts with the docstring's framing as "logged no-op
  rather than a hard throw". Operators see different error shapes
  depending on their role: low-priv = 403, high-priv = `phase_1_disabled`.
- **Impact.** No vulnerability. UX inconsistency only. Documented here so
  the Phase 2 implementer remembers the role-gate is already in place.
- **Recommendation.** Either drop the `has_permission` call (the endpoint
  does nothing anyway), or — recommended, since it matches Phase 2's
  eventual contract — keep the gate and update the docstring to
  acknowledge "logged-no-op for authorized callers; 403 for unauthorized".
- **Why this is new.** Documentation/contract clarification; not in any
  DEC/LL/R/audit.

---

### S5.3 — No client-side integrity check on cart-line names   `Informational`

- **Source skills.** owasp-security (A08 Software & Data Integrity Failures);
  cybersecurity (Tampering / STRIDE).
- **OWASP / CWE.** OWASP A08:2025, CWE-353 (Missing Support for Integrity
  Check).
- **Location.** `hamilton_erp/page/asset_board/asset_board.js:602-609` and
  `submit_retail_sale` payload contract.
- **Pattern.** The cart sends `{item_code, qty, unit_price}`. Server-side
  rate authority correctly rejects mismatched `unit_price` per
  `submit_retail_sale` (api.py:570-580). The cart payload does NOT include
  `item_name`, so an attacker mutating the cart's display name client-side
  cannot affect the SI (the server fetches `item_name` independently for
  the SI line). However, the cart drawer renders `c.item_name` via
  `escape_html` — XSS-safe — but the display name shown to the operator
  during checkout is whatever the client says, divorced from the
  server-validated `item_code`. A compromised browser extension could
  render "Coke - $2" while the SI being submitted is for `LOCKER-DAY` at
  $5; the operator confirms based on the displayed name and gets a
  surprise on the receipt.
- **Impact.** Theoretical. Requires browser-side compromise of the
  operator's terminal. Hamilton's threat model treats the operator
  terminal as semi-trusted (DEC-005 blind cash assumes the operator can
  read whatever the screen shows). Adding integrity wouldn't hurt, but
  it's not a high-leverage fix.
- **Recommendation.** Make the operator confirmation modal display the
  server-resolved `item_name` (returned in the cash-payment confirmation
  flow) before final commit. Today the modal shows the client-side cart;
  flipping to a server-confirmed shape is straightforward and closes the
  semantic gap.
- **Why this is new.** No DEC/LL/R covers cart display integrity. Prior
  audit's "server-side rate authority" entry (CONFIRMED-SAFE #7) addresses
  rate, not name display.

---

## Findings already covered (NOT flagged)

- PII fields on Venue Session unmasked — see `R-007` and prior audit `HIGH-1`.
- `Comp Admission Log.comp_value` masking — see `R-006` and prior audit `HIGH-2`.
- `HAMILTON_POS_PROFILE` hardcoded — see prior audit `HIGH-3`.
- Cash Reconciliation `system_expected` stub returning 0 — see `R-011` /
  `DEC-069` and prior audit `HIGH-4`.
- `System Manager` in `HAMILTON_RETAIL_SALE_ROLES` — see prior audit `MEDIUM-1`.
- `WALKIN_CUSTOMER` not venue-configurable — see prior audit `MEDIUM-2`.
- `HST_RATE` hardcoded in JS cart preview — see prior audit `MEDIUM-3`.
- Cash Reconciliation cancel/amend not explicit — see prior audit `MEDIUM-4`.
- `frappe.in_test` vs `frappe.local.flags.in_test` — see prior audit `MEDIUM-5`.
- Bare `except Exception:` in `locks.py` — see prior audit `LOW-2`.
- Broad except in `_next_session_number` — see prior audit `LOW-3`.
- `full_name` in `get_asset_board_data` payload — see `R-007` and prior audit `LOW-4`.
- VenueSession.on_submit is a `pass` stub — see prior audit `LOW-5`.
- `frappe.db.commit()` in install hook — see prior audit `LOW-6`.
- SQL injection — confirmed safe; AST-pinned by `test_security_audit.py::TestSQLInjectionSafety`.
- XSS in Asset Board — escape_html applied; pinned by `test_security_audit.py::TestAssetBoardXSS`.
- Three-layer lock correctness — see `DEC-019` and prior audit CONFIRMED-SAFE #5.
- Rate limiting on mutating endpoints — see `DEC-074`.
- `submit_retail_sale` idempotency — see `DEC-067` (T0-1) and `LL-039`.
- Admin-correction audit trail — see `DEC-066` (Hamilton Board Correction).
- Operator self-escalation — `TestNoFrontDeskSelfEscalation` enforces.
- Asset Status Log immutability for operators — CONFIRMED-SAFE #11.
- POS Closing Entry blocked from operators — see `DEC-005` / `DEC-021`.
- Multi-venue isolation at bench level — see `DEC-073`.
- `get_doc_before_save() is None` defensive bypass — see `DEC-070`.
- Cash Drop envelope label print pipeline unbuilt — see `R-012`.
- MATCH list 1% chargeback risk — see `R-009` (Phase 2+).
- No hardcoded credentials in repo — confirmed by prior audit CONFIRMED-SAFE #14.

## Audit limitations

- **Frappe Cloud platform configuration** was not audited. CSP headers,
  TLS termination policy, backup encryption keys, and bench-level
  `nginx.conf` security headers are managed by Frappe Cloud and were
  not in repo scope.
- **Frappe / ERPNext core** was treated as trusted (per `LL-029`). CVEs
  in Frappe v16.x or ERPNext v16.x are not in this audit's scope.
- **Database privileges** at the MariaDB layer (least-privilege user
  for the bench session) were not inspected — also a Frappe Cloud
  platform concern.
- **The npm-audit oriented `security-auditor` skill** had limited
  applicability: the package has no JavaScript runtime dependencies,
  no `package.json`, and no `package-lock.json`. The skill served only
  as a confirmation that no JS supply chain exists to audit. Frappe's
  bundled Bootstrap / jQuery / socketio assets are platform-managed.
- **The Trail of Bits constant-time-analysis and zeroize-audit skills**
  were loaded but not actively applied: the codebase does no custom
  cryptography (auth and password hashing are delegated entirely to
  Frappe core). No findings expected from those lenses; reading their
  SKILL.md confirmed the pattern set is for C/C++/Rust crypto code.
- **The Trail of Bits agentic-actions-auditor skill** was loaded; no
  GitHub Actions workflows in the repo target Claude Code or other AI
  inference (`.github/workflows/` not present at audit time).
- **Heavy static-analysis runners** (Semgrep CLI, CodeQL) were NOT
  executed per the audit prompt's instructions. Their SKILL.md
  checklists were applied as conceptual lenses; running them as a
  follow-up is recommended for a quarterly cadence.
- **The Frappe skills audit** referenced in the prompt
  (`docs/audits/frappe_skills_audit_2026-05-04.md`) does not exist on
  disk. Cross-reference therefore could not deduplicate against it; if
  it lands later, re-walk this audit's findings against it and collapse
  any overlap.
- **Items needing deeper review:** S2.1 (realtime PII broadcast) should
  be verified by a live socketio capture against a populated Venue
  Session row before Philadelphia rollout. S3.2 (cart elevation audit
  row) should be designed alongside DEC-066's Hamilton Board Correction
  to share doctype patterns.
