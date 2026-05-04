# HST Remittance Report — CRA Line Item to ERPNext Field Mapping

**Date:** 2026-05-04  
**Purpose:** Task 31 specification — Map CRA Form GST34-2/GST62 line items to ERPNext data sources  
**Sources:**
- CRA: [canada.ca HST Return Instructions](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/complete-file-instructions.html)
- ERPNext: Local DocType schemas (Sales Invoice, Purchase Invoice, GL Entry)

---

## CRA Form Overview

**Form Numbers:** GST34-2 (Personalized) / GST62 (Non-Personalized)  
**Filing Frequency:** Monthly, quarterly, or annual (based on revenue threshold)  
**Applicable Tax:** HST 13% in Ontario (composed of 5% GST + 8% provincial portion)

---

## Line Item Mapping

| CRA Line | Description | ERPNext Data Source | Match Status | Notes |
|----------|-------------|---------------------|--------------|-------|
| **101** | Sales and other revenue | `Sales Invoice.net_total` (sum all submitted invoices) | ✅ CLEAN | Net total before tax. Include zero-rated and exempt supplies. |
| **103** | GST/HST collected or collectible | `Sales Taxes and Charges.base_tax_amount` WHERE `account_head` = HST Payable account | ✅ CLEAN | Sum from child table. Filter by HST account only. |
| **104** | Adjustments | Manual entry or custom field | ⚠️ GAP | ERPNext has no standard "HST adjustment" field. Requires custom field or Journal Entry tracking. |
| **105** | Total GST/HST (Line 103 + 104) | Calculated: Line 103 + Line 104 | ✅ CLEAN | Auto-calculated in report. |
| **106** | Input Tax Credits (ITCs) | `Purchase Taxes and Charges.base_tax_amount` WHERE `account_head` = HST Payable account | ✅ CLEAN | Sum from Purchase Invoice taxes child table. Same account as Line 103. |
| **107** | Other ITCs | Manual entry or custom tracking | ⚠️ GAP | Rare: includes capital asset ITCs, vehicle allowances. Not in standard ERPNext. |
| **108** | Total ITCs (Line 106 + 107) | Calculated: Line 106 + Line 107 | ✅ CLEAN | Auto-calculated in report. |
| **109** | Net tax (Line 105 - 108) | Calculated: Line 105 - Line 108 | ✅ CLEAN | Auto-calculated. Positive = owe CRA, negative = refund. |
| **110** | Quarterly instalments paid | `Payment Entry` WHERE `payment_type` = 'Pay' AND `party_type` = 'Supplier' AND `party` = 'CRA' | ⚠️ GAP | Requires tagging instalment payments to CRA as supplier. Not auto-tracked. |
| **111** | Pension entity rebate | Manual entry or N/A | ⚠️ GAP | Hamilton is not a pension entity. Field can remain null. |
| **113** | Refund or balance owing | Calculated: Line 109 - Line 110 - Line 111 | ✅ CLEAN | Auto-calculated. |
| **114** | Refund claimed (if negative) | Display Line 113 as positive if < 0 | ✅ CLEAN | Conditional display logic. |
| **115** | Amount due (if positive) | Display Line 113 if > 0 | ✅ CLEAN | Conditional display logic. |
| **205** | Real property purchases | `Purchase Invoice` with custom category or manual flag | ⚠️ GAP | Only for taxable real property >50% commercial use. Rare for Hamilton. Requires manual flagging. |

---

## Critical Gaps

### 1. **Zero-Rated vs Exempt Supplies (Line 101 Detail)**

**CRA Requirement:**  
Line 101 must include total revenue from:
- Taxable supplies (13% HST in Ontario)
- Zero-rated supplies (0% HST — exports, basic groceries)
- Exempt supplies (no HST — residential rent, financial services)

**ERPNext Reality:**  
- ERPNext calculates `net_total` correctly but **does not distinguish** zero-rated from exempt.
- Both are implemented as 0% tax rate in Item Tax Templates.
- CRA form does NOT require separate reporting of zero-rated vs exempt on Line 101, but CRA may request breakdown during audit.

**Solution for Hamilton:**  
- Hamilton has **no zero-rated or exempt items** (all admissions and retail are taxable at 13%).
- Line 101 = `net_total` sum is sufficient.
- If Hamilton adds exempt items (e.g., membership fees as financial service), create custom Item Group or Item Tax Category to classify.

**Flag:** ⚠️ **Minor gap** — acceptable for Hamilton Phase 1, revisit if exempt items added.

---

### 2. **HST Adjustments (Line 104)**

**CRA Requirement:**  
Adjustments include:
- Bad debt recoveries
- Previously uncollected HST now collected
- Corrections from prior periods

**ERPNext Reality:**  
- No standard field for "HST adjustment".
- Could use:
  - **Journal Entry** with HST account debit/credit (most accurate)
  - **Custom field** on a summary DocType (less auditable)

**Solution for Hamilton:**  
- Create **custom Journal Entry tag** or **Document naming convention** (e.g., "HST-ADJ-2024-Q1").
- Report queries Journal Entries with HST account and "ADJ" tag.

**Flag:** ⚠️ **Gap requires custom solution** — implement in Task 31.

---

### 3. **Instalment Payments (Line 110)**

**CRA Requirement:**  
Quarterly instalments paid to CRA during the reporting period.

**ERPNext Reality:**  
- Payment Entries can record payments to CRA as a "Supplier".
- No auto-link to HST remittance context.

**Solution for Hamilton:**  
- Create **CRA as a Supplier** in ERPNext.
- Tag instalment payments with custom field: `is_hst_instalment = 1`.
- Report sums Payment Entries with this flag.

**Flag:** ⚠️ **Gap requires custom field** — implement in Task 31.

---

### 4. **Real Property Purchases (Line 205)**

**CRA Requirement:**  
Report taxable real property purchases where buyer is GST/HST registrant and property used >50% commercially.

**ERPNext Reality:**  
- Purchase Invoices do not auto-flag real property.

**Solution for Hamilton:**  
- Hamilton unlikely to purchase real property during operations.
- If needed: manually flag Purchase Invoice with custom checkbox `is_real_property_purchase`.

**Flag:** ⚠️ **Low priority gap** — defer until needed.

---

## ERPNext Query Strategy

### Line 101: Sales Revenue
```sql
SELECT SUM(net_total)
FROM `tabSales Invoice`
WHERE docstatus = 1
  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
  AND company = %(company)s
```

### Line 103: HST Collected
```sql
SELECT SUM(stc.base_tax_amount)
FROM `tabSales Invoice` si
INNER JOIN `tabSales Taxes and Charges` stc
  ON stc.parent = si.name
WHERE si.docstatus = 1
  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
  AND si.company = %(company)s
  AND stc.account_head = %(hst_account)s
```

### Line 106: HST Paid on Purchases (ITCs)
```sql
SELECT SUM(ptc.base_tax_amount)
FROM `tabPurchase Invoice` pi
INNER JOIN `tabPurchase Taxes and Charges` ptc
  ON ptc.parent = pi.name
WHERE pi.docstatus = 1
  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
  AND pi.company = %(company)s
  AND ptc.account_head = %(hst_account)s
```

### Line 110: Instalments Paid (requires custom field)
```sql
SELECT SUM(paid_amount)
FROM `tabPayment Entry`
WHERE docstatus = 1
  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
  AND company = %(company)s
  AND party = 'CRA'
  AND is_hst_instalment = 1
```

---

## Implementation Checklist (Task 31)

### Schema Changes
- [ ] Add `Payment Entry.is_hst_instalment` (Check field)
- [ ] Add `Journal Entry.is_hst_adjustment` (Check field)
- [ ] Optional: Add `Purchase Invoice.is_real_property_purchase` (Check field)

### Configuration
- [ ] Create **CRA** as Supplier in ERPNext
- [ ] Document HST Payable account name (e.g., "HST Payable - H")
- [ ] Create **Sales Taxes and Charges Template** for HST 13% Ontario
- [ ] Verify Item Tax Templates for zero-rated items (if any)

### Report Build
- [ ] Create Script Report: `HST Remittance Report (CRA GST34)`
- [ ] Filters: `from_date`, `to_date`, `company`
- [ ] Columns: CRA Line Number, Description, Amount (CAD)
- [ ] Output format matches CRA form structure
- [ ] Chart: Net Tax trend (optional)

### Testing
- [ ] Run report on Hamilton test site with sample data
- [ ] Verify Line 103 matches GL Entry sum for HST Payable account (credit side)
- [ ] Verify Line 106 matches GL Entry sum for HST Payable account (debit side)
- [ ] Cross-check Line 113 against GL Entry balance for reporting period

### Documentation
- [ ] Manager guide: How to tag instalment payments
- [ ] Manager guide: How to record HST adjustments via Journal Entry
- [ ] Accountant guide: CRA form completion from report output

---

## Forward Compatibility Notes

### Multi-Location HST Rates
If Hamilton expands to other provinces:
- **Quebec:** 14.975% (5% GST + 9.975% QST — reported separately)
- **Alberta:** 5% GST only (no provincial portion)
- **BC:** 12% HST (5% GST + 7% provincial)

**Solution:** Filter by `Company` in report. Each venue entity has separate HST accounts.

### Philadelphia (Non-Canadian Entity)
- Philadelphia location will NOT file Canadian HST.
- Report must filter by `company = "Hamilton Bathhouse Ltd."` only.

---

## References

### CRA Official Docs
- [Instructions for preparing a GST/HST return](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/complete-file-instructions.html)
- [Which GST/HST return to use in your situation](https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/calculate-prepare-report/which-gst-hst-return-use-your-situation.html)
- [Transcript - How to complete a GST/HST return](https://www.canada.ca/en/revenue-agency/news/cra-multimedia-library/businesses-video-gallery/transcript-complete-a-gst-hst-return.html)

### ERPNext Docs
- [Sales Taxes and Charges Template](https://docs.erpnext.com/docs/v13/user/manual/en/selling/sales-taxes-and-charges-template)
- [Item Tax Template](https://docs.erpnext.com/docs/v13/user/manual/en/accounts/item-tax-template)
- [Setting Up Taxes](https://docs.erpnext.com/docs/user/manual/en/setting-up-taxes)

### ERPNext Source (Local)
- `apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.json`
- `apps/erpnext/erpnext/accounts/doctype/sales_taxes_and_charges/sales_taxes_and_charges.json`
- `apps/erpnext/erpnext/accounts/doctype/purchase_taxes_and_charges/purchase_taxes_and_charges.json`
- `apps/erpnext/erpnext/accounts/doctype/gl_entry/gl_entry.json`

---

**Status:** Mapping complete. Ready for Task 31 implementation.  
**Next Steps:** Review with Chris → Build Script Report → Test with sample transactions → Deploy to staging.
