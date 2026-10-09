"""Small, dependency-free geometry helpers (miles, WGS84 lat/lon)."""
import math

EARTH_RADIUS_MILES = 3958.8
METERS_PER_MILE = 1609.344


def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def resample(coords, step_miles=1.0):
    """Return [(lat, lon, miles_from_start)] spaced between 1x and 2x `step_miles` along the line.

    `coords` is a list of (lat, lon). Long straight segments are interpolated and dense stretches are
    thinned, so station-to-route distances measured against these points stay accurate and cheap.
    """
    if not coords:
        return []
    lat0, lon0 = coords[0]
    out = [(lat0, lon0, 0.0)]
    total = last_kept = 0.0
    for lat1, lon1 in coords[1:]:
        seg = haversine_miles(lat0, lon0, lat1, lon1)
        if seg == 0:
            continue
        steps = math.ceil(seg / step_miles)
        for i in range(1, steps + 1):
            mile = total + seg * i / steps
            if mile - last_kept >= step_miles:
                t = i / steps
                out.append((lat0 + (lat1 - lat0) * t, lon0 + (lon1 - lon0) * t, mile))
                last_kept = mile
        total += seg
        lat0, lon0 = lat1, lon1
    if out[-1][2] != total:
        out.append((lat0, lon0, total))
    return out


def decode_polyline(encoded, precision=5):
    """Decode a Google encoded polyline into [(lat, lon)]."""
    coords, index, lat, lon = [], 0, 0, 0
    factor = 10 ** precision
    while index < len(encoded):
        for axis in (0, 1):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))
    return coords


def simplify(coords, max_points=1500):
    """Evenly thin a coordinate list for display, always keeping the endpoints."""
    if len(coords) <= max_points:
        return list(coords)
    step = (len(coords) - 1) / (max_points - 1)
    return [coords[round(i * step)] for i in range(max_points)]
