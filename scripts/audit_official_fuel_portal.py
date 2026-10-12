#!/usr/bin/env python3
"""Read-only probe of Greece's official fuel-price observatory. Never changes live prices."""
import re
import requests
from html.parser import HTMLParser

BASE = "https://www.fuelprices.gr"
PATHS = ["/", "/GetGeography", "/GetGeography?nomos=-1&return_to=CheckPrices",
         "/PriceStats?prodclass=1", "/PriceStats?prodclass=3", "/PriceStats?prodclass=5"]

class Probe(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms=[]; self.form=None; self.inputs=[]; self.selects=[]; self.current_select=None
        self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="form":
            self.form={"action":a.get("action",""),"method":a.get("method","get"),"inputs":[],"selects":[]}
            self.forms.append(self.form)
        elif tag=="input" and self.form is not None:
            self.form["inputs"].append({k:a.get(k,"") for k in ("name","type","value")})
        elif tag=="select" and self.form is not None:
            self.current_select={"name":a.get("name",""),"options":[]}
            self.form["selects"].append(self.current_select)
        elif tag=="option" and self.current_select is not None:
            self.current_select["options"].append({"value":a.get("value","")})
        elif tag=="a" and a.get("href"):
            self.links.append(a["href"])
    def handle_endtag(self,tag):
        if tag=="select": self.current_select=None
        elif tag=="form": self.form=None

def main():
    s=requests.Session()
    s.headers["User-Agent"]="Mozilla/5.0 (compatible; KretaFuelSourceAudit/1.0)"
    for path in PATHS:
        url=BASE+path
        try:
            r=s.get(url,timeout=25)
            print(f"PAGE {path} HTTP={r.status_code} FINAL={r.url} TYPE={r.headers.get('Content-Type','')}")
            r.raise_for_status()
            p=Probe(); p.feed(r.text)
            print(" FORMS",p.forms[:8])
            print(" LINK_HINTS",[x for x in p.links if any(k in x.lower() for k in ("price","check","fuel","station","prat"))][:25])
            print(" TEXT_HINTS",re.sub(r"\\s+"," ",re.sub(r"<[^>]+>"," ",r.text))[:250])
        except Exception as e:
            print(" ERROR",repr(e))
if __name__=="__main__": main()
