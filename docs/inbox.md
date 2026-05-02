# Inbox

## 2026-05-01 — Phase 2 hardware research delivered

The five hardware-research entries that lived here are no longer needed in the inbox — each has shipped as a permanent doc. Trail:

- `docs/design/pos_scanner_spec.md` — front-desk ID scanner (Honeywell Voyager 1602g recommended) — PR #87
- `docs/design/pos_hardware_spec.md` — consolidated multi-venue hardware spec (8 categories, Hamilton + Philadelphia + DC + Dallas) — PR #88
- `docs/research/merchant_processor_comparison.md` — Fiserv at Hamilton, Stripe Terminal at new venues — PR #89
- `docs/research/erpnext_hardware_field_reports.md` — community-reports framework (needs WebSearch session to populate) — PR #90

Open questions still pending Chris's input live in each PR's body, not here.

## 2026-04-30 (afternoon) — PR #51 ready for human review

Follow-up to PR #49 (cart UX stub). Ships the QBO-mirrored accounting seed and replaces the cart Confirm stub with real POS Sales Invoice creation. PR: https://github.com/csrnicek/hamilton_erp/pull/51 — auto-merge enabled (squash + delete branch).

### Commits made
- `95cccc3` feat(asset-board): V9.1 Phase 2 cart → POS Sales Invoice with QBO-mirrored accounting seed
- `2389e6c` fix(install): POS Profile requires write_off_account + write_off_cost_center
- `635a77c` chore(tests): remove stale test_bulk_clean reference from /run-tests

### Tests run
Full local suite green on `hamilton-unit-test.localhost` after `bench migrate`. 415 pass / 6 skipped across 17 modules. New `test_retail_sales_invoice` module: 18 tests (9 seed verification + 9 end-to-end submit_retail_sale flow). All 78 `test_asset_board_rendering` tests still pass after replacing the 2 stub-contract tests with 3 positive contracts.

### CI result
CI started immediately on push: claude-review (queued), Linter (queued), Server Tests (in progress). Auto-merge gated on all three passing. Watch at https://github.com/csrnicek/hamilton_erp/actions/runs/25173827418.

### Files changed
13 files, +1294 / -70. New files: `hamilton_erp/test_retail_sales_invoice.py` (340), `hamilton_erp/patches/v0_1/seed_hamilton_accounting.py` (28). Largest existing-file changes: `setup/install.py` (+411), `api.py` (+120), `seed_hamilton_env.py` (+118), `inbox.md` (+90), `asset_board.js` (60 lines redone).

### Remaining risks
1. Production sites with an existing non-`Club Hamilton` company need `bench --site SITE set-config hamilton_company "<name>"` BEFORE migrate, else seed creates a sibling company.
2. Day-one stock seeding still required — the seed deliberately does NOT auto-create Stock Entries. First retail sale on production will fail until a Material Receipt lands the SKUs.
3. `_find_account_parent` heuristic tested only on `country=Canada, chart_of_accounts=Standard`. Country-specific CoAs may have different parent-group naming.

### Rollback notes
Reversible via `git revert -m 1 <merge SHA>`. Seeded artifacts persist on production after rollback (POS Profile, accounts, company) but are inert if the cart UX reverts to stub state. Optional cleanup: `frappe.delete_doc('POS Profile', 'Hamilton Front Desk')`. Item Defaults rows on retail items are additive — only fire when POS Profile is referenced.

### Recommended merge command
Already set: `gh pr merge --squash --auto --delete-branch` — fires when CI green.

### Open questions for Chris
1. **Production company pinning.** Pin `hamilton_company` on `hamilton-erp.v.frappe.cloud` BEFORE running migrate? If so, what's the existing real company name, or should production run under "Club Hamilton" too?
2. **Initial stock on day one.** Want a small follow-up PR that seeds 24 units of each retail SKU as a Material Receipt (gated by `frappe.conf.seed_initial_retail_stock=true`), or do the first Material Receipt manually via Desk?
3. **Phase 2 hardware queue priority.** Receipt printer first (operational impact) or merchant adapter first (longest lead time on processor approval)?

## 2026-04-30 — Frappe Cloud production prep (Tier 0 launch tasks)

Surfaced by the Frappe Cloud production-hosting research session (2026-04-30). These augment the existing Tier 0 foundations in the post-PR-9 cleanup section below. All four are pre-go-live blockers — none can wait until after opening day.

### T0-FC-1 — Enable backup encryption BEFORE any PII or card payments ship

**Action:** `bench --site hamilton-erp.v.frappe.cloud set-config encryption_key '<random-key>'` and store the key in 1Password.

**Why:** Frappe Cloud's backup encryption is opt-in. Default = unencrypted. Without an encryption key, restored backups CAN be opened by anyone with S3 read access to the Mumbai bucket — fine for Phase 1 (no PII, cash-only) but a regulatory landmine the moment Phase 2 next iteration ships card payments (last-4, merchant_transaction_id, customer email/SMS for digital receipts).

**Critical inverse risk:** if the encryption key is set AFTER existing backups are taken, those existing backups are still un-encrypted. Set the key BEFORE any sensitive data lands. Once set, store the key forever — losing it makes encrypted backups unrecoverable.

**Effort:** 5 minutes + 1Password entry.

### T0-FC-2 — Move backup region from Mumbai to Canada or US East

**Action:** Open a support ticket with Frappe Cloud requesting backup region change from default `ap-south-1` (Mumbai, India) to `ca-central-1` (Montreal) or `us-east-1` (Virginia).

**Why:** Default backup destination is an AWS S3 bucket in Mumbai. PIPEDA (Canada's privacy law) doesn't strictly prohibit cross-border data transfer, but customer PII stored in India creates a disclosure obligation in privacy notices and increases the risk surface in the event of a Frappe Cloud account compromise. `ca-central-1` is the gold standard (data residency in Canada); `us-east-1` is a defensible second choice with US Cloud Act implications.

**Time pressure:** Same as T0-FC-1 — must land before Phase 2 next iteration adds PII / card data.

**Effort:** Support ticket + Frappe response time. Frappe-side complexity unknown; may require a plan tier upgrade.

### T0-FC-3 — Verify $40/month plan storage allocation is ≥20 GB

**Action:** Confirm with Frappe Cloud support (or check the bench config UI) that the current $40/month plan includes at least 20 GB of database + file storage.

**Why:** Hamilton's database growth projection: ~1-1.5 GB after Year 1, ~5-8 GB after Year 5 (GL Entry / Sales Invoice / Stock Ledger Entry growth, no partitioning). Plus receipt-bytes retention for chargeback evidence (Phase 2 next): ~2KB/receipt × 600 receipts/day × 365 days = **~430 MB/year just for receipts**. Total 5-year storage need: **~5-10 GB database + ~2-4 GB file storage = ~7-14 GB**. 20 GB gives headroom; below that, Hamilton will need to bump plan tiers mid-year, which is operationally expensive (planned migration window required).

**Effort:** Read the plan dashboard + ticket if unclear. <30 minutes.

### T0-FC-4 — Restore-to-staging exercise to measure actual RTO

**Action:** Trigger a real restore from Frappe Cloud's offsite backup to a staging site (NOT production). Time the operation. Document the actual RTO (recovery time objective in minutes) in the launch runbook.

**Why:** Frappe Cloud advertises 24-hour RPO (daily backups, retention 7d/4w/12m/10y) but **does not publish an RTO**. The actual restore time depends on backup size, S3-to-Mumbai-to-bench bandwidth, and Frappe support response time. Hamilton's measurement IS the operational baseline — without it, the disaster-recovery plan is "do whatever Frappe says" with unknown duration.

**Pass criteria:** Documented RTO < 4 hours for Hamilton's database size (currently small, will grow). If the actual RTO is >24 hours, that's a "consider Dedicated server tier ($200/month) for the < 2-hour critical-issue SLA" decision point.

**Caveat:** Frappe Cloud's docs don't describe whether restore is self-serve via the portal or requires a support ticket. Find out as part of this exercise — the RTO measurement is dominated by whichever path applies.

**Effort:** ~1 hour for the restore + 30 minutes for runbook documentation.

### T0-FC-5 — Verify `/app/asset-board` route works on v16 production

**Action:** After production deploy of Hamilton ERP onto Frappe Cloud, navigate to `https://hamilton-erp.v.frappe.cloud/app/asset-board` and confirm the page loads without redirect issues.

**Why:** v16 renamed the desk frontend route prefix from `/app` to `/desk` (per the v15→v16 migration wiki). Frappe added a redirect for `/app` → `/desk` to preserve backward compatibility, but redirects are exactly the kind of thing that quietly break in production deploys when an nginx config or proxy intercepts the wrong path. Hamilton's POS UI lives at `/app/asset-board`; if the redirect silently fails, the operator gets a 404 on opening day.

**Pass criteria:** GET on `/app/asset-board` either returns the page directly OR returns a 301/302 to `/desk/asset-board` which then returns the page. Either path works; total time-to-render <2s.

**Effort:** 5 minutes (curl + browser verification).

### T0-FC-6 — Verify `Accounts Settings.use_sales_invoice_in_pos` matches Hamilton's flow

**Action:** Read `Accounts Settings.use_sales_invoice_in_pos` on production and document the value. Hamilton's `submit_retail_sale` doesn't depend on this toggle (it sets `is_pos=1` directly on a `Sales Invoice` doc, bypassing the standard POS UI which the toggle controls), but consistency between the toggle state and Hamilton's actual path eliminates surprise behavior.

**Why:** The v16 architecture change (PR `frappe/erpnext#46485`, "feat: sales invoice integration with pos") added this toggle in Accounts Settings. When ON, the standard POS UI creates Sales Invoice records (Hamilton's path); when OFF, it creates POS Invoice records (the legacy path). Hamilton bypasses the standard POS UI entirely by going through the cart drawer + `submit_retail_sale`. But: any future "enable the standard POS UI as a backup" or any operator who opens `/app/point-of-sale` directly will hit the toggle's behavior. Setting it to ON aligns the standard surface with Hamilton's custom surface.

**Recommended state:** ON (Hamilton's path is Sales Invoice). Document the choice in `docs/decisions_log.md` if not already.

**Effort:** 5 minutes.

### T0-FC-7 — Verify stock valuation method is FIFO at company level

**Action:** On `Company "Club Hamilton"` (or whatever Hamilton's pinned company is), confirm `default_in_transit_warehouse` and the per-item / per-company stock valuation method is FIFO.

**Why:** v16 made stock valuation method selectable per-company (was global in v15). The seed doesn't currently set this explicitly — Standard CoA's default is FIFO, which is what Hamilton wants for retail (small SKU count, fast turnover, each unit's cost matches the one before it within $0.01). Moving Average and LIFO are wrong for Hamilton's retail model.

**Pass criteria:** Stock Settings → Valuation Method = FIFO (default) AND Company "Club Hamilton" has no override that flips it to Moving Average.

**Effort:** 5 minutes.

### T0-FC-8 — Restore-to-staging drill against current v16 minor (not launch version)

**Action:** Trigger a restore from production backup to a staging site running the **current** `version-16` minor (e.g., `v16.3.4` if that's the latest tag at the time of drill), NOT the version production was launched with. Run Hamilton's full test suite against the restored data on the new minor.

**Why this is different from T0-FC-4:** T0-FC-4 measures RTO. This drill validates the **migration path** — that Hamilton's actual production data (Sales Invoices, Stock Ledger Entries, Asset Status Logs, etc.) survives a v16 minor upgrade without data loss or schema mismatch. The polish-wave fix cadence (R-010) makes it likely that one of the ~10 monthly fixes touches a doctype Hamilton uses.

**Pass criteria:** All 17 test modules pass on the restored data + new minor. Specifically: GL Entries balance, Stock Ledger Entries reconcile, Sales Invoice → Cash Drop → Cash Reconciliation chain validates.

**Frequency:** Run on every monthly upgrade promotion (per the CLAUDE.md cadence). The first run is pre-launch on whatever minor is current; subsequent runs are part of the normal upgrade flow.

**Effort:** 1-2 hours per drill.

### T0-FC-9 — Resolve `frappe/payments` strategy before go-live

**Action:** Decide whether Hamilton's production bench installs `frappe/payments` (and from which branch) or omits it entirely.

**Why:** ERPNext issue [#51946](https://github.com/frappe/erpnext/issues/51946) — "Payment Gateway Doctype not present in version-16" — has been open since 2026-01-21 with no fix announced as of 2026-04-30. Hamilton's CI installs `frappe/payments@develop` as a workaround for the `IntegrationTestCase` setUpClass test issue. Production code itself doesn't reference Payment Gateway (per `docs/inbox.md` 2026-04-28 production-code reality check), so omitting frappe/payments from production should be safe — but if Phase 2 next iteration's card payment flow ever uses Frappe's Payment Entry / Payment Gateway tooling, the absence becomes a runtime error.

**Three options to evaluate:**
1. **Omit frappe/payments from production.** Lowest risk if Phase 2 next is built on a custom merchant adapter (per inbox merchant abstraction spec) that doesn't use Frappe's Payment Gateway doctype.
2. **Install `frappe/payments@develop`.** Mirrors CI; brings Payment Gateway doctype into production. Risk: develop-branch instability.
3. **Wait for `frappe/payments@version-16`.** Cleanest if it ships before Hamilton goes live; otherwise blocks options 1 or 2 from being decided.

**Decide before:** Hamilton goes live on Frappe Cloud (production deploy). The decision affects bench config which is cleanest set BEFORE the first migration runs against production.

**Effort:** 30-minute review of Phase 2 next iteration's adapter design (does it use Payment Gateway doctype?) + 5-min bench config change.

### Sequencing for the nine

T0-FC-1 through T0-FC-4 are the core Frappe Cloud hardening (pre-PII / pre-card-payments). T0-FC-5 through T0-FC-9 are v16-specific verification and decisions.

All nine should land in the 2-3 weeks BEFORE Hamilton opens:
1. **T0-FC-3 storage check** + **T0-FC-9 frappe/payments decision** first (may need plan upgrade lead time and/or upstream frappe/payments visibility).
2. **T0-FC-1 encryption** next (5 minutes, but blocking T0-FC-4's restore drill — restore drill should test the encrypted-backup path).
3. **T0-FC-2 region change** in parallel (depends on Frappe support response time).
4. **T0-FC-4 RTO drill** + **T0-FC-8 v16-minor migration drill** after deploy is finalized (these need a real production-state backup to test against).
5. **T0-FC-5 / T0-FC-6 / T0-FC-7** verification once production is up (5 minutes each, before opening day).

2026-04-24: V9 of asset board shipped to main as squash commit 1cc9125. PR #8 merged. decisions_log.md Part 3.1 amended (countdown text amber→red). V9 plan archived at docs/design/archive/. NEXT SESSION: update docs/claude_memory.md to reflect V9 shipping; cancel unused Frappe Cloud site (~$40/mo, won't need until deploy 6-8 weeks out).

## 2026-04-27 — Late evening

### CLAUDE.md gap — "follow Frappe v16 conventions" is too vague

Today's CI marathon surfaced that the codebase has been drifting from Frappe v16 conventions even though CLAUDE.md says to follow them. Tests aren't self-contained (they assume seed data exists), lint config didn't match Frappe's tabs-not-spaces formatter, etc. The instruction in CLAUDE.md exists but isn't actionable — it doesn't tell Claude where to find the conventions or what specifically to enforce. Sessions interpret it loosely against general Frappe training knowledge instead of consulting the actual upstream sources.

**Decision for tomorrow-Chris with fresh eyes:** Either (a) add explicit links to Frappe docs + a list of hard rules at the top of CLAUDE.md, or (b) trust CI/linters/conformance tests to catch violations and skip the documentation effort. Probably both.

**Proposed CLAUDE.md additions if going with option (a):**

Add a new section near the top of CLAUDE.md, immediately after the existing "Hard requirements" block:

```markdown
## Frappe v16 Conventions

When writing any Frappe code, consult these sources before writing:
- Frappe docs: https://frappeframework.com/docs/v16/user/en
- Frappe wiki: https://github.com/frappe/frappe/wiki
- ERPNext contributing guide: https://github.com/frappe/erpnext/blob/develop/CONTRIBUTING.md
- Reference implementation: read existing patterns in apps/frappe/ source code

If a convention is unclear, prefer matching what frappe/frappe itself does over inventing something new.

## Hard rules that override defaults

- Tests must be self-contained — each test creates and tears down its own data, no reliance on global seed
- Use tabs, not spaces (matches Frappe formatter; lint config in pyproject.toml already ignores W191/E101)
- Inherit from frappe.tests.UnitTestCase, not unittest.TestCase
- Use frappe.db.get_value(..., for_update=True) for race-condition protection
- Never use frappe.db.commit() in controllers
- Use @frappe.whitelist() with allow_guest=False as the default for any callable method
- Validate permissions in controllers, not in client-side JS
```

The second list is more important than the first — specific rules get followed; vague references get skimmed.

**Why both options matter:** Even with the rules in CLAUDE.md, sessions still drift over long conversations. CI + linters + conformance tests are the actual enforcement. CLAUDE.md is the first line of defense; automated checks are the actual guard rail. Don't pick one or the other — pick both, with CLAUDE.md as the cheap fast option to ship now and Layer 1 conformance tests (Task 25) as the durable enforcement.

**Related deferred work:** The 89 lint findings (78 auto-fixable + 11 manual) and 37 files needing `ruff format` are the concrete artifacts of this drift. Cleanup is straightforward but should happen after Hamilton goes live so it doesn't block Phase 1.

---

## 2026-04-28 — frappe/payments + production deploy question

CI now installs `frappe/payments` (develop branch — no version-16 yet) so `IntegrationTestCase.setUpClass`'s recursive Link-field walk can resolve `Payment Gateway` (Hamilton's 6 doctype tests transitively link to it via User → various ERPNext doctypes).

**Decision for tomorrow-Chris:** Does Frappe Cloud's standard install include `frappe/payments` automatically? If not, do production deploys of hamilton_erp need `frappe/payments` installed alongside ERPNext on Frappe Cloud?

**Production code reality check:** Hamilton's own production code (api.py, install.py, controllers in hamilton_erp/doctype/) has **zero** Payment Gateway references — confirmed via grep. So hamilton_erp does NOT functionally depend on frappe/payments at runtime. The dependency only surfaces during test-record bootstrap (a Frappe internal during testing).

**Implication:** Production deploys probably do NOT need frappe/payments installed for hamilton_erp to work. But if Chris ever runs `bench --site SITE run-tests --app hamilton_erp` on a production site for verification, those 6 doctype tests will fail at setUpClass the same way CI did. If that's a real workflow (production smoke test post-deploy), frappe/payments needs to be on production too.

**Recommendation:** Install frappe/payments on Frappe Cloud as a precaution. It's small and ships from the Frappe team — low risk, eliminates the verification gap. Decide tomorrow with fresh eyes.

**Branch used in CI:** `develop`. frappe/payments has no `version-16` branch yet (only `version-14`, `version-15`, `version-15-hotfix`, `develop`). Once frappe/payments cuts a version-16 branch, switch the workflow checkout to it.

---

## 2026-04-28 — Post-PR-9 cleanup items


### Production monitoring and AI-assisted on-call plan

**Why this plan exists:** Chris's biggest fear is "Hamilton crashes Saturday night and I can't fix it." The realistic 2026 answer isn't "AI fixes it before anyone notices" — that's not production-ready for customer-facing systems handling money. The realistic answer is "30-second incident instead of 30-minute incident" via better detection + faster diagnosis + tier-2 person + AI-proposed fixes Chris approves from his phone.

This plan is sequenced. Don't try to build all of it before launch. The 2-4 weeks AFTER opening is when you build this, because you have real traffic patterns to monitor against.

---

#### Tier 0 — Pre-opening foundations (NON-NEGOTIABLE before Hamilton goes live)

**0.1 Sentry error tracking.** Free tier covers 5k errors/month. Catches Python and JavaScript exceptions, groups similar errors, shows exact line of code and the request that caused it. Already on the production audit T0 list (item T0-4). Estimated effort: 3 hours.

**0.2 Better Stack uptime monitoring.** ~$20/month. Pings hamilton-erp.v.frappe.cloud every 30 seconds. SMS or push notification within a minute of downtime. Already on the production audit T0 list (item T0-4). Estimated effort: 30 minutes.

**0.3 Frappe Cloud backup restore drill.** Already paying for backups in the $40/month plan; verify they actually work by performing one real restore to a staging site. Already on the production audit T0 list (item T0-2). Estimated effort: 1 hour.

**0.4 One Playwright synthetic test.** Run the asset-board check-in flow against production every 5 minutes via GitHub Actions cron. Free if hosted in your existing GitHub Actions minutes. Catches the "system is up but checkout is broken" scenarios that pure uptime monitoring misses. Estimated effort: 2 hours.

**0.5 Tier-2 person identified and trained.** Even part-time. Even Patrick or Andrew if they have technical interest. Document the basics in `docs/ops_runbook.md`. 5 procedures, max 2 pages. Already in Hamilton Launch Playbook V2. Estimated effort: ongoing.

**Tier 0 total cost: ~$20-30/month. Tier 0 total effort: 1-2 days. Build all of this in the week before opening.**

---

#### Tier 1 — Post-launch active monitoring (build during weeks 2-4 after Hamilton opens)

**1.1 Anomaly detection on transaction volume.** If Hamilton normally sees 80 check-ins between 10pm-midnight Saturday, and suddenly sees 0, something is wrong. Even when Sentry shows no errors, absence of activity means something is broken (front desk paralyzed, payment processor down, network issue). Tools: simple SQL query on a 5-minute cron with Slack/SMS alert on threshold breach. Estimated effort: 1-2 days.

**1.2 Background worker heartbeat.** Frappe uses background workers for async tasks. If they crash, work piles up silently. Add a scheduled task that pings every 5 minutes; if heartbeat missing, page someone. Already on the production audit T1 list (item T1-7 "scheduler heartbeat"). Estimated effort: half day.

**1.3 Auto-rollback on bad deploy.** When Frappe Cloud deploys a new version, run the synthetic monitoring (#0.4). If failures spike, automatically roll back to previous version. May be supported natively by Frappe Cloud — check docs first. Estimated effort: 1-3 days depending on Frappe Cloud capabilities.

**1.4 Database query monitoring.** Generic MariaDB monitoring (Percona PMM, ScaleGrid, or Frappe Cloud's built-in if available). Catches slow queries before they become outages. The race-condition risk from the launch playbook would surface here as "lock wait timeouts spiking" minutes before customers notice. Estimated effort: 1 day setup, ongoing tuning.

**1.5 Synthetic monitoring expansion.** Beyond the single check-in flow from #0.4, add: refund flow, cash drop submission, end-of-shift close, comp admission. Each one becomes a Playwright test on the same 5-minute cron. Estimated effort: 1 day per flow, build incrementally.

**Tier 1 total ongoing cost: ~$50-100/month if using paid tools (Checkly $50/month or self-hosted free). Tier 1 build effort: 2-3 weeks part-time.**

---

#### Tier 2 — Claude Code as on-call agent (build month 2-3 post-launch when system is stable)

**The pattern in plain English:**

1. Sentry detects an error
2. Sentry webhook fires to a small script running on a cheap VPS or Frappe Cloud worker
3. Script invokes Claude Code with the error details + access to the hamilton_erp repo
4. Claude Code analyzes the error, proposes a fix, runs it on a staging branch, runs the tests
5. If tests pass: Claude Code creates a PR + texts Chris "fix proposed for [error], PR #234, want me to deploy?"
6. Chris taps yes/no from phone
7. If yes: Claude Code merges, Frappe Cloud auto-deploys, synthetic monitoring confirms green

**Realistic latency:** 5-10 minutes from error to fix-proposal landing on Chris's phone. Saturday night that's the difference between "Hamilton manager calls Chris in a panic" and "Chris taps yes on his phone and goes back to dinner."

**Requirements:**
- Sentry must be live (#0.1)
- Tests must be reliably green (already true after PR #9)
- CLAUDE.md autonomy rules in place (already true)
- A small webhook handler service (Express on a $5 VPS, or a Frappe Cloud worker)
- Claude API budget (estimate $50/month if 5-10 incidents handled per month)
- Twilio or similar for SMS notifications ($1/month)

**Build effort:** 1-2 weeks part-time. The webhook handler is simple; the careful part is the prompt engineering for Claude Code to know what kinds of fixes are auto-proposable vs which need Chris to look at directly.

**Trust-gradient rollout:**
- Week 1: Claude Code only diagnoses (no fix attempt). Posts diagnosis to Slack.
- Week 2-3: Claude Code proposes fixes but doesn't push. Chris reviews proposals on phone.
- Week 4+: Claude Code pushes to staging branch, runs tests, asks for approval before merging.
- Month 2+: For specific narrow categories (e.g. "frontend display bug, no DB changes, all tests pass"), allow auto-merge. Everything else requires approval.

**Tier 2 total ongoing cost: ~$60-80/month. Tier 2 build effort: 1-2 weeks for initial setup, ongoing tuning.**

---

#### Tier 3 — What's NOT realistic in 2026 (so you don't chase it)

**True self-healing agents that fix production without human review.** Exists as research (OpenAI Symphony lays groundwork, Anthropic has experimental Claude agents). NOT production-ready for live customer-facing systems handling money. The risk: AI "fixes" a bug that was actually intentional behavior, breaks something else, no audit trail of what happened.

The conservative version of this fantasy IS Tier 2 above (AI proposes, Chris approves from phone). Don't try to leapfrog to true autonomy until at least 2027 and only after Tier 2 has been running flawlessly for 6+ months.

**Anomaly detection AI.** Things like "Datadog Watchdog" or "New Relic AI" claim to detect anomalies automatically. Worth evaluating in late 2026 for hamilton_erp scale. For now, the simple SQL-cron approach in #1.1 covers 80% of the value at 0% of the cost.

---

#### Total cost when fully built (estimated)

- Frappe Cloud: $40/month (existing)
- Sentry: $0-26/month (free tier likely sufficient)
- Better Stack: $20/month
- Checkly or self-hosted Playwright on GH Actions: $0-50/month
- VPS for Claude Code agent: $5-30/month
- Claude API for on-call agent: ~$50/month
- Twilio: $1-5/month
- Database monitoring: $0-50/month depending on tool

**Total: $115-275/month for a much more bulletproof Hamilton.** Less than one night's revenue at one venue. Easy ROI.

---

#### The honest framing of Chris's fear

"It crashes Saturday night and I can't fix it" is NOT solvable by AI in 2026.

It IS solvable by:

1. Better detection (Sentry, uptime monitoring) — you know within 30 seconds
2. Faster diagnosis (Sentry shows the exact error line) — you know what to fix in 2-3 minutes
3. Tier-2 person with a runbook — they handle 80% of incidents before you're paged
4. AI-proposed fixes (Claude Code on-call agent) — for the 20% that needs you, tap yes/no from phone, fix deploys in 10 minutes
5. Synthetic monitoring — you catch problems BEFORE customers do, sometimes hours before

The combination means: even if Hamilton crashes Saturday night, you're alerted immediately, you see the cause immediately, your tier-2 handles the routine stuff, and for the 20% needing your judgment you tap yes from your phone instead of opening a laptop.

That's not "no one ever sees crashes." It IS "crashes are 30-second incidents instead of 30-minute incidents."

---

#### Recommended sequencing

**Pre-launch (next 2-4 weeks):** Tier 0 only. Don't try to build Tier 1 or 2 before opening. You don't have real traffic patterns to monitor against, and you don't want untested monitoring infrastructure adding new failure modes during launch week.

**Weeks 2-4 post-launch:** Build Tier 1 incrementally as you observe real traffic. Each component takes a half-day to a day. Don't batch.

**Month 2-3 post-launch:** Build Tier 2 when system is stable. Trust gradient: diagnose only → propose only → propose + auto-test → narrow auto-fix categories. Each step takes 1-2 weeks of observation before promoting.

**Month 6+ post-launch:** Re-evaluate. The tooling landscape will be different. What's realistic in November 2026 is not what's realistic now.

### PR #9 MERGED to main — 2026-04-28

**Merge commit:** `98c2d2a0b8438068829904702c5514728d405fad`
**PR:** https://github.com/csrnicek/hamilton_erp/pull/9
**Squash merge:** yes
**Branch deleted:** yes (fix/ci-vendor-setup-action) — origin pruned via `gh api -X DELETE`; local branch still exists for reference, safe to delete with `git branch -D fix/ci-vendor-setup-action`

**What landed in main:**
- GitHub Actions CI workflow (.github/workflows/tests.yml) — runs on every push and PR; 464 tests, 7 conformance assertions
- GitHub Actions linter workflow (.github/workflows/lint.yml) — ruff with continue-on-error (until lint cleanup)
- Install path productionized: _ensure_erpnext_prereqs(), _seed_hamilton_data(), _create_roles() updates, _ensure_no_setup_wizard_loop() called from BOTH after_install and after_migrate
- pyproject.toml: [project.optional-dependencies] test = ["hypothesis"]
- Test fixture fixes: asset_tier "Standard" → "Single Standard", asset_code added to 3 doctype tests
- test_load_10k throughput threshold lowered 10/sec → 5/sec with explanatory comment
- docs/lessons_learned.md: 2026-04-27 CI bootstrap trap entry
- docs/inbox.md: frappe/payments + production deploy decision question

**Branch protection:** Server Tests check NEEDS MANUAL UI STEP. The API PUT to `required_status_checks` returned 404 (token lacks admin scope for branch protection writes). State was NOT modified — verified pre and post are identical (`{strict: false, contexts: [], checks: []}`). To add manually:

> GitHub UI → Settings → Branches → main → Edit protection rule → Required status checks → search "Server Tests" → add it. Save. Estimated 30 seconds.

After adding, optionally also add `Linter` and `claude-review` if you want them required (both are currently non-blocking by design — Linter has `continue-on-error: true` on its ruff steps, but its workflow result is still pass/fail).

**What's still pending in main but uncommitted in working tree:**
- docs/inbox.md has multiple uncommitted appends from this session — review before next commit (the appends include: Frappe v16 conventions gap, frappe/payments deploy question, 4 Post-PR-9 cleanup items including this entry, the PR #9 ready-for-review summary, and the Hamilton Launch Playbook one-liner)
- docs/HAMILTON_LAUNCH_PLAYBOOK.md — uncommitted, ready for Chris to commit when he's ready
- .claude/settings.json.backup, .claude/settings.local.json.backup, V8/ — pre-existing untracked, leave alone

**Open questions for Chris (next session):**
1. Should frappe/payments be installed on Frappe Cloud production? (Decision deferred from PR #9)
2. Lint cleanup — flip continue-on-error off after fixing the 89 findings
3. Test fixture factory refactor (Venue Asset shared helper)
4. Begin Tier 0 monitoring setup per the production monitoring plan in this inbox

**Next Taskmaster work:** continue Phase 1 — Task 17 browser QA (17.3-17.5), then Tasks 18-25 toward the launch-readiness milestone.


---

## 2026-04-28 — Hamilton Launch Playbook

Hamilton Launch Playbook V2 added at docs/HAMILTON_LAUNCH_PLAYBOOK.md — opening-weekend operational risk audit with go/no-go checklist, top 12 risks, front desk runbook, and technical preflight. Review before scheduling opening week prep work.

---

## 2026-04-29 — Overnight autonomous run

**PRs landed (squash-merged to main):**
- **PR #24** — `fix(asset-board): backend enrichment for V9 panels (E8/E11)` — `api.get_asset_board_data` now returns `guest_name` (from Venue Session) and `oos_set_by` (from Asset Status Log → User.full_name). Batched lookups, no N+1. JS panel rendering updated for both expanded panel and Return-to-Service modal.
- **PR #25** — `test(asset-board): pin V9 enrichment fields in schema snapshot` — `guest_name` and `oos_set_by` now in `REQUIRED_ASSET_FIELDS`. Removed two integration tests that hit the `frappe.in_test` short-circuit in `_make_asset_status_log`. Field-presence guard remains.
- **PR #26** — `test(phase1): consolidate H10+H11+H12 E2E tests for Tasks 22-24` — 18 tests, supersedes stale PRs #5, #6, #7 (95 commits behind). Fixes a latent bug in their `real_logs()` context manager: it toggled `frappe.flags.in_test` but `_make_asset_status_log` reads `frappe.in_test` (different module attribute, see lifecycle.py:86 vs frappe/__init__.py:83). Fixed version clears both. _**Status: in CI when this note was written.**_
- **PR #27** — `docs(reviews): pre-Task-25 3-AI deploy review prompts` — paired blind + context-aware review prompts for the Task 25 Frappe Cloud deploy checkpoint. _**Status: queued for auto-merge.**_

**Tomorrow-Chris: close stale PRs**
PRs #5, #6, #7 should be closed with comment pointing at PR #26. They predated the Server Tests CI workflow and contain the `frappe.flags.in_test` bug described above.

**Task 26 — scope is bigger than estimated**
Taskmaster says "Estimated 15 minutes" for fixing stale imports in `test_stress_simulation.py`. Reality:
- 42 tests in the file, **all 42 are currently `@unittest.skip`-decorated** (so file does not fail CI, but contributes zero coverage).
- The stale imports include `assign_asset` (renamed to `start_session_for_asset`, signature changed from positional to keyword-only with new `customer` param), `vacate_asset` (renamed to `vacate_session`, new required `vacate_method` param), and `acquire_lock`/`release_lock` (these don't exist — `locks.py` only exposes the `asset_status_lock` context manager).
- Old API took `admission_type` (Walk-in/Member); new API has no equivalent (membership system is Phase 4).
- Many tests reference `assignment_status` field which is now just `status`.

This is a 2-3 hour rewrite, not 15 minutes. Either rewrite from scratch against the live API or delete the file and replace with a new stress simulation suite scoped to the current state machine. Recommend deletion + new file rather than line-by-line rewrite — too much divergence.

**Phase 1 task status after tonight (Taskmaster IDs)**
- 1-19: done (pre-existing)
- 20: Asset Board realtime listeners — pending, frontend, needs design spec check before code
- 21: Bulk Mark All Clean confirmation dialog — pending, frontend, 3-AI checkpoint after this task
- 22, 23, 24: in PR #26 (E2E coverage). After #26 lands these can flip to "done" in Taskmaster.
- 25: Frappe Cloud deploy + manual QA — pending, requires owner + browser. Review prompts now live in `docs/reviews/review_task25_blind.md` + `review_task25_context.md` (PR #27).
- 26: stale stress simulation — see scope note above. Defer to a dedicated session.
- 27: re-seed local test site — local environment housekeeping, no PR. One bench console invocation.

**Other notes**
- Frappe v16 module attribute gotcha: `frappe.in_test` (module-level boolean at frappe/__init__.py:83) and `frappe.local.flags.in_test` (request-scoped flag) are **independent**. The test runner sets both via `frappe.tests.utils.toggle_test_mode(enable)`. If your code reads one and you toggle the other, you get silent no-ops. Worth a one-line entry in `docs/lessons_learned.md` next time it gets a sweep.
- `_make_asset_status_log` (lifecycle.py:86) is the only place in the codebase reading `frappe.in_test`. E2E tests that need real audit logs use the `real_logs()` context manager from `test_e2e_phase1.py`.

---

## 2026-04-29 — Visual regression testing research

**Recommendation: Do not adopt now. Defer to Phase 2 trigger.** When you do adopt, use **Playwright Python (`pytest-playwright`) with built-in `toHaveScreenshot`**, baselines generated on Linux CI only, no third-party SaaS.

### Why not now (Phase 1, single venue)

1. Phase 1 risk profile doesn't justify it. Single viewport, one operator, behind staff login. Blast radius is "operator notices and tells Chris," not customer-facing.
2. False-positive tax falls entirely on Chris (beginner solo dev). Once you accept three "diff is fine, accept new baseline" PRs in a row without looking, the suite is dead weight.
3. No Storybook → all snapshots are full-page → any layout change anywhere invalidates every baseline. Highest-churn form of visual regression.
4. Existing tests (`test_asset_board_rendering.py` substring contracts + manual QA) cover ~80% of what matters.
5. Tool landscape is moving — picking a stale tool today (BackstopJS, Loki) wastes effort; picking the right one (Playwright) is cheaper in 6 months when `pytest-playwright` is more mature.

### When to revisit — any one of these

- **Trigger A — multi-venue:** second venue (Ottawa or DC) goes live with per-venue CSS branding. Branding drift is what visual regression is uniquely good at catching.
- **Trigger B — Phase 2 POS work begins.** POS UI is more complex (forms, totals, cash flow) and customer-facing. Add visual regression at the start, not retrofit.
- **Trigger C — first production visual bug.** The day Chris merges a CSS change that breaks the Asset Board layout in production and a substring test failed to catch it.
- **Trigger D — Frappe v17 upgrade.** Major framework upgrades reliably change parent-page CSS.

### Tool landscape (as of 2026-04-29, verified via web)

| Tool | Status | Cost | Verdict |
|---|---|---|---|
| **Playwright `toHaveScreenshot`** | Active, built into `pytest-playwright` | Free OSS | **Pick this when trigger fires.** |
| **Percy (BrowserStack)** | Active SaaS | Free 5K/mo, paid $199/mo+ | Overkill for one venue. Vendor risk. |
| **Chromatic** | Active SaaS, Storybook-tied | Free 5K/mo, Pro $149/mo | No Storybook → skip. |
| **BackstopJS** | **STALE** (last commit 2024-09-07, ~19 mo idle) | Free OSS | Skip — wrong direction. |
| **reg-suit** | Active (release 2026-03-16) | Free OSS, BYO storage | Just the comparison half; couples to Node. Skip unless you outgrow Playwright's built-in diffing. |
| **Loki** | **STALE** (~18 mo since last release) | Free OSS | Storybook-only, skip on both counts. |
| **Cypress + plugin** | Active | Free OSS | Frappe community moved off it. Skip. |

### Frappe community standard

There is none. `frappe/erpnext_ui_tests` (Cypress, last push 2022, 16 stars) is abandoned. Newer Frappe apps (`frappe/insights`, `frappe/wiki`, `frappe/meet`) use **Playwright for behavioral E2E** but no pixel-diff regression. Hamilton would be ahead of the curve if it adopted visual regression at all.

### When trigger fires — setup shape

1. Add `pytest-playwright` to dev requirements; `playwright install chromium` in CI.
2. Create `tests/visual/` with 3–5 scenario tests (empty board, mid-occupancy with overtime tile, expanded panel open).
3. Add a `visual-tests` GitHub Actions job that depends on the existing `tests` job, on `ubuntu-latest` (matches baseline platform).
4. Generate baselines once on CI with `--update-snapshots`, commit to `tests/visual/__snapshots__/`.
5. PRs on every change: failures upload diff PNGs as workflow artifacts.

**Why Playwright Python over alternatives:** Python-native (matches `bench run-tests`); no SaaS account or quota; mask + animation handling solves dynamic content (`mask=[locator]` for timestamps, `animations="disabled"` for color flashes); Frappe ecosystem direction (community already moved to Playwright). Scales to multi-venue by parameterizing base URL.

**Estimated effort to deploy first version:** ~1 day (Opus reasoning for dynamic-content masking).

**Estimated maintenance per UI change:** 5–30 min depending on whether new scenarios or just new locators.

### Cheapest catch-the-most-bugs upgrade right now (NOT visual regression)

Add **2 Playwright behavioral tests** (no screenshots): load `/app/asset-board`, assert 59 tiles render, assert each tile has one of the four expected status classes. Half a day of effort. Catches CSS-only regressions, parent-container swaps, and runtime bugs that produce syntactically-correct DOM that renders wrong — none of which `test_asset_board_rendering.py` substring tests can catch. **Track as a new Taskmaster task before Task 25.**

### Sources

- Playwright `toHaveScreenshot` docs (playwright.dev)
- `pytest-playwright-visual-snapshot` (iloveitaly, last push 2026-04-27, active)
- Percy / Chromatic pricing pages (verified 2026-04-29)
- BackstopJS / Loki staleness verified via GitHub last-commit dates
- `frappe/erpnext_ui_tests` abandonment verified (last push 2022-11-30, 16 stars)
- Frappe community Playwright adoption verified via `gh search code` against frappe org

---

## 2026-04-29 — AI bloat audit (3 methods)

**Goal:** Find what to clean up before Task 25 (Frappe Cloud deploy + handoff) so the production codebase is as small as possible.

**Headline:** Codebase is in good shape overall (radon CC avg = A on 52 production blocks, MI grade A across every production module). Real bloat is concentrated in three places: (1) the parallel "DocType whitelisted methods" API in `venue_asset.py` that duplicates `api.py` and is never called from any UI; (2) two pieces of dead JS code in `asset_board.js` that read `asset.oos_days` and `asset.reason` fields the API never returns — **this is a USER-FACING BUG: operators see "Reason unknown" on every OOS tile**; (3) one near-verbatim ~40-line duplicate between `_show_overlay` and `_redraw_overlay`. Phase 2 not-yet-built stubs are intentional placeholders, NOT bloat.

### Method 1 — Claude-prompt audit (top findings)

#### Dead code

1. **`hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py:75-110` — five DocType whitelisted methods are never called from any production UI.** `assign_to_session`, `mark_vacant`, `mark_clean`, `set_out_of_service`, `return_to_service` are exact 1-line delegators to `lifecycle.*`. The Asset Board JS (`asset_board.js:855-859`) calls top-level `hamilton_erp.api.start_walk_in_session` / `vacate_asset` / `clean_asset` / `set_asset_oos` / `return_asset_from_oos` — never the doctype-bound variants. Only `test_venue_asset.py:218,225` references `mark_vacant`/`set_out_of_service`. ~36 lines of parallel API surface that exists only to be tested. Cheapest fix: delete the doctype methods + their two test references.

2. **`hamilton_erp/hamilton_erp/page/asset_board/asset_board.js:344-351` — OOS day-counter badge code is unreachable.** The block reads `asset.oos_days` and renders `<span class="hamilton-oos-days">…d</span>`. But `api.py:get_asset_board_data` (lines 89-95 field list) does NOT include `oos_days` in its enrichment. The `if (asset.oos_days != null)` guard always evaluates false; the `oos_days_html` variable is always empty.

3. **`hamilton_erp/hamilton_erp/page/asset_board/asset_board.js:631, 769` — `asset.reason` is read in two places, never sent by the API.** The OOS expand panel renders `asset.reason` (line 631) and the Return-to-Service modal context line (line 769) reads `asset.reason`. `api.py:get_asset_board_data` does not include `reason` in its `frappe.get_all` field list, so `asset.reason` is always `undefined` and both spots fall back to `__("Reason unknown")`. **USER-FACING BUG.** Fix: add `"reason"` (and `"hamilton_last_status_change"` if computing oos_days server-side) to the `frappe.get_all` field list at `api.py:91`. 5-min fix, zero risk.

4. **`hamilton_erp/tasks.py:4` — `check_overtime_sessions()` is a no-op `pass` body wired into scheduler_events every 15 minutes.** Intentional Phase 1 placeholder per docstring; consumes a scheduler slot that fires 96×/day to do nothing. Acceptable until Phase 2.

#### Unused imports / vars

5. None of substance found. Vulture's flags on `hooks.py` top-level vars (`app_title`, `app_publisher`, `doc_events`, `extend_doctype_class`, etc.) are false positives — Frappe loads these by string name.

#### Over-commenting

6. **`lifecycle.py:138-198` — `_create_session` has a 60-line docstring before 35 lines of code.** A third of it is provenance metadata ("3-AI review I3", "Fix 10, DEC-056") that belongs in `decisions_log.md`, not the source file. Consider keeping operational what+why; move review/decision provenance to `# Decision: DEC-056. Review: lessons_learned.md 2026-04-10.` Saves ~40 lines.

7. **`lifecycle.py:437-446` — 10-line comment justifying why `_set_cleaned_timestamp` is separate from `_set_vacated_timestamp`.** Defensive justification longer than the 3-line function body. Reduce to one line: `# Separate from _set_vacated_timestamp because OOS entry sets neither.`

8. **`locks.py:79-83` — `# TODO(phase-2): distinguish transient contention from stuck-lock recovery…`** Floating TODO with no plan. Either file as Taskmaster Phase 2 task or delete.

9. **`api.py:11-43` — `on_sales_invoice_submit` docstring (24 lines) is longer than the function body (10 lines).** Most describes the `extend_doctype_class` registration mechanism (already documented in `hooks.py`). Trim to ~5 lines: purpose, phase status, realtime payload contract.

#### Duplicated patterns

10. **`asset_board.js:271-308` (`_show_overlay`) and `:533-572` (`_redraw_overlay`) — ~40 lines of near-verbatim duplication.** HTML construction (`status_cls`, `code_html`, `actions_html`, the `<div class="hamilton-expand-overlay…">` template), the `find("[data-action]").on("click.action", …)` handler, and the 6-branch action dispatcher are duplicated verbatim. Only difference: `_show_overlay` adds source-tile dim class + scroll listener; `_redraw_overlay` skips both. Extract `_build_overlay(asset)` returning the `$overlay` element + bound action handler. Saves ~30 lines.

11. **`api.py:280-326` and `venue_asset.py:75-110` — 5 paired wrappers.** Each pair is 6-9 lines of `has_permission` + `from … import` + 1-line delegator. Five of these per file = ~80 lines that could be 0 if either file is deleted. See finding #1.

12. **`api.py:216-230` — `mark_all_clean_rooms()` and `mark_all_clean_lockers()`** are 5-line wrappers around `_mark_all_clean(category=...)`. Could collapse into one whitelisted endpoint. **Verdict: borderline; leave as-is for audit clarity** (2 narrow endpoints permission/audit cleaner than 1 generic).

#### Over-abstraction (mostly verdict: keep)

13. `api.py:180-194 _get_hamilton_settings()` — called once but the defaults-on-fresh-install logic is non-trivial. Keep.
14. `realtime.py:77-92 publish_board_refresh()` — 1-line wrapper around `frappe.publish_realtime`. Pins event-name contract for Phase 2 callers. Keep.
15. `lifecycle.py:59-61 _require_oos_entry` — 3 lines, called once. Borderline; leave as-is.

### Method 2 — Automated tools (vulture + radon)

**vulture findings (production code only, after filtering Frappe-by-name hooks):** zero real dead code. Vulture is largely uninformative on Frappe codebases because the framework dispatches by name (vulture cannot resolve `doc_events`, `extend_doctype_class`, doctype controller class names, or string-method `frappe.call` callsites in JS).

**radon cyclomatic complexity:** average production CC is 2.79 (grade A). Only one above grade A:
- `api.py:52 get_asset_board_data` — grade D (CC ≈ 19). **Justified** (4 query-and-enrich passes to keep query count constant; pinned by `test_get_asset_board_data_under_one_second`).
- `locks.py:46 asset_status_lock` — grade B (CC ≈ 7). **Justified** (TTL check + Lua release branches per 3-AI review).
- `setup/install.py:168 _create_roles` — grade B (CC ≈ 6). **Justified** (idempotent guards inflate count; benign).

**radon maintainability index:** every production module rates A. None below 65. **No MI red flags.**

### Method 3 — Manual file review

**`realtime.py` (92 lines):** Comments are load-bearing (the `after_commit=True` invariant is non-obvious). Two functions emit different events with different payloads — cannot collapse without losing event-name contract. **Verdict: clean.**

**`utils.py` (30 lines):** No production callers in Phase 1; `test_utils.py` is 100%-covered. Cash-Drop adjacent, scheduled for Phase 3. **Verdict: keep — referenced in build phase plan.**

**`venue_session.py` (54 lines):** `before_insert` docstring is 18 lines for a 5-line function with speculative provenance. Could compress to 2 lines. `_set_defaults` and `_validate_session_end` could be inlined into `validate` but the helper-pair pattern is consistent with `venue_asset.py`. **Verdict: trim docstring; leave helpers.**

### Recommended cleanup actions before Task 25

1. **Fix `asset.reason` and `asset.oos_days` user-facing bug.** Effort: 5 min. Add `"reason"` (and `"hamilton_last_status_change"` if computing oos_days server-side) to `api.py:91` field list. **Highest priority — operators see "Reason unknown" on every OOS tile.**

2. **Delete the parallel DocType-method API in `venue_asset.py:75-110`.** Effort: 20 min. ~36 lines + 2 test updates. Risk: low (no JS or Python production caller).

3. **Extract `_build_overlay()` from `_show_overlay` / `_redraw_overlay`.** Effort: 30 min. ~30 lines saved. Risk: medium (Operator action path; needs manual click-test of each action in each status before/after).

4. **Trim `_create_session` docstring** (`lifecycle.py:138-198`). Effort: 15 min. ~40 lines. Risk: zero.

5. **Resolve or delete `TODO(phase-2)` in `locks.py:79-83`.** Effort: 5 min.

**Total realistic cleanup: ~110 lines deleted, 1 user-visible bug fixed, ~75 minutes of work.**

### What is NOT bloat (verified)

- **Triple-layer locking pattern** (Redis + FOR UPDATE + version CAS) — load-bearing per DEC-013.
- **`lifecycle._make_asset_status_log` short-circuits when `frappe.in_test`** — documented (Grok review 2026-04-10); tests that need real logs explicitly clear `frappe.in_test`.
- **`venue_session.before_insert` local import** — prevents documented circular-import hazard.
- **`api.py:get_asset_board_data` 4-query batched enrichment** — pins 1s SLA, multi-venue plan has ~200+ assets per site.
- **Phase 2 stubs** (`assign_asset_to_session` throw, `tasks.check_overtime_sessions` no-op) — intentional.
- **`setup/install.py` layered patches** — each guard fixes a documented Frappe bug.
- **`hooks.py` top-level vars + DocType controller classes** — Frappe loads by string name; vulture false positives.
- **`utils.py` (0 Phase 1 callers)** — Phase 3 cash-drop scheduled work.
- **`venue_asset.py:_validate_status_transition`** — encapsulates state-machine guard + new-record rule; right grain.

### Test suite redundancy audit

**Goal:** Find tests to delete or consolidate before Task 25 to keep the test suite lean as Phase 1 closes.

**Headline:** ~494 tests across 30 modules with 4 high-overlap clusters (state-machine invalid transitions, lock-release-on-exception, version-CAS sweeps, "after vacate, current_session is None"). At least 35-50 tests are pure restatements of an invariant already pinned elsewhere; another ~10-15 are testing Frappe (TimestampMismatch, MandatoryError, DuplicateEntryError) rather than Hamilton. Net cull target: **~50 tests / ~1,200 LOC, no coverage loss.**

**Suite size today:** 494 test methods across 30 modules. Largest concentrations: `test_lifecycle.py` (62), `test_checklist_complete.py` (63), `test_database_advanced.py` (51), `test_asset_board_rendering.py` (45), `test_adversarial.py` (45 — 8 skipped).

#### Pure redundancy (delete or consolidate)

**1. Invalid state-machine transitions tested in 4 places.** The 9 invalid edges of the FSM are exhaustively covered in `test_additional_expert.py::TestAllInvalidTransitions` (5 tests). They are also re-covered by `test_venue_asset.py` doctype tests, `test_e2e_phase1.py::TestH12OccupiedAssetRejection` (5 tests), and `test_lifecycle.py::TestLifecycleHelpers::test_require_transition_throws_on_mismatch`. Recommend deleting `TestAllInvalidTransitions` (~55 LOC) — it duplicates the doctype-folder tests at the same layer.

**2. "Lock released after exception" tested 7+ times** across `test_additional_expert.py`, the 5 inline `verify-release` blocks in `test_lifecycle.py` (lines 132-134, 206-208, 286-288, 422-424, 491-493), `test_extreme_edge_cases.py`, `test_checklist_complete.py`, `test_database_advanced.py`, and `test_adversarial.py::TestFamilyB`. Recommend deleting the 5 inline `verify-release` blocks — the dedicated lock-release tests cover this. ~30 LOC.

**3. Version increments by 1 on each transition — tested 8 times.** Canonical full-sweep: `test_checklist_complete.py::TestEntryExitActionsChecklist::test_version_increments_on_every_transition`. Plus `test_lifecycle.py::TestVersionCAS::test_D3` (direct CAS test). Recommend deleting `test_database_advanced.py::test_version_increments_monotonically` and `test_checklist_complete.py::TestGuardBoundaries::test_version_increments_correctly`. ~15 LOC.

**4. "current_session is None after vacate" tested 5 times.** Recommend deleting `test_database_advanced.py::test_current_session_cleared_after_vacate` and `test_extreme_edge_cases.py::test_current_session_never_silently_left_populated_after_vacate`. ~25 LOC.

**5. "OOS reason whitespace rejected" tested 6 times.** Recommend folding `TestGuardConditionBoundaries::test_oos_reason_single_space_is_rejected` and `test_oos_reason_tab_only_is_rejected` into the F1/F2 NBSP/newline set as parametrized cases. ~15 LOC.

#### Low-value tests (consider deleting)

**1. `test_hamilton_settings.py` is literally `class TestHamiltonSettings(IntegrationTestCase): pass`.** Zero assertions. Delete the file or write the missing tests.

**2. `test_lifecycle.py::TestNamedConstants` (5 tests, lines 880-907).** Pins literal strings. `assertEqual(lifecycle.WALKIN_CUSTOMER, "Walk-in")` is `assertEqual(x, x)` if the import works. ~25 LOC. Delete.

**3. `test_lifecycle.py::TestHamiltonSettingsDefaults` (4 tests, lines 910-940).** Already covered by `test_seed_patch.py::test_seed_populates_hamilton_settings`. ~25 LOC. Fold into seed test or delete.

**4. `test_database_advanced.py::test_frappe_in_test_flag_is_true` (line 468).** Tests the test runner's flag. ~5 LOC. Delete.

**5. `test_database_advanced.py::test_after_migrate_hook_is_importable` and `test_scheduler_job_is_importable` (lines 479-484).** "Function is callable / importable" smoke tests with zero logic. ~10 LOC. Delete.

~~**6. `test_environment_health.py::test_redis_cache_port_reachable` and `test_redis_queue_port_reachable`.**~~ Belong in `/debug-env`, not the suite. If Redis is down, every test fails 30s later anyway. ~30 LOC. ~~Demote.~~ **[✅ DONE in PR #37 2026-04-29]**

#### Framework-testing (delete or refactor to test Hamilton instead)

> **Status: 12/12 tests deleted in PR #37 (2026-04-29). Section retained for historical reference.**

These test Frappe/MariaDB/redis-py behavior, not Hamilton's. If the framework ships a different version with different behavior, they fail for reasons unrelated to Hamilton.

- ~~`test_frappe_edge_cases.py::test_timestamp_mismatch_on_concurrent_save`~~ — testing Frappe's conflict detection. Hamilton's CAS tests cover what we rely on. ~~Delete.~~ **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_frappe_edge_cases.py::test_xss_stripped_from_oos_reason`~~ — testing Frappe's `strip_html_tags`. Hamilton-side XSS test is in `test_security_audit.py`. ~~Delete.~~ **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_frappe_edge_cases.py::test_mandatory_field_enforced_on_insert`~~ — testing Frappe's required-field validator. ~~Delete.~~ **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_frappe_edge_cases.py::test_new_doc_with_fields_pattern`~~ — testing Frappe's constructor signature. ~~Delete.~~ **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_frappe_edge_cases.py::test_frappe_ui_lock_prevents_second_lock` and `test_frappe_ui_lock_persists_across_instances`~~ — testing Frappe's `Document.lock()`. ~~Delete~~ (keep the third test in the class — `test_lifecycle_bypasses_frappe_ui_lock` is Hamilton-specific). **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_frappe_edge_cases.py::TestNamingAndSequence::test_asset_code_unique_constraint_raises_duplicate_entry`~~ — testing the MariaDB UNIQUE constraint. Same invariant in `test_database_advanced.py`. ~~Keep one, delete the duplicate.~~ **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_database_advanced.py::TestMariaDBEdgeCases::test_for_update_locks_row_not_table`~~, ~~`test_datetime_microsecond_precision`~~ — testing MariaDB defaults. ~~Delete the other 3. Document MariaDB requirements in `docs/coding_standards.md`.~~ **[✅ DONE in PR #37 2026-04-29]**
- ~~`test_database_advanced.py::TestRedisEdgeCases::test_incr_returns_integer`~~, ~~`test_incr_at_large_values`~~, ~~`test_nx_flag_prevents_overwrite`~~ — testing redis-py contracts. Hamilton-side is pinned by `test_lifecycle.py::test_C3_incr_return_value_cast_to_int`. ~~Delete.~~ **[✅ DONE in PR #37 2026-04-29]**

**Total: ~14 tests, ~200 LOC.**

#### Pinned-to-implementation (refactor to test behavior, not strings)

**Implementation pins (refactor or delete):**

- `test_asset_board_rendering.py::test_js_defines_show_overlay`, `_position_overlay`, `_hide_overlay` — greps for specific function names. If overlay refactored to an `OverlayManager` class, fails without user-visible regression. Demote to a single test that asserts the file contains "overlay". ~50 LOC.
- `test_js_defines_countdown_threshold_constant` — asserts `COUNTDOWN_THRESHOLD_MIN = 60` appears verbatim. If renamed, fails for non-bug. Same problem with `LIVE_TICK_MS = 15000`. Delete.
- `test_js_reads_guest_name_from_asset` — greps for `asset.guest_name` in the JS source. Destructuring would break. Change to regex allowing destructuring patterns, or move to behavioral test.

**Acceptable behavior pins (keep):**
- `test_js_defines_all_seven_oos_reasons` — pins user-visible reason list.
- `test_css_no_longer_scales_expanded_tile` — pins absence of broken pattern.
- `test_js_does_not_implement_rejected_warning_state` — pins absence of rejected design.
- `test_js_footer_drops_dirty_count_per_v9_spec` — pins V9 Decision 6.2.

#### Slow + redundant (cull)

- `test_extreme_edge_cases.py::test_concurrent_writes_do_not_exceed_connection_pool` — runs 5 full lifecycle cycles for "no leaks." Implicit in every other test. Delete (~1.5s + 20 LOC).
- `test_extreme_edge_cases.py::test_bulk_operation_completes_within_hetzner_request_timeout` — 5-asset perf assertion loosely coupled to 59-asset Nginx reality. Delete or replace with 59-asset stress test (~1s + 30 LOC).
- `test_extreme_edge_cases.py::test_slow_query_does_not_block_indefinitely` — full lifecycle + `< 10s` assertion. If anything takes 10s, operators notice instantly. Delete (~12 LOC).
- `test_database_advanced.py::test_lock_acquisition_under_50ms` — flaky on shared CI. Delete or relax to <500ms (~10 LOC).

#### Recommended actions before Task 25

Ranked by ROI:

1. ~~**Delete framework-testing tests** (~14 tests, ~200 LOC). Effort: 30 min. Risk: zero — these don't test Hamilton.~~ **[✅ DONE in PR #37 2026-04-29]**
2. **Delete `TestNamedConstants` and `TestHamiltonSettingsDefaults` from `test_lifecycle.py`** (9 tests, ~50 LOC). Effort: 5 min. Risk: zero.
3. **Delete duplicate "current_session is None after vacate" tests** (2 tests, ~25 LOC). Effort: 5 min.
4. **Delete the 5 inline `verify-release` blocks in `test_lifecycle.py`** (~30 LOC). Effort: 10 min.
5. **Delete `TestAllInvalidTransitions`** in `test_additional_expert.py` (5 tests, ~55 LOC). Effort: 5 min.
6. **Delete or fold the implementation-string overlay/constant pins** in `test_asset_board_rendering.py` (5-6 tests, ~70 LOC). Effort: 15 min.
7. **Delete `test_hamilton_settings.py` empty pass-class** OR write the actual tests it implies. Effort: 5-30 min.

**Total cull target: ~50 tests, ~500-700 LOC. Suite drops from 494 to ~440 tests. No coverage loss against the lines that matter.**

#### What is NOT redundancy (verified)

- **Schema snapshot in `test_api_phase1.py`** vs. doctype-folder tests — pins API contract vs. individual DocType fields. Keep both.
- **Hypothesis property tests** vs. unit tests — property tests deliberately exercise the same state machine via random sequences. Keep both.
- **6 doctype-folder test files** — layer-1 conformance tests per CLAUDE.md. Keep all 6.
- **Stress simulation 11 tests** — real threads + commits exercise concurrency unit tests can't. Keep all.
- **`test_e2e_phase1.py` 18 "real_logs" tests** — turn off `in_test` short-circuit so audit-log path runs. Different layer. Keep all 18.
- **`test_locks.py::test_A1` and `test_A4`** — different scales (deterministic vs. stress). Keep both.
- **`test_lifecycle.py::TestAuditTrailExactlyOneLog`** — pins 1:1 contract against double-logging. Keep.
- **`test_api_phase1.py::TestAssetBoardHTTPVerb`** — only test driving through `frappe.handler.execute_cmd` with spoofed verb. Documented in DEC-058. Keep.
- **`test_database_advanced.py::TestDatabaseIndexes` (7 tests)** — pin Hamilton's index requirements (Frappe doesn't auto-create on Link fields). Keep all 7.


---

# Browser test session 2026-04-29 — V9 production verification

**Result:** All 6 critical V9 launch-blockers from yesterday confirmed fixed. 25 tests run. Production matches V9 spec for the locker + room lifecycle.

## Bugs to fix

1. **RTS modal shows "Reason unknown"** — OOS reason captured at SET OOS isn't read back on Return-to-Service. Same root cause likely affects asset-record persistence. Repro: OOS L029 with "Lock or Hardware" → click L029 → modal shows "Reason unknown" instead.

2. **RTS modal "SET" line missing timestamp** — shows "by Administrator" but should match OOS audit format ("by ADMINISTRATOR at HH:MM AM/PM").

3. **Watch tab missing active-state styling** — selected tab looks identical whether on it or not. Other tabs invert correctly.

4. **No "dirty since X minutes" timer on dirty tiles** — V9 spec wanted this for cleaner prioritization. Missing on both lockers and rooms.

## Decisions to log in decisions_log.md

- **Tab badge = Available count only** (sellable now). Verified consistent across Lockers, Single, Double, GH Room.
- **Watch badge = OT + OOS combined** (everything needing attention).
- **Watch tab grouping by sub-category subtitles** (e.g. "Single Standard 4") — extends to all tabs per earlier V9.1 amendment discussion.
- **Header PM SHIFT + ADMINISTRATOR are read-only** by design. Shift change / logout live on dedicated pages, not header.

## Minor

- Expanded tile shows "26h 24m elapsed" but collapsed tile shows "26h 24m late" — pick one word.

## Already queued (no action needed)
- L029 audit log query.

---

## 2026-04-29 — L029 audit verification (today's browser-test data)

**Asked:** verify L029 OOS+RTS rows in audit log; check whether asset record persists `oos_reason` and `oos_set_at`.

**Result:** persistence works correctly. The "Reason unknown" symptom is the API-field-list bug, **already fixed by PR #35** (merged today). No data integrity issue; recommended browser-cache + bench-start restart and re-test.

### Audit log (Asset Status Log)

Both rows exist and populate `reason` correctly:

| name | previous_status | new_status | reason | operator | timestamp (UTC) |
|---|---|---|---|---|---|
| 365 | Available | Out of Service | **Lock or Hardware** ✓ | Administrator | 2026-04-30 02:38:41 |
| 366 | Out of Service | Available | Resolved | Administrator | 2026-04-30 02:41:24 |

Two notes:
- Timestamps are 22:38 and 22:41 EDT April 29 (my local), not the 04:05/04:11 PM Chris reported. These are likely from a later test run that overwrote earlier state. The audit log is append-only so earlier rows would still exist; only 2 rows total today, so either earlier tests had been pruned or the 04:05/04:11 PM session was on a different asset code.
- Audit log table exists and is fully wired. Audit logging is **not** Phase 2 — it's Phase 1 (lifecycle.py:70 `_make_asset_status_log`).

### Asset record (Venue Asset L029 / VA-2901) right now

| field | value |
|---|---|
| status | Available |
| reason | NULL |
| hamilton_last_status_change | 2026-04-30 02:41:24.195939 |
| current_session | NULL |

The schema does **not** have separate `oos_reason` or `oos_set_at` fields. It uses:
- `reason` (text) — populated when entering OOS, **cleared when leaving OOS** (lifecycle.py:447, "the reason field is OOS-specific. ANY transition that does not enter OOS clears it").
- `hamilton_last_status_change` (datetime) — bumped on every transition.

Currently NULL is **correct** because L029 has been returned to service. During the OOS window (02:38–02:41 UTC), `asset.reason` was "Lock or Hardware".

### Verified via code review

- `set_asset_out_of_service` → calls `_set_asset_status` with `log_reason=reason`.
- `_set_asset_status` (lifecycle.py:289) writes `asset.reason = log_reason` when `new_status == "Out of Service"`. So persistence works.
- `_set_asset_status` (lifecycle.py:301) clears `asset.reason = None` on any transition out of OOS. So clearing on RTS works.
- Audit log gets the `log_reason` separately via `_make_asset_status_log`. So both rows have their respective reasons (the OOS reason and the RTS reason).

### Root cause of "Reason unknown" in today's browser test

The Asset Board JS reads `asset.reason` from the API payload. Before PR #35, `api.get_asset_board_data` did **not** include `reason` in its `frappe.get_all` field list. So `asset.reason` was always `undefined` in the JS, falling back to the literal "Reason unknown" string.

**PR #35 (merged ~12:22 PM EST today)** added `"reason"` to the field list. The asset record persistence was always working — the bug was purely the API not returning the field.

If Chris's browser test happened with a stale `bench start` process or stale browser cache, the old behavior would still show. **Recommended:** restart bench start (or `bench restart` if running it as a service) to ensure the new api.py is loaded, hard-refresh the browser (Cmd+Shift+R), and re-run the L029 OOS → click L029 reproduction.

### Bug status update for the V9 browser-test session entry (above)

Bug #1 ("RTS modal Reason unknown") is **already fixed in main** as of PR #35. It's not a separate persistence bug. The Task 5 "Fix V9 browser test bugs" PR can drop bug #1 from its scope, narrowing to:

- ~~RTS modal "Reason unknown"~~ (fixed by PR #35; if it still shows after bench restart + browser refresh, file as a fresh bug)
- RTS modal SET line missing timestamp
- Remove "Mark All Clean" feature entirely (per DEC-054)
- Dirty-for-Xm timer

If the "Reason unknown" symptom persists after the user's restart + refresh, the next investigation step is to capture the actual API response payload (browser DevTools → Network tab → `get_asset_board_data` response) and confirm whether `reason` is in the payload for the OOS asset.

## 2026-04-29 — Late evening

### Pre-Handoff Research — Prompt 1 (ERPNext production best practices)

**Headline.** Hamilton ERP is in good structural shape for a v16 custom app — `hooks.py` is well-organized, fixtures are filtered to avoid cross-app contamination, `after_install` is idempotent, and CI runs on the upstream-correct Python 3.14 / Node 24 / MariaDB 11.8 / Redis stack. But there are six concrete gaps a senior Frappe developer would call out at handoff: (1) `hooks.py` line ~69 still uses `extend_doctype_class` correctly but the `override_doctype_class` migration story isn't documented, (2) the wildcard `*` in scheduler/doc_events isn't used yet but its perf trap should be a written rule before Phase 2, (3) `property_setter.json` is empty (0 bytes — known Frappe gotcha, file kept on disk by exporter but contributes nothing), (4) no Sentry/external error monitoring is wired up despite Frappe Cloud's built-in monitoring being analytics-only with no alerting, (5) v16's new `mask: 1` field-level data masking is unused even though comp/payment data would benefit, and (6) there is no documented `init.sh` or fresh-bench bootstrap script — the install path is `bench install-app` + `after_install` only, which works but doesn't capture the full re-create-from-zero workflow a new developer would need. Everything else (patches.txt structure, fixtures filter, role permission gating, audit/version tracking, CI conformance gates) is at or above industry standard for an AI-assisted single-developer build.

---

#### 1. Custom app structure and upgrade safety

**What Frappe expects under `apps/<app>/<app>/`:** the canonical layout is `apps/<app_name>/<app_name>/` with `__init__.py`, `hooks.py`, `modules.txt`, `patches.txt`, plus subdirs for each module containing DocType folders. The outer directory holds `pyproject.toml`, `MANIFEST.in`, `license.txt`, `README.md`, `setup.py`. Hamilton ERP follows this exactly — verified at `/Users/chrissrnicek/hamilton_erp/hamilton_erp/`.

**What breaks `bench update`:**
- Editing core DocType JSON files in `apps/frappe/` or `apps/erpnext/` directly — these get overwritten on `bench update --pull`. Use Custom Field / Property Setter fixtures instead.
- Forgetting to commit `modules.txt` after creating a new module — the migration runner can't find DocTypes whose `module` field references an unlisted module.
- Mixing developer-mode JSON edits with database-only edits without `bench export-fixtures` — schema drift between dev and prod.
- Leaving `developer_mode = 0` in `site_config.json` while editing DocType JSONs locally — changes go to DB only and disappear on next `bench migrate` from a fresh checkout.

**`extend_doctype_class` vs `override_doctype_class` (v16):** `override_doctype_class` has a "last app wins" defect — when two apps both override the same DocType, only the last-installed wins, silently breaking the other app. v16 introduced `extend_doctype_class` which composes mixins via MRO so multiple apps can coexist. Hamilton ERP uses `extend_doctype_class` for `Sales Invoice → HamiltonSalesInvoice` (verified `hooks.py` line 69) — this is the correct v16 pattern. **Concrete rule for handoff:** never reach for `override_doctype_class` in v16+ unless you genuinely need to replace, not extend, the parent class. ([extend_doctype_class proposal #33940](https://github.com/frappe/frappe/issues/33940), [Override doctype hook PR #11527](https://github.com/frappe/frappe/pull/11527))

**Already covered:** Hamilton ERP's app structure, `extend_doctype_class` usage, and modules.txt are correct.

**Gap:** No `CHANGELOG.md` or `app_version` bump policy documented. v16 bench update behavior reads `app_version` to decide whether to run patches; if you forget to bump it the patches still run (driven by `patches.txt` row presence), but a release-discipline note would help the next dev.

---

#### 2. Fixtures

**How declared in `hooks.py`:** the `fixtures` list takes either bare DocType names or dicts with `dt` and `filters`. Filters are crucial — without them, `bench export-fixtures` exports every Custom Field / Property Setter / Role on the site, including ones from other apps. Hamilton ERP gets this right with `[["name", "like", "%-hamilton_%"]]` filters on Custom Field and Property Setter.

**What `bench export-fixtures` exports:** the command iterates the `fixtures` hook from every installed app and writes JSON files to `<app>/fixtures/<doctype_snake_case>.json`. The file is overwritten on every export — there is no merge.

**Empty `property_setter.json` gotcha:** if your filter matches zero rows (or the filter is wrong), the exporter still creates/keeps the file at zero bytes — it does not delete it. Hamilton ERP has this exact symptom: `fixtures/property_setter.json` is 0 lines. This is **not necessarily a bug** — it just means no Hamilton-prefixed Property Setters exist yet — but a senior dev will flag it because (a) it's indistinguishable from a broken filter, and (b) on `bench migrate` the empty array is loaded and silently does nothing. Best practice: either add a comment in the file (`[]` with a header) or delete the empty file and let it regenerate when needed. ([Can't export property setter](https://discuss.frappe.io/t/cant-export-property-setter/131284))

**Always-include fixtures for multi-venue rollout:**
- `Custom Field` with name filter — schema customizations.
- `Property Setter` with name filter — field reorders, defaults, validations.
- `Role` — custom roles must exist before role-permission rows reference them.
- `Custom DocPerm` — role permission rows (otherwise rebuilt sites have empty perm tables for your custom DocTypes).
- `Workflow`, `Workflow State`, `Workflow Action Master` — only if your app uses workflows.
- `Print Format` — if your app ships printable documents.
- `Letter Head`, `Email Template` — if shipped per-venue.
- `Server Script`, `Client Script` — controversial: many teams ban these from fixtures because they're code-as-data and bypass code review. Hamilton ERP's `tests.yml` enables `server_script_enabled = 1` but doesn't ship server scripts as fixtures — that's the right call.

**Gap:** Hamilton ERP's fixtures don't include `Custom DocPerm`. The 6 Hamilton DocTypes all gate by the `Hamilton Operator` role (per memory observation 1691) but the *permission rows themselves* are created in `setup/install.py`, not exported. That works, but means if `install.py` changes a perm row, sites already deployed won't pick up the change without a separate patch. Industry-standard pattern: export `Custom DocPerm` filtered to your roles and let `bench migrate` reconcile.

---

#### 3. Patches

**How `patches.txt` works:** INI-like file with `[pre_model_sync]` and `[post_model_sync]` sections. Each line is a Python module path. Lines must be unique. Frappe records executed patches in `tabPatch Log`; a patch never runs twice. ([Database Migrations docs](https://docs.frappe.io/framework/v15/user/en/database-migrations))

**Section semantics:**
- `[pre_model_sync]` runs *before* DocType JSON → DB schema sync. Use only when you need the OLD schema to migrate data (e.g. you're about to drop a column and want to copy values somewhere first).
- `[post_model_sync]` runs *after* schema sync. All DocTypes already reloaded — no manual `frappe.reload_doc()` needed. **Default for ~95% of patches.** Hamilton ERP correctly puts both v0_1 patches here.

**Hook firing order (full bench migrate cycle):**
1. `before_migrate` (per app, in install order)
2. Pre-model-sync patches (per app)
3. DocType schema sync (all apps)
4. Post-model-sync patches (per app)
5. Fixtures sync (per app)
6. `after_migrate` (per app, in install order)

**`before_install` vs `after_install`:**
- `before_install` — fires before any DocTypes from your app are loaded into the DB. Limited utility; can't reference your own DocTypes yet. Useful for prerequisite checks ("is ERPNext installed?").
- `after_install` — fires after DocTypes loaded but before site is "ready". This is where seed data goes. **Critical v16 detail:** `install_app()` calls `set_all_patches_as_completed()` which marks `patches.txt` lines as done WITHOUT running them. So initial seed data MUST live in `after_install`, not in a patch. Hamilton ERP's `setup/install.py` docstring captures this correctly.

**Right place for idempotent seed data:** `after_install` for first-time seed; a post_model_sync patch for *changes* to seed (e.g. adding a new role to existing sites). Always guard inserts with `frappe.db.exists()` checks.

**Already covered:** Hamilton ERP's two patches and `after_install` follow this pattern correctly.

**Gap:** No documented "patch authoring template." A senior dev expects a docstring on every patch describing what it does, why, and idempotency proof. Hamilton ERP's `seed_hamilton_env.py` and `rename_glory_hole_to_gh_room.py` should both have this — verify next session.

---

#### 4. `hooks.py` best practices

**Wildcard `*` events vs specific DocType events:** `doc_events = {"*": {...}}` fires on every save of every DocType. For an audit-log app, fine. For a single-DocType validation, catastrophic — Frappe's hook dispatcher loads and calls your handler on every Note, every Comment, every File upload. Always prefer `doc_events = {"Sales Invoice": {...}}` over `*` unless you genuinely need universal coverage. ([Run on all event and all doctype](https://discuss.frappe.io/t/run-on-all-event-and-all-doctype/134607))

**Try-except in doc_events (silent failures):** never wrap a doc_event handler body in `try/except: pass`. Frappe relies on hook handlers raising to abort the transaction. A swallowed exception leaves the DB in a half-saved state and produces no error log. **Rule:** if you must catch, log via `frappe.log_error()` and re-raise. The only legitimate catch-and-suppress is for non-critical side effects like analytics pings.

**`extend_doctype_class` vs `override_doctype_class`:** covered in §1 above. Always call `super()` in extended methods.

**`scheduler_events` caching:** scheduler reads `hooks.py` at process start. After editing `hooks.py` you must `bench restart` (or `supervisorctl restart all` in prod) — *and* run `bench --site SITE migrate` so the corresponding `Scheduled Job Type` rows get inserted/updated. Without migrate, the entry exists in `hooks.py` but the scheduler doesn't know about it because Scheduled Job Type is the source of truth at runtime. ([Scheduler not running](https://discuss.frappe.io/t/scheduler-from-hooks-is-not-working/61479), [Scheduler Not Working: Causes and Fixes](https://tidyrepo.com/frappe-scheduler-not-working-causes-and-fixes/))

**Fixtures / patches / installs ordering:** within one bench operation:
1. `before_install` (install only)
2. App's DocTypes loaded into DB
3. Patches (post_model_sync only on install, since `set_all_patches_as_completed` already ran)
4. Fixtures synced
5. `after_install` (install only) OR `after_migrate` (migrate only)

So: do NOT depend on fixtures inside `before_install`, and DO depend on fixtures inside `after_install` (roles from `fixtures/role.json` are loaded before `after_install` fires — Hamilton ERP's `_set_role_permissions` correctly relies on this).

**Already covered:** Hamilton ERP uses specific DocType events (no `*`), uses `extend_doctype_class`, restarts after hook changes (memory observation 915 documented this).

**Gap:** No written rule banning `try/except: pass` in doc_events. Add to `coding_standards.md` before handoff.

**Gap:** Memory observation 1063 flags "hooks.py Line 69 Uses override_doctype_class — Known Bug to Fix" but the current file shows `extend_doctype_class` at line 69. Either the bug was already fixed (likely, given the current file content) or the memory is stale. Verify and clear the observation.

---

#### 5. CI/CD with GitHub Actions

**Canonical workflow shape:** Frappe doesn't ship an officially-published reusable Action — every custom app rolls its own. The community-canonical pattern is what Hamilton ERP's `tests.yml` already does:
1. Service container: MariaDB 11.x with `MARIADB_ROOT_PASSWORD`
2. `actions/checkout@v4` for app + `frappe/frappe@version-16` + `frappe/erpnext@version-16` (+ `frappe/payments@develop` if needed for setUpClass dependency walk)
3. `actions/setup-python@v5` with `python-version: "3.14"`
4. `actions/setup-node@v4` with `node-version: "24"`
5. `npm install -g yarn`
6. apt: `mariadb-client libmariadb-dev libcups2-dev redis-server wkhtmltopdf`
7. `pip install frappe-bench`
8. `bench init --frappe-path <local-checkout> --skip-assets --no-backups --python "$(which python)" --ignore-exist`
9. Trim Procfile (drop `watch:` and `schedule:` lines for CI)
10. `bench get-app --skip-assets <each app>`
11. `bench start &` then poll Redis ports 13000 (cache) + 11000 (queue)
12. `bench new-site test_site --install-app ...`
13. `bench --site test_site set-config allow_tests 1 --parse`
14. `bench --site test_site run-tests --app <app>`

Hamilton ERP's `tests.yml` is unusually thorough — the install-conformance gate (lines 215+) that asserts `desktop:home_page='setup-wizard'` is cleared *without* a follow-up `bench migrate` is exactly the kind of regression pin a senior Frappe dev would write. ([Frappe DevOps CI/CD guide](https://frappedevops.hashnode.dev/how-to-setup-ci-cd-for-the-frappe-applications-using-github-actions))

**Required upstream version pins (do not downgrade):**
- Python: `>=3.14,<3.15` (PEP 695 syntax in Frappe v16 source — older Python fails with `SyntaxError`)
- Node: `>=24` (Frappe's `package.json` `engines.node` enforces this; yarn install rejects Node 20)
- MariaDB: `>=11.x` (UTF-8 charset + JSON column features)
- Redis: any 6+ (bench Procfile spawns its own on 13000/11000)

**Community-published Actions:** none official. Some teams use `rtCamp/frappe-deployer` for deploy steps, but for tests, in-line workflow is the norm. The Frappe wiki has a "Shared Test CI Actions" page but it's a stub — don't rely on it.

**Already covered:** Hamilton ERP's CI is at the high end of community quality (PR #9 hardened it; install-conformance gate is rare).

**Gap:** No nightly cron-triggered run against `frappe:develop` to catch upstream breaking changes early. Add `schedule: - cron: '0 6 * * *'` to a copy of the workflow that points at `develop` instead of `version-16`. This is the single most valuable add for handoff because it gives the new dev early warning of upstream regressions.

**Gap:** No `concurrency:` block in `tests.yml` — concurrent pushes to the same PR all run in parallel. Add `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }` to save CI minutes.

---

#### 6. Role-based permissions and field masking

**Frappe v16 permission model basics (unchanged):** Role + DocPerm row + (optional) User Permission + (optional) Permission Query Conditions. Default deny — every read/write requires an explicit permission rule.

**Permission Levels (perm_level):** group fields by integer level (0, 1, 2, ...). Role can have read/write on level 0 but only read on level 2. This is how you make a field read-only-for-some, editable-for-others without a separate DocType. ([Managing Perm Level](https://docs.frappe.io/erpnext/user/manual/en/managing-perm-level))

**v16's new feature — field-level data masking:** add `"mask": 1` to a DocField. Users without the mask permlevel see `xxxx` placeholders; authorized users see the real value. Coverage: form, list, standard report, REST API (`/api/resource/...`, `/api/method/...`). **Limitation:** custom SQL queries and Query Reports using raw SQL bypass masking — you must mask manually in those code paths. Supports Data, Phone, Password, Currency, Date, Datetime, Float, Int, Link, Dynamic Link, Select, Read Only, Percent, Duration field types. ([Data Masking docs](https://docs.frappe.io/framework/data-masking))

**How to test permissions:** in test code, switch user with `frappe.set_user("operator@example.com")`, then call `frappe.has_permission("DocType", "read", doc=doc)`. For ptype-specific tests use `frappe.has_permission("DocType", ptype="write", doc=doc)`. Reset with `frappe.set_user("Administrator")` in tearDown. The `frappe.tests.IntegrationTestCase` auto-resets user between tests but not within.

**Already covered:** Hamilton ERP gates 6 DocTypes by `Hamilton Operator` role (memory observation 1691). Role fixtures are exported correctly.

**Gap:** Comp Admission Log and Cash Drop both contain financially sensitive data (PIN entries, blind cash totals). Neither uses v16 field masking. Adding `"mask": 1` to the operator PIN and any expected_total fields would be a low-effort, high-signal hardening for handoff. **This is the single most v16-idiomatic improvement available right now.**

**Gap:** No tests assert that `Hamilton Operator` cannot read `Hamilton Manager`-only fields. The role permissions exist; nothing pins them. Add a `test_role_perms.py` with: switch to operator user, attempt read on Hamilton Manager-gated field, assert `frappe.PermissionError`.

---

#### 7. Audit Trail vs Document Versioning

**Document Versioning (`tabVersion`):** enabled by checking `track_changes` on the DocType. On every save, Frappe inserts a Version row containing JSON diff (`{"changed": [[fieldname, old, new]], "added": [...], "removed": [...]}`). Tracks: field changes, child table additions/removals, child table field changes. Does NOT track: deletions of the parent doc, document submission/cancellation transitions (those go to Comment), permission changes, raw SQL writes via `frappe.db.sql()`. ([Document Versioning](https://docs.frappe.io/erpnext/user/manual/en/document-versioning))

**Audit Trail (built-in v16 doctype):** layered on top of Versioning specifically for *submittable* doctypes that get amended (cancelled → new doc with `-1`, `-2` suffix). Audit Trail follows the amendment chain across name changes. Limitation: shows at most 5 amended versions back. ([Audit Trail docs](https://docs.frappe.io/framework/user/en/audit-trail))

**Why you need a custom audit log on top:**
1. Versioning misses **deletes** — when a doc is deleted, its Version rows go too. For regulatory audit you need an append-only log keyed by `(doctype, name, action, user, timestamp)`.
2. Versioning misses **permission changes** — who granted/revoked which role to whom is not tracked. Build a dedicated DocType.
3. Versioning misses **non-doctype state** — Redis lock acquire/release, scheduler job runs, payment gateway calls. These need a custom log.
4. Versioning's JSON-diff format is hostile to compliance reporters — they want columnar data they can pivot in Excel. A custom append-only log with one row per change is friendlier.

**Already covered:** Hamilton ERP has `Asset Status Log` and `Shift Record` which serve exactly this append-only role for asset state and shift events.

**Gap:** Hamilton ERP doesn't enable `track_changes` on its 6 custom DocTypes. Verify next session — for `Venue Session`, `Cash Drop`, and `Cash Reconciliation` the lack of Versioning means an operator can edit a cash_drop after the fact and there's no built-in record. Audit Trail won't help here because these are not submittable. **Recommended:** turn on `track_changes` for all 6 DocTypes, ship as a Property Setter fixture if not already a DocType field default.

---

#### 8. Scheduler Jobs

**Registration in `hooks.py`:**
```python
scheduler_events = {
    "all": [...],          # every ~3 minutes (the system tick)
    "hourly": [...],
    "daily": [...],
    "weekly": [...],
    "monthly": [...],
    "cron": {
        "*/15 * * * *": ["myapp.tasks.every_15_min"],
        "0 9 * * MON": ["myapp.tasks.weekly_monday_9am"],
    },
    "hourly_long": [...],  # for jobs > 5 minutes
    "daily_long": [...],
}
```

**Hamilton ERP's pattern:** `*/15 * * * *` cron registering `hamilton_erp.tasks.check_overtime_sessions`. Currently a no-op stub (memory observation 2309). That's fine for now; the registration is correct.

**The migration gotcha:** `hooks.py` is the **declaration**, but `tabScheduled Job Type` is the **runtime source of truth**. Editing `hooks.py` does NOT add/remove rows in that table. You must run `bench --site SITE migrate` after every change. Without migrate: scheduler's `enqueue_events()` loops over `Scheduled Job Type` rows; your hook entry is invisible to it. This is the #1 cause of "I added a scheduled job but it's not running." ([Scheduler from hooks not working](https://discuss.frappe.io/t/scheduler-from-hooks-is-not-working/61479))

**Other gotchas:**
- `scheduler_enabled` in site_config.json must be `true` (default true on new sites; some Frappe Cloud setups have it false during maintenance).
- Procfile must include `schedule:` line (Hamilton ERP's CI deliberately strips this — fine for tests, but make sure prod has it).
- Long-running jobs (>5 min) must use `hourly_long` / `daily_long` event names to run on the long worker queue, otherwise they hit the default worker timeout (300s).
- Each scheduled job runs as user `Administrator` — if your task does `frappe.has_permission()` checks, they pass trivially.

**Already covered:** Hamilton ERP's scheduler entry is registered correctly with cron syntax.

**Gap:** `check_overtime_sessions` is a no-op stub. For handoff, either remove the registration entirely or implement the body. A no-op scheduled job pollutes `tabScheduled Job Log` with success rows for nothing.

---

#### 9. Frappe Cloud error log monitoring

**Built-in error log:** `tabError Log` DocType, populated by `frappe.log_error(title, message)`. Accessible at `/app/error-log`. Retention: rows older than `error_log_retention_days` (default 30) are deleted by the daily `frappe.utils.scheduler.cleanup_email_log` patch. **No alerting** — you must check manually or build a notification.

**Frappe Cloud-specific monitoring:** the dashboard's "Analytics" tab shows requests/min, CPU usage, background jobs, uptime (every 3 min ping). `web.log`, `web.err.log`, `worker.log`, `worker.err.log` are downloadable from the Logs section. **Critically, there is no built-in alerting on Frappe Cloud** — analytics are visualization-only. ([Frappe Cloud Logs](https://docs.frappe.io/cloud/logs), [Frappe Cloud Monitoring](https://docs.frappe.io/cloud/sites/monitoring))

**Logs that persist vs ephemeral:**
- Persist (DB): Error Log, Activity Log, Email Queue, Scheduled Job Log, Version (per DocType).
- Ephemeral (file): web.log, worker.log — rotated, not backed up. Lost on container restart in some Frappe Cloud configurations.
- Persist with retention: Error Log Snapshot (saved request payload), retention default 7 days.

**Sentry integration:** the [ParsimonyGit/frappe-sentry](https://github.com/ParsimonyGit/frappe-sentry) app monkey-patches `frappe.log_error` to forward to Sentry. v14-tested; community reports of v15 working with minor patches; v16 untested as of 2025-11. **Recommended pattern:** wire Sentry's `sentry_sdk` initialization into a custom `app_init` hook (or in `hooks.py` module-load) and add `before_request` / `after_request` instrumentation for tracing. ([frappe-sentry repo](https://github.com/ParsimonyGit/frappe-sentry))

**Gap:** Hamilton ERP has zero external error monitoring. For a single-venue go-live this is acceptable (Chris reads error log manually). For 6-venue rollout it is not — you need at minimum a daily email digest of new Error Log entries. Quick fix: add a daily scheduled job that queries `tabError Log` for `creation > now() - 1d` and emails Chris if count > 0. Better fix: Sentry. **Decision required at handoff.**

**Gap:** No log retention policy documented. Frappe defaults are fine but the new dev should know what they are.

---

#### 10. `init.sh` / startup script pattern

**No standard.** Frappe's `bench init` creates a bench skeleton, then `bench get-app` + `bench install-app` add your code, but there is no canonical "fresh-bench bootstrap" script in the framework. Each shop rolls their own. The Anthropic harness pattern (single shell script that idempotently installs all needed apps and seeds reference data) does map cleanly onto Frappe.

**Recommended pattern (idempotent fresh-bench script):**
```bash
#!/usr/bin/env bash
set -euo pipefail

BENCH_DIR="${BENCH_DIR:-frappe-bench-hamilton}"
SITE="${SITE:-hamilton.localhost}"

# 1. Bench init — guard with -d check
[ -d "$BENCH_DIR" ] || bench init "$BENCH_DIR" --frappe-branch version-16 --python python3.14

cd "$BENCH_DIR"

# 2. Get apps — bench get-app is idempotent (checks existing dir)
bench get-app --branch version-16 https://github.com/frappe/erpnext
bench get-app --branch develop https://github.com/frappe/payments  # for setUpClass dep walk
bench get-app --branch main https://github.com/csrnicek/hamilton_erp

# 3. Site — guard with bench --site list
if ! bench --site "$SITE" list-apps >/dev/null 2>&1; then
    bench new-site "$SITE" --admin-password admin --mariadb-root-password admin \
      --install-app erpnext --install-app payments --install-app hamilton_erp
fi

# 4. Config — set-config is idempotent
bench --site "$SITE" set-config allow_tests 1 --parse
bench --site "$SITE" set-config developer_mode 1 --parse

echo "OK — bench ready at $BENCH_DIR / site $SITE"
```

**What it should configure:** developer_mode (dev only), allow_tests (test site only), maintenance_mode off, scheduler enabled, admin_password, db_host/db_port if non-default.

**What it should NOT do:** modify production data, install fixtures from a different branch, hardcode secrets (use `${ADMIN_PASSWORD:?must set}` instead).

**Gap:** Hamilton ERP has no such script committed. The `tests.yml` workflow performs equivalent steps but is GHA-specific — a new dev cloning fresh has to read the workflow and reverse-engineer it. **Add `scripts/init.sh` for handoff.** Estimated effort: 30 min.

---

#### 11. What a clean professional handoff looks like

A senior Frappe dev receiving this codebase will look for these artifacts in this order:

**Confidence signals (Hamilton ERP has these):**
- `CLAUDE.md` / `README.md` with bench setup, test invocation, deploy steps. **Present.**
- `docs/decisions_log.md` with numbered decisions and dates. **Present** (DEC-001 through DEC-060).
- `docs/coding_standards.md`. **Present.**
- CI workflow that runs on PR + push, passes green. **Present** (`tests.yml`).
- Test suite covering happy path + adversarial + edge cases, >80% coverage on critical modules. **Present** (306+ tests, 14 modules per CLAUDE.md).
- `pyproject.toml` with pinned dependencies + `[test]` extra. **Present** (verified in `tests.yml` step "Install hamilton_erp test extras").
- Idempotent `after_install` and `after_migrate` hooks. **Present** (`setup/install.py`).
- Filtered fixtures (no cross-app contamination). **Present.**
- Conformance tests (assert install path produces correct state). **Present** (the desktop:home_page gate).

**Confidence signals (Hamilton ERP missing):**
- `CHANGELOG.md` with version → date → changes. **Gap.**
- `scripts/init.sh` for fresh-bench bootstrap. **Gap.**
- External error monitoring (Sentry or daily digest). **Gap.**
- Production runbook (how to deploy, how to roll back, how to handle X failure). Some of this is in `docs/venue_rollout_playbook.md` but not phrased as a runbook. **Partial.**
- Architecture diagram (3-layer locking, asset state machine, data flow). **Gap** unless it's in `docs/design/` and I missed it.
- `SECURITY.md` (vuln reporting policy, supported versions). **Gap.**
- Load test results from a representative bench. **Present** (`test_load_10k.py` exists; results need a write-up).

**Lack-of-confidence signals (avoid):**
- `# TODO`, `# FIXME`, `# HACK` comments scattered in code without tracking.
- Tests that import but don't actually assert (rubber-stamp tests).
- Commented-out code blocks > 10 lines.
- `print()` calls left in production code.
- Hardcoded paths, passwords, or URLs.
- Tests that depend on global seed and break in isolation.
- A `requirements.txt` AND a `pyproject.toml` (pick one).
- Empty fixture files (looks like a misconfigured filter).
- `override_doctype_class` in v16 code (use `extend_doctype_class`).

**Top-3 handoff priorities ranked by ROI:**

1. **Add Sentry or equivalent error monitoring.** No senior dev will accept a multi-venue production deploy with manual error-log review. Highest ROI.
2. **Enable v16 field masking on Cash Drop's `expected_total` and Comp Admission Log's PIN field.** This is the most v16-idiomatic improvement available and signals "this dev is up to date with v16 features." Low effort.
3. **Write `scripts/init.sh`.** Lets the new dev clone, run one command, get a working bench. Reduces ramp-up from 2 hours to 5 minutes.

**Citations / references:**

- [Frappe Hooks Reference](https://docs.frappe.io/framework/user/en/python-api/hooks)
- [Frappe v16 Migration Wiki](https://github.com/frappe/frappe/wiki/Migrating-to-version-16)
- [Frappe v16 Release Notes](https://frappe.io/releases/version-16)
- [extend_doctype_class proposal #33940](https://github.com/frappe/frappe/issues/33940)
- [Database Migrations docs](https://docs.frappe.io/framework/v15/user/en/database-migrations)
- [Audit Trail docs](https://docs.frappe.io/framework/user/en/audit-trail)
- [Document Versioning](https://docs.frappe.io/erpnext/user/manual/en/document-versioning)
- [Data Masking docs](https://docs.frappe.io/framework/data-masking)
- [Managing Perm Level](https://docs.frappe.io/erpnext/user/manual/en/managing-perm-level)
- [Frappe Cloud Logs](https://docs.frappe.io/cloud/logs)
- [Frappe Cloud Monitoring](https://docs.frappe.io/cloud/sites/monitoring)
- [Frappe Cloud App Patches](https://docs.frappe.io/cloud/benches/app-patches)
- [Frappe-Sentry app](https://github.com/ParsimonyGit/frappe-sentry)
- [Scheduler from hooks not working](https://discuss.frappe.io/t/scheduler-from-hooks-is-not-working/61479)
- [Run on all event and all doctype](https://discuss.frappe.io/t/run-on-all-event-and-all-doctype/134607)
- [Can't export property setter](https://discuss.frappe.io/t/cant-export-property-setter/131284)
- [Override doctype hook PR #11527](https://github.com/frappe/frappe/pull/11527)
- [Mastering ERPNext 16 Custom App Guide](https://davidmuraya.com/blog/develop-erpnext-custom-app/)
- [Frappe DevOps CI/CD guide](https://frappedevops.hashnode.dev/how-to-setup-ci-cd-for-the-frappe-applications-using-github-actions)
- [Frappe v16 release feature summary](https://tcbinfotech.com/frappe-version-16-release-notes/)

---

### Pre-Handoff Research — Prompt 4 (Multi-venue portability)

**Headline:** Hamilton ERP's existing knowledge architecture (CLAUDE.md, claude_memory.md, decisions_log.md, lessons_learned.md, venue_rollout_playbook.md, Hamilton Settings SingleType) is fundamentally sound and mostly canonical for Frappe v16, but it has three structural gaps that will cost you on venue #2: (a) docs are chronological-only with no venue tag or topic index, so a Philadelphia-builder Claude can't ask "what does Hamilton know about cash drops" in one query; (b) the feature-flag layer is split between `site_config.json`, `Hamilton Settings`, and hardcoded venue logic with no documented decision rule on which to use when; (c) fixtures live in the repo (correct) but there is no `apply_venue_config.py` patch that idempotently materializes a venue from a single declarative config file, so onboarding still has manual steps. Fixing these three things — venue-tagged + topic-indexed docs, a written feature-flag decision rule, and a single-config-file venue installer — is what makes venue #2 50% faster than venue #1.

#### 1. Repo vs AI memory vs external docs — what should live where

The current buckets are roughly right. Mapped to canonical purpose:

| Bucket | Current file | Purpose | Status |
|---|---|---|---|
| Hard rules + style | `CLAUDE.md` | Rules that must apply to every code change | Good |
| Session bridge | `docs/claude_memory.md` | "What was done last session, where to start" | Good — but bloating (802 lines) |
| Architectural decisions | `docs/decisions_log.md` | Why we chose X, what alternatives we rejected | Good |
| Bug retrospectives | `docs/lessons_learned.md` | What broke and how we fixed it | Good — but venue-agnostic format |
| Deploy runbook | `docs/venue_rollout_playbook.md` | Step-by-step new-venue checklist | Thin (156 lines) |
| Inbox | `docs/inbox.md` | claude.ai → Claude Code bridge | Working as designed |

**Gap:** no operations runbook for after a venue is live. The playbook stops at go-live. Each venue site needs documented procedures for: rotating an operator password, handling a stuck Redis lock in production, restoring a corrupt cash-drop, resetting setup_wizard.

**Gap:** no `docs/venue_config_schema.md`. There is no single document that lists every per-venue configurable knob (tabs, currency, tax_mode, tablet_count, asset categories enabled, room count, locker count, etc.) with type, default, and where it lives.

**Improve:** `claude_memory.md` is becoming a chronological session log instead of an index. At 802 lines it's eating context budget on every session. Split it: keep a short top-of-file "current state + last session summary" (max 100 lines) and move pre-2026-04-15 history to `docs/retrospectives/claude_memory_archive_2026Q1.md`.

**Missing bucket:** `docs/venue_config/<venue>.yaml`. A declarative per-venue config file. Today the venue-specific values are scattered across the playbook table, hardcoded in JS (`venueConfig.tabs`), and implied in DEC-061..DEC-066. Centralize.

#### 2. Doc structure for portability — venue-tagged, topic-indexed, hybrid

**Today's structure is chronological-only.** That works for Hamilton-the-only-venue. It fails the moment a Philadelphia Claude session asks "show me everything we know about cash drops."

**Proposal:** every entry gets two tags: `[venue]` and `[topic]`.

```
## DEC-061 — Tab visibility uses combined config + data rule
- Date: 2026-04-13
- Venues: [all]
- Topic: [asset-board, frontend, venue-config]
- Status: LOCKED
- ...

## LL-014 — Multi-tenant fixture export trap
- Date: 2026-03-18
- Venues: [hamilton]
- Topic: [fixtures, deployment]
- ...
```

Add a topic index at the head of each file. A venue-#2 Claude session can grep `[venue:hamilton]` to find Hamilton-specific lessons, and `[venues:all]` for cross-venue invariants.

**Improve:** promote `docs/decisions_log.md` Part 1/2/3 structure into a real ADR (Architecture Decision Record) format. The current file mixes ADRs (DEC-001, DEC-002...) with prose sections. Pure ADR format (one decision per `## DEC-NNN` heading, with Context / Decision / Consequences subsections) matches what ChatGPT and Grok will expect when reading the file in 3-AI review.

#### 3. Git branching strategy — single main, per-venue config files

Frappe Cloud's architecture documents the canonical answer. Per [Frappe Cloud Benches docs](https://docs.frappe.io/cloud/what-are-benches-and-bench-groups): "A Bench is a collection of apps and sites where all sites on a Bench share the same configuration."

**Recommendation: single `main` branch, per-venue config files. Do NOT use per-venue branches or per-venue forks.**

- Per-venue branches diverge fast. Frappe and ERPNext push 5–20 commits per week to develop. Maintaining 6 long-lived venue branches and rebasing each one onto main is a maintenance tax that compounds.
- Per-venue forks lose CI symmetry.
- Per-venue config files match Frappe Cloud's mental model. Frappe Cloud expects one app, one repo, one branch, many sites. Each site gets its own `site_config.json`.

**The "Group House Room category" problem (Hamilton has it, others won't) is a feature-flag problem, not a branching problem.**

**For Frappe Cloud release groups:** use one private bench per region, not per venue. `bench-canada` → Hamilton (Toronto, Ottawa eventually); `bench-us-east` → Philadelphia, DC; `bench-us-central` → Dallas. This batches deploys within a region and lets you stagger v16.x → v16.y upgrades by region, not by venue.

**Tags:** use git tags for production releases. `v0.4.0-hamilton`, `v0.4.1-hamilton-fix-cashdrop`. Frappe Cloud can pin a bench to a tag rather than a moving branch, which is the safest pattern for production.

#### 4. Feature flags in Frappe — canonical pattern is layered

Frappe gives you four mechanisms. Each has a canonical use. **Document the decision rule in CLAUDE.md** so future Claude sessions don't reinvent.

| Mechanism | Where it lives | When to use | When NOT to use |
|---|---|---|---|
| **`site_config.json`** | Per-site JSON, accessed via `frappe.conf.get("key")` | Static venue identity (venue_id, currency, tax_mode), boolean feature toggles, secrets/API keys | User-editable settings, anything that needs validation, anything with a UI |
| **SingleType DocType (e.g., `Hamilton Settings`)** | One row per site in DB, has Desk UI | User-editable settings (tablet_count, default_session_duration, cleaning_threshold_min) | Bootstrap config (chicken-and-egg if needed before DocType exists) |
| **Custom Field with site default** | Per-site DB row | Per-document-type defaults (e.g., default warehouse on Sales Invoice) | Cross-cutting venue identity |
| **Property Setter** | Per-site DB row | Modifying existing DocType field properties (hidden, mandatory, default, options) per venue | Anything that needs business logic |
| **`frappe.get_hooks()` + conditional** | hooks.py code | Conditional registration of doc_events, scheduler tasks, override classes | Runtime-flippable flags (hooks load at boot) |

**Canonical decision rule (recommend adding to CLAUDE.md):**

1. Bootstrap / identity / secrets → `site_config.json`. Set with `bench --site X set-config key value`. Read with `frappe.conf.get("key", default)`.
2. User-editable runtime settings → `Hamilton Settings` SingleType.
3. Per-DocType field tweaks → fixture (Custom Field or Property Setter), filter-scoped.
4. Hook-level conditional → read `site_config.json` inside the registered handler, not at registration time (per [issue #24680](https://github.com/frappe/frappe/issues/24680), `frappe.conf` is not always populated at hooks-load time).

**Where Hamilton ERP gets this right today:** `Hamilton Settings` SingleType for venue runtime config. `site_config.json` flags. Filter-scoped fixtures in hooks.py.

**Gap:** no documented decision rule. Write the rule into CLAUDE.md and into a new `docs/venue_config_schema.md`.

**Improve:** rename `Hamilton Settings` → `Venue Settings`. It encodes Hamilton in the DocType name, but it's installed on every venue site. Per Frappe naming conventions, settings DocTypes are usually generic (`Stock Settings`, not `ERPNext Stock Settings`). Low-risk rename via a Frappe rename DocType patch but should be done before Philadelphia goes live.

#### 5. Fixtures + Patches strategy — declarative venue config + idempotent installer

**The canonical fixtures-from-app-source-not-from-site pattern.** Hamilton ERP already does this right via the filtered hooks.py declaration. Filters prevent the trap [documented in this thread](https://discuss.frappe.io/t/bench-export-fixtures-includes-custom-field-added-by-erpnext-patches/73805) where bench captures Custom Fields added by ERPNext patches that don't belong to your app.

**What goes in committed fixtures (Hamilton already does):**
- Custom Fields filtered to `*-hamilton_*` naming pattern
- Property Setters filtered to `*-hamilton_*`
- Roles: `Hamilton Operator`, `Hamilton Manager`, `Hamilton Admin` (filtered by name list)

**What does NOT go in committed fixtures:**
- Venue Asset records (the 26 rooms + 33 lockers) — venue-specific data
- `Hamilton Settings` singleton row — venue-specific
- Letter Heads, Print Formats with venue branding — venue-specific
- Any DocType row that contains a Link to a user, customer, or company

**Gap:** Hamilton ERP loads venue-specific data via `seed_hamilton_env.execute` patch, hardcoded. Philadelphia would need either a separate `seed_philadelphia_env.execute` patch (duplication) or, better, a single `apply_venue_config.py` patch that reads from a per-venue config file.

**Recommended:** declarative per-venue config + one idempotent installer.

```
docs/venue_config/hamilton.yaml
docs/venue_config/philadelphia.yaml
docs/venue_config/dc.yaml
docs/venue_config/dallas.yaml
```

Each file declares everything that differs (venue_id, venue_name, currency, tax_mode, tablet_count, features, tabs, assets/rooms/lockers).

Then a single patch `hamilton_erp/patches/v0_2/apply_venue_config.py`:

```python
def execute():
    venue_id = frappe.conf.get("anvil_venue_id")
    if not venue_id:
        frappe.throw("anvil_venue_id not set in site_config.json")
    config = load_venue_config(venue_id)
    apply_settings_singleton(config)
    apply_assets(config)
    apply_features(config)
```

Idempotency via `frappe.db.exists()` guards (already required by Hamilton's CLAUDE.md hard rules).

**Letter Heads + Print Formats:** keep one *template* in fixtures (e.g., `LetterHead-anvil_template`) and have the venue config patch clone it with the venue's name and address. Don't commit per-venue letter heads.

**Custom Fields on standard ERPNext DocTypes (e.g., Sales Invoice):** keep in committed fixtures with the `-hamilton_` filter.

**Property Setters that need to differ per venue** (e.g., default value differs between Hamilton CAD and Philadelphia USD): should NOT be Property Setters — make them Custom Fields with a venue-config-driven default.

**Improve:** add `docs/venue_config_schema.md` documenting every key in the YAML schema with type, default, and which Frappe mechanism it maps to.

#### 6. What's missing — the second-venue gap

Distilled across forum threads on multi-tenant setup, fixture-includes-other-app-fields trap, and the [Site Fixture feature request](https://github.com/frappe/frappe/issues/36398):

1. **Fixture filtering is not the default.** First-time builders run `bench export-fixtures` without a filter, capture every Custom Field on the site, commit it, and deploy to venue #2 — which now has Custom Fields it shouldn't. **Hamilton already mitigates this** with the `name like %-hamilton_%` filter.

2. **Custom Field naming convention matters as a fixture filter.** Hamilton's `-hamilton_` suffix is workable.

3. **`Single` DocType data** is included in fixtures only if explicitly listed. **Hamilton already does NOT export Hamilton Settings as a fixture.** Correct.

4. **Workspaces and Dashboards are global app fixtures, not site-overridable.** If Hamilton's `Asset Board` Workspace gets edited on the Hamilton site and re-exported, that change deploys to Philadelphia too. **Discipline:** edit Workspaces in code, never via Desk on the dev site.

5. **`bench migrate` order matters across multiple sites on the same private bench.** If a fixture introduces a new Required field on a DocType that already has rows, migrate fails on the older site first. **Mitigation:** every new Required field gets a default and a backfill patch that runs before the field becomes required.

6. **Frappe Cloud's auto-deploy fires on every push to main.** A single PR merge deploys to all six venues simultaneously. **Mitigation:** Frappe Cloud release groups (separate benches per region) let you stagger.

7. **No `bench rollback` for custom fixtures.** Once a Custom Field fixture deploys, removing it from hooks.py + main does NOT remove the field from the DB. **Mitigation:** every field deletion is a paired commit (remove from fixtures + add a `delete_field.py` patch).

**The thing nobody documents: the second-venue test plan.** Hamilton's test suite all runs against `hamilton-unit-test.localhost`. **Gap:** add a CI job that creates a fresh `philadelphia-unit-test.localhost` site, installs hamilton_erp, runs the venue_config installer with `philadelphia.yaml`, and asserts the site is in the expected state.

#### 7. The actual venue rollout sequence

**Phase 0 — Pre-purchase (manual, ~1 day)**
- Confirm region; venue ID slug; write `docs/venue_config/<venue>.yaml` and PR-merge BEFORE provisioning; decide bench grouping.

**Phase A — Frappe Cloud provisioning (manual, ~10 min)**
- Buy subscription; create site via dashboard; install apps frappe → erpnext → hamilton_erp; verify load.

**Phase B — Initial site config (automatable, ~5 min)**
- `bench set-config anvil_venue_id <venue>`, `anvil_currency`, `anvil_tax_mode`, `venue_features`.

**Phase C — Apply venue config (automatable, ~2 min) — NEW**
- `bench --site <site> migrate` (loads fixtures)
- `bench --site <site> execute hamilton_erp.patches.v0_2.apply_venue_config.execute`
- Verify with `frappe.get_doc("Venue Settings").venue_id == "<venue>"`.

**Phase D — Operator setup (manual, ~30 min)**
- Create operator User accounts; assign Roles; first-login flow.

**Phase E — Pre-launch testing (automatable, ~15 min)**
- Smoke-test API; manual browser smoke test on tablet; verify Redis lock cleanup; verify scheduler active.

**Phase F — Go-live (manual, ~10 min)**
- First real session lifecycle; verify Error Log clean; verify cash drop modal blind mode; backup snapshot.

**Phase G — Post-launch ops (NEW section)**
- Document tablet IDs, operator names, escalation contacts; first-week monitoring; first-month retro.

**Total time, current vs proposed:**
- Current Hamilton playbook: ~4–8 hours
- Proposed (with `apply_venue_config.py` + per-venue YAML): ~1.5–2 hours

The 50% goal is achievable. Leverage is in #5 (declarative installer), not in #3 (git is correct) or #4 (flags are roughly correct, just need documenting).

#### Summary of recommended actions, prioritized

1. Build `docs/venue_config/<venue>.yaml` + `apply_venue_config.py` patch — biggest single time-saver.
2. Write `docs/venue_config_schema.md`.
3. Add topic + venue tags to decisions_log.md, lessons_learned.md, claude_memory.md plus topic indexes.
4. Rename `Hamilton Settings` SingleType to `Venue Settings` — before any second site exists.
5. Add a fresh-site CI job.
6. Document the feature-flag decision rule in CLAUDE.md.
7. Split `claude_memory.md` — move pre-2026-04-15 entries to retrospectives.

**Sources:** Frappe v16 docs, Frappe Cloud docs, ERPNext community forum threads (cited inline above).

---

### Pre-Handoff Research — Prompt 5 (Professional handoff audit)

**Research date:** 2026-04-29. **Repo audited:** `csrnicek/hamilton_erp`.

**Scope:** What a senior Frappe developer needs in their first 30 minutes to productively own this codebase, and what they will silently bill extra hours to discover if it's missing.

#### Prioritized Handoff Checklist (Top 15 by ROI)

| # | Item | Effort | Why |
|---|---|---|---|
| 1 | **Rewrite `README.md`** from 5 lines to a real handoff doc | 1-2 hrs | Today is 5 lines + two CI badges. First-impressions doc gives them nothing. |
| 2 | **Create `CONTRIBUTING.md`** with bench setup, test commands, lint rules, branch/PR conventions | 1-2 hrs | All of this lives in CLAUDE.md (AI-targeted) — senior dev shouldn't read AI instructions to find `bench install-app`. |
| 3 | **Add `docs/HANDOFF.md`** — single-page "if you read nothing else, read this" | 2-3 hrs | The 70%-of-the-value doc that doesn't exist. `current_state.md` and `claude_memory.md` are session diaries, not architecture docs. |
| 4 | **Add `docs/ARCHITECTURE.md`** — state machine diagram, three-layer locking diagram, doctype ER diagram | 3-4 hrs | The lifecycle FSM exists in code and prose but is not drawn anywhere. Senior dev expects this. |
| 5 | **Conformance test for fresh install** — `bench install-app hamilton_erp` lands in known-good state, asserted by `test_environment_health` | 4-6 hrs | First install reveals undocumented assumptions. Catching in conformance test means loud failures with fix-message. |
| 6 | **Stub-task purge** — `tasks.py:check_overtime_sessions` is a `pass`. Either delete from `hooks.py scheduler_events` or implement | 30 min | Senior dev spots in 60 seconds and immediately distrusts cron config. |
| 7 | **`utils.py` audit** — move test-only helpers to `test_helpers.py` or delete | 1 hr | Reviewer signal: "this codebase doesn't know what it ships." |
| 8 | **`hooks.py` comment audit** — trim by 30%, especially the `app_include_css` block | 30 min | Comment-bloat is a known AI-code tell. |
| 9 | **`docs/SECURITY.md`** — list every `@frappe.whitelist()`, role gates, mutation surface | 1-2 hrs | No single place answers "what does my POS operator role permission to do via HTTP?" |
| 10 | **DocType field-type and index audit** — document non-obvious choices in JSON `description` field | 2-3 hrs | Intent of schema choices in `decisions_log.md` but not in doctype JSON. |
| 11 | **Permission matrix doc** (`docs/permissions_matrix.md`) — rows = roles, columns = doctypes + actions | 2 hrs | Needed for client signoff. |
| 12 | **`docs/RUNBOOK.md`** — Redis down, tests failing, `is_setup_complete` flips, stuck Active session | 2-3 hrs | Today is tribal knowledge. |
| 13 | **CHANGELOG.md** — extract from git log | 1 hr | ERPNext partner devs expect. |
| 14 | **`docs/api_reference.md`** — generated or hand-written for the 9 whitelisted endpoints | 3-4 hrs | Today `test_api_phase1.py` is the de-facto reference. Tests are not docs. |
| 15 | **Production deploy doc** — verify `HAMILTON_LAUNCH_PLAYBOOK.md` covers Frappe Cloud bench config, env vars, payments install, redis namespace, backup/restore, rollback | 1-2 hrs | Task 25 is the deploy. |

**Total prep effort to top-of-class handoff:** ~28-40 hours. Skipping items 1-5 will easily cost the senior dev that much in the first week.

#### What Hamilton ERP already gets right (do not regress)

1. ADRs (`decisions_log.md` DEC-001..DEC-066) — gold-standard decision tracking
2. Locking I/O hygiene (`coding_standards.md` §13) — better than 90% of production ERPNext apps
3. Test breadth (28 files, 467 tests, every expected category covered)
4. v16-correct patterns (`extend_doctype_class`, no `db.commit()` in controllers, `IntegrationTestCase`, fixture filtering)
5. `install.py` setup-wizard heal — real fix for a real Frappe footgun, well-documented
6. CI (tests.yml, lint.yml, claude-review.yml) already green
7. design/V9_CANONICAL_MOCKUP.html with manifest — unusually rigorous

#### Top concerns to fix before handoff (ranked)

1. README is 5 lines — they will form a bad first impression
2. No CONTRIBUTING.md — they will dig through CLAUDE.md and find AI boilerplate
3. `tasks.py` is a no-op stub firing every 15 minutes — they will not trust the cron config
4. No conformance test on `bench install-app` — first install will reveal undocumented assumptions
5. `app_email = "chris@hamilton.example.com"` — placeholder
6. **Realtime room scoping — the C2 payload may leak to non-Hamilton users** (security gap; see §6 below)
7. No rate limiting on POST endpoints

#### Production-ready test suite (industry consensus + Hamilton state)

| Module category | Expected | Hamilton ERP today | Status |
|---|---|---|---|
| Lifecycle | yes | `test_lifecycle.py` | Present |
| Locks | yes | `test_locks.py` | Present |
| API | yes | `test_api_phase1.py` | Present |
| E2E | yes | `test_e2e_phase1.py` | Present |
| Stress | yes | `test_stress_simulation.py`, `test_load_10k.py` | Present |
| Seed/install | yes | `test_seed_patch.py` | Present |
| Security | yes | `test_security_audit.py` | Present |
| Asset board rendering | yes | `test_asset_board_rendering.py` | Present |
| Hypothesis property | yes | `test_hypothesis.py` | Present |
| Database advanced | nice | `test_database_advanced.py` | Present |
| Adversarial / edge | nice | `test_adversarial.py` etc. | Present |
| Environment health | yes | `test_environment_health.py` | Present |
| Governance | unique | `test_canonical_mockup_governance.py` etc. | Present |
| Bulk ops | yes | `test_bulk_clean.py` | Present |

**Gap:** No documented coverage floor. **Action:** add to CI: `pytest --cov=hamilton_erp --cov-fail-under=85`.

#### Common AI-code anti-patterns (industry literature) vs Hamilton state

1. **Redundant abstraction** — Hamilton: not detected. utils.py 2 functions, locks.py one entry point, realtime.py 2 publishers. Already gets right.
2. **Missing error handling at framework boundaries** — Hamilton: realtime.py explicitly handles "row deleted between lifecycle and publish." Good. Action: sample audit api.py + lifecycle.py.
3. **Vocabulary inconsistency** — Hamilton: minor `_change` vs `_changed` mix in publishers. Action: small naming pass.
4. **Incomplete DocType definitions** — Hamilton: 4 indexed fields on venue_asset.json. Likely correct but a senior dev will second-guess. Action: 1-line justification in JSON `description`.
5. **Comment-bloat** — Hamilton: comments mostly load-bearing (lifecycle.py, install.py docstrings explain WHY). hooks.py slightly heavy. Action: trim 30%.
6. **Production code calling test-mode short-circuits** — Hamilton: `_make_asset_status_log` short-circuits when `frappe.in_test`. **Documented and tested but worth flagging in handoff.**
7. **Per-doctype controllers with 5-line bodies** — Hamilton: 9 doctype directories. Action: sample audit. Pure scaffolding is fine; logic-duplication is the bug.
8. **Unused imports / dead code** — Hamilton: `tasks.py` no-op stub. Confirmed. Action: delete or implement.

#### Security checklist — most-overlooked

- [x] Whitelist verb gating — Hamilton uses `methods=["GET"]`/`["POST"]` correctly
- [x] Role-based access — `frappe.has_permission(throw=True)` at top of every endpoint
- [ ] **Realtime publish permissions — `publish_realtime` writes to "all" room by default. C2 payload includes `current_session`. Anyone with System User role can subscribe. Gap: is the asset-board event leaking session data to non-Hamilton users? Action: scope to room="hamilton_asset_board" with `can_subscribe` hook (~2-3 hrs).** This is the biggest security finding.
- [ ] Field-level permissions on Cash Drop / Cash Reconciliation cash-amount fields — verify `permlevel` set, read-restricted to Manager+
- [ ] Rate limiting on whitelisted endpoints — none have `@rate_limit`. For session-creation endpoint (`check_in`), real concern in multi-tenant deploy. Action: add `@rate_limit(limit=60, seconds=60)` on mutation endpoints.
- [x] CSRF — Frappe handles for `/api/method/` automatically with SID cookies

#### `hooks.py` red flags (consensus + Hamilton state)

| Red flag | Hamilton |
|---|---|
| Wildcard `"*"` doc_events without justification | Not present (Sales Invoice only). Good. |
| Try-except swallowing exceptions in hooks | Not present. Good. |
| Local imports inside hook functions | Not present (refs by string path). Good. |
| Schedulers firing every minute that do nothing | **Present.** `*/15 * * * *` calls `check_overtime_sessions` which is `pass`. **Gap.** |
| Conflicting `extend_doctype_class` registrations | Not present. Good. |
| `frappe.db.commit()` inside hooks | Present in `after_install` — documented as intentional. Add 1-line comment. |
| `app_include_js`/css site-wide for one page | Present (`asset_board.css`). Comment correctly explains intentional. Good. |
| `permission_query_conditions` on critical doctypes | Not declared. Action: verify if needed for Venue Session per-shift filtering. |
| `app_email`/`app_logo_url` defaults | `app_email = "chris@hamilton.example.com"` placeholder. Action: real email or note. |
| `before_install` missing — no version preconditions | Not present. Action: consider adding for MariaDB/Redis version checks. |

#### Bottom line for the senior developer

Hamilton ERP is significantly above industry baseline for an AI-built custom Frappe app. The strengths (ADRs, locking hygiene, test breadth, v16-correct patterns) outweigh the weaknesses (thin top-level docs, no-op stub, realtime room scoping). Estimated prep: ~28-40 hours for top-of-class handoff. ~8 hours for "competent" handoff (items 1, 2, 6 from the checklist + the no-op stub purge + room scoping).

**Sources:** ERPNext code security guidelines (frappe/erpnext wiki); Frappe Hooks Reference; Migrating to v16 wiki; AI code review literature (CodeRabbit 2026 report; Addy Osmani's "Code Review in the Age of AI"); Mintlify Frappe docs; multiple discuss.frappe.io threads (cited inline).

---

### Combined: Top actions across all three pre-handoff prompts

**Critical (blocks clean handoff):**
1. Rewrite README.md (1-2 hrs)
2. Create CONTRIBUTING.md (1-2 hrs)
3. Add docs/HANDOFF.md (2-3 hrs)
4. Conformance test for fresh install (4-6 hrs)
5. Realtime room scoping audit + fix (2-3 hrs) — **security gap**

**High-value polish:**
6. Stub-task purge (`tasks.py:check_overtime_sessions`) (30 min)
7. `app_email` placeholder fix (5 min)
8. `docs/SECURITY.md` (1-2 hrs)
9. `docs/permissions_matrix.md` (2 hrs)
10. `docs/RUNBOOK.md` (2-3 hrs)
11. CHANGELOG.md (1 hr)
12. `docs/api_reference.md` (3-4 hrs)

**Multi-venue prep (do before Philadelphia):**
13. `docs/venue_config/<venue>.yaml` + `apply_venue_config.py` patch (4-8 hrs) — **biggest time-saver for venue #2**
14. Rename `Hamilton Settings` → `Venue Settings` (2-3 hrs) — must do before any second site exists
15. Topic + venue tagging in decisions_log/lessons_learned (2 hrs)
16. Document feature-flag decision rule in CLAUDE.md (30 min)
17. Fresh-site CI job (3 hrs)

**Production hardening (before Frappe Cloud go-live):**
18. Sentry integration via `ParsimonyGit/frappe-sentry` (2-4 hrs) — production monitoring is currently absent
19. `track_changes` on the 6 Hamilton DocTypes (1 hr)
20. Field masking on Cash Drop / Comp Admission Log (1-2 hrs)
21. Rate limiting on POST endpoints (1 hr)
22. `scripts/init.sh` for fresh dev bench (2-3 hrs)

---

## Pre-DC: evaluate Frappe Claude Skill Package

Repo: https://github.com/OpenAEC-Foundation/Frappe_Claude_Skill_Package

61 deterministic Frappe/ERPNext skills (MIT, drop-in install at `~/.claude/skills/`). Encodes Frappe-specific gotchas similar to ones we've already hit (e.g. `frappe.flags.in_test` vs `frappe.in_test`, `override_doctype_class` vs `extend_doctype_class`).

Timing: install AFTER Task 25 ships and BEFORE starting DC/Crew Club multi-venue refactor. Don't install mid-Phase-1 — it changes Claude Code behavior and could introduce noise in in-flight PRs.

When evaluating: review which of the 61 skills overlap with patterns already in claude_memory.md (avoid duplication), and which fill gaps (especially around Server Scripts, hooks.py, custom apps, and v16-specific behavior).

---

## 2026-04-30 — Third autonomous overnight run (8 PRs shipped)

**Run summary.** Chris invoked an overnight autonomous stack run after PR #52 (PIPEDA research) merged. 8 PRs shipped across 5 stack items + 1 wording fix + 3 overflow items. Stack #3 deferred (bench migrate STOP condition).

**PRs opened:**

- **#53** — chore: stub-task purge + app_email fix → **MERGED**
- **#54** — test: track_changes regression-pin (9 DocTypes) → auto-merge queued
- **#55** — docs(research): PIPEDA wording fix (no "adult" classification) → **AWAITING CHRIS REVIEW** (no auto-merge per his instruction)
- **#56** — test: fresh-install conformance test (28 tests) → auto-merge queued
- **#57** — docs: operational RUNBOOK.md (10 sections) → auto-merge queued
- **#58** — docs: CHANGELOG.md (46 merged PRs documented) → auto-merge queued
- **#59** — chore: scripts/init.sh (fresh-bench bootstrap) → auto-merge queued
- **#60** — docs: api_reference.md (7 whitelisted endpoints) → auto-merge queued

### Stack #3 — DEFERRED until Chris-supervised session

**Original scope:** Add `mask: 1` to Cash Drop, Cash Reconciliation, and Comp Admission Log fields per `permissions_matrix.md` Task 25 item 7.

**Why deferred:** Adding `mask: 1` to a DocType JSON requires `bench migrate` to apply the schema change. CLAUDE.md "Autonomous Command Rules" lists "bench migrate is required" as a STOP condition — autonomous Opus does not run migrate without Chris's approval.

**Field-name reconciliation already done.** `permissions_matrix.md` lists:
- `Cash Drop.amount` → actual field is `declared_amount` (also `section_amount`)
- `Cash Reconciliation.expected_cash` → actual field is `system_expected`
- `Cash Reconciliation.actual_cash` → actual field is `actual_count`
- `Cash Reconciliation.variance` → actual field is `variance_amount`
- `Comp Admission Log.value_at_door` → actual field is `comp_value`

**When picked up next:** the same PR should also fix these labels in `permissions_matrix.md` to match the actual JSON. The doc-update half of the work needs no migrate; the JSON-update half does.

**Suggested PR scope:**
1. Fix `permissions_matrix.md` field names (no migrate)
2. Add `mask: 1` to the 6 fields listed above (migrate required)
3. Decide field-level `permlevel` strategy — currently no fields have `permlevel: 1`, so `mask: 1` alone may be a no-op for the default-permlevel-0 viewer (need to verify Frappe v16 mask: 1 behavior with context7 first)
4. Add tests pinning `mask: 1` on each field (regression-pin similar to track_changes Stack #2)
5. Run `bench --site hamilton-unit-test.localhost migrate` (Chris's hands)

**Reference:** `docs/research/pipeda_venue_session_pii.md` for the broader v16 masking pattern; PR #50 (security: field masking gap #1 — Shift Record.system_expected) is the existing precedent for how this work is done on Hamilton DocTypes.

### Tests baseline — 2 failures + 6 errors all pre-existing

Confirmed via `git stash` + run on main:
- 2 failures: env_health asset count + asset board accessibility — seed contamination canary
- 6 errors: doctype setUpClass — `DocType Payment Gateway not found` (frappe/payments missing on local bench)

Not regressions from any of this run's changes.

### Tasks 18–21 (Asset Board UI) NOT picked up

Yellow-list items per the original "what can run autonomously overnight" analysis. Code can be drafted autonomously but visual verification in a browser requires Chris. Skipped per the autonomous-vs-yellow-vs-red triage.

### Open green-list items still available

Not picked up this run, available for next overnight:
- SECURITY.md (1-2 hr) — vuln-disclosure template
- README.md rewrite (1-2 hr) — taste-driven, may want Chris's eye
- CONTRIBUTING.md (1-2 hr) — mostly mechanical

### What this run validated

- Multi-PR autonomous flow with auto-merge queueing works cleanly. 8 PRs shipped in ~1.5 hours.
- Pre-flight checks save time: track_changes Stack #2 was discovered already-implemented; Stack #3 was caught as a STOP condition before any code was written.
- The `git stash` baseline trick is the cleanest way to attribute test failures (mine vs pre-existing).
- Chris's `wording-fix` label + no-auto-merge instruction worked perfectly for PR #55.

## 2026-04-30 — Phase 2 hardware + integration backlog (post-cart-UX)

V9.1 Phase 2 retail cart shipped with cash-only single-tender (PR #49). The follow-up wires real Sales Invoice creation. After that, the next Phase 2 work is hardware integration and a card-payment merchant abstraction. Captured here so it doesn't get lost between cart-UX shipping and store-opening.

### Receipt printing — Epson TM-T20III

**Hardware:** Epson TM-T20III thermal receipt printer. Ethernet + WiFi capable. Same integration pattern as the Brother label printer (DEC-011) — IP address configured per-venue in Hamilton Settings, not hard-coded.

**Behavior:** Print every transaction automatically after payment confirms. The receipt content includes:
- Sale line items + totals (HST broken out)
- Asset assignment (room number / locker number) when the sale is part of a check-in flow
- Sales Invoice ID and timestamp
- Cash given / change due (or last-4 of card pan if Card)

**Operational pattern — receipt as physical control token.** The paper receipt printed at point-of-sale doubles as the asset-board control token. The operator hangs the receipt on the assigned key hook. Receipt-on-hook = room/locker is occupied. This keeps the physical state visible without the operator having to look at a screen, and survives system outages — if the asset board is down, the hooks still tell you what's free.

**Design implications:**
- Receipt printer config lives in Hamilton Settings: `receipt_printer_ip` (string), `receipt_printer_enabled` (check). Mirror Brother label printer fields.
- Print job is a side-effect, not part of the Sales Invoice transaction. If the printer is offline, the sale must still complete; queue the print job to retry, surface a "printer offline" indicator on the board.
- Test path: a `print_receipt(sales_invoice_name)` whitelisted endpoint that takes a Sales Invoice and renders to ESC/POS. Backend does the formatting; client just triggers.

**v16 PRINT-FORMAT GOTCHA — load by name, do not rely on UI selection.** ERPNext v16 issue [#53857](https://github.com/frappe/erpnext/issues/53857) ("Add Sales Invoice support to POS Profile print format filter") is open as of 2026-04-30: the POS Profile's print-format filter UI doesn't show Sales Invoice formats, only POS Invoice formats. Hamilton's path uses Sales Invoice (via the v16 `is_pos=1` architecture). This means **the receipt printer code path MUST specify the print format programmatically** — load the Print Format by name (`frappe.get_doc("Print Format", "<Hamilton Receipt>")`), render the SI through `frappe.get_print(doctype, name, print_format=...)`, and send the rendered output to the printer. Do NOT depend on `pos_profile.print_format` being set correctly via the Desk UI; that field's filter is broken in v16 and will silently stay empty for Sales-Invoice-flavored POS profiles.

**Concrete pattern:**
```python
def print_receipt(sales_invoice_name: str):
    si = frappe.get_doc("Sales Invoice", sales_invoice_name)
    html = frappe.get_print(
        doctype="Sales Invoice",
        name=sales_invoice_name,
        print_format="Hamilton Receipt",  # explicit, NOT pos_profile.print_format
    )
    escpos_bytes = render_html_to_escpos(html)
    send_to_printer(hamilton_settings.receipt_printer_ip, escpos_bytes)
    # Also: store escpos_bytes on the SI per the receipt-bytes retention rule above.
```
The "Hamilton Receipt" Print Format is created as a fixture in the Hamilton ERP app and referenced by name. When ERPNext fixes #53857 (likely a v16.x patch), the workaround stays correct — it doesn't break, just becomes redundant.

### CRA compliance — mandatory receipt content (Ontario / Canada)

Sourced from the Ontario CRA receipt-requirements research (2026-04-30). Receipt printer code must produce output that satisfies CRA's tiered receipt rules so Hamilton stays compliant for the 6-year audit window AND so business customers (corporate cards, bachelor-party blocks) can claim Input Tax Credit on their purchases.

**Pre-Phase-2 setup — Hamilton Settings field:**

- Add `gst_hst_registration_number` (Data field) to Hamilton Settings BEFORE the receipt printer ships. The receipt printer integration reads this value and prints it on every receipt. Pre-populate via Desk on first install (operator types it in once); seed code can't auto-derive it because it's an external CRA-issued identifier specific to Hamilton's legal entity.

**Mandatory fields on every printed receipt (and digital receipt):**

| Field | Source / value |
|---|---|
| Business name | "Club Hamilton" — Company.company_name |
| Business address | Hamilton Settings field (add if missing) — venue street address |
| Business phone | Hamilton Settings field (add if missing) — venue phone |
| Date | SI.posting_date + SI.posting_time, formatted for human reading |
| Items list | SI.items[] — item_code, item_name, qty, rate, amount per line |
| Tax indication per line | Implicit (all currently 13%); explicit when Phase 3 mixes rebate-eligible items |
| HST line | "HST 13%" with rate AND dollar amount (NOT just "HST $0.91" — the rate must be visible) |
| Total | SI.rounded_total (cash) or SI.grand_total (card) — see Canadian penny-elimination amendment |
| GST/HST registration number | Hamilton Settings.gst_hst_registration_number — print on EVERY receipt |
| "PAID" indication | Phrase like "PAID — CASH" or "PAID — CARD" derived from SI.payments[0].mode_of_payment |

**Why GST/HST registration number on EVERY receipt regardless of amount tier:** CRA's tiered rule technically only requires the GST/HST number on transactions $30+. But: (a) the implementation cost of the conditional is higher than always printing it, (b) below-$30 receipts that omit the number can't be used by business customers for ITC even when they're inside the $30 tier informally (e.g., one-cent rounding or split-tender), (c) receipts are often given to expense-report owners separate from the original buyer. **Print it always.** No downside; eliminates a class of compliance gap.

**HST display rule (CRA permits three options; Hamilton uses Option A):**

- **Option A (Hamilton's choice — separate line):** "Subtotal $7.00 / HST 13% $0.91 / Total $7.91". Matches the cart drawer JS preview, matches what `submit_retail_sale` writes to the SI's tax line. Cleanest for operators and customers.
- Option B (tax-included with rate disclosed): "Total (HST 13% included) $7.91" — valid CRA option but worse for operator math during cash transactions.
- Option C (net + total + rate notation): "Net $7.00 / Total $7.91 / HST applied at 13%" — valid but verbose.

**Rate must be visible.** A receipt showing "HST $0.91" without the "13%" rate is non-compliant for $30+ transactions. Always include "HST 13%" verbatim.

**Retention:** CRA requires 6 years from the end of the tax year the records relate to. Frappe Cloud's offsite backup retention (7 daily / 4 weekly / 12 monthly / **10 yearly**) covers this naturally — the live database is the system of record (the SI itself, with `taxes_and_charges`, `taxes`, `payments`, etc.); the printed paper receipt is operator UX. The 10-year long-tail backup retention exceeds the 6-year CRA requirement comfortably. No additional retention infrastructure needed.

**Receipt copy retention (chargeback evidence + CRA back-stop):** Per the Phase 2 hardware backlog above, retain ESC/POS bytes server-side for ≥18 months for chargeback dispute response. The 18-month chargeback window is shorter than the 6-year CRA window, so the SI-record-of-record outlasts the receipt-bytes copy by design. CRA cares about the SI; the receipt bytes are operator/dispute-investigation convenience.

### Phase 3 forward-compat — Ontario prepared-food rebate (will apply if Hamilton adds menu items)

CRA GI-064 documents the Ontario point-of-sale rebate on qualifying prepared food and beverages: when total price (excluding HST) is ≤ $4, the 8% provincial portion of HST is rebated at the point of sale. Effective HST on those items drops from 13% to 5% (federal-only).

**What qualifies:** hot meals, sandwiches, heated beverages, prepared food ready for immediate consumption.

**What does NOT qualify:** carbonated/sweetened beverages, snack items (chips, candy, granola bars, energy bars, protein bars), single-serving bottled water.

**Hamilton's current 4 retail SKUs (WAT-500, GAT-500, BAR-PROT, BAR-ENRG) all fall into the "does not qualify" categories** — full 13% HST is correct, no rebate. The accounting seed is correct as-is.

**When this becomes relevant:** Phase 3+ if Hamilton adds menu items — hot coffee/tea, made-to-order sandwiches, hot soups, etc. At that point:

1. Add a per-Item flag (Custom Field on Item: `qualifies_for_on_food_rebate` Check) OR use ERPNext's Item Tax Template feature.
2. The cleanest pattern is **Item Tax Template per-item override**: create a "Ontario HST 5% (rebate-eligible)" Sales Taxes Template and attach it to qualifying items via Item Tax Template. The cart's per-line tax computation will pick up the per-item override automatically.
3. Cart logic must check the under-$4 threshold per qualifying item: rebate applies only when (item qualifies) AND (item price excluding HST ≤ $4) AND (item is sold in a "prepared for immediate consumption" context — coffee/sandwich orders qualify; bulk grocery purchases of the same item do not).
4. Receipt format must show the rebate as a separate line per CRA's three permitted presentations of POS rebates (full HST minus rebate / federal-only / HST-included with net-tax notation). Choose one and apply consistently.

**Scope estimate when ready:** ~3-5 days of work including the Item Tax Template seed, cart conditional-tax logic, receipt format update, regression tests covering the under-$4 threshold edge cases.

### Phase 3 forward-compat — B2B invoice tier ($150+ corporate billing)

CRA's tiered receipt rule: at $150+, additional fields become mandatory beyond the standard receipt — **buyer's name, description of purchase, terms of payment**.

**Hamilton's current flow:** every cart sale is to "Walk-in" (anonymous) at retail prices. No corporate billing. Most carts are well under $150.

**When this becomes relevant:** if Hamilton ever offers corporate billing for bachelor-party blocks, gift card purchases, multi-room reservations, etc. At that point the cart needs:

1. A "named customer" path — operator types or selects a Customer record other than "Walk-in" (could be an existing membership Customer, could be an ad-hoc corporate Customer created at the cart).
2. Per-line item descriptions written to the SI (Hamilton's seed already provides item_name → SI line description; verify it's not stripped by any custom code).
3. Payment terms field on the SI (already a standard ERPNext SI field; just needs to be exposed in the cart UI when the customer is non-walkin).

**Scope estimate when ready:** ~2-3 days for the cart UX (customer selector, payment-terms field, named-customer routing) + the receipt format already includes the customer name field for non-Walk-in receipts.

### Digital receipt option

Offer "Email or SMS receipt" in addition to the paper print. Operator types the customer's email or phone, system sends a digital copy. Paper still prints by default (control-token role); digital is additive, not a replacement.

**Implementation note:** Digital receipt is a Sales Invoice email/SMS via Frappe's standard notification machinery — not a custom integration. Per-venue email-from address comes from Hamilton Settings (already exists per `app_email`).

### Tap-to-pay treated as Card method

**Decision:** Tap-to-pay does NOT get its own Mode of Payment row. It IS "Card." The merchant terminal handles the chip/swipe/tap distinction internally. The Sales Invoice records `mode_of_payment="Card"` regardless of how the customer presented their card.

This avoids the trap of having "Tap", "Chip", "Swipe", "Apple Pay" as four separate Mode of Payment values that the operator has to choose between — none of which are knowable in advance because the terminal decides based on what the customer does.

### Merchant abstraction (multi-merchant resilience)

**Why this matters:** Hamilton operates as a standard commercial merchant (per DEC-062, locked 2026-05-01) — Fiserv MID 1131224 is standard-classified, not adult-classified. The merchant-abstraction work is still warranted, but for a different reason: any merchant relationship can end (chargeback ratio, classification change, processor business decision, M&A) and the system MUST support swapping merchants without code changes, ideally with multiple active merchants for redundancy.

Some processors (notably Stripe and Square) may *perceive* bathhouse hospitality as adult-adjacent within their own internal risk models even when Hamilton is not formally adult-classified — that's the processors' policy stance, not Hamilton's classification. The abstraction work decouples Hamilton from any single processor's risk model so a perception-driven termination at one processor doesn't take Hamilton offline.

**Design:**
- Per-venue merchant config lives in `site_config.json` (or Hamilton Settings, leaning toward site_config because credentials shouldn't be in DB).
- Each venue can have **1 or N** active merchants. The default merchant is selected by name; alternates are available as a fallback if the default declines or times out.
- Adding a new merchant must be a config change, not a code change. The codebase ships with adapter classes for the common processors (Stripe, Square, Moneris in Canada, Helcim in Canada-adult-friendly, Stripe US) and `merchant_type` selects which adapter to use.

**Sales Invoice integration:**
- Every `mode_of_payment="Card"` payment captures a `merchant_transaction_id` (custom field on Sales Invoice or Mode of Payment Account row, decision pending).
- Capture the merchant name too (`merchant_name`), since with multiple active merchants the txn ID alone doesn't identify which merchant settled it.
- Both fields searchable on Sales Invoice — refunds, disputes, and reconciliation all need to look up by merchant_transaction_id.

**Field schema (proposal — expanded per PR #51 deeper audit, Topic 3):**

The chargeback-evidence research (Visa Compelling Evidence 3.0, EMV liability shift reason codes 10.1 / 10.2 / 4870) showed that a generic `merchant_transaction_id` is **necessary but not sufficient** to win a card-present dispute. The fields below convert a generic transaction record into compelling evidence:

```
Sales Invoice custom fields (10 fields total):
  hamilton_merchant_name         Data        (e.g. "Fiserv", "Helcim")
  hamilton_merchant_txn_id       Data        (returned by terminal/processor)
  hamilton_descriptor_used       Data        (the descriptor that appears on
                                              the cardholder's statement —
                                              e.g. "CLUB HAMILTON" not
                                              "HAMILTON BATHHOUSE"; NEW per
                                              deeper audit, reduces friendly-
                                              fraud chargebacks where the
                                              cardholder claims "I don't
                                              recognize this charge")
  hamilton_card_last_4           Data        (last 4 of pan, for receipt
                                              + dispute lookup)
  hamilton_card_brand            Data        (Visa / MC / Amex / Interac /
                                              Discover)
  hamilton_card_entry_method     Select      ("Chip" / "Swipe" / "Manual" /
                                              "Tap" / "Apple Pay" / "Google
                                              Pay" — swiped on EMV card =
                                              merchant liability per VRC
                                              10.1; chip-read shifts liability
                                              to issuer)
  hamilton_card_cvm              Select      ("PIN" / "Signature" / "NoCVM" /
                                              "Failed" — proper CVM is the
                                              compelling-evidence backbone)
  hamilton_auth_code             Data        (issuer's authorization
                                              response code; required for
                                              every dispute response)
  hamilton_card_aid              Data        (AID resolved by terminal —
                                              which scheme actually settled,
                                              critical for cards with
                                              multiple AIDs e.g. Visa Debit +
                                              Interac)
  hamilton_terminal_id           Data        (which terminal — multi-terminal
                                              venues need this for batch
                                              reconciliation and dispute
                                              filtering)
  hamilton_receipt_bytes         Long Text   (or attached as File: the
                                              ESC/POS bytes sent to the
                                              printer, retained server-side
                                              for >=18 months so a receipt
                                              can be re-printed for dispute
                                              response 6 months after the
                                              fact)
```

**Receipt-as-evidence retention rule:** print to printer + `frappe.get_doc("File", ...).insert()` the same ESC/POS bytes as a server-side attachment to the SI. Reproducible printing means a manager can re-print a receipt 6 months later without depending on the original paper copy still being in a filing cabinet. Retention period: 18 months (covers Visa's 120-day dispute window + re-presentment + arbitration).

**Why these fields collectively:** EMV liability shift (chip + CVM) handles the bulk of fraud-reason-code chargebacks (10.1, 10.2, 4870). Merchant descriptor + receipt bytes + auth code handle friendly-fraud and "I don't recognize this charge" cases. `terminal_id` + `card_aid` are batch-reconciliation safety. The 10 fields together implement the Visa CE3.0 evidence model for card-present POS.

**Per-venue config shape (proposal, in site_config.json):**
```json
{
  "hamilton_merchants": {
    "default": "helcim",
    "available": {
      "helcim": {"adapter": "helcim_v2", "api_key_path": "secrets/helcim.key", "terminal_id": "..."},
      "stripe_backup": {"adapter": "stripe", "api_key_path": "secrets/stripe.key"}
    }
  }
}
```

**Failover behavior:** If the default merchant's terminal times out or returns DECLINED-COMMS-ERROR (not DECLINED-INSUFFICIENT-FUNDS — those are real declines, don't retry), the operator gets a one-tap "Try backup processor" button on the cart drawer. This is operator-driven not automatic — automatic failover risks double-charging the customer if the first processor actually settled but the response was lost.

### Polish — cart drawer change preview off by ≤4¢

The cart drawer + cash payment modal preview the running total and change using the client-side `_cart_total()` (subtotal + HST 13%, no nickel rounding). The actual post-Confirm transaction is correct because the server applies Canadian nickel rounding (Amendment 2026-04-30 (c)) and returns the rounded change in the toast — but the *pre-Confirm preview* can be off by ≤4¢.

Concrete example for a $7.91 cart with $20 cash tendered:
- **Drawer/modal preview shows:** "Total $7.91" and "Change $12.09" (penny-precision)
- **Server returns:** rounded_total $7.90, change $12.10 (nickel)
- **Operator sees:** preview $12.09 → tap Confirm → toast "Sale ACC-... — change $12.10"
- **Worse symptom:** Confirm button is gated on `cash_received >= due` where `due = grand_total = $7.91`. If operator types exactly $7.90 (the actual rounded amount due), the button stays disabled because the JS thinks $7.91 is owed; they have to type $7.91 or more to enable Confirm. Then the API rounds and returns $0.00 change for $7.90 tendered — which is the right answer the operator already knew, but the modal didn't help them get there.

**Fix:** add a client-side `roundToNickel(value)` helper in `asset_board.js` and use it in:
- `_cart_total()` — show the rounded total in the drawer summary so the operator's mental math matches the cash they'll collect.
- The cash modal `due` variable — gate Confirm on `cash_received >= rounded_total`, compute change preview against rounded_total.

**Implementation note:** the math is identical to the server-side rule:
```js
function roundToNickel(value) {
    // Canadian penny-elimination rule (2013): round half-up to nearest 0.05.
    // Mirrors frappe.utils.round_based_on_smallest_currency_fraction.
    return Math.round(value * 20) / 20;
}
```
Add a unit test in `test_asset_board_rendering.py` (source-substring contract) asserting the helper exists and is called in `_cart_total` + the cash modal Confirm-gate path. Should be a half-day task.

**Why deferred from PR #51:** Functional correctness (the actual sale, the actual change handed back, the GL entry) is server-side and already correct as of commit `b3e5715`. The drawer preview is UX polish that doesn't affect any data, money flow, or audit trail — operators will adjust to "preview shows ${X}.{xx}, actual change is ${X}.{x0 or x5}" within their first shift if the polish doesn't ship by go-live. Worth fixing before opening day for clean operator UX, but not blocking PR #51 review.

### Phase 2 prep checklist — confirm with Fiserv / merchant before card work starts

These are the questions Chris needs answered before Phase 2 next iteration (card payments) begins. Pre-confirming avoids re-architecting the integration mid-build when answers come back differently than assumed.

- [ ] **MCC code on Fiserv MID 1131224.** Confirm the Merchant Category Code Fiserv has registered Hamilton under. MCC 7298 (health/beauty/spa) and 7299 (services not elsewhere classified) are the two likely candidates for a bathhouse. The MCC determines the card-network fee tier, the chargeback-ratio threshold, and whether Hamilton's transactions trigger any "high-risk" flagging in card-network systems. Hamilton processes as standard, but the MCC confirms which standard tier.
- [ ] **Descriptor on cardholder statements.** Confirm the exact merchant descriptor that appears on Visa / Mastercard statements when a customer pays at Hamilton. The descriptor field on the SI (`hamilton_descriptor_used`) must match this exactly — friendly-fraud chargebacks ("I don't recognize this charge") happen when the descriptor is generic or unfamiliar. Hamilton operates as a standard merchant (DEC-062), but customers may still find a bathhouse charge sensitive on a shared statement: a short, neutral name like "CLUB HAMILTON" reduces embarrassment-driven disputes vs. "HAMILTON BATHHOUSE / SAUNA". This is a customer-experience choice, not a classification claim.
- [ ] **Chargeback notification process.** How does Fiserv notify Hamilton of an incoming chargeback? Email, portal, fax (still happens), API callback? What's the SLA — 7 days from cardholder dispute filing? 15 days? Hamilton's response window for compelling evidence depends on this; a portal-only notification with an unmonitored email = missed chargebacks = MATCH-list risk (R-009).
- [ ] **Dispute portal credentials.** Get login credentials for Fiserv's dispute portal (Vantiv DisputeManager or similar) BEFORE the first chargeback. Operations runbook needs the portal URL, primary login, secondary login, escalation contact. Pre-Phase-2 ops task.
- [ ] **Reserve schedule and held-funds release.** What reserve does Fiserv hold (% of monthly volume, fixed amount, rolling 90-day)? When does held cash release back to Hamilton's bank account? This affects cash-flow planning, not chargeback handling, but matters operationally.
- [ ] **Terminal data flow for SAQ-A confirmation.** Confirm that the chosen terminal model (Verifone? Ingenico? Pax? Fiserv-supplied?) sends card data DIRECTLY to Fiserv via an encrypted channel that doesn't transit Hamilton's network. SAQ-A eligibility depends on this. If the terminal pumps card data through a Hamilton local server first, scope expands to SAQ-D (~$5-50k/year QSA assessment).

### Sequencing

This work happens AFTER the cart Confirm is wired to Sales Invoice creation (current PR). Order:

1. Receipt printer integration — Epson TM-T20III + ESC/POS receipt rendering + Hamilton Settings config + retry queue + server-side ESC/POS bytes retention (per the deeper audit's receipt-as-evidence rule). Probably 2-4 days.
2. Card payment Mode of Payment + merchant adapter scaffolding — basic Fiserv integration, capture all 10 EMV fields per the expanded schema above (merchant_transaction_id + descriptor + entry_method + cvm + auth_code + AID + terminal_id + card_brand + last_4 + receipt_bytes), add custom fields to Sales Invoice. Probably 3-5 days.
3. Multi-merchant config + manual failover button. **Lower priority now** — R-008 is downgraded because Hamilton runs as standard merchant via Fiserv. Phase 3+ unless chargeback ratio drives need. Original estimate 2-3 days remains accurate when scheduled.
4. Digital receipt (email/SMS). Probably half-day on top of receipt printer work since the templating is mostly shared.
5. Cart drawer nickel-rounding polish (Phase 2 polish section). Half-day. Standalone — can land before or after items 1-4.

Total: 1-2 weeks of focused Phase 2 work after Sales Invoice creation lands.

### Open questions for tomorrow-Chris

- Which processors are realistic backups for the Hamilton standard MID? Per DEC-062 Hamilton is a standard merchant via Fiserv; the question is which processor's perception-of-bathhouse risk model is least likely to terminate (Helcim is friendly to bathhouse-hospitality in Canada). Research backup adapters before committing to the abstraction layer.
- Hardware: confirm TM-T20III can be sourced in Canada and supports both ethernet and WiFi (some sub-models are ethernet-only). Verify the ESC/POS command set is the standard one that python-escpos supports out of the box.
- Receipt tape: brand + cost per roll + how many transactions per roll? Need this for the operations runbook.
