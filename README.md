# Yatri Bandhu

A student-focused travel decision assistant for Chandigarh & Mohali (HCI course project).

> Don't make students understand the transportation system. Make the transportation system understandable to students.

Built with **Python + Flask** (backend, route planning, pages) and **Leaflet** maps with OpenStreetMap data.
Bus data comes from the **CTU time table of local & tri-city routes, as on 25.07.2026** (all 68 routes).

## Run it

```bash
cd Yatri Bandhu
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py              # http://127.0.0.1:5000
```

`data/build/network.json` is already built, so the app runs offline. Only the map tiles need internet.

**Location on a phone:** browsers only share GPS on `https://` or `localhost`. To test "Use my location" on a phone,
expose the laptop with an https tunnel (e.g. `ngrok http 5000`) and open the https link on the phone.

## Screens

Navigation follows the Moovit pattern: five bottom tabs, full-screen search, results as a clean list, and maps only
where they help (journey, live trip, stop/line/nearby/explore map views).

| Area | Screen | URL |
|------|--------|-----|
| Website | Landing page | `/` |
| | Onboarding: usual start + usual priority (2 steps) | `/welcome` |
| **Plan** tab | Home: "Where are you going?", your places, recent, popular | `/app` |
| | Full-screen search (places, stops, current location) | `/search` |
| | Trip setup: from/to, when, what matters most | `/plan` |
| | Route results (best for you + labelled options) | `/routes` |
| | Filters (budget, walking, changes) | `/routes/filters` |
| | Compare side by side | `/routes/compare` |
| | Other ways (walk, bike taxi, auto, cab estimates) | `/routes/other` |
| | Journey: map + numbered itinerary | `/journey` |
| | Live trip: current instruction, "get ready" alert | `/trip/<id>` |
| | Feedback after a trip | `/feedback/<id>` |
| **Stops** tab | Stops near me (list / map) | `/nearby`, `/nearby/map` |
| | Stop: departures / lines here / map | `/stop/<id>`, `/stop/<id>/map` |
| **Lines** tab | All 68 lines with filters | `/lines` |
| | Line: both directions, stop diagram, map | `/line/<no>`, `/line/<no>/map` |
| **Explore** tab | "I have ₹20 / 30 min, where can I go?" (list / map) | `/explore`, `/explore/map` |
| **Me** tab | Hub, saved places, add place, trip history | `/me`, `/saved`, `/saved/new`, `/history` |
| | Route settings (incl. light / dark / auto theme), accessibility | `/settings`, `/accessibility` |
| | How to read Yatri Bandhu (map symbols, glossary), about the data | `/help`, `/about` |
| | Usability test console, SUS questionnaire, CSV export | `/study`, `/sus`, `/export/<table>.csv` |

**Light / dark mode:** the sun/moon button in every page header switches theme. The choice is remembered in a cookie.
Settings → Appearance also has *Auto* (follow the phone).

## Map design rules (used on every map)

- **Bus** = thick solid line in the route's colour. The same colour is used for the route's number badge in the text.
- **Walk** = grey dotted line.
- **Numbered circles 1, 2, 3** = the same numbered steps in the list next to the map. Tapping a step zooms to it.
- Short labels only at decision points: *Start*, *Board 38B*, *Change to 22*, *Get off*, 🏁 destination.
- The basemap is desaturated so it doesn't compete with the route. Dark mode and high contrast are supported.
- The map is never the only source of information. Everything is also in the text steps (for screen readers).

## How it works

```
data/routes_source.py   CTU time table transcribed: stop order, first/last bus, frequency, km, buses
data/gazetteer.py       stop names + OpenStreetMap search hints + manual / derived coordinates
tools/build_data.py     geocode stops, fetch road shapes (OSRM), estimate ride times  -> data/build/network.json
routemate/network.py    loads routes into directional "patterns" with an even timetable
routemate/planner.py    finds direct + 1-change journeys with walking, ranks them, explains trade-offs
routemate/store.py      SQLite: saved places, trips, feedback, usability-test logs, SUS scores
app.py                  Flask pages + small JSON API (/api/search, /api/plan)
templates/, static/     UI: Jinja templates, one CSS design system (light/dark tokens), Leaflet map code
```

Ranking (spec section 15): each option gets labels by tie-break order. *Cheapest* = fare → time → walk,
*Fastest* = time → changes → fare, *Simplest* = changes → walk → time, *Least walking* = walk → changes → time.
"Balanced" uses a weighted score. Limits (budget, walking, changes) never hide options silently.
Options outside the limits move to an "outside your limits" section that says why.

## What is estimated (be honest about this in the report)

- **Times are not live.** The time table gives first/last bus and frequency, so departures are spread evenly in that window.
  Ride time = route length at ~21 km/h, split over stops by road distance.
- **Stop locations are approximate.** Junctions like "22/17" are placed between the two sector centres.
  Places OSM couldn't find are marked `# est` in `data/gazetteer.py`. Please verify them.
- **Fares:** approximate CTU non-AC slabs (₹10 ≤5 km, ₹20 5–10 km, ₹25 >10 km). Check the current CTU notification.
- **Bike taxi / auto / cab:** rough distance-based estimates, clearly labelled. Not prices from any app.
- Route 38AB's printed hours (00:40–22:10) were copied as printed. They look like a typo in the source.

## Changing the data

1. Edit `data/routes_source.py` (stops use tokens such as `22/17`, `S35`, `M82`, `ISBT43`).
2. New landmark? Add it to `LANDMARKS` (and `MANUAL_COORDS` if OSM can't find it) in `data/gazetteer.py`.
3. Run `.venv/bin/python tools/build_data.py` (results are cached in `data/cache/`, so re-runs are fast).

## Usability testing workflow

1. Settings → *Usability test console* → enter participant ID, pick task (T1–T5 from the spec), *Start*.
2. Hand over the phone. A purple bar times the task and counts taps on every screen. The observer taps *+ error* when needed.
3. *Done* / *Gave up* → participant rates confidence 1–5 → saved.
4. After all tasks: *SUS questionnaire*. Export CSVs for analysis.

## Add-on features (safety, green, passes, booking)

Built as add-ons so the planner and existing pages stay unchanged:

| File | What it does |
|------|--------------|
| `data/extras.json` | Electric routes (23A, 206, 202, 239, 6, 7), official CTU fares & passes (notification of 16 Jan 2020), helplines, night hours, CO₂ factors |
| `routemate/enrich.py` | Runs *after* planning: electric tags, CO₂ saved vs cab, after-dark notes, stop safety summaries. Never changes routes, fares or ranking |
| `routemate/extras.py` | Blueprint with its own tables: `/passes`, `/book` → `/tickets/<id>` (demo), `/trip/<id>/share` → `/s/<token>`, `/stop/<id>/report` |
| `routemate/live.py` | Plug-in point for an official real-time feed (CTU API / GTFS-Realtime). Defaults to timetable only |

- **Women's safety:** SOS (112) and women helpline (1091) on the trip screen, share-live-trip link, after-dark notes, and student stop reports (felt safe / lit / CCTV / busy). Ratings only show after 3+ reports.
- **Green:** electric bus badges and CO₂ saved per trip.
- **Passes & fares:** official fare slabs and passes, with a student pass break-even check from your trip history.
- **Pre-booked tickets:** full flow with official concessions (child/senior 50%, half-ticket rounding). **Demo only:** no payment, not valid for travel. Real booking needs CTU's ticketing/payment system.
- **Live ETAs:** not scraped. Implement `CTULiveFeed` in `routemate/live.py` once official access is available.

To switch the add-ons off: remove the `enrich_all`/`enrich` calls and `init_extras(...)` in `app.py`.

## Smart bikes (first / last mile)

`routemate/bikes.py` + `data/bike_docks.json`. When a trip has a walk of 7+ minutes and there's a bike-share dock near both ends,
route detail suggests riding instead ("Smart bike: save 3 min"), and the map shows pick-up/drop docks. Short trips with docks at
both ends get a "Smart bike" option on the Auto/Cab tab, and Nearby lists docks around you.

Docks are seeded from OpenStreetMap: 11 Panchkula municipal bike stations + 5 Chandigarh SmartBike docks. Chandigarh's
hundreds of other SmartBike docks aren't on OpenStreetMap, and SmartBike publishes no open data feed (GBFS). **Add docks to
`data/bike_docks.json`** (id, name, lat, lng, operator, city) and the feature appears there automatically. Bikes are never
required for a trip, since there is no live availability.
