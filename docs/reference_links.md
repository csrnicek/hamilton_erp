# Hamilton ERP — Reference Links

Quick-access links for developers working on the Hamilton ERP custom Frappe app.

---

## 1. Core Repositories

| Repository | URL | Branch |
|---|---|---|
| Frappe Framework | https://github.com/frappe/frappe | `version-16` |
| ERPNext | https://github.com/frappe/erpnext | `version-16` |
| Frappe Bench (CLI) | https://github.com/frappe/bench | `main` |
| Frappe Docker | https://github.com/frappe/frappe_docker | `main` |

### ERPNext POS Source Code (read to understand standard POS behavior before extending)

These paths are relative to the `erpnext` app root:

- **POS Page:** `erpnext/selling/page/point_of_sale/`
- **POS Opening Entry:** `erpnext/accounts/doctype/pos_opening_entry/`
- **POS Closing Entry:** `erpnext/accounts/doctype/pos_closing_entry/`
- **POS Profile:** `erpnext/accounts/doctype/pos_profile/`
- **Sales Invoice:** `erpnext/accounts/doctype/sales_invoice/`
- **Pricing Rule:** `erpnext/accounts/doctype/pricing_rule/`
- **Mode of Payment:** `erpnext/accounts/doctype/mode_of_payment/`
- **Item Tax Template:** `erpnext/accounts/doctype/item_tax_template/`

---

## 2. Official Documentation

| Resource | URL |
|---|---|
| Frappe Framework Docs (main) | https://frappeframework.com/docs/user/en/introduction |
| Frappe Developer API | https://frappeframework.com/docs/user/en/api |
| Frappe Document API | https://frappeframework.com/docs/user/en/api/document |
| Frappe Database API | https://frappeframework.com/docs/user/en/api/database |
| Frappe REST API | https://frappeframework.com/docs/user/en/api/rest |
| **Frappe Hooks (critical)** | https://frappeframework.com/docs/user/en/python-api/hooks |
| **Database Migrations & Patches** | https://frappeframework.com/docs/user/en/database-migrations |
| **Realtime / Socket.io** | https://docs.frappe.io/framework/user/en/api/realtime |
| Frappe Tutorial (build an app) | https://frappeframework.com/docs/user/en/tutorial |
| ERPNext User Documentation | https://docs.erpnext.com |
| ERPNext POS Documentation | https://docs.frappe.io/erpnext/user/manual/en/point-of-sale |
| ERPNext POS Profile Docs | https://docs.frappe.io/erpnext/user/manual/en/pos-profile |
| Frappe School (video courses) | https://frappe.school |

---

## 3. v16 Migration and Breaking Changes

| Resource | URL |
|---|---|
| Frappe v16 Migration Guide | https://github.com/frappe/frappe/wiki/Migrating-to-version-16 |
| ERPNext v16 Migration Guide | https://github.com/frappe/erpnext/wiki/Migration-Guide-To-ERPNext-Version-16 |
| Frappe v16 Feature Overview | https://frappe.io/framework/version-16 |
| ERPNext + Frappe v16 Release Page | https://frappe.io/releases/version-16 |
| ERPNext v16.0.0 Release Notes | https://github.com/frappe/erpnext/releases/tag/v16.0.0 |

**Key v16 changes affecting Hamilton ERP development:**

- Query builder is the default backend for `get_all` / `get_list` — new aggregation syntax required
- State-changing whitelisted methods must use POST (not GET)
- JS files load as IIFEs — no global scope leakage between files
- Default list sort is by `creation`, not `modified`
- Desk route changed from `/app` to `/desk`
- `frappe.permission.has_permission` no longer accepts `raise_exception` — use `print_logs`
- Transaction Log DocType removed
- `frappe.new_doc` used in frontend instead of several removed whitelisted methods
- Document hooks via `hooks.py` can no longer commit database transactions
- Custom event handlers for realtime via `handlers.js` (experimental in v16)

---

## 4. Community and Support

| Resource | URL |
|---|---|
| Frappe Discussion Forum | https://discuss.frappe.io |
| Frappe GitHub Issues | https://github.com/frappe/frappe/issues |
| ERPNext GitHub Issues | https://github.com/frappe/erpnext/issues |
| **ERPNext Coding Standards (wiki)** | https://github.com/frappe/erpnext/wiki/Coding-Standards |
| **ERPNext Code Style Guide (Mintlify)** | https://www.mintlify.com/frappe/erpnext/developers/code-style |
| ERPNext Source Tree (v16) | https://github.com/frappe/erpnext/tree/develop/erpnext |

### Relevant Forum Threads

| Topic | URL |
|---|---|
| Extending POS via POS Controller class | https://discuss.frappe.io/t/extending-point-of-sale-in-erpnext-using-pos-controller/101521 |
| Custom Field fixtures best practices | https://discuss.frappe.io/t/what-is-best-practice-to-create-custom-fields-fixtures-or-coding/135904 |
| Frappe v16 WebSocket issues | https://discuss.frappe.io/t/frappe-v16-websocket-issues/159969 |
| Custom page with many UI views | https://discuss.frappe.io/t/best-practice-for-a-frappe-app-with-many-custom-ui-pages/117417 |
| doc_events hooks behavior | https://discuss.frappe.io/t/how-do-doc-hooks-work/140744 |

---

## 5. Development Environment Setup

### Option A: Frappe Docker (recommended for local dev)

```bash
git clone https://github.com/frappe/frappe_docker.git
cd frappe_docker
# Follow the development container setup in the repo README
# Then inside the container:
bench new-app hamilton_erp
bench --site dev.localhost install-app hamilton_erp
bench --site dev.localhost set-config developer_mode 1
```

### Option B: Native bench install

```bash
bench init --frappe-branch version-16 frappe-bench
cd frappe-bench
bench get-app --branch version-16 erpnext
bench new-site hamilton.localhost
bench --site hamilton.localhost install-app erpnext
bench new-app hamilton_erp
bench --site hamilton.localhost install-app hamilton_erp
bench --site hamilton.localhost set-config developer_mode 1
bench start
```

---

## 6. Hamilton ERP GitHub Repository

**Repository:** https://github.com/csrnicek/hamilton_erp  
**Default branch:** `main`

Any bench environment can pull the app:

```bash
bench get-app https://github.com/csrnicek/hamilton_erp.git
bench --site [sitename] install-app hamilton_erp
```

---

## 7. Hardware Reference

Per build spec §12:

| Hardware | Purpose | Notes |
|---|---|---|
| Label printer (Dymo/Brother QL) | Cash drop envelope labels | Browser print or direct USB — driver approach TBD in Phase 2 |
| Thermal receipt printer | Guest receipts | Standard ESC/POS — ERPNext POS supports natively |
| Tablet (iPad or Android) | Primary POS device | Chrome browser accessing ERPNext |
