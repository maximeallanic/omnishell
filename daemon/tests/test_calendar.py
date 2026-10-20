import time
import unittest
from datetime import datetime, timedelta

from babel import Locale

from omnishell.calendar import CalendarStore
from omnishell.dates import DateReader
from omnishell.google_api import GoogleApi
from tests.fake_google import FakeGoogle, FakeTokens

FR_FR = Locale.parse("fr_FR")
NOW = datetime(2026, 10, 3, 10, 0)


def ev(id_, summary, start, location=None, all_day=False):
    e = {"id": id_, "summary": summary, "htmlLink": f"https://cal/{id_}"}
    if location:
        e["location"] = location
    e["start"] = {"date": start.date().isoformat()} if all_day else {"dateTime": start.astimezone().isoformat()}
    return e


class Clock:
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t


class TestCalendar(unittest.TestCase):
    def setUp(self):
        self.g = FakeGoogle()
        self.api = GoogleApi(FakeTokens(), tasks_base=self.g.url, cal_base=self.g.url, timeout=5)
        self.g.routes[("GET", "/users/me/calendarList")] = (200, {"items": [
            {"id": "c1", "selected": True}, {"id": "c2", "selected": False}, {"id": "c3"}]})
        self.g.routes[("GET", "/calendars/c1/events")] = (200, {"items": [
            ev("e1", "Réunion d'équipe", NOW + timedelta(days=1, hours=4)),
            ev("e2", "Dentiste", NOW + timedelta(days=5), location="Lyon"),
            ev("e3", "Anniversaire", NOW + timedelta(days=1), all_day=True),
        ]})
        self.g.routes[("GET", "/calendars/c3/events")] = (200, {"items": []})
        self.clock = Clock()
        self.store = CalendarStore(self.api, DateReader(["fr"], "DMY", FR_FR), clock=self.clock)

    def tearDown(self):
        self.g.close()

    def test_selected_calendars_only(self):
        self.store.search("reunion", 2)
        self.assertEqual(self.g.made("GET", "/calendars/c2/events"), [])
        self.assertEqual(len(self.g.made("GET", "/calendars/c1/events")), 1)

    def test_calendar_id_is_url_encoded(self):
        self.g.routes[("GET", "/users/me/calendarList")] = (200, {"items": [
            {"id": "fr.french#holiday@group.v.calendar.google.com"}]})
        self.g.routes[("GET", "/calendars/fr.french#holiday@group.v.calendar.google.com/events")] = (200, {"items": [
            ev("h1", "Toussaint", NOW + timedelta(days=29), all_day=True)]})
        self.assertEqual([i["name"] for i in self.store.search("toussaint", 2)], ["Toussaint"])

    def test_follows_next_page_token(self):
        self.g.routes[("GET", "/users/me/calendarList")] = lambda req: (200, {
            "items": [{"id": "c1"}], "nextPageToken": "cp2"} if "pageToken" not in req["query"] else {
            "items": [{"id": "c3"}]})
        self.g.routes[("GET", "/calendars/c3/events")] = lambda req: (200, {
            "items": [ev("e4", "Réunion client", NOW + timedelta(days=2))], "nextPageToken": "ep2"}
            if "pageToken" not in req["query"] else {
            "items": [ev("e5", "Réunion bilan", NOW + timedelta(days=20))]})
        self.assertEqual([i["name"] for i in self.store.search("reunion", 2)],
                         ["Réunion d'équipe", "Réunion client", "Réunion bilan"])
        pages = self.g.made("GET", "/calendars/c3/events")
        self.assertEqual([r["query"].get("pageToken") for r in pages], [None, "ep2"])
        self.assertEqual(pages[1]["query"]["timeMin"], pages[0]["query"]["timeMin"])

    def test_window_30_days_single_events(self):
        self.store.search("reunion", 2)
        q = self.g.made("GET", "/calendars/c1/events")[0]["query"]
        self.assertEqual((q["singleEvents"], q["orderBy"], q["maxResults"]), ("true", "startTime", "250"))
        t0, t1 = datetime.fromisoformat(q["timeMin"]), datetime.fromisoformat(q["timeMax"])
        self.assertEqual(t1 - t0, timedelta(days=30))

    def test_match_title_or_location_accents(self):
        r = self.store.search("reunion", 2)
        self.assertEqual([i["name"] for i in r], ["Réunion d'équipe"])
        self.assertEqual(r[0]["description"], "dim. 4 oct. 14:00")
        self.assertEqual((r[0]["group"], r[0]["kind"], r[0]["url"], r[0]["icon"]),
                         ("agenda", "event", "https://cal/e1", "x-office-calendar-symbolic"))
        self.assertEqual([i["name"] for i in self.store.search("lyon", 2)], ["Dentiste"])

    def test_day_query(self):
        r = self.store.search("demain", 2)
        self.assertEqual([(i["name"], i["description"]) for i in r],
                         [("Anniversaire", "All day"), ("Réunion d'équipe", "14:00")])

    def test_cache_5_min(self):
        self.store.search("reunion", 2)
        self.clock.t = NOW + timedelta(minutes=4)
        self.store.search("reunion", 2)
        self.assertEqual(len(self.g.made("GET", "/calendars/c1/events")), 1)
        self.clock.t = NOW + timedelta(minutes=6)
        self.store.search("reunion", 2)
        self.assertEqual(len(self.g.made("GET", "/calendars/c1/events")), 2)

    def test_prefetch_warms_cache(self):
        self.g.delay = 0.5
        self.store.prefetch()
        self.g.delay = 3
        t0 = time.monotonic()
        self.assertEqual([i["name"] for i in self.store.search("reunion", 0.2)], ["Réunion d'équipe"])
        self.assertLess(time.monotonic() - t0, 0.3)

    def test_goa_glib_error_does_not_stick(self):
        from gi.repository import GLib
        tokens = self.api.tokens
        orig = tokens.token
        def boom():
            raise GLib.Error("GoaError: NotAuthorized")
        tokens.token = boom
        self.assertEqual(self.store.search("reunion", 2), [])
        tokens.token = orig
        self.assertEqual([i["name"] for i in self.store.search("reunion", 2)], ["Réunion d'équipe"])

    def test_timeout_returns_cached_or_empty(self):
        self.g.delay = 3
        t0 = time.monotonic()
        self.assertEqual(self.store.search("reunion", 1.5), [])
        self.assertLess(time.monotonic() - t0, 1.7)
