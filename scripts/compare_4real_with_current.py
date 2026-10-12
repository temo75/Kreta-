#!/usr/bin/env python3
"""Read-only comparison of 4real fuel prices against current data by station phone."""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path
import requests

REGIONS={"Ρέθυμνο":"rethymno","Ηράκλειο":"iraklio","Χανιά":"chania","Λασίθι":"lasithi"}
BASE="https://www.4real.gr/FuelPrices/public/times/{}/brand"

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.tables=[]; self.table=None; self.row=None; self.cell=None; self.inside=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="table": self.table=[]
        elif tag=="tr" and self.table is not None: self.row=[]
        elif tag in ("td","th") and self.row is not None: self.cell={"text":"","alt":[]}; self.inside=True
        elif tag=="img" and self.cell is not None and a.get("alt"): self.cell["alt"].append(a["alt"].strip())
    def handle_data(self,data):
        if self.inside and self.cell is not None: self.cell["text"]+=data
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None and self.row is not None:
            self.cell["text"]=re.sub(r"\s+"," ",self.cell["text"]).strip(); self.row.append(self.cell); self.cell=None; self.inside=False
        elif tag=="tr" and self.row is not None and self.table is not None:
            if self.row: self.table.append(self.row)
            self.row=None
        elif tag=="table" and self.table is not None: self.tables.append(self.table); self.table=None

def digits(s): return re.sub(r"\D","",s or "")
def parse_price(s):
    m=re.search(r"(?<!\d)(\d[,.]\d{2,3})(?!\d)",s or "")
    if not m: return None
    try: v=float(m.group(1).replace(",","."))
    except ValueError: return None
    return round(v,3) if 0.5<v<5 else None

def read_source(html):
    p=Parser(); p.feed(html); out=[]
    for table in p.tables:
        for row in table:
            if len(row)<8: continue
            cells=[c["text"] for c in row]
            address=cells[1] if len(cells)>1 else ""
            phone=digits(address)
            if len(phone)<10: continue
            prices=[parse_price(x) for x in cells[2:8]]
            out.append({"address":address,"phone":phone[-10:],"prices":{"95":prices[0],"100":prices[1],"super":prices[2],"diesel":prices[3],"heating_oil":prices[4],"autogas":prices[5]}})
    return out

def main():
    current=json.loads(Path("fuel-data.json").read_text(encoding="utf-8"))
    total=0; matched=0; differences=0; errors=0
    session=requests.Session(); session.headers.update({"User-Agent":"Mozilla/5.0 TEMO-Kreta-read-only-comparison/1.0"})
    for region,slug in REGIONS.items():
        try:
            response=session.get(BASE.format(slug),timeout=30); response.raise_for_status()
            rows=read_source(response.text)
        except Exception as exc:
            print(f"ERROR | {region} | {exc}"); errors+=1; continue
        current_region=next((x for x in current.get("regions",[]) if x.get("region")==region),{})
        stations=current_region.get("stations",[])
        index={}
        for st in stations:
            all_digits=digits(st.get("address",""))
            if len(all_digits)>=10: index.setdefault(all_digits[-10:],[]).append(st)
        region_matches=0; region_diffs=0
        for row in rows:
            candidates=index.get(row["phone"],[])
            if len(candidates)!=1: continue
            station=candidates[0]; region_matches+=1; matched+=1
            old={x.get("type"):x.get("price") for x in station.get("prices",[])}
            changed=[]
            for typ in ("95","100","diesel","autogas"):
                new=row["prices"].get(typ)
                if new is not None and old.get(typ) is not None and abs(float(old[typ])-new)>0.0005:
                    changed.append(f"{typ}: {old[typ]} -> {new}")
            print(f"MATCH | {region} | phone={row['phone']} | {station.get('name')} | {row['address']} | prices={json.dumps(row['prices'],ensure_ascii=False,sort_keys=True)}")
            if changed:
                region_diffs+=1; differences+=1
                print(f"DIFF | {region} | {station.get('name')} | {row['address']} | "+"; ".join(changed))
        total+=len(rows)
        print(f"REGION | {region} | source_stations={len(rows)} | exact_phone_matches={region_matches} | stations_with_differences={region_diffs}")
    print(f"SUMMARY | source_rows={total} | exact_phone_matches={matched} | stations_with_differences={differences} | fetch_errors={errors}")
    if matched==0 or errors: sys.exit(1)

if __name__=="__main__": main()
