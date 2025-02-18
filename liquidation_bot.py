import asyncio
import json
import websockets
import logging
from datetime import datetime

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

def set_web_update_callback(callback):
    """Set the callback function for web updates"""
    global web_callback
    web_callback = callback
    logger.info("Web callback set successfully")

async def process_message(message):
    """Process incoming WebSocket messages"""
    try:
        data = json.loads(message)
        if 'topic' in data and data['topic'] == 'liquidation':
            await process_liquidation(data['data'][0])
    except Exception as e:
        logger.error(f"Error processing message: {e}")

async def process_liquidation(data):
    """Process liquidation data and update stats"""
    try:
        symbol = data['symbol'].replace('USDT', '')
        if symbol not in stats:
            return

        # Extract and validate data
        try:
            amount = float(data.get('size', data.get('qty', 0)))
            price = float(data['price'])
            value = amount * price
            side = 'LONG' if data['side'].upper() == 'BUY' else 'SHORT'
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing liquidation data: {e}")
            return

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
            'timestamp': data.get('updatedTime', datetime.now().timestamp())
        }

        # Send update to web interface
        if web_callback:
            logger.info(f"Sending liquidation event to web interface: {liquidation_event}")
            await asyncio.get_event_loop().run_in_executor(
                None, web_callback, liquidation_event
            )
        else:
            logger.warning("No web callback set for liquidation events")

    except Exception as e:
        logger.error(f"Error processing liquidation: {e}")

async def connect_websocket():
    """Connect to Bybit WebSocket and handle messages"""
    uri = "wss://stream.bybit.com/v5/public/linear"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("Subscribed to liquidation feed")
                
                # Subscribe to liquidation feed
                subscribe_message = {
                    "op": "subscribe",
                    "args": ["liquidation.BTCUSDT", "liquidation.ETHUSDT", "liquidation.SOLUSDT"]
                }
                await websocket.send(json.dumps(subscribe_message))
                
                # Process messages
                while True:
                    try:
                        message = await websocket.recv()
                        await process_message(message)
                    except websockets.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error in message processing loop: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await asyncio.sleep(5)  # Wait before reconnecting

if __name__ == "__main__":
    asyncio.run(connect_websocket())
