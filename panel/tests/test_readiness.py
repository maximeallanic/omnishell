"""Readiness of the drawer (readiness.py): Show answers when the view has something to show. Real GTK/WebKit window in
test mode, pages served by a local server that can delay or withhold a resource. Run with tests/run.sh (private
headless compositor), never on the live session."""
import http.server
import os
import threading
import time
import unittest
from urllib.parse import parse_qs, urlparse

from .test_panel import PAGES, run_panel

PAGE = b'<!doctype html><meta charset="utf-8"><title>page</title><p>content</p><script src="%s"></script>'


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/slow.html":
            self._send(PAGE % b"/delay.js?ms=1500", "text/html")
        elif url.path == "/hang.html":
            self._send(PAGE % b"/never.js", "text/html")
        elif url.path == "/delay.js":
            time.sleep(int(parse_qs(url.query)["ms"][0]) / 1000)
            self._send(b"document.title = 'late';", "text/javascript")
        elif url.path == "/never.js":
            self.server.released.wait()  # held until the test ends: the load neither finishes nor fails
        else:
            self.send_error(404)

    def _send(self, body, mime):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def index(lines, wanted):
    for i, line in enumerate(lines):
        if line == wanted:
            return i
    raise AssertionError(f"{wanted!r} missing in:\n" + "\n".join(lines))


@unittest.skipUnless(os.environ.get("WAYLAND_DISPLAY"), "graphical session required (tests/run.sh)")
class TestReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.server.released = threading.Event()
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.released.set()
        cls.server.shutdown()
        cls.server.server_close()

    def lines(self, url, *args):
        return run_panel(None, *args, url=url).splitlines()

    def test_show_waits_for_the_load_then_for_a_frame(self):
        lines = self.lines(f"{self.base}/slow.html", "--show-after", "100")
        order = [index(lines, l) for l in ("MAP", "LOAD-EVENT: finished", "FRAME", "SHOW: ready")]
        self.assertEqual(order, sorted(order), lines)

    def test_show_of_a_loaded_page_waits_for_a_frame_only(self):
        lines = self.lines((PAGES / "ask_ok.html").as_uri(), "--show-after", "2000")
        order = [index(lines, l) for l in ("LOAD-EVENT: finished", "MAP", "FRAME", "SHOW: ready")]
        self.assertEqual(order, sorted(order), lines)

    def test_offline_answers_at_once_with_the_status_page(self):
        lines = self.lines((PAGES / "ask_ok.html").as_uri(), "--fake-network", "offline", "--show-after", "200")
        self.assertLess(index(lines, "STATUS: offline"), index(lines, "SHOW: offline"), lines)
        self.assertNotIn("FRAME", lines)
        self.assertFalse([l for l in lines if l.startswith("LOAD:")], lines)

    def test_offline_status_page_leaves_when_the_network_returns(self):
        lines = self.lines((PAGES / "ask_ok.html").as_uri(), "--fake-network", "offline,online",
                           "--show-after", "200", "--quit-after-show", "10000")
        order = [index(lines, l) for l in ("STATUS: offline", "SHOW: offline", "NET: online", "STATUS: web")]
        self.assertEqual(order, sorted(order), lines)

    def test_failed_load_is_retried_by_show_and_answers_failed(self):
        lines = self.lines((PAGES / "absent.html").as_uri(), "--show-after", "1500")
        self.assertEqual(sum(1 for l in lines if l.startswith("LOAD:")), 2, lines)
        self.assertEqual(lines.count("STATUS: failed"), 2, lines)
        self.assertGreater(index(lines, "SHOW: failed"), len(lines) - 1 - lines[::-1].index("STATUS: failed"), lines)
        self.assertNotIn("STATUS: web", lines)

    def test_load_that_never_finishes_answers_stalled(self):
        t0 = time.monotonic()
        lines = self.lines(f"{self.base}/hang.html", "--show-after", "100", "--stall-ms", "2000")
        self.assertIn("SHOW: stalled", lines)
        self.assertNotIn("LOAD-EVENT: finished", lines)
        self.assertGreater(time.monotonic() - t0, 2.0)

    def test_hide_cancels_a_pending_show(self):
        lines = self.lines(f"{self.base}/hang.html", "--show-after", "100", "--hide-after", "1500")
        self.assertIn("SHOW: cancelled", lines)
