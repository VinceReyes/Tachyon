import os
import requests
import ast
import time

from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
RPC_URL = os.environ.get('RPC_URL')
ORACLE_ADDRESS = os.environ.get('ORACLE_ADDRESS')
ORACLE_ABI = os.environ.get('ORACLE_ABI')
POLYMARKET_BASE_API = 'https://gamma-api.polymarket.com/events/slug/'
URL_SUFFIX = os.environ.get('URL_SUFFIX')
PRICE_SCALE = 10**6

def get_yes_token_id() -> str:
    url = f"{POLYMARKET_BASE_API}{URL_SUFFIX}"

    r = requests.get(url)
    response = r.json()

    markets = response['markets'][0]
    tokens = markets['clobTokenIds']
    yes_token = ast.literal_eval(tokens)

    return yes_token[0]

def get_yes_token_price(_token_id: str) -> float:
    url = 'https://clob.polymarket.com/midpoint'
    query = {'token_id': _token_id}
    r = requests.get(url, params=query)
    response = r.json()
    price = int((response['mid']) * PRICE_SCALE)
    return price

def init_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = w3.eth.account.from_key(PRIVATE_KEY)
    w3.eth.default_account = account.address
    return w3

def update_oracle(w3: Web3, _price: int):
    contract = w3.eth.contract(address=ORACLE_ADDRESS, abi=ORACLE_ABI)
    account = w3.eth.default_account

    tx_params = {
        'from': account,
        'gas': 200000,
        'gasPrice': w3.to_wei(1, "gwei"),
        'nonce': w3.eth.get_transaction_count(account),
        'chainId': w3.eth.chain_id
    }

    tx = contract.functions.update_oracle(_price).build_transaction(tx_params)
    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    w3.eth.send_raw_transaction(signed_tx.raw_transaction)

def keeper_loop():
    yes_token_id = get_yes_token_id()
    w3 = init_web3(RPC_URL)

    while True:
        price = get_yes_token_price(yes_token_id)
        if price == 1 or price == 0:
            return False
        
        update_oracle(w3, price)

        time.sleep(3600)

def main():
    keeper_loop()

if __name__ == "__main__":
    main()



