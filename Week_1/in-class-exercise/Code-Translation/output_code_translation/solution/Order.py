class Order:
    def __init__(self):
        self.menu = []
        self.selected_dishes = []
        self.sales = {}

    def add_dish(self, dish):
        for menu_dish in self.menu:
            if dish['dish'] == menu_dish['dish']:
                if menu_dish['count'] < dish['count']:
                    return False
                else:
                    menu_dish['count'] -= dish['count']
                    break
        self.selected_dishes.append(dish)
        return True

    def calculate_total(self):
        total = 0
        for dish in self.selected_dishes:
            if dish['dish'] in self.sales:
                total += dish['price'] * dish['count'] * self.sales[dish['dish']]
        return total

    def checkout(self):
        if not self.selected_dishes:
            return 0
        total = self.calculate_total()
        self.selected_dishes.clear()
        return total
