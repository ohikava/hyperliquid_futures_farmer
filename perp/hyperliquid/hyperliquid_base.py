from abc import ABCMeta
import perp.config as config

class HyperliquidBase(metaclass=ABCMeta):
    def __init__(self):
        self.address = ""
        self.name = 'hyperliquid'

    def buy(self, coin, sz, px):
        pass

    def sell(self, coin, sz, px):
        pass

    def market_buy(self, coin, sz):
        pass

    def market_sell(self, coin, sz):
        pass

    def get_balance(self, coin):
        pass

    def get_mid_price(self, coin):
        pass

    def get_positions(self):
        pass