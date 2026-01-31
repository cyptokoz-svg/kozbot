# Kozbot - Polymarket AI Trading Agent

JARVIS AI Agent for Polymarket prediction market trading with ML-enhanced strategies.

## 🏗️ Repository Structure

This repository contains the **core trading bot**. Skills have been extracted to a separate repository.

```
kozbot/
├── polymarket-bot/          # Trading bot core
│   ├── btc_15m_bot_v3.py   # Main trading logic
│   ├── train_ml.py         # ML model training
│   └── ...
├── memory/                  # Session logs and records
├── skills/                  # [External] Clone of jarvis-skills
└── [config files]
```

## 🔗 Related Repositories

| Repository | Description | Link |
|------------|-------------|------|
| **kozbot** (this) | Trading bot core | [GitHub](https://github.com/cyptokoz-svg/kozbot) |
| **jarvis-skills** | AI agent skills collection | [GitHub](https://github.com/cyptokoz-svg/jarvis-skills) |

## 🚀 Quick Start

### 1. Clone Bot Repository
```bash
git clone https://github.com/cyptokoz-svg/kozbot.git
cd kozbot
```

### 2. Clone Skills (Optional)
```bash
git clone https://github.com/cyptokoz-svg/jarvis-skills.git skills
```

### 3. Setup Bot
```bash
cd polymarket-bot
pip install -r requirements.txt
python btc_15m_bot_v3.py
```

## 📊 Features

- **ML-Enhanced Trading**: 15 features captured for model training
- **Automated Training**: Daily model retraining with auto-cleanup
- **Risk Management**: Stop-loss, take-profit, position sizing
- **Real-time Monitoring**: WebSocket price feeds
- **Paper Trading**: Test strategies without real money

## 🧠 ML Features (15 total)

| Category | Features |
|----------|----------|
| **Basic** | direction_code, entry_price, pnl |
| **Time** | hour, dayofweek, minutes_remaining |
| **Order Book** | poly_spread, poly_bid_depth, poly_ask_depth |
| **Price** | btc_price, diff_from_strike |
| **Technical** | rsi_14, atr_14, bb_pct, trend_ema |

## 📝 License

Private - All rights reserved.

## 🤖 About JARVIS

JARVIS (Just A Rather Very Intelligent System) is an AI agent designed for:
- Prediction market trading
- Social intelligence (Moltbook integration)
- Autonomous skill development

---

**Note**: This bot is for educational purposes. Trading carries significant risk.
