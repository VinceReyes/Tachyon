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

interface ORACLE:
    def get_oracle_price() -> uint256: view

# ------------------------------------------------------------------
#                              STATE
# ------------------------------------------------------------------
funding_index: public(int256)
funding_rate_per_second: public(int256)
last_funding_timestamp: public(uint256)
positions: public(HashMap[address, Position])
limit_orders: public(HashMap[address, LimitOrder])

# ------------------------------------------------------------------
#                            IMMUTABLES
# ------------------------------------------------------------------
authorized_vault_address: public(immutable(address))
authorized_matching_engine: public(immutable(address))
market_id: public(immutable(uint256))
market_name: public(immutable(String[64]))
authorized_funding_updater: public(immutable(address))
margin_token_address: public(immutable(address))
oracle_address: public(immutable(address))
OWNER: public(immutable(address))

# ------------------------------------------------------------------
#                            CONSTANTS
# ------------------------------------------------------------------
FUNDING_SCALE: constant(uint256) = 10**18
MAX_ELAPSED: constant(uint256) = 86400

# ------------------------------------------------------------------
#                              STRUCT
# ------------------------------------------------------------------
struct Position:
    margin: uint256
    leverage: uint256
    entry_price: uint256
    size: uint256 # margin * leverage
    funding_index_snapshot: int256
    direction: bool # true for long, false for short
    is_open: bool

struct LimitOrder:
    trader_address: address
    leverage: uint256
    margin: uint256
    price: uint256
    quantity: uint256
    direction: bool # true for long, false for short
    is_open: bool # will remain true even if partially filled, and false if fully filled
    timestamp: uint256

@deploy
def __init__(_authorized_vault_address: address, _market_id: uint256, _market_name: String[64], _authorized_funding_updater: address, _margin_token_address: address, _oracle_address: address, _authorized_matching_engine: address):
    assert _authorized_vault_address != empty(address)
    assert _authorized_funding_updater != empty(address)
    assert _oracle_address != empty(address)

    OWNER = msg.sender
    authorized_vault_address = _authorized_vault_address
    authorized_matching_engine = _authorized_matching_engine
    market_id = _market_id
    market_name = _market_name
    authorized_funding_updater = _authorized_funding_updater
    margin_token_address = _margin_token_address
    oracle_address = _oracle_address

    self.funding_index = 0
    self.funding_rate_per_second = 0
    self.last_funding_timestamp = block.timestamp

@internal
def _get_market_price() -> uint256:
    return staticcall ORACLE(oracle_address).get_oracle_price()

@internal
def _get_funding_impact(pos: Position) -> int256:
    delta_index: int256 = self.funding_index - pos.funding_index_snapshot
    impact: int256 = (convert(pos.size, int256) * delta_index) // convert(FUNDING_SCALE, int256)
    if pos.direction: 
        impact = -impact
    return impact

@internal
def _integrate_funding():
    elapsed: uint256 = block.timestamp - self.last_funding_timestamp
    if elapsed == 0:
        return
    
    if elapsed > MAX_ELAPSED:
        elapsed = MAX_ELAPSED

    self.funding_index += self.funding_rate_per_second * convert(elapsed, int256)
    self.last_funding_timestamp = block.timestamp

@internal
def _calculate_health_factor(_address: address) -> int256:
    assert _address != empty(address), "No address provided"
    assert self.positions[_address].is_open, "No position open for address"

    pos: Position = self.positions[_address]

    entry_price: uint256 = pos.entry_price
    mark_price: uint256 = self._get_market_price()
    margin: uint256 = pos.margin
    leverage: uint256 = pos.leverage

    price_diff: int256 = convert(mark_price, int256) - convert(entry_price, int256)

    pnl: int256 = (convert(margin, int256) * convert(leverage, int256) * price_diff) // convert(entry_price, int256)

    if not pos.direction:
        pnl = -pnl

    funding_impact: int256 = self._get_funding_impact(pos)
    equity: int256 = convert(margin, int256) + pnl - funding_impact

    return equity

@external
@nonreentrant
def add_limit_order(_leverage: uint256, _margin: uint256, _price: uint256, _quantity: uint256, _direction: bool):
    assert _leverage > 0, "leverage cannot be <= 0"
    assert _margin > 0, "margin must be > 0"
    assert _price > 0, "price cannot be <= 0"
    assert not self.positions[msg.sender].is_open, "cannot open limit with existing open position"
    assert not self.limit_orders[msg.sender].is_open, "already have a limit order placed"

    allowed: uint256 = staticcall ERC20(margin_token_address).allowance(msg.sender, self)
    assert allowed >= _margin
    success: bool = extcall ERC20(margin_token_address).transferFrom(msg.sender, self, _margin)
    assert success

    limit_order: LimitOrder = LimitOrder(
        trader_address = msg.sender,
        leverage = _leverage,
        margin = _margin,
        price = _price,
        quantity = _quantity,
        direction = _direction,
        is_open = True,
        timestamp = block.timestamp
    )

    self.limit_orders[msg.sender] = limit_order

@external
@nonreentrant
def close_limit_order():
    assert self.limit_orders[msg.sender].is_open, "no limit orders open"

    margin_to_send_back: uint256 = self.limit_orders[msg.sender].margin

    self.limit_orders[msg.sender].leverage = 0
    self.limit_orders[msg.sender].margin = 0
    self.limit_orders[msg.sender].price = 0
    self.limit_orders[msg.sender].quantity = 0
    self.limit_orders[msg.sender].is_open = False
    self.limit_orders[msg.sender].timestamp = 0

    success: bool = extcall ERC20(margin_token_address).transfer(msg.sender, margin_to_send_back)
    assert success, "failed to return limit order margin"

@external
@nonreentrant
def fill_limit_order(_address: address, _quantity_to_fill: uint256):
    assert msg.sender == authorized_matching_engine
    assert self.limit_orders[_address].is_open, "no limit order open for provided address"

    current_position: LimitOrder = self.limit_orders[_address]

    if _quantity_to_fill < current_position.quantity:
        remaining_quantity: uint256 = current_position.quantity - _quantity_to_fill
        quantity_based_size_of_limit: uint256 = current_position.price * current_position.quantity
        quantity_based_size_of_market: uint256 = current_position.price * _quantity_to_fill
        remaining_margin: uint256 = (quantity_based_size_of_limit - quantity_based_size_of_market) // current_position.leverage
        margin_filled: uint256 = (_quantity_to_fill * current_position.price) // current_position.leverage

        # for mvp purposes, right now we are simply refunding leftover margin to the user, but this code can be used in the future for multi position handling and a more robust system
        # self.limit_orders[_address].quantity = remaining_quantity
        # self.limit_orders[_address].margin = remaining_margin
        # self._integrate_funding()
        
        position: Position = Position(
            margin = margin_filled,
            leverage = current_position.leverage,
            entry_price = current_position.price,
            size = margin_filled * current_position.leverage,
            funding_index_snapshot = self.funding_index,
            direction = current_position.direction,
            is_open = True
        )

        assert not self.positions[_address].is_open, "maker already has an open position"
        self.positions[_address] = position


        # used for mvp refund system
        success: bool = extcall ERC20(margin_token_address).transfer(_address, remaining_margin)
        assert success, "failed to return remaining margin"

        self.limit_orders[_address].leverage = 0
        self.limit_orders[_address].margin = 0
        self.limit_orders[_address].price = 0
        self.limit_orders[_address].quantity = 0
        self.limit_orders[_address].is_open = False
        self.limit_orders[_address].timestamp = 0

    else:
        assert _quantity_to_fill <= current_position.quantity, "overfilling"

        self._integrate_funding()

        position: Position = Position(
            margin = current_position.margin,
            leverage = current_position.leverage,
            entry_price = current_position.price,
            size = current_position.margin * current_position.leverage,
            funding_index_snapshot = self.funding_index,
            direction = current_position.direction,
            is_open = True
        )

        assert not self.positions[_address].is_open, "maker already has an open position"
        self.positions[_address] = position

        self.limit_orders[_address].leverage = 0
        self.limit_orders[_address].margin = 0
        self.limit_orders[_address].price = 0
        self.limit_orders[_address].quantity = 0
        self.limit_orders[_address].is_open = False
        self.limit_orders[_address].timestamp = 0

@external
@nonreentrant
def open_position(_margin: uint256, _leverage: uint256, _direction: bool):
    assert not self.positions[msg.sender].is_open, "Already opened postion"
    assert _margin > 0
    assert _leverage > 0

    _entry_price: uint256 = self._get_market_price()
    assert _entry_price > 0, "Bad entry price"

    allowed: uint256 = staticcall ERC20(margin_token_address).allowance(msg.sender, self)
    assert allowed >= _margin
    success: bool = extcall ERC20(margin_token_address).transferFrom(msg.sender, self, _margin)
    assert success

    self._integrate_funding()

    new_positions: Position = Position(
        margin = _margin,
        leverage = _leverage,
        entry_price = _entry_price,
        size = _margin * _leverage,
        funding_index_snapshot = self.funding_index,
        direction = _direction,
        is_open = True
    )

    self.positions[msg.sender] = new_positions

@external
@nonreentrant
def close_position():
    assert self.positions[msg.sender].is_open, "No open position for user"

    self._integrate_funding()

    current_position: Position = self.positions[msg.sender]
    current_price: uint256 = self._get_market_price()
    funding_impact: int256 = self._get_funding_impact(self.positions[msg.sender])
    assert current_position.entry_price > 0, "Bad entry price"
    price_differential: int256 = convert(current_price, int256) - convert(current_position.entry_price, int256)
    pnl: int256 = 0
    if current_position.direction:
        raw_pnl: int256 = price_differential * convert(current_position.size, int256)
        pnl = raw_pnl // convert(current_position.entry_price, int256)
    else:
        raw_pnl: int256 = -price_differential * convert(current_position.size, int256)
        pnl = raw_pnl // convert(current_position.entry_price, int256)
    adjusted_pnl: int256 = pnl - funding_impact
    assert current_position.margin > 0, "Invalid margin"
    assert convert(current_position.margin, int256) + adjusted_pnl >= 0, "Invalid equity, cannot close position"

    payout_pnl: uint256 = 0
    profit: uint256 = 0
    remaining_margin: uint256 = 0
    to_vault_margin: uint256 = 0
   
    if adjusted_pnl > 0:
        payout_pnl = convert(adjusted_pnl, uint256) + current_position.margin
        profit = payout_pnl - current_position.margin
        remaining_margin = current_position.margin
   
    elif convert(current_position.margin, int256) + adjusted_pnl > 0:
        payout_pnl = 0
        profit = 0
        remaining_margin = convert((convert(current_position.margin, int256) + adjusted_pnl), uint256)
        to_vault_margin = current_position.margin - remaining_margin
    
    else:
        success_send_vault: bool = extcall ERC20(margin_token_address).transfer(authorized_vault_address, current_position.margin)
        assert success_send_vault, "Failed to send margin from full loss back to vault upon close"

        current_position.margin = 0
        current_position.is_open = False
        current_position.size = 0
        current_position.entry_price = 0
        return

    if profit > 0:
        success_profit: bool = extcall VAULT(authorized_vault_address).payout(msg.sender, profit)
        assert success_profit, "Could not payout profit"
    
    if remaining_margin > 0:
        success_margin: bool = extcall ERC20(margin_token_address).transfer(msg.sender, remaining_margin)
        assert success_margin, "Could not payout margin"
    
    if to_vault_margin > 0:
        success_to_vault: bool = extcall ERC20(margin_token_address).transfer(authorized_vault_address, to_vault_margin)
        assert success_to_vault, "Could not send trader's lost margin to vault"

    current_position.margin = 0
    current_position.is_open = False
    current_position.size = 0
    current_position.entry_price = 0

@external
@nonreentrant
def liquidate(_address: address):
    assert msg.sender != _address, "cannot liquidate your own position"

    self._integrate_funding()

    user_equity: int256 = self._calculate_health_factor(_address)
    user_margin: uint256 = self.positions[_address].margin
    threshold: int256 = (convert(user_margin, int256) * 20) // 100

    if user_equity <= threshold:
        self.positions[_address].is_open = False
        self.positions[_address].margin = 0
        self.positions[_address].size = 0
        self.positions[_address].entry_price = 0

        reward: uint256 = (user_margin * 5) // 100

        vault_success: bool = extcall ERC20(margin_token_address).transfer(authorized_vault_address, user_margin)
        assert vault_success, "Failed to transfer remaining margin to vault"

        success: bool = extcall VAULT(authorized_vault_address).payout(msg.sender, reward)
        assert success, "Failed to payout reward"

@external
def update_funding(_new_rate_per_second: int256):
    assert msg.sender == authorized_funding_updater, "Only authorized funding updater can update funding"
    self._integrate_funding()
    self.funding_rate_per_second = _new_rate_per_second