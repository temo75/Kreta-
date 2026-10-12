import requests
from bs4 import BeautifulSoup
URL = "https://www.vrisko.gr/en/fuel-prices/rethymno/"
for url in [URL, "https://www.vrisko.gr/times-kafsimon-venzinadika/rethymno/"]:
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36","Accept-Language":"el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7"},timeout=20)
        print("URL",url,"STATUS",r.status_code,"LENGTH",len(r.text),"FINAL",r.url)
        print("TITLE",BeautifulSoup(r.text,"html.parser").title.get_text(" ",strip=True) if r.status_code==200 and BeautifulSoup(r.text,"html.parser").title else "")
        if r.status_code==200:
            soup=BeautifulSoup(r.text,"html.parser")
            print("HEADINGS",len(soup.find_all(["h2","h3"])),"SAMPLE",soup.get_text(" ",strip=True)[:1200])
    except Exception as e:
        print("ERROR",url,repr(e))
