import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.fuelprices.gr/"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (compatible; TEMO-Kreta/1.0)"
for nomos in ["91000000", "92000000", "93000000", "94000000"]:
    url = urljoin(BASE, "GetGeography")
    r = s.get(url, params={"nomos":nomos,"return_to":"CheckPrices"}, timeout=30)
    r.encoding = "cp1253"
    soup = BeautifulSoup(r.text, "html.parser")
    dimos = [el.get("value") for el in soup.select('input[name="dimos"][type="checkbox"]') if el.get("value")]
    print("\nPREFECTURE", nomos, "municipalities", len(dimos))
    # Submit all municipalities, just as the site's "Select all" action does.
    params = [("nomos",nomos),("return_to","CheckPrices")] + [("dimos",v) for v in dimos] + [("submit","Επόμενο")]
    action = urljoin(r.url, soup.find("form").get("action") or "GetGeography")
    r2 = s.get(action, params=params, timeout=40)
    r2.encoding = "cp1253"
    soup2 = BeautifulSoup(r2.text, "html.parser")
    print("RESULT", r2.status_code, r2.url, "bytes", len(r2.content), "title", soup2.title.get_text(" ",strip=True) if soup2.title else "")
    print("TEXT", soup2.get_text(" ",strip=True)[:1800])
    for form in soup2.find_all("form"):
        print(" FORM", form.get("action"), form.get("method"))
        for el in form.find_all(["input","select","button"]):
            if el.name=="select":
                print(" SELECT",el.get("name"),[(o.get("value"),o.get_text(" ",strip=True)) for o in el.find_all("option")])
            else:
                print(" INPUT",el.name,el.get("name"),el.get("type"),el.get("value"),el.get_text(" ",strip=True)[:80])
