## Inbox — April 14 2026 — Fraud Research & Task 25 Planning

### Fraud Research Findings
- Conducted extensive ERPNext fraud research. Key risks for ANVIL:
  - Cash skimming (no session entered) — most likely real-world attack
  - Transaction void after cash collected — requires cancel permission lockdown
  - Offline mode abuse — browser cache wipe deletes unsynced transactions
  - Role self-escalation — anyone with System Manager can grant themselves any role
  - Direct DB access bypasses all ERPNext controls entirely
  - Ghost employees, vendor invoice fraud, expense inflation also documented

### Key Scan / Barcode Decision
- Phase 2 feature confirmed: physical key must be scanned BEFORE payment
- Scan validates that physical key matches selected asset in ERPNext
- Dual purpose: fraud prevention + asset/payment verification
- Pairs with blind cash reconciliation (also Phase 2)

### Task 25 Hardening Checklist
- Export Fixtures to Git as JSON
- Write Patches for site setup automation
- Add GitHub Actions CI/CD
- Enable v16 Role-Based Field Masking
- Audit hooks.py — replace wildcards, add try-except
- Clear Frappe Cloud error log
- Create docs/lessons_learned.md
- Create docs/venue_rollout_playbook.md
- Update CLAUDE.md to reference all new docs

### Knowledge Portability Strategy
- Philly, DC, Dallas each inherit full Hamilton knowledge
- docs/decisions_log.md — architectural decisions + reasoning
- docs/lessons_learned.md — bugs, mistakes, fixes
- docs/venue_rollout_playbook.md — step-by-step venue setup checklist
- Each build faster than the last

### Inbox Workflow Adopted
- docs/inbox.md is the bridge between claude.ai and Claude Code
- End of claude.ai session: paste summary into inbox.md on GitHub
- Start of Claude Code session: "read inbox.md, merge into docs, clear it"
