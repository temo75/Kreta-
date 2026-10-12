import requests
from bs4 import BeautifulSoup

URL = "https://www.vrisko.gr/times-kafsimon-venzinadika/rethymno/"
r = requests.get(URL, headers={"User-Agent":"Mozilla/5.0 (compatible; TEMO-Kreta-FuelBot/1.0)"}, timeout=30)
print("STATUS", r.status_code, "URL", r.url, "LENGTH", len(r.text), "TYPE", r.headers.get("content-type"))
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")
for text in soup.find_all(string=lambda x: x and "ΠΑΠΑΔΑΚΗΣ ΒΑΣΙΛΕΙΟΣ" in x):
    node = text.parent
    for depth in range(1, 8):
        node = node.parent
        print("\nDEPTH", depth, "TAG", node.name, "ID", node.get("id"), "CLASS", node.get("class"))
        print(str(node)[:5000])
        if depth >= 4:
            break
