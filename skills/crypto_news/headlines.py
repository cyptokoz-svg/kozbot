import requests
import json
import xml.etree.ElementTree as ET

def get_news():
    # Use Coindesk RSS as a reliable proxy for "Twitter-like" breaking news
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    try:
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        
        news = []
        for item in root.findall(".//item")[:5]:
            title = item.find("title").text
            link = item.find("link").text
            news.append({"title": title, "link": link})
            
        print(json.dumps(news, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    get_news()
