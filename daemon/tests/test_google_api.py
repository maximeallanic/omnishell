import unittest

from omnishell.google_api import ApiError, GoogleApi, NoAccountError, OfflineError
from tests.fake_google import FakeGoogle, FakeTokens, closed_port_url


class TestGoogleApi(unittest.TestCase):
    def setUp(self):
        self.g = FakeGoogle()
        self.tokens = FakeTokens()
        self.api = GoogleApi(self.tokens, tasks_base=self.g.url, cal_base=self.g.url, timeout=2)

    def tearDown(self):
        self.g.close()

    def test_bearer_header(self):
        self.g.routes[("GET", "/x")] = (200, {"ok": 1})
        self.assertEqual(self.api.get(self.g.url + "/x", {"a": "b c"}), {"ok": 1})
        self.assertEqual(self.g.requests[0]["auth"], "Bearer tok0")
        self.assertEqual(self.g.requests[0]["query"], {"a": "b c"})

    def test_401_refresh_once(self):
        self.g.routes[("GET", "/x")] = [(401, {}), (200, {"ok": 1})]
        self.assertEqual(self.api.get(self.g.url + "/x"), {"ok": 1})
        self.assertEqual(self.tokens.refreshed, 1)
        self.assertEqual(self.g.requests[1]["auth"], "Bearer tok1")

    def test_401_twice_raises(self):
        self.g.routes[("GET", "/x")] = (401, {"error": {"message": "nope"}})
        with self.assertRaises(ApiError) as cm:
            self.api.get(self.g.url + "/x")
        self.assertEqual(cm.exception.status, 401)
        self.assertEqual(self.tokens.refreshed, 1)

    def test_post_patch_send_json(self):
        self.g.routes[("POST", "/p")] = (200, {"id": "1"})
        self.g.routes[("PATCH", "/p")] = (200, {"id": "1"})
        self.api.post(self.g.url + "/p", {"title": "é"})
        self.api.patch(self.g.url + "/p", {"status": "completed"})
        self.assertEqual([r["body"] for r in self.g.requests], [{"title": "é"}, {"status": "completed"}])

    def test_offline(self):
        with self.assertRaises(OfflineError):
            self.api.get(closed_port_url() + "/x")

    def test_goa_error_maps_to_no_account(self):
        from gi.repository import GLib
        def boom():
            raise GLib.Error("GoaError: NotAuthorized")
        self.tokens.token = boom
        with self.assertRaises(NoAccountError):
            self.api.get(self.g.url + "/x")

    def test_goa_refusing_credentials_maps_to_no_account(self):
        from gi.repository import GLib
        def refused():
            raise GLib.Error("GoaError: NotAuthorized")
        self.tokens.refresh = refused
        self.g.routes[("GET", "/x")] = (401, {})
        with self.assertRaises(NoAccountError):
            self.api.get(self.g.url + "/x")
        self.assertEqual(len(self.g.requests), 1)

    def test_no_account(self):
        self.tokens.account = False
        with self.assertRaises(NoAccountError):
            self.api.get(self.g.url + "/x")
        self.assertEqual(self.g.requests, [])
