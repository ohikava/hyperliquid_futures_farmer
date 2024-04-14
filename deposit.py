from perp.hyperliquid.main import Hyperliquid
from perp.utils.funcs import load_json_file, format_portfolio
import perp.constants as constants
import perp.config as config 
from perp.contracts import Contracts
from eth_account import Account
from perp.encode import load_encoded
from getpass import getpass
import os 

password = getpass()

name = "1"
conf = load_json_file(os.path.join("wallets_configs", f"{name}.json"))
pk = load_encoded(password, os.path.join("wallets_encoded", name))

str1 = {**conf, **pk}
secret1 = str1['perp1']['secret']
secret2 = str1['perp2']['secret']
proxies1 = str1['perp1']['proxies']
proxies2 = str1['perp2']['proxies']

wallet_config = str1['config']

p1 = Hyperliquid.from_row(secret1, proxies=proxies1, wallet_config=wallet_config)
p2 = Hyperliquid.from_row(secret2, proxies=proxies2, wallet_config=wallet_config)
contracts = Contracts()
usdc_balance_1 = round(contracts.usdc_contract.functions.balanceOf(p1.address).call() / 10**constants.USDC_DECIMALS, 2)
print(f"USDC Balance {p1.address[:5]}: {usdc_balance_1} USDC")
if usdc_balance_1 >= 2:
    r = contracts.deposit(p1.wallet, usdc_balance_1)
    if r:
        print(f"successfully deposited {usdc_balance_1} from {p1.address[:5]}")
    else:
        print(f"{p1.address[:5]} {usdc_balance_1} {r}")


usdc_balance_2 = round(contracts.usdc_contract.functions.balanceOf(p2.address).call() / 10**constants.USDC_DECIMALS, 2)
print()
print(f"USDC Balance {p2.address[:5]}: {usdc_balance_2} USDC")
if usdc_balance_2 >= 2:
    r = contracts.deposit(p2.wallet, usdc_balance_2)
    if r:
        print(f"successfully transfered {usdc_balance_2} from {p2.address[:5]}")
    else:
        print(f"{p2.address[:5]} {usdc_balance_2} {r}")
