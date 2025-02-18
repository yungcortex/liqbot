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
    if isinstance(e, (IOError, OSError)):
        error_code = getattr(e, 'errno', None)
        if error_code in (errno.EBADF, errno.EPIPE, errno.ENOTCONN, errno.ESHUTDOWN):
            logger.warning(f"Expected socket error: {e}")
            return True
        logger.error(f"Unexpected socket error: {e}")
    return False

def wrap_socket(sock):
    """Wrap a socket with error handling"""
    if not sock or not hasattr(sock, 'send') or not hasattr(sock, 'close'):
        return sock
        
    _send = sock.send
    _close = sock.close
    _shutdown = getattr(sock, 'shutdown', None)
    
    def safe_send(data, *args, **kwargs):
        try:
            if hasattr(sock, 'closed') and sock.closed:
                return 0
            if hasattr(sock, 'fileno'):
                try:
                    if sock.fileno() == -1:
                        return 0
                except Exception:
                    return 0
            return _send(data, *args, **kwargs)
        except Exception as e:
            if not handle_socket_error(sock, e):
                logger.error(f"Error in safe_send: {e}")
            return 0
            
    def safe_close(*args, **kwargs):
        try:
            if hasattr(sock, 'closed') and sock.closed:
                return
                
            # Try to shutdown the socket first if it's still valid
            if _shutdown and hasattr(sock, 'fileno'):
                try:
                    if sock.fileno() != -1:
                        _shutdown(socket.SHUT_RDWR)
                except Exception as e:
                    handle_socket_error(sock, e)
            
            # Then close it
            return _close(*args, **kwargs)
        except Exception as e:
            if not handle_socket_error(sock, e):
                logger.error(f"Error in safe_close: {e}")
            
    sock.send = safe_send
    sock.close = safe_close
    return sock

def cleanup_socket(sid, socket):
    """Clean up a single socket"""
    try:
        logger.info(f"Cleaning up socket {sid}")
        
        # Remove from socket manager first
        socket_manager.remove_socket(sid)
        
        if not socket:
            logger.warning(f"Socket {sid} already removed")
            return
            
        # Check if socket is already closed
        if hasattr(socket, 'closed') and socket.closed:
            logger.warning(f"Socket {sid} is already closed")
            return
            
        # Remove from rooms
        if hasattr(socketio.server, 'rooms'):
            try:
                rooms = list(socketio.server.rooms(sid, '/'))
                for room in rooms:
                    try:
                        socketio.server.leave_room(sid, room, '/')
                    except Exception as e:
                        logger.warning(f"Error removing from room {room}: {e}")
            except Exception as e:
                logger.warning(f"Error getting rooms for {sid}: {e}")
        
        # Close socket safely
        if hasattr(socket, 'close'):
            try:
                # Check if socket is still valid before attempting shutdown
                if hasattr(socket, 'fileno'):
                    try:
                        if socket.fileno() != -1:
                            if hasattr(socket, 'shutdown'):
                                try:
                                    socket.shutdown(socket.SHUT_RDWR)
                                except Exception as e:
                                    handle_socket_error(socket, e)
                    except Exception:
                        pass
                
                # Close the socket
                socket.close(wait=False, abort=True)
            except Exception as e:
                handle_socket_error(socket, e)
            
        # Remove from server
        try:
            if hasattr(socketio.server, 'eio') and sid in socketio.server.eio.sockets:
                del socketio.server.eio.sockets[sid]
        except Exception as e:
            logger.warning(f"Error removing socket from server: {e}")
            
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
            socket = environ['eventlet.input'].socket
            if socket and not (hasattr(socket, 'closed') and socket.closed):
                environ['eventlet.input'].socket = wrap_socket(socket)
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
    manage_session=False,  # Disable session management to prevent ID mismatch
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
    reconnection=True,
    reconnection_attempts=float('inf'),
    reconnection_delay=1000,
    reconnection_delay_max=5000,
    max_retries=float('inf'),
    retry_delay=1000,
    retry_delay_max=5000,
    ping_interval_grace_period=2000,
    async_handlers_kwargs={'async_mode': 'eventlet'},
    engineio_logger_kwargs={'level': logging.INFO},
    namespace='/',  # Explicitly set default namespace
    allow_upgrades=False,  # Disable upgrades to prevent race conditions
    initial_packet_timeout=5,  # Reduce initial packet timeout
    connect_timeout=5,
    upgrades=[],  # Disable all upgrades
    allow_reconnection=True
)

# Socket connection handler
@socketio.on('connect')
def handle_connect():
    """Handle new socket connections"""
    try:
        sid = request.sid
        if not sid:
            logger.error("No session ID found for connection")
            return False
            
        # Initialize Socket.IO session
        if hasattr(socketio.server, 'manager'):
            try:
                # Create session
                socketio.server.manager.initialize(sid)
                socketio.server.enter_room(sid, sid, namespace='/')
                
                # Get the Engine.IO socket
                socket = socketio.server.eio.sockets.get(sid)
                if not socket:
                    logger.error(f"No Engine.IO socket found for {sid}")
                    return False
                
                # Wrap socket with error handling
                wrapped_socket = wrap_socket(socket)
                if wrapped_socket:
                    socket_manager.add_socket(sid, wrapped_socket)
                    logger.info(f"New socket connection established: {sid}")
                    
                    # Emit connection success
                    try:
                        socketio.emit('connection_success', {'status': 'connected', 'sid': sid}, room=sid, namespace='/')
                        eventlet.sleep(0)  # Force immediate emission
                        return True
                    except Exception as e:
                        logger.error(f"Error sending connection success: {e}")
                        cleanup_socket(sid, wrapped_socket)
                        return False
                    
            except Exception as e:
                logger.error(f"Error initializing Socket.IO session for {sid}: {e}")
                return False
            
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")
        if 'sid' in locals():
            cleanup_socket(sid, None)
        return False
    
    return True

@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection"""
    try:
        sid = request.sid
        if sid:
            logger.info(f"Client disconnecting: {sid}")
            if hasattr(socketio.server, 'manager'):
                socketio.server.leave_room(sid, sid, namespace='/')
                socketio.server.manager.disconnect(sid, '/')
            cleanup_socket(sid, socketio.server.eio.sockets.get(sid))
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {e}")

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