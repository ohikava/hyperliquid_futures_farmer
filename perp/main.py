from copy import deepcopy
from perp.hyperliquid.main import Hyperliquid
from perp.observer import Observer
from perp.utils.funcs import load_json_file, run_with_traceback, dump_json
from perp.utils.types import PerpPair, Position, ClosedPosition
import perp.randomizer as randomizer
import perp.config as config
import perp.constants as constants
import time 
from os.path import join
from typing import Tuple , List
import logging 
import os 
import traceback 
import threading
from perp.contracts import Contracts
from perp.stats import get_profit
from perp.encode import load_encoded
from getpass import getpass
logger = logging.getLogger(__name__)


wallets_encoded = "wallets_encoded"
wallets_configs = "wallets_configs"
positions_state_file = "positions_state.json"

class Main():
    def __init__(self):
        self.observer = Observer()
        self.pairs: List[Tuple[Hyperliquid, Hyperliquid]] = []
        self.last_closed_position = ()
        password = getpass()
        wallets = os.listdir(wallets_encoded)
        for wallet in wallets:
            pk = load_encoded(password, os.path.join(wallets_encoded, wallet))
            conf = load_json_file(os.path.join(wallets_configs, wallet + ".json"))
            wallet_data = {**pk, **conf}
            self.add_wallets(wallet_data)
        self.contracts = Contracts()
        self.last_notification_time = time.time()
        try:
            self.observer.observer_stats(*get_profit())
        except:
            pass 
        threading.Thread(target=self.observe).start()

    def observe(self):
        try:
            self.observer.observer_stats(*get_profit())
            for pair in self.pairs:
                p1, p2 = pair 
                self.observer.porftolio_state(p1.address, p2.address, p1.get_portfolio(), p2.get_portfolio())
            
                msg = f"{p1.address[:5]}\n"
                msg += f"USDC Balance: {round(self.contracts.usdc_contract.functions.balanceOf(p1.address).call() / 10**constants.USDC_DECIMALS, 2)}\n"
                msg += f"ETH Balance: {round(self.contracts.w3.from_wei(self.contracts.w3.eth.get_balance(p1.address), 'ether'), 6)}\n"
                msg += f"\n{p2.address[:5]}\n"

                msg += f"USDC Balance: {round(self.contracts.usdc_contract.functions.balanceOf(p2.address).call() / 10**constants.USDC_DECIMALS, 2)}\n"
                msg += f"ETH Balance: {round(self.contracts.w3.from_wei(self.contracts.w3.eth.get_balance(p2.address), 'ether'), 6)}"

                self.observer.send_sync_message(msg)
                time.sleep(5)
        except:
            logger.error(traceback.format_exc())
        while True:
            if time.time() - self.last_notification_time > config.NOTIFY_INTERVAL * 60:
                self.last_notification_time = time.time()
                try:
                    self.observer.observer_stats(*get_profit())
                    for pair in self.pairs:
                        p1, p2 = pair 
                        self.observer.porftolio_state(p1.address, p2.address, p1.get_portfolio(), p2.get_portfolio())
                        time.sleep(5)
                except Exception:
                    logger.error(traceback.format_exc())
                    pass 
    
    def add_wallets(self, wallets: dict):
        perp1 = wallets["perp1"]
        perp2 = wallets["perp2"]
        wallets_config = wallets['config']

        perp1: Hyperliquid = Hyperliquid.from_row(perp1['secret'], proxies=perp1['proxies'], wallet_config=wallets_config)
        perp2: Hyperliquid = Hyperliquid.from_row(perp2['secret'], proxies=perp2['proxies'], wallet_config=wallets_config)

        self.pairs.append((perp1, perp2))
        perp1.close_all_orders()
        perp2.close_all_orders()

    def run(self):
        ix = 0
        while True:
            print(f"Iteration #{ix} has began")
            positions_state = load_json_file(positions_state_file)
            
            for pair in self.pairs:
                self.load_user_states(pair)
                self.update_positions(pair)
                self.check_balances(pair)
                self.remove_positions(pair)
                
                time.sleep(5)
                p1, p2 = pair 

                if p1.address not in positions_state:
                    positions_state[p1.address] = {}

                dump_json(positions_state_file, positions_state)
     
                open_positions = set(p1.positions.keys()) & set(p2.positions.keys())

                if time.time() - positions_state[p1.address].get("open_time", time.time()) > p1.config['positions_lifetime'] * 60:
                    for coin in open_positions:
                        run_with_traceback(self.close_position, logger, pair, coin)
                    positions_state[p1.address] = {}
                    dump_json(positions_state_file, positions_state)
                    time.sleep(2)
                    open_positions = set(p1.positions.keys()) & set(p2.positions.keys())

                if not positions_state[p1.address]:
                    leverage= p1.config['leverage']
                    balance_p1 = p1.get_balance()
                    balance_p2 = p2.get_balance()

                    min_eq = min(balance_p1['accountValue'], balance_p2['accountValue'])
                    total = min_eq * leverage
                    positions_state[p1.address]['sz_usd'] = round(total / p1.config['n_positions'], 2)
                    dump_json(positions_state_file, positions_state)

                sz_usd = positions_state[p1.address]['sz_usd']

                n_new = p1.config['n_positions'] - len(open_positions)
                n_new = max(0, n_new)
                    
                coins = randomizer.random_coins(open_positions, n_new)
                current_sides = [p1.positions[i]['side'] for i in open_positions]
                sides = randomizer.random_sides(current_sides, len(coins))
                sides = {coin: side for coin, side in zip(coins, sides)}

                for coin, side in sides.items():
                    run_with_traceback(self.open_position, logger, pair, coin, side, sz_usd)
                    time.sleep(2)

                    self.load_user_states(pair)
                    self.update_positions(pair)
                    p1, p2 = pair 
                    
                    p1_pos = p1.positions.get(coin, {})
                    p2_pos = p2.positions.get(coin, {})

                    if p1_pos.get("sz") == p2_pos.get("sz") and p1_pos.get("side") != p2_pos.get("side"):
                        positions_state[p1.address]['open_time'] = time.time()
                        dump_json(positions_state_file, positions_state)
                    else:
                        if p1_pos.get("side") == constants.LONG:
                            p1.market_sell(coin, p1_pos.get("sz"))
                            logging.info(f"{p1.address} closing {coin} {p1_pos.get('sz')} long because position opened wrong")
                        elif p1_pos.get("side") == constants.SHORT:
                            p1.market_buy(coin, p1_pos.get("sz"))
                            logging.info(f"{p1.address} closing {coin} {p1_pos.get('sz')} short because position opened wrong")

                        if p2_pos.get("side") == constants.LONG:
                            p2.market_sell(coin, p2_pos.get("sz"))
                            logging.info(f"{p2.address} closing {coin} {p2_pos.get('sz')} long because position opened wrong")
                        elif p2_pos.get("side") == constants.SHORT:
                            p2.market_buy(coin, p2_pos.get("sz"))
                            logging.info(f"{p2.address} closing {coin} {p2_pos.get('sz')} short because position opened wrong")


                    time.sleep(2)
            logger.info(f"positions state: {positions_state}")
            ix += 1
            time.sleep(30 * 1)

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

    def open_position(self, perp_pair: Tuple[Hyperliquid, Hyperliquid], coin: str, p1_side: str, sz_usd: float):
        logger.info(f"try to open {coin} for {sz_usd}$")
        p1, p2 = perp_pair

        mid_price = p1.get_mid_price(coin)
        position_size = sz_usd / mid_price
        min_decimals = p1.size_decimals[coin]
        sz = round(position_size, min_decimals)

        if p1_side == constants.LONG:
            p1.market_buy(coin, sz)
        else:
            p1.market_sell(coin, sz)

        start_time = time.time()
        while coin in p1.orders:
            if time.time() - start_time > 30:
                logger.error(f"{p1.address[:5]} can't open {coin} {sz} {p1_side}")
                orders = p1.get_open_orders()
                for order in orders:
                    if order['coin'] == coin:
                        p1.cancel(coin, order['oid'])
                        p1.orders.pop(coin)
                        logger.info(f"{p1.address[:5]} removed {order['side']} order with size {order['sz']}")
                return  
            
        p2_side = constants.SHORT if p1_side == constants.LONG else constants.LONG
        if p2_side == constants.LONG:
            p2.market_buy(coin, sz)
        else:
            p2.market_sell(coin, sz)

        start_time = time.time()
        while coin in p2.orders:
            if time.time() - start_time > 60:
                logger.error(f"{p2.address[:5]} can't open {coin} {sz} {p2_side}")
                orders = p2.get_open_orders()
                for order in orders:
                    if order['coin'] == coin:
                        p2.cancel(coin, order['oid'])
                        p2.orders.pop(coin)
                        logger.info(f"{p2.address[:5]} removed {order['side']} order with size {order['sz']}")
                break  
        
                

    def remove_positions(self, pair: Tuple[Hyperliquid, Hyperliquid]):
        logger.info(f"try to remove positions")
        p1, p2 = pair 

        p1_pos = deepcopy(p1.positions)
        p2_pos = deepcopy(p2.positions)

        for coin, position in p1_pos.items():
            side = position['side']
            if coin not in p2_pos:
                logger.info(f"removing {coin} {position['sz']} from {p1.address[:5]} as it is not hedged")

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
            
            elif round(position['sz'] - p2_pos[coin]['sz'], p1.size_decimals[coin]) > 0:
                difference = round(position['sz'] - p2_pos[coin]['sz'], p1.size_decimals[coin])

                logger.info(f"removing partially {coin} {difference} from {p1.address[:5]}")

                if side == constants.LONG:
                    r = p1.market_sell(coin, difference )
                else:
                    r = p1.market_buy(coin, difference )
                if r['code'] == constants.ERROR_FIELD:
                    if side == constants.LONG:
                        p1.market_sell(coin, position['sz'])
                    else:
                        p1.market_buy(coin, position['sz'])

                    if side == constants.LONG:
                        p2.market_buy(coin, p2_pos[coin]['sz'])
                    else:
                        p2.maker_sell(coin, p2_pos[coin]['sz'])

                    
        time.sleep(5)
        p1_pos = deepcopy(p1.positions)
        p2_pos = deepcopy(p2.positions)
        for coin, position in p2_pos.items():
            side = position['side']

            if coin not in p1_pos:
                logger.info(f"removing {coin} {position['sz']} from {p2.address[:5]} as it is not hedged")
                if side == constants.LONG:
                    p2.market_sell(coin, position['sz'])
                else:
                    p2.market_buy(coin, position['sz'])

            elif round(position['sz'] - p1_pos[coin]['sz'], p1.size_decimals[coin]) > 0:
                difference = round(position['sz'] - p1_pos[coin]['sz'], p1.size_decimals[coin]) 
                logger.info(f"removing partially {coin} {difference} from {p2.address[:5]}")
                if side == constants.LONG:
                    r = p2.market_sell(coin, difference)
                else:
                    r = p2.market_buy(coin, difference)

                if r['code'] == constants.ERROR_FIELD:
                    if side == constants.LONG:
                        p2.market_sell(coin, position['sz'])
                    else:
                        p2.market_buy(coin, position['sz'])  

                    if side == constants.LONG:
                        p1.market_buy(coin, p1_pos[coin]['sz'])
                    else:
                        p1.market_sell(coin, p1_pos[coin]['sz'])   

    def close_position(self, pair: Tuple[Hyperliquid, Hyperliquid], coin: str):
        logger.info(f"try to close {coin}")
        p1, p2 = pair

        p1_pos= p1.positions.get(coin, {})
        p1_sz = p1_pos.get('sz', 0)
        p1_side = p1_pos.get('side')

        if not p1_side:
            logging.error(f"There is no {coin} in {p1.address[:5]} positions")
            return 
        
        if p1_side == constants.LONG:
            p1.market_sell(coin, p1_sz)
        else:
            p1.market_buy(coin, p1_sz)

        start_time = time.time()
        while coin in p1.positions:
            if time.time() - start_time > 60:
                logger.error(f"{p1.address[:5]} can't close {coin} {p1_sz} {p1_side}")
                orders = p1.get_open_orders()
                for order in orders:
                    if order['coin'] == coin:
                        p1.cancel(coin, order['oid'])
                        p1.orders.pop(coin)
                        logger.info(f"{p1.address[:5]} removed {order['side']} order with size {order['sz']}")
                return 
        
        p2_pos= p2.positions.get(coin, {})
        p2_sz = p2_pos.get('sz')
        p2_side = p2_pos.get('side')

        if not p1_side:
            logging.error(f"There is not {coin} in {p2.address[:5]} positions")
            return 
        
        if p2_side == constants.LONG:
            p2.market_sell(coin, p2_sz)
        else:
            p2.market_buy(coin, p2_sz)
        
        start_time = time.time()
        while coin in p2.positions:
            if time.time() - start_time > 60:
                logger.error(f"{p2.address[:5]} can't close {coin} {p2_sz} {p2_side}")
                orders = p2.get_open_orders()
                for order in orders:
                    if order['coin'] == coin:
                        p2.cancel(coin, order['oid'])
                        p2.orders.pop(coin)
                        logger.info(f"{p2.address[:5]} removed {order['side']} order with size {order['sz']}")
                break 
                
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
                    logger.info(f"started withdrawing from f{p1.address[:5]}")
                    p1.withdraw_from_bridge(send+1, p1.address)
                    logger.info(f"tried to send {send} from f{p1.address[:5]} to {p2.address[:5]}")
                    self.contracts.send_usdc(p1.wallet, send, p2.address)
                    logger.info(f"tried to deposit {send} from f{p2.address}")
                    r = self.contracts.deposit(p2.wallet, send)

                    if r:
                        logger.info(f"successfully transfered {send} from {p1.address[:5]} to {p2.address[:5]}")
                    else:
                        logger.error(f"{p1.address[:5]} {send} {r}")
                    time.sleep(15)
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
                    logger.info(f"started withdrawing from f{p2.address[:5]}")
                    p2.withdraw_from_bridge(send+1, p2.address)
                    logger.info(f"tried to send {send} from f{p2.address[:5]} to {p1.address[:5]}")
                    self.contracts.send_usdc(p2.wallet, send, p1.address)
                    logger.info(f"tried to deposit {send} from f{p1.address}")
                    r = self.contracts.deposit(p1.wallet, send)

                    if r:
                        logger.info(f"successfully transfered {send} from {p1.address[:5]} to {p2.address[:5]}")
                    else:
                        logger.error(f"{p1.address[:5]} {send} {r}")
                    time.sleep(15)
                    
    def load_user_states(self, pair: Tuple[Hyperliquid, Hyperliquid]):
        p1, p2 = pair 

        threads = [threading.Thread(target=p1.load_user_state), threading.Thread(target=p2.load_user_state)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()