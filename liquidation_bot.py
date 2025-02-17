import asyncio
import websockets
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
web_update_callback = None
stats = {
    "BTC": {"longs": 0, "shorts": 0, "total_value": 0},
    "ETH": {"longs": 0, "shorts": 0, "total_value": 0},
    "SOL": {"longs": 0, "shorts": 0, "total_value": 0}
}

def set_web_update_callback(callback):
    """Set the callback function for web updates"""
    global web_update_callback
    web_update_callback = callback

def process_liquidation(data):
    """Process a liquidation event and update statistics"""
    try:
        # Log the raw data for debugging
        logger.debug(f"Processing raw liquidation data: {data}")
        
        # Parse the message
        if isinstance(data, str):
            data = json.loads(data)
        
        # Extract the data field if it exists
        if 'data' in data:
            liquidation = data['data']
        else:
            liquidation = data
            
        # Forward the event to the web interface if callback is set
        if web_update_callback:
            web_update_callback(data)
            
    except Exception as e:
        logger.error(f"Error processing liquidation: {e}", exc_info=True)

async def connect_websocket():
    """Connect to Bybit WebSocket and subscribe to liquidation feed"""
    uri = "wss://stream.bybit.com/v5/public/linear"
    
    async with websockets.connect(uri) as websocket:
        # Subscribe to liquidation stream
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
        logger.info("Subscribed to liquidation feed")
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Handle subscription confirmation
                if 'op' in data and data['op'] == 'subscribe':
                    logger.info("Successfully subscribed to liquidation feed")
                    continue
                
                # Handle liquidation events
                if 'topic' in data and 'liquidation.' in data['topic']:
                    process_liquidation(data)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket connection closed unexpectedly")
                raise
            except Exception as e:
                logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
                raise
