# Crypto Liquidation Tracker

A real-time terminal-based tracker for cryptocurrency liquidations on Bybit. Monitors BTC, ETH, and SOL liquidations with color-coded notifications for long and short positions.

## Features

- Real-time liquidation tracking for BTC, ETH, and SOL
- Color-coded output (green for long liquidations, red for short liquidations)
- Live statistics table showing:
  - Number of long liquidations
  - Number of short liquidations
  - Total liquidation value in USD
- Fire emoji (🔥) indicators for visual appeal

## Setup

1. Make sure you have Python 3.7+ installed
2. Download or clone this repository to your computer
3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Running the Bot

There are two ways to run the bot:

### Method 1: From the project directory (Recommended)
1. Open your terminal
2. Navigate to where you downloaded the project:
```bash
cd "path/to/liquidation-bot"
```
3. Run the bot:
```bash
python liquidation_bot.py
```

### Method 2: From any location
You can run the bot from any directory by providing the full path to the script:
```bash
python "path/to/liquidation-bot/liquidation_bot.py"
```

Replace `path/to/liquidation-bot` with the actual path where you downloaded the project.

For example:
- Windows: `python "C:\Users\YourUsername\Downloads\liquidation-bot\liquidation_bot.py"`
- Mac/Linux: `python "/Users/YourUsername/Downloads/liquidation-bot/liquidation_bot.py"`

## Understanding the Output

- 🟢 Green messages indicate long position liquidations
- 🔴 Red messages indicate short position liquidations
- The table shows running totals for each type of liquidation
- All values are displayed in USD
- Blue messages show raw WebSocket data (for debugging)
- Cyan messages show connection status and successful processing

## Troubleshooting

If you get module errors, ensure all dependencies are installed:
```bash
pip install websockets==12.0 python-dotenv==1.0.0 rich==13.7.0
```

Press Ctrl+C to exit the program. 