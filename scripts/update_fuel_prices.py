import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.vrisko.gr/en/fuel-prices/rethymno/"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()

def parse_price(value):
    match = re.search(r"(\d{1,2}[,.]\d{2,3})\s*€", value)
    return float(match.group(1).replace(",", ".")) if match else None

response = requests.get(URL, headers=HEADERS, timeout=30)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")
items, seen = [], set()

for heading in soup.find_all("h2"):
    name = clean(heading.get_text(" ", strip=True))
    if not name:
        continue
    container = heading
    block = ""
    # Select the smallest ancestor containing the station's update timestamp.
    for _ in range(7):
        container = container.parent if container else None
        if container is None:
            break
        candidate = clean(container.get_text(" | ", strip=True))
        if re.search(r"(?:Last Update|Τελευταία Ενημέρωση)", candidate, re.I) and len(candidate) < 3000:
            block = candidate
            break
    if not block:
        continue

    parts = [clean(x) for x in container.stripped_strings]
    address = ""
    for part in parts:
        if part and part != name and not parse_price(part) and not re.search(r"(?:Last Update|Τελευταία Ενημέρωση|Diesel|Αμόλυβδη|Unleaded|AutoGas|Υγραέριο|Heating Oil|Θέρμανσης)", part, re.I):
            address = part
            break

    prices = {}
    for part in parts:
        p = parse_price(part)
        if p is None:
            continue
        lower = part.lower()
        if ("100" in lower or "ultimate 100" in lower) and ("αμόλυβδη" in lower or "unleaded" in lower or "okt" in lower):
            prices["unleaded100"] = p
        elif "autogas" in lower or "υγραέριο κίνησης" in lower:
            prices["autogas"] = p
        elif "diesel" in lower or "πετρέλαιο κίνησης" in lower or "βιοντήζελ" in lower:
            prices["diesel"] = p
        elif "95" in lower or "αμόλυβδη" in lower or "unleaded" in lower or "d-force unleaded" in lower:
            prices["unleaded95"] = p

    updated_at = ""
    for idx, part in enumerate(parts):
        if part.lower() in ("last update", "τελευταία ενημέρωση") and idx + 1 < len(parts):
            updated_at = parts[idx + 1]
            break
    if not prices:
        continue

    item = {"name": name, "address": address, "prices": prices, "updatedAt": updated_at}
    key = (name, address, tuple(sorted(prices.items())), updated_at)
    if key not in seen:
        seen.add(key)
        items.append(item)

if not items:
    raise SystemExit("No Vrisko fuel prices parsed; preserving the existing JSON.")

payload = {"source": URL, "fetchedAt": datetime.now(timezone.utc).isoformat(), "items": items}
Path("fuel-prices.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Saved {len(items)} station records.")
