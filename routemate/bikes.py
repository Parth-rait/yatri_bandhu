"""
Public bike-share add-on (Chandigarh SmartBike, Panchkula municipal bikes).

Bikes are a FIRST / LAST MILE helper only: when a trip has a long walk and there is a dock
near both ends of that walk, we suggest riding instead. We never make a trip depend on a bike,
because there is no live availability feed (no public GBFS) and docks may be empty.

Docks come from data/bike_docks.json (seeded from OpenStreetMap). Add more docks there and the
feature appears in those areas automatically.
"""
import json
import math
from pathlib import Path

DATA = json.loads((Path(__file__).resolve().parent.parent / "data" / "bike_docks.json").read_text())
FARE_NOTE = DATA["fare_note"]
APP_LINK = DATA["app_link"]
DOCKS = DATA["docks"]

NEAR_DOCK_M = 350      # how far we'd walk to / from a dock
MIN_WALK_TO_REPLACE = 7  # only suggest bikes instead of walks this long (minutes)
BIKE_KMH = 12
UNLOCK_MIN = 2         # unlock + dock time


def _dist_m(a_lat, a_lng, b_lat, b_lng):
    R, r = 6371000, math.pi / 180
    h = math.sin((b_lat - a_lat) * r / 2) ** 2 + math.cos(a_lat * r) * math.cos(b_lat * r) * math.sin((b_lng - a_lng) * r / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def init(net):
    """Give unnamed docks a useful name: the nearest bus stop."""
    for d in DOCKS:
        if d["name"] in ("Bike share dock", "", None) or d["name"].lower().startswith("smartbike"):
            near = net.stops_near(dict(lat=d["lat"], lng=d["lng"]), 10)
            d["name"] = f"Near {net.stops[near[0][0]]['name']}" if near else "Bike share dock"


def docks_near(lat, lng, max_m=NEAR_DOCK_M):
    out = []
    for d in DOCKS:
        m = _dist_m(lat, lng, d["lat"], d["lng"])
        if m <= max_m:
            out.append(dict(d, meters=round(m * 1.3, -1), walk=max(1, round(m * 1.3 / 75))))
    return sorted(out, key=lambda d: d["meters"])


def ride_minutes(a, b):
    km = _dist_m(a["lat"], a["lng"], b["lat"], b["lng"]) * 1.3 / 1000
    return round(km / BIKE_KMH * 60) + UNLOCK_MIN, round(km, 1)


def bike_option(a, b):
    """Whole trip by bike (short trips only), if there are docks at both ends."""
    if _dist_m(a["lat"], a["lng"], b["lat"], b["lng"]) > 6000:
        return None
    da, db = docks_near(a["lat"], a["lng"]), docks_near(b["lat"], b["lng"])
    if not da or not db or da[0]["id"] == db[0]["id"]:
        return None
    ride, km = ride_minutes(da[0], db[0])
    return dict(pick=da[0], drop=db[0], ride=ride, km=km, total=da[0]["walk"] + ride + db[0]["walk"])


def decorate(j):
    """Hook for enrich(): mark walk legs that a bike could replace."""
    j["bike_tips"] = []
    for i, leg in enumerate(j["legs"]):
        if leg["type"] != "walk" or leg["minutes"] < MIN_WALK_TO_REPLACE:
            continue
        a, b = leg["start"], leg["end"]
        da, db = docks_near(a["lat"], a["lng"]), docks_near(b["lat"], b["lng"])
        if not da or not db or da[0]["id"] == db[0]["id"]:
            continue
        ride, km = ride_minutes(da[0], db[0])
        total = da[0]["walk"] + ride + db[0]["walk"]
        if total <= leg["minutes"] - 2:
            tip = dict(leg=i, pick=da[0], drop=db[0], ride=ride, total=total, saves=leg["minutes"] - total, walk=leg["minutes"])
            leg["bike"] = dict(pick=dict(name=da[0]["name"], lat=da[0]["lat"], lng=da[0]["lng"]),
                               drop=dict(name=db[0]["name"], lat=db[0]["lat"], lng=db[0]["lng"]))
            j["bike_tips"].append(tip)
    return j
