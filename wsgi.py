import eventlet
eventlet.monkey_patch()  # Full monkey patch for better compatibility

from app import app, socketio, background_tasks
import threading
import logging
import signal
import sys
import time
import json
import os
from eventlet import wsgi
from flask import request, session
from flask_cors import CORS
import redis
from flask_session import Session
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
try:
    # Parse Redis URL
    redis_url = urlparse(REDIS_URL)
    redis_client = redis.Redis(
        host=redis_url.hostname or 'localhost',
        port=int(redis_url.port or 6379),
        username=redis_url.username,
        password=redis_url.password,
        db=0,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30
    )
    # Test Redis connection
    redis_client.ping()
    logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

# Configure Flask session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_client
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
Session(app)

# Global state
active_connections = {}
connection_lock = threading.Lock()

def cleanup_socket(sid):
    """Clean up a single socket connection"""
    try:
        with connection_lock:
            if sid in active_connections:
                # Remove from Redis if available
                if redis_client:
                    try:
                        redis_client.delete(f"socket:{sid}")
                    except Exception as e:
                        logger.error(f"Error removing socket from Redis: {e}")
                
                # Remove from active connections
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

# Initialize Socket.IO with optimized settings
socketio_config = {
    'async_mode': 'eventlet',
    'cors_allowed_origins': ["https://liqbot-038f.onrender.com"],
    'ping_timeout': 60000,
    'ping_interval': 25000,
    'manage_session': True,
    'always_connect': True,
    'transports': ['polling'],
    'cookie': None,
    'logger': True,
    'engineio_logger': True,
    'async_handlers': True,
    'monitor_clients': True,
    'upgrade_timeout': 20000,
    'max_http_buffer_size': 1024 * 1024,
    'cors_credentials': True,
    'cors_headers': ['Content-Type', 'X-Requested-With'],
    'close_timeout': 60000,
    'max_queue_size': 100,
    'reconnection': True,
    'reconnection_attempts': 5,
    'reconnection_delay': 1000,
    'reconnection_delay_max': 5000,
    'max_retries': 5,
    'retry_delay': 1000,
    'retry_delay_max': 5000,
    'ping_interval_grace_period': 5000,
    'allow_upgrades': False,
    'json': json,
    'http_compression': False,
    'compression_threshold': 1024,
    'max_decode_packets': 50,
    'max_encode_packets': 50,
    'handle_sigint': False,
    'namespace': '/'
}

# Add message queue configuration if Redis is available
if redis_client:
    socketio_config['message_queue'] = REDIS_URL

socketio.init_app(app, **socketio_config)

# Configure CORS for Flask app
CORS(app, resources={
    r"/*": {
        "origins": ["https://liqbot-038f.onrender.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Requested-With"],
        "supports_credentials": True,
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
        
        # Store session data in memory and Redis if available
        session_data = {
            'connected_at': int(time.time()),
            'last_heartbeat': int(time.time())
        }
        
        if redis_client:
            try:
                redis_client.hmset(f"socket:{sid}", session_data)
                redis_client.expire(f"socket:{sid}", 3600)  # Expire after 1 hour
            except Exception as e:
                logger.error(f"Error storing session in Redis: {e}")
        
        with connection_lock:
            active_connections[sid] = session_data
            
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

@socketio.on('error')
def handle_error(error):
    """Handle socket errors"""
    try:
        sid = request.sid
        logger.error(f"Socket error for {sid}: {error}")
        if sid:
            cleanup_socket(sid)
    except Exception as e:
        logger.error(f"Error in handle_error: {e}")

@socketio.on('heartbeat')
def handle_heartbeat():
    """Handle client heartbeat"""
    try:
        sid = request.sid
        if not sid:
            return
            
        current_time = int(time.time())
            
        # Update heartbeat in Redis if available
        if redis_client:
            try:
                redis_client.hset(f"socket:{sid}", "last_heartbeat", current_time)
                redis_client.expire(f"socket:{sid}", 3600)  # Reset expiration
            except Exception as e:
                logger.error(f"Error updating Redis heartbeat: {e}")
            
        # Always update in-memory state
        with connection_lock:
            if sid in active_connections:
                active_connections[sid]['last_heartbeat'] = current_time
                
        socketio.emit('heartbeat_response', {'status': 'alive'}, room=sid)
    except Exception as e:
        logger.error(f"Error in handle_heartbeat: {e}")

def cleanup_stale_connections():
    """Clean up stale connections periodically"""
    while True:
        try:
            current_time = time.time()
            with connection_lock:
                # Work with a copy of the connections to avoid modification during iteration
                connections = dict(active_connections)
                for sid, data in connections.items():
                    try:
                        # Check if connection is stale (no heartbeat for 30 seconds)
                        if current_time - data['last_heartbeat'] > 30:
                            logger.info(f"Cleaning up stale connection: {sid}")
                            cleanup_socket(sid)
                    except Exception as e:
                        logger.error(f"Error checking connection {sid}: {e}")
                        cleanup_socket(sid)
        except Exception as e:
            logger.error(f"Error in cleanup thread: {e}")
        time.sleep(10)  # Run cleanup every 10 seconds

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_stale_connections, daemon=True)
cleanup_thread.start()

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