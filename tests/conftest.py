import pytest
import boa
from eth_utils import to_wei
from script.deploy import deploy
from script.deploy_mock_usdc import deploy_token

@pytest.fixture
def owner():
    addr = boa.env.generate_address()
    boa.env.set_balance(addr, to_wei(1, "ether"))
    return addr

@pytest.fixture
def deploy_test_system(owner):
    usdc_c = deploy_token()
    
    with boa.env.prank(owner):
        vault_c, oracle_c, perps_contract_c = deploy(usdc_c.address, owner)

    return {
        "owner": owner,
        "usdc": usdc_c,
        "vault": vault_c,
        "oracle": oracle_c,
        "perps": perps_contract_c,
    }

@pytest.fixture
def deploy_test_token(owner):
    with boa.env.prank(owner):
        c = deploy_token()
    return c

@pytest.fixture
def test_user():
    user_for = boa.env.generate_address()
    boa.env.set_balance(user_for, to_wei(2, "ether"))
    return user_for

@pytest.fixture
def test_user_two():
    user_for = boa.env.generate_address()
    boa.env.set_balance(user_for, to_wei(2, "ether"))
    return user_for

@pytest.fixture
def test_user_three():
    user_for = boa.env.generate_address()
    boa.env.set_balance(user_for, to_wei(2, "ether"))
    return user_for