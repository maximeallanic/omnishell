"""Minimal HTTP client for the Google APIs (OAuth token provided by GNOME Online Accounts)."""
import json
import socket
import urllib.error
import urllib.request
from urllib.parse import urlencode

from gi.repository import GLib


class OfflineError(Exception):
    pass


class NoAccountError(Exception):
    def __init__(self, message: str = "no usable Google account in GNOME Online Accounts"):
        super().__init__(message)


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"{status} {message}")
        self.status = status
        self.message = message


class GoogleApi:
    def __init__(self, tokens, tasks_base="https://tasks.googleapis.com/tasks/v1",
                 cal_base="https://www.googleapis.com/calendar/v3", timeout=10):
        self.tokens = tokens
        self.tasks_base = tasks_base
        self.cal_base = cal_base
        self.timeout = timeout

    def get(self, url, params=None):
        return self._request("GET", url + ("?" + urlencode(params) if params else ""))

    def post(self, url, body):
        return self._request("POST", url, body)

    def patch(self, url, body):
        return self._request("PATCH", url, body)

    def _request(self, method, url, body=None, retried=False):
        if not self.tokens.has_account():
            raise NoAccountError()
        try:
            token = self.tokens.token()
        except GLib.Error as e:  # GOA: account to sign in again, goa-daemon missing…
            raise NoAccountError(e.message) from None
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            with e:
                return self._http_error(e, method, url, body, retried)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            raise OfflineError(str(e)) from None

    def _http_error(self, e, method, url, body, retried):
        if e.code == 401 and not retried:
            try:
                self.tokens.refresh()
            except GLib.Error as err:  # GOA refuses the credentials: the account must be signed in again
                raise NoAccountError(err.message) from None
            return self._request(method, url, body, retried=True)
        try:
            msg = json.loads(e.read()).get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            msg = ""
        raise ApiError(e.code, msg or e.reason) from None
