# Hamilton ERP — Manager Training Manual

**Audience:** Shift managers and floor managers. You have an operations background but no software experience. This manual explains what Hamilton ERP expects from you, step by step, in plain English.

**Scope:** Cash reconciliation, variance investigation, comp/refund/void approvals, end-of-day close, escalation thresholds, and weekly/monthly responsibilities.

**Important — Phase caveat:** Hamilton ERP is launching in phases. Some features described here are **not yet built**. Each section is clearly labelled: "Live today" or "Coming in Phase X." Do not wait for those features — the workaround procedure is given inline.

---

## Table of Contents

1. Manager Role Overview
2. Daily Reconciliation Workflow
3. Variance Handling
4. Comp Approval
5. Refund Approval
6. Void Approval
7. End-of-Day Reconciliation
8. Comp / Refund / Void Review
9. Escalations to Chris
10. What Managers Must Never Do
11. Weekly Tasks
12. Monthly Tasks
13. Quick Reference — Variance Flag Meanings
14. Quick Reference — Escalation Thresholds

---

## 1. Manager Role Overview

### What separates your role from an operator

Operators run the cart. They check guests in, assign rooms and lockers, process sales, and drop cash into envelopes at end of shift. They never see expected totals, system figures, or variance — by design. That restriction is intentional (see "Why blind" below).

As a manager, you see everything operators do not:

| What you can see | Why you have access |
|---|---|
| Expected cash totals from the POS system | You need them to complete the three-way reconciliation |
| Variance flag and variance amount | You investigate and resolve discrepancies |
| Comp Admission Log | You review operator comp patterns |
| All Cash Reconciliation records | You complete and sign off each envelope |

Your additional responsibilities beyond operations:

- **Morning reconciliation** — count envelopes from the prior night's drops
- **Comp approval** — approve or deny operator comp requests (Phase 2; see §4)
- **Refund approval** — authorize cash or card refunds above threshold (Phase 2; see §5)
- **Void approval** — authorize cancellation of cart lines outside the self-service window (Phase 2; see §6)
- **End-of-day check** — confirm all records are closed before you leave
- **Error log review** — once a week, scan for new system errors
- **Pattern review** — weekly and monthly review of comp, refund, and void trends

### The blind cash principle — why operators are kept in the dark

The system uses what is called a **three-number triangulation** to detect cash theft:

- **A (POS expected):** What the computer says should be in the envelope, based on cash sales recorded during the shift. The system generates this number automatically. No human touches it.
- **B (Operator declared):** What the operator typed when they made their cash drop. They counted their till and typed a number before sealing the envelope.
- **C (Manager counted):** What you physically count when you open the envelope the next morning.

For triangulation to work, each number must come from an independent source. If the operator sees A before they type B, they can skim cash by a "safe" amount and still match the system's number. If you see B before you count C, you will unconsciously count toward the operator's stated figure even if you are completely honest — this is called anchoring and it happens to everyone. The system prevents both by hiding each party's number from the other until after both have committed their count.

This design is baked into every permission, every form, every field in the reconciliation workflow. Do not try to work around it, even when it feels slow. It protects you as much as it protects the venue.

---

## 2. Daily Reconciliation Workflow

### When to do this

The previous shift's envelopes are available for reconciliation the morning of your shift. Do this before anything else when you arrive.

### Step 1 — Open the Cash Reconciliation list

1. Log in to Hamilton ERP at your venue's desk terminal.
2. In the left menu, click **Cash Reconciliation**.
3. You will see a list of records — one per envelope from the prior shift(s).
4. Filter by yesterday's date if the list is long.

### Step 2 — For each envelope, open the linked Cash Drop record

1. Click on a Cash Reconciliation record.
2. At the top of the form you will see a link to the **Cash Drop** record. Click it.
3. The Cash Drop record shows:
   - **Operator** — who made the drop
   - **Shift date and shift identifier** — which shift this envelope belongs to
   - **Drop type** — Mid-Shift or End-of-Shift
   - **Drop number** — the sequence number of the drop within that shift
   - **Declared amount** — what the operator typed when they dropped
4. Take note of the declared amount, but do not let it anchor your count. Put the record aside. Pick up the physical envelope.

### Step 3 — Count the cash physically, before you look at any system figures

This step is the most important part of the whole process. Do not skip it or rush it.

1. Break the envelope seal.
2. Count all bills and coins. Use a counting tray if available.
3. Count again from scratch — two counts minimum.
4. Write your count on a separate scrap of paper. Do not type it yet.
5. If the two counts agree: proceed to step 4.
6. If the two counts disagree: count a third time, then proceed.

**Why count before looking at system figures?** Because if you see the declared amount first, your brain will reach for that number. You may stop counting at $217 because you saw $217 in the record, even if there is actually $194 in the envelope. The discipline of blind counting is the entire point of this workflow.

### Step 4 — Type your count into the form

1. Go back to the Cash Reconciliation record.
2. In the field labelled **Actual Count**, type the number you counted. Include cents (e.g. 194.50).
3. Do not type in any other field. Do not edit the operator's declared amount.
4. Click **Submit**.

### Step 5 — Read the result

After you submit, the system reveals three numbers:

| Label | What it means |
|---|---|
| **A — POS Expected** | What the POS system calculated based on recorded cash sales |
| **B — Operator Declared** | What the operator said they dropped |
| **C — Your Count** | The number you just typed |

The system will also show a **Variance Flag** — one of three values: **Clean**, **Possible Theft or Error**, or **Operator Mis-declared**.

### Phase 1 caveat — the variance flag is currently unreliable

**IMPORTANT — read this before interpreting any variance flag.**

During Phase 1 (the current launch phase), the system's calculation of A (POS Expected) is a placeholder. It always shows zero. This is a known issue documented in the project risk register as R-011.

**The practical effect:** Every real reconciliation will show a variance flag of "Possible Theft or Error" or "Operator Mis-declared" — because A (system expected) will always be zero, which will never match B or C (which will be real dollar amounts). The flag is noise, not signal, until Phase 3 ships the real calculator.

**What to do during Phase 1:**
- Ignore the variance flag entirely.
- Instead, do this manually: Is B (Operator declared) ≈ C (Your count)? If yes and within a dollar or two, treat the drop as clean. File the reconciliation.
- Only investigate if B and C diverge significantly — use the variance handling procedure in §3.

When Phase 3 ships the real calculator, this caveat will be removed and the variance flag will become the primary signal. Chris will notify all managers when Phase 3 goes live.

---

## 3. Variance Handling

### What the variance flags mean (post-Phase 3)

When the system's POS expected figure is real (post-Phase 3), the variance flag will mean:

**Clean** — A, B, and C are within tolerance of each other. No action needed. File the reconciliation. Move on.

**Possible Theft or Error** — A (POS expected) and B (Operator declared) agree reasonably, but C (Your count) is materially lower. The envelope contains less cash than both the system and the operator said should be there.

**Operator Mis-declared** — B (Operator declared) disagrees significantly from A (POS expected) and/or C (Your count). The operator's stated figure is the outlier.

### Investigating "Possible Theft or Error"

Before assuming theft, work through these common causes in order:

**1. Recount the envelope from scratch.** Miscounts happen. Do a full recount — pull everything out, sort by denomination, count bills and coins separately. If the new count resolves the discrepancy, update your actual count and resubmit.

**2. Check for a tip pull.** Card tips are paid from the till in cash at end of shift (the venue owes operators their card tips immediately; the processor settles to the bank account later). If the operator pulled card tips from the till, that amount should appear in the Cash Drop record under the field **Tip Pull Amount**. Subtract it: if (B − Tip Pull Amount) ≈ C, the envelope is clean.

**Example:** Operator declared $300. Your count is $258. Tip pull amount in the Cash Drop record shows $42. Adjusted: $300 − $42 = $258. That matches your count. Clean.

**3. Check for a mid-shift drop.** Operators can make multiple drops per shift. If there was a mid-shift drop earlier in the shift, that cash is in a separate envelope. Make sure you are not comparing a single end-of-shift drop against a total that spans multiple drops.

**4. Card terminal mistype.** Until Phase 2 (Task 37) ships integrated card reconciliation, a card sale typed as cash on the POS will inflate A (POS expected) by that amount. If you cannot reconcile, check whether there is a card receipt from the shift that does not correspond to a card line on the Sales Invoice list. This is a manual cross-check — time-consuming but occasionally necessary.

**5. Coin tray miscount.** Coins are easy to miscount. Recount the coin tray specifically if the gap is under $5.

**6. Genuine theft.** If you have worked through all five steps above and cannot explain the discrepancy, escalate to Chris immediately. See §9.

### Investigating "Operator Mis-declared"

This usually means the operator typed a wrong number when they made the drop — a fat-finger error ($27 instead of $127, for example). Compare B vs C:

- If C (your count) is correct and B (declared) is clearly a typo: note the discrepancy in the reconciliation notes field. No further action needed for an isolated incident.
- If it happens more than twice with the same operator in a week: raise it with Chris as a pattern, not an individual incident.

### Recount mechanics — what the system shows you during recount (post-Phase 3)

After Phase 3 ships, the system will implement recount attempt mechanics:

1. You submit your count.
2. If A ≈ B ≈ C within tolerance: Clean. Done.
3. If mismatch: the system says "Doesn't match. Recount." — nothing else. No dollar amount, no direction, no hint. This is intentional — any additional information breaks the triangulation.
4. You recount the physical cash and resubmit.
5. After three failed attempts, the system enters **reveal mode**: it shows all three numbers plus the variance categorization. At that point you pick a resolution, write a comment, and enter the **Final Cash Amount**.

**The Final Cash Amount is the number that flows into accounting.** It is not the POS expected figure. It is not the operator declared figure. It is the manager-entered figure after reviewing all available information and making a judgment call. This matters for tax: if the POS expected $300 but there is genuinely only $258 in the till, the venue should not remit HST on $300 of cash revenue it never received.

---

## 4. Comp Approval

**Comps** (short for "complimentary") are admissions given to guests at no charge — a loyalty reward, a promotional offer, or a manager's discretion call. Comps affect revenue, so they require a manager to sign off.

### When Task 32 ships (Phase 2)

1. Operator initiates a comp at the cart for a guest.
2. The system pauses and prompts for a **manager PIN**.
3. You walk to the cart terminal, verify the operator's stated reason ("guest is a loyalty card holder," "promo night," "my call — regular"), type your 4-digit manager PIN, and press Submit.
4. The comp processes. The Comp Admission Log records your identity alongside the operator's.
5. You can review all comps you approved in the Comp Admission Log.

### Today — pre-Task-32 (current state)

The manager PIN gate does not exist yet. Operators can issue comps without approval.

**This is a pre-go-live blocker.** Task 32 must ship before Hamilton opens to the public. Until then:
- Operators have been instructed to call you before issuing any comp.
- You should physically verify and document any comp in your shift notes.
- Review the Comp Admission Log at end of every shift to confirm no unauthorized comps were issued.

---

## 5. Refund Approval

A **refund** returns money to a guest — cash back or card reversal — after a sale has been completed.

### When Task 31 ships (Phase 2)

1. Operator initiates a refund above the threshold amount (threshold to be set by Chris before go-live).
2. System pauses and prompts for a **manager PIN**.
3. You verify the reason, type your PIN, refund processes.
4. The refund is recorded with your identity in the audit trail.

### Today — pre-Task-31 (current state)

There is no refund flow in the system. Emergency refunds require a manager to:

1. Log in to Frappe Desk (the back-end admin interface, separate from the operator cart).
2. Locate the relevant **Sales Invoice** (Frappe Desk → Accounting → Sales Invoice).
3. Cancel the Sales Invoice, then amend it if a partial refund is needed.

Only managers have access to Frappe Desk. Operators cannot perform this action. If a guest requests a refund and you are not present, the operator should take the guest's contact information and tell them a manager will follow up within 24 hours. Do not have operators attempt to cancel Sales Invoices themselves.

---

## 6. Void Approval

A **void** cancels a line item on the current cart before the sale is finalized — for example, an operator accidentally added the wrong item and needs to remove it before charging the guest.

### When Task 33 ships (Phase 2)

The workflow will work as follows:

- **Within 5 minutes of adding the line:** The operator can void it themselves without manager approval. This covers fat-finger errors.
- **After 5 minutes:** The system requires a manager PIN. You walk over, verify the reason, type your PIN, void processes.

### Today — pre-Task-33 (current state)

There is no void flow. The workaround is:

1. Operator adds the wrong item, charges the guest.
2. Operator performs a refund for the wrong item (which today requires Frappe Desk, as above — see §5).
3. Operator re-rings the correct item.

This creates a confusing audit trail (a sale plus a refund plus another sale for what was actually a single transaction). The audit trail is accurate, but it takes extra time to explain during reconciliation. Document these situations in your shift notes.

---

## 7. End-of-Day Reconciliation

At the end of your shift, or before you hand off to the next manager, run through this checklist. It takes 5–10 minutes when everything is in order.

### Checklist

**1. All Cash Drops have linked Cash Reconciliations submitted?**
- Go to Cash Reconciliation list.
- Filter by today's date.
- Every envelope from the shift should have a submitted reconciliation record.
- If any are missing: find the operator who made that drop, obtain the envelope, complete the reconciliation before leaving.

**2. Any unresolved "Possible Theft" flags?**
- Scan the reconciliation list for any variance flags that have not been resolved.
- Do not leave for the day with an unresolved "Possible Theft" flag.
- If you cannot resolve it tonight, document your investigation in the notes field and call Chris.

**3. Any orphan invoices?**
- An **orphan invoice** is a Sales Invoice that was created during a shift but never linked to a closing entry or a session. This can happen if the POS was interrupted mid-transaction.
- Once Task 35 ships, the system will email you a daily list of orphan invoices automatically. Until then, this is a manual check: Frappe Desk → Accounting → Sales Invoice → filter by today's date and status "Submitted" — any invoice without a linked Venue Session is an orphan.
- Resolve each by linking it to a closing entry or voiding it (Frappe Desk, manager only).

**4. POS Closing Entry submitted for the day?**
- The system creates a POS Closing Entry automatically when the shift closes.
- Confirm it exists: Frappe Desk → Retail → POS Closing Entry → filter by today.
- If it is missing, do not create one manually — call Chris.

**5. Bank deposit slip matches Final Cash Amount across all drops?**
- Sum the Final Cash Amount across all Cash Reconciliation records for the shift.
- Compare to the physical cash you are depositing.
- They should match. If they do not, investigate before making the deposit.

---

## 8. Comp / Refund / Void Review

At the end of every shift, spend five minutes reviewing the activity log.

### Comp review

- Go to Comp Admission Log.
- Filter by today's date.
- For each comp record, check: Is the reason category filled in? If the reason is "Other," is the free-text explanation adequate?
- A comp without a documented reason is an audit liability. If you find one, ask the operator to add a note while the shift is fresh.

### Patterns to watch for

| Pattern | What it may mean | Action |
|---|---|---|
| Same operator, multiple comps in one shift | Casual use of comps as a perk; operator may not understand the policy | Coaching conversation; no escalation unless it continues |
| Comp spike across multiple operators on a single night | Possibly a promotional event that was not entered in the system | Confirm with Chris; log as a legitimate promo in the record |
| Same guest comped repeatedly by same operator | Possible personal relationship influencing comps | Escalate to Chris |
| Refund spike | Could be a system error (wrong price loaded, wrong item) or a guest service issue | Investigate the common cause; if system error, page Chris |
| Void spike | Operators are miskeying regularly | Consider additional training; if hardware-related (sticky keys, etc.), flag to Chris |

---

## 9. Escalations to Chris

Call or text Chris directly for any of the following. Do not attempt to resolve these on your own.

**Cash:**
- A variance greater than $50 that you cannot explain after working through §3.
- Any suspicion of theft, even if you are not certain. "I think something is off" is enough — you do not need proof to call.
- The bank deposit amount does not match the day's Final Cash Amounts after completing reconciliation.

**System:**
- The asset board is blank or shows fewer assets than expected (59 total: 26 rooms, 33 lockers).
- An operator reports they can see expected cash totals or variance figures on their screen. This is a serious security issue — call immediately, do not wait until morning.
- The system is down completely and guests are at the door.
- A POS Closing Entry is missing and cannot be found in Frappe Desk.

**People:**
- An operator quits or goes no-show mid-shift.
- A guest situation escalates beyond normal operations (medical, safety, law enforcement).

**Reference:** For system outages, see `docs/RUNBOOK_EMERGENCY.md` when it ships. Until then, Chris is the single point of contact for all system emergencies.

### Escalation contact

Chris Srnicek: csrnicek@yahoo.com

For system support (Frappe platform issues — site is down, database error, deploy failed): these are handled by Frappe Cloud support. Chris will open the ticket; do not attempt to contact Frappe Cloud yourself.

---

## 10. What Managers Must Never Do

These are hard rules. Each one exists because the consequence of violating it is either a security failure, an audit problem, or a compliance risk.

**Never approve a comp without verifying the operator's reason.**
When Task 32 ships, your PIN on a comp record is a legal signature of your approval. If you approve without verifying and that comp is later questioned, your name is on the record. "I just typed my PIN without checking" is not a defense.

**Never adjust an operator's declared amount or your own actual count after submission.**
The Cash Reconciliation record is immutable once submitted. Frappe does not allow edits to submitted documents. If you discover a mistake in your own count, document it in the notes field with a timestamp and your explanation. Do not attempt to cancel and resubmit to "fix" the number — that creates a gap in the audit log.

**Never manually create a POS Closing Entry to fix a discrepancy.**
A missing POS Closing Entry is a symptom, not the problem. Creating one manually to make the numbers balance covers up whatever caused it to be missing. Instead: investigate the cause, document it in your shift notes, and call Chris if you cannot identify it.

**Never share your manager PIN.**
Your PIN is your identity in every approval record. If you share it, you lose the ability to prove you were not involved in actions taken under your PIN. If you believe your PIN has been compromised, contact Chris immediately to have it reset.

**Never mark a "Possible Theft" reconciliation as Clean without investigation.**
Filing a "Possible Theft" flag as Clean without working through §3 is a compliance failure. If you genuinely cannot investigate at the moment (shift is chaos, you are short-staffed), write a note in the record stating you will investigate and give a time. Then actually investigate. Do not let it sit.

---

## 11. Weekly Tasks

Set aside 30 minutes at the end of your last shift of the week.

**Variance pattern review**
- Pull up Cash Reconciliation list for the past 7 days.
- Note any recurring variance flags on the same operator's drops.
- A single incident is usually an error. Two or more in a week with the same operator is a pattern worth documenting. Three or more warrants a call to Chris.

**Comp/Refund/Void totals**
- Export or count the Comp Admission Log entries for the week.
- How many comps total? What is the total declared value of comped admissions? Is this consistent with prior weeks or spiking?
- Note any operator whose weekly comp count is significantly above average.

**Float balance confirmation**
- The standard float is $300 per operator per active shift (configurable in Hamilton Settings).
- Confirm the physical cash in the safe matches $300 × (number of operators who had active shifts this week and have not yet been reconciled).
- Discrepancies in the float are reconciled at shift start, not shift end — but a weekly audit catches anything that slipped past.

**Bank deposit sign-off**
- Review the week's bank deposit receipts against the week's Final Cash Amounts across all Cash Reconciliation records.
- Sign off (physically or in your manager notes) that they match.
- If they do not: investigate before the next bank run.

---

## 12. Monthly Tasks

These take about an hour and are best done in the first week of each month, after the prior month's records are all filed.

**Period-close coordination with bookkeeper**
Once Hamilton's bookkeeper is onboarded, you will hand them a summary of the month's Cash Reconciliation records, any unresolved variance flags, and the comp/refund/void totals. A detailed procedure will be provided in `docs/training/bookkeeper_monthly.md` (not yet written). Until then, call Chris for guidance on the monthly close.

**Sales tax remittance review**
Hamilton collects Ontario HST at 13% on all admissions. The 13% is already included in the prices guests pay (prices are HST-inclusive). The remittance to CRA is calculated by the bookkeeper from the Sales Invoice records.

Your role in this review: confirm that the Sales Invoice total for the month matches the sum of Final Cash Amounts from Cash Reconciliation records for that month, plus any card sales from the POS. If they diverge materially, there may be an orphan invoice or a reconciliation error. Flag it before the bookkeeper files the HST return.

**Comp pattern review — operator by operator**
Pull the Comp Admission Log for the full month. Sort by operator. Review each operator's total comp count and declared reasons. You are looking for:
- One operator accounting for a disproportionate share of comps
- A shift in reason categories (a lot of "Manager Decision" with thin explanations)
- Comps concentrated on specific nights (possible promo not recorded in the system)

Bring findings to Chris in your monthly check-in.

---

## 13. Quick Reference — Variance Flag Meanings

| Flag | What it means | First action |
|---|---|---|
| **Clean** | A, B, C within tolerance | File the record. No action. |
| **Possible Theft or Error** | Your count (C) is materially below POS expected (A) and operator declared (B) | Recount. Check tip pull. Check for mid-shift drop. Check card mistype. If still unexplained, call Chris. |
| **Operator Mis-declared** | Operator's declared amount (B) is the outlier | Confirm your count is correct. If so, note as likely operator error. If pattern repeats with same operator, call Chris. |

**Phase 1 reminder:** The variance flag is currently unreliable (system_expected is stubbed at zero). Ignore the flag. Compare B vs C manually.

---

## 14. Quick Reference — Escalation Thresholds

| Situation | Escalate to Chris? |
|---|---|
| Variance under $10, single drop, no pattern | No — document and move on |
| Variance $10–$50, single drop, explained by tip pull or recount | No — document the explanation |
| Variance over $50, any cause | Yes — call Chris |
| Variance under $50, same operator, 2+ times in one week | Yes — call Chris |
| Any suspicion of theft regardless of amount | Yes — call Chris |
| Operator sees expected totals on screen | Yes — call Chris immediately, this is a P0 security incident |
| System down, guests at door | Yes — call Chris immediately |
| POS Closing Entry missing | Yes — call Chris |
| Bank deposit doesn't match Final Cash Amounts | Yes — call Chris before making the deposit |

---

*This manual reflects Hamilton ERP Phase 1. Last updated: 2026-05-01. Sections marked "Phase 2" or "Phase 3" describe features not yet in production. When those phases ship, this manual will be updated. If you are reading a section that says a feature is "coming" but it has already shipped, ask Chris for an updated copy.*
