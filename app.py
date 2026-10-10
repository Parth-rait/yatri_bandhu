"""
Yatri Bandhu — student-centric mobility assistant for Chandigarh & Mohali.

Run:   .venv/bin/python app.py      then open http://127.0.0.1:5000
"""
import csv
import io
import os
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import (Flask, Response, abort, g, jsonify, redirect, render_template, request, session,
                   url_for)

from routemate import store
from routemate.network import Network, distance_m, route_sort_key
from routemate.planner import MODES, Planner, fmt_dur, fmt_time
from routemate.enrich import ELECTRIC, EXTRAS, enrich, enrich_all
from routemate.extras import init_extras, stop_safety

TZ = ZoneInfo("Asia/Kolkata")
app = Flask(__name__)
app.secret_key = os.environ.get("ROUTEMATE_SECRET", "dev-only-change-me")

net = Network()
planner = Planner(net)

STUDY_TASKS = [
    dict(id="T1", text="You have ₹30 and need to reach Sector 17. Find the cheapest route."),
    dict(id="T2", text="You have an appointment and need to reach the railway station as quickly as possible."),
    dict(id="T3", text="Find a route from Plaksha to Mohali Phase 7 that does not require changing buses."),
    dict(id="T4", text="You have ₹20. Find places you can reach from Plaksha."),
    dict(id="T5", text="Find which buses stop closest to where you are standing right now."),
]
SUS_QUESTIONS = [
    "I think that I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to be able to use this system.",
    "I found the various functions in this system were well integrated.",
    "I thought there was too much inconsistency in this system.",
    "I would imagine that most people would learn to use this system very quickly.",
    "I found the system very cumbersome to use.",
    "I felt very confident using the system.",
    "I needed to learn a lot of things before I could get going with this system.",
]
FEEDBACK_ISSUES = ["Bus did not arrive", "Could not find the bus stop", "Too much walking",
                   "Timing was wrong", "Route was confusing", "Fare was different", "Other"]
SAVED_ICONS = ["home", "cap", "briefcase", "star", "bag", "food", "hospital", "train", "tree"]
PLACE_ICON = {"Campus": "cap", "Education": "cap", "Shopping": "bag", "Market": "bag", "Bus terminal": "bus",
              "Transit": "train", "Hospital": "hospital", "Leisure": "tree", "Food": "food", "Work": "briefcase",
              "Junction": "route", "Town": "building"}
# Which bottom tab is highlighted for each page
TABS = {
    "home": {"app_home", "plan", "search", "routes", "routes_filters", "routes_compare", "routes_other",
             "journey", "trip_live", "trip_ticket", "feedback", "extras.book", "extras.share", "extras.ride"},
    "routes": {"lines", "lines_all", "line", "line_map", "nearby", "nearby_map", "stop", "stop_map", "explore",
               "explore_map", "extras.stop_report"},
    "pick": {"extras.pick_map"},
    "saved": {"saved", "saved_new"},
    "profile": {"profile", "extras.passes", "extras.tickets", "extras.ticket", "history", "settings", "settings_start", "accessibility", "help", "about", "study", "sus"},
}


# ---------------------------------------------------------------- points
def place_icon(p):
    return "plane" if "Airport" in p["name"] else PLACE_ICON.get(p["category"], "pin")


def parse_point(s):
    """'place:<id>' | 'stop:<id>' | 'geo:<lat>,<lng>' -> dict(id, name, sub, lat, lng, icon)"""
    if not s:
        return None
    kind, _, val = s.partition(":")
    if kind == "place" and val in net.places:
        p = net.places[val]
        return dict(id=s, name=p["name"], sub=f"{p['category']} · {p['area']}", lat=p["lat"], lng=p["lng"],
                    icon=place_icon(p))
    if kind == "stop" and val in net.stops:
        st = net.stops[val]
        return dict(id=s, name=st["name"], sub=f"Bus stop · {st['area']}", lat=st["lat"], lng=st["lng"], icon="stop",
                    stop_id=val)
    if kind == "geo":
        try:
            lat, lng = map(float, val.split(","))
        except ValueError:
            return None
        near = net.stops_near(dict(lat=lat, lng=lng), 30)
        sub = f"Near {net.stops[near[0][0]]['name']}" if near else "Outside Chandigarh / Mohali"
        return dict(id=s, name="Current location", sub=sub, lat=lat, lng=lng, icon="locate")
    if kind == "poi":
        # a named place from map search / map pin: "poi:<lat>,<lng>|<name>|<subtitle>"
        coords, _, rest = val.partition("|")
        name, _, sub = rest.partition("|")
        try:
            lat, lng = map(float, coords.split(","))
        except ValueError:
            return None
        return dict(id=s, name=(name or "Dropped pin")[:60], sub=(sub or "Chosen on map")[:80], lat=lat, lng=lng, icon="pin")
    return None


def search_points(q, limit=12, kind="all"):
    q = q.strip().lower()
    if not q:
        return []
    out = []
    if kind != "stops":
        for p in net.places.values():
            if q in f"{p['name']} {p['aliases']} {p['category']}".lower():
                out.append((0 if p["name"].lower().startswith(q) else 1, dict(
                    id=f"place:{p['id']}", name=p["name"], sub=f"{p['category']} · {p['area']}", icon=place_icon(p))))
    for s in net.stops.values():
        if q in f"{s['name']} {s['area']}".lower().replace("/", " ") or q in s["name"].lower():
            n = len(net.routes_at_stop.get(s["id"], []))
            out.append((1 if s["name"].lower().startswith(q) else 2, dict(
                id=f"stop:{s['id']}", name=s["name"], icon="stop",
                sub=f"Bus stop · {s['area']} · {n} line{'s' if n != 1 else ''}")))
    out.sort(key=lambda x: (x[0], x[1]["name"]))
    return [o for _, o in out[:limit]]


def safe_ret(ret, default="/app"):
    return ret if ret and ret.startswith("/") and not ret.startswith("//") else default


@app.template_filter("fill")
def fill(ret, point_id):
    """Search results are links: put the chosen point into the return URL."""
    return ret.replace("__PT__", quote(point_id, safe=":,"))


# ---------------------------------------------------------------- request helpers
def now_min():
    n = datetime.now(TZ)
    return n.hour * 60 + n.minute


def req_time(args=None):
    at = (args or request.args).get("at")
    if at:
        try:
            h, m = map(int, at.split(":"))
            return h * 60 + m
        except ValueError:
            pass
    return now_min()


def limits_from_args(args):
    def num(k):
        v = str(args.get(k, ""))
        return int(v) if v.isdigit() else None
    return dict(budget=num("budget"), walk=num("walk"), changes=num("changes"))


def search_args(**over):
    """Current trip-search parameters (for building links), with overrides."""
    keys = ("from", "to", "via", "mode", "budget", "walk", "changes", "at", "trip", "back")
    a = {k: request.args.get(k) for k in keys if request.args.get(k)}
    a.update({k: v for k, v in over.items() if v is not None})
    return {k: v for k, v in a.items() if v != ""}


def journey_map_data(j, origin, dest):
    """Everything the map needs to draw a journey, numbered to match the step list."""
    return dict(origin=origin, dest=dest, legs=[
        dict(type=l["type"], line=l.get("line"), route=l.get("route"), depart=l.get("depart"),
             arrive=l.get("arrive"), start=l.get("start") or l.get("board"), end=l.get("end") or l.get("alight"),
             stops=[[net.stops[x["stop_id"]]["lat"], net.stops[x["stop_id"]]["lng"]] for x in l.get("stops_timed", [])])
        for l in j["legs"]], now=now_min())


def default_mode():
    return g.settings.get("default_mode", "balanced")


@app.before_request
def load_user():
    if request.endpoint == "static":
        return
    if "uid" not in session:
        session["uid"] = store.new_id()
        session.permanent = True
    g.uid = session["uid"]
    g.saved = store.saved_places(g.uid)
    g.settings = store.get_settings(g.uid)


@app.context_processor
def inject():
    ep = request.endpoint or ""
    tab = next((t for t, eps in TABS.items() if ep in eps), None)
    s = g.get("settings", store.DEFAULT_SETTINGS)
    name = (s.get("name") or "").strip()
    initials = "".join(w[0] for w in name.split()[:2]).upper() or None
    return dict(settings=s, MODES=MODES, fmt_time=fmt_time,
                fmt_dur=fmt_dur, active=store.active_trip(g.uid) if g.get("uid") else None, now=now_min(),
                search_args=search_args, endpoint=ep, tab=tab, saved=g.get("saved", []),
                user_name=name, initials=initials, electric_routes=ELECTRIC, helplines=EXTRAS["safety"]["helplines"], fav_points={x["point"] for x in g.get("saved", []) if x["kind"] == "fav"})


@app.template_filter("ago")
def ago(ts):
    d = datetime.fromtimestamp(ts, TZ)
    today = datetime.now(TZ).date()
    if d.date() == today:
        return "Today"
    if d.date() == today - timedelta(days=1):
        return "Yesterday"
    if (today - d.date()).days < 7:
        return d.strftime("%A")
    return d.strftime("%d %b")


def greeting():
    h = datetime.now(TZ).hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


# ---------------------------------------------------------------- landing & onboarding
@app.route("/")
def landing():
    demo = None
    o, d = parse_point("place:plaksha"), parse_point("place:sec17")
    if o and d:
        res = planner.plan(o, d, 9 * 60)
        demo = planner.rank(res["journeys"], "balanced")["options"][:3]
    return render_template("landing.html", demo=demo, n_routes=len(net.routes), n_stops=len(net.stops))


@app.route("/welcome", methods=["GET", "POST"])
def welcome():
    """Two quick questions: your name, and where home is."""
    step = request.args.get("step", "1")
    if request.method == "POST":
        s = g.settings
        if "name" in request.form:
            s["name"] = request.form["name"].strip()[:40]
        home = parse_point(request.form.get("home"))
        if home:
            s["default_from"] = home["id"]
            store.add_saved(g.uid, "Home", "home", home["id"], home["name"], "home")
        if "use_location" in request.form:
            s["use_location"] = request.form["use_location"] == "1"
        if request.form.get("next") in ("2", "3"):
            store.save_settings(g.uid, s)
            return redirect(url_for("welcome", step=request.form["next"]))
        s["onboarded"] = True
        store.save_settings(g.uid, s)
        return redirect(url_for("app_home"))
    home = parse_point(request.args.get("home")) or next(
        (parse_point(x["point"]) for x in g.saved if x["kind"] == "home"), None)
    return render_template("welcome.html", step=step, home=home)


# ---------------------------------------------------------------- planning flow
@app.route("/app")
def app_home():
    origin = parse_point(request.args.get("from") or g.settings.get("default_from"))
    recent, seen = [], set()
    for t in store.trips(g.uid, 20):
        k = (t["origin"], t["dest"])
        if k not in seen:
            seen.add(k)
            recent.append(t)
    home = next((x for x in g.saved if x["kind"] == "home"), None)
    work = next((x for x in g.saved if x["kind"] == "work"), None)
    favs = [x for x in g.saved if x["kind"] == "fav"]
    return render_template("app_home.html", origin=origin, recent=recent[:4], home=home, work=work, favs=favs)


@app.route("/search")
def search():
    ret = safe_ret(request.args.get("ret"), "/plan?to=__PT__")
    kind = request.args.get("kind", "all")
    q = request.args.get("q", "")
    recent_dest = []
    if kind == "all":
        seen = set()
        for t in store.trips(g.uid, 20):
            if t["dest"] not in seen and parse_point(t["dest"]):
                seen.add(t["dest"])
                recent_dest.append(parse_point(t["dest"]))
    if kind == "stops":
        hubs = ["ISBT17", "ISBT43", "PGI", "RLY", "TRIBUNE", "PLAKSHA", "YPS", "MOHALI_ISBT"]
        popular = [parse_point(f"stop:{h}") for h in hubs if h in net.stops]
    else:
        popular = [parse_point(f"place:{p}") for p in net.places][:10]
    from routemate.extras import CATEGORIES, search_places
    near = parse_point(g.settings.get("default_from"))
    places = list(search_places(q.strip().lower(), round(near["lat"], 2), round(near["lng"], 2))) if q and kind != "stops" and near else []
    return render_template("search.html", ret=ret, kind=kind, q=q, places=places, categories=CATEGORIES,
                           near_lat=near["lat"] if near else 30.73, near_lng=near["lng"] if near else 76.78,
                           title=request.args.get("title") or ("Find a stop" if kind == "stops" else "Where to?"),
                           allow_geo=request.args.get("geo", "1") == "1",
                           results=search_points(q, 20, kind) if q else None,
                           recent=recent_dest[:4], popular=popular,
                           saved_pts=[] if kind == "stops" else g.saved)


@app.route("/plan")
def plan():
    origin = parse_point(request.args.get("from") or g.settings.get("default_from"))
    dest = parse_point(request.args.get("to"))
    if not dest:
        return redirect(url_for("search", ret=f"/plan?from={quote(origin['id'], safe=':,') if origin else ''}&to=__PT__"))
    return render_template("plan.html", origin=origin, dest=dest, mode=request.args.get("mode") or default_mode(),
                           at=request.args.get("at", ""))


@app.route("/remember-priority", methods=["POST"])
def remember_priority():
    s = g.settings
    s["ask_priority"] = False
    s["default_mode"] = request.form.get("mode", "balanced")
    store.save_settings(g.uid, s)
    return ("", 204)


def combine_trips(ja, jb, via, t):
    """Join 'origin -> stop' and 'stop -> destination' into one trip with a stopover in the middle."""
    stop_leg = dict(type="via", start=dict(name=via["name"], lat=via["lat"], lng=via["lng"]),
                    end=dict(name=via["name"], lat=via["lat"], lng=via["lng"]), minutes=0, arrive=ja["arrive"])
    return dict(legs=ja["legs"] + [stop_leg] + jb["legs"], leave=ja["leave"], arrive=jb["arrive"],
                time=jb["arrive"] - t, duration=jb["arrive"] - ja["leave"], fare=ja["fare"] + jb["fare"],
                walk=ja["walk"] + jb["walk"], changes=ja["changes"] + jb["changes"], wait_change=0,
                routes=ja["routes"] + jb["routes"], key=f"{ja['key']}~{jb['key']}")


def plan_trip(origin, dest, t, via=None, mode="balanced"):
    """Plan origin -> dest, optionally stopping at `via` on the way. Same result shape as planner.plan."""
    if not via:
        return planner.plan(origin, dest, t)
    first = planner.plan(origin, via, t)
    part_a = planner.rank(first["journeys"], mode)["options"][:3] or ([first["walk_only"]] if first["walk_only"] else [])
    combos, last = [], None
    for ja in part_a:
        last = planner.plan(via, dest, ja["arrive"])
        part_b = planner.rank(last["journeys"], mode)["options"][:2] or ([last["walk_only"]] if last["walk_only"] else [])
        combos += [combine_trips(ja, jb, via, t) for jb in part_b]
    others = []
    for x, y in zip(planner.other_modes(origin, via), planner.other_modes(via, dest)):
        others.append(dict(x, low=x["low"] + y["low"], high=x["high"] + y["high"], minutes=x["minutes"] + y["minutes"],
                           km=round(x["km"] + y["km"], 1)))
    return dict(journeys=combos, walk_only=None, others=others, near_origin=first["near_origin"],
                near_dest=last["near_dest"] if last else first["near_dest"])


def plan_request():
    """Shared by the results sub-pages: parse the trip, plan it and rank it."""
    origin, dest = parse_point(request.args.get("from")), parse_point(request.args.get("to"))
    via = parse_point(request.args.get("via"))
    if not origin or not dest or origin["id"] == dest["id"]:
        return None
    t = req_time()
    mode = request.args.get("mode") or default_mode()
    limits = limits_from_args(request.args)
    if limits["walk"] is None and g.settings.get("max_walk"):
        limits["walk"] = int(g.settings["max_walk"])
    res = plan_trip(origin, dest, t, via, mode)
    enrich_all(res["journeys"], stop_safety)
    ranked = planner.rank(res["journeys"], mode, limits)
    return dict(origin=origin, dest=dest, via=via, t=t, mode=mode, limits=limits, res=res, ranked=ranked)


@app.route("/routes")
def routes():
    ctx = plan_request()
    if not ctx:
        return redirect(url_for("app_home", **search_args()))
    rec = ctx["ranked"]["recommended"]
    n_filters = sum(v is not None for v in ctx["limits"].values())
    shown = ctx["ranked"]["options"] or ctx["ranked"]["misfits"]
    # Round trip: plan the way back (destination -> origin) at the return time, same priority and filters.
    back = None
    if request.args.get("trip") == "round":
        default_back = (ctx["t"] + 180) // 30 * 30
        back_t = req_time({"at": request.args.get("back")}) if request.args.get("back") else default_back
        back_t = min(back_t, 23 * 60 + 30)
        res_b = planner.plan(ctx["dest"], ctx["origin"], back_t)
        enrich_all(res_b["journeys"], stop_safety)
        ranked_b = planner.rank(res_b["journeys"], ctx["mode"], ctx["limits"])
        hhmm = f"{back_t // 60:02d}:{back_t % 60:02d}"
        back = dict(t=back_t, hhmm=hhmm, ranked=ranked_b, res=res_b,
                    args={k: v for k, v in dict(search_args(), **{"from": ctx["dest"]["id"], "to": ctx["origin"]["id"],
                                                                  "at": hhmm}).items() if k not in ("trip", "back", "via")})
    return render_template("routes.html", **ctx, rec=rec, by=request.args.get("by", "bus"), back=back,
                           map_data=journey_map_data(shown[0], ctx["origin"], ctx["dest"]) if shown else
                           dict(origin=ctx["origin"], dest=ctx["dest"], legs=[]),
                           reason=planner.reason(rec, ctx["mode"]) if rec else None,
                           tradeoff=planner.tradeoff(rec, ctx["ranked"]["options"]),
                           n_filters=n_filters, show_all=request.args.get("show") == "all")


@app.route("/routes/filters")
def routes_filters():
    ctx = plan_request()
    if not ctx:
        return redirect(url_for("app_home"))
    return render_template("routes_filters.html", **ctx)


@app.route("/routes/compare")
def routes_compare():
    ctx = plan_request()
    if not ctx:
        return redirect(url_for("app_home"))
    return render_template("routes_compare.html", **ctx)


@app.route("/routes/other")
def routes_other():
    ctx = plan_request()
    if not ctx:
        return redirect(url_for("app_home"))
    return render_template("routes_other.html", **ctx)


def find_journey(args=None):
    args = args or request.args
    origin, dest = parse_point(args.get("from")), parse_point(args.get("to"))
    if not origin or not dest:
        return None, None, None, None
    t = req_time(args)
    res = plan_trip(origin, dest, t, parse_point(args.get("via")), args.get("mode", "balanced"))
    key = args.get("key")
    j = next((x for x in res["journeys"] if x["key"] == key), None)
    if not j and key == "walk":
        j = res["walk_only"]
    if j:
        planner.rank([j], args.get("mode", "balanced"), limits_from_args(args))
        enrich(j, stop_safety)
    return origin, dest, t, j


def later_buses(j):
    first_bus = next((l for l in j["legs"] if l["type"] == "bus"), None)
    if not first_bus:
        return []
    return [d for d in planner.departures(first_bus["board"]["stop_id"], first_bus["depart"] + 1, 120, 3)
            if d["pattern"] == first_bus["pattern"]][:3]


@app.route("/journey")
def journey():
    origin, dest, t, j = find_journey()
    if not j:
        return redirect(url_for("routes", **search_args()))
    return render_template("journey.html", origin=origin, dest=dest, t=t, j=j, later=later_buses(j),
                           map_data=journey_map_data(j, origin, dest), key=request.args.get("key"))


@app.route("/trip/start", methods=["POST"])
def trip_start():
    args = {k: v for k, v in request.form.items() if v}
    origin, dest, t, j = find_journey(args)
    if not j:
        return redirect(url_for("app_home"))
    summary = dict(fare=j["fare"], time=j["time"], walk=j["walk"], changes=j["changes"], routes=j["routes"],
                   leave=j["leave"], arrive=j["arrive"], params=args)
    tid = store.start_trip(g.uid, origin["id"], dest["id"], origin["name"], dest["name"],
                           args.get("mode", "balanced"), summary)
    return redirect(url_for("trip_live", tid=tid))


@app.route("/trip/<tid>")
def trip_live(tid):
    trip = store.trip(g.uid, tid)
    if not trip:
        abort(404)
    if trip["status"] != "active":
        return redirect(url_for("history"))
    origin, dest, t, j = find_journey(trip["summary"].get("params", {}))
    if not j:
        return redirect(url_for("routes", **{"from": trip["origin"], "to": trip["dest"]}))
    return render_template("trip_live.html", trip=trip, origin=origin, dest=dest, j=j,
                           map_data=journey_map_data(j, origin, dest))


@app.route("/trip/<tid>/ticket")
def trip_ticket(tid):
    """A trip pass for the conductor's reference. Not a real ticket: fares are paid on the bus."""
    import qrcode
    import qrcode.image.svg
    trip = store.trip(g.uid, tid)
    if not trip:
        abort(404)
    sm = trip["summary"]
    text = (f"Yatri Bandhu trip pass (not a ticket) | Bus {' + '.join(sm['routes']) or 'walk'} | "
            f"{trip['origin_name']} -> {trip['dest_name']} | Rs {sm['fare']} | {fmt_time(sm['leave'])}")
    text = "https://ctuonline.chd.gov.in/"  # scanning opens the official CTU portal
    svg = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=1).to_string(encoding="unicode")
    return render_template("trip_ticket.html", trip=trip, sm=sm, qr=svg)


@app.route("/trip/<tid>/arrived", methods=["POST"])
def trip_arrived(tid):
    store.set_trip_status(g.uid, tid, "done")
    return redirect(url_for("feedback", tid=tid))


@app.route("/trip/<tid>/cancel", methods=["POST"])
def trip_cancel(tid):
    store.set_trip_status(g.uid, tid, "cancelled")
    return redirect(url_for("app_home"))


@app.route("/feedback/<tid>", methods=["GET", "POST"])
def feedback(tid):
    trip = store.trip(g.uid, tid)
    if not trip:
        abort(404)
    if request.method == "POST":
        rating = int(request.form.get("rating") or 0)
        acc = request.form.get("accurate")
        store.add_feedback(g.uid, tid, rating, None if acc is None else int(acc == "yes"),
                           request.form.getlist("issues"), request.form.get("comment", "").strip()[:1000])
        return render_template("feedback.html", trip=trip, done=True, issues=FEEDBACK_ISSUES)
    return render_template("feedback.html", trip=trip, done=False, issues=FEEDBACK_ISSUES)


# ---------------------------------------------------------------- stops
def nearby_rows(lat, lng):
    here = dict(lat=lat, lng=lng)
    t = now_min()
    rows = []
    for sid, w in net.stops_near(here, 20)[:12]:
        s = net.stops[sid]
        rows.append(dict(s=s, walk=w, meters=round(distance_m(lat, lng, s["lat"], s["lng"]) * 1.3, -1),
                         deps=planner.departures(sid, t + w, 60, 1)[:3], routes=net.routes_at_stop.get(sid, [])))
    return here, rows


def buses_near(lat, lng):
    """'Buses near you': the next bus of each line/direction from the closest stops."""
    t = now_min()
    seen, buses = set(), []
    for sid, w in net.stops_near(dict(lat=lat, lng=lng), 15)[:8]:
        for d in planner.departures(sid, t + w, 75, 1):
            k = d["pattern"]
            if k in seen:
                continue
            seen.add(k)
            s = net.stops[sid]
            buses.append(dict(d, stop=s, walk=w, mins=max(0, d["time"] - t)))
    return sorted(buses, key=lambda b: b["mins"])[:12]


@app.route("/nearby")
def nearby():
    lat, lng = request.args.get("lat", type=float), request.args.get("lng", type=float)
    if lat is None or lng is None:
        return render_template("nearby.html", located=False, demo=net.places.get("plaksha"))
    here, rows = nearby_rows(lat, lng)
    return render_template("nearby.html", located=True, here=here, rows=rows, buses=buses_near(lat, lng))


@app.route("/nearby/map")
def nearby_map():
    return redirect(url_for("nearby", **request.args))


def get_stop(sid):
    sid = sid.removeprefix("stop:")
    s = net.stops.get(sid)
    if not s:
        abort(404)
    return s


@app.route("/stop/<path:sid>")
def stop(sid):
    s = get_stop(sid)
    t = req_time()
    routes_here = planner.route_summaries(s["id"])
    reach = {}
    for r in routes_here:
        for x in r["reach"]:
            reach.setdefault(x, set()).add(r["route"])
    reach_places = [dict(place=p, icon=place_icon(p), routes=sorted(reach[p["stop"]], key=route_sort_key))
                    for p in net.places.values() if p["stop"] in reach and p["stop"] != s["id"]]
    return render_template("stop.html", safety=stop_safety(s["id"]), reported=request.args.get("reported"), s=s, t=t, deps=planner.departures(s["id"], t), routes_here=routes_here,
                           reach_places=reach_places, lines=sorted({r["route"] for r in routes_here}, key=route_sort_key),
                           view=request.args.get("view", "departures"))


@app.route("/stop/<path:sid>/map")
def stop_map(sid):
    s = get_stop(sid)
    routes_here = planner.route_summaries(s["id"])
    lines = [dict(route=r["route"], line=(lambda sh: sh[::5] + [sh[-1]])(net.pattern_by_id[r["pattern"]].shape))
             for r in routes_here if r["pattern"].endswith((":fwd", ":loop"))]
    return render_template("stop_map.html", s=s, lines=lines)


# ---------------------------------------------------------------- lines
def line_area_tags(r):
    areas = {net.stops[s]["area"] for s in r["stops"]}
    tags = []
    if "Chandigarh" in areas:
        tags.append("chd")
    if "Mohali" in areas:
        tags.append("moh")
    if areas & {"Panchkula", "Zirakpur"}:
        tags.append("pkl")
    if r["night"]:
        tags.append("night")
    return tags


POPULAR_LINES = ["38B", "39", "20", "35B", "551", "22"]


def line_row(no):
    r = net.routes[no]
    lo, hi = r["every"]
    a, b = net.stops[r["stops"][0]]["name"], net.stops[r["stops"][-1]]["name"]
    return dict(no=no, name=r["name"], ends="Circular" if r["loop"] else f"{a} – {b}",
                every=f"{lo}" if lo == hi else f"{lo}–{hi}", search=f"{no} {r['name']}".lower())


@app.route("/lines")
def lines():
    return render_template("lines.html", popular=[line_row(n) for n in POPULAR_LINES if n in net.routes],
                           total=len(net.routes))


@app.route("/lines/all")
def lines_all():
    return render_template("lines_all.html", rows=[line_row(n) for n in sorted(net.routes, key=route_sort_key)],
                           q=request.args.get("q", ""))


def line_pattern(no):
    r = net.routes.get(no)
    if not r:
        abort(404)
    d = request.args.get("dir", "loop" if r["loop"] else "fwd")
    p = net.pattern_by_id.get(f"{no}:{d}") or net.pattern_by_id[f"{no}:{'loop' if r['loop'] else 'fwd'}"]
    return r, p


@app.route("/line/<no>")
def line(no):
    r, p = line_pattern(no)
    stops = [dict(id=s, name=net.stops[s]["name"], time=round(o), others=[x for x in net.routes_at_stop.get(s, []) if x != no])
             for s, o in zip(p.stops, p.offsets)]
    other = None if r["loop"] else net.pattern_by_id[f"{no}:{'rev' if p.direction == 'fwd' else 'fwd'}"]
    return render_template("line.html", r=r, p=p, stops=stops, other=other,
                           fwd_head=net.stops[r["stops"][-1]]["name"], rev_head=net.stops[r["stops"][0]]["name"])


@app.route("/line/<no>/map")
def line_map(no):
    r, p = line_pattern(no)
    stops = [dict(id=s, name=net.stops[s]["name"], lat=net.stops[s]["lat"], lng=net.stops[s]["lng"]) for s in p.stops]
    return render_template("line_map.html", r=r, p=p, stops=stops)


# ---------------------------------------------------------------- explore
def explore_ctx():
    origin = parse_point(request.args.get("from") or g.settings.get("default_from"))
    kind = request.args.get("kind", "budget")
    value = request.args.get("value", type=int) or (20 if kind == "budget" else 45)
    t = req_time()
    reach, out = planner.explore(origin, t, kind, value, list(net.places.values())) if origin else ([], [])
    for r in reach + out:
        r["icon"] = place_icon(r["place"])
    return dict(origin=origin, kind=kind, value=value, reach=reach, out=out, t=t)


@app.route("/explore")
def explore():
    return render_template("explore.html", **explore_ctx())


@app.route("/explore/map")
def explore_map():
    return render_template("explore_map.html", **explore_ctx())


# ---------------------------------------------------------------- me
@app.route("/me")
def me():
    return redirect(url_for("profile"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        g.settings["name"] = request.form.get("name", "").strip()[:40]
        store.save_settings(g.uid, g.settings)
        return redirect(url_for("profile"))
    return render_template("profile.html", student_id="RM" + g.uid[:6].upper(), edit=request.args.get("edit"))


@app.route("/logout", methods=["POST"])
def logout():
    """No accounts: logging out (or 'Not you?') starts a fresh profile on this device and asks for a new name."""
    session.clear()
    return redirect(url_for("welcome"))


@app.route("/saved", methods=["GET", "POST"])
def saved():
    if request.method == "POST" and request.form.get("delete"):
        store.delete_saved(g.uid, request.form["delete"])
        return redirect(url_for("saved"))
    return render_template("saved.html")


@app.route("/saved/toggle", methods=["POST"])
def saved_toggle():
    """Star / unstar a place as a favourite to visit."""
    p = parse_point(request.form.get("point"))
    if p:
        store.toggle_favourite(g.uid, p["id"], p["name"])
    return redirect(safe_ret(request.form.get("next"), url_for("saved")))


@app.route("/saved/new", methods=["GET", "POST"])
def saved_new():
    kind = request.values.get("kind", "fav")
    kind = kind if kind in ("home", "work", "fav") else "fav"
    if request.method == "POST":
        p = parse_point(request.form.get("point"))
        label = (request.form.get("label") or "").strip()[:30] or {"home": "Home", "work": "Work"}.get(kind, p["name"] if p else "")
        icon = {"home": "home", "work": "briefcase"}.get(kind, "star")
        if p and label:
            store.add_saved(g.uid, label, icon, p["id"], p["name"], kind)
            if kind == "home":
                g.settings["default_from"] = p["id"]
                store.save_settings(g.uid, g.settings)
            return redirect(url_for("saved"))
    return render_template("saved_new.html", kind=kind, point=parse_point(request.args.get("point")),
                           label=request.args.get("label", ""))


@app.route("/history")
def history():
    groups = {}
    for t in store.trips(g.uid):
        groups.setdefault(ago(t["started"]), []).append(t)
    return render_template("history.html", groups=groups)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    s = g.settings
    if request.method == "POST":
        s["ask_priority"] = request.form.get("ask_priority") == "on"
        s["default_mode"] = request.form.get("default_mode", "balanced")
        mw = request.form.get("max_walk", "")
        s["max_walk"] = int(mw) if mw.isdigit() else None
        store.save_settings(g.uid, s)
        return redirect(url_for("settings", saved=1))
    return render_template("settings.html", just_saved=request.args.get("saved"),
                           default_point=parse_point(s.get("default_from")))


@app.route("/settings/start")
def settings_start():
    p = parse_point(request.args.get("point"))
    if p:
        g.settings["default_from"] = p["id"]
        store.save_settings(g.uid, g.settings)
    return redirect(url_for("settings", saved=1))


@app.route("/accessibility", methods=["GET", "POST"])
def accessibility():
    s = g.settings
    if request.method == "POST":
        for k in ("large_text", "high_contrast", "simple_ui", "reduce_motion"):
            s[k] = request.form.get(k) == "on"
        store.save_settings(g.uid, s)
        return redirect(url_for("accessibility", saved=1))
    return render_template("accessibility.html", just_saved=request.args.get("saved"))


@app.route("/help")
def help():
    return render_template("help.html")


@app.route("/about")
def about():
    return render_template("about.html", source=net.source, n_stops=len(net.stops), n_routes=len(net.routes))


# ---------------------------------------------------------------- evaluation (usability testing)
@app.route("/study")
def study():
    return render_template("study.html", tasks=STUDY_TASKS, results=store.table("study")[-20:])


@app.route("/sus", methods=["GET", "POST"])
def sus():
    score = None
    if request.method == "POST":
        answers = [int(request.form.get(f"q{i}", 3)) for i in range(10)]
        score = store.add_sus(g.uid, request.form.get("participant", "").strip(), answers)
    return render_template("sus.html", questions=SUS_QUESTIONS, score=score)


@app.route("/export/<name>.csv")
def export(name):
    if name not in ("feedback", "study", "sus", "trips"):
        abort(404)
    rows = store.table(name)
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=yatri-bandhu-{name}.csv"})


# ---------------------------------------------------------------- JSON API
@app.route("/api/search")
def api_search():
    return jsonify(search_points(request.args.get("q", ""), 12, request.args.get("kind", "all")))


@app.route("/api/study", methods=["POST"])
def api_study():
    d = request.get_json(force=True)
    store.add_study(g.uid, participant=str(d.get("participant", ""))[:40], task=str(d.get("task", ""))[:10],
                    seconds=float(d.get("seconds", 0)), clicks=int(d.get("clicks", 0)), errors=int(d.get("errors", 0)),
                    outcome=str(d.get("outcome", ""))[:20], confidence=int(d.get("confidence") or 0),
                    path=d.get("path", [])[:200])
    return jsonify(ok=True)


@app.route("/api/plan")
def api_plan():
    """Machine-readable route options (useful for testing the ranking)."""
    origin, dest = parse_point(request.args.get("from")), parse_point(request.args.get("to"))
    if not origin or not dest:
        return jsonify(error="from and to are required, e.g. from=place:plaksha&to=place:sec17"), 400
    res = planner.plan(origin, dest, req_time())
    ranked = planner.rank(res["journeys"], request.args.get("mode", "balanced"), limits_from_args(request.args))
    strip = lambda j: {k: v for k, v in j.items() if k != "legs"} | dict(
        steps=[(l["type"], l.get("route"), l.get("minutes")) for l in j["legs"]])
    return jsonify(recommended=strip(ranked["recommended"]) if ranked["recommended"] else None,
                   options=[strip(j) for j in ranked["options"]])


init_extras(app, find_journey=find_journey, journey_map_data=journey_map_data, parse_point=parse_point,
            net=net, TZ=TZ, safe_ret=safe_ret, plan_request=plan_request, search_args=search_args)


@app.errorhandler(404)
def not_found(e):
    return render_template("not_found.html"), 404


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
