# Venue Rollout Playbook — Hamilton ERP

Step-by-step checklist for deploying Hamilton ERP to a new venue.
Specific enough that Claude Code can follow it autonomously.

**Audience:** Chris (system admin) or Claude Code (autonomous deploy)

---

## Prerequisites

- [ ] GitHub repo `csrnicek/hamilton_erp` is up to date on `main`
- [ ] All fixtures exported and committed (Custom Fields, Roles, DocPerms, Property Setters)
- [ ] `pyproject.toml` at repo root with bounded Frappe dependency:
  ```toml
  [tool.bench.frappe-dependencies]
  frappe = ">=16.0.0-dev,<17.0.0-dev"
  ```
- [ ] All patches listed in `patches.txt` with correct `[pre_model_sync]` / `[post_model_sync]` sections

---

## Phase A — Frappe Cloud Site Creation

1. Log in to Frappe Cloud dashboard
2. Create new site:
   - **Site name:** `{venue_id}-erp.v.frappe.cloud` (e.g., `philadelphia-erp.v.frappe.cloud`)
   - **Region:** Choose closest to venue (Hamilton = N. Virginia, Philly = N. Virginia, Dallas = Dallas)
   - **Apps:** Frappe, ERPNext, hamilton_erp (from `csrnicek/hamilton_erp` repo, `main` branch)
3. Wait for site provisioning (typically 5-10 minutes)
4. Verify site loads in browser

---

## Phase B — Site Configuration

5. Set venue-specific feature flags via `bench set-config`:
   ```bash
   bench --site {site} set-config anvil_venue_id "{venue_id}"
   bench --site {site} set-config anvil_membership_enabled 0
   bench --site {site} set-config anvil_tax_mode "{tax_mode}"
   bench --site {site} set-config anvil_tablet_count 1
   bench --site {site} set-config anvil_currency "{currency}"
   ```

   Reference table:
   | Venue        | venue_id     | tax_mode | currency | membership | tablets |
   |--------------|--------------|----------|----------|------------|---------|
   | Hamilton     | hamilton     | CA_HST   | CAD      | 0          | 1       |
   | Philadelphia | philadelphia | US_NONE  | USD      | 0          | 1       |
   | DC           | dc           | US_NONE  | USD      | 1          | 3       |
   | Dallas       | dallas       | US_NONE  | USD      | 0          | 1       |

6. Run migrations to apply all patches:
   ```bash
   bench --site {site} migrate
   ```
   This fires the `after_migrate` hook (`ensure_setup_complete`) and runs all patches in `patches.txt`.

---

## Phase C — Fixture Sync and Seed Data

7. Sync fixtures (Custom Fields, Roles, DocPerms, Property Setters):
   ```bash
   bench --site {site} migrate
   ```
   (Fixtures declared in `hooks.py` are synced automatically during migrate.)

8. Run seed data patch to create venue assets:
   ```bash
   bench --site {site} execute hamilton_erp.patches.seed_hamilton_env.execute
   ```
   This creates:
   - 59 Venue Assets (26 rooms + 33 lockers) — or venue-specific count if customized
   - Walk-in Customer record
   - Hamilton Settings singleton with defaults

---

## Phase D — Role and Permission Setup

9. Create venue-specific operator accounts:
   - ANVIL Front Desk — operators who run the asset board and POS
   - ANVIL Floor Manager — can cancel/amend, access reconciliation
   - ANVIL Manager — full access except System Manager

10. Verify role permissions:
    - [ ] System Manager restricted to Chris only
    - [ ] Cancel/amend locked to Floor Manager+ only
    - [ ] Front Desk cannot self-escalate permissions
    - [ ] Export role permission matrix as fixture

11. Enable security features:
    - [ ] Document Versioning on all critical DocTypes (Venue Asset, Venue Session, Cash Drop, Shift Record)
    - [ ] Audit Trail in System Settings
    - [ ] v16 Role-Based Field Masking on sensitive financial fields

---

## Phase E — Testing

12. Run full test suite on the venue site:
    ```bash
    bench --site {site} run-tests --app hamilton_erp
    ```
    All modules must pass. Zero failures.

13. Manual smoke test in browser:
    - [ ] Asset Board loads with correct asset count
    - [ ] Can change asset status (Available → Occupied → Dirty → Available)
    - [ ] Out of Service flow works (mandatory reason)
    - [ ] Mark All Clean bulk action works
    - [ ] Correct color coding and tier badges displayed

---

## Phase F — Go-Live Verification

14. Verify Frappe Cloud auto-deploy is configured:
    - GitHub repo connected to Frappe Cloud site
    - Push to `main` triggers auto-deploy within 3 minutes

15. Clear error logs:
    - [ ] Frappe Cloud dashboard → site → Error Logs tab: zero unacknowledged errors
    - [ ] Inside ERPNext: Settings → Error Log: clean

16. Final checks:
    - [ ] `bench --site {site} scheduler status` — scheduler is running
    - [ ] Redis is healthy (no stuck jobs)
    - [ ] Site loads on tablet browser at venue

---

## Post-Deploy — Ongoing Operations

### Inbox Workflow (claude.ai ↔ Claude Code bridge)

After any claude.ai planning or research session:
1. Paste summary into `docs/inbox.md` on GitHub
2. At start of next Claude Code session: "read inbox.md, merge into docs, clear it"
3. This ensures all research and decisions are captured in the structured docs

### Knowledge Portability

Each new venue inherits the full Hamilton knowledge base:
- `docs/decisions_log.md` — architectural decisions + reasoning
- `docs/lessons_learned.md` — bugs, mistakes, fixes
- `docs/venue_rollout_playbook.md` — this file
- `docs/claude_memory.md` — session bridge and planning notes

Each venue build should be faster than the last.

---

*Update this playbook after each venue deployment with any new steps or gotchas discovered.*
