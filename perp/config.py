import json 

HL_SLIPPAGE_PERCENTS = 0.5 

HL_SLIPPAGE = HL_SLIPPAGE_PERCENTS / 100

MIN_POSITION_TIME = 5* 60 

HL_TAKER_FEE = 0.025 / 100
HL_MAKER_FEE = -0.002 / 100 

MIN_LEVERAGE = 5
MAX_LEVERAGE = 7

POSITION_SIZE = 70
SLEEP = 0.5
MIN_SLEEP_TIME = 1
MAX_SLEEP_TIME = 3

WAIT_BEFORE_ORDER_MIN = 3
WAIT_BEFORE_ORDER_MAX = 5

MIN_LIFETIME = 8 * 60
MAX_LIFETIME = 10 * 60

HYPERLIQUID_TAKER_FEE = 0.035 / 100
HYPERLIQUID_MAKER_FEE = 0.010 / 100

"""SYSTEM SETTINGS"""
THREADS_BATCH = 20

with open("coins.json") as file:
    decimals = json.load(file)

PRICE_DECIMALS = {key:value[0] for key, value in decimals.items()}
SIZE_DECIMALS = {key:value[1] for key, value in decimals.items()}
COINS = {key for key in decimals}

LOW_LIQUIDITY_COINS = set(['TRX', 'STG'])