def calculate_total(items, discount=0):
    """
    Calculate the total price of a list of items applying a numeric discount.

    Parameters
    ----------
    items : iterable of dict
        Each dict must contain ``price`` (number) and ``quantity`` (int).
    discount : float or int, optional
        A flat amount to subtract from the subtotal. If ``None`` or non‑numeric,
        it is treated as 0.

    Returns
    -------
    float
        The final total, never negative.
    """
    # 1️⃣ Compute the subtotal safely
    subtotal = 0.0
    for item in items:
        try:
            price = float(item["price"])
            qty   = int(item["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid item {item!r}: {exc}") from None
        subtotal += price * qty

    # 2️⃣ Normalise the discount (treat None / non‑numeric as 0)
    try:
        discount_val = float(discount) if discount is not None else 0.0
    except (TypeError, ValueError):
        discount_val = 0.0

    # 3️⃣ Apply the discount – never let the total go below zero
    total = max(subtotal - discount_val, 0.0)

    return total