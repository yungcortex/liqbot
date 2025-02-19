import asyncio
import json
import websockets
import logging
from datetime import datetime
import aiohttp
import hmac
import time
import base64
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
web_callback = None
stats = {
    "BTC": {"longs": 0, "shorts": 0, "total_value": 0},
    "ETH": {"longs": 0, "shorts": 0, "total_value": 0},
    "SOL": {"longs": 0, "shorts": 0, "total_value": 0}
}

# WebSocket URLs
WEBSOCKET_URLS = {
    'bybit': "wss://stream.bybit.com/v5/public/linear",
    'binance': "wss://fstream.binance.com/ws",
    'okx': "wss://ws.okx.com:8443/ws/v5/public",
    'gate': "wss://fx-ws.gateio.ws/v4/ws/usdt"
}

def set_web_update_callback(callback):
    """Set the callback function for web updates"""
    global web_callback
    web_callback = callback
    logger.info("Web callback set successfully")

def normalize_symbol(symbol, exchange):
    """Normalize symbol names across exchanges"""
    symbol = symbol.upper()
    if exchange == 'binance':
        return symbol.replace('USDT', '')
    elif exchange == 'okx':
        return symbol.split('-')[0]
    elif exchange == 'gate':
        return symbol.split('_')[0]
    return symbol.replace('USDT', '')

def normalize_side(side, exchange):
    """Normalize trading sides across exchanges"""
    side = side.upper()
    if exchange == 'binance':
        return 'LONG' if side == 'BUY' else 'SHORT'
    elif exchange == 'okx':
        return 'LONG' if side == 'BUY' else 'SHORT'
    elif exchange == 'gate':
        return 'LONG' if side == 'BUY' else 'SHORT'
    return 'LONG' if side == 'BUY' else 'SHORT'

async def process_message(message, exchange):
    """Process incoming WebSocket messages"""
    try:
        data = json.loads(message)
        
        if exchange == 'bybit' and 'topic' in data and data['topic'] == 'liquidation':
            await process_bybit_liquidation(data['data'][0])
        elif exchange == 'binance' and 'e' in data and data['e'] == 'forceOrder':
            await process_binance_liquidation(data)
        elif exchange == 'okx' and 'event' in data and data['event'] == 'liquidation':
            await process_okx_liquidation(data['data'])
        elif exchange == 'gate' and 'channel' in data and data['channel'] == 'futures.liquidates':
            if 'result' in data and isinstance(data['result'], list):
                for liquidation in data['result']:
                    await process_gate_liquidation(liquidation)
            elif 'result' in data:
                await process_gate_liquidation(data['result'])
            
    except Exception as e:
        logger.error(f"Error processing {exchange} message: {e}")

async def process_bybit_liquidation(data):
    """Process Bybit liquidation data"""
    try:
        symbol = normalize_symbol(data['symbol'], 'bybit')
        if symbol not in stats:
            return

        amount = float(data.get('size', data.get('qty', 0)))
        price = float(data['price'])
        value = amount * price
        side = normalize_side(data['side'], 'bybit')

        await update_and_emit_stats(symbol, side, amount, price, value, 'Bybit')
    except Exception as e:
        logger.error(f"Error processing Bybit liquidation: {e}")

async def process_binance_liquidation(data):
    """Process Binance liquidation data"""
    try:
        # Check if data has the expected structure
        if not isinstance(data, dict):
            logger.error(f"Invalid Binance data format: {data}")
            return
            
        # Handle different message types
        if 'e' not in data:
            logger.debug(f"Ignoring non-liquidation Binance message: {data}")
            return
            
        if data['e'] != 'forceOrder':
            logger.debug(f"Ignoring Binance message type: {data['e']}")
            return
            
        # Extract required fields with validation
        required_fields = {'s': 'symbol', 'S': 'side', 'q': 'quantity', 'p': 'price'}
        for key, name in required_fields.items():
            if key not in data:
                logger.error(f"Missing {name} in Binance liquidation data: {data}")
                return
                
        symbol = normalize_symbol(data['s'], 'binance')
        if symbol not in stats:
            logger.debug(f"Ignoring unsupported Binance symbol: {symbol}")
            return

        try:
            amount = float(data['q'])
            price = float(data['p'])
            value = amount * price
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting Binance numeric values: {e}")
            return
            
        side = normalize_side(data['S'], 'binance')

        await update_and_emit_stats(symbol, side, amount, price, value, 'Binance')
        
    except Exception as e:
        logger.error(f"Error processing Binance liquidation: {str(e)}")
        logger.debug(f"Problematic data: {data}", exc_info=True)

async def process_okx_liquidation(data):
    """Process OKX liquidation data"""
    try:
        symbol = normalize_symbol(data['instId'], 'okx')
        if symbol not in stats:
            return

        amount = float(data['sz'])
        price = float(data['bkPx'])
        value = amount * price
        side = normalize_side(data['side'], 'okx')

        await update_and_emit_stats(symbol, side, amount, price, value, 'OKX')
    except Exception as e:
        logger.error(f"Error processing OKX liquidation: {e}")

async def process_gate_liquidation(data):
    """Process Gate.io liquidation data"""
    try:
        if not data:
            return

        # Gate.io sends data in different formats depending on the event type
        if isinstance(data, dict):
            symbol = normalize_symbol(data.get('contract', '').split('_')[0], 'gate')
        elif isinstance(data, list) and len(data) >= 1:
            symbol = normalize_symbol(data[0].split('_')[0], 'gate')
        else:
            logger.error(f"Unexpected Gate.io data format: {data}")
            return

        if symbol not in stats:
            return

        try:
            if isinstance(data, dict):
                amount = float(data.get('size', 0))
                price = float(data.get('price', 0))
                side = normalize_side(data.get('side', ''), 'gate')
            else:
                # Handle array format if needed
                amount = float(data[1])
                price = float(data[2])
                side = normalize_side('buy' if data[3] > 0 else 'sell', 'gate')
        except (IndexError, ValueError, TypeError) as e:
            logger.error(f"Error parsing Gate.io values: {e}")
            return

        value = amount * price
        await update_and_emit_stats(symbol, side, amount, price, value, 'Gate.io')
    except Exception as e:
        logger.error(f"Error processing Gate.io liquidation: {e}")

async def update_and_emit_stats(symbol, side, amount, price, value, exchange):
    """Update stats and emit events"""
    try:
        # Update stats
        if side == 'LONG':
            stats[symbol]['longs'] += 1
        else:
            stats[symbol]['shorts'] += 1
        stats[symbol]['total_value'] += value

        # Prepare liquidation event
        liquidation_event = {
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price,
            'value': value,
            'exchange': exchange,
            'timestamp': int(time.time() * 1000)
        }

        # Send update to web interface
        if web_callback:
            logger.info(f"Sending {exchange} liquidation event: {liquidation_event}")
            await asyncio.get_event_loop().run_in_executor(
                None, web_callback, liquidation_event
            )
        else:
            logger.warning("No web callback set for liquidation events")

    except Exception as e:
        logger.error(f"Error updating stats: {e}")

async def subscribe_bybit():
    """Subscribe to Bybit WebSocket"""
    try:
        async with websockets.connect(WEBSOCKET_URLS['bybit']) as websocket:
            subscribe_message = {
                "op": "subscribe",
                "args": ["liquidation.BTCUSDT", "liquidation.ETHUSDT", "liquidation.SOLUSDT"]
            }
            await websocket.send(json.dumps(subscribe_message))
            while True:
                message = await websocket.recv()
                await process_message(message, 'bybit')
    except Exception as e:
        logger.error(f"Bybit WebSocket error: {e}")

async def subscribe_binance():
    """Subscribe to Binance WebSocket"""
    try:
        async with websockets.connect(WEBSOCKET_URLS['binance']) as websocket:
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [
                    "btcusdt@forceOrder",
                    "ethusdt@forceOrder",
                    "solusdt@forceOrder"
                ],
                "id": 1
            }
            await websocket.send(json.dumps(subscribe_message))
            while True:
                message = await websocket.recv()
                await process_message(message, 'binance')
    except Exception as e:
        logger.error(f"Binance WebSocket error: {e}")

async def subscribe_okx():
    """Subscribe to OKX WebSocket"""
    try:
        async with websockets.connect(WEBSOCKET_URLS['okx']) as websocket:
            subscribe_message = {
                "op": "subscribe",
                "args": [
                    {"channel": "liquidation-orders", "instId": "BTC-USDT"},
                    {"channel": "liquidation-orders", "instId": "ETH-USDT"},
                    {"channel": "liquidation-orders", "instId": "SOL-USDT"}
                ]
            }
            await websocket.send(json.dumps(subscribe_message))
            while True:
                message = await websocket.recv()
                await process_message(message, 'okx')
    except Exception as e:
        logger.error(f"OKX WebSocket error: {e}")

async def subscribe_gate():
    """Subscribe to Gate.io WebSocket"""
    try:
        async with websockets.connect(WEBSOCKET_URLS['gate']) as websocket:
            # Initial subscription
            subscribe_message = {
                "time": int(time.time()),
                "channel": "futures.liquidates",
                "event": "subscribe",
                "payload": ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
            }
            await websocket.send(json.dumps(subscribe_message))

            # Handle incoming messages
            while True:
                try:
                    message = await websocket.recv()
                    await process_message(message, 'gate')
                except websockets.ConnectionClosed:
                    logger.warning("Gate.io WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error in Gate.io message loop: {e}")
                    continue

    except Exception as e:
        logger.error(f"Gate.io WebSocket error: {e}")
        await asyncio.sleep(5)  # Wait before reconnecting

async def connect_all_websockets():
    """Connect to all exchange WebSockets"""
    while True:
        try:
            # Create tasks for all exchanges
            tasks = [
                asyncio.create_task(subscribe_bybit()),
                asyncio.create_task(subscribe_binance()),
                asyncio.create_task(subscribe_okx()),
                asyncio.create_task(subscribe_gate())
            ]
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error in WebSocket connections: {e}")
            await asyncio.sleep(5)

async def run_liquidation_bot():
    """Run the liquidation bot and forward updates to web clients"""
    set_web_update_callback(process_liquidation_event)
    await connect_all_websockets()

def background_tasks():
    """Run background tasks in asyncio event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_liquidation_bot())

if __name__ == "__main__":
    asyncio.run(run_liquidation_bot())
