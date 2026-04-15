## Inbox — April 14 2026 — Fraud Research & Task 25 Planning

### Fraud Research Findings
- Conducted extensive ERPNext fraud research. Key risks for ANVIL:
  - Cash skimming (no session entered) — most likely real-world attack
  - Transaction void after cash collected — requires cancel permission lockdown
  - Offline mode abuse — browser cache wipe deletes unsynced transactions
  - Role self-escalation — anyone with System Manager can grant themselves any role
  - Direct DB access bypasses all ERPNext controls entirely
  - Ghost employees, vendor invoice fraud, expense inflation also documented

### Key Scan / Barcode Decision
- Phase 2 feature confirmed: physical key must be scanned BEFORE payment
- Scan validates that physical key matches selected asset in ERPNext
- Dual purpose: fraud prevention + asset/payment verification
- Pairs with blind cash reconciliation (also Phase 2)

### Task 25 Hardening Checklist
- Export Fixtures to Git as JSON
- Write Patches for site setup automation
- Add GitHub Actions CI/CD
- Enable v16 Role-Based Field Masking
- Audit hooks.py — replace wildcards, add try-except
- Clear Frappe Cloud error log
- Create docs/lessons_learned.md
- Create docs/venue_rollout_playbook.md
- Update CLAUDE.md to reference all new docs

### Knowledge Portability Strategy
- Philly, DC, Dallas each inherit full Hamilton knowledge
- docs/decisions_log.md — architectural decisions + reasoning
- docs/lessons_learned.md — bugs, mistakes, fixes
- docs/venue_rollout_playbook.md — step-by-step venue setup checklist
- Each build faster than the last

### Inbox Workflow Adopted
- docs/inbox.md is the bridge between claude.ai and Claude Code
- End of claude.ai session: paste summary into inbox.md on GitHub
- Start of Claude Code session: "read inbox.md, merge into docs, clear it"

# Inbox — Pre-Handoff Research Summary
**Source:** Three claude.ai research sessions, April 2026
**Action:** Merge into claude_memory.md, decisions_log.md, lessons_learned.md,
venue_rollout_playbook.md, and CLAUDE.md as appropriate. Then clear this file.

---

## BLOCK 1 — Production Hardening (Pre-Handoff Checklist)

### Critical: pyproject.toml (NEW — Feb 2026 Frappe Cloud requirement)
Frappe Cloud now requires ALL apps (including private) to have a pyproject.toml
at the repo root with a bounded Frappe dependency. Without it, deployments will
be blocked. Correct format (comma required, not space):
  [tool.bench.frappe-dependencies]
  frappe = ">=16.0.0-dev,<17.0.0-dev"
ACTION: Verify pyproject.toml exists and has this exact format.

### Fixtures — most commonly missed production item
Any configuration done in the ERPNext UI (Custom Fields, Roles, Property Setters,
Workflows, Print Formats) is stored in the DATABASE only. It is invisible to Git.
It will be lost when a new venue site is created.
MUST export before handoff:
- All Custom Fields (filter by app = hamilton_erp)
- All custom Roles: ANVIL Front Desk, ANVIL Floor Manager, ANVIL Manager
- All DocPerm entries for those roles
- All Property Setters (filter by app = hamilton_erp)
- Any Workflow definitions
Export command:
  bench --site hamilton-erp.v.frappe.cloud export-fixtures --app hamilton_erp
Fixtures must be declared in hooks.py AND exported. Both steps required.

### Patches — automate all manual UI setup
Every UI configuration step done manually on Hamilton must become an idempotent
patch so new venues require zero manual clicking after bench migrate.
All patches must check before creating (idempotent pattern).
patches.txt must use [pre_model_sync] / [post_model_sync] sections.
Key patches needed:
- validate_venue_config (fail loudly if required site_config keys missing)
- create_anvil_roles
- set_system_settings
- seed_asset_statuses
- configure_session_numbering

### hooks.py audit required
- Remove ANY wildcard doc_events {"*": ...} — runs on every doc save site-wide
- Every function called from hooks.py must have try-except + frappe.log_error()
- After changing scheduler_events, bench migrate must be run
- Use before_install / after_install hooks for one-time setup

### CI/CD — GitHub Actions
File must exist at .github/workflows/ci.yml
Runs on push to main and on PRs. Spins up MariaDB, installs hamilton_erp,
runs full test suite. If missing, ask Claude Code to generate it.
v16 requires Python 3.12+.

### Security checklist
- System Manager role: restricted to Chris only
- Cancel/amend permissions: Floor Manager+ only, not Front Desk
- Verify no Front Desk role can self-escalate permissions
- Export role permission matrix as fixture so it deploys automatically

### Document Versioning vs Audit Trail (both needed, different purpose)
Document Versioning = tracks field-level changes inside a specific document
  → Enable by: Customize Form → check "Track Changes" on each critical DocType
  → Must be ON before records are created — cannot retroactively get history
  → Enable on: Locker Asset, Session record, Cash Drop, any financial DocType
Audit Trail = tracks who did what actions across the whole site (logins, deletes)
  → Enable in: Settings → System Settings → Enable Audit Trail
CRITICAL: Document Versioning cannot be retroactively applied. Do it now.

### v16 Role-Based Field Masking
New v16 feature. Sensitive fields can be masked in List, Form, and Report views
based on role. Front Desk should not see certain financial fields.
Configure per field in Customize Form → set masking + which roles can see it.

### Frappe Scheduler Jobs
Defined in hooks.py under scheduler_events.
Use daily_long for anything that might take more than a few seconds.
After ANY change to scheduler_events: run bench migrate.
Scheduler can silently get stuck — check with:
  bench --site [site] scheduler status
Phase 2 nightly jobs: stale asset detection, session reconciliation, cash drop
verification. All go in scheduler_events, not external cron.

### Frappe Cloud Error Log
Before handoff: zero unacknowledged errors in both:
- Frappe Cloud dashboard → site → Error Logs tab
- Inside ERPNext: Settings → Error Log
A developer inheriting the project will spend paid hours sorting through old errors.

### init.sh pattern
Create init.sh at repo root. Starts bench, runs migrations, runs full test suite,
exits non-zero if any tests fail. Every session (human or AI) starts from
known-good state. Make executable: chmod +x init.sh

### Git tag before handoff
  git tag v1.0.0-hamilton-handoff && git push origin --tags
Provides a fixed reference point so Philadelphia starts from a clean known commit.

---

## BLOCK 2 — Multi-Venue Architecture

### Single codebase, separate Frappe Cloud sites per venue
One GitHub repo (csrnicek/hamilton_erp) → 4+ separate Frappe Cloud sites.
Do NOT fork the codebase per venue. Do NOT create per-venue branches.
Venue-specific behaviour controlled entirely by site_config.json flags.

### Feature flags via site_config.json
Frappe's native per-site config mechanism. Values readable in Python via frappe.conf.
Set flags on each site:
  bench --site [site] set-config anvil_venue_id "philadelphia"
  bench --site [site] set-config anvil_membership_enabled 0
  bench --site [site] set-config anvil_tax_mode "US_NONE"
  bench --site [site] set-config anvil_tablet_count 1
  bench --site [site] set-config anvil_currency "USD"

Read in Python — all reads centralised in one file:
  hamilton_erp/utils/venue_config.py
  import frappe
  def is_membership_enabled():
      return bool(frappe.conf.get("anvil_membership_enabled", 0))
NEVER scatter frappe.conf.get() calls across the codebase.

Venue flag schema must be documented in docs/site_config_schema.md.

### Planned venue config table
| Venue       | venue_id     | tax_mode  | currency | membership | tablets |
|-------------|--------------|-----------|----------|------------|---------|
| Hamilton    | hamilton     | CA_HST    | CAD      | 0          | 1       |
| Philadelphia| philadelphia | US_NONE   | USD      | 0          | 1       |
| DC          | dc           | US_NONE   | USD      | 1          | 3       |
| Dallas      | dallas       | US_NONE   | USD      | 0          | 1       |

### Git branching strategy — trunk-based development
One main branch. Always deployable. CI must pass before merge.
Short-lived feature branches (hours to 2 days max) → PR → merge to main.
NO long-lived venue branches. NO per-venue forks.
Venue differences handled by feature flags, not branches.
DC membership module: write behind anvil_membership_enabled flag — code ships
to all sites, only activates where flag is on.
Hotfix pattern: tag last known-good commit, create hotfix/ branch from tag,
fix, merge to main AND cherry-pick to production tag.

### Race condition note (preserve in decisions_log.md)
Hamilton's Redis lock system IS the production solution for DC's 3-tablet race
condition. Do NOT remove or simplify it during Philadelphia build.
Philadelphia has 1 tablet — no race condition risk — but the lock system is
harmless there. Keep it. DC depends on it.
MariaDB prevents data corruption but NOT double-assignment. Frappe adds no
application-level locking. The custom Redis lock is the only guard.

### Knowledge location rule
Git repo = permanent truth. If it's not committed, it doesn't exist for the dev.
claude_memory.md = session bridge (always synced back to repo via inbox.md)
External docs (Notion, Drive, etc.) = never store technical decisions here.

---

## BLOCK 3 — Missing Docs (Create Before Handoff)

### New files needed in the repo

VENUES.md (repo root)
  Lists all planned venues: site URL, venue_id, tax_mode, currency,
  tablet count, current build status, Frappe Cloud site name.

docs/site_config_schema.md
  Documents every site_config.json key hamilton_erp reads.
  Columns: key, type, default, required, description, which venues use it.
  ACTION: Ask Claude Code to audit all frappe.conf.get() calls and generate this.

docs/lessons_learned.md
  Template per entry:
    ## Lesson: [title]
    What happened / How long it cost / Root cause / The fix /
    Prevention for next venue / Relevant commit
  Must include: Redis lock key bug, NNN>999 deferred fix, any Frappe Cloud
  deploy failures, scheduler_events + migrate requirement.

docs/venue_rollout_playbook.md
  Step-by-step numbered checklist: create Frappe Cloud site → set site_config
  flags → run migrate → sync fixtures → run tests → verify roles → smoke test.
  Must be specific enough that Claude Code can follow it autonomously.
  Include inbox.md workflow: after any claude.ai planning session, paste summary
  to docs/inbox.md; at start of Claude Code session, merge and clear.

### Updates needed to existing docs

decisions_log.md — add formal entries for:
  - Redis locking choice (why not MariaDB-level)
  - Session number format {d}-{m}-{y}---{NNN} rationale
  - Single site per venue vs multi-company architecture
  - Dual WAN failover vs offline-first
  - No Stripe in Phase 1 (deliberate deferral)
  - NNN>999 sort bug deferred to Task 11 with :04d fix noted
  - DC race condition: Redis lock is the solution, preserve it
  Each entry: Context / Options considered / Decision / Reason /
  Consequences / Venue applicability

CLAUDE.md — add:
  - Reference to VENUES.md, site_config_schema.md, lessons_learned.md,
    venue_rollout_playbook.md so future sessions auto-load them
  - Karpathy 4 principles: Think Before Coding, Simplicity First,
    Surgical Changes, Goal-Driven Execution
  - inbox.md workflow instruction

---

## BLOCK 4 — Task 25 Checklist (Consolidated)

In addition to standard handoff doc and codebase audit:

Security & permissions:
  [ ] Cancel/amend locked to Floor Manager+ only
  [ ] System Manager restricted to Chris only
  [ ] Enable Document Versioning on all critical DocTypes (now, not at handoff)
  [ ] Enable Audit Trail in System Settings
  [ ] Verify no Front Desk role self-escalation possible
  [ ] Export role permission matrix as fixture
  [ ] Enable v16 Role-Based Field Masking on sensitive fields

Code quality:
  [ ] Export all fixtures (Custom Fields, Roles, DocPerms, Property Setters)
  [ ] Verify patches.txt covers all manual setup steps
  [ ] Add venue config validation patch (fails loudly on missing flags)
  [ ] Audit hooks.py — remove wildcards, add try-except to all hook functions
  [ ] Add pyproject.toml with bounded v16 Frappe dependency
  [ ] Add GitHub Actions CI/CD workflow
  [ ] Clear Frappe Cloud error log
  [ ] Create init.sh
  [ ] Tag v1.0.0-hamilton-handoff

New files to create:
  [ ] VENUES.md
  [ ] docs/site_config_schema.md
  [ ] hamilton_erp/utils/venue_config.py (centralised flag reads)
  [ ] docs/lessons_learned.md
  [ ] docs/venue_rollout_playbook.md
  [ ] .github/workflows/ci.yml

Handoff doc (at Task 25 completion):
  [ ] Every architectural decision + why
  [ ] Known bugs and deferred items with ticket/task references
  [ ] How to run tests, deploy, troubleshoot
  [ ] Role matrix
  [ ] Phase 2 scope: check-in flow, POS, Stripe Terminal, retail, cash drop,
      manager reports, key/barcode scan-to-activate, Playwright UI tests,
      Frappe Scheduler nightly jobs, inbox.md-to-GitHub automation script
