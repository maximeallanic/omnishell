import json
import tempfile
import unittest
from pathlib import Path

from omnishell.omnibox import google_items, load_keywords, looks_like_url, parse_suggest


class TestOmnibox(unittest.TestCase):
    def test_url(self):
        self.assertEqual(looks_like_url("github.com/foo"), "https://github.com/foo")
        self.assertEqual(looks_like_url("fr.wikipedia.org"), "https://fr.wikipedia.org")
        self.assertEqual(looks_like_url("localhost:8080"), "http://localhost:8080")
        self.assertEqual(looks_like_url("пример.рф"), "https://пример.рф")
        self.assertEqual(looks_like_url("例子.中国"), "https://例子.中国")
        self.assertEqual(looks_like_url("xn--e1afmkfd.xn--p1ai"), "https://xn--e1afmkfd.xn--p1ai")
        self.assertEqual(looks_like_url("http://x.org/a b"), None)
        self.assertEqual(looks_like_url("https://x.org/a"), "https://x.org/a")
        for no in ("foo bar", "3.14", "foo", "a.b."):
            self.assertIsNone(looks_like_url(no), no)

    def test_parse_suggest_latin1_and_utf8(self):
        body = '["cafe",["café crème","cafetière"]]'
        self.assertEqual(parse_suggest(body.encode("latin-1"), "text/javascript; charset=ISO-8859-1"),
                         ["café crème", "cafetière"])
        self.assertEqual(parse_suggest(body.encode(), "application/json"), ["café crème", "cafetière"])
        self.assertEqual(parse_suggest(b"<html>", "text/html"), [])

    def test_google_items_order(self):
        kw = load_keywords(None, "fr")
        items = google_items("github.com", ["github.com", "github copilot", "a", "b", "c"], kw)
        self.assertEqual([i["kind"] for i in items],
                         ["url", "search", "gemini", "search", "search", "search", "search"])
        self.assertEqual(items[1]["name"], "Search “github.com” on Google")
        self.assertEqual(items[2]["name"], "Ask Gemini: “github.com”")
        self.assertNotIn("github.com", [i["name"] for i in items[3:]])
        self.assertEqual(len({i["id"] for i in items}), len(items))
        for i in items:
            self.assertEqual(i["group"], "google")
            self.assertEqual(set(i), {"group", "id", "name", "description", "icon", "kind", "url"})

    def test_keyword_first(self):
        items = google_items("yt chat noir", [], load_keywords(None, "fr"))
        self.assertEqual(items[0]["name"], "YouTube: chat noir")
        self.assertEqual(items[0]["url"], "https://www.youtube.com/results?search_query=chat+noir")
        self.assertNotIn("url", [i["kind"] for i in items[1:]])

    def test_wikipedia_follows_session_language(self):
        for lang in ("fr", "ja", "ar"):
            items = google_items("w chat noir", [], load_keywords(None, lang))
            self.assertEqual(items[0]["url"], f"https://{lang}.wikipedia.org/w/index.php?search=chat+noir")

    def test_keyword_needs_text(self):
        items = google_items("yt ", [], load_keywords(None, "fr"))
        self.assertNotIn("google:kw:yt", [i["id"] for i in items])

    def test_short_query(self):
        self.assertEqual(google_items("ab", [], load_keywords(None, "fr")), [])

    def test_minimum_length_follows_the_script(self):
        kw = load_keywords(None, "fr")
        for q in ("猫", "東京", "서울", "мир", "سلام", "été"):
            self.assertTrue(google_items(q, [], kw), q)
        for q in ("a", "é", "м"):
            self.assertEqual(google_items(q, [], kw), [], q)

    def test_user_keywords_override_and_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "keywords.json")
            p.write_text(json.dumps({"yt": ["YT", "https://y/{q}"], "dd": ["DDG", "https://ddg/?q={q}"]}))
            kw = load_keywords(p, "fr")
            self.assertEqual(kw["yt"], ("YT", "https://y/{q}"))
            self.assertIn("dd", kw)
            self.assertIn("w", kw)
            p.write_text("{oops")
            with self.assertLogs(level="WARNING"):
                self.assertIn("yt", load_keywords(p, "fr"))
