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
        "bounds": (35.1094, 35.4159, 24.3240, 24.8932),
    },
    {
        "region": "Ηράκλειο",
        "points": [(35.3387, 25.1442), (35.45, 25.15), (35.20, 25.35), (35.15, 24.90)],
        "bounds": (34.9537, 35.4090, 24.7595, 25.4890),
    },
    {
        "region": "Χανιά",
        "points": [(35.5138, 24.0180), (35.55, 23.75), (35.35, 23.90), (35.40, 24.20)],
        "bounds": (35.1813, 35.5806, 23.5943, 24.3021),
    },
    {
        "region": "Λασίθι",
        "points": [(35.1900, 25.7150), (35.10, 25.95), (35.25, 26.10), (35.05, 25.50)],
        "bounds": (34.9936, 35.3004, 25.4574, 26.2610),
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


def is_older_than_24h(value):
    """Treat a price as stale based on its confirmation time, not file-fetch time."""
    if not value:
        return True

    # Source values may be ISO timestamps or a timestamp embedded in a label.
    match = re.search(
        r"\\d{4}-\\d{2}-\\d{2}(?:[ T]\\d{2}:\\d{2}(?::\\d{2}(?:\\.\\d+)?)?(?:Z| UTC|[+-]\\d{2}:\\d{2})?)?",
        str(value),
    )
    if not match:
        return True

    raw_stamp = match.group(0).replace(" UTC", "+00:00").replace("Z", "+00:00")
    if len(raw_stamp) == 10:
        raw_stamp += "T00:00:00+00:00"
    try:
        stamp = datetime.fromisoformat(raw_stamp)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() > 24 * 60 * 60

def main():
    result = {
        "source_name": "FuelGR / DEiXTo (third-party data feed)",
        "official_source_url": "https://www.fuelprices.gr/CheckPrices",
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
            "source": "FuelGR / DEiXTo (third-party data feed)",
            "stations": station_list,
        })
        total += len(station_list)
        print(f'{region["region"]}: {len(station_list)} stations')

    if total < 5:
        raise RuntimeError(f"Only {total} stations returned; refusing to publish incomplete data.")

    # Preserve previously published station prices when the source temporarily omits them.
    # New prices are stamped individually; carried-over prices are explicitly marked stale.
    target = Path("fuel-data.json")
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}

        previous_regions = {r.get("region"): r for r in previous.get("regions", [])}
        for region in result["regions"]:
            old_region = previous_regions.get(region["region"], {})
            old_stations = old_region.get("stations", [])
            old_by_key = {
                (str(s.get("name", "")).strip().casefold(), str(s.get("address", "")).strip().casefold()): s
                for s in old_stations
            }
            new_keys = set()
            for station in region["stations"]:
                key = (str(station.get("name", "")).strip().casefold(), str(station.get("address", "")).strip().casefold())
                new_keys.add(key)
                old = old_by_key.get(key)
                old_prices = {p.get("type"): p for p in (old or {}).get("prices", [])}
                new_prices = {p.get("type"): p for p in station.get("prices", [])}
                for fuel_key, old_price in old_prices.items():
                    if fuel_key not in new_prices:
                        carried = dict(old_price)
                        carried["stale"] = True
                        carried["last_confirmed_at"] = old_price.get("last_confirmed_at") or old.get("updated") or previous.get("fetched_at")
                        station["prices"].append(carried)
                    else:
                        # A successful poll does not mean the station price itself was updated.
                        # Keep the last-confirmed timestamp when the numeric value is unchanged,
                        # and mark that price stale after 24 hours instead of pretending it is fresh.
                        if old_price and str(old_price.get("price")) == str(new_prices[fuel_key].get("price")):
                            confirmed = old_price.get("last_confirmed_at") or old.get("updated") or previous.get("fetched_at")
                        else:
                            confirmed = result["fetched_at"]
                        new_prices[fuel_key]["last_confirmed_at"] = confirmed
                        new_prices[fuel_key]["stale"] = is_older_than_24h(confirmed)
                # Preserve previous station coordinates if source values are invalid/missing.
                if old and (not station.get("latitude") or not station.get("longitude")):
                    station["latitude"] = old.get("latitude", station.get("latitude"))
                    station["longitude"] = old.get("longitude", station.get("longitude"))

            # Keep stations omitted by a partial upstream response, with old prices clearly stale.
            for old in old_stations:
                key = (str(old.get("name", "")).strip().casefold(), str(old.get("address", "")).strip().casefold())
                if key in new_keys or not old.get("prices"):
                    continue
                carried_station = dict(old)
                carried_station["prices"] = []
                for price in old.get("prices", []):
                    carried = dict(price)
                    carried["stale"] = True
                    carried["last_confirmed_at"] = price.get("last_confirmed_at") or old.get("updated") or previous.get("fetched_at")
                    carried_station["prices"].append(carried)
                carried_station["stale_station"] = True
                region["stations"].append(carried_station)

    # Write only after all four regions returned valid real data.
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published {total} stations across {len(result['regions'])} regions.")


if __name__ == "__main__":
    main()
