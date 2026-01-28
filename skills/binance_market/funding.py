import requests
import sys
import json

def get_funding(symbol="BTCUSDT"):
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    params = {"symbol": symbol}
    try:
        resp = requests.get(url, params=params).json()
        rate = float(resp.get("lastFundingRate", 0))
        print(json.dumps({
            "symbol": symbol,
            "fundingRate": rate,
            "annualized": rate * 3 * 365 * 100 # % per year
        }, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    get_funding(sym)
