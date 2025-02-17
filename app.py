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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Store the latest statistics
latest_stats = {
    "BTC": {"longs": 0, "shorts": 0, "total_value": 0},
    "ETH": {"longs": 0, "shorts": 0, "total_value": 0},
    "SOL": {"longs": 0, "shorts": 0, "total_value": 0}
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print("Client connected")
    # Send current stats to newly connected client
    emit('stats_update', latest_stats)

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

def emit_update(data, event_type='stats_update'):
    """Emit updates to all connected clients"""
    try:
        print(f"Emitting {event_type}:", data)
        if event_type == 'stats_update':
            # Update our local stats
            for symbol, values in data.items():
                if symbol in latest_stats:
                    latest_stats[symbol].update(values)
        socketio.emit(event_type, data)
    except Exception as e:
        print(f"Error emitting {event_type}: {e}")

def process_liquidation_event(data):
    """Process a liquidation event and emit it to clients"""
    try:
        # Extract relevant information
        symbol = data.get('symbol', '')
        side = 'LONG' if data.get('side', '').upper() == 'BUY' else 'SHORT'
        amount = float(data.get('amount', 0))
        price = float(data.get('price', 0))
        
        # Update stats
        if symbol in latest_stats:
            if side == 'LONG':
                latest_stats[symbol]['longs'] += 1
            else:
                latest_stats[symbol]['shorts'] += 1
            latest_stats[symbol]['total_value'] += amount * price
        
        # Emit both the liquidation event and updated stats
        socketio.emit('liquidation', {
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price
        })
        socketio.emit('stats_update', latest_stats)
        
        print(f"Processed liquidation: {symbol} {side} {amount} @ {price}")
    except Exception as e:
        print(f"Error processing liquidation: {e}")

async def run_liquidation_bot():
    """Run the liquidation bot and forward updates to web clients"""
    # Set the callback for web updates
    set_web_update_callback(process_liquidation_event)
    
    while True:
        try:
            print("Connecting to Bybit WebSocket...")
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
    
    # Start the liquidation bot in a separate thread
    bot_thread = threading.Thread(target=background_tasks)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 10000))
    
    # Run the Flask application
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False) 