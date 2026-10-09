"""Loads data/build/network.json and turns each route into one or two travel patterns."""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "build" / "network.json"

WALK_M_PER_MIN = 75      # ~4.5 km/h
WALK_DETOUR = 1.3        # streets are not straight lines

# Approximate CTU non-AC fare slabs (Rs) by distance travelled on one bus.
# Source: CTU fare revision reported by The Tribune; verify before relying on it.
FARE_SLABS = [(5, 10), (10, 20), (math.inf, 25)]

# Rough ranges for non-bus options. These are NOT live prices.
OTHER_MODES = [
    dict(id="bike", label="Bike taxi", icon="🛵", base=20, per_km=7, speed=26),
    dict(id="auto", label="Auto-rickshaw", icon="🛺", base=30, per_km=13, speed=22),
    dict(id="cab", label="Cab (app-based)", icon="🚕", base=60, per_km=16, speed=26),
]


def distance_m(a_lat, a_lng, b_lat, b_lng):
    R = 6371000
    la1, lo1, la2, lo2 = map(math.radians, (a_lat, a_lng, b_lat, b_lng))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def walk_minutes(a, b):
    m = distance_m(a["lat"], a["lng"], b["lat"], b["lng"]) * WALK_DETOUR
    return 0 if m < 60 else max(1, round(m / WALK_M_PER_MIN))


def fare_for_km(km):
    for limit, fare in FARE_SLABS:
        if km <= limit:
            return fare
    return FARE_SLABS[-1][1]


class Pattern:
    """One direction of one route, with an evenly spaced departure schedule."""

    def __init__(self, route, direction, stops, offsets, km_at, window, shape, shape_idx, stop_names):
        self.route = route
        self.no = route["no"]
        self.id = f"{route['no']}:{direction}"
        self.direction = direction
        self.stops = stops
        self.offsets = offsets
        self.km_at = km_at
        self.start, self.end = window
        lo, hi = route["every"]
        self.every_text = f"every {lo} min" if lo == hi else f"every {lo}–{hi} min"
        self.headway = (lo + hi) / 2
        self.shape = shape
        self.shape_idx = shape_idx
        self.headsign = stop_names[stops[-1]] if direction != "loop" else f"circular via {stop_names[stops[len(stops) // 2]]}"

    def trip_start(self, i, t):
        """Start time (at first stop) of the first trip that reaches stop i at or after t."""
        off = self.offsets[i]
        shifts = (0, 1440) if self.end > 1440 else (0,)
        for shift in shifts:
            tt = t + shift
            k = max(0, math.ceil((tt - off - self.start) / self.headway - 1e-9))
            s = self.start + k * self.headway
            if s <= self.end:
                return s - shift
        return None

    def is_last_trip(self, start):
        return start + self.headway > self.end

    def first_last_at(self, i):
        return self.start + self.offsets[i], self.end + self.offsets[i]


class Network:
    def __init__(self, path=DATA):
        raw = json.loads(Path(path).read_text())
        self.source = raw["source"]
        self.stops = {s["id"]: s for s in raw["stops"]}
        self.places = {p["id"]: p for p in raw["places"]}
        self.routes = {r["no"]: r for r in raw["routes"]}
        names = {k: s["name"] for k, s in self.stops.items()}
        self.patterns = []
        for r in raw["routes"]:
            if r["loop"]:
                self.patterns.append(Pattern(r, "loop", r["stops"], r["offsets"], r["km_at"], r["fwd"],
                                             r["shape"], r["shape_idx"], names))
                continue
            self.patterns.append(Pattern(r, "fwd", r["stops"], r["offsets"], r["km_at"], r["fwd"],
                                         r["shape"], r["shape_idx"], names))
            total, km_total, n = r["offsets"][-1], r["km_at"][-1], len(r["shape"]) - 1
            self.patterns.append(Pattern(
                r, "rev", r["stops"][::-1], [round(total - o, 1) for o in r["offsets"][::-1]],
                [round(km_total - k, 2) for k in r["km_at"][::-1]], r["rev"] or r["fwd"],
                r["shape"][::-1], [n - i for i in r["shape_idx"][::-1]], names))
        self.pattern_by_id = {p.id: p for p in self.patterns}
        self.at_stop = {}
        for p in self.patterns:
            for i, s in enumerate(p.stops):
                self.at_stop.setdefault(s, []).append((p, i))
        self.routes_at_stop = {s: sorted({p.no for p, _ in v}, key=route_sort_key) for s, v in self.at_stop.items()}
        self.neighbours = {}
        for a in self.stops.values():
            self.neighbours[a["id"]] = [(b["id"], walk_minutes(a, b)) for b in self.stops.values()
                                        if walk_minutes(a, b) <= 6]

    def stops_near(self, point, max_min):
        out = []
        for s in self.stops.values():
            w = walk_minutes(point, s)
            if w <= max_min:
                out.append((s["id"], w))
        return sorted(out, key=lambda x: x[1])


def route_sort_key(no):
    digits = "".join(c for c in no if c.isdigit())
    return (int(digits) if digits else 0, no)
