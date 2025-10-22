import boa
from eth_utils import to_wei

ORACLE_STARTING_PRICE: int = int(0.5 * (10**6))

def test_initialization(owner, deploy_test_token):
    with boa.env.prank(owner):
        deploy_test_token.mint(owner, 2000)
        assert deploy_test_token.balanceOf(owner) == 2000

def test_vault_initialization(deploy_test_system):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]

    assert vault.USDC_ADDRESS() == usdc.address

    perps = deploy_test_system["perps"]
    assert perps.oracle_address() == deploy_test_system["oracle"].address

    assert oracle.oracle_price() == ORACLE_STARTING_PRICE


