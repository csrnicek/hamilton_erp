# Inbox

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
