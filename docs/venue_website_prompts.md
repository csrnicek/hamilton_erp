# Venue Website Design Prompts
**For:** Hamilton ERP venue websites (Club Hamilton, Club Philadelphia, Club Dallas, ANVIL Toronto)
**Stack:** WordPress + integration with Hamilton ERP (Frappe/ERPNext v16 API)
**Saved:** 2026-04-10

These prompts are designed to be used in sequence. Start with Prompt 1 for architecture,
then work through as needed. Each prompt builds on the previous output.

---

## PROMPT 1: The Architecture Strategist

```
You are a Principal Architect at Vercel. Build a [WEBSITE TYPE] website.

Requirements:
- Target: [AUDIENCE]
- Features: [LIST 3-5]
- Tech: [RESPONSIVE/SEO/PERFORMANCE]
- Platform: WordPress
- Backend integration: Frappe/ERPNext v16 REST API at [SITE_URL]/api/

Deliver:
1. Site map (page hierarchy)
2. User flows (3 journeys)
3. Data models (if dynamic)
4. API requirements — specifically which Frappe/ERPNext endpoints are needed
5. Component inventory (30+ items)
6. Page templates (wireframes)
7. Tech stack recommendation (WordPress theme, plugins, API integration approach)
8. Performance budgets
9. SEO structure
```

**For Hamilton ERP venues, replace:**
- [WEBSITE TYPE] → men's bathhouse / wellness club
- [AUDIENCE] → gay men aged 25-55 in [city]
- Features → online membership signup, event calendar, pricing/admission info, location/hours, photo gallery
- [SITE_URL] → hamilton-erp.v.frappe.cloud (or venue-specific URL)

---

## PROMPT 2: The Design System Generator

```
You are Apple's Design Director. Create a design system for [BRAND].

Brand attributes: [MINIMAL/BOLD/LUXURY/PLAYFUL]
Platform: WordPress (Elementor or Gutenberg blocks)

Generate:
1. Color palette (primary, secondary, semantic, dark mode)
2. Typography scale (9 levels) — Google Fonts or system fonts
3. Spacing system (8px grid)
4. Component specs (buttons, cards, forms, navigation)
5. WordPress-specific implementation notes (CSS variables, theme.json)
6. Mobile-first breakpoints
```

**For Club Hamilton:**
- Brand: masculine, mature, discreet, premium
- Attributes: MINIMAL + LUXURY
- Primary color direction: dark, muted, sophisticated (not rainbow/pride-flag obvious)

---

## PROMPT 3: The Content Architect

```
You are Ogilvy's Conversion Copywriter. Write all copy for a [WEBSITE TYPE] in [CITY].

Voice: [PROFESSIONAL/CASUAL/BOLD]
Target: [AUDIENCE]
Goal: [CONVERSION/AWARENESS/RETENTION]
Tone: discreet, welcoming, non-explicit (this is a legitimate licensed venue)

Per page:
1. Hero (6-word headline, 15-word subhead, CTA)
2. About/What We Offer (3 feature blocks)
3. Admission & Pricing (tiers, membership options)
4. Hours & Location
5. FAQ (8 Q&As covering: what to bring, what to expect, rules, payment)
6. Footer

Use emotional triggers (belonging, safety, discretion). Specify H1/H2/body tags.
Avoid explicit language — this must be suitable for public web indexing.
```

---

## PROMPT 4: The Component Logic Builder

```
You are a Frontend Architect. Design WordPress component logic for a venue website
that integrates with a Frappe/ERPNext v16 REST API.

Components needed:
1. Membership signup form (validation, progress, Stripe payment, creates ERPNext Customer)
2. Admission pricing calculator (room tiers, dynamic pricing by day/time)
3. Hours display (pulls from ERPNext settings, shows today's hours prominently)
4. Event calendar (syncs with ERPNext events if applicable)
5. Contact/inquiry form (submits to ERPNext Lead)

Per component:
- State machine (text diagram)
- Data flow (WordPress → Frappe API → response)
- Frappe API endpoint used
- Error handling
- Loading/empty states
- Edge cases (API down, sold out, etc.)

Output as WordPress block or Elementor widget specification.
```

---

## PROMPT 5: The Responsive Behavior Strategist

```
You are a Responsive Design Specialist. Plan breakpoints for a venue website on WordPress.

Breakpoints:
- Mobile: 375px (primary — most visitors on phones)
- Tablet: 768px
- Desktop: 1440px

For each page section, define:
1. Layout transformation (grid → stack, sidebar → drawer)
2. Typography scaling (font sizes at each breakpoint)
3. Image behavior (crop, scale, hide, swap)
4. Navigation adaptation (hamburger menu on mobile)
5. Spacing adjustments (padding, margin, gap)
6. Content prioritization (what hides on mobile, what comes first)

WordPress implementation: specify whether to use theme.json, custom CSS, or Elementor responsive settings.
```

---

## PROMPT 6: The WordPress + Frappe API Integration Planner

```
You are a Full-Stack Architect. Design the WordPress ↔ Frappe/ERPNext v16 integration
for a venue website.

Frappe site: [FRAPPE_SITE_URL]
WordPress site: [WP_SITE_URL]

Integration requirements:
1. Authentication (API key/secret for server-side calls, no user OAuth needed)
2. Data flowing FROM Frappe TO WordPress:
   - Pricing/admission tiers (display on site)
   - Current operating hours
   - Membership types and prices
3. Data flowing FROM WordPress TO Frappe:
   - New membership signups → create Customer + Membership in ERPNext
   - Contact form submissions → create Lead in ERPNext
   - Payment confirmations from Stripe → create Sales Invoice in ERPNext

Deliver:
1. Which Frappe REST API endpoints to use
2. WordPress plugin recommendation (WP REST API, custom plugin, or ACF + webhook)
3. Authentication approach (API key in wp-config.php)
4. Error handling strategy (what happens when Frappe is down)
5. Caching strategy (don't hammer the API on every page load)
6. Security considerations (don't expose API keys client-side)
```

---

## PROMPT 7: The QA & Launch Checklist

```
You are a QA Engineer. Review this venue website before launch.

Website type: Men's bathhouse / wellness club on WordPress
Integration: Frappe/ERPNext v16 API

Checklist:
□ Performance (Core Web Vitals — LCP < 2.5s, CLS < 0.1, FID < 100ms)
□ Accessibility (WCAG 2.2 AA — important for legal compliance)
□ SEO (meta tags, structured data, local business schema, Google Business Profile alignment)
□ Security (HTTPS, no API keys exposed, contact form spam protection)
□ Browser compatibility (Chrome, Safari, Firefox — mobile Safari is critical)
□ Mobile optimization (touch targets 44px+, no horizontal scroll)
□ Analytics (Google Analytics 4 events: page views, form submits, pricing page views)
□ Frappe API integration (fallbacks if API is unreachable)
□ Privacy/legal (cookie consent, privacy policy, age verification if required)
□ Local SEO (NAP consistency, Google Business Profile match, schema markup)

Flag any issues specific to adult venue / age-restricted content policies.
```

---

## Usage notes

**Sequence for a new venue website:**
1. Run Prompt 1 → get architecture and site map
2. Run Prompt 2 → get design system
3. Run Prompt 3 → get all copy
4. Run Prompt 6 → plan the Frappe API integration
5. Build in WordPress
6. Run Prompt 7 → QA before launch

**Venues to build:**
- Club Hamilton (Hamilton, ON) — hamiltonclub.ca or similar
- Club Philadelphia (Philadelphia, PA)
- Club Dallas (Dallas, TX)
- ANVIL Toronto (Toronto, ON)
- The Crew Club (Washington, DC) — 1321 14th Street NW

**WordPress hosting note:**
WP Engine and Kinsta restrict adult content. Use a host that permits it.
Previously researched: SiteGround, Hostinger, or a VPS (DigitalOcean/Linode).
