import re
import sys
import requests
from bs4 import BeautifulSoup

URL = "https://www.vrisko.gr/times-kafsimon-venzinadika/rethymno/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TEMO-Kreta-FuelBot/1.0)", "Accept-Language": "el-GR,el;q=0.9"}

def main():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    print("STATUS", r.status_code, "URL", r.url, "LENGTH", len(r.text), "TYPE", r.headers.get("content-type"))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    headings = soup.find_all(["h2", "h3"])
    dates = re.findall(r"\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}", text)
    print("TITLE", soup.title.get_text(" ", strip=True) if soup.title else "")
    print("HEADINGS", len(headings), "TIMESTAMPS", len(dates))
    print("TEXT SAMPLE")
    print("\n".join(text.splitlines()[90:145]))
    for candidate in soup.find_all(string=lambda x: x and "ΠΑΠΑΔΑΚΗΣ ΒΑΣΙΛΕΙΟΣ" in x):
        node = candidate.parent
        for depth in range(1, 5):
            node = node.parent
            print("DOM_DEPTH", depth, "TAG", node.name, "ID", node.get("id"), "CLASS", node.get("class"))
            print(str(node)[:1800])
    if r.status_code == 200 and len(headings) >= 5 and len(dates) >= 5:
        print("PROBE_RESULT=PAGE_ACCESS_OK")
    else:
        print("PROBE_RESULT=UNEXPECTED_HTML")
        sys.exit(2)

if __name__ == "__main__":
    main()
