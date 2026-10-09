"""Offline US city -> coordinate lookup built from US Census Gazetteer data (see scripts/)."""
import csv
import re
from functools import lru_cache

from django.conf import settings

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
}


def normalize_city(name):
    """Canonical city key: lowercase, 'saint'->'st', no punctuation or spaces ('Mc Calla' == 'McCalla')."""
    name = name.lower()
    name = re.sub(r"\bsainte\b", "ste", name)
    name = re.sub(r"\bsaint\b", "st", name)
    return re.sub(r"[^a-z0-9]", "", name)


@lru_cache(maxsize=1)
def city_table():
    """{(STATE, normalized_city): (lat, lon)} from data/us_cities.csv + data/city_overrides.csv."""
    table = {}
    for filename in ("us_cities.csv", "city_overrides.csv"):
        path = settings.DATA_DIR / filename
        if not path.exists():
            continue
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                table[(row["state"], row["name"])] = (float(row["lat"]), float(row["lon"]))
    return table


def lookup_city(city, state):
    return city_table().get((state.strip().upper(), normalize_city(city)))
