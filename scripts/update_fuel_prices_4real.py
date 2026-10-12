#!/usr/bin/env python3
# Live updater verified to use conservative phone/address matching; ambiguous stations remain untouched.
"""Refresh Crete fuel prices from 4real; conservative station matching."""
import json, re, sys, unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
import requests

REGIONS = {"Ρέθυμνο":"rethymno", "Ηράκλειο":"iraklio", "Χανιά":"chania", "Λασίθι":"lasithi"}
BASE = "https://www.4real.gr/FuelPrices/public/times/{}/brand"
PRICE_TYPES = ["95", "100", "super", "diesel", "heating_oil", "autogas"]
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; TEMO-Kreta-FuelUpdater/1.0)"}

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[]; self.table=None; self.row=None; self.cell=None; self.in_cell=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="table": self.table=[]
        elif tag=="tr" and self.table is not None: self.row=[]
        elif tag in ("td","th") and self.row is not None:
            self.cell={"text":"","alt":[]}; self.in_cell=True
        elif tag=="img" and self.cell is not None and a.get("alt"):
            self.cell["alt"].append(a["alt"].strip())
    def handle_data(self, data):
        if self.in_cell and self.cell is not None: self.cell["text"] += data
    def handle_endtag(self, tag):
        if tag in ("td","th") and self.cell is not None and self.row is not None:
            self.cell["text"]=re.sub(r"\s+"," ",self.cell["text"]).strip()
            self.row.append(self.cell); self.cell=None; self.in_cell=False
        elif tag=="tr" and self.row is not None and self.table is not None:
            if self.row: self.table.append(self.row)
            self.row=None
        elif tag=="table" and self.table is not None:
            self.tables.append(self.table); self.table=None

def digits(s): return re.sub(r"\D","",s or "")
def norm(s):
    s=unicodedata.normalize("NFKD", (s or "").casefold())
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.replace("λεωφ."," ").replace("λεωφόρος"," ").replace("χλμ"," ").replace("χλ."," ")
    return re.sub(r"[^a-z0-9α-ω]+"," ",s).strip()
def price(s):
    m=re.search(r"(?<!\d)(\d[,.]\d{2,3})(?!\d)",s or "")
    if not m: return None
    try: v=float(m.group(1).replace(",","."))
    except ValueError: return None
    return round(v,3) if 0.5 < v < 5 else None
def source_rows(html):
    p=TableParser(); p.feed(html); out=[]
    for table in p.tables:
        for row in table:
            if len(row)<8: continue
            cells=[c["text"] for c in row]
            address=cells[1] if len(cells)>1 else ""
            vals=[price(x) for x in cells[2:8]]
            if not address or not any(v is not None for v in vals): continue
            brand=next((a for c in row for a in c["alt"]), "") or (cells[0] if cells else "")
            ph=digits(address)
            out.append({"brand":brand.strip(),"address":address,"phone":ph[-10:] if len(ph)>=10 else "",
                        "norm":norm(address),"prices":dict(zip(PRICE_TYPES,vals))})
    # De-duplicate rows that appear repeatedly in malformed/duplicated table layouts.
    uniq={}
    for r in out: uniq[(r["phone"],r["norm"],tuple(sorted(r["prices"].items())))]=r
    return list(uniq.values())

def brand_norm(s):
    b=norm(s)
    aliases={"aegean":"αιγαιο","αιγαιο":"αιγαιο","ελιν":"ελινοιλ","elinoil":"ελινοιλ"}
    return aliases.get(b,b)

def match_station(stations, row, used):
    ph=row["phone"]
    if ph:
        matches=[s for s in stations if id(s) not in used and len(digits(s.get("address","")) )>=10 and digits(s.get("address",""))[-10:]==ph]
        if len(matches)==1: return matches[0], "phone"
    target_brand=brand_norm(row["brand"])
    ranked=[]
    for s in stations:
        if id(s) in used: continue
        sb=brand_norm(s.get("name",""))
        # Brand must agree; permit known Latin/Greek spellings only.
        if not sb or not target_brand or sb != target_brand:
            continue
        score=SequenceMatcher(None,row["norm"],norm(s.get("address",""))).ratio()
        if score>=0.76: ranked.append((score,s))
    ranked.sort(key=lambda x:x[0],reverse=True)
    if ranked and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>=0.10):
        return ranked[0][1], f"address:{ranked[0][0]:.2f}"
    return None,None

def main():
    path=Path("fuel-data.json")
    data=json.loads(path.read_text(encoding="utf-8"))
    session=requests.Session(); session.headers.update(HEADERS)
    now=datetime.now(timezone.utc).isoformat()
    total_rows=total_matches=total_prices=0
    for region_name,slug in REGIONS.items():
        region=next((r for r in data.get("regions",[]) if r.get("region")==region_name),None)
        if region is None: raise RuntimeError("Missing existing region: "+region_name)
        response=session.get(BASE.format(slug),timeout=35); response.raise_for_status()
        if "text/html" not in response.headers.get("Content-Type",""): raise RuntimeError("4real response is not HTML")
        rows=source_rows(response.text)
        priced=[r for r in rows if any(v is not None for v in r["prices"].values())]
        if len(priced)<10: raise RuntimeError(f"Only {len(priced)} priced rows for {region_name}; refusing to publish")
        used=set(); matches=0; updates=0
        for row in priced:
            station,method=match_station(region.get("stations",[]),row,used)
            if station is None: continue
            used.add(id(station)); matches+=1
            for typ,val in row["prices"].items():
                if val is None: continue
                item=next((p for p in station.setdefault("prices",[]) if p.get("type")==typ),None)
                if item is None:
                    item={"type":typ,"price":val}
                    station["prices"].append(item)
                old=item.get("price")
                if old is None or abs(float(old)-val)>0.0005:
                    item["price"]=val
                item["stale"]=False
                item["last_confirmed_at"]=now
                updates+=1
            station["updated"]="4real.gr "+now
            station.pop("stale_station",None)
            print(f"MATCH | {region_name} | {method} | {station.get('name')} | {station.get('address')} | "+json.dumps(row["prices"],ensure_ascii=False,sort_keys=True))
        # 4real coverage is partial; unmatched stations remain unchanged.
        region["source"]="4real.gr (verified station matches; partial coverage)"
        print(f"REGION | {region_name} | source_rows={len(priced)} | matched={matches} | price_fields_refreshed={updates} | existing_stations={len(region.get('stations',[]))}")
        total_rows+=len(priced); total_matches+=matches; total_prices+=updates
    if total_matches<8 or total_prices<25:
        raise RuntimeError(f"Unsafe low coverage: matches={total_matches}, price_fields={total_prices}; refusing to publish")
    data["source_name"]="4real.gr"
    data["source_url"]="https://www.4real.gr/FuelPrices/public/times"
    data["fetched_at"]=now
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"SUMMARY | source_rows={total_rows} | matched_stations={total_matches} | refreshed_price_fields={total_prices}")
if __name__=="__main__": main()
