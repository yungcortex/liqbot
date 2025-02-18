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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize eventlet hub before anything else
eventlet.hubs.use_hub()

# Global state
is_shutting_down = False
connection_pool = weakref.WeakValueDictionary()
socket_pool = weakref.WeakValueDictionary()

class SocketManager:
    def __init__(self):
        self.sockets = weakref.WeakValueDictionary()
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
    if isinstance(e, (IOError, OSError)) and e.errno == errno.EBADF:
        # Bad file descriptor - socket was closed
        logger.warning(f"Socket was already closed: {e}")
        return True
    return False

def wrap_socket(sock):
    """Wrap a socket with error handling"""
    _send = sock.send
    _close = sock.close
    
    def safe_send(data, *args, **kwargs):
        try:
            return _send(data, *args, **kwargs)
        except Exception as e:
            if not handle_socket_error(sock, e):
                raise
            return 0
            
    def safe_close(*args, **kwargs):
        try:
            return _close(*args, **kwargs)
        except Exception as e:
            if not handle_socket_error(sock, e):
                raise
            
    sock.send = safe_send
    sock.close = safe_close
    return sock

def cleanup_socket(sid, socket):
    """Clean up a single socket"""
    try:
        logger.info(f"Cleaning up socket {sid}")
        
        # Remove from socket manager
        socket_manager.remove_socket(sid)
        
        # Remove from rooms
        if hasattr(socketio.server, 'rooms'):
            rooms = socketio.server.rooms(sid, '/')
            if rooms:
                for room in rooms:
                    socketio.server.leave_room(sid, room, '/')
        
        # Close socket safely
        if hasattr(socket, 'close'):
            try:
                socket.close(wait=False, abort=True)
            except Exception as e:
                handle_socket_error(socket, e)
            
        # Remove from server
        if hasattr(socketio.server, 'eio') and sid in socketio.server.eio.sockets:
            del socketio.server.eio.sockets[sid]
            
    except Exception as e:
        logger.error(f"Error cleaning up socket {sid}: {e}")

def cleanup_sockets():
    """Clean up all socket connections"""
    try:
        logger.info("Starting socket cleanup...")
        if hasattr(socketio.server, 'eio'):
            # Get a copy of the sockets dict to avoid modification during iteration
            sockets = dict(socketio.server.eio.sockets)
            for sid, socket in sockets.items():
                cleanup_socket(sid, socket)
                
            # Clear all remaining state
            socketio.server.eio.sockets.clear()
            socket_manager.clear()
            
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
        # Wrap the socket with error handling
        if 'eventlet.input' in environ:
            environ['eventlet.input'].socket = wrap_socket(environ['eventlet.input'].socket)
        return wsgi_app(environ, start_response)
    return middleware

# Apply middleware
application.wsgi_app = socket_middleware(application.wsgi_app)

# Initialize Socket.IO with improved settings
socketio.init_app(
    app,
    async_mode='eventlet',
    cors_allowed_origins=["https://liqbot-038f.onrender.com"],
    ping_timeout=20,
    ping_interval=10,
    manage_session=True,
    message_queue=None,
    always_connect=True,
    transports=['websocket'],
    cookie=False,
    logger=True,
    engineio_logger=True,
    async_handlers=True,
    monitor_clients=True,
    upgrade_timeout=5000,
    max_http_buffer_size=1024 * 1024,
    websocket_ping_interval=10,
    websocket_ping_timeout=20,
    websocket_max_message_size=1024 * 1024,
    cors_credentials=False,
    cors_headers=['Content-Type'],
    close_timeout=10,
    max_queue_size=10,
    async_mode_client='eventlet',
    reconnection=True,
    reconnection_attempts=float('inf'),
    reconnection_delay=1000,
    reconnection_delay_max=5000,
    max_retries=float('inf'),
    retry_delay=1000,
    retry_delay_max=5000,
    ping_interval_grace_period=2000
)

# Socket connection handler
@socketio.on('connect')
def handle_connect():
    """Handle new socket connections"""
    try:
        sid = request.sid
        if hasattr(socketio.server, 'eio'):
            socket = socketio.server.eio.sockets.get(sid)
            if socket:
                # Wrap socket with error handling
                wrapped_socket = wrap_socket(socket)
                socket_manager.add_socket(sid, wrapped_socket)
                logger.info(f"New socket connection: {sid}")
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")

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