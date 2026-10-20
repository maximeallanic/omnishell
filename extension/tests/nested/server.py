"""Local page server of the nested drawer check: a page whose load is held until the driver releases it.

GET /page.html   the drawer page (composer and send button of tests/pages/ask_ok.html); its blocking script /gate.js
                 is answered only after /release, so the load cannot finish before
GET /release     lets every /gate.js through, now and later
GET /hold        holds /gate.js again (next load)
GET /sent?text=  called by the page when its send button is clicked
GET /log         JSON: {"requests": [...paths], "sent": [...texts]}
Usage: server.py PORT_FILE   (binds 127.0.0.1 on a free port, writes the port, serves until killed)
"""
import http.server
import json
import sys
import threading
from urllib.parse import parse_qs, urlparse

PAGE = b"""<!doctype html><meta charset="utf-8"><title>drawer</title>
<style>body { background: #2a6; font: 20px sans-serif; }</style>
<p>drawer page</p>
<rich-textarea><div class="ql-editor" contenteditable="true"></div></rich-textarea>
<button class="send-button"
  onclick="fetch('/sent?text=' + encodeURIComponent(document.querySelector('[contenteditable]').textContent))">send</button>
<script src="/gate.js"></script>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        srv = self.server
        srv.requests.append(self.path)
        if url.path == "/page.html":
            self._send(PAGE, "text/html")
        elif url.path == "/gate.js":
            srv.gate.wait()
            self._send(b"document.title = 'released';", "text/javascript")
        elif url.path == "/release":
            srv.gate.set()
            self._send(b"ok", "text/plain")
        elif url.path == "/hold":
            srv.gate.clear()
            self._send(b"ok", "text/plain")
        elif url.path == "/sent":
            srv.sent.append(parse_qs(url.query).get("text", [""])[0])
            self._send(b"ok", "text/plain")
        elif url.path == "/log":
            self._send(json.dumps({"requests": srv.requests, "sent": srv.sent}).encode(), "application/json")
        else:
            self.send_error(404)

    def _send(self, body, mime):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.gate = threading.Event()
    server.requests, server.sent = [], []
    with open(sys.argv[1], "w") as f:
        f.write(str(server.server_address[1]))
    server.serve_forever()


if __name__ == "__main__":
    main()
