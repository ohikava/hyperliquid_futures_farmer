from collections import defaultdict
import os 
from datetime import datetime 
import json 
import logging

logger = logging.getLogger(__name__)
def get_profit():
    filename = f"fills/{datetime.today().strftime('%Y-%m-%d')}.txt"

    with open(filename) as file:
        data = file.readlines()
    data_jsoned = [json.loads(i) for i in data]

    wallets = {}
    for item in data_jsoned:
        coin = item['coin']
        address = item['address']
        if address not in wallets:
            wallets[address] = defaultdict(list)
        wallets[address][coin].append(item)

    def calculate_profit(history):
        p = 0

        current_side = ""
        entry_price = -1
        current_sz = 0
        paid_fees = 0.0
        n = 0
        profit = 0.0
        while p < len(history):
            item = history[p]
            if not current_side:
                current_side = item['side']
                entry_price = item['px']
                current_sz = item['sz']
                n = 1
            elif current_side == item['side']:
                current_sz += item['sz']
                entry_price += item['px']
                n += 1
            else:
                entry_price /= n
                n = 1
                current_sz -= item['sz']
                side = 1 if current_side == 'LONG' else -1
                profit += (item['sz']*item['px'] - item['sz']*entry_price)*side

                if current_sz == 0.0:
                    current_side = ""
                    entry_price = -1
                    current_sz = 0
                    n = 0

            paid_fees += item.get('fee', 0.0)
            p += 1
        return profit, paid_fees


    coins_stats = {}
    w1_address, w2_address = list(wallets.keys())
    w1 = wallets[w1_address]
    w2 = wallets[w2_address]
    for coin in set(w1.keys()) | set(w2.keys()):
        if coin in w1 and coin in w2:
            coins_stats[coin] = (calculate_profit(w1[coin]), calculate_profit(w2[coin]))
        elif coin in w1:
            coins_stats[coin] = (calculate_profit(w1[coin]), None)
        else:
            coins_stats[coin] = (None, calculate_profit(w2[coin]))

    total_profit_w1 = 0.0
    total_profit_w2 = 0.0

    for value in coins_stats.values():
        if value[0]:
            total_profit_w1 += value[0][0] - value[0][1]
        if value[1]:
            total_profit_w2 += value[1][0] - value[1][1]

    log_msg = f"{w1_address[:5]}: Total {round(total_profit_w1, 3)}, {w2_address[:5]}: Total {round(total_profit_w2, 3)}. TOTAL: {round(total_profit_w2 + total_profit_w1, 3)}"
    logger.info(log_msg)
    return w1_address, w2_address, total_profit_w1, total_profit_w2