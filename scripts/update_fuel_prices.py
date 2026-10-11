import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

# FuelGR / Deixto data service. Prices are returned in EUR and are queried
# one fuel type at a time. Query only Crete instead of scanning all Greece.
BASE_URL = "https://deixto.gr/fuel/get_data_v4.php"
PARAMS_BASE = {
    "dev": "android.4.0-b2da2cf97330ca3b",
    "b": "0",
    "d": "30",
    "p": "0",
    "dSig": "google/coral/coral:14/UQ1A.240205.004/1709778835:userdebug/release-keys",
    "iLoc": "unknown",
    "apkSig": "UPJ2YQunu9eGXu8a/WOiVNAZlYA=",
}
FUELS = [
    ("1", "95", "Βενζίνη 95"),
    ("2", "100", "Βενζίνη 98–100"),
    ("4", "diesel", "Πετρέλαιο κίνησης"),
    ("6", "autogas", "Υγραέριο"),
]
# Center plus surrounding points improve coverage; each query covers a 30 km radius.
REGIONS = [
    {
        "region": "Ρέθυμνο",
        "points": [(35.3656, 24.4820), (35.48, 24.45), (35.25, 24.55), (35.36, 24.25)],
        "bounds": (35.10, 35.60, 24.00, 24.90),
    },
    {
        "region": "Ηράκλειο",
        "points": [(35.3387, 25.1442), (35.45, 25.15), (35.20, 25.35), (35.15, 24.90)],
        "bounds": (34.90, 35.60, 24.70, 26.00),
    },
    {
        "region": "Χανιά",
        "points": [(35.5138, 24.0180), (35.55, 23.75), (35.35, 23.90), (35.40, 24.20)],
        "bounds": (35.15, 35.75, 23.30, 24.40),
    },
    {
        "region": "Λασίθι",
        "points": [(35.1900, 25.7150), (35.10, 25.95), (35.25, 26.10), (35.05, 25.50)],
        "bounds": (34.80, 35.50, 25.35, 26.50),
    },
]
HEADERS = {
    "Accept": "application/xml,text/xml,*/*",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13)",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def tag_text(node, name):
    child = node.find(name)
    if child is None:
        return ""
    return "".join(child.itertext()).strip()


def parse_response(xml_text, fuel_key):
    """Return station records from the FuelGR XML; never invent missing prices."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # The upstream occasionally wraps the XML in a declaration/extra text.
        start = xml_text.find("<")
        end = xml_text.rfind(">")
        if start < 0 or end <= start:
            return []
        try:
            root = ET.fromstring(xml_text[start:end + 1])
        except ET.ParseError:
            return []

    records = []
    for node in root.iter():
        if node.tag.split("}")[-1] != "gs":
            continue
        sid = (node.attrib.get("id") or "").strip()
        lat_s, lon_s = tag_text(node, "lt"), tag_text(node, "lg")
        try:
            lat, lon = float(lat_s), float(lon_s)
        except (TypeError, ValueError):
            continue
        if not (34.7 <= lat <= 35.9 and 22.8 <= lon <= 27.0):
            continue

        brand = tag_text(node, "br")
        address = tag_text(node, "ad")
        # The response may include more than one <ft>; use the first valid price.
        price = None
        for child in node.iter():
            if child.tag.split("}")[-1] != "ft":
                continue
            raw = child.attrib.get("pr", "")
            try:
                candidate = float(raw.replace(",", "."))
            except (TypeError, ValueError):
                continue
            if 0.5 < candidate < 5.0:
                price = round(candidate, 3)
                break
        records.append({
            "id": sid,
            "name": brand,
            "address": address,
            "lat": lat,
            "lon": lon,
            "price": price,
            "fuel": fuel_key,
            "county": node.attrib.get("cnt", ""),
        })
    return records


def fetch_point(lat, lon, fuel_code, fuel_key):
    params = dict(PARAMS_BASE, lat=lat, **{"long": lon}, f=fuel_code)
    response = SESSION.get(BASE_URL, params=params, timeout=25)
    response.raise_for_status()
    return parse_response(response.text, fuel_key)


def in_bounds(station, bounds):
    south, north, west, east = bounds
    return south <= station["lat"] <= north and west <= station["lon"] <= east


def main():
    result = {
        "source_name": "FuelGR / Deixto",
        "source_url": "https://deixto.gr/",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "regions": [],
    }
    total = 0

    for region in REGIONS:
        # Keyed by source station ID; merge fuel prices across separate requests.
        stations = {}
        for fuel_code, fuel_key, _label in FUELS:
            for lat, lon in region["points"]:
                try:
                    batch = fetch_point(lat, lon, fuel_code, fuel_key)
                    for item in batch:
                        if not in_bounds(item, region["bounds"]):
                            continue
                        # A missing brand is not replaced with a fabricated station name.
                        if not item["name"]:
                            continue
                        sid = item["id"] or f'{item["name"]}|{item["lat"]:.5f}|{item["lon"]:.5f}'
                        if sid not in stations:
                            stations[sid] = {
                                "name": item["name"],
                                "address": item["address"],
                                "latitude": item["lat"],
                                "longitude": item["lon"],
                                "prices": {},
                                "updated": "ონლაინ წყაროდან მიღებულია " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                            }
                        if not stations[sid]["address"] and item["address"]:
                            stations[sid]["address"] = item["address"]
                        if item["price"] is not None:
                            stations[sid]["prices"][fuel_key] = item["price"]
                except (requests.RequestException, ValueError) as exc:
                    print(f'Warning: {region["region"]} {fuel_key} at {lat},{lon}: {exc}')
                time.sleep(0.25)

        station_list = []
        for station in stations.values():
            prices = [
                {"type": fuel_key, "price": station["prices"][fuel_key]}
                for _code, fuel_key, _label in FUELS
                if fuel_key in station["prices"]
            ]
            if not prices:
                continue
            station["prices"] = prices
            station_list.append(station)
        station_list.sort(key=lambda s: (s["name"].casefold(), s["address"].casefold()))
        if not station_list:
            raise RuntimeError(
                f'No stations with real prices were received for {region["region"]}; '
                "refusing to publish empty or fabricated data."
            )
        result["regions"].append({
            "region": region["region"],
            "source": "FuelGR / Deixto",
            "stations": station_list,
        })
        total += len(station_list)
        print(f'{region["region"]}: {len(station_list)} stations')

    if total < 5:
        raise RuntimeError(f"Only {total} stations returned; refusing to publish incomplete data.")

    # Write only after all four regions returned valid real data.
    target = Path("fuel-data.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {total} stations across {len(result['regions'])} regions.")


if __name__ == "__main__":
    main()
