import perp.config as config 
import perp.constants as constants 
from perp.hyperliquid.hyperliquid_types import Cloid, Meta, WsMsg
from perp.hyperliquid.hyperliquid_api import API
from perp.hyperliquid.hyperliquid_signing import OrderType, OrderRequest, OrderWire, \
                                        get_timestamp_ms, order_request_to_order_wire, order_wires_to_order_action, \
                                        sign_l1_action
from perp.hyperliquid.hyperliquid_base import HyperliquidBase
from perp.hyperliquid.ws import WebsocketManager
from perp.utils.types import Proxies, Balance
import eth_account
import logging 
from typing import Optional, Any, List, cast
import time 
import json 

logger = logging.getLogger(__name__)
HYPERLIQUID_TAKER_FEE = 0.025 / 100
HYPERLIQUID_MAKER_FEE = -0.002 / 100

class Hyperliquid(API, HyperliquidBase):
    def __init__(self, private_key: str, proxies: Proxies):
        super().__init__(proxies=proxies)

        self.wallet = eth_account.Account.from_key(private_key)
        self.vault_address = None
        self._meta = self._meta()
        self.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in enumerate(self._meta["universe"])}
        self.last_fill = {} 
        self.size_decimals = config.SIZE_DECIMALS
        self.price_decimals = config.PRICE_DECIMALS
        self.address = self.wallet.address
        self.name = 'hyperliquid'

        self.ws = WebsocketManager(self.base_url, proxies.get('http'))
        self.ws.start()

        self.ws.subscribe({ "type": "userEvents", "user": f"{self.address}" }, self.on_user_event)
        
    def on_user_event(self, msg: WsMsg):
        print(msg)


    def market_buy(self, coin, sz, px=None):
        return self.market_open(coin, True, sz, px)
    
    def market_sell(self, coin, sz, px=None):
        return self.market_open(coin, False, sz, px)
    
    def get_mid_price(self, coin):
        return float(self._all_mids()[coin])
    
    def maker_buy(self, coin, sz):
        prices = self.prices(coin)
        lowest_px = prices[0]

        tick = self.price_decimals[coin]
        print(lowest_px)
        px = lowest_px - 2 * 10 ** (-tick)
        print(px)

        return self.buy(coin, sz, px)

    def maker_sell(self, coin, sz):
        prices = self.prices(coin)
        highest_px = prices[1]

        tick = self.price_decimals[coin]
        print(highest_px)
        px = highest_px + 2 * 10 ** (-tick)
        print(px)

        return self.sell(coin, sz, px)

    def buy(self, coin, sz, px):
        order_result = self._order(coin, True, sz, px, order_type={"limit": {"tif": "Alo"}}, reduce_only=False, cloid=None)

        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    out = {
                        "px": float(filled['avgPx']),
                        "sz": float(filled["totalSz"]),
                        "order_status": "filled",
                        "side": constants.LONG,
                        "coin": coin,
                        "fill_time": time.time(),
                        'perp': 'hyperliquid',
                        'fee': HYPERLIQUID_TAKER_FEE * float(filled["totalSz"]) * float(filled["avgPx"])
                    }
                    self.last_fill = out
                    return out 
                
                except KeyError:
                    if "resting" in status:
                        resting = status['resting']
                        logger.info(f"Order #{coin} is open")
                        return {}
                    else:
                        logger.error(f"status {json.dumps(status)}")
                        return {}
        else:
            logger.error(f'status {order_result["status"]}')
            return {}

    def prices(self, coin):
       depth = self.post("/info", {"type": "l2Book", "coin": coin})
       return float(depth['levels'][0][0]['px']), float(depth['levels'][1][0]['px'])

    def sell(self, coin, sz, px):
        order_result = self._order(coin, False, sz, px, order_type={"limit": {"tif": "Alo"}}, reduce_only=False, cloid=None)

        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    out = {
                        "px": float(filled['avgPx']),
                        "sz": float(filled["totalSz"]),
                        "order_status": "filled",
                        "side": constants.SHORT,
                        "coin": coin,
                        "fill_time": time.time(),
                        'perp': 'hyperliquid',
                        'fee': HYPERLIQUID_TAKER_FEE * float(filled["totalSz"]) * float(filled["avgPx"])
                    }
                    self.last_fill = out
                    return out 
                
                except KeyError:
                    if "resting" in status:
                        resting = status['resting']
                        logger.info(f"Order #{coin} is open")
                        return {}
                    else:
                        logger.error(f"status {json.dumps(status)}")
                        return {}
        else:
            logger.error(f'status {order_result["status"]}')
            return {}
    
    def market_open(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        px: Optional[float] = None,
        slippage: float = config.HL_SLIPPAGE,
        cloid: Optional[Cloid] = None,
    ) -> Any:

        px = self._slippage_price(coin, is_buy, slippage, px)
        order_result = self._order(coin, is_buy, sz, px, order_type={"limit": {"tif": "Ioc"}}, reduce_only=False, cloid=cloid)

        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    out = {
                        "px": float(filled['avgPx']),
                        "sz": float(filled["totalSz"]),
                        "order_status": "filled",
                        "side": constants.LONG if is_buy else constants.SHORT,
                        "coin": coin,
                        "fill_time": time.time(),
                        'perp': 'hyperliquid',
                        'fee': HYPERLIQUID_TAKER_FEE * float(filled["totalSz"]) * float(filled["avgPx"])
                    }
                    self.last_fill = out
                    return out 
                
                except KeyError:
                    if "resting" in status:
                        resting = status['resting']
                        logger.info(f"Order #{coin} is open")
                        return {}
                    else:
                        logger.error(f"status {json.dumps(status)}")
                        return {}
        else:
            logger.error(f'status {order_result["status"]}')
            return {}
    
    def _order(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        limit_px: float,
        order_type: OrderType,
        reduce_only: bool = False,
        cloid: Optional[Cloid] = None,
    ) -> Any:
        order: OrderRequest = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "limit_px": limit_px,
            "order_type": order_type,
            "reduce_only": reduce_only,
        }
        if cloid:
            order["cloid"] = cloid
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
    
    @classmethod
    def from_row(cls, row:str, proxies: Proxies):
        row = row.strip()
        return cls(private_key=row, proxies=proxies)
    
    def get_balance(self) -> Balance:
        user_state = self._get_user_state()
        return {
            "accountValue": user_state['marginSummary']['accountValue'],
            'totalMarginUsed': user_state['marginSummary']['totalMarginUsed'],
            "available": user_state['withdrawable'] 
        }

    def _get_user_state(self):
        return self.post("/info", {"type": "clearinghouseState", "user": self.address})

    def get_positions(self):
        user_state = self._get_user_state()
        return user_state["assetPositions"]
    
    def transfer(self, sz: float, destination: str):
        pass    

