from django.test import SimpleTestCase

from routing.services.geo import decode_polyline, haversine_miles, resample, simplify


class GeoTests(SimpleTestCase):
    def test_decode_polyline(self):
        # Example from Google's polyline algorithm documentation.
        coords = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        expected = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
        for (lat, lon), (elat, elon) in zip(coords, expected):
            self.assertAlmostEqual(lat, elat)
            self.assertAlmostEqual(lon, elon)

    def test_haversine(self):
        # New York -> Los Angeles is ~2445 miles great-circle.
        self.assertAlmostEqual(haversine_miles(40.7128, -74.006, 34.0522, -118.2437), 2445, delta=5)

    def test_resample_spacing_and_total(self):
        line = [(35.0, -100.0), (35.0, -99.0), (35.0, -98.9999), (36.0, -99.0)]
        pts = resample(line, step_miles=1.0)
        gaps = [b[2] - a[2] for a, b in zip(pts, pts[1:])]
        self.assertTrue(all(g < 2.0 for g in gaps))
        total = sum(haversine_miles(*a, *b) for a, b in zip(line, line[1:]))
        self.assertAlmostEqual(pts[-1][2], total, places=6)

    def test_simplify_keeps_endpoints(self):
        pts = [(i, i) for i in range(10_000)]
        out = simplify(pts, 100)
        self.assertEqual(len(out), 100)
        self.assertEqual((out[0], out[-1]), (pts[0], pts[-1]))
