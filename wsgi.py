import eventlet
eventlet.monkey_patch()

from app import app, socketio, background_tasks
import threading

# Start the liquidation bot in a separate thread
bot_thread = threading.Thread(target=background_tasks)
bot_thread.daemon = True
bot_thread.start()

# Create the WSGI application with Socket.IO middleware
application = socketio.middleware(app)

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