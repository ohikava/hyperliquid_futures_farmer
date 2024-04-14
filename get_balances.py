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
print(f"USDC Balance {p1.address[:5]}: {round(contracts.usdc_contract.functions.balanceOf(p1.address).call() / 10**constants.USDC_DECIMALS, 2)} USDC")
print(f"ETH Balance {p1.address[:5]}: {round(contracts.w3.from_wei(contracts.w3.eth.get_balance(p1.address), "ether"), 6)} ETH")

print()
print(f"USDC Balance {p2.address[:5]}: {round(contracts.usdc_contract.functions.balanceOf(p2.address).call() / 10**constants.USDC_DECIMALS, 2)} USDC")
print(f"ETH Balance {p2.address[:5]}: {round(contracts.w3.from_wei(contracts.w3.eth.get_balance(p2.address), "ether"), 6)} ETH")
