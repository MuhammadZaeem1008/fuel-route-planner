import random
from types import SimpleNamespace

from django.test import SimpleTestCase

from routing.services.optimizer import NoFeasiblePlan, plan_fuel_stops


def station(price, name="S"):
    return SimpleNamespace(price=price, name=name)


def brute_force_cost(candidates, total, rng, mpg):
    """Exact minimum cost by trying every purchase amount, one mile at a time (integer miles only).

    cost[f] = cheapest way to be at the current mile with f miles of fuel in the tank.
    """
    inf = float("inf")
    price_at = {}
    for st, mile, _ in candidates:
        price_at[int(mile)] = min(price_at.get(int(mile), inf), st.price)
    cost = [0.0] + [inf] * rng
    for mile in range(int(total)):
        if mile in price_at:
            for f in range(1, rng + 1):  # buy one more mile of fuel here
                cost[f] = min(cost[f], cost[f - 1] + price_at[mile] / mpg)
        cost = cost[1:] + [inf]  # drive one mile
    return min(cost)


class OptimizerTests(SimpleTestCase):
    def test_short_trip(self):
        cands = [(station(3.0), 5.0, 1.0), (station(2.0), 100.0, 1.0)]
        # Cheapest: 10 gal @ $3 (origin -> mile 100), then 20 gal @ $2.
        plan = plan_fuel_stops(cands, total_miles=300, range_miles=500, mpg=10)
        self.assertEqual([round(s.gallons, 6) for s in plan.stops], [10.0, 20.0])
        self.assertAlmostEqual(plan.total_cost, 70.0)

    def test_buys_cheap_fuel_ahead_when_worth_it(self):
        # Expensive at start: buy only enough to reach the cheap station, then fill there.
        cands = [(station(4.0), 0.0, 0.0), (station(2.0), 50.0, 0.0), (station(5.0), 400.0, 0.0)]
        plan = plan_fuel_stops(cands, total_miles=500, range_miles=500, mpg=10)
        self.assertEqual([s.station.price for s in plan.stops], [4.0, 2.0])
        self.assertAlmostEqual(plan.stops[0].gallons, 5.0)
        self.assertAlmostEqual(plan.stops[1].gallons, 45.0)
        self.assertAlmostEqual(plan.total_cost, 5 * 4 + 45 * 2)

    def test_fills_up_when_no_cheaper_station_in_range(self):
        # Cheapest fuel is at the start and nothing in range beats it: fill the tank there.
        cands = [(station(2.0), 0.0, 0.0), (station(3.0), 300.0, 0.0), (station(4.0), 450.0, 0.0)]
        plan = plan_fuel_stops(cands, total_miles=700, range_miles=500, mpg=10)
        self.assertEqual([(s.station.price, round(s.gallons, 6)) for s in plan.stops], [(2.0, 50.0), (3.0, 20.0)])
        self.assertAlmostEqual(plan.stops[1].fuel_on_arrival_gallons, 20.0)

    def test_long_trip_needs_multiple_stops_within_range(self):
        cands = [(station(3.0 + (m % 7) / 10), float(m), 0.5) for m in range(0, 2000, 40)]
        plan = plan_fuel_stops(cands, total_miles=2000, range_miles=500, mpg=10)
        miles = [0.0] + [s.route_mile for s in plan.stops] + [2000.0]
        self.assertTrue(all(b - a <= 500 + 1e-6 for a, b in zip(miles, miles[1:])))
        self.assertGreaterEqual(len(plan.stops), 4)
        self.assertAlmostEqual(plan.total_gallons, 200.0)

    def test_matches_brute_force_on_random_routes(self):
        rnd = random.Random(42)
        checked = 0
        for _ in range(200):
            total = rnd.randint(50, 300)
            miles = sorted({0, *[rnd.randint(0, total - 1) for _ in range(rnd.randint(5, 40))]})
            cands = [(station(round(rnd.uniform(2.5, 4.5), 3)), float(m), 0.0) for m in miles]
            try:
                plan = plan_fuel_stops(cands, total, range_miles=60, mpg=10, start_window_miles=0)
            except NoFeasiblePlan:
                self.assertEqual(brute_force_cost(cands, total, 60, 10), float("inf"))
                continue
            self.assertAlmostEqual(plan.total_cost, brute_force_cost(cands, total, 60, 10), places=6)
            self.assertAlmostEqual(plan.total_gallons, total / 10, places=6)
            checked += 1
        self.assertGreater(checked, 50)

    def test_gap_larger_than_range_is_infeasible(self):
        cands = [(station(3.0), 0.0, 0.0), (station(3.0), 600.0, 0.0)]
        with self.assertRaises(NoFeasiblePlan):
            plan_fuel_stops(cands, 1000, 500, 10)

    def test_no_stations(self):
        with self.assertRaises(NoFeasiblePlan):
            plan_fuel_stops([], 100, 500, 10)
