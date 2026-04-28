# Production Practices Audit — Hamilton ERP

**Audit date:** 2026-04-27
**Audit scope:** 24 categories of modern production-software practice, evaluated for a single-developer custom Frappe/ERPNext v16 app (Hamilton ERP) approaching its first production deploy on Frappe Cloud and a 6-venue rollout (Hamilton → DC → Philadelphia → Dallas → Toronto → Ottawa).
**Audience:** Chris Srnicek (owner / sole developer / beginner coder). Read-with-fresh-eyes; nothing in this document requires a decision tonight.
**Note on industry:** Adult bathhouse venues. This raises the privacy and consent stakes meaningfully and will be called out explicitly where it changes the recommendation.

---

## How to read this document

- **Section 1** is a one-paragraph plain-English explanation of every category, in case anything is unfamiliar. Skim or skip.
- **Section 2** is the audit — what hamilton_erp has today, with file paths and concrete evidence.
- **Section 3** is the meat — every gap, ranked into five tiers (Tier 0 = blocking go-live; Tier 4 = year-three aspirational). Each gap has: plain-English description, why it matters specifically for Hamilton/bathhouse industry, estimated effort, suggested tools with alternatives, references, and prerequisites.
- **Section 4** is a concrete week-by-week adoption roadmap for Tier 0 + Tier 1.
- **Section 5** is what to deliberately *not* do. Important — production shops do many things that would be overkill here.
- **Section 6** is a focused section on bathhouse-industry-specific practices (privacy, age verification, PCI scope, regional compliance).
- **Section 7** is every URL cited, organized by category, for deeper reading later.

Where I made a judgment call (Tier 1 vs Tier 2, tool A vs tool B), I explain the call in one sentence.

---

# Section 1 — Executive Summary (Plain-English Definitions)

A one-paragraph orientation per category. Skip anything you already understand.

### 1. Source control & branching
Git records every code change so you can undo mistakes and so two streams of work can coexist. Branching = a temporary parallel copy of the code. "Conventional Commits" is a strict format for commit messages (e.g. `feat:`, `fix:`, `chore:`) that lets tools auto-generate changelogs and version numbers. Without these conventions, your history becomes archaeology.

### 2. CI/CD
CI = Continuous Integration: every commit triggers automated tests. CD = Continuous Delivery (or Deployment): code that passes tests goes automatically (or one click) to a real environment. A "pipeline" is the chain of stages: lint → test → security scan → build → deploy → smoke test. Manual laptop-deployment is the #1 cause of "it worked on my machine" Friday-night outages.

### 3. Testing
Tests are code that runs your code to check it does what it should. The "test pyramid" describes the right mix: lots of fast tiny **unit tests**, fewer **integration tests** (multiple parts together), very few slow **end-to-end (E2E)** tests. Specialized tests: **property-based** (thousands of random inputs), **mutation testing** (deliberately break code to verify your tests catch it), **DAST** (security tests that attack a running app), **load** (1,000 users at once).

### 4. Code quality & review
A **linter** finds bad patterns. A **formatter** rewrites code to one consistent style. A **type checker** verifies that a function expecting a number isn't called with a string. **Pre-commit hooks** run automatically before every commit, blocking it if something fails. Without these, refactoring becomes hide-and-seek.

### 5. Dependency management
Your app uses other people's libraries (Frappe, redis-py, requests, etc.). A **lockfile** records the exact version of every library so two installs produce identical environments. **SBOM** = Software Bill of Materials, a machine-readable list of every dependency, useful for "did the log4j vulnerability hit us?" questions.

### 6. Security
**SAST** (Static Analysis Security Testing) reads your source code for vulnerable patterns. **DAST** (Dynamic) attacks a running app. **Secret scanning** detects API keys committed to git. **Threat modeling** is sitting down and asking "if I were an attacker, where would I attack?" **Security headers** (CSP, HSTS) tell browsers to enforce extra protections.

### 7. Secrets management
Secrets are the passwords of software: API keys, database credentials, encryption keys. Secrets management is the discipline of storing them outside your code, distributing them only to processes that need them, rotating them on a schedule, and auditing every access. Code is public-by-default; secrets must live somewhere code cannot reach.

### 8. Observability
Observability is the ability to ask "why is the system behaving this way?" without shipping new code. It rests on four signals: **logs** (what happened), **metrics** (how much / how fast), **traces** (which call caused which call), and as of 2026 **continuous profiling** (which line of code burned the CPU). Without it you debug by guessing; with it you debug by querying.

### 9. Deployment
Deployment is getting code from your laptop to the running production system. Modern deployment has three pillars: **environments** (dev → staging → prod, each isolated), **automation** (deploy is one command, not a 14-step checklist), and **reversibility** (every deploy can be rolled back in minutes).

### 10. Backup & disaster recovery
Backups answer "can I get my data back?" Disaster recovery (DR) answers "can I get the whole business back online?" Two numbers govern the design: **RPO** (Recovery Point Objective — how much data am I willing to lose) and **RTO** (Recovery Time Objective — how long can the system be down). Backups that are never restored are not backups.

### 11. Incident response
The structured process of handling production breaks: detect → page the right person → follow a runbook → communicate via a status page → write a blameless post-mortem afterward. Severity levels (SEV1–SEV5) prevent treating a typo on a marketing page like a payment outage.

### 12. Documentation
The written knowledge of how the system works. Splits into four kinds: **tutorials** (teach a beginner), **how-to guides** (help a user accomplish a task), **reference** (look up a fact), **explanation** (understand why). Mixing these on one page is the #1 cause of bad docs. **Architecture Decision Records (ADRs)** capture *why* a non-obvious decision was made, dated and immutable.

### 13. Performance
Measuring where your app spends its time and memory, then fixing the slow parts before users notice. Has four layers: **profiling** (which line of Python is slow?), **query optimization** (which SQL is the bottleneck?), **caching** (don't recompute things), and **frontend metrics** (does the page feel responsive?).

### 14. Accessibility & UX quality
A blind staff member using a screen reader, a clerk who can't use a mouse, or a colorblind manager can all do their job in your app. WCAG 2.2 (current 2026 standard) is the legal floor. Internal employee tools still need this for ADA/AODA exposure and because employees with disabilities do exist.

### 15. Compliance & legal
Privacy and accessibility laws set rules for what data you can collect, how long you can keep it, when you must delete it on request, and how you tell users. Bathhouse data is "sensitive" in most modern frameworks because membership reveals sexual orientation in many cases. PIPEDA (Canada), CCPA/CPRA (California), TDPSA (Texas), MHMDA (Washington), and PCI-DSS v4.0.1 (cards) are the relevant frameworks.

### 16. Data engineering
The discipline of changing your database schema and data without losing or corrupting anything. Covers safe migrations, audit logs (who changed what), soft deletes, anonymization, and zero-downtime schema changes. A bad migration is the #1 way single-dev teams lose data permanently.

### 17. Feature flags & progressive rollout
A feature flag is an `if (flag_on) { new code } else { old code }` switch you can flip in production without redeploying. Lets you ship code dark, enable for one venue, fix bugs, then enable for all venues. The hidden cost is **flag debt** — flags become permanent if not cleaned up.

### 18. API design
How you let other systems (mobile app, partners, future POS) talk to Hamilton ERP without breaking when you change the code. Good APIs are predictable, documented, versioned, and survive the user pressing "submit" twice (idempotency). Without versioning you can't ship breaking changes; without idempotency keys, a flaky network double-charges a customer.

### 19. Frontend specific
Measuring and shipping a fast, accessible, error-resilient browser experience. Includes **Core Web Vitals** (LCP, INP, CLS — INP replaced FID in March 2024), Lighthouse audits, **bundle size monitoring** (every kilobyte you ship is parsed and executed on a phone), and image optimization (AVIF/WebP, lazy loading).

### 20. Database specific
Keeping the relational database (MariaDB, in Hamilton's case) fast, durable, and safe to change. Includes index review, slow-query logging, EXPLAIN/EXPLAIN ANALYZE, N+1 detection, online schema migration, and physical vs logical backups. The DB is almost always the first thing to break under load.

### 21. Team & process (solo-dev adapted)
The lightweight equivalents of team agile rituals when the team is one person plus AI assistants. Stand-ups → daily journal. Retros → weekly review. Sprint planning → kanban. Knowledge sharing → ADRs. Solo work fails not from lack of skill but from lack of structure.

### 22. Cost monitoring
Visibility into what your software stack costs each month, anomaly alerting (catching the $5k surprise on day 2 not day 30), and a vendor cost tracker. The discipline is called **FinOps**. Cloud bills are designed to grow silently; a forgotten staging site can quietly 10x a bill mid-month.

### 23. Legal & business continuity
Code escrow, IP assignment agreements (so contractors don't accidentally own what they build for you), DPAs (Data Processing Agreements with vendors), SOC 2 readiness for enterprise sales, and **bus-factor mitigation** — what happens to the venues' software if Chris is hit by a bus.

### 24. AI development practices specific to 2026
The new layer that emerged once LLMs started writing real code: **model and prompt versioning**, **eval harnesses** (automated tests for AI behavior), **agent memory** (claude-mem, MCP servers, RAG over the codebase), **AI-assisted code review** (CodeRabbit, Greptile, Qodo), and the converging "AI-aware" config files (CLAUDE.md, AGENTS.md, .cursorrules).

---

# Section 2 — Current State Audit

Below is what hamilton_erp has *today* (2026-04-27, branch `fix/ci-vendor-setup-action` post-Phase-1 close). Numbers and file paths are evidence; opinions are deferred to Section 3.

## High-level snapshot

| Category | State | One-line evidence |
|---|---|---|
| 1. Source control | ✅ Mature | 316 commits last 60 days; conventional commit prefixes (feat/fix/ci/docs/chore); 7 active branches |
| 2. CI/CD | ⚠️ In flight | `.github/workflows/{tests,lint,claude-review}.yml` — being stabilized in PR #9; no deploy pipeline |
| 3. Testing | ✅ Mature | 464 test methods across 30 files; mutmut at 91% kill score; Hypothesis property-based tests |
| 4. Code quality | ✅ Strong | ruff configured in `pyproject.toml`; lint CI step exists |
| 5. Dependency management | ⚠️ Minimal | No lockfile; no Dependabot config; Frappe v16 hard-pinned in `pyproject.toml` |
| 6. Security | ⚠️ Gap | `test_security_audit.py` exists; no SAST/DAST/secret scanning; no SECURITY.md |
| 7. Secrets management | ✅ Safe baseline | `.env.example` only; `.env` gitignored; no vault |
| 8. Observability | ⚠️ Gap | `frappe.logger()` calls; no Sentry; no structured logs; no metrics |
| 9. Deployment | ⚠️ Gap | Frappe Cloud auto-deploy on git push; no staging site; no rollback runbook |
| 10. Backup & DR | ❌ Missing | No backup scripts; no restore runbook; no documented RPO/RTO |
| 11. Incident response | ❌ Missing | No runbooks/; no status page; no postmortem template; no on-call |
| 12. Documentation | ✅ Extensive | 53+ markdown files; `decisions_log.md` with 66+ DEC entries; `lessons_learned.md` |
| 13. Performance | ✅ Good | EXPLAIN tests, SLA timing assertions, 10K load test |
| 14. Accessibility | ⚠️ Mentioned | Tab height note in design spec; no WCAG audit; no axe-core config |
| 15. Compliance | ⚠️ Partial | `track_changes` enabled on key DocTypes; no privacy policy / PIPEDA docs / retention policy |
| 16. Data engineering | ✅ Good | Versioned patches in `hamilton_erp/patches/v0_1/`; idempotent seed; track_changes |
| 17. Feature flags | ❌ Missing | None |
| 18. API design | ⚠️ Partial | `api.py` exists; idempotency tested; no versioning; no rate limiting |
| 19. Frontend | ⚠️ Minimal | Asset board page DocType + design spec; no bundle analyzer; no Lighthouse CI |
| 20. Database | ✅ Strong | Index audits via INFORMATION_SCHEMA; EXPLAIN tests; MariaDB 12.2.2 (current) |
| 21. Team/process | ✅ Mature | `.taskmaster/`; `decisions_log.md`; `claude_memory.md`; daily inbox flow |
| 22. Cost monitoring | ❌ Missing | No tracker; no Frappe Cloud budget docs |
| 23. Legal/BC | ❌ Missing | No code escrow; no IP assignment templates; no SOC 2 plan; no bus-factor doc |
| 24. AI dev practices | ✅ Mature | `CLAUDE.md` (292 lines); `.claude/` agents/commands/skills; claude-mem |

## Detail by category

### 1. Source control & branching
- **Commits:** 316 in last 60 days (~5/day).
- **Conventional Commits**: prefixes used consistently (`feat`, `fix`, `chore`, `docs`, `ci`).
- **Branches**: `main`, `fix/ci-vendor-setup-action` (current), plus feature branches `feature/task-20-realtime` through `feature/task-24-h12-e2e`.
- **Tags**: none (no semantic versioning).
- **`.gitignore`**: covers `__pycache__`, `.DS_Store`, `node_modules/`, `env/`, `*.log`, `.superpowers/`, `dump.rdb`.
- **Missing**: no PR template, no `.gitmessage`, no `CHANGELOG.md`, no semver tags, branch protection on `main` not verified.

### 2. CI/CD
- **GitHub Actions workflows**: `tests.yml` (5,569 bytes — currently being stabilized in PR #9), `lint.yml` (743 bytes), `claude-review.yml` (887 bytes).
- **Frappe Cloud**: live site `hamilton-erp.v.frappe.cloud`; auto-deploy on push to main.
- **Custom slash command**: `.claude/commands/deploy.md`.
- **Missing**: no Frappe Cloud manifest in repo; no staging environment; no rollback runbook; no smoke-test post-deploy; no DORA metrics tracked.

### 3. Testing
- **Counts**: 464 `def test_*` methods across 103 classes in 30 test files.
- **Notable test files**: `test_lifecycle.py` (66 KB), `test_extreme_edge_cases.py` (26 KB), `test_stress_simulation.py` (29 KB), `test_database_advanced.py` (30 KB), `test_load_10k.py` (13 KB), `test_security_audit.py` (14 KB), `test_hypothesis.py` (10 KB).
- **pytest config**: `[tool.pytest.ini_options]` in `pyproject.toml`; `testpaths = ["hamilton_erp"]`.
- **Hypothesis**: in `test_hypothesis.py` for property-based testing.
- **mutmut**: configured in `pyproject.toml`; 91% kill score on `lifecycle.py` and `locks.py`.
- **conftest.py**: present (1.5 KB), boots Frappe for pytest/mutmut.
- **Missing**: no `.coveragerc`; no coverage threshold enforced in CI; no Codecov upload; no E2E browser tests; no DAST; no contract testing (which is fine — overkill for monolith); no chaos drills; no smoke test post-deploy.

### 4. Code quality & review
- **ruff** configured: `line-length = 110`, `target-version = "py311"`, lint rules `["F","E","W","I"]`, ignore `["E501","W191","E101"]` (long lines and Frappe's tab indentation).
- **Format**: tab indent, double quote.
- **Missing**: no `.pre-commit-config.yaml`; no mypy/pyright config (typing imports are used but not enforced); no complexity gating (radon/lizard); no dead-code detection (vulture); no bandit/semgrep.

### 5. Dependency management
- `pyproject.toml [project]`: `requires-python = ">=3.11"`, dependencies empty.
- `[tool.bench.frappe-dependencies]`: `frappe>=16.0.0,<17.0.0`, `erpnext>=16.0.0,<17.0.0`.
- **`.env.example`** present (12 API key placeholders).
- **Missing**: no lockfile (no `uv.lock`, `poetry.lock`, `requirements.lock`, or `package-lock.json`); no Dependabot; no Renovate; no `pip-audit` in CI; no SBOM.

### 6. Security
- `test_security_audit.py` (14 KB) — dedicated security audit tests.
- `frappe.logger().warning(...)` for lock-contention events in `locks.py` and `lifecycle.py`.
- Hardening commit `365259a` ("Phase 0 hardening — 19 bugs fixed across 6 test runs").
- **Missing**: no `SECURITY.md`; no bandit/semgrep; no secret scanning configured (gitleaks/trufflehog); no documented threat model; no CSRF/CORS policy doc; no security headers documented.

### 7. Secrets management
- `.env.example` tracked; `.env` gitignored; `env/` directory gitignored.
- **Missing**: no rotation policy; no vault integration; no secret scanning in CI.

### 8. Observability
- `frappe.logger()` calls (plain `.warning()`, not structured).
- **Missing**: no Sentry; no external logging service; no metrics; no APM; no structured JSON logs; no log aggregation; no SLO/SLI.

### 9. Deployment
- Auto-deploy on push to main (Frappe Cloud).
- `hooks.py` (3.8 KB) defines `scheduler_events`, `override_doctype_class`.
- `setup/install.py` (3.2 KB).
- Patches in `hamilton_erp/patches/v0_1/`.
- **Missing**: no `frappe-cloud.json`; no staging site; no environment-specific configs; no rollback procedure documented; no deploy frequency tracked; no deploy windows.

### 10. Backup & DR
- Test fixture `restore_dev_state()` in `test_helpers.py` (dev-only, not a backup).
- **Missing**: no backup scripts; no restore runbook; no RPO/RTO targets; no immutable / off-site backup; no test-restore drill record. (Frappe Cloud automatic backups exist but are not documented in our repo or proven via test restore.)

### 11. Incident response
- `docs/lessons_learned.md` (151 lines) — incident retrospectives.
- `docs/troubleshooting.md` (80 lines) — symptoms and fixes.
- `docs/venue_rollout_playbook.md` (207 lines).
- **Missing**: no `runbooks/` directory; no postmortem template; no severity levels defined; no on-call alerting; no status page; no customer-comms templates.

### 12. Documentation
- `docs/decisions_log.md` (378 lines, DEC-001 → DEC-066+).
- `docs/lessons_learned.md`, `docs/testing_guide.md` (441 lines), `docs/build_phases.md` (273 lines), `docs/current_state.md` (438 lines).
- `docs/coding_standards.md` (32 KB), `docs/hamilton_erp_build_specification.md` (40 KB), `docs/phase1_design.md` (50 KB), `docs/claude_memory.md` (39 KB).
- Subdirs: `design/`, `reviews/`, `inbox/`, `superpowers/`.
- **Missing**: no Diataxis structure; no auto-generated API docs; no published docs site; no glossary.

### 13. Performance
- `test_database_advanced.py` includes EXPLAIN-plan tests, SLA timing assertions (<100 ms board query, <200 ms session, <50 ms lock).
- `test_load_10k.py` (13 KB) — 10,000 check-in load simulation.
- Index audits via `INFORMATION_SCHEMA.STATISTICS`.
- **Missing**: no profiling (py-spy, Scalene); no Frappe Recorder workflow; no production slow-query log review cadence; no Cloudflare; no bundle-size budget.

### 14. Accessibility
- One mention: V8 design notes "Tab height: 56px (accessibility)".
- WCAG 2.2 referenced in `venue_website_prompts.md`.
- **Missing**: no WCAG audit; no axe-core; no Lighthouse CI; no manual screen-reader pass; no AODA accessibility statement.

### 15. Compliance & legal
- `track_changes: 1` on `venue_session.json` and `shift_record.json`.
- Activity Log retention mentioned in inbox audit doc.
- Age verification mentioned in `venue_website_prompts.md` (not implemented).
- **Missing**: no `PRIVACY.md`; no terms-of-service; no PIPEDA RROSH playbook; no retention policy documented; no cookie consent; no DPAs catalogued; no PCI scope statement.

### 16. Data engineering
- Patches in `hamilton_erp/patches/v0_1/`: `seed_hamilton_env.py` (idempotent), `rename_glory_hole_to_gh_room.py` (rename).
- Custom audit DocTypes: `asset_status_log`, `comp_admission_log`, `cash_reconciliation`, `hamilton_board_correction`.
- 11 custom DocTypes total.
- **Missing**: no expand-and-contract documentation; no soft-delete pattern doc; no right-to-erasure flow; no anonymization job.

### 17. Feature flags
- None.

### 18. API design
- `api.py` (9.5 KB) — Hamilton-specific endpoints.
- Idempotency tested (`test_seed_is_idempotent`).
- **Missing**: no API versioning (no `/v1/`); no rate limiting; no OpenAPI spec; no webhook reliability infra; no API auth scheme doc.

### 19. Frontend
- Asset board page DocType: `hamilton_erp/page/asset_board/asset_board.json`.
- `docs/design/V9_CANONICAL_MOCKUP.html` (69 KB), `docs/design/asset_board_ui.md` (5.7 KB), V9 commits 2026-04-27.
- 9 `.js` files.
- **Missing**: no bundle analyzer; no Lighthouse CI; no browser support matrix; no INP measurement; no error boundaries doc.

### 20. Database (MariaDB)
- MariaDB 12.2.2 locally (current GA per Feb 2026 release).
- Index tests in `test_database_advanced.py` verify primary + composite indexes.
- EXPLAIN tests for asset board, session, lock SLAs.
- **Missing**: no slow-query log analysis cadence; no `pt-query-digest` workflow; no read replica plan; no PITR documentation.

### 21. Team & process
- `.taskmaster/` (config, state, tasks, templates).
- `docs/decisions_log.md` (66+ entries), `docs/lessons_learned.md`, `docs/claude_memory.md`.
- Inbox pattern via `docs/inbox.md`.
- `CLAUDE.md` (292 lines) with playbooks.
- `.superpowers/brainstorm/` with dated sessions.
- **Missing**: no weekly retro; no Shape Up cycles; no public roadmap.

### 22. Cost monitoring
- None.

### 23. Legal & business continuity
- None.

### 24. AI dev practices
- `CLAUDE.md` (292 lines).
- `.claude/` directory with agents, commands, skills, settings.
- `docs/claude_memory.md` (39 KB).
- claude-mem MCP (per memory references).
- 3-AI review checkpoints documented.
- **Missing**: no AGENTS.md (cross-tool standard, ratified Dec 2025); no prompt eval harness; no AI-review tool in CI (CodeRabbit/Greptile/Qodo); no model-versioning policy beyond commit messages.

---

# Section 3 — Prioritized Gaps

Five tiers, each gap structured as: **What** / **Why for Hamilton** / **Effort** / **Tools (alternatives)** / **References** / **Prereqs**.

Effort estimates are calendar-realistic for a beginner solo dev: a "2-hour" task usually runs 4–6h once tooling friction is included.

## Tier 0 — Blocking go-live

These five gaps **must** ship before Hamilton's production launch (Task 25). They are the difference between "small business launching software" and "small business posting customer data on the open internet."

### T0-1. Privacy policy + terms of service published on the site

- **What:** Two public pages: `Privacy Policy` and `Terms of Service`. Privacy must reference PIPEDA, name Chris as Privacy Officer, list data collected, disclose data retention windows, name third-party processors (Stripe, Frappe Cloud), and document the breach-notification process.
- **Why for Hamilton (bathhouse):** PIPEDA mandates a designated Privacy Officer and a public privacy notice for any commercial collection of personal data. A bathhouse member's name + visit time + locker assignment is sensitive ("real risk of significant harm" in PIPEDA terms — humiliation, damage to relationships counts). Going live without this is illegal in Canada and an instant complaint magnet.
- **Effort:** 4 hours with iubenda or Termly questionnaire; 2 hours of self-review for bathhouse-specific clauses; 30 minutes to publish.
- **Tools:** **iubenda Pro** (~$30/mo, multi-region, scales to 6 venues — recommended). Alternative: **Termly** ($15/mo, easier solo flow). Alternative: **TermsFeed** (cheapest, less polished). Skip free generators — they don't cover PIPEDA + multiple US state laws together.
- **References:**
  - https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda_brief/
  - https://www.iubenda.com/en/privacy-and-cookie-policy-generator/
- **Prereqs:** Decide on data retention windows first (T0-2 below).

### T0-2. Backup + restore runbook with a *tested* restore

- **What:** A `docs/runbooks/restore.md` file documenting: (1) where Frappe Cloud's backups land, (2) how to restore to a throwaway site, (3) the exact CLI commands, (4) where the encryption key is stored separately. Plus an actual once-per-quarter test restore into a scratch site, with screenshot or log evidence.
- **Why for Hamilton:** Frappe Cloud auto-backs-up every 6 hours on the $25+ plan with one offsite copy in S3 (Mumbai by default). But if the encryption key in `site_config.json` is lost, the backup is useless. Untested backups become "we paid for backups" not "we have backups." Ransomware in 2025 targeted backup infrastructure in 96% of attacks per CISA.
- **Effort:** 3 hours to write runbook; 2 hours for first test restore; 1 hour quarterly thereafter.
- **Tools:** Frappe Cloud built-in (already paid). Add Backblaze B2 with Object Lock at scale ($6/TB/mo) for the second offsite copy in Tier 2.
- **References:**
  - https://docs.frappe.io/cloud/sites/backups
  - https://www.veeam.com/blog/321-backup-rule.html
- **Prereqs:** Ensure the Frappe Cloud encryption key is exported and stored in 1Password before launch.

### T0-3. Secret scanning in CI + no committed secrets

- **What:** Two commits: (1) add **gitleaks** as a pre-commit hook so accidental secret commits fail locally, (2) enable **GitHub native secret scanning + push protection** on the repo settings. Verify nothing currently committed contains a real secret (the `.env.example` is fine; check `.claude/settings.json.backup` — that's untracked but should be reviewed).
- **Why for Hamilton:** A leaked Stripe key on a public repo costs $50K in 4 hours. A leaked Frappe Cloud admin token gives attackers your member database. Snyk reported 28.65 million secrets leaked on public GitHub in 2025 alone.
- **Effort:** 1 hour total.
- **Tools:** **gitleaks** (pre-commit, free) + **GitHub secret scanning + push protection** (free for public repos, $4/dev/mo for private). Alternative for runtime credential checks: **TruffleHog** weekly cron (verifies leaked secrets are still live).
- **References:**
  - https://github.com/gitleaks/gitleaks
  - https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning
  - https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- **Prereqs:** None.

### T0-4. Sentry integration for error tracking + Better Stack uptime

- **What:** Sign up for Sentry's free tier; install `sentry-sdk[python]`; add a 3-line `sentry_sdk.init(dsn=..., traces_sample_rate=0.1)` in `hooks.py`; configure DSN as a Frappe site config. Sign up for Better Stack free tier; add one HTTPS check on `hamilton-erp.v.frappe.cloud` every 3 minutes; route alerts to Chris's phone via SMS + push.
- **Why for Hamilton:** When an operator hits a 500 error during a 11pm check-in rush, you need to know inside 30 seconds, not the next morning. Sentry captures stack trace + breadcrumbs + user; Better Stack tells you "site is down" before the operator does. Without these, you operate in the dark.
- **Effort:** 2 hours total (Sentry: 45min; Better Stack: 30min; testing: 45min).
- **Tools:** **Sentry free tier** (5K errors/mo, sufficient for 1 venue). Alternative: **GlitchTip** (self-hosted Sentry-compatible, free if you run it yourself — too much overhead). **Better Stack free tier** for uptime. Alternative: **UptimeRobot** (older but free).
- **References:**
  - https://docs.sentry.io/platforms/python/integrations/
  - https://betterstack.com/uptime
- **Prereqs:** None.

### T0-5. PCI-DSS scope statement + Stripe Checkout (not Elements)

- **What:** A `docs/compliance/pci_scope.md` declaring that Hamilton ERP processes payments via **Stripe Checkout** (fully Stripe-hosted), keeping the system in **PCI SAQ-A** scope. No card data ever touches your server. Confirm the Stripe integration uses redirects to Stripe-hosted checkout pages, not embedded Elements.
- **Why for Hamilton:** PCI DSS v4.0.1 became the only valid version on Dec 31, 2024; the 51 future-dated requirements became mandatory March 31, 2025. SAQ-A is the lightest level (~9 questions, no engineering work). Anything that brings cards onto your server jumps you to SAQ-D and dramatically more requirements (quarterly external scans, annual penetration test). For a 6-venue rollout, staying SAQ-A is non-negotiable.
- **Effort:** 30 min if Stripe Checkout is already used; 8 hours if Elements is used and needs replacing.
- **Tools:** **Stripe Checkout** (mandatory choice). Alternative for redundancy: **Square Online Checkout** (similar SAQ-A profile, useful as a backup processor).
- **References:**
  - https://www.pcisecuritystandards.org/document_library/
  - https://stripe.com/docs/security/guide
  - https://strictlyzero.com/announcements/payments-announcements/pci-compliance-checklist-2026-the-merchants-guide-to-dss-4-0-1/
- **Prereqs:** Confirm payment integration approach before Phase 2.

## Tier 1 — First 30 days post go-live

These can wait a month but should not wait longer. They harden the launch and give you the artifacts you'll need the first time something goes wrong in production.

### T1-1. Incident response runbooks + status page

- **What:** Create `docs/runbooks/` with one file per known failure mode: `redis_lock_stuck.md`, `mariadb_full.md`, `frappe_cloud_outage.md`, `payment_processor_down.md`, `realtime_dropped.md`. Each runbook is 5–15 lines: detect, diagnose, fix, verify. Set up a public status page at `status.hamilton-erp.com` (Better Stack hosted, free with the uptime plan).
- **Why for Hamilton:** Runbooks turn 3am panic into 3am procedure. A status page preempts the support flood — when customers see an acknowledged incident, support tickets drop ~70%.
- **Effort:** 6 hours total (1h per runbook x 5; 1h status page setup).
- **Tools:** **Better Stack** (already in T0-4, free tier includes status page + uptime + on-call). Alternative: **Instatus** (cheaper, prettier, status-page-only).
- **References:**
  - https://www.atlassian.com/incident-management/handbook
  - https://sre.google/sre-book/postmortem-culture/
  - https://response.pagerduty.com/before/severity_levels/
- **Prereqs:** T0-4 done.

### T1-2. Postmortem template + first-incident exercise

- **What:** `docs/postmortems/TEMPLATE.md` based on Google SRE's blameless format (timeline, root cause, what went well, what went badly, action items). After your first SEV1 (outage > 30 min), fill it in within 48 hours.
- **Why for Hamilton:** Even with one developer, the discipline of writing it down forces clear thinking. Postmortems are how the next incident becomes less likely.
- **Effort:** 30 min for template; 2 hours per postmortem when needed.
- **Tools:** Just markdown.
- **References:**
  - https://sre.google/sre-book/example-postmortem/
- **Prereqs:** T1-1 done (you need severity levels first).

### T1-3. Dependabot + pip-audit in CI

- **What:** Add `.github/dependabot.yml` with weekly schedule for `pip` and `github-actions` ecosystems, group security updates. Add a `pip-audit` step to the existing test workflow that fails on high/critical CVEs.
- **Why for Hamilton:** OWASP Top 10 2025 elevated **Software Supply Chain Failures** — dependency CVEs are now the fastest-growing attack vector. Dependabot is free and zero-config for GitHub.
- **Effort:** 1 hour total (Dependabot YAML + CI step).
- **Tools:** **Dependabot** (built into GitHub, free, zero-config). Alternative: **Renovate** (more configurable, better PR grouping; overkill for 1-dev shop). For vuln scanning: **pip-audit** (PyPA official) over **safety** (older).
- **References:**
  - https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/about-dependabot-version-updates
  - https://github.com/pypa/pip-audit
- **Prereqs:** None.

### T1-4. SECURITY.md + threat model document

- **What:** `SECURITY.md` at repo root explaining how to report vulnerabilities. `docs/security/threat_model.md` doing one-page STRIDE on the asset board and lifecycle methods (1 column per: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege).
- **Why for Hamilton:** SECURITY.md is the GitHub-recommended convention; researchers won't disclose to you without one. Threat model forces you to think like an attacker before they think like one.
- **Effort:** 4 hours total.
- **Tools:** Just markdown. Microsoft's Threat Modeling Tool is overkill.
- **References:**
  - https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository
  - https://owasp.org/www-community/Threat_Modeling
- **Prereqs:** None.

### T1-5. Pre-commit framework + ruff + gitleaks + bandit

- **What:** `.pre-commit-config.yaml` running `ruff check`, `ruff format`, `gitleaks` (already in T0-3), and `bandit` (Python security linter) on every commit.
- **Why for Hamilton:** Without pre-commit hooks, broken/insecure code reaches the repo and breaks the next pull. Pre-commit framework is the de facto standard.
- **Effort:** 2 hours.
- **Tools:** **pre-commit framework** (Python, huge ecosystem, the safer default). Alternative: **Lefthook** (Go, ~3x faster, parallel — upgrade path when hooks get slow).
- **References:**
  - https://pre-commit.com/
  - https://github.com/PyCQA/bandit
- **Prereqs:** T0-3 (gitleaks).

### T1-6. Data retention policy + scheduled anonymization job

- **What:** A `docs/compliance/data_retention.md` declaring: guest check-in records → hard delete after 90 days; Member records inactive 24 months → anonymize (replace name with hash, keep visit count); audit log entries → keep 24 months minimum (PIPEDA breach record retention). Implement as a Frappe scheduled job (weekly).
- **Why for Hamilton:** PIPEDA Principle 5 (Limiting Use, Disclosure, and Retention) requires deletion when no longer needed. Bathhouse data exposure has career-ending implications for victims; aggressive pruning is ethics, not just compliance. Without a written policy, you have no defense if a regulator asks.
- **Effort:** 2 hours policy + 6 hours code (scheduled job + tests).
- **Tools:** Frappe scheduled events (`hooks.py` `scheduler_events`). Add audit log row for every anonymization to prove it ran.
- **References:**
  - https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda_brief/
  - https://axiom.co/blog/the-right-to-be-forgotten-vs-audit-trail-mandates
- **Prereqs:** T0-1.

### T1-7. AODA accessibility statement + axe-core in CI

- **What:** Public `Accessibility` page on the venue's site referencing WCAG 2.2 AA conformance. Add `axe-core` smoke test in CI on the asset board template; fail PR on serious/critical violations.
- **Why for Hamilton:** AODA (Accessibility for Ontarians with Disabilities Act) requires WCAG 2.0 AA conformance for orgs with 50+ employees in Ontario, with a public statement. Penalties up to CA$100,000/day for non-compliance. Even pre-50-employee, the public statement and a CI gate cost almost nothing and signal due diligence.
- **Effort:** 4 hours (statement + CI integration + first round of fixes).
- **Tools:** **axe-core** in CI (free, Deque). Alternative for manual review: **axe DevTools browser extension**. Skip JAWS for screen-reader testing — NVDA + VoiceOver covers majority of users.
- **References:**
  - https://www.w3.org/WAI/standards-guidelines/wcag/
  - https://www.deque.com/canada-compliance/aoda/
  - https://www.deque.com/axe/
- **Prereqs:** None.

### T1-8. ADR/decisions log convergence on Nygard format

- **What:** Convert `docs/decisions_log.md`'s informal entries into one-file-per-decision Markdown ADRs (Nygard format: Title, Status, Context, Decision, Consequences) under `docs/adrs/`. Keep the rolling log file as an index.
- **Why for Hamilton:** Hamilton already has the discipline (DEC-001 → DEC-066+); the ADR format is just better at scale because each decision has its own URL and history. Future-you (or a contractor) will thank you when looking up "why is the lock TTL 15 seconds?"
- **Effort:** 6 hours (mostly migration).
- **Tools:** Just Markdown + the **MADR** template. Alternative: **adr-tools** CLI for new ADRs.
- **References:**
  - https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
  - https://adr.github.io/adr-templates/
- **Prereqs:** None.

## Tier 2 — Before second venue (DC / Crew Club)

When a second venue (DC / Crew Club) joins, you can no longer treat the system as single-tenant. These items prevent the kinds of bugs that show up only in multi-venue ops.

### T2-1. Staging environment on Frappe Cloud

- **What:** Add a second Frappe Cloud bench/site `hamilton-staging.frappe.cloud` (~$25/mo). Every change merges to staging first, runs tests, soaks for 24h, then promotes to prod via tag-based deploy.
- **Why for Hamilton:** Catching a broken migration on staging is $0; catching it on prod is "Hamilton lobby line out the door at 11pm."
- **Effort:** 4 hours setup + ongoing $25/mo.
- **Tools:** **Frappe Cloud Bench** (built-in). No alternative — fight Frappe Cloud, lose.
- **References:**
  - https://docs.frappe.io/cloud/sites/migrate-an-existing-site
- **Prereqs:** None.

### T2-2. Feature flags (per-venue rollout)

- **What:** Either (a) a simple `Site Settings` DocType with checkbox fields per venue (cheap), or (b) self-host **Unleash** alongside Frappe Cloud (better at scale).
- **Why for Hamilton:** Different venues need different features (DC has 3 tablets; Hamilton has 1; Dallas has key scanners). Without flags, every venue runs the same code, including features that aren't ready for them. Kill switches for payments and check-in are also flag patterns.
- **Effort:** 1 day for DocType-based; 3 days for Unleash self-host.
- **Tools:** **DocType + Frappe cache** for the first 5–10 flags. Alternative: **Unleash** (free self-host, OpenFeature SDK). Alternative: **GrowthBook** (free self-host, also does A/B testing). Skip **LaunchDarkly** ($10/seat/mo) until 50+ flags.
- **References:**
  - https://www.cncf.io/projects/openfeature/
  - https://www.getunleash.io/
  - https://www.statsig.com/perspectives/feature-flag-debt-management
- **Prereqs:** Decide: DocType vs service.

### T2-3. Smoke tests after deploy

- **What:** A `pytest --smoke` marker on a tiny set of tests that hit the live URL with a service-account login: home page loads, login works, asset board renders one venue. Run automatically after every Frappe Cloud deploy.
- **Why for Hamilton:** Catches the "deploy succeeded but the site is broken" class of bug in 30 seconds instead of the operator-discovers-it-at-9am scenario.
- **Effort:** 6 hours.
- **Tools:** **pytest + requests** (already in stack). Alternative: **Playwright** (heavier, needed if smoke tests need DOM interaction).
- **References:**
  - https://docs.pytest.org/en/stable/how-to/mark.html
- **Prereqs:** T2-1 (staging) so you can test smoke on staging before prod.

### T2-4. Rollback automation

- **What:** A `bench rollback` runbook + a `gh workflow` that, given a target commit SHA, checks out the SHA on Frappe Cloud and triggers a redeploy. Practice quarterly.
- **Why for Hamilton:** Frappe Cloud's "revert deploy" UI works but is slow under stress. A scripted rollback can be triggered in 30 seconds from a phone.
- **Effort:** 8 hours.
- **Tools:** **GitHub Actions + Frappe Cloud API**. Alternative: just document the manual UI steps if API automation feels risky.
- **References:**
  - https://docs.frappe.io/cloud/sites/backups
- **Prereqs:** T2-1.

### T2-5. Structured JSON logs

- **What:** Configure Frappe to emit JSON logs (timestamp, level, site, user, request_id, trace_id) instead of plain text. Pipe to **Better Stack Logs** (free 1GB/mo) or **Axiom** (free 500GB/mo).
- **Why for Hamilton:** Multi-venue means you need to filter logs by venue. Plain text logs make this manual; JSON makes it queryable.
- **Effort:** 1 day.
- **Tools:** **structlog** + **python-json-logger**. Backend: **Better Stack Logs** (simplest) or **Grafana Cloud Loki** (more powerful, free tier 50GB).
- **References:**
  - https://www.structlog.org/
- **Prereqs:** T0-4 (Sentry/Better Stack already in place).

### T2-6. Slow-query log analysis cadence

- **What:** Enable MariaDB `log_slow_query_time = 0.5`, `log_queries_not_using_indexes = ON` in production. Weekly cron runs **pt-query-digest** and emails Chris the top 5 slow queries.
- **Why for Hamilton:** A single missing index can turn a 2ms query into a 2-second table scan. With 6 venues sharing the schema, this matters more.
- **Effort:** 4 hours setup + 30 min/week ongoing.
- **Tools:** **pt-query-digest** (Percona Toolkit, free). Alternative: paid APMs surface this automatically (Datadog, New Relic) — overkill for $40/mo Frappe Cloud.
- **References:**
  - https://mariadb.com/docs/server/server-management/server-monitoring-logs/slow-query-log/slow-query-log-overview
  - https://www.percona.com/doc/percona-toolkit/LATEST/pt-query-digest.html
- **Prereqs:** None.

### T2-7. AGENTS.md cross-tool symlink

- **What:** A thin `AGENTS.md` at repo root that imports/refers to `CLAUDE.md` (or duplicates the universal parts). AGENTS.md became the converging cross-tool standard in Dec 2025 (Linux Foundation Agentic AI Foundation, backed by OpenAI/Anthropic/Google/AWS).
- **Why for Hamilton:** When a contractor (or future-you) uses Cursor or Codex instead of Claude Code, AGENTS.md is the file they read. Today CLAUDE.md is the only signal.
- **Effort:** 1 hour.
- **Tools:** Just markdown.
- **References:**
  - https://thepromptshelf.dev/blog/cursorrules-vs-claude-md/
  - https://www.augmentcode.com/guides/how-to-build-agents-md
- **Prereqs:** None.

### T2-8. CodeRabbit (AI code review)

- **What:** Install **CodeRabbit** GitHub App on the repo; let it comment on every PR.
- **Why for Hamilton:** CodeRabbit catches ~44% of bugs in benchmarks; for a 1-dev shop with no second pair of eyes, this is the cheapest "second reviewer." $24/dev/mo.
- **Effort:** 30 min setup.
- **Tools:** **CodeRabbit** ($24/dev/mo, best signal-per-dollar for solo dev). Alternative: **Greptile** (premium, 82% bug catch, higher cost — worth it once a missed bug costs more than the price delta). Alternative: **Qodo Merge** (combines review + auto unit-test generation).
- **References:**
  - https://www.coderabbit.ai/
  - https://www.greptile.com/benchmarks
- **Prereqs:** None.

### T2-9. Cost tracker + Frappe Cloud weekly check

- **What:** A Google Sheet with vendor / monthly / renewal date columns (Frappe Cloud, GitHub, Anthropic API, domain registrar, Stripe fees, Sentry, Better Stack, etc.). 30-second weekly look at Frappe Cloud's billing dashboard for per-site usage anomalies.
- **Why for Hamilton:** With 6 venues, each on a $25-40/mo plan, that's $150-240/mo just for Frappe Cloud — easy to miss a runaway report job that doubles a venue's bill.
- **Effort:** 1 hour setup + 30 min/month.
- **Tools:** Just a Google Sheet. Alternative for >$1k/mo: **Vendr** or **Tropic** (procurement tools — overkill at your scale).
- **References:**
  - https://frappe.io/cloud/pricing
  - https://docs.frappe.io/cloud/billing/billing-cycle
  - https://www.finops.org/framework/principles/
- **Prereqs:** None.

### T2-10. Bus-factor doc + 1Password emergency access

- **What:** `docs/business_continuity.md` (2 pages): who to call if Chris is unreachable; where the code lives (GitHub URL + recovery email + 2FA backup codes location); how to disable bookings; how to contact each venue manager. Set up **1Password Family or Business** with a designated emergency-access person.
- **Why for Hamilton:** A bus factor of 1 is the most common failure mode for solo-owner businesses. Even rough documentation buys 95% of the value here.
- **Effort:** 4 hours (2h doc + 2h 1Password setup).
- **Tools:** **1Password Family** ($10/mo) or **1Password Business** ($8/user/mo). Alternative: **Bitwarden Family** (cheaper, similar emergency-access feature).
- **References:**
  - https://support.1password.com/emergency-kit/
  - https://swimm.io/learn/developer-experience/what-is-the-bus-factor-why-it-matters-and-how-to-increase-it
- **Prereqs:** None.

## Tier 3 — Year-one maturity

These are practices a mature shop has but a 1-venue pilot can defer 12–18 months without serious risk.

### T3-1. OpenTelemetry + Grafana Cloud (real metrics + traces)

- **What:** Add OpenTelemetry Python SDK to the Frappe app; ship metrics + traces via OTel Collector to **Grafana Cloud free tier** (10k metrics, 50GB logs, 50GB traces). Define SLIs (p95 latency, error rate, lock acquisition time) and SLOs (99.5% of asset board ops < 500ms).
- **Why for Hamilton:** Sentry is great for errors but doesn't surface "the asset board is getting slower week over week" patterns. OTel + Grafana shows trends.
- **Effort:** 3 days.
- **Tools:** **OpenTelemetry SDK** + **OTel Collector** + **Grafana Cloud free tier**. Alternative: **Axiom** (similar free tier, simpler queries, weaker alerting).
- **References:**
  - https://opentelemetry.io/
  - https://grafana.com/products/cloud/
- **Prereqs:** T2-5.

### T3-2. SBOM (Software Bill of Materials)

- **What:** Generate a CycloneDX SBOM in CI on every release tag.
- **Why for Hamilton:** Necessary if any enterprise customer (e.g. a hotel partnership) ever asks. Otherwise low-priority.
- **Effort:** 4 hours.
- **Tools:** **cyclonedx-py** (free, official). Alternative: **Syft** (general-purpose, works for non-Python too).
- **References:**
  - https://github.com/CycloneDX/cyclonedx-python
- **Prereqs:** None.

### T3-3. OWASP ZAP DAST baseline scan weekly

- **What:** GitHub Actions cron that runs OWASP ZAP baseline scan against staging weekly.
- **Why for Hamilton:** Catches authentication misconfigs, missing security headers, SQL injection patterns DAST can find by attacking. Pairs well with Semgrep SAST (Tier 4).
- **Effort:** 4 hours.
- **Tools:** **OWASP ZAP** (free, open-source, Docker container).
- **References:**
  - https://www.zaproxy.org/
- **Prereqs:** T2-1 (staging environment).

### T3-4. Lighthouse CI + Real User Monitoring

- **What:** Lighthouse CI on every PR with hard thresholds (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1, a11y ≥ 90). RUM via the `web-vitals` JS library piped to a dashboard (DebugBear or self-hosted via Plausible).
- **Why for Hamilton:** Catches frontend performance regressions before staff at the slowest venue (DC has 3 tablets on bathhouse WiFi) notice.
- **Effort:** 1 day.
- **Tools:** **Lighthouse CI** (free, Google). **web-vitals** JS library (free).
- **References:**
  - https://github.com/GoogleChrome/lighthouse-ci
  - https://web.dev/articles/vitals
- **Prereqs:** None.

### T3-5. Diataxis-structured docs site

- **What:** Migrate `docs/` into a published **MkDocs Material** site at `docs.hamilton-erp.com` with Diataxis structure: `/tutorials/`, `/how-to/`, `/reference/`, `/explanation/`. Auto-generate Frappe doctype reference under `/reference/doctypes/`.
- **Why for Hamilton:** When you train a contractor or write venue-staff user docs, a real docs site beats a pile of markdown.
- **Effort:** 2 days.
- **Tools:** **MkDocs Material** (entered maintenance mode Nov 2025 but still works fine for years; free; Python-native; the simplest pick). Alternative: **Docusaurus** (Meta, React, more flexible). Alternative: **GitBook** (zero-ops, paid, vendor lock-in).
- **References:**
  - https://diataxis.fr/
  - https://squidfunk.github.io/mkdocs-material/
- **Prereqs:** T1-8 helps but not strict.

### T3-6. Right-to-erasure flow tested end-to-end

- **What:** Implement a `Member Erasure Request` DocType with workflow: submitted → verified → anonymized → confirmed-to-member-by-email. Test quarterly. Keep audit log entry for legal defense.
- **Why for Hamilton:** PIPEDA gives the right to access/correct; sensitive industry ethics extend that to erasure. Sister jurisdictions (CCPA, GDPR for EU traffic) have explicit erasure rights with 30-day SLAs.
- **Effort:** 1 week.
- **Tools:** Custom Frappe DocType + scheduled job + email template.
- **References:**
  - https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda_brief/
  - https://www.ironmountain.com/blogs/2019/is-the-anonymization-of-personal-data-the-same-as-data-erasure
- **Prereqs:** T1-6.

### T3-7. API versioning + OpenAPI spec

- **What:** Version every public Frappe whitelisted method as `hamilton_erp.api.v1.checkin`. Hand-write `docs/api/openapi.yaml` covering the 5–10 endpoints you expose. Publish via **Stoplight Studio** (free up to 3 projects) or **Redocly**.
- **Why for Hamilton:** When the first partner integration arrives (e.g. mobile app, POS plug-in), versioning gives you a way to ship breaking changes without breaking them.
- **Effort:** 1 week.
- **Tools:** OpenAPI 3.1. **Stoplight** for designing; **Redocly** for hosting partner docs.
- **References:**
  - https://swagger.io/specification/
  - https://www.speakeasy.com/api-design/versioning
- **Prereqs:** First partner integration scoped.

### T3-8. Inspect AI eval harness

- **What:** When AI starts shipping user-facing output (e.g. an AI-summary of guest history), wire **Inspect AI** evals into CI. Run on every PR touching AI features.
- **Why for Hamilton:** AI features regress silently across model upgrades. Evals catch this.
- **Effort:** 4 days for first eval suite.
- **Tools:** **Inspect AI** (UK AISI, used by Anthropic/DeepMind/Grok). Alternative: **Promptfoo** (simpler YAML+CLI, less long-term backing).
- **References:**
  - https://hamel.dev/notes/llm/evals/inspect.html
  - https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- **Prereqs:** AI features actually exist.

### T3-9. Mutation testing in CI (mutmut already exists; gate it)

- **What:** Add a CI step that runs `mutmut` on `lifecycle.py` and `locks.py` weekly; fail PR if kill score drops below 88% (current is 91%).
- **Why for Hamilton:** Prevents "added a test that doesn't actually assert anything" regressions. Hamilton already has mutmut at 91%; the gap is putting it in CI.
- **Effort:** 4 hours.
- **Tools:** **mutmut** (already used). Alternative: **Cosmic Ray** (more configurable, slower).
- **References:**
  - https://johal.in/mutation-testing-with-mutmut-python-for-code-reliability-2026/
- **Prereqs:** None.

### T3-10. WCAG 2.2 AA full audit

- **What:** Run a full WCAG 2.2 AA audit (manual + axe-core) against the asset board and member-facing pages. Fix all serious/critical findings. Update the public Accessibility statement (T1-7) with the audit date.
- **Why for Hamilton:** AODA legal floor. ADA exposure for US venues (DC, Philadelphia, Dallas).
- **Effort:** 1 week.
- **Tools:** **axe DevTools** + manual NVDA + VoiceOver. Optional: pay an IAAP-certified auditor (~$3-5k) for a third-party report.
- **References:**
  - https://www.w3.org/WAI/standards-guidelines/wcag/
  - https://www.deque.com/canada-compliance/aoda/
- **Prereqs:** T1-7.

## Tier 4 — Aspirational

Things mature ops have. A 1-developer 6-venue rollout can reasonably defer until headcount grows or a customer demands them.

### T4-1. SOC 2 Type 1 / Type 2

- **What:** Engage Drata, Vanta, or Comp AI; run 8–12 weeks of evidence collection; pass Type 1 audit ($10–25k); follow with Type 2 over 6–12 months ($25–50k).
- **Why for Hamilton:** Only worthwhile if/when an enterprise customer (hotel chain partnership, $100k+ ACV) demands it. Don't pre-pay.
- **Effort:** Months + $35–75k.
- **Tools:** **Comp AI** (cheapest), **Vanta** (most polished), **Drata** (deepest integration catalog).
- **References:**
  - https://trycomp.ai/soc-2-checklist-for-saas-startups
  - https://promise.legal/guides/soc2-roadmap
- **Prereqs:** Enterprise customer asks.

### T4-2. ISO 27001

- **What:** Same shape as SOC 2 but international.
- **Why:** Only if EU enterprise customer demands.

### T4-3. Chaos engineering

- **What:** Quarterly drills: deliberately kill Redis on staging, kill MariaDB replica, partition network. Document recovery time.
- **Why for Hamilton:** Useful at multi-region scale or when you have replicas. With single Frappe Cloud site, the kill-Redis test is the only one that returns signal.
- **Effort:** Half-day per quarter.
- **Tools:** Manual `kill -9` is fine. Skip **Litmus** / **Chaos Mesh** (Kubernetes-only, not your stack).
- **Prereqs:** Multi-region or replica setup.

### T4-4. Kubernetes / multi-region active-active

- **What:** None of your business until ~50 venues.
- **Why for Hamilton:** Frappe Cloud handles infra. Don't build a SRE team to support 6 retail locations.

### T4-5. Code escrow

- **What:** Third party holds source so customers can recover if you vanish.
- **Why for Hamilton:** Useless when you ARE the customer (you own the venues). Reconsider only if you license the software to other venue groups.
- **References:**
  - https://www.escode.com/iron-mountain-software-escrow/

### T4-6. Per-venue private secrets vault (Infisical / Doppler)

- **What:** Self-host Infisical or pay for Doppler; rotate keys every 30–90 days automatically.
- **Why for Hamilton:** Useful at 6 venues with shared staff but different Stripe accounts. Frappe Cloud's site config is sufficient until then.
- **Effort:** 3 days.
- **Tools:** **Infisical** (free self-host) or **Doppler** ($7/user/mo, zero-ops).
- **References:**
  - https://infisical.com/
  - https://www.doppler.com/

### T4-7. OpenTofu / Pulumi for non-Frappe infra

- **What:** Manage DNS, Cloudflare rules, S3 buckets, monitoring config as code.
- **Why for Hamilton:** Useful only when your non-Frappe surface area grows (>3 cloud services with custom config). At your scale, you have ~3 things, all manageable in their UIs.
- **Tools:** **OpenTofu** (Linux Foundation Terraform fork). **Pulumi** (Python/TS, more flexible).

### T4-8. Bug bounty / disclosure program

- **What:** Public `security.txt` on the domain; HackerOne / Bugcrowd page.
- **Why for Hamilton:** Real risk of being spammed by low-quality reports. Wait until you have a meaningful customer base or have been pen-tested first.

### T4-9. Mobile app

- **What:** Native iOS/Android.
- **Why for Hamilton:** Out of scope until staff workflows demand it (e.g. operators wanting offline-capable check-in). Your asset board on a tablet browser is fine for years.

### T4-10. AI agent for venue staff (RAG over docs + actions)

- **What:** A staff-facing chatbot that answers "how do I refund a session?" and can perform simple actions.
- **Why for Hamilton:** Genuinely interesting in 2027+ once Anthropic Computer Use / Claude Agents stabilize. Today the failure modes (hallucination, action mistakes) are too expensive for cash-handling environments.

---

# Section 4 — Recommended Adoption Roadmap

Concrete week-by-week pacing for Tier 0 and Tier 1. Assumes ~10 hours/week available for production-readiness work, on top of current Phase 1 task work.

## Pre-launch (Weeks -4 to 0 before Task 25)

| Week | Focus | Deliverables |
|---|---|---|
| **-4** | Privacy & policy | T0-1 (privacy policy + ToS via iubenda); T0-5 (PCI scope statement + confirm Stripe Checkout) |
| **-3** | Backups & secrets | T0-2 (backup runbook + first test restore); T0-3 (gitleaks pre-commit + GitHub secret scanning) |
| **-2** | Observability | T0-4 (Sentry + Better Stack uptime + status page) |
| **-1** | Pre-flight | Verify all T0 items; rehearse rollback once; final 3-AI review |
| **0**  | Launch (Task 25) | Push to prod; all T0 boxes ticked |

## Post-launch (Weeks 1–4)

| Week | Focus | Deliverables |
|---|---|---|
| **1** | Incident response | T1-1 (runbooks/ + status page wired up); T1-2 (postmortem template) |
| **2** | Supply chain | T1-3 (Dependabot + pip-audit); T1-5 (pre-commit framework with ruff + bandit) |
| **3** | Security & docs | T1-4 (SECURITY.md + threat model); T1-8 (ADR/decisions log convergence) |
| **4** | Compliance hardening | T1-6 (data retention policy + scheduled anonymization); T1-7 (AODA statement + axe-core) |

## Months 2–6 (toward second venue, DC / Crew Club)

| Phase | Focus | Items |
|---|---|---|
| **Month 2** | Staging + flags | T2-1 (staging on Frappe Cloud); T2-2 (feature flags via DocType) |
| **Month 3** | Deploy hardening | T2-3 (smoke tests post-deploy); T2-4 (rollback automation) |
| **Month 4** | Observability v2 | T2-5 (structured JSON logs); T2-6 (slow-query log + pt-query-digest) |
| **Month 5** | Tooling polish | T2-7 (AGENTS.md); T2-8 (CodeRabbit); T2-9 (cost tracker) |
| **Month 6** | Bus-factor | T2-10 (continuity doc + 1Password emergency access) |

## Year 2 (Tier 3, opportunistic)

Pick what's relevant to the next venue:
- **Toronto / Ottawa** with shared staff: T3-1 (OTel + Grafana metrics)
- **Dallas** with key/barcode scanners: T3-7 (API versioning) for the scanner integrations
- **Philadelphia** if any partnership emerges: T3-2 (SBOM)
- Always: T3-9 (mutation testing in CI) and T3-10 (WCAG 2.2 AA audit)

---

# Section 5 — Things That DO NOT Apply To Hamilton ERP

Production shops do many things that would be **active waste** for a 1-developer 6-venue bathhouse rollout. Skipping these is not "technical debt" — it's correct sizing.

| Practice | Why skip |
|---|---|
| **Kubernetes / Docker Swarm** | Frappe Cloud abstracts containers. Adopting K8s would 10x your operational complexity for zero customer benefit. |
| **Multi-region active-active** | Your customers are physically standing in your venues. There is no "Toronto user routes to Dallas data center" scenario. |
| **Microservices** | One Frappe monolith is correct for an ERP. Splitting into services adds latency, deployment surface, and bug classes. |
| **GraphQL or gRPC** | REST + Frappe whitelisted methods cover everything an internal ERP needs. GraphQL solves problems you don't have. |
| **Service Mesh (Istio, Linkerd)** | Same reason as K8s. |
| **Separate SRE team** | You have 1 developer. SRE is a function, not a person, at your scale. |
| **Code escrow** | You ARE the customer. Useless unless you license the software externally. |
| **SOC 2 / ISO 27001 pre-emptively** | Wait for a customer to demand it. ~$35–75k of evidence collection for "maybe" is bad ROI. |
| **Bug bounty program** | Will spam you with low-quality reports. Wait until you've passed an internal pen test. |
| **Chaos engineering with Litmus / Chaos Mesh** | K8s-only tools. Manual `kill -9 redis` is sufficient. |
| **Continuous Profiling in production (always-on Pyroscope)** | Hamilton's load is too small to warrant the data ingest. Sentry's "slow transaction" sampling is enough. |
| **Database read replicas** | Until cross-venue reporting becomes a real bottleneck (not before year 2), Frappe Cloud's single primary handles you fine. |
| **A/B testing infrastructure** | You have 1 customer (your own venues). A/B tests need user volume that doesn't exist. |
| **Pact / contract testing** | You have one service. Contract tests solve a 3+ service problem. |
| **GitFlow** | Largely retired for web/SaaS. GitHub Flow + squash-merge is correct. |
| **Reserved-capacity cloud purchases / FinOps tooling** | Frappe Cloud bills are not cloud bills. The Frappe Cloud billing dashboard is sufficient. |
| **Internal developer platform (Backstage)** | One-developer "platform" = your CLAUDE.md + slash commands + shell. Already done. |
| **Microsoft Threat Modeling Tool** | Free-form STRIDE in markdown is enough. |
| **HIPAA compliance** | A bathhouse is not a "covered entity" under HIPAA. PIPEDA + state laws cover this. Don't pretend HIPAA applies — it actually muddles the legal picture. |
| **Heavy ITIL / change management board** | You ARE the change management board. A 5-line PR template is the right level. |
| **Datadog / New Relic** | $50–500/mo APM is overkill before $10k+ MRR. Sentry + Better Stack + Grafana free covers you. |
| **Custom build system (Bazel, Pants)** | `pip install` + Frappe bench is the build system. Don't fight it. |

The unifying theme: **Frappe Cloud is opinionated and good at the things it does**. The mistake to avoid is treating it like AWS/GCP and reproducing the heavyweight tooling those clouds need. Trust Frappe Cloud for backups, deploys, container orchestration, secrets storage, basic monitoring; spend your scarce time on the things only you can do (privacy, business continuity, runbooks, AI workflows).

---

# Section 6 — Bathhouse Industry Specific

These practices matter more than usual because of the industry. They are NOT optional even though Section 5 is full of "skip this." None of these are scaled-down — they're as-stringent or more stringent than what most SaaS startups do.

## 6.1 Member privacy beyond regulatory minimum

Bathhouse member exposure has career- and life-altering consequences for victims. The legal floor (PIPEDA's "personal information") underprices the real harm. Standards to apply *above* the legal minimum:

- **Pseudonymous member records.** Use first name + DOB + photo for entry. Collect full legal name only when required for refund/dispute. The lower the surface area of identifying data, the smaller the breach impact.
- **Encrypted-at-rest member fields.** Frappe supports a `Password` field type with encryption — extend the pattern to legal name and date of birth. Store the encryption key in Frappe Cloud's site config (already separate from backups).
- **No member directory, ever.** No "find friends," no "who's here now," no leaderboards. The temptation to add social features must be refused at the architecture level.
- **No marketing email opt-out — opt-in only.** Double opt-in. One-click unsubscribe. CAN-SPAM and CASL both require this; bathhouse industry should over-comply.
- **Aggressive retention pruning.** 90 days for guest check-in records. 24 months inactive → anonymize Member record. **Never** hard-delete audit log entries (PIPEDA breach record retention).
- **Photo handling.** Entry photos for ID-match only, retention 30–90 days max, delete after dispute window.
- **Staff access logging.** Every read of a Member record by an operator generates an audit row visible to the member on request (PIPEDA right of access).
- **No third-party trackers on logged-in pages.** No Google Analytics, no Meta Pixel. Third-party trackers + bathhouse member identity is a litigation magnet.

## 6.2 Age verification (in-person)

US state-by-state age verification mandates are expanding rapidly (TX HB 1181 effective Jan 1 2026; PA SB 603 in committee; ~half of US states have or are passing similar laws). The conservative posture is **point-of-sale ID scan in every venue regardless of state** — sidesteps the online-content legal question entirely.

- **Hardware tier (recommended for 6 venues):** counter-mounted scanner (Patronscan, IDScan.net VeriScan, Minor Decliner) at $800–1500 per venue. Pays back in <1 year vs. phone-based subscriptions.
- **Critical setting:** the scanner must store **only the age verification result + scan timestamp**, NOT the full DL data. Most scanners default to keeping everything — this expands your PIPEDA scope dramatically. Verify this in vendor settings before deployment.
- **mDL support** (mobile driver's license in Apple/Google Wallet) is the 2026 differentiator — Ontario and ~14 US states issue these.
- Document the scanner's data flow in `docs/compliance/age_verification.md`.

## 6.3 PCI-DSS scope minimization

Already covered in T0-5 but bears repeating: **Stripe Checkout, never Elements**. Stripe Checkout keeps you in SAQ-A scope (~9 questions, no engineering). Elements requires a tiny CSP/integrity check. Anything that brings card data onto your server jumps you to SAQ-D (quarterly external scans, annual penetration test, ~$5–15k/yr). For a 6-venue rollout, staying SAQ-A is non-negotiable.

## 6.4 Quebec biometric prohibition (preemptive)

Quebec's CAI (Commission d'accès à l'information) under Law 25 has prohibited employer biometric door access **even with employee consent** when necessity and proportionality cannot be demonstrated. Required filing: 60 days advance notice to the CAI before deploying any biometric system. Hamilton ERP venues are not in Quebec, but case law in one province influences others; do not implement biometric auth or facial recognition for staff or members anywhere in the system without explicit lawyer sign-off.

## 6.5 PIPEDA breach playbook

Breach notification since November 2018: any breach with **"real risk of significant harm" (RROSH)** must be reported to the Office of the Privacy Commissioner (OPC) **and** affected individuals **as soon as feasible**. "Significant harm" explicitly includes "humiliation, damage to reputation or relationships." For bathhouse member data, the RROSH threshold is met by the mere fact of exposure, not just financial harm. Penalties up to $100,000 CAD per knowing violation.

The minimum playbook (`docs/compliance/breach_playbook.md`):

1. **Detect** (within 24h ideally — Sentry + Better Stack help here).
2. **Contain** (revoke compromised credentials, kill suspected exfil paths).
3. **Assess RROSH** (1-page checklist: data type, sensitivity, encryption status, who got it).
4. **Notify** OPC and individuals "as soon as feasible" (no fixed SLA but 72h is the practical floor).
5. **Document** in the breach log (24-month retention required, even for non-RROSH breaches).

## 6.6 Slip-and-fall / liability waiver software defenses

Ontario courts uphold liability waivers when (a) not gross negligence, (b) clear, (c) genuinely consented to. Electronic waivers are accepted in practice though not heavily litigated yet. Hamilton ERP can defend the venue by:

- Capturing waiver acceptance with timestamp + IP + scrolled-to-bottom flag.
- Audit-logging every entry/exit event with asset state.
- Storing CCTV-handoff metadata (start/end times, operator on shift) — enables venue's lawyer to subpoena targeted footage instead of pulling 24h of tape.

## 6.7 Bathhouse-specific data retention table

A starting point — review with counsel before locking in:

| Data | Retention | Rationale |
|---|---|---|
| Guest check-in record (full) | 90 days | Dispute window + minor refunds |
| Guest check-in record (anonymized) | 7 years | Tax / financial audit |
| Member record (active) | While active | Legitimate business interest |
| Member record (24 months inactive) | Anonymize | PIPEDA Principle 5 |
| Audit log (entry/exit, cash) | 24 months minimum | PIPEDA breach defense |
| Audit log (financial) | 7 years | CRA / IRS retention |
| Entry photos (ID-match) | 30–90 days | Delete after dispute window |
| Age-verification results | 24 months | Legal defense for under-age claims |
| CCTV footage handoff metadata | 24 months | Slip-and-fall defense |
| Marketing opt-in records | While subscribed + 24 months | CAN-SPAM/CASL evidence |

## 6.8 Regional summary

| Jurisdiction | Key law | What changes |
|---|---|---|
| **Ontario (Hamilton, Toronto, Ottawa)** | PIPEDA + AODA | Designated Privacy Officer; WCAG 2.0 AA accessibility statement; 24-month breach record retention |
| **Quebec** (none of your venues, but watch) | Law 25 | Biometric pre-auth filing; data localization considerations |
| **Texas (Dallas)** | TDPSA + HB 1181 | Age verification mandate effective Jan 1 2026; small-business exemption from most TDPSA but consent for sensitive data sale required |
| **Pennsylvania (Philadelphia)** | SB 603 (pending) | Age verification likely; monitor 2026 status |
| **Washington DC** | DC Security Breach Protection Amendment Act 2019 | Broad PII definition; treble damages or $1,500/violation + attorney's fees |
| **Washington state** (none of your venues, but watch) | MHMDA | Consumer health data inference from venue visits could trigger this if you ever serve WA users |

---

# Section 7 — Sources & Further Reading

Organized by category for deeper reading later. URLs verified during the research run on 2026-04-27.

### Source control & branching
- https://www.conventionalcommits.org/en/v1.0.0/
- https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development
- https://cloudcusp.com/blogs/git-workflow-how-to-choose-branching-strategy/
- https://oleksiipopov.com/blog/npm-release-automation/
- https://github.com/googleapis/release-please
- https://semver.org/

### CI/CD
- https://getdx.com/blog/dora-metrics/
- https://devdynamics.ai/blog/the-ultimate-guide-to-dora-software-metrics-what-they-are-and-why-they-matter
- https://octopus.com/devops/software-deployments/blue-green-vs-canary-deployments/
- https://docs.frappe.io/cloud/sites/migrate-an-existing-site
- https://docs.gitlab.com/ci/environments/deployment_safety/

### Testing
- https://hypothesis.readthedocs.io/
- https://johal.in/mutation-testing-with-mutmut-python-for-code-reliability-2026/
- https://www.vervali.com/blog/best-load-testing-tools-in-2026-definitive-guide-to-jmeter-gatling-k6-loadrunner-locust-blazemeter-neoload-artillery-and-more/
- https://crosscheck.cloud/blogs/best-accessibility-testing-tools-wcag
- https://docs.pytest.org/en/stable/how-to/mark.html

### Code quality
- https://docs.astral.sh/ruff/
- https://github.com/facebook/pyrefly
- https://blog.edward-li.com/tech/comparing-pyrefly-vs-ty/
- https://pre-commit.com/
- https://github.com/jendrikseipp/vulture
- https://pypi.org/project/radon/

### Dependency management
- https://docs.astral.sh/uv/
- https://blog.pullnotifier.com/blog/dependabot-vs-renovate-dependency-update-tools
- https://owasp.org/Top10/2025/
- https://github.com/pypa/pip-audit
- https://github.com/CycloneDX/cyclonedx-python

### Security
- https://owasp.org/Top10/2025/
- https://about.gitlab.com/blog/2025-owasp-top-10-whats-changed-and-why-it-matters/
- https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- https://github.com/gitleaks/gitleaks
- https://github.com/trufflesecurity/trufflehog
- https://www.zaproxy.org/
- https://semgrep.dev/
- https://github.com/PyCQA/bandit
- https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning
- https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository
- https://owasp.org/www-community/Threat_Modeling

### Secrets management
- https://infisical.com/
- https://www.doppler.com/
- https://12factor.net/config

### Observability
- https://opentelemetry.io/
- https://opentelemetry.io/docs/collector/
- https://docs.sentry.io/platforms/python/integrations/
- https://betterstack.com/
- https://grafana.com/products/cloud/
- https://www.thoughtworks.com/en-us/radar/techniques/observability-2-0
- https://sre.google/sre-book/service-level-objectives/

### Deployment
- https://docs.frappe.io/cloud/
- https://www.pulumi.com/docs/iac/comparisons/terraform/opentofu/
- https://opentofu.org/
- https://dora.dev/guides/dora-metrics-four-keys/

### Backup & DR
- https://docs.frappe.io/cloud/sites/backups
- https://www.veeam.com/blog/321-backup-rule.html
- https://www.datto.com/blog/3-2-1-1-0-backup-rule/
- https://www.backblaze.com/cloud-storage/object-lock
- https://www.cloudsafe.com/dr-testing-frequency/

### Incident response
- https://sre.google/sre-book/postmortem-culture/
- https://sre.google/sre-book/example-postmortem/
- https://www.atlassian.com/incident-management/handbook
- https://response.pagerduty.com/before/severity_levels/
- https://betterstack.com/community/comparisons/pagerduty-alternatives/
- https://www.openstatus.dev/guides/incident-severity-matrix

### Documentation
- https://diataxis.fr/
- https://adr.github.io/adr-templates/
- https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- https://martinfowler.com/bliki/ArchitectureDecisionRecord.html
- https://squidfunk.github.io/mkdocs-material/

### Performance
- https://web.dev/articles/vitals
- https://web.dev/blog/inp-cwv-launch
- https://github.com/benfred/py-spy
- https://github.com/plasma-umass/scalene
- https://docs.frappe.io/framework/user/en/profiling
- https://github.com/frappe/erpnext/wiki/ERPNext-Performance-Tuning
- https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html
- https://www.cloudflare.com/plans/free/

### Accessibility
- https://www.w3.org/WAI/standards-guidelines/wcag/
- https://www.w3.org/WAI/standards-guidelines/wcag/wcag3-intro/
- https://www.deque.com/canada-compliance/aoda/
- https://www.ontario.ca/page/completing-your-accessibility-compliance-report
- https://www.deque.com/axe/
- https://inclly.com/resources/axe-vs-lighthouse
- https://accessibility-test.org/blog/development/screen-readers/nvda-vs-jaws-vs-voiceover-2025-screen-reader-comparison/

### Compliance & legal
- https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda_brief/
- https://www.priv.gc.ca/en/privacy-topics/business-privacy/breaches-and-safeguards/privacy-breaches-at-your-business/gd_pb_201810/
- https://laws-lois.justice.gc.ca/eng/acts/p-8.6/
- https://www.fasken.com/en/knowledge/2022/05/now-you-see-me-new-requirements-for-electronic-monitoring-in-ontario-workplaces
- https://www.osler.com/en/insights/updates/high-bar-for-biometric-data-processing/
- https://natlawreview.com/article/new-age-verification-reality-compliance-rapidly-expanding-state-regulatory
- https://avpassociation.com/us-state-age-verification-laws-for-adult-content/
- https://code.dccouncil.gov/us/dc/council/code/sections/28-3852
- https://strictlyzero.com/announcements/payments-announcements/pci-compliance-checklist-2026-the-merchants-guide-to-dss-4-0-1/
- https://www.pcisecuritystandards.org/
- https://blog.pcisecuritystandards.org/just-published-pci-dss-v4-0-1
- https://iapp.org/resources/article/washington-my-health-my-data-act-overview
- https://www.dwt.com/blogs/privacy--security-law-blog/2023/07/texas-data-privacy-and-security-act-overview
- https://www.iubenda.com/en/privacy-and-cookie-policy-generator/
- https://www.gluckstein.com/news-item/what-are-liability-waivers-and-are-they-valid-in-ontario
- https://canadianunderwriter.ca/news/industry/what-to-consider-when-using-electronic-waivers-of-liability/

### Bathhouse-industry-specific
- https://idscan.net/age-verification-software/
- https://minordecliner.com/pages/mobile-drivers-license-scanner
- https://www.patronscan.com
- https://axiom.co/blog/the-right-to-be-forgotten-vs-audit-trail-mandates

### Data engineering
- https://docs.frappe.io/framework/v15/user/en/database-migrations
- https://frappe.io/blog/erpnext-features/versioning-and-audit-trail
- https://docs.frappe.io/framework/user/en/audit-trail
- https://www.tim-wellhausen.de/papers/ExpandAndContract/ExpandAndContract.html
- https://usercentrics.com/knowledge-hub/gdpr-right-to-be-forgotten/
- https://medium.com/@aalam-info-solutions-llp/frappe-patching-a-guide-to-smooth-updates-and-data-migrations-f9fe2a2e9e37

### Feature flags
- https://www.cncf.io/projects/openfeature/
- https://www.getunleash.io/
- https://www.statsig.com/perspectives/feature-flag-debt-management
- https://launchdarkly.com/docs/guides/flags/technical-debt
- https://docs.devcycle.com/best-practices/tech-debt/
- https://www.growthbook.io/

### API design
- https://swagger.io/specification/
- https://www.speakeasy.com/api-design/versioning
- https://oauth.net/2.1/
- https://stytch.com/blog/oauth-2-1-vs-2-0/
- https://stripe.com/blog/idempotency
- https://docs.stripe.com/api/idempotent_requests
- https://brandur.org/idempotency-keys
- https://www.svix.com/resources/webhook-best-practices/retries/
- https://api7.ai/blog/token-bucket-vs-leaky-best-rate-limiting-algorithm

### Frontend
- https://web.dev/articles/defining-core-web-vitals-thresholds
- https://web.dev/baseline
- https://developer.chrome.com/docs/lighthouse
- https://github.com/GoogleChrome/lighthouse-ci
- https://www.frontendtools.tech/blog/modern-image-optimization-techniques-2025
- https://npmtrends.com/source-map-explorer-vs-webpack-bundle-analyzer
- https://blog.logrocket.com/signals-fix-error-boundaries/

### Database (MariaDB)
- https://endoflife.date/mariadb
- https://mariadb.com/docs/release-notes/community-server/12.2/12.2.2
- https://mariadb.com/docs/server/server-management/server-monitoring-logs/slow-query-log/slow-query-log-overview
- https://mariadb.com/docs/server/server-management/server-monitoring-logs/slow-query-log/explain-in-the-slow-query-log
- https://mariadb.com/resources/blog/reduced-operational-downtime-with-new-alter-table-features/
- https://mariadb.com/kb/en/backup-and-restore-overview/
- https://severalnines.com/blog/online-schema-change-mysql-mariadb-comparing-github-s-gh-ost-vs-pt-online-schema-change/
- https://docs.frappe.io/cloud/faq/mariadb-slow-queries-in-your-site
- https://docs.frappe.io/cloud/performance-tuning
- https://www.percona.com/doc/percona-toolkit/LATEST/pt-query-digest.html

### Team & process (solo-dev)
- https://www.ideaplan.io/compare/shape-up-vs-scrum
- https://www.curiouslab.io/blog/basecamp-shape-up-myths
- https://www.projectshelf.dev/blog/best-project-management-tools-solo-developers-2025
- https://builtbyme.io/blog/linear-alternatives-solo-founder-project-management
- https://calnewport.com/from-deep-tallies-to-deep-schedules-a-recent-change-to-my-deep-work-habits/
- https://fortelabs.com/blog/para/

### Cost monitoring / FinOps
- https://www.finops.org/framework/
- https://www.finops.org/insights/2025-finops-framework/
- https://aws.amazon.com/aws-cost-management/aws-cost-anomaly-detection/
- https://frappe.io/cloud/pricing
- https://docs.frappe.io/cloud/billing/billing-cycle
- https://developers.cloudflare.com/registrar/account-options/renew-domains/

### Legal & business continuity
- https://www.escode.com/iron-mountain-software-escrow/
- https://trycomp.ai/soc-2-checklist-for-saas-startups
- https://promise.legal/guides/soc2-roadmap
- https://stripe.com/legal/dpa
- https://www.techminers.com/knowledge/bus-factor-in-technical-departments
- https://swimm.io/learn/developer-experience/what-is-the-bus-factor-why-it-matters-and-how-to-increase-it
- https://www.index.dev/blog/freelance-software-developer-contract-template
- https://support.1password.com/emergency-kit/

### AI development practices
- https://thepromptshelf.dev/blog/cursorrules-vs-claude-md/
- https://www.augmentcode.com/guides/how-to-build-agents-md
- https://contextarch.ai/blog/agents-md-vs-claude-md-confusion-2026
- https://hamel.dev/notes/llm/evals/inspect.html
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- https://www.greptile.com/benchmarks
- https://www.coderabbit.ai/
- https://aicodereview.cc/tool/qodo/
- https://github.com/thedotmack/claude-mem/
- https://www.helicone.ai/blog/prompt-evaluation-frameworks
- https://en.wikipedia.org/wiki/Vibe_coding
- https://visualstudiomagazine.com/articles/2025/04/25/vibe-coding-pioneer-advises-tight-leash-to-rein-in-ai-bs.aspx

---

## Final notes for Chris

**What surprised me during this audit:** Hamilton ERP is *significantly* ahead of the average single-developer Frappe project. The combination of 464 tests, 91% mutation kill, Hypothesis property-based testing, claude-mem, decisions_log.md (66+ entries), Subagent-Driven Development, and Phase 1 design discipline is a level of rigor most 10-person teams don't have. The gaps are not "you've been sloppy"; they are "production deploy adds new categories of risk that you haven't been touching yet because you weren't producing yet."

**The single highest-leverage gap:** **T0-1 (privacy policy) + T1-6 (data retention policy) + T0-2 (tested backups)**. These three together are the difference between "small business launching software" and "small business that gets sued the first time someone is outed by a leak." None of your 464 tests will help you if a regulator asks for the privacy policy and you don't have one.

**Recommended Monday action:** start with T0-2 (backup test restore) — it has zero external dependencies, takes a single afternoon, and gives you certainty about something you'd otherwise just hope works. Privacy policy (T0-1) requires a few hours of decisions about retention windows, so it's better to start that on a quieter morning.

**Categories where the 2026-current information was thinnest:**
- WCAG 3.0 status — confirmed Working Draft only (March 2026); not usable as compliance target.
- PCI-DSS 4.1 — confirmed does NOT exist; v4.0.1 is current.
- OpenFeature CNCF status — confirmed Incubating (not yet Graduated as of Q1 2026).
- Texas TDPSA / HB 1181 — confirmed Jan 1 2026 effective date but enforcement details are still emerging; revisit before Dallas opens.
- Specific PCI v4.0.1 wording for SAQ-A merchants on iframe pages (req 6.4.3 / 11.6.1) — confirmed but the practical interpretation for Frappe + Stripe Checkout is still being clarified by QSAs; lawyer review before Dallas.

**Disagreement with the original 24 categories:** none material. The categorization works. If anything, I would have folded category 22 (Cost Monitoring) into 9 (Deployment) for a 1-dev shop because at this scale they are the same conversation. I left them split because at year-3 they diverge. Nothing was missed; the 24 are the right shape.

**End of audit.**
