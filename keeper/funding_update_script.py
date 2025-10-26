import os
import time
import requests
import json

from web3 import Web3
from dotenv import load_dotenv
from off_chain_systems.position_manager import PositionManager

load_dotenv()

PRICE_SCALE = 10**6
FUNDING_SCALE = 10**18
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
RPC_URL = os.environ.get('RPC_URL')
PERPS_ADDRESS = os.environ.get('PERPS_ADDRESS')
PERPS_ABI = json.loads(os.environ.get('PERPS_ABI'))
ORACLE_ADDRESS = os.environ.get('ORACLE_ADDRESS')
ORACLE_ABI = json.loads(os.environ.get('ORACLE_ABI'))
BASE_URL = "http://127.0.0.1:8000"

pm: PositionManager = PositionManager()

def get_oracle_price():
    r = requests.get(f"{BASE_URL}/oracle_price")
    return float(r.text)

def get_perp_price():
    r = requests.get(f"{BASE_URL}/perp_price")
    return float(r.text)

def calculate_funding_rate():
    oracle_price = get_oracle_price()
    perp_price = get_perp_price()
    funding_rate = (perp_price - oracle_price) / oracle_price
    return funding_rate

def update_funding_on_chain(w3, sender, funding_rate: float, nonce) -> bool:
    try:
        contract = w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)

        funding_rate_converted = int(funding_rate * FUNDING_SCALE)

        tx_params = {
            "from": sender.address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": w3.to_wei(1, "gwei")
        }

        tx = contract.functions.update_funding(funding_rate_converted).build_transaction(tx_params)
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"[FundingKeeper] Sent tx {tx_hash.hex()} rate={funding_rate:.8f}")
        return tx_hash
    except Exception as e:
        print(f"[FundingKeeper] Failed to update funding: {e}")
        return None
    
def update_perp_price_on_chain(w3, sender, nonce):
    try:
        contract = w3.eth.contract(address=ORACLE_ADDRESS, abi=ORACLE_ABI)

        perp_price = get_perp_price()
        perp_price_converted = int(perp_price * PRICE_SCALE)

        tx_params = {
            "from": sender.address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": w3.to_wei(1, "gwei")
        }

        tx = contract.functions.update_perp(perp_price_converted).build_transaction(tx_params)
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"[FundingKeeper] Sent tx {tx_hash.hex()} perp price={perp_price:.8f}")
        return tx_hash
    except Exception as e:
        print(f"[FundingKeeper] Failed to update perp_price: {e}")
        return None

def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ValueError("Could not connect to specified RPC URL")
    sender = w3.eth.account.from_key(PRIVATE_KEY)
    while True:
        nonce = w3.eth.get_transaction_count(sender.address)
        update_perp_price_on_chain(w3, sender, nonce)
        rate = calculate_funding_rate()
        update_funding_on_chain(w3, sender, rate, nonce + 1)
        #change to 4 hours for production
        print("cycle")
        time.sleep(10)
    
if __name__ == "__main__":
    main()