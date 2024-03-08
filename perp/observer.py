import logging 
import requests 

logger = logging.getLogger(__name__)

client_id=-1002005413825
token = "6827720178:AAGyGWS3m0-0VlSujJvqekpUIhWeZtpvuzA"

class Observer:
    def send_sync_message(self, msg):
        uri = f"https://api.telegram.org/bot{token}/sendMessage"
    
        body = {
            "chat_id": client_id,
            "text": msg
        }

        requests.post(uri, json=body)
    
    def order_filled(self, order_info, order_type):
        logger_msg = f"{order_info['perp']} {order_info['side']} {order_info['coin']} sz {order_info['sz']} px {order_info['px']} tp {order_type} filled"
        logger.info(logger_msg)
        self.send_sync_message(logger_msg)

    def show_stats(self, perp1_fees, perp2_fees, perp1_profit, perp2_profit):
        logger_msg = f"fee1{perp1_fees}$ fee2 {perp2_fees}$ profit1 {perp1_profit}$ profit2 {perp2_profit}$ total {perp1_profit + perp2_profit - perp2_fees - perp1_fees}$"
        logger.info(logger_msg)
        tg_msg = f"fee1: {perp1_fees}$\nfee2: {perp2_fees}$\nprofit1: {perp1_profit}$\nprofit2: {perp2_profit}$\ntotal: {round(perp1_profit + perp2_profit - perp1_fees - perp2_fees, 2)}$"
        self.send_sync_message(tg_msg)
