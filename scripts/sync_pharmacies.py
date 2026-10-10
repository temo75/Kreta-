import json, re, urllib.request
from html.parser import HTMLParser
from pathlib import Path

CATALOG_URL = "https://www.rethymno.gr/guide/pharmacies"
DUTY_URL = "https://www.rethymno.gr/information-services/pharmacies/pharmacies.html"

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        s=" ".join(data.split())
        if s: self.parts.append(s)

def fetch_lines(url):
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 TEMO-pharmacy-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        html=response.read().decode("utf-8", "replace")
    parser=TextParser(); parser.feed(html)
    return parser.parts

def phone_numbers(text):
    return re.findall(r'(?<!\d)(?:\+30\s*)?(?:\d[\s.-]?){9,10}\d(?!\d)', text)

def clean_phone(p):
    digits=re.sub(r"\D","",p)
    if digits.startswith("30") and len(digits)>10: digits=digits[2:]
    return digits

def scrape_catalog():
    parts=fetch_lines(CATALOG_URL)
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
    return list(unique.values())

def scrape_duty():
    parts=fetch_lines(DUTY_URL)
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
    return [r for r in records if r["date"] and (r["day"] or r["night"])]

def main():
    catalog=scrape_catalog()
    duty=scrape_duty()
    if len(catalog)<20: raise RuntimeError(f"Catalog parse returned only {len(catalog)} pharmacies; refusing to overwrite good data")
    if not duty: raise RuntimeError("No duty schedules parsed; refusing to overwrite good data")
    Path("pharmacies.json").write_text(json.dumps({"updatedAt":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"source":CATALOG_URL,"pharmacies":catalog},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path("duty.json").write_text(json.dumps({"updatedAt":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"source":DUTY_URL,"schedule":duty},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Saved {len(catalog)} pharmacies and {len(duty)} duty dates")

if __name__=="__main__": main()
