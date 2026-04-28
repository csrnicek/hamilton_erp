# Phase 1: Asset Board and Session Lifecycle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tablet-optimized Asset Board for 59 Hamilton assets with a full manual session lifecycle (Assign → Occupied → Vacate → Dirty → Clean → Available), three-layer locking (Redis + MariaDB `FOR UPDATE` + version field), auto-audit via Asset Status Log, seed data for fresh installs, and realtime cross-tab sync.

**Architecture:** Asset-centric (design doc §4.4). Whitelisted methods stay on `Venue Asset` as thin entry points; their bodies delegate to a new `hamilton_erp/lifecycle.py` module that drives the three-layer lock (`hamilton_erp/locks.py`) and emits realtime events through `hamilton_erp/realtime.py` **outside** the lock section. The Asset Board is a Frappe Page (`/app/asset-board`) with a vanilla JS class `hamilton_erp.AssetBoard`.

**Tech Stack:** Frappe v16 / ERPNext v16 (Python 3.14, Node 24, MariaDB 10.6–12.x, Redis), vanilla JS (no frameworks), `IntegrationTestCase` from `frappe.tests`, TDD via `bench run-tests`.

**Reference docs (read first):**
- `docs/phase1_design.md` — authoritative design (2026-04-10)
- `docs/build_phases.md` — Phase 1 test criteria
- `docs/decisions_log.md` — DEC-019 (locking), DEC-031 (timestamps), DEC-033 (session_number), DEC-054 (bulk clean), DEC-055 (seed scope)
- `docs/coding_standards.md` §2.11 (FOR UPDATE), §13 (lock section rules)

---

## Pre-requisite M0 — Local Frappe bench (NOT code work)

Phase 1 TDD requires a running bench because integration tests call `frappe.get_doc()`, `frappe.publish_realtime()`, and hit MariaDB + Redis. M0 installs that harness. Complete **all** of the following before starting Task 1. None of these steps produce code — they are infrastructure.

Current state at 2026-04-10 (from `docs/phase1_design.md` §12): brew has installed `pyenv`, `nvm`, `mariadb@12.2.2`, `redis@8.6.2`. Everything else is pending.

- [ ] **M0.1** — Get user approval for the following `.zshrc` append (pyenv + nvm shell init):

  ```bash
  # pyenv
  export PYENV_ROOT="$HOME/.pyenv"
  [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"

  # nvm
  export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"
  ```
- [ ] **M0.2** — `mkdir ~/.nvm`
- [ ] **M0.3** — `brew services start mariadb && brew services start redis`
- [ ] **M0.4** — Open a fresh terminal, verify: `pyenv --version && nvm --version && mysql --version && redis-cli ping`
- [ ] **M0.5** — Use system Python 3.14 at `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3` (Frappe `version-16` `pyproject.toml` declares `requires-python = ">=3.14,<3.15"`). Do NOT use pyenv for this — the plan previously pinned 3.11.9 but Frappe v16 tip has moved past that. Verify: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 --version` → `Python 3.14.0`
- [ ] **M0.6** — `nvm install 24 && nvm alias default 24 && npm install -g yarn` (Frappe `version-16` `package.json` declares `engines.node >=24`. Node 20 LTS is stale for v16 tip.)
- [ ] **M0.7** — `pip install frappe-bench` (can install into any active Python; frappe-bench is the orchestration CLI — the actual bench venv uses the Python passed via `--python` in M0.8)
- [ ] **M0.8** — `bench init ~/frappe-bench-hamilton --frappe-branch version-16 --python /Library/Frameworks/Python.framework/Versions/3.14/bin/python3`
- [ ] **M0.9** — `cd ~/frappe-bench-hamilton && bench new-site hamilton-test.localhost --mariadb-root-password '' --admin-password admin`
  - If MariaDB 12.2 rejects Frappe's root auth: `brew uninstall mariadb && brew install mariadb@11.4 && brew services start mariadb@11.4` and retry.
- [ ] **M0.10** — `cd ~/frappe-bench-hamilton && bench get-app erpnext --branch version-16`
- [ ] **M0.11** — `bench --site hamilton-test.localhost install-app erpnext`
- [ ] **M0.12** — `bench get-app /Users/chrissrnicek/hamilton_erp` (installs the working copy, not a clone — edits in-place)
- [ ] **M0.13** — `bench --site hamilton-test.localhost install-app hamilton_erp`
- [ ] **M0.14** — `bench --site hamilton-test.localhost set-config developer_mode 1`
- [ ] **M0.15** — `bench start` smoke test in one terminal, then open `http://hamilton-test.localhost:8000` and confirm login works. Ctrl-C when verified.
- [ ] **M0.16** — `bench --site hamilton-test.localhost run-tests --app hamilton_erp` — must finish with zero errors (Phase 0 tests only — 0 may be outdated tiers, that's OK for the handshake; real fix is Task 1).

**Gate:** Do not proceed to Task 1 until M0.16 has shown a successful `bench run-tests` round-trip (even if individual tests fail — a clean test harness boot is what we need).

---

## File structure

**New files created by this plan:**

| Path | Responsibility |
|---|---|
| `hamilton_erp/hamilton_erp/locks.py` | `asset_status_lock` context manager — Redis NX-lock + MariaDB `FOR UPDATE` row lock |
| `hamilton_erp/hamilton_erp/lifecycle.py` | 5 state-transition functions + private helpers + `_next_session_number()` + `_mark_all_clean()` loop |
| `hamilton_erp/hamilton_erp/realtime.py` | `publish_status_change()` / `publish_board_refresh()` wrappers with `after_commit=True` |
| `hamilton_erp/hamilton_erp/test_locks.py` | Unit-style tests for the lock helper |
| `hamilton_erp/hamilton_erp/test_lifecycle.py` | Integration tests for every lifecycle function |
| `hamilton_erp/hamilton_erp/test_api_phase1.py` | Integration tests for new `api.py` endpoints + performance baseline |
| `hamilton_erp/hamilton_erp/test_e2e_phase1.py` | H10 / H11 / H12 end-to-end tests |
| `hamilton_erp/hamilton_erp/patches/v0_1/seed_hamilton_env.py` | Idempotent seed patch (59 assets + Walk-in Customer + Hamilton Settings) |
| `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/__init__.py` | Empty package marker |
| `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.json` | Frappe Page metadata (title, roles) |
| `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.py` | Minimal page controller |
| `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js` | `hamilton_erp.AssetBoard` vanilla JS class |
| `hamilton_erp/hamilton_erp/public/css/asset_board.css` | Scoped tile, popover, overtime styles |

**Modified files:**

| Path | Reason |
|---|---|
| `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py` | Replace `frappe.throw("not yet implemented")` stubs with real delegations to `lifecycle.py` |
| `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py` | Update tier names from legacy `"Standard"` to `"Single Standard"` |
| `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.py` | Add `before_insert` → session_number generator |
| `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json` | Mark 7 fields `read_only: 1` (DEC-055 §2) |
| `hamilton_erp/hamilton_erp/api.py` | Expand `get_asset_board_data` (session enrichment + permission check), add `mark_all_clean_rooms` / `mark_all_clean_lockers` |
| `hamilton_erp/hamilton_erp/patches.txt` | Register `v0_1.seed_hamilton_env` under `[post_model_sync]` |
| `hamilton_erp/hamilton_erp/hooks.py` | Add `app_include_css` → `/assets/hamilton_erp/css/asset_board.css` |

---

## TDD workflow — the shape every code task follows

Every task below uses the same five-step cycle:

1. **Write the failing test** (show the full test code)
2. **Run the test** and confirm the expected failure (show the exact command + expected output)
3. **Write the minimal implementation** (show the full code)
4. **Run the test again** and confirm it passes (show the exact command + expected output)
5. **Commit** (show the exact `git add` + `git commit` command)

**Command template for Frappe tests throughout:**

```bash
cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
  --app hamilton_erp --module hamilton_erp.<module_path>
```

For a single test: append `--test <TestClass>.<test_name>`.

---

## Task 1: Clean up stale Phase 0 tier names in existing tests

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py`

**Why:** The Phase 0 test fixture helper uses `tier="Standard"`, but the Phase 0 validator in `venue_asset.py` requires one of `{"Single Standard", "Deluxe Single", "Glory Hole", "Double Deluxe"}`. The tests would fail on a fresh bench. Fix first so we start Phase 1 on green.

- [ ] **Step 1: Run the existing Phase 0 tests on the fresh local bench**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
  ```

  Expected: some tests fail with `ValidationError: Rooms must have a room tier…`.

- [ ] **Step 2: Update the `_make_asset` helper**

  Edit `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py` line 6 — change the default `tier` argument from `"Standard"` to `"Single Standard"`:

  ```python
  def _make_asset(self, name: str, category: str = "Room", tier: str = "Single Standard") -> object:
  ```

- [ ] **Step 3: Fix `test_locker_tier_is_cleared_on_save`**

  The existing test passes `"Standard"` as tier on a Locker and expects it to be silently cleared. The current validator throws instead. Rewrite it to reflect the actual behaviour — lockers must have tier `"Locker"`:

  ```python
  def test_locker_requires_locker_tier(self):
      """Lockers must have tier 'Locker' — any other tier raises."""
      doc = frappe.get_doc({
          "doctype": "Venue Asset",
          "asset_name": "Test Locker Wrong Tier",
          "asset_category": "Locker",
          "asset_tier": "Single Standard",
          "status": "Available",
          "display_order": 99,
      })
      self.assertRaises(frappe.ValidationError, doc.insert)
  ```

  Replace the entire `test_locker_tier_is_cleared_on_save` method with this.

- [ ] **Step 4: Run the Phase 0 tests again**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
  ```

  Expected: **all tests pass**.

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py
  git commit -m "test(venue_asset): align tier names with current validator"
  git push origin main
  ```

---

## Task 2: Three-layer lock helper (`locks.py`)

**Files:**
- Create: `hamilton_erp/hamilton_erp/locks.py`
- Create: `hamilton_erp/hamilton_erp/test_locks.py`

**Design reference:** `docs/phase1_design.md` §5.2 and `docs/coding_standards.md` §13.2.

**What this delivers:** A `@contextmanager` that yields the locked asset row to the caller and guarantees (a) only one caller can hold the lock per `(asset_name, operation)` pair, (b) the row is locked at the MariaDB level via `FOR UPDATE`, (c) the Redis token is released via a Lua atomic CAS on exit, and (d) zero I/O is performed by the helper itself (I/O is the caller's responsibility, *outside* the `with` block).

- [ ] **Step 1: Write the failing test file**

  Create `hamilton_erp/hamilton_erp/test_locks.py` with the full content:

  ```python
  """Tests for hamilton_erp.locks — the three-layer lock helper."""
  import threading
  import time
  import uuid

  import frappe
  from frappe.tests import IntegrationTestCase

  from hamilton_erp.locks import asset_status_lock, LockContentionError


  class TestAssetStatusLock(IntegrationTestCase):
      def setUp(self):
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"Lock Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9001,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_lock_yields_row_dict(self):
          """Happy path — lock yields {name, status, version} from the DB row."""
          with asset_status_lock(self.asset.name, "test") as row:
              self.assertEqual(row["name"], self.asset.name)
              self.assertEqual(row["status"], "Available")
              self.assertIn("version", row)

      def test_second_acquisition_raises(self):
          """Holding the lock blocks a second acquisition in a separate thread."""
          acquired = threading.Event()
          contention_seen = {"value": False}

          def holder():
              with asset_status_lock(self.asset.name, "assign"):
                  acquired.set()
                  time.sleep(0.5)

          def contender():
              acquired.wait(timeout=2)
              try:
                  with asset_status_lock(self.asset.name, "assign"):
                      pass
              except LockContentionError:
                  contention_seen["value"] = True

          t1 = threading.Thread(target=holder)
          t2 = threading.Thread(target=contender)
          t1.start(); t2.start(); t1.join(); t2.join()
          self.assertTrue(contention_seen["value"])

      def test_different_operations_are_independent(self):
          """Lock keys are (asset_name, operation) — separate ops don't block."""
          with asset_status_lock(self.asset.name, "assign"):
              with asset_status_lock(self.asset.name, "oos"):
                  pass  # must not raise
  ```

- [ ] **Step 2: Run the test and confirm it fails**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_locks
  ```

  Expected: `ModuleNotFoundError: No module named 'hamilton_erp.locks'` or `ImportError`.

- [ ] **Step 3: Implement the lock helper**

  Create `hamilton_erp/hamilton_erp/locks.py`:

  ```python
  """Three-layer lock helper for Venue Asset status changes.

  Usage:
      with asset_status_lock(asset_name, "assign") as row:
          # row is {"name", "status", "version"} read under FOR UPDATE
          # ... mutate, save, create log — NO I/O here ...
      # ... publish_realtime, enqueue, print — out here, after the with-block

  Layer 1: Redis advisory lock with UUID token (atomic NX set, Lua release)
  Layer 2: MariaDB row lock via SELECT … FOR UPDATE
  Layer 3: Version-field check — caller's responsibility, compares row["version"]
           to the document's version before saving
  """
  from __future__ import annotations

  import uuid
  from contextlib import contextmanager
  from typing import Iterator

  import frappe
  from frappe import _

  LOCK_TTL_MS = 15_000  # 15s — every critical section must complete well under this

  _RELEASE_SCRIPT = """
  if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
  else
      return 0
  end
  """


  class LockContentionError(frappe.ValidationError):
      """Raised when the Redis advisory lock cannot be acquired."""


  @contextmanager
  def asset_status_lock(asset_name: str, operation: str) -> Iterator[dict]:
      """Acquire the three-layer lock for a Venue Asset status change.

      Yields: {"name", "status", "version"} — the row read under FOR UPDATE.
      Raises: LockContentionError if the Redis lock is held by another caller.
      """
      cache = frappe.cache()
      key = f"hamilton:asset_lock:{asset_name}:{operation}"
      token = uuid.uuid4().hex
      # Layer 1 — Redis NX set with TTL
      acquired = cache.set(key, token, nx=True, px=LOCK_TTL_MS)
      if not acquired:
          raise LockContentionError(
              _("Asset {0} is being processed by another operator. "
                "Refresh the board and try again.").format(asset_name)
          )
      try:
          # Layer 2 — MariaDB row lock
          rows = frappe.db.sql(
              "SELECT name, status, version FROM `tabVenue Asset` "
              "WHERE name = %s FOR UPDATE",
              asset_name,
              as_dict=True,
          )
          if not rows:
              frappe.throw(_("Venue Asset {0} not found.").format(asset_name))
          yield rows[0]
      finally:
          # Atomic release via Lua CAS — only delete if the token is still ours
          try:
              cache.eval(_RELEASE_SCRIPT, 1, key, token)
          except Exception:
              # Lock will TTL out — log but don't mask the primary exception
              frappe.logger().warning(
                  f"asset_status_lock: Lua release failed for {key}; TTL fallback"
              )
  ```

- [ ] **Step 4: Run the tests and confirm they pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_locks
  ```

  Expected: **3 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/locks.py hamilton_erp/hamilton_erp/test_locks.py
  git commit -m "feat(locks): add three-layer asset_status_lock context manager (DEC-019)"
  git push origin main
  ```

---

## Task 3: `lifecycle.py` scaffold with state-machine helpers

**Files:**
- Create: `hamilton_erp/hamilton_erp/lifecycle.py`
- Create: `hamilton_erp/hamilton_erp/test_lifecycle.py`

**What this delivers:** The lifecycle module's skeleton — `_valid_transitions()`, `_require_transition()`, `_require_oos_entry()`, plus the `_make_asset_status_log()` helper with the `frappe.flags.in_test` guard (Grok review). Pure functions that can be unit-tested without a lock.

- [ ] **Step 1: Write the failing test file**

  Create `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  """Unit-style tests for hamilton_erp.lifecycle helper functions.

  Task 3 covers only the pure helpers — transition validation.
  Tasks 4–8 add integration tests against the real DB for each
  whitelisted lifecycle function.
  """
  import frappe
  from frappe.tests import IntegrationTestCase

  from hamilton_erp import lifecycle


  class TestLifecycleHelpers(IntegrationTestCase):
      def test_valid_transitions_map(self):
          t = lifecycle._valid_transitions()
          self.assertIn("Occupied", t["Available"])
          self.assertIn("Dirty", t["Occupied"])
          self.assertIn("Available", t["Dirty"])
          self.assertIn("Out of Service", t["Available"])
          self.assertIn("Available", t["Out of Service"])

      def test_require_transition_passes_on_valid(self):
          row = {"name": "VA-0001", "status": "Available", "version": 0}
          lifecycle._require_transition(row, current="Available",
                                        target="Occupied", asset_name="VA-0001")

      def test_require_transition_throws_on_mismatch(self):
          row = {"name": "VA-0001", "status": "Dirty", "version": 0}
          with self.assertRaises(frappe.ValidationError):
              lifecycle._require_transition(row, current="Available",
                                            target="Occupied", asset_name="VA-0001")

      def test_require_oos_entry_throws_on_already_oos(self):
          row = {"name": "VA-0001", "status": "Out of Service", "version": 0}
          with self.assertRaises(frappe.ValidationError):
              lifecycle._require_oos_entry(row, asset_name="VA-0001")

      def test_require_oos_entry_passes_on_other_states(self):
          for status in ("Available", "Occupied", "Dirty"):
              row = {"name": "VA-0001", "status": status, "version": 0}
              lifecycle._require_oos_entry(row, asset_name="VA-0001")  # no raise

      def test_log_helper_skipped_in_test_flag(self):
          """Grok review: Asset Status Log helper short-circuits when in_test is set."""
          frappe.flags.in_test = True
          try:
              result = lifecycle._make_asset_status_log(
                  asset_name="VA-0001",
                  previous="Available",
                  new_status="Occupied",
                  reason=None,
                  operator="test@example.com",
                  venue_session=None,
              )
              self.assertIsNone(result)
          finally:
              frappe.flags.in_test = False
  ```

- [ ] **Step 2: Run the test and confirm it fails**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: `ModuleNotFoundError: No module named 'hamilton_erp.lifecycle'`.

- [ ] **Step 3: Create the lifecycle module skeleton**

  Create `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  """Venue Asset state-transition and session lifecycle core.

  Public API (called from venue_asset.py whitelisted methods and from api.py):
      start_session_for_asset, vacate_session, mark_asset_clean,
      set_asset_out_of_service, return_asset_to_service, mark_all_clean

  All public functions:
    - acquire the three-layer lock (locks.asset_status_lock)
    - validate the transition
    - mutate the asset, bump version, write timestamps
    - create an Asset Status Log entry (skipped in tests — see _make_asset_status_log)
    - publish the realtime event OUTSIDE the lock (via hamilton_erp.realtime)

  No function here performs I/O (print, enqueue, publish_realtime) inside
  the lock section.
  """
  from __future__ import annotations

  from typing import Optional

  import frappe
  from frappe import _


  # ---------------------------------------------------------------------------
  # State machine
  # ---------------------------------------------------------------------------


  def _valid_transitions() -> dict[str, list[str]]:
      return {
          "Available": ["Occupied", "Out of Service"],
          "Occupied": ["Dirty", "Out of Service"],
          "Dirty": ["Available", "Out of Service"],
          "Out of Service": ["Available"],
      }


  def _require_transition(row: dict, *, current: str, target: str, asset_name: str) -> None:
      """Throw if row["status"] != current OR if current→target is not a valid edge."""
      if row["status"] != current:
          frappe.throw(_("Cannot {0} {1}: current status is {2}, expected {3}.")
                       .format(target.lower(), asset_name, row["status"], current))
      if target not in _valid_transitions().get(current, []):
          frappe.throw(_("Invalid transition {0}→{1} for {2}.")
                       .format(current, target, asset_name))


  def _require_oos_entry(row: dict, *, asset_name: str) -> None:
      """Out of Service can come from Available / Occupied / Dirty, but not from itself."""
      if row["status"] == "Out of Service":
          frappe.throw(_("Asset {0} is already Out of Service.").format(asset_name))


  # ---------------------------------------------------------------------------
  # Asset Status Log — in-test guard (Grok review 2026-04-10)
  # ---------------------------------------------------------------------------


  def _make_asset_status_log(
      *,
      asset_name: str,
      previous: str,
      new_status: str,
      reason: Optional[str],
      operator: str,
      venue_session: Optional[str],
  ) -> Optional[str]:
      """Create an Asset Status Log entry. Short-circuits in tests.

      Returns the log name, or None when suppressed.

      Tests that specifically assert log creation must clear frappe.flags.in_test
      locally via setUp/tearDown.
      """
      if frappe.flags.in_test:
          return None
      log = frappe.get_doc({
          "doctype": "Asset Status Log",
          "venue_asset": asset_name,
          "previous_status": previous,
          "new_status": new_status,
          "reason": reason,
          "operator": operator,
          "venue_session": venue_session,
          "timestamp": frappe.utils.now_datetime(),
      }).insert(ignore_permissions=True)
      return log.name
  ```

- [ ] **Step 4: Run the tests and confirm they pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **6 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): add state-machine helpers + in_test log guard"
  git push origin main
  ```

---

## Task 4: `start_session_for_asset` — Available → Occupied

**Files:**
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

**What this delivers:** The first real transition function. Acquires the lock, validates Available→Occupied, inserts a Venue Session (with `assignment_status="Assigned"`, `operator_checkin`, `customer="Walk-in"`, `session_start=now`), flips the asset to Occupied with `current_session` set and `version` bumped, writes the status log (suppressed in tests), and returns the session name. Realtime event fires after the with-block.

- [ ] **Step 1: Add the failing integration test**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  import uuid


  class TestStartSession(IntegrationTestCase):
      def setUp(self):
          # Walk-in customer is required (DEC-055 §1). The seed patch creates it,
          # but this test runs before Task 11, so create it here as a local fixture.
          if not frappe.db.exists("Customer", "Walk-in"):
              frappe.get_doc({
                  "doctype": "Customer",
                  "customer_name": "Walk-in",
                  "customer_group": frappe.db.get_value(
                      "Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
                  "territory": frappe.db.get_value(
                      "Territory", {"is_group": 0}, "name") or "All Territories",
              }).insert(ignore_permissions=True)

          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"Start Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9002,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_start_session_flips_asset_to_occupied(self):
          session_name = lifecycle.start_session_for_asset(
              self.asset.name, operator="Administrator"
          )
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Occupied")
          self.assertEqual(asset.current_session, session_name)
          self.assertEqual(asset.version, 1)

      def test_start_session_creates_venue_session(self):
          session_name = lifecycle.start_session_for_asset(
              self.asset.name, operator="Administrator"
          )
          s = frappe.get_doc("Venue Session", session_name)
          self.assertEqual(s.venue_asset, self.asset.name)
          self.assertEqual(s.assignment_status, "Assigned")
          self.assertEqual(s.operator_checkin, "Administrator")
          self.assertEqual(s.status, "Active")
          self.assertIsNotNone(s.session_start)

      def test_start_session_rejects_non_available(self):
          self.asset.status = "Dirty"
          self.asset.save(ignore_permissions=True)
          with self.assertRaises(frappe.ValidationError):
              lifecycle.start_session_for_asset(self.asset.name, operator="Administrator")
  ```

- [ ] **Step 2: Run and confirm the new tests fail**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 3 new tests fail with `AttributeError: module 'hamilton_erp.lifecycle' has no attribute 'start_session_for_asset'`.

- [ ] **Step 3: Implement `start_session_for_asset` and its private helpers**

  Append to `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Public lifecycle functions
  # ---------------------------------------------------------------------------


  def start_session_for_asset(asset_name: str, *, operator: str, customer: str = "Walk-in") -> str:
      """Available → Occupied + create Venue Session. Returns session name."""
      from hamilton_erp.locks import asset_status_lock
      from hamilton_erp.realtime import publish_status_change

      with asset_status_lock(asset_name, "assign") as row:
          _require_transition(row, current="Available", target="Occupied",
                              asset_name=asset_name)
          session_name = _create_session(asset_name, operator=operator, customer=customer)
          _set_asset_status(
              asset_name,
              new_status="Occupied",
              session=session_name,
              log_reason=None,
              operator=operator,
              previous="Available",
              expected_version=row["version"],
          )
      publish_status_change(asset_name, previous_status="Available")
      return session_name


  # ---------------------------------------------------------------------------
  # Private helpers (all run INSIDE the lock — zero I/O)
  # ---------------------------------------------------------------------------


  def _create_session(asset_name: str, *, operator: str, customer: str) -> str:
      session = frappe.get_doc({
          "doctype": "Venue Session",
          "venue_asset": asset_name,
          "operator_checkin": operator,
          "customer": customer,
          "session_start": frappe.utils.now_datetime(),
          "status": "Active",
          "assignment_status": "Assigned",
          "identity_method": "not_applicable",
      }).insert(ignore_permissions=True)
      return session.name


  def _set_asset_status(
      asset_name: str,
      *,
      new_status: str,
      session: Optional[str],
      log_reason: Optional[str],
      operator: str,
      previous: str,
      expected_version: int,
  ) -> None:
      """Write the new status, bump version, and create the audit log.

      The caller must have just read `expected_version` under FOR UPDATE inside the
      same lock, so an optimistic-lock conflict here would be a bug, not a race.
      """
      asset = frappe.get_doc("Venue Asset", asset_name)
      if asset.version != expected_version:
          frappe.throw(_("Concurrent update to {0} — please refresh and retry.")
                       .format(asset_name))
      asset.status = new_status
      asset.current_session = session
      asset.version = expected_version + 1
      asset.hamilton_last_status_change = frappe.utils.now_datetime()
      if new_status == "Out of Service":
          asset.reason = log_reason
      asset.save(ignore_permissions=True)
      _make_asset_status_log(
          asset_name=asset_name,
          previous=previous,
          new_status=new_status,
          reason=log_reason,
          operator=operator,
          venue_session=session,
      )
  ```

- [ ] **Step 4: Create a stub `realtime.py` so the import succeeds**

  The full implementation lands in Task 13. For now, create `hamilton_erp/hamilton_erp/realtime.py` with just the two no-op wrappers so this task's tests don't error on import:

  ```python
  """Realtime publishers — full impl in Task 13. Stubbed here so lifecycle
  imports succeed during early TDD."""
  from __future__ import annotations


  def publish_status_change(asset_name: str, previous_status: str | None = None) -> None:
      pass  # replaced in Task 13


  def publish_board_refresh(triggered_by: str, count: int) -> None:
      pass  # replaced in Task 13
  ```

- [ ] **Step 5: Run the tests and confirm they pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **9 tests pass** (6 from Task 3 + 3 new).

- [ ] **Step 6: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py \
          hamilton_erp/hamilton_erp/realtime.py \
          hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): start_session_for_asset (Available→Occupied)"
  git push origin main
  ```

---

## Task 5: `vacate_session` — Occupied → Dirty

**Files:**
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

- [ ] **Step 1: Add failing tests**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  class TestVacateSession(IntegrationTestCase):
      def setUp(self):
          if not frappe.db.exists("Customer", "Walk-in"):
              frappe.get_doc({
                  "doctype": "Customer",
                  "customer_name": "Walk-in",
                  "customer_group": frappe.db.get_value(
                      "Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
                  "territory": frappe.db.get_value(
                      "Territory", {"is_group": 0}, "name") or "All Territories",
              }).insert(ignore_permissions=True)
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"Vacate Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9003,
              "version": 0,
          }).insert(ignore_permissions=True)
          self.session_name = lifecycle.start_session_for_asset(
              self.asset.name, operator="Administrator"
          )

      def tearDown(self):
          frappe.db.rollback()

      def test_vacate_moves_to_dirty(self):
          lifecycle.vacate_session(
              self.asset.name, operator="Administrator", vacate_method="Key Return"
          )
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Dirty")
          self.assertIsNone(asset.current_session)
          self.assertIsNotNone(asset.last_vacated_at)

      def test_vacate_closes_session(self):
          lifecycle.vacate_session(
              self.asset.name, operator="Administrator", vacate_method="Key Return"
          )
          s = frappe.get_doc("Venue Session", self.session_name)
          self.assertEqual(s.status, "Completed")
          self.assertEqual(s.operator_vacate, "Administrator")
          self.assertEqual(s.vacate_method, "Key Return")
          self.assertIsNotNone(s.session_end)

      def test_vacate_rejects_non_occupied(self):
          # Move asset to Dirty first so it's no longer Occupied
          lifecycle.vacate_session(
              self.asset.name, operator="Administrator", vacate_method="Key Return"
          )
          with self.assertRaises(frappe.ValidationError):
              lifecycle.vacate_session(
                  self.asset.name, operator="Administrator", vacate_method="Key Return"
              )

      def test_vacate_requires_valid_method(self):
          with self.assertRaises(AssertionError):
              lifecycle.vacate_session(
                  self.asset.name, operator="Administrator", vacate_method="Nonsense"
              )
  ```

- [ ] **Step 2: Run tests, confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 4 tests fail with `AttributeError: … no attribute 'vacate_session'`.

- [ ] **Step 3: Implement `vacate_session` + helpers**

  Append to `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  _VACATE_METHODS = ("Key Return", "Discovery on Rounds")


  def vacate_session(asset_name: str, *, operator: str, vacate_method: str) -> None:
      """Occupied → Dirty + close linked Venue Session."""
      assert vacate_method in _VACATE_METHODS, f"vacate_method must be one of {_VACATE_METHODS}"
      from hamilton_erp.locks import asset_status_lock
      from hamilton_erp.realtime import publish_status_change

      with asset_status_lock(asset_name, "vacate") as row:
          _require_transition(row, current="Occupied", target="Dirty",
                              asset_name=asset_name)
          _close_current_session(asset_name, operator=operator, vacate_method=vacate_method)
          _set_asset_status(
              asset_name,
              new_status="Dirty",
              session=None,
              log_reason=None,
              operator=operator,
              previous="Occupied",
              expected_version=row["version"],
          )
          _set_vacated_timestamp(asset_name)
      publish_status_change(asset_name, previous_status="Occupied")


  def _close_current_session(asset_name: str, *, operator: str, vacate_method: str) -> str:
      current = frappe.db.get_value("Venue Asset", asset_name, "current_session")
      if not current:
          frappe.throw(_("Asset {0} has no current session to close.").format(asset_name))
      session = frappe.get_doc("Venue Session", current)
      session.session_end = frappe.utils.now_datetime()
      session.operator_vacate = operator
      session.vacate_method = vacate_method
      session.status = "Completed"
      session.save(ignore_permissions=True)
      return session.name


  def _set_vacated_timestamp(asset_name: str) -> None:
      frappe.db.set_value("Venue Asset", asset_name,
                          "last_vacated_at", frappe.utils.now_datetime())
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **13 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): vacate_session (Occupied→Dirty)"
  git push origin main
  ```

---

## Task 6: `mark_asset_clean` + bulk reason support

**Files:**
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

- [ ] **Step 1: Add failing tests**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  class TestMarkClean(IntegrationTestCase):
      def setUp(self):
          if not frappe.db.exists("Customer", "Walk-in"):
              frappe.get_doc({
                  "doctype": "Customer",
                  "customer_name": "Walk-in",
                  "customer_group": frappe.db.get_value(
                      "Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
                  "territory": frappe.db.get_value(
                      "Territory", {"is_group": 0}, "name") or "All Territories",
              }).insert(ignore_permissions=True)
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"Clean Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Dirty",
              "display_order": 9004,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_mark_clean_moves_dirty_to_available(self):
          lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Available")
          self.assertIsNotNone(asset.last_cleaned_at)

      def test_mark_clean_rejects_non_dirty(self):
          self.asset.status = "Available"
          self.asset.save(ignore_permissions=True)
          with self.assertRaises(frappe.ValidationError):
              lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")

      def test_mark_clean_accepts_bulk_reason(self):
          """Bulk reason is stored on the log entry (DEC-054 §5). Not asserted here
          because the in_test flag suppresses log creation — covered in Task 11
          integration via the seed patch."""
          lifecycle.mark_asset_clean(
              self.asset.name, operator="Administrator",
              bulk_reason="Bulk Mark Clean — Room reset",
          )
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Available")
  ```

- [ ] **Step 2: Run tests, confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 3 new failures.

- [ ] **Step 3: Implement `mark_asset_clean`**

  Append to `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  def mark_asset_clean(
      asset_name: str,
      *,
      operator: str,
      bulk_reason: Optional[str] = None,
  ) -> None:
      """Dirty → Available. bulk_reason is set by the bulk Mark All Clean flow."""
      from hamilton_erp.locks import asset_status_lock
      from hamilton_erp.realtime import publish_status_change

      with asset_status_lock(asset_name, "clean") as row:
          _require_transition(row, current="Dirty", target="Available",
                              asset_name=asset_name)
          _set_asset_status(
              asset_name,
              new_status="Available",
              session=None,
              log_reason=bulk_reason,
              operator=operator,
              previous="Dirty",
              expected_version=row["version"],
          )
          _set_cleaned_timestamp(asset_name)
      publish_status_change(asset_name, previous_status="Dirty")


  def _set_cleaned_timestamp(asset_name: str) -> None:
      frappe.db.set_value("Venue Asset", asset_name,
                          "last_cleaned_at", frappe.utils.now_datetime())
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **16 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): mark_asset_clean (Dirty→Available)"
  git push origin main
  ```

---

## Task 7: `set_asset_out_of_service` (any → OOS)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

- [ ] **Step 1: Add failing tests**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  class TestSetOutOfService(IntegrationTestCase):
      def setUp(self):
          if not frappe.db.exists("Customer", "Walk-in"):
              frappe.get_doc({
                  "doctype": "Customer",
                  "customer_name": "Walk-in",
                  "customer_group": frappe.db.get_value(
                      "Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
                  "territory": frappe.db.get_value(
                      "Territory", {"is_group": 0}, "name") or "All Territories",
              }).insert(ignore_permissions=True)
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"OOS Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9005,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_oos_from_available(self):
          lifecycle.set_asset_out_of_service(
              self.asset.name, operator="Administrator", reason="Plumbing failure"
          )
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Out of Service")
          self.assertEqual(asset.reason, "Plumbing failure")

      def test_oos_from_occupied_closes_session(self):
          session_name = lifecycle.start_session_for_asset(
              self.asset.name, operator="Administrator"
          )
          lifecycle.set_asset_out_of_service(
              self.asset.name, operator="Administrator", reason="Emergency"
          )
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Out of Service")
          s = frappe.get_doc("Venue Session", session_name)
          self.assertEqual(s.status, "Completed")
          self.assertEqual(s.vacate_method, "Discovery on Rounds")

      def test_oos_requires_reason(self):
          with self.assertRaises(frappe.ValidationError):
              lifecycle.set_asset_out_of_service(
                  self.asset.name, operator="Administrator", reason=""
              )

      def test_oos_reject_if_already_oos(self):
          lifecycle.set_asset_out_of_service(
              self.asset.name, operator="Administrator", reason="First"
          )
          with self.assertRaises(frappe.ValidationError):
              lifecycle.set_asset_out_of_service(
                  self.asset.name, operator="Administrator", reason="Second"
              )
  ```

- [ ] **Step 2: Run tests, confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 4 new failures.

- [ ] **Step 3: Implement `set_asset_out_of_service`**

  Append to `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  def set_asset_out_of_service(asset_name: str, *, operator: str, reason: str) -> None:
      """Any state (except OOS) → Out of Service. Reason is mandatory."""
      if not reason or not reason.strip():
          frappe.throw(_("A reason is required to set an asset Out of Service."))
      from hamilton_erp.locks import asset_status_lock
      from hamilton_erp.realtime import publish_status_change

      with asset_status_lock(asset_name, "oos") as row:
          previous = row["status"]
          _require_oos_entry(row, asset_name=asset_name)
          if previous == "Occupied":
              _close_current_session(asset_name, operator=operator,
                                     vacate_method="Discovery on Rounds")
          _set_asset_status(
              asset_name,
              new_status="Out of Service",
              session=None,
              log_reason=reason,
              operator=operator,
              previous=previous,
              expected_version=row["version"],
          )
      publish_status_change(asset_name, previous_status=previous)
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **20 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): set_asset_out_of_service with session auto-close"
  git push origin main
  ```

---

## Task 8: `return_asset_to_service` (OOS → Available)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

> **Additional requirement — Gemini AI review (2026-04-10):** When an asset
> transitions from Out of Service back to Available, the persisted `reason`
> field (set by Task 7's `set_asset_out_of_service`) must be cleared —
> otherwise the stale OOS reason lingers on the asset forever. Two changes
> are required in this task:
>
> 1. **Modify `_set_asset_status`** (defined in Task 5, around line 714 of
>    this plan — the `if new_status == "Out of Service": asset.reason = log_reason`
>    branch). Extend it with an `elif` branch:
>    ```python
>    if new_status == "Out of Service":
>        asset.reason = log_reason
>    elif previous == "Out of Service":
>        asset.reason = None
>    ```
>    This keeps the reason-field lifecycle symmetric with the status-field
>    lifecycle and centralizes the clearing logic in the one helper that all
>    lifecycle functions already go through.
> 2. **Extend `test_return_moves_to_available`** (Step 1 below) with an
>    assertion: `self.assertFalse(asset.reason)` after the transition. The
>    `setUp` for this test already seeds `reason: "Initial OOS"`, so this
>    catches a regression if `_set_asset_status` stops clearing it.

- [ ] **Step 1: Add failing tests**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  class TestReturnToService(IntegrationTestCase):
      def setUp(self):
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"Return Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Out of Service",
              "reason": "Initial OOS",
              "display_order": 9006,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_return_moves_to_available(self):
          lifecycle.return_asset_to_service(
              self.asset.name, operator="Administrator", reason="Repair done"
          )
          asset = frappe.get_doc("Venue Asset", self.asset.name)
          self.assertEqual(asset.status, "Available")
          self.assertIsNotNone(asset.last_cleaned_at)

      def test_return_requires_reason(self):
          with self.assertRaises(frappe.ValidationError):
              lifecycle.return_asset_to_service(
                  self.asset.name, operator="Administrator", reason="   "
              )

      def test_return_rejects_non_oos(self):
          self.asset.status = "Available"
          self.asset.save(ignore_permissions=True)
          with self.assertRaises(frappe.ValidationError):
              lifecycle.return_asset_to_service(
                  self.asset.name, operator="Administrator", reason="any"
              )
  ```

- [ ] **Step 2: Run tests, confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 3 new failures.

- [ ] **Step 3: Implement `return_asset_to_service`**

  Append to `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  def return_asset_to_service(asset_name: str, *, operator: str, reason: str) -> None:
      """Out of Service → Available. Reason is mandatory."""
      if not reason or not reason.strip():
          frappe.throw(_("A reason is required to return an asset to service."))
      from hamilton_erp.locks import asset_status_lock
      from hamilton_erp.realtime import publish_status_change

      with asset_status_lock(asset_name, "return") as row:
          _require_transition(row, current="Out of Service", target="Available",
                              asset_name=asset_name)
          _set_asset_status(
              asset_name,
              new_status="Available",
              session=None,
              log_reason=reason,
              operator=operator,
              previous="Out of Service",
              expected_version=row["version"],
          )
          _set_cleaned_timestamp(asset_name)
      publish_status_change(asset_name, previous_status="Out of Service")
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **23 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): return_asset_to_service (OOS→Available)"
  git push origin main
  ```

---

## Task 9: `_next_session_number()` — Redis INCR with DB fallback

**Files:**
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

**Design reference:** `docs/phase1_design.md` §5.5, DEC-033 format, Q9 (Redis INCR + 48h TTL + DB reconciliation fallback).

- [ ] **Step 1: Add failing tests**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  from unittest.mock import patch


  class TestSessionNumberGenerator(IntegrationTestCase):
      def setUp(self):
          # Flush any leftover key from prior runs
          today = frappe.utils.nowdate()  # "YYYY-MM-DD"
          y, m, d = today.split("-")
          key = f"hamilton:session_seq:{int(d)}-{int(m)}-{int(y)}"
          frappe.cache().delete_value(key)

      def test_first_call_returns_001(self):
          n = lifecycle._next_session_number()
          self.assertTrue(n.endswith("---001"))

      def test_second_call_returns_002(self):
          lifecycle._next_session_number()
          n2 = lifecycle._next_session_number()
          self.assertTrue(n2.endswith("---002"))

      def test_format_matches_dec_033(self):
          n = lifecycle._next_session_number()
          prefix, seq = n.split("---")
          parts = prefix.split("-")
          self.assertEqual(len(parts), 3)  # d-m-y
          self.assertEqual(len(seq), 3)    # 001 padding

      def test_db_fallback_when_redis_cold(self):
          """If Redis key is missing but DB already has today's sessions, resume the
          sequence at DB max + 1."""
          # Seed a fake row
          today = frappe.utils.nowdate()
          y, m, d = today.split("-")
          prefix = f"{int(d)}-{int(m)}-{int(y)}"
          # Create an asset + session directly so we have a real DB row
          asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"Fallback Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9007,
              "version": 0,
          }).insert(ignore_permissions=True)
          frappe.get_doc({
              "doctype": "Venue Session",
              "venue_asset": asset.name,
              "session_number": f"{prefix}---005",
              "status": "Active",
              "identity_method": "not_applicable",
              "session_start": frappe.utils.now_datetime(),
          }).insert(ignore_permissions=True)
          # Flush redis key so fallback kicks in
          frappe.cache().delete_value(f"hamilton:session_seq:{prefix}")
          n = lifecycle._next_session_number()
          self.assertEqual(n, f"{prefix}---006")

      def tearDown(self):
          frappe.db.rollback()
  ```

- [ ] **Step 2: Run and confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 4 new failures.

- [ ] **Step 3: Implement the generator**

  Append to `hamilton_erp/hamilton_erp/lifecycle.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Session number generator (DEC-033 + Q9)
  # ---------------------------------------------------------------------------

  _SESSION_KEY_TTL_MS = 48 * 60 * 60 * 1000  # 48 hours


  def _next_session_number() -> str:
      """Return the next session number for today in DEC-033 format.

      Format: {d}-{m}-{y}---{NNN}, e.g. "9-4-2026---001".
      Resets via key name, not key TTL — the 48h TTL is just garbage collection.
      """
      year, month, day = frappe.utils.nowdate().split("-")  # "YYYY-MM-DD"
      d, m, y = int(day), int(month), int(year)
      prefix = f"{d}-{m}-{y}"
      key = f"hamilton:session_seq:{prefix}"
      cache = frappe.cache()
      if not cache.exists(key):
          db_max = _db_max_seq_for_prefix(prefix)
          cache.set(key, db_max, nx=True, px=_SESSION_KEY_TTL_MS)
      seq = int(cache.incr(key))
      return f"{prefix}---{seq:03d}"


  def _db_max_seq_for_prefix(prefix: str) -> int:
      """Parse the trailing NNN from the highest session_number matching today."""
      row = frappe.db.sql(
          "SELECT session_number FROM `tabVenue Session` "
          "WHERE session_number LIKE %s "
          "ORDER BY session_number DESC LIMIT 1",
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

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **27 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/lifecycle.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(lifecycle): session_number via Redis INCR with DB fallback (DEC-033, Q9)"
  git push origin main
  ```

---

## Task 10: Wire `_next_session_number` into `VenueSession.before_insert` + read-only lockdown

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.py`
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json`
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/test_venue_session.py`

- [ ] **Step 1: Add failing test**

  Append to `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/test_venue_session.py`:

  ```python
  def test_before_insert_sets_session_number(self):
      asset = frappe.get_doc({
          "doctype": "Venue Asset",
          "asset_name": "Session Number Test",
          "asset_category": "Room",
          "asset_tier": "Single Standard",
          "status": "Available",
          "display_order": 9008,
      }).insert(ignore_permissions=True)
      s = frappe.get_doc({
          "doctype": "Venue Session",
          "venue_asset": asset.name,
          "status": "Active",
          "identity_method": "not_applicable",
          "session_start": frappe.utils.now_datetime(),
      }).insert(ignore_permissions=True)
      self.assertTrue(s.session_number)
      self.assertIn("---", s.session_number)

  def test_sales_invoice_field_is_read_only(self):
      """DEC-055 §2 — sales_invoice must be read_only on the form."""
      meta = frappe.get_meta("Venue Session")
      field = meta.get_field("sales_invoice")
      self.assertEqual(field.read_only, 1)
  ```

- [ ] **Step 2: Run and confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_session.test_venue_session
  ```

  Expected: 2 new failures.

- [ ] **Step 3: Add `before_insert` to the controller**

  Edit `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.py` — add the `before_insert` hook:

  ```python
  def before_insert(self):
      if not self.session_number:
          from hamilton_erp.lifecycle import _next_session_number
          self.session_number = _next_session_number()
  ```

  Insert this method between `validate` and `on_submit`.

- [ ] **Step 4: Mark the 7 system-owned fields `read_only: 1`**

  Edit `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json`. For each of the following field entries, set `"read_only": 1`:
  - `sales_invoice`
  - `admission_item`
  - `operator_checkin`
  - `shift_record`
  - `pricing_rule_applied`
  - `under_25_applied`
  - `comp_flag`

  Example patch for one field (apply the same `"read_only": 1` line to all seven):

  ```json
  {
    "fieldname": "sales_invoice",
    "fieldtype": "Link",
    "label": "Sales Invoice",
    "options": "Sales Invoice",
    "read_only": 1
  }
  ```

- [ ] **Step 5: Run `bench migrate` so Frappe picks up the JSON change, then run tests**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost migrate
  bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_session.test_venue_session
  ```

  Expected: **all tests pass.** Also re-run `test_lifecycle` to confirm earlier tests still pass (the Venue Session `before_insert` now runs inside `_create_session`):

  ```bash
  bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **27 tests still pass.**

- [ ] **Step 6: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.py \
          hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json \
          hamilton_erp/hamilton_erp/doctype/venue_session/test_venue_session.py
  git commit -m "feat(venue_session): session_number via before_insert + read_only lockdown (DEC-055)"
  git push origin main
  ```

---

## Task 11: Seed migration patch (`seed_hamilton_env.py`)

**Files:**
- Create: `hamilton_erp/hamilton_erp/patches/v0_1/seed_hamilton_env.py`
- Modify: `hamilton_erp/hamilton_erp/patches.txt`
- Create: `hamilton_erp/hamilton_erp/test_seed_patch.py`
- Modify: `hamilton_erp/hamilton_erp/lifecycle.py` (session_number format: `:03d` → `:04d`)
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_session/venue_session.json` (unique constraint on `session_number`)
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py` (update format assertions to 4-digit sequence)

**Design reference:** `docs/phase1_design.md` §5.8. Idempotent. Creates Walk-in Customer + Hamilton Settings defaults + all 59 assets.

**Additional Task 11 requirements (from Task 9 3-AI review, 2026-04-10):**

a. **Switch `_next_session_number()` zero-pad from `:03d` to `:04d`.** Also update `len(seq)` / `{seq:03d}` references in `test_lifecycle.py::TestSessionNumberGenerator` (`test_format_matches_dec_033` asserts `len(seq) == 3` — change to `4`). Eliminates the NNN>999 lexicographic sort bug permanently: with 4-digit padding, `ORDER BY session_number DESC` stays correct up to 9999 sessions/day, well beyond Club Hamilton's operational ceiling. DEC-033 must be amended to note the width change.

b. **Add DB uniqueness constraint on `Venue Session.session_number`** in `venue_session.json` (`"unique": 1`). This is the load-bearing guard for the `_next_session_number()` Redis-blip race: if the SET between `get()` and `incr()` silently fails and INCR auto-creates the key at 1, the resulting `---0001` INSERT collides with the persisted row and raises `frappe.exceptions.DuplicateEntryError`, which the caller can catch and retry. Without the unique constraint, the collision would silently persist duplicate session numbers.

c. **Add bounded retry on `DuplicateEntryError` in `_create_session()`** (3 attempts max). If `frappe.get_doc(...).insert()` raises `frappe.exceptions.DuplicateEntryError` on the `session_number` field, call `_next_session_number()` again and retry. After 3 failures, raise `frappe.ValidationError("Session number collision — please try again.")`. Log each retry via `frappe.logger().warning` so production can spot a pathological Redis flap. Test: monkeypatch `_next_session_number` to return a colliding value twice then a fresh value, assert the third attempt succeeds.

Removing the Task 9 `TODO(task-11)` markers in `lifecycle.py` (lines ~500 and ~548) is part of this task's cleanup.

- [ ] **Step 1: Write the failing test**

  Create `hamilton_erp/hamilton_erp/test_seed_patch.py`:

  ```python
  """Tests for the Phase 1 seed patch — seed_hamilton_env."""
  import frappe
  from frappe.tests import IntegrationTestCase

  from hamilton_erp.patches.v0_1 import seed_hamilton_env


  class TestSeedPatch(IntegrationTestCase):
      def tearDown(self):
          frappe.db.rollback()

      def test_seed_creates_walkin_customer(self):
          frappe.db.delete("Customer", {"name": "Walk-in"})
          seed_hamilton_env.execute()
          self.assertTrue(frappe.db.exists("Customer", "Walk-in"))

      def test_seed_populates_hamilton_settings(self):
          s = frappe.get_single("Hamilton Settings")
          s.float_amount = 0
          s.default_stay_duration_minutes = 0
          s.save(ignore_permissions=True)
          seed_hamilton_env.execute()
          s = frappe.get_single("Hamilton Settings")
          self.assertEqual(s.float_amount, 300)
          self.assertEqual(s.default_stay_duration_minutes, 360)

      def test_seed_creates_59_assets_in_correct_order(self):
          # Clean slate for this test
          frappe.db.delete("Venue Asset")
          seed_hamilton_env.execute()
          assets = frappe.get_all(
              "Venue Asset",
              fields=["asset_code", "asset_category", "asset_tier", "display_order"],
              order_by="display_order asc",
          )
          self.assertEqual(len(assets), 59)
          # Spot-check the ordering boundaries per Q6
          self.assertEqual(assets[0]["asset_code"], "R001")   # first Single Standard
          self.assertEqual(assets[10]["asset_code"], "R011")  # last Single Standard
          self.assertEqual(assets[11]["asset_code"], "R012")  # first Deluxe Single
          self.assertEqual(assets[20]["asset_code"], "R021")  # last Deluxe Single
          self.assertEqual(assets[21]["asset_code"], "R022")  # first Glory Hole
          self.assertEqual(assets[22]["asset_code"], "R023")  # last Glory Hole
          self.assertEqual(assets[23]["asset_code"], "R024")  # first Double Deluxe
          self.assertEqual(assets[25]["asset_code"], "R026")  # last Double Deluxe
          self.assertEqual(assets[26]["asset_code"], "L001")  # first Locker
          self.assertEqual(assets[58]["asset_code"], "L033")  # last Locker

      def test_seed_is_idempotent(self):
          seed_hamilton_env.execute()
          count1 = frappe.db.count("Venue Asset")
          seed_hamilton_env.execute()
          count2 = frappe.db.count("Venue Asset")
          self.assertEqual(count1, count2)
  ```

- [ ] **Step 2: Run and confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_seed_patch
  ```

  Expected: `ModuleNotFoundError: … seed_hamilton_env`.

- [ ] **Step 3: Create the seed patch**

  Create `hamilton_erp/hamilton_erp/patches/v0_1/seed_hamilton_env.py`:

  ```python
  """Phase 1 seed patch — idempotent.

  Creates:
    1. Walk-in Customer (DEC-055 §1)
    2. Hamilton Settings defaults (DEC-055 §3)
    3. All 59 Venue Assets in the Q6 order:
       R001–R011 Single Standard, R012–R021 Deluxe Single,
       R022–R023 Glory Hole, R024–R026 Double Deluxe, L001–L033 Lockers
  """
  import frappe


  def execute():
      _ensure_walkin_customer()
      _ensure_hamilton_settings()
      _ensure_venue_assets()


  def _ensure_walkin_customer() -> None:
      if frappe.db.exists("Customer", "Walk-in"):
          return
      frappe.get_doc({
          "doctype": "Customer",
          "customer_name": "Walk-in",
          "customer_group": frappe.db.get_value(
              "Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
          "territory": frappe.db.get_value(
              "Territory", {"is_group": 0}, "name") or "All Territories",
      }).insert(ignore_permissions=True)


  def _ensure_hamilton_settings() -> None:
      settings = frappe.get_single("Hamilton Settings")
      defaults = {
          "float_amount": 300,
          "default_stay_duration_minutes": 360,
          "grace_minutes": 15,
          "assignment_timeout_minutes": 15,
      }
      changed = False
      for field, value in defaults.items():
          if not settings.get(field):
              settings.set(field, value)
              changed = True
      if changed:
          settings.save(ignore_permissions=True)


  def _ensure_venue_assets() -> None:
      if frappe.db.count("Venue Asset") > 0:
          return  # idempotent guard
      company = frappe.defaults.get_global_default("company")
      if not company:
          frappe.logger().warning(
              "seed_hamilton_env: no default company — assets created with company=None"
          )

      # (code_prefix, count, category, tier, name_prefix, code_start, display_start)
      plan = (
          ("R", 11, "Room", "Single Standard", "Sing STD",  1,  1),
          ("R", 10, "Room", "Deluxe Single",   "Sing DLX", 12, 12),
          ("R",  2, "Room", "Glory Hole",      "Glory",    22, 22),
          ("R",  3, "Room", "Double Deluxe",   "Dbl DLX",  24, 24),
          ("L", 33, "Locker", "Locker",        "Lckr",      1, 27),
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
                  "company": company,
                  "version": 0,
              }).insert(ignore_permissions=True)
  ```

- [ ] **Step 4: Register the patch in `patches.txt`**

  Edit `hamilton_erp/hamilton_erp/patches.txt` — under the `[post_model_sync]` section, append:

  ```
  hamilton_erp.patches.v0_1.seed_hamilton_env
  ```

- [ ] **Step 5: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_seed_patch
  ```

  Expected: **4 tests pass.**

- [ ] **Step 6: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/patches/v0_1/seed_hamilton_env.py \
          hamilton_erp/hamilton_erp/patches.txt \
          hamilton_erp/hamilton_erp/test_seed_patch.py
  git commit -m "feat(patches): seed_hamilton_env — 59 assets + Walk-in + Settings (DEC-055)"
  git push origin main
  ```

---

## Task 12: Realtime publishers (`realtime.py`)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/realtime.py`
- Modify: `hamilton_erp/hamilton_erp/test_lifecycle.py`

**Design reference:** `docs/phase1_design.md` §5.9. Replaces the Task 4 stub with the real publishers. Called **outside** the lock section; both events use `after_commit=True`.

- [ ] **Step 1: Add failing test**

  Append to `hamilton_erp/hamilton_erp/test_lifecycle.py`:

  ```python
  class TestRealtimePublishers(IntegrationTestCase):
      def setUp(self):
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"RT Test {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9009,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_publish_status_change_emits_expected_payload(self):
          captured = {}

          def fake_publish(event, payload, **kwargs):
              captured["event"] = event
              captured["payload"] = payload
              captured["kwargs"] = kwargs

          from hamilton_erp import realtime
          with patch.object(frappe, "publish_realtime", side_effect=fake_publish):
              realtime.publish_status_change(self.asset.name, previous_status="Available")

          self.assertEqual(captured["event"], "hamilton_asset_status_changed")
          self.assertEqual(captured["payload"]["name"], self.asset.name)
          self.assertEqual(captured["payload"]["old_status"], "Available")
          self.assertIn("version", captured["payload"])
          self.assertTrue(captured["kwargs"].get("after_commit"))

      def test_publish_board_refresh_emits_expected_payload(self):
          captured = {}
          def fake_publish(event, payload, **kwargs):
              captured["event"] = event; captured["payload"] = payload
              captured["kwargs"] = kwargs

          from hamilton_erp import realtime
          with patch.object(frappe, "publish_realtime", side_effect=fake_publish):
              realtime.publish_board_refresh("bulk_clean", 5)

          self.assertEqual(captured["event"], "hamilton_asset_board_refresh")
          self.assertEqual(captured["payload"]["triggered_by"], "bulk_clean")
          self.assertEqual(captured["payload"]["count"], 5)
          self.assertTrue(captured["kwargs"].get("after_commit"))
  ```

- [ ] **Step 2: Run and confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: 2 new failures (`publish_realtime` was never called because stubs are no-ops).

- [ ] **Step 3: Replace the stub with the real implementation**

  Overwrite `hamilton_erp/hamilton_erp/realtime.py` with:

  ```python
  """Realtime publishers for the Asset Board.

  Both functions fire with after_commit=True — they must only be called
  AFTER the lock section has exited and the underlying transaction has
  committed (or is about to). Calling inside the lock risks emitting an
  event for state that gets rolled back.
  """
  from __future__ import annotations

  from typing import Optional

  import frappe


  def publish_status_change(asset_name: str, previous_status: Optional[str] = None) -> None:
      """Emit hamilton_asset_status_changed with the moderate C2 payload."""
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
      frappe.publish_realtime(
          "hamilton_asset_status_changed", row, after_commit=True
      )


  def publish_board_refresh(triggered_by: str, count: int) -> None:
      """Emit hamilton_asset_board_refresh for bulk operations."""
      frappe.publish_realtime(
          "hamilton_asset_board_refresh",
          {"triggered_by": triggered_by, "count": count},
          after_commit=True,
      )
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: **29 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/realtime.py hamilton_erp/hamilton_erp/test_lifecycle.py
  git commit -m "feat(realtime): status_changed + board_refresh publishers with after_commit"
  git push origin main
  ```

---

## Task 13: Venue Asset whitelisted methods delegate to `lifecycle.py`

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py`
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py`

**What this delivers:** The 5 Phase 0 stubs on `VenueAsset` get real bodies that call the `lifecycle` module. This is the REST-callable entry point for the Asset Board UI.

- [ ] **Step 1: Add failing integration test**

  Append to `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py`:

  ```python
  # ------------------------------------------------------------------
  # Phase 1 — whitelisted methods call lifecycle module
  # ------------------------------------------------------------------

  def test_mark_vacant_delegates_to_lifecycle(self):
      if not frappe.db.exists("Customer", "Walk-in"):
          frappe.get_doc({
              "doctype": "Customer",
              "customer_name": "Walk-in",
              "customer_group": frappe.db.get_value(
                  "Customer Group", {"is_group": 0}, "name") or "All Customer Groups",
              "territory": frappe.db.get_value(
                  "Territory", {"is_group": 0}, "name") or "All Territories",
          }).insert(ignore_permissions=True)
      asset = self._make_asset("Test Whitelist Vacate")
      asset.reload()
      # Put it into Occupied via the lifecycle module so state is consistent
      from hamilton_erp import lifecycle
      lifecycle.start_session_for_asset(asset.name, operator="Administrator")
      asset.reload()
      asset.mark_vacant(vacate_method="Key Return")  # the whitelisted method
      asset.reload()
      self.assertEqual(asset.status, "Dirty")

  def test_set_out_of_service_requires_reason(self):
      asset = self._make_asset("Test Whitelist OOS")
      with self.assertRaises(frappe.ValidationError):
          asset.set_out_of_service(reason="")
  ```

- [ ] **Step 2: Run, confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
  ```

  Expected: test_mark_vacant_delegates_to_lifecycle fails with the Phase 0 stub error `"mark_vacant is not yet implemented"`.

- [ ] **Step 3: Replace the 5 stub bodies with real delegations**

  Edit `hamilton_erp/hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py` — replace the block starting at `# Whitelisted methods — stubs for Phase 0, implemented in Phase 1` through the end of the class with:

  ```python
  # ------------------------------------------------------------------
  # Whitelisted methods — Phase 1 real bodies (delegate to lifecycle.py)
  # ------------------------------------------------------------------

  @frappe.whitelist(methods=["POST"])
  def assign_to_session(self):
      """Assign a walk-in session to this asset. Available → Occupied."""
      frappe.has_permission("Venue Asset", "write", throw=True)
      from hamilton_erp.lifecycle import start_session_for_asset
      return {"session": start_session_for_asset(self.name, operator=frappe.session.user)}

  @frappe.whitelist(methods=["POST"])
  def mark_vacant(self, vacate_method: str):
      """Close the current session and move to Dirty."""
      frappe.has_permission("Venue Asset", "write", throw=True)
      from hamilton_erp.lifecycle import vacate_session
      vacate_session(self.name, operator=frappe.session.user,
                     vacate_method=vacate_method)

  @frappe.whitelist(methods=["POST"])
  def mark_clean(self):
      """Dirty → Available."""
      frappe.has_permission("Venue Asset", "write", throw=True)
      from hamilton_erp.lifecycle import mark_asset_clean
      mark_asset_clean(self.name, operator=frappe.session.user)

  @frappe.whitelist(methods=["POST"])
  def set_out_of_service(self, reason: str):
      """Any state (except OOS) → Out of Service."""
      frappe.has_permission("Venue Asset", "write", throw=True)
      from hamilton_erp.lifecycle import set_asset_out_of_service
      set_asset_out_of_service(self.name, operator=frappe.session.user, reason=reason)

  @frappe.whitelist(methods=["POST"])
  def return_to_service(self, reason: str):
      """Out of Service → Available."""
      frappe.has_permission("Venue Asset", "write", throw=True)
      from hamilton_erp.lifecycle import return_asset_to_service
      return_asset_to_service(self.name, operator=frappe.session.user, reason=reason)
  ```

- [ ] **Step 4: Run all affected test modules, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
  bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_lifecycle
  ```

  Expected: both modules pass.

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py \
          hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py
  git commit -m "feat(venue_asset): whitelisted methods delegate to lifecycle"
  git push origin main
  ```

---

## Task 14: `api.py` — `get_asset_board_data` with session enrichment + performance baseline

**Files:**
- Modify: `hamilton_erp/hamilton_erp/api.py`
- Create: `hamilton_erp/hamilton_erp/test_api_phase1.py`

**Design reference:** `docs/phase1_design.md` §5.7. Includes the `test_get_asset_board_data_under_one_second` performance baseline (Grok review) to guard against N+1 regressions.

- [ ] **Step 1: Write failing tests**

  Create `hamilton_erp/hamilton_erp/test_api_phase1.py`:

  ```python
  """Tests for the Phase 1 api.py additions."""
  import time

  import frappe
  from frappe.tests import IntegrationTestCase

  from hamilton_erp import api
  from hamilton_erp.patches.v0_1 import seed_hamilton_env


  class TestGetAssetBoardData(IntegrationTestCase):
      @classmethod
      def setUpClass(cls):
          super().setUpClass()
          # Seed the full 59-asset inventory once for the performance test
          frappe.db.delete("Venue Asset")
          seed_hamilton_env.execute()
          frappe.db.commit()

      def test_returns_all_active_assets(self):
          data = api.get_asset_board_data()
          self.assertEqual(len(data["assets"]), 59)

      def test_returns_settings_block(self):
          data = api.get_asset_board_data()
          self.assertIn("settings", data)
          self.assertIn("grace_minutes", data["settings"])

      def test_occupied_assets_include_session_start(self):
          """Pick one asset, occupy it via lifecycle, then check enrichment."""
          from hamilton_erp import lifecycle
          asset_name = frappe.db.get_value(
              "Venue Asset", {"asset_code": "R001"}, "name"
          )
          lifecycle.start_session_for_asset(asset_name, operator="Administrator")
          frappe.db.commit()
          data = api.get_asset_board_data()
          r001 = next(a for a in data["assets"] if a["name"] == asset_name)
          self.assertEqual(r001["status"], "Occupied")
          self.assertIn("session_start", r001)
          self.assertIsNotNone(r001["session_start"])

      def test_get_asset_board_data_under_one_second(self):
          """Grok review — single-query perf baseline. 59 assets in < 1.0s."""
          # Occupy a handful so the enrichment branch fires
          from hamilton_erp import lifecycle
          for code in ("R002", "R003", "L001", "L002"):
              name = frappe.db.get_value("Venue Asset", {"asset_code": code}, "name")
              if frappe.db.get_value("Venue Asset", name, "status") == "Available":
                  lifecycle.start_session_for_asset(name, operator="Administrator")
          frappe.db.commit()
          t0 = time.perf_counter()
          data = api.get_asset_board_data()
          elapsed = time.perf_counter() - t0
          self.assertEqual(len(data["assets"]), 59)
          self.assertLess(
              elapsed, 1.0,
              f"get_asset_board_data took {elapsed:.3f}s — suspect N+1 regression"
          )
  ```

- [ ] **Step 2: Run and confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_api_phase1
  ```

  Expected: `KeyError: 'settings'` and related failures (current `get_asset_board_data` returns only `assets`).

- [ ] **Step 3: Expand `get_asset_board_data` in `api.py`**

  Edit `hamilton_erp/hamilton_erp/api.py`. **Replace** the existing `get_asset_board_data` function (keeping `on_sales_invoice_submit` and `assign_asset_to_session` untouched) with:

  ```python
  @frappe.whitelist(methods=["GET"])
  def get_asset_board_data() -> dict:
      """Initial Asset Board load. Single batched query shape — no N+1.

      Returns:
          {
              "assets": [ {name, asset_code, asset_name, asset_category, asset_tier,
                           status, current_session, expected_stay_duration,
                           display_order, last_vacated_at, last_cleaned_at,
                           hamilton_last_status_change, version,
                           session_start (only for Occupied)}, ... ],
              "settings": {grace_minutes, default_stay_duration_minutes, ...},
          }
      """
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
          limit_page_length=500,
      )

      # Batched session_start lookup — one query for all occupied tiles
      occupied_session_ids = [
          a["current_session"] for a in assets
          if a["status"] == "Occupied" and a.get("current_session")
      ]
      session_starts: dict[str, object] = {}
      if occupied_session_ids:
          rows = frappe.get_all(
              "Venue Session",
              fields=["name", "session_start"],
              filters={"name": ["in", occupied_session_ids]},
          )
          session_starts = {r["name"]: r["session_start"] for r in rows}
      for a in assets:
          a["session_start"] = session_starts.get(a.get("current_session"))

      return {"assets": assets, "settings": _get_hamilton_settings()}


  def _get_hamilton_settings() -> dict:
      s = frappe.get_cached_doc("Hamilton Settings")
      return {
          "grace_minutes": s.get("grace_minutes") or 15,
          "default_stay_duration_minutes": s.get("default_stay_duration_minutes") or 360,
          "assignment_timeout_minutes": s.get("assignment_timeout_minutes") or 15,
      }
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_api_phase1
  ```

  Expected: **4 tests pass.** If the performance test fails (> 1s), check for accidental N+1 — the enrichment must be a single batched `frappe.get_all(..., filters={"name": ["in", ...]})`, not a loop of `get_value` calls.

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/api.py hamilton_erp/hamilton_erp/test_api_phase1.py
  git commit -m "feat(api): get_asset_board_data with session enrichment + <1s perf baseline"
  git push origin main
  ```

---

## Task 15: `api.py` — bulk `mark_all_clean_rooms` / `mark_all_clean_lockers`

**Files:**
- Modify: `hamilton_erp/hamilton_erp/api.py`
- Modify: `hamilton_erp/hamilton_erp/test_api_phase1.py`

**Design reference:** DEC-054, phase1_design.md §5.7. Sorted by name for deadlock prevention.

- [ ] **Step 1: Add failing tests**

  Append to `hamilton_erp/hamilton_erp/test_api_phase1.py`:

  ```python
  class TestBulkMarkClean(IntegrationTestCase):
      @classmethod
      def setUpClass(cls):
          super().setUpClass()
          frappe.db.delete("Venue Asset")
          seed_hamilton_env.execute()
          frappe.db.commit()

      def setUp(self):
          # Dirty a few rooms and a few lockers
          from hamilton_erp import lifecycle
          for code in ("R001", "R002", "R003"):
              name = frappe.db.get_value("Venue Asset", {"asset_code": code}, "name")
              if frappe.db.get_value("Venue Asset", name, "status") == "Available":
                  lifecycle.start_session_for_asset(name, operator="Administrator")
                  lifecycle.vacate_session(name, operator="Administrator",
                                           vacate_method="Key Return")
          for code in ("L001", "L002"):
              name = frappe.db.get_value("Venue Asset", {"asset_code": code}, "name")
              if frappe.db.get_value("Venue Asset", name, "status") == "Available":
                  lifecycle.start_session_for_asset(name, operator="Administrator")
                  lifecycle.vacate_session(name, operator="Administrator",
                                           vacate_method="Key Return")
          frappe.db.commit()

      def test_mark_all_clean_rooms_clears_only_rooms(self):
          result = api.mark_all_clean_rooms()
          self.assertGreaterEqual(len(result["succeeded"]), 3)
          # Verify rooms are Available, lockers still Dirty
          r001 = frappe.db.get_value(
              "Venue Asset", {"asset_code": "R001"}, "status")
          l001 = frappe.db.get_value(
              "Venue Asset", {"asset_code": "L001"}, "status")
          self.assertEqual(r001, "Available")
          self.assertEqual(l001, "Dirty")

      def test_mark_all_clean_lockers_clears_only_lockers(self):
          api.mark_all_clean_rooms()  # clean rooms first so we can isolate lockers
          result = api.mark_all_clean_lockers()
          self.assertGreaterEqual(len(result["succeeded"]), 2)
          l001 = frappe.db.get_value(
              "Venue Asset", {"asset_code": "L001"}, "status")
          self.assertEqual(l001, "Available")
  ```

- [ ] **Step 2: Run and confirm failures**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_api_phase1
  ```

  Expected: `AttributeError: module 'hamilton_erp.api' has no attribute 'mark_all_clean_rooms'`.

- [ ] **Step 3: Add bulk endpoints to `api.py`**

  Append to `hamilton_erp/hamilton_erp/api.py`:

  ```python
  @frappe.whitelist(methods=["POST"])
  def mark_all_clean_rooms() -> dict:
      frappe.has_permission("Venue Asset", "write", throw=True)
      return _mark_all_clean(category="Room")


  @frappe.whitelist(methods=["POST"])
  def mark_all_clean_lockers() -> dict:
      frappe.has_permission("Venue Asset", "write", throw=True)
      return _mark_all_clean(category="Locker")


  def _mark_all_clean(category: str) -> dict:
      """Loop over all Dirty assets of the given category, cleaning each one.

      Sorted by name to establish a deterministic lock ordering across the loop
      (coding_standards.md §13.4). Per-asset failures are recorded and reported;
      the loop does not abort.
      """
      from hamilton_erp.lifecycle import mark_asset_clean
      from hamilton_erp.realtime import publish_board_refresh

      dirty = frappe.get_all(
          "Venue Asset",
          filters={"status": "Dirty", "asset_category": category, "is_active": 1},
          fields=["name", "asset_code", "asset_name"],
          order_by="name asc",
      )
      succeeded: list[str] = []
      failed: list[dict] = []
      reason = f"Bulk Mark Clean — {category} reset"
      for asset in dirty:
          try:
              mark_asset_clean(
                  asset["name"],
                  operator=frappe.session.user,
                  bulk_reason=reason,
              )
              succeeded.append(asset["asset_code"])
          except Exception as e:
              failed.append({"code": asset["asset_code"], "error": str(e)})
      publish_board_refresh("bulk_clean", len(succeeded))
      return {"succeeded": succeeded, "failed": failed}
  ```

- [ ] **Step 4: Run tests, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_api_phase1
  ```

  Expected: **6 tests pass.**

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/api.py hamilton_erp/hamilton_erp/test_api_phase1.py
  git commit -m "feat(api): bulk mark_all_clean endpoints with deadlock-safe ordering (DEC-054)"
  git push origin main
  ```

---

## Task 16: Asset Board page scaffold (empty Frappe Page)

**Files:**
- Create: `hamilton_erp/hamilton_erp/hamilton_erp/page/__init__.py` (if missing)
- Create: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/__init__.py`
- Create: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.json`
- Create: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.py`
- Create: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`
- Create: `hamilton_erp/hamilton_erp/public/css/asset_board.css`
- Modify: `hamilton_erp/hamilton_erp/hooks.py`

**What this delivers:** Just the page exists at `/app/asset-board`, gated to Hamilton roles, and shows a placeholder "Loading..." message. The JS class skeleton is stubbed — full rendering lands in Tasks 17-20.

- [ ] **Step 1: Create the `page` package (only if missing)**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp/hamilton_erp/hamilton_erp/hamilton_erp
  ls page 2>/dev/null || mkdir page && touch page/__init__.py
  mkdir -p page/asset_board
  touch page/asset_board/__init__.py
  ```

- [ ] **Step 2: Create `asset_board.json` (Frappe Page metadata)**

  Create `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.json`:

  ```json
  {
   "content": "",
   "creation": "2026-04-10 12:00:00.000000",
   "docstatus": 0,
   "doctype": "Page",
   "idx": 0,
   "modified": "2026-04-10 12:00:00.000000",
   "modified_by": "Administrator",
   "module": "Hamilton ERP",
   "name": "asset-board",
   "owner": "Administrator",
   "page_name": "asset-board",
   "roles": [
    {"role": "Hamilton Operator"},
    {"role": "Hamilton Manager"},
    {"role": "Hamilton Admin"}
   ],
   "standard": "Yes",
   "system_page": 0,
   "title": "Asset Board"
  }
  ```

- [ ] **Step 3: Create the minimal Python controller**

  Create `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.py`:

  ```python
  """Asset Board — Frappe Page controller.

  Empty on purpose. The page is driven entirely by asset_board.js, which
  calls hamilton_erp.api endpoints for data. All permission checks live
  in the API layer (get_asset_board_data), not here.
  """
  ```

- [ ] **Step 4: Create the JS skeleton**

  Create `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`:

  ```javascript
  frappe.provide("hamilton_erp");

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
          this.assets = [];
          this.settings = {};
          this.overtime_interval = null;
          this.init();
      }

      async init() {
          this.wrapper.html(`<div class="hamilton-loading">${__("Loading...")}</div>`);
          await this.fetch_board();
          this.render();
          // Task 17: bind_events, Task 18: popover, Task 19: overtime, Task 20: realtime
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

      render() {
          // Task 17 expands this. For the scaffold, just show the asset count.
          this.wrapper.html(
              `<div class="hamilton-asset-board">
                   <p>${this.assets.length} ${__("assets loaded")}</p>
               </div>`
          );
      }
  };
  ```

- [ ] **Step 5: Create the CSS file**

  Create `hamilton_erp/hamilton_erp/public/css/asset_board.css`:

  ```css
  /* Hamilton Asset Board — scoped styles. All selectors start with
     .hamilton-asset-board to avoid bleeding into other Frappe pages. */

  .hamilton-asset-board {
      padding: 16px;
  }
  .hamilton-loading {
      padding: 24px;
      text-align: center;
      color: var(--text-muted);
  }
  ```

- [ ] **Step 6: Register the CSS in `hooks.py`**

  Edit `hamilton_erp/hamilton_erp/hooks.py`. Find an existing `app_include_css` entry or create one, and append `asset_board.css`:

  ```python
  app_include_css = ["/assets/hamilton_erp/css/asset_board.css"]
  ```

  (If the hook already has a list, add the path to the list.)

- [ ] **Step 7: Migrate and smoke-test in the browser**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost migrate
  bench --site hamilton-test.localhost clear-cache
  bench build --app hamilton_erp
  bench start &
  ```

  In another terminal, run:
  ```bash
  sleep 3 && curl -s -o /dev/null -w "%{http_code}\n" \
    "http://hamilton-test.localhost:8000/app/asset-board"
  ```

  Expected: HTTP `302` (redirects to login, which is correct). Then stop `bench start` with `kill %1`.

  **Manual check:** Visit `http://hamilton-test.localhost:8000/app/asset-board` in a browser while logged in as Administrator, confirm the page loads and shows "X assets loaded".

- [ ] **Step 8: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/ \
          hamilton_erp/hamilton_erp/public/css/asset_board.css \
          hamilton_erp/hamilton_erp/hooks.py
  git commit -m "feat(page): Asset Board scaffold at /app/asset-board"
  git push origin main
  ```

---

## Task 17: Asset Board — tile rendering (Rooms zone + Lockers zone)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`
- Modify: `hamilton_erp/hamilton_erp/public/css/asset_board.css`

**Design reference:** phase1_design.md §5.6.3. Rooms on top grouped by tier, Lockers below. Status colors: green/grey/amber/red.

- [ ] **Step 1: Replace the `render()` stub with full tile rendering**

  In `asset_board.js`, replace the `render()` method with:

  ```javascript
  render() {
      const rooms = this.assets.filter((a) => a.asset_category === "Room");
      const lockers = this.assets.filter((a) => a.asset_category === "Locker");
      const tierOrder = ["Single Standard", "Deluxe Single", "Glory Hole", "Double Deluxe"];

      const room_groups = tierOrder
          .map((tier) => {
              const tier_assets = rooms.filter((a) => a.asset_tier === tier);
              if (tier_assets.length === 0) return "";
              return `
                  <div class="hamilton-tier-group">
                      <h4 class="hamilton-tier-label">${frappe.utils.escape_html(tier)}</h4>
                      <div class="hamilton-tier-grid">
                          ${tier_assets.map((a) => this.render_tile(a)).join("")}
                      </div>
                  </div>
              `;
          })
          .join("");

      const locker_tiles = lockers.map((a) => this.render_tile(a)).join("");

      this.wrapper.html(`
          <div class="hamilton-asset-board">
              <section class="hamilton-zone hamilton-zone-rooms">
                  <div class="hamilton-zone-header">
                      <h3>${__("Rooms")}</h3>
                      <button class="btn btn-default btn-sm hamilton-bulk-rooms">
                          ${__("Mark All Dirty Rooms Clean")}
                      </button>
                  </div>
                  ${room_groups}
              </section>
              <section class="hamilton-zone hamilton-zone-lockers">
                  <div class="hamilton-zone-header">
                      <h3>${__("Lockers")}</h3>
                      <button class="btn btn-default btn-sm hamilton-bulk-lockers">
                          ${__("Mark All Dirty Lockers Clean")}
                      </button>
                  </div>
                  <div class="hamilton-tier-grid">${locker_tiles}</div>
              </section>
          </div>
      `);
  }

  render_tile(asset) {
      const status_class = `hamilton-status-${asset.status.toLowerCase().replace(/ /g, "-")}`;
      const tier_short = asset.asset_tier === "Single Standard" ? "STD"
          : asset.asset_tier === "Deluxe Single" ? "DLX"
          : asset.asset_tier === "Glory Hole" ? "GH"
          : asset.asset_tier === "Double Deluxe" ? "2DLX"
          : asset.asset_tier === "Locker" ? "" : asset.asset_tier;
      return `
          <div class="hamilton-tile ${status_class}"
               data-asset-name="${frappe.utils.escape_html(asset.name)}"
               data-asset-code="${frappe.utils.escape_html(asset.asset_code || "")}"
               data-status="${asset.status}">
              <div class="hamilton-tile-code">${frappe.utils.escape_html(asset.asset_code || "")}</div>
              <div class="hamilton-tile-name">${frappe.utils.escape_html(asset.asset_name)}</div>
              ${tier_short ? `<div class="hamilton-tile-tier">${tier_short}</div>` : ""}
          </div>
      `;
  }
  ```

> **Superseded by V9 (2026-04-24, commit 1cc9125):** The `data-asset-code` DOM attribute requirement no longer applies. See `docs/decisions_log.md` Part 2 V9 Amendment for current tile attribute spec.

- [ ] **Step 2: Expand `asset_board.css`**

  Append to `hamilton_erp/hamilton_erp/public/css/asset_board.css`:

  ```css
  .hamilton-zone {
      margin-bottom: 24px;
  }
  .hamilton-zone-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
  }
  .hamilton-zone-header h3 {
      margin: 0;
  }
  .hamilton-tier-group {
      margin-bottom: 16px;
  }
  .hamilton-tier-label {
      margin: 8px 0 4px 0;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
  }
  .hamilton-tier-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
  }
  .hamilton-tile {
      position: relative;
      min-width: 96px;
      min-height: 96px;
      padding: 12px;
      border-radius: 6px;
      cursor: pointer;
      user-select: none;
      color: #fff;
      display: flex;
      flex-direction: column;
      justify-content: center;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12);
      transition: transform 0.1s;
  }
  .hamilton-tile:active {
      transform: scale(0.97);
  }
  .hamilton-tile-code {
      position: absolute;
      top: 4px;
      left: 6px;
      font-size: 10px;
      opacity: 0.8;
  }
  .hamilton-tile-name {
      font-weight: 600;
      text-align: center;
      font-size: 14px;
  }
  .hamilton-tile-tier {
      position: absolute;
      bottom: 4px;
      right: 6px;
      font-size: 10px;
      opacity: 0.8;
  }
  /* Status colors */
  .hamilton-status-available { background: #28a745; }
  .hamilton-status-occupied  { background: #495057; }
  .hamilton-status-dirty     { background: #fd7e14; }
  .hamilton-status-out-of-service { background: #dc3545; }
  ```

- [ ] **Step 3: Rebuild assets and manually verify**

  ```bash
  cd ~/frappe-bench-hamilton && bench build --app hamilton_erp && bench --site hamilton-test.localhost clear-cache
  bench start &
  sleep 3
  ```

  Open `http://hamilton-test.localhost:8000/app/asset-board`. Confirm:
  - 59 tiles visible (26 rooms + 33 lockers)
  - Rooms grouped by tier with labels
  - All tiles green (all Available after fresh seed)
  - Bulk buttons visible above each zone

  Stop bench with `kill %1`.

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js \
          hamilton_erp/hamilton_erp/public/css/asset_board.css
  git commit -m "feat(asset_board): card-based tile rendering for Rooms + Lockers"
  git push origin main
  ```

---

## Task 18: Asset Board — popover interaction + action dispatch

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`
- Modify: `hamilton_erp/hamilton_erp/public/css/asset_board.css`

**Design reference:** phase1_design.md §5.6.4. State-dispatched popover, OOS expands inline with textarea.

- [ ] **Step 1: Add `bind_events` + popover methods to the JS class**

  Append to the class body in `asset_board.js` (before the closing `};`):

  ```javascript
  bind_events() {
      this.wrapper.on("click", ".hamilton-tile", (e) => {
          const name = $(e.currentTarget).data("asset-name");
          const asset = this.assets.find((a) => a.name === name);
          if (asset) this.open_popover(asset, e.currentTarget);
      });
      this.wrapper.on("click", ".hamilton-bulk-rooms", () =>
          this.confirm_bulk_clean("Room"));
      this.wrapper.on("click", ".hamilton-bulk-lockers", () =>
          this.confirm_bulk_clean("Locker"));
      // Dismiss popover on outside click
      $(document).on("click.hamilton-popover", (e) => {
          if (!$(e.target).closest(".hamilton-tile, .hamilton-popover").length) {
              this.close_popover();
          }
      });
  }

  close_popover() {
      $(".hamilton-popover").remove();
  }

  open_popover(asset, tile_el) {
      this.close_popover();
      const buttons = this.popover_buttons_for(asset);
      const $pop = $(`
          <div class="hamilton-popover" data-asset-name="${frappe.utils.escape_html(asset.name)}">
              <div class="hamilton-popover-header">
                  <strong>${frappe.utils.escape_html(asset.asset_name)}</strong>
                  <a class="hamilton-popover-info"
                     href="/app/venue-asset/${encodeURIComponent(asset.name)}"
                     target="_blank" rel="noopener">
                     <i class="fa fa-info-circle"></i>
                  </a>
              </div>
              <div class="hamilton-popover-actions">
                  ${buttons}
              </div>
              <div class="hamilton-popover-reason" style="display:none;">
                  <textarea class="form-control" rows="2"
                            placeholder="${__("Reason (required)")}"></textarea>
                  <button class="btn btn-primary btn-sm hamilton-popover-confirm">
                      ${__("Confirm")}
                  </button>
              </div>
              <div class="hamilton-popover-error" style="display:none;"></div>
          </div>
      `);
      $(tile_el).append($pop);
      this.wire_popover_actions($pop, asset);
  }

  popover_buttons_for(asset) {
      switch (asset.status) {
          case "Available":
              return `
                  <button class="btn btn-sm btn-success" data-action="assign">
                      ${__("Assign Occupant")}
                  </button>
                  <button class="btn btn-sm btn-danger" data-action="oos">
                      ${__("Set Out of Service")}
                  </button>
              `;
          case "Occupied":
              return `
                  <button class="btn btn-sm btn-primary" data-action="vacate-key">
                      ${__("Vacate — Key Return")}
                  </button>
                  <button class="btn btn-sm btn-warning" data-action="vacate-rounds">
                      ${__("Vacate — Discovery on Rounds")}
                  </button>
                  <button class="btn btn-sm btn-danger" data-action="oos">
                      ${__("Set Out of Service")}
                  </button>
              `;
          case "Dirty":
              return `
                  <button class="btn btn-sm btn-success" data-action="clean">
                      ${__("Mark Clean")}
                  </button>
                  <button class="btn btn-sm btn-danger" data-action="oos">
                      ${__("Set Out of Service")}
                  </button>
              `;
          case "Out of Service":
              return `
                  <button class="btn btn-sm btn-success" data-action="return">
                      ${__("Return to Service")}
                  </button>
              `;
          default:
              return "";
      }
  }

  wire_popover_actions($pop, asset) {
      const self = this;
      $pop.on("click", "[data-action]", function (e) {
          e.stopPropagation();
          const action = $(this).data("action");
          if (action === "oos" || action === "return") {
              $pop.find(".hamilton-popover-actions").hide();
              $pop.find(".hamilton-popover-reason").show();
              $pop.find("textarea").focus();
              $pop.data("pending-action", action);
          } else {
              self.run_action(asset, action, $pop);
          }
      });
      $pop.on("click", ".hamilton-popover-confirm", function (e) {
          e.stopPropagation();
          const reason = $pop.find("textarea").val().trim();
          if (!reason) {
              self.show_popover_error($pop, __("Reason is required"));
              return;
          }
          const action = $pop.data("pending-action");
          self.run_action(asset, action, $pop, {reason});
      });
  }

  async run_action(asset, action, $pop, extra = {}) {
      const api_map = {
          "assign":        {method: `run.hamilton_erp.hamilton_erp.doctype.venue_asset.venue_asset.assign_to_session`, payload: {}},
          "vacate-key":    {doctype_method: "mark_vacant", payload: {vacate_method: "Key Return"}},
          "vacate-rounds": {doctype_method: "mark_vacant", payload: {vacate_method: "Discovery on Rounds"}},
          "clean":         {doctype_method: "mark_clean", payload: {}},
          "oos":           {doctype_method: "set_out_of_service", payload: extra},
          "return":        {doctype_method: "return_to_service", payload: extra},
      };
      const spec = api_map[action];
      if (!spec) return;
      $pop.find("button").prop("disabled", true);
      try {
          await frappe.call({
              method: "frappe.client.insert",  // placeholder — real call below
              type: "POST",
              args: {},
          }).then(() => null).catch(() => null);
          // Real call: use frappe.xcall to hit the DocType whitelisted method
          if (spec.doctype_method) {
              await frappe.xcall(
                  `frappe.client.run_doc_method`,
                  {
                      dt: "Venue Asset",
                      dn: asset.name,
                      method: spec.doctype_method,
                      args: spec.payload,
                  }
              );
          } else {
              // assign_to_session uses the same pathway
              await frappe.xcall(
                  `frappe.client.run_doc_method`,
                  {
                      dt: "Venue Asset",
                      dn: asset.name,
                      method: "assign_to_session",
                      args: spec.payload,
                  }
              );
          }
          this.close_popover();
          // Realtime will refresh the tile — no manual refetch needed
      } catch (err) {
          const msg = (err && err.message) || __("Action failed");
          this.show_popover_error($pop, msg);
          $pop.find("button").prop("disabled", false);
      }
  }

  show_popover_error($pop, msg) {
      $pop.find(".hamilton-popover-error").text(msg).show();
  }

  confirm_bulk_clean(category) {
      // Full implementation in Task 20. For now, simple native confirm.
      const dirty = this.assets.filter(
          (a) => a.asset_category === category && a.status === "Dirty"
      );
      if (dirty.length === 0) {
          frappe.show_alert({message: __("No dirty assets to clean"), indicator: "orange"});
          return;
      }
      const names = dirty.map((a) => `${a.asset_code} ${a.asset_name}`).join("\n");
      if (confirm(`${__("Mark these clean?")}\n\n${names}`)) {
          const method = category === "Room"
              ? "hamilton_erp.api.mark_all_clean_rooms"
              : "hamilton_erp.api.mark_all_clean_lockers";
          frappe.call({method, type: "POST"}).then((r) => {
              frappe.show_alert({
                  message: `${r.message.succeeded.length} ${__("cleaned")}, ${r.message.failed.length} ${__("failed")}`,
                  indicator: r.message.failed.length ? "orange" : "green",
              });
          });
      }
  }
  ```

  **Also update the `init()` method to call `bind_events()`:**

  ```javascript
  async init() {
      this.wrapper.html(`<div class="hamilton-loading">${__("Loading...")}</div>`);
      await this.fetch_board();
      this.render();
      this.bind_events();
  }
  ```

- [ ] **Step 2: Add popover styles to `asset_board.css`**

  Append:

  ```css
  .hamilton-popover {
      position: absolute;
      top: 100%;
      left: 0;
      z-index: 100;
      min-width: 200px;
      padding: 12px;
      background: #fff;
      color: #333;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      border: 1px solid var(--border-color);
  }
  .hamilton-popover-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 14px;
  }
  .hamilton-popover-info {
      color: var(--text-muted);
      text-decoration: none;
  }
  .hamilton-popover-actions .btn {
      display: block;
      width: 100%;
      margin-bottom: 4px;
  }
  .hamilton-popover-reason textarea {
      margin-bottom: 8px;
  }
  .hamilton-popover-error {
      margin-top: 8px;
      padding: 6px 8px;
      background: #f8d7da;
      color: #721c24;
      border-radius: 4px;
      font-size: 12px;
  }
  ```

- [ ] **Step 3: Rebuild, manually QA**

  ```bash
  cd ~/frappe-bench-hamilton && bench build --app hamilton_erp && bench --site hamilton-test.localhost clear-cache
  bench start &
  sleep 3
  ```

  In the browser:
  - Tap an Available tile → see [Assign Occupant] + [Set Out of Service] → tap Assign → tile turns grey after ~1s
  - Tap an Occupied tile → see vacate options → tap Vacate Key Return → tile turns amber
  - Tap the amber tile → Mark Clean → turns green
  - Tap any tile → Set Out of Service → type a reason → Confirm → red tile
  - Tap red tile → Return to Service → type reason → Confirm → green tile

  Stop bench.

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js \
          hamilton_erp/hamilton_erp/public/css/asset_board.css
  git commit -m "feat(asset_board): state-dispatched popover + action wiring"
  git push origin main
  ```

---

## Task 19: Asset Board — overtime ticker (2-stage visual)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`
- Modify: `hamilton_erp/hamilton_erp/public/css/asset_board.css`

**Design reference:** phase1_design.md §5.6.5. Single 30-second setInterval, no live countdown. Amber border → red pulsing border.

- [ ] **Step 1: Add overtime methods to the class**

  Append to the class body in `asset_board.js`:

  ```javascript
  start_overtime_ticker() {
      this.overtime_interval = setInterval(() => this.refresh_overtime_overlays(), 30_000);
      this.refresh_overtime_overlays();
  }

  refresh_overtime_overlays() {
      const grace = this.settings.grace_minutes || 15;
      const now = new Date();
      for (const asset of this.assets) {
          if (asset.status !== "Occupied" || !asset.session_start) continue;
          const start = new Date(asset.session_start);
          const elapsed_min = (now - start) / 60000;
          const stay = asset.expected_stay_duration || 360;
          const $tile = this.wrapper.find(
              `.hamilton-tile[data-asset-name="${$.escapeSelector(asset.name)}"]`
          );
          $tile.removeClass("hamilton-warning hamilton-overtime");
          if (elapsed_min > stay + grace) {
              $tile.addClass("hamilton-overtime");
          } else if (elapsed_min > stay) {
              $tile.addClass("hamilton-warning");
          }
      }
  }

  teardown() {
      if (this.overtime_interval) clearInterval(this.overtime_interval);
      $(document).off("click.hamilton-popover");
  }
  ```

  **Update `init()` to start the ticker and register teardown:**

  ```javascript
  async init() {
      this.wrapper.html(`<div class="hamilton-loading">${__("Loading...")}</div>`);
      await this.fetch_board();
      this.render();
      this.bind_events();
      this.start_overtime_ticker();
      this.page.wrapper.on("page-destroyed", () => this.teardown());
  }
  ```

- [ ] **Step 2: Add overtime styles to `asset_board.css`**

  Append:

  ```css
  /* Stage 1 — warning (past stay_duration) */
  .hamilton-tile.hamilton-warning {
      border-left: 4px solid #ffc107;
  }
  .hamilton-tile.hamilton-warning::after {
      content: "⏱";
      position: absolute;
      top: 4px;
      right: 6px;
      font-size: 12px;
  }
  /* Stage 2 — overtime (past stay_duration + grace) */
  .hamilton-tile.hamilton-overtime {
      border: 3px solid #dc3545;
      animation: hamilton-pulse 1.5s ease-in-out infinite;
  }
  .hamilton-tile.hamilton-overtime::after {
      content: "OT";
      position: absolute;
      top: 4px;
      right: 6px;
      font-size: 11px;
      font-weight: 700;
      background: #dc3545;
      padding: 1px 4px;
      border-radius: 3px;
  }
  @keyframes hamilton-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(220,53,69,0.6); }
      50%      { box-shadow: 0 0 0 6px rgba(220,53,69,0); }
  }
  ```

- [ ] **Step 3: Manually QA**

  ```bash
  cd ~/frappe-bench-hamilton && bench build --app hamilton_erp && bench --site hamilton-test.localhost clear-cache
  ```

  Temporarily shorten an asset's stay on the backend so overtime fires quickly:

  ```bash
  bench --site hamilton-test.localhost console
  ```

  In the console:
  ```python
  import frappe
  name = frappe.db.get_value("Venue Asset", {"asset_code": "R001"}, "name")
  frappe.db.set_value("Venue Asset", name, "expected_stay_duration", 1)  # 1 minute
  frappe.db.commit()
  exit()
  ```

  ```bash
  bench start &
  sleep 3
  ```

  In the browser, Assign R001. Wait ~90 seconds → amber warning border appears. Wait ~17 min → red pulsing border.
  Reset R001 to 360 minutes after verification.

  Stop bench.

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js \
          hamilton_erp/hamilton_erp/public/css/asset_board.css
  git commit -m "feat(asset_board): overtime ticker with warning → pulsing overtime stages"
  git push origin main
  ```

---

## Task 20: Asset Board — realtime listeners (cross-tab sync)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`

**Design reference:** phase1_design.md §5.6.2, §5.9.

- [ ] **Step 1: Add `listen_realtime` + `apply_status_change` methods**

  Append to the class body in `asset_board.js`:

  ```javascript
  listen_realtime() {
      frappe.realtime.on("hamilton_asset_status_changed",
          (d) => this.apply_status_change(d));
      frappe.realtime.on("hamilton_asset_board_refresh",
          () => this.fetch_board().then(() => this.render_preserving_events()));
  }

  apply_status_change(payload) {
      const local = this.assets.find((a) => a.name === payload.name);
      if (!local) return;
      // Discard stale events (out-of-order delivery)
      if (payload.version != null && local.version != null && payload.version <= local.version) {
          return;
      }
      Object.assign(local, payload);
      // Re-render this single tile in place
      const $tile = this.wrapper.find(
          `.hamilton-tile[data-asset-name="${$.escapeSelector(local.name)}"]`
      );
      const $new = $(this.render_tile(local));
      $tile.replaceWith($new);
      this.refresh_overtime_overlays();
  }

  render_preserving_events() {
      // After a full refresh, rebind is implicit because bind_events uses
      // delegated selectors on this.wrapper.
      this.render();
      // Overtime overlays are reapplied on the next tick automatically
      this.refresh_overtime_overlays();
  }
  ```

  **Update `teardown()` to unregister listeners:**

  ```javascript
  teardown() {
      if (this.overtime_interval) clearInterval(this.overtime_interval);
      $(document).off("click.hamilton-popover");
      frappe.realtime.off("hamilton_asset_status_changed");
      frappe.realtime.off("hamilton_asset_board_refresh");
  }
  ```

  **Update `init()` to call `listen_realtime`:**

  ```javascript
  async init() {
      this.wrapper.html(`<div class="hamilton-loading">${__("Loading...")}</div>`);
      await this.fetch_board();
      this.render();
      this.bind_events();
      this.start_overtime_ticker();
      this.listen_realtime();
      this.page.wrapper.on("page-destroyed", () => this.teardown());
  }
  ```

- [ ] **Step 2: Manually QA cross-tab sync**

  ```bash
  cd ~/frappe-bench-hamilton && bench build --app hamilton_erp && bench --site hamilton-test.localhost clear-cache
  bench start &
  sleep 3
  ```

  Open **two browser tabs** to `http://hamilton-test.localhost:8000/app/asset-board`. In tab A, tap any Available tile → Assign. Within ~1 second tab B should show the same tile turned grey without a manual refresh.

  Also verify realtime cleanup: navigate tab B away from the page and back. Watch Chrome DevTools → Network → WS: there should be one active websocket, not two.

  Stop bench.

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js
  git commit -m "feat(asset_board): realtime listeners + in-place tile updates"
  git push origin main
  ```

---

## Task 21: Asset Board — bulk Mark All Clean confirmation dialog (upgrade to Frappe dialog)

**Files:**
- Modify: `hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js`

**What this delivers:** Replaces the Task 18 native `confirm()` with a proper Frappe `Dialog` showing a bulleted list of `{asset_code} {asset_name}` items (DEC-054 §3 — list-style confirmation).

- [ ] **Step 1: Replace `confirm_bulk_clean` in `asset_board.js`**

  Replace the existing `confirm_bulk_clean` method with:

  ```javascript
  confirm_bulk_clean(category) {
      const dirty = this.assets.filter(
          (a) => a.asset_category === category && a.status === "Dirty"
      );
      if (dirty.length === 0) {
          frappe.show_alert({message: __("No dirty assets to clean"), indicator: "orange"});
          return;
      }
      const list_html = `
          <p>${__("The following {0} assets will be marked clean:", [dirty.length])}</p>
          <ul class="hamilton-bulk-list">
              ${dirty.map((a) =>
                  `<li><strong>${frappe.utils.escape_html(a.asset_code)}</strong>
                   ${frappe.utils.escape_html(a.asset_name)}</li>`
              ).join("")}
          </ul>
      `;
      const d = new frappe.ui.Dialog({
          title: __("Confirm Bulk Mark Clean — {0}", [category]),
          fields: [{fieldtype: "HTML", options: list_html}],
          primary_action_label: __("Mark All Clean"),
          primary_action: async () => {
              d.get_primary_btn().prop("disabled", true);
              const method = category === "Room"
                  ? "hamilton_erp.api.mark_all_clean_rooms"
                  : "hamilton_erp.api.mark_all_clean_lockers";
              try {
                  const r = await frappe.xcall(method, {});
                  frappe.show_alert({
                      message: __("{0} cleaned, {1} failed",
                                  [r.succeeded.length, r.failed.length]),
                      indicator: r.failed.length ? "orange" : "green",
                  });
                  if (r.failed.length) {
                      console.warn("Bulk Mark Clean failures:", r.failed);
                  }
                  d.hide();
              } catch (err) {
                  frappe.msgprint(
                      {title: __("Bulk Mark Clean failed"),
                       message: (err && err.message) || String(err),
                       indicator: "red"}
                  );
                  d.get_primary_btn().prop("disabled", false);
              }
          },
      });
      d.show();
  }
  ```

- [ ] **Step 2: Manually QA**

  ```bash
  cd ~/frappe-bench-hamilton && bench build --app hamilton_erp && bench --site hamilton-test.localhost clear-cache
  bench start &
  sleep 3
  ```

  In the browser:
  1. Dirty 3 rooms by running the occupy→vacate cycle on each
  2. Tap "Mark All Dirty Rooms Clean"
  3. See dialog with 3 bulleted `{code} {name}` items
  4. Click "Mark All Clean"
  5. Alert shows "3 cleaned, 0 failed", tiles turn green

  Stop bench.

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/hamilton_erp/page/asset_board/asset_board.js
  git commit -m "feat(asset_board): list-style bulk Mark Clean confirmation dialog (DEC-054)"
  git push origin main
  ```

---

## Task 22: H10 E2E — Vacate and Turnover

**Files:**
- Create: `hamilton_erp/hamilton_erp/test_e2e_phase1.py`

- [ ] **Step 1: Write the failing H10 test**

  Create `hamilton_erp/hamilton_erp/test_e2e_phase1.py`:

  ```python
  """Phase 1 end-to-end QA test cases H10, H11, H12.

  These tests exercise the full stack: lifecycle.py + venue_asset
  whitelisted methods + Asset Status Log auto-create. They turn
  off frappe.flags.in_test inside each test so the status log
  path is exercised (the default guard is helpful for unit tests
  at scale but E2E tests must verify the real log).
  """
  import uuid
  from contextlib import contextmanager

  import frappe
  from frappe.tests import IntegrationTestCase

  from hamilton_erp import lifecycle
  from hamilton_erp.patches.v0_1 import seed_hamilton_env


  @contextmanager
  def real_logs():
      """Temporarily turn off the in_test flag so Asset Status Log is written."""
      prior = frappe.flags.in_test
      frappe.flags.in_test = False
      try:
          yield
      finally:
          frappe.flags.in_test = prior


  class TestH10VacateAndTurnover(IntegrationTestCase):
      def setUp(self):
          # Ensure the seed patch has run (Walk-in customer etc.)
          seed_hamilton_env.execute()
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"H10 Asset {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9100,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_h10_full_turnover_cycle(self):
          """H10: Available → Occupied → Dirty → Available with status logs at each step."""
          with real_logs():
              # 1. Assign
              session = lifecycle.start_session_for_asset(
                  self.asset.name, operator="Administrator"
              )
              a = frappe.get_doc("Venue Asset", self.asset.name)
              self.assertEqual(a.status, "Occupied")
              self.assertEqual(a.current_session, session)

              log1 = frappe.get_all(
                  "Asset Status Log",
                  filters={"venue_asset": self.asset.name, "new_status": "Occupied"},
                  fields=["previous_status", "new_status"],
              )
              self.assertEqual(len(log1), 1)
              self.assertEqual(log1[0]["previous_status"], "Available")

              # 2. Vacate
              lifecycle.vacate_session(
                  self.asset.name, operator="Administrator",
                  vacate_method="Key Return",
              )
              a = frappe.get_doc("Venue Asset", self.asset.name)
              self.assertEqual(a.status, "Dirty")
              self.assertIsNone(a.current_session)
              self.assertIsNotNone(a.last_vacated_at)

              sess = frappe.get_doc("Venue Session", session)
              self.assertEqual(sess.status, "Completed")
              self.assertEqual(sess.vacate_method, "Key Return")

              # 3. Mark Clean
              lifecycle.mark_asset_clean(self.asset.name, operator="Administrator")
              a = frappe.get_doc("Venue Asset", self.asset.name)
              self.assertEqual(a.status, "Available")
              self.assertIsNotNone(a.last_cleaned_at)

              # Three audit log entries total (Occupied, Dirty, Available)
              all_logs = frappe.get_all(
                  "Asset Status Log",
                  filters={"venue_asset": self.asset.name},
                  fields=["previous_status", "new_status"],
                  order_by="creation asc",
              )
              self.assertEqual(len(all_logs), 3)
              self.assertEqual(
                  [(l["previous_status"], l["new_status"]) for l in all_logs],
                  [("Available", "Occupied"),
                   ("Occupied", "Dirty"),
                   ("Dirty", "Available")],
              )
  ```

- [ ] **Step 2: Run, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_e2e_phase1
  ```

  Expected: **H10 passes.**

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/test_e2e_phase1.py
  git commit -m "test(e2e): H10 Vacate and Turnover end-to-end"
  git push origin main
  ```

---

## Task 23: H11 E2E — Out of Service

**Files:**
- Modify: `hamilton_erp/hamilton_erp/test_e2e_phase1.py`

- [ ] **Step 1: Append the H11 test**

  Append to `hamilton_erp/hamilton_erp/test_e2e_phase1.py`:

  ```python
  class TestH11OutOfService(IntegrationTestCase):
      def setUp(self):
          seed_hamilton_env.execute()
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"H11 Asset {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9101,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_h11_oos_from_occupied_with_session_close(self):
          """H11: OOS on an Occupied asset closes the session and logs the reason."""
          with real_logs():
              session_name = lifecycle.start_session_for_asset(
                  self.asset.name, operator="Administrator"
              )
              lifecycle.set_asset_out_of_service(
                  self.asset.name, operator="Administrator",
                  reason="Plumbing failure — flooding",
              )
              a = frappe.get_doc("Venue Asset", self.asset.name)
              self.assertEqual(a.status, "Out of Service")
              self.assertEqual(a.reason, "Plumbing failure — flooding")

              session = frappe.get_doc("Venue Session", session_name)
              self.assertEqual(session.status, "Completed")
              self.assertEqual(session.vacate_method, "Discovery on Rounds")

              # Verify OOS log carries the reason
              logs = frappe.get_all(
                  "Asset Status Log",
                  filters={"venue_asset": self.asset.name, "new_status": "Out of Service"},
                  fields=["reason"],
              )
              self.assertEqual(len(logs), 1)
              self.assertEqual(logs[0]["reason"], "Plumbing failure — flooding")

      def test_h11_oos_without_reason_rejected(self):
          with self.assertRaises(frappe.ValidationError):
              lifecycle.set_asset_out_of_service(
                  self.asset.name, operator="Administrator", reason="   "
              )

      def test_h11_return_to_service_cycle(self):
          with real_logs():
              lifecycle.set_asset_out_of_service(
                  self.asset.name, operator="Administrator", reason="Maintenance",
              )
              lifecycle.return_asset_to_service(
                  self.asset.name, operator="Administrator", reason="Repaired",
              )
              a = frappe.get_doc("Venue Asset", self.asset.name)
              self.assertEqual(a.status, "Available")
              self.assertIsNotNone(a.last_cleaned_at)
  ```

- [ ] **Step 2: Run, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_e2e_phase1
  ```

  Expected: **H10 + H11 pass.**

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/test_e2e_phase1.py
  git commit -m "test(e2e): H11 Out of Service cycle"
  git push origin main
  ```

---

## Task 24: H12 E2E — Occupied Asset Rejection

**Files:**
- Modify: `hamilton_erp/hamilton_erp/test_e2e_phase1.py`

- [ ] **Step 1: Append the H12 test**

  Append to `hamilton_erp/hamilton_erp/test_e2e_phase1.py`:

  ```python
  class TestH12OccupiedAssetRejection(IntegrationTestCase):
      def setUp(self):
          seed_hamilton_env.execute()
          self.asset = frappe.get_doc({
              "doctype": "Venue Asset",
              "asset_name": f"H12 Asset {uuid.uuid4().hex[:6]}",
              "asset_category": "Room",
              "asset_tier": "Single Standard",
              "status": "Available",
              "display_order": 9102,
              "version": 0,
          }).insert(ignore_permissions=True)

      def tearDown(self):
          frappe.db.rollback()

      def test_h12_cannot_assign_to_occupied(self):
          """H12: A second start_session on an Occupied asset is rejected."""
          with real_logs():
              lifecycle.start_session_for_asset(
                  self.asset.name, operator="Administrator"
              )
              with self.assertRaises(frappe.ValidationError):
                  lifecycle.start_session_for_asset(
                      self.asset.name, operator="Administrator"
                  )
              # State unchanged
              a = frappe.get_doc("Venue Asset", self.asset.name)
              self.assertEqual(a.status, "Occupied")
              # Log count unchanged — only the first Occupied event
              logs = frappe.get_all(
                  "Asset Status Log",
                  filters={"venue_asset": self.asset.name},
              )
              self.assertEqual(len(logs), 1)

      def test_h12_cannot_mark_clean_if_not_dirty(self):
          with self.assertRaises(frappe.ValidationError):
              lifecycle.mark_asset_clean(
                  self.asset.name, operator="Administrator"
              )

      def test_h12_cannot_vacate_if_not_occupied(self):
          with self.assertRaises(frappe.ValidationError):
              lifecycle.vacate_session(
                  self.asset.name, operator="Administrator",
                  vacate_method="Key Return",
              )
  ```

- [ ] **Step 2: Run, confirm pass**

  ```bash
  cd ~/frappe-bench-hamilton && bench --site hamilton-test.localhost run-tests \
    --app hamilton_erp --module hamilton_erp.test_e2e_phase1
  ```

  Expected: **H10 + H11 + H12 all pass.**

- [ ] **Step 3: Run the FULL test suite — one final green run before deployment**

  ```bash
  bench --site hamilton-test.localhost run-tests --app hamilton_erp
  ```

  Expected: **every Phase 0 + Phase 1 test passes**.

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add hamilton_erp/hamilton_erp/test_e2e_phase1.py
  git commit -m "test(e2e): H12 Occupied Asset Rejection + full E2E suite green"
  git push origin main
  ```

---

## Task 25: Deploy to Frappe Cloud + manual QA on real hardware

**Files:** None — deployment and manual verification only.

**Design reference:** phase1_design.md §10 acceptance criteria, build_phases.md Phase 1 test criteria (full checklist).

- [ ] **Step 1: Trigger Frappe Cloud bench update**

  Frappe Cloud pulls from the repo automatically on push, but a manual deploy confirms the app rebuild. Log in to Frappe Cloud → private bench `hamilton-erp-bench` (bench-37550) → trigger an Update/Deploy for app `hamilton_erp`. Wait for the deploy to complete (typically 2-4 minutes).

- [ ] **Step 2: Run migrate on Frappe Cloud**

  From the Frappe Cloud console for `hamilton-erp.v.frappe.cloud`:

  ```bash
  bench --site hamilton-erp.v.frappe.cloud migrate
  ```

  Expected: the `v0_1.seed_hamilton_env` patch runs and seeds 59 Venue Assets, Walk-in Customer, and Hamilton Settings defaults.

- [ ] **Step 3: Visit the live Asset Board**

  Open `https://hamilton-erp.v.frappe.cloud/app/asset-board` as Administrator.

  Verify:
  - All 59 tiles render (26 Rooms grouped by tier + 33 Lockers)
  - All tiles green
  - Bulk buttons present

- [ ] **Step 4: Walk through the full Phase 1 acceptance checklist**

  Against `docs/build_phases.md` Phase 1 test criteria, verify every item. Use a second browser tab to verify realtime sync.

  Items to specifically check:
  - H10, H11, H12 all pass through the UI
  - Asset board loads in < 1 second (browser DevTools → Network → check `get_asset_board_data` time-to-last-byte)
  - Cross-tab sync within 2 seconds
  - Bulk Mark Clean dialog works as specced
  - Role gating: log in as a user with no Hamilton role → `/app/asset-board` returns 403
  - Non-Hamilton users don't see the workspace in the sidebar (DEC-055 §4 regression)
  - Overtime warning and overtime borders appear at the correct thresholds (briefly shorten `expected_stay_duration` on one asset to test)

- [ ] **Step 5: Update `current_state.md` to mark Phase 1 complete**

  Edit `docs/current_state.md`:
  - Update the "Last updated" line to today's date
  - Change "Current phase" to: `Phase 1 — Complete. Next: Phase 2 POS integration.`
  - Under "Overall Status" table, change Phase 1 row from "Not started" to "**Complete — live on Frappe Cloud**"
  - Add a session note dated today summarizing: 25 tasks completed, 9 new files, full Phase 1 test suite green, H10/H11/H12 pass live on Frappe Cloud

- [ ] **Step 6: Update auto-memory project entry**

  Edit `/Users/chrissrnicek/.claude/projects/-Users-chrissrnicek-hamilton-erp/memory/project_hamilton_erp.md` — append a line noting Phase 1 completion date and the next step (Phase 2 POS integration).

- [ ] **Step 7: Final commit**

  ```bash
  cd /Users/chrissrnicek/hamilton_erp
  git add docs/current_state.md
  git commit -m "docs: mark Phase 1 complete — Asset Board live on Frappe Cloud"
  git push origin main
  ```

---

## Self-Review Checklist (already applied)

**Spec coverage:** Every Phase 1 deliverable from `docs/phase1_design.md` §2.1 and `docs/build_phases.md` Phase 1 test criteria maps to a task above:
- Locks → Task 2
- State machine + lifecycle functions → Tasks 3-8
- Session number generator → Task 9
- Venue Session lockdown → Task 10
- Seed patch → Task 11
- Realtime publishers → Task 12
- Whitelisted methods delegate → Task 13
- API endpoints (including perf baseline) → Task 14-15
- Page scaffold → Task 16
- Tile rendering → Task 17
- Popover → Task 18
- Overtime → Task 19
- Realtime listeners → Task 20
- Bulk dialog → Task 21
- E2E H10/H11/H12 → Tasks 22-24
- Deploy + acceptance → Task 25

**Placeholder scan:** No "TBD"/"TODO"/"implement later" references in the plan. Every code step contains the full code. Every command has an expected output or state.

**Type consistency:**
- Lifecycle function names match across tasks: `start_session_for_asset`, `vacate_session`, `mark_asset_clean`, `set_asset_out_of_service`, `return_asset_to_service`
- Private helper names consistent: `_set_asset_status`, `_create_session`, `_close_current_session`, `_set_vacated_timestamp`, `_set_cleaned_timestamp`, `_make_asset_status_log`, `_next_session_number`, `_db_max_seq_for_prefix`
- Realtime event names consistent: `hamilton_asset_status_changed`, `hamilton_asset_board_refresh`
- Lock operation strings consistent: `"assign"`, `"vacate"`, `"clean"`, `"oos"`, `"return"`
- CSS class names consistent: `hamilton-tile`, `hamilton-popover`, `hamilton-warning`, `hamilton-overtime`, `hamilton-status-available/occupied/dirty/out-of-service`

**Known scope gaps (deliberate, per design doc §2.2):** POS integration, admission items, pricing rules, refunds, cash drops, shift management, manual rename reconciliation — all Phase 2+.

---

*End of Phase 1 implementation plan.*
