import os
import time
from web3 import Web3
from dataclasses import dataclass
from dotenv import load_dotenv
from enum import Enum

load_dotenv()

PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
RPC_URL = os.environ.get('RPC_URL')
ORACLE_ADDRESS = os.environ.get('ORACLE_ADDRESS')
ORACLE_ABI = os.environ.get("ORACLE_ABI")
PRICE_SCALE = 10**6

class Side(Enum):
    BUY = "buy"
    SELL = "sell"

class Status(Enum):
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"

@dataclass
class Account:
    account_id: str
    positions: list

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"

@dataclass
class Position:
    account_id: str
    position_id: int
    market_id: str
    side: Side
    entry_price: float
    quantity: float
    leverage: int
    margin: float
    liq_price: float
    unrealized_pnl: float
    realized_pnl: float
    funding_paid: float
    status: Status
    open_timestamp: int
    close_timestamp: int

@dataclass
class Order:
    trader_id: str # wallet address
    order_id: int
    side: Side
    price: float
    quantity: float
    filled_quantity: float
    leverage: int
    margin: float
    timestamp: int
    order_type: OrderType
    status: Status

@dataclass
class Trade:
    timestamp: int
    trade_id: int
    price: float
    quantity: float
    taker_id: str
    maker_id: str
    taker_side: Side
    taker_fee: float
    maker_fee: float

class PositionManager:
    def __init__(self):
        self.accounts = {}
        self.position_id: int = 0
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise ValueError("Could not connect to specified RPC URL")
        account = self.w3.eth.account.from_key(PRIVATE_KEY)
        self.w3.eth.default_account = account.address

    def increment_position_id(self) -> int:
        self.position_id += 1
        return self.position_id

    def get_price(self) -> float:
        contract = self.w3.eth.contract(address=ORACLE_ADDRESS, abi=ORACLE_ABI)

        price: int = contract.functions.get_oracle_price().call()
        converted_price = float(price / PRICE_SCALE)

        return converted_price
    
    def create_account(self, _address):
        if _address not in self.accounts:
            self.accounts[_address] = Account(
                account_id = _address,
                positions = []
            )
            print(f"Account created for {_address}")
    
    def create_taker_positions(self, _taker_id: str, _asset_name: str, _side: Side, _entry_price: float, _quantity: float, _leverage: int, _margin: float):

        if _taker_id not in self.accounts:
            raise ValueError("taker is not a registered user")
        
        taker_position: Position = Position(
            account_id = _taker_id,
            position_id = self.increment_position_id(),
            market_id = _asset_name,
            side = _side,
            entry_price = _entry_price,
            quantity = _quantity,
            leverage = _leverage,
            margin = _margin,
            liq_price = 0,
            unrealized_pnl = 0,
            realized_pnl = 0,
            funding_paid = 0,
            status = Status.OPEN,
            open_timestamp = time.time(),
            close_timestamp = 0
        )

        self.accounts[_taker_id].positions.append(taker_position)
        print(f"Position created for {_taker_id}: {taker_position.market_id}, {_side}, qty={_quantity}, avg_price={_entry_price}")
    
    def create_maker_position(self):
        pass