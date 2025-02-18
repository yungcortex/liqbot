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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['DEBUG'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

# Initialize SocketIO with optimized settings
socketio = SocketIO(
    app,
    cors_allowed_origins=["https://liqbot-038f.onrender.com"],
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    manage_session=False,
    cookie=False,
    always_connect=True,
    transports=['websocket'],
    max_http_buffer_size=1e6,
    async_handlers=False,
    monitor_clients=False
)

# Configure CORS with proper settings
CORS(app, resources={
    r"/*": {
        "origins": ["https://liqbot-038f.onrender.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

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

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    try:
        sid = request.sid
        logger.info(f"Client connected - SID: {sid}")
        # Send initial stats
        emit('stats_update', latest_stats, broadcast=False)
        emit('connection_success', {'status': 'connected', 'sid': sid}, broadcast=False)
        # Force event emission
        socketio.sleep(0)
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")
        if hasattr(request, 'sid'):
            try:
                socketio.server.disconnect(request.sid, namespace='/')
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up connection {request.sid}: {cleanup_error}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    try:
        sid = request.sid
        logger.info(f"Client disconnected - SID: {sid}")
        # Clean up any remaining session data
        if hasattr(request, 'sid'):
            try:
                # Remove client from any rooms
                rooms = socketio.server.rooms(sid, '/')
                for room in rooms:
                    socketio.server.leave_room(sid, room, '/')
                # Disconnect the client
                socketio.server.disconnect(request.sid, namespace='/')
            except Exception as e:
                logger.error(f"Error cleaning up session {request.sid}: {e}")
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")

@socketio.on_error_default
def default_error_handler(e):
    """Handle all Socket.IO errors"""
    try:
        sid = request.sid if hasattr(request, 'sid') else 'Unknown'
        logger.error(f"Socket.IO error for SID {sid}: {str(e)}")
        
        # Clean up session on error
        if hasattr(request, 'sid'):
            try:
                socketio.server.disconnect(request.sid, namespace='/')
            except Exception as session_error:
                logger.error(f"Error cleaning up session {request.sid}: {session_error}")
                
    except Exception as error:
        logger.error(f"Error in error handler: {error}")

def emit_update(data, event_type='stats_update'):
    """Emit updates to all connected clients"""
    try:
        if event_type == 'stats_update':
            for symbol, values in data.items():
                if symbol in latest_stats:
                    latest_stats[symbol].update(values)
        
        # Log the event before emitting
        logger.info(f"Emitting {event_type} event: {data}")
        
        # Emit with broadcast and force immediate send
        socketio.emit(event_type, data, broadcast=True, namespace='/')
        socketio.sleep(0)  # Force event emission
        
        # Verify emission
        logger.info(f"Successfully emitted {event_type} event")
    except Exception as e:
        logger.error(f"Error emitting {event_type}: {e}")
        # Try to recover any broken connections
        try:
            for sid in socketio.server.eio.sockets:
                if not socketio.server.eio.sockets[sid].connected:
                    socketio.server.disconnect(sid, namespace='/')
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up broken connections: {cleanup_error}")

def process_liquidation_event(data):
    """Process a liquidation event and emit it to clients"""
    try:
        if not isinstance(data, dict):
            logger.error(f"Invalid data format received: {data}")
            return

        symbol = data.get('symbol')
        if not symbol or symbol not in latest_stats:
            logger.error(f"Invalid symbol in data: {data}")
            return

        side = data.get('side')
        if not side or side not in ['LONG', 'SHORT']:
            logger.error(f"Invalid side in data: {data}")
            return

        try:
            amount = float(data.get('amount', 0))
            price = float(data.get('price', 0))
            value = float(data.get('value', 0))
        except (ValueError, TypeError):
            logger.error(f"Error converting numeric values: {data}")
            return

        # Update stats
        if side == 'LONG':
            latest_stats[symbol]['longs'] += 1
        else:
            latest_stats[symbol]['shorts'] += 1
        latest_stats[symbol]['total_value'] += value

        # Log the event before emitting
        logger.info(f"Processing liquidation event: {data}")
        logger.info(f"Current stats: {latest_stats}")

        # Emit events with broadcast and force immediate send
        try:
            socketio.emit('liquidation', data, broadcast=True, namespace='/')
            socketio.sleep(0)  # Force first event emission
            socketio.emit('stats_update', latest_stats, broadcast=True, namespace='/')
            socketio.sleep(0)  # Force second event emission
        except Exception as e:
            logger.error(f"Error emitting events: {e}")
            # Try to recover any broken connections
            try:
                for sid in socketio.server.eio.sockets:
                    if not socketio.server.eio.sockets[sid].connected:
                        socketio.server.disconnect(sid, namespace='/')
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up broken connections: {cleanup_error}")

    except Exception as e:
        logger.error(f"Error processing liquidation: {e}")

async def run_liquidation_bot():
    """Run the liquidation bot and forward updates to web clients"""
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
    
    # Run the Flask application with optimized settings
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000)),
        debug=False,
        use_reloader=False,
        log_output=True,
        ping_timeout=60,
        ping_interval=25,
        cors_allowed_origins="*",
        websocket=True,
        allow_upgrades=True,
        http_compression=True,
        max_http_buffer_size=1e6,
        manage_session=True,
        cookie=True,
        cors_credentials=True,
        verify_session=True,
        session_lifetime=120
    ) 