# Shop Cart Implementation Plan

Goal: a tiny money-safe shopping cart with discount rules. Python 3.10, stdlib only.

## Global constraints

- Python 3.10, standard library only, `unittest`. No new dependencies.
- Run all tests with: `python3 -m unittest discover -s tests -t .`
- Money is `decimal.Decimal`, never float. Every money value that leaves a public function is quantized to cents with `ROUND_HALF_UP`.
- Commit after each task with a one-line message `task N: <title>`. The repo already has git identity configured.
- Edit only the files listed under the task's "Allowed files".

## Interfaces

- `src/constants.py`: `CENT = Decimal("0.01")`, `MAX_QTY = 99`, `TAX_RATE = Decimal("0.08")`.
- `src/cart.py`: `class Cart` with `add(sku: str, price: Decimal, qty: int = 1) -> None`, `lines() -> dict[str, tuple[Decimal, int]]` (sku -> (unit price, qty)), `subtotal() -> Decimal`.
- `src/discounts.py`: `PercentOff(sku, percent)`, `BuyNGetOneFree(sku, n)` dataclasses; `apply_discounts(cart, rules) -> Decimal` (total discount, positive, cents).

### Task 1: Constants

Allowed files: `src/constants.py`

Create `src/constants.py` defining exactly the three constants from "Interfaces" (`CENT`, `MAX_QTY`, `TAX_RATE`) with `Decimal` imported from `decimal`. Nothing else.

Acceptance: `python3 -c "from src.constants import CENT, MAX_QTY, TAX_RATE; print(CENT, MAX_QTY, TAX_RATE)"` prints `0.01 99 0.08` (run from the repo root).

### Task 2: Cart

Allowed files: `src/cart.py`, `tests/test_cart.py`

Implement `Cart` per "Interfaces", using `CENT` and `MAX_QTY` from `src/constants.py`.

- `add` rejects with `ValueError`: empty `sku`; `price` that is not a `Decimal` or is negative; `qty` that is not an `int`, is < 1, or would make the line's total qty exceed `MAX_QTY`.
- Adding an existing sku with the same price merges the qty; with a different price raises `ValueError` and leaves the cart unchanged.
- `lines()` returns a copy; mutating it must not change the cart.
- `subtotal()` is the sum of price * qty, quantized to cents (`ROUND_HALF_UP`); an empty cart gives `Decimal("0.00")`.

Tests (`tests/test_cart.py`) cover every rule above, written first and shown failing before the implementation.

### Task 3: Discounts

Allowed files: `src/discounts.py`, `src/cart.py`, `tests/test_discounts.py`, `tests/test_cart.py`

Create `src/discounts.py` and add `Cart.total(rules=()) -> Decimal` to `src/cart.py`.

Rule semantics for `apply_discounts(cart, rules)`:
- Rules apply in list order. A rule only touches lines whose sku equals the rule's sku; a rule for a sku not in the cart is ignored (no error).
- Each rule works on the line's *remaining value* after earlier rules on that same sku (starting from unit price * qty).
- `PercentOff(sku, percent)`: `percent` is a `Decimal` in (0, 100], else `ValueError` at construction. Discount = remaining value * percent / 100, quantized to cents `ROUND_HALF_UP`.
- `BuyNGetOneFree(sku, n)`: `n` is an `int` >= 1, else `ValueError` at construction. Free units = `qty // (n + 1)`. Discount = free units * unit price, but never more than the line's remaining value.
- The total discount is the sum of all rule discounts, capped at 50% of the cart subtotal (cap quantized to cents `ROUND_HALF_UP`). Return the capped total as a cent-quantized `Decimal`.
- `Cart.total(rules=())` = `(subtotal - apply_discounts(self, rules)) * (1 + TAX_RATE)` quantized to cents `ROUND_HALF_UP`. `src/discounts.py` must not import `src/cart.py` at module level in a way that creates an import cycle (`apply_discounts` only needs `cart.lines()`).

Tests (`tests/test_discounts.py`, plus new cases in `tests/test_cart.py` for `total`) cover: each rule, stacking two rules on one sku in both orders (results differ), the 50% cap, an ignored sku, rounding at a half-cent boundary, and constructor validation.
