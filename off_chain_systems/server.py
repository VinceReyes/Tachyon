from fastapi import FastAPI, Body
from matching_engine import OrderBook, Side
from position_manager import PositionManager
from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

PERPS_ADDRESS = os.getenv("PERPS_ADDRESS")
PERPS_ABI = os.getenv("PERPS_ABI")
RPC_URL = os.getenv("RPC_URL")
MARKET_NAME = os.getenv("MARKET_NAME")

pm: PositionManager = PositionManager()
engine: OrderBook = OrderBook(MARKET_NAME, pm)

app = FastAPI(title="Tachyon Backend API")

@app.get("/orderbook")
def get_orderbook():
    return engine.snapshot()

@app.get("/positions/{address}")
def get_open_positions(address: str):
    account = pm.accounts.get(address)
    if not account:
        return {"positions": []}
    positions = [p.__dict__ for p in account.positions]
    return {"positions": positions}

@app.get("/oracle_price")
def get_oracle_price():
    return {"price": pm.get_price()}

@app.post("/tx/limit_order")
def build_limit_order(order: dict = Body(...)):
    direction_enum = Side.BUY if order["direction"].lower() == "buy" else Side.SELL
    tx = engine.send_limit_order(
        engine.w3,
        _leverage=order["leverage"],
        _margin=order["margin"],
        _price=order["price"],
        _quantity=order["quantity"],
        _direction=direction_enum,
        trader_address=order["trader_address"]
    )

    return {
        "to": tx["to"],
        "from": tx["from"],
        "data": tx["data"].hex() if hasattr(tx["data"], "hex") else tx["data"],
        "gas": tx["gas"],
        "gasPrice": tx["gasPrice"],
        "value": tx.get("value", 0),
    }

@app.post("/tx/market_order")
def build_market_order(order: dict = Body(...)):
    direction_enum = Side.BUY if order["direction"].lower() == "buy" else Side.SELL
    tx = engine.send_market_order(
        engine.w3,
        _margin=order["margin"],
        _leverage=order["leverage"],
        _direction=direction_enum,
        trader_address=order["trader_address"]
    )

    return {
        "to": tx["to"],
        "from": tx["from"],
        "data": tx["data"].hex() if hasattr(tx["data"], "hex") else tx["data"],
        "gas": tx["gas"],
        "gasPrice": tx["gasPrice"],
        "value": tx.get("value", 0),
    }

@app.post("/tx/remove_limit_order")
def build_limit_order_removal(order: dict = Body(...)):
    trader_address = order["trader_address"]

    tx = engine.send_limit_order_removal(
        engine.w3,
        trader_address
    )

    return {
        "to": tx["to"],
        "from": tx["from"],
        "data": tx["data"].hex() if hasattr(tx["data"], "hex") else tx["data"],
        "gas": tx["gas"],
        "gasPrice": tx["gasPrice"],
        "value": tx.get("value", 0),
    }

@app.get("/trades")
def get_trades():
    trades = [t.__dict__ for t in engine.trade_events[-20:]]
    return {"trades": trades}

@app.get("/")
def root():
    return {"status": "ok", "message": "Tachyon backend running"}