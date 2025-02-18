import eventlet
eventlet.monkey_patch()

from app import app, socketio, background_tasks
import threading
import logging
import signal
import sys
import time
import weakref
from eventlet import wsgi, websocket
from eventlet.green import socket
import errno
from flask import request
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize eventlet hub before anything else
eventlet.hubs.use_hub()

# Global state
is_shutting_down = False
active_connections = {}
connection_lock = threading.Lock()

class SocketManager:
    def __init__(self):
        self.sockets = {}
        self.lock = threading.Lock()
        
    def add_socket(self, sid, socket):
        with self.lock:
            self.sockets[sid] = socket
            
    def remove_socket(self, sid):
        with self.lock:
            if sid in self.sockets:
                del self.sockets[sid]
                
    def get_socket(self, sid):
        with self.lock:
            return self.sockets.get(sid)
            
    def clear(self):
        with self.lock:
            self.sockets.clear()

socket_manager = SocketManager()

def handle_socket_error(socket, e):
    """Handle socket errors gracefully"""
    if isinstance(e, (IOError, OSError)):
        error_code = getattr(e, 'errno', None)
        if error_code in (errno.EBADF, errno.EPIPE, errno.ENOTCONN, errno.ESHUTDOWN):
            logger.warning(f"Expected socket error: {e}")
            return True
        logger.error(f"Unexpected socket error: {e}")
    return False

def wrap_socket(sock):
    """Wrap a socket with error handling"""
    if not sock:
        return sock
        
    # Store original methods
    _send = getattr(sock, 'send', None)
    _close = getattr(sock, 'close', None)
    _fileno = getattr(sock, 'fileno', None)
    
    def safe_send(data, *args, **kwargs):
        try:
            if not _send or getattr(sock, 'closed', False):
                return 0
            return _send(data, *args, **kwargs)
        except Exception as e:
            if isinstance(e, (IOError, OSError)) and e.errno == errno.EBADF:
                logger.debug(f"Bad file descriptor in safe_send")
            else:
                logger.error(f"Error in safe_send: {e}")
            return 0
            
    def safe_close(*args, **kwargs):
        try:
            if not _close or getattr(sock, 'closed', False):
                return
            _close(*args, **kwargs)
        except Exception as e:
            if isinstance(e, (IOError, OSError)) and e.errno == errno.EBADF:
                logger.debug(f"Bad file descriptor in safe_close")
            else:
                logger.error(f"Error in safe_close: {e}")
            
    def safe_fileno(*args, **kwargs):
        try:
            if not _fileno or getattr(sock, 'closed', False):
                raise IOError(errno.EBADF, "Bad file descriptor")
            return _fileno(*args, **kwargs)
        except Exception as e:
            if isinstance(e, (IOError, OSError)) and e.errno == errno.EBADF:
                logger.debug(f"Bad file descriptor in safe_fileno")
            else:
                logger.error(f"Error in safe_fileno: {e}")
            raise
            
    # Replace methods
    if _send:
        sock.send = safe_send
    if _close:
        sock.close = safe_close
    if _fileno:
        sock.fileno = safe_fileno
        
    return sock

def cleanup_socket(sid, socket):
    """Clean up a single socket"""
    try:
        logger.info(f"Cleaning up socket {sid}")
        
        # Remove from socket manager first
        socket_manager.remove_socket(sid)
        
        # Remove from active connections
        with connection_lock:
            active_connections.pop(sid, None)
        
        if socket:
            try:
                # Close WebSocket first if it exists
                if hasattr(socket, 'ws') and socket.ws:
                    try:
                        socket.ws.close()
                    except Exception as e:
                        if isinstance(e, (IOError, OSError)) and e.errno == errno.EBADF:
                            logger.debug(f"Bad file descriptor while closing WebSocket")
                        else:
                            logger.error(f"Error closing WebSocket: {e}")
                
                # Then close the socket itself
                if not getattr(socket, 'closed', False):
                    try:
                        socket.close()
                    except Exception as e:
                        if isinstance(e, (IOError, OSError)) and e.errno == errno.EBADF:
                            logger.debug(f"Bad file descriptor while closing socket")
                        else:
                            logger.error(f"Error closing socket: {e}")
                            
            except Exception as e:
                logger.error(f"Error in socket cleanup: {e}")
                
    except Exception as e:
        logger.error(f"Error cleaning up socket {sid}: {e}")

def cleanup_sockets():
    """Clean up all socket connections"""
    try:
        logger.info("Starting socket cleanup...")
        if hasattr(socketio.server, 'eio'):
            # Get a copy of the sockets dict to avoid modification during iteration
            try:
                sockets = dict(socketio.server.eio.sockets)
                for sid, socket in sockets.items():
                    try:
                        cleanup_socket(sid, socket)
                    except Exception as e:
                        logger.error(f"Error cleaning up socket {sid}: {e}")
                        continue
                    
                # Clear all remaining state
                socketio.server.eio.sockets.clear()
                socket_manager.clear()
                
            except Exception as e:
                logger.error(f"Error getting sockets dict: {e}")
            
        logger.info("Socket cleanup completed")
    except Exception as e:
        logger.error(f"Error in socket cleanup: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global is_shutting_down
    logger.info(f"Received signal {signum}. Starting graceful shutdown...")
    is_shutting_down = True
    cleanup_sockets()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Start the liquidation bot in a separate thread
bot_thread = threading.Thread(target=background_tasks)
bot_thread.daemon = True
bot_thread.start()

# Create the WSGI application
application = app

# Socket.IO middleware to wrap sockets
def socket_middleware(wsgi_app):
    def middleware(environ, start_response):
        # Only wrap valid sockets
        if 'eventlet.input' in environ and hasattr(environ['eventlet.input'], 'socket'):
            sock = environ['eventlet.input'].socket
            if sock and not getattr(sock, 'closed', False):
                environ['eventlet.input'].socket = wrap_socket(sock)
        return wsgi_app(environ, start_response)
    return middleware

# Apply middleware
application.wsgi_app = socket_middleware(application.wsgi_app)

# Initialize Socket.IO with improved settings
socketio.init_app(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",  # Temporarily allow all origins for testing
    ping_timeout=20000,
    ping_interval=10000,
    manage_session=False,
    message_queue=None,
    always_connect=True,
    transports=['polling', 'websocket'],  # Enable both transports
    cookie=None,
    logger=True,
    engineio_logger=True,
    async_handlers=True,
    monitor_clients=False,
    upgrade_timeout=20000,
    max_http_buffer_size=1024 * 1024,
    websocket_ping_interval=10000,
    websocket_ping_timeout=20000,
    cors_credentials=False,
    cors_headers=['Content-Type', 'X-Requested-With'],
    close_timeout=20000,
    max_queue_size=100,
    reconnection=True,
    reconnection_attempts=float('inf'),
    reconnection_delay=1000,
    reconnection_delay_max=5000,
    max_retries=float('inf'),
    retry_delay=1000,
    retry_delay_max=5000,
    ping_interval_grace_period=2000,
    allow_upgrades=True,
    json=True,
    http_compression=False,
    compression_threshold=1024,
    max_decode_packets=50,
    max_encode_packets=50,
    handle_sigint=False,
    namespace='/',
    async_handlers_kwargs={'async_mode': 'eventlet'},
    engineio_logger_kwargs={'level': logging.INFO}
)

# Configure CORS for Flask app
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Temporarily allow all origins for testing
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-Requested-With"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

# Socket connection handler
@socketio.on('connect')
def handle_connect():
    """Handle new socket connections"""
    try:
        sid = request.sid
        if not sid:
            logger.error("No session ID found for connection")
            return False

        logger.info(f"New connection attempt from {sid}")
            
        # Get the Engine.IO socket
        socket = None
        if hasattr(socketio.server, 'eio'):
            socket = socketio.server.eio.sockets.get(sid)
            
        if not socket:
            logger.error(f"No Engine.IO socket found for {sid}")
            return False
            
        # Add to active connections
        with connection_lock:
            active_connections[sid] = {
                'connected_at': time.time(),
                'last_heartbeat': time.time(),
                'socket': socket
            }
            
        logger.info(f"New socket connection established: {sid}")
        
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
        if 'sid' in locals() and 'socket' in locals():
            cleanup_socket(sid, socket)
        return False

@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection"""
    try:
        sid = request.sid
        if sid:
            logger.info(f"Client disconnecting: {sid}")
            with connection_lock:
                if sid in active_connections:
                    socket = active_connections[sid].get('socket')
                    cleanup_socket(sid, socket)
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")

# Add heartbeat handler
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

# Register cleanup function
import atexit
atexit.register(cleanup_sockets)

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
        cleanup_sockets()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        cleanup_sockets()
    finally:
        cleanup_sockets() 