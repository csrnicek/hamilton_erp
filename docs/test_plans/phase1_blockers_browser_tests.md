# Phase 1 BLOCKER Browser Tests — Launch Verification

**Purpose:** Operator-runnable walkthroughs to verify all 8 Phase 1 BLOCKERs are
production-ready before the Hamilton go-live URL flips.

**Who runs these:** A manager or senior operator who knows the system well. Each
test section is self-contained — run them in order, but each can stand alone.

**Environment:** `hamilton-erp.v.frappe.cloud` (live site). Do NOT run on
`hamilton-unit-test.localhost` — that site may have corrupted seed data.

**Hardware connected before starting:**
- Brother QL-820NWB label printer — LAN IP confirmed in Hamilton Settings
  (`label_printer_ip` field)
- Epson TM-m30III receipt printer — LAN IP confirmed in Hamilton Settings
  (`receipt_printer_ip` field)
- APG VASARIO cash drawer — RJ-11 connected to TM-m30III DK port
- iPad at front desk station — logged in as Hamilton Operator (test account)
- Manager login credentials available (Hamilton Manager role)

**Test customers (use these names throughout):**
- Walk-in cash customer: **Alex Thornton**
- Walk-in comp customer: **Jordan Reyes**
- Error-scenario customer: **Marcus Bell** (used for typo/void scenarios)

---

## BLOCKER 30: Cash Drop Envelope Label Print Pipeline

**Design reference:** `docs/hamilton_erp_build_specification.md` §7.4
**Risk:** Without printed labels, operators must handwrite declared amounts on
envelopes. Handwriting can be altered after the fact, which defeats the
blind-cash anti-theft design (DEC-005).

### Pre-conditions

1. Hamilton Settings has `label_printer_ip` set to the Brother QL-820NWB's
   static LAN IP (e.g. `192.168.1.20`).
2. Brother QL-820NWB is powered on, online (green LED), and loaded with
   DK-2205 continuous tape roll.
3. An active shift is open on the system (Shift Record with `status = Open`).
4. At least one Sales Invoice has been submitted this shift (any amount).
5. Logged in as Hamilton Operator (test account `operator_test@hamilton.ca`).

### Test scenarios

**Scenario B30-1: Standard mid-shift cash drop prints a complete 8-field label**

1. On the Hamilton cart UI, tap "Cash Drop."
2. Count $120 in bills (3 × $20 + 6 × $10). Enter `120.00` in the
   "Declared Drop Amount" field.
3. Select Drop Type: "Mid-Shift."
4. Tap "Submit Drop."

   EXPECTED: Brother QL-820NWB prints one label within 3 seconds.
   Label must contain all 8 fields, each on its own line:
   - `Club Hamilton`
   - Today's date in YYYY-MM-DD format (e.g. `2026-05-01`)
   - Operator name matching the logged-in user (e.g. `Alex Operator`)
   - Shift identifier matching the active shift (e.g. `Evening`)
   - `Mid-Shift Drop`
   - `Drop 1 of Shift` (or `Drop 2` if a prior drop already happened)
   - `$120.00`
   - Timestamp in HH:MM format (e.g. `21:47`)

5. Affix the printed label to an empty envelope. Seal the envelope and
   physically examine the label.

   EXPECTED: All 8 fields are legible. No handwriting on the envelope.

6. Open the Cash Drop record in Frappe desk (as manager).
   Navigate to: Desk > Hamilton ERP > Cash Drop > the record just created.

   EXPECTED: Record shows `declared_amount = 120.00`, `drop_type = Mid-Shift`,
   `drop_number = 1`, `label_printed = True`, `operator` = logged-in user,
   `shift_record` linked to the active shift.

**Scenario B30-2: End-of-shift cash drop label shows correct drop type**

1. On the Hamilton cart UI, tap "Cash Drop."
2. Enter `185.00` in the "Declared Drop Amount" field.
3. Select Drop Type: "End-of-Shift."
4. Tap "Submit Drop."

   EXPECTED: Label prints. Drop Type field on label reads `End-of-Shift Drop`.
   Drop number increments from B30-1 result (e.g. `Drop 2 of Shift`).

**Scenario B30-3: Sequential drop numbers increment correctly within a shift**

1. Submit a second Mid-Shift drop for `$50.00`.

   EXPECTED: Label prints with `Drop 3 of Shift` (or whatever the correct
   sequential number is for this shift). Drop numbers never repeat within
   a shift.

**Scenario B30-4: Print failure does NOT silently suppress the error**

1. Disconnect the Brother QL-820NWB from the network (unplug the LAN cable
   or turn the printer off).
2. On the cart UI, attempt a Cash Drop for `$75.00`.
3. Tap "Submit Drop."

   EXPECTED: System displays an error message visible to the operator:
   "Label printer unreachable — drop not submitted. Reconnect printer
   and try again." (or similar). The Cash Drop record is NOT created in
   the database.

4. Reconnect the printer. Retry the drop.

   EXPECTED: Drop submits, label prints, record created.

**Scenario B30-5: Template is sourced from Hamilton Settings, not hardcoded**

1. As manager, open Hamilton Settings in Frappe desk.
2. Note the value in `printer_cash_drop_template_name`.
3. Open Label Template list. Find the template with that name.
4. Verify the template's `data_fields` references the `Cash Drop` DocType.

   EXPECTED: Template name in Hamilton Settings matches an existing Label
   Template record whose DocType is `Cash Drop`. If you change the template
   name in Hamilton Settings to a different template name, the next drop
   prints the new template (not tested in this script — note the architecture
   is correct here).

### Pass criteria

BLOCKER 30 is launch-ready when ALL of the following are true:
- B30-1 prints all 8 fields correctly (legible, correct values)
- B30-2 shows correct drop type
- B30-3 shows sequential drop numbers without repeats
- B30-4 blocks submission when printer is offline (no silent failure)
- B30-5 template comes from Hamilton Settings (not hardcoded)

### Fail recovery

**B30-1/B30-2/B30-3 fail (wrong fields or missing fields):** Check the Label
Template record in Frappe desk. Verify all 8 `data_fields` are mapped to the
correct Cash Drop fields. If a field is missing, add it to the template and
re-run. If the template is correct but printing is wrong, check the print
endpoint code in `hamilton_erp/api.py` for the `print_cash_drop_label` function.

**B30-4 fails (drop creates record even with printer offline):** This is a
regression in the atomicity guarantee. Stop and escalate to development — the
print-before-commit ordering is broken.

**B30-5 fails (template name is hardcoded):** Check `Hamilton Settings` for the
`printer_cash_drop_template_name` field. If the field doesn't exist, the schema
wasn't migrated. Run `bench migrate` on the production site and verify the field
appears.

---

## BLOCKER 31: Cash-Side Refunds

**Design reference:** `docs/design/refunds_phase2.md` §2
**Risk:** Without a refund flow, an operator's only option on a refund request is
to handwrite a note or give cash without logging it. Either creates a phantom
theft flag on reconciliation.

### Pre-conditions

1. A completed Sales Invoice exists from the current shift. Use this one as
   your starting point: an admission + towel sale for Alex Thornton, total
   `$33.90` CAD (Room 12, $28.25 + towel $5.00 + 13% HST = $33.90).
   If this record doesn't exist, create it first: submit a POS sale on the
   cart for Room 12 + 1 towel, cash payment, `$40.00` tendered, `$6.10`
   change. Note the invoice number (e.g. `HAMILTON-INV-0042`).
2. Manager PIN known and manager account (`manager@hamilton.ca`) can log into
   the same iPad or a second device.
3. Cash drawer contains enough cash to cover the refund.

### Test scenarios

**Scenario B31-1: Full refund — correct amount uses grand_total, not paid_amount**

1. On the cart UI, tap "Refund."
2. Scan or type the original Sales Invoice number (`HAMILTON-INV-0042`).

   EXPECTED: System loads the SI. Shows the line items: Room 12 ($28.25),
   Towel ($5.00), HST ($4.65), Grand Total $33.90.

3. Select ALL line items for refund.

   EXPECTED: Refund amount displayed = `$33.90`. NOT `$40.00` (the cash
   tendered). This is the G-019 defense — the system uses grand_total, not
   paid_amount.

4. Select reason: "Customer Dissatisfaction" from the dropdown.
5. Tap "Process Refund."

   EXPECTED: System prompts: "Manager approval required — enter PIN."

6. Manager enters correct PIN.

   EXPECTED: System creates a Sales Return (negative Sales Invoice) linked to
   the original. UI confirms: "Pay $33.90 to Alex Thornton from till."

7. Count $33.90 from the drawer and hand it to the customer.
8. Open the refund record in Frappe desk.

   EXPECTED: Sales Return SI shows `grand_total = -33.90`, linked to
   `HAMILTON-INV-0042`, `refund_reason = Customer Dissatisfaction`,
   `operator = operator_test`, `manager_approver = manager_test`,
   `refund_timestamp` present.

**Scenario B31-2: Refund of nickel-rounded sale rounds in customer's favor**

1. Create a new sale: one item at a price that rounds oddly. Example: one
   admission SKU at $26.55 + 13% HST = $29.9715, which rounds to $30.00
   (nearest nickel). Submit the sale. Note the invoice number.
2. Initiate a refund on that invoice.

   EXPECTED: Refund amount displayed = `$30.00` (rounds UP in customer's
   favor — never $29.95). The system pays out the rounded nickel amount.

3. Complete the refund (manager PIN, hand cash to customer).
4. Verify in Frappe desk: Sales Return grand_total = `-30.00` (not -29.95).

**Scenario B31-3: Refund blocked without manager PIN**

1. Initiate a refund for any invoice (any amount).
2. When the manager PIN prompt appears, tap "Cancel" instead of entering a PIN.

   EXPECTED: System throws: "Manager approval required." The refund record
   is NOT created. The original Sales Invoice is untouched.

**Scenario B31-4: Refund reason is mandatory**

1. Initiate a refund. Load the original invoice line items.
2. Select line items but do NOT select a reason from the dropdown.
3. Tap "Process Refund."

   EXPECTED: System throws: "Refund reason is required." PIN prompt does
   not appear. Refund is blocked.

**Scenario B31-5: Refund subtracts from system_expected_cash in reconciliation**

1. Before refund: note the shift's current `system_expected_cash` value. Open
   Frappe desk > Shift Record > active shift. Note the field value (e.g.
   `$165.00`).
2. Process a full refund of `$33.90` (B31-1 scenario or a new test sale).
   Complete the refund with manager PIN.
3. After refund: open the same Shift Record. Refresh.

   EXPECTED: `system_expected_cash` has decreased by `$33.90`. New value
   = `$131.10` (or prior value minus $33.90).

4. At end of shift, run cash reconciliation. Count the actual till.

   EXPECTED: The `system_expected` in reconciliation accounts for the refund.
   If sales total $165 and refund was $33.90, reconciliation expects $131.10.
   Manager count should match.

**Scenario B31-6: Partial refund (one item from a multi-line invoice)**

1. Create a sale with two line items: Room 14 admission ($28.25) + one towel
   ($5.00) + HST. Grand total = $33.90.
2. Initiate a refund. Load the invoice.
3. Select ONLY the towel line ($5.00 + its HST portion = $5.65). Do NOT
   select the Room 14 line.

   EXPECTED: Refund amount = `$5.65`. Not $33.90.

4. Select reason: "Wrong Item." Enter manager PIN. Complete refund.
5. Open the Sales Return SI in Frappe desk.

   EXPECTED: Return SI has one line (Towel, -$5.00). HST reversal = -$0.65.
   Original SI (`HAMILTON-INV-XXXX`) is unchanged — Room 14 admission still
   posted on the original.

### Pass criteria

BLOCKER 31 is launch-ready when ALL of the following are true:
- B31-1 shows grand_total in refund amount (not paid_amount)
- B31-2 rounds refund UP to nearest nickel (customer's favor)
- B31-3 blocks refund without manager PIN
- B31-4 blocks refund without reason
- B31-5 reconciliation subtracts the refund from system_expected_cash
- B31-6 partial refund creates a one-line return SI and leaves original intact

### Fail recovery

**B31-1 shows paid_amount ($40.00) instead of grand_total ($33.90):** This is
the G-019 bug. The refund function is reading the wrong field. Escalate to
development immediately — this is a cash-out fraud vector.

**B31-3/B31-4 fail (refund submits without PIN or reason):** Authorization gate
is broken. Do not go live until fixed.

**B31-5 fails (system_expected_cash doesn't change after refund):** The refund
event is not wired to the reconciliation calculator. Escalate — reconciliation
will show false theft flags every time a refund happens.

---

## BLOCKER 32: Comps Manager-PIN Gate

**Design reference:** `docs/design/manager_override_phase2.md` §6 (solo-operator
phase); `docs/audits/pos_business_process_gap_audit.md` process #2
**Risk:** Without the PIN gate, any operator can issue free admissions without
manager knowledge. The audit trail captures THAT a comp happened, but the gate
is what ensures someone with authority approved it.

### Pre-conditions

1. Manager PIN set and known for `manager@hamilton.ca`.
2. A "Comp Admission" item exists in the price list with `selling_price = $0.00`.
3. Comp reasons configured (e.g.: Staff Admission, VIP Guest, Manager Comp,
   Promo Event, Other).
4. Logged in as Hamilton Operator.

### Test scenarios

**Scenario B32-1: Comp submission requires manager PIN**

1. On the cart UI, tap "Comp Admission."
2. Select asset: Room 6 (or any available room).
3. Select comp reason: "Manager Comp."
4. Enter customer name: "Jordan Reyes."
5. Tap "Issue Comp."

   EXPECTED: System displays "Manager approval required — enter PIN." The
   comp Sales Invoice is NOT submitted yet.

6. Do NOT enter a PIN. Tap "Cancel."

   EXPECTED: Comp is cancelled. No Sales Invoice created. Room 6 remains
   Available on the asset board.

**Scenario B32-2: Correct PIN allows comp to proceed**

1. Repeat steps 1–5 from B32-1.
2. When PIN prompt appears, enter the correct manager PIN.

   EXPECTED: Comp Sales Invoice submitted. `grand_total = $0.00`. Room 6
   transitions to Occupied on the asset board. Comp Admission Log entry
   created.

3. Open the Comp Admission Log entry in Frappe desk.

   EXPECTED: Record shows:
   - `operator` = logged-in operator user
   - `manager_approver` = manager user (whose PIN was entered)
   - `comp_reason = Manager Comp`
   - `comp_value` field is populated (visible to manager, hidden from operator)
   - `approval_timestamp` present

**Scenario B32-3: Wrong PIN increments lockout counter**

1. Initiate a comp (B32-1 steps 1–5).
2. At the PIN prompt, enter a wrong PIN three times in a row.

   EXPECTED: After the third wrong attempt, system displays: "Too many
   failed attempts — manager must log in directly to proceed." PIN prompt
   is locked out temporarily.

3. Wait 5 minutes (or the configured lockout window).

   EXPECTED: PIN prompt becomes available again.

**Scenario B32-4: Comp value is hidden from operator role**

1. As the operator (NOT the manager), navigate to Frappe desk > Comp
   Admission Log > the record created in B32-2.

   EXPECTED: The `comp_value` field is NOT visible. Operator sees the comp
   reason, customer name, room, and timestamp — but not the dollar value.

2. Log in as manager. Open the same Comp Admission Log record.

   EXPECTED: `comp_value` is visible (e.g. `$28.25` for the room admission).

**Scenario B32-5: Comp audit trail is immutable**

1. As manager, attempt to edit the Comp Admission Log record created in B32-2.
   Change the `manager_approver` field to a different user.

   EXPECTED: System either (a) does not allow editing after submission, or
   (b) creates a versioned amendment that preserves the original. The original
   approval cannot be erased.

### Pass criteria

BLOCKER 32 is launch-ready when ALL of the following are true:
- B32-1 blocks comp submission without PIN
- B32-2 allows comp with correct PIN; audit log shows both user IDs
- B32-3 lockout activates after repeated wrong PINs
- B32-4 comp_value is hidden from operator role
- B32-5 the audit trail cannot be silently overwritten

### Fail recovery

**B32-1 fails (comp submits without PIN):** Critical authorization gap — do not
go live. The entire audit model for comps depends on this gate.

**B32-4 fails (operator can see comp_value):** Check the `permlevel` on the
`comp_value` field in the Comp Admission Log DocType JSON. It must be set to
`1` (manager-only). Run `bench migrate` and verify.

---

## BLOCKER 33: Voids — Mid-Shift Transaction Undo

**Design reference:** `docs/design/voids_phase1.md`
**Risk:** Without a void flow, operator typo recovery requires escalation to a
manager with Frappe-desk access. At 11 PM with one operator on shift, that means
calling the owner. One misrung sale per month costs time; multiple per week is
an operational breakdown.

### Pre-conditions

1. Active shift open.
2. Cart connected to Epson TM-m30III (receipt printer) and APG VASARIO (cash
   drawer).
3. Logged in as Hamilton Operator.
4. Manager PIN available.

### Test scenarios

**Scenario B33-1: Happy-path void within the time window**

1. Submit a sale: Room 3 admission for Marcus Bell, cash payment, `$40.00`
   tendered, `$7.75` change (grand_total = `$31.86` with 13% HST... adjust to
   whatever your room tier is). Note the invoice number (e.g.
   `HAMILTON-INV-0055`).
2. Within 5 minutes of submission, tap "Void Last Transaction" on the cart UI.

   EXPECTED: UI displays a summary of `HAMILTON-INV-0055`: Marcus Bell, Room 3,
   $31.86, cash, submitted at HH:MM. Prompts: "Is this the transaction to void?"

3. Tap "Yes, Void This."
4. Select reason: "Wrong Tier" from the dropdown.

   EXPECTED: System creates a Sales Return SI (negative) linked to the
   original. UI confirms: "Transaction voided — return $31.86 to Marcus Bell."
   Cash drawer kicks open.

5. Count $31.86 from the drawer and hand to the customer.

   EXPECTED: Drawer pop is audible and the drawer is open.

6. Open the void record in Frappe desk.

   EXPECTED: Void record shows: `original_invoice = HAMILTON-INV-0055`,
   `void_reason = Wrong Tier`, `operator = operator_test`, `timestamp`
   present. Original SI shows `status = Cancelled` (or a `voided = True` flag).

7. On the asset board, check Room 3.

   EXPECTED: Room 3 is back to "Available." (It was set to Occupied when the
   original sale was submitted; the void released it.)

**Scenario B33-2: Void releases asset and cancels Venue Session**

1. Verify the Venue Session created for Marcus Bell / Room 3 in B33-1.
   Open Frappe desk > Venue Session > the record for Room 3 / HAMILTON-INV-0055.

   EXPECTED: Session status = "Cancelled." Session record is preserved (not
   deleted). Asset Status Log contains an entry with reason "Voided sale."

**Scenario B33-3: Void outside the time window requires manager PIN**

1. Submit a sale: any amount, any room. Note the invoice number.
2. Wait more than 5 minutes (or advance the clock past the void window if your
   test environment supports it).
3. Tap "Void Last Transaction."

   EXPECTED: System prompts: "Void window expired — manager PIN required."
   (NOT automatically rejected — escalation path opens.)

4. Enter manager PIN.

   EXPECTED: Void proceeds as in B33-1 but with manager authorization logged.

**Scenario B33-4: Cross-shift void is blocked**

1. Close the current shift. Open a new shift.
2. In the new shift, tap "Void Last Transaction."

   EXPECTED: System either (a) shows no transaction (void window is empty
   because the current shift has no transactions yet), or (b) shows the prior
   shift's last transaction and displays: "Cannot void a transaction from a
   closed shift — use Refund instead."

   If (b): tapping "Void" on the prior-shift transaction must be blocked.

**Scenario B33-5: Void reason is mandatory**

1. Submit a sale. Within 5 minutes, tap "Void Last Transaction."
2. When the "Select reason" dropdown appears, tap "Void This" without
   selecting a reason.

   EXPECTED: System throws: "Reason required." Void does not proceed.

**Scenario B33-6: Void of a void is blocked**

1. Submit a sale. Void it immediately (B33-1 steps).
2. On the same cart UI, tap "Void Last Transaction" again.

   EXPECTED: The just-voided SI does NOT appear as the void candidate. Either
   the next-most-recent unvoided transaction is shown, or the UI indicates
   "No recent transactions available to void."

**Scenario B33-7: Reconciliation reflects the void**

1. Run a shift with exactly these transactions: $28.25 cash sale, $31.86 cash
   sale (Marcus Bell / Room 3), then void the $31.86 sale.
2. At end of shift, run cash reconciliation.

   EXPECTED: `system_expected_cash` = `$28.25` (the unvoided sale only).
   Operator declares $28.25. Manager counts $28.25. Variance = Clean.

### Pass criteria

BLOCKER 33 is launch-ready when ALL of the following are true:
- B33-1 voids within window; drawer pops; SI marked cancelled
- B33-2 Room 3 returns to Available; Venue Session is Cancelled
- B33-3 expired window requires manager PIN (not hard-blocked)
- B33-4 cross-shift void is blocked with "use Refund" message
- B33-5 reason is mandatory
- B33-6 voided transaction cannot be voided again
- B33-7 reconciliation excludes the voided amount

### Fail recovery

**B33-1 fails (drawer does not kick):** Check the ESC/POS pulse command is
being sent in the receipt print pipeline. The drawer kick is sent by the TM-m30III
on transaction end — verify `receipt_printer_ip` is set correctly and the
ePOS-Print command includes the drawer pulse (`ESC p 0 100 100`).

**B33-2 fails (Room 3 stays Occupied after void):** Asset release side-effect
failed or did not run. Check the void's server-side code — asset release must
be part of the same transaction as the SI reversal. Do not go live if asset
state can become inconsistent.

**B33-4 fails (cross-shift void is allowed):** This is a fraud vector — voids
of another operator's shift should never proceed silently. Escalate.

---

## BLOCKER 34: Tip-Pull Schema (SHIPPED — PR #122)

**Design reference:** `docs/design/tip_pull_phase2.md` §1 (Phase 1 scope)
**Status:** PR #122 shipped. This test verifies the schema is present and
reconciliation does not break when tip_pull_amount = 0.

### Pre-conditions

1. Bench migration run after PR #122 merged (confirm `bench migrate` output
   shows no errors for the `cash_drop` or related DocTypes).
2. A Cash Drop record can be created in the current environment.

### Test scenarios

**Scenario B34-1: Tip pull field present on Cash Drop form**

1. Open the cart UI. Tap "Cash Drop."
2. Inspect the form.

   EXPECTED: A field labeled "Tip Pull Amount" (or `tip_pull_amount`) is
   visible on the form. Its default value is `$0.00`.

3. Do NOT change the tip pull amount. Submit a Cash Drop for `$50.00` declared.

   EXPECTED: Drop submits successfully. The label prints. No error about the
   tip pull field.

4. Open the Cash Drop record in Frappe desk.

   EXPECTED: `tip_pull_amount = 0.00`. Field exists on the DocType.

**Scenario B34-2: Reconciliation does not break with zero tip pull**

1. Run a full shift: 2 cash sales ($28.25 + $31.86 = $60.11 total), no
   tip pull, one Cash Drop for $60.11.
2. Run manager reconciliation.

   EXPECTED: Reconciliation completes without error. `system_expected_cash`
   is calculated correctly (does not crash on the tip pull subtraction, even
   though tip pull = $0). Variance = Clean.

**Scenario B34-3: Tip pull field is visible to operator for writing**

1. On the Cash Drop form, type `12.70` in the "Tip Pull Amount" field.
2. Submit the Cash Drop.

   EXPECTED: Drop submits. `tip_pull_amount = 12.70` saved on the record.
   No permission error for the operator role writing this field.

3. As manager, verify the field value is visible in Frappe desk.

   EXPECTED: Manager can read `tip_pull_amount = 12.70`.

### Pass criteria

BLOCKER 34 is launch-ready when ALL of the following are true:
- B34-1 field exists with default $0.00; Cash Drop submits without error
- B34-2 reconciliation calculator handles zero tip pull without error
- B34-3 operator can write the field; manager can read it

### Fail recovery

**B34-1 fails (field not present):** PR #122 migration did not run. Check
`bench migrate` output for errors. If the field is in the DocType JSON but not
in the database, a failed migration is the cause.

**B34-2 fails (reconciliation throws an error):** The tip pull subtraction hook
in `_calculate_system_expected` is not properly guarded with a null/zero check.
This is a code fix, not a data fix.

---

## BLOCKER 35: Post-Close Orphan-Invoice Integrity Check (SHIPPED — PR #124)

**Design reference:** `docs/design/post_close_integrity_phase1.md`
**Status:** PR #124 shipped. This test verifies the daily job runs, detects
orphans, and surfaces alerts to the right people.

### Pre-conditions

1. Logged into Frappe desk as Hamilton Manager.
2. The daily integrity check job is registered in `hooks.py` under
   `scheduler_events`.
3. Test ability to trigger the job manually: know the job function name
   (e.g. `hamilton_erp.scheduled_tasks.integrity_check.run_integrity_check`).

### Test scenarios

**Scenario B35-1: Happy day — no alerts when all invoices are consolidated**

1. Run the integrity check job manually via Frappe console:
   ```
   bench console --site hamilton-unit-test.localhost
   frappe.enqueue("hamilton_erp.scheduled_tasks.integrity_check.run_integrity_check")
   ```
   Or if a "Run Integrity Check" button exists in the UI, use that.
2. Wait for the job to complete (< 30 seconds for a small dataset).

   EXPECTED: No new `Integrity Alert` records created. Manager dashboard
   shows zero alerts. Notification badge is clear.

**Scenario B35-2: Orphaned POS Invoice triggers an alert**

1. In Frappe desk, create a test Sales Invoice manually:
   - `is_pos = 1`
   - `status = Submitted`
   - `consolidated_invoice = ""` (leave blank — this is the orphan condition)
   - Amount: any value (e.g. $28.25)
2. Run the integrity check job.

   EXPECTED: One `Integrity Alert` record is created.
   - `alert_type = orphaned_invoice`
   - `severity = HIGH`
   - `affected_records` list contains the orphaned Sales Invoice name
   - `recovery_path` is populated (not blank)

3. Check notification badge as Hamilton Manager.

   EXPECTED: Badge shows "1 Integrity Alert (HIGH)."

4. Log in as Hamilton Operator. Check notification badge.

   EXPECTED: Operator sees NO alert badge.

**Scenario B35-3: Alert acknowledgement requires resolution notes**

1. As manager, open the Integrity Alert from B35-2.
2. Click "Acknowledge" without entering any text in the "Resolution Notes"
   field.

   EXPECTED: System throws: "Resolution notes required."

3. Enter resolution notes: "Test orphan created manually — deleted after test."
4. Click "Acknowledge."

   EXPECTED: Alert status changes to "Acknowledged." `acknowledged_by` =
   manager user. `acknowledged_timestamp` present. Notification badge clears.

**Scenario B35-4: Sequence gap in invoice naming triggers alert**

1. In Frappe desk, note the last three Hamilton Sales Invoice names (e.g.
   `HAMILTON-INV-0060`, `HAMILTON-INV-0061`, `HAMILTON-INV-0062`).
2. Create and submit a new Sales Invoice named manually as `HAMILTON-INV-0064`
   (skipping `HAMILTON-INV-0063`). NOTE: this may require Frappe-desk access
   to override naming series.
3. Run the integrity check job.

   EXPECTED: An `Integrity Alert` with `alert_type = sequence_gap` is created.
   `affected_records` shows the gap (0063 missing).

**Scenario B35-5: Session mismatch triggers alert**

1. Create and submit an admission Sales Invoice (item type = Room admission).
2. Manually delete the corresponding Venue Session record from the database
   (Frappe desk > Venue Session > find the matching session > delete).
3. Run the integrity check job.

   EXPECTED: An `Integrity Alert` with `alert_type = session_mismatch` is
   created. `affected_records` contains the admission SI whose session is missing.

**Scenario B35-6: 4 AM schedule is configured correctly**

1. In Frappe desk, open Scheduled Job Type list.
2. Find the integrity check job.

   EXPECTED: Job is configured as a `cron` job. The cron expression targets
   4 AM in the venue's local timezone (EST for Hamilton: `0 4 * * *` in EST,
   which is `0 9 * * *` UTC). Verify the UTC offset is accounted for.

### Pass criteria

BLOCKER 35 is launch-ready when ALL of the following are true:
- B35-1 job runs clean with no false positives
- B35-2 detects orphan invoice and creates HIGH severity alert
- B35-3 alert acknowledgement requires resolution notes
- B35-4 sequence gap is detected
- B35-5 session mismatch is detected
- B35-6 scheduler is configured for 4 AM EST (9 AM UTC)

### Fail recovery

**B35-2 fails (orphan not detected):** The Query 1 filter in `integrity_check.py`
has an error. Check that `consolidated_invoice` is being checked for blank/null,
not just null. ERPNext often stores empty strings, not NULLs.

**B35-6 fails (cron is set to UTC not EST):** Change the scheduler event to the
EST-equivalent UTC time (`9 AM UTC = 4 AM EST`). Note: when Canada observes
Daylight Saving Time (summer), EST becomes EDT (UTC-4), so 4 AM EDT = 8 AM UTC.
If the Hamilton open date spans DST transitions, use the Frappe venue timezone
aware pattern described in `docs/design/post_close_integrity_phase1.md` §2.

---

## BLOCKER 36: Zero-Value Comp Invoice Regression Test (SHIPPED — PR #123)

**Design reference:** `docs/audits/pos_business_process_gap_audit.md` process #20
**Status:** PR #123 shipped. This test verifies the regression pin is in place
AND that the zero-value invoice actually submits on the live site's ERPNext
version.

### Pre-conditions

1. The test exists in the Python test suite and passes in CI (check GitHub
   Actions for PR #123's CI run — must be green).
2. Access to run the test suite locally or confirm CI run.

### Test scenarios

**Scenario B36-1: Zero-value comp invoice submits without error (browser
verification)**

1. On the cart UI, tap "Comp Admission."
2. Select Room 9. Select reason "Staff Admission."
3. Enter customer name "Jordan Reyes."
4. Enter manager PIN.

   EXPECTED: Comp Sales Invoice submits. `grand_total = $0.00`. No error message
   about "invoice total cannot be zero" or "paid amount mismatch." Room 9
   transitions to Occupied.

5. Open the Sales Invoice in Frappe desk.

   EXPECTED: SI status = Submitted. `grand_total = 0.00`. `is_pos = 1`.
   HST = $0.00 (zero base, zero tax). Comp Admission Log entry linked.

**Scenario B36-2: Regression test passes in CI**

1. Go to GitHub > hamilton_erp > Actions.
2. Find the CI run associated with PR #123.

   EXPECTED: All test jobs pass (green check). Specifically find the test
   named `TestZeroValueCompInvoice::test_zero_grand_total_submits` (or
   equivalent). It must be in the passing count.

3. Verify the test is listed in `.claude/commands/run-tests.md`.

   EXPECTED: The zero-value comp test module is included in the `/run-tests`
   command's module list.

**Scenario B36-3: What to do if the test FAILS**

   If B36-1 shows a submission error on the live site, this is the G-003 bug
   present in Hamilton's current ERPNext v16 minor version.

   DO NOT go live. Document the exact error message. Escalate to development
   with: ERPNext version number, exact error text, steps to reproduce. Options:
   (a) wait for an upstream fix in the next v16 minor, (b) apply Hamilton's own
   workaround (see `refunds_phase2.md` §2 Option B/C pattern — similar
   circumvention approach), (c) pin to a prior v16 minor where the bug is absent.

### Pass criteria

BLOCKER 36 is launch-ready when ALL of the following are true:
- B36-1 zero-value comp submits on the live site with no error
- B36-2 regression test is green in CI and listed in run-tests command

### Fail recovery

If either B36-1 or B36-2 fails: stop. Do not attempt to ship a workaround
without explicit approval from Chris. This is a go/no-go gate, not a
"figure it out on launch night" issue.

---

## BLOCKER 37: Receipt Printer Integration — Epson TM-m30III

**Design reference:** `docs/research/receipt_printer_evaluation_2026_05.md`;
`docs/design/pos_hardware_spec.md` §4
**Hardware:** Epson TM-m30III (SKU C31CK50022 black or C31CK50021 white).
Connectivity: LAN (static IP at Hamilton front desk).
**Risk:** Without printed receipts, there is no paper control token. The build
spec §6.6 promises "printed on a thermal receipt printer when the guest requests
one." Failing this means Hamilton cannot fulfill that promise on day 1.

### Pre-conditions

1. TM-m30III powered on, static IP assigned (e.g. `192.168.1.21`), LAN cable
   connected.
2. Hamilton Settings: `receipt_printer_ip = 192.168.1.21`,
   `receipt_printer_enabled = True`, `receipt_printer_connection = wired`.
3. APG VASARIO cash drawer connected via RJ-11 to the TM-m30III DK port.
4. 80mm thermal paper loaded in the TM-m30III. Paper positioned properly
   (tear bar accessible).
5. Epson ePOS-Print SDK version matches the TM-m30III firmware version (verify
   via Epson Device Admin tool or the printer's self-test print).

### Test scenarios

**Scenario B37-1: Standard sale receipt prints on cash payment**

1. On the cart UI, submit a cash sale: Alex Thornton, Room 11 admission,
   `$40.00` tendered, `$8.14` change (grand_total = `$31.86`).

   EXPECTED: TM-m30III prints a receipt immediately after the SI submits.
   Cash drawer kicks open (audible pop).

2. Pick up the printed receipt. Verify it contains:
   - "Club Hamilton" at the top (venue name, prominent)
   - Date and time
   - Line item: Room 11 - Admission, `$28.19` (or your room tier price)
   - HST 13%: `$3.67`
   - Grand Total: `$31.86`
   - Tendered: `$40.00`
   - Change: `$8.14`
   - Sales Invoice name (e.g. `HAMILTON-INV-0070`) — must be prominent and
     machine-readable for audit
   - Operator name or ID
   - "Thank you" or similar closing line

3. Verify the paper is cleanly cut (auto-cutter activates).

**Scenario B37-2: Void receipt prints with VOID header**

1. Submit a sale (any amount, any room). Note the invoice number.
2. Within 5 minutes, void the transaction (B33-1 procedure).

   EXPECTED: TM-m30III prints a void receipt. The receipt header must show
   "VOID" or "TRANSACTION REVERSED" prominently at the top. Original
   invoice number is printed. Amount shows as negative or clearly labeled
   as reversed. DO NOT let this receipt be mistaken for a valid sale receipt.

**Scenario B37-3: Refund receipt prints with REFUND header**

1. Submit a sale (any amount). Refund it (B31-1 procedure).

   EXPECTED: TM-m30III prints a refund receipt. The receipt header shows
   "REFUND" prominently. Original invoice number is printed. Refunded amount
   shown. Manager approver name or ID on the receipt.

**Scenario B37-4: Comp receipt prints (no dollar amount visible to customer)**

1. Issue a comp for Jordan Reyes, Room 4 (B32-2 procedure).

   EXPECTED: TM-m30III prints a comp receipt. Receipt shows:
   - "Club Hamilton"
   - Date, time
   - "Complimentary Admission — Room 4"
   - "Jordan Reyes"
   - Grand Total: `$0.00`
   - Comp reason: "Manager Comp"
   - The `comp_value` (dollar amount of the waived admission) does NOT appear
     on the printed receipt. Customers do not see what they "saved."

**Scenario B37-5: Cash drawer kicks ONLY on cash payment, not card**

1. Submit a card payment (if card flow is available). Or simulate by setting
   `payment_method = Card` if the test environment supports it.

   EXPECTED: Receipt prints. Cash drawer does NOT kick. (Drawer should only
   open when the operator needs to make change.)

   NOTE: If Card flow is not available at Phase 1, mark this test as "Phase 2
   — deferred until card integration." Record the deferred status here.

**Scenario B37-6: Print failure does NOT block Sales Invoice submission**

1. Disconnect the TM-m30III LAN cable.
2. Submit a cash sale for any amount.

   EXPECTED: Sales Invoice submits successfully. An error message is shown
   to the operator: "Receipt printer unreachable — transaction saved.
   Retry print from the Sales Invoice record." The SI is visible in Frappe
   desk with status = Submitted.

3. Reconnect the printer. On the SI record, find the "Reprint Receipt" button.
   Tap it.

   EXPECTED: Receipt prints without re-submitting the SI (idempotent reprint).

4. Verify the SI is not duplicated (only one SI exists for this transaction).

**Scenario B37-7: Receipt contains correct HST line for CRA compliance**

1. Print any cash receipt.
2. Verify the HST line shows:
   - "HST 13%"
   - Exact dollar amount of HST collected
   - Hamilton's Business Number (BN) in the format `BN: 123456789 RT0001`
     (your actual BN). This is required for HST-registered businesses in Canada.

   EXPECTED: BN is printed. CRA requires it on receipts over $30 for input
   tax credit eligibility.

**Scenario B37-8: Printer self-test confirms connectivity**

1. Press and hold the TM-m30III's FEED button while powering on.

   EXPECTED: Printer prints a self-test page showing: firmware version, MAC
   address, IP address (confirm it matches `receipt_printer_ip` in Hamilton
   Settings), and "ONLINE" status.

2. Use Epson's ePOS-Print "Test Print" from the iPad app (if available) or
   trigger a test print from Hamilton Settings.

   EXPECTED: Test receipt prints. Confirms the SDK-to-printer communication
   path is working end-to-end from the iPad to the printer.

### Pass criteria

BLOCKER 37 is launch-ready when ALL of the following are true:
- B37-1 sale receipt has all required fields including BN; cash drawer kicks
- B37-2 void receipt has VOID header; cannot be mistaken for a valid receipt
- B37-3 refund receipt has REFUND header
- B37-4 comp receipt shows $0.00 but hides comp_value
- B37-5 drawer kicks on cash only (or is noted as Phase 2 deferred for card)
- B37-6 print failure does not block SI submission; reprint works
- B37-7 HST line shows BN for CRA compliance
- B37-8 printer self-test confirms it's online and IP matches Hamilton Settings

### Fail recovery

**B37-1 fails (receipt doesn't print at all):** Check `receipt_printer_ip` in
Hamilton Settings. Ping the IP from the iPad browser (`http://192.168.1.21/`).
If the printer is unreachable, check LAN cable, switch port, and DHCP lease.
If reachable but not printing, check the ePOS-Print SDK connection in the cart
JS code.

**B37-1 fails (drawer doesn't kick):** The ESC/POS drawer pulse command
(`ESC p 0 100 100`) is not in the print stream. Check the ePOS-Print command
builder in `hamilton_erp/public/js/` for the cash-payment branch.

**B37-2 fails (void and sale receipts look identical):** This is a fraud/audit
risk — a voided receipt can be presented as a valid sale. Escalate immediately.
The void receipt print template must be clearly distinct from the sale receipt.

**B37-7 fails (no BN on receipt):** Add the Hamilton Business Number to
Hamilton Settings as `business_number` field. Receipt template must pull this
field and print it on every receipt. Without it, Hamilton is non-compliant for
customers claiming input tax credits.

---

## Summary: BLOCKER Status Checklist

| BLOCKER | Task | Status at testing |
|---|---|---|
| Cash Drop envelope label print | Task 30 | Pending — not yet shipped |
| Cash-side refunds | Task 31 | Pending — not yet shipped |
| Comps manager-PIN gate | Task 32 | Pending — not yet shipped |
| Voids — mid-shift undo | Task 33 | Pending — not yet shipped |
| Tip-pull schema | Task 34 | SHIPPED (PR #122) |
| Post-close orphan integrity | Task 35 | SHIPPED (PR #124) |
| Zero-value comp regression | Task 36 | SHIPPED (PR #123) |
| Receipt printer TM-m30III | Task 37 | Pending — not yet shipped |

Update the "Status at testing" column when you run each section. A row is
"Pass" only when every scenario in that section passes without exceptions.

## Final Go-Live Gate

Hamilton is launch-ready when:
1. All 8 BLOCKERs show "Pass" in the table above.
2. No scenario in any BLOCKER section ended with "Fail — escalate."
3. The receipt contains a valid Business Number (B37-7) — this is a CRA
   compliance requirement, not just a nice-to-have.
4. The integrity check job is scheduled for 4 AM EST and has run at least
   one clean cycle on the live site (B35-1).

Do not flip the go-live URL until all four conditions are met.
