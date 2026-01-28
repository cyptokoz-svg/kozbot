# Polymarket BTC 15m AI Trading Bot

An autonomous quant trading system for Polymarket's BTC 15-minute options markets.

## Features

- **Hybrid Strategy**: Combines Fair Value (Probability) with Machine Learning (Random Forest).
- **Auto-Learning**: Automatically retrains its ML model every 3 hours using self-mined historical data.
- **Dynamic Risk Management**: Adjusts position sizing and safety margins based on recent Profit Factor.
- **Self-Healing**: Monitors system health and restarts services automatically.

## Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your credentials:
   ```
   PK=your_private_key
   POLYGON_RPC=your_rpc_url
   ```
4. Run the bot:
   ```bash
   python btc_15m_bot_v3.py
   ```

## Architecture

- `btc_15m_bot_v3.py`: Main trading engine (AsyncIO).
- `train_ml.py`: ML model training script (Random Forest).
- `fetch_history.py`: Data mining script for historical market data.
- `augment_data.py`: Data augmentation for training balance.

## Disclaimer

This software is for educational purposes only. Use at your own risk.
