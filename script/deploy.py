from src import oracle, perps_contract, vault
from moccasin.boa_tools import VyperContract

# USDC_ADDRESS: str = ""
INITIAL_USDC_BALANCE: int = 0

ORACLE_STARTING_PRICE: int = int(0.5 * (10**6))
# AUTHORIZED_ORACLE_UPDATER: str = ""

MARKET_ID: int = 0
MARKET_NAME: str = "test"
# AUTHORIZED_FUNDING_UPDATER: str = ""
# AUTHORIZED_MATCHING_ENGINE: str = ""

# def deploy() -> VyperContract:
#     vault_c: VyperContract = vault.deploy(USDC_ADDRESS, INITIAL_USDC_BALANCE)
#     oracle_c: VyperContract = oracle.deploy(ORACLE_STARTING_PRICE, AUTHORIZED_ORACLE_UPDATER)
#     perps_contract_c: VyperContract = perps_contract.deploy(vault_c.address, MARKET_ID, MARKET_NAME, AUTHORIZED_FUNDING_UPDATER, USDC_ADDRESS, oracle_c.address, AUTHORIZED_MATCHING_ENGINE)
#     return vault_c, oracle_c, perps_contract_c

def deploy(_usdc_address: str, _authorized_wallet: str) -> VyperContract:
    vault_c: VyperContract = vault.deploy(_usdc_address, INITIAL_USDC_BALANCE)
    oracle_c: VyperContract = oracle.deploy(ORACLE_STARTING_PRICE, _authorized_wallet)
    perps_contract_c: VyperContract = perps_contract.deploy(vault_c.address, MARKET_ID, MARKET_NAME, _authorized_wallet, _usdc_address, oracle_c.address, _authorized_wallet)
    return vault_c, oracle_c, perps_contract_c

def moccasin_main() -> VyperContract:
    return deploy()
