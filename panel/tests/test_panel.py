"""Drawer tests: they start the real GTK/WebKit window (a Wayland display is required: run them through tests/run.sh)."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
PAGES = HERE / "pages"
PANEL = HERE.parent


def run_panel(page, *args, timeout=40, url=None, env_extra=None):
    env = dict(os.environ, PYTHONPATH=str(PANEL), **(env_extra or {}))
    p = subprocess.run([sys.executable, "-W", "ignore", "-m", "google_hub_panel", "--test",
                        "--url", url or (PAGES / page).as_uri().replace("%23", "#"), *args],
                       capture_output=True, text=True, timeout=timeout, env=env)
    # Passed on to the test's stderr: run.sh runs unittest with -b, which shows it only when the test fails.
    sys.stderr.write(f"--- panel stderr ({url or page}, exit {p.returncode}) ---\n{p.stderr}")
    return p.stdout


@unittest.skipUnless(os.environ.get("WAYLAND_DISPLAY"), "Wayland display required (run tests/run.sh)")
class TestPanel(unittest.TestCase):
    ALLOW = ("--allow-origin", "file:///*")

    def test_ask_inserts_and_sends(self):
        self.assertIn("TITLE: DONE sent=bonjour", run_panel("ask_ok.html", "--ask-on-load", "bonjour"))

    def test_ask_send_button_found_without_label(self):
        # No send-button class and a Japanese label: the Material icon name alone must identify the button.
        self.assertIn("TITLE: DONE sent=bonjour", run_panel("ask_icon.html", "--ask-on-load", "bonjour"))

    def test_ask_missing_composer(self):
        out = run_panel("ask_missing.html", "--ask-on-load", "bonjour")
        self.assertIn("ASK-RESULT: no-composer", out)
        self.assertIn("ASK: false", out)
        self.assertIn("CLIPBOARD: bonjour", out)

    def test_ask_missing_send_button_is_logged(self):
        # An English label alone is not a send-button hook any more: the failed step is reported.
        out = run_panel("ask_no_send.html", "--ask-on-load", "bonjour")
        self.assertIn("ASK-RESULT: no-send-button", out)
        self.assertIn("ASK: false", out)

    def test_page_follows_dark_appearance(self):
        # ADW_DEBUG_COLOR_SCHEME stands in for the system preference (libadwaita's debug override).
        for scheme, expected in (("prefer-dark", "dark"), ("prefer-light", "light")):
            out = run_panel("color_scheme.html", env_extra={"ADW_DEBUG_COLOR_SCHEME": scheme})
            self.assertIn(f"TITLE: DONE {expected}", out)

    def test_probe_composer(self):
        self.assertIn("PROBE: true", run_panel("ask_ok.html", "--probe-on-load"))
        self.assertIn("PROBE: false", run_panel("ask_missing.html", "--probe-on-load"))

    def test_speech_success_sequence(self):
        out = run_panel("speech.html", *self.ALLOW, "--fake-listen", "salut")
        self.assertIn("TITLE: DONE start,audiostart,speechstart,speechend,audioend,result:salut:true,end", out)

    def test_speech_no_speech(self):
        out = run_panel("speech.html", *self.ALLOW, "--fake-listen", "")
        self.assertIn("TITLE: DONE start,audiostart,error:no-speech,end", out)

    def test_speech_network(self):
        out = run_panel("speech.html", *self.ALLOW, "--fake-listen", "error:network")
        self.assertIn("TITLE: DONE start,audiostart,error:network,end", out)

    def test_speech_abort(self):
        out = run_panel("speech.html#abort", *self.ALLOW, "--fake-listen", "salut")
        self.assertIn("TITLE: DONE start,audiostart,end", out)
        self.assertNotIn("result:", out)

    def test_offline_at_start_loads_when_network_returns(self):
        out = run_panel("ask_missing.html", "--fake-network", "offline,online")
        lines = out.splitlines()
        self.assertIn("NET: offline", lines)
        self.assertIn("NET: online", lines)
        load = [i for i, l in enumerate(lines) if l.startswith("LOAD:")]
        self.assertTrue(load, out)
        self.assertGreater(load[0], lines.index("NET: online"), out)

    def test_failed_load_retried_when_network_returns(self):
        out = run_panel("absent.html", "--fake-network", "online,offline,online")
        self.assertIn("LOADFAILED", out)
        self.assertEqual(sum(1 for l in out.splitlines() if l.startswith("LOAD:")), 2, out)

    def test_polyfill_not_on_other_origins(self):
        self.assertIn("TITLE: DONE nopolyfill", run_panel("speech.html", "--fake-listen", "salut"))
