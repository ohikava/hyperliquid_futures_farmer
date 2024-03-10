from perp.hyperliquid.main import Hyperliquid
from perp.randomizer import Randomizer
from perp.observer import Observer
from perp.utils.funcs import calculate_profit, load_json_file, dump_json, run_with_traceback
from perp.utils.types import PerpPair, Position, Perp, ClosedPositionInfo, PerpStats
import perp.config as config
import perp.constants as constants
import json 
import threading
import time 
from os.path import join
from typing import Union, Dict, List


wallets_path = "wallets"


class Main():
    def __init__(self):
        self.randomizer = Randomizer()
        self.observer = Observer()
        self.positions_total = []
        self.pairs = {}

        self.load_pair(join(wallets_path, "1.json"))


    def load_pair(self, wallets_path: str):
        wallets = load_json_file(wallets_path)
        perp1 = wallets["perp1"]
        perp2 = wallets["perp2"]

        self.add_pair(perp1, perp2)

    def add_pair(self, perp1: Perp, perp2: Perp):
        perp1: Hyperliquid = Hyperliquid.from_row(perp1['secret'], proxies=perp1['proxies'])
        perp2: Hyperliquid = Hyperliquid.from_row(perp2['secret'], proxies=perp2['proxies'])

        self.pairs[(perp1.address, perp2.address)]= {
            'perp1': perp1,
            'perp2': perp2,
            'perp1_positions': {},
            'perp2_positions': {}
        }
    
    def run(self):
        while True:
            for pair in self.pairs:
                self.check_user_stats(pair) # Проверяет баланс пользователя, подсчитывает убытки

                self.check_positions(pair) # Проверяет позиции, не пора ли закрывать, сколько открыто, открыты ли вообще

                self.open_positions(pair) # Открывает позиции, если есть место



    def check_user_stats(self, pair: PerpPair):
        """"
        Проверяет баланс пользователя, подсчитывает убытки, перебалансирует баланс между кошельками
        """
        p1 = pair['perp1']
        p2 = pair['perp2']

        p1_balance = p1.get_balance()
        p2_balance = p2.get_balance()

        if pair['rebalance'] and abs(p1_balance - p2_balance) / min(p1_balance, p2_balance) >= 0.2:
            total_sum = p1_balance + p2_balance
            new_balance = total_sum / 2

            if p1_balance > p2_balance:
                p1.transfer(p1_balance - new_balance, p2.address)
            else:
                p2.transfer(p2_balance - new_balance, p1.address)

            pair['min_balance'] = new_balance
            pair['rebalance'] = False
        else:
            pair['min_balance'] = min(p1_balance, p2_balance)

        self.calculate_stats(pair)

    def open_positions(self, pair: PerpPair):
        open_positions = pair['perp1_positions'] 

        if len(open_positions) > pair['max_open_positions']:
            return
        
        open_pairs = list(open_positions.keys())

        new_positions = self.randomizer.get_random_coins(open_pairs, pair['max_open_positions'] - len(open_positions))

        for position in new_positions:
            self.open_position(pair)

    def check_positions(self, pair: PerpPair):
        for position in pair['perp1_positions']:
            assert position in pair['perp2_positions'], f"Position {position} is not in perp2_positions"

            perp1_position = pair['perp1_positions'][position]

            if time.time() - perp1_position["fill_time"] > perp1_position["position_lifetime"]:
                self.close_position(pair, position)

    def open_position(self, perp_pair: PerpPair):
        perp1_positions: Dict[str, Position] = perp_pair['perp1_positions']
        perp2_positions: Dict[str, Position] = perp_pair['perp2_positions']

        if perp1_positions or perp2_positions:
            return 

        perp1: Hyperliquid = perp_pair['perp1']
        perp2: Hyperliquid = perp_pair['perp2']

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
        perp1: Hyperliquid = perp_pair['perp1']
        perp2: Hyperliquid = perp_pair['perp2']
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
        
        perp_pair['closed_position_info'].append(total)
        
        perp1_positions.pop(coin)
        perp2_positions.pop(coin)
    
    def calculate_stats(self, perp_pair: PerpPair):
        perp1_address = perp_pair['perp1'].address
        perp2_address = perp_pair['perp2'].address

        perp1_fees = 0.0
        perp2_fees = 0.0
        perp1_profit = 0.0
        perp2_profit = 0.0

        for deal in perp_pair['closed_position_info']:
            perp1_fees += deal["perp1_fees"]
            perp2_fees += deal["perp2_fees"]

            perp1_profit += deal["perp1_profit"]
            perp2_profit += deal["perp2_profit"]
        
        perp_stats: PerpStats = {
            "perp1_address": perp1_address,
            "perp2_address": perp2_address,
            "perp1_fees": round(perp1_fees, 2),
            "perp2_fees": round(perp2_fees, 2),
            "perp1_profit": round(perp1_profit, 2),
            "perp2_profit": round(perp2_profit, 2)
        }
        self.observer.show_stats(perp_stats)
        

