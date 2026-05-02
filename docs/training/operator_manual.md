# Hamilton ERP — Front-Desk Operator Training Manual

**Audience:** Front-desk staff. No software background assumed.
**Version:** Phase 1 (Asset Board + Session Lifecycle + Retail Cart)
**Last updated:** 2026-05-01

---

## Before you read anything else

This system runs on an iPad at the front desk. You will log in with your own account. Everything you do is recorded under your name — check-ins, cash drops, vacates, all of it. This protects you as much as it protects the venue.

If something looks wrong and you're not sure what to do, **stop and call your manager.** Cash mistakes compound. A wrong entry is much harder to fix after the fact than before.

---

## 1. What you'll see when you log in

After logging in, you land on the **Asset Board** — the main screen you'll use for your entire shift.

The board shows every room and locker in the venue. Each one is represented by a small coloured tile with the room code (e.g. "R-01", "Lckr-14") printed on it.

### The colour system

The tile colour tells you the status at a glance:

| Colour | Status | What it means |
|---|---|---|
| **Dark green** (green border) | Available | Empty and clean. Ready for a guest. |
| **Dark red** (red border) | Occupied | A guest is in this room or locker right now. |
| **Dark amber** (amber/orange border) | Dirty | Guest has left. Room needs to be cleaned before the next guest. |
| **Dark purple** (purple border) | Out of Service | Room is not available — broken, deep cleaning, etc. |

You will never see a status word printed on the tile itself. The colour is the signal. If you're ever unsure, tap the tile to expand it and you'll see the full details.

### Overtime tiles

If a guest has been in a room past their expected stay time (6 hours), the tile **pulses** (it fades in and out slowly) and shows a red badge that says something like **"14m late"** or **"2h 5m late."**

That's your cue to check in with the guest — they may need to extend or be ready to check out.

If a stay is within the last 60 minutes, you'll see **"45m left"** in red text on the tile. That's a heads-up, not urgent yet.

### Tabs at the top

The board is split into tabs across the top:

- **Lockers** — all 33 lockers
- **Single** — single standard and deluxe rooms
- **Double** — double deluxe rooms
- **VIP** — VIP-tier rooms (e.g. Glory rooms)
- **Waitlist** — guests waiting for an asset (Phase 2, not yet active)
- **Other** — anything that doesn't fit the above categories
- **Watch** — a single tab that collects all overtime tiles and all Out of Service tiles across every category. Use this tab for a quick "anything urgent?" scan.

The Watch tab has a pulsing red badge on it when there are any overtime or OOS (Out of Service) tiles. When the badge is gone, nothing urgent needs attention.

---

## 2. Start of your shift

### Step 1 — Log in with your own account

Open the Hamilton ERP site on the iPad. Type your username and password. Do not use anyone else's account. Every action is logged to the account that's signed in.

### Step 2 — Count the float

The **float** is the starting cash in the till — a fixed amount ($200 by default; your manager will confirm if this is different at your venue) that stays in the drawer across shifts. It is NOT yours to drop. It stays behind for the next shift.

Before you do anything else, count the cash in the float bag or till drawer. It should match the float amount. If it doesn't, note the discrepancy and tell your manager before proceeding.

### Step 3 — Review the asset board

Spend 30 seconds scanning the board before your first transaction:

- Are any tiles purple (Out of Service)? Know which rooms are unavailable.
- Are any tiles pulsing (Overtime)? Those are carry-overs from the prior shift. If the guest is still present, that's expected. If the room should be empty, tell your manager.
- Are any tiles amber (Dirty)? Those rooms need cleaning before they can be assigned.

### Step 4 — Start your shift

Tap **Start Shift** (or the equivalent button your manager shows you on your first day). The system records the exact time your shift began. This timestamp is used later when the manager reconciles cash.

---

## 3. Checking a guest in

### Admission only (no retail items)

1. Tap the green (Available) tile for the room or locker the guest wants.
2. The tile expands to show its details. Tap **Assign Guest.**
3. The system prompts for payment. Choose **Cash** or **Card.**
   - **Cash:** count the guest's money, verify it equals or exceeds the price, then confirm. The system will show you the change to return (for example: "Price $36.00 — Cash received $40.00 — Change $4.00").
   - **Card:** ring it on the terminal. Once the terminal approves, confirm in the system.
4. The tile turns red (Occupied). The guest is checked in.

### Admission + retail items

1. Tap the retail tab (e.g. **Drink/Food**) to see available items.
2. Each tap on a retail tile adds one of that item to the cart. Tapping the same tile again adds another (it increments the quantity).
3. The cart appears at the bottom of the screen as a slide-up drawer. Tap the drawer to expand it and see the full breakdown: items, subtotal, HST 13%, and total.
4. To remove an item, tap the minus (−) button next to it in the drawer. Reducing to zero removes the line.
5. When you're ready to pay, tap **Cash payment** in the drawer.
6. A payment modal opens showing the total. Type in the cash the guest hands you. The modal shows the change owed in real time. The **Confirm** button only activates when the cash received is enough to cover the total.
7. Tap Confirm. The system creates the sale record, the cart clears, and a confirmation toast shows the invoice ID and the change to return.
8. After payment, go back to the asset board. Tap the green tile for their room or locker and tap **Assign Guest** to complete the check-in. The tile turns red.

**Note on pricing:** All room and locker prices are HST-inclusive. The price you see is the price the guest pays — the system handles the tax calculation behind the scenes. Retail items (drinks, snacks) show a subtotal + 13% HST breakdown in the cart drawer.

**Current prices (Hamilton):**

| Asset | Price (HST-inclusive) |
|---|---|
| Locker | $29.00 |
| Single Standard Room | $36.00 |
| Single Deluxe Room | $41.00 |
| Glory Hole Room | $45.00 |
| Double Deluxe Room | $47.00 |

---

## 4. End of a guest's stay (vacating a room)

When a guest is done:

1. Tap the red (Occupied) tile for their room or locker.
2. Tap **Vacate.**
3. Two sub-buttons appear:
   - **Key Return** — the guest came to the desk and returned the key or wristband themselves. This is the normal path.
   - **Discovery on Rounds** — you found the room empty during a walkthrough and the guest had already left without formally checking out. Use this when no one returned a key.
4. Tap the appropriate button. The tile changes:
   - **Rooms (Single, Double, VIP)** — tile turns amber (Dirty). The room needs cleaning before it can be used again.
   - **Lockers** — tile goes straight back to green (Available). Lockers don't require a cleaning step.

### Marking a room clean

After cleaning a room:

1. Tap the amber (Dirty) tile.
2. Tap **Mark Clean.**
3. The tile turns green (Available). It's ready for the next guest.

---

## 5. Out of Service (OOS)

Use Out of Service when a room or locker cannot be used — broken plumbing, a maintenance job is scheduled, deep cleaning needed, etc.

### Setting a room Out of Service

1. Tap the tile (it can be green/Available or amber/Dirty — you cannot set OOS on an occupied room).
2. Tap **Set Out of Service.**
3. A dropdown appears. Pick the reason:
   - Plumbing
   - Electrical
   - Lock or Hardware
   - Cleaning required (deep)
   - Damage
   - Maintenance scheduled
   - Other (requires a written note)
4. Confirm. The tile turns purple.

The reason is required — there is no way to skip it. If "Other" is selected, a text box opens and you must type a brief note (e.g. "bed frame cracked").

### Returning a room to service

1. Tap the purple (OOS) tile.
2. Tap **Return to Service.**
3. A confirmation screen appears showing who set it OOS, the reason, and how long ago. It also tells you that your name and the current time will be recorded as the person who cleared it.
4. Tap **Confirm reason resolved.** The tile turns green (Available).

---

## 6. Comps (free or discounted admission)

A **comp** means giving a guest free (or discounted) admission. This is different from a sale — it doesn't generate revenue, but it does create a record.

1. Tap the Available (green) tile for the room or locker.
2. Tap **Assign Guest.**
3. In the cart or admission screen, select the comp item. The price shows as $0.00.
4. You will be required to select a **comp reason**:
   - Loyalty Card
   - Promo
   - Manager Decision
   - Other (requires a written note)
5. **Manager PIN required.** A manager PIN step is being built (not yet available in Phase 1). Until it is, follow your manager's instructions for how to authorize a comp manually.
6. Submit. The tile turns red. A Comp Admission Log entry is created automatically — the comp is tracked and the manager can see it during reconciliation.

---

## 7. Cash drops (mid-shift and end-of-shift)

A **cash drop** means you count the cash in the till, pull out everything above the float amount, seal it in an envelope, and put it in the safe. You do this at least once at the end of your shift, and possibly once in the middle of a long shift.

### Why the system is blind

You will **never** see an "expected total" on the cash drop screen. The system only shows you what you type. This is intentional — it's called a **blind drop** system. The manager reconciles the numbers separately. This protects everyone: you can't be pressured to match a number, and the system can detect discrepancies without anyone gaming the count.

### How to do a cash drop

1. Count all the cash in the till.
2. Set aside the float amount ($200 — or the amount your manager confirmed). That stays in the drawer.
3. The rest is your drop amount.
4. Open the **Cash Drop** form in the system.
5. Select the drop type: **Mid-Shift** or **End-of-Shift.**
6. Type the dollar amount you counted (e.g. `$143.50`). Do not round, do not guess — type the exact count. This number is your declaration. If your count is $143.50, type $143.50.
7. If you pulled card tips from the till (see Section 8 below), enter that amount in the **Tip Pull Amount** field.
8. Tap Submit.
9. **The system will print an adhesive label** (label printing is being built — see below). Affix the label to the envelope.
10. Seal the envelope. Drop it in the safe.

**Important:** Do not write anything on the envelope by hand. The label is the record. If label printing isn't live yet, leave the envelope unmarked — the manager identifies envelopes by the Cash Drop record in the system, not by handwritten notes. A handwritten number on an envelope can cause disputes; a blank envelope with a system record cannot.

---

## 8. Tip pulls (taking your card tips in cash tonight)

Card tips are processed electronically and settle to the venue's bank account 1–2 business days later. If you want your card tips in cash at the end of your shift tonight, you do a **tip pull**: you take the cash equivalent from the till now, and the system adjusts the expected totals so the cash drop doesn't flag as short.

### How it works (Phase 1)

1. At the end of your shift, check your terminal batch report for total card tips earned.
2. Round your card tip total **up** to the nearest $0.05 (Canada's nickel rule). Example: $12.67 in card tips → round up to $12.70. Take $12.70 from the till.
3. On the Cash Drop form, type `$12.70` in the **Tip Pull Amount** field.
4. Type your remaining cash drop in the **Declared Amount** field as usual (after subtracting the float, but NOT subtracting the tip pull — the system adjusts for that separately).
5. Submit.

**Take exactly what you typed.** Not $13. Not $12.65. The typed amount is what the system uses to adjust the reconciliation. If you take a different amount than what you typed, the recon will show a false variance and the manager will have to investigate.

---

## 9. End of your shift

1. Do your **End-of-Shift cash drop** (Section 7 above, selecting the "End-of-Shift" drop type).
2. Count and confirm the float you are leaving behind in the till. It should equal the float amount ($200, or your venue's configured amount). If it doesn't, note the difference and tell your manager.
3. Tap **Close Shift.** The system records your shift end time and queues a POS Closing Entry for accounting purposes (this happens in the background — you don't need to do anything else for it).
4. Hand off to the incoming operator. Tell them:
   - Any rooms currently OOS and why
   - Any overtime rooms that haven't resolved
   - Anything unusual that happened during your shift

---

## 10. Common situations

### "The terminal charged the guest the wrong amount."

This is a terminal-side error. Flag it to your manager. The terminal and the system don't talk to each other yet in Phase 1 — a Phase 2 update will link them so this can't happen. Until then, the manager handles corrections.

### "I rang an item through the cart but the amount or item was wrong."

The ability to void a cart line is being built (Phase 1 doesn't have it yet). Until that feature ships, flag this to your manager — they will ring the correct amount and apply a refund for the wrong one. Do not try to compensate by ringing $0.01 and refunding or by doing workaround entries. That corrupts the audit trail and is harder to fix than the original mistake.

### "A guest doesn't remember which locker they were assigned."

Look at the Lockers tab on the asset board. Occupied lockers show a start time. Ask the guest roughly what time they checked in, and match it against the tiles. The tile with the closest start time to their arrival is likely theirs.

### "I can't see the expected cash total anywhere."

That's correct — by design. Operators are not shown expected totals. Only managers see reconciliation data. If you're looking for it because you think your count is wrong, recount the physical cash. That's the right step.

### "A tile is overtime but the guest is still in the room."

That's normal — the timer counts from check-in and the system has no way to know the guest is intentionally staying longer. The tile will pulse until they check out. You may want to let the guest know they're past their expected time and check if they'd like to extend (Phase 2 will add a formal "Extend Stay" button).

### "A tile is purple (OOS) but I don't know why."

Tap the tile. The expanded view shows the reason, who set it, and how long ago. If it looks like a mistake, call your manager rather than returning it to service on your own.

---

## 11. What you should never do

**Do not write on cash drop envelopes by hand.** The label the system prints is the official record. Handwriting on the envelope creates disputes. Until label printing is live, leave envelopes blank — the manager uses the system record to identify them.

**Do not log in as another operator.** Every action is tied to the account that's signed in. Logging in as someone else misattributes their sales, their drops, and their errors to you (and yours to them). This also breaks the audit trail and cannot be undone after the fact.

**Do not ring $0.01 or $0.00 and then refund it as a workaround.** If something went wrong, flag it. Fake entries corrupt the audit trail and can make the situation much harder to resolve.

**Do not take a different tip pull amount than what you typed.** If you type $12.70 in the Tip Pull Amount field, take exactly $12.70 from the till. Taking $13 or $12 causes a reconciliation discrepancy that looks like a cash error.

**Do not count the float as part of your drop.** The float ($200 or your venue's configured amount) stays in the till. Only count and drop cash above that amount.

**Do not eyeball the cash drop amount.** Count the bills and coins. The number you type is your declaration — it becomes part of the official record that the manager compares against the sales totals.

**Do not try to "fix" discrepancies on your own.** If you think your count is off, recount. If it's still off, submit your count as-is and tell your manager. The manager handles reconciliation. Trying to adjust by ringing a fake transaction or choosing a different drop amount makes the problem worse.

---

## 12. When to call your manager

Call your manager for any of these situations:

- **A variance flag fires** — after the manager completes a cash reconciliation, if your declared amount didn't match, they will come to you. That conversation is theirs to initiate — don't be alarmed. Just be ready to walk through your count.
- **A customer dispute during a transaction** — if a guest argues about a charge, price, or comp eligibility, don't negotiate. Get the manager.
- **A refund is needed** — refunds require a manager PIN (Phase 2). For now, no operator can process a refund unilaterally. Get the manager.
- **Terminal or system login problems** — see `RUNBOOK_EMERGENCY.md` (posted at the front desk). For anything not covered there, call the manager.
- **You're unsure what to do** — "I don't know" is the right thing to say. Guessing with cash is always more expensive than asking.

---

## Quick reference

| Tile colour | Status | Next action |
|---|---|---|
| Green | Available | Assign to a new guest |
| Red | Occupied | Vacate when guest is done |
| Amber | Dirty | Mark Clean after cleaning |
| Purple | Out of Service | Return to Service when fixed |
| Red + pulsing | Overtime | Check on the guest |

| Drop type | When to use |
|---|---|
| Mid-Shift | Any time during your shift when the till is getting full |
| End-of-Shift | Last thing before closing shift; leave float behind |

**Float amount:** $200 (confirm with your manager — this is configurable per venue).

**HST rate:** 13% (Ontario). Applied to retail items at checkout. Asset prices are already HST-inclusive.

---

*This manual covers Phase 1 of Hamilton ERP. Features marked as "being built" or "Phase 2" will be added in a future update. Your manager will brief you on any changes before they go live.*
