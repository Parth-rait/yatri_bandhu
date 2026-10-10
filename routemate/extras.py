"""
Add-on features as a separate Flask blueprint, with their own database tables:

    /passes                      official CTU fares & passes + student pass advisor
    /book  ->  /tickets/<id>     pre-booked ticket flow (DEMO: no payment, not valid for travel)
    /trip/<id>/share  ->  /s/<token>   share a live trip with a friend (read-only page)
    /stop/<id>/report            "Did you feel safe here?" stop reports (lighting, CCTV, crowd)

Nothing here changes the planner or the existing pages. app.py registers it with init_extras().
"""
import json
import secrets
import time
from datetime import datetime

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from . import store
from .enrich import EXTRAS, ELECTRIC, SAFETY

bp = Blueprint("extras", __name__)
H = {}   # helpers from app.py (find_journey, parse_point, journey_map_data, fmt_time, TZ, net)

SCHEMA = """
CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, uid TEXT, trip_id TEXT, created REAL);
CREATE TABLE IF NOT EXISTS bookings (id TEXT PRIMARY KEY, uid TEXT, summary TEXT, passengers TEXT, total INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS stop_reports (id TEXT PRIMARY KEY, uid TEXT, stop_id TEXT, felt_safe INTEGER, lit INTEGER,
    cctv INTEGER, crowd TEXT, night INTEGER, created REAL);
"""


def db():
    con = store.connect()
    con.executescript(SCHEMA)
    return con


def init_extras(app, **helpers):
    H.update(helpers)
    app.register_blueprint(bp)


# ---------------------------------------------------------------- fares
def fare_for(km, ac=False):
    for slab in EXTRAS["fares"]["ac" if ac else "non_ac"]:
        if slab["upto_km"] is None or km <= slab["upto_km"]:
            return slab["fare"]


def concession_price(fare, discount):
    """Half tickets round 50 paise up to Rs 1 (per the notification)."""
    import math
    return int(math.ceil(fare * (100 - discount) / 100))


# ---------------------------------------------------------------- stop safety reports
def stop_safety(stop_id):
    """Aggregate of student reports for a stop, or None if there aren't enough reports yet."""
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM stop_reports WHERE stop_id=?", (stop_id,))]
    if len(rows) < SAFETY["min_reports_to_show"]:
        return None
    n = len(rows)
    pct = lambda k: round(100 * sum(1 for r in rows if r[k] == 1) / n)
    busy = sum(1 for r in rows if r["crowd"] == "busy")
    return dict(n=n, felt_safe=pct("felt_safe"), lit=pct("lit"), cctv=pct("cctv"),
                crowd="usually busy" if busy * 2 >= n else "often quiet")


@bp.route("/stop/<path:sid>/report", methods=["GET", "POST"])
def stop_report(sid):
    s = H["net"].stops.get(sid.removeprefix("stop:"))
    if not s:
        abort(404)
    if request.method == "POST":
        yn = lambda k: {"yes": 1, "no": 0}.get(request.form.get(k))
        now = datetime.now(H["TZ"])
        with db() as con:
            con.execute("INSERT INTO stop_reports VALUES (?,?,?,?,?,?,?,?,?)",
                        (store.new_id(), g.uid, s["id"], yn("felt_safe"), yn("lit"), yn("cctv"),
                         request.form.get("crowd"), int(now.hour >= 19 or now.hour < 6), time.time()))
        return redirect(url_for("stop", sid=s["id"], reported=1))
    return render_template("stop_report.html", s=s)


# ---------------------------------------------------------------- passes & fares
@bp.route("/passes")
def passes():
    trips = [t for t in store.trips(g.uid, 300) if t["status"] in ("done", "active")]
    month_start = datetime.now(H["TZ"]).replace(day=1, hour=0, minute=0, second=0).timestamp()
    this_month = [t for t in trips if t["started"] >= month_start]
    spent = sum(t["summary"]["fare"] for t in this_month)
    avg = round(sum(t["summary"]["fare"] for t in trips) / len(trips)) if trips else 25
    student_all = next(p for p in EXTRAS["passes"] if p["id"] == "student_all")
    breakeven = -(-student_all["price"] // max(avg, 1))   # ceil
    return render_template("passes.html", fares=EXTRAS["fares"], passes=EXTRAS["passes"], notes=EXTRAS["pass_notes"],
                           n_month=len(this_month), spent=spent, avg=avg, breakeven=breakeven, student_all=student_all)


# ---------------------------------------------------------------- pre-booked tickets (demo)
@bp.route("/book", methods=["GET", "POST"])
def book():
    args = request.form if request.method == "POST" else request.args
    origin, dest, t, j = H["find_journey"](args)
    if not j:
        return redirect(url_for("app_home"))
    buses = [l for l in j["legs"] if l["type"] == "bus"]
    base = sum(fare_for(l["km"]) for l in buses)
    types = EXTRAS["fares"]["concessions"]
    if request.method == "POST":
        pax, total = [], 0
        for c in types:
            n = max(0, min(9, int(request.form.get(c["id"], 0) or 0)))
            if n:
                price = concession_price(base, c["discount"])
                pax.append(dict(type=c["label"], n=n, each=price))
                total += n * price
        if not pax:
            return redirect(url_for("extras.book", **{k: v for k, v in args.items()}))
        bid = store.new_id()
        summary = dict(origin=origin["name"], dest=dest["name"], routes=j["routes"], leave=j["leave"], arrive=j["arrive"],
                       electric=any(l["route"] in ELECTRIC for l in buses))
        with db() as con:
            con.execute("INSERT INTO bookings VALUES (?,?,?,?,?,?)",
                        (bid, g.uid, json.dumps(summary), json.dumps(pax), total, time.time()))
        return redirect(url_for("extras.ticket", bid=bid))
    return render_template("book.html", origin=origin, dest=dest, j=j, base=base, types=types,
                           params={k: v for k, v in args.items()}, concession_price=concession_price)


@bp.route("/tickets/<bid>")
def ticket(bid):
    import qrcode
    import qrcode.image.svg
    with db() as con:
        r = con.execute("SELECT * FROM bookings WHERE id=? AND uid=?", (bid, g.uid)).fetchone()
    if not r:
        abort(404)
    sm, pax = json.loads(r["summary"]), json.loads(r["passengers"])
    text = f"YATRI BANDHU DEMO TICKET (NOT VALID FOR TRAVEL) {bid} | Bus {'+'.join(sm['routes'])} | Rs {r['total']}"
    qr = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=1).to_string(encoding="unicode")
    return render_template("ticket_demo.html", b=dict(r), sm=sm, pax=pax, qr=qr)


@bp.route("/tickets")
def tickets():
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM bookings WHERE uid=? ORDER BY created DESC", (g.uid,))]
    for r in rows:
        r["summary"] = json.loads(r["summary"])
    return render_template("tickets.html", rows=rows)


# ---------------------------------------------------------------- share a live trip
@bp.route("/trip/<tid>/share")
def share(tid):
    trip = store.trip(g.uid, tid)
    if not trip:
        abort(404)
    with db() as con:
        row = con.execute("SELECT token FROM shares WHERE uid=? AND trip_id=?", (g.uid, tid)).fetchone()
        token = row["token"] if row else secrets.token_urlsafe(9)
        if not row:
            con.execute("INSERT INTO shares VALUES (?,?,?,?)", (token, g.uid, tid, time.time()))
    return render_template("share.html", trip=trip, link=url_for("extras.shared", token=token, _external=True))


@bp.route("/s/<token>")
def shared(token):
    """Read-only view for a friend: where the trip is going and the bus's scheduled position. No personal data."""
    with db() as con:
        row = con.execute("SELECT uid, trip_id FROM shares WHERE token=?", (token,)).fetchone()
        trip = con.execute("SELECT * FROM trips WHERE id=? AND uid=?", (row["trip_id"], row["uid"])).fetchone() if row else None
    if not trip:
        abort(404)
    trip = dict(trip)
    trip["summary"] = json.loads(trip["summary"])
    origin, dest, t, j = H["find_journey"](trip["summary"].get("params", {}))
    if not j:
        abort(404)
    return render_template("trip_shared.html", trip=trip, origin=origin, dest=dest, j=j,
                           map_data=H["journey_map_data"](j, origin, dest))
