# V9 Integration Plan — Asset Board

**Status:** READY FOR IMPLEMENTATION. Synthesis of three V8 reviews (Claude, Grok, Reviewer 3). All four open questions answered by Chris on 2026-04-24. Ready for Claude Code handoff.

**Created:** 2026-04-24
**Supersedes:** nothing yet — V8 remains the source-of-truth mockup (`docs/design/asset_board_mockup_v7.html` path, currently `asset_board_FINAL_v2.html`) until V9 is built.
**Sibling document:** `decisions_log.md` — V8 locked decisions. This plan does NOT reverse any locked decision. Where a V9 change modifies a decision, it's called out explicitly.

---

## 1. How to read this document

This is the brief Claude Code will work from to build V9. It does three things:

1. Lists every V9 change ranked by confidence × impact.
2. Documents what was rejected from the reviews and why, so future sessions don't re-open the question.
3. Records the four decisions Chris locked on 2026-04-24 to close out the planning phase.

Once V9 is built and passes tests, this document's entries get folded into `decisions_log.md` as new locked decisions, and this file is archived or deleted.

---

## 2. Review provenance

- **Claude review** (`v8_review_chatgpt.md`, labelled Claude Opus 4.7 internally). Ran the HTML live in headless Chromium at deviceScaleFactor 2. Took pixel measurements. Captured screenshots of every state.
- **Grok review** (`Grok_v8_review.md`). Reviewed PDF screenshots only — Grok's own self-doubt #1 admits he could not interactively click the HTML. Strong on spec compliance, weak on mechanical bugs.
- **Reviewer 3 review** (`Gemini_V8_Review.md`, but H1 header says "ChatGPT"). Provenance ambiguous. Did not follow the template — delivered Strengths/Weaknesses/Interactive Observations/Rationale Engagement/Final Recommendation instead of the requested sections. No self-doubt, no per-decision pass/concern/fail. Reviewer 3's "interactive testing" section reads more like assertion than observation. **Action item: Chris to confirm provenance before this review gets logged as official 3-AI rotation input.**

All three reviewers delivered `SHIP WITH MINOR REVISIONS`. No reviewer called for redesign.

---

## 3. Agreement map

### Flagged by all three reviewers
- Expanded-overlay button label wrap (already acknowledged in `decisions_log.md` Part 11.1).

### Flagged by two reviewers
- Density pressure in the expanded overlay / tiles. Each reviewer picked a different specific target (Grok: 10px time text; Claude: 8.5/7.5px buttons; Reviewer 3: wrap destroys shape-recognition). Different diagnoses of the same underlying condition.

### Flagged by one reviewer — measured/mechanical
- Scroll-while-expanded overlay drift (Claude)
- Source tile pulsing under overlay (Claude)
- `Extend StayPhase 2` missing-space render bug (Claude)
- Set OOS vs Return to Service friction asymmetry (Claude)
- Live-tick cadence unspecified (Claude)
- "1.5×" claim doesn't match measured 1.37× (Claude)

These are measured facts, not opinions. 1-of-3 reflects only that the other two reviewers didn't run the live mockup — not that the bugs aren't real.

### Flagged by one reviewer — judgement calls
- 10px time-status text too small (Grok)
- "NEEDS CLEANING" / "Dirty" terminology drift (Grok)
- OOS day counter `11d` ambiguous (Grok)
- OOS "Other" textarea needs Clear/X button (Reviewer 3)
- Footer per-tab counts redundant with section headers (Reviewer 3)
- Overtime border should be thicker than Occupied for high-glare (Reviewer 3)

---

## 4. V9 change list

### 4.1 Must fix before building production code

**M1. Shorten wrapping button labels.**
- "Set Out of Service" → "Set OOS"
- "Discovery on Rounds" → "Rounds"
- "Extend Stay" → hidden entirely (see M2)
Rationale: 3-of-3 reviewer agreement, pre-acknowledged in `decisions_log.md` Part 11.1. "Set OOS" wording confirmed by Chris (D2 below).
Conflicts: none. Part 4.6 locks the *concept* of Key Return vs Discovery on Rounds, not the wording.

**M2. Hide Phase-2 Extend Stay button from Occupied overlay.**
Rationale: Renders as `Extend StayPhase 2` with no space (template bug), adds vertical height to overlay for no current functionality, trains staff that buttons "don't work yet". Confirmed by Chris (D3 below).
Side effect: eliminates the render bug automatically.
Conflicts: none. Part 4.3 lists Extend Stay as a Phase-2 button but doesn't require Phase-1 visibility.

**M3. Increase time-status text from 10px to 12–13px bold.**
Rationale: Grok's critical #1. On re-read, Claude concurs — 10px next to 17px asset codes is small for the stated 50+ target user. 12-13px keeps the hierarchy (smaller than asset code) while improving legibility. Must not overflow the 95×58 tile; implementation must re-verify vertical balance across normal/countdown/overtime states.
Conflicts: Part 8.3 mentions "Time text: 10px bold" but doesn't lock it. Update Part 8.3 in `decisions_log.md` when V9 ships.

**M4. Fix scroll-while-expanded overlay drift.**
Rationale: Claude measured the bug. Overlay is positioned once via `getBoundingClientRect()` on tile click, never re-positioned on scroll. If `.board` scrolls with overlay open, overlay detaches visually from source tile. Implementation: close the overlay on `.board` scroll event (2-line patch). Alternative (reposition on scroll) is acceptable but more code.
Conflicts: none. Part 2.4 says "Tap outside to collapse" — closing on scroll extends that pattern.

**M5. Add `animation: none` to `.tile.is-source`.**
Rationale: Claude measured. Source tiles with `.overtime` class continue to run `pulse-strong` keyframe animation at 0.3 opacity under the expanded overlay. Distracting. Wastes GPU.
Conflicts: none.

### 4.2 Should fix in V9

**S1. Standardise Dirty-state terminology to "DIRTY" across mockup, footer, and `decisions_log.md`.**
Rationale: Grok significant #1 + Claude minor. Mockup section header currently says "NEEDS CLEANING", footer label says "Dirty", `decisions_log.md` uses "Dirty" in Part 4 examples. **Chris's decision (2026-04-24):** standardise on "DIRTY" — visual parity with other single-concept headers (AVAILABLE / DIRTY / OCCUPIED / OUT OF SERVICE), matches existing footer language, matches existing `decisions_log.md` Part 4 language.
Implementation: change mockup section header text from "Needs Cleaning" to "Dirty" (will render as "DIRTY" via existing CSS `text-transform: uppercase`). No footer change needed (already "Dirty"). Update any "Needs Cleaning" references in `decisions_log.md` to "Dirty".
Conflicts: none — section header wording was never locked.

**S2. Add audit-preview line to Set OOS modal.**
Rationale: Claude significant. The Return to Service modal shows "By confirming, this action will be recorded as: Returned to service by A. NOLAN at 23:43". The Set OOS modal has no equivalent. Mirror the accountability pattern without adding a new tap — just an inline preview line above the Confirm button.
Conflicts: **Does not** conflict with Part 4.5 (which rejects an additional *dialog*). A preview line is inline, not a dialog.

**S3. Raise expanded-overlay button sizes.**
Rationale: Claude + Reviewer 3 shape-recognition framing. Primary buttons: 11–12px font, ~28–30px height. Secondary buttons: match primary or one step smaller. Test AFTER M1 label shortening — shortening may reduce need to widen overlay.
Conflicts: none. Part 8.3 didn't size buttons.

**S4. Add live-tick interval for time-status recomputation.**
Rationale: Claude significant. Mockup `elapsedMin` is static. Production needs a refresh cadence so tiles transition to overtime smoothly rather than jumping on the next user interaction. Suggested: 15s (visually imperceptible, cheap on Frappe).
Implementation: `setInterval(render, 15000)` plus a guard so modals/expanded-overlay state isn't destroyed on tick. Document cadence in `decisions_log.md` Part 3.
Conflicts: none — Part 3 doesn't specify cadence.

**S5. Correct `decisions_log.md` Part 2.4.**
Current text: "grows to 1.5× scale with edge-aware positioning". Measured reality: overlay uses `min-width: 130px` on a 95px source (~1.37×) and grows vertically to fit content (up to 3.26× source height for Vacate-expanded).
Replacement wording: "Tap any tile → floats a separate overlay anchored near the source tile with `min-width: 130px` and content-driven height. Source tile stays at normal size underneath (dimmed). Edge-aware positioning clamps overlay to viewport."
Conflicts: this IS a decisions_log correction — flag it in the V9 commit message.

**S6. Add Clear/X button inside OOS "Other" note textarea.**
Rationale: Reviewer 3. Touch keyboards are error-prone; a quick reset is cheap.
Conflicts: none.

### 4.3 Decisions locked by Chris on 2026-04-24

**D1. Footer KEEPS per-tab counts (not swapped to facility-wide metric).**
- Reviewer 3 argued: footer counts duplicate section headers; suggested replacing with Total Occupancy % or similar facility-wide metric for manager-level awareness.
- Decision rationale: Front-desk staff need *this tab right now* — "how many rooms do I have available" — not facility-wide occupancy. That's a manager metric served by other reports. Footer real estate faces the person doing the work; should answer the question they'll actually ask. The "duplicates section headers" critique has a real counter: on Lockers tab with 25 Available tiles, the AVAILABLE header and tiles can occupy most of the screen, pushing OCCUPIED and OOS counts down. Footer gives all four counts in one place at all times, glanceable from across the desk.
- Grok: graded Part 6 PASS. No opinion on redesign.
- Claude: re-read changed position back to keep — Reviewer 3 is solving a manager's problem, not an attendant's.
- **Outcome:** no footer change in V9. R5 below now formally rejects this proposal.

**D2. Button wording: "Set OOS" (shortened).**
- Decision rationale: Staff already say "OOS" in conversation. The term is already used in the Watch tab, the section header ("OUT OF SERVICE"), the day counter context, and `decisions_log.md`. Shortening fixes the wrap problem in M1 without widening the overlay. Alternatives ("Take Offline") drift terminology away from established hospitality language.
- **Outcome:** M1 implementation uses "Set OOS" as the button label.

**D3. Phase-2 Extend Stay button HIDDEN ENTIRELY in V9.**
- Decision rationale: Disabled "Phase 2" buttons train staff that some buttons don't work, eroding interface trust. Wastes vertical pixels in cramped overlay. Eliminates the `Extend StayPhase 2` render bug as a side effect. When Phase 2 ships, the button will be added fresh as a working feature with no negative training history.
- Plain-text placeholder option ("Extend Stay — coming in Phase 2") was considered and rejected because it consumes more vertical pixels than the disabled button does.
- **Outcome:** M2 implementation removes the Extend Stay button entirely from the Occupied expanded tile. To be reintroduced when Phase 2 ships.

### 4.4 Rejected from reviews — do not adopt

**R1. Thicken overtime border from 3px to 4px for high-glare distinction (Reviewer 3 only).**
Reason: Grok graded Part 3 PASS, explicitly praising pulse visibility. Claude concurs. 1-of-3 against 2-of-3. Hold unless UAT contradicts.

**R2. Change `11d` to "11 days" or "11d ago" (Grok only).**
Reason: Context disambiguates — `11d` sits on a purple OOS-styled tile with an L0xx code. No real confusion risk. Change would consume cramped corner-badge space.

**R3. Scale expansion 1.5× → 1.6× as alternative to shortening labels (Reviewer 3 only).**
Reason: Mechanically wrong. Overlay is content-sized (min-width 130px + flex content height), not transform-scaled. A 1.6× number doesn't apply to the current implementation. Reviewer 3 didn't run the live mockup.

**R4. Dirty amber vs countdown amber visual collision concern (Claude only, last round).**
Reason: On re-inspection via screenshot, the full-amber Dirty tile and the red-tile-with-amber-text Countdown are sufficiently distinct. Monitor in UAT.

**R5. Replace footer per-tab counts with facility-wide metric (Reviewer 3 only).**
Reason: Decision D1 above. Footer faces the attendant; per-tab counts answer the attendant's actual question. Facility-wide metrics are a manager concern and live in other reports.

### 4.5 Deferred — out of V9 scope

- Move `COUNTDOWN_THRESHOLD_MIN` to `venueConfig` (already in Part 11.2, defer to multi-venue refactor).
- Long guest name stress test (add fixture during Phase 2 backend wiring).
- Colour-blind secondary cues (Phase 2 accessibility roadmap).
- Portrait orientation handling (intentionally landscape-dock-mounted).
- ESC keyboard handling for modals (minor, batch with other keyboard-shortcut work in Phase 2).

---

## 5. Implementation sequence for Claude Code

Recommended order when Claude Code builds V9:

1. Start from V8 (`asset_board_FINAL_v2.html`) on branch `feature/asset-board-ui-rebuild` (PR #8).
2. Apply M1–M2 (label shortening + Extend Stay hide). Re-run the 59-test suite. All should still pass.
3. Apply M3 (time-text size). Re-measure tile layout. Re-run tests.
4. Apply M4 (scroll close). Add new test: open overlay, scroll `.board`, verify overlay closed.
5. Apply M5 (is-source animation none). Visual check only.
6. Apply S1–S6 in any order. Each adds targeted tests where applicable.
7. Update `decisions_log.md` Part 2.4 (S5) and Part 8.3 (M3 size) and Part 3 (S4 cadence).
8. Visual inspection by Chris before PR merge.
9. On merge: fold this document's contents into `decisions_log.md` as new locked decisions, archive or delete this plan.

---

## 6. Decisions locked by Chris on 2026-04-24

All four open questions answered. Plan is ready for Claude Code handoff.

- **Q1 → DIRTY** (not "Needs Cleaning"). Visual parity with other single-concept headers; matches existing footer and `decisions_log.md` Part 4 language. Implements as S1.
- **Q2 → Keep per-tab counts** in footer (no facility-wide metric swap). Footer faces the attendant doing the work; their question is "how many available right now," not "what's facility occupancy." Captured as R5 (rejected proposal).
- **Q3 → "Set OOS"** (shortened button label). Matches conversational staff usage; fixes wrap problem in M1 without widening overlay. Implements as M1.
- **Q4 → Hide Extend Stay entirely** in V9. Reintroduce as a live working button when Phase 2 ships. Implements as M2.
