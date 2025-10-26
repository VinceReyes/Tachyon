from src import oracle, perps_contract, vault
from moccasin.boa_tools import VyperContract
from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
RPC_URL = os.environ.get('RPC_URL')
USDC_ABI = os.environ.get('USDC_ABI')
SCALE = 10**6

USDC_ADDRESS: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
INITIAL_USDC_BALANCE: int = 0

ORACLE_STARTING_PRICE: int = int(0.5 * (10**6))
ORACLE_PERP_STARTING_PRICE: int = int(0.5 * (10**6))
AUTHORIZED_ORACLE_UPDATER: str = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

MARKET_ID: int = 0
MARKET_NAME: str = "maduro"
AUTHORIZED_FUNDING_UPDATER: str = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
AUTHORIZED_MATCHING_ENGINE: str = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

TRADER_0 = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
TRADER_1 = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
TRADER_2 = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
TRADER_3 = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
TRADER_4 = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
TRADER_5 = "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"
TRADER_6 = "0x976EA74026E726554dB657fA54763abd0C3a0aa9"
TRADER_7 = "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"
TRADER_8 = "0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f"
TRADER_9 = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"

def deploy() -> VyperContract:
    vault_c: VyperContract = vault.deploy(USDC_ADDRESS, INITIAL_USDC_BALANCE)
    oracle_c: VyperContract = oracle.deploy(ORACLE_STARTING_PRICE, AUTHORIZED_ORACLE_UPDATER, ORACLE_PERP_STARTING_PRICE)
    perps_contract_c: VyperContract = perps_contract.deploy(vault_c.address, MARKET_ID, MARKET_NAME, AUTHORIZED_FUNDING_UPDATER, USDC_ADDRESS, oracle_c.address, AUTHORIZED_MATCHING_ENGINE)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    deployer = w3.eth.account.from_key(PRIVATE_KEY)

    mock_usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)

    mint_amount = 100000 * SCALE
    for trader in [TRADER_0, TRADER_1, TRADER_2, TRADER_3, TRADER_4, TRADER_5, TRADER_6, TRADER_7, TRADER_8, TRADER_9]:
        tx = mock_usdc_contract.functions.mint(trader, mint_amount).transact({"from": deployer.address})

        w3.eth.wait_for_transaction_receipt(tx)
        print(f"Minted {mint_amount/10**6:,.0f} mock USDC to {trader}")

    print(f"vault deployed at {vault_c}")
    print(f"oracle deployed at {oracle_c}")
    print(f"perps_contract deployed at {perps_contract_c}")
    print("done")
    return vault_c, oracle_c, perps_contract_c

# def deploy(_usdc_address: str, _authorized_wallet: str) -> VyperContract:
#     vault_c: VyperContract = vault.deploy(_usdc_address, INITIAL_USDC_BALANCE)
#     oracle_c: VyperContract = oracle.deploy(ORACLE_STARTING_PRICE, _authorized_wallet, ORACLE_PERP_STARTING_PRICE)
#     perps_contract_c: VyperContract = perps_contract.deploy(vault_c.address, MARKET_ID, MARKET_NAME, _authorized_wallet, _usdc_address, oracle_c.address, _authorized_wallet)
#     return vault_c, oracle_c, perps_contract_c

def moccasin_main() -> VyperContract:
    return deploy()
