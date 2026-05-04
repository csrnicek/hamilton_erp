# Hamilton Opening-Weekend Launch Playbook

**Version:** 2.0 (revised after ChatGPT review)
**Author:** Claude Opus 4.7 + ChatGPT cross-review
**Date:** 2026-04-28
**Scope:** First 48 hours of real operations at Club Hamilton on the new Frappe ERP system

---

## What changed in this version

The first version of this audit ranked risks like an engineer ("which code path is most likely to fail?"). ChatGPT's review pointed out that opening weekend is an *operations recovery* problem, not a software correctness problem. The system does not need to be perfect to open — staff need to know what to do when something is imperfect.

This revision reflects that lens. Major changes:

- **Re-ranked the top 12** to put customer-facing operational risks at the top
- **Added 5 risks** that the first version missed: wrong key handed out, dirty room marked clean, overtime handling, staff login sharing, wrong tax/price mapping
- **Demoted recurring membership** (not active in Hamilton phase 1) and **frappe/payments CI dependency** (technical preflight, not front desk concern)
- **Added a Go/No-Go checklist** at the top — brutally simple yes/no decision gate
- **Added a 2-page Front Desk Runbook** that staff can print and tape up
- **Added a Technical Preflight** for Chris before launch day

The guiding principle from ChatGPT's review:

> Stop treating opening weekend as mainly a software correctness problem. Treat it as an operations recovery problem.

---

# PART 1 — Go/No-Go Checklist

**Print this. Answer each item yes or no. Any "no" is a launch blocker until resolved or until a manual fallback is documented.**

## Operations readiness

- [ ] Can two tablets attempt to assign the same key, and only one succeeds with a clear error message that the second staff member can act on?
- [ ] If a payment succeeds but the session fails to open, is there a written recovery procedure that any front desk staff can execute?
- [ ] Can a refund or void be processed by trained staff (or escalated within 5 minutes)?
- [ ] If end-of-shift cash count does not match expected, do staff know the variance threshold rules and reporting procedure?
- [ ] If the internet drops for 30 minutes, can Hamilton continue to take check-ins on paper and reconcile later?
- [ ] If Chris does not respond to a page for 30 minutes, is there a tier-2 person who can perform the basic recovery procedures?
- [ ] Can the audit log reconstruct who did what, on which device, with what payment ID, after an incident?

## Technical readiness

- [ ] CI is green on main (PR #9 merged, all subsequent merges still passing)
- [ ] Frappe/payments dependency decision made for production (install or override-tests)
- [ ] No untested scheduler jobs can fire in production (verify Frappe Cloud cron settings)
- [ ] Permissions audit completed: front desk role cannot cancel/amend/delete operational records
- [ ] Document Versioning + Audit Trail enabled on Venue Session, Bathhouse Assignment, Cash Drop, Comp Admission Log
- [ ] Backup tested by actual restore (not just "backup exists" — a real restore drill)
- [ ] No unpinned `develop` branch dependencies in production deployment

## Staff readiness

- [ ] Each front desk staff has their own login PIN — no shared accounts
- [ ] Each staff has done at least 2 practice shifts on the actual tablets with actual workflows
- [ ] Staff have practiced 6 failure scenarios: paid-but-no-session, wrong key, refund request, cash variance, internet drop, key already assigned
- [ ] Staff have a printed runbook (Part 3 below) at the front desk
- [ ] Staff have a phone number to reach Chris or tier-2 for emergencies
- [ ] Manager is on the floor for opening weekend, not in the office

**Rule:** If any item is "no", either fix it before opening OR document the manual fallback procedure. Opening with unanswered questions is the failure mode.

---

# PART 2 — Top 12 Operational Risks (Re-Ranked)

Ranked by likelihood × customer-facing impact during the first 48 hours.

## #1 — Payment succeeded but session did not open

**The failure:** Charge succeeds at the payment processor. Network hiccup, Frappe timeout, or asset assignment failure prevents the session from opening. Guest is charged. Guest has no key. Guest is at the front desk, angry, with their phone showing the Stripe SMS notification.

**Why this is #1:** It is the single most damaging customer-facing failure possible. It happens fast, the guest sees evidence of the charge immediately, and untrained staff will compound the problem by refunding and re-charging (potentially double-charging).

**Before opening:**
- Read the actual payment flow code. Identify every line where "payment confirmed" and "session opened" are NOT in the same atomic transaction. Document the gap.
- Write the recovery procedure in plain English: "If processor shows paid and Frappe did not open a session, manager manually opens session with reason='post-payment recovery', records payment ID in notes, gives key, logs incident."
- Test the flow with a real $1 charge: charge, force a session-open failure, verify recovery procedure works, refund the $1.
- Bookmark Stripe dashboard URL on the manager's phone

**In the moment:**
- Verify in Stripe (not just the SMS) whether the charge actually succeeded
- If yes: open session manually in Frappe with the documented reason. Give the key. Log incident.
- If pending or failed: re-attempt. Do NOT refund-and-re-charge until processor confirms refund completed.
- Apologize to the guest. Comp something small if appropriate.

---

## #2 — Staff stop trusting the system and revert to parallel paper

**The failure:** Manager decides "the system is being weird, just track on paper, we'll enter Monday." Staff start running a parallel paper ledger. Now you have a duplicate record nobody trusts and reconciliation chaos for the week.

**Why this is #2:** This is the most common mode of ERP go-live failure in any industry. Once parallel paper starts, it does not stop. Staff confidence is harder to rebuild than software is to fix.

**Before opening:**
- Train staff for at least 2 full shifts on actual tablets BEFORE opening
- Run live failure drills with staff: paid-but-no-session, wrong key, internet drop. Don't just describe them — make staff handle them on the system.
- Set the rule clearly: paper is ONLY for ISP outage, variance documentation, and incidents documented in the runbook. Paper is not a "I prefer paper" option.
- Manager must be on the floor opening weekend, supporting staff in real time, not in the office

**In the moment:**
- If you see paper logging happening for any reason not on the runbook: stop, reset, walk through one transaction together on the system. Confidence is restored by guided success, not by orders.
- If the system is genuinely failing staff: pull the failure data, fix Monday, communicate Tuesday, retrain Wednesday, rebuild trust over a week.

---

## #3 — Cash drop reconciliation does not match

**The failure:** Front desk closes shift at 4am. System says $3,847 expected. Drawer has $3,790. Variance is $57. Staff are tired. They make the count match by adjusting the system or the cash. Either way, the truth is now lost.

**Why this is #3:** Variances WILL happen on opening weekend — staff are nervous, customers give wrong change, the system is new, someone fat-fingers a comp. The risk is not the variance itself; it's how it gets resolved.

**Phase 1 reconciliation rule (until DEC-069 / R-011 closes in Phase 3): paper is canonical.** The Cash Reconciliation form's variance classifier is hard-disabled — `variance_flag` reads `"Pending Phase 3"` regardless of inputs. The system does NOT compute "expected cash." Managers reconcile cash physically against the printed envelope label, sign a paper sheet, and enter the manager-counted `actual_count` into Frappe for the audit record. The dashboard headline on the form points back to this section. Full procedure: `RUNBOOK.md` §7.2.

**Before opening:**
- Train staff that variances are EXPECTED on opening weekend and there is NO PUNISHMENT for honest reporting
- Train staff that the form's `variance_flag` ALWAYS reads `"Pending Phase 3"` — this is the contract, not a bug. The flag is not the signal; the manager-vs-label comparison on paper is.
- Set the variance policy in writing: ±$20 = log and move on; >$20 = call manager; >$100 = call Chris
- Confirm the printed envelope label is legible and contains all 8 fields per R-012 (venue, date, operator, shift, drop type, drop number, declared amount, timestamp). The label IS the system-of-record for this drop until Phase 3.

**In the moment:**
- Compare manager-counted cash against the **printed envelope label's declared amount**, not against the form's variance flag.
- Log the variance, count again, log the new count, photograph the cash and screen, move on.
- Reconcile in detail Sunday morning when nobody is tired.
- Never let staff "fix" a variance by adjusting cash or system to match.

---

## #4 — Audit log does not capture enough detail to reconstruct an incident

**The failure:** Saturday night something goes wrong — exact details unclear. Sunday morning Chris tries to reconstruct. The audit log shows "session created" but not "by whom on which tablet at what time with what payment ID". Forensic reconstruction is impossible. The fix is guesswork.

**Why this is #4:** Without good audit data, every other recovery procedure on this list becomes harder. You can't catch shrinkage, you can't resolve guest disputes, you can't onboard new staff with confidence. This is the foundation for everything else.

**Before opening:**
- Verify Document Versioning is enabled on at minimum: Venue Session, Bathhouse Assignment, Cash Drop, Comp Admission Log
- Verify Audit Trail captures: actor (which user/PIN), timestamp, device/IP, before/after values
- Test it: open a session as User A, modify it as User B, confirm the audit log shows the modification with full attribution

**In the moment:**
- If audit logs are thin, supplement: front desk staff sign in/out of tablets at shift change to create time anchors; security camera footage is time-synced to Frappe
- Re-prioritize Task 25 audit items if they are not yet complete

---

## #5 — Wrong physical key handed to guest

**The failure:** System assigns Key 47 to a session. Staff physically grabs Key 48 from the board. Guest goes to Locker 48 (or worse, Room 48 already occupied). Now the system says occupant of 47 is the guest, but the guest is actually in 48, which is supposed to be empty.

**Why this matters:** This is not a software bug. It's a human/system mismatch that creates the same downstream chaos as a software failure: wrong asset occupancy, angry guests, reconciliation confusion, audit uncertainty.

**Before opening:**
- Train staff to read the key number out loud before handing it over: "I'm handing you Key Forty-Seven, please confirm."
- Add physical key-board discipline: one key removed = one system assignment, period.
- Consider a final confirmation screen: "You are handing out Key 47. Confirm." Worth implementing if not already there.

**In the moment:**
- Correct the system immediately — don't wait until end of shift
- Log reason: "physical key handoff mismatch"
- Do NOT silently swap records without documenting

---

## #6 — Race condition: two tablets, one key, simultaneous assignment

**The failure:** 3 tablets at front desk. Two staff scan the same physical key into the system within 200ms of each other. Either the lock system rejects the second assignment cleanly (good), or it allows both (catastrophic).

**Why this matters:** This is Hamilton's signature feature ("we don't double-book keys"). The custom lock system you built handles the happy path on a single Python process, but it has never been tested with real concurrent humans on actual wall-mounted tablets at peak load.

**Important nuance from ChatGPT:** Throughput and lock correctness are different things. A system can do 100/sec and still double-assign. A system can do 3/sec and be perfectly safe. The 5/sec CI threshold catches throughput regressions, NOT lock correctness. You need a dedicated concurrency test.

**Before opening:**
- Run a chaos test on local bench: open 3 browser tabs, log in as 3 different staff, manually click "assign key 47" in all 3 within 1 second. Verify only one wins. Verify the error message on the losing tablets is human-readable: "Key 47 is being assigned by [name] right now — wait 2 seconds and try again."
- Better: write a Playwright script that does this 50 times across random keys against a real bench. Run it before go-live.
- Best: do it on actual tablets at Hamilton, on Hamilton's actual Wi-Fi network, with actual staff doing the tapping.

**In the moment:**
- If "key already assigned" appears: walk to the other tablet, see who has it, resolve verbally
- If both tablets succeed (catastrophic): stop assignments, manually verify physical occupancy, fix in Frappe, document the incident as critical
- Have a paper backup form ready as universal fallback

---

## #7 — Internet outage during peak hours

**The failure:** ISP goes down Saturday at 10pm. Tablets cannot reach Frappe Cloud. System is dark for 45 minutes during peak revenue hours.

**Why this matters:** Bathhouses operate cash-heavy in a building with one ISP. ERPNext is cloud-hosted with no offline mode. 45 minutes of peak-hour outage is real revenue loss + reconciliation chaos + key-tracking chaos.

**Before opening:**
- Verify Hamilton has backup internet (4G/5G modem, second ISP, or mobile hotspot) and that staff know how to switch tablets to it
- Print a manual check-in form. Fields: name, time in, key/locker, payment amount, payment method, staff initials. Stock at front desk in a labeled folder.
- Decide policy in writing: at what point does staff switch to manual? 30 seconds of outage? 2 minutes? Document and train.

**In the moment:**
- Switch to backup internet first
- If still down: paper forms, take cash, manually pull keys from board, photograph the key board hourly to track occupancy
- Reconcile Sunday morning by entering each form into Frappe with reason="ISP outage manual check-in [date/time]"

---

## #8 — Refund or void on a session that has already been opened

**The failure:** Guest pays, gets a key, walks in, walks out 10 minutes later because they changed their mind. Front desk needs to refund. Was process_refund deleted in Phase 4? Do staff know the procedure?

**Why this matters:** Refunds are operationally common in any payment system. If staff don't know how to do it, they will hand cash from the till — which breaks reconciliation every night until it's fixed.

**Before opening:**
- Document the refund procedure even if it's manual: "manager calls Chris, Chris refunds via Stripe dashboard, manager voids the session in Frappe with reason='manual refund'." Written, laminated, taped to the front desk.
- Test the flow once with a real $1 charge, refunded, with the session voided in Frappe. Document any UI weirdness.
- Decide BEFORE opening: who has refund authority? Manager only? Senior front desk? Anyone? Write it down.

**In the moment:**
- If documented flow doesn't exist: pay refunds out of the till, write a paper receipt, reconcile manually Sunday
- Bathhouse refund frequency is low; manual handling for 48 hours is survivable

---

## #9 — Permissions are too loose; junior staff can void or amend records

**The failure:** New front desk staff member trying to "fix" a stuck session at 1am clicks "void" or "amend" or "submit" on a record they shouldn't have. Cash reconciliation breaks. Audit gets murky.

**Why this matters:** ERPNext destructive buttons are often right next to safe buttons. New staff under pressure click first, ask later. Once you're in this state, the audit log helps but doesn't undo it.

**Before opening:**
- Audit role permissions on every DocType front desk touches. Front desk should have Read + Create + Submit. Not Cancel/Amend/Delete on Venue Session, Bathhouse Assignment, Cash Drop.
- Restrict System Manager role to Chris only. No staff account should have it.
- Test as a non-Chris user: try to delete a session, try to amend a submitted cash drop. Confirm both fail.

**In the moment:**
- If a session got destructively modified: pull audit log, reconstruct prior state, manually re-create with reason="recovery from accidental void"
- If audit log doesn't have it: ask staff what they remember, take their word, document, move on

---

## #10 — Dirty room accidentally marked clean

**The failure:** Staff mark a room clean when it wasn't actually cleaned, or front desk marks it clean because the cleaner verbally said it was done.

**Why this matters:** This is a guest experience failure, not just a data problem. In a bathhouse, cleanliness mistakes are high-impact. A guest finding a not-actually-clean room never returns.

**Before opening:**
- Require "cleaned by" field with timestamp on the clean status change
- Consider requiring cleaner role or manager role for room-clean status changes (front desk can request, cleaner confirms)
- For opening weekend, keep the cleaning workflow simple but strict — no shortcuts for "we know it's clean"

**In the moment:**
- Apologize, move the guest immediately to a confirmed-clean room
- Comp only if policy allows
- Log incident with which staff marked clean, which room, reported by which guest

---

## #11 — Overtime / expired session handling unclear

**The failure:** Guest stays beyond paid time. Staff see an overtime warning but don't know whether to charge, extend, ignore, or ask manager. Different staff apply different rules. Guest disputes the charge.

**Why this matters:** Inconsistent enforcement creates disputes and erodes the rule. Guests share with each other ("I never get charged overtime, just ask for [name]").

**Before opening:**
- Print overtime rules by asset type: locker, single room, deluxe room, suite. Different rates for different tiers.
- Define who can waive overtime (manager only? senior front desk?)
- Define whether overtime is automatically added by system, manually added by staff, or manager-approved

**In the moment:**
- Follow the printed policy
- Log waived overtime with staff initials and reason. No silent waivers.

---

## #12 — Chris becomes the single point of failure

**The failure:** Saturday at 11pm something breaks that only Chris knows how to fix. Chris is at a wedding / on a flight / asleep / unreachable. Hamilton has no one to call.

**Why this matters:** Per memory, you're the sole ERP architect, sole Frappe admin, sole Claude Code operator. Bathhouse staff operate at night; you operate during the day. This is genuinely not a sustainable on-call posture.

**Before opening:**
- Identify ONE other person who can do basics: restart bench on Frappe Cloud, view audit log, reset a stuck session, run a manual cash drop. Even part-time. Even Patrick or Andrew if they have technical interest.
- Document the basics in `docs/ops_runbook.md`. 5 procedures, max 2 pages. Not a manual — a cheat sheet.
- Create a paging chain: front desk → manager → tier-2 → Chris. You are tier-3 and only paged for genuine emergencies.

**In the moment:**
- Runbook handles 80% of incidents
- For the 20% that need Chris: have a phone number staff can text, acknowledge within 10 minutes, fix or defer to Monday
- Build a habit: every time you fix something at night, document HOW so the runbook covers it next time

---

# PART 3 — Front Desk Emergency Runbook

**Print this 2-page section. Tape it to the front desk. Staff use it during incidents.**

## When the system says "Key already assigned"

1. Walk to the other tablet
2. Find out who is assigning that key
3. Wait, or coordinate verbally about who takes the next-available key
4. Do NOT override; the system is correct

---

## When a guest's payment went through but their session didn't open

1. Stay calm; tell guest "let me sort this out, one moment"
2. Open Stripe dashboard on manager's phone
3. Verify the charge actually succeeded (not "pending")
4. If yes: open session manually in Frappe with reason "post-payment recovery", record payment ID in session notes, hand the key
5. If no: re-attempt the charge at the till
6. NEVER refund-and-recharge in the same minute (you'll double-charge)
7. Log the incident before end of shift

---

## When staff hand out the wrong key

1. Get the correct key back from the guest immediately, swap to right one
2. Update the system: cancel the wrong assignment, create the correct one
3. Reason field: "physical key handoff mismatch"
4. Log incident with staff initials before end of shift

---

## When a guest wants a refund

1. Verify the session is voidable (no excessive time used)
2. If session is voidable: void it in Frappe with reason "guest refund request", refund through Stripe dashboard
3. Record both the void reference and the Stripe refund ID together
4. If documented flow doesn't work: pay refund from till, write paper receipt with date/time/amount/reason/staff initials, give to manager, who hands to Chris on Sunday
5. NEVER refund cash and ALSO refund Stripe (double refund)

---

## When end-of-shift cash count doesn't match

| Variance | Action |
|---|---|
| Within ±$20 | Log variance with reason field. Submit cash drop. |
| $20 to $100 | Call manager. Recount together. Log with both initials. |
| Over $100 | Call Chris. Photograph cash, drawer, and screen. Hold cash drop until guidance. |

**No punishment for honest variance. Variance hidden = much bigger problem.**

---

## When the internet goes down

1. Switch tablets to backup internet (4G/5G hotspot, second ISP, etc.)
2. If still down after 30 seconds: pull the paper check-in form folder
3. For each new guest: fill paper form (name, time, key, payment, staff)
4. Take cash payments only during outage (no card)
5. Pull keys manually from board; photograph the key board hourly
6. When internet returns: keep using paper until end of shift
7. Sunday morning: enter each paper form into Frappe with reason "ISP outage manual check-in"

---

## When a guest reports their room is dirty

1. Apologize, move them immediately to a confirmed-clean room
2. Mark the original room as "Needs Cleaning" in Frappe
3. Note which staff marked it clean (in audit log)
4. Comp only if manager approves
5. Log incident before end of shift

---

## When you need to correct an audit log row (typo / mis-attribution)

Per **DEC-066** (decisions_log.md). Audit logs (`Asset Status Log`, `Comp Admission Log`) are append-only after T1-2 lands. You cannot delete rows — but you can record a correction.

**Workflow (admin-only):**

1. Identify the audit row that's wrong. Note its DocType (`Asset Status Log` or `Comp Admission Log`) and `name`.
2. Open a new **Hamilton Board Correction** in Frappe Desk.
3. Fill in:
   - **Target DocType** — `Asset Status Log` or `Comp Admission Log`
   - **Target Name** — the audit row's `name`
   - **Target Field** — optional; the specific field that's wrong (e.g. `reason`, `operator`)
   - **Old Value / New Value** — what the row says vs what it should say
   - **Reason** — REQUIRED — explain *why* the correction is being made (typo, mis-attribution, system glitch, operator dispute resolved, etc.)
4. Save. The Hamilton Board Correction row is itself audit-logged. Original audit row is untouched.
5. Forensic reconstruction = read the original audit row + any Hamilton Board Correction rows pointing at it.

**Who can do this:** Hamilton Admin (Chris) only — Hamilton Board Correction has no role permission rows so System Manager / Hamilton Admin are the only paths.

**When to use vs not use:**
- ✅ Typo: "operator was set to alice but should have been bob"
- ✅ Mis-attribution: "wrong status logged because of duplicate-tap before T0-1 idempotency landed"
- ✅ Genuine error: "OOS reason should have been Plumbing not Lock"
- ❌ "Hide a bad-looking row" — corrections are themselves audit-logged. There is no hiding.
- ❌ Operator-side typos — operators don't have access to Hamilton Board Correction. Operator brings the issue to a manager who logs the correction.

---

## Who to call

| Situation | Contact |
|---|---|
| Operational question, peak hours | Manager (on floor) |
| Manager unavailable, system issue (Tier-2 first call) | **Craig** (existing on-call contact — see venue front-desk binder for number) |
| Tier-2 first call unreachable (Tier-2 second call) | **Austin LeFrense — 905-920-0487** |
| Both Tier-2 contacts unreachable | Chris: [phone] |
| Cash variance over $100 | Chris directly |
| Wrong key + reconciliation looks broken | Chris directly |
| Internet down + Stripe also down | Chris directly |
| Anything that feels "really wrong" | Trust the feeling, escalate |

---

# PART 4 — Technical Preflight (For Chris)

**Complete before opening day. Each item is yes/no. No items remain in unknown state.**

## CI / Code

- [ ] PR #9 merged, all checks green on main
- [ ] CI runs green on at least 3 consecutive commits to main
- [ ] No skipped tests that would have caught opening-weekend issues (review the 56 currently skipped tests)
- [ ] Lint cleanup completed; ruff `continue-on-error` flipped back off
- [ ] Test fixtures factored into shared helpers (`make_test_venue_asset()`, etc.) — defers if needed but document the deferral

## Dependencies

- [ ] Decision made on `frappe/payments` for production: install (pinned commit, NOT develop) OR don't install (override 6 IntegrationTestCase tests with Path 2)
- [ ] No `develop` branch dependencies pinned in production deployment
- [ ] Frappe and ERPNext versions pinned to specific minor versions (not "latest")

## Frappe Cloud / Production

- [ ] **Frappe Cloud update policy configured per DEC-112** (`docs/operations/frappe_cloud_update_policy.md`):
  - Update window: **Monday OR Tuesday, 9 AM – 5 PM EST** only.
  - Approval: **Owner approval required before each update — never auto-update.**
  - Blackout window: **Thursday midnight through Monday 9 AM EST is a hard no-update zone.**
  - Pre-launch setup step: configure update-window pinning + auto-update disable in the Frappe Cloud dashboard manually.
- [ ] If the policy cannot be enforced via the dashboard: maintenance window negotiated directly with Frappe Cloud support, in writing.
- [ ] Backup procedure tested by actual restore (real restore drill, not "backup file exists")
- [ ] Restore time-to-recovery documented (how long does a full restore take?)
- [ ] No untested scheduler jobs can fire (verify Frappe Cloud cron settings)

## Permissions

- [ ] Front desk role: Read + Create + Submit on operational DocTypes only
- [ ] Front desk role: NO Cancel/Amend/Delete on Venue Session, Bathhouse Assignment, Cash Drop, Comp Admission Log
- [ ] Manager role: can Cancel/Amend with reason field required
- [ ] System Manager role: Chris only
- [ ] Tested as non-Chris user — confirmed destructive actions blocked

## Audit / Versioning

- [ ] Document Versioning enabled on: Venue Session, Bathhouse Assignment, Cash Drop, Comp Admission Log, Shift Record
- [ ] Audit Trail captures: actor (PIN), timestamp, device/IP, before/after values
- [ ] Tested with two-user modification — confirmed full attribution captured

## Staff accounts

- [ ] Each staff has unique login PIN (no shared "frontdesk" account)
- [ ] PINs are 4-digit minimum, not sequential, not birthdays
- [ ] PIN list stored in password manager (not on a sticky note)
- [ ] Staff trained: "you don't share your PIN, ever, even if it seems faster"

## Tax / Accounting

- [ ] Run 5 sample transactions: locker, room, upgrade, comp, retail
- [ ] Confirm invoice item, company, tax rate, price list, payment method are correct on each
- [ ] Bookkeeper/accountant has reviewed at least one test day-close
- [ ] Multi-location accounting setup verified (Hamilton vs other venues, if relevant)

## Hardware / Network

- [ ] Hamilton tablet count confirmed at **1** (DEC-111; single front-desk station). All tablets tested on Hamilton's actual Wi-Fi (not just home)
- [ ] Backup internet confirmed and tested (4G hotspot or secondary ISP)
- [ ] Tablets have screen lock with timeout (don't leave them unlocked at front desk)
- [ ] Stripe (or chosen processor) terminal hardware tested in Hamilton's actual network conditions

## People

- [ ] Tier-2 person identified and trained on the 5 basic recovery procedures
- [ ] Tier-2 has Frappe Cloud access (read-only minimum, full admin if trusted)
- [ ] Manager scheduled on the floor for opening Friday + Saturday + Sunday (no exceptions)
- [ ] Chris available by phone for the entire opening weekend (no flights, no off-grid)

## Documentation

- [ ] Front Desk Runbook (Part 3) printed and at every tablet station
- [ ] Refund procedure printed and at front desk
- [ ] Overtime policy printed and at front desk
- [ ] Cash variance policy printed and at front desk
- [ ] Tier-2 phone number written somewhere staff will find it at 11pm
- [ ] Chris phone number same

---

# Final note

The first version of this audit was written in the mindset of "what scares me most as an engineer about this system?" The revised version is written in the mindset of "what does Hamilton's manager need to know to run a successful opening weekend on imperfect software?"

That shift is the actual production-readiness move. Software doesn't have to be perfect to open. Operations do have to know how to recover when software is imperfect.

**My single sharpest recommendation:** Of the 12 risks above, the top 3 (paid-but-no-session recovery, staff trust, cash variance) are NOT engineering problems. They are training and process problems. Spend opening week prep on those, in that order, and the engineering risks below will mostly take care of themselves because trained staff handle imperfect software better than perfect software handles untrained staff.
