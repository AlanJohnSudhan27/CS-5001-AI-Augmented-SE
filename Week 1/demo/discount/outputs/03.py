from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Iterable, Mapping, Union, List, TypedDict

class CartItem(TypedDict):
    price: Union[str, float, Decimal]   # price in major currency unit
    quantity: int

def _to_decimal(value: Union[str, float, Decimal]) -> Decimal:
    """Coerce a monetary value to Decimal with two‑decimal precision."""
    try:
        d = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc
    return d

def calculate_total(
    items: Iterable[Mapping],
    discount: Union[Decimal, float, str, None] = None,
    *,
    discount_is_percent: bool = False,
    tax_rate: Decimal = Decimal('0.00')
) -> Decimal:
    """
    Calculate the payable amount for a list of items.

    - `price` must be a non‑negative monetary value.
    - `quantity` must be a non‑negative integer.
    - `discount` can be a flat amount or a percentage (set `discount_is_percent=True`).
    - `tax_rate` is a decimal fraction (e.g., 0.07 for 7 % tax).
    Returns a Decimal rounded to two decimal places, never negative.
    """
    subtotal = Decimal('0.00')

    for item in items:
        # ---- validation ----
        try:
            price = _to_decimal(item["price"])
            qty = int(item["quantity"])
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Item missing required fields: {item}") from exc

        if price < 0:
            raise ValueError(f"Negative price not allowed: {price}")
        if qty < 0:
            raise ValueError(f"Negative quantity not allowed: {qty}")

        # ---- accumulation ----
        line_total = (price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        subtotal += line_total

    # ---- discount handling ----
    if discount is not None:
        disc = _to_decimal(discount)
        if discount_is_percent:
            # Percent discount is applied on subtotal BEFORE tax
            if disc > Decimal('100'):
                raise ValueError("Percentage discount cannot exceed 100")
            disc_amount = (subtotal * disc / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            disc_amount = disc

        if disc_amount > subtotal:
            disc_amount = subtotal   # cap to avoid negative subtotal
        subtotal -= disc_amount

    # ---- tax ----
    if tax_rate:
        if not (Decimal('0') <= tax_rate <= Decimal('1')):
            raise ValueError("tax_rate must be between 0 and 1")
        tax = (subtotal * tax_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        subtotal += tax

    # Ensure final amount is non‑negative and has exactly two decimal places
    final_total = max(subtotal, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return final_total