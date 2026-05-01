# Label Printer Evaluation — Hamilton ERP POS Stack
**Date:** 2026-05-01
**Author:** Claude Code research pass (Opus)
**Status:** Procurement brief — feeds DEC-011 review and `pos_hardware_spec.md` update PR
**Decision owner:** Chris Srnicek
**Scope:** Multi-venue rollout — Hamilton (ON), Philadelphia (PA), DC, Dallas (TX)

---

## 1. TL;DR

- **Top recommendation:** **Keep Brother QL-820NWB as primary** for Phase 1 Hamilton go-live. It is the only printer in the field that ships a first-party iOS/iPadOS SDK with P-touch template support, full template/variable substitution, and a USB+WiFi+Bluetooth+Ethernet quadruple-interface — every other contender either ships AirPrint-only (no template flexibility) or has weak/no iPadOS SDK.
- **Backup recommendation:** **Zebra ZD421d** as the secondary/escalation choice for venues that need higher throughput or 4-inch wide retail labels. Link-OS iOS SDK is more mature and venue-agnostic than Brother's, but ZD421d is overkill for locker-tag/cash-drop and the unit cost is roughly 2× the QL-820NWB.

**Bottom line:** Brother is still right for 2026-Q2. DEC-011 does NOT need amending. The decision should be re-confirmed (with explicit current-2026 evidence on the record) rather than reversed.

---

## 2. Hard requirements recap

| Requirement | Source |
|---|---|
| iPadOS 17+ via USB-C or WiFi (LAN ethernet acceptable backup) | Hamilton iPad-only POS architecture |
| Template registry — accept arbitrary label dimensions and dynamic data fields from Hamilton's `Label Template` DocType | Hamilton ERP design |
| Direct thermal (no ribbon swap) | Operator-friendly — single-operator most shifts |
| Available CA + US through normal B2B channels | Multi-venue rollout (Hamilton, Philly, DC, Dallas) |
| Sub-CAD $400 unless quality justifies higher | Per-venue procurement budget |
| Three use cases: locker-key tag (~1.1×0.4 in), cash-drop label (~2.4×1.1 in), retail SKU (~1×1 in continuous) | Phase 1 + Phase 2 cart |

Per Hamilton's "hardware procurement is per-venue, never bulk" rule (CLAUDE.md), this brief sets the **spec-of-record at the time of Hamilton go-live**. Each future venue re-evaluates against the then-current spec — this is not a multi-site lock-in.

---

## 3. Comparison table

| Model | iPad path | Roll economics ($/1000 labels, est.) | SDK / template flex | Direct thermal? | CA + US availability | Price (USD) | Notable caveats |
|---|---|---|---|---|---|---|---|
| **Brother QL-820NWB** *(incumbent)* | First-party Brother Print SDK for iOS (Network/WiFi/BT) + iPrint&Label app + AirPrint fallback | DK-1209 (locker tag, 1.1×2.4): genuine ~$25/800 = **$31/1k**; generic ~$4-8/800 = **$5-10/1k**. DK-1201 (cash drop, 1.1×3.5): genuine ~$22/400 = **$55/1k**. Continuous DK-2205 (retail): genuine ~$22/100ft = ~$22/1k @ 1″ length | **Excellent** — Brother iOS SDK supports raster/PDF/PNG/template, P-touch Template engine with up to 255 templates × 50 objects, variable substitution from data. P-touch Template Command Reference doc public. | Yes | Amazon.ca, Amazon.com, CDW.ca, CDW.com, B&H, Staples — all stock | **~$280-330** | DK-roll lock-in is real but generic compatible rolls work fine in practice; WiFi+BT+Ethernet+USB; 300×600dpi |
| **Brother QL-1110NWB** *(successor / wider format)* | Same first-party iOS SDK as QL-820NWB | Same DK rolls + DK-1247 (4″ wide shipping) — only model in family that goes wide. ~$30/200 = **$150/1k** for 4″ | **Excellent** (same SDK) | Yes | Amazon, B&H, Best Buy, Staples, CDW, Shopify Hardware | **~$300-380** | Adds 4″ wide capability. Overkill for locker tags but flexible; ~69 labels/min |
| **Zebra ZD421d** | First-party Link-OS Multiplatform SDK (Objective-C / Swift), Bluetooth LE 5.0/5.3 + WiFi + USB | Generic 4″ direct-thermal continuous rolls dominate market. **$10-20/1k** at scale (Zebra Z-Perform / generic). Tiny labels (1.1×0.4) require die-cut order — niche supply | **Best in class** — Link-OS SDK is the industry reference. ZPL native, raw command support, arbitrary dimensions, label-format variable substitution. Used by Shopify POS, Square Hardware, and most enterprise WMS | Yes (ZD421d = direct thermal variant; ZD421t = ribbon) | CDW, B&H, Atlas RFID, Barcode Factory, durafast, omegabrand — all stock; CDW.ca for Canada | **~$450-650 USD** depending on connectivity tier (USB-only ~$450, WiFi+BT ~$600+) | Over budget for sub-CAD $400 target. 4-inch printer is physically larger; small locker-tag use case is awkward — die-cut tag stock for Zebra is harder to source than DK-1209 |
| **Rollo X1040 Wireless** | **AirPrint only** — no SDK | 4×6 shipping role only — designed for it. Generic 4×6 thermal: **~$10-15/1k**. Tiny tag/cash drop sizes are NOT supported (1.57″ minimum width). | **None** — AirPrint only; no template engine, no variable substitution. iPad sees it as a generic IPP printer | Yes | Best Buy, Newegg, Walmart, Micro Center, Rollo direct | **~$280** | **Fails locker-tag use case**: 1.57″ minimum width vs Hamilton's 1.1″ tag. 4×6 shipping-label specialist, not a multi-format printer |
| **Munbyn ITPP941** | AirPrint over WiFi (ITPP941AP variant) or Bluetooth (ITPP941B) | 4″ wide max; small-format support same problem as Rollo. **~$8-12/1k** generic | **Weak** — AirPrint primary; Labelife app on iOS but no documented programmatic SDK suitable for an ERP-driven template registry | Yes | Amazon, eBay, Munbyn direct (US shipping; Canada via Amazon.ca) | **~$160-220** | Cheapest in class but the SDK story is the dealbreaker. Consumer-grade build; reviews reasonable but enterprise deployment risk is real |
| **Phomemo PM-241BT** | Bluetooth-only, Labelife app on iOS | 4″ wide only — fails locker-tag size | **Weak** — manufacturer SDK story is unclear; Labelife is the only documented mobile path. No published Objective-C/Swift SDK | Yes | Amazon, Phomemo direct | **~$80-130** | Consumer-grade. **Bluetooth-only** rules it out per Hamilton's WiFi-required network model (front desk has no wired drop near printer; BT range/pairing reliability is operator-hostile in shift-handoff scenarios). |
| **DYMO LabelWriter 5XL** | **No AirPrint, USB-only, no iPadOS app for 5XL** (only the Wireless variant has iOS) | DYMO 4×6 rolls are proprietary and pricier than Zebra/generic. **~$25-40/1k** | **None on iPad** — DYMO LabelWriter Wireless is the iOS option, but the 5XL is USB-only | Yes | Amazon, CDW, Office Depot, Staples | **~$210-300** | **Hard fail on iPad**. The 5XL specifically has no iOS path. The "DYMO LabelWriter Wireless" variant has iOS support but is a different (slower, smaller) printer |

**Notes on the table:**

- Roll-economics numbers are order-of-magnitude estimates from current retail listings. Procurement should re-quote when an actual order is placed; high-volume B2B pricing typically beats the retail figures by 20-40%.
- "First-party iOS SDK" means a manufacturer-published, manufacturer-maintained SDK with template/variable-substitution APIs. AirPrint is a print-stack abstraction — it does NOT support arbitrary template engines with dynamic data binding, only raster/PDF flow.
- Hamilton's Phase 2 retail SKUs are 4 items and sub-1″ continuous. None of the contenders fail on retail; the locker-tag use case is the discriminator.

---

## 4. Use-case scoring matrix

| Printer | UC-1 Locker tag (1.1×0.4) | UC-2 Cash-drop label (2.4×1.1) | UC-3 Retail SKU (1×1 continuous) | Overall |
|---|---|---|---|---|
| Brother QL-820NWB | ✅ DK-1209 (1.1×2.4) cropped or custom; SDK supports custom dims | ✅ DK-1209 native size | ✅ DK-2205 continuous + cut | **All three** |
| Brother QL-1110NWB | ✅ Same DK roll family; wider capacity unused but available | ✅ Same | ✅ Same | **All three** |
| Zebra ZD421d | ⚠️ Possible with custom die-cut; small-format niche supply chain | ✅ Native 4″ direct thermal | ✅ Continuous roll | **All three** but UC-1 supply chain weaker |
| Rollo X1040 | ❌ 1.57″ minimum width — cannot print locker tag at 1.1″ width | ⚠️ Possible at 2.4×1.1 if 1.57″ min isn't actually 1.57″ across all variants — verify | ✅ Continuous 4×6 | **Fails UC-1** |
| Munbyn ITPP941 | ❌ Same width-floor issue as Rollo | ⚠️ Width-floor; verify spec for narrow labels | ✅ Continuous | **Fails UC-1** + weak SDK |
| Phomemo PM-241BT | ❌ Width-floor + Bluetooth-only | ⚠️ Width-floor | ✅ Continuous | **Fails UC-1** + BT-only |
| DYMO LabelWriter 5XL | ❌ No iPad path (USB-only on 5XL) | ❌ No iPad path | ❌ No iPad path | **Fails all three on iPad** |

**Conclusion:** Only the two Brother models and the Zebra ZD421d cover all three use cases. The shipping-label specialists (Rollo, Munbyn, Phomemo) and DYMO 5XL are eliminated.

---

## 5. iPad SDK notes per model

| Printer | iPad SDK status | Hamilton fit |
|---|---|---|
| Brother QL-820NWB / QL-1110NWB | First-party Brother Print SDK for iOS (also called "Mobile SDK"). Supports raster/PRN/PDF/PNG/JPEG/BMP. P-touch Template engine with up to 255 templates and variable substitution from external data. Public command reference (P-touch Template Command Reference, doc cv_ql820_eng_ptemp_102.pdf). Capacitor/Cordova/Flutter community wrappers exist. iPad listed as supported target. | **Strong fit.** Hamilton's `Label Template` DocType maps cleanly onto P-touch Template object/variable model. Templates are designed in P-touch Editor (desktop), transferred to printer once, then triggered with data from iPad. |
| Zebra ZD421d | Link-OS Multiplatform SDK — Objective-C iOS bindings, Swift-compatible. Raw ZPL command support. Most mature SDK in the desktop-thermal segment; Bluetooth LE 5.0/5.3 + WiFi + USB. Used by Shopify POS, Square Hardware, most enterprise WMS. | **Strong fit on SDK; budget marginal.** ZPL is more powerful than P-touch Template but also requires more dev work to template properly. Total cost rules it out as primary unless throughput justifies it (it does not for Hamilton Phase 1). |
| Rollo X1040 | **AirPrint only.** No published SDK. iPad sees the printer as a generic IPP/Bonjour endpoint. | **Yellow flag.** AirPrint sends a rasterized page; there's no first-class way to send a template name + variable data and have the printer fill in the rest. Hamilton would have to render the entire label image client-side on every print, which works but ties label rendering to iPad code rather than a template registry. Also imposes a width floor that fails UC-1. |
| Munbyn ITPP941 | AirPrint + Labelife consumer mobile app. No public iOS SDK with template/variable-substitution APIs documented. | **Eliminated.** AirPrint-only constraints + width floor. |
| Phomemo PM-241BT | Bluetooth + Labelife app. No public iOS SDK suitable for ERP integration. | **Eliminated.** BT-only + no SDK. |
| DYMO LabelWriter 5XL | **No iPad SDK on the 5XL** (USB-only variant). DYMO LabelWriter Wireless is a separate, smaller, slower printer that does have iOS support via DYMO Connect Mobile. | **Eliminated** for Hamilton (5XL specifically). DYMO Connect Mobile is consumer-grade and is not a programmatic SDK in the sense Hamilton needs. |

**Why "AirPrint-only" is a yellow flag for Hamilton:**
Hamilton's `Label Template` DocType is supposed to store templates with named data fields (e.g., `{locker_number}`, `{check_in_time}`, `{operator_initials}`). The intended flow is: server-side or iPad-side substitutes values into a template, sends to printer. With a first-party SDK (Brother / Zebra), substitution can happen on the printer using stored templates — fast, low-bandwidth, consistent. With AirPrint-only, every print must be a fully-rendered raster image, which makes the printer a "dumb" output device and pushes all template logic to iPad rendering. That works, but it means Hamilton's Label Template registry becomes a JavaScript/iPad-side rendering problem rather than a printer-side template problem, with the cost paid in label-render code complexity and per-print latency.

---

## 6. Final recommendation

### Primary: **Brother QL-820NWB** (no change from incumbent spec)

**Reasoning:**

1. **Only contender that covers all three use cases AND has a real iOS SDK AND fits the budget.** Zebra ZD421d also covers all three but is over budget. Everything else fails at least one of (a) locker-tag width, (b) iPad SDK, (c) WiFi connectivity.
2. **First-party Brother Print SDK for iOS** is real, current, and exposes the P-touch Template engine that Hamilton's `Label Template` DocType is effectively designed to drive. Up to 255 templates × 50 objects with variable substitution — comfortably more than Hamilton needs.
3. **DK-roll "lock-in" is overstated.** Generic compatible DK-1209 / DK-1201 rolls are widely available at $4-10 per 800-label roll (vs Brother branded ~$25). The proprietary roll cassette is a venue-by-venue annoyance but not a structural cost problem.
4. **Multi-interface (USB + WiFi + Bluetooth + Ethernet)** matches Hamilton's "WiFi primary, ethernet acceptable backup" requirement exactly. No other in-budget contender offers all four.
5. **Sub-budget at ~$280-330 USD** (~CAD $380-450 at current rates — close to budget; verify CAD pricing at quote time).

### Backup: **Zebra ZD421d** (escalation only)

**Reasoning:**

1. Best-in-class iOS SDK (Link-OS), full ZPL programmability.
2. Use only if (a) Hamilton finds the Brother SDK insufficient in practice for a future feature, OR (b) a future venue (Philadelphia/DC/Dallas) needs higher throughput or 4-inch wide retail labels at volume that the QL-820NWB can't handle.
3. Over-budget at $450-650 USD per unit; small-format die-cut supply chain weaker than Brother's DK roll line.

### Re-evaluate at the QL-1110NWB upgrade decision point

- If Hamilton's Phase 2 retail SKUs grow to require 4-inch wide labels, the QL-1110NWB ($300-380 USD) is the natural next step. Same SDK, same DK-roll family, just wider. This would not be a vendor change — same Brother stack.
- The QL-1115NWB exists in some Brother references (community SDKs reference it) but appears to be regional/EU-flavored. Don't pursue unless Brother formally lists it on brother-usa.com / brother.ca with full support docs.

### DEC-011 amendment status

**Not needed.** Brother QL-820NWB remains the primary spec. The decisions log should record this re-evaluation as a re-confirmation, not an amendment:

> **DEC-011 re-confirmation (2026-05-01):** Re-evaluated against Zebra ZD421d, Rollo X1040, Munbyn ITPP941, Phomemo PM-241BT, DYMO LabelWriter 5XL, and Brother QL-1110NWB. Brother QL-820NWB remains primary. Zebra ZD421d added as backup/escalation. See `docs/research/label_printer_evaluation_2026_05.md`.

If Chris wants a stronger paper trail he can formally append this as a comment to DEC-011 rather than a separate decision number.

---

## 7. Action items (post-review, separate PR)

1. Update `docs/design/pos_hardware_spec.md` to:
   - Cite this brief as the 2026-Q2 re-evaluation
   - Confirm Brother QL-820NWB primary
   - Add Zebra ZD421d as named backup
   - Note QL-1110NWB as the natural upgrade if Phase 2 needs wider labels
2. Append re-confirmation note to `docs/decisions_log.md` DEC-011 entry
3. No code changes required — Hamilton's `Label Template` DocType design already aligns with Brother P-touch Template semantics

---

## 8. Sources

### Manufacturer pages
- [Brother QL-820NWB product page](https://www.brother-usa.com/products/ql820nwb)
- [Brother QL-820NWB specifications (Canada)](https://support.brother.com/g/b/spec.aspx?c=ca&lang=en&prod=lpql820nwbeus)
- [Brother QL-820NWB downloads / SDK](https://support.brother.com/g/b/downloadtop.aspx?c=us&lang=en&prod=lpql820nwbeus)
- [Brother QL-1110NWB product page](https://www.brother-usa.com/products/ql1110nwb)
- [Brother iPrint&Label app (App Store)](https://apps.apple.com/us/app/brother-iprint-label/id523047493)
- [Brother Developer Program — SDK downloads](https://developerprogram.brother-usa.com/sdk-download)
- [Brother Mobile SDK Manual](https://support.brother.com/g/s/es/htmldoc/mobilesdk/)
- [Brother P-touch Template Command Reference (QL-810W/820NWB)](https://download.brother.com/welcome/docp100307/cv_ql820_eng_ptemp_102.pdf)
- [Zebra ZD421 product page](https://www.zebra.com/us/en/products/printers/desktop/zd400-series/zd421.html)
- [Zebra ZD421 Series support](https://www.zebra.com/us/en/support-downloads/printers/desktop/zd421.html)
- [Zebra Link-OS Multiplatform SDK — Developer Portal](https://developer.zebra.com/products/printers/link-os-multiplatform-sdk)
- [Zebra Link-OS iOS TechDocs](https://techdocs.zebra.com/link-os/2-13/ios/)
- [Zebra Printer Setup Utility (App Store)](https://apps.apple.com/us/app/zebra-printer-setup-utility/id1454308745)
- [Rollo Wireless Label Printer (X1040)](https://www.rollo.com/product/rollo-wireless-printer/)
- [Rollo blog — AirPrint workflow](https://www.rollo.com/blog/how-airprint-and-rollo-simplify-your-shipping/)
- [Munbyn ITPP941 overview](https://munbyn.com/pages/itpp941-thermal-label-printer-white-overview)
- [Munbyn 941 Series POS](https://pos.munbyn.com/munbyn-itpp941-series-thermal-label-printer/)
- [Phomemo PM-241BT](https://phomemo.com/products/pm-241bt)
- [DYMO LabelWriter 5XL](https://www.dymo.com/label-makers-printers/labelwriter-label-printers/dymo-labelwriter-5xl-label-printer/SP_1373968.html)
- [DYMO LabelWriter 5XL CDW](https://www.cdwg.com/product/dymo-labelwriter-5xl-label-printer-b-w-direct-thermal/6650138)

### Retail / B2B availability + pricing
- [Brother QL-820NWB on Amazon.com](https://www.amazon.com/Brother-QL-820NWB-Professional-Monochrome-Connectivity/dp/B01MTYE0X6)
- [Brother QL-820NWB on Amazon.ca](https://www.amazon.ca/Brother-QL820NWB-Electronic-Label-Printer/dp/B01MTYE0X6)
- [Brother QL-820NWB CDW.ca](https://www.cdw.ca/product/brother-ql-820nwb-label-printer-b-w-direct-thermal/4543346)
- [Brother QL-820NWB CDW.com](https://www.cdw.com/product/brother-ql-820nwb-label-printer-b-w-direct-thermal/4432484)
- [Brother QL-1110NWB B&H](https://www.bhphotovideo.com/c/product/1618049-REG/brother_ql_1110nwb_wide_format_professional_label.html)
- [Brother QL-1110NWB Amazon](https://www.amazon.com/Brother-QL-1110NWB-Professional-Wireless-Connectivity/dp/B079G51QT9)
- [Zebra ZD421d on Amazon](https://www.amazon.com/Thermal-Desktop-Printer-Ethernet-ZD4A042-D01E00EZ/dp/B09BXZVGXQ)
- [Zebra ZD421d CDW (USB+ethernet)](https://www.cdw.com/product/zebra-zd400-series-zd421-label-printer-b-w-direct-thermal/6477314)
- [Zebra ZD421d CDW (WiFi)](https://www.cdw.com/product/zebra-zd421-203dpi-direct-thermal-desktop-printer-ezpl/6480130)
- [Zebra ZD421d Barcode Factory](https://www.barcodefactory.com/zebra/printers/zd421d)
- [Rollo X1040 Best Buy](https://www.bestbuy.com/product/rollo-wireless-label-printer-wi-fi-airprint-thermal-printer-for-shipping-packages-supports-windows-and-mac-iphone-white/JJGCY945C5)
- [Rollo X1040 Newegg](https://www.newegg.com/p/N82E16828953002)
- [Munbyn ITPP941 on Amazon](https://www.amazon.com/MUNBYN-Wireless-Shipping-Compatible-Chromebook/dp/B0CXJ7K5SJ)
- [Phomemo PM-241BT on Amazon](https://www.amazon.com/Phomemo-241bt-Thermal-Printer-Business/dp/B0C9Q1YRM4)

### DK roll economics
- [Brother DK-1209 (24-pack)](https://www.brother-usa.com/products/dk120924pk)
- [DK-1209 generic compatible (Amazon, 8-pack)](https://www.amazon.com/Compatible-Brother-DK-1209-Address-Printers/dp/B0DXTXJ25L)
- [DK-1209 generic 40-pack USUPERINK](https://www.amazon.com/USUPERINK-Compatible-Brother-DK-1209-Shipping/dp/B09YV68T1M)
- [DK-1209 LD Products compatible](https://www.ldproducts.com/compatible-brother-dk1209-white-address-label)
- [DK-1209 4inkjets compatible](https://www.4inkjets.com/compatible-brother-dk1209-white-address-label)

### iPad / SDK references
- [Brother iOS SDK community wrapper (Capacitor)](https://github.com/rdlabo-team/capacitor-brotherprint)
- [Brother QL Python raster wrapper (pklaus/brother_ql)](https://github.com/pklaus/brother_ql)
- [Apple Community thread — DYMO 4XL/5XL on iPad (no path)](https://discussions.apple.com/thread/8316462)
- [DYMO FAQ — printing from iPad (UK Dymo Shop)](https://www.dymo-label-printers.co.uk/news/faq-can-i-print-to-a-labelwriter-from-an-ipad.html)

---

**Prepared for Chris Srnicek's review.** No code or production changes made by this brief; it drives a follow-up PR that updates `docs/design/pos_hardware_spec.md` and appends a re-confirmation note to `docs/decisions_log.md` DEC-011.
