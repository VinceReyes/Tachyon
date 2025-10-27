# Tachyon Perpetual Futures

Tachyon is a hybrid on-chain/off-chain perpetual futures exchange that settles against a prediction market on Polymarket. The protocol publishes on-chain pricing and funding data, while an off-chain matching engine, position manager, and FastAPI service coordinate user orders, positions, and liquidations. Keepers continuously sync Polymarket market data into the Tachyon oracle so that every perpetual contract tracks the underlying Polymarket YES token.

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Local Development](#local-development)
- [Deployment Guide](#deployment-guide)
- [API Surface](#api-surface)
- [Troubleshooting & Tips](#troubleshooting--tips)

## Project Overview

- **Goal:** Offer leveraged perpetual exposure on Polymarket events. Each perps market settles toward the Polymarket midpoint price gathered directly from the clob.
- **Settlement source:** The `keeper/oracle_update_script.py` process reads Polymarket data (via `https://gamma-api.polymarket.com` and `https://clob.polymarket.com/midpoint`) and pushes the scaled price on-chain to `oracle.vy`.
- **Execution workflow:** Traders interact with the FastAPI server (directly or via the CLI). Orders are routed to the in-memory `OrderBook`, which interfaces with the on-chain `perps_contract.vy` for final settlement and state updates.
- **Risk management:** `PositionManager` tracks account risk off-chain and drives liquidation requests to the perps contract whenever unrealised PnL breaches thresholds. Funding payments are computed from deviations between Polymarket (oracle) pricing and the perp mark price.

## Architecture

| Layer            | Components                                                                                                                     | Responsibilities                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| On-chain (Vyper) | `src/perps_contract.vy`, `src/oracle.vy`, `src/vault.vy`, `src/mock_usdc.vy`                                                    | Custody user margin, settle fills, expose oracle interface, account for funding, and distribute PnL.                               |
| Off-chain core   | `off_chain_systems/matching_engine.py`, `off_chain_systems/position_manager.py`, `off_chain_systems/server.py`                 | Maintain sorted order book, calculate fills, create/close positions, enforce risk checks, offer REST API endpoints.               |
| Interfaces       | `cli/cli.py`, `cli/wallet_manager.py`                                                                                           | Operator-facing CLI that can submit orders, query order book, and open a live dashboard.                                          |
| Keepers          | `keeper/oracle_update_script.py`, `keeper/funding_update_script.py`                                                             | Sync Polymarket midpoint prices, update oracle and perp price feeds, and push funding rate adjustments to chain.                  |
| Tooling          | Moccasin (`mox`) scripts and `tests/`                                                                                           | Deploy and test smart contracts locally or on supported testnets.                                                                 |

### Data Flow

1. **Oracle sync** — The oracle keeper fetches the Polymarket YES token midpoint and posts the scaled value to `oracle.vy`.
2. **Order intake** — Traders submit limit/market orders through the API. The matching engine enforces leverage/margin rules and sends transactions to the perps contract.
3. **Position tracking** — `PositionManager` keeps derived state (PnL, funding, liquidation checks) and exposes read endpoints (`/positions/{address}`).
4. **Funding loop** — The funding keeper compares perp prices against oracle prices and updates the perps contract funding rate and mark price.
5. **Settlement** — When orders fill, the engine signs and submits the corresponding on-chain transactions using the configured hot wallet.

## Repository Layout

- `src/`: Vyper smart contracts for the Tachyon protocol.
- `off_chain_systems/`: Matching engine, position manager, and FastAPI server.
- `cli/`: Rich-powered command line interface plus wallet helper.
- `keeper/`: Oracle and funding keepers that poll Polymarket and the Tachyon API.
- `script/`, `tests/`: Moccasin scripts/tests for contract deployment and validation.
- `out/`: Compiled contract artifacts (used for ABIs).

## Prerequisites

- Python 3.11+ (recommended to use `uv` or `pip` within a virtual environment).
- Access to an EVM RPC endpoint (e.g., Anvil, Sepolia, or another testnet).
- A funded private key for the network you deploy to (hot wallet used by keepers and the matching engine).
- `mox` (Moccasin CLI) if you plan to deploy or test contracts (`pip install moccasin`).
- Optional: `uv` command (`pip install uv`) for fast dependency resolution respecting `pyproject.toml` and `uv.lock`.

## Environment Configuration

Create a `.env` file in the project root with the following entries:

| Variable         | Description                                                                                         | Example / Notes |
| ---------------- | --------------------------------------------------------------------------------------------------- | --------------- |
| `PRIVATE_KEY`    | Hex-encoded private key used for signing perps/oracle transactions.                                 | `0xabc123...` (do **not** commit). |
| `RPC_URL`        | HTTP RPC endpoint for the target chain.                                                             | `http://127.0.0.1:8545` |
| `PERPS_ADDRESS`  | Deployed address of `perps_contract.vy`.                                                            | `0x...` |
| `PERPS_ABI`      | JSON string of the perps contract ABI.                                                              | `export PERPS_ABI="$(cat out/perps_contract.json)"` |
| `ORACLE_ADDRESS` | Deployed address of `oracle.vy`.                                                                    | `0x...` |
| `ORACLE_ABI`     | JSON string of the oracle contract ABI.                                                             | `export ORACLE_ABI="$(cat out/oracle.json)"` |
| `MARKET_NAME`    | Human-readable identifier for the running market (used by the server and position manager).         | `POLYMARKET_EVENT_2024` |
| `URL_SUFFIX`     | Slug segment appended to `https://gamma-api.polymarket.com/events/slug/` to locate the event data.  | `us-election-2024` |

Additional optional variables:

- `POLYMARKET_BASE_API` — Override the base URL used by the oracle keeper (defaults to `https://gamma-api.polymarket.com/events/slug/`).
- `BASE_URL` (keeper funding script) — Override Tachyon API host if the server is not on `http://127.0.0.1:8000`.

> **Tip:** Because `PERPS_ABI` and `ORACLE_ABI` are parsed with `json.loads`, the `.env` entries must contain valid JSON (single-line strings are fine). Use command substitution or string escaping to avoid newline issues.

## Local Development

### 1. Install dependencies

```bash
# From the repo root
uv sync
# or, with pip
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

If you are developing contracts, install Moccasin globally or inside the virtual environment:

```bash
pip install moccasin
```

### 2. Compile & deploy contracts (optional local chain)

```bash
mox run deploy
```

This command uses Moccasin to spin up a local Anvil instance, compile the Vyper contracts, and deploy them. Capture the contract addresses and populate your `.env`. You can inspect artifacts under `out/`.

### 3. Seed environment variables

```bash
cp .env.example .env  # if you maintain an example file
# Fill in RPC_URL, contract addresses, ABIs, URL_SUFFIX, and private key
```

### 4. Start the FastAPI server

```bash
uvicorn off_chain_systems.server:app --host 0.0.0.0 --port 8000 --reload
```

The server exposes endpoints for order submission, pricing, and account inspection. It also starts the position management loop as a background thread.

### 5. Launch the trading CLI (optional dashboard)

```bash
python -m cli.cli
```

You will be prompted for the trader wallet private key (compatible with the RPC network). Available commands:

- `dashboard` — Launch Rich TUI with live order book and positions.
- `limit` / `market` — Submit orders.
- `cancel` — Cancel your outstanding limit order.
- `quit` — Exit the CLI.

### 6. Run keepers

**Oracle keeper** — Streams Polymarket midpoint into the on-chain oracle.

```bash
python keeper/oracle_update_script.py
```

**Funding keeper** — Computes funding and updates mark price using the Tachyon API plus oracle price.

```bash
python keeper/funding_update_script.py
```

Run both services whenever the exchange is live; they require the `.env` credentials and connectivity to both the RPC node and the FastAPI instance.

### 7. Optional utilities

- Seed sample orders: `curl -X POST http://127.0.0.1:8000/seed_orders`
- Simulate a market fill: `curl -X POST http://127.0.0.1:8000/simulate_market_fill`
- Seed test positions: `curl -X POST http://127.0.0.1:8000/seed_positions`

These endpoints are intended for local testing and should be disabled in production deployments.

## Deployment Guide

1. **Compile contracts:** `mox build` to generate artifacts, or `mox run deploy --network <network>` to deploy to a configured testnet/mainnet RPC.
2. **Verify addresses:** Update `.env` with the deployed `PERPS_ADDRESS` and `ORACLE_ADDRESS`. Export their ABI JSON (from `out/<contract>.json`) into the environment variables.
3. **Backend services:**
   - Containerize or run the FastAPI server behind a process manager (`systemd`, `pm2`, `supervisord`, etc.).
   - Configure environment variables for production RPC endpoints and Polymarket slug.
4. **Keepers & monitoring:**
   - Run oracle and funding scripts on a cadence (cron, `systemd` timers, or container jobs).
   - Monitor logs for failed transactions and Polymarket API responses.
5. **Frontend/CLI:** Distribute the CLI to operators or integrate the REST API with your own frontend. Ensure wallets used for trading are funded with the quote asset and have permission to call the perps contract.

> **Security note:** The keeper and matching engine wallet currently shares the same `PRIVATE_KEY`. For production deployment, consider using dedicated keys and custody solutions, plus rate limiting on the API.

## API Surface

The FastAPI server (default `http://127.0.0.1:8000`) exposes:

- `GET /` — Health check.
- `GET /orderbook` — Aggregated bids/asks (best 5 levels returned in CLI).
- `GET /positions/{address}` — Open positions plus live PnL for a trader.
- `GET /oracle_price` — Latest Polymarket-derived price.
- `GET /perp_price` — Mark price from recent trades or mid-market.
- `GET /funding_rate` — Current funding rate on chain.
- `GET /trades` — Recent trades (last 20).
- `POST /tx/limit_order` — Submit a limit order (`price`, `quantity`, `leverage`, `direction`, `trader_address`).
- `POST /tx/market_order` — Submit a market order (`quantity`, `leverage`, `direction`, `trader_address`).
- `POST /tx/remove_limit_order` — Cancel outstanding limit order for a trader.

## Troubleshooting & Tips

- Ensure the RPC URL is reachable; the matching engine and keepers will raise `ValueError` if they cannot connect.
- If `PERPS_ABI` or `ORACLE_ABI` fails to parse, check for newline characters or invalid JSON in the `.env`.
- Polymarket APIs enforce rate limits; consider caching responses or backing off (the keeper currently sleeps 10 seconds between updates).
- `URL_SUFFIX` must correspond to your Polymarket market slug; verify the associated `clobTokenIds` contains the YES token referenced by the perps product.
- Use `mox test` to run contract tests after making Vyper changes.

With the above steps, you can run Tachyon end-to-end: deploy contracts, feed oracle data from Polymarket, match orders locally or via CLI, and monitor positions in real time.
