from abc import ABCMeta

class HyperliquidBase(metaclass=ABCMeta):
    def __init__(self):
        self.address = ""
        self.positions = {}

    def get_balance(self, coin):
        pass

    def get_mid_price(self, coin):
        pass

    def get_positions(self):
        pass
    
    def cancel(self, coin, oid):
        pass 

    def open_opposite_position(self, fill):
        pass 

    def set_user_event_update(self, cb):
        pass 
    @classmethod
    def from_row(cls, row, proxies, **kwargs):
        pass 

    def transfer(self, sz, destination):
        pass 

    def set_user_event_update(self, cb):
        pass 

    def open_maker_position(self, coin, sz):
        pass 
    
    def close_maker_position(self, coin):
        pass 

    def close_market_position(self, coin):
        pass 

    def maker_buy(self, coin, sz):
        pass 

    def maker_sell(self, coin, sz):
        pass 


