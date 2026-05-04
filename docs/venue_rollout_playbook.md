# Venue Rollout Playbook — Hamilton ERP

Step-by-step checklist for deploying Hamilton ERP to a new venue.
Specific enough that Claude Code can follow it autonomously.

**Audience:** Chris (system admin) or Claude Code (autonomous deploy)

**Last updated:** 2026-05-01 (Task 25 item 16 refresh — added v16 pinning, init.sh, and Hamilton accounting conventions references).

---

## Prerequisites

- [ ] GitHub repo `csrnicek/hamilton_erp` is up to date on `main`
- [ ] All fixtures exported and committed (Custom Fields, Roles, DocPerms, Property Setters)
- [ ] `pyproject.toml` at repo root with bounded Frappe dependency:
  ```toml
  [tool.bench.frappe-dependencies]
  frappe = ">=16.0.0-dev,<17.0.0-dev"
  ```
  This range is the app's **compatibility window** (what versions of Frappe Hamilton's code is known to work with), NOT the **production deployment pin**. Frappe Cloud production must pin a specific tagged minor release (e.g. `v16.3.4`) per Phase A step 2 + CLAUDE.md "Production version pinning." The `>=16.0.0-dev,<17.0.0-dev` range allows local dev / CI to install any compatible v16, while the production-side pin chooses ONE specific release. These are different things and both are needed.
- [ ] All patches listed in `patches.txt` with correct `[pre_model_sync]` / `[post_model_sync]` sections
- [ ] **Local dev bench is working before deploying to Frappe Cloud.** Use `scripts/init.sh` for the fresh-bench bootstrap — it verifies version pins (Python 3.14, Node 24, MariaDB, Redis, frappe-bench), sets up a working bench, and installs frappe + erpnext + payments + hamilton_erp on a dev site. The script is idempotent. CI uses the same install path (`.github/workflows/tests.yml`), so a green local `init.sh` is the strongest signal that production deploy will succeed.

---

## Phase 0 — Per-venue site survey + procurement (before Phase A)

These are physical-site and merchant-relationship decisions made BEFORE the Frappe Cloud site goes up. Each new venue (Philadelphia, DC, Dallas, future) runs through the full sequence at rollout time. Hamilton skipped this phase historically; future venues do not.

### Step 0.1 — Site survey for connectivity

- [ ] **Ethernet drop at front desk.** Check whether the venue's front-desk location has a wired ethernet drop available within cable reach. If yes, plan wired LAN for the receipt printer, label printer, and cash drawer. If no, plan WiFi for all networked hardware and confirm WiFi signal strength at the front-desk location is reliable enough for the receipt-print latency budget.
- [ ] **Power outlets.** Confirm enough outlets near the front desk to support the iPad charger, scanner (if specced), card terminal, receipt printer, label printer, and cash drawer — plus a UPS / surge protector. A typical station needs 4-6 outlets.
- [ ] **Cellular signal** (backup connectivity). Some card terminals (Clover Flex with cellular) can run on cell when WiFi/LAN is down. Confirm cell signal at the venue if specifying a cellular-capable terminal.

### Step 0.2 — Pick primary processor + backup processor (DEC-063 + DEC-064)

- [ ] **Choose primary processor.** Per DEC-063, each venue picks based on local availability, iPad/ERPNext SDK fit, hardware fit, fees, and risk policy. See `docs/research/merchant_processor_comparison.md` for the ranked table. Default for new USD venues is **Stripe Terminal** (CA + USD support, native ERPNext SDK, BBPOS WisePOS E hardware), but the venue's local ISO offers + cost negotiation can override. Hamilton stays on existing Fiserv MID 1131224.
- [ ] **Choose backup processor.** Per DEC-064, every venue must have a backup processor pre-approved + integration-tested. Helcim is the natural Canadian backup (adult-friendly TOS); Stripe is the natural US backup if Stripe isn't already primary. The backup must be a different processor than the primary AND must support the same operations (charge, refund, void, capture, settle).
- [ ] **Open both merchant accounts.** Even if the backup is "dormant," the application + underwriting + KYC happens upfront. A "backup" that takes 4 weeks to onboard at the moment of need is not a backup.

### Step 0.3 — Integration-test both processors

- [ ] **Process a $1 live test transaction through each.** Confirm the iPad → terminal → processor → settlement flow works end-to-end on BOTH primary and backup. A backup that's "approved but never tested" is also not a backup.
- [ ] **Verify webhooks / callbacks.** Both processors must successfully deliver post-transaction webhooks to the venue's site (success, failure, refund, dispute notifications). Set up the webhook URLs in both portals during this step.
- [ ] **Verify swap mechanism.** Confirm the per-venue config flip (`bench set-config primary_processor backup_processor_name`) followed by a worker restart correctly switches subsequent transactions to the backup. Document the exact command in `docs/RUNBOOK.md`.

### Step 0.4 — Order hardware including spares

- [ ] **Per-venue hardware list,** based on `docs/design/pos_hardware_spec.md`:
  - iPad (10th gen, USB-C) — quantity = number of stations at this venue
  - ID scanner (Honeywell Voyager 1602g + Apple USB-C-to-USB Adapter) — quantity = stations + 1 spare per venue (deferred for Hamilton until Phase 2; required for venues with loyalty / DL-verification flows)
  - Card terminal (model per Step 0.2 primary processor) — quantity = stations
  - Receipt printer (Epson TM-T20III dual LAN/WiFi) — quantity = stations
  - Label printer (Brother QL-820NWB) — quantity = 1 per venue (shared) OR 1 per station (high-volume)
  - Cash drawer (RJ-11 to receipt printer) — quantity = stations
  - Cables (USB-C charger, ethernet patch if wired, USB-C-to-USB-A adapter for scanner) — verify lengths against site-survey measurements
- [ ] **Spares budget.** Multi-station venues (DC's 3 stations) carry: 1 spare scanner, 1 spare card-terminal cable / dock, 1 case of receipt paper, 1 case of label DK rolls. Decide spares quantity at order time, not after the first failure.

### Step 0.5 — Compatibility check before deployment

- [ ] **Scanner ↔ iPad.** USB-C native or USB-C-to-USB-A adapter confirmed; HID keyboard wedge mode tested.
- [ ] **Card terminal ↔ iPad.** SDK pair tested; one $1 transaction completed end-to-end.
- [ ] **Receipt printer ↔ network.** Pings from iPad's WiFi / LAN to printer IP succeed.
- [ ] **Label printer ↔ network.** Pings + AirPrint discovery from iPad succeed.
- [ ] **Cash drawer ↔ receipt printer.** RJ-11 cable plugged; ESC/POS kick command pops the drawer on test transaction.

**Note on scanner / spare counts and per-station hardware distribution:** these are operational decisions made at venue rollout time, NOT in `docs/design/pos_hardware_spec.md`. The hardware spec lists what's available and integration-tested; the rollout playbook decides what each venue actually orders based on station count, traffic forecast, layout, and budget.

---

## Phase A — Frappe Cloud Site Creation

1. Log in to Frappe Cloud dashboard
2. Create new site:
   - **Site name:** `{venue_id}-erp.v.frappe.cloud` (e.g., `philadelphia-erp.v.frappe.cloud`)
   - **Region:** Choose closest to venue (Hamilton = N. Virginia, Philly = N. Virginia, Dallas = Dallas)
   - **Apps:** Frappe, ERPNext, hamilton_erp (from `csrnicek/hamilton_erp` repo, `main` branch)

   **🔒 Production version pin — CRITICAL.** When configuring the apps for the new site, frappe and erpnext **MUST** be pinned to a specific tagged v16 minor release (e.g. `v16.3.4`), NOT to the `version-16` branch HEAD and NEVER to `develop`. The hamilton_erp custom app tracks `main`. Auto-upgrade on the production bench MUST be disabled — promote new minor releases manually after staging soak. See **CLAUDE.md → "Production version pinning — tagged v16 minor release, NEVER branch HEAD or develop"** for the full rule, the manual upgrade cadence (monthly review window + 48-hour staging soak), and the rationale (~10 fixes/month land in `version-16` HEAD; auto-pulling them invites production churn).

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
   | Hamilton     | hamilton     | CA_HST   | CAD      | 0          | 1 (DEC-111) |
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

8. (Optional re-seed) The seed patch already ran automatically during step 6's `bench migrate` (it's registered in `patches.txt` under `[post_model_sync]`). The block below is **only** for re-running the seed on an already-migrated site (e.g. after wiping seeded records by hand for testing). For a fresh deploy, skip this step — step 6 already did it.

   ```bash
   bench --site {site} execute hamilton_erp.patches.v0_1.seed_hamilton_env.execute
   ```

   Note the dotted path includes `v0_1` — the patches module is namespaced by version, and `hamilton_erp.patches.seed_hamilton_env.execute` (without `v0_1`) **does NOT resolve and will error out**. The correct path matches the entry in `patches.txt`.

   The seed creates:
   - 59 Venue Assets (26 rooms + 33 lockers) — or venue-specific count if customized
   - Walk-in Customer record
   - Hamilton Settings singleton with defaults

   **Hamilton accounting conventions configured by the seed (see CLAUDE.md → "Hamilton accounting / multi-venue conventions"):**

   The seed patches under `hamilton_erp/patches/v0_1/` (registered in `patches.txt`, applied automatically by step 6's `bench migrate`) install the full Hamilton accounting setup. Operators should know these were applied so they don't re-create or override them by hand:

   - **CAD nickel rounding** — `Currency CAD.smallest_currency_fraction_value = 0.05`. Cash POS sales round to the nearest nickel per Canada's 2013 penny-elimination rule. **Site-global setting** — affects every CAD invoice on the site, not just POS. If a future Hamilton flow creates a CAD invoice for a non-cash workflow (B2B vendor invoice, membership invoice, intercompany invoice), it must explicitly set `disable_rounded_total=1` on that invoice or it will silently round to nickels. The cart's `submit_retail_sale` is the reference pattern: nickel rounding is gated by `payment_method` and disabled for Card payments.
   - **Round Off Account + Cost Center** — linked to the Hamilton cost center (not the Standard CoA "Main" default). Round-off GL entries tie to venue-level reporting.
   - **Mode of Payment "Cash"** — wired to the Hamilton Cash account.
   - **POS Profile "Hamilton Front Desk"** — configured with `write_off_account`, `write_off_cost_center`, and `write_off_limit = 0`.
   - **Price List "Hamilton Standard Selling"** — set as the Company default selling price list (renamed from "Standard Selling" to avoid collision with ERPNext test fixtures).
   - **Fiscal Year covering today** — explicit creation; ERPNext's auto-fiscal-year doesn't cover all CI/install scenarios.

   These conventions are CRA-aware (CAD nickel rule), QBO-mirrored (chart of accounts naming), and verified by the `test_retail_sales_invoice` test module (968 lines, 10 adversarial tests covering rounding gates, permission elevation, stock pre-checks).

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
    - [ ] **🔒 v16 Role-Based Field Masking — PRE-GO-LIVE BLOCKER, supervised migration only.** This is NOT a routine setup item. See `docs/risk_register.md` R-006, R-007, R-012 for full BLOCKER context. Status as of 2026-05-01:
      - ✅ R-006 (Comp Admission Log `comp_value`) — closed by PR #98
      - ✅ R-007 (Venue Session 7 PII fields) — in flight via PR #100; awaiting auto-merge
      - ⏸ Cash Reconciliation field masking (gap #4) — **DEFERRED to Phase 3** alongside the variance redesign in `docs/design/cash_reconciliation_phase3.md` (PR #108). Item ships as 4 of 5 gaps complete.
      - 🔓 R-012 (Cash Drop envelope label print pipeline) — open BLOCKER tracked as Taskmaster Task 30; must close before Hamilton go-live.
      - ✅ Cash Drop `if_owner` row-level isolation (gap #3) — in flight via PR #99.
      Verify each linked PR has merged AND the matching test in `hamilton_erp/test_security_audit.py` passes before checking this box.

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
    - [ ] Correct color coding and tier badges displayed

    **Note:** "Mark All Clean bulk action" is no longer a smoke-test step — the Bulk Mark All Clean feature was REMOVED per `docs/decisions_log.md` "A29-1 Bulk 'Mark All Clean' feature REMOVED" (DEC-054 reversed). Do NOT re-add this test step or attempt to resurrect the deleted endpoints (`mark_all_clean_rooms`, `mark_all_clean_lockers`, `_mark_all_clean`). The asset board now uses per-tile clean actions only.

---

## Phase F — Go-Live Verification

### 🛑 DO NOT LAUNCH UNTIL — Risk Register + Phase 1 BLOCKERs cleared

Before flipping the production URL on a new venue, every **Critical / High / PRE-GO-LIVE BLOCKER** entry in `docs/risk_register.md` MUST be CLOSED, and every **Phase 1 BLOCKER** Taskmaster task MUST be in `done` status. The risk register and Taskmaster live in separate files — without this explicit cross-reference, an operator following the playbook can complete Phases A–F successfully while a launch-blocking risk silently sits in the risk register.

**Pre-launch gate (verify each line CLOSED before launching):**

| Source | Item | How to verify |
|---|---|---|
| `docs/risk_register.md` | R-006 — Comp Admission Log comp_value masking | PR #98 merged; `TestCompAdmissionLogValueMasking` passes |
| `docs/risk_register.md` | R-007 — Venue Session PII masking | PR #100 merged; `TestVenueSessionPIIMasking` passes |
| `docs/risk_register.md` | R-009 — MATCH list 1% chargeback threshold | Latent until card-payment integration (Phase 2). Confirm no card-integration code shipped to this venue at launch. |
| `docs/risk_register.md` | R-010 — ERPNext v16 polish-wave fix cadence | Frappe + erpnext pinned to specific tagged v16 minor (Phase A step 2); auto-upgrade disabled |
| `docs/risk_register.md` | R-011 — Cash Reconciliation variance non-functional | Manager training documented; managers know to ignore variance flag until Phase 3 ships |
| `docs/risk_register.md` | R-012 — Cash Drop envelope label print pipeline | Taskmaster Task 30 status = `done` |
| `docs/risk_register.md` | R-013 — Deferred stock validation @ POS Closing | Latent until Phase 2 returns. Confirm refund flow not shipped at launch (cash-only refunds via Task 31 if shipped). |
| Taskmaster Task 31 | Cash-side refunds (Phase 1 BLOCKER) | Status = `done` if refund flow is in scope at launch; otherwise documented as deferred |
| Taskmaster Task 32 | Comps manager-PIN gate | Status = `done` |
| Taskmaster Task 33 | Voids — mid-shift undo | Status = `done` |
| Taskmaster Task 34 | Tip-pull schema | Status = `done` (schema only; full UX is Phase 2) |
| Taskmaster Task 35 | Post-close orphan-invoice integrity check | Status = `done` |
| Taskmaster Task 36 | Zero-value comp item verification test | Status = `done` (test passes against the production-pinned v16 minor) |
| Taskmaster Task 37 | Receipt printer integration (Epson TM-m30III) | Status = `done` |

If any entry above is NOT closed, **do NOT launch.** Either:
- (a) close the entry first, OR
- (b) document an explicit deferral with Chris's written approval (e.g. "Hamilton launches without integrated card payments; standalone Fiserv terminal accepted; integrated card path queued for Phase 2"). Deferrals must be captured in `docs/inbox.md` with date stamp.

The point of this gate is to make it impossible to "complete Phase F" while a launch blocker silently sits in a separate file. The risk register and Taskmaster tracking are NOT optional reading.

### Standard Phase F steps

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
