# Crypto Liquidation Tracker

<<<<<<< HEAD
A real-time cryptocurrency liquidation tracker for Bybit. Monitor BTC, ETH, and SOL liquidations with both terminal and web interfaces. Features color-coded notifications for long and short positions.
=======
A real-time terminal-based tracker for cryptocurrency liquidations on Bybit. Monitors BTC, ETH, and SOL liquidations with color-coded notifications for long and short positions.
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d

## Features

- Real-time liquidation tracking for BTC, ETH, and SOL
<<<<<<< HEAD
- Two interfaces:
  - Terminal-based interface with Rich text formatting
  - Modern web interface with real-time updates
- Color-coded output (green for long liquidations, red for short liquidations)
- Live statistics showing:
=======
- Color-coded output (green for long liquidations, red for short liquidations)
- Live statistics table showing:
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d
  - Number of long liquidations
  - Number of short liquidations
  - Total liquidation value in USD
- Fire emoji (🔥) indicators for visual appeal

## Setup

1. Make sure you have Python 3.7+ installed
<<<<<<< HEAD
2. Download or clone this repository:
```bash
git clone https://github.com/yungcortex/liquitation_bot.git
cd liquitation_bot
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
=======
2. Download or clone this repository to your computer
3. Install the required packages:
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d
```bash
pip install -r requirements.txt
```

## Running the Bot

<<<<<<< HEAD
You can run the bot in either terminal mode or web interface mode:

### Terminal Interface

1. Navigate to the project directory:
```bash
cd "path/to/liquidation-bot"
```
2. Activate the virtual environment (if not already activated):
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
3. Run the terminal interface:
=======
There are two ways to run the bot:

### Method 1: From the project directory (Recommended)
1. Open your terminal
2. Navigate to where you downloaded the project:
```bash
cd "path/to/liquidation-bot"
```
3. Run the bot:
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d
```bash
python liquidation_bot.py
```

<<<<<<< HEAD
### Web Interface

1. Navigate to the project directory:
```bash
cd "path/to/liquidation-bot"
```
2. Activate the virtual environment (if not already activated):
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
3. Start the web server:
```bash
cd web
python app.py
```
4. Open your browser and visit: `http://localhost:5000`

The web interface features:
- Modern, dark-themed UI
- Real-time updates via WebSocket
- Responsive design for mobile and desktop
- Cryptocurrency logos and card-based layout
- Color-coded liquidation feed
=======
### Method 2: From any location
You can run the bot from any directory by providing the full path to the script:
```bash
python "path/to/liquidation-bot/liquidation_bot.py"
```

Replace `path/to/liquidation-bot` with the actual path where you downloaded the project.

For example:
- Windows: `python "C:\Users\YourUsername\Downloads\liquidation-bot\liquidation_bot.py"`
- Mac/Linux: `python "/Users/YourUsername/Downloads/liquidation-bot/liquidation_bot.py"`
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d

## Understanding the Output

- 🟢 Green messages indicate long position liquidations
- 🔴 Red messages indicate short position liquidations
<<<<<<< HEAD
- The statistics show running totals for each type of liquidation
=======
- The table shows running totals for each type of liquidation
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d
- All values are displayed in USD
- Blue messages show raw WebSocket data (for debugging)
- Cyan messages show connection status and successful processing

## Troubleshooting

<<<<<<< HEAD
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
=======
If you get module errors, ensure all dependencies are installed:
```bash
pip install websockets==12.0 python-dotenv==1.0.0 rich==13.7.0
```

Press Ctrl+C to exit the program. 
>>>>>>> e8941924efa6cfdf36e68721f5ea18000731339d
