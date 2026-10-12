import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.fuelprices.gr/"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (compatible; TEMO-Kreta/1.0)"
for nomos in ["91000000", "92000000", "93000000", "94000000"]:
    r = s.get(urljoin(BASE,"GetGeography"), params={"nomos":nomos,"return_to":"CheckPrices"}, timeout=30)
    r.encoding = "cp1253"
    soup = BeautifulSoup(r.text, "html.parser")
    municipalities = [el.get("value") for el in soup.select('input[name="dimos"][type="checkbox"]') if el.get("value")]
    params = [("nomos",nomos),("return_to","CheckPrices")] + [("dimos",v) for v in municipalities] + [("submit","Επόμενο")]
    r = s.get(urljoin(r.url,soup.find("form").get("action") or "GetGeography"),params=params,timeout=40)
    r.encoding = "cp1253"
    soup = BeautifulSoup(r.text,"html.parser")
    form=soup.find("form")
    dd=[el.get("value") for el in soup.select('input[name="DD"][type="checkbox"]') if el.get("value")]
    print("\nPREFECTURE",nomos,"municipalities",len(municipalities),"districts",len(dd),"form",form.get("action"),form.get("method"))
    action=urljoin(r.url,form.get("action") or "CheckPrices")
    # Select every local district as the site supports "Select All".
    payload=[("nomos",nomos),("return_to","CheckPrices")]+[("DD",v) for v in dd]
    r2=s.post(action,data=payload,timeout=45)
    r2.encoding="cp1253"
    soup2=BeautifulSoup(r2.text,"html.parser")
    print("RESULT",r2.status_code,r2.url,"bytes",len(r2.content),"title",soup2.title.get_text(" ",strip=True) if soup2.title else "")
    print("TEXT",soup2.get_text(" ",strip=True)[:3500])
    for form2 in soup2.find_all("form"):
        print(" RESULTFORM",form2.get("action"),form2.get("method"))
        for el in form2.find_all(["input","select","button"]):
            if el.name=="select":
                print(" SELECT",el.get("name"),[(o.get("value"),o.get_text(" ",strip=True)) for o in el.find_all("option")])
            else:
                print(" INPUT",el.name,el.get("name"),el.get("type"),el.get("value"),el.get_text(" ",strip=True)[:60])
