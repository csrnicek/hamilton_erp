# Review of `Hamilton ERP — Production & Handoff Readiness Audit (Merged)`

**Purpose:** Identify additional changes, recommendations, contradictions, and knowledge gaps in the merged production/handoff audit document before it becomes the master pre-launch checklist.

**Bottom line:** The document is strong and useful, but it should be cleaned up before being treated as the official source of truth. The biggest problem is not missing effort — it is that the document mixes verified facts, recommendations, assumptions, and future tasks in a few places. That can confuse a professional developer, especially during handoff.

---

## Executive Summary

The merged audit does a good job combining two important views:

1. **Production readiness** — can Hamilton ERP survive real business use?
2. **Developer handoff readiness** — can a professional Frappe/ERPNext developer take over without wasting time?

The core priorities are correct:

- Add automated CI testing.
- Run and document a real backup restore drill.
- Enable Track Changes and Audit Trail.
- Improve README / HANDOFF documentation.
- Add scheduler health monitoring.
- Explain `ignore_permissions=True`.
- Verify fixtures and patches.
- Lock down permissions and secrets.

However, before using this file as the master checklist, I recommend fixing the issues below.

---

# 1. Replace misleading ✅ symbols on unfinished tasks

## Issue

The “If You Do Nothing Else” Top 10 uses ✅ symbols for items that are clearly not completed yet.

Example:

```markdown
2. ✅ A working GitHub Actions CI runs your 270+ tests automatically on every push.
```

But later the same document says:

```markdown
There is no test-runner workflow.
```

That is contradictory.

## Why this matters

A developer or future reviewer may scan the top section and think those tasks are already complete.

That is dangerous because several of those “✅” items are actually **launch blockers**.

## Recommendation

Use unchecked task boxes for work that still needs to be done:

```markdown
- [ ] A working GitHub Actions CI runs tests automatically on every push.
```

Reserve ✅ only for items that have actually been verified.

Suggested status language:

```markdown
- ✅ Verified complete
- 🟡 Exists but needs validation
- 🔴 Missing / launch blocker
- ❓ Unknown / needs hands-on check
- [ ] To do
```

---

# 2. Separate verified facts from recommendations

## Issue

Some sections say “verified” or “factual,” but contain items that still require confirmation.

Example:

```markdown
patches.txt — Clean structure; idempotency to verify
```

That means the patch files exist, but the most important safety behavior has not been proven.

## Why this matters

A professional developer needs to know what is actually confirmed versus what still needs testing.

## Recommendation

Add a “verification status” column.

Example:

```markdown
| Area | What exists | Verification Status | Next Action |
|---|---|---|---|
| patches.txt | 2 patches in post_model_sync | 🟡 Structure verified, idempotency not verified | Run each patch twice |
| GitHub Actions | Claude review workflow only | 🔴 No test CI | Add tests.yml |
| Fixtures | Custom Field, Property Setter, Role fixtures | 🟡 Filters look good, export drift unknown | Run export-fixtures and check git diff |
```

---

# 3. Fix inconsistent test count: 270+ vs 306+

## Issue

The document says both:

- “270+ tests”
- “306+ tests”

## Why this matters

It makes the audit look less precise than it is.

## Recommendation

Use one safer phrase throughout:

```markdown
The repo has 19 test files and prior notes report roughly 306+ local tests passing. The exact count should be confirmed by CI.
```

Do not keep switching between 270+ and 306+.

---

# 4. Confirm whether `override_doctype_class` has already been replaced

## Issue

The document says:

```markdown
override_doctype_class → extend_doctype_class correction applied
```

But elsewhere it says:

```markdown
Apply the override_doctype_class → extend_doctype_class correction at hooks.py:69 if not yet done.
```

## Why this matters

That is a direct contradiction.

Either the fix is done, or it is not.

## Recommendation

Replace both statements with one precise status:

```markdown
Current status: `extend_doctype_class` appears to be the intended v16-safe pattern. Verify current `hooks.py` before handoff. If `override_doctype_class` still appears anywhere, replace it with `extend_doctype_class` unless there is a documented reason not to.
```

Also add a command:

```bash
grep -rn "override_doctype_class\|extend_doctype_class" hamilton_erp/hooks.py
```

---

# 5. Verify all Frappe v16 claims against official docs/current repo

## Issue

The document contains several Frappe v16-specific claims that may be correct, but should be verified before being treated as rules.

Examples:

- `frappe.flags.in_test` → `frappe.in_test`
- v16 booleans/integers replacing `"1"` / `"0"` string comparisons
- field masking details
- Frappe Cloud version pinning behavior
- shared CI workflow behavior
- `cron_long` availability/behavior

## Why this matters

Frappe and ERPNext change quickly. If one detail is wrong, a developer may waste time following a false instruction.

## Recommendation

Create a short section called:

```markdown
## Items requiring Frappe v16 verification
```

Include:

```markdown
- [ ] Confirm correct test flag usage: `frappe.in_test` vs `frappe.flags.in_test`.
- [ ] Confirm boolean return behavior for fields currently compared to `"1"` / `"0"`.
- [ ] Confirm field masking setup steps in current Frappe v16 UI.
- [ ] Confirm Frappe Cloud version pinning options in the actual dashboard.
- [ ] Confirm Frappe shared GitHub Actions workflow works for this app.
- [ ] Confirm whether `cron_long` is available and appropriate on the selected Frappe Cloud plan.
```

---

# 6. Be careful with “every hook wrapped in try/except”

## Issue

The Top 10 says:

```markdown
every handler wrapped in try/except
```

But this is not always correct.

For some hooks, you **want** an exception to stop the transaction.

For example:

- validation hooks
- financial checks
- permission checks
- lifecycle state enforcement
- asset assignment rules

If these fail, the save/submit should fail.

## Why this matters

Overusing `try/except` can hide real business-rule failures.

## Recommendation

Change the wording.

Better:

```markdown
Every non-critical side-effect hook should handle/log errors safely. Critical validation and financial integrity hooks should fail loudly and block the transaction.
```

Plain English:

> If the hook is sending a notification, do not let it break the sale.  
> If the hook is protecting money, assets, permissions, or state, let it block the action.

---

# 7. Clarify scheduler error handling: re-raise or continue?

## Issue

The document gives two slightly different patterns:

1. Inside loops, catch one record’s error and continue.
2. For `check_overtime_sessions`, catch, log, and re-raise.

Both can be valid, but the document should explain the difference.

## Why this matters

A future developer may copy the wrong pattern.

## Recommendation

Add this rule:

```markdown
Scheduler error handling rule:
- If one bad record should not stop the entire job, catch/log per record and continue.
- If the whole job is in an unsafe or unknown state, log and re-raise so the failure is visible.
```

For overtime detection, decide which behavior is correct.

Example:

```markdown
For `check_overtime_sessions`, preferred behavior should be:
- log the job start/end;
- process sessions one by one;
- log per-session failures;
- continue where safe;
- raise a final summary error if any sessions failed, so Error Log/alerts still show the job was unhealthy.
```

---

# 8. Backup advice needs operational precision

## Issue

The document says:

- enable hourly backups
- enable backup encryption
- save the encryption key
- restore a backup to a fresh site

That is good, but it needs more detail.

## Knowledge gaps

The document does not clearly answer:

- Who owns the Frappe Cloud account?
- Who has access to backups?
- Where is the encryption key stored?
- Who can restore?
- How long should backups be retained?
- Are offsite backups available on the current plan?
- Is the restore drill using a same-version site?
- What is the acceptable recovery time?

## Recommendation

Add a short disaster recovery table:

```markdown
| Question | Current Answer | Needed Before Go-Live |
|---|---|---|
| Who can access Frappe Cloud backups? | Unknown | Name owner + backup admin |
| Where is encryption key stored? | Unknown | 1Password / Bitwarden entry |
| How often are backups taken? | Daily by default | Hourly if available |
| How often is restore tested? | Not yet | Before go-live, then quarterly |
| Target recovery time | Unknown | Define, e.g. under 2 hours |
| Target data loss window | Unknown | Define, e.g. under 1 hour |
```

---

# 9. Define RTO and RPO

## Issue

The document warns about backups but does not define recovery targets.

## Plain English

These two terms matter:

**RTO — Recovery Time Objective**

> How long can the business survive with the system down?

**RPO — Recovery Point Objective**

> How much data can the business afford to lose?

## Recommendation

Add this:

```markdown
## Recovery Targets

- RTO: maximum acceptable downtime during business hours: ______
- RPO: maximum acceptable data loss: ______
```

Example for Hamilton:

```markdown
Suggested starting point:
- RTO: restore basic operations within 2 hours.
- RPO: lose no more than 1 hour of transaction data.
```

If you want an RPO under 1 hour, daily backups are not enough.

---

# 10. Add manual fallback procedures for live operations

## Issue

The document discusses technical recovery but not front-desk survival if the system is down.

## Why this matters

A bathhouse cannot stop operations completely just because the web app is down.

## Recommendation

Add a section:

```markdown
## Manual Fallback Procedure
```

Include:

- paper check-in sheet
- manual room/locker assignment sheet
- manual cash/card recording
- how to record ID/member verification when offline
- who approves manual overrides
- how to enter paper records back into ERPNext after recovery
- how to prevent double-renting rooms during outage

Plain English:

> If the system is down for 45 minutes, staff need a safe manual process, not just a developer runbook.

---

# 11. Clarify Frappe Cloud auto-deploy assumptions

## Issue

The document says bad commits can auto-deploy to Frappe Cloud.

That may be true depending on the Frappe Cloud configuration, but it should be verified.

## Recommendation

Add a check:

```markdown
- [ ] Confirm whether Frappe Cloud auto-deploys from `main`.
- [ ] Confirm whether deployment requires manual approval.
- [ ] Confirm rollback process.
- [ ] Confirm whether migrations run automatically on deploy.
- [ ] Document exact deployment trigger in `docs/HANDOFF.md`.
```

This matters because CI urgency is even higher if deploys are automatic.

---

# 12. Add database migration safety checklist

## Issue

The document discusses patches, but not enough about schema migrations.

## Recommendation

Add a migration checklist:

```markdown
## Migration Safety Checklist

Before production migration:
- [ ] backup taken immediately before migration
- [ ] migration tested on restored staging copy
- [ ] `bench migrate` output reviewed
- [ ] no destructive field changes without backup
- [ ] long migrations tested for runtime
- [ ] patch logs checked after migrate
- [ ] asset board smoke-tested after migrate
```

Plain English:

> A patch can pass locally but still fail on production data. Always test against a restored copy.

---

# 13. Add smoke tests after deployment

## Issue

The document says run tests and CI, but it should also define quick human checks after deploy.

## Recommendation

Add:

```markdown
## Post-Deploy Smoke Test

After every production deploy:
- [ ] log in as Admin
- [ ] log in as Hamilton Operator
- [ ] open asset board
- [ ] load current rooms/lockers
- [ ] create test/manual session in staging only
- [ ] verify permissions block unauthorized cash screens
- [ ] verify Error Log has no new deploy errors
- [ ] verify scheduler heartbeat updates
- [ ] verify background workers are running
```

This helps catch problems that unit tests may miss.

---

# 14. Clarify production vs staging vs local

## Issue

The document refers to:

- local test site
- fresh Frappe Cloud site
- production site
- sandbox site
- staging site

But it does not define the intended environment structure.

## Recommendation

Add an environment table:

```markdown
| Environment | URL / Site Name | Purpose | Data Type | Who Can Access |
|---|---|---|---|---|
| Local dev | hamilton-unit-test.localhost | Developer testing | Fake/sample data | Devs |
| Staging | TBD | Test deploys and restore drills | Restored/sanitized copy | Chris + dev |
| Production | hamilton-erp.v.frappe.cloud | Live operations | Real data | Authorized users only |
```

Also define:

```markdown
Never test destructive changes directly on production.
```

---

# 15. Clarify personal data / privacy obligations

## Issue

The document mentions member PII but does not deeply cover privacy handling.

Hamilton may store:

- names
- phone numbers
- emails
- ID scan-related information
- membership status
- visit/session history
- possibly sensitive venue attendance data

## Why this matters

This is not just a technical issue. It is a legal and reputational risk.

## Recommendation

Add a privacy/security section:

```markdown
## Privacy / Personal Data Handling

- [ ] List all personal data stored.
- [ ] Identify which fields are sensitive.
- [ ] Confirm whether ID images/barcodes are stored or only parsed.
- [ ] Confirm retention policy for ID/member data.
- [ ] Restrict export/report permissions.
- [ ] Mask phone/email where possible.
- [ ] Confirm backup encryption.
- [ ] Confirm who can access production database.
- [ ] Add privacy incident response plan.
```

Plain English:

> This app likely contains sensitive customer information. Treat it like a privacy-risk system, not just a room-management app.

---

# 16. Add payment and cash-control specifics

## Issue

The document talks about cash drops, cash reconciliation, and Sales Invoice, but does not clearly define the financial controls.

## Recommendation

Add:

```markdown
## Cash / Payment Controls To Verify

- [ ] Who can open a shift?
- [ ] Who can close a shift?
- [ ] Who can see expected cash?
- [ ] Who can enter actual cash?
- [ ] Who can approve discrepancies?
- [ ] Who can refund?
- [ ] Who can cancel or amend Sales Invoices?
- [ ] Are all refunds logged with reason?
- [ ] Are same-shift refund rules enforced?
- [ ] Are cash drops tied to staff identity?
```

This should connect directly to the permission matrix.

---

# 17. Add role/account rules for floor staff

## Issue

The document says System Manager should be restricted, but it does not fully define operational account rules.

## Recommendation

Add:

```markdown
## User Account Rules

- [ ] No shared System Manager account.
- [ ] No shared manager account.
- [ ] Floor staff PIN identity must be auditable.
- [ ] Staff identity must attach to cash-sensitive actions.
- [ ] Deactivated staff must lose access immediately.
- [ ] Staff PIN reset process documented.
- [ ] Failed PIN attempts are rate-limited and logged.
```

Plain English:

> If five people use the same login, the audit trail becomes much weaker.

---

# 18. Add frontend/browser/device readiness

## Issue

The document focuses mostly on backend, Frappe, CI, backups, and handoff.

It does not deeply cover actual front-desk hardware/browser readiness.

## Recommendation

Add:

```markdown
## Front Desk Device Readiness

- [ ] Supported browser chosen.
- [ ] Asset board tested on actual front-desk device.
- [ ] Touchscreen behavior tested.
- [ ] Session timeout behavior tested.
- [ ] Browser refresh/reconnect behavior tested.
- [ ] Network drop behavior tested.
- [ ] Printer/receipt workflow tested if applicable.
- [ ] Cash drawer integration tested if applicable.
- [ ] Barcode/ID scanner tested if applicable.
```

Plain English:

> A system can pass backend tests and still fail at the actual counter because the tablet, browser, scanner, or printer behaves differently.

---

# 19. Add performance/load expectations

## Issue

The document references scheduler performance and 2-second checks, but does not define expected production load.

## Recommendation

Add a short capacity section:

```markdown
## Expected Production Load

- Expected check-ins per day: ______
- Peak check-ins per hour: ______
- Number of front desk stations: ______
- Number of simultaneous staff users: ______
- Number of rooms/lockers/assets: ______
- Expected asset board refresh rate: ______
- Maximum acceptable asset board load time: ______
```

Then define smoke targets:

```markdown
- Asset board should load in under 2 seconds under normal load.
- Assign/vacate/clean actions should complete in under 1 second under normal load.
```

These numbers can be adjusted, but they should exist.

---

# 20. Add data retention and deletion policy

## Issue

The document says to keep logs for 90/365/730 days, but does not define a wider retention policy.

## Recommendation

Add:

```markdown
## Data Retention Policy

- Error Log: 90 days
- Activity Log: 365 days
- Version history: 365+ days for financial/asset records
- Sales Invoice: per accounting/legal requirements
- Membership records: define retention after inactivity
- ID scan data: minimize and define retention
- Backups: define daily/hourly/monthly retention
```

Plain English:

> Do not keep sensitive data forever unless there is a business/legal reason.

---

# 21. Add GitHub Issues tracking rule

## Issue

The document lists many action items, but if left inside one Markdown file, they may not get managed properly.

## Recommendation

Add:

```markdown
## Tracking Rule

Every Tier 1 and Tier 2 item must become either:
- a GitHub Issue,
- a completed commit,
- or a documented “not doing now” decision.

Do not leave open launch blockers only inside this Markdown file.
```

This prevents the checklist from becoming passive documentation instead of an active project plan.

---

# 22. Add owner/responsibility column

## Issue

The checklist has tasks and time estimates but no owner.

## Recommendation

Add columns:

```markdown
| Item | Owner | Status | Due Before | Notes |
```

Example:

```markdown
| Add CI test runner | Developer / Claude Code | Not started | Before handoff | Required before production |
| Backup restore drill | Chris + Dev | Not started | Before go-live | Needs Frappe Cloud access |
| Enable Track Changes | Chris / Admin | Not started | Immediately | UI configuration |
```

Plain English:

> If nobody owns the task, it will not happen.

---

# 23. Add “what not to change” warnings

## Issue

The document explains good patterns, but it should explicitly protect dangerous areas.

## Recommendation

Add:

```markdown
## Do Not Change Without Review

- Do not remove Redis/DB locking logic.
- Do not bypass lifecycle state checks.
- Do not replace Workflow state with a plain Select field.
- Do not allow operators to see expected cash totals.
- Do not add `allow_guest=True` endpoints.
- Do not use `ignore_permissions=True` without documented upstream permission checks.
- Do not customize production UI without exporting fixtures or converting to code.
- Do not run destructive patches on production without a fresh backup.
```

This is especially useful for handoff.

---

# 24. Add exact acceptance criteria for Tier 1

## Issue

Some Tier 1 items are broad.

Example:

```markdown
Add scheduler heartbeat job + dead-scheduler alert
```

What counts as done?

## Recommendation

Add acceptance criteria.

Example:

```markdown
Done when:
- heartbeat timestamp updates at least every 5 minutes;
- manager/admin can see stale heartbeat alert;
- test proves stale heartbeat is detected;
- runbook explains how to restart/check scheduler.
```

Do this for each Tier 1 item.

---

# 25. Add branch/deployment protection checklist

## Issue

The CI section says to add branch protection, but it should be more explicit.

## Recommendation

Add:

```markdown
## GitHub Branch Protection

- [ ] Require pull request before merge to main.
- [ ] Require tests workflow to pass.
- [ ] Require lint workflow to pass if enabled.
- [ ] Block force pushes to main.
- [ ] Require conversation resolution before merge.
- [ ] Require signed commits if desired.
- [ ] Restrict who can push directly to main.
```

Plain English:

> CI does not help if someone can bypass it and push straight to main.

---

# 26. Add release/rollback process

## Issue

The document mentions hotfix and rollback but does not define a release process.

## Recommendation

Add:

```markdown
## Release Process

Before deploy:
- [ ] CI green
- [ ] backup taken
- [ ] migration tested on staging
- [ ] release notes written
- [ ] rollback commit/tag identified

After deploy:
- [ ] smoke test passed
- [ ] Error Log checked
- [ ] scheduler heartbeat checked

Rollback:
- [ ] revert commit if code-only issue
- [ ] restore backup if data migration issue
- [ ] document incident
```

Also require Git tags:

```bash
git tag prod-2026-04-25
git push origin prod-2026-04-25
```

---

# 27. Add incident response template

## Issue

The “Saturday night” scenario is good, but the document should include a template for recording incidents.

## Recommendation

Add:

```markdown
## Incident Report Template

- Date/time:
- Reported by:
- Symptoms:
- Users affected:
- Revenue/customer impact:
- Error Log links:
- Recent deploys/settings changes:
- Immediate fix:
- Root cause:
- Follow-up tasks:
- Preventive test added:
```

Plain English:

> Every real incident should produce a fix and a test, not just a memory.

---

# 28. Add business continuity role list

## Issue

The document says “can you do this at 11pm?” but does not define who is responsible.

## Recommendation

Add:

```markdown
## Emergency Contacts / Authority

- Business owner:
- Technical owner:
- Frappe Cloud account owner:
- Backup admin:
- On-call developer:
- Who can approve restore:
- Who can approve manual operations:
```

This prevents confusion during an emergency.

---

# 29. Tighten claims about CVEs and future dates

## Issue

The document references specific security issues and CVEs, including future-looking or very specific claims.

## Why this matters

Security references should be accurate, current, and verified. If a CVE citation is wrong, it weakens the whole audit.

## Recommendation

Move all security claims that depend on current CVE data into a “verify before publication” list.

Example:

```markdown
- [ ] Verify cited CVE IDs and dates.
- [ ] Verify Frappe/ERPNext current security advisories.
- [ ] Verify whether the cited CSRF issue applies to Hamilton’s version/configuration.
```

Keep the principle even if the exact CVE changes:

> Every whitelisted endpoint should declare allowed HTTP methods and reject unauthorized state-changing requests.

---

# 30. Add “source confidence” to Appendix C

## Issue

The document includes official docs, blogs, community posts, and AI/research-derived claims.

Those are not equal-quality sources.

## Recommendation

Group sources by confidence:

```markdown
## Source Confidence

### Highest confidence
- Official Frappe docs
- Official ERPNext docs
- Frappe Cloud docs
- Current repo inspection

### Medium confidence
- Frappe forum
- practitioner blogs
- community tutorials

### Lower confidence / verify before acting
- third-party security pages
- AI-generated audit notes
- future-version commentary
```

Plain English:

> Use official docs and current repo state as final authority when there is conflict.

---

# 31. Make the merged document shorter or split it

## Issue

The merged audit is extremely long.

That is good for completeness, but bad for execution.

## Recommendation

Keep this full file as an archive, but create three shorter working docs:

```markdown
docs/production/TIER1_GO_LIVE_CHECKLIST.md
docs/HANDOFF.md
docs/operations/RUNBOOK.md
```

Suggested split:

### `TIER1_GO_LIVE_CHECKLIST.md`
Only launch blockers and acceptance criteria.

### `HANDOFF.md`
Developer onboarding, decisions, setup, deploy, known gotchas.

### `RUNBOOK.md`
What to do during outages, restore, scheduler failures, cash issues.

Plain English:

> A 700+ line audit is useful. A 40-item go-live checklist is what actually gets completed.

---

# 32. Add beginner explanations for technical terms

## Issue

The document is better than most, but it still includes many technical terms.

Examples:

- fixture
- patch
- idempotent
- CI/CD
- scheduler heartbeat
- RQ
- Redis
- `permission_query_conditions`
- `extend_doctype_class`
- CSRF
- field masking
- migration
- smoke test

## Recommendation

Add a glossary at the top or bottom.

Example:

```markdown
## Glossary

**Fixture:** A saved copy of a Frappe UI customization so it can be recreated on another site.

**Patch:** A one-time script that changes data or settings during migration.

**Idempotent:** Safe to run more than once without duplicating or breaking anything.

**CI:** Automatic testing that runs in GitHub when code changes.

**Smoke test:** A quick basic test after deploy to confirm the main screens still work.
```

This is especially helpful because Chris is using the document to manage developers.

---

# 33. Add “do not assume local equals production”

## Issue

The document references local tests heavily, but local success does not guarantee production success.

## Recommendation

Add:

```markdown
## Local vs Production Warning

Passing local tests is required but not sufficient.

Before production:
- test on staging;
- test with production-like data;
- test with actual Frappe Cloud version;
- test with actual roles/users;
- test with real front-desk browser/device;
- test restore from real backup.
```

---

# 34. Confirm the actual repo path names

## Issue

The document uses names like:

- `Bathhouse Shift`
- `Shift Record`
- `Venue Asset`
- `Bathhouse Asset`
- `Cash Drop`
- `Cash Reconciliation`
- `Bathhouse Receivable Log`

Some may be real DocTypes, aliases, older names, or future names.

## Why this matters

If a DocType name is wrong, a developer may waste time searching for something that does not exist.

## Recommendation

Add a generated DocType inventory:

```bash
find hamilton_erp/hamilton_erp/doctype -maxdepth 2 -name "*.json" | sort
```

Then list the exact DocType names in `docs/data_model.md`.

Add a note:

```markdown
Do not mix older project names with current DocType names. Use exact DocType names from the repo.
```

---

# 35. Add “current status as of commit” section

## Issue

The document says “verified 2026-04-25,” but if changes are made later, the document may become stale.

## Recommendation

Add:

```markdown
## Status Metadata

- Audit date:
- Repo:
- Branch:
- Commit reviewed:
- Frappe version reviewed:
- ERPNext version reviewed:
- Local site used:
- Frappe Cloud site checked:
- Reviewer:
```

Then every future update can be tied to a known commit.

---

# 36. Make “what is done” and “what remains” machine-trackable

## Issue

Markdown checklists are good, but a long checklist can drift.

## Recommendation

Use a simple status label per task:

```markdown
Status: NOT_STARTED / IN_PROGRESS / BLOCKED / DONE / DEFERRED
```

Example:

```markdown
| ID | Task | Status | Evidence |
|---|---|---|---|
| T1.1 | Add CI test runner | NOT_STARTED | No tests.yml in .github/workflows |
| T1.8 | Enable Track Changes | UNKNOWN | Needs UI check |
| T1.13 | Audit secrets | NOT_STARTED | No output saved |
```

The “Evidence” column is important.

---

# 37. Add evidence requirement for completed tasks

## Issue

The document says some tasks should be done, but does not specify how to prove they were done.

## Recommendation

For every completed Tier 1 item, require evidence.

Examples:

```markdown
| Task | Evidence Required |
|---|---|
| CI added | Link to successful GitHub Actions run |
| Backup restore drill | Screenshot/log + disaster_recovery.md |
| Track Changes enabled | Screenshot or exported fixture/property setter |
| Secrets audit | Command output saved in docs/security/secrets_audit_YYYY-MM-DD.md |
| Fixtures clean | `git diff` output showing no changes |
```

Plain English:

> “Done” should mean there is proof, not just memory.

---

# 38. Add user-training checklist

## Issue

Production readiness is not only technical. Staff need to know how to use the system safely.

## Recommendation

Add:

```markdown
## Staff Training Before Go-Live

- [ ] How to assign a room/locker.
- [ ] How to vacate a room.
- [ ] How to mark dirty/clean.
- [ ] How to handle out-of-service assets.
- [ ] How to handle payment/cash drop.
- [ ] How to handle system outage/manual fallback.
- [ ] What staff are not allowed to override.
- [ ] Who to call when stuck.
```

Plain English:

> A perfect system can still fail if staff do not know the procedure.

---

# 39. Add go/no-go decision checklist

## Issue

The final sanity check says “if red, do not deploy,” but it would help to have a formal go/no-go checklist.

## Recommendation

Add:

```markdown
## Go / No-Go Checklist

Go-live is approved only if:
- [ ] CI green
- [ ] backup restore drill passed
- [ ] audit trail and Track Changes enabled
- [ ] core permissions tested with operator user
- [ ] asset board tested on front-desk device
- [ ] manual fallback printed and available
- [ ] emergency contacts documented
- [ ] rollback plan documented
- [ ] owner signs off
```

---

# 40. Overall recommendation

Use the merged document as the **master audit archive**, but do not use it alone as the working launch plan.

Recommended structure:

```text
docs/inbox/prompt1_production_audit_2026-04-25.md
docs/inbox/prompt5_handoff_audit_2026-04-25.md
docs/production/merged_audit_full.md
docs/production/TIER1_GO_LIVE_CHECKLIST.md
docs/HANDOFF.md
docs/operations/RUNBOOK.md
docs/operations/DISASTER_RECOVERY.md
docs/security/PERMISSION_MATRIX.md
docs/security/SECRETS_AUDIT.md
```

## Final plain-English takeaway

The document is good, but it needs cleanup before it becomes the official checklist.

The most important improvements are:

1. Fix misleading checkmarks.
2. Separate verified facts from recommendations.
3. Add owners, statuses, due dates, and evidence.
4. Define production/staging/local environments.
5. Add manual fallback procedures.
6. Add disaster recovery targets.
7. Add post-deploy smoke tests.
8. Add privacy/data-retention checks.
9. Add exact acceptance criteria for Tier 1.
10. Split the huge audit into smaller working documents.

The merged audit is not wrong. It is just too broad and a little too mixed together right now.

With the cleanup above, it becomes much more useful as a handoff and go-live control document.
