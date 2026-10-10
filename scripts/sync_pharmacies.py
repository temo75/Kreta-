import json, re, urllib.request
from html.parser import HTMLParser
from pathlib import Path

CATALOG_URLS = [
    "https://www.rethymno.gr/guide/pharmacies",
    "https://www.dreth.gr/%CF%86%CE%B1%CF%81%CE%BC%CE%B1%CE%BA%CE%B5%CE%AF%CE%B1/",
]
DUTY_URLS = [
    "https://www.rethymno.gr/information-services/pharmacies/pharmacies.html",
    "https://rethymno.efhmeries.gr/Nearby/",
]
DUTY_URL = DUTY_URLS[0]
DUTY_SOURCE_USED = DUTY_URL

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        s=" ".join(data.split())
        if s: self.parts.append(s)

def fetch_lines(url):
    import time
    last_error = None
    for attempt in range(1, 5):
        try:
            req=urllib.request.Request(url, headers={
                "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language":"el,en-US;q=0.9,en;q=0.8",
                "Connection":"close"
            })
            with urllib.request.urlopen(req, timeout=45) as response:
                html=response.read().decode("utf-8", "replace")
            parser=TextParser(); parser.feed(html)
            if len(parser.parts) < 10:
                raise RuntimeError(f"Unexpectedly short response from {url}")
            return parser.parts
        except Exception as exc:
            last_error = exc
            print(f"Fetch attempt {attempt}/4 failed for {url}: {exc}", flush=True)
            if attempt < 4:
                time.sleep(attempt * 5)
    raise RuntimeError(f"Could not fetch {url} after 4 attempts: {last_error}")

def phone_numbers(text):
    return re.findall(r'(?<!\d)(?:\+30\s*)?(?:\d[\s.-]?){9,10}\d(?!\d)', text)

def clean_phone(p):
    digits=re.sub(r"\D","",p)
    if digits.startswith("30") and len(digits)>10: digits=digits[2:]
    return digits

def scrape_catalog():
    parts = None
    used_url = None
    errors = []
    for url in CATALOG_URLS:
        try:
            candidate = fetch_lines(url)
            if len(candidate) >= 20:
                parts = candidate
                used_url = url
                break
            errors.append(f"{url}: response too short")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if parts is None:
        raise RuntimeError("Could not fetch any official municipality pharmacy catalog: " + " | ".join(errors))
    rows=[]
    i=0
    while i < len(parts):
        line=parts[i]
        if "|" in line and not any(x in line.lower() for x in ["http","@"]):
            name,address=[x.strip() for x in line.split("|",1)]
            if name and address and len(name)<100:
                extras=[]; phones=[]
                j=i+1
                while j < min(i+5,len(parts)):
                    t=parts[j]
                    if "|" in t: break
                    nums=phone_numbers(t)
                    if nums:
                        phones.extend(clean_phone(n) for n in nums); break
                    if not any(k in t.lower() for k in ["αρχική","επιχειρήσεις","φαρμακεία","τηλέφωνο:","home"]):
                        extras.append(t)
                    j+=1
                address=" ".join([address]+extras).strip()
                rows.append({"name":name,"address":address,"phones":list(dict.fromkeys(phones))})
        i+=1
    unique={}
    for p in rows:
        key=(p["name"].casefold(),p["address"].casefold())
        if key not in unique: unique[key]=p
    result = list(unique.values())
    if len(result) < 20:
        raise RuntimeError(f"Catalog parser found only {len(result)} pharmacies at {used_url}")
    print(f"Catalog source: {used_url}; parsed {len(result)} pharmacies", flush=True)
    return result

def scrape_duty():
    global DUTY_SOURCE_USED
    parts=None
    errors=[]
    used_url=None
    for url in DUTY_URLS:
        try:
            candidate=fetch_lines(url)
            if len(candidate) >= 10:
                parts=candidate
                used_url=url
                DUTY_SOURCE_USED=url
                break
            errors.append(f"{url}: response too short")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if parts is None:
        raise RuntimeError("Could not fetch any duty schedule source: " + " | ".join(errors))
    records=[]
    current_date=None; period=None; i=0
    date_re=re.compile(r"(?:Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s+\d{1,2}\s+\w+\s+\d{4}",re.I)
    while i < len(parts):
        t=parts[i]
        if date_re.search(t):
            current_date=t
            records.append({"dateLabel":t,"date":None,"day":[],"night":[]})
            period=None
        elif records and ("08:00" in t and "21:00" in t):
            period="day"
        elif records and ("21:00" in t and "08:00" in t):
            period="night"
        elif records and period and i+1 < len(parts):
            # A pharmacy record starts with a Greek name followed by its address and phone.
            if "Φαρμακείο" not in t and not t.startswith("Τηλέφωνο"):
                nums=phone_numbers(t)
                if not nums and len(t)<100 and not any(x in t for x in ["Δείτε","www.","Φαρμακείο Διεύθυνση"]):
                    name=t
                    address=""
                    phones=[]
                    for j in range(i+1,min(i+5,len(parts))):
                        line=parts[j]
                        if date_re.search(line) or ("08:00" in line and "21:00" in line) or ("21:00" in line and "08:00" in line): break
                        found=phone_numbers(line)
                        if found:
                            phones.extend(clean_phone(n) for n in found); break
                        if not line.startswith("Τηλέφωνο") and len(line)<180:
                            address=(address+" "+line).strip()
                    if phones and name and address:
                        item={"name":name,"address":address,"phones":list(dict.fromkeys(phones))}
                        if not any(p["name"]==name and p["address"]==address for p in records[-1][period]):
                            records[-1][period].append(item)
        i+=1
    # Convert Greek date labels to ISO dates using a small Greek month map.
    months={"Ιανουαρίου":"01","Φεβρουαρίου":"02","Μαρτίου":"03","Απριλίου":"04","Μαΐου":"05","Ιουνίου":"06","Ιουλίου":"07","Αυγούστου":"08","Σεπτεμβρίου":"09","Οκτωβρίου":"10","Νοεμβρίου":"11","Δεκεμβρίου":"12"}
    for r in records:
        m=re.search(r"(\d{1,2})\s+(\S+)\s+(\d{4})",r["dateLabel"])
        if m and m.group(2) in months:
            r["date"]=f'{m.group(3)}-{months[m.group(2)]}-{int(m.group(1)):02d}'
    result=[r for r in records if r["date"] and (r["day"] or r["night"])]
    print(f"Duty source: {used_url}; parsed {len(result)} duty dates", flush=True)
    return result

def main():
    catalog=scrape_catalog()
    if len(catalog)<20:
        raise RuntimeError(f"Catalog parse returned only {len(catalog)} pharmacies; refusing to overwrite good data")
    now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    Path("pharmacies.json").write_text(json.dumps({"updatedAt":now,"source":"municipality official catalog (primary/fallback)","pharmacies":catalog},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Saved {len(catalog)} pharmacies", flush=True)
    try:
        duty=scrape_duty()
        if not duty:
            raise RuntimeError("No duty schedules parsed")
        Path("duty.json").write_text(json.dumps({"updatedAt":now,"source":DUTY_SOURCE_USED,"schedule":duty},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"Saved {len(duty)} duty dates", flush=True)
    except Exception as exc:
        print(f"WARNING: duty schedule refresh failed; preserving any existing duty.json: {exc}", flush=True)
        if not Path("duty.json").exists():
            print("WARNING: no previous duty.json exists; website fallback data will be used", flush=True)

if __name__=="__main__": main()
