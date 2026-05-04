# Frappe Cloud Update Policy

**Status:** Active. Pinned by DEC-112 (`docs/decisions_log.md`).
**Audience:** Chris (owner), anyone with Frappe Cloud dashboard access.
**Companion doc:** `docs/HAMILTON_LAUNCH_PLAYBOOK.md` Frappe Cloud / Production checklist.

---

## TL;DR

| Rule | Value |
|---|---|
| **Update window** | Monday OR Tuesday, 9 AM – 5 PM EST only |
| **Approval** | Owner approval required before every update — NEVER auto-update |
| **Blackout window** | Thursday 00:00 EST → Monday 09:00 EST is a hard no-update zone |
| **Setup** | Pre-launch step: configure update-window pinning + disable auto-update in the Frappe Cloud dashboard |

---

## 1. Update window

Updates to Frappe, ERPNext, or any installed app may only run during:

- **Monday, 9 AM – 5 PM EST**, OR
- **Tuesday, 9 AM – 5 PM EST**.

Outside this window, no update may run on the production bench, even if it was queued earlier.

**Why these days.** Hamilton's revenue concentrates Thursday night through Sunday. Monday and Tuesday give us 4–5 days of operational distance before the next peak — enough time to identify and roll back a bad update without affecting customers.

## 2. Approval — never auto-update

Frappe Cloud's "Auto-update" toggle for the production bench MUST be **disabled**. Every update — minor releases, security patches, app upgrades — is initiated manually after explicit owner (Chris) approval.

This rule covers:

- ERPNext minor releases (e.g. v16.3.4 → v16.3.5).
- Frappe minor releases.
- `hamilton_erp` app upgrades from `main`.
- Any third-party app installed on the bench.

The cadence and rationale align with **CLAUDE.md → "Production version pinning — tagged v16 minor release, NEVER branch HEAD or develop"** (manual promotion after staging soak; ~10 fixes/month land in `version-16` HEAD and auto-pulling them invites production churn).

## 3. Blackout window — hard no

From **Thursday 00:00 EST through Monday 09:00 EST**, no update may run, regardless of urgency rating, even if Frappe Cloud schedules one in the dashboard.

If Frappe Cloud announces a "mandatory" security update inside the blackout window:

1. Apply it on staging immediately.
2. Notify Chris.
3. Decide whether the risk of waiting until Monday 9 AM EST exceeds the risk of updating during peak revenue hours. Default: wait.
4. Apply on production at the next valid Monday/Tuesday window.

## 4. Pre-launch setup step

Before Hamilton's go-live (June 2026), Chris configures the policy in the Frappe Cloud dashboard:

1. Open the bench → Settings → Auto-update.
2. **Disable** auto-update.
3. Open the bench → Settings → Update Window.
4. Set the maintenance window to **Monday 09:00 – 17:00 EST OR Tuesday 09:00 – 17:00 EST**.
5. Confirm the dashboard shows the window correctly and that auto-update is OFF.
6. Add this configuration to the launch checklist (`HAMILTON_LAUNCH_PLAYBOOK.md` Frappe Cloud / Production section).

If the dashboard does not support pinning a custom update window, escalate to Frappe Cloud support and negotiate the window in writing before go-live.

## 5. When the policy is violated

If an update lands outside the window (e.g. auto-update reactivated after a dashboard reset, support team pushed an unscheduled update):

1. Document in `docs/decisions_log.md` as an amendment to DEC-112 — exact time, package, who initiated.
2. Run the post-update smoke test (`docs/RUNBOOK.md` §3.5 if present, or the runbook chapter on production smoke tests).
3. If anything breaks during peak hours as a result, page Chris and follow `RUNBOOK_EMERGENCY.md`.
4. Re-confirm the dashboard settings; do not assume the policy is enforced after a violation.

---

**References.**
- DEC-112 — Frappe Cloud update policy (this doc's authoritative DEC).
- DEC-098 — receipt printer (Phase 2 hardware track context).
- CLAUDE.md → "Production version pinning."
- `docs/venue_rollout_playbook.md` Phase A step 2 (production version pin).
- `docs/HAMILTON_LAUNCH_PLAYBOOK.md` Frappe Cloud / Production checklist.
