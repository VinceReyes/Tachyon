# pragma version 0.4.3
# @license MIT

# ------------------------------------------------------------------
#                              STATE
# ------------------------------------------------------------------
oracle_price: public(uint256)
last_update_time: public(uint256)

# ------------------------------------------------------------------
#                            IMMUTABLES
# ------------------------------------------------------------------
authorized_oracle_updater: immutable(address)
authorized_perp: immutable(address)

# ------------------------------------------------------------------
#                            CONSTANTS
# ------------------------------------------------------------------
STALE_TIME: constant(uint256) = 3600


@deploy
def __init__(_oracle_price: uint256, _authorized_oracle_updater: address, _authorized_perp: address):
    self.oracle_price = _oracle_price
    self.last_update_time = block.timestamp
    authorized_oracle_updater = _authorized_oracle_updater
    authorized_perp = _authorized_perp

@external
def update_oracle(_oracle_price: uint256):
    assert msg.sender == authorized_oracle_updater
    self.oracle_price = _oracle_price

@external
def get_oracle_price() -> uint256:
    assert msg.sender == authorized_perp
    assert block.timestamp - self.last_update_time < STALE_TIME
    return self.oracle_price
    

    

