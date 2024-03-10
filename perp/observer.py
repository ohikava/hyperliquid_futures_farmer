import logging 
import requests 
from perp.utils.types import PerpStats

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

    def show_stats(self, perp_stats: PerpStats):
        logger_msg = f"perp1: {perp_stats['perp1_address']} fees: {perp_stats['perp1_fees']} profit: {perp_stats['perp1_profit']}"
        logger_msg += f"perp2: {perp_stats['perp2_address']} fees: {perp_stats['perp2_fees']} profit: {perp_stats['perp2_profit']}"
        logger.info(logger_msg)

        tg_msg = f"perp1 wallet: {perp_stats['perp1_address']}\nfees: {perp_stats['perp1_fees']}\nprofit: {perp_stats['perp1_profit']}\n\nperp2 wallet: {perp_stats['perp2_address']}\nfees: {perp_stats['perp2_fees']}\nprofit: {perp_stats['perp2_profit']}"
        self.send_sync_message(tg_msg)
