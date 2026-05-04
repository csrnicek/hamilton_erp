# POS Hardware Spec — Multi-Venue Rollout

**Status:** Draft — initial research deliverable from inbox queue 2026-05-01.
**Scope:** Front-desk hardware for Hamilton plus the rollout to Philadelphia, DC, and Dallas.
**Companion docs:** `docs/design/pos_scanner_spec.md` (ID scanner specifically), `docs/research/merchant_processor_comparison.md` (card-payment processor selection), `docs/research/erpnext_hardware_field_reports.md` (community field-tested gotchas — feeds this spec).

---

## TL;DR — Recommended hardware (per-station)

| # | Category | Recommendation | Per-unit price (USD, verify) | Hamilton qty | DC qty | Notes |
|---|---|---|---|---|---|---|
| 1 | ID + retail barcode scanner | Honeywell Voyager 1602g | ~$240 | 1 + 1 spare | 3 + 1 | One device covers both DL parsing AND retail SKU scanning. See `pos_scanner_spec.md`. |
| 2 | Card reader | First Data / Fiserv terminal (existing MID 1131224); Stripe Terminal as backup | ~$300-600 | 1 | 3 | Existing Fiserv MID + standard classification is the active config. See `docs/risk_register.md` R-008. |
| 3 | Tablet | Standard iPad (10th gen, 10.9-inch) | ~$350-450 | 1 | 3 | NOT iPad Air, NOT iPad Pro, NOT 12.9". Standard model gives 3-5 year support runway at the lowest cost. |
| 4 | Receipt printer | Epson TM-T20III (Ethernet + WiFi) | ~$220-280 | 1 | 1 per station (2-3) | Per inbox 2026-04-30 Phase 2 backlog. Drives the cash drawer kick (#7). |
| 5 | Label printer | Brother QL-820NWB | ~$220-280 | 1 | 1 | Locker key tags, asset stickers. Same integration pattern as receipt printer (IP-based). |
| 6 | Cash drawer | APG VASARIO 1416 (or any RJ-11 / ESC/POS-compatible drawer) | ~$120-180 | 1 | 1 per station | RJ-11 cable to the receipt printer; printer kicks the drawer on transaction-end via ESC/POS. |
| 7 | Receipt paper | Standard 80mm thermal rolls | ~$2 / roll | 50-roll case | 50-roll case | Defer Canadian supplier choice until printer is locked. |

**Hamilton single-station total:** ~$1,650 USD + ~$50 / month for receipt paper at moderate volume.
**DC three-station total:** ~$3,500 USD + ~$150 / month for receipt paper.

⚠️ **All prices verify against current vendor pages before purchase.** Multi-venue volume pricing is negotiable through authorized resellers.

---

## 1. ID + Retail Barcode Scanner — Honeywell Voyager 1602g (with caveats)

**See `docs/design/pos_scanner_spec.md` for the full vendor analysis.**

Key insight: **one scanner covers both use cases.** The Voyager 1602g reads:
- PDF417 (driver's licenses) → DOB + name parsing for age verification / customer matching
- 1D barcodes (UPC, EAN, Code 128) → retail SKU scanning at checkout

**iPad cable requirement (NEW 2026-05-01):** The chosen scanner MUST connect to the iPad via **USB-C native cable**. USB-A + Apple USB-C-to-USB-A adapter is acceptable as a **fallback only** — adapters add a failure point and a part to lose. Native USB-C is preferred wherever a model exists in the same product class.

**Honeywell Voyager 1602g status:** ships USB-A natively. No USB-C variant currently exists in the 1602g family per training-data research; the industrial 2D scanner market is heavily USB-A-cabled. Two paths:
1. **Use Voyager 1602g + Apple USB-C-to-USB Adapter (~$20).** Acceptable as fallback per the rule above. Buy one adapter per scanner + one spare per venue.
2. **Open follow-up research** for a USB-C-native industrial 2D scanner (Datalogic, Code, or Symbol/Zebra latest) that matches the Voyager's PDF417 + AAMVA support, durability, and price. **Recommend treating this as Phase 2 follow-up** — the adapter path is operationally fine; switching scanner vendors over a cable is over-engineering. Re-evaluate if Hamilton's deployment proves the adapter unreliable (drops, fails to enumerate, etc.).

**Hamilton retail mix (for context):** From `docs/inbox.md` 2026-04-30 V9.1 Phase 2 retail cart UX entry, Hamilton sells towels, lube, condoms, and similar low-SKU-count consumables. SKU count is small (estimated <50 SKUs), so a barcode scanner is a nice-to-have rather than a must-have. Manual SKU search in the cart UI works for small inventories. **Recommend scanning at counter over manual entry once SKU count exceeds ~20** for ergonomic / speed reasons.

**Hamilton scanner deferred to Phase 2 (NEW 2026-05-01):** Don't order a scanner for Hamilton at launch. Phase 2 ships when (a) a loyalty program lands and front-desk needs DL parsing for membership, OR (b) rentable asset key barcode scanning lands. Until then, Hamilton's check-in flow is anonymous walk-in with no scanner dependency. New venues (Philadelphia / DC / Dallas) decide at rollout based on local needs.

**Per-station scanner counts** (1 per station, 1 per spare, etc.) are operational decisions made at venue rollout time, not in this hardware spec. See `docs/venue_rollout_playbook.md` for the per-venue ordering process.

---

## 2. Card Reader — Fiserv (existing) + Stripe Terminal backup

**Defer the full vendor analysis to `docs/research/merchant_processor_comparison.md`** (companion deliverable — also queued from inbox 2026-05-01). This section captures only the hardware decisions, not the processor comparison.

**Existing setup (Hamilton):** Fiserv merchant ID 1131224, standard classification per DEC-062 (Hamilton operates as a standard commercial business, not adult-classified). Per `docs/risk_register.md` R-008, the standard MID is preferred over processors that perceive bathhouse-hospitality as adult-adjacent because:
- 30-day termination notice (vs zero-day for processors with stricter perception)
- Lower-risk MATCH-list exposure (R-009)

**Hamilton's terminal — CONFIRMED 2026-05-04 (DEC-106).** **Clover Flex C405**. Serial `C045UQ24930247`, hardware revision 1.01, Android 10, **SRED enabled**, on the venue WiFi at `192.168.0.136`. iPad integration uses the **Clover Connect API over WiFi**. SRED confirms **SAQ-A PCI scope** — the adapter receives an encrypted token only, never raw card data. See DEC-106 in `docs/decisions_log.md` for the full spec + SAQ-A reasoning + Phase-2 integration plan.

**Card-present rule (NEW 2026-05-01):** Hamilton (and all ANVIL venues) accept **card-present transactions only** — physical card chip / tap / swipe OR digital wallets (Apple Pay, Google Pay, contactless). **No card-not-present (manual key-in) anywhere.** Every recommended terminal MUST support **NFC / contactless** as a hard requirement. This rules out older Fiserv FD150/FD130 and any terminal without NFC.

**Hardware integration paths (in preference order):**

1. **Fiserv-supplied terminal** — physical pole-mounted or counter-mounted EMV+NFC pad. ~~Currently TBD pending Hamilton's existing-model confirmation.~~ **2026-05-04: CONFIRMED — Hamilton runs a Clover Flex C405 (option 2 below). DEC-106.**
2. **Clover Flex C405** (handheld via Clover Connect API) — **Hamilton's installed terminal** as of 2026-05-04 (DEC-106). Serial `C045UQ24930247`, HW 1.01, Android 10, SRED enabled, WiFi @ 192.168.0.136. Phase-2 adapter integrates via Clover Connect API over WiFi.
3. **Stripe Terminal** (BBPOS WisePOS E or Stripe S700) — well-documented fallback for new venues that don't inherit Hamilton's Fiserv MID. Works in CA + US.
4. **Square Terminal** — skip per DEC-062 / DEC-063 rationale: Square's TOS is stricter on bathhouse-hospitality merchants (their internal stance, not Hamilton's classification — but it raises termination risk).
5. **Helcim Smart Terminal** — Helcim is Canadian-flagship and explicit-friendly toward bathhouse-hospitality businesses. Useful as Hamilton's Phase 2 backup processor (per DEC-064) even though Hamilton itself is standard-classified.

**Per-venue choice (DEC-063):** each venue picks its own primary processor at rollout based on local availability, iPad/ERPNext SDK fit, hardware fit, fees, and risk policy. There is no corporate-wide processor mandate.

**Primary + backup (DEC-064):** every venue must have BOTH a primary AND a backup processor pre-approved + integration-tested; system supports config-driven swap in hours. Hamilton's primary is Fiserv; backup is **NOT YET selected** (open task in `docs/inbox.md` for backup processor selection).

**Decision deferred to:** `docs/research/merchant_processor_comparison.md` (full ranked table + recommendation per venue, plus the Fiserv / Clover terminal hardware section).

---

## 3. Tablet — Standard iPad

**Recommendation: 10th-gen iPad (10.9-inch, A14 Bionic, USB-C).**

NOT:
- iPad Air (more expensive, not needed for cart-UX scope)
- iPad Pro (significantly more expensive, no operational benefit)
- iPad 12.9-inch (too large for the front-desk ergonomic — operators want one-handed reach)

Why standard 10th-gen:
- ~$350-450 USD per unit at single-quantity (verify; multi-pack pricing is lower)
- Apple's tablet support runway is typically 5+ years on the Standard line
- Front-desk UI (Asset Board, Cart drawer) is built for portrait or landscape on a 10.9-inch screen — verified during V9.1 Phase 2 cart UX work (PR #49)
- USB-C lets it charge from the same cable as everything else at the station

**Existing tablet design spec:** Search `docs/design/` returns no prior tablet spec — V9 Decision 3.8 references "iPad viewport constraints" but doesn't lock a model. **This spec is the canonical model recommendation.**

**Per-venue tablet count** (from `docs/venue_rollout_playbook.md` Phase B reference table):
- Hamilton: **1** — confirmed by DEC-111 (single front-desk station, single transaction lane).
- Philadelphia: 1
- DC: 3
- Dallas: 1

DC's 3-tablet setup likely reflects a higher-traffic floor with multiple operators working in parallel. Each tablet station gets its own scanner, card reader, receipt printer, and cash drawer — they're independent transaction stations.

---

## 4. Receipt Printer — Epson TM-T20III (dual LAN + WiFi)

**Recommendation: Epson TM-T20III with BOTH wired Ethernet AND WiFi connectivity supported.**

Per `docs/inbox.md` 2026-04-30 Phase 2 hardware backlog entry. Reaffirmed here as the right call:

- Industry-standard 80mm thermal printer; widely supported in POS integrations (ESC/POS command set is the de-facto standard)
- Long product runway (TM-T series has been continuously refreshed for 15+ years)
- Drives the cash drawer kick via the included DK port (RJ-11) — see #6 below
- ~$220-280 USD per unit

**Connectivity requirement (NEW 2026-05-01):** The printer model selected for each venue MUST support **both wired Ethernet AND WiFi**. Per-venue connection method:

- **Hamilton: wired LAN** (ethernet drop confirmed available at front desk). Wired is more reliable than WiFi for the receipt-print latency budget; pick this where the site supports it.
- **Other venues: WiFi default unless ethernet is confirmed during site survey.** New venues do NOT assume ethernet is available — the rollout playbook (`docs/venue_rollout_playbook.md`) includes a site-survey step to check for ethernet drops at the front desk before ordering. If ethernet is confirmed, switch to wired; otherwise default WiFi.

**Why both:** ordering printers without one or the other forces a re-buy when the site reality differs from plan. The TM-T20III line includes Ethernet+WiFi-capable variants — verify the SKU at order time supports both interfaces. Single-interface variants are cheaper but introduce a re-order risk that cancels the savings.

**Configuration in Hamilton Settings (when integration ships):**
- `receipt_printer_ip` (Data) — per-venue printer IP (LAN or WiFi DHCP-assigned)
- `receipt_printer_enabled` (Check) — toggle for "this venue uses a printer"
- `receipt_printer_connection` (Select: `wired` / `wifi`) — operational metadata; helps the runbook diagnose connection issues

The integration pattern was scoped in `docs/inbox.md` 2026-04-30 — print receipt as a side-effect after Sales Invoice submit; the receipt is also the physical control token (operator hangs it on the assigned key hook).

**Watch (per LL-036 in `docs/lessons_learned.md`):** Paper receipt as occupancy token is a defensible-but-fragile control. Digital state remains canonical; paper receipt is operator UX. Receipt MUST print the Sales Invoice `name` prominently for audit traceability.

---

## 5. Label Printer — Brother QL-820NWB (extensible template registry)

**Recommendation: Brother QL-820NWB driven by an extensible template registry.**

### Use cases (current 2026-05-01)

| Template | Size | Trigger | Operator workflow |
|---|---|---|---|
| **Locker key tag** | DK-1201 29×90mm address label | Check-in flow assigns a locker | Auto-print on session create; operator attaches to physical key |
| **Cash drop envelope** | DK-1209 62×100mm shipping label OR DK-2205 continuous tape (custom length) | Operator triggers from Cash Drop form | Print on Save of Cash Drop record |
| **Retail SKU label** | DK-1201 29×90mm OR DK-1208 38×90mm | Inventory restock event | Batch print from Item list view |

### Architectural requirement: template registry

Today's three use cases are the starting set. The system MUST support **adding or removing label types without re-speccing the printer or rewriting integration code.** The shape this takes:

- **Template definitions** live in a Hamilton ERP DocType (e.g. `Label Template`) with fields: `name`, `label_size` (Select: DK-1201 / DK-1208 / DK-1209 / DK-2205-continuous / etc.), `layout` (Long Text — the print template), `data_fields` (which Hamilton DocType + which fields populate the layout).
- **Print endpoint** takes a `template_name` + a record reference. Renders the template with the record's data and dispatches to the printer.
- **Operator UX requirement: fast template switching from the active iPad screen, no context switch.** The ERP UI exposes a "Print label" button on each relevant DocType form (Venue Session, Cash Drop, Item) with a dropdown of applicable templates. Operator picks template → label prints → no app switch, no separate print app, no menu dive.

### Why Brother QL-820NWB handles all current sizes

- **DK roll cassette swap:** each label size maps to a DK roll. Operator swaps the roll for the use case, or each station has a dedicated printer for high-volume sizes.
- **Continuous tape (DK-2205):** prints custom-length labels in any width. Cash drop envelopes are typically larger than the standard DK-1209 — continuous tape gives the flexibility.
- **Ethernet + WiFi + USB connectivity** matches the receipt printer dual-connectivity rule (#4 above): wired LAN at Hamilton, WiFi default for new venues unless site survey confirms ethernet.
- **Native AirPrint support** simplifies iPad direct printing for the v1 integration; deeper integration (server-rendered templates) is Phase 2.
- ~$220-280 USD

### Per-station vs per-venue printer count

Operational decision at venue rollout (per `venue_rollout_playbook.md`). Hamilton's single-station setup needs one printer at the front desk. Multi-station venues (DC's 3 stations) decide whether each station gets its own printer or stations share one — usually depends on physical layout and DK roll size variance per station. **Not in scope for this hardware spec.**

### DEC-011 reference

`docs/inbox.md` 2026-04-30 Phase 2 backlog entry references "the Brother label printer (DEC-011)." Verification: searching `docs/decisions_log.md` for "DEC-011" or "Brother" returns no matches. **DEC-011 may be aspirational from inbox notes; the canonical decision has not been entered into `decisions_log.md`.** Open question for Chris: formalize DEC-011 in decisions_log.md, or remove the inbox reference?

---

## 6. Cash Drawer — APG VASARIO 1416 (or any RJ-11 / ESC/POS-compatible)

**Recommendation: APG VASARIO 1416 (or equivalent — drawer hardware is largely commoditized).**

The cash drawer is dumb hardware — it has a single function: pop open when an electrical pulse arrives on the RJ-11 cable. Buying brand-name vs generic matters less than:
- **Cable type:** RJ-11 (12V or 24V — must match the receipt printer's DK port spec)
- **Coin tray layout:** 5 or 6 coin slots + 4 or 5 bill slots, depending on regional currency
- **Lock mechanism:** Locking position to disable the drawer when not in use
- **Build quality:** Look for steel construction, not plastic

**Integration with receipt printer:** The Epson TM-T20III's DK port sends a 24V pulse on transaction-end (configurable in the ESC/POS command stream). The drawer receives the pulse, releases the latch, drawer opens. **No separate code or USB integration to the iPad** — the drawer is downstream of the printer.

**Hamilton configuration:**
- One drawer per station (per receipt printer)
- The blind-cash-control invariant (DEC-005, DEC-021) applies: operator drops cash without seeing the expected total. The drawer is just a vault; the math happens in `Cash Reconciliation` and `Cash Drop` DocTypes per existing Phase 1 design.

---

## 7. Receipt Paper — Defer to Canadian supplier choice

**Specification:** Standard 80mm × 80mm thermal paper rolls (the universal POS tape).

**Source choice deferred** until printer is ordered — sourcing thermal paper in Canada is a separate exercise (not vendor-locked to Epson). Common Canadian suppliers:
- Staples / The Source — convenience, price premium
- Amazon.ca — fast delivery, mid-tier pricing
- Specialized POS-supply vendors (POSCentral.ca, POSPaperRolls.ca) — best per-unit price for case quantities

**Estimated consumption (Hamilton):** ~50 rolls / month at moderate volume (1 roll = ~50-80 receipts depending on receipt length). 50-roll case ~$100 CAD. **~$100 / month / station** at sustained traffic.

**No code touchpoints.** This is consumable.

---

## Cross-cutting integration concerns

### Hamilton Settings fields needed (when integrations ship)

Based on the IP-per-device pattern:

| Field | Type | Purpose |
|---|---|---|
| `receipt_printer_ip` | Data | Epson TM-T20III LAN IP |
| `receipt_printer_enabled` | Check | Toggle the print-on-submit hook |
| `label_printer_ip` | Data | Brother QL-820NWB LAN IP |
| `label_printer_enabled` | Check | Toggle the locker-tag print flow |
| `card_terminal_id` | Data | Fiserv terminal ID or Stripe Terminal reader ID |
| `id_scanner_required` | Check | If true, check-in cannot proceed without DL scan |

All per-venue values configured via `bench set-config` per `docs/venue_rollout_playbook.md` Phase B pattern.

### Phase ordering

This spec is for Phase 2+ work. Phase 1 (current) ships with no hardware integrations — the cart Confirm flow creates a Sales Invoice but doesn't print, doesn't kick a drawer, doesn't process a card payment. Phase 2 introduces these integrations one device at a time:

1. **Receipt printer** (first) — gives operators the paper trail and triggers cash drawer kick
2. **Cash drawer** (with #1) — paired with the receipt printer
3. **Card reader integration** (next) — replaces "cash only" with real card payments; depends on `merchant_processor_comparison.md` decision
4. **Label printer** (alongside or after #3) — locker key tags
5. **ID scanner** (later, optional) — gates check-in by age verification if required

### Truth-doc cross-checks

- ✅ `CLAUDE.md` "Hamilton accounting / multi-venue conventions" — spec respects CAD nickel rounding (cash sales only), Card payments don't round
- ✅ `docs/risk_register.md` R-008 (Fiserv standard merchant) — card reader recommendation aligned
- ✅ `docs/research/pipeda_venue_session_pii.md` — ID scanner integration boundary (`scanner_data` field) noted; PIPEDA work gated by Task 25 item 7
- ✅ `docs/lessons_learned.md` LL-036 — paper-receipt-as-occupancy-token rule; spec calls this out
- ✅ `docs/lessons_learned.md` LL-037 — Hamilton Settings 60-second cache TTL on `bench set-config` writes; operators must wait or restart workers after config changes
- ⚠️ `docs/decisions_log.md` DEC-011 — Brother label printer reference exists in inbox but not in decisions_log; recommend formalizing or removing the reference
- ⏳ `docs/research/merchant_processor_comparison.md` — companion deliverable; defers card-reader processor decision

---

## Open questions for Chris

1. ~~**Existing Fiserv terminal hardware:** Is there a specific Fiserv pole-mount model already in use at Hamilton, or is the relationship at the MID level only (no installed terminal yet)? This determines whether to defer to the existing model or recommend Stripe Terminal as the new install.~~ **CLOSED 2026-05-04 (DEC-106):** Clover Flex C405, serial `C045UQ24930247`, SRED enabled, WiFi @ 192.168.0.136. Adapter integrates via Clover Connect API. SAQ-A scope.
2. **DC's 3-tablet setup:** Confirm the 3 tablets are 3 independent transaction stations (each with own scanner / printer / drawer / card reader)? If so, the cost estimate above is correct. If they share peripherals, the cost is lower.
3. **Label printer use case for Hamilton specifically:** Locker key tags are the primary use case — is that sufficient justification, or are there additional Hamilton flows (kitchen, retail SKU labels) that change the requirements?
4. **Receipt printer LAN/WiFi:** Can each Hamilton station get a wired LAN drop, or is WiFi required? Wired is more reliable; WiFi is more flexible. Both Epson TM-T20III variants support both.
5. **DEC-011 status:** Does the Brother label printer reference in `docs/inbox.md` correspond to an actual decisions-log entry that was lost, or is it aspirational? If aspirational, recommend entering DEC-011 formally now or removing the inbox reference.

---

## Cost summary (multi-venue rollout)

| Category | Per-station cost (USD) |
|---|---|
| Honeywell Voyager 1602g | ~$240 |
| Card reader (Fiserv or Stripe Terminal) | ~$400 |
| iPad 10th gen | ~$400 |
| Epson TM-T20III | ~$250 |
| Brother QL-820NWB | ~$250 |
| APG VASARIO 1416 | ~$150 |
| Setup misc (cables, mounts, power) | ~$100 |
| **Per-station total** | **~$1,790 USD** |

**Per venue:**
- Hamilton (1 station): ~$1,790 + 1 spare scanner ($240) = ~$2,030
- Philadelphia (1 station): ~$1,790 + spares = ~$2,030
- DC (3 stations): ~$5,370 + 1 spare scanner = ~$5,610
- Dallas (1 station): ~$1,790 + spares = ~$2,030

**Total across 4 venues: ~$11,700 USD hardware.** Plus ongoing receipt-paper consumables (~$100-300 / month / venue depending on traffic).

⚠️ **All pricing requires current-quote verification.** Multi-venue volume + multi-product bundle pricing through an authorized POS reseller is likely 10-20% lower than single-quantity retail.

---

## References

- `docs/design/pos_scanner_spec.md` — full ID scanner analysis (Honeywell Voyager 1602g)
- `docs/research/merchant_processor_comparison.md` — card reader processor selection (companion deliverable)
- `docs/research/erpnext_hardware_field_reports.md` — community gotchas (companion deliverable)
- `docs/inbox.md` 2026-04-30 — Phase 2 hardware backlog (original Epson + cash-drawer notes)
- `docs/risk_register.md` R-008, R-009 — Fiserv classification + MATCH-list risk
- `docs/lessons_learned.md` LL-036, LL-037 — receipt-canonicality + site_config TTL
- `docs/research/pipeda_venue_session_pii.md` — `scanner_data` field PIPEDA boundary
- `docs/venue_rollout_playbook.md` Phase B reference table — per-venue tablet counts
- `docs/RUNBOOK.md` — operational procedures including hardware troubleshooting (TBD; may need extension as integrations land)
