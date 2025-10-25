from dataclasses import dataclass
from enum import Enum
from sortedcontainers import SortedDict
import time
from web3 import Web3
from dotenv import load_dotenv
import os
import json
from off_chain_systems.position_manager import PositionManager

load_dotenv()

PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
RPC_URL = os.environ.get('RPC_URL')
PERPS_ADDRESS = os.environ.get('PERPS_ADDRESS')
PERPS_ABI = json.loads(os.environ.get("PERPS_ABI"))
PRICE_SCALE = 10**6

class Side(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"

class Status(Enum):
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"
    OPEN = "open"

@dataclass
class Trade:
    timestamp: float
    trade_id: int
    price: float
    quantity: float
    taker_id: str
    maker_id: str
    taker_side: Side
    taker_fee: float
    maker_fee: float

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
    timestamp: float
    order_type: OrderType
    status: Status

class OrderBook:
    def __init__(self, _asset_name, _pm):
        self.asset_name: str = _asset_name
        self.order_id: int = 0
        self.trade_id: int = 0
        self.bids: SortedDict = SortedDict()
        self.asks: SortedDict = SortedDict()
        self.trade_events = []
        self.MAKER_FEE: float = 0.0002
        self.TAKER_FEE: float = 0.0006
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise ValueError("Could not connect to specified RPC URL")
        account = self.w3.eth.account.from_key(PRIVATE_KEY)
        self.w3.eth.default_account = account.address
        self.pm: PositionManager = _pm

    def send_limit_order(self, w3: Web3, _leverage: int, _margin: float, _price: float, _quantity: float, _direction: Side, trader_address: str):
        print("Simulating on-chain limit order — skipping Web3 transaction.")
        return True
        # contract = w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)

        # margin = int(_margin * PRICE_SCALE)
        # price = int(_price * PRICE_SCALE)
        # quantity = int(_quantity)
        # direction: bool = True if _direction == Side.BUY else False

        # tx = contract.functions.add_limit_order(
        #     _leverage,
        #     margin,
        #     price,
        #     quantity,
        #     direction
        # ).build_transaction({
        #     "from": trader_address,
        #     "nonce": w3.eth.get_transaction_count(trader_address),
        #     "gas": 300000,
        #     "gasPrice": w3.to_wei(1, "gwei")
        # })

        # return tx
    
    def send_limit_order_removal(self, w3: Web3, trader_address: str):
        contract = w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)

        tx = contract.functions.close_limit_order().build_transaction({
            "from": trader_address,
            "nonce": w3.eth.get_transaction_count(trader_address),
            "gas": 300000,
            "gasPrice": w3.to_wei(1, "gwei")
        })

        return tx
    
    def call_fill_limit_order(self, w3: Web3, _address: str, _quantity_to_fill: int):
        print(f"Simulating fill for {_address} with quantity {_quantity_to_fill} — skipping Web3 transaction.")
        return True
        # contract = w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)
        # sender = w3.eth.account.from_key(PRIVATE_KEY)

        # quantity_to_fill = _quantity_to_fill

        # tx_params = {
        #     "from": sender,
        #     "nonce": w3.eth.get_transaction_count(sender),
        #     "gas": 300000,
        #     "gasPrice": w3.to_wei(1, "gwei")
        # }

        # tx = contract.functions.fill_limit_order(_address, quantity_to_fill).build_transaction(tx_params)
        # signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        # tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        # receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # return receipt
    
    def send_open_position(self, w3: Web3, _margin: float, _leverage: int, _direction: Side, trader_address: str, _price: float):
        print(f"Simulating open position for {trader_address} at {_price} (no Web3 tx).")
        return True
        # contract = w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)

        # margin = int(_margin * PRICE_SCALE)
        # direction: bool = True if _direction == Side.BUY else False
        # price: int = int(_price * PRICE_SCALE)

        # tx = contract.functions.open_position(margin, _leverage, direction, price).build_transaction({
        #     "from": trader_address,
        #     "nonce": w3.eth.get_transaction_count(trader_address),
        #     "gas": 300000,
        #     "gasPrice": w3.to_wei(1, "gwei")
        # })

        # return tx
    
    def send_close_position(self, w3: Web3, trader_address: str, _price: float):
        print(f"Simulating close position for {trader_address} at {_price} (no Web3 tx).")
        return True
        # contract = w3.eth.contract(address=PERPS_ADDRESS, abi=PERPS_ABI)

        # sender = w3.eth.account.from_key(PRIVATE_KEY)

        # price: int = int(_price * PRICE_SCALE)

        # tx = contract.functions.close_position(trader_address, price).build_transaction({
        #     "from": sender,
        #     "nonce": w3.eth.get_transaction_count(sender),
        #     "gas": 300000,
        #     "gasPrice": w3.to_wei(1, "gwei")
        # })

        # signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        # tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        # receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # return receipt

    def log_trade(self, order: Order, _fill_quantity, _taker_id, _maker_id, _taker_side, taker_order: Order) -> Trade:
        trade: Trade = Trade(
            timestamp = time.time(),
            trade_id = self.increment_trade_id(),
            price = order.price,
            quantity = _fill_quantity,
            taker_id = _taker_id,
            maker_id = _maker_id,
            taker_side = _taker_side,
            taker_fee = (taker_order.margin * taker_order.leverage) * self.TAKER_FEE,
            maker_fee = (order.margin * order.leverage) * self.MAKER_FEE
        )
        self.trade_events.append(trade)
        return trade

    def increment_order_id(self) -> int:
        self.order_id += 1
        return self.order_id
    
    def increment_trade_id(self) -> int:
        self.trade_id += 1
        return self.trade_id
    
    def get_best_bid(self) -> float:
        return max(self.bids) if self.bids else None
    
    def get_best_ask(self) -> float:
        return min(self.asks) if self.asks else None
    
    def snapshot(self) -> dict:
        def levels(book, reverse=False):
            items = reversed(book.items()) if reverse else book.items()
            return [
                [price, sum(o.quantity - o.filled_quantity for o in orders)]
                for price, orders in items
            ]
        return {
            "bids": levels(self.bids, reverse=True),
            "asks": levels(self.asks)
        }

    def add_limit_order(
            self,
            _trader_id: str,
            _side: Side,
            _price: float,
            _quantity: float,
            _leverage: int,
            _margin: float
    ):
        if _price >= 1:
            raise ValueError("Cannot set limit at 1")
        if _price <= 0:
            raise ValueError("Cannot set limit at 0")

        order: Order = Order(
            trader_id = _trader_id,
            order_id = self.increment_order_id(),
            side = _side,
            price = _price,
            quantity = _quantity,
            filled_quantity = 0,
            leverage = _leverage,
            margin = _margin,
            timestamp = time.time(),
            order_type = OrderType.LIMIT,
            status = Status.OPEN
        )

        book = self.bids if order.side == Side.BUY else self.asks

        self.send_limit_order(self.w3, order.leverage, order.margin, order.price, order.quantity, order.side, order.trader_id)

        if order.price not in book:
            order_list = [order]
            book[order.price] = order_list
        else:
            book[order.price].append(order)

    def remove_limit_order(self, _trader_id: str, _order_id: int, _side: Side, _price: float):
        book = self.bids if _side == Side.BUY else self.asks
        order_list = book[_price]
        removal_index = None

        for i in range(len(order_list)):
            order: Order = order_list[i]
            if order.trader_id == _trader_id and order.order_id == _order_id:
                removal_index = i
                break
        
        if removal_index is not None:
            order_list.pop(removal_index)

        if not order_list:
            del book[_price]

        self.send_limit_order_removal(self.w3, _trader_id)
    
    def market_order(
            self,
            _trader_id: str,
            _side: Side,
            _price: float,
            _quantity: float,
            _leverage: int,
            _margin: float,
    ):
        if _quantity <= 0:
            raise ValueError("Cannot send 0 or negative quantity orders")
        if _margin <= 0:
            raise ValueError("Margin is <= 0, need more margin")
        if _price <= 0:
            raise ValueError("Negative price values not allowed")
        
        order: Order = Order(
            trader_id = _trader_id,
            order_id = self.increment_order_id(),
            side = _side,
            price = _price,
            quantity = _quantity,
            filled_quantity = 0,
            leverage = _leverage,
            margin = _margin,
            timestamp = time.time(),
            order_type = OrderType.MARKET,
            status = Status.OPEN
        )

        book = self.asks if order.side == Side.BUY else self.bids
        fills = []

        if not book:
            raise ValueError("No book depth to execute market order")

        current_quantity: float = _quantity
        
        if order.side == Side.BUY:
            to_delete_levels = []
            for price_level in list(book.keys()):
                order_list = book[price_level]
                order_removal_list = []
                for resting_order in list(order_list):
                    current_order = resting_order
                    if current_quantity >= current_order.quantity:
                        fills.append(self.log_trade(current_order, current_order.quantity, order.trader_id, current_order.trader_id, order.side, order))
                        current_quantity = current_quantity - current_order.quantity
                        order_removal_list.append(resting_order)

                        self.call_fill_limit_order(self.w3, current_order.trader_id, current_order.quantity)

                        has_position = self.find_open_positions(current_order.trader_id, current_order.side)

                        if has_position:
                            self.pm.close_position(current_order.trader_id, self.asset_name, current_order.quantity, current_order.price)
                        else:
                            self.pm.create_position(current_order.trader_id, self.asset_name, current_order.side, current_order.price, current_order.quantity, current_order.leverage, current_order.margin)
                    else:
                        resting_filled_quantity = current_quantity
                        fills.append(self.log_trade(current_order, resting_filled_quantity, order.trader_id, current_order.trader_id, order.side, order))

                        # right now for mvp, we are refunsing margin that doesn't get filled and closing out the ramining limit
                        # current_order.quantity = current_order.quantity - current_quantity
                        # current_order.status = Status.PARTIALLY_FILLED

                        current_quantity = 0

                        self.call_fill_limit_order(self.w3, current_order.trader_id, resting_filled_quantity)

                        has_position = self.find_open_positions(current_order.trader_id, current_order.side)

                        if has_position:
                            self.pm.close_position(current_order.trader_id, self.asset_name, resting_filled_quantity, current_order.price)
                        else:
                            self.pm.create_position(current_order.trader_id, self.asset_name, current_order.side, current_order.price, resting_filled_quantity, current_order.leverage, current_order.margin)

                        # used for mvp refund system
                        order_removal_list.append(resting_order)

                    if current_quantity == 0:
                        break
                for removed_order in order_removal_list:
                    order_list.remove(removed_order)
                if not order_list:
                    to_delete_levels.append(price_level)
                if current_quantity == 0:
                    break
            for level in to_delete_levels:
                del book[level]
        else:
            to_delete_levels = []
            for price_level in reversed(list(book.keys())):
                order_list = book[price_level]
                order_removal_list = []
                for resting_order in list(order_list):
                    current_order = resting_order
                    if current_quantity >= current_order.quantity:
                        fills.append(self.log_trade(current_order, current_order.quantity, order.trader_id, current_order.trader_id, order.side, order))
                        current_quantity = current_quantity - current_order.quantity
                        order_removal_list.append(resting_order)

                        self.call_fill_limit_order(self.w3, current_order.trader_id, current_order.quantity)

                        has_position = self.find_open_positions(current_order.trader_id, current_order.side)

                        if has_position:
                            self.pm.close_position(current_order.trader_id, self.asset_name, current_order.quantity, current_order.price)
                        else:
                            self.pm.create_position(current_order.trader_id, self.asset_name, current_order.side, current_order.price, current_order.quantity, current_order.leverage, current_order.margin)
                    else:
                        resting_filled_quantity = current_quantity
                        fills.append(self.log_trade(current_order, resting_filled_quantity, order.trader_id, current_order.trader_id, order.side, order))

                        # right now for mvp, we are refunsing margin that doesn't get filled and closing out the ramining limit
                        # current_order.quantity = current_order.quantity - current_quantity
                        # current_order.status = Status.PARTIALLY_FILLED

                        current_quantity = 0

                        self.call_fill_limit_order(self.w3, current_order.trader_id, resting_filled_quantity)

                        has_position = self.find_open_positions(current_order.trader_id, current_order.side)

                        if has_position:
                            self.pm.close_position(current_order.trader_id, self.asset_name, resting_filled_quantity, current_order.price)
                        else:
                            self.pm.create_position(current_order.trader_id, self.asset_name, current_order.side, current_order.price, resting_filled_quantity, current_order.leverage, current_order.margin)

                        # used for mvp refund system
                        order_removal_list.append(resting_order)

                    if current_quantity == 0:
                        break
                for removed_order in order_removal_list:
                    order_list.remove(removed_order)
                if not order_list:
                    to_delete_levels.append(price_level)
                if current_quantity == 0:
                    break
            for level in to_delete_levels:
                del book[level]
        avg_price = sum(trade.price * trade.quantity for trade in fills) / sum(trade.quantity for trade in fills)
        total_quantity = sum(trade.quantity for trade in fills)

        has_opposite_position: bool = self.find_open_positions(order.trader_id, order.side)

        if has_opposite_position:
            self.send_close_position(self.w3, order.trader_id, avg_price)

            self.pm.close_position(order.trader_id, self.asset_name, total_quantity, avg_price)
        else:
            self.send_open_position(self.w3, order.margin, order.leverage, order.side, order.trader_id, avg_price)

            self.pm.create_position(order.trader_id, self.asset_name, order.side, avg_price, total_quantity, order.leverage, order.margin)
    
    def find_open_positions(self, _address: str, _order_side: Side) -> bool:
        account = self.pm.accounts.get(_address)
        if account is None:
            return False
        for position in account.positions:
            if position.status == Status.OPEN and \
            position.market_id == self.asset_name and \
            _order_side != position.side:
                return True
        return False


# market = OrderBook("BTC")

# market.add_limit_order("01", Side.BUY, 0.1, 0.2, 0, 2)
# market.add_limit_order("01", Side.BUY, 0.1, 0.7, 0, 10)

# print(market.bids[0.1])
# print()

# # market.remove_limit_order("01", 1, Side.BUY, 0.1)
# # print("removing order")
# # print()

# print(market.bids[0.1])
# print()

# market.market_order("02", Side.SELL, 0.1, 0.9, 2, 10)

# print(market.bids)
# print()
# print(market.trade_events)
