from typing import TypedDict, Union, Literal, Optional
from typing_extensions import NotRequired
from perp.hyperliquid.hyperliquid_types import Cloid
from eth_account.messages import encode_structured_data
import time 
from decimal import Decimal
import msgpack
from eth_utils import keccak, to_hex


Tif = Union[Literal["Alo"], Literal["Ioc"], Literal["Gtc"]]
Tpsl = Union[Literal["tp"], Literal["sl"]]
LimitOrderType = TypedDict("LimitOrderType", {"tif": Tif})
TriggerOrderType = TypedDict("TriggerOrderType", {"triggerPx": float, "isMarket": bool, "tpsl": Tpsl})
OrderType = TypedDict("OrderType", {"limit": LimitOrderType, "trigger": TriggerOrderType}, total=False)
OrderRequest = TypedDict(
    "OrderRequest",
    {
        "coin": str,
        "is_buy": bool,
        "sz": float,
        "limit_px": float,
        "order_type": OrderType,
        "reduce_only": bool,
        "cloid": NotRequired[Optional[Cloid]],
    },
    total=False,
)
TriggerOrderTypeWire = TypedDict("TriggerOrderTypeWire", {"triggerPx": str, "isMarket": bool, "tpsl": Tpsl})
OrderTypeWire = TypedDict("OrderTypeWire", {"limit": LimitOrderType, "trigger": TriggerOrderTypeWire}, total=False)
OrderWire = TypedDict(
    "OrderWire",
    {
        "a": int,
        "b": bool,
        "p": str,
        "s": str,
        "r": bool,
        "t": OrderTypeWire,
        "c": NotRequired[Optional[str]],
    },
)

def order_type_to_wire(order_type: OrderType) -> OrderTypeWire:
    if "limit" in order_type:
        return {"limit": order_type["limit"]}
    elif "trigger" in order_type:
        return {
            "trigger": {
                "isMarket": order_type["trigger"]["isMarket"],
                "triggerPx": float_to_wire(order_type["trigger"]["triggerPx"]),
                "tpsl": order_type["trigger"]["tpsl"],
            }
        }
    raise ValueError("Invalid order type", order_type)

def float_to_wire(x: float) -> str:
    rounded = "{:.8f}".format(x)
    if abs(float(rounded) - x) >= 1e-12:
        raise ValueError("float_to_wire causes rounding", x)
    if rounded == "-0":
        rounded = "0"
    normalized = Decimal(rounded).normalize()
    return f"{normalized:f}"

def order_request_to_order_wire(order: OrderRequest, asset: int) -> OrderWire:
    order_wire: OrderWire = {
        "a": asset,
        "b": order["is_buy"],
        "p": float_to_wire(order["limit_px"]),
        "s": float_to_wire(order["sz"]),
        "r": order["reduce_only"],
        "t": order_type_to_wire(order["order_type"]),
    }
    if "cloid" in order and order["cloid"] is not None:
        order_wire["c"] = order["cloid"].to_raw()
    return order_wire

def order_wires_to_order_action(order_wires):
    return {
        "type": "order",
        "orders": order_wires,
        "grouping": "na",
    }

def action_hash(action, nonce):
    data = msgpack.packb(action)
    data += nonce.to_bytes(8, "big")
    
    data += b"\x00"
    return keccak(data)

def construct_phantom_agent(hash):
    return {"source": "a", "connectionId": hash}

def sign_inner(wallet, data):
    structured_data = encode_structured_data(data)
    signed = wallet.sign_message(structured_data)
    return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}

def sign_l1_action(wallet, action, nonce):
    hash = action_hash(action, nonce)
    phantom_agent = construct_phantom_agent(hash)
    data = {
        "domain": {
            "chainId": 1337,
            "name": "Exchange",
            "verifyingContract": "0x0000000000000000000000000000000000000000",
            "version": "1",
        },
        "types": {
            "Agent": [
                {"name": "source", "type": "string"},
                {"name": "connectionId", "type": "bytes32"},
            ],
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
        },
        "primaryType": "Agent",
        "message": phantom_agent,
    }
    return sign_inner(wallet, data)

def get_timestamp_ms() -> int:
    return int(time.time() * 1000)