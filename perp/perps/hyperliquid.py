import perp.config as config 
import perp.constants as constants 
from perp.utils.hyperliquid_types import Cloid, Meta
from perp.utils.hyperliquid_api import API
from perp.utils.hyperliquid_signing import OrderType, OrderRequest, OrderWire, \
                                        get_timestamp_ms, order_request_to_order_wire, order_wires_to_order_action, \
                                        sign_l1_action
import eth_account
import logging 
from typing import Optional, Any, List, cast, TypedDict
import time 
import os 
from dotenv import load_dotenv
import json 


load_dotenv()




logger = logging.getLogger(__name__)
HYPERLIQUID_TAKER_FEE = 0.025 / 100
HYPERLIQUID_MAKER_FEE = -0.002 / 100

Proxies = TypedDict(
    'Proxies',
    {
        "https": str,
        "http": str
    }
)

class Hyperliquid(API):
    def __init__(self, private_key: str, proxies: Proxies):
        super().__init__(proxies=proxies)

        self.wallet = eth_account.Account.from_key(private_key)
        self.vault_address = None
        self.meta = self.meta()
        self.coin_to_asset = {asset_info["name"]: asset for (asset, asset_info) in enumerate(self.meta["universe"])}
        self.last_fill = {} 
        self.size_decimals = config.HL_SIZE_DECIMALS
        self.price_decimals = config.HL_PRICE_DECIMALS
        self.address = self.wallet.address
        self.name = 'hyperliquid'

    def market_buy(self, coin, sz, px=None):
        return self.market_open(coin, True, sz, px)
    
    def market_sell(self, coin, sz, px=None):
        return self.market_open(coin, False, sz, px)
    
    def get_mid_price(self, coin):
        return float(self.all_mids()[coin])
    
    def buy(self, coin, sz, px):
        order_result = self.order(coin, True, sz, px, order_type={"limit": {"tif": "Ioc"}}, reduce_only=False, cloid=None)

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

    def sell(self, coin, sz, px):
        order_result = self.order(coin, False, sz, px, order_type={"limit": {"tif": "Ioc"}}, reduce_only=False, cloid=None)

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

        # Get aggressive Market Price
        px = self._slippage_price(coin, is_buy, slippage, px)
        # Market Order is an aggressive Limit Order IoC
        order_result = self.order(coin, is_buy, sz, px, order_type={"limit": {"tif": "Ioc"}}, reduce_only=False, cloid=cloid)

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
    
    def order(
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
        return self.bulk_orders([order])
    
    def bulk_orders(self, order_requests: List[OrderRequest]) -> Any:
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
    
    def meta(self) -> Meta:
        return cast(Meta, self.post("/info", {"type": "meta"}))
    
    def all_mids(self) -> dict:
        return self.post("/info", {"type": "allMids"})
        
    def _slippage_price(
        self,
        coin: str,
        is_buy: bool,
        slippage: float,
        px: Optional[float] = None,
    ) -> float:

        if not px:
            # Get midprice
            px = float(self.all_mids()[coin])
        # Calculate Slippage
        px *= (1 + slippage) if is_buy else (1 - slippage)
        # We round px to 5 significant figures and 6 decimals
        return round(float(f"{px:.5g}"), 6)
    
    @classmethod
    def from_row(cls, row:str, proxies: Proxies):
        row = row.strip()
        return cls(private_key=row, proxies=proxies)
    
