import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import asyncio
import threading
import json
from datetime import datetime
import sys
import os
import logging
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['CORS_SUPPORTS_CREDENTIALS'] = False
app.config['CORS_EXPOSE_HEADERS'] = ['Content-Range', 'X-Content-Range']
app.config['DEBUG'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

# Initialize CORS with simpler configuration
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize SocketIO with production-ready settings
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8,
    async_handlers=True,
    path='/socket.io/',
    manage_session=False,
    websocket=True,
    allow_upgrades=True,
    cookie=None,
    always_connect=True,
    transports=['websocket', 'polling'],
    cors_credentials=False,
    max_queue_size=10,
    message_queue=None,
    channel='socketio',
    write_only=False,
    json=None,
    async_handlers_pool_size=100
)

# Add parent directory to path to import liquidation_bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from liquidation_bot import stats, process_liquidation, connect_websocket, set_web_update_callback

# Store the latest statistics
latest_stats = {
    "BTC": {"longs": 0, "shorts": 0, "total_value": 0},
    "ETH": {"longs": 0, "shorts": 0, "total_value": 0},
    "SOL": {"longs": 0, "shorts": 0, "total_value": 0}
}

@app.route('/')
def index():
    return render_template('index.html')

@app.after_request
def after_request(response):
    """Add headers to every response."""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Cache-Control', 'no-cache')
    return response

@socketio.on('connect')
def handle_connect():
    try:
        with app.app_context():
            logger.info(f"Client connected via {request.environ.get('wsgi.url_scheme', 'unknown')}")
            emit('stats_update', latest_stats)
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    try:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")

@socketio.on('heartbeat')
def handle_heartbeat():
    """Handle heartbeat messages from clients to keep the connection alive"""
    try:
        with app.app_context():
            emit('heartbeat_response', {'status': 'ok'})
    except Exception as e:
        logger.error(f"Error in handle_heartbeat: {e}")

@socketio.on('get_stats')
def handle_get_stats():
    """Handle requests for current statistics"""
    try:
        with app.app_context():
            emit('stats_update', latest_stats)
            logger.debug("Sent stats update in response to get_stats request")
    except Exception as e:
        logger.error(f"Error in handle_get_stats: {e}")

def emit_update(data, event_type='stats_update'):
    """Emit updates to all connected clients"""
    try:
        with app.app_context():
            logger.debug(f"Emitting {event_type}: {data}")
            if event_type == 'stats_update':
                for symbol, values in data.items():
                    if symbol in latest_stats:
                        latest_stats[symbol].update(values)
            socketio.emit(event_type, data)
    except Exception as e:
        logger.error(f"Error emitting {event_type}: {e}")

def process_liquidation_event(data):
    """Process a liquidation event and emit it to clients"""
    try:
        with app.app_context():
            logger.debug(f"Received liquidation data: {data}")
            
            # Handle Bybit's data format
            if isinstance(data, dict):
                if 'data' in data:
                    liquidation_data = data['data']
                else:
                    liquidation_data = data
            else:
                logger.error(f"Invalid data format received: {data}")
                return
            
            # Extract the symbol (remove USDT suffix)
            symbol = liquidation_data.get('symbol', '').replace('USDT', '')
            
            # Get the size and price
            try:
                # Bybit uses 'size' for amount
                amount = float(liquidation_data.get('size', liquidation_data.get('qty', 0)))
                price = float(liquidation_data.get('price', 0))
                value = amount * price
            except (ValueError, TypeError):
                logger.error(f"Error converting size/price: {liquidation_data}")
                return
            
            # Determine if it's a long or short liquidation
            side = 'LONG' if liquidation_data.get('side', '').upper() == 'BUY' else 'SHORT'
            
            logger.info(f"Processing liquidation: {symbol} {side} {amount} @ {price} = ${value}")
            
            # Update stats if we have a valid symbol
            if symbol in latest_stats:
                # Update the stats
                if side == 'LONG':
                    latest_stats[symbol]['longs'] += 1
                else:
                    latest_stats[symbol]['shorts'] += 1
                latest_stats[symbol]['total_value'] += value
                
                # First emit the liquidation event
                liquidation_event = {
                    'symbol': symbol,
                    'side': side,
                    'amount': amount,
                    'price': price,
                    'value': value,
                    'timestamp': liquidation_data.get('updatedTime', datetime.now().timestamp())
                }
                
                logger.debug(f"Emitting liquidation event: {liquidation_event}")
                socketio.emit('liquidation', liquidation_event)
                
                # Then emit the updated stats
                logger.debug(f"Emitting updated stats: {latest_stats}")
                socketio.emit('stats_update', latest_stats)
                
                logger.info(f"Updated {symbol} stats - Longs: {latest_stats[symbol]['longs']}, Shorts: {latest_stats[symbol]['shorts']}, Total: ${latest_stats[symbol]['total_value']:.2f}")
            else:
                logger.warning(f"Received liquidation for unknown symbol: {symbol}")
    except Exception as e:
        logger.error(f"Error processing liquidation: {e}", exc_info=True)

async def run_liquidation_bot():
    """Run the liquidation bot and forward updates to web clients"""
    # Set the callback for web updates
    set_web_update_callback(process_liquidation_event)
    
    while True:
        try:
            logger.info("Connecting to Bybit WebSocket...")
            await connect_websocket()
        except Exception as e:
            logger.error(f"Error in liquidation bot: {e}")
            await asyncio.sleep(5)

def background_tasks():
    """Run background tasks in asyncio event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_liquidation_bot())

if __name__ == '__main__':
    logger.info("Starting Liquidation Tracker Web Interface...")
    
    # Start the liquidation bot in a separate thread
    bot_thread = threading.Thread(target=background_tasks)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Run the Flask application
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000)),
        debug=True,
        use_reloader=False,
        log_output=True
    ) 