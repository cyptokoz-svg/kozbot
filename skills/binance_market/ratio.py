import requests
import sys
import json

def get_ls_ratio(symbol="BTCUSDT"):
    url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
    params = {"symbol": symbol, "period": "5m", "limit": 1}
    try:
        resp = requests.get(url, params=params).json()
        if resp:
            data = resp[0]
            print(json.dumps({
                "symbol": symbol,
                "longShortRatio": float(data["longShortRatio"]),
                "longAccount": float(data["longAccount"]),
                "shortAccount": float(data["shortAccount"])
            }, indent=2))
        else:
            print(json.dumps({"error": "No data"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    get_ls_ratio(sym)
