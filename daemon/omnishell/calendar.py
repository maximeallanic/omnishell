"""Google Calendar for the search: events of the next 30 days, cached for 5 minutes."""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date, datetime, timedelta
from urllib.parse import quote

from .i18n import _
from .text import matches

log = logging.getLogger(__name__)

CACHE_S = 300
WINDOW = timedelta(days=30)


class CalendarStore:
    def __init__(self, api, dates, clock=datetime.now):
        self.api = api
        self.dates = dates
        self.clock = clock
        self._events: list[dict] = []
        self._fetched_at = None
        self._future = None
        self._pool = ThreadPoolExecutor(max_workers=1)

    def _fetch(self) -> list[dict]:
        base = self.api.cal_base
        now = self.clock().astimezone()
        params = {"timeMin": now.isoformat(), "timeMax": (now + WINDOW).isoformat(),
                  "singleEvents": "true", "orderBy": "startTime", "maxResults": "250"}
        events = []
        for cal in self._items(f"{base}/users/me/calendarList"):
            if cal.get("selected") is False:
                continue
            for e in self._items(f"{base}/calendars/{quote(cal['id'], safe='@')}/events", params):
                start = e.get("start", {})
                if "dateTime" in start:
                    when = datetime.fromisoformat(start["dateTime"]).astimezone().replace(tzinfo=None)
                elif "date" in start:
                    when = date.fromisoformat(start["date"])
                else:
                    continue
                events.append({"id": f"event:{cal['id']}:{e['id']}", "summary": e.get("summary", ""),
                               "location": e.get("location", ""), "start": when,
                               "url": e.get("htmlLink", "")})
        return events

    def _items(self, url: str, params: dict | None = None):
        """Every item of a paged list, following nextPageToken until the last page."""
        token = None
        while True:
            page = self.api.get(url, {**(params or {}), **({"pageToken": token} if token else {})})
            yield from page.get("items", [])
            token = page.get("nextPageToken")
            if not token:
                return

    def _sort_key(self, e):
        s = e["start"]
        return (s if isinstance(s, datetime) else datetime.combine(s, datetime.min.time()),
                isinstance(s, datetime))

    def _ensure(self, timeout: float):
        fresh = self._fetched_at and (self.clock() - self._fetched_at).total_seconds() < CACHE_S
        if fresh:
            return
        if self._future is None:
            self._future = self._pool.submit(self._fetch)
        try:
            events = self._future.result(timeout=timeout)
        except FutureTimeout:
            return
        except Exception as e:  # noqa: BLE001 — any error frees the next fetch
            log.info("Calendar unavailable: %s", e)
            self._future = None
            return
        self._future = None
        self._events = sorted(events, key=self._sort_key)
        self._fetched_at = self.clock()

    def prefetch(self, timeout: float = 30) -> None:
        self._ensure(timeout)

    def search(self, query: str, timeout: float) -> list[dict]:
        self._ensure(timeout)
        day = self.dates.day_query(query, self.clock().date())
        out = []
        for e in self._events:
            s = e["start"]
            if day is not None:
                if (s.date() if isinstance(s, datetime) else s) != day:
                    continue
                desc = self.dates.format_time(s) if isinstance(s, datetime) else _("All day")
            elif matches(query, e["summary"], e["location"]):
                desc = self.dates.format_when(s)
            else:
                continue
            out.append({"group": "agenda", "id": e["id"], "name": e["summary"], "description": desc,
                        "icon": "x-office-calendar-symbolic", "kind": "event", "url": e["url"]})
        return out
