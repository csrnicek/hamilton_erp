# Phase 2 Multi-Venue Refactor Plan

**Status:** Planning — not implementation spec
**Authored:** 2026-05-01
**Scope:** Hamilton → Philadelphia → DC → Dallas rollout sequence; per-venue feature flag
dependencies; code-vs-spec drift that must close before venue two ships
**Source authority:** `docs/venue_rollout_playbook.md`, `docs/decisions_log.md` DEC-062/063/064,
`docs/design/cash_reconciliation_phase3.md` §3, `docs/design/manager_override_phase2.md`,
`CLAUDE.md` §Hamilton accounting / multi-venue conventions, `docs/risk_register.md` R-008

---

## 1. Scope and Timing

Hamilton ERP is a single-codebase, multi-site deployment. Each venue gets its own Frappe Cloud
site. Differentiation happens entirely through `site_config.json` feature flags — there are no
per-venue code branches and there never should be.

**Hamilton** is the only live venue today. Phase 1 is in progress; Phase 2 begins after Task 25
ships the Hamilton go-live verification.

**Sequence (planned, dates TBD):**

| Venue | Priority driver | Config delta from Hamilton |
|---|---|---|
| Hamilton | Already running | Baseline |
| DC | Membership (anvil_membership_enabled=1), 3 tablets | USD, US_NONE tax, membership DocType, multi-tablet sync |
| Philadelphia | PA tax complexity, rental waiver paperwork | USD, PA tax templates, multi-warehouse stock |
| Dallas | Straightforward USD, TX tax | USD, TX tax template |

DC ships before Philadelphia because DC's feature requirements (membership lifecycle, multi-tablet
operator support) are the deepest and should be validated before the simpler venues inherit the
pattern. Dallas ships last — it is the closest configuration to a "vanilla" USD venue and adds
only a new tax template.

**Why each venue is its own Frappe Cloud site, not a multi-company setup:**

Each venue operates as a separate legal entity under ANVIL Corp. They have separate tax
registrations, separate bank accounts, separate POS Closing Entries, and separate audit trails.
ERPNext's multi-company model would couple those audit trails and create cross-venue data
visibility risks. Per-site isolation is the correct architecture. Cross-venue consolidated
reporting (monthly ANVIL Corp P&L) is done by querying each site's API, not by sharing a
database.

---

## 2. Per-Venue Config — Current State

Per-venue differentiation is implemented through five `site_config.json` keys set via
`bench set-config` at deploy time. These are the only currently-defined feature flags.

| Key | Type | Hamilton | Philadelphia | DC | Dallas |
|---|---|---|---|---|---|
| `anvil_venue_id` | string | `hamilton` | `philadelphia` | `dc` | `dallas` |
| `anvil_membership_enabled` | int (0/1) | `0` | `0` | `1` | `0` |
| `anvil_tax_mode` | string | `CA_HST` | `US_NONE` | `US_NONE` | `US_NONE` |
| `anvil_tablet_count` | int | `1` | `1` | `3` | `1` |
| `anvil_currency` | string | `CAD` | `USD` | `USD` | `USD` |

**What `US_NONE` means today:** The `anvil_tax_mode` value `US_NONE` is a placeholder. It signals
"not Canadian HST" but does not yet encode which US jurisdiction applies. Before any US venue
ships, `US_NONE` must be replaced with venue-specific values: `US_PA`, `US_DC`, `US_TX`. Each
of those will resolve to a different Sales Taxes Template (see §4). The config key rename is a
two-line code change plus a fixture update; capture it in the first US venue's rollout PR.

**What is NOT in site_config today but will need to be:**

- `anvil_primary_processor` — string, e.g. `fiserv`, `stripe_terminal` (required by DEC-063/064
  before any card payments ship at venue two)
- `anvil_backup_processor` — string, same choices (required by DEC-064)
- `anvil_float_amount` — decimal, per-venue starting till float (currently hardcoded to 0)
- `anvil_recon_profile` — DocType name for the venue's Reconciliation Profile (see §3 and
  `cash_reconciliation_phase3.md` §3)

These additions are non-breaking. Adding a new `site_config.json` key without code that reads it
has no effect. Add the key at rollout time; add the reading code in the same PR that needs it.

---

## 3. Membership Lifecycle — DC Priority

### Current state

`anvil_membership_enabled = 0` on all venues. No Membership DocType exists. Hamilton uses an
anonymous walk-in flow: every customer is the singleton "Walk-In Customer" record; sessions
carry no identifying information beyond `session_number`.

### What DC needs

DC sets `anvil_membership_enabled = 1`. The membership lifecycle has five states:

```
PENDING_PAYMENT → ACTIVE → LAPSED → CANCELLED
                            ↑  (renewal reactivates)
                 → SUSPENDED (manual, e.g. bad debt)
```

**Signup:** Member presents ID (required for age verification; see R-007 for the field-masking
requirement on `date_of_birth`). Operator creates a Member record. Payment clears. Status
transitions to ACTIVE. Member receives a member card (physical or digital QR).

**Check-in:** Operator scans member card. System resolves `member_id` → Member record →
eligibility check (ACTIVE status, no outstanding arrears). On pass, create Venue Session linked
to the member (as opposed to Walk-In Customer). On fail, surface the reason (LAPSED, SUSPENDED,
etc.) without exposing sensitive financial detail to front-desk operators.

**Renewal:** On expiry (30 days / 90 days / annual — venue-configurable), member status
transitions to LAPSED. Renewal payment reactivates. Grace period configurable.

**Cancel:** Operator or member requests cancellation. Status → CANCELLED. No further charges.
Prorated refund if prepaid; no refund if pay-per-use cycle already consumed.

**Refund:** Follows `docs/design/refunds_phase2.md` with the membership-specific rule:
refundable only within the current billing cycle's unused days. After cycle consumed, non-
refundable. Manager override required above the per-venue threshold (DEC-064 architecture).

### New DocType required: `Member`

Minimum fields:

| Field | Type | Notes |
|---|---|---|
| `member_id` | Data | Auto-generated unique ID (barcode/QR compatible) |
| `full_name` | Data | permlevel=1 (Manager+ only per R-007) |
| `date_of_birth` | Date | permlevel=1; AGCO age-verification if licensed |
| `identity_method` | Select | ID_CARD, PASSPORT, OTHER |
| `scanner_data` | Small Text | Raw scanner blob; permlevel=1 |
| `membership_status` | Select | PENDING_PAYMENT, ACTIVE, LAPSED, SUSPENDED, CANCELLED |
| `membership_tier` | Link | Membership Tier DocType (price, duration, access rules) |
| `joined_date` | Date | Auto on signup |
| `expiry_date` | Date | Computed from joined_date + tier.duration |
| `block_status` | Select | NONE, WARNED, BLOCKED |
| `arrears_amount` | Currency | permlevel=1 |
| `eligibility_snapshot` | Small Text | JSON snapshot at last eligibility check; permlevel=1 |

The eight permlevel=1 fields listed in R-007 must be implemented **before Philadelphia ships**
(R-007 is a pre-go-live blocker for venue two). Since the Member DocType is new, the
field-masking can be built in from the start rather than retrofitted.

### Hamilton's anonymous walk-in flow is unaffected

When `anvil_membership_enabled = 0`, the Member DocType exists on the site but no member records
are created. All sessions use Walk-In Customer. The asset board and session lifecycle do not
change. This is the correct pattern: shared schema, per-venue behavior via feature flag.

### Feature flag gate pattern

```python
# In api.py or session creation controller
if frappe.db.get_single_value("Hamilton Settings", "membership_enabled"):
    # Member lookup, eligibility check, session link to member
else:
    # Existing walk-in flow — unchanged
```

The flag is read from `Hamilton Settings` singleton (which mirrors `site_config` via the
`ensure_setup_complete` hook), not directly from `site_config` at call time. This preserves
testability: tests can toggle the Hamilton Settings field without touching the filesystem.

---

## 4. Multi-Jurisdiction Tax

### The rule (from CLAUDE.md)

One Sales Taxes Template per place-of-supply jurisdiction. Each venue's template must reflect
its own jurisdiction. No "global" template that covers multiple provinces or states.

### Current state

Hamilton: "Ontario HST 13%" template, set as the company's default. This template is correct for
Ontario only and must never be used for US venues.

### Required templates per venue

| Venue | Jurisdiction | Template name | Rate(s) | Notes |
|---|---|---|---|---|
| Hamilton | Ontario, Canada | Ontario HST 13% | HST 13% | Exists. Do not modify. |
| Philadelphia | Pennsylvania, USA | Pennsylvania Sales Tax PA | 6% standard; 8% prepared food/drinks | Two line items on the template — 6% base + 2% prepared-food surcharge via Item Tax Template for applicable SKUs |
| DC | Washington DC, USA | DC Sales Tax | 6% standard; 10% alcohol/restaurant | Same two-line pattern; `anvil_tax_mode` resolves to this template |
| Dallas | Texas, USA | Texas Sales Tax | 8.25% combined (state 6.25% + typical city/county) | Single combined rate for Harris County / Dallas County; verify local rate at rollout |

**Item Tax Templates** (for SKU-level overrides):
- Philadelphia and DC have category-level rate exceptions (prepared food, alcohol). These cannot
  be expressed in a single-rate Sales Taxes Template. ERPNext's Item Tax Template covers this:
  each affected Item Group (e.g. "Beverages", "Food") gets an Item Tax Template that overrides
  the base rate for that category. Hamilton's 4 current SKUs are all 13%-taxable; this is not
  needed today but will be needed in Phase 2 menu expansion.

**Implementation pattern at each new venue:**
1. Seed script creates the Sales Taxes Template for the venue's jurisdiction.
2. Template name is stored in `Hamilton Settings.default_sales_taxes_template` (new field to add
   before venue two ships; currently hardcoded as "Ontario HST 13%" in the Hamilton seed).
3. `submit_retail_sale` reads the template name from `Hamilton Settings` instead of a hardcoded
   string. This is a one-line change in `api.py`.
4. At the new venue, the seed sets `default_sales_taxes_template` to the venue-specific name.
5. Test: `test_retail_sales_invoice.py` gets a parameterized fixture test that verifies the
   submitted invoice carries the correct tax template for the current site's `anvil_tax_mode`.

**CAD nickel rounding does not apply to US venues:**
US venues use USD. `Currency USD.smallest_currency_fraction_value = 0.01` (one cent). The
`disable_rounded_total` logic in `submit_retail_sale` is already gated by `payment_method`; no
change is needed there. What does need to change: the nickel-rounding seed step
(`Currency CAD.smallest_currency_fraction_value = 0.05`) must be guarded by
`if anvil_currency == "CAD"` in the seed. Running the Hamilton seed on a USD venue would
incorrectly round USD invoices to $0.05.

---

## 5. Multi-Currency

### Current state

Hamilton runs CAD. `anvil_currency = CAD`. The `tip_pull_currency` field on Cash Drop reads
`CAD` for Hamilton.

The venue's currency affects:
- **Tip rounding rule** — CAD: round up to $0.05 (Canada's nickel rule). USD: round to $0.01.
  `tip_pull_phase2.md` documents the mechanics; the rounding rule must become a venue-config
  lookup, not a hardcoded Canadian nickel.
- **Refund rounding** — same: CAD nickels, USD pennies.
- **Bank deposit slip format** — currency symbol, decimal separator, deposit account.
- **Tax remittance schedule** — CRA (Canada) vs IRS/state (US); different cadences and forms.
- **POS Profile currency** — each venue's POS Profile must be configured with the correct
  Company (which carries the currency). Cross-currency posting would create incorrect GL entries.

### Implementation rule

`anvil_currency` is the single source of truth for the venue's operating currency. Any code that
formats a monetary amount, rounds a figure, generates a receipt, or creates a GL entry must read
`anvil_currency` from `Hamilton Settings`, not assume CAD.

**Where to audit before venue two ships:**

```
hamilton_erp/api.py              — submit_retail_sale, tip_pull rounding
hamilton_erp/lifecycle.py        — any monetary field initialization
hamilton_erp/doctype/cash_drop/  — tip_pull_currency field default
hamilton_erp/fixtures/           — seed scripts that touch Currency DocType
```

The audit is a grep for `"CAD"` and `0.05` as hardcoded strings in Python files. Any match that
is not inside an `if anvil_currency == "CAD"` guard is a bug waiting to fire on venue two.

---

## 6. Per-Venue Processor Selection

DEC-062, DEC-063, and DEC-064 establish the architecture. Summary:

- All ANVIL venues are **standard merchants**, not adult-classified (DEC-062). This is the
  baseline for all processor relationships.
- Each venue picks its own primary processor at rollout (DEC-063). There is no corporate-wide
  mandate. Hamilton: Fiserv (MID 1131224, already running). New US venues: Stripe Terminal is
  the current default recommendation per `docs/research/merchant_processor_comparison.md`, but
  is evaluated per-venue.
- Every venue must have both a primary AND a backup processor pre-approved, integrated-tested,
  and swap-ready in hours (DEC-064). The swap mechanism is a `site_config.json` flip + bench
  restart, never a code deploy.
- Hamilton's backup processor is **not yet selected** (open action item in
  `docs/decisions_log.md` DEC-064 open instances). Must be resolved before Hamilton go-live.

### The processor-abstraction layer (Phase 2 build)

The processor abstraction must support the same operations across primary and backup adapters:

| Operation | Required |
|---|---|
| charge | yes |
| refund | yes |
| void | yes |
| capture (pre-auth) | yes |
| settle (batch) | yes |

Each adapter implements this interface. The active adapter is determined by:

```python
processor = frappe.conf.get("anvil_primary_processor", "fiserv")
# On failover:
processor = frappe.conf.get("anvil_backup_processor", None)
```

Switching adapters is: `bench set-config anvil_primary_processor stripe_terminal` + bench
restart. No code change. This is the DEC-064 "config flip, not code change" requirement.

**SAQ-A validation requirement (from CLAUDE.md):** Before any card payments go live at any
venue, confirm the chosen processor supports a SAQ-A integration model (card data stays at the
terminal; Hamilton's network sees only last 4, brand, auth code, `merchant_transaction_id`).
Receipt printers must print last 4 only, never full PANs. Re-attest SAQ-A annually.

### R-008 watch points

R-008 (single-acquirer SPOF) is downgraded to MEDIUM for Hamilton's actual standard-merchant
classification. The watch triggers that escalate it back to HIGH:
- Fiserv re-classifies the MID to high-risk
- Chargeback ratio approaches the 0.65% Visa-monitored threshold (R-009)
- Fiserv changes terms on the MID

If any of these fires, the DEC-064 backup-processor architecture becomes an emergency
requirement, not a Phase 3 nice-to-have.

---

## 7. GH Room Tab Hardcode — Task 38 (Must Close Before Venue Two)

### The drift

`asset_board.js` line 84 hardcodes a Hamilton-specific asset tier as a named tab:

```javascript
{ id: "gh-room", label: __("GH Room"), filter: (a) =>
    a.asset_category === "Room" && a.asset_tier === "GH Room" },
```

This is a Hamilton-only asset tier. Philadelphia, DC, and Dallas may have different tier names
and different tab structures. A second venue that loads this asset board will either see an empty
"GH Room" tab (if it has no GH Room assets) or need a code change to add its own tier-specific
tab.

The same file also has a "VIP" tab hardcoded:

```javascript
{ id: "vip", label: __("VIP"), filter: (a) =>
    a.asset_category === "Room" && a.asset_tier === "VIP" },
```

### The fix

Tabs should be **data-driven from the venue's actual asset tiers**. The pattern:

1. `get_asset_board_data` API call returns the set of distinct `asset_tier` values present on
   the current site's Venue Assets.
2. The asset board builds tabs dynamically from that set, grouping by `asset_category` first
   (Locker vs Room), then by `asset_tier` within the Room category.
3. Hardcoded tier names ("GH Room", "VIP", "Double Deluxe", "Single Standard") are replaced by
   the API-returned tier values.
4. The `asset_tabs` array in `get tabs()` becomes a computed property from `this.asset_tiers`
   (returned by the API call) rather than a static literal.

**Why this must close before venue two:**
A second venue that has different tier names will silently show empty tabs or miss tiers
entirely. The fix is straightforward but touches the asset board's tab rendering and the API
payload — it requires the V10 canonical mockup review to confirm the new dynamic-tab behavior
matches spec, and a regression test confirming the tab set matches the database's distinct tier
values.

Task 38 is planned but not yet in Taskmaster. It must be entered as a task and sequenced
**before the first US venue rollout PR**.

---

## 8. Multi-Tablet Sync — DC's 3-Tablet Requirement

### Current design

Hamilton runs one tablet. The realtime broadcast in `lifecycle.py` uses
`frappe.publish_realtime("asset_board_refresh", {}, after_commit=True)` to push updates to any
connected client. With one tablet, this is sufficient: update happens, tablet refreshes.

### What DC requires

DC sets `anvil_tablet_count = 3`. Three operators run overlapping shifts. All three tablets must
show the same asset state within seconds of any state change.

**The good news:** the realtime broadcast architecture already covers this. Frappe's
`publish_realtime` broadcasts to all connected clients on the site. If all three tablets are
open on the asset board, all three receive the broadcast and re-fetch data.

**The untested risk:** concurrent state changes from multiple tablets. Consider:
- Tablet A marks Room 5 as Occupied.
- Tablet B marks Room 5 as Dirty simultaneously (operator made an error).
- Both fire the three-layer lock sequence (Redis → MariaDB FOR UPDATE → optimistic version).

The lock architecture (documented in `docs/coding_standards.md` §13) handles this case: one
tablet wins the lock, the other gets a TimestampMismatchError or Redis lock contention and
retries. The question is whether the current UI surfaces that contention gracefully (retry
message? Error alert?) rather than silently failing.

### What must be validated before DC ships

1. **Concurrent write stress test:** simulate two tablets submitting simultaneous state changes
   to the same asset. Verify: exactly one succeeds, the other surfaces a retryable error, the
   losing tablet re-fetches and shows the correct post-winning-write state.
2. **Broadcast latency under load:** with 3 tablets connected and a high check-in rate
   (DC Saturday night: ~50 check-ins/hour peak), verify all tablets refresh within 2 seconds.
3. **Operator UI for contention:** the current asset board has no UX for "your action was
   blocked by a concurrent write." DC's multi-operator environment will hit this regularly. A
   non-blocking toast ("Room 5 was updated by another operator — refreshed") is the minimum
   acceptable UX.
4. **Realtime channel scoping:** confirm `frappe.publish_realtime` broadcasts are scoped to the
   current site. On a multi-site Frappe Cloud setup, broadcasts should not cross venue boundaries.
   Verify this in the Frappe v16 docs before DC ships.

**Reference:** `docs/design/cash_reconciliation_phase3.md` §4 captures the architectural note
that the same realtime channel powers portable reconciliation on DC's three tablets:
`venue-{venue_id}-shift-events`. Confirm the channel naming is consistent between the cash-recon
design and the asset-board broadcast.

---

## 9. Per-Venue Role and Permission Scoping

### Current state

Hamilton has one venue. Every Venue Asset, Venue Session, Cash Drop, and Shift Record row
implicitly belongs to Hamilton because there is only one venue. The permission system uses
role-based DocPerm rows but no row-level data fences. An operator with "Hamilton Operator" role
can see every row in every DocType, and that is correct because every row is Hamilton's.

### What breaks at venue two

The day a second Frappe Cloud site shares the same codebase but different data, the issue is not
cross-site data leakage (each site has its own database — that's already solved). The issue is
within a single site if ANVIL Corp ever consolidates to a multi-company ERPNext setup.

More immediately relevant: **the Hamilton Operator role is defined in fixtures** and applied via
`bench --site {site} migrate`. When the Philadelphia site is created and the same fixtures are
applied, Philadelphia operators receive a role called "Hamilton Operator." That is confusing and
potentially misleading on audit.

### The fix

Before venue two ships, the role fixtures must be generalized:

| Current name | Replacement |
|---|---|
| `Hamilton Operator` | `ANVIL Front Desk` |
| `Hamilton Floor Manager` | `ANVIL Floor Manager` |
| `Hamilton Manager` | `ANVIL Manager` |
| `Hamilton Admin` | `ANVIL Admin` |

Role names are exported as fixtures. The rename requires:
1. Update DocType JSON fixtures for each role.
2. Update all DocPerm rows that reference the old role names.
3. Update `CLAUDE.md`, `docs/permissions_matrix.md`, and `docs/coding_standards.md` references.
4. Run `bench migrate` on `hamilton-unit-test.localhost` and verify all tests pass (role names
   appear in test setup).

**`permission_query_conditions` for row-level data fences:**

`docs/hooks_audit.md` notes that multi-venue requires per-venue data fences via
`permission_query_conditions` on Venue Session, Asset Status Log, and similar DocTypes. These
are not needed while each venue is its own site (separate databases). They become necessary only
if ANVIL Corp ever moves to a consolidated multi-company site. Defer until that architectural
decision is made. Flag as a risk to revisit at Phase 3 scale.

---

## 10. Sequenced Delivery Plan

The table below lists what blocks what. "Pre-DC" means must ship before the DC site goes live.
"Pre-Philadelphia" means before Philadelphia. Items not marked as blockers are recommended but
not hard blockers for the named venue.

### Pre-DC blockers (highest priority)

| Item | What it is | Why it blocks DC |
|---|---|---|
| **Task 38 — GH Room hardcode** | Data-drive asset board tabs from API | Second venue will have different tier names; hardcoded tabs break the board |
| **Member DocType** | New DocType with field masking from day one | DC has `anvil_membership_enabled=1`; no membership flow exists yet |
| **USD currency support** | Audit all CAD-hardcoded strings; make rounding rule a config lookup | DC runs USD; CAD nickel-rounding must not fire |
| **`anvil_tax_mode` → per-venue values** | Rename `US_NONE` to `US_DC`; create DC Sales Tax template | DC has 6%/10% rates; `US_NONE` placeholder is not deployable |
| **Multi-tablet stress test** | Concurrent write test + broadcast latency test | DC has 3 tablets; untested concurrent-write path |
| **Manager override service** | Shared `override.request()` from `manager_override_phase2.md` | DC opens with multi-operator overlapping shifts; solo-operator self-approval is no longer safe |
| **Processor abstraction layer** | Primary + backup adapter interface (DEC-064) | DC takes card payments; no processor abstraction exists today |
| **Hamilton backup processor** | Select + pre-approve + test a backup for Hamilton (Helcim TBD) | DEC-064 requires backup before card payments ship at any venue |
| **Role rename** | ANVIL Front Desk / Floor Manager / Manager / Admin | Hamilton-named roles on a DC site are a confusing audit artifact |
| **R-007 field masking** | `permlevel=1` on 8 PII fields on Venue Session | Pre-go-live blocker for any second venue; Philadelphia PII fields must be masked |

### Pre-Philadelphia additions

| Item | What it is | Why it matters |
|---|---|---|
| **PA tax templates** | Pennsylvania Sales Tax template (6% base + 8% prepared food Item Tax Template) | Philadelphia's tax structure requires two-rate template + item-level overrides |
| **Multi-warehouse stock** | Venue-specific warehouse for each venue's SKU inventory | Philadelphia may carry different SKUs; stock must not cross-contaminate |
| **Required paperwork checklist** | Per-venue reconciliation checklist on Reconciliation Profile | Philadelphia adds rental waiver acknowledgments to the manager checklist |
| **Processor selection** | Philadelphia primary + backup processor chosen and tested | Stripe Terminal recommended; evaluate at rollout per DEC-063 |

### Pre-Dallas additions

| Item | What it is | Why it matters |
|---|---|---|
| **TX tax template** | Texas Sales Tax (8.25% combined state+local) | Dallas-specific; verify local rate at rollout |
| **Processor selection** | Dallas primary + backup | Evaluate at rollout; do not presume Philadelphia's processor |

### Not yet sequenced (needs Chris's call)

- **Consolidated ANVIL Corp P&L reporting** — cross-site reporting requires an API aggregation
  layer or a separate reporting site. Not needed until venue two ships. Architecture TBD.
- **`permission_query_conditions` row-level fences** — only needed if ANVIL ever consolidates
  to a single multi-company site. Defer until that architectural decision is made.
- **Playwright visual regression** — `docs/inbox.md` entry flags this for installation "after
  Task 25 ships and before starting DC/Crew Club multi-venue refactor." Recommended; not a
  hard blocker.

---

## 11. Open Questions for Chris

These require a decision before Phase 2 implementation begins. None block Phase 1 / Hamilton
go-live, but all block the first multi-venue rollout.

**Q1. Hamilton backup processor — what is it?**
DEC-064 requires a pre-approved, integration-tested backup. Helcim was the prior suggestion;
`docs/research/hamilton_backup_processor_evaluation.md` found Helcim as recommended runner-up.
Chris must confirm whether to proceed with Helcim or evaluate another option (Moneris was
flagged as the "if Helcim declines" fallback). This unblocks the DEC-064 open instance and is a
pre-go-live item for Hamilton card payments.

**Q2. DC or Philadelphia first?**
This plan recommends DC first (membership + multi-tablet are the deepest requirements; validating
them before simpler venues is lower risk). If ANVIL Corp's business timeline has Philadelphia
opening sooner, the sequence flips. Philadelphia's blocker list is shorter (no membership DocType,
no multi-tablet sync), making it a viable "first US venue" if DC's timeline slips.

**Q3. Membership tier structure for DC**
The Member DocType needs a `Membership Tier` linked DocType defining price, duration, and access
rules. Chris must specify: what tiers DC offers (monthly, 3-month, annual?), what the price
points are, whether any tier grants differential access (e.g. locker-only vs full access), and
whether unused days are refundable at cancellation. These are business decisions; the DocType
schema can be scaffolded but the tier definitions must come from Chris.

**Q4. Consolidated ANVIL Corp reporting**
When two venues are running, Chris will want a single-view monthly P&L across venues. Options:
(a) manual export + spreadsheet, (b) a read-only aggregation API that queries both sites, (c)
a separate ERPNext "ANVIL Corp HQ" site used for consolidation only. Each option has different
complexity and data-freshness tradeoffs. This does not block venue two but should be designed
before venue three.

**Q5. Exact MCC code on Fiserv MID 1131224**
DEC-062 deferred MCC confirmation to a Fiserv call. The classification decision stands regardless
of which standard-tier MCC the MID uses, but the exact code matters for: (a) Stripe Terminal
onboarding at US venues (Stripe's TOS review process asks for MCC), and (b) choosing the correct
ERPNext Item Group for tax categorization. Chris should confirm the MCC with Fiserv before the
first US venue's processor selection.

**Q6. Role rename scope and timing**
The "Hamilton Operator → ANVIL Front Desk" rename touches fixtures, permissions, tests, and
docs. It is safest to do as a dedicated PR with zero other changes. Chris should confirm whether
to ship it as a standalone Phase 1 cleanup PR before the DC rollout begins, or to bundle it into
the DC rollout setup PR. Bundling saves one PR but makes the rollout PR larger and harder to
review.

---

## Appendix — Feature Flag Dependency Matrix

The table below shows which Phase 2 features depend on which `anvil_*` flag being non-default.
Any feature marked for a venue must have its flag's reading code audited for correctness before
that venue ships.

| Phase 2 Feature | `anvil_membership_enabled` | `anvil_currency` | `anvil_tax_mode` | `anvil_tablet_count` |
|---|---|---|---|---|
| Member signup / check-in | ✓ (must be 1) | — | — | — |
| Membership renewal / cancel | ✓ (must be 1) | ✓ (refund rounding) | — | — |
| US tax template selection | — | — | ✓ (US_PA / US_DC / US_TX) | — |
| CAD nickel rounding guard | — | ✓ (must be CAD) | — | — |
| Tip pull rounding rule | — | ✓ (CAD vs USD) | — | — |
| Multi-tablet concurrent sync | — | — | — | ✓ (>1) |
| Manager override activation | — | — | — | ✓ (>1) |
| Processor abstraction layer | — | ✓ (currency in receipts) | — | — |
| Portable reconciliation UI | — | — | — | ✓ (>1) |
| Required paperwork checklist | — | — | ✓ (US_PA adds rental waivers) | — |

---

*When this doc and the source files disagree, the source files win.*
*Add an Amendment heading below with the date and change summary if this plan changes.*
