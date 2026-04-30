# Security Policy

## Reporting a vulnerability

If you've discovered a security issue in Hamilton ERP, please report it privately so we can fix it before public disclosure.

**Where to report:** Email **csrnicek@yahoo.com** with subject `[hamilton_erp security]` and the vulnerability details. Use PGP if you have it; if not, plain text is fine — Hamilton ERP is a small project and a clear written description is more useful than encrypted noise.

**Do NOT report security issues via:**
- GitHub issues (public)
- Pull requests (public, even if draft)
- Slack, Discord, or any chat platform
- Comments on existing PRs / commits / discussions

**What to include in the report:**
- A description of the vulnerability and its impact (what an attacker could do)
- Steps to reproduce, including the affected file path or endpoint
- Your view on severity (low / medium / high / critical)
- Whether the vulnerability is already public knowledge — if so, where
- (Optional) A proposed fix or mitigation

## Response expectations

Hamilton ERP is a single-developer project. Response targets are best-effort:

| Severity | First acknowledgement | Resolution target |
|---|---|---|
| Critical (data loss, RCE, auth bypass) | 24 hours | 7 days |
| High (privilege escalation, sensitive data exposure) | 72 hours | 30 days |
| Medium (information disclosure, CSRF, etc.) | 7 days | 90 days |
| Low (defense-in-depth gaps, hardening suggestions) | 14 days | next release window |

These are targets, not contracts. If you've sent a report and not heard back within the first-acknowledgement window, send a follow-up — emails do go to spam.

## Supported versions

| Version | Status |
|---|---|
| `main` (HEAD) | **Supported.** Security fixes land here first. |
| `0.1.x` (pre-release) | **Supported.** Hamilton ERP is currently pre-1.0 (`hooks.py:app_version = "0.1.0"`). |
| Tagged releases | None yet. |
| Forks | Not supported. Contact the fork maintainer. |

When Hamilton ERP cuts a 1.0 release, this section will be updated with a longer support matrix.

## Scope

### In scope
- Code in this repository (`hamilton_erp/` and subdirectories)
- Configuration committed to this repository (e.g. `.github/workflows/`, `pyproject.toml`)
- Documentation that, if exploited, leaks sensitive operational detail (API endpoint behaviour, locking mechanics, etc.)

### Out of scope
- **Frappe / ERPNext core vulnerabilities.** Report those to [the Frappe security team](https://frappe.io/security) instead. Hamilton ERP can mitigate but not fix upstream issues.
- **Frappe Cloud platform issues** (Redis, MariaDB, network, deploy infrastructure). Report to Frappe Cloud support.
- **Self-XSS** that requires the operator to paste attacker-controlled JavaScript into their own browser console.
- **Denial-of-service via volume** (e.g. flooding the Asset Board endpoint). Hamilton runs on Frappe Cloud's infrastructure with rate limiting; Hamilton ERP does not own that surface.
- **Issues in third-party dependencies** unless Hamilton's specific use of the dependency creates the vulnerability. Report dependency CVEs upstream first; if Hamilton's wrapper code makes it exploitable, that wrapper code is in scope.
- **Best-practices suggestions without a demonstrated exploit.** Useful but not "vulnerabilities" — open a GitHub Discussion or PR instead.

## What constitutes a Hamilton-specific vulnerability

The threat model that's relevant for Hamilton ERP specifically:

1. **Cash control bypass.** Anything that lets a Hamilton Operator role see expected-cash totals or variance, or modify Cash Drop / Cash Reconciliation records they shouldn't be able to. DEC-005 (blind cash control) is the invariant; see `docs/permissions_matrix.md`. RUNBOOK §7 documents the response if exploited.

2. **Asset state lock bypass.** Anything that lets a caller bypass the three-layer lock (Redis advisory + MariaDB FOR UPDATE + version field) and double-book an asset, leak partial state, or corrupt the state machine. DEC-019 is the invariant; `coding_standards.md` §13 documents the rules.

3. **PII exposure (forward-compat).** When Venue Session PII fields populate (Philadelphia rollout or Hamilton membership launch), unauthorized disclosure of the eight PII fields plus the `customer` Link. See `docs/research/pipeda_venue_session_pii.md`. PIPEDA breach-reporting requirements attach the day PII populates.

4. **Privilege escalation between Hamilton roles.** A user with `Hamilton Operator` reaching `Hamilton Manager` or `Hamilton Admin` capabilities without explicit role grant. The `_block_pos_closing_for_operator` install scrub is one defense; Custom DocPerm changes that re-grant blocked perms are the canonical way this could fail.

5. **Authentication / session bypass.** Anything that allows unauthenticated access to whitelisted API endpoints (none are `allow_guest=True`). The contract is documented in `docs/api_reference.md`.

## Disclosure timeline

Default disclosure timeline after a fix lands:
- **Day 0:** Fix merged to `main` and deployed to Hamilton's Frappe Cloud production site.
- **Day 7:** GitHub Security Advisory published (private / draft) for the reporter's review.
- **Day 14:** Public advisory published unless the reporter requests an extension and Hamilton agrees.

For critical vulnerabilities affecting Hamilton's live data, this timeline can compress. For low-severity issues with no production impact, it can extend by mutual agreement.

## Recognition

Hamilton ERP is a single-venue, single-developer project — there is no formal bug bounty program. Reporters who provide a clear, reproducible report and act in good faith will be acknowledged in the corresponding GitHub Security Advisory and CHANGELOG.md entry, unless they request anonymity.

## Safe-harbor

Good-faith security research conducted under the following constraints will not be referred to legal action:

1. The research targets Hamilton ERP's code repository, NOT Hamilton's live production data, customer records, or operational systems at any venue.
2. The researcher reports findings to csrnicek@yahoo.com before public disclosure.
3. The research does not involve social engineering Hamilton employees, denial of service against production, or accessing data belonging to actual venue customers.
4. The researcher follows the disclosure timeline above unless Hamilton explicitly waives it.

If your research approach is unusual or borderline, ask first via the security email — clarification before research is always welcome.

## Cryptographic considerations

Hamilton ERP uses Frappe v16's session, password, and CSRF mechanisms — Hamilton does not implement custom cryptography. Vulnerabilities in those layers should be reported to the [Frappe security team](https://frappe.io/security).

When PII fields populate, encryption-at-rest for `scanner_data` is planned per `docs/research/pipeda_venue_session_pii.md` §5. Until that's implemented, raw scanner data is not stored — Hamilton's current threat model assumes `scanner_data` is null.

## Related references

- `docs/decisions_log.md` — Locked design decisions including DEC-005 (blind cash), DEC-019 (locking), DEC-021 (field masking)
- `docs/permissions_matrix.md` — DocType-level role permissions (canonical) + Task 25 item 7 sensitive-fields list
- `docs/research/pipeda_venue_session_pii.md` — PIPEDA legal analysis for forward-compat PII fields
- `docs/RUNBOOK.md` §7 — Cash-control incident response (P0)
- `docs/api_reference.md` — Public API surface and the four named exception types

---

*Last updated 2026-04-30. Hamilton ERP is pre-1.0 and pre-Task-25 (handoff prep in progress). This policy will tighten when Hamilton enters production-customer use.*
