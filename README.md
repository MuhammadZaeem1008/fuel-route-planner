# Fuel Route Planner

A Django REST API that takes a start and finish location in the USA and returns:

- the driving route as GeoJSON (paste it into [geojson.io](https://geojson.io) to view the map),
- where to fuel up along the way, chosen to keep fuel spend low, for a vehicle with a **500-mile range**,
- the **total fuel cost** at **10 miles per gallon**, using the prices in the provided CSV.

A request makes **one** call to the routing API (OSRM). Locations given as `"City, ST"` or `"lat,lon"` are resolved
offline. A street address adds one Nominatim call per address, so a request makes 3 calls at most. Identical requests
are cached and make **0** external calls.

## Quick start

Requires **Python 3.12+** (Django 6.1).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_fuel_stations     # loads ~6.6k US truck stops with coordinates (< 1 s)
python manage.py runserver
```

Run the tests with `python manage.py test`.

## API

### `POST /api/route/`

```json
{ "start": "New York, NY", "finish": "Los Angeles, CA" }
```

Both fields are required. Each can be `"City, ST"` (offline lookup), `"lat,lon"`, or any US address or place
(Nominatim).

Response (trimmed):

```json
{
  "start":  { "query": "New York, NY", "label": "New York, NY", "latitude": 40.66, "longitude": -73.94 },
  "finish": { "query": "Los Angeles, CA", "label": "Los Angeles, CA", "latitude": 34.02, "longitude": -118.41 },
  "vehicle": { "range_miles": 500, "mpg": 10 },
  "summary": {
    "total_distance_miles": 2810.4,
    "estimated_drive_time_hours": 50.31,
    "total_gallons": 281.04,
    "total_fuel_cost": 852.46,
    "average_price_per_gallon": 3.033,
    "number_of_fuel_stops": 19,
    "stations_considered": 459
  },
  "fuel_stops": [
    {
      "stop_number": 1, "opis_id": 62790, "name": "7-ELEVEN #40084",
      "address": "US-46/US-1/US-9", "city": "Palisades Park", "state": "NJ",
      "latitude": 40.85, "longitude": -73.99,
      "price_per_gallon": 3.099, "route_mile": 9.4, "distance_from_route_miles": 8.2,
      "fuel_on_arrival_gallons": 0.0, "gallons_purchased": 6.94, "cost": 21.52
    }
  ],
  "geojson": { "type": "FeatureCollection", "features": ["route LineString, start/finish and fuel-stop Points"] },
  "meta": { "external_api_calls": 1, "cached": false, "elapsed_ms": 1330.2 }
}
```

Errors: `400` for invalid input or a location outside the USA, `422` if no plan is possible (a gap between stations
longer than the vehicle's range), `502` if the routing or geocoding service fails.

To view the map, paste the `geojson` field into [geojson.io](https://geojson.io). It shows the route line, start and
finish markers, and the fuel stops with their prices and costs.

A Postman collection is in [`postman_collection.json`](postman_collection.json).

## How it works

```
start/finish ──► geocode (offline gazetteer | lat,lon | Nominatim)
             ──► OSRM /route  (1 call, full geometry as an encoded polyline)
             ──► resample the route to about 1 point per mile
             ──► match stations within the corridor using an in-memory grid index
             ──► greedy fuel optimizer (cheapest total cost)
             ──► JSON + GeoJSON (cached for repeat requests)
```

**Station coordinates.** The CSV has addresses but no coordinates, and geocoding 8,000 rows on each request isn't an
option. `scripts/build_city_coords.py` builds `data/us_cities.csv` from the US Census Gazetteer (places + county
subdivisions, about 48k entries). `scripts/geocode_missing_cities.py` geocoded the ~140 remaining small towns once
through Nominatim, and those results are in `data/city_overrides.csv`. Both files are committed, so
`load_fuel_stations` needs no network access. Canadian rows are skipped because the trip is US-only. Duplicate OPIS IDs
are collapsed to the cheapest listing.

**Matching stations to the route.** Stations sit in a 0.25° grid held in memory, built once per process. The route is
resampled to about 1 point per mile. Each station gets its closest point on the route, which gives its offset from the
route and its mile marker along it. On a coast-to-coast route this step takes about 60 ms.

**Choosing fuel stops** (`routing/services/optimizer.py`). A greedy algorithm, the textbook solution to the "gas
station problem". At each stop it looks at the stations within the 500-mile range:

- if one is **cheaper** than the current station, buy just enough fuel to reach the first such station;
- otherwise the current station has the cheapest fuel in range, so **fill the tank** and drive to the cheapest station
  in range.

This gives the minimum possible total fuel cost. The tests check it against a brute-force search on 200 random routes.
It runs in about 1 ms on a coast-to-coast route. For NY→LA the plan costs $852.46. Because the goal is purely the
cheapest cost, the plan may include short stops that buy a gallon or two when a slightly cheaper station is just ahead.

**Assumptions**

- The vehicle starts with an (almost) empty tank and fills up within the first 25 miles. The fuel used to reach that
  station is charged at its price, so total gallons always equal `distance / 10`.
- Station coordinates are at city level, so stations within 10 miles of the route are considered. Detour distance to reach a station is
  not modelled.
- Prices are treated as constant. The total cost covers the fuel actually burned, so the vehicle arrives with an empty
  tank.

**Speed.** On a cache miss, most of the time goes to the OSRM round trip (about 0.2–1.2 s depending on route length).
Local computation is about 60 ms coast to coast. Cache hits return in under 1 ms. The station index and city table
load once per process.

## Project layout

```
config/                      Django settings & root URLs
routing/
  models.py                  FuelStation
  views.py, serializers.py   API view + input validation
  services/
    geocoding.py             location parsing / offline lookup / Nominatim fallback
    directions.py            OSRM client (single call)
    stations.py              in-memory spatial index + corridor matching
    optimizer.py             greedy fuel-stop planner
    planner.py               orchestration + caching + response shaping
    geo.py                   haversine, polyline decoding, resampling
  management/commands/load_fuel_stations.py
  tests/                     optimizer, geo, geocoding and API tests
data/                        fuel price CSV + offline city coordinates
scripts/                     one-off data preparation scripts
```

## Configuration

`VEHICLE_RANGE_MILES`, `VEHICLE_MPG` and `CORRIDOR_MILES` are set in
`config/settings.py`. `OSRM_URL` and `NOMINATIM_URL` can also be overridden with environment variables. The public OSRM
demo server is free but rate-limited. For production, point `OSRM_URL` at a self-hosted OSRM.
