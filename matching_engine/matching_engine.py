from dataclasses import dataclass
from enum import Enum
from sortedcontainers import SortedDict
import time

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
    timestamp: int
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
    timestamp: int
    order_type: OrderType
    status: Status

class OrderBook:
    def __init__(self, _asset_name):
        self.asset_name: str = _asset_name
        self.order_id: int = 0
        self.trade_id: int = 0
        self.bids: SortedDict = SortedDict()
        self.asks: SortedDict = SortedDict()
        self.trade_events = []
        self.MAKER_FEE: float = 0.0002
        self.TAKER_FEE: float = 0.0006

    def log_trade(self, order: Order, _fill_quantity, _taker_id, _maker_id, _taker_side, taker_order: Order):
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
        book_snapshot = {} 
        book_snapshot["bids"] = self.bids
        book_snapshot["asks"] = self.asks
        return book_snapshot

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

        if not book:
            raise ValueError("No book depth to execute market order")

        current_quantity: float = _quantity
        
        if order.side == Side.BUY:
            for price_level in book:
                order_list = book[price_level]
                order_removal_list = []
                for resting_order in order_list:
                    current_order = resting_order
                    if current_quantity >= current_order.quantity:
                        self.log_trade(current_order, current_order.quantity, order.trader_id, current_order.trader_id, order.side, order)
                        current_quantity = current_quantity - current_order.quantity
                        order_removal_list.append(resting_order)
                    else:
                        resting_filled_quantity = current_quantity
                        self.log_trade(current_order, resting_filled_quantity, order.trader_id, current_order.trader_id, order.side, order)
                        current_order.quantity = current_order.quantity - current_quantity
                        current_order.status = Status.PARTIALLY_FILLED
                        current_quantity = 0

                    if current_quantity == 0:
                        return
                for order in order_removal_list:
                    order_list.remove(order)
                if not order_list:
                    del book[price_level]
        else:
            for price_level in reversed(book.keys()):
                order_list = book[price_level]
                order_removal_list = []
                for resting_order in order_list:
                    current_order = resting_order
                    if current_quantity >= current_order.quantity:
                        self.log_trade(current_order, current_order.quantity, order.trader_id, current_order.trader_id, order.side, order)
                        current_quantity = current_quantity - current_order.quantity
                        order_removal_list.append(resting_order)
                    else:
                        resting_filled_quantity = current_quantity
                        self.log_trade(current_order, resting_filled_quantity, order.trader_id, current_order.trader_id, order.side, order)
                        current_order.quantity = current_order.quantity - current_quantity
                        current_order.status = Status.PARTIALLY_FILLED
                        current_quantity = 0

                    if current_quantity == 0:
                        break
                for order in order_removal_list:
                    order_list.remove(order)
                if not order_list:
                    del book[price_level]
        return self.trade_events[-1]

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