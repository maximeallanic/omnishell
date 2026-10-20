"""Google Tasks: local cache, grouping by due date, offline action queue."""
import json
import logging
import os
import threading
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from babel.lists import format_list

from .google_api import ApiError, OfflineError
from .i18n import _
from .text import matches

log = logging.getLogger(__name__)

DEFAULT_LINK = "https://tasks.google.com/"


def _due_iso(d: str) -> str:
    return f"{d}T00:00:00.000Z"


class TaskStore:
    def __init__(self, api, cache_path: Path, dates, today=date.today):
        self.api = api
        self.dates = dates
        self.cache_path = Path(cache_path)
        self.today = today
        self.online = True
        self.lists: list[dict] = []
        self._tasks: list[dict] = []
        self.pending: list[dict] = []
        self.failed_ops: list[dict] = []
        self._local_seq = 0
        self._lock = threading.RLock()  # refresh (replay) / complete / add from several threads
        self._load()

    # --- cache -------------------------------------------------------------
    def _load(self):
        try:
            data = json.loads(self.cache_path.read_text())
        except (OSError, ValueError):
            return
        self.lists = data.get("lists", [])
        self._tasks = data.get("tasks", [])
        self.pending = data.get("pending", [])
        self.failed_ops = data.get("failed_ops", [])
        self._local_seq = max([int(t["id"][6:]) for t in self._tasks if t["id"].startswith("local:")] or [0])

    def _save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"lists": self.lists, "tasks": self._tasks, "pending": self.pending,
                                   "failed_ops": self.failed_ops}, ensure_ascii=False))
        os.replace(tmp, self.cache_path)

    # --- reading -----------------------------------------------------------
    @property
    def multi_list(self) -> bool:
        return len(self.lists) > 1

    def _bucket(self, due: str) -> str:
        if not due:
            return "undated"
        d, today = date.fromisoformat(due), self.today()
        if d < today:
            return "overdue"
        if d == today:
            return "today"
        return "week" if d <= today + timedelta(days=7) else "later"

    def tasks(self) -> list[dict]:
        order = {"overdue": 0, "today": 1, "week": 2, "later": 3, "undated": 4}
        out = [dict(t, bucket=self._bucket(t["due"])) for t in self._tasks]
        return sorted(out, key=lambda t: (order[t["bucket"]], t["due"]))

    def new_item(self, query: str) -> dict | None:
        """Preview of the task "t <title> [due date]" would create."""
        q = " ".join(query.split())
        if not q.startswith("t ") or not q[2:].strip():
            return None
        today = self.today()
        title, due = self.dates.parse_trailing_date(q[2:], today)
        if due:
            desc = self.dates.format_day(due)
        else:
            # A date in a language that is not read stays in the title: say which ones are read.
            read = format_list(self.dates.languages, locale=self.dates.display) if self.dates.languages else _("no language")
            # Translators: {languages} is a list of language codes ("fr and en"); date_languages is the config.json
            # key, not translated.
            desc = _("No due date · dates read in {languages} (date_languages)").format(languages=read)
        return {"group": "agenda", "id": "task:new", "name": _("Create task: {title}").format(title=title),
                "description": desc, "icon": "list-add-symbolic", "kind": "new-task", "url": ""}

    def search(self, query: str) -> list[dict]:
        return [{"group": "agenda", "id": f"task:{t['list']}:{t['id']}", "name": t["title"],
                 "description": self.dates.format_day(date.fromisoformat(t["due"])) if t["due"] else t["list_title"],
                 "icon": "checkbox-symbolic", "kind": "task", "url": t["link"]}
                for t in self.tasks() if matches(query, t["title"])]

    # --- network ------------------------------------------------------------
    def _fetch(self):
        base = self.api.tasks_base
        lists = [{"id": l["id"], "title": l.get("title", "")}
                 for l in self.api.get(f"{base}/users/@me/lists").get("items", [])]
        tasks = []
        for l in lists:
            token = None
            while True:
                params = {"showCompleted": "false", "showHidden": "false", "maxResults": "100"}
                if token:
                    params["pageToken"] = token
                page = self.api.get(f"{base}/lists/{quote(l['id'], safe='')}/tasks", params)
                for t in page.get("items", []):
                    tasks.append(self._from_api(t, l))
                token = page.get("nextPageToken")
                if not token:
                    break
        return lists, tasks

    @staticmethod
    def _from_api(t: dict, lst: dict) -> dict:
        return {"id": t["id"], "list": lst["id"], "list_title": lst.get("title", ""),
                "title": t.get("title", ""), "due": (t.get("due") or "")[:10],
                "link": t.get("webViewLink") or DEFAULT_LINK}

    def _send(self, op: dict):
        base = self.api.tasks_base
        if op["op"] == "complete":
            self.api.patch(f"{base}/lists/{quote(op['list'], safe='')}/tasks/{quote(op['id'], safe='')}", {"status": "completed"})
            return None
        body = {"title": op["title"]}
        if op.get("due"):
            body["due"] = _due_iso(op["due"])
        return self.api.post(f"{base}/lists/@default/tasks", body)

    def _replay(self) -> bool:
        while self.pending:
            op = self.pending[0]
            try:
                created = self._send(op)
            except OfflineError:
                return False
            except ApiError as e:
                if e.status < 500:
                    log.warning("Action dropped %s: %s", op, e)
                    self.failed_ops.append(op)
                else:
                    return False
            else:
                if op.get("local_id"):
                    self._adopt_server_id(op["local_id"], created["id"])
            self.pending.pop(0)
            self._save()
        return True

    def _adopt_server_id(self, local_id: str, server_id: str):
        """A task created offline now exists at Google: its temporary id is replaced everywhere."""
        for t in self._tasks:
            if t["id"] == local_id:
                t["id"] = server_id
        for op in self.pending:
            if op.get("id") == local_id:
                op["id"] = server_id

    def refresh(self) -> bool:
        with self._lock:
            return self._refresh()

    def _refresh(self) -> bool:
        before = (self.lists, self._tasks)
        try:
            if not self._replay():
                self.online = False
                return False
            lists, tasks = self._fetch()
        except OfflineError:
            self.online = False
            return False
        self.online = True
        self.lists, self._tasks = lists, tasks
        self._save()
        return (self.lists, self._tasks) != before

    def take_failed_ops(self) -> list[dict]:
        with self._lock:
            ops, self.failed_ops = self.failed_ops, []
            self._save()
            return ops

    # --- actions -----------------------------------------------------------
    def complete(self, list_id: str, task_id: str) -> None:
        with self._lock:
            self._complete(list_id, task_id)

    def _complete(self, list_id: str, task_id: str) -> None:
        idx = next((i for i, t in enumerate(self._tasks) if t["list"] == list_id and t["id"] == task_id), None)
        removed = self._tasks.pop(idx) if idx is not None else None
        if task_id.startswith("local:"):
            # Never created at Google (the replay replaces the id as soon as it is created): dropping its
            # pending creation is enough, there is nothing to complete on the server.
            self.pending = [op for op in self.pending if op.get("local_id") != task_id]
            self._save()
            return
        op = {"op": "complete", "list": list_id, "id": task_id}
        try:
            self._send(op)
            self.online = True
        except OfflineError:
            self.online = False
            self.pending.append(op)
        except Exception:
            if removed:
                self._tasks.insert(idx, removed)
            raise
        finally:
            self._save()

    def add(self, text: str) -> dict:
        with self._lock:
            return self._add(text)

    def _add(self, text: str) -> dict:
        title, due = self.dates.parse_trailing_date(text, self.today())
        due_s = due.isoformat() if due else ""
        op = {"op": "add", "title": title, "due": due_s}
        default = self.lists[0] if self.lists else {"id": "@default", "title": ""}
        try:
            created = self._send(op)
            self.online = True
            t = self._from_api(created, default)
        except OfflineError:
            self.online = False
            self._local_seq += 1
            local_id = f"local:{self._local_seq}"
            self.pending.append(dict(op, local_id=local_id))
            t = {"id": local_id, "list": default["id"], "list_title": default["title"],
                 "title": title, "due": due_s, "link": DEFAULT_LINK}
        self._tasks.append(t)
        self._save()
        return dict(t, bucket=self._bucket(t["due"]))
