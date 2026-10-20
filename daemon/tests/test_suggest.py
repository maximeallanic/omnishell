import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from gi.repository import Gio, GLib

from google_hub.suggest import EXTENSION_UUID, KEY, SCHEMA_ID, SuggestionSwitch, find_schema

SCHEMA_XML = (Path(__file__).resolve().parents[2] / "extension" / EXTENSION_UUID / "schemas"
              / f"{SCHEMA_ID}.gschema.xml")


def drain():
    ctx = GLib.MainContext.default()
    while ctx.iteration(False):
        pass


@unittest.skipUnless(shutil.which("glib-compile-schemas"), "glib-compile-schemas missing")
class TestSuggestionSwitch(unittest.TestCase):
    """The daemon reads the extension's own schema, compiled next to it as install.sh does."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.schemas = Path(self.tmp.name, "schemas")
        self.schemas.mkdir()
        shutil.copy(SCHEMA_XML, self.schemas)
        subprocess.run(["glib-compile-schemas", "--strict", str(self.schemas)], check=True)
        self.backend = Gio.memory_settings_backend_new()  # never the user's real dconf database

    def tearDown(self):
        self.tmp.cleanup()

    def switch(self):
        return SuggestionSwitch(find_schema([Path(self.tmp.name, "absent"), self.schemas]), self.backend)

    def test_on_by_default(self):
        self.assertTrue(self.switch()())

    def test_follows_the_key(self):
        sw = self.switch()
        other = Gio.Settings.new_full(find_schema([self.schemas]), self.backend, None)  # the preferences window
        other.set_boolean(KEY, False)
        drain()
        self.assertFalse(sw())
        other.set_boolean(KEY, True)
        drain()
        self.assertTrue(sw())

    def test_off_when_the_schema_is_missing(self):
        # Unknown choice: no request rather than one the user may have refused.
        self.assertFalse(SuggestionSwitch(None)())

    def test_off_when_the_key_is_missing(self):
        old = self.schemas / f"{SCHEMA_ID}.gschema.xml"
        old.write_text(old.read_text().replace(f'name="{KEY}"', 'name="renamed-key"'))
        subprocess.run(["glib-compile-schemas", "--strict", str(self.schemas)], check=True)
        self.assertFalse(SuggestionSwitch(find_schema([self.schemas]), self.backend)())


if __name__ == "__main__":
    unittest.main()
