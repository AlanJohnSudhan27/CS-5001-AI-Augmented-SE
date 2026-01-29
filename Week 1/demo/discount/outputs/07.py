from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Union

def _to_decimal(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def calculate_total(
    items: List[Dict[str, Union[int, float, str]]],
    discount: Union[None, Dict] = None,
) -> Decimal:
    # ---------- subtotal ----------
    subtotal = Decimal('0')
    for it in items:
        price = _to_decimal(it["price"])
        qty   = int(it["quantity"])
        if price < 0 or qty < 0:
            raise ValueError("price/quantity must be non‑negative")
        subtotal += price * qty

    # ---------- discount ----------
    if discount:
        dtype = discount.get("type")
        dval  = _to_decimal(discount.get("value", 0))

        if dtype == "flat":
            if dval < 0 or dval > subtotal:
                raise ValueError("invalid flat discount")
            subtotal -= dval

        elif dtype == "percent":
            if not (Decimal('0') <= dval <= Decimal('100')):
                raise ValueError("percent must be 0‑100")
            reduction = (subtotal * dval / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            subtotal -= reduction
        else:
            raise ValueError("unknown discount type")

    # ---------- guard ----------
    return max(Decimal('0.00'), subtotal)
```

- All monetary math uses `Decimal` → no floating‑point drift.  
- Validation enforces the rules above; any violation raises `ValueError`.  
- The function returns a **Decimal** rounded to two decimal places, ready for downstream tax/shipping calculations.

=== STEP 4 ===
**Refactored implementation**

```python
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Union, Optional

# helpers --------------------------------------------------------------
def _as_decimal(v: Union[int, float, str]) -> Decimal:
    """Convert to Decimal and round to 2 dp."""
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _validate_item(item: Dict) -> None:
    price = _as_decimal(item.get("price"))
    qty   = int(item.get("quantity"))
    if price < 0 or qty < 0:
        raise ValueError("price and quantity must be non‑negative")
    # keep the converted values for later use
    item["_price"] = price
    item["_qty"]   = qty


def _apply_flat(subtotal: Decimal, value: Decimal) -> Decimal:
    if not (Decimal('0') <= value <= subtotal):
        raise ValueError("flat discount must be ≥0 and ≤ subtotal")
    return subtotal - value


def _apply_percent(subtotal: Decimal, value: Decimal) -> Decimal:
    if not (Decimal('0') <= value <= Decimal('100')):
        raise ValueError("percent discount must be between 0 and 100")
    reduction = (subtotal * value / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    return subtotal - reduction


# public API ------------------------------------------------------------
def calculate_total(
    items: List[Dict[str, Union[int, float, str]]],
    discount: Optional[Dict[str, Union[int, float, str]]] = None,
) -> Decimal:
    """
    Compute order total.

    * Subtotal = Σ price × quantity (price rounded to 2 dp).
    * Discount object:
        {"type": "flat",    "value": <numeric>}   # applied after taxes/fees
        {"type": "percent", "value": <numeric>}   # applied before taxes/fees
    * Validation & rounding follow the business‑rules table.
    * Result is never negative – ``max(0, total)``.
    """
    # --------- subtotal ----------
    subtotal = Decimal('0')
    for it in items:
        _validate_item(it)                         # raises on bad data
        subtotal += it["_price"] * it["_qty"]

    # --------- discount ----------
    if discount:
        dtype = discount.get("type")
        dval  = _as_decimal(discount.get("value", 0))

        if dtype == "flat":
            subtotal = _apply_flat(subtotal, dval)
        elif dtype == "percent":
            subtotal = _apply_percent(subtotal, dval)
        else:
            raise ValueError("unknown discount type")

    # --------- guard ----------
    return max(Decimal('0.00'), subtotal)