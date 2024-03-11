from typing_extensions import TypedDict
from typing import Union, Dict, List
from perp.hyperliquid.hyperliquid_base import HyperliquidBase

Position = TypedDict(
    'Position',
    {
        "px": float,
        "sz": float,
        "order_status": str,
        "side": str,
        "coin": str,
        "fill_time": int,
        "perp": str,
        "fee": float,
        "position_lifetime": int 
    }
)

ClosedPositionInfo = TypedDict(
    'CLOSED_POSITION_INFO',
    {
        "perp1_profit": float,
        "perp2_profit": float,
        "perp1_fees": float,
        "perp2_fees": float
    }
)
PerpPair = TypedDict(
    "PerpPair",
    {
        'perp1': HyperliquidBase,
        'perp2': HyperliquidBase,
        'perp1_positions': Dict[str, Position],
        'perp2_positions': Dict[str, Position],
        "min_balance": float,
        "min_position_lifetime": int,
        "rebalance": bool ,
        "closed_position_info": List[ClosedPositionInfo],
        'max_open_positions': int,
        'leverage': int,
        'position_size': float 
    }
)

PerpStats = TypedDict(
    "PerpStats",
    {
        "perp1_address": str,
        "perp2_address": str,
        "perp1_fees": float,
        "perp2_fees": float,
        "perp1_profit": float,
        "perp2_profit": float
    }

)

Proxies = TypedDict(
    'Proxies',
    {
        "https": str,
        "http": str
    }
)

Perp = TypedDict(
    "Perp",
    {
        "name": str,
        "secret": str,
        "proxy": Proxies
    }
)

Balance= TypedDict(
    "Balance",
    {
        "accountValue": float,
        "totalMarginUsed": float,
        "available": float 
    }
)

Proxies = TypedDict(
    'Proxies',
    {
        "https": str,
        "http": str
    }
)

Proxy = TypedDict(
    'Proxy',
    {
        'host': str,
        'port': int,
        'username': str,
        'password': str
    }
)