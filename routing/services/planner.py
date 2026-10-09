"""Orchestrates geocoding -> one routing call -> station matching -> fuel optimisation."""
import hashlib
import time

from django.conf import settings
from django.core.cache import cache

from .directions import get_route
from .geo import resample, simplify
from .geocoding import geocode
from .optimizer import plan_fuel_stops
from .stations import get_station_index

CACHE_VERSION = 2


def _cache_key(start, finish):
    raw = f"{start.lat:.5f},{start.lon:.5f}|{finish.lat:.5f},{finish.lon:.5f}"
    return f"route-plan:v{CACHE_VERSION}:{hashlib.sha1(raw.encode()).hexdigest()}"


def plan_trip(start_query, finish_query):
    t0 = time.perf_counter()

    start, start_calls = geocode(start_query)
    finish, finish_calls = geocode(finish_query)
    external_calls = start_calls + finish_calls

    key = _cache_key(start, finish)
    result = cache.get(key)
    if result is None:
        route = get_route(start, finish)
        external_calls += 1
        result = _build_plan(start, finish, route)
        cache.set(key, result)
        cached = False
    else:
        cached = True

    return {
        **result,
        "meta": {
            "external_api_calls": external_calls,
            "cached": cached,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    }


def _build_plan(start, finish, route):
    points = resample(route.coords, step_miles=1.0)
    # Scale our haversine mileage onto OSRM's (road-accurate) distance so positions line up.
    scale = route.distance_miles / points[-1][2] if points and points[-1][2] else 1.0
    points = [(lat, lon, mile * scale) for lat, lon, mile in points]

    candidates = get_station_index().stations_along(points, settings.CORRIDOR_MILES)
    plan = plan_fuel_stops(
        candidates,
        total_miles=route.distance_miles,
        range_miles=settings.VEHICLE_RANGE_MILES,
        mpg=settings.VEHICLE_MPG,
    )

    stops = [
        {
            "stop_number": n,
            "opis_id": s.station.opis_id,
            "name": s.station.name,
            "address": s.station.address,
            "city": s.station.city,
            "state": s.station.state,
            "latitude": s.station.lat,
            "longitude": s.station.lon,
            "price_per_gallon": round(s.station.price, 3),
            "route_mile": round(s.route_mile, 1),
            "distance_from_route_miles": round(s.offset_miles, 1),
            "fuel_on_arrival_gallons": round(s.fuel_on_arrival_gallons, 2),
            "gallons_purchased": round(s.gallons, 2),
            "cost": round(s.cost, 2),
        }
        for n, s in enumerate(plan.stops, start=1)
    ]
    line = [[round(lon, 5), round(lat, 5)] for lat, lon in simplify(route.coords, 2000)]

    return {
        "start": {"query": start.query, "label": start.label, "latitude": start.lat, "longitude": start.lon},
        "finish": {"query": finish.query, "label": finish.label, "latitude": finish.lat, "longitude": finish.lon},
        "vehicle": {"range_miles": settings.VEHICLE_RANGE_MILES, "mpg": settings.VEHICLE_MPG},
        "summary": {
            "total_distance_miles": round(route.distance_miles, 1),
            "estimated_drive_time_hours": round(route.duration_hours, 2),
            "total_gallons": round(plan.total_gallons, 2),
            "total_fuel_cost": round(plan.total_cost, 2),
            "average_price_per_gallon": round(plan.total_cost / plan.total_gallons, 3) if plan.total_gallons else 0,
            "number_of_fuel_stops": len(stops),
            "stations_considered": len(candidates),
        },
        "fuel_stops": stops,
        "geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"kind": "route", "stroke": "#2563eb", "stroke-width": 4},
                    "geometry": {"type": "LineString", "coordinates": line},
                },
                _point(start.lon, start.lat, {"kind": "start", "name": start.label, "marker-color": "#16a34a"}),
                _point(finish.lon, finish.lat, {"kind": "finish", "name": finish.label, "marker-color": "#dc2626"}),
                *[
                    _point(s["longitude"], s["latitude"], {
                        "kind": "fuel_stop",
                        "stop_number": s["stop_number"],
                        "name": s["name"],
                        "price_per_gallon": s["price_per_gallon"],
                        "gallons_purchased": s["gallons_purchased"],
                        "cost": s["cost"],
                        "marker-color": "#f59e0b",
                        "marker-symbol": "fuel",
                    })
                    for s in stops
                ],
            ],
        },
    }


def _point(lon, lat, props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [lon, lat]}}
