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

## 1. ID + Retail Barcode Scanner — Honeywell Voyager 1602g

**See `docs/design/pos_scanner_spec.md` for the full vendor analysis.**

Key insight: **one scanner covers both use cases.** The Voyager 1602g reads:
- PDF417 (driver's licenses) → DOB + name parsing for age verification / customer matching
- 1D barcodes (UPC, EAN, Code 128) → retail SKU scanning at checkout

No need to spec a separate retail-only barcode scanner. A second Voyager unit per station is an option for DC's 3-tablet setup if cashier and front-desk are physically separated.

**Hamilton retail mix (for context):** From `docs/inbox.md` 2026-04-30 V9.1 Phase 2 retail cart UX entry, Hamilton sells towels, lube, condoms, and similar low-SKU-count consumables. SKU count is small (estimated <50 SKUs), so a barcode scanner is a nice-to-have rather than a must-have. Manual SKU search in the cart UI works for small inventories. **Recommend scanning at counter over manual entry once SKU count exceeds ~20** for ergonomic / speed reasons.

---

## 2. Card Reader — Fiserv (existing) + Stripe Terminal backup

**Defer the full vendor analysis to `docs/research/merchant_processor_comparison.md`** (companion deliverable — also queued from inbox 2026-05-01). This section captures only the hardware decisions, not the processor comparison.

**Existing setup (Hamilton):** Fiserv merchant ID 1131224, standard classification. Per `docs/risk_register.md` R-008, this is preferred over high-risk processors for adult-classified businesses because:
- 30-day termination notice (vs zero-day for high-risk processors)
- Lower-risk MATCH-list exposure (R-009)

**Hardware integration paths (in preference order):**

1. **Fiserv-supplied terminal** — pole-mounted PIN pad, EMV chip + tap. Cleanest integration if Fiserv's API supports the required `merchant_transaction_id` capture for Hamilton's reconciliation flow. Verify before locking.
2. **Stripe Terminal** (BBPOS WisePOS E or Stripe S700) — if Fiserv hardware integration is too painful, Stripe Terminal is the well-documented fallback. Works in CA + US, important for the multi-venue rollout (CAD at Hamilton, USD at Philadelphia / DC / Dallas). Native ERPNext Stripe integration exists.
3. **Square Terminal** — third option. Less compelling for adult classification (Square's TOS is stricter than Fiserv).
4. **Helcim** — Canadian-friendly for adult-hospitality, but USD support is via partner relationships rather than native — adds rollout complexity for the US venues.

**Decision deferred to:** `docs/research/merchant_processor_comparison.md` (full ranked table + recommendation backed by integration-effort analysis).

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
- Hamilton: 1
- Philadelphia: 1
- DC: 3
- Dallas: 1

DC's 3-tablet setup likely reflects a higher-traffic floor with multiple operators working in parallel. Each tablet station gets its own scanner, card reader, receipt printer, and cash drawer — they're independent transaction stations.

---

## 4. Receipt Printer — Epson TM-T20III

**Recommendation: Epson TM-T20III (Ethernet + USB models).**

Per `docs/inbox.md` 2026-04-30 Phase 2 hardware backlog entry. Reaffirmed here as the right call:

- Industry-standard 80mm thermal printer; widely supported in POS integrations (ESC/POS command set is the de-facto standard)
- Ethernet + WiFi options for flexible station layout
- Drives the cash drawer kick via the included DK port (RJ-11) — see #6 below
- Long product runway (TM-T series has been continuously refreshed for 15+ years)
- ~$220-280 USD per unit

**Configuration in Hamilton Settings (when integration ships):**
- `receipt_printer_ip` (Data) — per-venue Ethernet IP
- `receipt_printer_enabled` (Check) — toggle for "this venue uses a printer"

The integration pattern was scoped in `docs/inbox.md` 2026-04-30 — print receipt as a side-effect after Sales Invoice submit; the receipt is also the physical control token (operator hangs it on the assigned key hook).

**Watch (per LL-036 in `docs/lessons_learned.md`):** Paper receipt as occupancy token is a defensible-but-fragile control. Digital state remains canonical; paper receipt is operator UX. Receipt MUST print the Sales Invoice `name` prominently for audit traceability.

---

## 5. Label Printer — Brother QL-820NWB

**Recommendation: Brother QL-820NWB.**

Use cases:
- **Locker key tags** — printed as needed at check-in (locker number + truncated session ID)
- **Asset stickers** — one-time print run during venue setup; not a recurring need
- Optional: **Kitchen / vendor labels** if Hamilton ever expands food/drink service

Why Brother QL-820NWB:
- Continuous-tape thermal label printer; fast (1.5 sec / label)
- Ethernet + WiFi + USB connectivity options
- Native AirPrint support for iPad workflow
- Standard DK-1201 (29×90mm address labels) covers locker keys; DK-2205 continuous-length tape covers asset stickers
- ~$220-280 USD

**DEC-011 reference:** `docs/inbox.md` 2026-04-30 Phase 2 backlog entry references "the Brother label printer (DEC-011)." Verification: searching `docs/decisions_log.md` for "DEC-011" or "Brother" returns no matches. **DEC-011 may be aspirational from inbox notes; the canonical decision has not been entered into `decisions_log.md`.** Recommend either entering DEC-011 formally or removing the reference from inbox.md to close the drift.

**Integration:** Same pattern as the receipt printer — IP-based, configured per-venue via Hamilton Settings. Brother QL printers support standard CUPS / ESC/POS-style commands; the iPad workflow uses the Brother iPrint&Label app or AirPrint.

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

1. **Existing Fiserv terminal hardware:** Is there a specific Fiserv pole-mount model already in use at Hamilton, or is the relationship at the MID level only (no installed terminal yet)? This determines whether to defer to the existing model or recommend Stripe Terminal as the new install.
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
