"""D-Bus service io.github.maximeallanic.GoogleHub: search, tasks, voice, daily summary."""
import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from gi.repository import Gio, GLib

from .google_api import ApiError, NoAccountError, OfflineError
from .i18n import _
from .notify import summary_due, summary_text
from .omnibox import google_items, long_enough, search_url
from .voice import CAPTURE_BUDGET_S, CaptureError
from .whisper import TRANSCRIBE_BUDGET_S, TranscribeError

log = logging.getLogger(__name__)

BUS_NAME = "io.github.maximeallanic.GoogleHub"
PATH = "/io/github/maximeallanic/GoogleHub"
IFACE = "io.github.maximeallanic.GoogleHub"
ERR = "io.github.maximeallanic.GoogleHub.Error."
SEARCH_TIMEOUT = 1.5
LISTEN_MARGIN_S = 5  # D-Bus round trips and the hand-off to the worker pool
# Client-side timeout for Listen, published as the ListenTimeout property: every step of a Listen
# is bounded below it, so a client never gives up while the daemon is still working.
LISTEN_TIMEOUT_MS = int((CAPTURE_BUDGET_S + TRANSCRIBE_BUDGET_S + LISTEN_MARGIN_S) * 1000)
REFRESH_S = 300
TASKS_URL = "https://tasks.google.com/"
NODE = Gio.DBusNodeInfo.new_for_xml((Path(__file__).with_name("introspection.xml")).read_text())


def setup_item() -> dict:
    """Search result shown instead of Calendar and Tasks while no Google account is set up."""
    return {"group": "agenda", "id": "setup", "name": _("Connect your Google account"),
            "description": _("Settings → Online Accounts"), "icon": "avatar-default-symbolic",
            "kind": "setup", "url": ""}


class Busy(Exception):
    pass


ERRORS = [(ApiError, "Api"), (OfflineError, "Offline"), (NoAccountError, "NoAccount"),
          (CaptureError, "AudioCapture"), (TranscribeError, "Transcribe"), (Busy, "Busy")]


@dataclass
class Deps:
    tokens: object  # goa.GoaTokens: has_account() never blocks, watch(callback) on account changes
    chrome: object
    task_store: object
    calendar: object
    keywords: dict
    suggest: Callable[[str], list]
    listener_factory: Callable
    open_uri: Callable[[str], None]
    spawn: Callable[[list], None]
    notify: Callable
    state_dir: Path
    summary_hour: int
    whisper_loaded: Callable[[], bool]
    today: Callable[[], date] = date.today
    watch_network: Callable | None = None  # watch_network(callback(online: bool))


def _strs(d: dict) -> dict:
    return {k: GLib.Variant("s", str(v)) for k, v in d.items()}


class HubService:
    def __init__(self, bus, deps: Deps, ctx=None, on_ready=None, start_timers=True):
        self.bus = bus
        self.d = deps
        self.ctx = ctx or GLib.MainContext.default()
        self.pool = ThreadPoolExecutor(max_workers=24, thread_name_prefix="hub")
        self.io = ThreadPoolExecutor(max_workers=48, thread_name_prefix="io")
        self._last: dict[str, dict] = {}
        self._sugg: OrderedDict[str, list] = OrderedDict()
        self._lock = threading.Lock()
        self._listener = None
        self._status = self._compute_status()
        self._sources = []
        self._summary_deferred = None
        self._reg = bus.register_object(PATH, NODE.interfaces[0], self._on_call, self._on_get, None)
        self.d.tokens.watch(self._on_account)
        if self.d.watch_network:
            self.d.watch_network(self._on_network)
        self._own = Gio.bus_own_name_on_connection(bus, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
                                                   lambda *_: on_ready and on_ready(), None)
        if start_timers:
            self.call_soon(self.refresh_tasks)
            self.call_soon(self.prefetch_calendar)
            self._every(REFRESH_S, self.refresh_tasks)
            self._every(REFRESH_S, self.prefetch_calendar)
            self._summary_running = False
            self.call_soon(self._check_summary)
            self._every(60, self._check_summary)  # wall clock: a suspend does not shift the summary

    def close(self):
        for s in self._sources:
            s.destroy()
        Gio.bus_unown_name(self._own)
        self.bus.unregister_object(self._reg)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.io.shutdown(wait=False, cancel_futures=True)

    # --- loop -------------------------------------------------------------
    def call_soon(self, fn, *args):
        src = GLib.idle_source_new()
        src.set_callback(lambda *_: (fn(*args), False)[1])
        src.attach(self.ctx)

    def _every(self, seconds, fn):
        src = GLib.timeout_source_new_seconds(seconds)
        src.set_callback(lambda *_: (fn(), True)[1])
        src.attach(self.ctx)
        self._sources.append(src)

    def _background(self, fn, done=None):
        """Run fn on the pool; any exception is logged, and done always runs back on the main loop."""
        def job():
            try:
                fn()
            except Exception:  # noqa: BLE001 — background job: nobody reads the future, so log it here
                log.exception("background job %s failed", getattr(fn, "__qualname__", fn))
            finally:
                if done:
                    self.call_soon(done)
        self.pool.submit(job)

    def _emit(self, name, params=None):
        self.bus.emit_signal(None, PATH, IFACE, name, params)

    # --- D-Bus -------------------------------------------------------------
    def _on_get(self, _conn, _sender, _path, _iface, prop):
        if prop == "ListenTimeout":
            return GLib.Variant("u", LISTEN_TIMEOUT_MS)
        return GLib.Variant("a{sv}", {k: GLib.Variant("b", v) for k, v in self._status.items()})

    def _on_call(self, _conn, _sender, _path, _iface, method, params, inv):
        args = params.unpack()
        deadline = time.monotonic() + SEARCH_TIMEOUT  # counted from the arrival of the call
        handlers = {
            "Search": (lambda: self._search(*args, deadline=deadline), lambda r: GLib.Variant("(aa{sv})", ([_strs(i) for i in r],))),
            "Activate": (lambda: self._activate(*args), None),
            "ListTasks": (lambda: self.d.task_store.tasks(),
                          lambda r: GLib.Variant("(aa{sv})", ([_strs(t) for t in r],))),
            "CompleteTask": (lambda: self._complete(*args), None),
            "AddTask": (lambda: self._add(*args), lambda r: GLib.Variant("(a{sv})", (_strs(r),))),
            "Listen": (self._listen, lambda r: GLib.Variant("(s)", (r,))),
        }
        if method == "StopListen" or method == "CancelListen":
            lst = self._listener
            if lst:
                (lst.stop if method == "StopListen" else lst.cancel)()
            inv.return_value(None)
            return
        if method == "Listen":
            with self._lock:
                if self._listener:
                    inv.return_dbus_error(ERR + "Busy", "a listen is already in progress")
                    return
                self._listener = self.d.listener_factory(self._on_listen_state)
        work, wrap = handlers[method]
        self.pool.submit(self._run, inv, work, wrap)

    def _run(self, inv, work, wrap):
        try:
            result = work()
        except Exception as e:  # noqa: BLE001 — returned to the D-Bus caller
            name = next((n for cls, n in ERRORS if isinstance(e, cls)), None)
            if name is None:
                log.exception("unexpected error")
                name = "Failed"
            inv.return_dbus_error(ERR + name, str(e) or name)
            return
        inv.return_value(wrap(result) if wrap else None)

    # --- search --------------------------------------------------------
    def _suggest(self, q):
        with self._lock:
            if q in self._sugg:
                self._sugg.move_to_end(q)
                return self._sugg[q]
        r = self.d.suggest(q)
        with self._lock:
            self._sugg[q] = r
            while len(self._sugg) > 200:
                self._sugg.popitem(last=False)
        return r

    def _agenda(self, q):
        if not self.d.tokens.has_account():
            return [setup_item()]
        out = []
        nt = self.d.task_store.new_item(q)
        if nt:
            out.append(nt)
        out += self.d.calendar.search(q, SEARCH_TIMEOUT - 0.1)
        out += self.d.task_store.search(q)
        return out

    def _search(self, terms, deadline=None):
        q = " ".join(" ".join(terms).split())
        if not long_enough(q):
            return []
        deadline = deadline or time.monotonic() + SEARCH_TIMEOUT
        futures = [self.io.submit(self._suggest, q), self.io.submit(self.d.chrome.search, q),
                   self.io.submit(self._agenda, q)]

        def wait(f):
            try:
                return f.result(timeout=max(0.0, deadline - time.monotonic()))
            except Exception as e:  # noqa: BLE001 — a failing group does not block the others
                log.debug("search group skipped: %r", e)
                return []

        sugg, chrome, agenda = (wait(f) for f in futures)
        items = google_items(q, sugg, self.d.keywords) + chrome + agenda
        with self._lock:
            self._last = {i["id"]: i for i in items}
        return items

    def _activate(self, id_, terms):
        q = " ".join(terms)
        if id_ == "task:new":
            text = q.strip()
            self._add(text[2:] if text.startswith("t ") else text)
            return
        if id_ == "setup":
            self.d.spawn(["gnome-control-center", "online-accounts"])
            return
        item = self._last.get(id_)
        if item is None:
            if id_ == "google:search":
                self.d.open_uri(search_url(q))
            return
        if item["kind"] == "setup":
            self.d.spawn(["gnome-control-center", "online-accounts"])
        elif item["kind"] in ("url", "search", "event", "task") and item["url"]:
            self.d.open_uri(item["url"])

    # --- tasks -------------------------------------------------------------
    def _complete(self, list_id, task_id):
        try:
            self.d.task_store.complete(list_id, task_id)
        finally:
            self.call_soon(self._after_tasks_change, True)

    def _add(self, text):
        t = self.d.task_store.add(text)
        self.call_soon(self._after_tasks_change, True)
        return t

    def _after_tasks_change(self, changed):
        # The extension also reloads the tasks when only the status (online, account) changed.
        if self._update_status() or changed:
            self._emit("TasksChanged")

    def _on_network(self, online):
        """Network back: tasks and calendar reloaded at once (without waiting for the 5-minute cycle)."""
        if online:
            self.refresh_tasks()
            self.prefetch_calendar()

    def _on_account(self):
        """Google account added, removed or signed in again: status now, tasks and agenda reloaded."""
        self._after_tasks_change(False)
        if self.d.tokens.has_account():
            self.refresh_tasks()
            self.prefetch_calendar()

    def refresh_tasks(self, done=None):
        def work():
            changed = False
            try:
                changed = self.d.task_store.refresh()
            except (ApiError, NoAccountError) as e:
                log.info("Tasks not refreshed: %s", e)
            failed = self.d.task_store.take_failed_ops() if self.d.task_store.failed_ops else []
            for op in failed:
                # Translators: a task created or completed offline that Google refused once back online.
                text = _("Change not saved: {task}").format(task=op.get("title") or op.get("id"))
                self.d.notify(_("Google Tasks"), text)
            self.call_soon(self._after_tasks_change, changed or bool(failed))
        self._background(work, done)

    def prefetch_calendar(self):
        self._background(self.d.calendar.prefetch)

    # --- status ------------------------------------------------------------
    def _compute_status(self):
        return {"account": bool(self.d.tokens.has_account()), "online": bool(self.d.task_store.online),
                "whisper_loaded": bool(self.d.whisper_loaded()), "multi_list": bool(self.d.task_store.multi_list)}

    def _update_status(self) -> bool:
        new = self._compute_status()
        if new == self._status:
            return False
        self._status = new
        self.bus.emit_signal(None, PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                             GLib.Variant("(sa{sv}as)", (IFACE, {"Status": self._on_get(*[None] * 4, "Status")}, [])))
        return True

    # --- voice --------------------------------------------------------------
    def _on_listen_state(self, state, level):
        self._emit("ListenState", GLib.Variant("(sd)", (state, float(level))))

    def _listen(self):
        try:
            return self._listener.listen()
        finally:
            with self._lock:
                self._listener = None
            self.call_soon(self._update_status)

    # --- daily summary ---------------------------------------------------
    def _summary_state(self) -> Path:
        return self.d.state_dir / "summary.json"

    def _last_sent(self):
        try:
            return date.fromisoformat(json.loads(self._summary_state().read_text())["last_sent"])
        except (OSError, ValueError, KeyError):
            return None

    def _check_summary(self):
        if not self._summary_running and summary_due(datetime.now(), self._last_sent(), self.d.summary_hour):
            self._summary_running = True
            self.run_summary(lambda: setattr(self, "_summary_running", False))

    def run_summary(self, done=None):
        def work():
            # A summary built from a stale cache would be wrong and would use up the day: when the
            # refresh fails (offline at login, API error, no account yet), nothing is recorded and
            # the per-minute _check_summary tries again until the tasks are fresh.
            try:
                self.d.task_store.refresh()
            except (ApiError, NoAccountError, OfflineError) as e:
                self._defer_summary(f"{type(e).__name__}: {e}")
                return
            if not self.d.task_store.online:  # TaskStore.refresh() absorbs OfflineError itself
                self._defer_summary("offline")
                return
            self._summary_deferred = None
            text = summary_text(self.d.task_store.tasks())
            # Recorded before notifying: if the state cannot be written, the per-minute retry
            # must not repeat the notification.
            self.d.state_dir.mkdir(parents=True, exist_ok=True)
            self._summary_state().write_text(json.dumps({"last_sent": self.d.today().isoformat()}))
            if text:
                self.d.notify(_("Google Tasks"), text, TASKS_URL)
        self._background(work, done)

    def _defer_summary(self, reason: str):
        """Log why the summary waits, once per reason: the retry runs every minute."""
        if reason != self._summary_deferred:
            log.info("Daily summary deferred, tasks not refreshed: %s", reason)
            self._summary_deferred = reason
