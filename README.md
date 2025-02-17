# Crypto Liquidation Tracker

A real-time cryptocurrency liquidation tracker for Bybit. Monitor BTC, ETH, and SOL liquidations with both terminal and web interfaces. Features color-coded notifications for long and short positions.

## Features

- Real-time liquidation tracking for BTC, ETH, and SOL
- Two interfaces:
  - Terminal-based interface with Rich text formatting
  - Modern web interface with real-time updates
- Color-coded output (green for long liquidations, red for short liquidations)
- Live statistics showing:
  - Number of long liquidations
  - Number of short liquidations
  - Total liquidation value in USD
- Fire emoji (🔥) indicators for visual appeal

## Setup

1. Make sure you have Python 3.7+ installed
2. Download or clone this repository:
```bash
git clone https://github.com/yungcortex/liqbot.git
cd liqbot
```

3. Create and activate a virtual environment:

### For Windows:
```bash
python -m venv .venv
.venv\Scripts\activate
```

### For Mac/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. Install the required packages:
```bash
pip install -r requirements.txt
```

## Running the Bot

You can run the bot in either terminal mode or web interface mode:

### Terminal Interface

1. Navigate to the project directory:
```bash
cd "path/to/liqbot"
```
2. Activate the virtual environment (if not already activated):
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
3. Run the terminal interface:
```bash
python liquidation_bot.py
```

### Web Interface

1. Navigate to the project directory:
```bash
cd "path/to/liqbot"
```
2. Activate the virtual environment (if not already activated):
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
3. Start the web server:
```bash
cd web
python app.py
```
4. Open your browser and visit: `http://localhost:8080`

The web interface features:
- Modern, dark-themed UI
- Real-time updates via WebSocket
- Responsive design for mobile and desktop
- Cryptocurrency logos and card-based layout
- Color-coded liquidation feed

## Understanding the Output

- 🟢 Green messages indicate long position liquidations
- 🔴 Red messages indicate short position liquidations
- The statistics show running totals for each type of liquidation
- All values are displayed in USD
- Blue messages show raw WebSocket data (for debugging)
- Cyan messages show connection status and successful processing

## Troubleshooting

If you get module errors, make sure you:
1. Have activated the virtual environment (you should see `(.venv)` in your terminal prompt)
2. Have installed all dependencies:
```bash
pip install websockets==12.0 python-dotenv==1.0.0 rich==13.7.0 flask==3.0.2 flask-socketio==5.3.6
```

To deactivate the virtual environment when you're done, simply type:
```bash
deactivate
```

## Contributing

Feel free to submit issues and enhancement requests!
