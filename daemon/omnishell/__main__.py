"""omnishell-daemon: entry point (systemd user service, D-Bus activatable)."""
import locale
import logging
import signal
from functools import partial
from pathlib import Path

from gi.repository import Gio, GLib, GLibUnix

from .calendar import CalendarStore
from .chrome import ChromeIndex, find_chrome_root
from .config import DEFAULT_MODEL, load_config
from .dates import DateReader
from .goa import GoaTokens
from .google_api import GoogleApi
from .notify import Notifier
from .omnibox import load_keywords
from .service import Deps, HubService
from .session_locale import google_hl, session_locale, wikipedia_language
from .suggest import SuggestionSwitch, find_schema, schema_dirs, suggest
from .tasks import TaskStore
from .voice import Listener, MicSource
from .whisper import WhisperServer, default_threads

log = logging.getLogger("omnishell")

# XDG base directories, as GLib reads them (XDG_CONFIG_HOME and friends, else ~/.config, ~/.cache…).
CONFIG = Path(GLib.get_user_config_dir()) / "omnishell"
CACHE = Path(GLib.get_user_cache_dir()) / "omnishell"
STATE = Path(GLib.get_user_state_dir()) / "omnishell"
DATA = Path(GLib.get_user_data_dir()) / "omnishell"


def open_uri(uri: str) -> None:
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error as e:
        logging.warning("cannot open %s: %s", uri, e.message)


def spawn(argv: list) -> None:
    Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)


def watch_network(callback) -> None:
    """callback(True) when full connectivity comes back, callback(False) when it is lost."""
    monitor = Gio.NetworkMonitor.get_default()

    def online():
        return monitor.get_network_available() and monitor.get_connectivity() == Gio.NetworkConnectivity.FULL

    state = {"online": online()}

    def changed(*_):
        now = online()
        if now != state["online"]:
            state["online"] = now
            callback(now)

    monitor.connect("network-changed", changed)
    monitor.connect("notify::connectivity", changed)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        locale.setlocale(locale.LC_TIME, "")  # numeric date order of the session (dates.session_date_order)
    except locale.Error as e:
        log.warning("Session LC_TIME locale unavailable (%s): numeric dates use dateparser's default order", e)
    cfg = load_config(CONFIG / "config.json")
    dates = DateReader.from_session(list(cfg["date_languages"]))
    ui = session_locale("LC_MESSAGES")
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    tokens = GoaTokens(bus)
    api = GoogleApi(tokens)
    model = Path(cfg["whisper_model"]).expanduser() if cfg["whisper_model"] else DATA / "models" / DEFAULT_MODEL
    whisper = WhisperServer(model, language=cfg["whisper_language"], binary=cfg["whisper_server"],
                            threads=int(cfg["whisper_threads"]) or default_threads())
    chrome_root = Path(cfg["chrome_dir"]).expanduser() if cfg["chrome_dir"] else find_chrome_root()
    deps = Deps(
        tokens=tokens, chrome=ChromeIndex(root=chrome_root, cache_dir=CACHE),
        task_store=TaskStore(api, CACHE / "tasks.json", dates), calendar=CalendarStore(api, dates),
        keywords=load_keywords(CONFIG / "keywords.json", wikipedia_language(ui)), suggest=partial(suggest, hl=google_hl(ui)),
        suggestions_enabled=SuggestionSwitch(find_schema(schema_dirs())),
        listener_factory=lambda on_state: Listener(MicSource, whisper.transcribe, on_state),
        open_uri=open_uri, spawn=spawn, notify=Notifier(bus, open_uri), state_dir=STATE,
        summary_hour=int(cfg["summary_hour"]), whisper_loaded=lambda: whisper.running,
        watch_network=watch_network)
    loop = GLib.MainLoop()
    service = HubService(bus, deps)
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, sig, lambda *_: (loop.quit(), False)[1])
    try:
        loop.run()
    finally:
        service.close()
        whisper.close()


if __name__ == "__main__":
    main()
