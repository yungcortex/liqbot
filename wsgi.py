import eventlet
eventlet.monkey_patch(socket=True, select=True)

from app import app, socketio, background_tasks
import threading

# Start the liquidation bot in a separate thread
bot_thread = threading.Thread(target=background_tasks)
bot_thread.daemon = True
bot_thread.start()

# Create the WSGI application
application = app

# Wrap with Socket.IO
socketio.init_app(app, async_mode='eventlet')

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