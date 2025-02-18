import eventlet
eventlet.monkey_patch()

from app import app, socketio, background_tasks
import threading

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
    max_http_buffer_size=1e6,
    manage_session=False,
    message_queue=None,
    always_connect=True,
    transports=['websocket', 'polling'],
    cookie=False,
    logger=True,
    engineio_logger=True
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