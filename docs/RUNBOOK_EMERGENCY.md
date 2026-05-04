# Hamilton ERP — Emergency Decision Tree Runbook

**Audience:** Front-desk operators and floor managers. Use this under stress.
**This file:** Fast triage only. Full procedures live in `docs/RUNBOOK.md`.
**Paper backup forms:** `docs/EMERGENCY_PAPER_FORMS.md`

---

## HOW TO USE THIS FILE

1. Find the scenario header that matches what you see.
2. Run the TRIAGE checks in order — stop at the first one that matches.
3. Follow NEXT ACTION exactly.
4. If the CALL CHRIS criterion is met, call immediately — do not wait.

**Chris's number:** _(add mobile number here before go-live)_
**Fiserv merchant support:** 1-800-872-7882 (24/7)
**Frappe Cloud status page:** https://frappecloud.com/dashboard/status

### Tier-2 Escalation Chain (when Chris is unreachable)

When this runbook says "call Chris" but Chris cannot be reached, escalate in this order:

1. **First call — Craig** (existing on-call contact; number kept in the venue front-desk binder).
2. **Second call — Austin LeFrense — 905-920-0487.**
3. If neither answers within 10 minutes, retry Chris and continue retrying every 5 minutes until contact is made.

See DEC-108 for the rule. See `HAMILTON_LAUNCH_PLAYBOOK.md` "Who to call" table for the same chain in the launch context.

---

---

## 1. SYSTEM COMPLETELY DOWN — Asset board won't load, blank screen or browser error

### TRIAGE

1. Look at the other tabs on the same tablet — do any Frappe pages load at all?
2. Check another tablet or phone on the venue WiFi — same problem?
3. Open your phone's hotspot and try loading the site on mobile data — does it load?

### NEXT ACTION

**If phone hotspot loads the site → network is down at the venue. Go to Scenario 3.**

**If nothing loads anywhere:**
1. Check if the Frappe Cloud site itself is down. Go to Scenario 11.
2. If Frappe Cloud is confirmed down: switch to paper immediately.
   - Paper forms: `docs/EMERGENCY_PAPER_FORMS.md`
   - Log every check-in, assignment, and cash transaction on paper.
   - Retroactively enter all paper records when the system comes back.

**If the site loads but the asset board page is blank:**
1. Hard-refresh the browser: **Cmd+Shift+R** (Mac) or **Ctrl+F5** (Windows/tablet).
2. If still blank, log out and log back in.
3. If still blank after re-login, this is a system issue — go to Scenario 5.

### CALL CHRIS IF

- System is unreachable from all devices AND phone hotspot test also fails AND it has been more than **15 minutes** during operating hours.

---

---

## 2. CARD TERMINAL NOT RESPONDING — Can't take card payments

### TRIAGE

1. Is the terminal screen completely dark (vs. showing an error code)?
2. Is there an error code on screen? Note it exactly.
3. If you have more than one terminal: is the problem on all of them, or just one?

### NEXT ACTION

**Terminal screen is dark:**
1. Unplug the terminal's power cable from the wall.
2. Wait 30 seconds.
3. Plug it back in and wait 60 seconds for it to fully boot.
4. If it comes back, try a test transaction.

**Terminal shows an error code:**
1. Note the exact error code.
2. Call Fiserv: **1-800-872-7882** — give them the error code and your MID: **1131224**.
3. Follow their instructions.

**Terminal still not responding after power cycle:**
1. Put up cash-only signage at the front door and desk immediately.
2. Accept cash only until the terminal is fixed.
3. Log every cash-only transaction on paper (customer name, amount, asset assigned).
4. Call Fiserv support with the error code.

### CALL CHRIS IF

- Terminal is down more than **30 minutes** during operating hours.
- Fiserv support cannot resolve it remotely.

---

---

## 3. NETWORK OUT — Internet down at the venue, system loads from cache or fails API calls

### TRIAGE

1. Check the WiFi icon on the tablet — is it connected to the venue WiFi at all?
2. Open a new browser tab and try loading `google.com` — does it load?
3. Test on your phone's mobile data — can you reach `hamilton-erp.v.frappe.cloud` from your phone?

### NEXT ACTION

**WiFi connected but no internet:**
1. Go to the router/modem (ask manager for location).
2. Unplug the power cable from the modem (the device connected to the wall/cable).
3. Wait 30 seconds. Plug back in. Wait 2 minutes for reconnection.
4. Try `google.com` again.

**Router cycle didn't fix it:**
1. Check if the venue has a backup internet line (ask manager).
2. If yes: switch to the backup line connection.
3. If no backup line: switch to cash-only mode immediately.
   - Put up cash-only sign at the door.
   - Log every transaction on paper for retroactive entry.
   - Do NOT attempt to process card payments without confirmed internet connectivity.

**Network is out with active occupied assets:**
1. Continue managing assets on paper.
2. Do not check out guests who are occupying assets until the system is back.
3. When system returns: enter all paper activity retroactively before the shift closes.

### CALL CHRIS IF

- Network is out more than **1 hour**.
- Network goes out mid-shift when assets are occupied and you cannot reach Frappe Cloud from your phone hotspot.

---

---

## 4. CAN'T LOG IN — Correct username and password are rejected

### TRIAGE

1. Is Caps Lock on? Check the keyboard indicator light.
2. Has your password been changed recently by a manager?
3. Can another operator log in on the same tablet with their own credentials?

### NEXT ACTION

**Caps Lock was on:**
1. Turn it off.
2. Type the password again.

**Another operator can log in but you can't:**
1. Click "Forgot Password" on the login page.
2. Check your email for a reset link. Click it and set a new password.
3. Log in with the new password.

**Email reset link is not arriving:**
1. Ask the floor manager to reset your account via Frappe Desk.
2. If manager is unavailable: continue operations under the manager's login (manager assumes responsibility for the shift log).
3. See RUNBOOK §3.2 for full account recovery steps.

**Nobody can log in at all:**
1. This is a site-wide authentication issue.
2. Check if the Frappe Cloud site is down (Scenario 11).
3. Switch to paper backup immediately.

### CALL CHRIS IF

- No operator can log in to the site at all AND the Frappe Cloud status page shows the site as up.

---

---

## 5. ASSET BOARD SHOWS WRONG STATUS — What the screen shows doesn't match reality on the floor

### TRIAGE

1. Hard-refresh the browser: **Cmd+Shift+R** (Mac) or **Ctrl+F5** (Windows/tablet).
2. Check if another browser tab on the same machine recently did something (assigned an asset, changed a status) that hasn't synced yet.
3. Check if this is on one asset only vs. the whole board looking wrong.

### NEXT ACTION

**Hard-refresh fixed it:**
- Done. The board was showing a stale cached state.

**Hard-refresh did not fix it — board still shows wrong statuses:**
1. Log out completely.
2. Log back in.
3. Check the board again.

**Still wrong after re-login:**
1. This requires a bench reload — manager only.
2. See RUNBOOK §3.4 for the bench reload procedure.
3. While waiting: manage assets manually, noting the current true state on paper.

**Important known issue (R-011):** The variance flag on cash reconciliation is a false alarm in Phase 1. If the variance flag fires, document it and move on — this is expected behavior until Phase 3 ships. Do not call Chris about variance flags alone.

### CALL CHRIS IF

- Status mismatch persists more than **5 minutes** after a bench reload.
- The board shows assets as available that you know are occupied (chargeback risk if re-assigned).

---

---

## 6. CASH DROP WON'T SUBMIT — System rejects the cash drop entry

### TRIAGE

1. Read the error message on screen exactly — does it say "missing fields", a field name, or something about network?
2. Is the declared_amount field filled in? Is it a positive number?
3. Is the timestamp field filled in?

### NEXT ACTION

**Error says a field is missing or invalid:**
1. Check each required field: timestamp, declared_amount, drop_type.
2. Fill in the missing field.
3. Submit again.

**Error says negative amount or invalid amount:**
1. Re-enter the declared amount. Must be a positive number (e.g. `245.00`).
2. Submit again.

**Error is about network connectivity:**
1. Check if the internet is working (load `google.com`).
2. If network is down, go to Scenario 3.
3. If network looks fine, wait 30 seconds and retry once.

**System keeps rejecting and you can't identify why:**
1. Do NOT keep trying — log the drop on paper instead:
   - Date, time, operator name, declared amount, envelope number.
2. Place the envelope in the safe as normal.
3. Enter the cash drop retroactively when the system is working.

**Important — blind cash control (DEC-005):** You should never see the system's expected amount before you submit your declared amount. If the system shows you an expected total before you submit, stop immediately. Go to Scenario 7.1 (RUNBOOK §7.1) and call Chris.

### CALL CHRIS IF

- The cash drop form shows you an expected-cash figure before you have submitted your declared amount.
- You cannot submit a cash drop and the shift is ending.

---

---

## 7. OPERATOR NO-SHOW OR QUITS MID-SHIFT

### TRIAGE

1. Is this a no-show (never arrived) or a mid-shift walkout?
2. Is there an open shift_record in the system for the missing operator?
3. Are there active occupied assets that the departing operator was managing?

### NEXT ACTION

**Operator is late (under 30 minutes):**
1. Wait. Do not close their shift in the system yet.
2. Continue operations as floor manager if needed.

**Operator is confirmed no-show or has quit:**
1. The existing operator's shift_record stays open in the system — do not close it manually.
2. Floor manager covers the desk under their own login.
3. At end of shift: log out of the departing operator's session via their account if accessible.
4. At shift close: floor manager reconciles the cash drop as normal.
5. Next morning: manager reviews the shift record and annotates any anomalies.

**Active occupied assets during the transition:**
1. Note the current state of all occupied assets on paper immediately.
2. Continue managing transitions (check-outs, cleanings) under manager login.
3. Record every transition in the system as it happens — do not batch them later.

### CALL CHRIS IF

- The operator walked out with cash on hand and you cannot account for the envelope.
- You cannot safely manage the floor with available staff.

---

---

## 8. VARIANCE FLAG FIRES UNEXPECTEDLY — Manager sees a mismatch alert on reconciliation

### TRIAGE

1. **Read observation 3908 first:** The variance system is a known false alarm in Phase 1 (R-011). The system hardcodes `system_expected = 0`, so every real reconciliation will flag a variance. This is expected.
2. Did you count the cash physically, independent of the system?
3. Check the `tip_pull_amount` field on the Cash Drop record — is it filled correctly?

### NEXT ACTION

**Phase 1 false-alarm (almost certainly the cause):**
1. Count the physical cash independently.
2. If the physical count matches the declared amount on the envelope — this is a false alarm. Document it and close the reconciliation.
3. The system variance flag does not reflect a real shortage until Phase 3 ships.

**Physical count does NOT match the declared amount:**
1. Count again — independently, a second time.
2. Check tip_pull_amount on the Cash Drop DocType — was a tip entered correctly?
3. If a real variance is confirmed: follow `docs/RUNBOOK_VARIANCE.md` (ships in Phase 3; if it doesn't exist yet, document the details and hold).

**Documenting a variance:**
- Record: date, shift, operator, declared amount, physical count, difference amount, any notes.

### CALL CHRIS IF

- Variance is more than **$50** and you cannot explain it.
- You see the same operator flagging variances across 2 or more shifts. Go to Scenario 9 immediately.

---

---

## 9. SUSPECTED THEFT — Multiple variance flags from the same operator over 2+ days

### TRIAGE

1. Map the dates and amounts of each flag to the specific operator on duty.
2. Rule out innocent causes: were those nights unusually busy? Was tip_pull_amount entered correctly on those shifts? Were any large drop amounts involved?
3. Do you have physical evidence (photos of envelopes, screenshots of reconciliation records)?

### NEXT ACTION

1. **STOP. Do not confront the operator.**
2. Do not change anything in the system — preserve all records as-is.
3. Gather evidence immediately:
   - Take screenshots of each variance flag and the associated Cash Drop records.
   - Photograph the relevant envelopes if they are still in the safe.
   - Write a timeline: dates, amounts, operator name, shift times.
4. Secure the timeline and screenshots — email them to yourself if needed.
5. **Call Chris before the operator's next scheduled shift.**

### CALL CHRIS

- **Immediately.** Do not wait. Do not take further action until you speak with Chris.

---

---

## 10. NETWORK OUT + CUSTOMER WANTS TO PAY BY CARD

### TRIAGE

- Is the network actually down, or is just the card terminal down? (These are different problems.)
- Network down = internet is out at the venue. Go to Scenario 3 first to confirm.
- Terminal down only = internet works but terminal is unresponsive. Go to Scenario 2.

### NEXT ACTION

**Network is confirmed down and customer wants to pay by card:**
1. Tell the customer: "Our card system is temporarily unavailable. We're cash-only right now."
2. Do not take the card and promise to charge it later — this creates a chargeback risk and breaks the audit trail.
3. Do not write down card numbers — this is a PCI violation.
4. If the customer cannot pay cash: politely offer to hold their spot for 10 minutes while they use an ATM, if there is one nearby.
5. If the customer leaves without paying: log the refused admission (customer description, time, asset that was being assigned). This is a revenue signal if it becomes a pattern.

**If refusals are happening repeatedly across multiple shifts:**
1. Log each one with date, time, and context.
2. Report the pattern to the manager and to Chris — repeated card failures during network outages signal that the backup internet line or mobile hotspot policy needs to be set up.

### CALL CHRIS IF

- More than 3 card-only customers turned away in a single shift due to network outage.

---

---

## 11. FRAPPE CLOUD SITE IS DOWN — Production URL doesn't load from any device

### TRIAGE

1. Try loading `hamilton-erp.v.frappe.cloud` from your phone on mobile data (not venue WiFi).
2. Check the Frappe Cloud status page: **https://frappecloud.com/dashboard/status**
3. Is the status page showing an incident or degraded service?

### NEXT ACTION

**Phone hotspot can't reach the site either AND Frappe Cloud shows an incident:**
1. This is a Frappe Cloud outage — nothing you can do at the venue to fix it.
2. Switch to paper backup immediately: `docs/EMERGENCY_PAPER_FORMS.md`
3. Log every transaction on paper for retroactive entry.
4. Check the Frappe Cloud status page every 15 minutes for updates.

**Phone hotspot can't reach the site BUT Frappe Cloud status page shows all systems operational:**
1. This might be a site-specific issue, not a platform outage.
2. Call Chris — he may need to restart the site from the Frappe Cloud dashboard.

**Venue WiFi can't reach the site but phone hotspot CAN:**
- This is a local network problem, not a Frappe Cloud problem. Go to Scenario 3.

### CALL CHRIS IF

- Frappe Cloud site is unreachable from mobile data AND the status page shows all systems up.
- Site is down for more than **15 minutes** during operating hours regardless of cause.

---

---

## 12. FORGOT MANAGER PIN

### TRIAGE

1. Is there another manager on duty or reachable by phone who can reset it?
2. Does the current manager still have access to the Frappe Desk (the admin back-end)?

### NEXT ACTION

**Another manager is available:**
1. Have the other manager log in to Frappe Desk.
2. Go to: Frappe Desk → Hamilton Settings → Manager PIN field.
3. Enter a new temporary PIN.
4. Use the temporary PIN to proceed with the current operation.
5. Change it to a permanent PIN after the shift.

**No other manager is available but you have Frappe Desk access:**
1. Log in to Frappe Desk with your manager credentials.
2. See RUNBOOK §3.5 for the full PIN reset procedure.

**No other manager, no Frappe Desk access:**
1. Operations that require a Manager PIN (comp admissions, certain overrides) cannot proceed.
2. Document everything that required a PIN and was skipped — annotate the shift record.
3. Complete those actions retroactively when a manager is available.

### CALL CHRIS IF

- No manager PIN is available and a situation arises that genuinely requires immediate manager authorization (e.g. a safety issue, a large comp decision, a customer dispute requiring override).

---

---

## 13. COMP ADMISSION LOG WON'T SUBMIT

### TRIAGE

1. Read the error message exactly. Does it mention a missing field, a "Manager PIN required" message, or a network error?
2. Are all required fields filled: reason_category, operator, and any linked document fields?
3. Is the Manager PIN attestation checkbox present and unchecked?

### NEXT ACTION

**Error says a required field is missing:**
1. Check each field: reason_category, operator name, any linked sales_invoice or session field.
2. Fill in the missing field.
3. Submit again.

**Error says "Manager PIN required":**
1. The operator needs to enter the Manager PIN to attest the comp.
2. Ask the manager to enter their PIN on the comp form.
3. If no manager is available: defer the comp log entry. Do not issue the comp without logging it.
4. Note: once Task 32 ships, this PIN requirement is enforced by the system. Until then, see RUNBOOK for current behavior.

**Persistent submission error not related to fields or PIN:**
1. Log the comp on paper: date, time, operator, guest description, comp type, reason.
2. Enter retroactively when the system is working.

### CALL CHRIS IF

- The system is accepting comp submissions without asking for a Manager PIN — this may indicate a permissions regression. Note the date and time and report it.

---

---

## 14. RECEIPT PRINTER OFFLINE OR OUT OF PAPER

### TRIAGE

1. Is the paper roll empty? Open the printer cover and check.
2. Is the printer powered on? Check the power light.
3. If powered on and paper is present: is the printer's IP address reachable? (Ask manager for IP or check printer label.)

### NEXT ACTION

**Paper roll is empty:**
1. Open the printer cover (refer to Epson TM-T20III manual if needed).
2. Insert a new paper roll — thermal side facing outward.
3. Close the cover. Printer should self-test and come back online.

**Printer is off or unresponsive:**
1. Check the power cable connection at the printer and at the wall.
2. Power cycle: unplug, wait 10 seconds, plug back in.
3. Wait 30 seconds for the printer to initialize.

**Printer is on and has paper but still not printing:**
1. The printer may have lost its network connection.
2. Power cycle the printer (unplug 30 seconds, replug).
3. If still unresponsive, ask the manager to check the printer's IP connectivity.

**Printer cannot be fixed quickly:**
1. Transactions can complete without a printed receipt.
2. Manager provides a handwritten receipt if the customer requires one.
3. Note: Hamilton likely has no spare printer on-site (per-venue procurement rule — spares are not maintained in a shared stockroom). If the printer is hardware-failed, a replacement must be ordered.

### CALL CHRIS IF

- Printer is hardware-failed (not paper, not power, not network) and no replacement is available.

---

---

## 15. LABEL PRINTER OFFLINE — Envelope label can't print

### TRIAGE

1. Is the Brother QL-820NWB powered on? Check the power light.
2. Is the label roll loaded and not empty?
3. Is this happening at the time of a Cash Drop submission?

### NEXT ACTION

**Label printer is off or unresponsive:**
1. Check the power cable.
2. Power cycle: unplug 30 seconds, replug. Wait 20 seconds.
3. Try printing again.

**Label roll is empty:**
1. Load a new DK-series label roll.
2. Try printing again.

**Pre-Task 30 (current state — label printing not yet integrated):**
- If Task 30 has not shipped yet: the label printer not working does not block Cash Drop submission.
- Operators do not write on envelopes — managers identify envelopes from the Frappe record.
- No action needed; proceed with the cash drop as normal.

**Post-Task 30 (once label printing is required for Cash Drop):**
- A label printer failure will block Cash Drop submission.
- This becomes a Scenario 6 issue — treat it as a Cash Drop submit failure.
- Log the drop on paper. Place the envelope in the safe. Enter retroactively when the printer is working.

### CALL CHRIS IF

- Label printer is hardware-failed and Task 30 has shipped (meaning Cash Drop submit is now blocked without a working printer).

---

---

## QUICK ESCALATION GUIDE

| Situation | Call Chris? | Timing |
|---|---|---|
| System down > 15 min during hours | Yes | After 15 min |
| Card terminal down > 30 min | Yes | After 30 min |
| Network out > 1 hour | Yes | After 1 hour |
| Nobody can log in, site is up | Yes | Immediately |
| Asset mismatch > 5 min after reload | Yes | After reload fails |
| Variance > $50 unexplained | Yes | After confirming real |
| Suspected theft (pattern) | Yes | IMMEDIATELY — before operator's next shift |
| Frappe Cloud down > 15 min | Yes | After 15 min |
| Operator quits with cash unaccounted | Yes | Immediately |
| Card system shows expected total before submit | Yes | Immediately |

---

*Companion document to `docs/RUNBOOK.md`. For full technical procedures, see that file.*
*Paper backup forms: `docs/EMERGENCY_PAPER_FORMS.md`*
*Last updated: 2026-05-01*
