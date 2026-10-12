import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
s=requests.Session(); s.headers["User-Agent"]="Mozilla/5.0 (compatible; TEMO-Kreta/1.0)"
for url in ["https://www.fuelprices.gr/","https://www.fuelprices.gr/deltia.view","https://www.fuelprices.gr/price_stats_ng.view?prodclass=1&time=1"]:
 r=s.get(url,timeout=30); r.encoding="cp1253"; soup=BeautifulSoup(r.text,"html.parser")
 print("\nPAGE",r.status_code,r.url,"bytes",len(r.content))
 for a in soup.find_all("a",href=True):
  t=a.get_text(" ",strip=True); h=urljoin(r.url,a["href"])
  if any(k in (t+" "+h).lower() for k in ["ημερήσια","νομό","delt","xls","csv","pdf","report","price","δελτί"]):
   print("LINK",repr(t),h)
 for form in soup.find_all("form"):
  print("FORM",form.get("action"),form.get("method"),[(x.name,x.get("name"),x.get("type"),x.get("value")) for x in form.find_all(["input","select"])][:20])
