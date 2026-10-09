"""Driving route from the public OSRM server: exactly one HTTP call per route."""
from dataclasses import dataclass

from django.conf import settings

from .geo import METERS_PER_MILE, decode_polyline
from .http import ExternalServiceError, get_json


@dataclass
class Route:
    distance_miles: float
    duration_hours: float
    coords: list  # [(lat, lon)]


def get_route(start, finish):
    url = (
        f"{settings.OSRM_URL}/route/v1/driving/"
        f"{start.lon:.6f},{start.lat:.6f};{finish.lon:.6f},{finish.lat:.6f}"
    )
    data = get_json(url, {"overview": "full", "geometries": "polyline", "steps": "false"})
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ExternalServiceError(f"No drivable route found ({data.get('code')}: {data.get('message', '')}).")
    route = data["routes"][0]
    return Route(
        distance_miles=route["distance"] / METERS_PER_MILE,
        duration_hours=route["duration"] / 3600,
        coords=decode_polyline(route["geometry"]),
    )
