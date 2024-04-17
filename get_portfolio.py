from perp.hyperliquid.main import Hyperliquid
from perp.utils.funcs import load_json_file, format_portfolio
import perp.constants as constants
import perp.config as config 
# from perp.depositer import Transfer
from eth_account import Account
from perp.encode import load_encoded
from getpass import getpass
import os 


wallets = os.listdir("wallets_configs")
for wallet in wallets:
    wallet = wallet.replace(".json", "")
    conf = load_json_file(os.path.join("wallets_configs", wallet + ".json"))
    if conf['encoded']:
        password = getpass()
        pk = load_encoded(password, os.path.join("wallets_encoded", wallet))
    else:
        pk = load_json_file(os.path.join("wallets_encoded", wallet))
        wallet_data = {**pk, **conf}

    str1 = {**conf, **pk}
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

    for coin in positions1:
        if coin not in positions2:
            print(f"NOT MIRRORED POSITION in {p1.address[:5]}")
            print(positions1[coin])
        elif positions1[coin]['side'] == positions2[coin]['side']:
            print(f"THE SAME SIDE BETWEEN {p1.address[:5]} and {p2.address[:5]}")
            print(positions1[coin])
        elif positions1[coin]['sz'] != positions2[coin]['sz']:
            print(f"SIZED DOESN'T MATCH and {p2.address[:5]}")
            print(f"{p1.address[:5]}: {positions1[coin]['sz']}. {p2.address[:5]}: {positions2[coin]['sz']}") 

    for coin in positions2:
        if coin not in positions1:
            print(f"NOT MIRRORED POSITION in {p2.address[:5]}")
            print(positions2[coin])

    print(p1.address[:5])
    print(format_portfolio(portfolio1))
    print('\n')
    print(p2.address[:5])
    print(format_portfolio(portfolio2))