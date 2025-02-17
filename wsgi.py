import eventlet
eventlet.monkey_patch()

import os
import threading
from app import app, socketio, background_tasks

# Start the liquidation bot in a separate thread
bot_thread = threading.Thread(target=background_tasks)
bot_thread.daemon = True
bot_thread.start()

# This is what Gunicorn uses
application = socketio.middleware(app)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000))) 