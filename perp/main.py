from perp.hyperliquid.main import Hyperliquid
from perp.observer import Observer
from perp.utils.funcs import load_json_file
from perp.utils.types import PerpPair, Position
import perp.randomizer as randomizer
import perp.config as config
import perp.constants as constants
import threading
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

        self.add_wallets(join(wallets_path, "1.json"))

    def add_wallets(self, wallets_path: str):
        wallets = load_json_file(wallets_path)
        perp1 = wallets["perp1"]
        perp2 = wallets["perp2"]
        wallets_config = wallets['config']
        perp1: Hyperliquid = Hyperliquid.from_row(perp1['secret'], proxies=perp1['proxies'], wallet_config=wallets_config)
        perp2: Hyperliquid = Hyperliquid.from_row(perp2['secret'], proxies=perp2['proxies'], wallet_config=wallets_config)
        res = {
            'max_open_positions': randomizer.random_int(config.MIN_OPEN_POSITIONS, config.MAX_OPEN_POSITIONS),
            'perp1': perp1,
            'perp2': perp2
        }
        self.pairs.append(res)

    def run(self):
        while True:
            threads = []
            for pair in self.pairs:
                open_positions = set(pair["perp1"].positions.keys()) & set(pair["perp2"].positions.keys())
                coins = randomizer.random_coins(open_positions, pair['max_open_positions'] - len(open_positions))

                for coin in coins:
                    threads.append(threading.Thread(target=self.open_position, args=(pair, coin))) 

                for coin in open_positions:
                    position: Position = pair["perp1"].positions[coin]

                    if time.time() - position["open_time"] > position["lifetime"]: 
                        threads.append(threading.Thread(target=self.close_position_maker, args=(pair, position)))
            
            ix = 0
            while ix < len(threads):
                batch = threads[ix:ix+config.THREADS_BATCH]

                for t in batch:
                    t.start()
                    sleep = randomizer.random_int(config.WAIT_BEFORE_ORDER_MIN, config.WAIT_BEFORE_ORDER_MAX)
                    time.sleep(sleep)
                
                for t in batch:
                    t.join()

                ix += config.THREADS_BATCH

            time.sleep(60 * 1)

    def open_position(self, perp_pair: PerpPair, coin: str):
        perp1: Hyperliquid = perp_pair['perp1']
        perp2: Hyperliquid = perp_pair['perp2']

        mid_price = perp1.get_mid_price(coin)
        position_size = config.POSITION_SIZE / mid_price

        min_decimals = perp1.size_decimals[coin]
        position_size = round(position_size, min_decimals)
        
        perp1.open_maker_position(coin, position_size)

        while coin not in perp1.positions:
            continue 

        p1_position: Position = perp1.positions.get(coin, {})
        if p1_position['side'] == constants.LONG:
            perp2.market_sell(coin, p1_position['sz'])
        else:
            perp2.market_buy(coin, p1_position['sz'])
        
        start_waiting = time.time()
        while coin not in perp2.positions:
            if time.time() - start_waiting > 15:
                logger.error(f"can't make market order for {coin}")
                break
            continue 


    def close_position_maker(self, pair: PerpPair, coin: str):
        p1 = pair['perp1']
        p2 = pair['perp2']

        p1_info:Position = p1.positions.get(coin, {})
        p2_info:Position = p2.positions.get(coin, {})

        assert p1_info and p2_info

        p1_oid = p1.close_maker_position(coin)
        p2_oid = p2.close_maker_position(coin)

        start_time = time.time()
        while True:
            if coin not in p1.positions:
                p2.cancel(coin, p2_oid)
                p2.close_market_position(coin)
                break 
            
            if coin not in p2.positions:
                p1.cancel(coin, p1_oid)
                p1.close_market_position(coin)
                break 
            
            if time.time() - start_time > 12:
                p1.cancel(coin, p1_oid)
                p2.cancel(coin, p2_oid)

                p1_oid = p1.close_maker_position(coin)
                p2_oid = p2.close_maker_position(coin)

