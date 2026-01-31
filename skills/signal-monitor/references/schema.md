# Signal Schema Documentation

## Core Signal Structure

```json
{
  "timestamp": "2026-01-31T03:15:00+00:00",
  "market_pair": "BTC-USD",
  "edge": 0.1234,
  "strike_price": 87500.00,
  "confidence": 0.73,
  "signal_type": "ENTRY",
  "metadata": {
    "volatility": 0.023,
    "spread": 0.0012,
    "liquidity_depth": 150000,
    "time_to_expiry_hours": 48
  }
}
```

## Field Definitions

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | UTC timestamp of signal generation |
| `market_pair` | string | Trading pair identifier (e.g., "BTC-USD") |
| `edge` | float | Calculated advantage (0.0-1.0, typically 0.02-0.25) |
| `strike_price` | float | Target entry/exit price |
| `confidence` | float | Model confidence (0.0-1.0) |
| `signal_type` | enum | ENTRY, EXIT, or HOLD |

### Optional Metadata

| Field | Type | Description |
|-------|------|-------------|
| `volatility` | float | Current market volatility |
| `spread` | float | Bid-ask spread ratio |
| `liquidity_depth` | float | Available liquidity at strike |
| `time_to_expiry_hours` | int | Hours until market resolution |

## Signal Types

- **ENTRY**: Open a new position
- **EXIT**: Close existing position
- **HOLD**: Maintain current position (informational)

## Edge Calculation

Edge represents the calculated advantage based on:
- Mathematical probability (70%)
- AI-driven market analysis (30%)

Typical ranges:
- 0.02-0.05: Marginal edge
- 0.05-0.10: Good edge
- 0.10+: Strong edge

## Storage Format

Signals are stored as JSON Lines (JSONL) for append-only efficiency:
```
{"timestamp": "...", "market_pair": "...", ...}
{"timestamp": "...", "market_pair": "...", ...}
```

## Query Patterns

See `analysis_patterns.md` for common queries.
