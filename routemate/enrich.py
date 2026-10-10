"""
Add-on layer: decorates journeys AFTER the planner has found them.

It never changes routes, times, fares or ranking. It only adds extra fields that the
templates can show:
    leg["electric"]        bus leg runs on an electric route
    j["electric"]          any bus in the trip is electric
    j["co2_saved_kg"]      rough CO2 saved compared with a cab
    j["night_notes"]       facts worth knowing after dark (long walks, long waits)
    j["stop_safety"]       what students reported about the boarding / change / alighting stops
Remove the one call in app.py and the app behaves exactly as before.
"""
import json
from pathlib import Path

EXTRAS = json.loads((Path(__file__).resolve().parent.parent / "data" / "extras.json").read_text())
ELECTRIC = set(EXTRAS["electric_routes"]["routes"])
SAFETY = EXTRAS["safety"]
CO2 = EXTRAS["co2"]


def _hhmm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


NIGHT_START, NIGHT_END = _hhmm(SAFETY["night_starts"]), _hhmm(SAFETY["night_ends"])


def is_night(minute):
    m = int(minute) % 1440
    return m >= NIGHT_START or m < NIGHT_END


def enrich(j, stop_safety=None):
    """Decorate one journey in place. `stop_safety(stop_id)` returns a report summary or None."""
    if not j or j.get("_enriched"):
        return j
    bus_legs = [l for l in j["legs"] if l["type"] == "bus"]
    for l in bus_legs:
        l["electric"] = l["route"] in ELECTRIC
    j["electric"] = any(l["electric"] for l in bus_legs)

    # CO2: same trip by cab vs this trip (walking is zero)
    bus_km = sum(l.get("km", 0) for l in bus_legs)
    walk_km = sum(l.get("meters", 0) for l in j["legs"] if l["type"] == "walk") / 1000
    cab_g = (bus_km + walk_km) * CO2["cab_g_per_km"]
    trip_g = sum(l.get("km", 0) * (CO2["electric_bus_g_per_km"] if l["electric"] else CO2["bus_g_per_km"]) for l in bus_legs)
    j["co2_saved_kg"] = round(max(0.0, cab_g - trip_g) / 1000, 1)

    # Night notes: facts, not verdicts
    notes = []
    clock = j.get("leave", 0)
    for l in j["legs"]:
        if l["type"] == "walk":
            if is_night(clock) and l["minutes"] >= SAFETY["long_walk_min"]:
                notes.append(f"{l['minutes']} min walk after dark to {l['end']['name']}")
            clock += l["minutes"]
        elif l["type"] == "bus":
            wait = l.get("wait")
            if wait is not None and wait >= SAFETY["long_wait_min"] and is_night(l["depart"]):
                notes.append(f"~{wait} min wait after dark at {l['board']['name']}")
            clock = l["arrive"]
    if bus_legs and is_night(bus_legs[-1]["depart"]) and bus_legs[-1].get("last_trip"):
        notes.append(f"Last bus {bus_legs[-1]['route']} of the day")
    j["night_notes"] = notes
    j["night"] = is_night(j.get("leave", 0)) or is_night(j.get("arrive", 0))

    # What students reported about the stops you'll stand at
    j["stop_safety"] = []
    if stop_safety:
        seen = set()
        for l in bus_legs:
            for role, p in (("Board", l["board"]), ("Get off", l["alight"])):
                sid = p.get("stop_id")
                if sid and sid not in seen:
                    seen.add(sid)
                    s = stop_safety(sid)
                    if s:
                        j["stop_safety"].append(dict(s, role=role, name=p["name"], stop_id=sid))
    j["_enriched"] = True
    return j


def enrich_all(journeys, stop_safety=None):
    for j in journeys:
        enrich(j, stop_safety)
    return journeys
