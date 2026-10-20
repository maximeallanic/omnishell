#!/usr/bin/env python3
"""Omnishell daemon with demo data, for the README screenshots in the nested Shell (dev/screenshots/run.sh).

The real HubService and its real stores, fed by a local fake of the Google APIs (tests/fake_google.py) with
invented tasks and events, a generated browser profile, canned suggestions and a listener that pretends to hear a
sentence. No Google account, no network call, no microphone: nothing personal can reach a screenshot.

Usage: demo_daemon.py   (on the nested session bus; XDG_CONFIG_HOME/XDG_CACHE_HOME must be private)
Environment: OMNISHELL_DEMO_PHRASE  the sentence the fake listener "hears"."""
import json
import logging
import math
import os
import sqlite3
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
# The daemon copied by prepare.sh next to its compiled catalogues (omnishell/i18n.py looks for ../locale), then
# this repository for the test fakes.
sys.path[:0] = [os.path.join(os.environ.get("XDG_DATA_HOME", ""), "omnishell", "daemon"), str(REPO / "daemon")]

from gi.repository import Gio, GLib  # noqa: E402

from omnishell.calendar import CalendarStore  # noqa: E402
from omnishell.chrome import ChromeIndex  # noqa: E402
from omnishell.dates import DateReader  # noqa: E402
from omnishell.google_api import GoogleApi  # noqa: E402
from omnishell.omnibox import load_keywords  # noqa: E402
from omnishell.service import Deps, HubService  # noqa: E402
from omnishell.session_locale import session_locale, wikipedia_language  # noqa: E402
from omnishell.tasks import TaskStore  # noqa: E402
from tests.fake_google import FakeGoogle, FakeTokens  # noqa: E402

log = logging.getLogger("demo")
CHROME_EPOCH = 11644473600  # seconds between 1601-01-01 and 1970-01-01
TODAY = date.today()


def chrome_profile(root: Path):
    """A Chromium-family profile with a few bookmarks and history entries (public sites only)."""
    prof = root / "Default"
    prof.mkdir(parents=True, exist_ok=True)
    (root / "Local State").write_text(json.dumps({"profile": {"last_used": "Default"}}))
    bookmarks = [("GNOME GitLab", "https://gitlab.gnome.org/"), ("GNOME Shell extensions", "https://extensions.gnome.org/"),
                 ("GitHub", "https://github.com/")]
    (prof / "Bookmarks").write_text(json.dumps({"roots": {
        "bookmark_bar": {"type": "folder", "children": [{"type": "url", "name": n, "url": u} for n, u in bookmarks]},
        "other": {"type": "folder", "children": []}}}))
    db = sqlite3.connect(prof / "History")
    db.execute("CREATE TABLE IF NOT EXISTS urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INTEGER,"
               " last_visit_time INTEGER, hidden INTEGER DEFAULT 0)")
    now = time.time()
    rows = [("https://github.com/trending", "Trending repositories on GitHub", 12, now - 3600),
            ("https://docs.gtk.org/gtk4/", "GTK 4 documentation", 30, now - 7200),
            ("https://gjs.guide/extensions/", "GNOME Shell extensions guide", 25, now - 86400)]
    db.executemany("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)",
                   [(u, t, n, int((ts + CHROME_EPOCH) * 1_000_000)) for u, t, n, ts in rows])
    db.commit()
    db.close()


def fake_google() -> FakeGoogle:
    g = FakeGoogle()

    def task(id_, title, days=None, notes=None):
        t = {"id": id_, "title": title, "status": "needsAction", "webViewLink": "https://tasks.google.com/"}
        if days is not None:
            t["due"] = f"{(TODAY + timedelta(days=days)).isoformat()}T00:00:00.000Z"
        if notes:
            t["notes"] = notes
        return t

    def event(id_, summary, days, hour, location=None):
        start = datetime.combine(TODAY + timedelta(days=days), datetime.min.time()).replace(hour=hour)
        e = {"id": id_, "summary": summary, "htmlLink": "https://calendar.google.com/",
             "start": {"dateTime": start.astimezone().isoformat()}}
        if location:
            e["location"] = location
        return e

    g.routes[("GET", "/users/@me/lists")] = (200, {"items": [{"id": "L1", "title": "Personal"}, {"id": "L2", "title": "Work"}]})
    g.routes[("GET", "/lists/L1/tasks")] = (200, {"items": [
        task("a", "Renew passport", -1), task("b", "Buy flowers", 0), task("c", "Book train tickets", 3)]})
    g.routes[("GET", "/lists/L2/tasks")] = (200, {"items": [
        task("d", "Review the release notes", 0), task("e", "Prepare the demo", 1), task("f", "Read the GTK 4.22 notes")]})
    g.routes[("GET", "/users/me/calendarList")] = (200, {"items": [{"id": "demo", "selected": True}]})
    g.routes[("GET", "/calendars/demo/events")] = (200, {"items": [
        event("e1", "Team meeting", 0, 14, "Room 3"), event("e2", "Dentist", 2, 9),
        event("e3", "Release review", 1, 11), event("e4", "Dinner with Sam", 4, 20)]})
    ok = (200, {})
    for list_id, ids in (("L1", "abc"), ("L2", "def")):
        for i in ids:
            g.routes[("PATCH", f"/lists/{list_id}/tasks/{i}")] = ok
    g.routes[("POST", "/lists/L1/tasks")] = lambda req: (200, dict(req["body"] or {}, id="new", status="needsAction"))
    return g


class DemoListener:
    """Pretends to listen: microphone levels for a few seconds (or until Stop), then the demo sentence."""

    def __init__(self, on_state, phrase, seconds=12.0):
        self.on_state, self.phrase, self.seconds = on_state, phrase, seconds
        self._done = threading.Event()
        self._cancelled = False

    def listen(self):
        t0 = time.monotonic()
        while not self._done.is_set() and time.monotonic() - t0 < self.seconds:
            t = time.monotonic() - t0
            self.on_state("listening", 0.35 + 0.3 * abs(math.sin(t * 3.1)) * abs(math.sin(t * 1.3)))
            time.sleep(0.05)
        self.on_state("idle", 0)
        return "" if self._cancelled else self.phrase

    def stop(self):
        self._done.set()

    def cancel(self):
        self._cancelled = True
        self._done.set()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s demo: %(message)s")
    config = Path(GLib.get_user_config_dir())
    cache = Path(GLib.get_user_cache_dir()) / "omnishell"
    bench_tmp = os.environ.get("OMNISHELL_BENCH_TMP", "")
    if not bench_tmp or not str(config).startswith(bench_tmp + "/"):
        sys.exit("demo_daemon.py: refusing to run outside the nested bench (XDG_CONFIG_HOME is not private)")
    chrome_root = config / "chromium"
    chrome_profile(chrome_root)
    g = fake_google()
    api = GoogleApi(FakeTokens(), tasks_base=g.url, cal_base=g.url, timeout=5)
    dates = DateReader.from_session([])
    ui = session_locale("LC_MESSAGES")
    phrase = os.environ.get("OMNISHELL_DEMO_PHRASE", "What is the weather like in Paris tomorrow morning?")
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    deps = Deps(
        tokens=FakeTokens(), chrome=ChromeIndex(root=chrome_root, cache_dir=cache),
        task_store=TaskStore(api, cache / "tasks.json", dates), calendar=CalendarStore(api, dates),
        keywords=load_keywords(None, wikipedia_language(ui)),
        suggest=lambda q: [f"{q} tutorial", f"{q} documentation", f"{q} release date"],
        suggestions_enabled=lambda: True,
        listener_factory=lambda on_state: DemoListener(on_state, phrase),
        open_uri=lambda uri: log.info("open %s", uri), spawn=lambda argv: log.info("spawn %s", argv),
        notify=lambda *a, **k: None, state_dir=cache / "state", summary_hour=23,
        whisper_loaded=lambda: True, watch_network=None)
    loop = GLib.MainLoop()
    service = HubService(bus, deps)
    try:
        loop.run()
    finally:
        service.close()
        g.close()


if __name__ == "__main__":
    main()
