import time
from web3 import Web3
from web3.exceptions import TransactionNotFound
import perp.config as config 
import perp.constants as constants
from perp.utils.funcs import retry
from eth_account import Account
import logging 

logger = logging.getLogger(__name__)

class Depositer:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.ARBITRUM_RPC))

        logger.info(f"RPC STATE: {self.w3.is_connected()}")

        self.usdc_contract = self.w3.eth.contract(address=Web3.to_checksum_address(constants.USDC_CONTRACT_ADDRESS), abi=constants.USDC_ABI)

    def wait_and_deposit(self, sender, amount):
        amount_wei = int(amount * 10**constants.USDC_DECIMALS )
        user_balance = self.usdc_contract.functions.balanceOf(sender.address).call()
        
        start_time = time.time()
        while user_balance < amount_wei:
            if time.time() - start_time > config.WAIT_FOR_DEPOSIT * 60:
                logger.error(f"{sender.address[:5]} INSUFFICIENT USDC AMOUNT(sends {amount}, got {user_balance/10**constants.USDC_DECIMALS}). Waiting too long")
                return 
            
            time.sleep(30)
            user_balance = self.usdc_contract.functions.balanceOf(sender.address).call()

        is_successful = self.deposit(sender, amount_wei)
        return is_successful

    def deposit(self, sender, amount_wei):
        dict_transaction = {
            "from": Web3.to_checksum_address(sender.address),
            "chainId": self.w3.eth.chain_id,
            "nonce": self.w3.eth.get_transaction_count(sender.address),
            "gasPrice": self.w3.eth.gas_price
        }
        tx = self.usdc_contract.functions.transfer(
            constants.HYPERLIQUID_BRIDGE_ADDRESS, amount_wei
        ).build_transaction(dict_transaction)

        tx_token, is_successful = self.send_transaction(tx, sender)

        return is_successful


    
        
        
    @retry(custom_message="Failed to submit transaction:", catch_exception=True, max_retries=2)
    def send_transaction(
            self, tx: dict, eth_account: Account,
            gas_upper: float = config.GAS_UPPER, wait_tx=True
    ) -> str:        
        gasEstimate = self.w3.eth.estimate_gas(tx) * gas_upper
        tx['gas'] = round(gasEstimate)

        signed_txn = eth_account.sign_transaction(tx)

        tx_token = Web3.to_hex(self.w3.eth.send_raw_transaction(signed_txn.rawTransaction))

        logger.info(f"{eth_account.address} approwed: {tx_token}")

        if wait_tx:
            if self.wait_until_tx_finished(tx_token, eth_account):
                time.sleep(60)
                return tx_token, True
            
            else: return tx_token, False
        else:
            return tx_token, False
        
    def wait_until_tx_finished(self, transaction_hash: str, eth_account: Account, max_waiting_time: int = 600) -> bool:
        start_time = time.time()

        while time.time() - start_time < max_waiting_time:
            try:
                receipts = self.w3.eth.get_transaction_receipt(transaction_hash)
                status = receipts.get("status")

                if status == 1:
                    logger.info(f"{eth_account.address[:5]} {transaction_hash} is completed")
                    return True
                elif status is None:
                    time.sleep(5)

                elif status != 1:
                    logger.error(f'{eth_account.address[:5]} [{transaction_hash}] transaction is failed')
                    return False
                
            except TransactionNotFound:
                time.sleep(3)