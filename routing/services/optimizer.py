"""Choose where to buy fuel along a fixed route, minimising total fuel cost.

Greedy algorithm for the classic "gas station problem". At each stop, look at the stations within range:
  * if one is cheaper than here, buy just enough fuel to reach the first such station;
  * otherwise this is the cheapest fuel in range, so fill the tank and go to the cheapest station in range.
This rule gives the minimum possible total cost.

Assumptions: the vehicle starts with an (almost) empty tank and makes its first fill-up at the cheapest
station within the first `start_window_miles` of the route; the fuel burned to reach that station is
bought there. So total gallons bought always equals route distance / mpg.
"""
from dataclasses import dataclass

EPS = 1e-6


class NoFeasiblePlan(Exception):
    pass


@dataclass
class FuelStop:
    station: object
    route_mile: float
    offset_miles: float
    gallons: float
    cost: float
    fuel_on_arrival_gallons: float


@dataclass
class FuelPlan:
    stops: list
    total_gallons: float
    total_cost: float


def plan_fuel_stops(candidates, total_miles, range_miles, mpg, start_window_miles=25.0):
    """`candidates` is [(station, route_mile, offset_miles)] sorted by route_mile."""
    nodes = [c for c in candidates if c[1] < total_miles]
    if not nodes:
        raise NoFeasiblePlan("No fuel stations found along this route.")

    window = max(start_window_miles, nodes[0][1])
    if window > range_miles:
        raise NoFeasiblePlan(f"First fuel station is {nodes[0][1]:.0f} miles in, beyond the vehicle range.")

    # The destination is the last node. Pricing it below every station means "a cheaper stop is in range"
    # also covers "the destination is in range": buy just enough to get there.
    miles = [c[1] for c in nodes] + [total_miles]
    prices = [c[0].price for c in nodes] + [float("-inf")]
    dest = len(nodes)

    i = min((k for k in range(dest) if miles[k] <= window), key=lambda k: prices[k])
    fuel = 0.0  # miles' worth of fuel in the tank on arrival at node i
    stops = []

    while i != dest:
        in_range = [j for j in range(i + 1, dest + 1) if miles[j] - miles[i] <= range_miles + EPS]
        if not in_range:
            raise NoFeasiblePlan(
                f"No feasible plan: a {miles[i + 1] - miles[i]:.0f}-mile stretch without fuel stations "
                f"exceeds the {range_miles:.0f}-mile range."
            )

        cheaper = next((j for j in in_range if prices[j] < prices[i]), None)
        if cheaper is not None:
            nxt = cheaper
            buy = max(0.0, miles[nxt] - miles[i] - fuel)
        else:
            nxt = min(in_range, key=lambda j: prices[j])
            buy = range_miles - fuel

        bought = buy + (miles[i] if not stops else 0.0)  # first stop also pays for the leg from the origin
        if bought > EPS:
            station, mile, offset = nodes[i]
            gallons = bought / mpg
            stops.append(FuelStop(station, mile, offset, gallons, gallons * station.price, fuel / mpg))

        fuel += buy - (miles[nxt] - miles[i])
        i = nxt

    return FuelPlan(stops, sum(s.gallons for s in stops), sum(s.cost for s in stops))
