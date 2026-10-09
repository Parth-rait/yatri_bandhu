"""
Build data/build/network.json from the CTU time table transcription.

    python tools/build_data.py            # geocode + road shapes (uses caches)
    python tools/build_data.py --offline  # only use cached results, never hit the network

Steps
1. Read every stop token from data/routes_source.py.
2. Geocode landmarks and sector centres with OpenStreetMap Nominatim (cached in
   data/cache/geocode.json, max 1 request per second as required by the OSM usage policy).
3. Junctions such as "22/17" are placed at the midpoint of the two sector centres.
4. Ask the public OSRM server for a road-following line through each route's stops
   (cached in data/cache/shapes.json) so maps show real roads, not straight lines.
5. Spread the route's printed length (km) over its stops to estimate ride times.
"""
import json
import math
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.gazetteer import DERIVED, LANDMARKS, MANUAL_COORDS, POPULAR  # noqa: E402
from data.routes_source import ROUTES  # noqa: E402

CACHE = ROOT / "data" / "cache"
OUT = ROOT / "data" / "build" / "network.json"
UA = "RouteMate-HCI-student-prototype/0.1"
# Tricity bounding box (lng_min, lat_max, lng_max, lat_min)
VIEWBOX = (76.55, 30.90, 76.98, 30.55)
BUS_KMH = 21  # average CTU bus speed in city traffic incl. stops (assumption)
OFFLINE = "--offline" in sys.argv


def load(name):
    p = CACHE / name
    return json.loads(p.read_text()) if p.exists() else {}


def dump(name, obj):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False))


geo_cache = load("geocode.json")
shape_cache = load("shapes.json")


def nominatim(query, must_contain=None):
    if query in geo_cache:
        hit = geo_cache[query]
    elif OFFLINE:
        return None
    else:
        time.sleep(1.1)
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=dict(q=query, format="json", limit=5, countrycodes="in",
                        viewbox=",".join(map(str, VIEWBOX)), bounded=1),
            headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        hit = r.json()
        geo_cache[query] = hit
        dump("geocode.json", geo_cache)
    for h in hit:
        if must_contain and must_contain.lower() not in h["display_name"].lower():
            continue
        return float(h["lat"]), float(h["lon"])
    return None


# ---------------------------------------------------------------- tokens
def classify(tok):
    """Return (kind, payload). kinds: landmark, sector, junction."""
    city = "CHD"
    t = tok
    if t[0] in "MP" and (t[1:2].isdigit()):
        city, t = {"M": "MOH", "P": "PKL"}[t[0]], t[1:]
    elif t[0] == "S" and t[1:].isdigit():
        return "sector", ("CHD", t[1:])
    if "/" in t and all(p.isdigit() for p in t.split("/")):
        a, b = sorted(t.split("/"), key=int)
        return "junction", (city, a, b)
    if t.isdigit():
        return "sector", (city, t)
    return "landmark", tok


CITY_Q = {
    "CHD": ["Sector {n}, Chandigarh"],
    "MOH": ["Sector {n}, Sahibzada Ajit Singh Nagar", "Sector {n}, Mohali", "Sector {n}, Chandigarh"],
    "PKL": ["Sector {n}, Panchkula"],
}
CITY_NAME = {"CHD": "Chandigarh", "MOH": "Mohali", "PKL": "Panchkula"}
CITY_PREFIX = {"CHD": "", "MOH": "Mohali ", "PKL": "Panchkula "}


def sector_center(city, n):
    for q in CITY_Q[city]:
        c = nominatim(q.format(n=n), must_contain=f"Sector {n}")
        if c:
            return c
    return None


def haversine(a, b):
    R = 6371000
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def stop_key(tok):
    kind, p = classify(tok)
    if kind == "landmark":
        return p
    if kind == "sector":
        return f"{p[0]}_S{p[1]}"
    return f"{p[0]}_J{p[1]}_{p[2]}"


def resolve(tok, problems):
    kind, p = classify(tok)
    if kind == "landmark":
        if p not in LANDMARKS:
            problems.append(f"unknown landmark token {p}")
            return None
        name, q, area = LANDMARKS[p]
        if p in MANUAL_COORDS:
            c = MANUAL_COORDS[p]
        elif p in DERIVED:
            parts = [resolve(x, problems) for x in DERIVED[p]]
            parts = [x for x in parts if x]
            c = (sum(x["lat"] for x in parts) / len(parts), sum(x["lng"] for x in parts) / len(parts)) if parts else None
        else:
            c = nominatim(q)
        if not c:
            problems.append(f"no coordinates for {p} ({q})")
            return None
        return dict(name=name, area=area, lat=c[0], lng=c[1], kind="landmark")
    if kind == "sector":
        city, n = p
        c = sector_center(city, n)
        if not c:
            problems.append(f"no coordinates for {city} sector {n}")
            return None
        return dict(name=f"{CITY_PREFIX[city]}Sector {n} Market", area=CITY_NAME[city],
                    lat=c[0], lng=c[1], kind="sector")
    city, a, b = p
    ca, cb = sector_center(city, a), sector_center(city, b)
    if not (ca and cb):
        problems.append(f"no coordinates for {city} junction {a}/{b}")
        return None
    gap = haversine(ca, cb)
    if gap > 2600:
        problems.append(f"suspicious junction {city} {a}/{b}: sector centres {gap:.0f} m apart")
    return dict(name=f"{CITY_PREFIX[city]}Sector {a}/{b}", area=CITY_NAME[city],
                lat=(ca[0] + cb[0]) / 2, lng=(ca[1] + cb[1]) / 2, kind="junction")


# ---------------------------------------------------------------- shapes
def osrm_shape(coords):
    """coords: [(lat,lng)...] -> (line [[lat,lng]...], leg_distances_m) or None."""
    key = ";".join(f"{lng:.5f},{lat:.5f}" for lat, lng in coords)
    if key in shape_cache:
        return shape_cache[key]
    if OFFLINE:
        return None
    url = f"https://router.project-osrm.org/route/v1/driving/{key}"
    for attempt in range(3):
        try:
            r = requests.get(url, params=dict(overview="full", geometries="geojson"),
                             headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200 and r.json().get("code") == "Ok":
                route = r.json()["routes"][0]
                line = [[round(lat, 5), round(lng, 5)] for lng, lat in route["geometry"]["coordinates"]]
                res = [line, [round(l["distance"]) for l in route["legs"]]]
                shape_cache[key] = res
                dump("shapes.json", shape_cache)
                time.sleep(1)
                return res
        except requests.RequestException:
            pass
        time.sleep(3)
    return None


def snap_indices(line, pts):
    """Index into line for each stop, moving forward only."""
    out, start = [], 0
    for p in pts:
        best, bi = 1e18, start
        for i in range(start, len(line)):
            d = (line[i][0] - p[0]) ** 2 + (line[i][1] - p[1]) ** 2
            if d < best:
                best, bi = d, i
        out.append(bi)
        start = bi
    return out


def hhmm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


# ---------------------------------------------------------------- build
def main():
    problems = []
    stops = {}
    routes = []
    for r in ROUTES:
        toks = r["stops"].split()
        keys = []
        for t in toks:
            k = stop_key(t)
            if k not in stops:
                s = resolve(t, problems)
                if not s:
                    continue
                stops[k] = dict(id=k, **s)
            if keys and keys[-1] == k:
                continue
            keys.append(k)
        if len(keys) < 2:
            problems.append(f"route {r['no']} has <2 placeable stops, skipped")
            continue

        pts = [(stops[k]["lat"], stops[k]["lng"]) for k in keys]
        shape = osrm_shape(pts)
        if shape:
            line, legs = shape
            idx = snap_indices(line, pts)
        else:
            line = [list(p) for p in pts]
            legs = [haversine(pts[i], pts[i + 1]) * 1.3 for i in range(len(pts) - 1)]
            idx = list(range(len(pts)))
            problems.append(f"route {r['no']}: no road shape, using straight lines")

        # spread printed route length over the legs to get minutes from first stop
        road_m = sum(legs) or 1
        total_min = r["km"] / BUS_KMH * 60
        # loops: printed length covers the full circuit; linear: one direction
        scale = total_min / road_m
        offsets, acc = [0], 0.0
        for d in legs:
            acc += d * scale
            offsets.append(round(acc, 1))
        km_from_start, acc_m = [0.0], 0.0
        ratio = (r["km"] * 1000) / road_m
        for d in legs:
            acc_m += d * ratio
            km_from_start.append(round(acc_m / 1000, 2))

        def span(t):
            a, b = hhmm(t[0]), hhmm(t[1])
            if b < a:  # night service crossing midnight
                b += 1440
            return [a, b]

        routes.append(dict(
            no=r["no"], name=r["name"], loop=bool(r.get("loop")), night=bool(r.get("night")),
            stops=keys, offsets=offsets, km_at=km_from_start,
            fwd=span(r["fwd"]), rev=span(r["rev"]) if r.get("rev") else None,
            every=list(r["every"]), km=r["km"], buses=r["buses"],
            shape=line, shape_idx=idx,
        ))

    places = []
    for pid, name, icon, cat, tok, aliases in POPULAR:
        k = stop_key(tok)
        s = stops.get(k) or resolve(tok, problems)
        if not s:
            continue
        places.append(dict(id=pid, name=name, icon=icon, category=cat, stop=k if k in stops else None,
                           lat=s["lat"], lng=s["lng"], area=s["area"], aliases=aliases))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(
        source="CTU time table of local & tri-city routes, as on 25.07.2026 (Depots II, III, IV)",
        built=time.strftime("%Y-%m-%d"),
        stops=list(stops.values()), routes=routes, places=places), ensure_ascii=False))
    print(f"{len(stops)} stops, {len(routes)} routes, {len(places)} places -> {OUT.relative_to(ROOT)}")
    if problems:
        print("\nProblems to review:")
        for p in problems:
            print(" -", p)


if __name__ == "__main__":
    main()
