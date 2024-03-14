from perp.hyperliquid.main import Hyperliquid
from perp.observer import Observer
from perp.utils.funcs import load_json_file, run_with_traceback
from perp.utils.types import PerpPair, Position, ClosedPosition
import perp.randomizer as randomizer
import perp.config as config
import perp.constants as constants
import time 
from os.path import join
from typing import List
import logging 

logger = logging.getLogger(__name__)


wallets_path = "wallets"


class Main():
    def __init__(self):
        self.observer = Observer()
        self.pairs: List[PerpPair] = []
        self.last_closed_position = ()

        self.add_wallets(join(wallets_path, "1.json"))

    def add_wallets(self, wallets_path: str):
        wallets = load_json_file(wallets_path)
        perp1 = wallets["perp1"]
        perp2 = wallets["perp2"]
        wallets_config = wallets['config']
        perp1: Hyperliquid = Hyperliquid.from_row(perp1['secret'], proxies=perp1['proxies'], wallet_config=wallets_config)
        perp2: Hyperliquid = Hyperliquid.from_row(perp2['secret'], proxies=perp2['proxies'], wallet_config=wallets_config)
        res = {
            'max_open_positions': randomizer.random_int(wallets_config["min_open_positions"], wallets_config["max_open_positions"]),
            'perp1': perp1,
            'perp2': perp2
        }
        self.pairs.append(res)

    def run(self):
        ix = 0
        while True:
            print(f"Iteration #{ix} has began")
            for pair in self.pairs:
                open_positions = set(pair["perp1"].positions.keys()) & set(pair["perp2"].positions.keys())
                coins = randomizer.random_coins(open_positions, pair['max_open_positions'] - len(open_positions))

                for coin in coins:
                    run_with_traceback(self.open_position, logger, pair, coin)
                    time.sleep(randomizer.random_int(config.MIN_SLEEP_TIME, config.MAX_SLEEP_TIME))

                for coin in open_positions:
                    position: Position = pair["perp1"].positions[coin]

                    if time.time() - position["open_time"] > position["lifetime"]: 
                        run_with_traceback(self.close_position_maker, logger, pair, coin)
                        time.sleep(randomizer.random_int(config.MIN_SLEEP_TIME, config.MAX_SLEEP_TIME))
            
            ix += 1
            time.sleep(60 * 1)


    def open_position(self, perp_pair: PerpPair, coin: str):
        perp1: Hyperliquid = perp_pair['perp1']
        perp2: Hyperliquid = perp_pair['perp2']

        mid_price = perp1.get_mid_price(coin)
        position_size = perp1.config['position_size'] / mid_price

        min_decimals = perp1.size_decimals[coin]
        position_size = round(position_size, min_decimals)
        
        response = perp1.open_maker_position(coin, position_size)

        if response == constants.ERROR_FIELD:
            return 

        while coin not in perp1.positions or perp1.positions[coin]['sz'] != position_size:
            continue 

        p1_position: Position = perp1.positions.get(coin, {})
        if p1_position['side'] == constants.LONG:
            order_result = perp2.market_sell(coin, p1_position['sz'])
        else:
            order_result = perp2.market_buy(coin, p1_position['sz'])
        
        start_waiting = time.time()
        while coin not in perp2.positions or perp2.positions[coin]['sz'] != position_size:
            if time.time() - start_waiting > 10:
                perp2.cancel(coin, order_result.get('oid', -1))
                if p1_position['side'] == constants.LONG:
                    if coin in perp2.positions:
                        order_result = perp2.market_sell(coin, p1_position['sz'] - perp2.positions[coin]['sz'])
                    else:
                        order_result = perp2.market_sell(coin, p1_position['sz'])
                else:
                    if coin in perp2.positions:
                        order_result = perp2.market_buy(coin, p1_position['sz'] - perp2.positions[coin]['sz'])
                    else:
                        order_result = perp2.market_buy(coin, p1_position['sz']) 
                start_waiting = time.time()


    def close_position_maker(self, pair: PerpPair, coin: str):
        p1 = pair['perp1']
        p2 = pair['perp2']

        p1_info:Position = p1.positions.get(coin, {})
        p2_info:Position = p2.positions.get(coin, {})

        assert p1_info and p2_info

        p1_oid = p1.close_maker_position(coin)
        p2_oid = p2.close_maker_position(coin)

        start_time = time.time()
        market_perp = None 
        while True:
            if coin not in p1.positions:
                p2.cancel(coin, p2_oid)
                market_perp = p2 

                break 
            
            if coin not in p2.positions:
                p1.cancel(coin, p1_oid)
                market_perp = p1 
                break 
            
            if time.time() - start_time > 12:
                p1.cancel(coin, p1_oid)
                p2.cancel(coin, p2_oid)

                if coin in p1.positions:
                    p1_oid = p1.close_maker_position(coin)
                if coin in p2.positions:
                    p2_oid = p2.close_maker_position(coin)

                start_time = time.time()
        
        order_result = market_perp.close_market_position(coin)

        start_time = time.time()
        while coin in market_perp.positions:
            if time.time() - start_time > 10:
                market_perp.cancel(order_result.get('oid', -1))
                order_result = market_perp.close_market_position(coin)
                start_time = time.time()

        p1_stats: ClosedPosition = p1.closed_positions[coin]
        p2_stats: ClosedPosition = p2.closed_positions[coin]
        
        self.observer.position_closed(coin, p1_stats['pnl'], p2_stats['pnl'], p1_stats['fee'], p2_stats['fee'], p1_stats['side'])
            
        

