import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from babel import Locale

from omnishell.google_api import ApiError, GoogleApi
from omnishell.dates import DateReader
from omnishell.tasks import TaskStore
from tests.fake_google import FakeGoogle, FakeTokens, closed_port_url

FR_FR = Locale.parse("fr_FR")
TODAY = date(2026, 10, 3)


def task(id_, title, due=None, **kw):
    t = {"id": id_, "title": title, "status": "needsAction"}
    if due:
        t["due"] = f"{due}T00:00:00.000Z"
    t.update(kw)
    return t


class TestTasks(unittest.TestCase):
    def setUp(self):
        self.g = FakeGoogle()
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name, "tasks.json")
        self.api = GoogleApi(FakeTokens(), tasks_base=self.g.url, cal_base=self.g.url, timeout=2)
        self.g.routes[("GET", "/users/@me/lists")] = (200, {"items": [{"id": "L1", "title": "Perso"},
                                                                       {"id": "L2", "title": "Boulot"}]})
        self.g.routes[("GET", "/lists/L1/tasks")] = lambda req: (200, {
            "items": [task("a", "En retard", "2026-10-01"), task("b", "Réunion budget", "2026-10-03")],
            "nextPageToken": "p2"} if "pageToken" not in req["query"] else {
            "items": [task("c", "Semaine", "2026-10-09", webViewLink="https://tasks.google.com/task/c")]})
        self.g.routes[("GET", "/lists/L2/tasks")] = (200, {"items": [task("d", "Plus tard", "2026-10-20"),
                                                                     task("e", "Sans date")]})

    def tearDown(self):
        self.g.close()
        self.tmp.cleanup()

    def store(self):
        return TaskStore(self.api, self.cache, DateReader(["fr"], "DMY", FR_FR), today=lambda: TODAY)

    def test_refresh_buckets_and_pagination(self):
        s = self.store()
        self.assertTrue(s.refresh())
        ts = s.tasks()
        self.assertEqual([t["bucket"] for t in ts], ["overdue", "today", "week", "later", "undated"])
        self.assertTrue(s.multi_list)
        self.assertEqual(ts[2]["link"], "https://tasks.google.com/task/c")
        self.assertEqual(ts[0]["link"], "https://tasks.google.com/")
        self.assertEqual(ts[3]["list_title"], "Boulot")
        self.assertEqual(set(ts[0]), {"id", "list", "list_title", "title", "due", "bucket", "link"})
        q = self.g.made("GET", "/lists/L1/tasks")[0]["query"]
        self.assertEqual((q["showCompleted"], q["showHidden"], q["maxResults"]), ("false", "false", "100"))
        self.assertFalse(s.refresh())

    def test_due_is_date_only(self):
        s = self.store()
        s.refresh()
        self.assertEqual(s.tasks()[2]["due"], "2026-10-09")

    def test_complete_ok(self):
        self.g.routes[("PATCH", "/lists/L1/tasks/b")] = (200, {})
        s = self.store()
        s.refresh()
        s.complete("L1", "b")
        self.assertEqual(self.g.made("PATCH", "/lists/L1/tasks/b")[0]["body"], {"status": "completed"})
        self.assertNotIn("b", [t["id"] for t in s.tasks()])

    def test_complete_api_error_rolls_back(self):
        self.g.routes[("PATCH", "/lists/L1/tasks/b")] = (500, {"error": {"message": "boom"}})
        s = self.store()
        s.refresh()
        with self.assertRaises(ApiError):
            s.complete("L1", "b")
        self.assertIn("b", [t["id"] for t in s.tasks()])

    def test_offline_queue_and_replay(self):
        s = self.store()
        s.refresh()
        url = self.api.tasks_base
        self.api.tasks_base = closed_port_url()
        s.complete("L1", "b")
        self.assertFalse(s.online)
        self.assertNotIn("b", [t["id"] for t in s.tasks()])
        self.assertEqual(json.loads(self.cache.read_text())["pending"],
                         [{"op": "complete", "list": "L1", "id": "b"}])
        s2 = self.store()
        self.assertNotIn("b", [t["id"] for t in s2.tasks()])
        self.api.tasks_base = url
        self.g.routes[("PATCH", "/lists/L1/tasks/b")] = (200, {})
        self.g.routes[("GET", "/lists/L1/tasks")] = (200, {"items": [task("a", "En retard", "2026-10-01")]})
        s2.refresh()
        self.assertTrue(s2.online)
        self.assertEqual(len(self.g.made("PATCH", "/lists/L1/tasks/b")), 1)
        self.assertEqual(json.loads(self.cache.read_text())["pending"], [])

    def test_offline_add_then_replay(self):
        s = self.store()
        s.refresh()
        url = self.api.tasks_base
        self.api.tasks_base = closed_port_url()
        t = s.add("pain demain")
        self.assertEqual((t["id"], t["title"], t["due"], t["bucket"]), ("local:1", "pain", "2026-10-04", "week"))
        self.assertIn("local:1", [x["id"] for x in s.tasks()])
        self.api.tasks_base = url
        self.g.routes[("POST", "/lists/@default/tasks")] = (200, task("n", "pain", "2026-10-04"))
        s.refresh()
        self.assertEqual(self.g.made("POST", "/lists/@default/tasks")[0]["body"],
                         {"title": "pain", "due": "2026-10-04T00:00:00.000Z"})

    def test_offline_add_then_complete_creates_nothing(self):
        s = self.store()
        s.refresh()
        url = self.api.tasks_base
        self.api.tasks_base = closed_port_url()
        t = s.add("pain")
        s.complete(t["list"], t["id"])
        self.assertNotIn(t["id"], [x["id"] for x in s.tasks()])
        self.assertEqual(json.loads(self.cache.read_text())["pending"], [])
        self.api.tasks_base = url
        s.refresh()
        self.assertEqual(self.g.made("POST", "/lists/@default/tasks"), [])
        self.assertEqual(s.failed_ops, [])

    def test_replayed_add_takes_server_id(self):
        s = self.store()
        s.refresh()
        url = self.api.tasks_base
        self.api.tasks_base = closed_port_url()
        t = s.add("pain")
        self.api.tasks_base = url
        self.g.routes[("POST", "/lists/@default/tasks")] = (200, task("n", "pain"))
        # Replay only, lists not read again: the network drops right after.
        self.assertTrue(s._replay())
        self.assertIn("n", [x["id"] for x in s.tasks()])
        self.assertNotIn(t["id"], [x["id"] for x in s.tasks()])
        self.g.routes[("PATCH", "/lists/L1/tasks/n")] = (200, {})
        s.complete("L1", "n")
        self.assertEqual(len(self.g.made("PATCH", "/lists/L1/tasks/n")), 1)

    def test_add_online(self):
        self.g.routes[("POST", "/lists/@default/tasks")] = (200, task("n", "lait"))
        s = self.store()
        s.refresh()
        t = s.add("lait")
        self.assertEqual((t["id"], t["bucket"]), ("n", "undated"))
        self.assertEqual(self.g.made("POST", "/lists/@default/tasks")[0]["body"], {"title": "lait"})

    def test_replay_permanent_failure_dropped(self):
        s = self.store()
        s.refresh()
        url = self.api.tasks_base
        self.api.tasks_base = closed_port_url()
        s.complete("L1", "b")
        self.api.tasks_base = url
        self.g.routes[("PATCH", "/lists/L1/tasks/b")] = (400, {"error": {"message": "bad"}})
        s.refresh()
        self.assertEqual(json.loads(self.cache.read_text())["pending"], [])
        self.assertEqual(s.failed_ops, [{"op": "complete", "list": "L1", "id": "b"}])

    def test_concurrent_refresh_replays_each_op_once(self):
        import threading
        s = self.store()
        s.refresh()
        url = self.api.tasks_base
        self.api.tasks_base = closed_port_url()
        s.add("pain")
        s.add("lait")
        self.api.tasks_base = url
        self.g.routes[("POST", "/lists/@default/tasks")] = lambda req: (200, task("n" + req["body"]["title"], req["body"]["title"]))
        self.g.delay = 0.2
        th = [threading.Thread(target=s.refresh) for _ in range(2)]
        for t in th:
            t.start()
        for t in th:
            t.join()
        titles = sorted(r["body"]["title"] for r in self.g.made("POST", "/lists/@default/tasks"))
        self.assertEqual(titles, ["lait", "pain"])

    def test_complete_rolls_back_on_any_error(self):
        from omnishell.google_api import NoAccountError
        s = self.store()
        s.refresh()
        self.api.tokens.account = False
        with self.assertRaises(NoAccountError):
            s.complete("L1", "b")
        self.assertIn("b", [t["id"] for t in s.tasks()])

    def test_search_accents(self):
        s = self.store()
        s.refresh()
        r = s.search("reunion")
        self.assertEqual([i["name"] for i in r], ["Réunion budget"])
        self.assertEqual((r[0]["group"], r[0]["kind"], r[0]["id"]), ("agenda", "task", "task:L1:b"))

    def test_new_task_item(self):
        s = self.store()
        it = s.new_item("t pain demain")
        self.assertEqual(it["name"], "Create task: pain")
        self.assertEqual(it["description"], "dim. 4 oct.")
        self.assertEqual((it["id"], it["kind"], it["group"]), ("task:new", "new-task", "agenda"))
        self.assertIsNone(s.new_item("tarte"))
        self.assertIsNone(s.new_item("t "))
        it = s.new_item("t Brot kaufen morgen")
        self.assertEqual(it["name"], "Create task: Brot kaufen morgen")
        self.assertEqual(it["description"], "No due date · dates read in fr (date_languages)")
