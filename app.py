import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
import asyncio
import threading
import json
from datetime import datetime
import sys
import os
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
import time
import weakref
from eventlet.green import socket
import errno

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
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=20,
    ping_interval=10,
    manage_session=True,
    cookie=False,
    always_connect=True,
    transports=['websocket'],
    max_http_buffer_size=1024 * 1024,
    async_handlers=True,
    monitor_clients=True,
    reconnection=True,
    reconnection_attempts=float('inf'),
    reconnection_delay=1000,
    reconnection_delay_max=5000,
    max_retries=float('inf'),
    retry_delay=1000,
    retry_delay_max=5000,
    ping_interval_grace_period=2000
)

# Configure CORS
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

# Track active connections and their last heartbeat
active_connections = {}
connection_lock = threading.Lock()

def is_socket_valid(sid):
    """Check if a socket connection is still valid"""
    try:
        if sid not in active_connections:
            return False
            
        socket = socketio.server.eio.sockets.get(sid)
        if not socket:
            return False
            
        if hasattr(socket, 'closed') and socket.closed:
            return False
            
        if hasattr(socket, 'fileno'):
            try:
                if socket.fileno() == -1:
                    return False
            except Exception:
                return False
                
        return True
    except Exception:
        return False

def cleanup_stale_connections():
    """Clean up stale connections periodically"""
    while True:
        try:
            current_time = time.time()
            with connection_lock:
                for sid, data in list(active_connections.items()):
                    if not is_socket_valid(sid) or current_time - data['last_heartbeat'] > 30:
                        try:
                            socketio.server.disconnect(sid)
                        except Exception:
                            pass
                        active_connections.pop(sid, None)
        except Exception as e:
            print(f"Error in cleanup thread: {e}")
        time.sleep(10)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_stale_connections, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle new client connections"""
    try:
        sid = request.sid
        if not sid:
            return
            
        with connection_lock:
            active_connections[sid] = {
                'connected_at': time.time(),
                'last_heartbeat': time.time()
            }
            
        # Send initial stats
        emit('stats', {'status': 'connected', 'sid': sid})
        print(f"Client connected: {sid}")
    except Exception as e:
        print(f"Error in handle_connect: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnections"""
    try:
        sid = request.sid
        if sid:
            with connection_lock:
                active_connections.pop(sid, None)
            print(f"Client disconnected: {sid}")
    except Exception as e:
        print(f"Error in handle_disconnect: {e}")

@socketio.on('heartbeat')
def handle_heartbeat():
    """Handle client heartbeat"""
    try:
        sid = request.sid
        if sid and sid in active_connections:
            with connection_lock:
                active_connections[sid]['last_heartbeat'] = time.time()
    except Exception as e:
        print(f"Error in handle_heartbeat: {e}")

@socketio.on('get_stats')
def handle_get_stats():
    """Handle stats request"""
    try:
        sid = request.sid
        if sid and is_socket_valid(sid):
            emit('stats', {'status': 'active', 'sid': sid})
    except Exception as e:
        print(f"Error in handle_get_stats: {e}")

def emit_update(data, event_type='stats_update'):
    """Emit updates to all connected clients"""
    try:
        if event_type == 'stats_update':
            for symbol, values in data.items():
                if symbol in latest_stats:
                    latest_stats[symbol].update(values)
        
        # Check for stale connections before emitting
        for sid in active_connections:
            if not is_socket_valid(sid):
                continue
            
        # Get list of active sids
        active_sids = list(active_connections.keys())
        
        # Emit to each active connection individually
        for sid in active_sids:
            try:
                socketio.emit(event_type, data, room=sid)
                socketio.sleep(0)  # Force event emission
            except Exception as e:
                if not isinstance(e, (IOError, OSError)) or e.errno != errno.EBADF:
                    logger.error(f"Error emitting to {sid}: {e}")
                active_connections.pop(sid, None)
        
    except Exception as e:
        logger.error(f"Error emitting {event_type}: {e}")

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

        # Check for stale connections before emitting
        for sid in active_connections:
            if not is_socket_valid(sid):
                continue
            
        # Get list of active sids
        active_sids = list(active_connections.keys())
        
        # Emit events to each active connection individually
        for sid in active_sids:
            try:
                socketio.emit('liquidation', data, room=sid)
                socketio.sleep(0)
                socketio.emit('stats_update', latest_stats, room=sid)
                socketio.sleep(0)
            except Exception as e:
                if not isinstance(e, (IOError, OSError)) or e.errno != errno.EBADF:
                    logger.error(f"Error emitting to {sid}: {e}")
                active_connections.pop(sid, None)

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
        log_output=True
    ) 