# tests/test_matching_engine.py

import pytest
from unittest.mock import Mock
from types import SimpleNamespace
from fastapi.testclient import TestClient

# import AFTER defining WEB3_IMPORT_PATHS to avoid circular import issues
WEB3_IMPORT_PATHS = (
    "off_chain_systems.matching_engine.Web3",
    "off_chain_systems.position_manager.Web3",
)
from off_chain_systems.matching_engine import OrderBook, Side, Status, OrderType
from off_chain_systems.position_manager import PositionManager, Side as PMSide, Status as PMStatus


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
    monkeypatch.setenv("ORACLE_ADDRESS", "0x0000000000000000000000000000000000000001")
    monkeypatch.setenv("ORACLE_ABI", "[]")

    # ---------- Fake Web3 implementation ----------
    class FakeEthAccount:
        @staticmethod
        def from_key(key):
            return SimpleNamespace(address="0xFAKEACCOUNT")

    class FakeContractFunction:
        def __init__(self, value_attr):
            self._value_attr = value_attr

        def call(self):
            return getattr(FakeWeb3, self._value_attr)

    class FakeContract:
        def __init__(self):
            self.functions = SimpleNamespace(
                get_oracle_price=lambda: FakeContractFunction("_oracle_price")
            )

    class FakeEth:
        def __init__(self):
            self.account = FakeEthAccount()
            self.default_account = None

        def get_transaction_count(self, addr):
            return 0

        def contract(self, address=None, abi=None):
            return FakeContract()

    class FakeWeb3:
        _oracle_price = 0

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


    # Patch the Web3 class used inside matching_engine and position_manager
    for path in WEB3_IMPORT_PATHS:
        monkeypatch.setattr(path, FakeWeb3)
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


@pytest.fixture
def position_manager():
    pm = PositionManager()
    pm.accounts.clear()
    pm.position_id = 0
    return pm


@pytest.fixture
def api_client(monkeypatch):
    from off_chain_systems import server

    def _tx(label: str):
        return {
            "to": "0xTxDestination",
            "from": "0xTxSender",
            "data": f"{label}_data",
            "gas": 21000,
            "gasPrice": 1,
            "value": 0,
        }

    fake_engine = Mock()
    fake_engine.order_id = 0
    fake_engine.snapshot.return_value = {
        "bids": [{"price": 0.4, "quantity": 1.0}],
        "asks": [{"price": 0.5, "quantity": 2.0}],
    }
    fake_engine.trade_events = [
        SimpleNamespace(trade_id=1, price=0.44, quantity=1.5),
    ]
    fake_engine.market_order = Mock()
    fake_engine.remove_limit_order = Mock()

    def _add_limit_order(*args, **kwargs):
        fake_engine.order_id += 1

    fake_engine.add_limit_order = Mock(side_effect=_add_limit_order)

    fake_pm = Mock()
    fake_pm.accounts = {
        "0xKnown": SimpleNamespace(positions=[
            SimpleNamespace(
                position_id=10,
                market_id="BTC",
                side=Side.BUY,
                quantity=1.0,
                entry_price=100.0,
                leverage=5,
                margin=20.0,
                unrealized_pnl=0.0,
                status=Status.OPEN
            )
        ])
    }

    fake_pm.get_perp_price.return_value = 0.42

    monkeypatch.setattr(server, "engine", fake_engine)
    monkeypatch.setattr(server, "pm", fake_pm)

    client = TestClient(server.app)
    return client, fake_engine, fake_pm


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


# ---------------------------------------------------------------------
#  PositionManager tests
# ---------------------------------------------------------------------
def test_position_manager_create_account(position_manager):
    address = "0xAlice"
    position_manager.create_account(address)

    assert address in position_manager.accounts
    account = position_manager.accounts[address]
    assert account.account_id == address
    assert account.positions == []


def test_position_manager_create_position_requires_registered_account(position_manager):
    with pytest.raises(ValueError, match="registered user"):
        position_manager.create_position(
            "0xUnregistered",
            "BTC",
            PMSide.BUY,
            0.4,
            1.0,
            2,
            100,
        )


def test_position_manager_create_position_adds_open_position(position_manager):
    position_manager.create_account("0xAlice")
    position_manager.create_position("0xAlice", "BTC", PMSide.BUY, 0.4, 1.5, 3, 250)

    account = position_manager.accounts["0xAlice"]
    assert len(account.positions) == 1
    position = account.positions[0]
    assert position.position_id == 1
    assert position.market_id == "BTC"
    assert position.side == PMSide.BUY
    assert position.quantity == pytest.approx(1.5)
    assert position.status == PMStatus.OPEN


def test_position_manager_update_pnl_buy_side(monkeypatch, position_manager):
    position_manager.create_account("0xAlice")
    position_manager.create_position("0xAlice", "BTC", PMSide.BUY, 0.5, 2.0, 2, 150)
    position = position_manager.accounts["0xAlice"].positions[0]

    # Force oracle to return a higher price
    monkeypatch.setattr(position_manager, "get_perp_price", lambda: 0.6)

    pnl = position_manager.update_pnl(position)
    expected = ((0.6 - 0.5) / 0.5) * (2 * 150)

    assert pnl == pytest.approx(expected)
    assert position.unrealized_pnl == pytest.approx(expected)


def test_position_manager_close_position_partial(position_manager):
    position_manager.create_account("0xAlice")
    position_manager.create_position("0xAlice", "BTC", PMSide.BUY, 0.5, 3.0, 2, 120)
    position = position_manager.accounts["0xAlice"].positions[0]

    pnl = position_manager.close_position("0xAlice", "BTC", 1.0, 0.55)
    expected = (0.55 - 0.5) * position.margin * position.leverage

    assert pnl == pytest.approx(expected)
    assert position.quantity == pytest.approx(2.0)
    assert position.status == PMStatus.OPEN
    assert position.realized_pnl == pytest.approx(expected)


def test_position_manager_close_position_full(position_manager):
    position_manager.create_account("0xBob")
    position_manager.create_position("0xBob", "ETH", PMSide.BUY, 1.0, 1.0, 3, 200)
    position = position_manager.accounts["0xBob"].positions[0]

    pnl = position_manager.close_position("0xBob", "ETH", 1.0, 1.1)
    expected = (1.1 - 1.0) * position.margin * position.leverage

    assert pnl == pytest.approx(expected)
    assert position.quantity == pytest.approx(0.0)
    assert position.status == PMStatus.CLOSED
    assert position.realized_pnl == pytest.approx(expected)
    assert position.close_timestamp > 0


# ---------------------------------------------------------------------
#  Server API tests
# ---------------------------------------------------------------------
def test_server_root(api_client):
    client, _, _ = api_client

    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Tachyon backend running"}


def test_server_orderbook_endpoint(api_client):
    client, fake_engine, _ = api_client

    response = client.get("/orderbook")
    assert response.status_code == 200
    assert response.json() == fake_engine.snapshot.return_value
    fake_engine.snapshot.assert_called_once()


def test_server_positions_endpoint_known(api_client):
    client, _, fake_pm = api_client

    response = client.get("/positions/0xKnown")
    assert response.status_code == 200
    body = response.json()
    assert "positions" in body
    assert len(body["positions"]) == 1
    assert body["positions"][0]["position_id"] == 10
    fake_pm.accounts["0xKnown"]  # ensure fixture still accessible


def test_server_positions_endpoint_unknown(api_client):
    client, _, _ = api_client

    response = client.get("/positions/0xUnknown")
    assert response.status_code == 200
    assert response.json() == {"positions": []}


def test_server_price_endpoints(api_client):
    client, _, fake_pm = api_client

    fake_pm.get_oracle_price.return_value = 0.42
    fake_pm.get_perp_price.return_value = 0.37

    oracle_response = client.get("/oracle_price")
    assert oracle_response.status_code == 200
    assert oracle_response.json() == 0.42

    # --- Perp price endpoint ---
    perp_response = client.get("/perp_price")
    assert perp_response.status_code == 200
    assert perp_response.json() == 0.37

def test_server_limit_order_endpoint(api_client):
    client, fake_engine, _ = api_client

    payload = {
        "direction": "buy",
        "leverage": 3,
        "margin": 150.0,
        "price": 0.45,
        "quantity": 2.0,
        "trader_address": "0xTrader",
    }
    response = client.post("/tx/limit_order", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["order_id"] == fake_engine.order_id
    assert body["orderbook"] == fake_engine.snapshot.return_value

    fake_engine.add_limit_order.assert_called_once()
    kwargs = fake_engine.add_limit_order.call_args.kwargs
    assert kwargs["_trader_id"] == "0xTrader"
    assert kwargs["_side"] == Side.BUY
    assert kwargs["_price"] == 0.45
    assert kwargs["_quantity"] == 2.0
    fake_engine.snapshot.assert_called_once()


def test_server_market_order_endpoint(api_client):
    client, fake_engine, _ = api_client

    payload = {
        "direction": "sell",
        "leverage": 4,
        "margin": 200.0,
        "price": 0.5,
        "quantity": 1.25,
        "trader_address": "0xTrader",
    }
    response = client.post("/tx/market_order", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["orderbook"] == fake_engine.snapshot.return_value
    assert body["trades"] == [trade.__dict__ for trade in fake_engine.trade_events]

    fake_engine.market_order.assert_called_once()
    kwargs = fake_engine.market_order.call_args.kwargs
    assert kwargs["_trader_id"] == "0xTrader"
    assert kwargs["_side"] == Side.SELL
    assert kwargs["_price"] == 0.5
    assert kwargs["_quantity"] == 1.25
    fake_engine.snapshot.assert_called_once()


def test_server_remove_limit_order_endpoint(api_client):
    client, fake_engine, _ = api_client

    payload = {
        "trader_address": "0xTrader",
        "order_id": 42,
        "direction": "buy",
        "price": 0.45,
    }
    response = client.post("/tx/remove_limit_order", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["orderbook"] == fake_engine.snapshot.return_value

    fake_engine.remove_limit_order.assert_called_once()
    kwargs = fake_engine.remove_limit_order.call_args.kwargs
    assert kwargs["_trader_id"] == "0xTrader"
    assert kwargs["_order_id"] == 42
    assert kwargs["_side"] == Side.BUY
    assert kwargs["_price"] == 0.45
    fake_engine.snapshot.assert_called_once()


def test_server_trades_endpoint(api_client):
    client, fake_engine, _ = api_client

    response = client.get("/trades")
    assert response.status_code == 200
    body = response.json()
    assert "trades" in body
    assert len(body["trades"]) == len(fake_engine.trade_events)
    assert body["trades"][0]["trade_id"] == fake_engine.trade_events[0].trade_id
