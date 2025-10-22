from src import mock_usdc
from moccasin.boa_tools import VyperContract

def deploy_token() -> VyperContract:
    token: VyperContract = mock_usdc.deploy()
    print(token)
    return token

def moccasin_main() -> VyperContract:
    return deploy_token()
