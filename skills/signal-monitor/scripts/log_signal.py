#!/usr/bin/env python3
"""
signal-monitor: Log trading signals to structured storage
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SIGNALS_DIR = Path.home() / ".local" / "share" / "signal-monitor"
SIGNALS_FILE = SIGNALS_DIR / "signals.jsonl"


def ensure_dir():
    """Ensure signals directory exists."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)


def log_signal(pair: str, edge: float, strike: float, confidence: float, 
               signal_type: str = "ENTRY", metadata: dict = None):
    """Log a single signal to the database."""
    ensure_dir()
    
    signal = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_pair": pair,
        "edge": round(edge, 4),
        "strike_price": round(strike, 2),
        "confidence": round(confidence, 4),
        "signal_type": signal_type,
        "metadata": metadata or {}
    }
    
    with open(SIGNALS_FILE, "a") as f:
        f.write(json.dumps(signal) + "\n")
    
    print(f"✓ Signal logged: {pair} @ edge={edge:.2%}, conf={confidence:.2%}")
    return signal


def main():
    parser = argparse.ArgumentParser(description="Log trading signals")
    parser.add_argument("--pair", required=True, help="Market pair (e.g., BTC-USD)")
    parser.add_argument("--edge", type=float, required=True, help="Edge/advantage (0.0-1.0)")
    parser.add_argument("--strike", type=float, required=True, help="Strike price")
    parser.add_argument("--confidence", type=float, required=True, help="Confidence score (0.0-1.0)")
    parser.add_argument("--type", default="ENTRY", choices=["ENTRY", "EXIT", "HOLD"], 
                        help="Signal type")
    parser.add_argument("--meta", type=str, help="JSON metadata string")
    
    args = parser.parse_args()
    
    metadata = json.loads(args.meta) if args.meta else None
    
    log_signal(
        pair=args.pair,
        edge=args.edge,
        strike=args.strike,
        confidence=args.confidence,
        signal_type=args.type,
        metadata=metadata
    )


if __name__ == "__main__":
    main()
