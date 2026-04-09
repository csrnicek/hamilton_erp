# Hamilton ERP — Coding Standards

**Target Platform:** ERPNext v16 / Frappe Framework v16  
**Custom App Name:** `hamilton_erp`  
**App Module:** `Hamilton ERP`  
**Language:** Python 3.11+ (backend), JavaScript (frontend)  
**Database:** MariaDB (Frappe default)

---

## 1. Golden Rule

**Use standard ERPNext before writing custom code.**

Before building anything, ask: "Does standard ERPNext already do this?" If yes, use it. If it almost does it, extend it with Custom Fields, Client Scripts, or Server Scripts. Only create custom DocTypes, Pages, or controllers when there is no standard equivalent.

Refer to `hamilton_erp_build_specification.md` §1.2 for the complete list of features that **must not** be custom-built.

---

## 2. Frappe v16 Specific Requirements

Frappe v16 introduced breaking changes from v15. All code must comply with these.

### 2.1 Query Builder (Mandatory in v16)

`frappe.get_all()` and `frappe.get_list()` now use the query builder backend. Use the v16 aggregation syntax:

```python
# v16 aggregation syntax
frappe.db.get_list("Venue Session",
    fields=[{"COUNT": "name", "as": "count"}, "status"],
    group_by="status"
)
```

Do **not** use raw SQL (`frappe.db.sql`) unless absolutely unavoidable. If raw SQL is required, document why in a code comment.

### 2.2 POST for State-Changing Methods

All state-changing whitelisted methods must accept POST requests only. GET requests for state changes will fail in v16.

```python
@frappe.whitelist(methods=["POST"])
def mark_asset_vacant(asset_name):
    ...
```

### 2.3 IIFE JavaScript Loading

Page and Report JS files are now loaded as IIFEs (Immediately Invoked Function Expressions) in v16. Do not rely on global variable scope between files. All variables must be scoped within their module. If you must modify global scope, explicitly mutate the `window` object (not recommended).

### 2.4 Default Sort Order

v16 defaults list views to sort by `creation` instead of `modified`. This also affects database APIs — `frappe.get_all()` now implicitly sorts by `creation desc`, not `modified desc`. Design queries and UI expectations accordingly. Always use explicit `order_by` when ordering matters.

### 2.5 Desk Route Change

The desk frontend is routed at `/desk` in v16 (changed from `/app`). Use `frappe.set_route()` for navigation — do not hardcode URL paths.

### 2.6 Permission Check Signature Change

`frappe.permission.has_permission` no longer accepts the `raise_exception` parameter. Use `print_logs` instead.

### 2.7 Removed Whitelisted Methods

Several whitelisted methods for creating documents were removed in v16. Use `frappe.new_doc` on the frontend instead:

```javascript
// v16 — use frappe.new_doc instead of removed make_* methods
frappe.new_doc("Venue Session", { venue_asset: asset_name });
```

### 2.8 Document Hooks Cannot Commit

Document hooks set up via `hooks.py` can no longer commit a database transaction in v16. This change prevents data integrity issues. Do not call `frappe.db.commit()` inside doc_events hooks.

---

## 3. Hooks — Extending Standard ERPNext

Hooks are the primary mechanism for extending ERPNext without modifying core code. All hooks are defined in `hooks.py`.

### 3.1 Required Apps

The Hamilton app depends on ERPNext. Declare this in `hooks.py`:

```python
# hooks.py
required_apps = ["frappe", "erpnext"]
```

This ensures `bench install-app hamilton_erp` fails if ERPNext isn't installed first.

### 3.2 doc_events — Hooking into Standard DocType Lifecycle

This is the most important pattern for Hamilton. Use `doc_events` to run custom code when standard DocTypes (like Sales Invoice) are created, saved, or submitted:

```python
# hooks.py
doc_events = {
    "Sales Invoice": {
        "on_submit": "hamilton_erp.api.on_sales_invoice_submit",
    }
}
```

```python
# hamilton_erp/api.py
import frappe

def on_sales_invoice_submit(doc, method):
    """After POS Sales Invoice is submitted, check for admission items."""
    has_admission = any(
        item.get("hamilton_is_admission")
        for item in doc.items
    )
    if has_admission:
        # Trigger asset assignment flow
        frappe.publish_realtime(
            "show_asset_assignment",
            {"invoice": doc.name, "category": get_admission_category(doc)},
            user=frappe.session.user,
            after_commit=True
        )
```

**Key rules for doc_events:**
- The hooked function receives `(doc, method)` as arguments
- The original controller's method runs first, then your hook
- Use specific DocType names, not `"*"` wildcards — wildcards run on every DocType and hurt performance
- Do not call `frappe.db.commit()` inside doc_events (v16 prohibits this)
- Keep hooks lightweight — offload heavy work to background jobs via `frappe.enqueue()`

### 3.3 override_doctype_class — Extending Standard DocType Classes

When you need to add methods (not just hook into events) to a standard DocType, use `override_doctype_class`:

```python
# hooks.py
override_doctype_class = {
    "Sales Invoice": "hamilton_erp.overrides.sales_invoice.HamiltonSalesInvoice"
}
```

```python
# hamilton_erp/overrides/sales_invoice.py
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

class HamiltonSalesInvoice(SalesInvoice):
    def has_admission_item(self):
        return any(item.get("hamilton_is_admission") for item in self.items)
```

**Prefer `doc_events` over `override_doctype_class`** when you only need to react to events. Use `override_doctype_class` when you need to add reusable methods to the class.

### 3.4 after_install — Initial Data Setup

Use the `after_install` hook to seed default data when the app is first installed:

```python
# hooks.py
after_install = "hamilton_erp.setup.install.after_install"
```

```python
# hamilton_erp/setup/install.py
import frappe

def after_install():
    """Create default records after app installation."""
    create_default_roles()
    # Do NOT create Venue Assets here — those are configured per-site
```

### 3.5 Fixtures — Exporting Custom Fields, Roles, and Configuration

Fixtures are JSON files that get synced on `bench migrate`. They are the correct way to ship Custom Fields, Property Setters, and Roles with the app.

```python
# hooks.py
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["name", "like", "%-hamilton_%"]]
    },
    {
        "dt": "Property Setter",
        "filters": [["name", "like", "%-hamilton_%"]]
    },
    {
        "dt": "Role",
        "filters": [["name", "in", ["Hamilton Operator", "Hamilton Manager"]]]
    }
]
```

**Fixture gotchas:**
- Run `bench export-fixtures` to export from dev to JSON files in `fixtures/`
- Fixtures sync on `bench migrate` — Custom Fields are synced before data fixtures
- Use filters to export only YOUR app's custom fields — without filters, `bench export-fixtures` exports ALL custom fields from all apps
- Fixture ordering matters: Custom Fields must exist before data that references them
- Property Setters let you modify standard field properties (labels, visibility, read-only) without editing the DocType JSON

### 3.6 Scheduler Events

For periodic background tasks (e.g., overtime detection, stale session alerts):

```python
# hooks.py
scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "hamilton_erp.tasks.check_overtime_sessions"
        ]
    }
}
```

After changing scheduler events in `hooks.py`, run `bench migrate` for changes to take effect.

---

## 4. DocType Development Standards

### 4.1 Naming Conventions

| Element | Convention | Example |
|---|---|---|
| DocType name | Title Case with spaces | `Venue Asset`, `Cash Drop` |
| Field name (fieldname) | snake_case | `asset_category`, `session_start` |
| Python module | snake_case | `venue_asset`, `cash_drop` |
| JavaScript file | snake_case matching DocType | `venue_asset.js` |
| Custom fields on standard DocTypes | Prefixed with `hamilton_` | `hamilton_is_admission` |

### 4.2 DocType JSON Files

DocType definitions live in JSON files generated by the framework. **Never hand-edit DocType JSON** — use the DocType form in Developer Mode, then export. Exception: fixture-loaded data can be managed in JSON.

### 4.3 Controller Pattern

Every custom DocType must have a controller class, even if initially empty:

```python
# hamilton_erp/hamilton_erp/doctype/venue_asset/venue_asset.py

import frappe
from frappe.model.document import Document


class VenueAsset(Document):
    def validate(self):
        self.validate_status_transition()

    def validate_status_transition(self):
        """Enforce valid state transitions per build spec §5.1."""
        if self.has_value_changed("status"):
            old_doc = self.get_doc_before_save()
            if old_doc:
                valid = self._get_valid_transitions()
                old_status = old_doc.status
                if self.status not in valid.get(old_status, []):
                    frappe.throw(
                        f"Cannot transition from {old_status} to {self.status}"
                    )

    @staticmethod
    def _get_valid_transitions():
        return {
            "Available": ["Occupied", "Out of Service"],
            "Occupied": ["Dirty", "Out of Service"],
            "Dirty": ["Available", "Out of Service"],
            "Out of Service": ["Available"],
        }
```

### 4.4 Mandatory Controller Hooks

Use Frappe's controller hooks — not custom workarounds:

- `validate()` — input validation before save
- `before_save()` — derived field calculation
- `after_insert()` — post-creation side effects
- `on_update()` — post-save side effects
- `on_trash()` — cleanup before deletion
- `before_submit()` / `on_submit()` — for submittable DocTypes

### 4.5 Custom Fields on Standard DocTypes

When extending standard DocTypes (e.g., adding `is_admission` to Item):

- Use fixtures in `hooks.py`, not manual creation
- Prefix all custom fields with `hamilton_` to avoid namespace collisions
- Document every custom field in `current_state.md`
- Use `insert_after` to control field placement in the form

### 4.6 Property Setters on Standard DocTypes

To modify properties of existing standard fields (e.g., hiding a field, making it read-only, changing a label) without touching core code, use Property Setters:

```python
# Can be created programmatically in after_install or via fixtures
frappe.make_property_setter({
    "doctype": "POS Closing Entry",
    "fieldname": "",
    "property": "restrict_to_domain",
    "value": "Hamilton Manager Only",
})
```

Export Property Setters via fixtures alongside Custom Fields.

### 4.5 Cash Variance Logic — Three-Way Comparison

Cash Reconciliation uses a three-way blind comparison. The comparison reference is the **manager's physical count** (`actual_count`), not the operator's declaration. The logic must be:

```
manager_matches_operator = _within_tolerance(manager, operator)
manager_matches_system   = _within_tolerance(manager, system)

Clean:                    all three agree
Possible Theft or Error:  manager ≈ operator, but system differs
                          — OR — system ≈ operator, but manager found less
Operator Mis-declared:    manager ≈ system, but operator declared wrong amount
```

**Variance tolerance must be a percentage with a minimum floor, not a flat amount.** A flat $0.05 tolerance flags every real-world count — cash handling always has ±$1–2 rounding. Use 2% of the larger amount with a $1.00 minimum:

```python
_VARIANCE_TOLERANCE_PCT = 0.02
_VARIANCE_TOLERANCE_MIN = 1.00

def _within_tolerance(a, b):
    diff = abs(a - b)
    threshold = max(abs(a), abs(b)) * _VARIANCE_TOLERANCE_PCT
    return diff <= max(threshold, _VARIANCE_TOLERANCE_MIN)
```

**Always validate `actual_count` is not null before running variance.** `flt(None) = 0.0` — a missing count produces a fraudulent "Possible Theft or Error" flag.

**`_mark_drop_reconciled()` must run in `on_submit`, not `before_submit`.** If `before_submit` throws after `_mark_drop_reconciled` runs, the Cash Drop is marked reconciled but the Cash Reconciliation rolled back. `on_submit` fires only after full commit.

---

## 5. Data Migration (Patches)

### 5.1 patches.txt Structure

Every custom app has a `patches.txt` file with two sections:

```
[pre_model_sync]
# Patches here run BEFORE DocType schema changes are applied
# Use when you need old schema to migrate data

[post_model_sync]
# Patches here run AFTER DocType schema changes are applied
# Use for most data patches — no need to call frappe.reload_doc()
hamilton_erp.patches.v0_1.seed_default_venue_assets
```

### 5.2 Writing Patches

Patches are one-time scripts that run during `bench migrate`. They must be **idempotent** (safe to run multiple times):

```python
# hamilton_erp/patches/v0_1/seed_default_venue_assets.py

import frappe

def execute():
    """Seed initial venue assets if they don't exist."""
    if frappe.db.count("Venue Asset") > 0:
        return  # Already seeded — idempotent guard

    for i in range(1, 11):
        frappe.get_doc({
            "doctype": "Venue Asset",
            "asset_name": f"Room {i}",
            "asset_category": "Room",
            "asset_tier": "Standard",
            "status": "Available",
            "display_order": i,
        }).insert(ignore_permissions=True)

    frappe.db.commit()
```

### 5.3 Patch Rules

- Each patch runs exactly once — tracked in `tabPatch Log`
- Lines in `patches.txt` must be unique. To re-run a patch, add a comment suffix: `hamilton_erp.patches.v0_1.fix_data #2`
- Patches in `[pre_model_sync]` have access to the OLD schema — use `frappe.reload_doc()` if you need the new schema
- Patches in `[post_model_sync]` have access to the NEW schema — prefer this section
- Always test patches in a staging environment before production
- Frappe does not support reverse patches — if you need rollback, write a second patch

---

## 6. API and Whitelisted Methods

### 6.1 Whitelisting

All custom API endpoints must use `@frappe.whitelist()`:

```python
@frappe.whitelist(methods=["POST"])
def assign_asset_to_session(sales_invoice: str, asset_name: str) -> dict:
    """Assign a Venue Asset after POS payment is confirmed."""
    frappe.has_permission("Venue Asset", "write", throw=True)
    # ... implementation
```

### 6.2 Permission Checks

**Never skip permission checks.** Every whitelisted method must verify the caller has the required role or DocType permission:

```python
# Check DocType permission
frappe.has_permission("Venue Asset", "write", throw=True)

# Or check role directly
if not frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": "Hamilton Manager"}):
    frappe.throw("Only managers can reconcile cash drops")
```

### 6.3 Error Handling

Use `frappe.throw()` for user-facing errors. Use `frappe.log_error()` for backend errors that should not interrupt the user:

```python
# User-facing validation error
frappe.throw(_("Asset {0} is not Available").format(asset_name))

# Backend logging (does not interrupt user)
frappe.log_error(
    title="Cash Drop Label Print Failed",
    message=frappe.get_traceback()
)
```

### 6.4 Return Values

Whitelisted methods called from the frontend should return plain dictionaries, not Document objects:

```python
@frappe.whitelist(methods=["POST"])
def get_asset_board_data() -> dict:
    assets = frappe.get_all("Venue Asset",
        fields=["name", "asset_name", "asset_category", "asset_tier", "status",
                "current_session", "expected_stay_duration", "display_order"],
        order_by="display_order asc"
    )
    return {"assets": assets}
```

---

## 7. Frontend / Client-Side Standards

### 7.1 Client Scripts vs Pages

Use Client Scripts (`[doctype].js`) for form-level interactivity on DocType forms. Use custom Frappe Pages for full-screen custom UIs (asset board, cash drop screen, shift screens, manager reconciliation).

### 7.2 Frappe Call Pattern

Always use `frappe.call` for backend communication:

```javascript
frappe.call({
    method: "hamilton_erp.api.assign_asset_to_session",
    args: {
        sales_invoice: invoice_name,
        asset_name: selected_asset
    },
    freeze: true,
    freeze_message: __("Assigning asset..."),
    callback: function(r) {
        if (r.message) {
            // handle response
        }
    }
});
```

### 7.3 Realtime Updates

Use Frappe's built-in realtime pub/sub for the asset board (multi-terminal sync):

```python
# Server side — after asset status change
frappe.publish_realtime(
    "asset_status_changed",
    {"asset": asset_name, "new_status": new_status},
    after_commit=True  # IMPORTANT: only emit after DB transaction commits
)
```

```javascript
// Client side — asset board page listens
frappe.realtime.on("asset_status_changed", function(data) {
    update_tile(data.asset, data.new_status);
});
```

**Realtime targeting options:**
- `user="operator@hamilton.com"` — send to a specific user
- `doctype="Venue Asset", docname="Room 7"` — send to anyone viewing that document
- No targeting args — broadcasts to the entire site (use for asset board updates)

**Always use `after_commit=True`** for realtime events triggered by database changes. Without it, the client may receive the event before the DB transaction commits, causing stale reads.

**Document every realtime event as a contract.** The server payload keys and the client destructuring keys must match exactly. A key name change on either side silently breaks all connected clients. Add a comment above every `publish_realtime` call:

```python
# Realtime payload contract:
# event:    "asset_status_changed"
# payload:  {"asset": str, "new_status": str}
#           asset     — Venue Asset name (e.g. "Room 103")
#           new_status — one of: Available, Occupied, Dirty, Out of Service
frappe.publish_realtime("asset_status_changed", ...)
```

**Handle WebSocket disconnection.** If the realtime connection drops, the board will silently show stale data. Listen for disconnect/reconnect events and show a reconnecting indicator:

```javascript
frappe.realtime.on("disconnect", () => {
    this.board_container.style.opacity = "0.5";
    frappe.show_alert({ message: __("Board connection lost — reconnecting..."), indicator: "orange" });
});
frappe.realtime.on("connect", () => {
    this.board_container.style.opacity = "1.0";
    this.load_board();  // full refresh on reconnect
});
```

**Use event delegation for tile click handlers**, not direct element listeners. When realtime updates replace a tile's HTML, any handler attached directly to the old element is lost. A single delegated handler on the stable parent container survives all tile replacements:

```javascript
// Attach once to the stable container — works for all current and future tiles
this.board_container.addEventListener("click", (e) => {
    const tile = e.target.closest("[data-asset]");
    if (!tile) return;
    this.open_tile_modal(tile.dataset.asset);
});
```

**Disable action buttons after first tap.** Add a processing state to prevent double-submission:

```javascript
btn.disabled = true;
btn.textContent = __("Processing...");
frappe.call({...}).finally(() => {
    btn.disabled = false;
    btn.textContent = original_text;
});
```

**Always clean up listeners** when leaving a page:

```javascript
// When page is destroyed
frappe.realtime.off("asset_status_changed");
```

### 7.4 JavaScript Structure

Keep JavaScript modular. Each custom page should have a clear class structure:

```javascript
hamilton_erp.AssetBoard = class AssetBoard {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.init();
    }

    async init() {
        this.assets = await this.fetch_assets();
        this.render();
        this.bind_events();
        this.listen_realtime();
    }
    // ... methods
};
```

Use `const` and `let` (never `var`), arrow functions for callbacks, template literals for string interpolation, and `__()` for all translatable strings.

---

## 8. Security and Audit Standards

### 8.1 Never Trust the Client

All business logic validation must happen server-side. Client-side checks are for UX convenience only — they are not security boundaries.

### 8.2 Audit Trail

Every custom action must create a log entry using the custom DocTypes defined in the build spec (Asset Status Log, Comp Admission Log, etc.) — not `frappe.log_error()` for operational audit.

### 8.3 Audit Log Write Protection — CRITICAL

**The Asset Status Log must never be writeable by Hamilton Operator from the Frappe desk.** The API creates log entries with `ignore_permissions=True`. If operators have `create` or `write` permission on Asset Status Log, they can fabricate entries directly from the desk form, undermining the audit trail.

Rule: Hamilton Operator has `read=1` only on Asset Status Log. All writes go through the API.

### 8.5 Blind Cash Control — CRITICAL

**No API endpoint, no client script, and no report may expose expected cash totals to operator-role users.** The `system_expected` field on Cash Reconciliation must only be calculated and revealed **after** the manager submits their blind count. Code reviews must specifically verify this rule.

### 8.6 Submit Permissions for Submittable DocTypes

Any DocType that uses `before_submit` or `on_submit` lifecycle hooks is a **submittable document**. The role that should complete the submission must be granted `submit=1` explicitly in `_ensure_role_permission`. Without it, the role can open and edit the form but cannot submit it, and the controller logic in those hooks never runs.

Cash Reconciliation: Hamilton Manager requires `submit=1`.

### 8.7 Plain-Language Error Messages

Every `frappe.throw()` message must be readable by a hospitality operator with no technical background. Apply these rules before committing any message:

**Prohibited words and what to use instead:**

| Do NOT use | Use instead |
|---|---|
| "transition" | "change," "update," or omit |
| "Venue Asset" | "room or locker," "this room," "this locker" |
| "Asset Tier" | "Room Tier," "room type" |
| "Session End / Session Start" | "check-out time / check-in time" |
| "status" | omit or use the actual state name (Occupied, Available, etc.) |
| "Phase 2 not yet implemented" | "This feature is not yet available. Please contact your manager." |
| Any stack trace, exception class, or Python error text | Wrap in a friendly `frappe.throw()` before it reaches the client |

**Every message must include what to do next**, not just what went wrong:

```python
# Bad — states the problem, no action
frappe.throw("Asset not found")

# Good — states the problem, tells operator what to do
frappe.throw(f"'{asset_name}' was not found. Please refresh the board and try again.")
```

**Approved message templates for the asset board API:**

```python
# _load_asset() — asset does not exist
f"'{asset_name}' was not found. Please refresh the board and try again."

# _assert_status() — wrong state for start_session
f"'{asset_name}' is currently {asset.status} and cannot be checked in. Please refresh the board."

# _assert_status() — wrong state for mark_vacant
f"'{asset_name}' is not currently occupied."

# _assert_status() — wrong state for mark_clean
f"'{asset_name}' is not waiting to be cleaned."

# _assert_status() — wrong state for mark_available_from_oos
f"'{asset_name}' is not currently out of service."

# mark_oos — empty reason after strip
f"Please enter a reason for taking '{asset_name}' out of service."

# mark_available_from_oos — empty reason after strip
f"Please enter a reason for returning '{asset_name}' to service."

# Reason too long (both OOS methods)
"Reason is too long — please shorten it to 500 characters or fewer."
```

**Controller safety-net messages** (fire only if API pre-checks are bypassed): follow the same rules. Use the approved templates above as a reference.

---

## 9. Testing Standards

### 9.1 Unit Tests

Every custom DocType controller must have a corresponding test file:

```
hamilton_erp/hamilton_erp/doctype/venue_asset/test_venue_asset.py
```

### 9.2 Test Structure

```python
import frappe
from frappe.tests import IntegrationTestCase


class TestVenueAsset(IntegrationTestCase):
    def test_valid_status_transition(self):
        asset = frappe.get_doc({
            "doctype": "Venue Asset",
            "asset_name": "Test Room 1",
            "asset_category": "Room",
            "asset_tier": "Standard",
            "status": "Available"
        }).insert()

        asset.status = "Occupied"
        asset.save()  # should succeed

    def test_invalid_status_transition(self):
        asset = frappe.get_doc({
            "doctype": "Venue Asset",
            "asset_name": "Test Room 2",
            "asset_category": "Room",
            "asset_tier": "Standard",
            "status": "Available"
        }).insert()

        asset.status = "Dirty"
        self.assertRaises(frappe.ValidationError, asset.save)
```

### 9.3 Running Tests

Use bench to run tests:

```bash
# Run all tests for the hamilton_erp app
bench --site [site] run-tests --app hamilton_erp

# Run tests for a specific DocType
bench --site [site] run-tests --doctype "Venue Asset"

# Run a specific test module
bench --site [site] run-tests --module hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset
```

### 9.4 QA Test Coverage

The build spec §15 defines 22 QA test cases (H1–H22). Each must have a corresponding automated or manual test. Track coverage in `current_state.md`.

### 9.5 Pre-Commit Verification Protocol

**All three methods below are mandatory before committing any state-management code.** "State-management code" means any API method, controller hook, or frontend handler that creates, reads, updates, or transitions a document. If all three methods pass with no open issues, the code may be committed.

---

#### Method 1 — QA Test Case Walkthrough

Walk every applicable QA test case (§15 of the build spec, H1–H22) step-by-step against the actual code. Do not skim. Read the code line by line while tracing each test case.

**Steps:**

1. List every QA test case that touches the changed code (e.g., H1 for Asset Status Transitions, H4 for Session Lifecycle, H22 for Record Structure Integrity).
2. For each listed test case, trace the **exact user actions** described in the test through the code path end-to-end: frontend call → API method → helpers → database writes → realtime publish.
3. At each step, ask: "Does the code actually do what this test step requires?"
4. Record every step where the answer is "no," "maybe," or "I'm not sure." These are bugs.
5. Fix all recorded issues before proceeding to Method 2.

**What this finds:** Missing steps, wrong field names, mismatched assumptions between the test plan and the implementation.

---

#### Method 2 — State × Action Matrix

Enumerate every combination of (current state × API action) for every stateful DocType touched by the change. Each cell must have **explicit handling** — either a valid transition path or an explicit pre-check that raises a human-readable error. Implicit fallthrough is not acceptable.

**Steps:**

1. List all stateful DocTypes in scope (e.g., VenueAsset with states: Available, Occupied, Dirty, Out of Service).
2. List all API actions that operate on each DocType (e.g., `start_session`, `mark_vacant`, `mark_clean`, `mark_oos`, `mark_available_from_oos`).
3. Build a matrix: rows = current states, columns = API actions.
4. For each cell, verify the code explicitly handles it:
   - **Valid transition:** code performs the transition and all required side effects (session create/close, log entry, realtime notify).
   - **Invalid combination:** code raises `frappe.ValidationError` with a message that names the current state and the disallowed action (e.g., `"Cannot start a session on a room that is Dirty"`).
   - **Unreachable (document the reason):** note why and ensure no code path can reach it.
5. Any cell that falls through to a generic exception or produces no response is a bug.

**What this finds:** Unhandled state/action pairs, missing error messages, silent no-ops that leave documents in bad states.

---

#### Method 3 — Failure Injection

For every API method, inject a failure at each discrete step and trace what happens. The goal is to verify that no failure mode produces partial writes, orphaned records, or assets/sessions stuck in inconsistent states.

**Steps:**

1. List every API method in scope and decompose it into its discrete steps (the private helpers it calls, in order).
2. For each step, ask: "If this step raises an exception, what is the state of the database?"
   - Are there any documents already written that should not exist?
   - Is any document left in a transitional status (e.g., asset set to Occupied but no session created)?
   - Is any foreign-key reference (e.g., `current_session`) set to a non-existent record?
3. Verify that Frappe's transaction boundary (a single `db.commit()` at the end of a successful request) protects against partial writes. Confirm no intermediate `frappe.db.commit()` calls exist inside the method or its helpers (§2.8).
4. For each failure point that would produce a bad state, add an explicit guard or restructure the operation order so the failure leaves the database unchanged.
5. For client-side failures (network drop after frappe.call, modal open when realtime fires), verify the UI recovers gracefully: modal closes, tile updates, no stale state shown.

**What this finds:** Partial write bugs, orphaned records, race conditions between browser state and server state, violation of §2.8 (intermediate commits).

---

#### Method 4 — Concurrency Analysis

Simulate two operators performing the same action on the same asset at the same time and trace what happens at the database level.

**Steps:**

1. For each state-changing API method, ask: "What happens if this method is called twice concurrently on the same asset, before either call commits?"
2. Trace the interleaved execution: both calls read the same pre-change state, both pass the `_assert_status` check, both proceed to write.
3. For each concurrent scenario, determine: does the second write produce an orphaned record? A double-transition? An asset stuck in a transitional state?
4. Verify that a `FOR UPDATE` row-level lock is acquired on the asset row at the very start of `_load_asset`, before any state reads, and that this lock is held until the transaction commits.
5. Confirm no intermediate `frappe.db.commit()` calls exist (§2.8), which would prematurely release the lock.

**What this finds:** Double-create bugs (two Active sessions from one Available asset), orphaned records, lost-update races.

---

#### Method 5 — Permission Boundary Matrix

Build a matrix of (API method × permission type required) and verify each method checks the correct permission — not just any permission.

**Steps:**

1. List every whitelisted API method.
2. For each method, determine the correct permission type: `"read"` for data-fetching methods, `"write"` for state-changing methods.
3. Read the actual `frappe.has_permission()` call in the method. Does the permission type match what the method actually does?
4. For any method that checks `"write"` when it only reads, flag it — future read-only roles (display boards, reporting) will be incorrectly blocked.
5. Verify no state-changing method uses `"read"` (too permissive).

**What this finds:** Incorrect permission types that over-restrict read-only access or under-restrict write access.

---

#### Method 6 — Data Integrity Walk

Walk every field defined in every DocType schema (§9 of the build spec) and verify that every mandatory field is set by the code that creates or updates that document.

**Steps:**

1. For each API method that creates or updates a document, list the document's schema fields.
2. For each field marked as mandatory or audit-required in the spec, confirm the code explicitly sets it.
3. Pay special attention to: operator attribution fields (`operator_checkin`, `operator_vacate`, `operator`), timestamps, status fields, and link fields.
4. For each unset mandatory field, add the assignment to the appropriate helper.
5. Check API method signatures: does every parameter the spec requires actually appear in the function signature? A spec-required param that is never collected is always null.

**What this finds:** Null audit fields, missing parameters, incomplete document writes that pass Frappe validation but violate spec requirements.

---

#### Method 7 — Boundary Value Analysis

Test every numeric and time field with its extreme valid values: zero, null, negative, maximum, and values that straddle thresholds.

**Steps:**

1. List all numeric and datetime fields used in calculations: `expected_stay_duration`, `display_order`, `session_start`, `declared_amount`, `float_expected`, `float_actual`.
2. For each, test: null, 0, negative, extremely large.
3. For calculated values (overtime elapsed, float variance), test: result exactly at threshold, result just below, result just above.
4. For client-side calculations involving datetime arithmetic, test: value exactly now (elapsed = 0), value in the future (elapsed negative).
5. Fix any case where null or zero produces a TypeError, division-by-zero, or unintended immediate threshold trigger.
6. Add `Math.max(0, ...)` or `if not value: continue` guards where appropriate.

**What this finds:** TypeErrors from null arithmetic, zero-division, instant false-positive thresholds, negative display values.

---

#### Method 8 — Frontend Event Sequencing

Trace the lifecycle of every JavaScript timer, event listener, and async call across page show, page hide, and navigation back.

**Steps:**

1. List every `setInterval`, `setTimeout`, `frappe.realtime.on`, and `frappe.call` established in `on_page_load`.
2. For each, verify it is explicitly torn down in `on_page_hide`: `clearInterval`, `clearTimeout`, `frappe.realtime.off`.
3. Simulate: user opens the board, navigates away, comes back. Are there now two timers running? Two realtime listeners? Fix: store all handles on `this` and clear them in `on_page_hide`.
4. Simulate: user opens the board, opens a modal, navigates away (page hides), comes back. Is the modal still open? Should it be?
5. Simulate: a `frappe.call` is in-flight when `on_page_hide` fires. When the call resolves, does the callback safely handle DOM elements that may have been reset?

**What this finds:** Timer accumulation on repeated navigation (memory/CPU leak), duplicate realtime listeners, callbacks operating on stale page state.

---

#### Method 9 — Database Constraint Verification

Verify that every Link field relationship is protected against deletion of the referenced record, and that every sort-critical field has a defined default and tiebreaker.

**Steps:**

1. List every Link field in every DocType. For each, ask: "What happens if the linked record is deleted?"
2. If the linked record being deleted would leave an orphaned Active document (e.g., deleting a Venue Asset with an Active Venue Session), add an `on_trash` guard in the referenced DocType's controller.
3. For every `order_by` clause in `frappe.get_all()`, verify: (a) the sort field has a defined non-null default, and (b) there is a deterministic tiebreaker (e.g., `, name asc`) so ordering is consistent when sort values are equal.
4. Verify no `order_by` field can be null at query time; add field defaults where needed.

**What this finds:** Orphaned Active records from deleted parents, non-deterministic sort order, null sort values producing DB-implementation-defined ordering.

---

#### Method 10 — Scheduler Resilience

Verify that scheduled tasks fail gracefully per-item and use the correct event names for any realtime signals they emit.

**Steps:**

1. For every scheduled task that iterates a list of records, wrap the per-record processing in try/except. A single bad record must not abort the entire run.
2. In the except block, call `frappe.log_error(frappe.get_traceback(), "descriptive label")` so the failure is visible in the Error Log, then `continue`.
3. For any `publish_realtime` call inside a scheduler task, verify the event name is appropriate: does the event name accurately describe what changed? If a scheduler task checks for overtime but the asset's `status` field has not changed, it must NOT emit "asset_status_changed" — that would trigger client handlers designed for real status changes (including modal-close logic).
4. Use a distinct event name for each distinct type of state change. Scheduler-initiated signals should use names like `"asset_overtime_started"`, not reuse `"asset_status_changed"`.

**What this finds:** Silent partial failures in scheduler loops, wrong event names triggering unintended client-side actions (e.g., open modals being closed).

---

#### Method 11 — Clock/Timezone Testing

Trace every datetime value from DB storage through API serialization to JavaScript consumption and verify UTC is preserved end-to-end.

**Steps:**

1. Frappe stores all datetimes in UTC as strings in the format `"YYYY-MM-DD HH:MM:SS"` (no timezone suffix).
2. Find every place the JS client receives a datetime string from the server (e.g., `session_start` from `get_asset_board_data`).
3. Check how the client parses it: `new Date("2026-04-08 19:30:00")`. Per ECMAScript spec, a datetime string with a space separator and no timezone designator is parsed as **local time** in Chrome, Firefox, and Safari — NOT UTC.
4. Fix: post-process the string on the server before returning it, replacing the space with "T" and appending "Z": `session_start.replace(" ", "T") + "Z"`. This forces all browsers to parse it as UTC.
5. Alternatively, return Unix timestamps (milliseconds) from the server and let the client use them directly.
6. Test: set your browser to a non-UTC timezone. Verify overtime calculations still produce the correct elapsed time.

**What this finds:** Elapsed time calculations wrong by the server-client UTC offset (up to ±12 hours), causing overtime to never show or show immediately.

---

#### Method 12 — API Response Contract

Verify every API method returns a consistent, documented value that client callbacks can safely inspect.

**Steps:**

1. List every whitelisted API method and its current return value (or lack of one).
2. For every method that currently returns `None` (Python implicit return), the client receives `r.message = undefined`. Any client code doing `r.message.field` throws TypeError.
3. Standardize: all state-change methods must return `{"status": "ok", "asset": asset_name, "new_status": new_status}`.
4. For data-fetching methods, verify the return shape matches what the client destructures.
5. If a method can return different shapes in success vs. error paths, ensure the error path always raises a Frappe exception rather than returning a null/empty value — exceptions produce structured error responses the client's error callback receives.

**What this finds:** Client callbacks that crash on `undefined`, inconsistent response shapes across methods, silent failures that look like success.

---

#### Method 13 — Input Validation / Adversarial Input

For every string parameter in every API method, test: empty after strip, whitespace-only, extremely long, and type-unexpected values.

**Steps:**

1. List every string parameter in every whitelisted API method: `asset_name`, `reason`, `vacate_method`.
2. For free-text parameters (`reason`): verify (a) empty/whitespace is rejected, (b) a maximum length is enforced (500 characters is a reasonable default for reason fields). No limit means a single API call could write megabytes to a log table.
3. For Select parameters (`vacate_method`): Frappe validates Select options on `doc.save()`, so type-checking is handled. Confirm this by reading the DocType field definition.
4. For Link parameters (`asset_name`): verify `frappe.db.exists()` is called before `frappe.get_doc()` (already required by Method 3, failure injection). SQL injection is not possible through Frappe's ORM, but empty strings still need to be caught.
5. Add length guards immediately after the `.strip()` call: `if len(reason) > 500: frappe.throw("Reason must be 500 characters or fewer")`.

**What this finds:** Oversized strings written to the database, missing guards on free-text parameters.

---

#### Checklist

Before every commit of state-management code, confirm all 13 methods are complete:

- [ ] Method 1 — QA test case walkthrough: all applicable cases traced, all gaps fixed
- [ ] Method 2 — State × action matrix: all cells explicitly handled
- [ ] Method 3 — Failure injection: no partial-write paths remain
- [ ] Method 4 — Concurrency: row-level lock in `_load_asset`, no concurrent double-transitions
- [ ] Method 5 — Permission boundary: read methods use `"read"`, write methods use `"write"`
- [ ] Method 6 — Data integrity walk: all mandatory/audit fields set in all create/update paths
- [ ] Method 7 — Boundary values: null/zero guards on all numeric calculations and datetime arithmetic
- [ ] Method 8 — Frontend event sequencing: all timers and listeners torn down in `on_page_hide`
- [ ] Method 9 — DB constraints: `on_trash` guards for all Active-session parents; deterministic sort with tiebreaker
- [ ] Method 10 — Scheduler resilience: per-record try/except; distinct event names for distinct change types
- [ ] Method 11 — Clock/timezone: all `session_start` strings returned with "T" + "Z" suffix
- [ ] Method 12 — API response contract: all state-change methods return `{"status": "ok", "asset": ..., "new_status": ...}`
- [ ] Method 13 — Input validation: 500-char limit on all free-text params; empty-after-strip rejected

---

#### Method 14 — Static Analysis

Read the code without running it. Check every `frappe.get_all()` call for `order_by`, every `@frappe.whitelist` for correct `methods=`, every raw SQL call for a §2.1 justification comment.

**Steps:**

1. Scan every `frappe.get_all()` and `frappe.get_list()` call in the codebase. Any call missing an explicit `order_by` violates §2.4 and must be fixed.
2. Scan every `@frappe.whitelist` decorator in `api.py`. Any state-changing method missing `methods=["POST"]` violates §2.2. Run this grep check:
   ```bash
   grep -n "@frappe.whitelist" hamilton_erp/api.py | grep -v 'methods=\["POST"\]'
   ```
   The only acceptable output is the read-only method (`get_asset_board_data`). Any other hit is a bug.
3. Scan every `frappe.db.sql()` call. Each must have a comment above it explaining why the ORM is insufficient (§2.1).
4. Run Ruff against all Python files. Zero warnings permitted before commit.
5. For JavaScript: scan for any `element.addEventListener` called directly on a tile or dynamically-rendered element (not the stable parent container). These handlers are lost when realtime replaces the element's HTML. All tile interaction must use event delegation on a stable ancestor.

**What this finds:** Missing `order_by` (non-deterministic queries), missing `methods=["POST"]` (GET-accessible state-change endpoints), undocumented raw SQL, Ruff violations, JS click handlers that break on realtime update.

---

#### Method 15 — Unit Testing

Write a unit test for every atomic piece of logic: every private helper, every guard, every validation. Read coverage after running tests — any untested function in `api.py`, `utils.py`, or any controller is a gap.

**Steps:**

1. After adding or modifying any controller method (including `on_trash` guards), add a corresponding test before committing.
2. For `on_trash` guards: test the guard fires when an Active session exists, and does NOT fire when no session exists.
3. For every audit field (e.g., `operator_vacate`, `operator_checkin`): after the relevant API call, reload the document from DB and assert the field is not null.
4. For test document names: never use hardcoded strings like `"Test Room 1"`. Use `frappe.generate_hash(length=6)` as a suffix and add `addCleanup(doc.delete)` to tear down after each test. Hardcoded names cause `DuplicateEntryError` on the second test run.
5. Run: `bench --site [site] run-tests --app hamilton_erp`. Zero failures before commit.

**What this finds:** Guards with no regression test (invisible until a refactor breaks them), audit fields left null in production, flaky tests from name collisions on re-run.

---

#### Method 16 — Integration Testing

Test multiple components end-to-end together: API method → all helpers → database commits → return value. Use `IntegrationTestCase` against a real Frappe site.

**Steps:**

1. For every multi-step API method (any method that makes more than one document write), write one integration test that asserts ALL writes committed correctly.
2. The "OOS from Occupied" test must check all four writes in one assertion block: `asset.status`, `asset.current_session`, `session.status`, `Asset Status Log` entry.
3. For every log entry written during a transition, assert `log.previous_status` reflects the state BEFORE the transition — not the state after. This verifies that `old_status` was captured before `_transition_asset` was called.
4. Document concurrency tests explicitly as out-of-scope for `IntegrationTestCase` (which uses a single DB connection). Add a code comment in `_load_asset` noting the row lock is verified by code review, not automated test.

**What this finds:** Partial writes (some commits succeeded, others didn't), wrong `previous_status` in audit logs (old_status captured after mutation), missing writes discovered only when all four assertions run together.

---

#### Method 17 — E2E / UI Testing

Drive a real browser (Playwright) through the full operator workflow. Check for interaction bugs that only appear when HTML, JS, and server are running together.

**Steps:**

1. **Event delegation test:** Open the board. Trigger a realtime update for any tile (call an API method from a second connection). Tap the updated tile. It must open a modal. If it does nothing, click handlers are not using event delegation — fix.
2. **Backdrop dismiss test:** Open a tile modal. Click outside the dialog (on the board background). Verify the modal does NOT close silently. The dialog must use `backdrop: "static"`.
3. **Rapid navigation test:** Open the board. Navigate away immediately (before `load_board()` finishes). Navigate back. Tap a tile. Verify: only one modal appears (no duplicate dialogs), only one `setInterval` is running (check `this._overtime_interval` is not accumulating).
4. **Overtime overlay test:** Set `expected_stay_duration` to 1 minute. Start a session. Wait 90 seconds. Verify the overtime ring and badge appear on the correct tile without a page reload.
5. **Realtime multi-terminal test:** Open the board in two browser tabs. In tab 1, mark a room OOS. Verify tab 2's tile updates within 2 seconds without tab 2 doing anything.

**What this finds:** Click handlers lost after realtime HTML replacement, accidental modal dismissal on backdrop tap, timer accumulation from repeated navigation, overtime overlay not appearing, realtime not propagating to all connected clients.

---

#### Method 18 — Load Testing

Simulate multiple concurrent users and rapid event bursts. Check for query amplification, render races, and timer accumulation under volume.

**Steps:**

1. **Concurrent `load_board()` guard test:** Simulate 8 realtime events arriving simultaneously on a board that has not yet finished its initial `load_board()` call. Verify that at most ONE `get_asset_board_data` API call is in-flight at any time. Implement with a `this._loading` flag in `load_board()` that blocks re-entry.
2. **N+1 query check for scheduler:** Review `check_overtime_sessions()`. If it loads each asset individually inside the loop (one DB call per session), refactor to a single query using a joined field or a second `frappe.get_all()` call keyed by asset name, run once before the loop.
3. **Realtime burst test:** Fire 10 concurrent `start_session` calls (on 10 different available assets). Verify: 10 sessions created, 10 assets set to Occupied, 0 orphaned sessions, 10 realtime events delivered to all connected clients.
4. **Board render scale test:** Configure all 59 assets. Load the board. Measure time from `on_page_load` to all 59 tiles rendered. Verify no individual tile query is made per tile — all data is fetched in 2 batch queries.

**What this finds:** Concurrent `load_board()` races during page load, N+1 query patterns in the scheduler, orphaned sessions from concurrent start calls (validates Bug 15 row lock fix works end-to-end), per-tile queries masquerading as a board load.

---

#### Checklist

Before every commit of state-management code, confirm all 18 methods are complete:

- [ ] Method 1 — QA test case walkthrough: all applicable cases traced, all gaps fixed
- [ ] Method 2 — State × action matrix: all cells explicitly handled
- [ ] Method 3 — Failure injection: no partial-write paths remain
- [ ] Method 4 — Concurrency: row-level lock in `_load_asset`, no concurrent double-transitions
- [ ] Method 5 — Permission boundary: read methods use `"read"`, write methods use `"write"`
- [ ] Method 6 — Data integrity walk: all mandatory/audit fields set in all create/update paths
- [ ] Method 7 — Boundary values: null/zero guards on all numeric calculations and datetime arithmetic
- [ ] Method 8 — Frontend event sequencing: all timers and listeners torn down in `on_page_hide`
- [ ] Method 9 — DB constraints: `on_trash` guards for all Active-session parents; deterministic sort with tiebreaker
- [ ] Method 10 — Scheduler resilience: per-record try/except; distinct event names for distinct change types
- [ ] Method 11 — Clock/timezone: all `session_start` strings returned with "T" + "Z" suffix
- [ ] Method 12 — API response contract: all state-change methods return `{"status": "ok", "asset": ..., "new_status": ...}`
- [ ] Method 13 — Input validation: 500-char limit on all free-text params; empty-after-strip rejected
- [ ] Method 14 — Static analysis: Ruff clean; every `get_all` has `order_by`; every state-change `whitelist` has `methods=["POST"]`; raw SQL documented; JS uses event delegation
- [ ] Method 15 — Unit testing: `on_trash` guards tested; audit fields asserted after each write; no hardcoded doc names; zero test failures
- [ ] Method 16 — Integration testing: multi-write transactions verified atomically; `previous_status` asserted in logs; concurrency gap documented
- [ ] Method 17 — E2E/UI: tile tappable after realtime update; modal uses `backdrop: static`; no timer accumulation; overtime overlay appears; realtime propagates to all tabs
- [ ] Method 18 — Load testing: `load_board()` guarded against concurrent calls; no N+1 in scheduler; concurrent start_session leaves zero orphaned sessions
- [ ] Method 19 — False positive audit: run all checks in §9.6 below
- [ ] All fixes from all methods are in the same commit

---

### 9.6 False Positive Audit Checklist

Run this after the 18-method pre-commit checklist passes. These checks look for code that appears correct but silently produces wrong results at runtime.

**FP-1 — Vacuous tests:** For every test that iterates a query result (`for row in rows: assert...`), verify the test also asserts `len(rows) > 0` (or equivalent). A loop that executes zero times always passes. Security tests in particular must have at least one assertion that fires unconditionally.

**FP-2 — Guard against blank function arguments:** Any utility function that takes a foreign key or identifier parameter (`shift_record`, `venue_asset`, `operator`) must throw immediately if that argument is blank rather than silently querying against NULL/empty. `frappe.db.count("DocType", {"field": None})` counts records with a null value, not all records — this is a silent wrong-answer scenario.

**FP-3 — flt(None) masking:** Trace every `flt(self.fieldname)` call. If the field is not `reqd=1` in the DocType JSON, `flt(None)` returns `0.0` silently. Confirm either (a) the field is `reqd=1` so null cannot be stored, or (b) a prior explicit null check throws before `flt()` is reached.

**FP-4 — is_submittable + hooks:** For every controller with `before_submit` or `on_submit`, confirm `is_submittable: 1` is in the DocType JSON. A controller can have these methods and compile cleanly; if the JSON flag is missing they will never fire.

**FP-5 — Custom DocPerm overrides JSON:** `install.py` creates `Custom DocPerm` rows. In Frappe, a Custom DocPerm row for a role+doctype pair **replaces** (not supplements) the DocType JSON permission row for that role. If `install.py` creates a row with `submit=0` for a submittable DocType, it overrides the JSON's `submit=1`. Verify that every is_submittable DocType has `submit=1` in both the JSON permission row and the `_ensure_role_permission` call.

**FP-6 — Select field code/JSON alignment:** For every string assigned to a Select field in Python (`self.variance_flag = "Clean"`), confirm the exact string appears in that field's `options` list in the DocType JSON. A mismatched string is silently stored but will fail DocType validation on re-save.

**FP-7 — sort_field nullability:** Every DocType `sort_field` must be either `reqd: 1` or have an explicit `default` value. In MySQL, `ORDER BY nullable_col ASC` places NULL rows first, corrupting list view order unpredictably.

**FP-8 — db.set_value bypasses validate():** Any `frappe.db.set_value(doctype, name, 'status', value)` call bypasses `validate()` entirely, including state machine checks. Confirm no Hamilton code uses `db.set_value` to change status fields. State changes must always go through `doc.save()`.

---

## 10. App File Structure

```
hamilton_erp/
├── hamilton_erp/
│   ├── __init__.py
│   ├── hooks.py
│   ├── api.py                          # Shared whitelisted methods
│   ├── utils.py                        # Shared utility functions
│   ├── patches.txt                     # Data migration patches
│   ├── patches/                        # Patch scripts directory
│   │   └── v0_1/
│   ├── fixtures/                       # Exported custom fields, roles, etc.
│   ├── setup/
│   │   └── install.py                  # after_install hook
│   ├── overrides/                      # override_doctype_class modules
│   │   └── sales_invoice.py
│   ├── hamilton_erp/                   # Module directory
│   │   ├── doctype/
│   │   │   ├── venue_asset/
│   │   │   │   ├── venue_asset.json
│   │   │   │   ├── venue_asset.py
│   │   │   │   ├── venue_asset.js
│   │   │   │   └── test_venue_asset.py
│   │   │   ├── venue_session/
│   │   │   ├── cash_drop/
│   │   │   ├── cash_reconciliation/
│   │   │   ├── asset_status_log/
│   │   │   ├── shift_record/
│   │   │   └── comp_admission_log/
│   │   └── page/
│   │       ├── asset_board/
│   │       ├── cash_drop_screen/
│   │       ├── shift_start/
│   │       ├── shift_close/
│   │       └── manager_reconciliation/
│   ├── public/
│   │   ├── css/
│   │   └── js/
│   └── templates/
├── pyproject.toml
├── setup.py
├── requirements.txt
├── license.txt
└── README.md
```

---

## 11. Code Style

These align with the official ERPNext coding standards (see `reference_links.md` for the wiki URL).

### Python
- **Tabs, not spaces** — this is Frappe/ERPNext's convention. Do not change it.
- **Double quotes** for strings (`"hello"` not `'hello'`) — matches Ruff formatter config
- **Maximum line length: 110 characters** — matches ERPNext's `pyproject.toml` Ruff config
- Type hints on function signatures
- f-strings for formatting (not `.format()` or `%`)
- Always `import frappe` at the top — never `from frappe import *`
- **Import ordering:** stdlib → third-party → frappe → local app:
  ```python
  import json
  from datetime import datetime

  import frappe
  from frappe import _
  from frappe.utils import flt, cint

  from hamilton_erp.utils import get_asset_by_category
  ```

### Function Design
- **Functions should do one thing.** Break up functions longer than ~10 lines into smaller, focused helpers.
- **Calling function above, called function below** — the top-level flow reads top-down:
  ```python
  def process_checkin(doc):
      validate_admission(doc)
      create_session(doc)

  def validate_admission(doc):
      ...

  def create_session(doc):
      ...
  ```
- **Code comments explain "why", not "how"** — the code itself should be readable enough to explain how. Comments are for business context and non-obvious decisions.

### SQL Safety
- **Never use `.format()` or f-strings in raw SQL** — this is an injection vulnerability:
  ```python
  # WRONG — SQL injection risk
  frappe.db.sql(f"SELECT name FROM tabUser WHERE name='{user}'")

  # RIGHT — parameterized
  frappe.db.sql("SELECT name FROM tabUser WHERE name=%s", user)
  ```
- Prefer the Frappe ORM over raw SQL in all cases.

### Query Performance
- **Always specify `fields`** in `get_all` / `get_list` — never fetch all columns:
  ```python
  # WRONG — fetches entire row
  frappe.get_all("Venue Asset")

  # RIGHT — fetch only what you need
  frappe.get_all("Venue Asset", fields=["name", "status"], limit_page_length=50)
  ```
- Use `frappe.enqueue()` to offload heavy work from hooks to background jobs:
  ```python
  def on_submit(doc, method):
      # Don't do heavy processing in the hook — enqueue it
      frappe.enqueue("hamilton_erp.tasks.process_shift_close", doc_name=doc.name)
  ```

### Deprecated APIs — Do Not Use
These are legacy and must not appear in Hamilton code:
- `cur_frm` — use the `frm` parameter passed to form event handlers
- `$c_obj()` — use `frappe.call()`
- `get_query` / `add_fetch` — use modern equivalents (`set_query`, `fetch_from`)

### JavaScript
- `const` / `let` only — never `var`
- Arrow functions for callbacks
- Template literals for string interpolation
- `__()` wrapping all user-facing strings
- Avoid `cur_frm` — always use the `frm` argument from form handlers

### Commit Messages
Follow conventional commits (https://www.conventionalcommits.org):
```
feat(asset-board): add overtime overlay indicator
fix(cash-drop): prevent label print when amount is zero
refactor(venue-session): extract status validation to mixin
docs: update build tracker with Phase 1 completion
```

### Developer Mode
Developer Mode **must** be enabled on the development site. Without it, DocType changes made in the UI are saved only to the database (not written to the filesystem as JSON), and they will be lost on the next migration. Enable it:
```bash
bench --site [site] set-config developer_mode 1
```

### .gitignore
The hamilton_erp repo must include a `.gitignore` that excludes:
```
__pycache__/
*.pyc
*.pyo
.DS_Store
.idea/
.vscode/
node_modules/
dist/
*.log
env/
.env
```
**Never commit** `sites/*/site_config.json` or `sites/*/private/` — these contain secrets.

---

## 12. Hard Prohibitions

1. **Do not bypass the Frappe ORM with raw SQL** unless documented why
2. **Do not modify standard ERPNext source files** — use hooks, overrides, custom fields
3. **Do not create custom payment handling** — use standard Mode of Payment
4. **Do not build a custom POS interface** — use the standard ERPNext POS
5. **Do not store business logic in Client Scripts alone** — server-side validation is mandatory
6. **Do not hardcode values** — use DocType settings or `frappe.db.get_single_value()`
7. **Do not skip the fixtures approach** for custom fields on standard DocTypes
8. **Do not use `frappe.db.sql` for simple CRUD** — use the Document API
9. **Do not expose expected cash totals** to any operator-facing endpoint or UI
10. **Do not omit forward-compatibility fields** because Hamilton doesn't use them yet
11. **Do not call `frappe.db.commit()` inside doc_events hooks** — v16 prohibits this
12. **Do not use `"*"` wildcard in doc_events** unless absolutely necessary — it fires on every DocType and hurts performance
