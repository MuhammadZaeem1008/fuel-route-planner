from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from routing.models import FuelStation
from routing.services.stations import get_station_index


def encode_polyline(coords, precision=5):
    out, prev = [], (0, 0)
    for lat, lon in coords:
        cur = (round(lat * 10**precision), round(lon * 10**precision))
        for delta in (cur[0] - prev[0], cur[1] - prev[1]):
            v = ~(delta << 1) if delta < 0 else delta << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        prev = cur
    return "".join(out)


# A straight east-west "highway" along latitude 39.0 from Kansas City-ish to Denver-ish (~ 520 mi).
ROUTE = [(39.0, -94.6), (39.0, -99.0), (39.0, -104.9)]


def osrm_response(*_args, **_kwargs):
    return {
        "code": "Ok",
        "routes": [{"distance": 545 * 1609.344, "duration": 8 * 3600, "geometry": encode_polyline(ROUTE)}],
    }


class RouteApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rows = [
            (1, "START STOP", -94.65, 3.40),
            (2, "CHEAP MIDWAY", -99.00, 2.80),
            (3, "PRICEY MIDWAY", -99.10, 3.90),
            (4, "OFF ROUTE CHEAP", -99.00, 1.00),  # 70 miles north: outside the corridor
            (5, "NEAR END", -104.5, 3.20),
        ]
        for opis, name, lon, price in rows:
            FuelStation.objects.create(
                opis_id=opis, name=name, address="I-70", city="Somewhere", state="KS",
                retail_price=price, latitude=40.0 if opis == 4 else 39.0, longitude=lon,
            )

    def setUp(self):
        cache.clear()
        get_station_index.cache_clear()
        self.addCleanup(get_station_index.cache_clear)
        patcher = mock.patch("routing.services.directions.get_json", side_effect=osrm_response)
        self.osrm = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, **body):
        return self.client.post(reverse("route-plan"), body, content_type="application/json")

    def test_plan_route(self):
        resp = self.post(start="39.0,-94.6", finish="39.0,-104.9")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()

        names = [s["name"] for s in data["fuel_stops"]]
        self.assertEqual(names, ["START STOP", "CHEAP MIDWAY"])
        self.assertNotIn("OFF ROUTE CHEAP", names)
        self.assertEqual(data["summary"]["total_distance_miles"], 545.0)
        self.assertAlmostEqual(data["summary"]["total_gallons"], 54.5, places=1)
        self.assertAlmostEqual(
            data["summary"]["total_fuel_cost"], sum(s["cost"] for s in data["fuel_stops"]), places=1
        )
        self.assertEqual(data["meta"]["external_api_calls"], 1)
        self.assertEqual(data["geojson"]["features"][0]["geometry"]["type"], "LineString")

    def test_repeat_request_is_served_from_cache(self):
        self.post(start="39.0,-94.6", finish="39.0,-104.9")
        data = self.post(start="39.0,-94.6", finish="39.0,-104.9").json()
        self.assertEqual(self.osrm.call_count, 1)
        self.assertEqual((data["meta"]["cached"], data["meta"]["external_api_calls"]), (True, 0))

    def test_get_not_allowed(self):
        resp = self.client.get(reverse("route-plan"), {"start": "39.0,-94.6", "finish": "39.0,-104.9"})
        self.assertEqual(resp.status_code, 405)
        self.osrm.assert_not_called()

    def test_validation_errors(self):
        self.assertEqual(self.post(start="Chicago, IL").status_code, 400)
        self.assertEqual(self.post(start="Toronto, ON", finish="Chicago, IL").status_code, 400)
        self.assertEqual(self.post(start="Chicago, IL", finish="chicago, il").status_code, 400)

    def test_no_route_from_osrm(self):
        self.osrm.side_effect = lambda *a, **k: {"code": "NoRoute", "message": "Impossible route"}
        self.assertEqual(self.post(start="39.0,-94.6", finish="39.0,-104.9").status_code, 502)
