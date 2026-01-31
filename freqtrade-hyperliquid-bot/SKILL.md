# Freqtrade Hyperliquid Skill

Freqtrade 交易所适配器 for Hyperliquid，支持现货和永续合约交易。

## 功能特性

- ✅ Hyperliquid 交易所集成
- ✅ 永续合约 (Perp) 交易支持
- ✅ Funding Rate 监控与套利
- ✅ 自动仓位管理
- ✅ 风险管理与止损

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 API
复制 `user_data/config/config.json.example` 到 `config.json` 并填入:
- `hyperliquid_api_key`
- `hyperliquid_api_secret`
- `hyperliquid_wallet_address`

### 3. 运行测试
```bash
python -m pytest tests/ -v
```

### 4. 启动交易
```bash
freqtrade trade --config user_data/config/config.json --strategy HyperliquidStrategy
```

## 策略说明

### HyperliquidStrategy
- 基于 Funding Rate 的套利策略
- 自动检测极端 funding 并进行对冲
- 结合 Polymarket 信号进行复合交易

## 项目结构

```
freqtrade-hyperliquid/
├── freqtrade_hl/          # 核心模块
│   ├── __init__.py
│   ├── exchange.py        # Hyperliquid 交易所适配
│   ├── funding_monitor.py # Funding Rate 监控
│   └── risk_manager.py    # 风险管理
├── tests/                 # 测试文件
├── user_data/             # 用户数据
│   ├── config/           # 配置文件
│   └── strategies/       # 策略文件
└── requirements.txt      # 依赖
```

## 配置文件

```json
{
  "exchange": {
    "name": "hyperliquid",
    "key": "your_api_key",
    "secret": "your_secret",
    "wallet": "your_wallet_address"
  },
  "strategy": "HyperliquidStrategy",
  "timeframe": "15m",
  "funding_monitor": {
    "enabled": true,
    "threshold": 0.001,
    "check_interval": 60
  }
}
```

## API 文档

### HyperliquidExchange
- `get_funding_rate(symbol)` - 获取资金费率
- `get_positions()` - 获取持仓
- `place_order(side, symbol, amount, price=None)` - 下单
- `get_balance()` - 获取余额

### FundingMonitor
- `start_monitoring()` - 启动监控
- `get_extreme_funding()` - 获取极端资金费率列表
- `get_arbitrage_opportunities()` - 获取套利机会

## 注意事项

1. **资金安全**: 首次使用请先用小资金测试
2. **API 限制**: 注意 Hyperliquid 的 API 频率限制
3. **网络延迟**: 建议使用靠近服务器的 VPS
4. **Funding 时间**: UTC 每 8 小时结算一次

## 免责声明

本 Skill 仅供学习研究使用，不构成投资建议。加密货币交易风险极高，可能导致本金全部损失。
