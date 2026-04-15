# Hamilton Build — Pre-Handoff Research Prompts

Run these in a fresh claude.ai session BEFORE starting Task 25.
Each is a standalone research session. Do them in order.
After each one, paste key findings into docs/inbox.md and run the merge command in Claude Code.

These prompts are designed to surface anything missed during the Hamilton build
before professional handoff. Better to find gaps now than after a developer bills
hours discovering them.

---

## Prompt 1 — ERPNext Production Best Practices Audit

```
I have a partially built production custom app on ERPNext v16 / Frappe Cloud
for a men's bathhouse/hospitality venue in Hamilton, Ontario. The app is called
hamilton_erp and lives at csrnicek/hamilton_erp on GitHub. It is about 70% complete
(Tasks 1-17 of 25 done) and will be handed off to a professional developer after
Task 25.

Before we finalize this build, search the internet and give me every best practice,
gotcha, production checklist item, common mistake, and expert tip that experienced
ERPNext v16 developers know. I want to find anything we may have missed before
it becomes a problem at handoff or in production.

Cover all of the following:
- Custom app structure and upgrade safety
- Fixtures — what they are, why they matter, how to export and commit them
- Patches — automating site setup so no manual UI configuration is needed on new sites
- hooks.py best practices — wildcard events, try-except blocks, performance traps
- CI/CD with GitHub Actions — auto-running tests on every push
- Role-based permissions and field masking (v16 feature)
- Audit Trail vs Document Versioning — the difference and why both matter
- Frappe Scheduler Jobs for nightly automation
- Frappe Cloud error log monitoring
- init.sh — environment startup script pattern from Anthropic harness research
- What a clean professional handoff looks like for an AI-assisted ERPNext build

I am a beginner with coding. Give me concrete actions, not theory.
Flag anything that is harder to fix after handoff than before it.
Flag anything that will cause a professional developer to ask questions or
bill extra hours because it's missing or messy.
```

---

## Prompt 4 — Multi-Venue Knowledge Portability Audit

```
I have a completed Phase 1 ERPNext v16 custom app for Hamilton, Ontario (venue 1
of 6). The next venues to build are Philadelphia, Washington DC, and Dallas — all
running the same custom Frappe app on separate Frappe Cloud sites.

Before I hand off the Hamilton build, help me audit whether the codebase and
documentation are structured for maximum reuse across venues.

Specifically:
- What should live in the repo vs in AI memory vs in external docs for a
  multi-venue single-codebase ERPNext deployment?
- How should docs/decisions_log.md, docs/lessons_learned.md, and
  docs/venue_rollout_playbook.md be structured so a new venue build inherits
  everything Hamilton learned?
- What is the right git branching strategy for a multi-venue single codebase
  where each venue may have slight differences?
- How should feature flags work in Frappe/ERPNext to turn venue-specific
  features on/off per site without forking the codebase?
- What should the Fixtures and Patches strategy look like so standing up
  Philadelphia requires zero manual UI configuration?
- What is missing from a typical AI-assisted ERPNext build that makes the
  second venue build harder than it needs to be?

I already have: CLAUDE.md, docs/claude_memory.md, docs/decisions_log.md
Tell me what's missing, what needs improving, and what to do before handoff
so Philadelphia starts 50% faster than Hamilton.
```

---

## Prompt 5 — Professional Developer Handoff Audit

```
I am about to hand off an AI-assisted ERPNext v16 custom app (hamilton_erp) to a
professional Frappe/ERPNext developer. I built it as a beginner using Claude Code
over several weeks. It covers asset lifecycle management, session tracking, and
Redis-based locking for a men's bathhouse operation.

Search for what a clean, professional Frappe/ERPNext custom app handoff looks like.
Then audit what is typically missing or messy in AI-generated ERPNext codebases
and give me a checklist to work through before I hand it over.

Cover:
- What documentation must exist for a developer to onboard without asking questions?
- What does a production-ready test suite look like for a custom Frappe app —
  coverage targets, what must be tested, what can be skipped?
- What should CLAUDE.md contain to brief a new AI coding session instantly?
- What fixtures, patches, and setup scripts should exist so a developer can
  spin up a fresh site in under 30 minutes?
- What are the most common problems developers find in AI-generated ERPNext
  codebases — redundant code, missing error handling, poorly named functions,
  incomplete DocType definitions, missing indexes?
- What security and permissions items are most commonly overlooked before handoff?
- What does a professional developer expect to see in hooks.py, and what red
  flags will make them lose confidence in the codebase immediately?
- What is the difference between code that works and code that is maintainable
  by someone who didn't write it?

Give me a prioritised handoff checklist. Flag anything that will cause the
developer to bill extra hours if it's missing.
Assume the developer is experienced with ERPNext but has never seen this codebase.
```

---

## After Running All Three Prompts

1. Paste key findings from each into `docs/inbox.md` on GitHub
2. Start Claude Code and run:
   ```
   git pull && read docs/inbox.md and merge its contents into claude_memory.md,
   decisions_log.md, lessons_learned.md, and venue_rollout_playbook.md,
   then clear inbox.md
   ```
3. Review what was added against the existing Task 25 checklist
4. Add any new items to Taskmaster before starting Task 25 work

---

## Why Prompt 2 and Prompt 3 Are Skipped

- **Prompt 2 (Fraud)** — already completed April 14 2026. Full research in
  docs/lessons_learned.md and claude_memory.md.
- **Prompt 3 (AI Session Management)** — already implemented. CLAUDE.md,
  claude_memory.md, inbox.md workflow, and harness patterns are all in place.

---

## Meta Note

These three prompts are the pre-handoff equivalent of a building inspection —
find the problems before the buyer walks through, not after.
Hamilton is the template for all future venues. Getting it right here
means Philadelphia, DC, and Dallas all start cleaner.
