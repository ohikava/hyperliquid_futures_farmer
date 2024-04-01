from copy import deepcopy
from perp.hyperliquid.main import Hyperliquid
from perp.observer import Observer
from perp.utils.funcs import load_json_file, run_with_traceback
from perp.utils.types import PerpPair, Position, ClosedPosition
import perp.randomizer as randomizer
import perp.config as config
import perp.constants as constants
import time 
from os.path import join
from typing import Tuple , List
import logging 
import os 
import threading
from perp.contracts import Contracts
from perp.stats import get_profit
logger = logging.getLogger(__name__)


wallets_path = "wallets"


class Main():
    def __init__(self):
        self.observer = Observer()
        self.pairs: List[Tuple[Hyperliquid, Hyperliquid]] = []
        self.last_closed_position = ()

        wallets = os.listdir(wallets_path)
        for wallet in wallets:
            if not wallet.endswith('.json'):
                continue
            self.add_wallets(join(wallets_path, wallet))
        self.contracts = Contracts()
        self.last_notification_time = time.time()
        try:
            self.observer.observer_stats(*get_profit())
        except:
            pass 
        threading.Thread(target=self.observe).start()

    def observe(self):
        while True:
            if time.time() - self.last_notification_time > config.NOTIFY_INTERVAL * 60:
                self.last_notification_time = time.time()
                try:
                    self.observer.observer_stats(*get_profit())
                except:
                    pass 
        
        
    def add_wallets(self, wallets_path: str):
        wallets = load_json_file(wallets_path)
        perp1 = wallets["perp1"]
        perp2 = wallets["perp2"]
        wallets_config = wallets['config']

        perp1: Hyperliquid = Hyperliquid.from_row(perp1['secret'], proxies=perp1['proxies'], wallet_config=wallets_config)
        perp2: Hyperliquid = Hyperliquid.from_row(perp2['secret'], proxies=perp2['proxies'], wallet_config=wallets_config)

        self.pairs.append((perp1, perp2))
        if not perp1.config['load_saved_positions']:
            self.clear_perps(self.pairs[-1])
        else:
            perp1.close_all_orders()
            perp2.close_all_orders()

    def run(self):
        ix = 0
        while True:
            print(f"Iteration #{ix} has began")
            for pair in self.pairs:
                self.load_user_states(pair)
                self.update_positions(pair)
                self.check_balances(pair)

                p1, p2 = pair 

                open_positions = set(p1.positions.keys()) & set(p2.positions.keys())
                n_new = randomizer.random_int(p1.config['min_open_positions'], p2.config['max_open_positions']) - len(open_positions)
                n_new = max(0, n_new)

                coins = randomizer.random_coins(open_positions, n_new)
                current_sides = [p1.positions[i]['side'] for i in open_positions]
                sides = randomizer.random_sides(current_sides, len(coins))
                sides = {coin: side for coin, side in zip(coins, sides)}

                n = len(open_positions) + len(coins)
                for coin, side in sides.items():
                    run_with_traceback(self.open_position, logger, pair, coin, side, n)
                    time.sleep(randomizer.random_int(config.MIN_SLEEP_TIME, config.MAX_SLEEP_TIME))

                for coin in open_positions:
                    position: Position = pair[0].positions[coin]

                    if time.time() - position["open_time"] > position["lifetime"]: 
                        run_with_traceback(self.close_position, logger, pair, coin)
                        time.sleep(randomizer.random_int(config.MIN_SLEEP_TIME, config.MAX_SLEEP_TIME))

                self.remove_positions(pair)
            ix += 1
            time.sleep(60 * 1)

    def clear_perps(self, perp_pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = perp_pair
        threads = [threading.Thread(target=p1.close_all_orders), threading.Thread(target=p2.close_all_orders)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        threads = [threading.Thread(target=p1.close_all_positions), threading.Thread(target=p2.close_all_positions)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    
    def clear_perps_sync(self, perp_pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = perp_pair
        p1.close_all_orders()
        p2.close_all_orders()
        p1.close_all_positions()
        p2.close_all_positions()

    def open_position(self, perp_pair: Tuple[Hyperliquid, Hyperliquid], coin: str, p1_side: str, n: int):
        p1, p2 = perp_pair

        leverage= p1.config['leverage']
        one_position_leverage= leverage / n

        balance_p1 = p1.get_balance()
        balance_p2 = p2.get_balance()

        min_eq = min(balance_p1['accountValue'], balance_p2['accountValue'])
        min_avail = min(balance_p1['available'], balance_p2['available'])

        if min_avail < p1.config['min_available_balance']:
            self.kill()

        position_size_usd = min_eq * one_position_leverage

        mid_price = p1.get_mid_price(coin)
        position_size = position_size_usd / mid_price
        min_decimals = p1.size_decimals[coin]
        sz = round(position_size, min_decimals)

        if p1_side == constants.LONG:
            ts = [threading.Thread(target=p1.maker_buy, args=(coin, sz)), threading.Thread(target=p2.maker_sell, args=(coin, sz))] 
        else:
            ts = [threading.Thread(target=p1.maker_sell, args=(coin, sz)), threading.Thread(target=p2.maker_buy, args=(coin, sz))]
        
        for t in ts:
            t.start()
        for t in ts:
            t.join()


        start_time = time.time()
        while True:
            if coin not in p1.orders:
                p2.cancel(coin, p2.orders.get(coin, {}).get('oid', 0))
                if coin in p2.orders and p1_side == constants.LONG:
                    p2.market_sell(coin, p2.orders[coin]['sz'])
                elif coin in p2.orders:
                    p2.market_buy(coin, p2.orders[coin]['sz'])
                break
            elif coin not in p2.orders:
                p1.cancel(coin, p1.orders.get(coin, {}).get('oid', 0))
                if coin in p1.orders and p1_side == constants.LONG:
                    p1.market_buy(coin, p1.orders[coin]['sz'])
                elif coin in p1.orders:
                    p1.market_sell(coin, p1.orders[coin]['sz'])
                break
            elif time.time() - start_time > 20:
                ts_1 = [threading.Thread(target=p1.cancel, args=(coin, p1.orders.get(coin, {}).get('oid', 0))), threading.Thread(target=p2.cancel, args=(coin, p2.orders.get(coin, {}).get('oid', 0)))]
                for t in ts_1:
                    t.start()
                for t in ts_1:
                    t.join()
                
                if p1_side == constants.LONG:
                    ts = [threading.Thread(target=p1.maker_buy, args=(coin, p1.orders[coin]['sz'])), threading.Thread(target=p2.maker_sell, args=(coin, p2.orders[coin]['sz']))] 
                else:
                    ts = [threading.Thread(target=p1.maker_sell, args=(coin, p1.orders[coin]['sz'])), threading.Thread(target=p2.maker_buy, args=(coin, p2.orders[coin]['sz']))]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()

                start_time = time.time()

    def remove_positions(self, pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = pair 

        p1_pos = deepcopy(p1.positions)
        p2_pos = deepcopy(p2.positions)

        for coin, position in p1_pos.items():
            side = position['side']
            if coin not in p2_pos:
                logger.info(f"removing {coin} {position['sz']} from {p1.address[:5]}")

                if side == constants.LONG:
                    p1.market_sell(coin, position['sz'])
                else:
                    p1.market_buy(coin, position['sz'])

            elif position['side'] == p2_pos[coin]['side']:
                logger.info(f"removing {coin} {position['sz']} from {p1.address[:5]} as it has the same side with {p2.address[:5]}")
                if side == constants.LONG:
                    p1.market_sell(coin, position['sz'])
                else:
                    p1.market_buy(coin, position['sz'])

            elif p2_pos[coin]['sz'] < position['sz']:
                logger.info(f"removing partially {coin} {position['sz']-p2_pos[coin]['sz']} from {p1.address[:5]}")

                if side == constants.LONG:
                    r = p1.market_sell(coin, position['sz']-p2_pos[coin]['sz'] )
                else:
                    r = p1.market_buy(coin, position['sz']-p2_pos[coin]['sz'] )
                if r['code'] == constants.ERROR_FIELD:
                    if side == constants.LONG:
                        p1.market_sell(coin, position['sz'])
                    else:
                        p1.market_buy(coin, position['sz'])

        
        p1_pos = deepcopy(p1.positions)
        p2_pos = deepcopy(p2.positions)
        for coin, position in p2_pos.items():
            side = position['side']

            if coin not in p1_pos:
                logger.info(f"removing {coin} {position['sz']} from {p2.address[:5]}")
                if side == constants.LONG:
                    p2.market_sell(coin, position['sz'])
                else:
                    p2.market_buy(coin, position['sz'])
            elif p1_pos[coin]['sz'] < position['sz']:
                logger.info(f"removing partially {coin} {position['sz']-p1_pos[coin]['sz']} from {p2.address[:5]}")
                if side == constants.LONG:
                    r = p2.market_sell(coin, position['sz']-p1_pos[coin]['sz'])
                else:
                    r = p2.market_buy(coin, position['sz']-p1_pos[coin]['sz'])

                if r['code'] == constants.ERROR_FIELD:
                    if side == constants.LONG:
                        p2.market_sell(coin, position['sz'])
                    else:
                        p2.market_buy(coin, position['sz'])


            
            


                

    def close_position(self, pair: Tuple[Hyperliquid, Hyperliquid], coin: str):
        p1, p2 = pair 

        p1_side = p1.positions[coin]['side']
        sz = p1.positions[coin]['sz']

        logger.info(f"CLOSING {coin} {sz} BECAUSE IT TIMED OUT")
        if p1_side == constants.LONG:
            ts = [threading.Thread(target=p1.maker_sell, args=(coin, sz)), threading.Thread(target=p2.maker_buy, args=(coin, sz))] 
        else:
            ts = [threading.Thread(target=p1.maker_buy, args=(coin, sz)), threading.Thread(target=p2.maker_sell, args=(coin, sz))]
        
        for t in ts:
            t.start()
        for t in ts:
            t.join()


        start_time = time.time()
        while coin in p1.orders or coin in p2.orders:
            if coin not in p1.orders:
                p2.cancel(coin, p2.orders.get(coin, {}).get('oid', 0))
                if coin in p2.orders and p1_side == constants.LONG:
                    p2.market_buy(coin, p2.orders[coin]['sz'])
                elif coin in p2.orders:
                    p2.market_sell(coin, p2.orders[coin]['sz'])
                break
            
            elif coin not in p2.orders:
                p1.cancel(coin, p1.orders.get(coin, {}).get('oid', 0))
                if coin in p1.orders and p1_side == constants.LONG:
                    p1.market_sell(coin, p1.orders[coin]['sz'])
                elif coin in p1.orders:
                    p1.market_buy(coin, p1.orders[coin]['sz'])
                break

            elif time.time() - start_time > 20:
                ts_1 = [threading.Thread(target=p1.cancel, args=(coin, p1.orders.get(coin, {}).get('oid', 0))), threading.Thread(target=p2.cancel, args=(coin, p2.orders.get(coin, {}).get('oid', 0)))]
                for t in ts_1:
                    t.start()
                for t in ts_1:
                    t.join()

                if p1_side == constants.LONG:
                    ts = [threading.Thread(target=p1.maker_sell, args=(coin, p1.orders[coin]['sz'])), threading.Thread(target=p2.maker_buy, args=(coin, p2.orders[coin]['sz']))] 
                else:
                    ts = [threading.Thread(target=p1.maker_buy, args=(coin, p1.orders[coin]['sz'])), threading.Thread(target=p2.maker_sell, args=(coin, p2.orders[coin]['sz']))]
                
                for t in ts:
                    t.start()
                for t in ts:
                    t.join()

                start_time = time.time()
            
    def update_positions(self, perp_pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = perp_pair

        threads = [threading.Thread(target=p1.update_positions), threading.Thread(target=p2.update_positions)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()
    
    def clean(self):
        for p in self.pairs:
            self.clear_perps_sync(p)

    def kill(self):
        self.clean()
        
        exit()

    def check_balances(self, pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = pair 
        
        p1_balance = p1.get_balance()['available']
        p2_balance = p2.get_balance()['available']

        diff = abs(p1_balance - p2_balance)
        ratio_percents = diff / min(p1_balance, p2_balance)*100
        logger.info(f"{p1.address[:5]} {p2.address[:5]} LIQUIDITY RATIO {round(ratio_percents, 2)}")
        is_rebalance = p1.config['rebalance']
        if is_rebalance and ratio_percents >= p1.config['transfer_ratio_percents']:
            if p1_balance > p2_balance:
                logger.info(f"{p1.address[:5]}:{round(p1_balance, 2)} > {p2.address[:5]}:{round(p2_balance, 2)}")
                send = round(diff / 2, 2)
                
                if p1.config['transfer_type'] == "hyperliquid":
                    r = p1.usd_transfer(send, p2.address)

                    if r.get('status') == 'ok':
                        logger.info(f"successfully transfered {send} from {p1.address[:5]} to {p2.address[:5]}")
                    else:
                        logger.error(f"{p1.address[:5]} {send} {r}")
                else:
                    logging.info(f"started withdrawing from f{p1.address[:5]}")
                    p1.withdraw_from_bridge(send, p1.address)
                    logging.info(f"tried to send {send} from f{p1.address[:5]} to {p2.address[:5]}")
                    self.contracts.send_usdc(p1.wallet, send, p2.address)
                    logging.info(f"tried to deposit {send} from f{p2.address}")
                    r = self.contracts.deposit(p2.wallet, send)

                    if r:
                        logger.info(f"successfully transfered {send} from {p1.address[:5]} to {p2.address[:5]}")
                    else:
                        logger.error(f"{p1.address[:5]} {send} {r}")
            else:
                logger.info(f"{p2.address[:5]}:{round(p2_balance, 2)} > {p1.address[:5]}:{round(p1_balance, 2)}")

                send = round(diff / 2, 2)
                if p1.config['transfer_type'] == 'hyperliquid':
                    r = p2.usd_transfer(send, p1.address)

                    if r.get('status') == 'ok':
                        logger.info(f"successfully transfered {send} from {p2.address[:5]} to {p1.address[:5]}")
                    else:
                        logger.error(f"{p2.address[:5]} {send} {r}")
                else:
                    logging.info(f"started withdrawing from f{p2.address[:5]}")
                    p2.withdraw_from_bridge(send, p2.address)
                    logging.info(f"tried to send {send} from f{p2.address[:5]} to {p1.address[:5]}")
                    self.contracts.send_usdc(p2.wallet, send, p1.address)
                    logging.info(f"tried to deposit {send} from f{p1.address}")
                    r = self.contracts.deposit(p1.wallet, send)

                    if r:
                        logger.info(f"successfully transfered {send} from {p1.address[:5]} to {p2.address[:5]}")
                    else:
                        logger.error(f"{p1.address[:5]} {send} {r}")
                    

    def load_user_states(self, pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = pair 

        threads = [threading.Thread(target=p1.load_user_state), threading.Thread(target=p2.load_user_state)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()