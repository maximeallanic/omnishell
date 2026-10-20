"""Google search suggestions, and the user's switch that allows them (GSettings key "search-suggestions").

The switch lives in the Shell extension's schema, edited in its preferences window. The daemon is the process that
sends the request, so it reads the switch itself rather than trusting each caller to pass it along: when the key is
false, or when the schema cannot be found, no request leaves the computer.
"""
import logging
import urllib.parse
import urllib.request
from pathlib import Path

from gi.repository import Gio, GLib

from .omnibox import parse_suggest

log = logging.getLogger(__name__)

SUGGEST_URL = "https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&q={q}"
EXTENSION_UUID = "google-hub@maximeallanic.github.io"
SCHEMA_ID = "org.gnome.shell.extensions.google-hub"
KEY = "search-suggestions"


def suggest(q: str, hl: str) -> list[str]:
    url = SUGGEST_URL.format(hl=urllib.parse.quote(hl), q=urllib.parse.quote(q))
    try:
        with urllib.request.urlopen(url, timeout=1.5) as r:
            return parse_suggest(r.read(), r.headers.get("Content-Type", ""))
    except OSError:
        return []


def schema_dirs() -> list[Path]:
    """The extension's schemas/ folders, in the order GNOME Shell looks the extension up: user, then system."""
    roots = [GLib.get_user_data_dir(), *GLib.get_system_data_dirs()]
    return [Path(root, "gnome-shell", "extensions", EXTENSION_UUID, "schemas") for root in roots]


def find_schema(dirs: list[Path]) -> Gio.SettingsSchema | None:
    """The extension's schema: compiled next to the extension (as Extension.getSettings() finds it) or installed
    system-wide by a distribution package."""
    default = Gio.SettingsSchemaSource.get_default()
    for d in dirs:
        if not (d / "gschemas.compiled").is_file():
            continue
        try:
            source = Gio.SettingsSchemaSource.new_from_directory(str(d), default, False)
        except GLib.Error as e:
            log.warning("unreadable compiled schemas in %s: %s", d, e.message)
            continue
        schema = source.lookup(SCHEMA_ID, False)
        if schema is not None:
            return schema
    return default.lookup(SCHEMA_ID, True) if default else None


class SuggestionSwitch:
    """Current value of the "search-suggestions" key, kept up to date from the main loop.

    Search runs on worker threads: they read a plain attribute instead of calling GSettings, which is not meant to
    be shared across threads. Construct it on the thread that runs the main loop.
    """

    def __init__(self, schema: Gio.SettingsSchema | None, backend: Gio.SettingsBackend | None = None):
        self.enabled = False
        self._settings = None
        if schema is None or not schema.has_key(KEY):
            log.warning("schema %s with key %s not found: Google suggestions stay off until the extension is "
                        "installed and the daemon restarted", SCHEMA_ID, KEY)
            return
        self._settings = Gio.Settings.new_full(schema, backend, None)
        self._settings.connect(f"changed::{KEY}", lambda *_: self._read())
        self._read()

    def _read(self):
        self.enabled = self._settings.get_boolean(KEY)
        log.info("Google suggestions %s", "on" if self.enabled else "off")

    def __call__(self) -> bool:
        return self.enabled
