# pragma version 0.4.3
# @license MIT

# ------------------------------------------------------------------
#                              STATE
# ------------------------------------------------------------------
oracle_price: public(uint256)
perp_price: public(uint256)
last_update_time: public(uint256)
last_update_time_perp: public(uint256)

# ------------------------------------------------------------------
#                            IMMUTABLES
# ------------------------------------------------------------------
authorized_oracle_updater: public(immutable(address))

# ------------------------------------------------------------------
#                            CONSTANTS
# ------------------------------------------------------------------
STALE_TIME: constant(uint256) = 3600
PRICE_SCALE: constant(uint256) = 10**6

@deploy
def __init__(_oracle_price: uint256, _authorized_oracle_updater: address, _perp_price: uint256):
    assert _authorized_oracle_updater != empty(address), "need to include an authorized address to update the oracle"
    self.oracle_price = _oracle_price
    self.perp_price = _perp_price
    self.last_update_time = block.timestamp
    authorized_oracle_updater = _authorized_oracle_updater

@external
def update_oracle(_oracle_price: uint256):
    assert msg.sender == authorized_oracle_updater, "not authorized to update oracle"
    assert _oracle_price <= PRICE_SCALE, "price > 1e6"
    self.oracle_price = _oracle_price
    self.last_update_time = block.timestamp

@external
def update_perp(_perp_price: uint256):
    assert msg.sender == authorized_oracle_updater, "not authorized to update oracle"
    assert _perp_price <= PRICE_SCALE, "price > 1e6"
    self.perp_price = _perp_price
    self.last_update_time_perp = block.timestamp

@external
@view
def get_oracle_price() -> uint256:
    assert block.timestamp - self.last_update_time <= STALE_TIME, "oracle has not been updated recently"
    return self.oracle_price

@external
@view
def get_perp_price() -> uint256:
    assert block.timestamp - self.last_update_time <= STALE_TIME, "oracle has not been updated recently"
    return self.perp_price