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
app.config['CORS_SUPPORTS_CREDENTIALS'] = True
app.config['CORS_EXPOSE_HEADERS'] = ['Content-Range', 'X-Content-Range']

# Initialize CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": ["Content-Type"],
        "expose_headers": ["Content-Range", "X-Content-Range"],
        "supports_credentials": True
    }
})

# Initialize SocketIO
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
    manage_session=True,
    websocket=True
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
    response.headers.add('Access-Control-Allow-Credentials', 'true')
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
            # Extract relevant information
            symbol = data.get('symbol', '')
            side = 'LONG' if data.get('side', '').upper() == 'BUY' else 'SHORT'
            amount = float(data.get('amount', 0))
            price = float(data.get('price', 0))
            
            # Update stats
            if symbol in latest_stats:
                if side == 'LONG':
                    latest_stats[symbol]['longs'] += 1
                else:
                    latest_stats[symbol]['shorts'] += 1
                latest_stats[symbol]['total_value'] += amount * price
            
            # Emit both the liquidation event and updated stats
            logger.info(f"Processing liquidation: {symbol} {side} {amount} @ {price}")
            
            socketio.emit('liquidation', {
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price
            })
            socketio.emit('stats_update', latest_stats)
    except Exception as e:
        logger.error(f"Error processing liquidation: {e}")

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