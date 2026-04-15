markdown# docs/inbox.md
# Bridge file: paste planning summaries here, then at start of next Claude Code session say:
# "read inbox.md and merge anything relevant into claude_memory.md and appropriate docs, then clear inbox"

---

## Entry: 2026-04-11 — Expert Testing Gaps Review

From claude.ai planning session reviewing expert-level test checklist gaps:

**5 Phase 2 testing gaps identified — add to docs/testing_checklist.md under "Phase 2 Testing Gaps":**

1. **Dedicated test site** — hamilton-unit-test.localhost should be fully isolated from dev browser sessions. Highest priority for Phase 2 start.
2. **Role × API permission matrix** — a test covering every Hamilton role against every whitelisted API method. Highest priority for Phase 2 start.
3. **UI tests (Cypress/Playwright)** — Asset Board tile rendering, popover interactions, and role-based button visibility.
4. **Background job and scheduler health tests** — using `bench doctor` and scheduler health checks. Important for DC which will have complex accounting flows.
5. **Frappe Recorder performance profiling** — full SQL trace visibility for N+1 query detection on busiest workflows. Current `test_api_phase1.py` guard is incomplete.

**Two critical security items — action required before production go-live:**

- **SQL injection audit**: ERPNext published a SQL injection vulnerability in late 2025. Every `frappe.db.sql()` call in `api.py` must be verified to pass parameters as a second argument, never via string formatting. Add a dedicated test for this.
- **XSS in asset_board.js**: ERPNext published a reflected XSS vulnerability in December 2025. The `render_tile()` function generates HTML dynamically from asset data. All dynamic values must be verified as properly escaped. Add a test.

**Paste to Claude Code to action the testing gaps:**
Please do the following to incorporate the expert test checklist gaps into our documentation and planning:

Add a new section to docs/testing_checklist.md called "Phase 2 Testing Gaps" documenting these 5 items with brief descriptions:

Dedicated test site (hamilton-unit-test.localhost) to isolate tests from dev browser
Role × API permission matrix covering every Hamilton role against every whitelisted API method
Playwright UI tests for Asset Board tile rendering, popover interactions, and role-based button visibility
Background job and scheduler health tests using bench doctor
Frappe Recorder performance profiling for N+1 query detection on busiest workflows


Add a note that items 1 and 2 are highest priority for Phase 2 start
Commit to GitHub with message: docs(tests): add Phase 2 testing gaps from expert checklist review


---

## Entry: 2026-04-14 — Playwright, Cognee, Karpathy Review

**Playwright (playwright.dev):**
- Phase 2 only. Not needed now. Phase 1 tests are Python backend tests; Playwright is JavaScript browser automation.
- Useful in Phase 2 for: check-in form submission, asset board visual updates, POS payment screen after key scan.
- Has native GitHub Actions integration — aligns with Task 25 CI/CD work.
- Already saved to memory as Phase 2 reminder.

**Cognee (graph/vector memory tool):**
- Evaluated and rejected for Hamilton ERP. Overkill — designed for agents querying 50,000+ documents dynamically.
- Current setup (claude_memory.md + inbox.md + decisions_log.md) is the right fit. No new infrastructure needed.
- Concept of episodic → semantic consolidation is a useful mental model for designing the Phase 2 inbox auto-commit Python script.

**Karpathy 4 Principles for CLAUDE.md (Task 25):**
- Already saved to memory/Task 25 checklist.
- At Task 25, run: `claude -p "Read the entire project and strengthen CLAUDE.md based on Karpathy's four principles — Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution. Adapt to the real architecture you see." --allowedTools Bash,Write,Read`

**"Everything Claude Code" (30+ agent framework):**
- Evaluated and rejected. Built for large engineering teams with parallel workstreams. Not suitable for a solo developer on a focused Frappe app. Would burn token limits and add management overhead.

---

## Entry: 2026-04-15 — Frappe/ERPNext Mastery Guide Review

Reviewed community guide: github.com/mohamed-ameer/Frappe-ERPNext-Tutorial-Mastery

**Important caveat:** Frappe community members flagged parts of this guide as AI-generated without deep verification, with possible errors and misconceptions. Use as a **topic navigation index only** — do not copy code examples without independent verification.

**Chapters directly relevant to Hamilton ERP by phase:**

**Task 25 (immediate):**
- Ch.12 — Security & Role-Based Access Control → permissions hardening (cancel/amend locked to manager roles)
- Ch.12.3 — Audit Logs → Document Versioning + Audit Trail task
- Ch.3 — Automation and Workflows → workflow approval states and transitions with role assignments
- Ch.13 — Frappe Fixtures → fixtures exported to Git as JSON

**Phase 2:**
- Ch.13 — Background Jobs / Cron Jobs / Worker Management → Scheduler Jobs (nightly stale asset detection, session reconciliation, cash drop verification)
- Ch.13 — Real-Time Updates / Synchronizing Data Across Clients → multi-tablet real-time sync for DC/Crew Club
- Ch.9.1 — Payment Gateways (Stripe) → Phase 2 Stripe Terminal integration
- Ch.9.5 — Webhooks → tablet-is-truth sync architecture

**Before production go-live (Frappe Cloud not yet set up):**
- Ch.11 — Frappe Cloud → Git integration, custom app deployment workflows, SSL, environment variables, monitoring, backups. Review this chapter as a checklist before going live.
- Ch.10.3 — Backup & Restore automation → set up before first real session data hits production.
