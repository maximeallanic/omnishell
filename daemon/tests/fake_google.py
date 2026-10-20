"""Fake Google server (Tasks + Calendar) for tests: programmable routes, recorded requests."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit


class FakeGoogle:
    def __init__(self):
        self.routes = {}      # (method, path) -> callable(req) -> (status, dict) | list of answers
        self.requests = []
        self.delay = 0.0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _handle(self):
                parts = urlsplit(self.path)
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n)) if n else None
                req = {"method": self.command, "path": unquote(parts.path),
                       "query": {k: v[0] for k, v in parse_qs(parts.query).items()},
                       "body": body, "auth": self.headers.get("Authorization")}
                fake.requests.append(req)
                if fake.delay:
                    time.sleep(fake.delay)
                route = fake.routes.get((self.command, unquote(parts.path)))
                if route is None:
                    status, payload = 404, {"error": {"message": "not found"}}
                elif isinstance(route, list):
                    status, payload = route.pop(0) if len(route) > 1 else route[0]
                elif callable(route):
                    status, payload = route(req)
                else:
                    status, payload = route
                data = json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = do_POST = do_PATCH = _handle

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def made(self, method, path):
        return [r for r in self.requests if r["method"] == method and r["path"] == path]


class FakeTokens:
    def __init__(self, account=True):
        self.account = account
        self.refreshed = 0
        self.watchers = []

    def watch(self, callback):
        self.watchers.append(callback)

    def has_account(self):
        return self.account

    def token(self):
        return f"tok{self.refreshed}"

    def refresh(self):
        self.refreshed += 1


def closed_port_url():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"
