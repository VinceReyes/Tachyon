from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.prompt import Prompt
from threading import Lock
from time import sleep
from wallet_manager import TraderWallet
import requests
import os
import sys

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
RPC_URL = os.getenv("RPC_URL")
BASE_URL = "http://127.0.0.1:8000"

# Initialize wallet + console
wallet = TraderWallet(RPC_URL)
TRADER_ADDRESS = wallet.address
console = Console()
print_lock = Lock()

# --------------------------------------------------------------------
# Thread-safe console helpers
# --------------------------------------------------------------------
def safe_print(msg):
    """Print safely even when Live() is running."""
    with print_lock:
        console.print(msg)

def safe_prompt(question: str):
    """Prompt safely even when Live() is running."""
    with print_lock:
        return Prompt.ask(question)

# --------------------------------------------------------------------
# Layout + Rendering
# --------------------------------------------------------------------
def make_layout() -> Layout:
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["body"].split_row(
        Layout(name="orderbook", ratio=2),
        Layout(name="positions", ratio=3),
    )
    return layout

# --------------------------------------------------------------------
# Data fetchers
# --------------------------------------------------------------------
def fetch_orderbook():
    try:
        r = requests.get(f"{BASE_URL}/orderbook")
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def fetch_positions(address: str):
    try:
        r = requests.get(f"{BASE_URL}/positions/{address}")
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# --------------------------------------------------------------------
# Table rendering
# --------------------------------------------------------------------
def render_orderbook(data: dict):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Side", justify="center")
    table.add_column("Price", justify="right")
    table.add_column("Size", justify="right")

    if "error" in data:
        table.add_row("Error", data["error"], "")
        return table

    bids = data.get("bids", [])
    asks = data.get("asks", [])

    for price, size in bids[:5]:
        table.add_row("[green]BID[/green]", f"{price:.3f}", str(size))
    for price, size in asks[:5]:
        table.add_row("[red]ASK[/red]", f"{price:.3f}", str(size))
    return table


def render_positions(data: dict):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Market", justify="center")
    table.add_column("Side", justify="center")
    table.add_column("Size", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("PnL", justify="right")

    if "error" in data:
        table.add_row("Error", data["error"], "", "", "")
        return table

    positions = data.get("positions", [])
    if not positions:
        table.add_row("-", "-", "-", "-", "-")
        return table

    for pos in positions:
        pnl_color = "green" if pos["pnl"] >= 0 else "red"
        table.add_row(
            pos["market"],
            pos["side"],
            f"{pos['size']:.2f}",
            f"{pos['entry']:.3f}",
            f"[{pnl_color}]{pos['pnl']:.2%}[/{pnl_color}]"
        )
    return table

# --------------------------------------------------------------------
# Dashboard display
# --------------------------------------------------------------------
def show_dashboard():
    safe_print("[bold yellow]Opening dashboard. Press Ctrl+C to return to the command prompt.[/bold yellow]")
    layout = make_layout()
    layout["header"].update(Panel(f"Tachyon Perps | Wallet: {TRADER_ADDRESS[:6]}...{TRADER_ADDRESS[-4:]}", style="bold cyan"))
    layout["footer"].update(Panel("Status: Connected", style="bold green"))

    try:
        with Live(layout, refresh_per_second=2, screen=True, transient=False):
            while True:
                orderbook_data = fetch_orderbook()
                positions_data = fetch_positions(TRADER_ADDRESS)

                orderbook_table = render_orderbook(orderbook_data)
                positions_table = render_positions(positions_data)

                layout["orderbook"].update(Panel(orderbook_table, title="Orderbook"))
                layout["positions"].update(Panel(positions_table, title="Positions"))

                sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        safe_print(f"[bold red]Dashboard error:[/bold red] {exc}")
    finally:
        safe_print("[bold yellow]Exited dashboard.[/bold yellow]")

# --------------------------------------------------------------------
# Command handler
# --------------------------------------------------------------------
def command_loop():
    while True:
        cmd = safe_prompt("[bold cyan]Command (dashboard/limit/market/cancel/help/quit)[/bold cyan]").strip()
        cmd_lower = cmd.lower()

        if cmd_lower in {"/dashboard", "dashboard"}:
            show_dashboard()
            continue

        if cmd_lower == "help":
            safe_print("""
[bold yellow]Available Commands[/bold yellow]
  dashboard – View live dashboard (Ctrl+C to exit)
  limit   – Place a limit order
  market  – Place a market order
  cancel  – Cancel a limit order
  quit    – Exit CLI
""")

        elif cmd_lower == "limit":
            direction = safe_prompt("Side (buy/sell)")
            price = float(safe_prompt("Price"))
            qty = float(safe_prompt("Quantity"))
            lev = int(safe_prompt("Leverage"))

            payload = {
                "trader_address": TRADER_ADDRESS,
                "direction": direction,
                "price": price,
                "quantity": qty,
                "leverage": lev
            }
            r = requests.post(f"{BASE_URL}/tx/limit_order", json=payload)
            safe_print(f"[green]Limit Order Response:[/green] {r.json()}")

        elif cmd_lower == "market":
            direction = safe_prompt("Side (buy/sell)")
            qty = float(safe_prompt("Quantity"))
            lev = int(safe_prompt("Leverage"))

            payload = {
                "trader_address": TRADER_ADDRESS,
                "direction": direction,
                "quantity": qty,
                "leverage": lev
            }
            r = requests.post(f"{BASE_URL}/tx/market_order", json=payload)
            safe_print(f"[green]Market Order Response:[/green] {r.json()}")

        elif cmd_lower == "cancel":
            payload = {
                "trader_address": TRADER_ADDRESS
            }
            r = requests.post(f"{BASE_URL}/tx/remove_limit_order", json=payload)
            safe_print(f"[yellow]Cancel Response:[/yellow] {r.json()}")

        elif cmd_lower == "quit":
            safe_print("[bold red]Exiting CLI...[/bold red]")
            sys.exit(0)
        else:
            safe_print(f"[bold red]Unknown command:[/bold red] {cmd}")

# --------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------
if __name__ == "__main__":
    safe_print(f"[bold cyan]Connected Wallet:[/bold cyan] {TRADER_ADDRESS}")
    safe_print("[bold green]Type 'dashboard' to open the UI, or 'help' for available commands.[/bold green]\n")
    command_loop()
