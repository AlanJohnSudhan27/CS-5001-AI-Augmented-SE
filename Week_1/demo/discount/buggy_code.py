def calculate_total(items, discount):
    total = 0
    for item in items:
        total += item["price"] * item["quantity"]
    if discount:
        total = total - discount
    return total
