"""
Route planning and preference-based ranking.

plan(origin, destination, t) finds bus journeys with 0 or 1 change, plus walking,
and returns them with simple numbers a student can compare:
    fare (Rs), time (minutes from now until arrival), walk (minutes), changes.

rank(journeys, mode, limits) decides which journey is Cheapest / Fastest / Simplest /
Least walking and which one to recommend for the user's chosen priority.
"""
import math

from .network import OTHER_MODES, distance_m, fare_for_km, walk_minutes

MAX_ACCESS_WALK = 20     # minutes to walk to the first stop / from the last stop
TRANSFER_BUFFER = 2      # minutes needed to change buses
MAX_TRANSFER_WAIT = 45
MAX_RESULTS = 5      # more choices than this adds cognitive load

MODES = {
    "balanced": dict(label="Balanced", icon="😌", situation="Normal day", blurb="A sensible mix of time, money and effort."),
    "fastest": dict(label="Fastest", icon="⚡", situation="I'm in a hurry", blurb="Get me there as early as possible."),
    "cheapest": dict(label="Cheapest", icon="💰", situation="I'm saving money", blurb="Spend as little as possible."),
    "simplest": dict(label="Simplest", icon="🧘", situation="Keep it simple", blurb="One bus if possible. No confusing changes."),
    "walking": dict(label="Least walking", icon="🚶", situation="Less walking", blurb="Keep walking to a minimum."),
}

# Tie-break order for each label (spec section 15)
CRITERIA = {
    "cheapest": ("fare", "time", "walk"),
    "fastest": ("time", "changes", "fare"),
    "simplest": ("changes", "walk", "time"),
    "walking": ("walk", "changes", "time"),
}

WEIGHTS = {
    "balanced": dict(time=0.4, fare=0.2, walk=0.2, changes=0.2),
    "fastest": dict(time=0.7, fare=0.1, walk=0.1, changes=0.1),
    "cheapest": dict(time=0.15, fare=0.7, walk=0.075, changes=0.075),
    "simplest": dict(time=0.15, fare=0.1, walk=0.2, changes=0.55),
    "walking": dict(time=0.15, fare=0.05, walk=0.6, changes=0.2),
}


class Planner:
    def __init__(self, net):
        self.net = net

    # ------------------------------------------------------------ helpers
    def _stop_point(self, sid):
        s = self.net.stops[sid]
        return dict(id=f"stop:{sid}", stop_id=sid, name=s["name"], lat=s["lat"], lng=s["lng"])

    def _bus_leg(self, p, i, j, trip_start):
        km = max(0.1, p.km_at[j] - p.km_at[i])
        a, b = p.shape_idx[i], p.shape_idx[j]
        return dict(
            type="bus", route=p.no, route_name=p.route["name"], pattern=p.id, headsign=p.headsign,
            board=self._stop_point(p.stops[i]), alight=self._stop_point(p.stops[j]),
            depart=round(trip_start + p.offsets[i]), arrive=round(trip_start + p.offsets[j]),
            n_stops=j - i, via=[self.net.stops[s]["name"] for s in p.stops[i + 1:j]],
            km=round(km, 1), fare=fare_for_km(km), every=p.every_text,
            last_trip=p.is_last_trip(trip_start), board_i=i,
            line=p.shape[a:b + 1] if b > a else [p.shape[a], p.shape[b]],
        )

    @staticmethod
    def _walk_leg(a, b, minutes):
        return dict(type="walk", start=dict(name=a["name"], lat=a["lat"], lng=a["lng"]),
                    end=dict(name=b["name"], lat=b["lat"], lng=b["lng"]), minutes=minutes,
                    meters=round(distance_m(a["lat"], a["lng"], b["lat"], b["lng"]) * 1.3, -1))

    def _journey(self, origin, dest, t, buses, w_access, w_transfer, w_egress):
        legs = []
        first, last = buses[0], buses[-1]
        if w_access:
            legs.append(self._walk_leg(origin, first["board"], w_access))
        legs.append(first)
        wait = 0
        if len(buses) == 2:
            second = buses[1]
            if w_transfer:
                legs.append(self._walk_leg(first["alight"], second["board"], w_transfer))
            wait = second["depart"] - first["arrive"] - w_transfer
            second["wait"] = wait
            legs.append(second)
        if w_egress:
            legs.append(self._walk_leg(last["alight"], dest, w_egress))
        leave = first["depart"] - w_access
        arrive = last["arrive"] + w_egress
        return dict(
            legs=legs, leave=leave, arrive=arrive, time=arrive - t, duration=arrive - leave,
            fare=sum(b["fare"] for b in buses), walk=w_access + w_transfer + w_egress,
            changes=len(buses) - 1, wait_change=wait, routes=[b["route"] for b in buses],
            key="|".join(f"{b['pattern']}@{b['board']['stop_id']}>{b['alight']['stop_id']}" for b in buses),
        )

    # ------------------------------------------------------------ planning
    def plan(self, origin, dest, t):
        net = self.net
        access = dict(net.stops_near(origin, MAX_ACCESS_WALK))
        egress = dict(net.stops_near(dest, MAX_ACCESS_WALK))
        # patterns that can drop us near the destination: pattern id -> [(index, walk)]
        drop = {}
        for sid, w in egress.items():
            for p, j in net.at_stop.get(sid, []):
                drop.setdefault(p.id, []).append((j, w))

        found = []
        for sid, wa in access.items():
            for p, i in net.at_stop.get(sid, []):
                start = p.trip_start(i, t + wa)
                if start is None:
                    continue
                # direct
                for j, we in drop.get(p.id, []):
                    if j > i:
                        found.append(self._journey(origin, dest, t, [self._bus_leg(p, i, j, start)], wa, 0, we))
                # one change
                for k in range(i + 1, len(p.stops)):
                    x = p.stops[k]
                    if x in egress:
                        continue  # would just walk from here
                    arr_x = start + p.offsets[k]
                    for y, wt in net.neighbours.get(x, []):
                        for q, m in net.at_stop.get(y, []):
                            if q.no == p.no or q.id not in drop:
                                continue
                            ends = [(n, we) for n, we in drop[q.id] if n > m]
                            if not ends:
                                continue
                            s2 = q.trip_start(m, arr_x + wt + TRANSFER_BUFFER)
                            if s2 is None or (s2 + q.offsets[m]) - arr_x > MAX_TRANSFER_WAIT:
                                continue
                            for n, we in ends:
                                found.append(self._journey(
                                    origin, dest, t,
                                    [self._bus_leg(p, i, k, start), self._bus_leg(q, m, n, s2)], wa, wt, we))
        journeys = self._prune(found)
        walk_only = None
        wm = walk_minutes(origin, dest)
        if wm <= 35:
            walk_only = dict(legs=[self._walk_leg(origin, dest, wm)], time=wm, walk=wm, fare=0, changes=0,
                             leave=t, arrive=t + wm, duration=wm, routes=[], key="walk")
        return dict(journeys=journeys, walk_only=walk_only, others=self.other_modes(origin, dest),
                    near_origin=len(access), near_dest=len(egress))

    @staticmethod
    def _prune(js):
        best = {}
        for j in js:  # identical trip & stops: keep earliest arrival
            if j["key"] not in best or j["arrive"] < best[j["key"]]["arrive"]:
                best[j["key"]] = j
        js = list(best.values())

        def dominates(a, b):
            ge = all(a[k] <= b[k] for k in ("time", "fare", "walk", "changes", "duration"))
            return ge and any(a[k] < b[k] for k in ("time", "fare", "walk", "changes", "duration"))

        js = [j for j in js if not any(dominates(o, j) for o in js if o is not j)]
        # Same bus numbers twice is noise unless the second saves real walking.
        js.sort(key=lambda j: (j["time"], j["walk"]))
        kept, out = {}, []
        for j in js:
            sig = tuple(j["routes"])
            prev = kept.setdefault(sig, [])
            if not prev or (len(prev) < 2 and all(p["walk"] - j["walk"] >= 3 for p in prev)):
                prev.append(j)
                out.append(j)
        return out[:MAX_RESULTS * 2]

    # ------------------------------------------------------------ ranking
    @staticmethod
    def limit_issues(j, limits):
        issues = []
        if limits.get("budget") is not None and j["fare"] > limits["budget"]:
            issues.append(f"Costs ₹{j['fare']}, over your ₹{limits['budget']} budget")
        if limits.get("walk") is not None and j["walk"] > limits["walk"]:
            issues.append(f"{j['walk']} min walking, more than your {limits['walk']} min limit")
        if limits.get("changes") is not None and j["changes"] > limits["changes"]:
            issues.append("Needs a bus change" if limits["changes"] == 0 else f"{j['changes']} bus changes")
        return issues

    def rank(self, journeys, mode="balanced", limits=None):
        limits = limits or {}
        for j in journeys:
            j["issues"] = self.limit_issues(j, limits)
            j["labels"] = []
        fits = [j for j in journeys if not j["issues"]]
        misfits = [j for j in journeys if j["issues"]]
        pool = fits or []
        for label, keys in CRITERIA.items():
            if pool:
                min(pool, key=lambda j: tuple(j[k] for k in keys))["labels"].append(label)
        if pool:
            w = WEIGHTS.get(mode, WEIGHTS["balanced"])
            span = {k: (min(j[k] for j in pool), max(j[k] for j in pool)) for k in w}
            for j in pool:
                j["score"] = sum(w[k] * ((j[k] - span[k][0]) / (span[k][1] - span[k][0]) if span[k][1] > span[k][0] else 0)
                                 for k in w)
            if mode in CRITERIA:
                pool.sort(key=lambda j: tuple(j[k] for k in CRITERIA[mode]) + (j["score"],))
            else:
                pool.sort(key=lambda j: j["score"])
        pool = pool[:MAX_RESULTS]
        rec = pool[0] if pool else None
        for j in journeys:
            j["warnings"] = self.warnings(j)
        return dict(recommended=rec, options=pool, misfits=misfits[:4])

    @staticmethod
    def warnings(j):
        out = []
        for leg in j["legs"]:
            if leg["type"] == "walk" and leg["minutes"] >= 12:
                out.append(f"Long walk: {leg['minutes']} min ({int(leg['meters'])} m)")
            if leg["type"] == "bus":
                if leg.get("wait") is not None and leg["wait"] <= 3:
                    out.append(f"Tight change: only {leg['wait']} min to catch bus {leg['route']}")
                if leg.get("wait") is not None and leg["wait"] >= 25:
                    out.append(f"Long wait of ~{leg['wait']} min for bus {leg['route']}")
                if leg["last_trip"]:
                    out.append(f"This is the last bus {leg['route']} today. Don't miss it.")
        return out

    @staticmethod
    def reason(j, mode):
        if mode == "cheapest":
            return f"Lowest fare: ₹{j['fare']}"
        if mode == "fastest":
            return f"Gets you there first, in about {j['time']} min"
        if mode == "simplest":
            return "One bus, no changes" if j["changes"] == 0 else "Fewest bus changes"
        if mode == "walking":
            return f"Only {j['walk']} min of walking"
        return "Best balance of time, money and walking"

    @staticmethod
    def tradeoff(rec, options):
        """One plain sentence comparing the recommendation with the main alternative."""
        if not rec or len(options) < 2:
            return None
        fastest = min(options, key=lambda j: j["time"])
        cheapest = min(options, key=lambda j: j["fare"])
        other = fastest if fastest is not rec else cheapest
        if other is rec:
            return None
        dt, df = rec["time"] - other["time"], rec["fare"] - other["fare"]
        parts = []
        if df < 0:
            parts.append(f"saves ₹{-df}")
        elif df > 0:
            parts.append(f"costs ₹{df} more")
        if dt > 0:
            parts.append(f"takes {dt} min longer")
        elif dt < 0:
            parts.append(f"is {-dt} min quicker")
        if not parts:
            return None
        name = "the fastest option" if other is fastest else "the cheapest option"
        return f"Compared with {name}, this " + " and ".join(parts) + "."

    # ------------------------------------------------------------ other modes
    @staticmethod
    def other_modes(a, b):
        km = distance_m(a["lat"], a["lng"], b["lat"], b["lng"]) * 1.35 / 1000
        out = []
        for m in OTHER_MODES:
            lo = m["base"] + m["per_km"] * km
            out.append(dict(m, low=int(5 * round(lo / 5)), high=int(5 * round(lo * 1.35 / 5)),
                            minutes=round(km / m["speed"] * 60) + 5, km=round(km, 1)))
        return out

    # ------------------------------------------------------------ stops
    def departures(self, sid, t, window=90, per_pattern=3):
        out = []
        for p, i in self.net.at_stop.get(sid, []):
            if i == len(p.stops) - 1:
                continue  # bus terminates here
            start = p.trip_start(i, t)
            n = 0
            while start is not None and start <= p.end and n < per_pattern:
                when = round(start + p.offsets[i])
                if when - t > window:
                    break
                out.append(dict(route=p.no, headsign=p.headsign, time=when, every=p.every_text,
                                pattern=p.id, last=p.is_last_trip(start)))
                start += p.headway
                n += 1
        return sorted(out, key=lambda d: d["time"])

    def route_summaries(self, sid):
        """For a stop: each pattern passing it, with frequency and where it goes next."""
        out = []
        for p, i in self.net.at_stop.get(sid, []):
            if i == len(p.stops) - 1:
                continue
            first, last = p.first_last_at(i)
            out.append(dict(route=p.no, name=p.route["name"], headsign=p.headsign, every=p.every_text,
                            first=round(first), last=round(last), pattern=p.id,
                            next_stops=[self.net.stops[s]["name"] for s in p.stops[i + 1:i + 6]],
                            reach=list(p.stops[i + 1:])))
        return out

    def explore(self, origin, t, kind, value, places):
        rows = []
        for pl in places:
            if distance_m(origin["lat"], origin["lng"], pl["lat"], pl["lng"]) < 400:
                continue
            res = self.plan(origin, pl, t)
            js = res["journeys"]
            if kind == "budget":
                ok = sorted([j for j in js if j["fare"] <= value], key=lambda j: (j["fare"], j["time"]))
            else:
                ok = sorted([j for j in js if j["time"] <= value], key=lambda j: (j["time"], j["fare"]))
            pick = ok[0] if ok else None
            if not pick and res["walk_only"] and (kind == "budget" or res["walk_only"]["time"] <= value):
                pick = res["walk_only"]
            best_any = min(js, key=lambda j: (j["fare"], j["time"])) if js else None
            rows.append(dict(place=pl, journey=pick, fallback=best_any))
        reach = sorted([r for r in rows if r["journey"]], key=lambda r: (r["journey"]["time"]))
        out = [r for r in rows if not r["journey"]]
        return reach, out


def fmt_time(m):
    if m is None:
        return ""
    m = int(round(m)) % 1440
    h, mm = divmod(m, 60)
    suffix = "AM" if h < 12 else "PM"
    return f"{(h % 12) or 12}:{mm:02d} {suffix}"


def fmt_dur(m):
    m = int(round(m))
    if m < 60:
        return f"{m} min"
    h, mm = divmod(m, 60)
    return f"{h} h {mm} min" if mm else f"{h} h"


def isfinite(x):
    return x is not None and not math.isinf(x)
