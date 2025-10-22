# @version 0.4.3
"""
Mock USDC token for local testing
- 6 decimals (like real USDC)
- Standard ERC20 interface
- Includes mint() for testing
"""

# Events
event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

# State variables
name: public(String[32])
symbol: public(String[8])
decimals: public(uint256)
total_supply: public(uint256)

balances: HashMap[address, uint256]
allowances: HashMap[address, HashMap[address, uint256]]

# Constructor
@deploy
def __init__():
    self.name = "Mock USDC"
    self.symbol = "USDC"
    self.decimals = 6  # same as real USDC
    self.total_supply = 0

# Core ERC20 functions
@view
@external
def balanceOf(owner: address) -> uint256:
    return self.balances[owner]

@view
@external
def allowance(owner: address, spender: address) -> uint256:
    return self.allowances[owner][spender]

@external
def approve(spender: address, amount: uint256) -> bool:
    self.allowances[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, value=amount)
    return True

@external
def transfer(recipient: address, amount: uint256) -> bool:
    self._transfer(msg.sender, recipient, amount)
    return True

@external
def transferFrom(sender: address, recipient: address, amount: uint256) -> bool:
    allowed: uint256 = self.allowances[sender][msg.sender]
    assert allowed >= amount, "insufficient allowance"
    self.allowances[sender][msg.sender] = allowed - amount
    self._transfer(sender, recipient, amount)
    return True

# Internal transfer logic
@internal
def _transfer(sender: address, recipient: address, amount: uint256):
    assert self.balances[sender] >= amount, "insufficient balance"
    self.balances[sender] -= amount
    self.balances[recipient] += amount
    log Transfer(sender=sender, receiver=recipient, value=amount)

# Mint function (testing only)
@external
def mint(to: address, amount: uint256):
    """
    Mints new mock USDC tokens for testing.
    Only callable by the deployer.
    """
    assert msg.sender == tx.origin, "only EOA can mint in mock"
    self.balances[to] += amount
    self.total_supply += amount
    log Transfer(sender=empty(address), receiver=to, value=amount)
