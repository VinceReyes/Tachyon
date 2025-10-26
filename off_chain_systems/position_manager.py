import os
import time
from web3 import Web3
from dataclasses import dataclass
from dotenv import load_dotenv
from enum import Enum
import json

load_dotenv()

PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
RPC_URL = os.environ.get('RPC_URL')
ORACLE_ADDRESS = os.environ.get('ORACLE_ADDRESS')
ORACLE_ABI = json.loads(os.environ.get("ORACLE_ABI"))
PERPS_ADDRESS = os.environ.get('PERPS_ADDRESS')
PERPS_ABI = json.loads(os.environ.get('PERPS_ABI'))
PRICE_SCALE = 10**6
FUNDING_SCALE = 10**18

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
    open_timestamp: float
    close_timestamp: float

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
    def __init__(self, orderbook=None):
        self.accounts = {}
        self.position_id: int = 0
        self.orderbook = orderbook
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise ValueError("Could not connect to specified RPC URL")
        account = self.w3.eth.account.from_key(PRIVATE_KEY)
        self.w3.eth.default_account = account.address

    def increment_position_id(self) -> int:
        self.position_id += 1
        return self.position_id

    def get_oracle_price(self) -> float:
        contract = self.w3.eth.contract(address=ORACLE_ADDRESS, abi=ORACLE_ABI)

        price: int = contract.functions.get_oracle_price().call()
        converted_price = float(price / PRICE_SCALE)

        return converted_price
    
    def get_perp_price(self) -> float:
        if self.orderbook:
            if len(self.orderbook.trade_events) > 0:
                return self. orderbook.trade_events[-1].price
        
        best_bid = self.orderbook.get_best_bid()
        best_ask = self.orderbook.get_best_ask()

        if best_bid and best_ask:
            return (best_bid + best_ask) / 2
        
        return self.get_oracle_price()
    
    def create_account(self, _address):
        if _address not in self.accounts:
            self.accounts[_address] = Account(
                account_id = _address,
                positions = []
            )
            print(f"Account created for {_address}")
    
    def create_position(self, _trader_id: str, _asset_name: str, _side: Side, _entry_price: float, _quantity: float, _leverage: int, _margin: float):

        if _trader_id not in self.accounts:
            raise ValueError("taker is not a registered user")
        
        taker_position: Position = Position(
            account_id = _trader_id,
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

        self.accounts[_trader_id].positions.append(taker_position)
        print(f"Position created for {_trader_id}: {taker_position.market_id}, {_side}, qty={_quantity}, avg_price={_entry_price}")

    def update_pnl(self, _position: Position):
        if _position.status != Status.OPEN:
            raise ValueError("position is not open")
        current_price: float = self.get_perp_price()

        if _position.side == Side.BUY:
            price_differential = current_price - _position.entry_price
        else:
            price_differential = _position.entry_price - current_price

        price_change_percentage = price_differential / _position.entry_price

        notional = _position.leverage * _position.margin
        pnl = notional * price_change_percentage

        _position.unrealized_pnl = pnl
        return pnl
    
    def close_position(self, _trader_id: str, _market_id: str, _quantity: float, _close_price: float):
        if _trader_id not in self.accounts:
            raise ValueError("trader not found")
        
        account: Account = self.accounts[_trader_id]

        position: Position = next((p for p in account.positions if p.market_id == _market_id and p.status == Status.OPEN), None)

        if not position:
            raise ValueError("no open position")
        
        if position.side == Side.BUY:
            pnl = (_close_price - position.entry_price) * position.margin * position.leverage
        else:
            pnl = (position.entry_price - _close_price) * position.margin * position.leverage

        position.realized_pnl += pnl

        if _quantity < position.quantity:
            position.quantity -= _quantity
        elif _quantity == position.quantity:
            position.quantity = 0
            position.close_timestamp = time.time()
            position.status = Status.CLOSED
        else:
            raise ValueError("quantity exceeds open position quantity")
        
        return pnl
    
    def liquidate_position(self, _address: str) -> bool:
        contract = self.w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)

        try:
            account = self.w3.eth.account.from_key(PRIVATE_KEY)

            tx = contract.functions.liquidate(_address).build_transaction({
                "from": account,
                "nonce": self.w3.eth.get_transaction_count(account),
                "gas": 300000,
                "gasPrice": self.w3.to_wei(1, "gwei")
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if _address in self.accounts:
                for p in self.accounts[_address].positions:
                    if p.status == Status.OPEN:
                        p.status = Status.LIQUIDATED
                        p.close_timestamp = time.time()
                        print(f"Position {p.position_id} liquidated at {p.close_timestamp}")

            return receipt.status == 1

        except Exception as e:
            print(f"Liquidation failed for {_address}: {e}")
            return False
        
    def get_funding_rate(self) -> float:
        contract = self.w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)
        raw = contract.functions.funding_rate_per_second().call()
        return raw / FUNDING_SCALE

        
    def management_loop(self):
        while True:
            for account in self.accounts.values():
                for position in account.positions:
                    if position.status == Status.OPEN:
                        try:
                            self.update_pnl(position)
                            if position.unrealized_pnl / position.margin < -0.8:
                                self.liquidate_position(position.account_id)
                        except Exception as e:
                            print(f"Error processing {position.account_id}: {e}")
            time.sleep(5)