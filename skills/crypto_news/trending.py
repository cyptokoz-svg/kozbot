import requests
import json

def get_trending():
    url = "https://api.coingecko.com/api/v3/search/trending"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        trends = []
        for coin in data.get("coins", [])[:5]:
            item = coin["item"]
            trends.append({
                "name": item["name"],
                "symbol": item["symbol"],
                "rank": item["market_cap_rank"]
            })
            
        print(json.dumps(trends, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    get_trending()
