# pragma version 0.4.3
# @license MIT

# ------------------------------------------------------------------
#                            INTERFACE
# ------------------------------------------------------------------
interface ERC20:
    def balanceOf(_owner: address) -> uint256: view
    def transfer(_to: address, _value: uint256) -> bool: nonpayable
    def transferFrom(_from: address, _to: address, _value: uint256) -> bool: nonpayable
    def approve(_spender: address, _value: uint256) -> bool: nonpayable
    def allowance(_owner: address, _spender: address) -> uint256: view

# ------------------------------------------------------------------
#                         STATE VARIABLES
# ------------------------------------------------------------------
user_deposits: public(HashMap[address, uint256])
lp_token_name: public(String[64])
lp_token_symbol: public(String[32])
lp_token_decimals: public(uint8)
lp_token_total_supply: public(uint256)
user_lp_balances: public(HashMap[address, uint256])
total_usd_balance: public(uint256)
authorized_perp_address: public(address)

# ------------------------------------------------------------------
#                     CONSTANTS AND IMMUTABLES
# ------------------------------------------------------------------
OWNER: immutable(address)
USDC_ADDRESS: immutable(address)

# deploying the contract will require the owner to deposit some USDC(not PYUSD) to the contract for initial liquidity
@deploy
def __init__(_usdc_address: address, _initial_usd_balance: uint256):
    USDC_ADDRESS = _usdc_address
    OWNER = msg.sender

    self.lp_token_name = "Tachyon LP"
    self.lp_token_symbol = "TLP"
    self.lp_token_decimals = 18
    self.lp_token_total_supply = 0

    allowed: uint256 = staticcall ERC20(USDC_ADDRESS).allowance(msg.sender, self)
    assert allowed >= _initial_usd_balance, "Insufficient allowance"
    success: bool = extcall ERC20(USDC_ADDRESS).transferFrom(msg.sender, self, _initial_usd_balance)
    assert success, "Transfer failed"
    self.user_deposits[msg.sender] = _initial_usd_balance

    self.total_usd_balance = _initial_usd_balance

# ------------------------------------------------------------------
#                             INTERNAL
# ------------------------------------------------------------------
@internal
def _mint(_to: address, _amount: uint256):
    assert _to != empty(address), "No address provided"
    assert _amount > 0, "Amount must be greater than 0"

    self.lp_token_total_supply += _amount
    self.user_lp_balances[_to] += _amount

@internal
def _burn(_from: address, _amount: uint256):
    assert _from != empty(address), "No address provided"
    assert _amount > 0, "Amount must be greater than 0"
    assert self.user_lp_balances[_from] >= _amount, "Insufficient balance to burn"

    self.lp_token_total_supply -= _amount
    self.user_lp_balances[_from] -= _amount

# ------------------------------------------------------------------
#                             EXTERNAL
# ------------------------------------------------------------------
@external
@nonreentrant
def add_liquidity(amount: uint256):
    assert amount > 0, "Amount must be greater than 0"
    assert msg.sender != empty(address), "No address provided"

    allowed: uint256 = staticcall ERC20(USDC_ADDRESS).allowance(msg.sender, self)
    assert allowed >= amount, "Insufficient allowance"
    success: bool = extcall ERC20(USDC_ADDRESS).transferFrom(msg.sender, self, amount)
    assert success, "Transfer failed"

    self.user_deposits[msg.sender] += amount
    self.total_usd_balance += amount
    self._mint(msg.sender, amount)

@external
@nonreentrant
def remove_liquidity(amount: uint256):
    assert amount > 0, "Amount must be greater than 0"
    assert msg.sender != empty(address), "No address provided"
    assert self.user_lp_balances[msg.sender] >= amount, "Insufficient balance to remove" 

    self._burn(msg.sender, amount)
    assert self.lp_token_total_supply > 0, "Total supply is 0"
    withdraw_amount: uint256 = amount * self.total_usd_balance // self.lp_token_total_supply
    self.total_usd_balance -= withdraw_amount

    success: bool = extcall ERC20(USDC_ADDRESS).transfer(msg.sender, withdraw_amount)
    assert success, "Transfer failed"

@external
@nonreentrant
def payout(_to: address, amount: uint256):
    assert self.authorized_perp_address != empty(address), "Perp address not authorized"
    assert msg.sender == self.authorized_perp_address, "Only authorized perp address can payout"
    assert _to != empty(address), "No address provided"
    assert amount > 0, "Amount must be greater than 0"
    assert self.total_usd_balance >= amount, "Insufficient balance to payout"

    self.total_usd_balance -= amount
    success: bool = extcall ERC20(USDC_ADDRESS).transfer(_to, amount)
    assert success, "Transfer failed"

@external
def authorize_perp_address(_address: address):
    assert msg.sender == OWNER, "Only owner can authorize perp address"
    assert _address != empty(address), "No address provided"
    self.authorized_perp_address = _address