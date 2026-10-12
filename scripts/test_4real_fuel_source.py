#!/usr/bin/env python3
"""Read-only smoke test for 4real.gr fuel-price pages. Does not change fuel-data.json."""
import re
import sys
from html.parser import HTMLParser

import requests

REGIONS = {
    "Ρέθυμνο": "rethymno",
    "Ηράκλειο": "iraklio",
    "Χανιά": "chania",
    "Λασίθι": "lasithi",
}
FUEL_PATHS = {
    "95": "benzini-amolyvdh-95",
    "100": "benzini-amolyvdh-100",
    "diesel": "petrelaio-kinhshs",
    "autogas": "ygraerio-kinhshs",
}
BASE = "https://www.4real.gr/FuelPrices/public/times"


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.table, self.row, self.cell = [], None, None, None
        self.in_cell = False
        self.img_alt = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": "", "tag": tag, "alt": []}
            self.in_cell = True
        elif tag == "img" and self.cell is not None:
            alt = attrs.get("alt", "").strip()
            if alt:
                self.cell["alt"].append(alt)

    def handle_data(self, data):
        if self.in_cell and self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.cell["text"] = re.sub(r"\s+", " ", self.cell["text"]).strip()
            self.row.append(self.cell)
            self.cell, self.in_cell = None, False
        elif tag == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_price(text):
    text = text.strip().replace(",", ".")
    if not text or text in ("-", "—", "N/A"):
        return None
    m = re.search(r"(?<!\d)(\d[.]?\d{2,3})(?!\d)", text)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    return round(value, 3) if 0.5 < value < 5 else None


def parse_page(html):
    parser = TableParser()
    parser.feed(html)
    found = {}
    for table in parser.tables:
        for row in table:
            texts = [c["text"] for c in row]
            if len(row) < 5:
                continue
            # 4real fuel tables place station name/logo and location first,
            # then 95, 100, super, diesel, heating oil and LPG columns.
            brand = next((a for c in row for a in c["alt"]), "")
            location = texts[1] if len(texts) > 1 else ""
            if not brand or not location:
                continue
            values = [parse_price(c) for c in texts[2:8]]
            if not any(v is not None for v in values):
                continue
            key = (brand.casefold().strip(), re.sub(r"\s+", " ", location.casefold()).strip())
            found[key] = {
                "brand": brand, "location": location,
                "95": values[0] if len(values) > 0 else None,
                "100": values[1] if len(values) > 1 else None,
                "super": values[2] if len(values) > 2 else None,
                "diesel": values[3] if len(values) > 3 else None,
                "heating_oil": values[4] if len(values) > 4 else None,
                "autogas": values[5] if len(values) > 5 else None,
            }
    return list(found.values())


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "TEMO-Kreta-fuel-source-check/1.0"})
    failures, total = [], 0
    for region, slug in REGIONS.items():
        region_count = 0
        for fuel, path in FUEL_PATHS.items():
            url = f"{BASE}/{slug}/{path}"
            try:
                response = session.get(url, timeout=25)
                response.raise_for_status()
                if "text/html" not in response.headers.get("Content-Type", ""):
                    raise RuntimeError("response is not HTML")
                records = parse_page(response.text)
                if not records:
                    raise RuntimeError("no station prices parsed")
                region_count = max(region_count, len(records))
                print(f"OK | {region} | {fuel} | {len(records)} stations | HTTP {response.status_code}")
                for record in records[:2]:
                    print(f"  {record['brand']} | {record['location']} | 95={record['95']} | 100={record['100']} | diesel={record['diesel']} | LPG={record['autogas']}")
            except Exception as exc:
                failures.append(f"{region}/{fuel}: {exc}")
                print(f"FAIL | {region} | {fuel} | {exc}")
        total += region_count
    print(f"SUMMARY | regions={len(REGIONS)} | approximate_station_rows={total} | failures={len(failures)}")
    if failures:
        print("\\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
