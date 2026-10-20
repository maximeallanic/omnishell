"""User configuration ($XDG_CONFIG_HOME/google-hub/config.json, default ~/.config/google-hub/config.json)."""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_MODEL = "ggml-small.bin"

DEFAULTS = {"summary_hour": 9,
            # Whisper model file; empty: $XDG_DATA_HOME/google-hub/models/ggml-small.bin (downloaded by install.sh).
            "whisper_model": "",
            # Language spoken to Whisper (ISO 639-1 code such as "fr", "ja"), or "auto" to detect it each time.
            "whisper_language": "auto",
            # whisper.cpp server program: a name looked up in PATH, or an absolute path.
            "whisper_server": "whisper-server",
            # CPU threads given to whisper-server; 0: chosen from the number of CPUs.
            "whisper_threads": 0,
            # Chromium-family profile folder read by the "Chrome" search group; empty: the first of
            # ~/.config/google-chrome, ~/.config/chromium that exists.
            "chrome_dir": "",
            # dateparser language codes read in task due dates and day searches, on top of the
            # session locale ones (e.g. ["en", "de"]).
            "date_languages": []}


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(Path(path).read_text()))
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        log.warning("config.json ignored (%s): %s", path, e)
    return cfg
