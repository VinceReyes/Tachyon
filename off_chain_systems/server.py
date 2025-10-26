from fastapi import FastAPI, Body, HTTPException
from off_chain_systems.matching_engine import OrderBook, Side
from off_chain_systems.position_manager import PositionManager, Status
import os
from dotenv import load_dotenv
import json
import threading
from contextlib import asynccontextmanager

load_dotenv()

PERPS_ADDRESS = os.getenv("PERPS_ADDRESS")
PERPS_ABI = json.loads(os.getenv("PERPS_ABI"))
RPC_URL = os.getenv("RPC_URL")
MARKET_NAME = os.getenv("MARKET_NAME")

pm: PositionManager = PositionManager()
engine: OrderBook = OrderBook(MARKET_NAME, pm)
pm.orderbook = engine

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    thread = threading.Thread(target=pm.management_loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        pass

app = FastAPI(title="Tachyon Backend API", lifespan=app_lifespan)

@app.get("/orderbook")
def get_orderbook():
    return engine.snapshot()

@app.get("/positions/{address}")
def get_open_positions(address: str):
    account = pm.accounts.get(address)
    if not account:
        return {"positions": []}

    # account is an Account object with a .positions list of Position objects
    positions_data = []
    for pos in account.positions:
        if pos.status != Status.OPEN:
            continue
        pm.update_pnl(pos)
        positions_data.append({
            "position_id": pos.position_id,
            "market": pos.market_id,
            "side": pos.side.value,
            "size": pos.quantity,
            "entry": pos.entry_price,
            "leverage": pos.leverage,
            "margin": pos.margin,
            "pnl": pos.unrealized_pnl,
            "status": pos.status.value,
        })

    return {"positions": positions_data}

@app.get("/oracle_price")
def get_oracle_pricing():
    return pm.get_oracle_price()

@app.get("/perp_price")
def get_perp_pricing():
    return pm.get_perp_price()

@app.post("/tx/limit_order")
def place_limit_order(order: dict = Body(...)):
    try:
        pm.create_account(order["trader_address"])
        direction_enum = Side.BUY if order["direction"].lower() == "buy" else Side.SELL
        engine.add_limit_order(
            _trader_id=order["trader_address"],
            _side=direction_enum,
            _price=order["price"],
            _quantity=order["quantity"],
            _leverage=order["leverage"]
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "order_id": engine.order_id,
        "orderbook": engine.snapshot(),
    }

@app.post("/tx/market_order")
def place_market_order(order: dict = Body(...)):
    try:
        pm.create_account(order["trader_address"])
        direction_enum = Side.BUY if order["direction"].lower() == "buy" else Side.SELL
        engine.market_order(
            _trader_id=order["trader_address"],
            _side=direction_enum,
            _quantity=order["quantity"],
            _leverage=order["leverage"]
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recent_trades = [t.__dict__ for t in engine.trade_events[-20:]]
    return {
        "status": "ok",
        "orderbook": engine.snapshot(),
        "trades": recent_trades,
    }

@app.post("/tx/remove_limit_order")
def cancel_limit_order(order: dict = Body(...)):
    try:
        pm.create_account(order["trader_address"])
        trader_address = order["trader_address"]
        engine.remove_limit_order(
            _trader_id=trader_address,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"Missing field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "orderbook": engine.snapshot(),
    }

@app.get("/trades")
def get_trades():
    trades = [t.__dict__ for t in engine.trade_events[-20:]]
    return {"trades": trades}

@app.get("/")
def root():
    return {"status": "ok", "message": "Tachyon backend running"}

# ------------------------------------------------------------------
#                              TESTS
# ------------------------------------------------------------------
@app.post("/seed_orders")
def seed_orders():
    engine.add_limit_order("0xa0Ee7A142d267C1f36714E4a8F75612F20a79720", Side.BUY, 0.5, 5, 2, 100.0)
    engine.add_limit_order("0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f", Side.SELL, 0.9, 4, 2, 100.0)
    return {"status": "ok"}

@app.post("/simulate_market_fill")
def simulate_market_fill():
    try:
        # Example trader addresses (you can swap to any)
        maker = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
        taker = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

        # Ensure both accounts exist in PositionManager
        pm.create_account(maker)
        pm.create_account(taker)

        # 1️⃣ Maker posts a limit order (SELL)
        engine.add_limit_order(
            _trader_id=maker,
            _side=Side.SELL,
            _price=0.98,
            _quantity=2.0,
            _leverage=5,
            _margin=100.0
        )

        # 2️⃣ Taker executes a market BUY that should match the maker
        engine.market_order(
            _trader_id=taker,
            _side=Side.BUY,
            _price=0.98,
            _quantity=2.0,
            _leverage=5,
            _margin=100.0
        )

        return {"status": "ok", "message": "Simulated market fill executed."}

    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/seed_positions")
def seed_positions():
    trader = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

    # Ensure the account exists first
    pm.create_account(trader)

    # Create dummy positions using PositionManager's API
    pm.create_position(
        _trader_id=trader,
        _asset_name="YES_TARIFF",
        _side=Side.BUY,
        _entry_price=0.95,
        _quantity=3.5,
        _leverage=5,
        _margin=100.0
    )

    pm.create_position(
        _trader_id=trader,
        _asset_name="BTC_EVENT",
        _side=Side.SELL,
        _entry_price=1.05,
        _quantity=2.0,
        _leverage=3,
        _margin=50.0
    )

    return {"status": "ok", "message": f"Seeded positions for {trader}"}

