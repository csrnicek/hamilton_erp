# Hamilton ERP — Phase 1 Design: Asset Board and Session Lifecycle

**Date:** 2026-04-10
**Status:** Draft — awaiting review
**Phase:** 1 (builds on Phase 0, which is complete and live on hamilton-erp.v.frappe.cloud)
**Target branch:** `main` (single-developer project, no feature branch yet)
**Test environment:** local Frappe v16 bench at `~/frappe-bench` (setup in progress — paused pending `.zshrc` approval)

---

## 1. Goal

By the end of Phase 1:

1. Operators see all 59 Hamilton assets on a tablet-optimized Asset Board (Rooms on top, grouped by tier; Lockers below).
2. Tapping any tile opens a state-aware popover whose actions match the tile's current status. All five status transitions work end-to-end.
3. Venue Sessions are created and completed through a full manual flow ("Assign Occupant" on Available tiles, "Vacate" on Occupied tiles) without any POS involvement — POS integration is Phase 2.
4. Every status change is protected by the three-layer lock (Redis advisory + MariaDB `FOR UPDATE` + `version` field) per DEC-019.
5. Every status change creates an `Asset Status Log` entry automatically via a controller hook.
6. The Asset Board stays in sync across multiple tabs via a site-wide realtime broadcast (DEC-055 / Q8).
7. Overtime is indicated on Occupied tiles via a two-stage visual (warning during the grace window, red overtime after) driven entirely client-side by one 30-second interval.
8. "Mark All Dirty Rooms Clean" and "Mark All Dirty Lockers Clean" bulk actions work per DEC-054, with list-style confirmation and per-asset locking.
9. A single seed migration patch creates 59 Venue Assets, a Walk-in Customer, and the Hamilton Settings singleton on any fresh install (DEC-055).
10. QA tests H10 (Vacate and Turnover), H11 (Out of Service), and H12 (Occupied Asset Rejection) all pass on the local bench and on Frappe Cloud.

---

## 2. Scope

### 2.1 In scope

| # | Deliverable | Notes |
|---|---|---|
| 1 | Venue Asset controller — real implementations of `assign_to_session`, `mark_vacant`, `mark_clean`, `set_out_of_service`, `return_to_service` | Replaces the "not yet implemented" stubs in `venue_asset.py` from Phase 0 |
| 2 | Three-layer lock helper (`lock_for_status_change`) as a context manager on Venue Asset | Redis advisory lock + MariaDB `FOR UPDATE` + version field check |
| 3 | Asset Status Log auto-creation on every successful transition | Inside the lock section — no I/O |
| 4 | `last_vacated_at` / `last_cleaned_at` auto-set per DEC-031 | Set in the appropriate transition path, inside the lock |
| 5 | Venue Session controller — `before_insert` sets `session_number` via Redis INCR (Q9) | 48h TTL on Redis key, DB-fallback reconciliation |
| 6 | Venue Session — system-owned fields marked `read_only: 1` per DEC-055 §2 | `sales_invoice`, `admission_item`, `operator_checkin`, `shift_record`, `pricing_rule_applied`, `under_25_applied`, `comp_flag` |
| 7 | Shared API module `hamilton_erp/api.py` — `get_asset_board_data`, `mark_all_clean_rooms`, `mark_all_clean_lockers` | Whitelisted, role-checked, POST-only for state changers |
| 8 | Asset Board custom page at `/app/asset-board` (Frappe Page) | Vanilla JS class `hamilton_erp.AssetBoard`, no framework |
| 9 | Tile rendering — card layout, color-coded, tier labels, overtime overlay | Scoped CSS in `public/css/asset_board.css` |
| 10 | Popover interaction (tap-to-act) with inline expansion for OOS reason | See §5.6 |
| 11 | Realtime events `hamilton_asset_status_changed` and `hamilton_asset_board_refresh` | Site-wide broadcast, `after_commit=True`, fired outside the lock |
| 12 | Seed migration patch `hamilton_erp/patches/v0_1/seed_hamilton_env.py` | Creates 59 assets + Walk-in Customer + Hamilton Settings. Idempotent. |
| 13 | Unit and integration tests | `IntegrationTestCase` against the local bench for controller/lock behaviour; JS manual QA for board interaction |
| 14 | Updates to `current_state.md` reflecting Phase 1 completion | Push after each milestone |

### 2.2 Explicitly out of scope (deferred to later phases)

- POS integration (Sales Invoice hook that triggers session creation) → Phase 2
- Admission items, pricing rules, comp prompt → Phase 2
- Refund / POS Return handling (DEC-051) → Phase 4
- Cash drop, shift start/close, manager reconciliation → Phase 3
- Paid-but-unassigned cleanup job (DEC-020) — Phase 1 creates sessions with `assignment_status = Assigned` directly, so there is nothing for the cleanup job to clean. The `check_overtime_sessions` scheduler task stays as a no-op stub through Phase 1.
- Label printing (Phase 3) and PDF print formats (wkhtmltopdf/WeasyPrint decision deferred to Phase 3)
- Manual rename reconciliation (if a manager renames an asset via the Frappe form while the board is open, clients show the old name until they manually refresh — flagged but not fixed in Phase 1)

---

## 3. Prerequisites and dependencies

| Prereq | State | Gating? |
|---|---|---|
| Phase 0 DocTypes, roles, fixtures, workspace | ✅ Complete and live | No |
| Workspace permission fix (DEC-055 §4) | ✅ Committed c101a41, pushed | No |
| FOR UPDATE / FOR NO KEY UPDATE doc correction | ✅ Committed 11a4d5f, pushed | No |
| DEC-054 (Mark All Clean rules) | ✅ Committed 5362aa7, pushed | No |
| DEC-055 (4 scope additions) | ✅ Committed c101a41, pushed | No |
| Local Frappe v16 bench at `~/frappe-bench` | 🟡 In progress — brew packages installed, services not started, `.zshrc` not yet edited | **Yes — blocks TDD** |
| `hamilton-test.localhost` site on local bench | ❌ Not yet created | **Yes — blocks integration tests** |
| `hamilton_erp` installed on local bench from `/Users/chrissrnicek/hamilton_erp` | ❌ Not yet | **Yes — blocks integration tests** |
| MariaDB 12.2.2 compatibility with Frappe v16 | ❓ Unknown | Possible issue at `bench new-site` — fallback is `mariadb@11.4` |
| Node 20 LTS via nvm | ❌ nvm installed, Node 20 not yet selected | **Yes — blocks `yarn build`** |
| Python 3.11 via pyenv | ❌ pyenv installed, 3.11.9 not yet built | **Yes — blocks `bench init`** |

The bench setup is a discrete pre-Phase-1 workstream. It must complete before any Phase 1 code is written (TDD requires a working test harness). The remaining bench steps are documented at the end of this doc (§9) so they can be executed as a separate mini-plan.

---

## 4. Architectural approaches considered

Three shapes were weighed for how state transitions and session lifecycle divide between controllers.

### 4.1 Approach A — Asset-centric (recommended)

Venue Asset holds the whitelisted methods as thin entry points (they already exist as Phase 0 stubs). Each whitelisted method delegates to a private helper inside a new module `hamilton_erp/lifecycle.py` that implements the lock-and-transition core. Venue Session is a passive linked record — its controller does nothing more than compute `session_number` and validate `session_end > session_start`.

- **+** Asset is the locked entity. Putting the locking authority on the asset is the natural home.
- **+** Zero refactoring of Phase 0 — the stubs on Venue Asset get real bodies.
- **+** Phase 2 can import helpers from `lifecycle.py` directly in its Sales Invoice `on_submit` hook; no REST round-trip to the whitelisted method.
- **+** DEC-019 and coding-standards §13 are written entirely around Venue Asset locking, so the locking code has a single home.
- **−** Venue Asset controller grows (still small — ~300 lines).

### 4.2 Approach B — Session-centric

Venue Session holds the whitelisted methods (`session.start(asset)`, `session.vacate(method)`). Status changes on Venue Asset are side effects of session lifecycle events. Locking happens indirectly: the session controller acquires the Redis lock on the asset before mutating either.

- **+** Session lifecycle semantically belongs to the session.
- **+** Phase 2's Sales Invoice hook feels natural (`session.start(asset=...)` after payment).
- **−** The locking protocol lives on Session but the locked entity is Asset. That's an awkward split — the lock helper has to know about both DocTypes.
- **−** Requires refactoring the Phase 0 stubs on Venue Asset (they'd become delegations to the session).
- **−** Status-only changes without a session (Set Out of Service on an Available asset, Mark Clean on a Dirty asset with no session) have no session to route through — you end up with a second lifecycle module on Venue Asset anyway.

### 4.3 Approach C — Service layer

Neither controller holds the whitelisted methods. A service module `hamilton_erp/services/session_lifecycle.py` orchestrates all state transitions and session creation. Controllers handle only their own validation.

- **+** Cleanest separation of concerns for the long term.
- **+** Makes Phase 2/3/4 easiest to layer on.
- **−** Most boilerplate now. Two tiny controllers + a service module + a whitelisted dispatch module.
- **−** YAGNI — Phase 1's requirements are narrow enough that this level of structure is speculative.

### 4.4 Recommendation — A, with a path to C in Phase 2

Use Approach A for Phase 1. The whitelisted methods stay on Venue Asset (matching Phase 0 stubs and DEC-019), but their bodies delegate to `hamilton_erp/lifecycle.py`. In Phase 2, when the Sales Invoice `on_submit` hook needs to start a session, it imports `lifecycle.start_session_for_asset()` directly. If Phase 2 or Phase 3 makes the lifecycle module's surface area big enough to justify its own namespace, we split it into `services/` at that point. This keeps Phase 1 YAGNI-clean while making Phase 2 painless.

---

## 5. Architecture

### 5.1 Module layout

```
hamilton_erp/
├── api.py                              # ← updated: whitelisted entry points
├── lifecycle.py                        # ← NEW: state transition + session lifecycle core
├── locks.py                            # ← NEW: three-layer lock context manager
├── realtime.py                         # ← NEW: thin wrappers around publish_realtime
├── hooks.py                            # unchanged from Phase 0
├── hamilton_erp/
│   ├── doctype/
│   │   ├── venue_asset/
│   │   │   ├── venue_asset.py          # ← updated: stubs become delegations
│   │   │   ├── venue_asset.json        # unchanged
│   │   │   └── test_venue_asset.py     # ← updated: real integration tests
│   │   ├── venue_session/
│   │   │   ├── venue_session.py        # ← updated: before_insert for session_number
│   │   │   ├── venue_session.json      # ← updated: read_only=1 on 7 fields (DEC-055 §2)
│   │   │   └── test_venue_session.py   # ← updated
│   │   └── asset_status_log/
│   │       ├── asset_status_log.py     # unchanged
│   │       └── asset_status_log.json   # unchanged
│   └── page/
│       └── asset_board/                # ← NEW directory
│           ├── __init__.py
│           ├── asset_board.json        # Frappe page metadata
│           ├── asset_board.py          # page controller (minimal)
│           └── asset_board.js          # hamilton_erp.AssetBoard class
├── public/
│   └── css/
│       └── asset_board.css             # ← NEW: scoped tile + popover styles
├── patches/
│   ├── __init__.py
│   └── v0_1/
│       ├── __init__.py
│       └── seed_hamilton_env.py        # ← NEW: assets + customer + settings
└── patches.txt                         # ← updated: add the seed patch
```

### 5.2 Three-layer lock — `hamilton_erp/locks.py`

A single context manager encapsulates all three layers. It is the only place that knows about `FOR UPDATE`, Redis, or the version field. Controllers and lifecycle helpers use it with a plain `with` statement.

Signature:

```python
@contextmanager
def asset_status_lock(asset_name: str, operation: str) -> Iterator[dict]:
    """Acquire the three-layer lock for a status-changing operation on a Venue Asset.

    Yields a dict {"name", "status", "version"} read under the MariaDB row lock.
    The caller must:
      - validate the transition against the yielded status
      - update the asset document and bump version
      - create the Asset Status Log entry
      - perform zero I/O (no print, no enqueue, no publish_realtime)
    All side effects with I/O (realtime, label print) must happen AFTER the with-block exits.
    """
```

Implementation outline (inside the contextmanager):

1. **Redis layer.** `key = f"hamilton:asset_lock:{asset_name}:{operation}"`. Generate a UUID4 token. `cache.set(key, token, nx=True, px=15000)`. If that returns falsy, raise `frappe.throw(_("Asset {0} is being processed by another operator…"))`.
2. **MariaDB layer.** `frappe.db.sql("SELECT name, status, version FROM \`tabVenue Asset\` WHERE name = %s FOR UPDATE", asset_name, as_dict=True)`. This is the correct MariaDB syntax per the 2026-04-10 docs correction. Yields the row dict to the caller.
3. **Release.** Outside the try block: Lua script atomic release using the token (§13.2 of coding standards — copied verbatim, not parameterized).
4. **Version field check.** Caller (not the lock) compares the yielded version to the document's pre-save version; if they diverge, `frappe.throw(_("Concurrent update to {0} — please refresh and retry."))`. The version bump happens in the caller's save, making this a pure optimistic check inside the pessimistic section.

Why a context manager: every lifecycle function becomes `with asset_status_lock(...) as row:` + small body. No way to accidentally forget the release. No way to accidentally leak I/O into the lock section because the indented block is tiny.

### 5.3 Lifecycle module — `hamilton_erp/lifecycle.py`

Five public functions, one per state transition. Each has the same shape:

```python
def start_session_for_asset(asset_name: str, *, operator: str, customer: str = "Walk-in") -> str:
    """Assign Occupant flow: Available → Occupied + create Venue Session.

    Returns the session name.
    """
    with asset_status_lock(asset_name, "assign") as row:
        _require_transition(row, current="Available", target="Occupied", asset_name=asset_name)
        session_name = _create_session(asset_name, operator=operator, customer=customer)
        _set_asset_status(asset_name, "Occupied", session=session_name, log_reason=None, operator=operator, previous="Available")
    _publish_status_change(asset_name)
    return session_name


def vacate_session(asset_name: str, *, operator: str, vacate_method: str) -> None:
    """Vacate flow: Occupied → Dirty + close Venue Session."""
    assert vacate_method in ("Key Return", "Discovery on Rounds")
    with asset_status_lock(asset_name, "vacate") as row:
        _require_transition(row, current="Occupied", target="Dirty", asset_name=asset_name)
        session_name = _close_current_session(asset_name, operator=operator, vacate_method=vacate_method)
        _set_asset_status(asset_name, "Dirty", session=None, log_reason=None, operator=operator, previous="Occupied")
        _set_vacated_timestamp(asset_name)
    _publish_status_change(asset_name)


def mark_asset_clean(asset_name: str, *, operator: str, bulk_reason: str | None = None) -> None:
    """Dirty → Available. bulk_reason is set by the bulk Mark All Clean flow (DEC-054)."""
    with asset_status_lock(asset_name, "clean") as row:
        _require_transition(row, current="Dirty", target="Available", asset_name=asset_name)
        _set_asset_status(asset_name, "Available", session=None, log_reason=bulk_reason, operator=operator, previous="Dirty")
        _set_cleaned_timestamp(asset_name)
    _publish_status_change(asset_name)


def set_asset_out_of_service(asset_name: str, *, operator: str, reason: str) -> None:
    """Any state → Out of Service. Reason is mandatory."""
    if not reason or not reason.strip():
        frappe.throw(_("A reason is required to set an asset Out of Service."))
    with asset_status_lock(asset_name, "oos") as row:
        previous = row["status"]
        # OOS can come from any state except OOS itself — state machine permits this
        _require_oos_entry(row, asset_name=asset_name)
        if previous == "Occupied":
            _close_current_session(asset_name, operator=operator, vacate_method="Discovery on Rounds")
        _set_asset_status(asset_name, "Out of Service", session=None, log_reason=reason, operator=operator, previous=previous)
    _publish_status_change(asset_name)


def return_asset_to_service(asset_name: str, *, operator: str, reason: str) -> None:
    """Out of Service → Available. Reason is mandatory."""
    if not reason or not reason.strip():
        frappe.throw(_("A reason is required to return an asset to service."))
    with asset_status_lock(asset_name, "return") as row:
        _require_transition(row, current="Out of Service", target="Available", asset_name=asset_name)
        _set_asset_status(asset_name, "Available", session=None, log_reason=reason, operator=operator, previous="Out of Service")
        _set_cleaned_timestamp(asset_name)  # returning to service resets the "recently cleaned" clock
    _publish_status_change(asset_name)
```

**Private helpers** (same module, not whitelisted):

- `_require_transition(row, current, target, asset_name)` — throws if `row["status"] != current`
- `_require_oos_entry(row, asset_name)` — throws if `row["status"] == "Out of Service"` (can't OOS something already OOS)
- `_set_asset_status(asset_name, new_status, *, session, log_reason, operator, previous)` — loads the doc, writes `status`, `current_session`, `version += 1`, `hamilton_last_status_change = now`, saves with `ignore_permissions=False`, creates the Asset Status Log entry. All inside the lock. **Zero I/O.**
- `_set_vacated_timestamp(asset_name)` — bumps `last_vacated_at`
- `_set_cleaned_timestamp(asset_name)` — bumps `last_cleaned_at`
- `_create_session(asset_name, operator, customer)` — creates a Venue Session with `assignment_status="Assigned"`, `operator_checkin=operator`, `session_start=now`, `customer=customer`. `session_number` is assigned by the Venue Session controller's `before_insert` (§5.4).
- `_close_current_session(asset_name, operator, vacate_method)` — loads the asset's `current_session`, sets `session_end=now`, `operator_vacate=operator`, `vacate_method=...`, `status="Completed"`, saves. Returns the session name.
- `_publish_status_change(asset_name)` — **called outside the with-block**. Loads the asset's now-current state, builds the C2 payload (name, status, old_status, version, current_session, last_vacated_at, last_cleaned_at, hamilton_last_status_change), and calls `frappe.publish_realtime("hamilton_asset_status_changed", payload, after_commit=True)`.

### 5.4 Venue Session controller changes

- Add `before_insert` that computes `session_number` via Redis INCR (§5.9).
- Mark these fields `read_only: 1` in `venue_session.json` per DEC-055 §2:
  - `sales_invoice`
  - `admission_item`
  - `operator_checkin`
  - `shift_record`
  - `pricing_rule_applied`
  - `under_25_applied`
  - `comp_flag`
- Keep the existing `validate` logic (identity_method default, session_end > session_start check) untouched.
- No controller changes for `vacate_method` — it's set by `_close_current_session()` in the lifecycle module.

### 5.5 Session number generation — Redis INCR with DB fallback

Approved in Q9. Implemented in `VenueSession.before_insert()`:

```python
def before_insert(self):
    if not self.session_number:
        self.session_number = _next_session_number()


def _next_session_number() -> str:
    """Generate the next session number for today.

    Format: {d}-{m}-{y}---{NNN}, e.g. 9-4-2026---001.
    Resets at midnight (driven by key name, not key expiry).
    """
    from frappe.utils import nowdate
    year, month, day = nowdate().split("-")  # YYYY-MM-DD
    d, m, y = int(day), int(month), int(year)
    prefix = f"{d}-{m}-{y}"
    key = f"hamilton:session_seq:{prefix}"
    cache = frappe.cache()

    # First use of this day's key — reconcile with DB in case of Redis restart.
    if not cache.exists(key):
        db_max = _db_max_seq_for_prefix(prefix)
        # SET NX so we don't stomp a concurrent worker who already seeded the key.
        cache.set(key, db_max, nx=True, px=48 * 3600 * 1000)  # 48h TTL (Q9)

    seq = int(cache.incr(key))
    return f"{prefix}---{seq:03d}"


def _db_max_seq_for_prefix(prefix: str) -> int:
    """Parse the trailing digits after '---' from the max session_number matching today's prefix."""
    row = frappe.db.sql(
        """
        SELECT session_number FROM `tabVenue Session`
        WHERE session_number LIKE %s
        ORDER BY session_number DESC LIMIT 1
        """,
        (f"{prefix}---%",),
        as_dict=True,
    )
    if not row:
        return 0
    tail = row[0]["session_number"].rsplit("---", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return 0
```

Why `ORDER BY session_number DESC LIMIT 1` instead of `SELECT MAX`: string sort is lexicographic on "001" / "002" / ... which is correct as long as the sequence is zero-padded to 3 digits. `MAX(CAST(... AS UNSIGNED))` would work too but is messier.

### 5.6 Asset Board page

#### 5.6.1 Route and file layout

- Route: `/app/asset-board` (Frappe's standard route prefix for pages in v16)
- Files: `hamilton_erp/hamilton_erp/page/asset_board/asset_board.{json,py,js}` + `hamilton_erp/public/css/asset_board.css`
- `asset_board.py` is minimal — just `@frappe.whitelist()`-free, the page is loaded by the frontend and all data comes from `api.py` endpoints.
- `asset_board.json` specifies roles `["Hamilton Operator", "Hamilton Manager", "Hamilton Admin"]`.

#### 5.6.2 JS class structure — `hamilton_erp.AssetBoard`

```javascript
frappe.pages["asset-board"].on_page_load = (wrapper) => {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Asset Board"),
        single_column: true,
    });
    new hamilton_erp.AssetBoard(page);
};

hamilton_erp.AssetBoard = class AssetBoard {
    constructor(page) {
        this.page = page;
        this.wrapper = $(page.body);
        this.assets = [];           // full list from get_asset_board_data
        this.settings = {};         // grace_minutes etc
        this.overtime_interval = null;
        this.init();
    }

    async init() {
        await this.fetch_board();
        this.render();
        this.bind_events();
        this.start_overtime_ticker();
        this.listen_realtime();
        this.page.wrapper.on("page-destroyed", () => this.teardown());
    }

    async fetch_board() {
        const r = await frappe.call({
            method: "hamilton_erp.api.get_asset_board_data",
            freeze: true,
            freeze_message: __("Loading board..."),
        });
        this.assets = r.message.assets;
        this.settings = r.message.settings;
    }

    render() { /* build two zones, one per category */ }
    render_tile(asset) { /* card-shaped tile with status class, overtime class */ }
    bind_events() { /* delegated tap handler for tiles, bulk buttons */ }
    open_popover(asset) { /* state-dispatched popover per §5.6.4 */ }

    start_overtime_ticker() {
        this.overtime_interval = setInterval(() => this.refresh_overtime_overlays(), 30_000);
        this.refresh_overtime_overlays();
    }
    refresh_overtime_overlays() { /* loop occupied tiles, compare now vs session_start + stay + grace */ }

    listen_realtime() {
        frappe.realtime.on("hamilton_asset_status_changed", (d) => this.apply_status_change(d));
        frappe.realtime.on("hamilton_asset_board_refresh", () => this.fetch_board().then(() => this.render()));
    }

    apply_status_change(payload) {
        const local = this.assets.find(a => a.name === payload.name);
        if (!local) return;
        // Discard stale events: ignore if payload.version <= local.version
        if (payload.version <= (local.version || 0)) return;
        Object.assign(local, payload);
        this.render_tile_in_place(local);
    }

    teardown() {
        if (this.overtime_interval) clearInterval(this.overtime_interval);
        frappe.realtime.off("hamilton_asset_status_changed");
        frappe.realtime.off("hamilton_asset_board_refresh");
    }
};
```

#### 5.6.3 Layout (from Q2 + Q5)

- **Zone 1 — Rooms.** Horizontal flex-wrap of tiles, grouped by tier in this order per Q6: Single Standard (11) → Deluxe Single (10) → Glory Hole (2) → Double Deluxe (3). A small tier label sits above each tier sub-group.
- **Zone 2 — Lockers.** Horizontal flex-wrap of 33 tiles, no sub-grouping.
- **Header strip.** "Mark All Dirty Rooms Clean" and "Mark All Dirty Lockers Clean" buttons live above their respective zones. Each button is disabled unless at least one Dirty asset exists in its zone.
- **Tile dimensions.** Minimum 96×96 px (≥ Q2's 80×80 floor), 12 px padding, 8 px gutter. Status color fills the tile background (green=Available, amber=Dirty, dark grey=Occupied, red=Out of Service). `asset_code` small top-left, `asset_name` bold center, tier abbreviation small bottom-right.

#### 5.6.4 Popover interaction (from Q3)

Single popover component, dispatched by the tile's current status. Popover anchor = tapped tile, dismiss on outside-tap or after action completes. Info icon in popover header opens `/app/venue-asset/{name}` in a new tab (zero hot-path cost per Q3).

State dispatch:

| Tile state | Popover contents |
|---|---|
| Available | `[Assign Occupant]` (one tap → calls `start_session_for_asset`), `[Set Out of Service]` (expands to textarea + Confirm) |
| Occupied | `[Vacate — Key Return]`, `[Vacate — Discovery on Rounds]`, `[Set Out of Service]` (expands) |
| Dirty | `[Mark Clean]`, `[Set Out of Service]` (expands) |
| Out of Service | `[Return to Service]` (expands to textarea + Confirm) |

All action buttons in the popover show a freeze spinner while their frappe.call is in flight. On error, the popover stays open and shows an inline error banner with the server's message (so concurrency failures don't wipe the operator's input).

#### 5.6.5 Overtime overlay (from Q5)

Driven by a single 30-second `setInterval` that loops over occupied tiles. For each tile:

- `elapsed_minutes = (now - session_start) / 60`
- `stay = asset.expected_stay_duration`
- `grace = settings.grace_minutes`
- If `elapsed > stay + grace`: add `.hamilton-overtime` class (red pulsing border + "OT" badge)
- Else if `elapsed > stay`: add `.hamilton-warning` class (amber left border + clock icon)
- Else: no class

All swapped via `classList.toggle`. Interval is cleared in `teardown()`. Clock drift tolerated — we recompute on each tick, never cache a deadline.

### 5.7 API surface — `hamilton_erp/api.py`

Three new whitelisted functions (plus Phase 0's existing `on_sales_invoice_submit`):

```python
@frappe.whitelist()
def get_asset_board_data() -> dict:
    """Initial board load. Returns all assets + settings needed to render."""
    frappe.has_permission("Venue Asset", "read", throw=True)
    assets = frappe.get_all(
        "Venue Asset",
        fields=[
            "name", "asset_code", "asset_name", "asset_category", "asset_tier",
            "status", "current_session", "expected_stay_duration", "display_order",
            "last_vacated_at", "last_cleaned_at", "hamilton_last_status_change", "version",
        ],
        filters={"is_active": 1},
        order_by="display_order asc",
        limit_page_length=500,  # safety cap, far above 59
    )
    # Enrich Occupied tiles with session_start for overtime computation
    occupied = [a for a in assets if a["status"] == "Occupied" and a["current_session"]]
    if occupied:
        session_starts = {
            row["name"]: row["session_start"]
            for row in frappe.get_all(
                "Venue Session",
                fields=["name", "session_start"],
                filters={"name": ["in", [a["current_session"] for a in occupied]]},
            )
        }
        for a in occupied:
            a["session_start"] = session_starts.get(a["current_session"])
    settings = _get_hamilton_settings()
    return {"assets": assets, "settings": settings}


@frappe.whitelist(methods=["POST"])
def mark_all_clean_rooms() -> dict:
    frappe.has_permission("Venue Asset", "write", throw=True)
    return _mark_all_clean(category="Room")


@frappe.whitelist(methods=["POST"])
def mark_all_clean_lockers() -> dict:
    frappe.has_permission("Venue Asset", "write", throw=True)
    return _mark_all_clean(category="Locker")


def _mark_all_clean(category: str) -> dict:
    """Bulk Mark Clean loop (DEC-054 §4). Sorted by name per §13.4."""
    from hamilton_erp.lifecycle import mark_asset_clean
    dirty = frappe.get_all(
        "Venue Asset",
        filters={"status": "Dirty", "asset_category": category, "is_active": 1},
        fields=["name", "asset_code", "asset_name"],
        order_by="name asc",  # sorted for deadlock prevention
    )
    succeeded, failed = [], []
    reason = f"Bulk Mark Clean — {category} reset"
    for asset in dirty:
        try:
            mark_asset_clean(asset["name"], operator=frappe.session.user, bulk_reason=reason)
            succeeded.append(asset["asset_code"])
        except Exception as e:  # concurrency failure, etc.
            failed.append({"code": asset["asset_code"], "error": str(e)})
    # One board-refresh event after the whole batch, not one per asset
    frappe.publish_realtime(
        "hamilton_asset_board_refresh",
        {"triggered_by": "bulk_clean", "count": len(succeeded)},
        after_commit=True,
    )
    return {"succeeded": succeeded, "failed": failed}
```

The existing Venue Asset whitelisted methods (`assign_to_session`, `mark_vacant`, `mark_clean`, `set_out_of_service`, `return_to_service`) get real bodies that delegate to `lifecycle.py`. Each is `POST`-only (per coding-standards §2.2) and checks permission via `frappe.has_permission("Venue Asset", "write", throw=True)` before delegating.

### 5.8 Seed migration patch — `hamilton_erp/patches/v0_1/seed_hamilton_env.py`

One idempotent patch with three responsibilities (DEC-054 §1 + DEC-055 §1 + DEC-055 §3):

```python
import frappe
from frappe.utils import logger

def execute():
    _ensure_walkin_customer()
    _ensure_hamilton_settings()
    _ensure_venue_assets()


def _ensure_walkin_customer():
    if frappe.db.exists("Customer", "Walk-in"):
        return
    frappe.get_doc({
        "doctype": "Customer",
        "customer_name": "Walk-in",
        "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
        "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
    }).insert(ignore_permissions=True)


def _ensure_hamilton_settings():
    settings = frappe.get_single("Hamilton Settings")
    changed = False
    defaults = {
        "float_amount": 300,
        "default_stay_duration_minutes": 360,
        "grace_minutes": 15,
        "assignment_timeout_minutes": 15,
    }
    for field, value in defaults.items():
        if not settings.get(field):
            settings.set(field, value)
            changed = True
    if changed:
        settings.save(ignore_permissions=True)


def _ensure_venue_assets():
    if frappe.db.count("Venue Asset") > 0:
        return  # idempotent guard
    company = frappe.defaults.get_global_default("company")
    if not company:
        frappe.logger().warning(
            "seed_hamilton_env: no default company set — Venue Assets will be created with company=None"
        )

    # Order per Q6:
    # R001–R011 Single Standard, R012–R021 Deluxe Single,
    # R022–R023 Glory Hole, R024–R026 Double Deluxe, L001–L033 Lockers
    plan = (
        # (code_prefix, count, category, tier, name_prefix, code_start, display_start)
        ("R", 11, "Room", "Single Standard", "Sing STD",   1,  1),
        ("R", 10, "Room", "Deluxe Single",   "Sing DLX",  12, 12),
        ("R",  2, "Room", "Glory Hole",      "Glory",     22, 22),
        ("R",  3, "Room", "Double Deluxe",   "Dbl DLX",   24, 24),
        ("L", 33, "Locker", "Locker",        "Lckr",       1, 27),
    )
    for code_prefix, count, category, tier, name_prefix, code_start, display_start in plan:
        for i in range(count):
            asset_code = f"{code_prefix}{code_start + i:03d}"
            asset_name = f"{name_prefix} {i + 1}"
            frappe.get_doc({
                "doctype": "Venue Asset",
                "asset_code": asset_code,
                "asset_name": asset_name,
                "asset_category": category,
                "asset_tier": tier,
                "status": "Available",
                "is_active": 1,
                "expected_stay_duration": 360,
                "display_order": display_start + i,
                "company": company,  # None is acceptable per Q6 option (b)
                "version": 0,
            }).insert(ignore_permissions=True)
```

Add to `patches.txt` under `[post_model_sync]`:

```
hamilton_erp.patches.v0_1.seed_hamilton_env
```

### 5.9 Realtime events — `hamilton_erp/realtime.py`

Thin wrappers so the call sites are one-liners and the payload shape is consistent:

```python
def publish_status_change(asset_name: str, previous_status: str | None = None) -> None:
    row = frappe.db.get_value(
        "Venue Asset", asset_name,
        fieldname=[
            "name", "status", "version", "current_session",
            "last_vacated_at", "last_cleaned_at", "hamilton_last_status_change",
        ],
        as_dict=True,
    )
    if not row:
        return
    row["old_status"] = previous_status
    frappe.publish_realtime("hamilton_asset_status_changed", row, after_commit=True)


def publish_board_refresh(triggered_by: str, count: int) -> None:
    frappe.publish_realtime(
        "hamilton_asset_board_refresh",
        {"triggered_by": triggered_by, "count": count},
        after_commit=True,
    )
```

Both are called **outside** the lock section (§13.3). `after_commit=True` is mandatory on both (§7.3).

---

## 6. Data flows (worked examples)

### 6.1 Assign Occupant (Available → Occupied)

1. Operator taps Available tile `R007` (Sing STD 7).
2. Popover opens with `[Assign Occupant]` and `[Set Out of Service]`.
3. Operator taps `[Assign Occupant]`.
4. `frappe.call("hamilton_erp.api.assign_to_session", {asset_name: "VA-0007"})`.
5. API method checks permission, delegates to `lifecycle.start_session_for_asset("VA-0007", operator=frappe.session.user)`.
6. `asset_status_lock("VA-0007", "assign")` acquires Redis + MariaDB row lock.
7. `_require_transition(row, current="Available", target="Occupied", …)` — passes.
8. `_create_session("VA-0007", …)` inserts a Venue Session. `before_insert` computes `session_number` via Redis INCR (§5.5). Session saves with `assignment_status="Assigned"`, `operator_checkin=user`, `customer="Walk-in"`, `status="Active"`, `session_start=now`.
9. `_set_asset_status(...)` sets asset status to `Occupied`, bumps `version`, sets `current_session` to the new session name, sets `hamilton_last_status_change=now`, saves.
10. Asset Status Log row inserted with `previous_status="Available"`, `new_status="Occupied"`, `operator=user`, `venue_session=session`, `timestamp=now`, `reason=None`.
11. Lock releases (with-block exits, Lua release script verifies UUID token).
12. `_publish_status_change("VA-0007")` fires `hamilton_asset_status_changed` with full C2 payload.
13. Client receives event, checks `payload.version > local.version`, applies in place. Tile turns grey with occupant indicator. Overtime ticker picks it up on its next 30 s pass.

### 6.2 Vacate — Key Return (Occupied → Dirty)

1. Operator taps Occupied tile `R007`.
2. Popover opens with `[Vacate — Key Return]`, `[Vacate — Discovery on Rounds]`, `[Set Out of Service]`.
3. Operator taps `[Vacate — Key Return]`.
4. `frappe.call("hamilton_erp.api.mark_vacant", {asset_name: "VA-0007", vacate_method: "Key Return"})`.
5. API method delegates to `lifecycle.vacate_session("VA-0007", operator=user, vacate_method="Key Return")`.
6. Lock acquired. `_require_transition(row, current="Occupied", target="Dirty", …)` — passes.
7. `_close_current_session` loads the linked Venue Session, sets `session_end=now`, `operator_vacate=user`, `vacate_method="Key Return"`, `status="Completed"`, saves.
8. `_set_asset_status(..., "Dirty", session=None, ...)` — asset moves to Dirty, `current_session` cleared, version bumped.
9. `_set_vacated_timestamp(...)` — `last_vacated_at=now`.
10. Asset Status Log entry written with `previous_status="Occupied"`, `new_status="Dirty"`, `venue_session=closed_session_name`.
11. Lock releases.
12. Realtime event fired. Tile turns amber. Overtime overlay (if any) is removed because the tile is no longer Occupied.

### 6.3 Mark Clean (Dirty → Available, single)

Identical shape. `_set_cleaned_timestamp` runs instead of `_set_vacated_timestamp`. No session involvement. Log entry has `log_reason=None` (distinguishes from bulk cleans, per DEC-054 §5).

### 6.4 Mark All Dirty Rooms Clean (bulk)

1. Operator taps `[Mark All Dirty Rooms Clean]` button above the Rooms zone.
2. Client calls `get_asset_board_data` locally to grab the list of Dirty rooms (or filters from its cached state) and opens a confirmation dialog: *"Mark these 7 rooms clean?"* with the list of `{asset_code} {asset_name}` pairs.
3. Operator confirms.
4. `frappe.call("hamilton_erp.api.mark_all_clean_rooms")`.
5. Server fetches Dirty rooms sorted by name (§13.4 deadlock ordering), loops over them calling `lifecycle.mark_asset_clean(name, operator=user, bulk_reason="Bulk Mark Clean — Room reset")`.
6. Each call is a complete three-layer-lock + transition + log cycle. Failures (e.g. an asset was re-occupied between the confirmation and the loop) are caught and recorded; the loop continues.
7. After the loop, a single `hamilton_asset_board_refresh` event fires.
8. Clients refetch the board and re-render. Any failures are shown in a toast to the operator who initiated the bulk action.

### 6.5 Set Out of Service (any → OOS)

1. Operator taps tile (any state). Popover opens.
2. Operator taps `[Set Out of Service]`. Popover expands in place: textarea labeled "Reason" + `[Confirm]` button.
3. Operator types a reason, taps `[Confirm]`.
4. `frappe.call("hamilton_erp.api.set_out_of_service", {asset_name, reason})`.
5. `lifecycle.set_asset_out_of_service` acquires the lock.
6. If current state is Occupied, `_close_current_session(..., vacate_method="Discovery on Rounds")` is called so the linked session is properly closed. (OOS'ing an occupied room is a legitimate edge case — e.g. a plumbing failure discovered mid-stay.)
7. Status updated to `Out of Service`. The Asset Status Log entry's `reason` field captures the operator's input verbatim (enforced mandatory by the Asset Status Log controller already).
8. Lock releases. Realtime event fired. Tile turns red with reason visible in the detail drawer.

---

## 7. Error handling and concurrency failure UX

| Failure | Detection | User-facing message | Recovery |
|---|---|---|---|
| Redis lock contention | `cache.set nx=True` returns falsy | "Asset {name} is being processed by another operator. Refresh the board and try again." | Client calls `refreshAssetBoard()` automatically per §13.5. No auto-retry of the action. |
| Transition violation (e.g. Dirty→Occupied attempted) | `_require_transition` throws | "Cannot transition {name} from {current} to {target}." | Board auto-refreshes so the operator sees the true state. |
| Version mismatch | Rare — version field check | "Concurrent update to {name} — please refresh and retry." | Same as above. |
| OOS without reason | `lifecycle.set_asset_out_of_service` precheck | "A reason is required to set an asset Out of Service." | Popover stays open with the textarea for the operator to fill in. |
| Walk-in Customer missing during assign | ERPNext link validation error | "Walk-in customer not found. Ask your Admin to run the setup patch." | Ops escalation; shouldn't happen post-seed. |
| Redis down | All lock acquisitions fail | "Realtime system unavailable. Please check back in a moment." | Redis is a hard dependency; without it nothing works. Ops escalation. |
| Bulk Mark Clean partial failure | Per-asset try/except in the loop | Toast: "5 rooms cleaned. 2 failed — check log." | Successful assets already moved. Failed ones stay Dirty. Operator can re-run or handle individually. |

---

## 8. Testing strategy

### 8.1 Unit tests (pure Python, no bench needed)

- `_next_session_number()` — given a mock Redis and a mock DB, verifies format, padding, daily key behaviour
- `_db_max_seq_for_prefix()` — parses trailing digits correctly, returns 0 on empty, handles malformed strings
- State machine validator — every valid transition passes, every invalid combination throws
- Asset code plan generator — given the plan tuple, produces the expected 59 codes in the expected order

These run under `pytest` standalone if needed, or under `bench run-tests` as plain `TestCase` subclasses.

### 8.2 Integration tests (IntegrationTestCase, requires local bench)

- `test_assign_available_to_occupied` — happy path, asset moves, session created, log written, version bumped
- `test_assign_blocks_when_not_available` — tries to assign a Dirty asset, expects `ValidationError`
- `test_vacate_moves_to_dirty_and_closes_session` — verifies session_end, operator_vacate, vacate_method all set
- `test_mark_clean_sets_last_cleaned_at` — verifies the timestamp is set and session remains unlinked
- `test_bulk_mark_clean_only_rooms` — verifies the category filter, the sort-by-name ordering, the single refresh event
- `test_bulk_mark_clean_partial_failure` — pre-occupies one of the dirty assets mid-loop (via a second session or direct DB update), verifies the loop reports failure without aborting
- `test_set_oos_closes_occupied_session` — OOS on an Occupied asset still closes the session properly
- `test_oos_without_reason_throws` — expects `ValidationError`
- `test_session_number_resets_per_day` — mocks `nowdate()`, verifies sequence starts at 001 on a new day
- `test_realtime_event_fires_after_commit` — uses a mock `publish_realtime` capture to verify event name and payload keys
- `test_redis_lock_prevents_double_assign` — spawns a thread holding the lock, verifies a second acquisition throws within the TTL
- H10 end-to-end (Vacate and Turnover)
- H11 end-to-end (Out of Service)
- H12 end-to-end (Occupied Asset Rejection)

All integration tests run with:
```
bench --site hamilton-test.localhost run-tests --app hamilton_erp
```

### 8.3 Manual QA checklist

- Popover opens on tap, dismisses on outside tap
- OOS reason textarea expands inline, Confirm button enabled only with non-empty reason
- Bulk confirmation dialog lists assets correctly
- Overtime warning border appears at stay_duration (tested by temporarily setting `expected_stay_duration=1` minute on a test asset)
- Overtime red border replaces warning at stay + grace
- Two tabs side by side: changes in tab A appear in tab B within ~1 second via realtime
- Page leave / browser back cleanly removes realtime listeners (verified with Chrome DevTools → Network → WS → no dangling subscriptions)
- Role-gating: logging in as a user with no Hamilton role cannot access `/app/asset-board` (403)
- Workspace appears in the sidebar only for Hamilton-role users (DEC-055 §4 regression check)

### 8.4 TDD order

Per workflow: each deliverable has its test written first, seen red, then implementation, then seen green. Order:
1. Lock helper → 2. State machine transitions → 3. lifecycle.start_session → 4. lifecycle.vacate → 5. lifecycle.mark_clean → 6. lifecycle.oos/return → 7. session_number generator → 8. Asset Status Log integration → 9. seed patch → 10. api.py endpoints → 11. Asset Board page JS (manual QA) → 12. Realtime integration → 13. bulk Mark All Clean → 14. H10/H11/H12 E2E.

---

## 9. Implementation milestones

Phase 1 executed as nine atomic milestones. Each milestone ends with: tests green, current_state.md updated, commit pushed.

| # | Milestone | Scope |
|---|---|---|
| **M0** | **Local bench complete** (pre-Phase-1) | Steps 1–16 from Q7. Concludes with `bench run-tests` passing on an empty hamilton_erp. |
| M1 | Lock helper + state machine tests | `locks.py`, unit tests for state transitions, first integration test using a real site |
| M2 | lifecycle.py — assign + vacate + mark_clean | Plus asset status log auto-creation and timestamp writers |
| M3 | lifecycle.py — set_oos + return_to_service | Plus OOS-from-Occupied edge case (close session) |
| M4 | Venue Session before_insert (session_number) | Plus read-only field lockdown per DEC-055 §2 |
| M5 | Seed migration patch | 59 assets + Walk-in Customer + Hamilton Settings, idempotent |
| M6 | api.py endpoints | get_asset_board_data + real bodies for the 5 Venue Asset whitelisted methods + 2 bulk endpoints |
| M7 | Asset Board page (JS + CSS) | Tile rendering, popover, overtime ticker, bulk confirmation dialog |
| M8 | Realtime integration | publish wrappers + client listeners + listener cleanup |
| M9 | H10/H11/H12 E2E + polish | Final test pass, push to Frappe Cloud, run manual QA on real tablet hardware |

M0 blocks everything. M1 blocks all subsequent milestones. M2 and M3 can share a PR but should land as separate commits. M5 can land any time after M4. M7 needs M6. M8 needs M7. M9 closes the phase.

---

## 10. Acceptance criteria

Phase 1 is "done" when all of the following are true:

1. All tests in §8.1 and §8.2 pass on the local bench under `bench run-tests --app hamilton_erp`
2. QA test H10 (Vacate and Turnover), H11 (Out of Service), and H12 (Occupied Asset Rejection) pass end-to-end from the Asset Board UI on the local bench
3. The Asset Board page loads at `/app/asset-board` on hamilton-erp.v.frappe.cloud showing all 59 seeded assets in the correct layout
4. Two tabs viewing the same live board stay in sync within ~1 second on status changes
5. Overtime warning and overtime borders appear at the correct thresholds under a contrived short-duration test
6. Both bulk Mark All Clean buttons work with list-style confirmation, log entries carry the distinguishing reason string
7. `current_state.md` reflects Phase 1 completion status, pushed to GitHub
8. `MEMORY.md` project entry is updated to reflect that Phase 1 is complete

---

## 11. Open items to hand to the writing-plans skill

These are implementation-time details I'm deliberately not solving in this design doc — they'll be worked out inside the plan skill or during TDD:

1. Exact CSS hex values and shadow depths (visual design to taste — confirm during manual QA on real tablet)
2. Exact wording of error messages (current draft lives in §7 table, refine during implementation)
3. Whether `asset_code` immutability should be enforced in a `validate` check in addition to the form-level `read_only_depends_on` (recommendation: yes, belt-and-braces)
4. MariaDB 12.2.2 vs 11.4 fallback decision — resolve empirically in M0 when `bench new-site` is first run
5. Whether to install WeasyPrint now as a future-proof PDF engine or defer entirely to Phase 3 (current plan: defer)
6. The `check_overtime_sessions` scheduled task — currently a no-op stub. Phase 1 keeps it that way; Phase 3 decides whether to delete or repurpose.

---

## 12. Appendix — paused bench install state

Snapshot at 2026-04-10 so the pre-Phase-1 workstream can be resumed without re-surveying:

**Installed via brew:**
- Homebrew 5.1.5 (after `brew update`, which cleaned up stale homebrew/core tap state)
- pyenv 2.6.27 (with m4, autoconf, ca-certificates, pkgconf dependencies)
- nvm 0.40.4 (brew warning: upstream does not support brew-managed nvm; acceptable for local dev)
- mariadb 12.2.2 (may need fallback to 11.4 — verify at first `bench new-site`)
- redis 8.6.2

**Still to do:**
- `.zshrc` edits (pyenv + nvm shell init — approval pending)
- `mkdir ~/.nvm`
- `brew services start mariadb && brew services start redis`
- Verify `pyenv --version` and `nvm --version` respond in a fresh shell
- `pyenv install 3.11.9`
- `nvm install 20 && nvm alias default 20`
- `pip install frappe-bench` (under pyenv 3.11.9)
- `bench init ~/frappe-bench --frappe-branch version-16 --python $(pyenv which python)`
- `bench new-site hamilton-test.localhost`
- `bench get-app erpnext --branch version-16`
- `bench --site hamilton-test.localhost install-app erpnext`
- `bench get-app /Users/chrissrnicek/hamilton_erp`
- `bench --site hamilton-test.localhost install-app hamilton_erp`
- `bench --site hamilton-test.localhost set-config developer_mode 1`
- `bench start` smoke test
- `bench --site hamilton-test.localhost run-tests --app hamilton_erp` sanity check

**Skipped from original 16-step plan:**
- wkhtmltopdf install (Q7 follow-up — no PDFs in Phase 1, deferred to Phase 3)

---

*End of Phase 1 design doc.*
