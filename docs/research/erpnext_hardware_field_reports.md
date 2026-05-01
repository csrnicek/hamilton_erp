# ERPNext / Frappe Community Hardware Field Reports

**Status:** **Framework + initial findings — not exhaustive.** This file ships the structure for a community-reports survey; populating it fully requires direct browsing of `discuss.frappe.io`, `github.com/frappe/erpnext/issues`, and Reddit `r/erpnext`. The next session with web-fetch tools should fill the TODO sections below.

**Why this isn't a complete deliverable:** Producing community field reports without browsing the forums means making up reports — which would defeat the purpose. The framework + methodology + initial known-pattern findings ship now; the rest needs actual evidence collection.

---

## Purpose

Surface real-world reports on POS hardware integration with ERPNext / Frappe v16. What works easily, what works with caveats, what people regret. Three lists: **Green** (works well), **Yellow** (works with caveats), **Red** (avoid).

Feeds into `docs/design/pos_hardware_spec.md` (consolidated hardware spec) and `docs/design/pos_scanner_spec.md` (ID scanner) as a sanity check on what vendor docs claim vs what real users report.

---

## Methodology (for completing this doc)

1. **Search `discuss.frappe.io`** with these query terms:
   - `epson tm-t20`, `epson receipt printer pos`, `pos receipt printer integration`
   - `barcode scanner pos`, `honeywell scanner erpnext`, `zebra scanner pos`
   - `cash drawer pos`, `esc/pos cash drawer`
   - `stripe terminal erpnext`, `stripe terminal frappe`, `card reader pos`
   - `tablet pos ipad`, `pos screen size`
   - `brother label printer`, `label printer integration`

2. **Search `github.com/frappe/erpnext/issues`** and `github.com/frappe/frappe/issues` with same terms. Filter to `state:open` AND `state:closed` (closed issues with workarounds are gold).

3. **Search Reddit `/r/erpnext`** for "pos hardware", "receipt printer", "cash drawer", "barcode scanner".

4. **For each report**, capture:
   - Source URL + date
   - Reporter (anonymized OK)
   - ERPNext version (v13, v14, v15, v16 — versions matter; v15→v16 changed POS substantially)
   - What worked / what didn't
   - Workaround if any
   - Resolution (still open, closed-as-fixed, closed-as-wontfix)

5. **Categorize as Green / Yellow / Red** using the criteria below.

6. **Cite every claim.** No paraphrased "users have reported" — direct links.

---

## Categorization criteria

### Green list — works well
- 2+ independent reports of clean integration
- No outstanding open issues for the same hardware
- Standard ERPNext (or commonly-used Frappe app) integration path exists
- No version-pinning concerns (works on v15 + v16)

### Yellow list — works with caveats
- At least one report of integration with a documented workaround
- Specific quirks (model variants behave differently, version constraints, known bugs that need ERPNext-side workarounds)
- Vendor support is active but the ERPNext side has friction

### Red list — avoid
- 2+ reports of broken integration that wasn't resolved
- Vendor abandoned the product or the integration
- Doesn't survive Frappe upgrades (breaks on v15→v16, v16→v17)
- Known data-loss reports (e.g. duplicated transactions on double-charge)
- Active GitHub issues with "won't fix" status

---

## Initial findings (training-data + known-pattern only — VERIFY ALL)

⚠️ The findings below are seeded from training-data knowledge of common ERPNext hardware patterns. **Each must be verified against actual community reports before relying on it.** Marked with `(VERIFY)` until confirmed.

### Green list (likely; verify)

#### Receipt printers — Epson TM-T series via ESC/POS / network printing
- **Status:** Likely Green. (VERIFY)
- **Reasoning:** TM-T series is the de-facto-standard thermal printer in POS ecosystems. ERPNext + community plugins typically print via ESC/POS or via OS-level printing (CUPS on Linux, AirPrint on iOS).
- **Models reported in community:** TM-T20III (Hamilton's specced model), TM-T82III, TM-T88V/VI
- **Open question:** Does ERPNext v16's POS specifically support direct-to-printer ESC/POS, or does it route through OS print? (Affects driver / setup story.)
- **TODO:** Pull 2-3 specific forum threads confirming TM-T20III + ERPNext v15 or v16 working integrations.

#### Honeywell handheld 1D/2D scanners — USB HID wedge
- **Status:** Likely Green. (VERIFY)
- **Reasoning:** USB HID keyboard wedge means ERPNext receives scanner input as keyboard events into focused input fields. No vendor-specific driver. Works regardless of Frappe version.
- **Models likely-reported:** Voyager 1450g, 1602g (Hamilton's pick), 1900g
- **TODO:** Search `discuss.frappe.io` for "honeywell hid wedge".

#### Stripe Terminal — `stripe-payments` ERPNext app
- **Status:** Likely Green for card-not-present; Yellow-or-Green for card-present.
- **Reasoning:** Stripe is the most-supported processor in the Frappe ecosystem. Stripe Terminal (BBPOS WisePOS E + iOS SDK) integration is documented but adds complexity vs CNP.
- **TODO:** Check the `frappe/payments` GitHub repo's open issues for Stripe Terminal-specific reports.

### Yellow list (likely; verify)

#### Cash drawer kick from receipt printer (ESC/POS DK port)
- **Status:** Likely Yellow.
- **Caveats:** Drawer kick command is sent INSIDE the receipt print stream — not a separate ESC/POS command channel. If the print job fails, the drawer doesn't kick. ERPNext's POS integration must be configured to include the kick code in every receipt print, not as a follow-up command.
- **Workaround pattern:** Customize the print template to include the ESC/POS drawer-kick byte sequence (typically `\x1B\x70\x00\x40\x40` for pin 2, 24V).
- **TODO:** Verify the byte sequence + find a discuss.frappe.io thread documenting the ERPNext v16 implementation.

#### Brother QL label printers — AirPrint vs ESC/POS
- **Status:** Likely Yellow.
- **Caveats:** Brother QL series supports AirPrint (good for iPad) and CUPS but does NOT use ESC/POS. Integration on a server that drives label printing requires Brother's `ql-printer` Linux drivers OR a print-server intermediary.
- **TODO:** Search community for "Brother QL ERPNext" — is anyone successfully driving label printing from ERPNext directly, or is everyone using the Brother iPrint&Label app outside ERPNext?

#### Barcode scanner integration with ERPNext POS Sales Invoice
- **Status:** Likely Yellow.
- **Caveats:** USB HID wedge means the scanned text goes to the focused input. ERPNext's POS UI must focus the right input (item search) before scan. If the focus is elsewhere (customer name, payment method), the scan goes to the wrong field.
- **Workaround pattern:** UI-level "scanner mode" that constrains focus, or a hidden global keystroke listener that intercepts scanner-burst patterns regardless of focus.
- **TODO:** Check Hamilton's existing JS for whether retail-cart UI implements scanner-mode focus management. (Almost certainly NOT yet — Phase 1 Hamilton has no scanner integration.)

### Red list (likely; verify)

#### Square Terminal with adult-classified merchants
- **Status:** Likely Red — but this is policy / classification, not technical integration.
- **Caveats:** Square's TOS explicitly excludes many adult-adjacent business types. Termination during operation has been reported across multiple POS platforms (not just ERPNext). The integration works fine until Square classifies and terminates.
- **TODO:** Find Reddit / forum reports specifically of Hamilton-style businesses being terminated by Square. Cross-reference with the merchant processor comparison doc.

#### Old Symbol scanners (pre-Zebra acquisition era)
- **Status:** Likely Red for new builds; Yellow if already in service.
- **Caveats:** Pre-2014 Symbol scanners (DS6707, DS6878, etc.) are out of vendor support. USB HID still works, but firmware updates are no longer issued. New AAMVA DL formats may not be parsed correctly.
- **TODO:** Confirm specific models flagged as discontinued.

#### Generic / no-name USB barcode scanners off Amazon
- **Status:** Likely Red.
- **Caveats:** Sub-$50 USB scanners may work technically, but: missing PDF417 support, missing 2D capability (1D only), inconsistent decode quality, no firmware updates, no warranty support.
- **TODO:** Find a couple of reddit/forum threads documenting community regrets.

---

## Format for completed entries

Once the methodology has been run, each entry should look like:

```
### [Hardware vendor / model]

**Verdict:** Green / Yellow / Red
**ERPNext versions tested:** v15.x, v16.x (per report)
**Sources:**
  - https://discuss.frappe.io/t/<thread-id> (date) — "<short summary>"
  - https://github.com/frappe/erpnext/issues/<issue-id> (date) — "<short summary>"
  - https://reddit.com/r/erpnext/comments/<id> (date) — "<short summary>"

**What works:** Specific list.
**What doesn't:** Specific list.
**Workaround:** Description if Yellow.
**Recommendation:** Buy / consider / avoid.
**Last reviewed:** YYYY-MM-DD by <reviewer>.
```

---

## How to keep this doc current

- **Cadence:** Re-run the methodology every 6 months. Frappe / ERPNext release cadence + processor TOS changes mean field reports go stale fast.
- **Integration with monthly upgrade window** (per `CLAUDE.md` "Production version pinning"): when reviewing the version-16 tag list each month, also scan recent ERPNext POS-related issues for hardware-affecting changes. Update this doc if a new hardware regression or fix lands.
- **Single source of truth:** This file is canonical. Don't fork into per-venue versions; one consolidated doc ensures Hamilton's findings inform Philadelphia / DC / Dallas decisions.

---

## What this doc DOES NOT do

- **Replace vendor-direct verification.** Specs change. Always verify against the vendor product page before purchase.
- **Substitute for hands-on testing.** Even a 2-week pilot of any new hardware before bulk ordering is worth the time.
- **Cover non-ERPNext POS scenarios.** This file is scoped to Frappe / ERPNext + iPad workflows. Different POS platforms have different community reports.

---

## Open work for the next session

To complete this doc, the next session needs:

1. **WebSearch / WebFetch tools loaded** (or browser access) — required for the methodology section above
2. **A budget of ~2-4 hours** to browse forums, capture URLs, summarize threads
3. **A second pass to verify each "(VERIFY)" claim above** with actual citations
4. **Cross-link back into `docs/design/pos_hardware_spec.md`** — once Green/Yellow/Red lists are populated, the hardware spec's recommendations should reference this doc inline (e.g. "Honeywell Voyager 1602g — Green list per `docs/research/erpnext_hardware_field_reports.md` §X")

If a future Claude session has WebSearch / WebFetch tools loaded by default, this is a natural follow-up task to schedule.

---

## References

- `docs/design/pos_hardware_spec.md` — consolidated hardware spec; consumes this doc's findings
- `docs/design/pos_scanner_spec.md` — ID scanner spec; consumes this doc's findings on Honeywell / Zebra scanners
- `docs/research/merchant_processor_comparison.md` — companion deliverable; complements this with processor-specific community reports
- `discuss.frappe.io` — primary research source
- `github.com/frappe/erpnext/issues` — secondary research source
- `reddit.com/r/erpnext` — tertiary research source
