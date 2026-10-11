import json, re, time
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://www.vrisko.gr/en/fuel-prices/"
AREAS = [
    ("Ρέθυμνο", "rethymno"),
    ("Ηράκλειο", "iraklio"),
    ("Χανιά", "chania"),
    ("Λασίθι", "lasithi"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TEMO-Crete-FuelPrices/1.0)"}
PRICE_RE = re.compile(r"(?<!\\d)(\\d[,.]\\d{2,3})\\s*€")
DATE_RE = re.compile(r"\\b(?:Last Update|Last updated)\\b\\s*[:]?\\s*(.{0,45})", re.I)

def scrape_area(label, slug):
    url = urljoin(BASE, slug + "/")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # Vrisko pages structure each station as a section/card around a heading.
    stations = []
    seen = set()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        name = " ".join(heading.get_text(" ", strip=True).split())
        if not name or name.lower() in {"information", "fuel prices"}:
            continue
        container = heading
        for _ in range(4):
            if container.parent:
                container = container.parent
        text = " ".join(container.get_text(" ", strip=True).split())
        if not PRICE_RE.search(text) or not re.search(r"Last Update", text, re.I):
            continue
        # Limit text to this station before the next station heading where possible.
        address = ""
        for sib in heading.find_all_next(["p", "div"], limit=8):
            candidate = " ".join(sib.get_text(" ", strip=True).split())
            if candidate and candidate != name and not PRICE_RE.search(candidate):
                address = candidate[:180]
                break
        prices = []
        # Capture only explicit fuel price labels followed by a price; don't infer missing values.
        labels = [
            ("95", r"(?:95(?:\\s*octane|\\s*οκτανίων)?|Unleaded 95)[^€]{0,80}?([0-9]+[,.][0-9]{2,3})\\s*€"),
            ("100", r"(?:100(?:\\s*octane|\\s*οκτ\\.)?|Unleaded 100)[^€]{0,80}?([0-9]+[,.][0-9]{2,3})\\s*€"),
            ("diesel", r"(?:Diesel Best|V-Power Diesel|Diesel Avio|Diesel Evolution|Diesel Κίνησης|Diesel Κινήσεως|Super Diesel)[^€]{0,80}?([0-9]+[,.][0-9]{2,3})\\s*€"),
            ("autogas", r"(?:AutoGas|Autogas|Υγραέριο Κίνησης)[^€]{0,80}?([0-9]+[,.][0-9]{2,3})\\s*€"),
        ]
        for key, pattern in labels:
            m = re.search(pattern, text, re.I)
            prices.append({"type": key, "price": (m.group(1).replace(",", ".") if m else None)})
        date_match = DATE_RE.search(text)
        updated = date_match.group(1).strip() if date_match else None
        signature = (name, address, tuple(x["price"] for x in prices))
        if signature in seen:
            continue
        seen.add(signature)
        stations.append({"name": name, "address": address, "prices": prices, "updated": updated})
    if not stations:
        raise RuntimeError(f"No stations parsed for {label}; refusing to overwrite good data")
    return {"region": label, "source": url, "stations": stations}

result = {"source_name": "Vrisko / Ministry of Development Fuel Prices Observatory",
          "fetched_at": datetime.now(timezone.utc).isoformat(),
          "regions": []}
for label, slug in AREAS:
    result["regions"].append(scrape_area(label, slug))
    time.sleep(1)
with open("fuel-data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("Updated regions:", [(r["region"], len(r["stations"])) for r in result["regions"]])
