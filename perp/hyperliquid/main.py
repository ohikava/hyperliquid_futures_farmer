from copy import copy, deepcopy
import perp.config as config 
import perp.constants as constants 
from perp.hyperliquid.hyperliquid_types import Meta, WsMsg
from perp.hyperliquid.hyperliquid_api import API
from perp.hyperliquid.hyperliquid_signing import OrderType, OrderRequest, OrderWire, CancelRequest, get_timestamp_ms, order_request_to_order_wire, order_wires_to_order_action, sign_l1_action
from perp.hyperliquid.hyperliquid_base import HyperliquidBase
from perp.hyperliquid.ws import WebsocketManager
from perp.utils.types import Proxies, Balance, UnfilledOrder, RepeatingOrder, Position, WalletConfig, MakerOrder, ClosedPosition
from perp.utils.funcs import handle_order_results
from perp.observer import Observer

import perp.randomizer as randomizer
import eth_account
import logging 
from typing import Optional, Any, List, cast, Dict, Callable
import time 
import traceback 

logger = logging.getLogger(__name__)

observer = Observer()

class Hyperliquid(API, HyperliquidBase):
    def __init__(self, private_key: str, proxies: Proxies, wallet_config: WalletConfig):
        super().__init__(proxies=proxies)
        print(private_key)

        self.wallet = eth_account.Account.from_key(private_key)
        self.address = self.wallet.address
        self._meta = self._meta()
        self.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in enumerate(self._meta["universe"])}
        self.config = wallet_config 

        self.size_decimals = config.SIZE_DECIMALS
        self.price_decimals = config.PRICE_DECIMALS

        self.unfilled_orders: Dict[str, UnfilledOrder] = {}
        self.maker_orders: Dict[str, MakerOrder] = {}
        self.repeating_orders: Dict[str, RepeatingOrder] = {} # EXPERIMENTS
        self.positions: Dict[str, Position] = {}

        self.proxies = proxies

        self.ws = WebsocketManager(self.base_url, proxies.get('http'), self._reload_socket)
        self.ws.start()

        self.ws.subscribe({ "type": "userEvents", "user": f"{self.address}" }, self._on_user_event)

        self._user_event_update = None 
        self.closed_positions: Dict[str, ClosedPosition] = {}

        self.close = {}

    """Sockets and events"""
    def _reload_socket(self, _ws, *args, **kwargs):
        self.ws = WebsocketManager(self.base_url, self.proxies.get('http'), self._reload_socket)
        self.ws.start()

        self.ws.subscribe({ "type": "userEvents", "user": f"{self.address}" }, self._on_user_event)

    def _on_user_event(self, msg: WsMsg):
        data = msg['data']
        fills = data.get('fills', [])

        for fill in fills:
            coin = fill['coin']
            side = constants.LONG if fill['side'] == 'B' else constants.SHORT 
            observer.save_fill(fill, wallet=self.address)

            if coin in deepcopy(self.close):
                sz = float(fill['sz'])
                self.close[coin] -= sz 

                if self.close[coin] == 0.0:
                    self.close.pop(coin)

            if coin in deepcopy(self.positions):
                if self.positions[coin]["side"] != side:
                    new_sz = self.positions[coin]['sz'] - float(fill['sz'])
                    if new_sz == 0:
                        side_m = 1 if side == constants.LONG else -1
                        self.closed_positions[coin] = {
                        "fee": float(self.positions[coin]["fee"]) + float(fill["fee"]),
                        "pnl": side_m * (float(fill["px"]) - float(self.positions[coin]["entry_price"])) * float(self.positions[coin]["sz"]),
                        "side": constants.LONG
                        }   
                        self.positions.pop(coin)
                    else:
                        self.positions[coin]['sz'] -= float(fill['sz'])
                else:
                    self.positions[coin]['entry_price'] += float(fill['px'])
                    self.positions[coin]['entry_price'] /= 2
                    self.positions[coin]['sz'] += float(fill['sz'])
                    

                continue 


            if coin in deepcopy(self.maker_orders):
                new_sz = self.maker_orders[coin]['sz'] - float(fill['sz'])
                if new_sz == 0.0:
                    opposite_side = 'short' if fill['side'] == 'B' else 'long'
                    oid = self.maker_orders[coin][opposite_side]
                    self.cancel(coin, oid)

                    self.maker_orders.pop(coin)
                else:
                    self.maker_orders[coin]['sz'] = new_sz
                    self.maker_orders[coin]['side'] = constants.LONG if fill['side'] == 'B' else constants.SHORT
                

            self.positions[coin] = {
                'entry_price': float(fill['px']),
                'fee': float(fill['fee']),
                'lifetime': randomizer.random_int(self.config["min_position_lifetime"]*60, self.config["max_position_lifetime"]*60),
                 "open_time": time.time(),
                "side": side,
                "sz": float(fill["sz"])
            }
            # DEBUG
            # print(self.positions)

    def set_user_event_update(self, cb: Callable):
        self._user_event_update = cb

    """Orders"""
    def cancel(self, coin: str, oid: int) -> Any:
        return self._bulk_cancel([{"coin": coin, "oid": oid}])
    
    """Market"""
    def market_buy(self, coin, sz, px=None):
        return self._market_open(coin, True, sz, px)
    
    def market_sell(self, coin, sz, px=None):
        return self._market_open(coin, False, sz, px)

    """Maker"""
    def open_maker_position(self, coin, sz, ):
        self.maker_orders[coin] = {
            'sz': sz,
            'side': ''
        }

        start_time = None 
        while coin in self.maker_orders:
            if not start_time or time.time() - start_time > 20:
                if start_time:
                    self.cancel(coin, order_status_long.get("oid", -1))
                    self.cancel(coin, order_status_short.get("oid", -1))

                if coin not in self.maker_orders:
                    return 
                
                if self.maker_orders[coin]['side'] != constants.SHORT:
                    order_status_long = self.maker_buy(coin, self.maker_orders[coin]['sz'])

                    while order_status_long.get("code") == constants.ERROR_POST_ORDER:
                        order_status_long = self.maker_buy(coin, self.maker_orders[coin]['sz'])

                    if order_status_long.get("code") == constants.ERROR_FIELD:
                        self.maker_orders.pop(coin)
                        return constants.ERROR_FIELD
                    
                    self.maker_orders[coin]['long'] = order_status_long.get("oid", -1)

                if coin in self.maker_orders and self.maker_orders[coin]['side'] != constants.LONG:
                    order_status_short = self.maker_sell(coin, self.maker_orders[coin]['sz'])

                    while order_status_short.get("code") == constants.ERROR_POST_ORDER and coin in self.maker_orders:
                        order_status_short = self.maker_sell(coin, self.maker_orders[coin]['sz'])

                    if coin not in self.maker_orders:
                        self.cancel(coin, order_status_short.get("oid", -1))
                        return 

                    if order_status_short.get("code") == constants.ERROR_FIELD:
                        self.cancel(coin, self.maker_orders[coin]['long'])
                        self.maker_orders.pop(coin)
                        return constants.ERROR_FIELD
                    
                    self.maker_orders[coin]['short'] =order_status_short.get("oid", -1)
                    start_time = time.time()

                    

    def close_market_position(self, coin: str):
        side = self.positions[coin]["side"]
        sz = self.positions[coin]["sz"]

        if side == constants.LONG:
            order_result = self.market_sell(coin, sz)
        else:
            order_result = self.market_buy(coin, sz)
        return order_result 


    def close_maker_position(self, coin: str):
        side = self.positions[coin]["side"]
        sz = self.positions[coin]["sz"]

        if side == constants.LONG:
            oid = self.maker_sell(coin, sz).get("oid", -1)
        else:
            oid = self.maker_buy(coin, sz).get("oid", -1)
        return oid 
        
    def maker_buy(self, coin, sz):
        prices = self._prices(coin)
        tick = self.price_decimals[coin]
        tick_delta = 1 if coin in config.LOW_LIQUIDITY_COINS else 2
        px = prices[0] - tick_delta * 10 ** (-tick)
        order_result = self._order(coin, True, float(sz), float(px), order_type={"limit": {"tif": "Alo"}}, reduce_only=False)
        return handle_order_results(order_result, coin, sz)

    def maker_sell(self, coin, sz):
        prices = self._prices(coin)
        tick = self.price_decimals[coin]
        tick_delta = 1 if coin in config.LOW_LIQUIDITY_COINS else 2
        px = prices[1] + tick_delta * 10 ** (-tick)
        order_result = self._order(coin, False, float(sz), float(px), order_type={"limit": {"tif": "Alo"}}, reduce_only=False)
        return handle_order_results(order_result, coin, sz)
    
    """System"""
    def _prices(self, coin):
       depth = self.post("/info", {"type": "l2Book", "coin": coin})
       return float(depth['levels'][0][0]['px']), float(depth['levels'][1][0]['px'])
    
    def _market_open(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        px: Optional[float] = None,
        slippage: float = config.HL_SLIPPAGE,
    ) -> Any:
        px = self._slippage_price(coin, is_buy, slippage, px)
        order_result = self._order(coin, is_buy, float(sz), float(px), order_type={"limit": {"tif": "Ioc"}}, reduce_only=False)
        return handle_order_results(order_result, coin, sz)
    
    def _order(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        limit_px: float,
        order_type: OrderType,
        reduce_only: bool = False,
    ) -> Any:
        order: OrderRequest = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "limit_px": limit_px,
            "order_type": order_type,
            "reduce_only": reduce_only,
        }
        return self._bulk_orders([order])
    
    def _bulk_orders(self, order_requests: List[OrderRequest]) -> Any:
        order_wires: List[OrderWire] = [
            order_request_to_order_wire(order, self.coin_to_asset[order["coin"]]) for order in order_requests
        ]
        timestamp = get_timestamp_ms()

        order_action = order_wires_to_order_action(order_wires)

        signature = sign_l1_action(
            self.wallet,
            order_action,
            timestamp,
        )

        return self._post_action(
            order_action,
            signature,
            timestamp,
        )
    
    def _post_action(self, action, signature, nonce):
        payload = {
            "action": action,
            "nonce": nonce,
            "signature": signature,
            "vaultAddress": None,
        }
        logging.debug(payload)
        try:
            return self.post("/exchange", payload)
        except:
            logger.error(traceback.format_exc())
            logger.info(payload)

    
    def _bulk_cancel(self, cancel_requests: List[CancelRequest]) -> Any:
        timestamp = get_timestamp_ms()
        cancel_action = {
            "type": "cancel",
            "cancels": [
                {
                    "a": self.coin_to_asset[cancel["coin"]],
                    "o": cancel["oid"],
                }
                for cancel in cancel_requests
            ],
        }
        signature = sign_l1_action(
            self.wallet,
            cancel_action,
            timestamp,
        )

        return self._post_action(
            cancel_action,
            signature,
            timestamp,
        )
    def _meta(self) -> Meta:
        return cast(Meta, self.post("/info", {"type": "meta"}))
    
    def _all_mids(self) -> dict:
        return self.post("/info", {"type": "allMids"})
        
    def _slippage_price(
        self,
        coin: str,
        is_buy: bool,
        slippage: float,
        px: Optional[float] = None,
    ) -> float:

        if not px:
            px = float(self._all_mids()[coin])
        px *= (1 + slippage) if is_buy else (1 - slippage)
        return round(float(f"{px:.5g}"), 6)
    
    def _get_user_state(self):
        return self.post("/info", {"type": "clearinghouseState", "user": self.address})

    def get_open_orders(self):
        return self.post("/info", {"type": "openOrders", "user": self.address})
    
    """Wallets and Info"""
    def get_positions(self):
        user_state = self._get_user_state()
        return user_state["assetPositions"]
    
    def transfer(self, sz: float, destination: str):
        pass    

    @classmethod
    def from_row(cls, row:str, proxies: Proxies, **kwargs):
        row = row.strip()
        return cls(private_key=row, proxies=proxies, **kwargs)
    
    def get_balance(self) -> Balance:
        user_state = self._get_user_state()
        return {
            "accountValue": user_state['marginSummary']['accountValue'],
            'totalMarginUsed': user_state['marginSummary']['totalMarginUsed'],
            "available": user_state['withdrawable'] 
        }
    
    def get_mid_price(self, coin):
        return float(self._all_mids()[coin])
    
    """Experimental"""
    def repeating_maker(self, coin, sz, side):
        self.repeating_orders[coin] = {
                'side': side,
                'sz': sz,
        }

        if side == constants.LONG:
            uid = self.maker_buy(coin, sz).get("oid", -1)
            self.repeating_orders[coin]['uid'] = uid 
        else:
            uid = self.maker_sell(coin, sz).get("oid", -1) 
            self.repeating_orders[coin]['uid'] = uid 
        
        time.sleep(8)
        while coin in self.repeating_orders:
            logger.info("Failed to fill order, creating new one for {coin} position. Creating new order")
            self.cancel(coin, self.repeating_orders[coin]['uid'])

            if side == constants.LONG:
                uid = self.maker_buy(coin, sz).get("oid", -1)
                self.repeating_orders[coin]['uid'] = uid
            else:
                uid = self.maker_sell(coin, sz).get("oid", -1) 
                self.repeating_orders[coin]['uid'] = uid 

            time.sleep(8)

    def close_all_orders(self):
        open_orders = self.get_open_orders()

        for order in open_orders:
            self.cancel(order['coin'], order['oid'])

    def close_all_positions(self):
        open_positions = self.get_positions()

        for position in open_positions:
            coin = position.get('position', {}).get('coin', "")
            sz = abs(float(position.get('position', {}).get("szi", 0)))
            side = constants.LONG if float(position.get('position', {}).get("szi", 1)) > 0 else constants.SHORT 

            self.close[coin] = sz 
            if side == constants.LONG:
                logger.info(f"{coin} {sz} {self.market_sell(coin, sz)}")
            else:
                logger.info(f"{coin} {sz} {self.market_buy(coin, sz)}")
                
        

            
            
            
            

