from perp.hyperliquid.main import Hyperliquid
from perp.utils.funcs import load_json_file, format_portfolio
import perp.constants as constants
import perp.config as config 
# from perp.depositer import Transfer
from eth_account import Account

str1 = load_json_file("wallets/1.json")
secret1 = str1['perp1']['secret']
secret2 = str1['perp2']['secret']
proxies1 = str1['perp1']['proxies']
proxies2 = str1['perp2']['proxies']

wallet_config = str1['config']

p1 = Hyperliquid.from_row(secret1, proxies=proxies1, wallet_config=wallet_config)
p2 = Hyperliquid.from_row(secret2, proxies=proxies2, wallet_config=wallet_config)

portfolio1 = p1.get_portfolio()
portfolio2 = p2.get_portfolio()

positions1 = {i["coin"]: i for i in portfolio1["positions"]}
positions2 = {i["coin"]: i for i in portfolio2["positions"]}

told = []
for coin in positions1:
    if coin not in positions2:
        print(f"NOT MIRRORED POSITION in {p1.address[:5]}")
        print(positions1[coin])
    elif positions1[coin]['side'] == positions2[coin]['side'] and coin not in told:
        print(f"THE SAME SIDE BETWEEN {p1.address[:5]} and {p2.address[:5]}")
        print(positions1[coin])
        told.append(coin)
    elif positions1[coin]['sz'] != positions2[coin]['sz'] and coin not in told:
        print(f"SIZED DOESN'T MATCH and {p2.address[:5]}")
        print(f"{p1.address[:5]}: {positions1[coin]["sz"]}. {p2.address[:5]}: {positions2[coin]["sz"]}") 

for coin in positions2:
    if coin not in positions1:
        print(f"NOT MIRRORED POSITION in {p2.address[:5]}")
        print(positions2[coin])

print(format_portfolio(portfolio1))
print('\n')
print(format_portfolio(portfolio2))
