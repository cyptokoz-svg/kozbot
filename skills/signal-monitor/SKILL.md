---
name: signal-monitor
description: Log, monitor, and analyze trading signals for the Polymarket bot. Use when tracking signal frequency, quality metrics, or post-OBI-filter performance analysis. Helps identify signal drift, over-trading, and edge degradation over time.
---

# Signal Monitor

Lightweight trading signal logging and analysis system for monitoring Polymarket bot performance after OBI filter removal.

## Quick Start

```bash
# Log a new signal
python3 scripts/log_signal.py --pair "BTC-USD" --edge 0.12 --strike 85000 --confidence 0.73

# View recent signals
python3 scripts/signal_report.py --last 24h

# Check signal quality metrics
python3 scripts/signal_report.py --quality --since 2026-01-25
```

## Core Concepts

### Signal Schema
Each signal is stored as a structured entity:
- `timestamp` - UTC timestamp
- `market_pair` - Trading pair (e.g., "BTC-USD")
- `edge` - Calculated edge/advantage (0.0-1.0)
- `strike_price` - Entry price target
- `confidence` - Model confidence score
- `signal_type` - ENTRY | EXIT | HOLD
- `metadata` - Optional context (volatility, liquidity, etc.)

### Quality Metrics
- **Signal Frequency** - Signals per hour/day
- **Edge Distribution** - Mean, std dev of edge values
- **Strike Hit Rate** - % of signals reaching strike
- **Confidence Calibration** - Predicted vs actual accuracy

## Workflows

### 1. Log a Signal (from trading bot)
Use `scripts/log_signal.py` to record each signal:
```bash
python3 scripts/log_signal.py \
  --pair "BTC-USD" \
  --edge 0.15 \
  --strike 87500 \
  --confidence 0.68 \
  --type ENTRY \
  --meta '{"volatility": 0.023, "spread": 0.0012}'
```

### 2. Daily Signal Report
Generate a summary of recent signals:
```bash
python3 scripts/signal_report.py --last 24h --output markdown
```

### 3. Quality Analysis (Post-OBI)
Monitor for signal degradation after OBI filter removal:
```bash
python3 scripts/signal_report.py --quality --compare baseline
```

### 4. Alert on Anomalies
Detect unusual signal patterns:
```bash
python3 scripts/signal_report.py --anomaly-check --threshold 2.5
```

## File Locations

- Signal database: `~/.local/share/signal-monitor/signals.jsonl`
- Baseline metrics: `references/baseline_metrics.json`
- Config: `~/.config/signal-monitor/config.json`

## Integration with Trading Bot

Add to your Polymarket bot:
```python
import subprocess

def on_signal_generated(pair, edge, strike, confidence):
    subprocess.run([
        "python3", "skills/signal-monitor/scripts/log_signal.py",
        "--pair", pair,
        "--edge", str(edge),
        "--strike", str(strike),
        "--confidence", str(confidence)
    ])
```

## See Also

- `references/schema.md` - Complete signal schema documentation
- `references/baseline_metrics.json` - Pre-OBI baseline for comparison
- `references/analysis_patterns.md` - Common analysis queries
