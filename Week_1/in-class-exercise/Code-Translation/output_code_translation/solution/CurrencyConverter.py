class CurrencyConverter:
    def __init__(self):
        self.rates = {
            "USD": 1.0,
            "EUR": 0.85,
            "GBP": 0.72,
            "JPY": 110.15,
            "CAD": 1.23,
            "AUD": 1.34,
            "CNY": 6.40,
        }
        self.currency_order = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CNY"]

    def convert(self, amount, from_currency, to_currency):
        if from_currency == to_currency:
            return amount
        if from_currency not in self.rates or to_currency not in self.rates:
            return False
        from_rate = self.rates[from_currency]
        to_rate = self.rates[to_currency]
        converted_amount = (amount / from_rate) * to_rate
        return converted_amount

    def get_supported_currencies(self):
        return self.currency_order

    def add_currency_rate(self, currency, rate):
        if currency in self.rates:
            return False
        self.rates[currency] = rate
        self.currency_order.append(currency)
        return True

    def update_currency_rate(self, currency, new_rate):
        if currency not in self.rates:
            return False
        self.rates[currency] = new_rate
        return True
