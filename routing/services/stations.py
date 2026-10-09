"""In-memory spatial index of fuel stations, built once per process from the database."""
import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from routing.models import FuelStation

from .geo import haversine_miles

CELL_DEGREES = 0.25  # ~17 miles of latitude per grid cell


@dataclass(frozen=True)
class Station:
    id: int
    opis_id: int
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lon: float


def _cell(lat, lon):
    return math.floor(lat / CELL_DEGREES), math.floor(lon / CELL_DEGREES)


class StationIndex:
    def __init__(self, stations):
        self.grid = defaultdict(list)
        for s in stations:
            self.grid[_cell(s.lat, s.lon)].append(s)

    def __len__(self):
        return sum(len(v) for v in self.grid.values())

    def stations_along(self, route_points, corridor_miles):
        """Match stations to a densified route.

        `route_points` is [(lat, lon, mile_from_start)]. Returns [(station, route_mile, offset_miles)]
        sorted by route_mile, where route_mile is the position of the closest route point.
        """
        best = {}
        lat_cells = math.ceil(corridor_miles / 69.0 / CELL_DEGREES)
        for lat, lon, mile in route_points:
            # A degree of longitude shrinks with latitude, so widen the search accordingly.
            lon_cells = math.ceil(corridor_miles / (69.0 * max(math.cos(math.radians(lat)), 0.2)) / CELL_DEGREES)
            ci, cj = _cell(lat, lon)
            for di in range(-lat_cells, lat_cells + 1):
                for dj in range(-lon_cells, lon_cells + 1):
                    for s in self.grid.get((ci + di, cj + dj), ()):
                        d = haversine_miles(lat, lon, s.lat, s.lon)
                        if d <= corridor_miles and (s.id not in best or d < best[s.id][2]):
                            best[s.id] = (s, mile, d)
        return sorted(best.values(), key=lambda t: t[1])


@lru_cache(maxsize=1)
def get_station_index():
    rows = FuelStation.objects.values_list(
        "id", "opis_id", "name", "address", "city", "state", "retail_price", "latitude", "longitude"
    )
    return StationIndex(
        Station(id, opis, name, addr, city, state, float(price), lat, lon)
        for id, opis, name, addr, city, state, price, lat, lon in rows
    )
