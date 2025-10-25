from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.prompt import Prompt
from time import sleep
import random
import requests

BASE_URL = "http://127.0.0.1:8000"

console = Console()

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

def fetch_orderbook():
    try:
        response = requests.get(f"{BASE_URL}/orderbook")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        return {"error": str(e)}
    return {}

def fetch_positions(address: str):
    try:
        response = requests.get(f"{BASE_URL}/positions/{address}")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        return {"error": str(e)}
    return {}

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
        table.add_row("[green]ASK[/green]", f"{price:.3f}", str(size))
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
        table.add_row("-", "-", "-", "-", "-",)
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

def render_dashboard():
    layout = make_layout()

    layout["header"].update(Panel("Tachyon Perps", style="bold cyan"))
    layout["footer"].update(Panel("Status: Connected"))

    with Live(layout, refresh_per_second=2, screen=True):
        while True:
            orderbook_data = fetch_orderbook()
            positions_data = fetch_positions("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")

            orderbook_table = render_orderbook(orderbook_data)
            positions_table = render_positions(positions_data)

            mock_bid = round(random.uniform(0.8, 1.0), 3)
            mock_ask = round(random.uniform(1.0, 1.2), 3)
            mock_pos_size = random.randint(0, 10)

            layout["orderbook"].update(
                Panel(orderbook_table, title="Orderbook")
            )

            layout["positions"].update(
                Panel(positions_table, title="Positions")
            )

            sleep(1)

if __name__ == "__main__":
    render_dashboard()