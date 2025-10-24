# tests/test_matching_engine.py

import pytest
from unittest.mock import Mock
from types import SimpleNamespace

# import AFTER defining WEB3_IMPORT_PATH to avoid circular import issues
WEB3_IMPORT_PATH = "off_chain_systems.matching_engine.Web3"
from off_chain_systems.matching_engine import OrderBook, Side, Status, OrderType


# ---------------------------------------------------------------------
#  Fixture to bypass real Web3 and .env dependencies
# ---------------------------------------------------------------------
@pytest.fixture(autouse=True)
def fake_env_and_web3(monkeypatch):
    """
    Set dummy env vars and replace Web3 with a fake version
    so OrderBook.__init__ never connects to a real node.
    """
    # Provide dummy env values expected by matching_engine
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "deadbeef" * 8)
    monkeypatch.setenv("RPC_URL", "http://127.0.0.1:8545")
    monkeypatch.setenv("PERPS_ADDRESS", "0x0000000000000000000000000000000000000000")
    monkeypatch.setenv("PERPS_ABI", "[]")

    # ---------- Fake Web3 implementation ----------
    class FakeEthAccount:
        @staticmethod
        def from_key(key):
            return SimpleNamespace(address="0xFAKEACCOUNT")

    class FakeEth:
        def __init__(self):
            self.account = FakeEthAccount()
            self.default_account = None

        def get_transaction_count(self, addr):
            return 0

    class FakeWeb3:
        class HTTPProvider:
            # stub so Web3(HTTPProvider(...)) doesn't crash
            def __init__(self, url):
                self.url = url

        def __init__(self, provider=None):
            self.provider = provider
            self.eth = FakeEth()

        def is_connected(self):
            return True

        def to_wei(self, amount, unit):
            return int(amount * 1e9) if unit == "gwei" else int(amount)


    # Patch the Web3 class used inside matching_engine
    monkeypatch.setattr(WEB3_IMPORT_PATH, FakeWeb3)
    yield


# ---------------------------------------------------------------------
#  Fixture for mock OrderBook with PositionManager dependency mocked
# ---------------------------------------------------------------------
@pytest.fixture
def mock_orderbook():
    fake_pm = Mock()
    fake_pm.accounts = {}
    fake_pm.create_position = Mock()
    fake_pm.close_position = Mock()

    ob = OrderBook(_asset_name="BTC", _pm=fake_pm)

    # patch on-chain network methods to avoid RPC calls
    ob.send_limit_order = Mock(return_value={"tx": "fake_tx"})
    ob.call_fill_limit_order = Mock(return_value={"tx": "fake_tx"})
    ob.send_open_position = Mock(return_value={"tx": "fake_tx"})
    ob.send_close_position = Mock(return_value={"tx": "fake_tx"})
    ob.send_limit_order_removal = Mock(return_value={"tx": "fake_tx"})

    return ob


@pytest.fixture
def register_account(mock_orderbook):
    """
    Helper to register mock PositionManager accounts with optional open positions.
    """

    def _register(address: str, *, positions=None):
        positions = positions or []
        mock_orderbook.pm.accounts[address] = SimpleNamespace(positions=list(positions))
        return mock_orderbook.pm.accounts[address]

    return _register


# ---------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------
def test_add_limit_order_creates_book_entry(mock_orderbook):
    ob = mock_orderbook

    ob.add_limit_order(
        _trader_id="0xTrader",
        _side=Side.BUY,
        _price=0.25,
        _quantity=0.5,
        _leverage=2,
        _margin=100,
    )

    assert len(ob.bids) == 1
    assert 0.25 in ob.bids
    order = ob.bids[0.25][0]
    assert order.status == Status.OPEN
    assert order.order_type == OrderType.LIMIT

    ob.send_limit_order.assert_called_once()


def test_remove_limit_order_removes_from_book(mock_orderbook):
    ob = mock_orderbook

    ob.add_limit_order("0x1", Side.BUY, 0.25, 1.0, 2, 100)
    ob.add_limit_order("0x1", Side.BUY, 0.25, 2.0, 2, 100)
    assert len(ob.bids[0.25]) == 2

    first_order = ob.bids[0.25][0]
    ob.remove_limit_order(
        _trader_id=first_order.trader_id,
        _order_id=first_order.order_id,
        _side=Side.BUY,
        _price=0.25,
    )

    assert len(ob.bids[0.25]) == 1
    ob.send_limit_order_removal.assert_called_once()


def test_get_best_bid_and_ask(mock_orderbook):
    ob = mock_orderbook

    ob.add_limit_order("0x1", Side.BUY, 0.20, 1.0, 2, 100)
    ob.add_limit_order("0x2", Side.BUY, 0.30, 1.0, 2, 100)
    ob.add_limit_order("0x3", Side.SELL, 0.40, 1.0, 2, 100)
    ob.add_limit_order("0x4", Side.SELL, 0.50, 1.0, 2, 100)

    assert ob.get_best_bid() == 0.30
    assert ob.get_best_ask() == 0.40


def test_snapshot_returns_both_books(mock_orderbook):
    ob = mock_orderbook
    ob.add_limit_order("0x1", Side.BUY, 0.20, 1.0, 2, 100)
    ob.add_limit_order("0x2", Side.SELL, 0.40, 1.0, 2, 100)

    snap = ob.snapshot()
    assert "bids" in snap and "asks" in snap
    assert len(snap["bids"]) == 1
    assert len(snap["asks"]) == 1


def test_add_limit_order_rejects_invalid_prices(mock_orderbook):
    ob = mock_orderbook

    with pytest.raises(ValueError):
        ob.add_limit_order("0x1", Side.BUY, 1.0, 1.0, 2, 100)
    with pytest.raises(ValueError):
        ob.add_limit_order("0x1", Side.SELL, 0.0, 1.0, 2, 100)

    ob.send_limit_order.assert_not_called()


def test_remove_limit_order_clears_price_level_when_empty(mock_orderbook):
    ob = mock_orderbook

    ob.add_limit_order("0x1", Side.SELL, 0.40, 1.0, 2, 100)
    order = ob.asks[0.40][0]

    ob.remove_limit_order(order.trader_id, order.order_id, order.side, order.price)

    assert 0.40 not in ob.asks
    ob.send_limit_order_removal.assert_called_once()


def test_market_order_buy_consumes_levels_and_opens_position(mock_orderbook, register_account):
    ob = mock_orderbook
    register_account("0xMakerA")
    register_account("0xMakerB")
    register_account("0xBuyer")

    ob.add_limit_order("0xMakerA", Side.SELL, 0.40, 1.0, 3, 100)
    ob.add_limit_order("0xMakerB", Side.SELL, 0.45, 2.0, 4, 150)

    ob.market_order("0xBuyer", Side.BUY, 0.50, 3.0, 5, 200)

    assert not ob.asks
    assert len(ob.trade_events) == 2
    assert ob.pm.close_position.call_count == 0
    ob.send_open_position.assert_called_once()
    ob.send_close_position.assert_not_called()
    assert ob.call_fill_limit_order.call_count == 2

    maker_calls = [
        entry for entry in ob.pm.create_position.call_args_list if entry[0][0] in {"0xMakerA", "0xMakerB"}
    ]
    assert len(maker_calls) == 2

    taker_call = next(entry for entry in ob.pm.create_position.call_args_list if entry[0][0] == "0xBuyer")
    _, asset_name, side, avg_price, total_qty, leverage, margin = taker_call[0]
    assert asset_name == "BTC"
    assert side == Side.BUY
    assert total_qty == pytest.approx(3.0)
    assert avg_price == pytest.approx((0.40 * 1.0 + 0.45 * 2.0) / 3.0)
    assert leverage == 5
    assert margin == 200


def test_market_order_sell_closes_existing_position(mock_orderbook, register_account):
    ob = mock_orderbook
    register_account("0xMakerBid")
    register_account(
        "0xSeller",
        positions=[SimpleNamespace(status=Status.OPEN, market_id="BTC", side=Side.BUY)],
    )

    ob.add_limit_order("0xMakerBid", Side.BUY, 0.55, 1.5, 3, 120)

    ob.market_order("0xSeller", Side.SELL, 0.50, 1.5, 4, 90)

    assert not ob.bids
    assert len(ob.trade_events) == 1
    ob.send_close_position.assert_called_once()
    ob.send_open_position.assert_not_called()
    ob.pm.close_position.assert_called_once_with("0xSeller", "BTC", pytest.approx(1.5), pytest.approx(0.55))
    # Maker receives a new position for the filled order.
    ob.pm.create_position.assert_any_call("0xMakerBid", "BTC", Side.BUY, 0.55, 1.5, 3, 120)


def test_market_order_raises_without_depth(mock_orderbook, register_account):
    ob = mock_orderbook
    register_account("0xBuyer")

    with pytest.raises(ValueError, match="No book depth"):
        ob.market_order("0xBuyer", Side.BUY, 0.30, 1.0, 2, 100)


@pytest.mark.parametrize(
    "kwargs,expected_message",
    [
        ({"_side": Side.BUY, "_price": 0.40, "_quantity": 0.0, "_leverage": 2, "_margin": 100}, "Cannot send 0 or negative quantity orders"),
        ({"_side": Side.SELL, "_price": 0.40, "_quantity": 1.0, "_leverage": 2, "_margin": 0}, "Margin is <= 0"),
        ({"_side": Side.BUY, "_price": 0.0, "_quantity": 1.0, "_leverage": 2, "_margin": 100}, "Negative price values not allowed"),
    ],
)
def test_market_order_rejects_invalid_inputs(mock_orderbook, register_account, kwargs, expected_message):
    ob = mock_orderbook
    register_account("0xTrader")

    with pytest.raises(ValueError, match=expected_message):
        ob.market_order("0xTrader", **kwargs)
