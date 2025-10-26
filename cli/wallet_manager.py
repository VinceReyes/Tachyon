from web3 import Web3
from eth_account import Account
import os
from dotenv import load_dotenv

load_dotenv()

class TraderWallet:
    def __init__(self, _rpc_url: str):
        self.web3 = Web3(Web3.HTTPProvider(_rpc_url))
        self.private_key = os.getenv("TRADER_KEY")
        self.account = self.web3.eth.account.from_key(self.private_key)
        self.address = self.account.address
    
    def sign_and_send(self, _tx_data):
        signed = self.web3.account.sign_transaction(_tx_data, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        return self.web3.to_hex(tx_hash)