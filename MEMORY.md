# Polymarket Bot Memory

## System Configuration (As of 2026-01-28)

### Core Strategy
- **Type**: Hybrid (Mathematical Fair Value + Machine Learning).
- **Script**: `btc_15m_bot_v3.py`.
- **Status**: ✅ Active / Running (Systemd: `polymarket-bot.service`).

### AI Model
- **Version**: V6.0 (2026-01-28 02:30 UTC).
- **Algorithm**: Random Forest Classifier.
- **Training Data**: ~6400 historical records (30 days).
- **Performance**: 70.22% Accuracy on validation set.
- **Key Features**: Previous Trend (35%), Momentum Strength (34%), Hour of Day (18%).
- **Auto-Evolution**: Retrains every 3 hours automatically.

### Risk Management
- **Stop Loss**: 25% (Hard limit).
- **Fee Setting**: Dynamic (Real-time Spread), capped at 3% conservative estimate.
- **Safety Margin**: 
  - Base: 0.06% (~$54 on $90k BTC).
  - Auto-Relax: If idle > 3 hours, drops to 0.04%.
- **Edge Requirement**: Min 10% theoretical edge (drops to 5% if idle).

### Infrastructure
- **Latency**: ~0.5ms to Binance, ~1.0ms to Polymarket.
- **Mode**: Paper Trading (Simulated execution, Real data/fees).
- **Privileges**: Private Key loaded for fee query, but trading flag is PAPER.

## Recent Events
- **2026-01-28 01:20**: Market chop caused 3 consecutive stop-losses.
- **Action**: Upgraded AI to V4/V5/V6, locked safety margin to 0.06% to filter noise.
- **Result**: Win rate stabilized, bot became more selective (fewer trades, higher quality).
