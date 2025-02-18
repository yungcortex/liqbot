import eventlet
eventlet.monkey_patch()

from app import app, socketio, background_tasks
import threading

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
    ping_timeout=60,
    ping_interval=25,
    manage_session=False,
    message_queue=None,
    always_connect=True,
    transports=['websocket'],
    cookie=False,
    logger=True,
    engineio_logger=True,
    async_handlers=False,
    monitor_clients=False,
    upgrade_timeout=15000,
    max_http_buffer_size=1024 * 1024,  # 1MB
    websocket_ping_interval=10,
    websocket_ping_timeout=30,
    websocket_max_message_size=1024 * 1024,  # 1MB
    cors_credentials=False,
    cors_headers=['Content-Type']
)

# For local development
if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=10000,
        debug=True,
        use_reloader=False,
        log_output=True
    ) 