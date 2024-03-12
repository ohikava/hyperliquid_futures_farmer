import perp.config as config 
import perp.constants as constants 
from perp.hyperliquid.hyperliquid_types import Meta, WsMsg
from perp.hyperliquid.hyperliquid_api import API
from perp.hyperliquid.hyperliquid_signing import OrderType, OrderRequest, OrderWire, CancelRequest, get_timestamp_ms, order_request_to_order_wire, order_wires_to_order_action, sign_l1_action
from perp.hyperliquid.hyperliquid_base import HyperliquidBase
from perp.hyperliquid.ws import WebsocketManager
from perp.utils.types import Proxies, Balance, UnfilledOrder, RepeatingOrder, Position, WalletConfig, MakerOrder
from perp.utils.funcs import handle_order_results

import perp.randomizer as randomizer
import eth_account
import logging 
from typing import Optional, Any, List, cast, Dict, Callable
import time 

logger = logging.getLogger(__name__)


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
            if coin in self.positions and self.positions[coin]["side"] != side:
                self.positions.pop(coin)
                # DEBUG
                print(self.positions)
                continue 
            elif coin in self.positions:
                self.positions[coin]['entry_price'] += fill['px']
                self.positions[coin]['entry_price'] /= 2
                self.positions[coin]['sz'] += fill['sz']
                continue 

            if coin in self.maker_orders:
                opposite_side = 'short' if fill['side'] == 'B' else 'long'
                oid = self.maker_orders[coin][opposite_side]
                self.cancel(coin, oid)

                self.maker_orders.pop(coin)

            self.positions[coin] = {
                'entry_price': fill['px'],
                'fee': fill['fee'],
                'lifetime': randomizer.random_int(self.config["min_position_lifetime"], self.config["max_position_lifetime"]),
                 "open_time": time.time(),
                "side": side,
                "sz": fill["sz"]
            }
            # DEBUG
            print(self.positions)

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
            
    def open_opposite_position(self, fill):
        coin = fill["coin"]
        sz = fill['sz']
        side = fill['side']

        if side == 'A':
            res = self.market_buy(coin, sz)
        else:
            res = self.market_sell(coin, sz)

        if type(res) == dict and res["order_status"] == "filled":
            self.positions[coin] = {
                'entry_price': res['px'],
                'fee': res['fee'],
                'lifetime': randomizer.random_int(self.config["min_position_lifetime"], self.config["max_position_lifetime"]),
                "open_time": time.time(),
                "side": constants.LONG if side == "A" else constants.SHORT,
                "sz": res["sz"]
            }

    """Maker"""
    def open_maker_position(self, coin, sz, ):
        self.maker_orders[coin] = {
            'sz': sz 
        }

        self.maker_orders[coin]['long'] = self.maker_buy(coin, sz)

        if coin in self.maker_orders:
            self.maker_orders[coin]['short'] = self.maker_sell(coin, sz)

        time.sleep(20)
        while coin in self.maker_orders:

            self.cancel(coin, self.maker_orders[coin]['long'])
            self.cancel(coin, self.maker_orders[coin]['short'])

            self.maker_orders[coin]['long'] = self.maker_buy(coin, sz)

            if coin in self.maker_orders:
                self.maker_orders[coin]['short'] = self.maker_sell(coin, sz)
            time.sleep(20)


            



        print(f"{coin} is open")
    
    def close_maker_position(self, coin: str):
        side = self.positions[coin]["side"]
        sz = self.positions[coin]["sz"]

        if side == constants.LONG:
            oid = self.maker_sell(coin, sz)
        else:
            oid = self.maker_buy(coin, sz)
        return oid 
        
    def maker_buy(self, coin, sz):
        prices = self._prices(coin)
        tick = self.price_decimals[coin]
        px = prices[0] - 2 * 10 ** (-tick)
        order_result = self._order(coin, True, sz, px, order_type={"limit": {"tif": "Alo"}}, reduce_only=False)
        return handle_order_results(order_result)

    def maker_sell(self, coin, sz):
        prices = self._prices(coin)
        tick = self.price_decimals[coin]
        px = prices[1] + 2 * 10 ** (-tick)
        order_result = self._order(coin, False, sz, px, order_type={"limit": {"tif": "Alo"}}, reduce_only=False)
        return handle_order_results(order_result)
    
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
        order_result = self._order(coin, is_buy, sz, px, order_type={"limit": {"tif": "Ioc"}}, reduce_only=False)
        return handle_order_results(order_result)
    
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
        return self.post("/exchange", payload)
    
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
            uid = self.maker_buy(coin, sz)
            self.repeating_orders[coin]['uid'] = uid 
        else:
            uid = self.maker_sell(coin, sz) 
            self.repeating_orders[coin]['uid'] = uid 
        
        time.sleep(8)
        while coin in self.repeating_orders:
            logger.info("Failed to fill order, creating new one for {coin} position. Creating new order")
            self.cancel(coin, self.repeating_orders[coin]['uid'])

            if side == constants.LONG:
                uid = self.maker_buy(coin, sz)
                self.repeating_orders[coin]['uid'] = uid
            else:
                uid = self.maker_sell(coin, sz) 
                self.repeating_orders[coin]['uid'] = uid 

            time.sleep(8)
