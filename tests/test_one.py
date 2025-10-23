import boa
from eth_utils import to_wei

ORACLE_STARTING_PRICE: int = int(0.5 * (10**6))

# ------------------------------------------------------------------
#                           VAULT TESTS
# ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
#                       PERPS CONTRACT TEST
# ------------------------------------------------------------------

def test_perps_initialization(deploy_test_system):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    assert perps.OWNER() == owner
    assert perps.authorized_vault_address() == vault.address
    assert perps.authorized_funding_updater() == owner
    assert perps.authorized_matching_engine() == owner
    assert perps.margin_token_address() == usdc.address
    assert perps.oracle_address() == oracle.address
    assert perps.funding_index() == 0
    assert perps.funding_rate_per_second() == 0
    assert perps.last_funding_timestamp() != 0

def test_add_limit_order(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(perps, 500)
        perps.add_limit_order(2, 500, price, 4000, True)

    assert perps.limit_orders(test_user).trader_address == test_user
    assert perps.limit_orders(test_user).leverage == 2
    assert perps.limit_orders(test_user).margin == 500
    assert perps.limit_orders(test_user).price == price
    assert perps.limit_orders(test_user).quantity == 4000
    assert perps.limit_orders(test_user).direction
    assert perps.limit_orders(test_user).is_open
    assert perps.limit_orders(test_user).timestamp != 0

def test_cannot_add_multiple_limit_orders_for_one_user(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(perps, 500)
        perps.add_limit_order(2, 500, price, 4000, True)
        with boa.reverts("already have a limit order placed"):
            perps.add_limit_order(2, 500, price, 4000, True)

def test_close_limit_order(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(perps, 500)
        perps.add_limit_order(2, 500, price, 4000, True)
        perps.close_limit_order()
    
    assert perps.limit_orders(test_user).leverage == 0
    assert perps.limit_orders(test_user).margin == 0
    assert perps.limit_orders(test_user).price == 0
    assert perps.limit_orders(test_user).quantity == 0
    assert not perps.limit_orders(test_user).is_open
    assert perps.limit_orders(test_user).timestamp == 0
    assert usdc.balanceOf(perps.address) == 0
    assert usdc.balanceOf(test_user) == 2000

def test_cannot_close_non_existing_limit_order(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(perps, 500)
        with boa.reverts("no limit orders open"):
            perps.close_limit_order()

def test_can_fill_limit_order_full(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000)
        usdc.approve(perps, 500)
        perps.add_limit_order(2, 500, price, 4000, True)

    with boa.env.prank(owner):
        perps.fill_limit_order(test_user, 4000)

    assert perps.positions(test_user).margin == 500
    assert perps.positions(test_user).leverage == 2
    assert perps.positions(test_user).entry_price == price
    assert perps.positions(test_user).size == 1000
    assert perps.positions(test_user).direction
    assert perps.positions(test_user).is_open

    assert perps.limit_orders(test_user).leverage == 0
    assert perps.limit_orders(test_user).margin == 0
    assert perps.limit_orders(test_user).price == 0
    assert perps.limit_orders(test_user).quantity == 0
    assert not perps.limit_orders(test_user).is_open
    assert perps.limit_orders(test_user).timestamp == 0

def test_can_partial_fill_limit_order(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))
    SCALE: int = 10**6

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.add_limit_order(2, 500 * SCALE, price, 4000, True)

    with boa.env.prank(owner):
        perps.fill_limit_order(test_user, 2000)

    assert perps.positions(test_user).margin == 250 * SCALE
    assert perps.positions(test_user).leverage == 2
    assert perps.positions(test_user).entry_price == price
    assert perps.positions(test_user).size == 500 * SCALE
    assert perps.positions(test_user).direction
    assert perps.positions(test_user).is_open

    assert perps.limit_orders(test_user).leverage == 0
    assert perps.limit_orders(test_user).margin == 0
    assert perps.limit_orders(test_user).price == 0
    assert perps.limit_orders(test_user).quantity == 0
    assert not perps.limit_orders(test_user).is_open
    assert perps.limit_orders(test_user).timestamp == 0

    assert usdc.balanceOf(test_user) == 1750 * SCALE
    assert usdc.balanceOf(perps.address) == 250 * SCALE

def test_revert_limit_fill_on_overfill(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))
    SCALE: int = 10**6

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.add_limit_order(2, 500 * SCALE, price, 4000, True)

    with boa.env.prank(owner):
        with boa.reverts("overfilling"):
            perps.fill_limit_order(test_user, 4001)

def test_can_open_position(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))
    SCALE: int = 10**6

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.open_position(500 * SCALE, 2, True, price)
    
    assert usdc.balanceOf(test_user) == 1500 * SCALE
    assert usdc.balanceOf(perps.address) == 500 * SCALE
    assert perps.positions(test_user).margin == 500 * SCALE
    assert perps.positions(test_user).leverage == 2
    assert perps.positions(test_user).entry_price == price
    assert perps.positions(test_user).size == 500 * SCALE * 2
    assert perps.positions(test_user).direction
    assert perps.positions(test_user).is_open

def test_cannot_open_position_with_existing_postion(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    price: int = int(0.25 * (10**6))
    SCALE: int = 10**6

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.open_position(500 * SCALE, 2, True, price)
        with boa.reverts("Already opened postion"):
            usdc.approve(perps, 500 * SCALE)
            perps.open_position(500 * SCALE, 2, True, price)

def test_can_close_position_in_profit(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    SCALE: int = 10**6
    price: int = int(0.25 * SCALE)
    close_price: int = int(0.375 * SCALE)

    with boa.env.prank(owner):
        usdc.mint(owner, 10000 * SCALE)
        usdc.approve(vault, 10000 * SCALE)
        vault.add_liquidity(10000 * SCALE)
        vault.authorize_perp_address(perps.address)

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.open_position(500 * SCALE, 2, True, price)

    with boa.env.prank(owner):
        perps.close_position(test_user, close_price)
    
    assert usdc.balanceOf(perps.address) == 0
    assert usdc.balanceOf(test_user) == 2500 * SCALE
    assert usdc.balanceOf(vault.address) == 9500 * SCALE
    assert perps.positions(test_user).margin == 0
    assert not perps.positions(test_user).is_open
    assert perps.positions(test_user).size == 0
    assert perps.positions(test_user).entry_price == 0

def test_can_close_position_in_loss(deploy_test_system, test_user):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    SCALE: int = 10**6
    price: int = int(0.25 * SCALE)
    close_price: int = int(0.1875 * SCALE)

    with boa.env.prank(owner):
        usdc.mint(owner, 10000 * SCALE)
        usdc.approve(vault, 10000 * SCALE)
        vault.add_liquidity(10000 * SCALE)
        vault.authorize_perp_address(perps.address)

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.open_position(500 * SCALE, 2, True, price)

    with boa.env.prank(owner):
        perps.close_position(test_user, close_price)
    
    assert usdc.balanceOf(perps.address) == 0
    assert usdc.balanceOf(test_user) == 1750 * SCALE
    assert usdc.balanceOf(vault.address) == 10250 * SCALE
    assert perps.positions(test_user).margin == 0
    assert not perps.positions(test_user).is_open
    assert perps.positions(test_user).size == 0
    assert perps.positions(test_user).entry_price == 0

def test_can_liquidate_position(deploy_test_system, test_user, test_user_two):
    vault = deploy_test_system["vault"]
    usdc = deploy_test_system["usdc"]
    owner = deploy_test_system["owner"]
    oracle = deploy_test_system["oracle"]
    perps = deploy_test_system["perps"]

    SCALE: int = 10**6
    price: int = int(0.25 * SCALE)
    oracle_price: int = int(0.1375 * SCALE)

    with boa.env.prank(owner):
        usdc.mint(owner, 10000 * SCALE)
        usdc.approve(vault, 10000 * SCALE)
        vault.add_liquidity(10000 * SCALE)
        vault.authorize_perp_address(perps.address)

    with boa.env.prank(test_user):
        usdc.mint(test_user, 2000 * SCALE)
        usdc.approve(perps, 500 * SCALE)
        perps.open_position(500 * SCALE, 2, True, price)

    with boa.env.prank(owner):
        oracle.update_oracle(oracle_price)

    with boa.env.prank(test_user_two):
        perps.liquidate(test_user)

    assert usdc.balanceOf(vault.address) == 10475 * SCALE
    assert usdc.balanceOf(test_user_two) == 25 * SCALE
    assert usdc.balanceOf(owner) == 0
    assert vault.total_usd_balance() == 10475 * SCALE
    assert usdc.balanceOf(perps.address) == 0