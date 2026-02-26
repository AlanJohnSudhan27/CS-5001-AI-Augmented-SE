class StockPortfolioTracker:
    def __init__(self, cash_balance):
        self.portfolio = []
        self.cash_balance = cash_balance

    def add_stock(self, stock):
        for pf in self.portfolio:
            if pf['name'] == stock['name']:
                pf['quantity'] += stock['quantity']
                return
        self.portfolio.append(stock)

    def remove_stock(self, stock):
        for i, pf in enumerate(self.portfolio):
            if pf['name'] == stock['name'] and pf['quantity'] >= stock['quantity']:
                pf['quantity'] -= stock['quantity']
                if pf['quantity'] == 0:
                    self.portfolio.pop(i)
                return True
        return False

    def buy_stock(self, stock):
        if stock['price'] * stock['quantity'] > self.cash_balance:
            return False
        else:
            self.add_stock(stock)
            self.cash_balance -= stock['price'] * stock['quantity']
            return True

    def sell_stock(self, stock):
        if not self.remove_stock(stock):
            return False
        self.cash_balance += stock['price'] * stock['quantity']
        return True

    def calculate_portfolio_value(self):
        total_value = self.cash_balance
        for stock in self.portfolio:
            total_value += stock['price'] * stock['quantity']
        return total_value

    def get_portfolio_summary(self):
        summary = []
        for stock in self.portfolio:
            summary.append({'name': stock['name'], 'value': self.get_stock_value(stock)})
        return (self.calculate_portfolio_value(), summary)

    def get_stock_value(self, stock):
        return stock['price'] * stock['quantity']

    def get_portfolio(self):
        return self.portfolio

    def get_cash_balance(self):
        return self.cash_balance

    def set_portfolio(self, p):
        self.portfolio = p
