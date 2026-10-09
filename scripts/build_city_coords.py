"""One-off: build data/us_cities.csv (state, name, lat, lon) from US Census Gazetteer files.

Usage: python scripts/build_city_coords.py <place_gazetteer.txt> <cousub_gazetteer.txt> <out.csv>
Gazetteer: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from routing.services.cities import normalize_city as normalize  # noqa: E402

SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|metropolitan government|unified government|"
    r"urban county|city|town|township|village|borough|CDP|municipality|plantation|CCD|UT|"
    r"comunidad|zona urbana|charter township|gore|grant|location|purchase|reservation|precinct|district)"
    r"(\s*\(.*\))?$",
    re.I,
)


def clean(raw):
    raw = re.sub(r"\s*\(.*\)$", "", raw.strip())
    raw = SUFFIX.sub("", raw).strip()
    # Consolidated city-counties: "Nashville-Davidson metropolitan government" -> "Nashville"
    return CONSOLIDATED.get(raw, raw)


CONSOLIDATED = {
    "Nashville-Davidson": "Nashville",
    "Lexington-Fayette": "Lexington",
    "Macon-Bibb County": "Macon",
    "Boise City": "Boise",
    "Louisville/Jefferson County": "Louisville",
    "Athens-Clarke County": "Athens",
    "Augusta-Richmond County": "Augusta",
    "Indianapolis city": "Indianapolis",
}


def main(place_path, cousub_path, out_path):
    coords = {}
    # County subdivisions first so incorporated places override them.
    for path in (cousub_path, place_path):
        with open(path, encoding="latin-1") as f:
            reader = csv.DictReader(f, delimiter="\t")
            reader.fieldnames = [h.strip() for h in reader.fieldnames]
            for row in reader:
                key = (row["USPS"], normalize(clean(row["NAME"])))
                coords[key] = (round(float(row["INTPTLAT"]), 5), round(float(row["INTPTLONG"].strip()), 5))
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "name", "lat", "lon"])
        for (state, name), (lat, lon) in sorted(coords.items()):
            w.writerow([state, name, lat, lon])
    print(f"wrote {len(coords)} cities")


if __name__ == "__main__":
    main(*sys.argv[1:4])
