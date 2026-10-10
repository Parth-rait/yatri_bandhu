"""
Plug-in point for REAL-TIME bus data.

Today Yatri Bandhu only has the CTU timetable, so every time it shows is a scheduled estimate.
CTU's own portal already shows live ETAs per shelter (e.g. "CH-01-GA-4744  10:17"), which means
the data exists. If the team gets official access (an API / GTFS-Realtime feed through a
government tie-up), implement `CTULiveFeed` below and set FEED = CTULiveFeed(...).

Rules:
  * Use only an official feed you have permission for. Do not scrape the CTU website.
  * Return None when unsure; callers then fall back to the timetable.
"""


class TimetableOnly:
    """Default: no live data. Everything falls back to the timetable."""
    name = "timetable"

    def eta(self, stop_id, route_no):
        """Minutes until the next bus of `route_no` reaches `stop_id`, or None if unknown."""
        return None

    def vehicle_position(self, route_no):
        """(lat, lng) of the nearest live bus on this route, or None."""
        return None


class CTULiveFeed(TimetableOnly):
    """Fill in once official access is available (endpoint, API key, stop/route id mapping)."""
    name = "ctu-live"

    def __init__(self, endpoint, api_key, stop_id_map=None):
        self.endpoint, self.api_key, self.stop_id_map = endpoint, api_key, stop_id_map or {}


FEED = TimetableOnly()
