import os
import json
from datetime import datetime

# Config
LOG_FILE = "/home/ubuntu/clawd/polymarket-bot/bot.log"
HTML_FILE = "/home/ubuntu/clawd/kozbot/index.html"
TRADES_FILE = "/home/ubuntu/clawd/polymarket-bot/paper_trades.jsonl"

def get_last_log():
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            return lines[-1].strip() if lines else "System Offline"
    except: return "No Logs"

def get_status():
    # Read bot mode from config or deduce (we know it's live)
    return "LIVE TRADING" 

def generate_html():
    status = get_status()
    last_log = get_last_log()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30"> <!-- Auto-refresh every 30s -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>J.A.R.V.I.S. Command</title>
    <style>
        body {{ background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }}
        h1 {{ border-bottom: 2px solid #0f0; padding-bottom: 10px; }}
        .status {{ font-size: 2em; font-weight: bold; color: {('#0f0' if 'LIVE' in status else '#ff0')}; }}
        .log {{ margin-top: 20px; padding: 10px; border: 1px solid #333; background: #050505; }}
        .timestamp {{ color: #555; font-size: 0.8em; }}
    </style>
</head>
<body>
    <h1>J.A.R.V.I.S. MONITOR</h1>
    <div class="timestamp">Last Updated: {now}</div>
    <br>
    <div>SYSTEM MODE: <span class="status">{status}</span></div>
    <div>BALANCE: <span style="color:white">$2.78 (Proxy)</span></div>
    
    <div class="log">
        <h3>>> LATEST TELEMETRY</h3>
        <p>{last_log}</p>
    </div>
</body>
</html>"""
    
    with open(HTML_FILE, 'w') as f:
        f.write(html)
    print("HTML Generated.")

if __name__ == "__main__":
    generate_html()
