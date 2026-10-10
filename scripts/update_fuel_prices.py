import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.vrisko.gr/times-kafsimon-venzinadika/rethymno/"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()

def parse_price(value):
    match = re.search(r"(\d{1,2}[,.]\d{2,3})\s*€", value)
    return float(match.group(1).replace(",", ".")) if match else None

response = requests.get(URL, headers=HEADERS, timeout=30)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")
items = []
seen = set()

# Each Vrisko station starts at an h2; collect its following siblings until
# the next station heading, which avoids mixing prices between nearby stations.
for heading in soup.find_all("h2"):
    name = clean(heading.get_text(" ", strip=True))
    if not name:
        continue
    chunks = []
    node = heading.find_next_sibling()
    while node is not None and node.name != "h2":
        value = clean(node.get_text(" ", strip=True))
        if value:
            chunks.append(value)
        node = node.find_next_sibling()
    if not chunks:
        continue

    address = chunks[0]
    prices = {}
    for line in chunks:
        lower = line.lower()
        p = parse_price(line)
        if p is None:
            continue
        if ("100" in lower or "ultimate 100" in lower) and ("αμόλυβδη" in lower or "unleaded" in lower or "okt" in lower):
            prices["unleaded100"] = p
        elif "autogas" in lower or "υγραέριο κίνησης" in lower:
            prices["autogas"] = p
        elif "diesel" in lower or "πετρέλαιο κίνησης" in lower or "βιοντήζελ" in lower:
            prices["diesel"] = p
        elif "95" in lower or "αμόλυβδη" in lower or "unleaded" in lower or "d-force unleaded" in lower:
            prices["unleaded95"] = p

    updated_at = ""
    for idx, line in enumerate(chunks):
        if "Τελευταία Ενημέρωση" in line or "Last Update" in line:
            if idx + 1 < len(chunks):
                updated_at = chunks[idx + 1]
            break
    if not prices:
        continue

    item = {"name": name, "address": address, "prices": prices, "updatedAt": updated_at}
    key = (name, address, tuple(sorted(prices.items())), updated_at)
    if key not in seen:
        seen.add(key)
        items.append(item)

if not items:
    raise SystemExit("Vrisko station prices were not parsed; existing data was not overwritten.")

payload = {
    "source": URL,
    "fetchedAt": datetime.now(timezone.utc).isoformat(),
    "items": items,
}
Path("fuel-prices.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Saved {len(items)} fuel station records.")
