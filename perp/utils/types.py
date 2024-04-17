from typing_extensions import TypedDict
from typing import Union, Dict, List, Literal, Callable
from perp.hyperliquid.hyperliquid_base import HyperliquidBase
import perp.constants as constants

PerpPair = TypedDict(
    "PerpPair",
    {
        'perp1': HyperliquidBase,
        'perp2': HyperliquidBase,
        "positions": Dict[str, int]
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

UnfilledOrder = TypedDict(
    'UnfilledOrder',
    {
        "coin": str,
        "sz": float,
        "type": Union[Literal["MAKER"], Literal["TAKER"]],
        "long": int,
        "short": int ,
        "cb": Callable
    }
)

RepeatingOrder = TypedDict(
    'RepeatingOrder',
    {
        'sz': float, 
        'side': str,
        'uid': int 
    }
)

Position = TypedDict(
    "OpenPosition",
    {
        "sz": float,
        "entry_price": float,
        "side": str,
        "lifetime": int,
        "open_time": int,
        "fee": float 
    }
)

WalletConfig = TypedDict(
    "WalletDict",
    {
        "positions_lifetime": int,
        "n_positions": int,
        "leverage": int,
        "min_available_balance": float,
        "transfer_ratio_percents": float,
        "rebalance": bool,
        "transfer_type": str ,
        "coins": list, 
        "encoded": bool 
    }
)

MakerOrder = TypedDict(
    "MakerOrder",
    {
        "long": int,
        "short": int,
        "sz": float 
    }
)

Order = TypedDict(
    "Order",
    {
        "side": str,
        "sz": float,
        "oid": int 
    }
)

ClosedPosition = TypedDict(
    "ClosedPosition",
    {
        "pnl": float,
        "fee": float,
        "side": str
    }
)