def calculate_total(items, discount=None):
    """
    items: list of dicts with keys "price" (float) and "quantity" (int)
    discount: None or dict with keys:
        - "type": "percentage" or "flat"
        - "value": numeric discount amount
    """
    # Compute subtotal
    total = sum(item["price"] * item["quantity"] for item in items)

    # Apply discount if provided
    if discount:
        disc_type = discount.get("type")
        value = discount.get("value", 0)

        if disc_type == "percentage":
            # value interpreted as percent (e.g., 10 → 10%)
            total *= max(0, 1 - value / 100.0)
        elif disc_type == "flat":
            total -= value
        else:
            # Fallback: treat as flat amount for backward compatibility
            total -= discount if isinstance(discount, (int, float)) else 0

    # Ensure total is not negative
    return max(total, 0)