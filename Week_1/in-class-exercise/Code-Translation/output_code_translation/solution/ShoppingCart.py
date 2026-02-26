class ShoppingCart:
    def __init__(self):
        self.items = {}

    def add_item(self, item, price, quantity=1):
        self.items[item] = {'price': price, 'quantity': quantity}

    def remove_item(self, item, quantity=1):
        if item in self.items:
            self.items[item]['quantity'] -= quantity
            if self.items[item]['quantity'] <= 0:
                del self.items[item]

    def view_items(self):
        return self.items

    def total_price(self):
        total = 0.0
        for info in self.items.values():
            total += info['price'] * info['quantity']
        return total
