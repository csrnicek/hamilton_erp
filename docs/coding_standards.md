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


### 2.9 v16 POS is a Vue.js Single Page Application

The ERPNext v16 POS is built as a Vue.js SPA. This has two consequences for Hamilton:

- Custom extensions that modify the POS UI must inject Vue components or use `page_js` hooks — they cannot manipulate the DOM like a traditional page.
- ERPNext updates can break UI injections. All POS UI extensions must be **loosely coupled** — use event hooks and realtime messages rather than direct DOM manipulation.

For Hamilton, the asset assignment prompt is triggered via `frappe.publish_realtime` after Sales Invoice submission (server-side), not by directly modifying the POS Vue UI. This is the correct, upgrade-safe approach.

### 2.10 v16 POS Uses pos_controller Events

The POS controller hook pattern changed in v16. Use the following approach for POS-specific behavior:

- Hook into `Sales Invoice` via `doc_events` on `on_submit` (already in §3.2) — this is the primary integration point.
- Do **not** attempt to hook into POS-specific Vue controller methods directly.
- For POS-specific behavior, prefer server-side hooks on Sales Invoice over client-side POS controller overrides.

### 2.11 Row Locking: Use FOR UPDATE (MariaDB)

When locking rows for status changes, use `FOR UPDATE` — this is the correct MariaDB syntax:

- `FOR NO KEY UPDATE` is PostgreSQL-only syntax and is **not supported in MariaDB**. Do not use it.
- `FOR UPDATE` acquires a row-level exclusive lock in MariaDB InnoDB. This is correct and required.
- The Redis advisory lock (§13.2) is the primary concurrency guard. The SQL `FOR UPDATE` is a secondary safety net held only for the duration of the validate+save operation.
- FK child blocking concern is mitigated by the short lock window (Redis ensures only one writer enters at a time).

```python
# CORRECT — use FOR NO KEY UPDATE in v16
locked = frappe.db.sql(
    "SELECT name, status, version FROM `tabVenue Asset` WHERE name = %s FOR NO KEY UPDATE",
    self.name, as_dict=True
)

# WRONG — do not use FOR UPDATE unless FK child blocking is specifically required
locked = frappe.db.sql(
    "SELECT name FROM `tabVenue Asset` WHERE name = %s FOR UPDATE",
    self.name, as_dict=True
)
```

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

### 8.3 Blind Cash Control — CRITICAL

**No API endpoint, no client script, and no report may expose expected cash totals to operator-role users.** The `system_expected` field on Cash Reconciliation must only be calculated and revealed **after** the manager submits their blind count. Code reviews must specifically verify this rule.

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

---

## 13. Concurrency and Locking Standards

These rules are mandatory for all `Venue Asset` status changes. Broken locking = double-booked rooms in production.

### 13.1 Three-Layer Locking (Required for All Venue Asset Status Changes)

Every status-changing operation on `Venue Asset` must use all three layers in order:

1. **Redis advisory lock** — fast pre-check, prevents queuing at the DB level
2. **MariaDB row lock** using `FOR UPDATE` — strong DB integrity
3. **Version field check** — catches any bypasses of layers 1 and 2

### 13.2 Redis Lock Specification

Use Frappe's built-in `frappe.cache()` (Redis) for advisory locks:

- **Key format:** `hamilton:asset_lock:{asset_name}:{operation_suffix}` (e.g. `hamilton:asset_lock:Room-7:assign`)
- **Lock TTL:** 15 seconds maximum (`px=15000`)
- **Owner token:** `str(uuid.uuid4())` — unique per acquisition
- **Acquire:** `cache.set(lock_key, token, nx=True, px=15000)` — atomic SET NX
- **Release:** Lua script for atomic token-verified release — **never raw DELETE**

Required Lua release script (copy exactly):
```python
RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""
cache.eval(RELEASE_SCRIPT, 1, lock_key, token)
```

If Redis lock cannot be acquired, throw a plain-language message:
```python
frappe.throw(
    _("Asset {0} is being processed by another operator. Refresh the board and try again.").format(self.asset_name)
)
```

### 13.3 Lock Section Rules — Critical

The code inside a lock must be minimal. Locks are held for milliseconds, not seconds.

**INSIDE a lock (allowed):**
- Read current status from DB
- Validate the transition
- Update status field and save the document
- Create Asset Status Log entry

**NEVER inside a lock:**
- Print a label
- Send email or notification
- Make external API calls
- `frappe.enqueue()` calls
- Any I/O operation
- `frappe.publish_realtime()` — this must go **after** the lock releases

### 13.4 Consistent Lock Ordering for Multiple Assets

If an operation ever needs to lock more than one `Venue Asset` simultaneously (e.g., future bulk operations), always sort by `name` before locking to prevent deadlocks:

```python
assets_to_lock = sorted(asset_list, key=lambda a: a["name"])
for asset in assets_to_lock:
    with asset.lock_for_status_change():
        # process
```

### 13.5 Frontend Retry Logic for Concurrency Failures

When an assignment attempt fails due to a concurrency conflict, the Asset Board JS must:

1. Show a plain-language message: "That room was just taken — the board is refreshing."
2. Auto-refresh the asset board via the realtime channel.
3. Allow the operator to try again — **do NOT auto-retry silently**.

```javascript
async function assignAsset(assetName, sessionName) {
    try {
        await frappe.call({
            method: "hamilton_erp.hamilton_erp.doctype.venue_asset.venue_asset.assign_to_session",
            args: { asset_name: assetName, session_name: sessionName },
            freeze: true,
            freeze_message: __("Assigning asset...")
        });
    } catch (err) {
        if (err.message && err.message.includes("being processed")) {
            frappe.show_alert({
                message: __("That room was just taken — refreshing board..."),
                indicator: "orange"
            });
            refreshAssetBoard();
        } else {
            frappe.msgprint(err.message);
        }
    }
}
```

### 13.6 MariaDB Isolation Level Consideration

Frappe uses `REPEATABLE READ` by default (MariaDB InnoDB default). If deadlocks appear during load testing (error 1213 in logs), set `READ COMMITTED` at the session level in the affected whitelisted method:

```python
frappe.db.sql("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
```

Do **not** set this globally — only per-session in the specific method where deadlocks are observed.
