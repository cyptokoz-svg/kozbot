import sys
import requests
import json

def search(query):
    url = "https://gamma-api.polymarket.com/events"
    params = {"q": query, "limit": 5}
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    search(q)
