import json 

HL_SLIPPAGE_PERCENTS = 5

HL_SLIPPAGE = HL_SLIPPAGE_PERCENTS / 100

MIN_SLEEP_TIME = 1
MAX_SLEEP_TIME = 3

"""SYSTEM SETTINGS"""
THREADS_BATCH = 20

with open("coins.json") as file:
    decimals = json.load(file)

PRICE_DECIMALS = {key:value[0] for key, value in decimals.items()}
SIZE_DECIMALS = {key:value[1] for key, value in decimals.items()}
# COINS = {key for key in decimals}

LOW_LIQUIDITY_COINS = set(['TRX', 'STG'])

ARBITRUM_RPC = "https://rpc.ankr.com/arbitrum/"
GAS_UPPER = 1.15

WAIT_FOR_DEPOSIT = 25 # IN MINUTES
NOTIFY_INTERVAL = 5 # IN MINUTES


ON_SERVER = False