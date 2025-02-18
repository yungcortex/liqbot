import eventlet
eventlet.monkey_patch()

from app import app, socketio, background_tasks
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize eventlet hub
eventlet.hubs.use_hub()

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
    ping_timeout=30,
    ping_interval=15,
    manage_session=True,
    message_queue=None,
    always_connect=True,
    transports=['websocket'],
    cookie=False,
    logger=True,
    engineio_logger=True,
    async_handlers=True,
    monitor_clients=True,
    upgrade_timeout=10000,
    max_http_buffer_size=1024 * 1024,  # 1MB
    websocket_ping_interval=5,
    websocket_ping_timeout=10,
    websocket_max_message_size=1024 * 1024,  # 1MB
    cors_credentials=False,
    cors_headers=['Content-Type'],
    close_timeout=10
)

def cleanup_sockets():
    """Clean up any remaining socket connections"""
    try:
        for sid in socketio.server.eio.sockets:
            try:
                socketio.server.disconnect(sid, namespace='/')
            except Exception as e:
                logger.error(f"Error cleaning up socket {sid}: {e}")
    except Exception as e:
        logger.error(f"Error in socket cleanup: {e}")

# Register cleanup function
import atexit
atexit.register(cleanup_sockets)

# For local development
if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=10000,
        debug=False,
        use_reloader=False,
        log_output=True
    ) 