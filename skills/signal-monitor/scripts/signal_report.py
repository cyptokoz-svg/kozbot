#!/usr/bin/env python3
"""
signal-monitor: Generate signal reports and quality analysis
"""

import argparse
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

SIGNALS_FILE = Path.home() / ".local" / "share" / "signal-monitor" / "signals.jsonl"


def load_signals(since: datetime = None) -> List[Dict[str, Any]]:
    """Load signals from database, optionally filtered by time."""
    signals = []
    
    if not SIGNALS_FILE.exists():
        return signals
    
    with open(SIGNALS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                signal = json.loads(line)
                if since:
                    signal_time = datetime.fromisoformat(signal["timestamp"])
                    if signal_time < since:
                        continue
                signals.append(signal)
            except json.JSONDecodeError:
                continue
    
    return signals


def calculate_metrics(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate quality metrics from signals."""
    if not signals:
        return {"count": 0}
    
    edges = [s["edge"] for s in signals]
    confidences = [s["confidence"] for s in signals]
    
    metrics = {
        "count": len(signals),
        "time_range": {
            "first": signals[0]["timestamp"],
            "last": signals[-1]["timestamp"]
        },
        "edge": {
            "mean": round(statistics.mean(edges), 4),
            "median": round(statistics.median(edges), 4),
            "std": round(statistics.stdev(edges), 4) if len(edges) > 1 else 0,
            "min": round(min(edges), 4),
            "max": round(max(edges), 4)
        },
        "confidence": {
            "mean": round(statistics.mean(confidences), 4),
            "median": round(statistics.median(confidences), 4),
            "std": round(statistics.stdev(confidences), 4) if len(confidences) > 1 else 0
        },
        "by_type": {}
    }
    
    # Group by signal type
    for signal in signals:
        sig_type = signal.get("signal_type", "UNKNOWN")
        if sig_type not in metrics["by_type"]:
            metrics["by_type"][sig_type] = 0
        metrics["by_type"][sig_type] += 1
    
    # Calculate frequency (signals per day)
    if len(signals) > 1:
        first = datetime.fromisoformat(signals[0]["timestamp"])
        last = datetime.fromisoformat(signals[-1]["timestamp"])
        days = max((last - first).total_seconds() / 86400, 0.001)
        metrics["frequency_per_day"] = round(len(signals) / days, 2)
    else:
        metrics["frequency_per_day"] = 0
    
    return metrics


def check_anomalies(signals: List[Dict[str, Any]], threshold: float = 2.0) -> List[Dict[str, Any]]:
    """Detect anomalous signals based on edge and confidence."""
    if len(signals) < 10:
        return []
    
    edges = [s["edge"] for s in signals]
    edge_mean = statistics.mean(edges)
    edge_std = statistics.stdev(edges) if len(edges) > 1 else 0
    
    anomalies = []
    for signal in signals:
        edge = signal["edge"]
        z_score = abs(edge - edge_mean) / edge_std if edge_std > 0 else 0
        if z_score > threshold:
            anomalies.append({
                "signal": signal,
                "z_score": round(z_score, 2),
                "reason": "edge_anomaly"
            })
    
    return anomalies


def format_markdown_report(metrics: Dict[str, Any], anomalies: List[Dict] = None) -> str:
    """Format metrics as markdown report."""
    lines = [
        "# 📊 Signal Monitor Report",
        "",
        f"**Total Signals:** {metrics['count']}",
        f"**Frequency:** {metrics.get('frequency_per_day', 0)} signals/day",
        "",
        "## Edge Statistics",
        f"- Mean: {metrics['edge']['mean']:.2%}",
        f"- Median: {metrics['edge']['median']:.2%}",
        f"- Std Dev: {metrics['edge']['std']:.2%}",
        f"- Range: {metrics['edge']['min']:.2%} - {metrics['edge']['max']:.2%}",
        "",
        "## Confidence Statistics",
        f"- Mean: {metrics['confidence']['mean']:.2%}",
        f"- Median: {metrics['confidence']['median']:.2%}",
        "",
        "## Signal Types",
    ]
    
    for sig_type, count in metrics.get("by_type", {}).items():
        lines.append(f"- {sig_type}: {count}")
    
    if anomalies:
        lines.extend([
            "",
            "## ⚠️ Anomalies Detected",
            f"Found {len(anomalies)} anomalous signals:",
        ])
        for a in anomalies[:5]:
            s = a["signal"]
            lines.append(f"- {s['market_pair']} @ {s['timestamp']}: edge={s['edge']:.2%}, z={a['z_score']}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate signal reports")
    parser.add_argument("--last", type=str, help="Time window (e.g., 24h, 7d)")
    parser.add_argument("--since", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--quality", action="store_true", help="Show quality metrics")
    parser.add_argument("--anomaly-check", action="store_true", help="Check for anomalies")
    parser.add_argument("--threshold", type=float, default=2.0, help="Anomaly threshold (z-score)")
    parser.add_argument("--output", choices=["json", "markdown"], default="markdown", 
                        help="Output format")
    
    args = parser.parse_args()
    
    # Determine time window
    since = None
    if args.last:
        if args.last.endswith("h"):
            hours = int(args.last[:-1])
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
        elif args.last.endswith("d"):
            days = int(args.last[:-1])
            since = datetime.now(timezone.utc) - timedelta(days=days)
    elif args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    
    # Load and analyze
    signals = load_signals(since)
    metrics = calculate_metrics(signals)
    
    anomalies = None
    if args.anomaly_check:
        anomalies = check_anomalies(signals, args.threshold)
    
    # Output
    if args.output == "json":
        result = {"metrics": metrics}
        if anomalies is not None:
            result["anomalies"] = anomalies
        print(json.dumps(result, indent=2))
    else:
        print(format_markdown_report(metrics, anomalies))


if __name__ == "__main__":
    main()
