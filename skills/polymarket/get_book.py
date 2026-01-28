import sys
import requests
import json

def get_book(token_id):
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    try:
        resp = requests.get(url)
        data = resp.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else ""
    get_book(tid)
