## Entry: 2026-04-15 — Frappe Cloud Version Pinning

Before production go-live, verify the Frappe Cloud site is pinned to a 
specific stable v16 minor version rather than auto-updating to latest.

Current latest is v16.14.0 (released April 14, 2026).

Action for Claude Code at Task 25:
1. Check what version hamilton-erp.v.frappe.cloud is currently running
2. Confirm auto-update settings in Frappe Cloud dashboard
3. Recommend pinning to current stable minor version before go-live
4. Document the pinned version in claude_memory.md

Note: v16.14.0 removes forced six-decimal rounding on valuation rate 
fields — verify no impact on Hamilton's session pricing calculations 
after any platform update.
