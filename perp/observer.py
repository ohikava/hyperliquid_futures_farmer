import logging 
import requests 
from perp.utils.types import PerpStats
import perp.constants as constants 
import perp.config as config 
from perp.utils.funcs import format_portfolio
from datetime import datetime
from collections import defaultdict
import json 
import os 

logger = logging.getLogger(__name__)

client_id=-1002005413825
token = "6827720178:AAGyGWS3m0-0VlSujJvqekpUIhWeZtpvuzA"

path_file = f"fills/{datetime.today().strftime('%Y-%m-%d')}.txt"

with open(path_file, 'a') as file:
    pass 

class Observer:
    def send_sync_message(self, msg):
        uri = f"https://api.telegram.org/bot{token}/sendMessage"
    
        body = {
            "chat_id": client_id,
            "text": msg
        }

        requests.post(uri, json=body)
        
    def save_fill(self, fill: dict, wallet: str):
        sz = float(fill['sz'])
        px = round(float(fill['px']),5)
        fee = float(fill['fee'])
        side = constants.LONG if fill['side'] == 'B' else constants.SHORT
        coin = fill['coin']

        path_file = f"fills/{datetime.today().strftime('%Y-%m-%d')}.txt"
        res = {
            "coin": coin,
            "px": px,
            "sz": sz, 
            "fee": fee,
            "side": side,
            "address": wallet
        }
        with open(path_file, 'a') as file:
            file.write(f"{json.dumps(res)}\n")
    def observer_stats(self, w1_address, w2_address, p1, p2):
        tg_msg = f"{w1_address[:5]}: {round(p1, 3)}\n{w2_address[:5]}: {round(p2, 3)}\nTOTAL: {round(p1 + p2, 3)}"

        self.send_sync_message(tg_msg)

    def porftolio_state(self, address1, address2, portfolio1, portfolio2):
        positions1 = {i["coin"]: i for i in portfolio1["positions"]}
        positions2 = {i["coin"]: i for i in portfolio2["positions"]}

        res = ""
        for coin in positions1:
            if coin not in positions2:
                res += f"\nNOT MIRRORED POSITION in {address1[:5]}\n"
                res += str(positions1[coin])
            elif positions1[coin]['side'] == positions2[coin]['side']:
                res += f"\nTHE SAME SIDE BETWEEN {address1[:5]} and {address2[:5]}\n"
                res += str(positions1[coin])
            elif positions1[coin]['sz'] != positions2[coin]['sz']:
                res += f"\nSIZED DOESN'T MATCH and {address2[:5]}\n"
                res += f"{address1[:5]}: {positions1[coin]["sz"]}. {address2[:5]}: {positions2[coin]["sz"]}"

        for coin in positions2:
            if coin not in positions1:
                res += f"\nNOT MIRRORED POSITION in {address2[:5]}\n"
                res += str(positions2[coin])

        if res:
            self.send_sync_message(res)
        self.send_sync_message(f"{address1[:5]} {format_portfolio(portfolio1)}")
        self.send_sync_message(f"{address2[:5]} {format_portfolio(portfolio2)}")



        
