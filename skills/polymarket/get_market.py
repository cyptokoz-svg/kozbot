import sys
import requests
import json

def get_market(condition_id):
    url = f"https://gamma-api.polymarket.com/markets/{condition_id}"
    try:
        resp = requests.get(url)
        data = resp.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else ""
    get_market(cid)
