from perp.perps.aevo import Aevo
from perp.perps.hyperliquid import Hyperliquid
from perp.randomizer import Randomizer
from perp.observer import Observer
from perp.utils.funcs import calculate_profit, load_json_file, dump_json
from perp.utils.types import PerpPair, Position, Perp 
import perp.config as config
import perp.constants as constants
import json 
import threading
import time 
from dotenv import load_dotenv
from os.path import join
from typing import Union, Dict, List

load_dotenv()


strategies_path = "strategies"


class Main():
    def __init__(self):
        self.load_strategy(join(strategies_path, "strategy.json"))

        self.randomizer = Randomizer()

        self.observer = Observer()
        self.positions_total = []

    def load_strategy(self, strategy_path: str):
        strategy = load_json_file(strategy_path)
        perp1 = strategy["perp1"]
        perp2 = strategy["perp2"]

        self.add_mirror_pair(perp1, perp2)

    def load_perp(self, perp: Perp):
        if perp['name'] == 'hyperliquid':
            perp = Hyperliquid.from_row(perp['secret'], proxies=perp['proxies'])
        elif perp['name'] == 'aevo':
            perp = Aevo.from_row(perp['secret'], proxies=perp['proxies'])
        
        return perp
    
    def add_mirror_pair(self, perp1: Perp, perp2: Perp):
        perp1 = self.load_perp(perp1)
        perp2 = self.load_perp(perp2)

        self.mirror_pairs[(perp1.address, perp2.address)]= {
            'perp1': perp1,
            'perp2': perp2,
            'perp1_positions': {},
            'perp2_positions': {}
        }
    
    def run(self):
        while True:
            for perp_pair in self.mirror_pairs.values():
                self.check_should_close_position(perp_pair) 

                self.open_position(perp_pair)
    
    def check_should_close_position(self, perp_pair: PerpPair):
        perp1_positions: Dict[str, Position] = perp_pair['perp1_positions']
        perp2_positions: Dict[str, Position] = perp_pair['perp2_positions']
        if not perp1_positions or not perp2_positions:
            return
        

        coin = list(perp1_positions.keys())[0]
        perp1_position = perp1_positions[coin]
        perp2_position = perp2_positions[coin]

        fill_time = min(perp1_position["fill_time"], perp2_position["fill_time"])

        if time.time() - fill_time < perp1_position["position_lifetime"]:
            return

        self.close_position(coin, perp_pair)

    def open_position(self, perp_pair: PerpPair):
        perp1_positions: Dict[str, Position] = perp_pair['perp1_positions']
        perp2_positions: Dict[str, Position] = perp_pair['perp2_positions']

        if perp1_positions or perp2_positions:
            return 

        perp1: Union[Hyperliquid, Aevo] = perp_pair['perp1']
        perp2: Union[Hyperliquid, Aevo] = perp_pair['perp2']

        coin = self.randomizer.get_random_coin()
        leverage = self.randomizer.get_random_leverage()
        sides = self.randomizer.get_random_sides()
        position_lifetime = self.randomizer.get_random_time()

        mid_price = perp1.get_mid_price(coin)
        position_size = config.POSITION_SIZE / mid_price

        scaled_position_size = position_size * leverage
        min_decimals = min(perp1.size_decimals[coin], perp2.size_decimals[coin])
        scaled_position_size = round(scaled_position_size, min_decimals)

        threads = []
        if sides == constants.LONG_PERP1_SHORT_PERP2:
            threads.append(threading.Thread(target=perp1.market_buy, args=(coin, scaled_position_size)))
            threads.append(threading.Thread(target=perp2.market_sell, args=(coin, scaled_position_size)))
        else:
            threads.append(threading.Thread(target=perp1.market_sell, args=(coin, scaled_position_size)))
            threads.append(threading.Thread(target=perp2.market_buy, args=(coin, scaled_position_size)))
        
        sleep_time = self.randomizer.get_random_sleep_time()
        if perp1.name == perp2.name:
            threads = threads[::self.randomizer.get_random_order()]
            
        for t in threads:
            t.start()
            if perp1.name == perp2.name:
                time.sleep(sleep_time)

        for t in threads:
            t.join()

        time.sleep(config.SLEEP)

        perp_pair['perp1_positions'][coin] = {**perp1.last_fill, "position_lifetime": position_lifetime}
        self.observer.order_filled(perp1.last_fill, 'OPEN')

        perp_pair['perp2_positions'][coin] = {**perp2.last_fill, "position_lifetime": position_lifetime}
        self.observer.order_filled(perp2.last_fill, 'OPEN')

        print(perp1_positions, perp2_positions)
    
    def close_position(self, coin, perp_pair: PerpPair):
        perp1_positions: Dict[str, Position] = perp_pair['perp1_positions']
        perp2_positions: Dict[str, Position] = perp_pair['perp2_positions']

        if coin not in perp1_positions or coin not in perp2_positions:
            return
        
        perp1_position = perp1_positions[coin]
        perp2_position = perp2_positions[coin]
        perp1: Union[Hyperliquid, Aevo] = perp_pair['perp1']
        perp2: Union[Hyperliquid, Aevo] = perp_pair['perp2']
        threads = []

        if perp1_position["side"] == constants.LONG:
            threads.append(threading.Thread(target=perp1.market_sell, args=(coin, perp1_position["sz"])))
            threads.append(threading.Thread(target=perp2.market_buy, args=(coin, perp2_position["sz"])))
        else:
            threads.append(threading.Thread(target=perp1.market_buy, args=(coin, perp1_position["sz"])))
            threads.append(threading.Thread(target=perp2.market_sell, args=(coin, perp2_position["sz"])))
        
        sleep_time = self.randomizer.get_random_sleep_time()
        if perp1.name == perp2.name:
            threads = threads[::self.randomizer.get_random_order()]
        for t in threads:
            t.start()
            if perp1.name == perp2.name:
                time.sleep(sleep_time)

        for t in threads:
            t.join()

        time.sleep(config.SLEEP)

        self.observer.order_filled(perp1.last_fill, 'CLOSE')
        
        self.observer.order_filled(perp2.last_fill, 'CLOSE')

        total = {
            "perp1_profit": calculate_profit(perp1_position, perp1.last_fill),
            "perp2_profit": calculate_profit(perp2_position, perp2.last_fill),
            "perp1_fees": perp1.last_fill["fee"] + perp1_position["fee"],
            "perp2_fees": perp2.last_fill["fee"] + perp2_position["fee"]
        }
        self.positions_total.clear()
        self.positions_total.append(total)
        
        perp1_positions.pop(coin)
        perp2_positions.pop(coin)

        self.calculate_stats()
    
    def calculate_stats(self):
        perp1_fees = 0.0
        perp2_fees = 0.0

        perp1_profit = 0.0
        perp2_profit = 0.0

        for deal in self.positions_total:
            perp1_fees += deal["perp1_fees"]
            perp2_fees += deal["perp2_fees"]

            perp1_profit += deal["perp1_profit"]
            perp2_profit += deal["perp2_profit"]
        
        self.observer.show_stats(round(perp1_fees, 2), round(perp2_fees, 2), round(perp1_profit, 2), round(perp2_profit, 2))
        

