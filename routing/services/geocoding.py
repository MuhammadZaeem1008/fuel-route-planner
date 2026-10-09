"""Resolve a user-supplied location to coordinates, avoiding external calls whenever possible.

Accepted inputs, in order of preference:
  1. "lat,lon"                -> parsed directly (0 API calls)
  2. "City, ST"               -> offline Census gazetteer lookup (0 API calls)
  3. anything else (address)  -> Nominatim, restricted to the USA (1 API call, cached)
"""
import re
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from .cities import US_STATES, lookup_city
from .http import get_json

LATLON_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
CITY_STATE_RE = re.compile(r"^\s*([^,]+?)\s*,\s*([A-Za-z]{2})\s*(?:,\s*(?:USA?|United States))?\s*$", re.I)

# Rough bounding boxes: contiguous US, Alaska, Hawaii.
US_BOXES = [(24.3, 49.5, -125.0, -66.8), (51.0, 71.5, -180.0, -129.9), (18.8, 22.4, -160.5, -154.7)]


class LocationError(ValueError):
    pass


@dataclass
class Location:
    query: str
    label: str
    lat: float
    lon: float
    source: str  # "coordinates" | "gazetteer" | "nominatim"


def in_usa(lat, lon):
    return any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOXES)


def geocode(query):
    """Returns (Location, external_calls_made)."""
    query = query.strip()
    if m := LATLON_RE.match(query):
        lat, lon = float(m[1]), float(m[2])
        loc, calls = Location(query, f"{lat:.5f},{lon:.5f}", lat, lon, "coordinates"), 0
    elif m := CITY_STATE_RE.match(query):
        city, state = m[1], m[2].upper()
        if state not in US_STATES:
            raise LocationError(f"'{state}' is not a US state code; start and finish must be within the USA.")
        if c := lookup_city(city, state):
            loc, calls = Location(query, f"{city.title()}, {state}", c[0], c[1], "gazetteer"), 0
        else:
            loc, calls = _nominatim(query)
    else:
        loc, calls = _nominatim(query)

    if not in_usa(loc.lat, loc.lon):
        raise LocationError(f"'{query}' is not within the USA.")
    return loc, calls


def _nominatim(query):
    key = f"geocode:{query.lower()}"
    if cached := cache.get(key):
        return cached, 0
    hits = get_json(
        f"{settings.NOMINATIM_URL}/search",
        {"q": query, "format": "jsonv2", "countrycodes": "us", "limit": 1, "addressdetails": 1},
    )
    if not hits:
        raise LocationError(f"Could not find location '{query}' in the USA.")
    hit = hits[0]
    loc = Location(query, _short_label(hit, query), float(hit["lat"]), float(hit["lon"]), "nominatim")
    cache.set(key, loc)
    return loc, 1


def _short_label(hit, fallback):
    """'Space Needle, Seattle, Washington' rather than Nominatim's full display_name."""
    addr = hit.get("address", {})
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet")
    parts = [hit.get("name"), city, addr.get("state")]
    label = ", ".join(dict.fromkeys(p for p in parts if p))  # dedupe, keep order
    return label or hit.get("display_name") or fallback
