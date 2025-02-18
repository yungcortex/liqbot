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
    ping_timeout=20,
    ping_interval=10,
    manage_session=True,
    cookie=False,
    always_connect=True,
    transports=['websocket'],
    max_http_buffer_size=1024 * 1024,  # 1MB
    async_handlers=True,
    monitor_clients=True
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

# Active connections tracking
active_connections = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    try:
        sid = request.sid
        logger.info(f"Client connected - SID: {sid}")
        
        # Track the connection
        active_connections[sid] = {
            'connected_at': datetime.now(),
            'last_heartbeat': datetime.now()
        }
        
        # Send initial stats
        emit('stats_update', latest_stats, broadcast=False)
        emit('connection_success', {'status': 'connected', 'sid': sid}, broadcast=False)
        
        # Force event emission
        socketio.sleep(0)
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")
        if hasattr(request, 'sid'):
            cleanup_connection(request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    try:
        sid = request.sid
        logger.info(f"Client disconnected - SID: {sid}")
        cleanup_connection(sid)
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")

def cleanup_connection(sid):
    """Clean up a connection"""
    try:
        # Remove from tracking
        if sid in active_connections:
            del active_connections[sid]
        
        # Clean up socket
        if hasattr(socketio, 'server') and hasattr(socketio.server, 'eio'):
            try:
                # Remove from rooms
                rooms = socketio.server.rooms(sid, '/')
                if rooms:
                    for room in rooms:
                        socketio.server.leave_room(sid, room, '/')
                
                # Close socket
                if sid in socketio.server.eio.sockets:
                    socket = socketio.server.eio.sockets[sid]
                    socket.close(wait=False, abort=True)
                    del socketio.server.eio.sockets[sid]
                
                # Disconnect from namespace
                socketio.server.disconnect(sid, namespace='/')
            except Exception as e:
                logger.error(f"Error cleaning up socket {sid}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup_connection for {sid}: {e}")

@socketio.on('heartbeat')
def handle_heartbeat():
    """Handle client heartbeat"""
    try:
        sid = request.sid
        if sid in active_connections:
            active_connections[sid]['last_heartbeat'] = datetime.now()
            emit('heartbeat_response', {'status': 'ok'}, broadcast=False)
    except Exception as e:
        logger.error(f"Error in handle_heartbeat: {e}")

def check_connections():
    """Check and clean up stale connections"""
    try:
        current_time = datetime.now()
        stale_sids = []
        
        for sid, data in active_connections.items():
            if (current_time - data['last_heartbeat']).total_seconds() > 30:  # 30 seconds timeout
                stale_sids.append(sid)
        
        for sid in stale_sids:
            logger.info(f"Cleaning up stale connection {sid}")
            cleanup_connection(sid)
    except Exception as e:
        logger.error(f"Error in check_connections: {e}")

def emit_update(data, event_type='stats_update'):
    """Emit updates to all connected clients"""
    try:
        if event_type == 'stats_update':
            for symbol, values in data.items():
                if symbol in latest_stats:
                    latest_stats[symbol].update(values)
        
        # Log the event
        logger.info(f"Emitting {event_type} event: {data}")
        
        # Check for stale connections before emitting
        check_connections()
        
        # Emit with broadcast and force immediate send
        socketio.emit(event_type, data, broadcast=True, namespace='/')
        socketio.sleep(0)  # Force event emission
        
        logger.info(f"Successfully emitted {event_type} event")
    except Exception as e:
        logger.error(f"Error emitting {event_type}: {e}")
        # Clean up any broken connections
        check_connections()

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

        # Log the event
        logger.info(f"Processing liquidation event: {data}")
        logger.info(f"Current stats: {latest_stats}")

        # Check for stale connections before emitting
        check_connections()

        # Emit events with broadcast and force immediate send
        try:
            socketio.emit('liquidation', data, broadcast=True, namespace='/')
            socketio.sleep(0)  # Force first event emission
            socketio.emit('stats_update', latest_stats, broadcast=True, namespace='/')
            socketio.sleep(0)  # Force second event emission
        except Exception as e:
            logger.error(f"Error emitting events: {e}")
            check_connections()

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