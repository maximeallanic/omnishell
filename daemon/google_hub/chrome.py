""""Chrome" search group: bookmarks then history, read locally."""
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from gi.repository import GLib

from .text import matches, normalize

log = logging.getLogger(__name__)

EPOCH_DELTA = 11644473600
COPY_MIN_INTERVAL = 60
# Profile folders tried, in order, under $XDG_CONFIG_HOME (Chrome and Chromium share the profile format).
BROWSER_DIRS = ("google-chrome", "chromium")


def find_chrome_root(config_dir: Path | None = None) -> Path:
    """First browser profile folder that exists; the first candidate when none does (search then finds nothing)."""
    base = Path(config_dir or GLib.get_user_config_dir())
    for name in BROWSER_DIRS:
        if (base / name).is_dir():
            return base / name
    return base / BROWSER_DIRS[0]


class ChromeIndex:
    def __init__(self, root: Path | None = None, cache_dir: Path | None = None, clock=time.time):
        self.root = Path(root or find_chrome_root())
        self.cache_dir = Path(cache_dir or Path(GLib.get_user_cache_dir()) / "google-hub")
        self.clock = clock
        self._copied_mtime = None
        self._copied_at = None
        self._rows: list[tuple[str, str, str, int, int]] = []  # (normalised text, title, url, visits, last visit)
        self._rows_key = None
        # Searches run concurrently in the service's io pool; only one thread copies and rebuilds.
        self._refresh_lock = threading.Lock()

    def _profile(self) -> Path:
        try:
            name = json.loads((self.root / "Local State").read_text())["profile"]["last_used"]
        except (OSError, ValueError, KeyError, TypeError):
            name = "Default"
        return self.root / (name or "Default")

    def _bookmarks(self, profile: Path) -> list[tuple[str, str]]:
        try:
            roots = json.loads((profile / "Bookmarks").read_text())["roots"]
        except (OSError, ValueError, KeyError, TypeError):
            return []
        out = []

        def walk(node):
            if not isinstance(node, dict):
                return
            if node.get("type") == "url":
                out.append((node.get("name", ""), node.get("url", "")))
            for child in node.get("children", []):
                walk(child)

        for root in roots.values():
            walk(root)
        return out

    def _history_copy(self, profile: Path) -> Path | None:
        src = profile / "History"
        dst = self.cache_dir / "History"
        try:
            mtime = src.stat().st_mtime
        except OSError:
            return None
        now = self.clock()
        stale = mtime != self._copied_mtime
        if stale and (self._copied_at is None or now - self._copied_at >= COPY_MIN_INTERVAL):
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".tmp")
            try:
                shutil.copy2(src, tmp)
                os.replace(tmp, dst)  # a reader still open on the old copy keeps a whole file
            finally:
                tmp.unlink(missing_ok=True)
            self._copied_mtime, self._copied_at = mtime, now
        return dst if dst.exists() else None

    def _history(self, profile: Path) -> list[tuple[str, str, str, int, int]]:
        """Normalised history, rebuilt only when the copy changes (a keystroke is a plain scan).

        Single flight: a search arriving while another thread copies or rebuilds scans the previous
        index instead of waiting or copying over the same file.
        """
        if not self._refresh_lock.acquire(blocking=False):
            return self._rows
        try:
            path = self._history_copy(profile)
            if not path:
                return []
            key = (str(path), path.stat().st_mtime)
            if key != self._rows_key:
                self._rows = [(normalize(f"{title or ''} {url}"), title, url, visits or 0, last or 0)
                              for url, title, visits, last in self._read_history(path)]
                self._rows_key = key
            return self._rows
        finally:
            self._refresh_lock.release()

    def _read_history(self, path: Path) -> list[tuple[str, str, int, int]]:
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                try:
                    rows = db.execute("SELECT url, title, visit_count, last_visit_time FROM urls"
                                      " WHERE hidden = 0").fetchall()
                except sqlite3.OperationalError as e:
                    if "hidden" not in str(e):
                        raise
                    rows = db.execute("SELECT url, title, visit_count, last_visit_time FROM urls").fetchall()
            finally:
                db.close()
            return rows
        except sqlite3.DatabaseError as e:
            log.warning("Chrome history unreadable (%s): %s", path, e)
            return []

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not self.root.exists():
            return []
        profile = self._profile()
        out, seen = [], set()

        def add(name, url, icon):
            if url in seen:
                return
            seen.add(url)
            out.append({"group": "chrome", "id": f"chrome:{url}", "name": name or url,
                        "description": url, "icon": icon, "kind": "url", "url": url})

        for name, url in self._bookmarks(profile):
            if matches(query, name, url):
                add(name, url, "starred-symbolic")
        now = self.clock()
        words = normalize(query).split()
        scored = []
        for hay, title, url, visits, last in self._history(profile):
            if words and all(w in hay for w in words):
                days = max(0.0, (now - (last / 1_000_000 - EPOCH_DELTA)) / 86400)
                scored.append((visits / (1 + days), title, url))
        for _, title, url in sorted(scored, key=lambda s: s[0], reverse=True):
            add(title, url, "document-open-recent-symbolic")
        return out[:limit]
