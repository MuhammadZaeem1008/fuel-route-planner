"""One-off: geocode truck-stop cities missing from data/us_cities.csv via Nominatim (1 req/s).

Appends results to data/city_overrides.csv so the app never geocodes stations at request time.
Usage: python scripts/geocode_missing_cities.py
"""
import csv
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from routing.services.cities import US_STATES, normalize_city as normalize  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    known = set()
    for name in ("us_cities.csv", "city_overrides.csv"):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            known |= {(r["state"], r["name"]) for r in csv.DictReader(open(path))}

    missing = {}
    for r in csv.DictReader(open(os.path.join(DATA, "fuel_prices.csv"))):
        state, city = r["State"].strip(), r["City"].strip()
        key = (state, normalize(city))
        if state in US_STATES and key not in known:
            missing[key] = city

    out_path = os.path.join(DATA, "city_overrides.csv")
    new_file = not os.path.exists(out_path)
    with open(out_path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["state", "name", "lat", "lon"])
        for (state, key), city in sorted(missing.items()):
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"city": city, "state": state, "country": "USA", "format": "json", "limit": 1},
                headers={"User-Agent": "fuel-route-planner-assessment/1.0"},
                timeout=15,
            )
            hits = resp.json()
            if hits:
                w.writerow([state, key, round(float(hits[0]["lat"]), 5), round(float(hits[0]["lon"]), 5)])
                print("ok  ", city, state)
            else:
                print("MISS", city, state)
            time.sleep(1.1)


if __name__ == "__main__":
    main()
