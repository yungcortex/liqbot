import eventlet
eventlet.monkey_patch()

from app import app, socketio, background_tasks
import threading
import logging
import signal
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize eventlet hub before anything else
eventlet.hubs.use_hub()

# Global flag for graceful shutdown
is_shutting_down = False
active_sockets = set()

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

def cleanup_sockets():
    """Clean up any remaining socket connections"""
    try:
        logger.info("Starting socket cleanup...")
        if hasattr(socketio, 'server') and hasattr(socketio.server, 'eio'):
            # Get a copy of the sockets dict to avoid modification during iteration
            sockets = dict(socketio.server.eio.sockets)
            for sid, socket in sockets.items():
                try:
                    logger.info(f"Cleaning up socket {sid}")
                    # Remove from rooms first
                    if hasattr(socketio.server, 'rooms'):
                        rooms = socketio.server.rooms(sid, '/')
                        if rooms:
                            for room in rooms:
                                socketio.server.leave_room(sid, room, '/')
                    
                    # Close socket with force
                    socket.close(wait=False, abort=True)
                    
                    # Remove from server
                    if sid in socketio.server.eio.sockets:
                        del socketio.server.eio.sockets[sid]
                        
                    # Clear any remaining state
                    if hasattr(socket, 'state'):
                        socket.state = None
                except Exception as e:
                    logger.error(f"Error cleaning up socket {sid}: {e}")
                    continue
                    
            # Clear all remaining state
            socketio.server.eio.sockets.clear()
            if hasattr(socketio.server, '_rooms'):
                socketio.server._rooms.clear()
            
        logger.info("Socket cleanup completed")
    except Exception as e:
        logger.error(f"Error in socket cleanup: {e}")

# Start the liquidation bot in a separate thread
bot_thread = threading.Thread(target=background_tasks)
bot_thread.daemon = True
bot_thread.start()

# Create the WSGI application
application = app

# Initialize Socket.IO with improved settings for Render
socketio.init_app(
    app,
    async_mode='eventlet',
    cors_allowed_origins=["https://liqbot-038f.onrender.com"],
    ping_timeout=15,
    ping_interval=5,
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
    max_http_buffer_size=1024 * 1024,  # 1MB
    websocket_ping_interval=5,
    websocket_ping_timeout=10,
    websocket_max_message_size=1024 * 1024,  # 1MB
    cors_credentials=False,
    cors_headers=['Content-Type'],
    close_timeout=5,
    max_queue_size=10,
    async_mode_client='eventlet',
    reconnection=True,
    reconnection_attempts=Infinity,
    reconnection_delay=1000,
    reconnection_delay_max=5000
)

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