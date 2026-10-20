import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from omnishell.chrome import ChromeIndex, find_chrome_root

EPOCH_DELTA = 11644473600  # seconds between 1601-01-01 and 1970-01-01


def chrome_ts(unix: float) -> int:
    return int((unix + EPOCH_DELTA) * 1_000_000)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class TestChrome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name, "chrome")
        self.cache = Path(self.tmp.name, "cache")
        self.now = time.time()
        self.clock = Clock(self.now)
        self.make_profile("Default")

    def tearDown(self):
        self.tmp.cleanup()

    def make_profile(self, name, last_used=None):
        prof = self.root / name
        prof.mkdir(parents=True, exist_ok=True)
        (self.root / "Local State").write_text(json.dumps({"profile": {"last_used": last_used or name}}))
        bookmarks = {"roots": {"bookmark_bar": {"type": "folder", "children": [
            {"type": "url", "name": "Réunion Lyon", "url": "https://meet.example/lyon"},
            {"type": "folder", "name": "Dossier", "children": [
                {"type": "url", "name": "Doc", "url": "https://doc.example/"}]},
        ]}, "other": {"type": "folder", "children": []}}}
        (prof / "Bookmarks").write_text(json.dumps(bookmarks))
        db = sqlite3.connect(prof / "History")
        db.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INTEGER,"
                   " last_visit_time INTEGER, hidden INTEGER DEFAULT 0)")
        rows = [
            ("https://notes.example/reunion", "reunion notes", 50, chrome_ts(self.now - 3600)),
            ("https://old.example/r", "réunion vieux", 2, chrome_ts(self.now - 365 * 86400)),
            ("https://meet.example/lyon", "Réunion Lyon (historique)", 99, chrome_ts(self.now)),
        ]
        db.executemany("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)", rows)
        db.commit()
        db.close()
        return prof

    def index(self):
        return ChromeIndex(self.root, self.cache, clock=self.clock)

    def test_bookmarks_first_then_frecency(self):
        r = self.index().search("reunion")
        self.assertEqual([i["name"] for i in r], ["Réunion Lyon", "reunion notes", "réunion vieux"])
        self.assertEqual(r[0]["icon"], "starred-symbolic")
        self.assertEqual(r[1]["icon"], "document-open-recent-symbolic")
        self.assertEqual(r[1]["id"], "chrome:https://notes.example/reunion")
        self.assertEqual(r[1]["description"], "https://notes.example/reunion")
        self.assertEqual({i["group"] for i in r}, {"chrome"})
        self.assertEqual({i["kind"] for i in r}, {"url"})

    def test_profile_from_local_state(self):
        prof = self.make_profile("Profile 1")
        db = sqlite3.connect(prof / "History")
        db.execute("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)",
                   ("https://p1.example/", "profil un", 1, chrome_ts(self.now)))
        db.commit()
        db.close()
        self.assertEqual([i["name"] for i in self.index().search("profil un")], ["profil un"])

    def test_limit_and_dedup(self):
        db = sqlite3.connect(self.root / "Default" / "History")
        db.executemany("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)",
                       [(f"https://x{i}.example/", f"reunion {i}", i, chrome_ts(self.now)) for i in range(9)])
        db.commit()
        db.close()
        r = self.index().search("reunion")
        self.assertEqual(len(r), 5)
        self.assertEqual(len({i["url"] for i in r}), 5)
        self.assertEqual(sum(1 for i in r if i["url"] == "https://meet.example/lyon"), 1)

    def test_history_copied_not_opened_in_place(self):
        lock = sqlite3.connect(self.root / "Default" / "History", isolation_level=None)
        lock.execute("BEGIN EXCLUSIVE")
        try:
            self.assertIn("reunion notes", [i["name"] for i in self.index().search("reunion")])
        finally:
            lock.execute("ROLLBACK")
            lock.close()
        self.assertTrue((self.cache / "History").exists())

    def test_copy_throttled(self):
        idx = self.index()
        idx.search("reunion")
        hist = self.root / "Default" / "History"
        db = sqlite3.connect(hist)
        db.execute("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)",
                   ("https://new.example/", "reunion nouvelle", 1000, chrome_ts(self.now)))
        db.commit()
        db.close()
        os.utime(hist, (self.now + 5, self.now + 5))
        self.clock.t = self.now + 30
        self.assertNotIn("reunion nouvelle", [i["name"] for i in idx.search("reunion")])
        self.clock.t = self.now + 61
        self.assertIn("reunion nouvelle", [i["name"] for i in idx.search("reunion")])

    def test_large_history_is_fast_after_first_search(self):
        db = sqlite3.connect(self.root / "Default" / "History")
        db.executemany("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)",
                       [(f"https://site{i}.example/page", f"Page numéro {i} à lire", 1, chrome_ts(self.now))
                        for i in range(50000)])
        db.commit()
        db.close()
        idx = self.index()
        idx.search("reunion")
        t0 = time.monotonic()
        for q in ("reu", "reun", "reuni", "reunio"):
            idx.search(q)
        self.assertLess((time.monotonic() - t0) / 4, 0.12)

    def test_refresh_is_single_flight(self):
        idx = self.index()
        idx.search("reunion")
        hist = self.root / "Default" / "History"
        db = sqlite3.connect(hist)
        db.execute("INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?,?,?,?)",
                   ("https://new.example/", "reunion nouvelle", 1000, chrome_ts(self.now)))
        db.commit()
        db.close()
        os.utime(hist, (self.now + 5, self.now + 5))
        self.clock.t = self.now + 61
        entered, release = threading.Event(), threading.Event()
        read = idx._read_history

        def slow_read(path):
            entered.set()
            release.wait(5)
            return read(path)

        idx._read_history = slow_read
        first = []
        t = threading.Thread(target=lambda: first.append(idx.search("reunion")))
        t.start()
        self.assertTrue(entered.wait(5))
        # A concurrent keystroke neither waits nor copies again: it scans the previous index.
        names = [i["name"] for i in idx.search("reunion")]
        self.assertIn("reunion notes", names)
        self.assertNotIn("reunion nouvelle", names)
        self.assertFalse((self.cache / "History.tmp").exists())
        release.set()
        t.join(5)
        self.assertIn("reunion nouvelle", [i["name"] for i in first[0]])

    def test_missing_chrome(self):
        self.assertEqual(ChromeIndex(Path(self.tmp.name, "absent"), self.cache).search("reunion"), [])

    def test_corrupt_history(self):
        (self.root / "Default" / "History").write_bytes(os.urandom(4096))
        with self.assertLogs(level="WARNING"):
            r = self.index().search("reunion")
        self.assertEqual([i["name"] for i in r], ["Réunion Lyon"])


class TestFindRoot(unittest.TestCase):
    def test_first_existing_browser_wins(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self.assertEqual(find_chrome_root(base), base / "google-chrome")  # none: first candidate
            (base / "chromium").mkdir()
            self.assertEqual(find_chrome_root(base), base / "chromium")
            (base / "google-chrome").mkdir()
            self.assertEqual(find_chrome_root(base), base / "google-chrome")
