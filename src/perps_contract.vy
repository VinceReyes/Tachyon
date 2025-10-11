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

interface VAULT:
    def payout(_to: address, _amount: uint256) -> bool: nonpayable

# ------------------------------------------------------------------
#                              STATE
# ------------------------------------------------------------------
funding_rate: public(int256)
last_funding_timestamp: public(uint256)
positions: public(HashMap[address, Position])

# ------------------------------------------------------------------
#                            IMMUTABLES
# ------------------------------------------------------------------
authorized_vault_address: immutable(address)
market_id: immutable(uint256)
market_name: immutable(String[64])
authorized_funding_updater: immutable(address)
margin_token_address: immutable(address)
OWNER: immutable(address)

# ------------------------------------------------------------------
#                              STRUCT
# ------------------------------------------------------------------
struct Position:
    margin: uint256
    leverage: uint256
    entry_price: uint256
    size: uint256 # margin * leverage
    funding_rate_snapshot: int256
    direction: bool # true for long, false for short
    is_open: bool

@deploy
def __init__(_authorized_vault_address: address, _market_id: uint256, _market_name: String[64], _authorized_funding_updater: address, _margin_token_address: address):
    OWNER = msg.sender
    authorized_vault_address = _authorized_vault_address
    market_id = _market_id
    market_name = _market_name
    authorized_funding_updater = _authorized_funding_updater
    margin_token_address = _margin_token_address

    self.funding_rate = 0
    self.last_funding_timestamp = 0

@internal
def update_funding(_funding_rate: int256):
    assert msg.sender == authorized_funding_updater, "Only authorized funding updater can update funding"
    self.funding_rate = _funding_rate
    self.last_funding_timestamp = block.timestamp

@internal
def _get_market_price() -> uint256:
    # this function needs to call the oracle to get the current price of the perp market or some outside script that will return the market price
    return 0

@internal
def _get_funding_impact() -> uint256:
    # function to get the funidng impact on a particular position
    # this will require some clever programming that possibly gets kept track of from both that runs a script to keep trakc of funding payments for each position
    return 0

@external
@payable
@nonreentrant
def open_position(_margin: uint256, _leverage: uint256, _direction: bool):
    assert not self.positions[msg.sender].is_open, "Already opened postion"
    assert _margin > 0
    assert _leverage >= 0

    _entry_price: uint256 = self._get_market_price()

    allowed: uint256 = staticcall ERC20(margin_token_address).allowance(msg.sender, OWNER)
    assert allowed >= _margin
    success: bool = extcall ERC20(margin_token_address).transfer(self, _margin)
    assert success

    new_positions: Position = Position(
        margin = _margin,
        leverage = _leverage,
        entry_price = _entry_price,
        size = _margin * _entry_price,
        funding_rate_snapshot = self.funding_rate,
        direction = _direction,
        is_open = True
    )

    self.positions[msg.sender] = new_positions

@external
@nonreentrant
def close_position():
    assert self.positions[msg.sender].is_open, "No open position for user"

    current_position: Position = self.positions[msg.sender]
    current_price: uint256 = self._get_market_price()
    funding_impact: uint256 = self._get_funding_impact()
    pnl: uint256 = current_position.entry_price - current_price
    adjusted_pnl: uint256 = pnl - funding_impact

    if adjusted_pnl > 0:
        success: bool = extcall VAULT(authorized_vault_address).payout(msg.sender, adjusted_pnl)
        assert success, "Could not payout"

    self.positions[msg.sender].is_open = False

@external
def liquidate():
    pass
    
