import eventlet
eventlet.monkey_patch()  # Full monkey patch for better compatibility

from app import app, socketio, background_tasks
import threading
import logging
import signal
import sys
import time
from eventlet import wsgi
from flask import request
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
active_connections = {}
connection_lock = threading.Lock()

def cleanup_socket(sid):
    """Clean up a single socket connection"""
    try:
        with connection_lock:
            if sid in active_connections:
                active_connections.pop(sid, None)
                logger.info(f"Cleaned up socket {sid}")
    except Exception as e:
        logger.error(f"Error cleaning up socket {sid}: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}. Starting graceful shutdown...")
    # Clean up all active connections
    with connection_lock:
        for sid in list(active_connections.keys()):
            cleanup_socket(sid)
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Start the liquidation bot in a separate thread
bot_thread = threading.Thread(target=background_tasks)
bot_thread.daemon = True
bot_thread.start()

# Initialize Socket.IO with simplified settings
socketio.init_app(
    app,
    async_mode='eventlet',
    cors_allowed_origins=["https://liqbot-038f.onrender.com"],
    ping_timeout=20000,
    ping_interval=10000,
    manage_session=True,
    message_queue=None,
    always_connect=True,
    transports=['polling'],  # Only use polling for now
    cookie=None,
    logger=True,
    engineio_logger=True,
    async_handlers=True,
    monitor_clients=True,
    upgrade_timeout=10000,
    max_http_buffer_size=1024 * 1024,
    cors_credentials=False,
    cors_headers=['Content-Type', 'X-Requested-With'],
    close_timeout=20000,
    max_queue_size=100,
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1000,
    reconnection_delay_max=5000,
    max_retries=5,
    retry_delay=1000,
    retry_delay_max=5000,
    ping_interval_grace_period=2000,
    allow_upgrades=False,  # Disable upgrades for now
    json=True,
    http_compression=False,
    compression_threshold=1024,
    max_decode_packets=50,
    max_encode_packets=50,
    handle_sigint=False,
    namespace='/'
)

# Configure CORS for Flask app
CORS(app, resources={
    r"/*": {
        "origins": ["https://liqbot-038f.onrender.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Requested-With"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

@socketio.on('connect')
def handle_connect():
    """Handle new socket connections"""
    try:
        sid = request.sid
        if not sid:
            logger.error("No session ID found for connection")
            return False

        logger.info(f"New connection: {sid}")
        
        with connection_lock:
            active_connections[sid] = {
                'connected_at': time.time(),
                'last_heartbeat': time.time()
            }
            
        # Emit initial connection success
        socketio.emit('connection_status', {'status': 'connected'}, room=sid)
        
        # Emit initial data
        socketio.emit('initial_data', {
            'bitcoin': {'long_liqs': 0, 'short_liqs': 0, 'total_value': 0},
            'ethereum': {'long_liqs': 0, 'short_liqs': 0, 'total_value': 0},
            'solana': {'long_liqs': 0, 'short_liqs': 0, 'total_value': 0}
        }, room=sid)
        
        return True
            
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")
        if 'sid' in locals():
            cleanup_socket(sid)
        return False

@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection"""
    try:
        sid = request.sid
        if sid:
            logger.info(f"Client disconnecting: {sid}")
            cleanup_socket(sid)
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")

@socketio.on('heartbeat')
def handle_heartbeat():
    """Handle client heartbeat"""
    try:
        sid = request.sid
        if sid in active_connections:
            with connection_lock:
                active_connections[sid]['last_heartbeat'] = time.time()
            socketio.emit('heartbeat_response', {'status': 'alive'}, room=sid)
    except Exception as e:
        logger.error(f"Error in handle_heartbeat: {e}")

# Create WSGI application
application = app

# For local development
if __name__ == '__main__':
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=10000,
            debug=False,
            use_reloader=False,
            log_output=True
        )
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Starting cleanup...")
        # Clean up all active connections
        with connection_lock:
            for sid in list(active_connections.keys()):
                cleanup_socket(sid)
    except Exception as e:
        logger.error(f"Error in main: {e}") 