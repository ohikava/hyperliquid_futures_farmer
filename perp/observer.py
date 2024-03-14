import logging 
import requests 
from perp.utils.types import PerpStats
import perp.constants as constants 
import perp.config as config 
from datetime import datetime
from collections import defaultdict
import json 
import os 

logger = logging.getLogger(__name__)

client_id=-1002005413825
token = "6827720178:AAGyGWS3m0-0VlSujJvqekpUIhWeZtpvuzA"

path_file = f"fills/{datetime.today().strftime('%Y-%m-%d')}.txt"

with open(path_file, 'w') as file:
    pass 

class Observer:
    def send_sync_message(self, msg):
        uri = f"https://api.telegram.org/bot{token}/sendMessage"
    
        body = {
            "chat_id": client_id,
            "text": msg
        }

        requests.post(uri, json=body)

    def position_closed(self, token, p1_pnl, p2_pnl, p1_fee, p2_fee, p1_side):
        logger_msg = f"{token} PNL: {p1_pnl + p2_pnl}. Fees: {p1_fee+p2_fee}"
        logger.info(logger_msg)

        tg_msg = f"{token} {p1_side}\n\nperp1 pnl: {p1_pnl}\nfee: {p1_fee}\n\nperp2 pnl: {p2_pnl}\nfee{p2_fee}\n\nTotal: {p1_pnl+p2_pnl-p1_fee-p2_fee}"

        self.send_sync_message(tg_msg)
        
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

        
