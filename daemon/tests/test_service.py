import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path

from gi.repository import Gio, GLib

from babel import Locale

from google_hub.calendar import CalendarStore
from google_hub.dates import DateReader
from google_hub.google_api import GoogleApi
from google_hub.service import BUS_NAME, IFACE, LISTEN_TIMEOUT_MS, PATH, Deps, HubService
from google_hub.tasks import TaskStore
from google_hub.voice import FIRST_SAMPLE_S, MAX_CAPTURE_MS, CaptureError
from google_hub.whisper import INFERENCE_TIMEOUT_S, KILL_GRACE_S, PROBE_TIMEOUT_S, START_TIMEOUT_S
from tests.fake_google import FakeGoogle, FakeTokens

FR_FR = Locale.parse("fr_FR")
TODAY = date(2026, 10, 3)


class StubChrome:
    def search(self, q, limit=5):
        return [{"group": "chrome", "id": "chrome:https://github.com/", "name": "GitHub",
                 "description": "https://github.com/", "icon": "starred-symbolic", "kind": "url",
                 "url": "https://github.com/"}] if "git" in q else []


class StubListener:
    def __init__(self, on_state, result="bonjour", error=None):
        self.on_state, self.result, self.error = on_state, result, error

    def listen(self):
        self.on_state("listening", 0.5)
        time.sleep(0.3)
        if self.error:
            self.on_state("error:audio-capture", 0)
            raise self.error
        self.on_state("idle", 0)
        return self.result

    def stop(self):
        pass

    def cancel(self):
        pass


class TestService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.testbus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        cls.testbus.up()

    @classmethod
    def tearDownClass(cls):
        cls.testbus.down()

    def setUp(self):
        self.g = FakeGoogle()
        self.g.routes[("GET", "/users/@me/lists")] = (200, {"items": [{"id": "L1", "title": "Perso"}]})
        self.g.routes[("GET", "/lists/L1/tasks")] = (200, {"items": [
            {"id": "b", "title": "Réunion", "due": "2026-10-03T00:00:00.000Z"}]})
        self.g.routes[("GET", "/users/me/calendarList")] = (200, {"items": []})
        self.tmp = tempfile.TemporaryDirectory()
        self.tokens = FakeTokens()
        api = GoogleApi(self.tokens, tasks_base=self.g.url, cal_base=self.g.url, timeout=2)
        self.opened, self.spawned, self.notes = [], [], []
        self.suggest_delay = 0.0
        self.listener_kw = {}
        self.network_callbacks = []

        def suggest(q):
            time.sleep(self.suggest_delay)
            return [q + " suggestion"]

        self.deps = Deps(
            tokens=self.tokens, chrome=StubChrome(),
            task_store=TaskStore(api, Path(self.tmp.name, "tasks.json"), DateReader(["fr"], "DMY", FR_FR), today=lambda: TODAY),
            calendar=CalendarStore(api, DateReader(["fr"], "DMY", FR_FR)), keywords={"yt": ("YouTube", "https://y/{q}")},
            suggest=suggest,
            listener_factory=lambda on_state: StubListener(on_state, **self.listener_kw),
            open_uri=self.opened.append, spawn=self.spawned.append,
            notify=lambda title, body, uri=None: self.notes.append((title, body, uri)),
            state_dir=Path(self.tmp.name, "state"), summary_hour=9, whisper_loaded=lambda: False,
            today=lambda: TODAY, watch_network=self.network_callbacks.append)
        self.ctx = GLib.MainContext.new()
        self.loop = GLib.MainLoop.new(self.ctx, False)
        ready = threading.Event()

        def run():
            self.ctx.push_thread_default()
            bus = Gio.bus_get_sync(Gio.BusType.SESSION)
            self.svc = HubService(bus, self.deps, self.ctx, on_ready=ready.set, start_timers=False)
            self.loop.run()
            self.svc.close()
            self.ctx.pop_thread_default()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self.assertTrue(ready.wait(5))
        self.bus = Gio.DBusConnection.new_for_address_sync(
            self.testbus.get_bus_address(),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)

    def tearDown(self):
        self.loop.quit()
        self.thread.join(5)
        self.bus.close_sync(None)
        self.g.close()
        self.tmp.cleanup()

    def call(self, method, args=None, sig=None, timeout=10000):
        return self.bus.call_sync(BUS_NAME, PATH, IFACE, method, args, GLib.VariantType(sig) if sig else None,
                                  Gio.DBusCallFlags.NONE, timeout, None).unpack()

    def search(self, *terms):
        return self.call("Search", GLib.Variant("(as)", (list(terms),)), "(aa{sv})")[0]

    def test_search_groups(self):
        r = self.search("github")
        groups = [i["group"] for i in r]
        self.assertEqual(groups, sorted(groups, key=["google", "chrome", "agenda"].index))
        self.assertIn("chrome", groups)
        self.assertEqual(len({i["id"] for i in r}), len(r))
        self.assertEqual(self.search("gi"), [])

    def test_search_concurrent_slow_suggest(self):
        self.suggest_delay = 3
        times, results = [], []

        def one():
            t0 = time.monotonic()
            results.append(self.search("chat noir"))
            times.append(time.monotonic() - t0)

        th = [threading.Thread(target=one) for _ in range(2)]
        th[0].start()
        time.sleep(0.05)
        th[1].start()
        for x in th:
            x.join()
        self.assertTrue(all(t <= 1.6 for t in times), times)
        for r in results:
            self.assertEqual([i["id"] for i in r if i["group"] == "google"], ["google:search", "google:gemini"])

    def test_fast_typing_slow_suggest_latency(self):
        self.suggest_delay = 1.5
        times = []
        lock = threading.Lock()

        def one(q):
            t0 = time.monotonic()
            self.search(q)
            with lock:
                times.append(time.monotonic() - t0)

        th = []
        word = "comment faire un gateau"
        for i in range(4, 16):
            t = threading.Thread(target=one, args=(word[:i],))
            t.start()
            th.append(t)
            time.sleep(0.15)
        for t in th:
            t.join()
        self.assertTrue(all(t <= 1.7 for t in times), [round(t, 2) for t in times])

    def test_activate_setup_without_prior_search(self):
        self.call("Activate", GLib.Variant("(sas)", ("setup", [])))
        self.assertEqual(self.spawned, [["gnome-control-center", "online-accounts"]])

    def test_activate_url_and_new_task(self):
        self.search("github")
        self.call("Activate", GLib.Variant("(sas)", ("chrome:https://github.com/", ["github"])))
        self.assertEqual(self.opened, ["https://github.com/"])
        self.g.routes[("POST", "/lists/@default/tasks")] = (200, {"id": "n", "title": "pain"})
        got = []
        sub = self.bus.signal_subscribe(BUS_NAME, IFACE, "TasksChanged", PATH, None, 0,
                                        lambda *a: got.append(a))
        self.search("t", "pain", "demain")
        self.call("Activate", GLib.Variant("(sas)", ("task:new", ["t", "pain", "demain"])))
        self.assertEqual(self.g.made("POST", "/lists/@default/tasks")[0]["body"],
                         {"title": "pain", "due": "2026-10-04T00:00:00.000Z"})
        deadline = time.monotonic() + 2
        while not got and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.01)
        self.bus.signal_unsubscribe(sub)
        self.assertTrue(got)

    def test_activate_setup(self):
        self.tokens.account = False
        r = self.search("reunion")
        setup = [i for i in r if i["group"] == "agenda"]
        self.assertEqual([(i["id"], i["name"]) for i in setup], [("setup", "Connect your Google account")])
        self.call("Activate", GLib.Variant("(sas)", ("setup", ["reunion"])))
        self.assertEqual(self.spawned, [["gnome-control-center", "online-accounts"]])

    def test_list_and_complete_error_maps(self):
        self.svc_refresh()
        tasks = self.call("ListTasks", None, "(aa{sv})")[0]
        self.assertEqual([(t["id"], t["bucket"]) for t in tasks], [("b", "today")])
        self.g.routes[("PATCH", "/lists/L1/tasks/b")] = (500, {"error": {"message": "boom"}})
        with self.assertRaises(GLib.Error) as cm:
            self.call("CompleteTask", GLib.Variant("(ss)", ("L1", "b")))
        self.assertIn("io.github.maximeallanic.GoogleHub.Error.Api", cm.exception.message)

    def svc_refresh(self):
        done = threading.Event()
        self.svc.call_soon(lambda: self.svc.refresh_tasks(done.set))
        self.assertTrue(done.wait(5))

    def test_add_task(self):
        self.g.routes[("POST", "/lists/@default/tasks")] = (200, {"id": "n", "title": "lait"})
        t = self.call("AddTask", GLib.Variant("(s)", ("lait",)), "(a{sv})")[0]
        self.assertEqual((t["id"], t["title"], t["bucket"]), ("n", "lait", "undated"))

    def test_listen_busy(self):
        out = []
        th = threading.Thread(target=lambda: out.append(self.call("Listen", None, "(s)")))
        th.start()
        time.sleep(0.1)
        with self.assertRaises(GLib.Error) as cm:
            self.call("Listen", None, "(s)")
        self.assertIn("Error.Busy", cm.exception.message)
        th.join()
        self.assertEqual(out, [("bonjour",)])

    def test_listen_error_maps(self):
        self.listener_kw = {"error": CaptureError("x")}
        with self.assertRaises(GLib.Error) as cm:
            self.call("Listen", None, "(s)")
        self.assertIn("Error.AudioCapture", cm.exception.message)

    def test_listen_state_signals(self):
        got = []
        sub = self.bus.signal_subscribe(BUS_NAME, IFACE, "ListenState", PATH, None, 0,
                                        lambda c, s, p, i, n, params: got.append(params.unpack()))
        self.call("Listen", None, "(s)")
        deadline = time.monotonic() + 2
        while len(got) < 2 and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.01)
        self.bus.signal_unsubscribe(sub)
        self.assertEqual(got[0], ("listening", 0.5))
        self.assertEqual(got[-1], ("idle", 0.0))

    def test_status_property(self):
        v = self.bus.call_sync(BUS_NAME, PATH, "org.freedesktop.DBus.Properties", "Get",
                               GLib.Variant("(ss)", (IFACE, "Status")), GLib.VariantType("(v)"),
                               Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
        self.assertEqual(set(v), {"account", "online", "whisper_loaded", "multi_list"})

    def test_listen_timeout_property_covers_the_daemon_worst_case(self):
        v = self.bus.call_sync(BUS_NAME, PATH, "org.freedesktop.DBus.Properties", "Get",
                               GLib.Variant("(ss)", (IFACE, "ListenTimeout")), GLib.VariantType("(v)"),
                               Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
        self.assertEqual(v, LISTEN_TIMEOUT_MS)
        worst_s = (MAX_CAPTURE_MS / 1000 + FIRST_SAMPLE_S + START_TIMEOUT_S + PROBE_TIMEOUT_S
                   + INFERENCE_TIMEOUT_S + KILL_GRACE_S)
        self.assertGreater(v, worst_s * 1000)

    def test_network_back_refreshes_tasks_and_calendar(self):
        url = self.deps.task_store.api.tasks_base
        self.deps.task_store.api.tasks_base = "http://127.0.0.1:9"  # hors ligne
        self.svc_refresh()
        self.assertFalse(self.deps.task_store.online)
        self.deps.task_store.api.tasks_base = url
        got = []
        sub = self.bus.signal_subscribe(BUS_NAME, IFACE, "TasksChanged", PATH, None, 0, lambda *a: got.append(a))
        before = len(self.g.made("GET", "/users/@me/lists"))
        self.assertEqual(len(self.network_callbacks), 1)
        self.svc.call_soon(self.network_callbacks[0], True)
        deadline = time.monotonic() + 3
        while not got and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.01)
        self.bus.signal_unsubscribe(sub)
        self.assertGreater(len(self.g.made("GET", "/users/@me/lists")), before)
        self.assertTrue(self.g.made("GET", "/users/me/calendarList"))
        self.assertTrue(self.deps.task_store.online)
        self.assertTrue(got, "TasksChanged expected: the offline status changed even though the tasks did not")

    def test_account_change_updates_status_and_reloads(self):
        self.assertEqual(len(self.tokens.watchers), 1)
        props = []
        sub = self.bus.signal_subscribe(BUS_NAME, "org.freedesktop.DBus.Properties", "PropertiesChanged", PATH,
                                        None, 0, lambda c, s, p, i, n, params: props.append(params.unpack()))

        def fire_and_wait(pred):
            self.svc.call_soon(self.tokens.watchers[0])
            deadline = time.monotonic() + 3
            while not pred() and time.monotonic() < deadline:
                GLib.MainContext.default().iteration(False)
                time.sleep(0.01)

        self.tokens.account = False
        fire_and_wait(lambda: props)
        self.assertFalse(props[-1][1]["Status"]["account"])
        before = len(self.g.made("GET", "/users/@me/lists"))
        self.tokens.account = True
        fire_and_wait(lambda: len(props) > 1 and len(self.g.made("GET", "/users/@me/lists")) > before)
        self.bus.signal_unsubscribe(sub)
        self.assertTrue(props[-1][1]["Status"]["account"])
        self.assertGreater(len(self.g.made("GET", "/users/@me/lists")), before)

    def test_network_loss_does_nothing(self):
        before = len(self.g.requests)
        self.svc.call_soon(self.network_callbacks[0], False)
        time.sleep(0.5)
        self.assertEqual(len(self.g.requests), before)

    def test_daily_summary(self):
        self.svc_refresh()
        done = threading.Event()
        self.svc.call_soon(lambda: self.svc.run_summary(done.set))
        self.assertTrue(done.wait(5))
        self.assertEqual(self.notes, [("Google Tasks", "1 task today", "https://tasks.google.com/")])
        self.assertTrue(Path(self.tmp.name, "state", "summary.json").exists())

    def test_daily_summary_waits_while_offline(self):
        self.svc_refresh()  # cache filled, then the network goes away
        url = self.deps.task_store.api.tasks_base
        self.deps.task_store.api.tasks_base = "http://127.0.0.1:9"
        done = threading.Event()
        with self.assertLogs("google_hub.service", "INFO") as logs:
            self.svc.call_soon(lambda: self.svc.run_summary(done.set))
            self.assertTrue(done.wait(5))
        self.assertIn("deferred", logs.output[0])
        self.assertEqual(self.notes, [], "no summary from a stale cache")
        self.assertFalse(Path(self.tmp.name, "state", "summary.json").exists(), "the day must not be used up")
        self.deps.task_store.api.tasks_base = url
        done = threading.Event()
        self.svc.call_soon(lambda: self.svc.run_summary(done.set))
        self.assertTrue(done.wait(5))
        self.assertEqual(self.notes, [("Google Tasks", "1 task today", "https://tasks.google.com/")])
        self.assertTrue(Path(self.tmp.name, "state", "summary.json").exists())

    def test_daily_summary_failure_is_logged_and_releases(self):
        Path(self.tmp.name, "state").write_text("not a directory")  # state_dir.mkdir() raises
        done = threading.Event()
        with self.assertLogs("google_hub.service", "ERROR") as logs:
            self.svc.call_soon(lambda: self.svc.run_summary(done.set))
            self.assertTrue(done.wait(5), "done must run even when the job fails")
        self.assertIn("failed", logs.output[0])
        self.assertEqual(self.notes, [], "no notification when the sent state cannot be recorded")
