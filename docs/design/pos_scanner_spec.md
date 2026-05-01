# Front-Desk ID Scanner Spec

**Status:** Draft — initial research deliverable from inbox queue 2026-05-01.
**Scope:** Hamilton's primary front-desk ID scanner. Multi-venue rollout (Hamilton, Philadelphia, DC, Dallas) inherits this spec.
**Use case:** Operator scans a customer's driver's license at check-in. System parses PDF417 barcode for DOB verification (18+ at Hamilton; potentially named-customer matching at Philadelphia per `docs/research/pipeda_venue_session_pii.md`).

---

## Requirements (ranked by priority)

1. **Driver's-license PDF417 parsing.** Must reliably parse Canadian provincial DLs (Ontario, Quebec, BC, Alberta — expected at Hamilton) and US state DLs (anywhere — expected at Philadelphia / DC / Dallas). The parsed payload includes DOB, name, expiry, ID number per AAMVA spec.
2. **USB connection — HID keyboard wedge.** Plug-and-play on iPad / desktop. No vendor-specific drivers required for the basic scan-into-focus flow. (Optional: USB HID POS or virtual COM port for richer integration.)
3. **Durable hardware.** Front desk environment — daily handling, occasional drops onto counter, food/drink proximity. Look for IP-rated builds, drop-tested certification.
4. **Long parts-availability runway.** Scanner choice should still be sourceable in 5+ years for new venue rollouts. Avoid models with rumored discontinuation. Honeywell and Zebra have the longest product lifecycles in this category.
5. **Continued vendor support.** Firmware updates for new state DL formats (states periodically refresh PDF417 layouts); active vendor support contracts.
6. **Front-desk ergonomics.** Either (a) presentation/omnidirectional scanner that sits on the counter and reads when the customer slides the ID across, OR (b) handheld with stand. Hands-free is preferable for high-volume nights.
7. **Cost.** Sub-$300 USD per unit at single-quantity volume. Mass discounts for multi-venue rollout welcome but not required.

## Out of scope

- **Age-verification SaaS** (Idology, IDology, TokenWorks subscription services). Hamilton's needs are decoded-DL-payload-only; vendor SaaS for fraud detection / cross-checking is over-engineered.
- **Biometric scanners** (fingerprint, facial). Not in scope.
- **Magnetic stripe readers.** DLs may have a magstripe but it's older and not standardized; PDF417 is the canonical machine-readable format on modern North American DLs.
- **Document scanners** (full-page DL scanners — NeoSCAN, AssureID, etc.). Over-engineered for Hamilton's needs and ~10× the cost.

---

## Vendor analysis (long-supported corded handheld + presentation scanners)

⚠️ **Pricing and current availability MUST be verified against vendor websites before purchase.** This research is from training data; specs and prices change.

### Tier 1 — Strongest candidates

#### Honeywell Voyager 1602g (handheld, USB)
- **Why on the shortlist:** Honeywell's flagship general-purpose 2D scanner. Documented PDF417 + AAMVA DL parsing. USB HID wedge by default. Extremely long product runway (Voyager line has been continuously refreshed since the 1990s).
- **Form factor:** Handheld with optional stand. Stand mode = hands-free presentation scan; pull-out mode = handheld for weird-angle scans.
- **Connection:** USB HID, USB virtual COM, or USB OPOS. Defaults to HID wedge — plug it in and it types decoded text into the focused input field.
- **Durability:** IP41-rated. 1.5m drop tested.
- **Parts runway:** Honeywell publishes 5-year support timelines per model. Voyager 1602g is mid-cycle as of training data.
- **Estimated price:** ~$200-280 USD single-quantity (verify against Barcodes Inc., POSGuys, or Honeywell direct).

#### Honeywell Hyperion 1300g (handheld, USB, 1D-only — RULE OUT for DL)
- **Important note:** Hyperion 1300g is **1D-only** — it does NOT read PDF417 (which is 2D). Listed here so it's not accidentally specced. **Not a candidate.** Move on.

#### Zebra DS2208 (handheld, USB)
- **Why on the shortlist:** Zebra's mid-tier handheld 2D scanner. PDF417 + AAMVA support. Backed by Zebra's enterprise support contracts.
- **Form factor:** Handheld with optional stand. Similar ergonomics to Voyager 1602g.
- **Connection:** USB HID by default.
- **Durability:** IP42-rated. 1.5m drop tested.
- **Parts runway:** Zebra's DS22xx line is the workhorse replacement for older Symbol DS97xx models — likely a long runway.
- **Estimated price:** ~$200-260 USD.

#### Datalogic QuickScan QD2430 (handheld, USB)
- **Why on the shortlist:** Datalogic's mid-tier corded 2D scanner. PDF417 + AAMVA support.
- **Form factor:** Handheld; ergonomic grip.
- **Connection:** USB HID, USB OPOS.
- **Durability:** IP42-rated. 1.5m drop tested.
- **Parts runway:** Datalogic has stable 5-year minimum support for QuickScan line.
- **Estimated price:** ~$180-240 USD.

### Tier 2 — Presentation/omnidirectional (hands-free counter scanner)

#### Honeywell Solaris 7820 (presentation, USB)
- **Why on the shortlist:** Designed for retail counter workflows where the customer slides the ID across the scanner glass. Reads PDF417 from a distance (no precise alignment needed).
- **Form factor:** Sits on counter; horizontal scan window.
- **Connection:** USB HID, USB OPOS.
- **Durability:** Moisture-resistant (counter spill exposure).
- **Estimated price:** ~$300-400 USD.

#### Zebra MP7000 (presentation, USB)
- **Why on the shortlist:** Multi-plane high-volume scanner. Overkill for Hamilton-scale (designed for grocery checkout) but worth knowing exists if a venue ever needs maximum throughput.
- **Estimated price:** ~$700-900 USD.

### Tier 3 — Age-verification-specific scanners (PROBABLY OVERKILL)

#### TokenWorks IDvisor Smart
- **What it is:** Handheld scanner + integrated DOB-validation logic. Native Bluetooth pairing with iPad.
- **Why probably overkill:** Hamilton's needs are decoded-DL-payload-only. The IDvisor Smart's integrated age-check / fake-ID detection is a SaaS feature ($X/scan or $XX/month subscription) on top of the hardware. If Hamilton's check-in flow does its own DOB ≥ 18 calculation against the parsed payload, the SaaS portion isn't needed.
- **When it would be a good fit:** Multi-venue rollout where one venue (e.g. DC) needs membership / repeat-customer matching against an external service, AND the integrated SaaS makes sense.
- **Estimated price:** ~$500-800 USD + ongoing subscription.

---

## Recommendation

**Primary recommendation: Honeywell Voyager 1602g** as the standard front-desk scanner for all four venues.

Reasoning:
1. PDF417 + AAMVA support confirmed in vendor docs
2. USB HID wedge means zero driver / zero integration code — operator plugs it in, scans, decoded text appears in the focused input field
3. Extremely long product runway (Voyager line has been refreshed continuously since the 1990s); parts and replacements will be available 5+ years out
4. Mid-range price point (~$200-280 USD) — affordable for multi-venue rollout
5. Stand-mode lets it work hands-free at the counter for high-volume nights; handheld mode for awkward angles

**Backup recommendation:** Zebra DS2208 — same capability profile, slightly cheaper, equivalent durability. Pick whichever is in stock when ordering.

**Skip:** Solaris 7820 / MP7000 unless Hamilton's traffic exceeds the front-desk workflow's natural pace (current Hamilton scale doesn't justify a $300-900 presentation scanner). Skip TokenWorks IDvisor Smart unless multi-venue rollout brings in a real need for subscription-backed age verification.

---

## Integration touchpoints in `hamilton_erp`

The scanner integrates as **HID keyboard input** to the front-desk UI. No code changes required for the basic flow:

1. Operator focuses the customer's name / ID input field on the check-in form (Asset Board → New Check-in flow, or Cart drawer → guest registration).
2. Operator scans the DL.
3. Scanner types the decoded PDF417 payload into the focused input.
4. JS handler parses the AAMVA payload (delimited by `\n` and `` per AAMVA D.20 spec) into named fields: `last_name`, `first_name`, `middle_name`, `dob`, `expiry`, `dl_number`, `state`, `address`, etc.
5. Form auto-populates: `Venue Session.full_name`, `Venue Session.date_of_birth`, optionally `Venue Session.scanner_data` (full payload retained for audit per `docs/research/pipeda_venue_session_pii.md`).

**File touchpoints (when the integration ships):**
- `hamilton_erp/hamilton_erp/page/asset_board/asset_board.js` — add an AAMVA parser helper. ~50 lines; pure client-side.
- No backend changes required for parsing — the parsed payload is sent to existing `Venue Session` endpoints.
- **PIPEDA boundary:** `Venue Session.scanner_data` requires `permlevel: 1` + encryption-at-rest per the PIPEDA research. That work is gated by Task 25 item 7 (bench migrate STOP).

**Hamilton Settings field (when added):**
- `id_scanner_required` (Check) — if checked, check-in cannot proceed without a scanned DL. Default unchecked (current Hamilton walk-in flow doesn't require DL scanning at check-in time).

**No vendor-specific code.** All shortlisted scanners output the same AAMVA payload format because that's an industry-standard format. Switching vendors later is a hardware swap, no software change.

---

## Hamilton-specific considerations

1. **Anonymous walk-ins are still supported.** Hamilton's check-in is anonymous by default per DEC. The DL scanner is for the OPTIONAL age-verification path (when a customer's age is in question) and for the Philadelphia-rollout customer-matching flow. Most Hamilton check-ins won't scan a DL.
2. **Provincial DLs (Ontario, Quebec, BC, Alberta) all use AAMVA-compliant PDF417.** Same parsing logic as US state DLs. No Canada-specific quirks beyond field-name differences (e.g. "Driver Licence" vs "Driver License" — purely cosmetic).
3. **Scan speed > scan accuracy.** Front-desk operators are not retail cashiers — they handle 1-50 customers per shift, not 500. A 1-second scan time is fine; sub-second optimization isn't a priority.
4. **The scanner is a recoverable failure point.** If it breaks mid-shift, manual DL date-of-birth entry is acceptable. The front-desk UI must support both flows (scan + manual fallback).

---

## Cost estimate (multi-venue rollout, single-unit per venue)

| Item | Per-unit | Hamilton | Philadelphia | DC | Dallas | Total |
|---|---|---|---|---|---|---|
| Honeywell Voyager 1602g (or Zebra DS2208 backup) | ~$240 USD | 1× | 1× | 3× | 1× | ~$1,440 USD |
| Spare unit per venue | ~$240 USD | 1× | 1× | 1× | 1× | ~$960 USD |
| **Total hardware** | | | | | | **~$2,400 USD** |
| AAMVA parser helper integration (one-time dev cost) | — | — | — | — | — | ~4-6 dev hours |

DC's tablet count is 3 per `docs/venue_rollout_playbook.md` Phase B reference table — assume each tablet station gets a scanner.

⚠️ **All prices verify against current vendor pages before ordering.** Honeywell and Zebra both have authorized resellers (Barcodes Inc., POSGuys, BarcodesAdvanced) with negotiable volume pricing.

---

## Verification checklist before ordering

- [ ] Confirm Honeywell Voyager 1602g (or whichever model is selected) currently advertises PDF417 + AAMVA DL parsing on the vendor product page
- [ ] Confirm USB HID keyboard wedge mode is the default
- [ ] Confirm a sample Ontario DL parses cleanly (vendor demo or local POS supplier)
- [ ] Confirm 5-year-minimum parts-availability commitment from the supplier
- [ ] Order 1 sample unit, integrate the AAMVA parser, run a check-in flow end-to-end before bulk ordering for all 4 venues

---

## References

- `docs/research/pipeda_venue_session_pii.md` — `scanner_data` field requirements; `permlevel: 1` + encrypt-at-rest gating
- `docs/inbox.md` 2026-05-01 — original queueing entry for this spec
- `docs/design/pos_hardware_spec.md` — consolidated hardware spec (this scanner spec is referenced from there)
- AAMVA D.20 standard (PDF417 DL barcode format): https://www.aamva.org/topics/dl-id-card-design-standard
- Honeywell Voyager 1602g product page: https://www.honeywellaidc.com (verify model availability)
- Zebra DS2208 product page: https://www.zebra.com (verify model availability)
- Datalogic QuickScan QD2430 product page: https://www.datalogic.com (verify model availability)

## Open questions

1. **Single scanner per tablet station or per venue?** DC has 3 tablets per the rollout playbook reference table. Assumption: each tablet station gets its own scanner.
2. **Is age verification ever a hard gate at Hamilton?** Currently the check-in flow allows anonymous walk-ins. If 18+ becomes a hard requirement (regulatory shift), the scanner becomes mandatory and the UI gating shifts.
3. **Replacement strategy for broken scanners during a shift?** Recommend keeping one spare per venue (cost included above).
4. **Bluetooth scanner option?** Wireless scanners (e.g. Zebra DS3678) are 1.5-2× the price and add a charging-pod operational burden. **Recommend wired** until a clear use case for wireless emerges.
