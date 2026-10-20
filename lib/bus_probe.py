#!/usr/bin/env python3
"""Read-only probes of an installed Google Hub, for verify.sh. Prints one JSON value on stdout.

Usage: bus_probe.py status | search TERM | tasks | extension-state UUID | shell-state | composer
       bus_probe.py transcribe DAEMON_DIR WAV
Exit status 0 when the probe got an answer, 1 with the error on stderr otherwise."""
import json
import sys

from gi.repository import Gio, GLib

HUB = ("io.github.maximeallanic.GoogleHub", "/io/github/maximeallanic/GoogleHub", "io.github.maximeallanic.GoogleHub")
SHELL = ("io.github.maximeallanic.GoogleHubShell", "/io/github/maximeallanic/GoogleHubShell",
         "io.github.maximeallanic.GoogleHubShell")
PANEL = ("io.github.maximeallanic.GoogleHubPanel", "/io/github/maximeallanic/GoogleHubPanel",
         "io.github.maximeallanic.GoogleHubPanel")
EXTENSIONS = ("org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions", "org.gnome.Shell.Extensions")


def call(target, method, args=None, timeout_ms=10000):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    name, path, iface = target
    reply = bus.call_sync(name, path, iface, method, args, None, Gio.DBusCallFlags.NONE, timeout_ms, None)
    return reply.unpack()


def transcribe(daemon_dir, wav):
    sys.path.insert(0, daemon_dir)
    from pathlib import Path

    import google_hub
    from google_hub.config import DEFAULT_MODEL, load_config
    from google_hub.whisper import WhisperServer
    if not google_hub.__file__.startswith(daemon_dir + "/"):
        raise RuntimeError(f"google_hub loaded from {google_hub.__file__}, not from {daemon_dir}")
    config = Path(GLib.get_user_config_dir()) / "google-hub" / "config.json"
    cfg = load_config(config)
    model = (Path(cfg["whisper_model"]).expanduser() if cfg["whisper_model"]
             else Path(GLib.get_user_data_dir()) / "google-hub" / "models" / DEFAULT_MODEL)
    server = WhisperServer(model, language="auto", binary=cfg["whisper_server"], idle_s=60)
    try:
        return server.transcribe(Path(wav).read_bytes())
    finally:
        server.close()


def main(argv):
    cmd, args = (argv[1], argv[2:]) if len(argv) > 1 else ("", [])
    if cmd == "status":
        props = ("org.freedesktop.DBus.Properties",)
        value = call(HUB[:2] + props, "Get", GLib.Variant("(ss)", (HUB[2], "Status")))[0]
    elif cmd == "search" and len(args) == 1:
        items = call(HUB, "Search", GLib.Variant("(as)", ([args[0]],)))[0]
        value = sorted({item.get("group", "") for item in items})
    elif cmd == "tasks":
        value = len(call(HUB, "ListTasks")[0])
    elif cmd == "extension-state" and len(args) == 1:
        # Numeric state (misc/extensionUtils.js ExtensionState): never the translated label of `gnome-extensions info`.
        value = call(EXTENSIONS, "GetExtensionInfo", GLib.Variant("(s)", (args[0],)))[0].get("state")
    elif cmd == "shell-state":
        value = json.loads(call(SHELL, "GetState")[0])
    elif cmd == "composer":
        value = call(PANEL, "ProbeComposer", timeout_ms=30000)[0]
    elif cmd == "transcribe" and len(args) == 2:
        value = transcribe(*args)
    else:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except GLib.Error as e:
        print(e.message, file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 - verify.sh reports any failure as a failed check, with this message
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
