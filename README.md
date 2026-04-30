# Hamilton ERP

Custom Frappe v16 / ERPNext v16 app for Club Hamilton — a men's bathhouse in Hamilton, Ontario. Phase 1 covers the Asset Board, session lifecycle, three-layer locking, and blind cash control. Phase 2+ extends to multi-venue rollout (Philadelphia, DC, Dallas), POS-driven session creation, and retail catalogue.

![Tests](https://github.com/csrnicek/hamilton_erp/actions/workflows/tests.yml/badge.svg) ![Linter](https://github.com/csrnicek/hamilton_erp/actions/workflows/lint.yml/badge.svg)

> **Status:** Pre-1.0 (`hooks.py:app_version = "0.1.0"`), pre-Task-25 handoff. Active development. Not yet recommended for non-Hamilton deployments.

## What this app does

- **Asset Board** — tablet-optimized live grid of all 59 venue assets (26 rooms + 33 lockers) with state-aware actions (`/app/asset-board`).
- **Session lifecycle** — `Available → Occupied → Dirty → Available`, plus `Out of Service` from any state. Every transition is protected by a three-layer lock (Redis advisory + MariaDB `FOR UPDATE` + optimistic version field) per [DEC-019](docs/decisions_log.md).
- **Blind cash control** — operators drop cash without seeing expected totals or variance. Manager-only Cash Reconciliation reveals the math. Per [DEC-005](docs/decisions_log.md).
- **Anonymous walk-in flow** — Walk-in Customer DocType pre-seeded; sessions assigned without Sales Invoice. Phase 2 reintroduces SI-driven assignment for retail and membership flows.
- **V9.1 retail catalogue** — Item Group "Drink/Food" + 4 sample SKUs (water, sports drink, protein bar, energy bar) seeded into the asset board UI. Cart UX shipped as a stub in [PR #49](https://github.com/csrnicek/hamilton_erp/pull/49); full Sales Invoice creation pending in [PR #51](https://github.com/csrnicek/hamilton_erp/pull/51).

## Quick start

### Local bench (development)

```bash
git clone https://github.com/csrnicek/hamilton_erp.git ~/hamilton_erp
bash ~/hamilton_erp/scripts/init.sh
```

The init script verifies prerequisites (Python 3.14, Node 24, MariaDB, Redis), bootstraps a working bench at `~/frappe-bench-hamilton`, and creates a dev site (`hamilton-test.localhost`) and a test site (`hamilton-unit-test.localhost`). It does NOT install system packages — if a prereq is missing, the script tells you what to install.

### Frappe Cloud (production)

The live site at `hamilton-erp.v.frappe.cloud` auto-deploys from the `main` branch. Pushes to `main` trigger a Frappe Cloud deploy in ~3 minutes. Operational details: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Tests

```bash
cd ~/frappe-bench-hamilton && source env/bin/activate
bench --site hamilton-unit-test.localhost run-tests --app hamilton_erp
```

**Never run tests against the dev site** (`hamilton-test.localhost`) — they corrupt browser state. Use `hamilton-unit-test.localhost` exclusively. Detail: [docs/testing_guide.md](docs/testing_guide.md).

The test suite has a documented baseline of pre-existing failures (Payment Gateway DocType link issue + seed contamination canary). See `CLAUDE.md` "Common Issues" before reporting a "test failure" — it's likely the baseline.

## Documentation

| File | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project context, environment, workflow rules. **Required first read for any contributor.** |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution conventions, branch / commit / PR conventions, coding standards |
| [`SECURITY.md`](SECURITY.md) | Vulnerability disclosure policy |
| [`CHANGELOG.md`](CHANGELOG.md) | Chronological list of merged PRs |
| [`docs/decisions_log.md`](docs/decisions_log.md) | **LOCKED** design decisions (DEC-001 through DEC-061+) |
| [`docs/coding_standards.md`](docs/coding_standards.md) | Code conventions; especially §13 on locking discipline |
| [`docs/lessons_learned.md`](docs/lessons_learned.md) | Recurring-failure catalogue (LL-001 through LL-032+) |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Operational incident response, routine ops |
| [`docs/api_reference.md`](docs/api_reference.md) | Public API surface — 7 whitelisted endpoints |
| [`docs/permissions_matrix.md`](docs/permissions_matrix.md) | DocType-level role permissions, sensitive fields list |
| [`docs/testing_guide.md`](docs/testing_guide.md) | 4 levels of testing + which to run when |
| [`docs/build_phases.md`](docs/build_phases.md) | Phase 1 / 2 / 3 / 4 plan |

## Architecture at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser — Asset Board (vanilla JS class)                        │
│  /app/asset-board                                                │
└──────────┬──────────────────────────────────┬────────────────────┘
           │                                  │
           │ frappe.call(method=...)          │ frappe.realtime.on(...)
           │                                  │
┌──────────┴────────────────────┐  ┌──────────┴────────────────────┐
│  hamilton_erp.api             │  │  hamilton_erp.realtime        │
│  (7 whitelisted endpoints)    │  │  (site-wide broadcast)        │
└──────────┬────────────────────┘  └────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  hamilton_erp.lifecycle (state-machine helpers)                  │
│  • start_session_for_asset, vacate_session, mark_asset_clean,    │
│    set_asset_out_of_service, return_asset_to_service             │
└──────────┬───────────────────────────────────────────────────────┘
           │
           │ all transitions go through:
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  hamilton_erp.locks (three-layer lock helper)                    │
│  • Redis advisory lock (15s TTL)                                 │
│  • MariaDB SELECT … FOR UPDATE                                   │
│  • Optimistic version field check                                │
└──────────┬───────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Frappe DocTypes:                                                │
│  Venue Asset · Venue Session · Asset Status Log · Shift Record · │
│  Cash Drop · Cash Reconciliation · Comp Admission Log ·          │
│  Hamilton Settings (singleton) · Hamilton Board Correction       │
└──────────────────────────────────────────────────────────────────┘
```

Detail: [`docs/api_reference.md`](docs/api_reference.md), [`docs/decisions_log.md`](docs/decisions_log.md), [`docs/coding_standards.md`](docs/coding_standards.md) §13.

## Project conventions in 30 seconds

- **Tabs, not spaces.** Matches Frappe formatter.
- **One PR per change.** Even single-line fixes. The PR is the unit of review and the unit of revert.
- **Tests are self-contained.** Don't rely on global seed surviving between tests.
- **Never `frappe.db.commit()` in controllers.** Let the framework manage transaction boundaries.
- **Zero I/O inside lock body.** Realtime broadcasts fire `after_commit=True`, never inside the lock. ([DEC-019](docs/decisions_log.md), [`coding_standards.md` §13](docs/coding_standards.md))
- **Idempotent seeds.** Use `frappe.db.exists()` guards before any insert in install/seed/migration code.

Full detail: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Reporting

- **Bugs:** [GitHub issues](https://github.com/csrnicek/hamilton_erp/issues)
- **Security vulnerabilities:** [`SECURITY.md`](SECURITY.md) — email csrnicek@yahoo.com, **never** open a public issue
- **Operational incidents on Hamilton's live site:** [`docs/RUNBOOK.md`](docs/RUNBOOK.md) §10

## License

[MIT](LICENSE). Contributions accepted under the same license.

---

*Hamilton ERP is a single-developer project today, built primarily through AI-assisted pair programming with Claude Code. It is not yet a general-purpose Frappe app — Phase 2 multi-venue refactor is the milestone where it becomes broadly portable.*
