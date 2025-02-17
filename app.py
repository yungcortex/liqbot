from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import asyncio
import threading
import json
from datetime import datetime
import sys
import os

# Add parent directory to path to import liquidation_bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from liquidation_bot import stats, process_liquidation, connect_websocket, set_web_update_callback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store the latest statistics
latest_stats = {
    "BTC": {"longs": 0, "shorts": 0, "total_value": 0},
    "ETH": {"longs": 0, "shorts": 0, "total_value": 0},
    "SOL": {"longs": 0, "shorts": 0, "total_value": 0}
}

@app.route('/')
def index():
    return render_template('index.html')

def emit_update(data, event_type='stats_update'):
    """Emit updates to all connected clients"""
    try:
        socketio.emit(event_type, data)
    except Exception as e:
        print(f"Error emitting {event_type}: {e}")

async def run_liquidation_bot():
    """Run the liquidation bot and forward updates to web clients"""
    # Set the callback for web updates
    set_web_update_callback(emit_update)
    
    while True:
        try:
            await connect_websocket()
        except Exception as e:
            print(f"Error in liquidation bot: {e}")
            await asyncio.sleep(5)

def background_tasks():
    """Run background tasks in asyncio event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_liquidation_bot())

if __name__ == '__main__':
    print("Starting Liquidation Tracker Web Interface...")
    print("Visit http://localhost:8080 in your browser")
    
    # Start the liquidation bot in a separate thread
    bot_thread = threading.Thread(target=background_tasks)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Run the Flask application
    socketio.run(app, debug=True, use_reloader=False, port=8080) 