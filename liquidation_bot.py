import asyncio
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from collections import deque
import websockets

# Initialize Rich console
console = Console()

# Initialize counters for statistics
stats = {
    "BTC": {"longs": 0, "shorts": 0, "total_value": 0},
    "ETH": {"longs": 0, "shorts": 0, "total_value": 0},
    "SOL": {"longs": 0, "shorts": 0, "total_value": 0}
}

# Keep a log of recent liquidations (last 50 entries)
liquidation_log = deque(maxlen=50)

# Callback for web updates (will be set by web app)
web_update_callback = None

def set_web_update_callback(callback):
    """Set the callback function for web updates"""
    global web_update_callback
    web_update_callback = callback

def generate_table():
    """Generate a rich table with current statistics"""
    table = Table(title="Liquidation Tracker")
    table.add_column("Asset")
    table.add_column("Long Liqs")
    table.add_column("Short Liqs")
    table.add_column("Total Value (USD)")
    
    for asset in stats:
        table.add_row(
            asset,
            str(stats[asset]["longs"]),
            str(stats[asset]["shorts"]),
            f"${stats[asset]['total_value']:,.2f}"
        )
    
    return table

def generate_log_panel():
    """Generate a panel with scrollable liquidation log"""
    log_content = "\n".join(liquidation_log)
    return Panel(log_content, title="Recent Liquidations", height=15)

def make_layout():
    """Create the layout with both table and log"""
    layout = Layout()
    layout.split_column(
        Layout(generate_table(), size=8),
        Layout(generate_log_panel(), size=15)
    )
    return layout

def process_liquidation(message):
    """Process liquidation data and update the display"""
    try:
        # Log raw message for debugging
        debug_log = f"[blue]{datetime.now().strftime('%H:%M:%S')} Raw message: {json.dumps(message)}[/blue]"
        liquidation_log.appendleft(debug_log)
        
        # Extract data from message
        if "data" in message:
            data = message["data"]
            if not data:  # Skip empty data
                return
                
            # Handle both list and dict formats
            if isinstance(data, list):
                data = data[0]
            
            # Extract required fields with V5 API field names
            symbol = data.get("symbol", "")
            side = data.get("side", "")
            price = float(data.get("price", 0))
            size = float(data.get("size", data.get("qty", 0)))  # Try both size and qty fields
            update_time = data.get("updatedTime", datetime.now().strftime("%H:%M:%S"))
            
            # Calculate value
            value = price * size
            
            # Extract the base asset (BTC, ETH, SOL)
            base_asset = None
            for asset in ["BTC", "ETH", "SOL"]:
                if asset in symbol:
                    base_asset = asset
                    break
            
            if base_asset and base_asset in stats and price > 0 and size > 0:
                # Update statistics based on side
                if side == "Sell":  # Short liquidation
                    stats[base_asset]["shorts"] += 1
                    log_entry = f"[red]{update_time} 🔥 SHORT LIQ[/red] {base_asset}: ${value:,.2f} @ ${price:,.2f}"
                elif side == "Buy":  # Long liquidation
                    stats[base_asset]["longs"] += 1
                    log_entry = f"[green]{update_time} 🔥 LONG LIQ[/green] {base_asset}: ${value:,.2f} @ ${price:,.2f}"
                else:
                    return  # Skip if side is not recognized
                
                stats[base_asset]["total_value"] += value
                liquidation_log.appendleft(log_entry)
                
                # Log successful processing
                debug_log = f"[cyan]{datetime.now().strftime('%H:%M:%S')} Processed liquidation: {base_asset} {side} {size} @ {price}[/cyan]"
                liquidation_log.appendleft(debug_log)
                
                # Update the live display
                if "live" in globals():
                    live.update(make_layout())
                
                # Send update to web interface if callback is set
                if web_update_callback:
                    # Send stats update
                    web_update_callback(stats, event_type='stats_update')
                    # Send liquidation message
                    clean_message = f"{update_time} 🔥 {'LONG' if side == 'Buy' else 'SHORT'} LIQ {base_asset}: ${value:,.2f} @ ${price:,.2f}"
                    web_update_callback({"message": clean_message}, event_type='liquidation')

    except Exception as e:
        error_log = f"[yellow]{datetime.now().strftime('%H:%M:%S')} Error processing message: {str(e)}[/yellow]"
        liquidation_log.appendleft(error_log)
        if "live" in globals():
            live.update(make_layout())

async def subscribe_liquidation(websocket):
    """Subscribe to liquidation stream"""
    # Subscribe to all symbols at once with correct V5 format
    subscribe_message = {
        "req_id": "liquidation_sub",
        "op": "subscribe",
        "args": [
            "liquidation.BTCUSDT",
            "liquidation.ETHUSDT",
            "liquidation.SOLUSDT"
        ]
    }
    await websocket.send(json.dumps(subscribe_message))
    # Wait for subscription response
    response = await websocket.recv()
    log_entry = f"[cyan]{datetime.now().strftime('%H:%M:%S')} Subscription response: {response}[/cyan]"
    liquidation_log.appendleft(log_entry)
    if "live" in globals():
        live.update(make_layout())

async def connect_websocket():
    """Connect to Bybit WebSocket and handle messages"""
    uri = "wss://stream.bybit.com/v5/public/linear"
    
    while True:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Origin": "https://www.bybit.com"
            }
            
            async with websockets.connect(uri, extra_headers=headers, ping_interval=20, ping_timeout=10) as websocket:
                # Log connection
                log_entry = f"[green]{datetime.now().strftime('%H:%M:%S')} ✓ Connected to Bybit WebSocket[/green]"
                liquidation_log.appendleft(log_entry)
                if "live" in globals():
                    live.update(make_layout())
                
                # Subscribe to liquidation streams
                await subscribe_liquidation(websocket)
                
                # Handle incoming messages
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Log all messages for debugging
                        debug_log = f"[blue]{datetime.now().strftime('%H:%M:%S')} Message received: {json.dumps(data)}[/blue]"
                        liquidation_log.appendleft(debug_log)
                        if "live" in globals():
                            live.update(make_layout())
                        
                        # Process different types of messages
                        if "topic" in data and "liquidation" in data["topic"]:
                            # This is a liquidation message
                            process_liquidation(data)
                        elif "op" in data and data["op"] == "subscribe":
                            # This is a response to our subscription
                            if data.get("success", False):
                                log_entry = f"[green]{datetime.now().strftime('%H:%M:%S')} Successfully subscribed to streams[/green]"
                                liquidation_log.appendleft(log_entry)
                            else:
                                log_entry = f"[red]{datetime.now().strftime('%H:%M:%S')} Failed to subscribe: {data.get('ret_msg', 'Unknown error')}[/red]"
                                liquidation_log.appendleft(log_entry)
                            
                    except websockets.ConnectionClosed:
                        raise
                    except Exception as e:
                        error_log = f"[yellow]{datetime.now().strftime('%H:%M:%S')} Error processing message: {str(e)}[/yellow]"
                        liquidation_log.appendleft(error_log)
                        if "live" in globals():
                            live.update(make_layout())
                        
        except Exception as e:
            error_log = f"[red]{datetime.now().strftime('%H:%M:%S')} WebSocket error: {str(e)}. Reconnecting...[/red]"
            liquidation_log.appendleft(error_log)
            if "live" in globals():
                live.update(make_layout())
            await asyncio.sleep(5)  # Wait before reconnecting

async def main():
    global live
    
    # Initialize and start the live display
    layout = make_layout()
    with Live(layout, refresh_per_second=1, screen=True) as live:
        await connect_websocket()

if __name__ == "__main__":
    console.print("[bold blue]Starting Liquidation Tracker...[/bold blue]")
    console.print("Monitoring liquidations for BTC, ETH, and SOL...")
    console.print("Press Ctrl+C to exit\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Shutting down...[/bold red]")
