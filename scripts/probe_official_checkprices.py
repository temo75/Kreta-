import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.fuelprices.gr/"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (compatible; TEMO-Kreta/1.0)"
for url in [
    urljoin(BASE, "CheckPrices"),
    urljoin(BASE, "GetGeography?nomos=81000000&return_to=CheckPrices"),
    urljoin(BASE, "GetGeography?nomos=82000000&return_to=CheckPrices"),
    urljoin(BASE, "GetGeography?nomos=83000000&return_to=CheckPrices"),
    urljoin(BASE, "GetGeography?nomos=84000000&return_to=CheckPrices"),
]:
    r=s.get(url, timeout=30)
    r.encoding = r.apparent_encoding or "cp1253"
    soup=BeautifulSoup(r.text, "html.parser")
    print("\nPAGE", r.status_code, r.url, "bytes", len(r.content), "title", soup.title.get_text(" ",strip=True) if soup.title else "")
    for form in soup.find_all("form"):
        print(" FORM", form.get("action"), form.get("method"))
        for el in form.find_all(["input","select","button"]):
            if el.name=="select":
                print(" SELECT", el.get("name"), [(o.get("value"),o.get_text(" ",strip=True)) for o in el.find_all("option")][:100])
            else:
                print(" INPUT", el.name, el.get("name"), el.get("type"), el.get("value"), el.get_text(" ",strip=True)[:80])
    print("TEXT", soup.get_text(" ",strip=True)[:1200])
