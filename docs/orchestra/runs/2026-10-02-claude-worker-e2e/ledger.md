Plan: docs/orchestra/plans/2026-10-02-shop-cart-plan.md
Routing: Easy=claude sonnet/medium, Medium=claude sonnet/high, Hard=claude sonnet/xhigh
| 1 | Constants | Easy | src/constants.py |
| 2 | Cart | Medium | src/cart.py, tests/test_cart.py |
| 3 | Discounts | Hard | src/discounts.py, src/cart.py, tests/test_discounts.py, tests/test_cart.py |
Task 1: complete (range d42a974..f574157, review clean, tests: python3 -c import constants -> 0.01 99 0.08; minor: scope-check flagged untracked src/__pycache__ because the plan has no .gitignore; added __pycache__/ to .git/info/exclude)
Task 2: complete (range f574157..922fd62, review clean, tests: python3 -m unittest discover -s tests -t . -> 12 OK; minor: worker also rejects NaN/Infinity price and bool qty, beyond brief; scope: only src/__pycache__/, tests/__pycache__/ (ignored) listed, expected)
Task 3: complete (range 922fd62..3d97dba, review clean, tests: python3 -m unittest discover -s tests -t . -> 31 OK; minor: unknown rule raises TypeError (beyond brief); sub-cent price can leave tiny negative remaining after PercentOff (plan gap, bounded by 50% cap); scope: only (ignored) __pycache__ listed)
Ruling: Task 3 fix round 1 (exercise the SendMessage fix path): PercentOff must also never discount more than the line's remaining value; worker's sub-cent finding accepted. Fix base 3d97dba.
Task 3 fix 1: complete (range 3d97dba..42d946f, re-review clean, tests: 32 OK, repro 0.01)
