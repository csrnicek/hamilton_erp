# Hamilton ERP — Review Prompts for Each AI

Use these prompts when submitting to each AI. Paste the full review package document FIRST, then paste the prompt for that AI.

---

## PROMPT FOR CHATGPT

You are a senior ERPNext and Frappe Framework developer with deep expertise in ERPNext v16.

I am building a custom Frappe app called `hamilton_erp` for a bathhouse venue in Ontario, Canada. The document above is our complete architecture plan, all decisions made so far, custom DocType schemas, pricing rules, and a review checklist.

Please review the entire document carefully and answer every question in the Review Checklist (Parts A through G, questions 1–22). Be direct and specific. Flag anything that is wrong, missing, risky, or could cause problems when we start building. Do not just validate what we have — look for gaps, edge cases, and things we haven't thought of.

Focus especially on:
- Whether our ERPNext v16 approach is correct
- Whether the DocType schemas are complete
- Whether the pricing rules are implementable in standard ERPNext
- Whether anything would need to be rewritten later when we add membership features

---

## PROMPT FOR GEMINI

You are an expert in ERPNext v16, Frappe Framework, and custom app development. You have built production ERPNext systems for hospitality and retail venues.

I am planning a custom Frappe app for a bathhouse venue. The document above contains the full architecture, all decisions, DocType schemas, pricing configuration, and a review checklist.

Please answer all 22 questions in the Review Checklist section at the bottom of the document. Be critical and thorough — I need to find any problems BEFORE we start writing code. Pay particular attention to:
- ERPNext v16 specific issues or breaking changes that affect our approach
- DocType schema completeness — are we missing any fields?
- Whether the blind cash control system is achievable purely through permissions
- Forward compatibility — will our schema support a future membership-enabled venue without painful migration?

---

## PROMPT FOR GROK

You are a senior Frappe/ERPNext developer. You have previously reviewed earlier versions of this project specification and provided feedback.

The document above is the current complete architecture plan for the `hamilton_erp` custom Frappe app. It includes all 16 architectural decisions, 7 custom DocType schemas, pricing rules, permissions model, and a full review checklist.

Please do a rigorous technical review and answer all 22 questions in the Review Checklist. This time focus particularly on:
- Anything that was flagged in previous reviews that may not have been addressed
- ERPNext v16 compatibility issues
- The non-stacking pricing rule implementation — is this achievable in standard ERPNext?
- The blind cash drop system — any security gaps?
- The three-way reconciliation logic — any mathematical or logical edge cases?
- What is the single most important thing we must get right before writing the first line of code?

