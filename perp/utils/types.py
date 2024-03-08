from typing_extensions import TypedDict
from typing import Union, Dict
from perp.perps.aevo import Aevo
from perp.perps.hyperliquid import Hyperliquid

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

PerpPair = TypedDict(
    "PerpPair",
    {
        'perp1': Union[Hyperliquid, Aevo],
        'perp2': Union[Hyperliquid, Aevo],
        'perp1_positions': Dict[str, Position],
        'perp2_positions': Dict[str, Position]
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