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
    perps = deploy_test_system["perps"]

    assert vault.USDC_ADDRESS() == usdc.address
    assert perps.oracle_address() == deploy_test_system["oracle"].address

    assert oracle.oracle_price() == ORACLE_STARTING_PRICE

def test_set_perp_in_vault(deploy_test_system):
    vault = deploy_test_system["vault"]
    owner = deploy_test_system["owner"]
    perps = deploy_test_system["perps"]

    with boa.env.prank(owner):
        vault.authorize_perp_address(perps.address)

    assert vault.authorized_perp_address() == perps.address

def test_vault_deposit(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(vault, 1000)
        vault.add_liquidity(1000)

    assert vault.user_deposits(test_user) == 1000
    assert vault.user_lp_balances(test_user) == 1000
    assert vault.total_usd_balance() == 1000
    assert vault.lp_token_total_supply() == 1000

def test_vault_remove(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(vault, 1000)
        vault.add_liquidity(1000)
        vault.remove_liquidity(500)

    assert vault.lp_token_total_supply() == 500
    assert vault.user_lp_balances(test_user) == 500
    assert usdc.balanceOf(test_user) == 1500

def test_can_payout(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    owner = deploy_test_system["owner"]
    perps = deploy_test_system["perps"]
    usdc = deploy_test_system["usdc"]


    with boa.env.prank(owner):
        vault.authorize_perp_address(perps.address)

    with boa.env.prank(owner):
        usdc.mint(owner, 2000)
        usdc.approve(vault, 1000)
        vault.add_liquidity(1000)