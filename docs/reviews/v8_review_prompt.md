# V8 Asset Board Review — Reviewer Brief

## Context

You are reviewing the V8 design of an asset-management board for Club Hamilton, a hospitality venue. The board runs on a tablet at the front desk, used by attendants (often aged 50+) to manage rooms and lockers in real time. The asset board shows the live state of every room/locker (Available, Occupied, Dirty, Out of Service) and lets staff perform state transitions through tap-to-expand tiles.

Two artifacts are attached:

1. **`asset_board_FINAL_v2.html`** — the interactive mockup. Open it in a browser. Click tiles to expand. Switch tabs. Try the OOS modal. Try Vacate. Try Return to Service. Open the dropdown for OOS reasons. Look at all three time-status states (normal, countdown, overtime).

2. **`decisions_log.md`** — the design rationale. Twelve-part document explaining every design decision, alternatives that were rejected, and the operational reasoning. **Read this in full before reviewing.** Many decisions that look "wrong" at first glance have a documented reason — your job is to engage with the reasoning, not to ignore it.

The mockup is the SOURCE OF TRUTH for visual + interactive design. Production code will be built to match it exactly.

## Your task

Produce a critical review of the V8 design as a **single Markdown file** with the structure below. Do not abbreviate. Do not be polite for the sake of politeness — flag real problems honestly. Equally, do not invent problems just to seem rigorous.

## Output format

Output a single .md file with these sections, in this order:

```markdown
# V8 Asset Board Review — [Reviewer Name: ChatGPT / Grok / Claude-Fresh]

## Overall verdict

One paragraph. Is this design ready to build, ready with revisions, or fundamentally flawed? Be direct.

## Strengths (what V8 gets right)

Bullet points. Specific. Each one references a concrete decision or design choice.

## Critical issues (must fix before building)

Numbered list. Each item:
- **What's wrong** — concrete description
- **Why it matters** — operational/UX consequence
- **Suggested fix** — actionable change
- **Decision conflict** — does this contradict a locked decision in decisions_log.md? If yes, name the part (e.g., "Conflicts with Part 3.2"). If no, say "No conflict."

## Significant concerns (should consider)

Same format as Critical issues, but lower stakes. These are things that would make the design notably better but aren't blockers.

## Minor observations (nice-to-have)

Brief bullet points only.

## Specific design areas — pass/concern/fail

For each of these, give a one-word grade (PASS / CONCERN / FAIL) and one sentence of reasoning:

- Tab structure and visibility (Part 1 of decisions_log)
- Tile visual design (Part 2)
- Time-status states — normal/countdown/overtime (Part 3)
- State machine — action buttons per state (Part 4)
- OOS workflow — set + return + audit (Part 5)
- Header and footer (Part 6)
- Tier-name-agnostic UI (Part 7)
- iPad viewport sizing for staff 50+ (Part 8)
- Rejected alternatives — were the right things rejected? (Part 10)

## Reviewer self-doubt

Three things you might be wrong about. Genuine epistemic humility — what assumptions in your review might not hold up in real operations?

## Final recommendation

One of: SHIP AS-IS / SHIP WITH MINOR REVISIONS / SHIP WITH MAJOR REVISIONS / DO NOT SHIP — REDESIGN
```

## Critical instructions

1. **Engage with the rationale, not just the artifact.** If a decision looks wrong, check decisions_log.md first. The rejected alternatives table (Part 10) explains why many "obvious" choices were turned down. If you still disagree after reading the rationale, say so — but acknowledge what the design team considered.

2. **Be specific.** "The colors look bad" is not useful. "The amber border on the Dirty status competes visually with the amber countdown text on Occupied tiles, creating ambiguity for staff scanning quickly" is useful.

3. **Test the actual mockup.** Don't just read the HTML — open it, click around, expand tiles, switch tabs, simulate the modal flows. Many issues only surface in interaction.

4. **Consider the user.** Front desk attendants aged 50+, working a busy shift, need fast unambiguous signals. A design that prioritizes elegance over readability is a fail in this context.

5. **Output ONE .md file.** Do not split your review across multiple files or paste it inline as a chat reply. The user needs a single artifact to upload back for cross-comparison.

## Output filename

Save your review as `v8_review_[your_name].md` — for example:
- `v8_review_chatgpt.md`
- `v8_review_grok.md`
- `v8_review_claude_fresh.md`

That filename pattern matters — the user will be uploading all three together for side-by-side analysis.
