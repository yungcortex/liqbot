import eventlet
eventlet.monkey_patch()

from app import app, socketio
import os

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 10000))) 