import json, re
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://www.vrisko.gr/times-kafsimon-venzinadika/rethymno/"
res = requests.get(URL, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
res.raise_for_status()
soup = BeautifulSoup(res.text, "html.parser")
text = soup.get_text(" ", strip=True)
# Save only clearly matched station records; if Vrisko changes layout, fail safely.
items = []
for node in soup.find_all(["article", "li", "div"]):
    block = re.sub(r"\s+", " ", node.get_text(" | ", strip=True))
    if len(block) > 1800 or len(block) < 30:
        continue
    if not re.search(r"(?:Last Update|Τελευταία Ενημέρωση|Ενημερώθηκε)", block, re.I):
        continue
    prices = {}
    for key, pattern in [
        ("unleaded95", r"(?:95|Αμόλυβδη 95)[^|]{0,100}?([12][,.]\d{2,3})\s*€?"),
        ("unleaded100", r"(?:100|Αμόλυβδη 100)[^|]{0,100}?([12][,.]\d{2,3})\s*€?"),
        ("diesel", r"(?:Diesel|Πετρέλαιο Κίνησης)[^|]{0,100}?([12][,.]\d{2,3})\s*€?"),
        ("autogas", r"(?:Autogas|Υγραέριο Κίνησης)[^|]{0,100}?([01][,.]\d{2,3})\s*€?"),
    ]:
        m = re.search(pattern, block, re.I)
        if m:
            prices[key] = float(m.group(1).replace(",", "."))
    if not prices:
        continue
    name = block.split("|")[0].strip()
    if len(name) < 3:
        continue
    item = {"name": name, "prices": prices}
    if item not in items:
        items.append(item)

if not items:
    raise SystemExit("Vrisko layout did not yield verified fuel prices; keeping existing data.")
Path("fuel-prices.json").write_text(json.dumps({
    "source": URL,
    "fetchedAt": datetime.now(timezone.utc).isoformat(),
    "items": items
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Saved {len(items)} records")
