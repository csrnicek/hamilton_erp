# Hamilton ERP — Complete Testing Guide
**Updated:** 2026-04-10 after Tasks 1-8 complete

This document tells you WHAT to run, WHEN to run it, and WHY.
The goal is code as close to perfect as possible.

---

## The 4 levels of testing

### Level 1 — /run-tests (run after EVERY task)
The core test suite. Always run this. Always run the full suite including expert tests.

**Command:**
```
cd ~/frappe-bench-hamilton && source env/bin/activate && ~/.pyenv/versions/3.11.9/bin/bench --site hamilton-test.localhost run-tests --app hamilton_erp --module hamilton_erp.test_lifecycle hamilton_erp.test_locks hamilton_erp.hamilton_erp.doctype.venue_asset.test_venue_asset hamilton_erp.test_additional_expert
```

**What it runs:**
- test_lifecycle.py — state machine + all 5 lifecycle methods (25 tests)
- test_locks.py — three-layer lock correctness (3 tests)
- test_venue_asset.py — validator rules (17 tests)
- test_additional_expert.py — expert edge cases (52 tests)

**When:** After every single task, no exceptions.

**Expected failures in test_additional_expert:** Some tests require
Tasks 9-11 to pass. Always report the full count so we can track progress.

---

### Level 2 — /coverage (run after Tasks 9 and 11)
Shows exactly which lines of code are never executed by any test.
Any uncovered line is a potential hidden bug.

**Install (one time):**
```
pip install pytest-cov --break-system-packages
```

**Command:**
```
cd ~/frappe-bench-hamilton && source env/bin/activate && python -m coverage run -m pytest && python -m coverage report --include="*/hamilton_erp/lifecycle.py,*/hamilton_erp/locks.py" --show-missing
```

**What to look for:** Any line marked as "not covered" in lifecycle.py or locks.py.
Target: 90%+ coverage on both files before production.

**When:** After Task 9 (all lifecycle methods) and Task 11 (seed patch).

---

### Level 3 — /mutmut — Mutation Testing (run after Task 9 and before Task 25)
The hardest test of all. Deliberately introduces small bugs into the code
(changes == to !=, removes conditions, flips operators) then runs all tests.
If a bug survives all tests, your tests are weaker than you think.

**What "surviving mutant" means:** Your tests missed a real bug.
**Target:** 0 surviving mutants in lifecycle.py and locks.py.

**Install (one time):**
```
pip install mutmut --break-system-packages
```

**Command:**
```
cd ~/hamilton_erp && mutmut run --paths-to-mutate hamilton_erp/lifecycle.py,hamilton_erp/locks.py && mutmut results
```

**When:** After Task 9 (all lifecycle complete) and Task 25 (pre-production deploy).
This is slow (~20-30 minutes) — only run at major checkpoints.

**Output legend:**
- 🎉 Killed = test caught the bug (good)
- 🙁 Survived = test MISSED the bug (bad — add a test)
- ⏰ Timeout = test took too long
- 🤔 Suspicious = test was slow but passed

---

### Level 4 — /hypothesis — Property-Based Testing (run after Task 9)
Instead of writing specific test cases, Hypothesis generates hundreds of
random inputs automatically and finds edge cases you would never think of.
Especially powerful for the state machine.

**Install (one time):**
```
pip install hypothesis --break-system-packages
```

**What it does for Hamilton ERP:**
- Tries random sequences of lifecycle calls (start, vacate, clean, oos, return)
- Finds invalid transition combinations you didn't test explicitly
- Tests that the version field always increments correctly
- Tests that timestamps are always monotonically increasing

**When:** After Task 9 when all 5 lifecycle methods exist.
Requires hamilton_erp/test_hypothesis.py — will be created at Task 9 hardening.

---

## 3-AI Review Checkpoints
Run ChatGPT + Grok + Claude (new claude.ai tab) reviews at:

| Checkpoint | When | Status |
|---|---|---|
| Tasks 1-2 | After locks.py complete | ✅ Done |
| Tasks 1-8 | After all 5 lifecycle methods | ✅ Done |
| Task 9 | After session number generation | 🔜 Next |
| Task 11 | After seed patch | 🔜 |
| Task 21 | After full Asset Board UI | 🔜 |
| Task 25 | Before Frappe Cloud deploy | 🔜 |

**Review files:**
- Blind review prompt: docs/reviews/review_task9_blind.md
- Context-aware review prompt: docs/reviews/review_task9_context.md

---

## Why each tool catches different bugs

| Tool | What it catches |
|---|---|
| /run-tests | Bugs you already thought to test |
| /coverage | Code paths you forgot to test at all |
| /mutmut | Tests that pass even when the code is wrong |
| /hypothesis | Edge cases you never thought of |
| 3-AI review | Architectural issues and design flaws |

No single tool is enough. All 4 together give you near-certainty.

---

## Current test count (as of Task 8)
- Core tests: 45 passing (25 lifecycle / 3 locks / 17 venue_asset)
- Expert tests: ~52 (some pending Tasks 9-11)
- Total target by Task 11: 90+ tests all passing
