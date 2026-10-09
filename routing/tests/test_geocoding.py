from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from routing.services.geocoding import LocationError, geocode


class GeocodingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_lat_lon_needs_no_api_call(self):
        loc, calls = geocode("41.8781, -87.6298")
        self.assertEqual((loc.lat, loc.lon, calls, loc.source), (41.8781, -87.6298, 0, "coordinates"))

    @mock.patch("routing.services.geocoding.get_json")
    def test_city_state_uses_offline_gazetteer(self, get_json):
        loc, calls = geocode("Chicago, IL")
        self.assertEqual((calls, loc.source), (0, "gazetteer"))
        self.assertAlmostEqual(loc.lat, 41.8, delta=0.2)
        get_json.assert_not_called()

    def test_non_us_state_rejected(self):
        with self.assertRaises(LocationError):
            geocode("Toronto, ON")

    def test_coordinates_outside_usa_rejected(self):
        with self.assertRaises(LocationError):
            geocode("51.5074, -0.1278")  # London

    @mock.patch("routing.services.geocoding.get_json")
    def test_address_falls_back_to_nominatim_and_is_cached(self, get_json):
        get_json.return_value = [{"lat": "38.8977", "lon": "-77.0365", "display_name": "White House"}]
        loc, calls = geocode("1600 Pennsylvania Ave NW, Washington DC")
        self.assertEqual((calls, loc.source), (1, "nominatim"))
        _, calls_again = geocode("1600 Pennsylvania Ave NW, Washington DC")
        self.assertEqual(calls_again, 0)
        get_json.assert_called_once()

    @mock.patch("routing.services.geocoding.get_json", return_value=[])
    def test_unknown_address(self, _):
        with self.assertRaises(LocationError):
            geocode("asdfghjkl nowhere")
